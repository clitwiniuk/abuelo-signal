# adapters/csv_data_provider.py
"""
CSV data provider for backtesting and simulation.
Loads historical market data from CSV files.
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from core.interfaces import IDataProvider, MarketData, DataProviderError


class CSVDataProvider(IDataProvider):
    """
    Data provider that loads market data from CSV files.
    Perfect for backtesting and development with historical data.
    """
    
    def __init__(self, data_path: str = "data/csv", auto_load: bool = True, use_synthetic_data: bool = False):
        self.data_path = Path(data_path)
        self.use_synthetic_data = use_synthetic_data
        self.logger = logging.getLogger("CSVDataProvider")
        
        # If using synthetic data, override path
        if self.use_synthetic_data:
            self.synthetic_data_path = Path("synthetic_data")
            self.metadata_path = self.synthetic_data_path / "events_metadata.csv"
            self.events_metadata = None
            self.logger.info("🎯 CSV DATA PROVIDER INITIALIZED - SYNTHETIC EVENTS MODE")
        else:
            self.logger.info("📂 CSV DATA PROVIDER INITIALIZED - STANDARD MODE")
        
        # Connection state
        self._connected = False
        
        # Data cache
        self._data_cache = {}  # symbol_timeframe -> DataFrame
        self._available_symbols = set()
        
        # Create data directory if it doesn't exist
        if not self.use_synthetic_data:
            self.data_path.mkdir(parents=True, exist_ok=True)
        
        if auto_load:
            self._scan_available_data()
    
    async def connect(self) -> bool:
        """Connect to CSV data source"""
        self._connected = True
        self._scan_available_data()
        self.logger.info(f"✅ CSV: Connected - found data for {len(self._available_symbols)} symbols")
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from CSV data source"""
        self._connected = False
        self._data_cache.clear()
        self.logger.info("📴 CSV: Disconnected")
    
    def is_connected(self) -> bool:
        """Check connection status"""
        return self._connected
    
    def _scan_available_data(self):
        """Scan data directory for available CSV files"""
        self._available_symbols.clear()
        
        if self.use_synthetic_data:
            self._scan_synthetic_data()
        else:
            self._scan_standard_csv_data()
        
        self.logger.info(f"📂 Found CSV data for symbols: {sorted(self._available_symbols)}")
    
    def _scan_standard_csv_data(self):
        """Scan standard CSV data directory"""
        for csv_file in self.data_path.glob("*.csv"):
            try:
                # Parse filename: SYMBOL_TIMEFRAME.csv
                filename = csv_file.stem
                if '_' in filename:
                    symbol = filename.split('_')[0]
                    self._available_symbols.add(symbol)
            except Exception as e:
                self.logger.warning(f"Could not parse filename {csv_file}: {e}")
    
    def _scan_synthetic_data(self):
        """Scan synthetic data directory"""
        if not self.synthetic_data_path.exists():
            self.logger.warning(f"Synthetic data directory not found: {self.synthetic_data_path}")
            return
        
        # Load events metadata if available
        if self.metadata_path.exists():
            self._load_events_metadata()
        
        # Scan for synthetic CSV files (AAAA.csv, AAAB.csv, etc.)
        for csv_file in self.synthetic_data_path.glob("*.csv"):
            try:
                filename = csv_file.stem
                # Skip metadata file
                if filename == "events_metadata":
                    continue
                # Synthetic files use pattern AAAA, AAAB, etc.
                if len(filename) == 4 and filename.isalpha():
                    self._available_symbols.add(filename)
                    self.logger.debug(f"Found synthetic symbol: {filename}")
            except Exception as e:
                self.logger.warning(f"Could not parse synthetic filename {csv_file}: {e}")
    
    async def get_bars(self, symbol: str, timeframe: str, count: int) -> List[MarketData]:
        """
        Get historical bars from CSV data
        """
        if not self._connected:
            raise DataProviderError("Not connected to CSV data source")
        
        try:
            cache_key = f"{symbol}_{timeframe}"
            
            # Load data if not cached
            if cache_key not in self._data_cache:
                self._load_symbol_data(symbol, timeframe)
            
            # Get data from cache
            if cache_key not in self._data_cache:
                self.logger.warning(f"No CSV data available for {symbol} {timeframe}")
                return []
            
            df = self._data_cache[cache_key]
            
            # Get the latest N bars
            latest_bars = df.tail(count)
            
            # Convert to MarketData objects
            bars = []
            for _, row in latest_bars.iterrows():
                bar = MarketData(
                    symbol=symbol,
                    timestamp=row['timestamp'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume']) if pd.notna(row['volume']) else 0,
                    timeframe=timeframe
                )
                bars.append(bar)
            
            self.logger.debug(f"📊 CSV: Loaded {len(bars)} bars for {symbol} {timeframe}")
            return bars
            
        except Exception as e:
            self.logger.error(f"Error loading CSV data for {symbol}: {e}")
            return []

    async def get_bars_by_date_range(self, symbol: str, timeframe: str, days_back: int) -> List[MarketData]:
        """
        Get historical bars from CSV data for specific date range (days back from today)
        """
        if not self._connected:
            raise DataProviderError("Not connected to CSV data source")
        
        try:
            cache_key = f"{symbol}_{timeframe}"
            
            # Load data if not cached
            if cache_key not in self._data_cache:
                self._load_symbol_data(symbol, timeframe)
            
            # Get data from cache
            if cache_key not in self._data_cache:
                self.logger.warning(f"No CSV data available for {symbol} {timeframe}")
                return []
            
            df = self._data_cache[cache_key]
            
            # Calculate date range (days_back from today)
            end_date = datetime.now().replace(hour=23, minute=59, second=59)
            start_date = end_date - timedelta(days=days_back)
            
            # Convert timestamps to datetime if they aren't already
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter by date range
            mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
            filtered_df = df[mask]
            
            # Convert to MarketData objects
            bars = []
            for _, row in filtered_df.iterrows():
                bar = MarketData(
                    symbol=symbol,
                    timestamp=row['timestamp'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume']) if pd.notna(row['volume']) else 0,
                    timeframe=timeframe
                )
                bars.append(bar)
            
            if bars:
                self.logger.info(f"📊 CSV: Loaded {len(bars)} bars for {symbol} from {bars[0].timestamp} to {bars[-1].timestamp} ({days_back} days back)")
                self.logger.info(f"📅 Date range used: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
                self.logger.info(f"📊 Today's date for reference: {datetime.now().strftime('%Y-%m-%d')}")
            else:
                self.logger.warning(f"📊 CSV: No bars found for {symbol} in the last {days_back} days")
                self.logger.warning(f"📅 Searched range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            return bars
            
        except Exception as e:
            self.logger.error(f"Error loading CSV data by date range for {symbol}: {e}")
            return []
    
    def _load_symbol_data(self, symbol: str, timeframe: str):
        """Load data for a specific symbol and timeframe"""
        if self.use_synthetic_data:
            self._load_synthetic_symbol_data(symbol, timeframe)
        else:
            self._load_standard_symbol_data(symbol, timeframe)
    
    def _load_standard_symbol_data(self, symbol: str, timeframe: str):
        """Load standard CSV data for a symbol"""
        csv_file = self.data_path / f"{symbol}_{timeframe.replace(' ', '_')}.csv"
        
        if not csv_file.exists():
            self.logger.debug(f"CSV file not found: {csv_file}")
            return
        
        try:
            df = pd.read_csv(csv_file)
            
            # Validate required columns
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                self.logger.error(f"CSV file {csv_file} missing columns: {missing_cols}")
                return
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Validate data
            if len(df) == 0:
                self.logger.warning(f"CSV file {csv_file} is empty")
                return
            
            # Cache the data
            cache_key = f"{symbol}_{timeframe}"
            self._data_cache[cache_key] = df
            
            self.logger.info(f"📊 Loaded {len(df)} bars for {symbol} {timeframe} from CSV")
            
        except Exception as e:
            self.logger.error(f"Error loading CSV file {csv_file}: {e}")
    
    def _load_synthetic_symbol_data(self, symbol: str, timeframe: str):
        """Load synthetic data for a symbol"""
        csv_file = self.synthetic_data_path / f"{symbol}.csv"
        
        if not csv_file.exists():
            self.logger.debug(f"Synthetic CSV file not found: {csv_file}")
            return
        
        try:
            df = pd.read_csv(csv_file)
            
            # Synthetic data uses 'Date' instead of 'timestamp'
            if 'Date' in df.columns:
                df['timestamp'] = pd.to_datetime(df['Date'])
                df.drop('Date', axis=1, inplace=True)
            
            # Validate required columns
            required_cols = ['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                self.logger.error(f"Synthetic CSV file {csv_file} missing columns: {missing_cols}")
                return
            
            # Normalize column names to lowercase
            df.columns = [col.lower() if col != 'timestamp' else col for col in df.columns]
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Validate data
            if len(df) == 0:
                self.logger.warning(f"Synthetic CSV file {csv_file} is empty")
                return
            
            # Cache the data
            cache_key = f"{symbol}_{timeframe}"
            self._data_cache[cache_key] = df
            
            self.logger.info(f"🎯 Loaded {len(df)} bars for synthetic symbol {symbol} {timeframe}")
            
        except Exception as e:
            self.logger.error(f"Error loading synthetic CSV file {csv_file}: {e}")
    
    async def get_current_price(self, symbol: str) -> float:
        """Get current market price (latest close price from data)"""
        try:
            # Get latest 1-minute bar
            bars = await self.get_bars(symbol, "1 min", 1)
            if bars:
                return bars[-1].close
            
            # Fallback to any available timeframe
            for timeframe in ["5 mins", "15 mins", "1 hour", "1 day"]:
                bars = await self.get_bars(symbol, timeframe, 1)
                if bars:
                    return bars[-1].close
            
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Error getting current price for {symbol}: {e}")
            return 0.0
    
    def get_available_symbols(self) -> List[str]:
        """Get list of symbols with available data"""
        return sorted(self._available_symbols)
    
    def get_date_range(self, symbol: str, timeframe: str) -> tuple[datetime, datetime]:
        """Get the date range available for a symbol"""
        try:
            cache_key = f"{symbol}_{timeframe}"
            
            if cache_key not in self._data_cache:
                self._load_symbol_data(symbol, timeframe)
            
            if cache_key not in self._data_cache:
                return None, None
            
            df = self._data_cache[cache_key]
            return df['timestamp'].min(), df['timestamp'].max()
            
        except Exception as e:
            self.logger.error(f"Error getting date range for {symbol}: {e}")
            return None, None
    
    def add_data_from_dataframe(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """Add data from a pandas DataFrame"""
        try:
            # Validate DataFrame
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                raise ValueError(f"DataFrame missing columns: {missing_cols}")
            
            # Convert timestamp to datetime
            df = df.copy()
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Save to CSV
            csv_file = self.data_path / f"{symbol}_{timeframe.replace(' ', '_')}.csv"
            df.to_csv(csv_file, index=False)
            
            # Cache the data
            cache_key = f"{symbol}_{timeframe}"
            self._data_cache[cache_key] = df
            self._available_symbols.add(symbol)
            
            self.logger.info(f"📊 Added {len(df)} bars for {symbol} {timeframe}")
            
        except Exception as e:
            self.logger.error(f"Error adding data for {symbol}: {e}")
    
    def create_sample_data(self, symbols: List[str] = None, days: int = 30):
        """Create sample data for testing"""
        if symbols is None:
            symbols = ['AAPL', 'MSFT', 'TSLA', 'SPY', 'QQQ', 'NVDA', 'AMD']
        
        import random
        from datetime import datetime, timedelta
        
        for symbol in symbols:
            # Generate sample data
            data = []
            current_time = datetime.now() - timedelta(days=days)
            current_price = random.uniform(50, 200)
            
            # Generate daily bars
            for day in range(days):
                # Market hours: 9:30 AM - 4:00 PM (390 minutes)
                market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
                
                # Generate 1-minute bars for the day
                day_data = []
                day_price = current_price
                
                for minute in range(390):  # 390 minutes in trading day
                    timestamp = market_open + timedelta(minutes=minute)
                    
                    # Random price movement
                    price_change = random.uniform(-0.02, 0.02)  # ±2%
                    
                    open_price = day_price
                    close_price = open_price * (1 + price_change)
                    high_price = max(open_price, close_price) * random.uniform(1.0, 1.005)
                    low_price = min(open_price, close_price) * random.uniform(0.995, 1.0)
                    volume = random.randint(1000, 10000)
                    
                    day_data.append({
                        'timestamp': timestamp,
                        'open': round(open_price, 2),
                        'high': round(high_price, 2),
                        'low': round(low_price, 2),
                        'close': round(close_price, 2),
                        'volume': volume
                    })
                    
                    day_price = close_price
                
                data.extend(day_data)
                current_time += timedelta(days=1)
                current_price = day_price * random.uniform(0.95, 1.05)  # Daily gap
            
            # Save as DataFrame
            df = pd.DataFrame(data)
            self.add_data_from_dataframe(symbol, "1 min", df)
        
        self.logger.info(f"📊 Created sample data for {len(symbols)} symbols ({days} days)")
    
    def get_stats(self) -> Dict[str, any]:
        """Get statistics about available data"""
        stats = {
            'total_symbols': len(self._available_symbols),
            'symbols': sorted(self._available_symbols),
            'cached_datasets': len(self._data_cache),
            'data_path': str(self.data_path)
        }
        
        # Get date ranges for each symbol
        date_ranges = {}
        for symbol in self._available_symbols:
            start_date, end_date = self.get_date_range(symbol, "1 min")
            if start_date and end_date:
                date_ranges[symbol] = {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': (end_date - start_date).days
                }
        
        stats['date_ranges'] = date_ranges
        
        if self.use_synthetic_data:
            stats.update({
                'synthetic_mode': True,
                'synthetic_data_path': str(self.synthetic_data_path),
                'events_metadata_loaded': self.events_metadata is not None,
                'total_events': len(self.events_metadata) if self.events_metadata is not None else 0
            })
        
        return stats
    
    def _load_events_metadata(self):
        """Load events metadata from CSV"""
        try:
            if not self.metadata_path.exists():
                self.logger.warning(f"Events metadata file not found: {self.metadata_path}")
                return
            
            self.events_metadata = pd.read_csv(self.metadata_path)
            self.events_metadata['event_timestamp'] = pd.to_datetime(self.events_metadata['event_timestamp'])
            
            self.logger.info(f"🎯 Loaded events metadata: {len(self.events_metadata)} events")
            self.logger.info(f"   📅 Event period: {self.events_metadata['event_timestamp'].min()} to {self.events_metadata['event_timestamp'].max()}")
            self.logger.info(f"   📈 Avg ratio: {self.events_metadata['ratio_vol'].mean():.1f}x")
            
        except Exception as e:
            self.logger.error(f"Error loading events metadata: {e}")
            self.events_metadata = None
    
    def get_event_info_for_symbol(self, symbol: str) -> Optional[dict]:
        """
        Get event information for a synthetic symbol
        
        Args:
            symbol: Symbol name (e.g., 'AAAA')
            
        Returns:
            Dictionary with event information or None
        """
        if not self.use_synthetic_data or self.events_metadata is None:
            return None
        
        try:
            # Find event info for this symbol
            symbol_events = self.events_metadata[self.events_metadata['csv_file'] == f"{symbol}.csv"]
            
            if symbol_events.empty:
                return None
            
            event_info = symbol_events.iloc[0].to_dict()
            return event_info
            
        except Exception as e:
            self.logger.error(f"Error getting event info for {symbol}: {e}")
            return None
    
    def is_synthetic_mode(self) -> bool:
        """Check if provider is in synthetic data mode"""
        return self.use_synthetic_data