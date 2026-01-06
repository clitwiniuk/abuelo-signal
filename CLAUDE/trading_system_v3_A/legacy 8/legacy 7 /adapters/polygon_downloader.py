# adapters/polygon_downloader.py
"""
Polygon.io data downloader for CSV data.
Downloads real market data to use with MockIBKRAdapter simulation.
Focused on smallcaps and growth stocks, with full flexibility for custom tickers.
"""

import asyncio
import aiohttp
import pandas as pd
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
import time
import os


class PolygonDownloader:
    """
    Downloads market data from Polygon.io and saves as CSV files
    Compatible with MockIBKRAdapter and CSVDataProvider
    Full flexibility for any ticker you want to download
    """
    
    def __init__(self, api_key: str, data_path: str = "data/csv"):
        self.api_key = api_key
        self.data_path = Path(data_path)
        self.logger = logging.getLogger("PolygonDownloader")
        self.logger.info("📥 POLYGON DOWNLOADER INITIALIZED - Any ticker you want!")
        
        # Rate limiting
        self.requests_per_minute = 5  # Free tier limit
        self.last_request_times = []
        
        # Create data directory
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Session for connection pooling
        self._session = None
        
        if not api_key:
            self.logger.warning("⚠️ No Polygon API key provided. Set POLYGON_API_KEY environment variable.")
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()
    
    def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        now = time.time()
        
        # Remove requests older than 1 minute
        self.last_request_times = [t for t in self.last_request_times if now - t < 60]
        
        # Check if we're at the limit
        if len(self.last_request_times) >= self.requests_per_minute:
            sleep_time = 60 - (now - self.last_request_times[0])
            if sleep_time > 0:
                self.logger.info(f"⏳ Rate limit reached, sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
        
        # Record this request
        self.last_request_times.append(now)
    
    async def download_symbol_data(self, symbol: str, days: int = 10, 
                                  timeframe: str = "1 min",
                                  start_date: Optional[datetime.date] = None,
                                  end_date: Optional[datetime.date] = None) -> bool:
        """
        Download data for ANY symbol you specify
        
        Args:
            symbol: ANY stock symbol you want (e.g., 'PLTR', 'TSLA', 'NVDA', etc.)
            days: Number of days to download (default 10) if dates not provided
            timeframe: Data timeframe (default '1 min')
            start_date: Explicit start date (optional)
            end_date: Explicit end date (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Calculate date range
            if not end_date:
                end_date = datetime.now().date()
            if not start_date:
                start_date = end_date - timedelta(days=days)
            
            self.logger.info(f"📥 Downloading {symbol} data from {start_date} to {end_date}")
            
            # Download data
            bars = await self._fetch_bars(symbol, start_date, end_date, timeframe)
            
            if not bars:
                self.logger.warning(f"❌ No data received for {symbol}")
                return False
            
            # Save to CSV
            success = self._save_to_csv(symbol, timeframe, bars)
            
            if success:
                self.logger.info(f"✅ Downloaded {len(bars)} bars for {symbol}")
                return True
            else:
                self.logger.error(f"❌ Failed to save data for {symbol}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error downloading {symbol}: {e}")
            return False
    
    async def _fetch_bars(self, symbol: str, start_date, end_date, timeframe: str) -> List[Dict]:
        """Fetch bars from Polygon API"""
        
        # Convert timeframe to Polygon format
        multiplier, timespan = self._convert_timeframe(timeframe)
        
        # Build URL
        url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_date}/{end_date}"
        
        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 50000,  # Max limit
            'apikey': self.api_key
        }
        
        self._check_rate_limit()
        
        try:
            if not self._session:
                raise RuntimeError("Session not initialized. Use async context manager.")
            
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('status') == 'OK' and 'results' in data:
                        bars = []
                        for result in data['results']:
                            # Convert timestamp from milliseconds (original working logic)
                            timestamp = datetime.fromtimestamp(result['t'] / 1000)
                            
                            # Skip weekend data
                            if timestamp.weekday() >= 5:
                                continue
                            
                            # No additional hour filtering - download all available data
                            # This matches the original working script logic
                            
                            bar = {
                                'timestamp': timestamp,
                                'open': result['o'],
                                'high': result['h'],
                                'low': result['l'],
                                'close': result['c'],
                                'volume': result['v']
                            }
                            bars.append(bar)
                        
                        return bars
                    elif data.get('status') == 'DELAYED':
                        self.logger.info(f"⏰ {symbol} - Account gratuito: datos retrasados pero disponibles")
                        if 'results' in data and data['results']:
                            bars = []
                            for result in data['results']:
                                timestamp = datetime.fromtimestamp(result['t'] / 1000)
                                if timestamp.weekday() >= 5:
                                    continue
                                if not (9.5 <= timestamp.hour + timestamp.minute/60 <= 16):
                                    continue
                                
                                bar = {
                                    'timestamp': timestamp,
                                    'open': result['o'],
                                    'high': result['h'],
                                    'low': result['l'],
                                    'close': result['c'],
                                    'volume': result['v']
                                }
                                bars.append(bar)
                            return bars
                        else:
                            self.logger.warning(f"⚠️ {symbol} - DELAYED pero sin resultados")
                            return []
                    else:
                        self.logger.warning(f"⚠️ Polygon API returned: {data.get('status', 'Unknown')} for {symbol}")
                        return []
                
                elif response.status == 429:
                    self.logger.warning("⚠️ Rate limited by Polygon API")
                    await asyncio.sleep(60)  # Wait 1 minute
                    return []
                
                else:
                    self.logger.error(f"❌ HTTP {response.status}: {await response.text()}")
                    return []
                    
        except Exception as e:
            self.logger.error(f"❌ Network error fetching {symbol}: {e}")
            return []
    
    def _convert_timeframe(self, timeframe: str) -> tuple[int, str]:
        """Convert timeframe to Polygon format"""
        timeframe_map = {
            '1 min': (1, 'minute'),
            '5 mins': (5, 'minute'),
            '15 mins': (15, 'minute'),
            '30 mins': (30, 'minute'),
            '1 hour': (1, 'hour'),
            '1 day': (1, 'day')
        }
        
        return timeframe_map.get(timeframe, (1, 'minute'))
    
    def _save_to_csv(self, symbol: str, timeframe: str, bars: List[Dict]) -> bool:
        """Save bars to CSV file"""
        try:
            df = pd.DataFrame(bars)
            
            if df.empty:
                self.logger.warning(f"⚠️ No bars to save for {symbol}")
                return False
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Format filename
            filename = f"{symbol}_{timeframe.replace(' ', '_')}.csv"
            filepath = self.data_path / filename
            
            # Save to CSV
            df.to_csv(filepath, index=False)
            
            self.logger.info(f"💾 Saved {len(df)} bars to {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error saving CSV for {symbol}: {e}")
            return False
    
    async def download_multiple_symbols(self, symbols: List[str], days: int = 10, 
                                      timeframe: str = "1 min", max_concurrent: int = 3) -> Dict[str, bool]:
        """
        Download data for multiple symbols with concurrency control
        Perfect for downloading your custom ticker lists!
        
        Args:
            symbols: List of ANY symbols you want to download
            days: Number of days to download
            timeframe: Data timeframe
            max_concurrent: Maximum concurrent downloads
            
        Returns:
            Dict mapping symbol to success status
        """
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def download_with_semaphore(symbol):
            async with semaphore:
                return await self.download_symbol_data(symbol, days, timeframe)
        
        self.logger.info(f"📥 Starting download for {len(symbols)} symbols")
        
        # Create tasks
        tasks = [download_with_semaphore(symbol) for symbol in symbols]
        
        # Execute with progress tracking
        results = {}
        completed = 0
        
        for symbol, coro in zip(symbols, asyncio.as_completed(tasks)):
            try:
                success = await coro
                results[symbol] = success
                completed += 1
                
                status = "✅" if success else "❌"
                self.logger.info(f"{status} {symbol} - Progress: {completed}/{len(symbols)}")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to download {symbol}: {e}")
                results[symbol] = False
                completed += 1
        
        # Summary
        successful = sum(results.values())
        self.logger.info(f"📊 Download complete: {successful}/{len(symbols)} successful")
        
        return results
    
    def get_available_data(self) -> List[str]:
        """Get list of symbols with downloaded data"""
        symbols = set()
        
        for csv_file in self.data_path.glob("*.csv"):
            try:
                symbol = csv_file.stem.split('_')[0]
                symbols.add(symbol)
            except:
                pass
        
        return sorted(symbols)
    
    def get_smallcap_suggestions(self) -> List[str]:
        """Get suggested smallcap symbols for trading (you can modify this list!)"""
        return [
            # Popular smallcaps with good volume
            'PLTR', 'BB', 'AMC', 'GME', 'MVIS', 'SNDL', 'SENS', 'BNGO',
            'CLOV', 'WISH', 'SPCE', 'NKLA', 'RIDE', 'WKHS', 'VLDR',
            'LAZR', 'HYLN', 'BLNK', 'CHPT', 'PLUG', 'FCEL', 'BLDP',
            'RIOT', 'MARA', 'CAN', 'EBON', 'SOS', 'XPEV', 'NIO',
            'SOFI', 'HOOD', 'RBLX', 'COIN', 'PATH',
            # High volatility smallcaps
            'DWAC', 'PHUN', 'BENE', 'MARK', 'PROG', 'ATER', 'BBIG'
        ]
    
    def get_growth_suggestions(self) -> List[str]:
        """Get suggested growth stocks (you can modify this list!)"""
        return [
            # High-growth tech
            'NVDA', 'AMD', 'CRM', 'SNOW', 'CRWD', 'ZS', 'DDOG',
            'OKTA', 'NET', 'FSLY', 'TEAM', 'ZM', 'DOCU', 'TWLO',
            # EV and clean energy growth
            'TSLA', 'RIVN', 'LCID', 'NKLA', 'QS', 'CHPT', 'BLNK',
            # Biotech growth
            'MRNA', 'BNTX', 'NVAX', 'VXRT', 'INO', 'OCGN', 'GEVO',
            # Fintech growth
            'SQ', 'PYPL', 'AFRM', 'UPST', 'SOFI', 'COIN', 'HOOD',
            # AI and Cloud
            'PLTR', 'RBLX', 'U', 'PATH', 'AI', 'C3AI'
        ]
    
    async def download_suggested_smallcaps(self, days: int = 10) -> Dict[str, bool]:
        """Download suggested smallcap portfolio"""
        symbols = self.get_smallcap_suggestions()
        self.logger.info(f"📥 Downloading suggested smallcaps: {len(symbols)} symbols")
        return await self.download_multiple_symbols(symbols, days)
    
    async def download_suggested_growth(self, days: int = 10) -> Dict[str, bool]:
        """Download suggested growth portfolio"""
        symbols = self.get_growth_suggestions()
        self.logger.info(f"📥 Downloading suggested growth stocks: {len(symbols)} symbols")
        return await self.download_multiple_symbols(symbols, days)
    
    def get_data_info(self, symbol: str) -> Dict[str, Any]:
        """Get information about downloaded data for a symbol"""
        csv_file = self.data_path / f"{symbol}_1_min.csv"
        
        if not csv_file.exists():
            return {'exists': False}
        
        try:
            df = pd.read_csv(csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            return {
                'exists': True,
                'bars_count': len(df),
                'start_date': df['timestamp'].min(),
                'end_date': df['timestamp'].max(),
                'file_size_mb': csv_file.stat().st_size / (1024 * 1024),
                'last_modified': datetime.fromtimestamp(csv_file.stat().st_mtime)
            }
            
        except Exception as e:
            return {'exists': True, 'error': str(e)}
    
    async def update_symbol_data(self, symbol: str, days: int = 2) -> bool:
        """Update existing data with recent bars"""
        try:
            info = self.get_data_info(symbol)
            
            if not info['exists']:
                self.logger.info(f"📥 No existing data for {symbol}, downloading fresh data")
                return await self.download_symbol_data(symbol, days=10)
            
            # Check if data is recent enough
            last_date = info.get('end_date')
            if last_date:
                if isinstance(last_date, str):
                    last_date = pd.to_datetime(last_date)
                
                days_old = (datetime.now() - last_date).days
                
                if days_old <= 1:
                    self.logger.info(f"✅ {symbol} data is current (last: {last_date.date()})")
                    return True
                
                self.logger.info(f"📥 Updating {symbol} data ({days_old} days old)")
            
            # Download recent data
            return await self.download_symbol_data(symbol, days=days)
            
        except Exception as e:
            self.logger.error(f"❌ Error updating {symbol}: {e}")
            return False
    
    @classmethod
    def from_env(cls, data_path: str = "data/csv") -> 'PolygonDownloader':
        """Create downloader using API key from environment variable"""
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            raise ValueError("POLYGON_API_KEY environment variable not set")
        
        return cls(api_key, data_path)


# Easy-to-use utility functions

async def download_any_symbols(symbols: List[str], api_key: str = None, 
                              days: int = 10, data_path: str = "data/csv") -> Dict[str, bool]:
    """
    Download data for ANY symbols you want
    
    Usage:
        # Download your custom list
        my_symbols = ['PLTR', 'TSLA', 'NVDA', 'AMD', 'CUSTOM_TICKER']
        results = await download_any_symbols(my_symbols)
    """
    
    if api_key is None:
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            raise ValueError("No API key provided and POLYGON_API_KEY not set")
    
    async with PolygonDownloader(api_key, data_path) as downloader:
        return await downloader.download_multiple_symbols(symbols, days)


async def download_single_symbol(symbol: str, api_key: str = None, 
                                days: int = 10, data_path: str = "data/csv") -> bool:
    """
    Download data for a single symbol
    
    Usage:
        success = await download_single_symbol('YOUR_FAVORITE_TICKER')
    """
    
    if api_key is None:
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            raise ValueError("No API key provided and POLYGON_API_KEY not set")
    
    async with PolygonDownloader(api_key, data_path) as downloader:
        return await downloader.download_symbol_data(symbol, days)


async def download_smallcap_suggestions(api_key: str = None, days: int = 10, 
                                       data_path: str = "data/csv") -> Dict[str, bool]:
    """
    Download suggested smallcap data (you can always add your own later!)
    
    Usage:
        results = await download_smallcap_suggestions()
    """
    
    if api_key is None:
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            raise ValueError("No API key provided and POLYGON_API_KEY not set")
    
    async with PolygonDownloader(api_key, data_path) as downloader:
        return await downloader.download_suggested_smallcaps(days)


async def download_growth_suggestions(api_key: str = None, days: int = 10, 
                                     data_path: str = "data/csv") -> Dict[str, bool]:
    """
    Download suggested growth stock data
    
    Usage:
        results = await download_growth_suggestions()
    """
    
    if api_key is None:
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            raise ValueError("No API key provided and POLYGON_API_KEY not set")
    
    async with PolygonDownloader(api_key, data_path) as downloader:
        return await downloader.download_suggested_growth(days)


async def update_existing_data(symbols: List[str] = None, api_key: str = None, 
                              data_path: str = "data/csv") -> Dict[str, bool]:
    """
    Update your existing data with latest bars
    
    Usage:
        # Update specific symbols
        results = await update_existing_data(['PLTR', 'YOUR_TICKER'])
        
        # Update all existing data
        results = await update_existing_data()
    """
    
    if api_key is None:
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            raise ValueError("No API key provided and POLYGON_API_KEY not set")
    
    async with PolygonDownloader(api_key, data_path) as downloader:
        if symbols is None:
            # Get all existing symbols
            symbols = downloader.get_available_data()
            if not symbols:
                # If no existing data, download suggestions
                symbols = list(set(
                    downloader.get_smallcap_suggestions() + 
                    downloader.get_growth_suggestions()
                ))
        
        results = {}
        for symbol in symbols:
            results[symbol] = await downloader.update_symbol_data(symbol)
        
        return results