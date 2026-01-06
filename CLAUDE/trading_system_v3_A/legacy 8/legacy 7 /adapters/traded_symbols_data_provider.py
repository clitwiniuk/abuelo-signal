# adapters/traded_symbols_data_provider.py
"""
Data provider for backtesting using symbols that have been actually traded.
Extends CSVDataProvider to automatically work with symbols from trading_data.db
and download missing historical data when needed.
"""

import sqlite3
import pandas as pd
import logging
import json
import requests
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

from .csv_data_provider import CSVDataProvider
from core.interfaces import DataProviderError


class PolygonDownloader:
    """
    Polygon.io downloader with rate limiting for free tier accounts
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.session = requests.Session()
        self.calls_made = 0
        self.last_batch_time = None
        self.free_tier_limit = 5  # 5 calls per minute for free tier
        self.wait_time = 65       # 65 seconds wait between batches
        
    def _check_rate_limit(self):
        """Check and respect rate limiting for free tier"""
        if self.calls_made >= self.free_tier_limit:
            if self.last_batch_time:
                elapsed = time.time() - self.last_batch_time
                if elapsed < self.wait_time:
                    wait_time = self.wait_time - elapsed
                    print(f"⏳ Rate limit reached. Waiting {wait_time:.0f}s...")
                    time.sleep(wait_time)
            
            self.calls_made = 0
            self.last_batch_time = time.time()
    
    def get_ticker_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Download 1-minute data for a specific ticker"""
        self._check_rate_limit()
        
        # URL for 1-minute aggregates
        url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/1/minute/{start_date}/{end_date}"
        
        params = {
            'apikey': self.api_key,
            'adjusted': 'true'
        }
        
        max_retries = 3
        retry_count = 0
        retry_delay = 12  # seconds
        
        while retry_count < max_retries:
            try:
                print(f"📥 Downloading {symbol}... ", end="")
                
                response = self.session.get(url, params=params, timeout=30)
                self.calls_made += 1
                
                # Handle rate limit error 429
                if response.status_code == 429:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"⏳ Rate limit (429). Retry {retry_count}/{max_retries} in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Double wait time on each retry
                        continue
                    else:
                        print(f"❌ Error 429 after {max_retries} retries")
                        return pd.DataFrame()
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'results' in data and data['results']:
                        df = pd.DataFrame(data['results'])
                        
                        # Convert Unix timestamp to datetime with UTC timezone
                        df['timestamp'] = pd.to_datetime(df['t'], unit='ms').dt.tz_localize('UTC')
                        
                        # Rename columns to standard format
                        column_mapping = {
                            'o': 'open',
                            'h': 'high', 
                            'l': 'low',
                            'c': 'close',
                            'v': 'volume'
                        }
                        df = df.rename(columns=column_mapping)
                        
                        # Select only required columns
                        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                        
                        # Filter market hours only (9:30-16:00 EST)
                        df = self._filter_market_hours(df)
                        
                        print(f"✅ {len(df)} bars")
                        return df
                    else:
                        print("❌ No data")
                        return pd.DataFrame()
                else:
                    print(f"❌ Error {response.status_code}")
                    return pd.DataFrame()
                
            except Exception as e:
                print(f"❌ Error: {str(e)[:40]}")
                return pd.DataFrame()
    
    def _filter_market_hours(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter data to include only regular market hours (9:30-16:00 ET)"""
        if df.empty:
            return df
        
        try:
            # Handle timezone conversion - data comes in Spain timezone
            if df['timestamp'].dt.tz is None:
                # Data is in Spain timezone (Europe/Madrid), convert to ET
                df['timestamp'] = df['timestamp'].dt.tz_localize('Europe/Madrid')
                
            # Convert to ET timezone for filtering and processing
            df_et = df.copy()
            df_et['timestamp'] = df_et['timestamp'].dt.tz_convert('US/Eastern')
            
            # Filter market hours (9:30-16:00 ET, weekdays only)
            market_hours = (
                (df_et['timestamp'].dt.time >= pd.Timestamp('09:30').time()) &
                (df_et['timestamp'].dt.time <= pd.Timestamp('16:00').time()) &
                (df_et['timestamp'].dt.weekday < 5)  # Only weekdays
            )
            
            # Return original df with UTC timestamps but filtered data
            filtered_df = df[market_hours].copy()
            
            # Convert back to naive datetime in ET for CSV storage
            # CSVs will be stored with ET timestamps (no timezone info)
            filtered_df['timestamp'] = df_et[market_hours]['timestamp'].dt.tz_localize(None)
            
            return filtered_df
        except Exception as e:
            print(f"Error filtering market hours: {str(e)}")
            return df


class TradedSymbolsDataProvider(CSVDataProvider):
    """
    Data provider that works with symbols that have been actually traded.
    Automatically queries trading_data.db for traded symbols and downloads
    missing CSV data when needed.
    """
    
    def __init__(self, 
                 db_path: str = "trading_data.db", 
                 data_path: str = "data/backtesting_csv",
                 auto_download: bool = True,
                 days_history: int = 90):
        """
        Initialize TradedSymbolsDataProvider
        
        Args:
            db_path: Path to trading database
            data_path: Directory to store CSV files
            auto_download: Whether to automatically download missing data
            days_history: How many days of history to download
        """
        # Initialize parent CSVDataProvider
        super().__init__(data_path=data_path, auto_load=False)
        
        # Load Polygon.io API key
        self.polygon_api_key = self._load_polygon_api_key()
        self.polygon_downloader = None
        
        if self.polygon_api_key and auto_download:
            self.polygon_downloader = PolygonDownloader(self.polygon_api_key)
            self.logger.info("✅ Polygon.io downloader initialized")
        elif auto_download:
            self.logger.warning("⚠️  Auto-download enabled but no Polygon.io API key found")
        
        self.db_path = db_path
        self.auto_download = auto_download
        self.days_history = days_history
        self.logger = logging.getLogger("TradedSymbolsDataProvider")
        
        # Create backtesting data directory
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Track symbols from database
        self._traded_symbols: Set[str] = set()
        self._symbols_with_data: Set[str] = set()
        self._missing_symbols: Set[str] = set()
        self._symbol_trade_dates: Dict[str, List[str]] = {}
        
        self.logger.info(f"🎯 TRADED SYMBOLS DATA PROVIDER INITIALIZED")
        self.logger.info(f"   📊 Database: {db_path}")
        self.logger.info(f"   📂 CSV Data: {data_path}")
        self.logger.info(f"   📥 Auto-download: {auto_download}")
        self.logger.info(f"   📅 History: {days_history} days")
    
    def _load_polygon_api_key(self) -> str:
        """Load Polygon.io API key from various sources"""
        # 1. Try environment variable
        api_key = os.getenv('POLYGON_API_KEY')
        if api_key:
            return api_key
        
        # 2. Try config file (check multiple locations)
        config_paths = [
            Path("config/polygon_config.json"),  # From project root
            Path("../config/polygon_config.json"),  # From backtesting/ dir
            Path("polygon_config.json"),  # Legacy location in root
            Path("../polygon_config.json")  # Legacy from backtesting/ dir
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        api_key = config.get('polygon_api_key')
                        if api_key:
                            self.logger.info(f"🔑 Found API key in: {config_path}")
                            return api_key
                except Exception as e:
                    self.logger.warning(f"Could not load config file {config_path}: {e}")
        
        return None
    
    async def connect(self) -> bool:
        """Connect and initialize data"""
        try:
            # Load traded symbols from database
            self._load_traded_symbols()
            
            # Scan existing CSV data
            self._scan_available_data()
            
            # Find missing symbols
            self._identify_missing_symbols()
            
            # Auto-download missing data if enabled
            if self.auto_download and self._missing_symbols:
                await self._download_missing_data()
                
                # Re-scan for available symbols after download
                self._scan_available_symbols()
                self._identify_missing_symbols()
            
            self._connected = True
            
            self.logger.info(f"✅ Connected - {len(self._traded_symbols)} traded symbols")
            self.logger.info(f"   📊 Available: {len(self._symbols_with_data)} symbols")
            if self._missing_symbols:
                self.logger.info(f"   ❌ Missing: {len(self._missing_symbols)} symbols")
            else:
                self.logger.info(f"   ✅ All symbols have data!")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            return False
    
    def _load_traded_symbols(self):
        """Load symbols and their specific trading dates from database"""
        try:
            if not Path(self.db_path).exists():
                self.logger.warning(f"Database not found: {self.db_path}")
                return
            
            with sqlite3.connect(self.db_path) as conn:
                # Get symbols and their specific trading dates
                query = """
                SELECT symbol, DATE(entry_time) as trade_date
                FROM trades 
                WHERE status = 'CLOSED' 
                  AND pnl IS NOT NULL
                  AND entry_time IS NOT NULL
                GROUP BY symbol, DATE(entry_time)
                ORDER BY symbol, trade_date
                """
                
                cursor = conn.execute(query)
                results = cursor.fetchall()
                
                # Store symbols and their trading dates
                self._symbol_trade_dates = {}
                for symbol, trade_date in results:
                    if symbol not in self._symbol_trade_dates:
                        self._symbol_trade_dates[symbol] = []
                    self._symbol_trade_dates[symbol].append(trade_date)
                
                self._traded_symbols = set(self._symbol_trade_dates.keys())
                
                total_trade_days = sum(len(dates) for dates in self._symbol_trade_dates.values())
                self.logger.info(f"📊 Loaded {len(self._traded_symbols)} symbols with {total_trade_days} specific trade dates")
                self.logger.debug(f"   Symbols: {sorted(self._traded_symbols)}")
                
                # Show some examples
                for symbol in list(self._traded_symbols)[:3]:
                    dates = self._symbol_trade_dates[symbol]
                    self.logger.debug(f"   {symbol}: {len(dates)} trade dates ({dates[0]} to {dates[-1]})")
                
        except Exception as e:
            self.logger.error(f"Error loading traded symbols: {e}")
            self._traded_symbols = set()
            self._symbol_trade_dates = {}
    
    def _identify_missing_symbols(self):
        """Identify symbols that need CSV data downloaded"""
        self._missing_symbols = self._traded_symbols - self._symbols_with_data
        
        if self._missing_symbols:
            self.logger.info(f"📥 Missing CSV data for {len(self._missing_symbols)} symbols:")
            self.logger.info(f"   {sorted(self._missing_symbols)}")
        else:
            self.logger.info(f"✅ All traded symbols have CSV data available")
    
    async def _download_missing_data(self):
        """Download missing CSV data for specific trade dates only"""
        if not self._missing_symbols or not self.polygon_downloader:
            if not self.polygon_downloader:
                self.logger.warning("📥 Cannot download: No Polygon.io API key configured")
            return
        
        # Calculate total download tasks
        total_downloads = 0
        for symbol in self._missing_symbols:
            if symbol in self._symbol_trade_dates:
                total_downloads += len(self._symbol_trade_dates[symbol])
        
        self.logger.info(f"📥 Starting optimized Polygon.io download...")
        self.logger.info(f"🎯 {len(self._missing_symbols)} symbols with {total_downloads} specific trade dates")
        self.logger.info(f"⚠️  Rate limit: 5 calls per minute (free tier)")
        
        downloaded_count = 0
        failed_count = 0
        symbols_list = list(self._missing_symbols)
        
        for i, symbol in enumerate(symbols_list, 1):
            try:
                if symbol not in self._symbol_trade_dates:
                    self.logger.warning(f"   ⚠️ No trade dates found for {symbol}")
                    continue
                
                trade_dates = self._symbol_trade_dates[symbol]
                self.logger.info(f"📥 [{i}/{len(symbols_list)}] {symbol} - {len(trade_dates)} trade dates")
                
                # Combine data from all trade dates for this symbol
                all_symbol_data = []
                
                for trade_date in trade_dates:
                    try:
                        # Download data for specific date only
                        df = self.polygon_downloader.get_ticker_data(symbol, trade_date, trade_date)
                        
                        if not df.empty:
                            all_symbol_data.append(df)
                            self.logger.debug(f"   ✅ {trade_date}: {len(df)} bars")
                        else:
                            self.logger.debug(f"   ❌ {trade_date}: No data")
                        
                    except Exception as e:
                        self.logger.debug(f"   ❌ {trade_date}: Error - {e}")
                        continue
                
                # Combine all data for this symbol
                if all_symbol_data:
                    combined_df = pd.concat(all_symbol_data, ignore_index=True)
                    combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)
                    
                    # Save to CSV
                    csv_file = self.data_path / f"{symbol}_1_min.csv"
                    combined_df.to_csv(csv_file, index=False)
                    
                    # Add to cache
                    self.add_data_from_dataframe(symbol, "1 min", combined_df)
                    
                    downloaded_count += 1
                    self.logger.info(f"   ✅ {symbol}: {len(combined_df)} total bars from {len(all_symbol_data)} trade dates")
                else:
                    self.logger.warning(f"   ❌ No data available for any trade dates of {symbol}")
                    failed_count += 1
                
            except Exception as e:
                self.logger.error(f"   ❌ Failed to download {symbol}: {e}")
                failed_count += 1
                continue
        
        # Final summary
        self.logger.info(f"📥 Optimized download complete:")
        self.logger.info(f"   ✅ Successful: {downloaded_count}")
        self.logger.info(f"   ❌ Failed: {failed_count}")
        self.logger.info(f"   📁 Files saved to: {self.data_path}")
        self.logger.info(f"   💾 Downloaded only specific trade dates (much faster!)")
        
        if downloaded_count > 0:
            # Rescan available data to update symbols_with_data
            self._scan_available_data()
    
    def get_traded_symbols(self) -> List[str]:
        """Get list of symbols that have been traded"""
        return sorted(self._traded_symbols)
    
    def get_available_traded_symbols(self) -> List[str]:
        """Get list of traded symbols that have CSV data available"""
        available = self._traded_symbols & set(self.get_available_symbols())
        return sorted(available)
    
    def get_trade_statistics_for_symbol(self, symbol: str) -> Optional[Dict]:
        """Get trading statistics for a symbol from database"""
        try:
            if not Path(self.db_path).exists():
                return None
            
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
                    COUNT(CASE WHEN pnl <= 0 THEN 1 END) as losing_trades,
                    ROUND(AVG(pnl), 2) as avg_pnl,
                    ROUND(SUM(pnl), 2) as total_pnl,
                    ROUND(MAX(pnl), 2) as best_trade,
                    ROUND(MIN(pnl), 2) as worst_trade,
                    ROUND(AVG(duration_minutes), 1) as avg_duration_minutes,
                    GROUP_CONCAT(DISTINCT strategy) as strategies_used
                FROM trades 
                WHERE symbol = ? 
                  AND status = 'CLOSED' 
                  AND pnl IS NOT NULL
                """
                
                cursor = conn.execute(query, (symbol,))
                row = cursor.fetchone()
                
                if row and row[0] > 0:  # total_trades > 0
                    return {
                        'symbol': symbol,
                        'total_trades': row[0],
                        'winning_trades': row[1],
                        'losing_trades': row[2],
                        'win_rate': round((row[1] / row[0]) * 100, 1) if row[0] > 0 else 0,
                        'avg_pnl': row[3],
                        'total_pnl': row[4],
                        'best_trade': row[5],
                        'worst_trade': row[6],
                        'avg_duration_minutes': row[7],
                        'strategies_used': row[8].split(',') if row[8] else []
                    }
                
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting trade statistics for {symbol}: {e}")
            return None
    
    def get_backtesting_report(self) -> Dict:
        """Generate a comprehensive backtesting report"""
        report = {
            'total_traded_symbols': len(self._traded_symbols),
            'symbols_with_data': len(self._symbols_with_data),
            'symbols_ready_for_backtesting': len(self.get_available_traded_symbols()),
            'missing_data_symbols': len(self._missing_symbols),
            'traded_symbols': sorted(self._traded_symbols),
            'available_symbols': self.get_available_traded_symbols(),
            'missing_symbols': sorted(self._missing_symbols),
            'data_path': str(self.data_path),
            'database_path': self.db_path
        }
        
        # Add individual symbol statistics
        symbol_stats = {}
        for symbol in self.get_available_traded_symbols():
            stats = self.get_trade_statistics_for_symbol(symbol)
            if stats:
                symbol_stats[symbol] = stats
        
        report['symbol_statistics'] = symbol_stats
        
        return report
    
    def print_backtesting_summary(self):
        """Print a formatted summary for backtesting"""
        report = self.get_backtesting_report()
        
        print("🎯 TRADED SYMBOLS BACKTESTING SUMMARY")
        print("=" * 50)
        print(f"📊 Total symbols traded: {report['total_traded_symbols']}")
        print(f"✅ Ready for backtesting: {report['symbols_ready_for_backtesting']}")
        if report['missing_data_symbols'] > 0:
            print(f"❌ Missing data: {report['missing_data_symbols']}")
        else:
            print(f"🎉 All symbols have data!")
        
        if report['available_symbols']:
            print(f"\n📈 SYMBOLS READY FOR BACKTESTING:")
            for symbol in report['available_symbols'][:10]:  # Show first 10
                stats = report['symbol_statistics'].get(symbol)
                if stats:
                    print(f"   {symbol}: {stats['total_trades']} trades, "
                          f"{stats['win_rate']}% WR, ${stats['total_pnl']} PnL")
            
            if len(report['available_symbols']) > 10:
                print(f"   ... and {len(report['available_symbols']) - 10} more symbols")
        
        if report['missing_symbols']:
            print(f"\n❌ MISSING DATA FOR:")
            print(f"   {', '.join(report['missing_symbols'])}")
        
        print(f"\n📂 CSV Data Directory: {report['data_path']}")
        print(f"🗄️  Database: {report['database_path']}")