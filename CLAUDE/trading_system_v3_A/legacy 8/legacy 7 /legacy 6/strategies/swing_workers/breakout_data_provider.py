"""
Data Providers for Breakout Strategy (Live & Backtest)

This module abstracts the data source for the Breakout Strategy, allowing it to toggle
between Live execution (fetching from IBKR + Caching) and Backtest execution (Reading from Cache).
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
import sqlite3
import pandas as pd
from typing import Optional, List, Dict
import json

class BreakoutDataProvider(ABC):
    """Abstract interface for data provision"""
    
    @abstractmethod
    async def get_daily_history(self, symbol: str, end_date: datetime, days: int = 60) -> Optional[pd.DataFrame]:
        """Fetch daily OHLCV history up to end_date"""
        pass

    @abstractmethod
    def get_current_date(self) -> datetime:
        """Get 'current' date (real or simulated)"""
        pass


class IBKRBreakoutDataProvider(BreakoutDataProvider):
    """
    Live Data Provider.
    1. Fetches from IBKR via IBKRAdapter
    2. Caches results to SQLite ('daily_bars_cache') to minimize API calls
    """
    
    def __init__(self, ibkr_adapter, db_path: str = "trading_data.db"):
        self.ibkr = ibkr_adapter
        self.db_path = db_path
        self.logger = logging.getLogger("IBKRDataProvider")
        self._ensure_cache_table()
        
    def _ensure_cache_table(self):
        """Create cache table if not exists"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_bars_cache (
                    symbol TEXT,
                    date TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    updated_at TEXT,
                    PRIMARY KEY (symbol, date)
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to init cache: {e}")

    def get_current_date(self) -> datetime:
        return datetime.now()

    async def get_daily_history(self, symbol: str, end_date: datetime, days: int = 60) -> Optional[pd.DataFrame]:
        """
        Strategy:
        1. Check DB cache first.
        2. If missing or stale, fetch from IBKR.
        3. Update cache.
        4. Return DataFrame.
        """
        # 1. Try Cache
        cached_df = self._get_from_cache(symbol, end_date, days)
        if cached_df is not None:
             # Check if we have enough data and it's up to date
             if len(cached_df) >= days * 0.8: # Allow some missing weekends
                 return cached_df
        
        # 2. Fetch from IBKR (Live)
        self.logger.info(f"📥 Fetching live history for {symbol}")
        try:
            # We request ample data to cover the period
            # We request ample data to cover the period
            # IBKR '1 M' or '3 M' duration
            # duration = "3 M" if days < 60 else "1 Y"
            
            # Request historical data with explicit count (handled by adapter now)
            bars = await self.ibkr.get_bars(symbol, "1 day", days + 20)
            
            if not bars:
                self.logger.warning(f"No data for {symbol}")
                return None
                
            # Convert to DataFrame
            df_data = []
            for b in bars:
                df_data.append({
                    'symbol': symbol,
                    'date': b.timestamp.strftime('%Y-%m-%d'),
                    'open': b.open,
                    'high': b.high,
                    'low': b.low,
                    'close': b.close,
                    'volume': b.volume
                })
            
            # 3. Update Cache
            self._save_to_cache(df_data)
            
            # Return as DataFrame
            df = pd.DataFrame(df_data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            
            # Filter by end_date
            mask = df.index <= end_date
            return df.loc[mask].tail(days)
            
        except Exception as e:
            self.logger.error(f"Error fetching IBKR data: {e}")
            return None

    def _get_from_cache(self, symbol: str, end_date: datetime, days: int) -> Optional[pd.DataFrame]:
        try:
            conn = sqlite3.connect(self.db_path)
            # Calculate start date roughly
            start_date_str = (end_date - timedelta(days=days*1.5)).strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            query = """
                SELECT date, open, high, low, close, volume 
                FROM daily_bars_cache 
                WHERE symbol = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
            """
            df = pd.read_sql_query(query, conn, params=(symbol, start_date_str, end_date_str), parse_dates=['date'])
            conn.close()
            
            if df.empty:
                return None
                
            df.set_index('date', inplace=True)
            return df
        except Exception:
            return None

    def _save_to_cache(self, data: List[Dict]):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            updated_at = datetime.now().isoformat()
            
            # Prepare data with updated_at
            for row in data:
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_bars_cache (symbol, date, open, high, low, close, volume, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (row['symbol'], row['date'], row['open'], row['high'], row['low'], row['close'], row['volume'], updated_at))
                
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Cache save failed: {e}")


class BacktestBreakoutDataProvider(BreakoutDataProvider):
    """
    Backtest Data Provider.
    1. Reads EXCLUSIVELY from DB ('daily_bars_cache' or 'historical_data').
    2. Uses simulated current_date.
    3. Throws error/warning if data missing (user must prefetch).
    """
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.current_date_simulated = None
        self.logger = logging.getLogger("BacktestDataProvider")

    def set_date(self, date: datetime):
        self.current_date_simulated = date

    def get_current_date(self) -> datetime:
        if not self.current_date_simulated:
             raise ValueError("Replay date not set in BacktestDataProvider")
        return self.current_date_simulated

    async def get_daily_history(self, symbol: str, end_date: datetime, days: int = 60) -> Optional[pd.DataFrame]:
        """
        Fetch ONLY from DB.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            # Look back enough days to ensure we get 'days' trading days
            start_date_limit = end_date - timedelta(days=days * 3) 
            
            query = """
                SELECT date, open, high, low, close, volume 
                FROM daily_bars_cache 
                WHERE symbol = ? AND date <= ? AND date >= ?
                ORDER BY date ASC
            """
            
            params = (symbol, end_date.strftime('%Y-%m-%d'), start_date_limit.strftime('%Y-%m-%d'))
            df = pd.read_sql_query(query, conn, params=params, parse_dates=['date'])
            conn.close()
            
            if df.empty:
                self.logger.warning(f"⚠️ MISSING HISTORICAL DATA: {symbol} at {end_date}. Run 'prefetch_data' tool first.")
                return None
                
            df.set_index('date', inplace=True)
            return df.tail(days)
            
        except Exception as e:
            self.logger.error(f"Backtest DB read error: {e}")
            return None
