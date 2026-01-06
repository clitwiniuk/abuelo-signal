"""
Historical Scanner Adapter & Data Prefetcher

This module enables "Time Travel" scanning. It allows the system to:
1. Ensure historical daily data exists in the DB for a list of symbols.
2. Run the Breakout Scanner logic on that historical data to find valid setups in the past.
3. Determine which tickers should be "fed" to the ReplayEngine for a specific date.
"""

import logging
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import asyncio

# Import scanner logic (reuse existing consolidation detection if possible)
# For now, we'll implement a simplified Qullamaggie filter here to ensure independence
from strategies.swing_workers.breakout_data_provider import IBKRBreakoutDataProvider

class HistoricalScannerAdapter:
    def __init__(self, ibkr_adapter, db_path: str = "trading_data.db"):
        self.provider = IBKRBreakoutDataProvider(ibkr_adapter, db_path)
        self.logger = logging.getLogger("HistoricalScanner")
        self.preloaded_results = {}
        
    async def ensure_data_available(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """
        Prefetch data for a list of symbols to ensure we have enough history 
        for scanning (need ~6 months before start_date).
        """
        lookback_date = start_date - timedelta(days=200) # 6 months buffer
        
        self.logger.info(f"📥 Prefetching data for {len(symbols)} symbols from {lookback_date.date()}")
        
        tasks = []
        for symbol in symbols:
            # We use get_daily_history which handles caching internally
            # Requesting up to end_date ensures we cover the whole backtest period
            days_needed = (end_date - lookback_date).days
            tasks.append(self.provider.get_daily_history(symbol, end_date, days=days_needed))
            
        # Run in chunks to avoid overwhelming IBKR
        chunk_size = 5
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i+chunk_size]
            await asyncio.gather(*chunk)
            self.logger.info(f"   Processed batch {i//chunk_size + 1}/{len(tasks)//chunk_size + 1}")
            await asyncio.sleep(1) # Rate limit courtesy
            
        self.logger.info("✅ Data prefetch complete")

    def load_results(self, results: Dict):
        """Load pre-computed scanner results"""
        self.preloaded_results = results

    async def scan_history(self, symbols: List[str], start_date: datetime, end_date: datetime) -> Dict[str, List[Dict]]:
        """
        Scans the history for the given symbols and returns a dictionary mapping 
        DATE -> List of Opportunities.
        
        Returns:
            {
                '2023-01-05': [
                    {'symbol': 'NVDA', 'breakout_data': {...}, 'quality_score': 85},
                    {'symbol': 'AMD', ...}
                ],
                ...
            }
        """
        # 0. Check Preloaded Results
        if self.preloaded_results:
            # Filter for requested range
            filtered = {}
            for date_str, hits in self.preloaded_results.items():
                try:
                    d = datetime.strptime(date_str, '%Y-%m-%d')
                    if start_date <= d <= end_date:
                        filtered[date_str] = hits
                except:
                    pass
            if filtered:
                return filtered
        
        scanner_results = {}
        
        # We process symbol by symbol
        for symbol in symbols:
            try:
                # Get full history
                days_total = (end_date - (start_date - timedelta(days=200))).days
                df = await self.provider.get_daily_history(symbol, end_date, days=days_total)
                
                if df is None or df.empty:
                    continue
                    
                # Iterate through each day in the backtest range
                current = start_date
                while current <= end_date:
                    # Slice data visible at 'current' date (simulate point-in-time)
                    visible_data = df[df.index <= current]
                    
                    if len(visible_data) < 50: # Need min history
                        current += timedelta(days=1)
                        continue
                        
                    # Check for Breakout Setup (Qullamaggie Logic)
                    is_setup, setup_data = self._check_breakout_setup(visible_data)
                    
                    if is_setup:
                        date_str = current.strftime('%Y-%m-%d')
                        if date_str not in scanner_results:
                            scanner_results[date_str] = []
                            
                        scanner_results[date_str].append({
                            'symbol': symbol,
                            'breakout_data': setup_data,
                            'quality_score': setup_data.get('quality_score', 0),
                            'volume_ratio': setup_data.get('volume_ratio', 1.0)
                        })
                        
                    current += timedelta(days=1)
                    
            except Exception as e:
                self.logger.error(f"Error scanning {symbol}: {e}")
                
        return scanner_results

    def _check_breakout_setup(self, df: pd.DataFrame) -> Tuple[bool, Dict]:
        """
        Simplified Qullamaggie Scan Logic applied to a DataFrame ending at 'today'
        """
        try:
            # Metrics
            current_close = df['close'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].tail(20).mean()
            
            # 0. Basic Filters (Price & Volume) based on Qullamaggie criteria
            # Price > 2 and < 50, Avg Vol > 300k, Dollar Vol > $10M
            min_price = 2.0
            max_price = 50.0
            min_avg_vol = 300_000
            min_dollar_vol = 10_000_000
            
            dollar_vol = current_close * avg_volume
            
            if current_close < min_price or current_close > max_price:
                return False, {}
                
            if avg_volume < min_avg_vol:
                return False, {}
                
            if dollar_vol < min_dollar_vol:
                return False, {}
            
            # 1. Performance (Trend)
            # 1 Month Gain
            close_20d = df['close'].iloc[-21] if len(df) > 21 else df['close'].iloc[0]
            gain_1m = ((current_close - close_20d) / close_20d) * 100
            
            # 3 Month Gain
            close_60d = df['close'].iloc[-63] if len(df) > 63 else df['close'].iloc[0]
            gain_3m = ((current_close - close_60d) / close_60d) * 100
            
            # 6 Month Gain
            close_120d = df['close'].iloc[-126] if len(df) > 126 else df['close'].iloc[0]
            gain_6m = ((current_close - close_120d) / close_120d) * 100
            
            # Filter: Must be up significantly in at least one timeframe
            if gain_1m < 10 and gain_3m < 20 and gain_6m < 30:
                return False, {}
                
            # 2. Consolidation (Tightness)
            # Look at last 10 days
            recent = df.tail(10)
            high_Recent = recent['high'].max()
            low_recent = recent['low'].min()
            range_pct = ((high_Recent - low_recent) / low_recent) * 100
            
            # Must be tight (< 15% range in last 2 weeks roughly)
            if range_pct > 15.0:
                return False, {}
                
            # ADR Check
            atr = self._calc_atr(df)
            adr_pct = (atr / current_close) * 100
            if adr_pct < 2.5: # Qullamaggie likes volatile movers, setting 2.5% as loose floor
                 return False, {}
                
            # 3. Near 10MA or 20MA? (Surfing)
            ma_10 = df['close'].rolling(10).mean().iloc[-1]
            ma_20 = df['close'].rolling(20).mean().iloc[-1]
            
            # Price should be above MA20
            if current_close < ma_20:
                return False, {}
                
            # 4. Construct Data
            quality_score = min(100, (gain_1m + gain_3m/2 + gain_6m/3)) 
            atr = self._calc_atr(df)
            
            return True, {
                'resistance': high_Recent,
                'support': low_recent,
                'atr': atr,
                'quality_score': int(quality_score),
                'distance_to_breakout_pct': abs((high_Recent - current_close)/current_close)*100,
                'volume_ratio': 1.5 # Assume volume comes in (intraday check will validate)
            }
            
        except Exception:
            return False, {}

    def _calc_atr(self, df, period=14):
        try:
            high = df['high']
            low = df['low']
            close = df['close'].shift(1)
            tr = pd.concat([high-low, (high-close).abs(), (low-close).abs()], axis=1).max(axis=1)
            return tr.rolling(period).mean().iloc[-1]
        except:
            return 0.0
