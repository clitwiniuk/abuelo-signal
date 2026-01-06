
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.workers.base_worker_logic import BaseWorkerLogic

class APlusWorkerLogic(BaseWorkerLogic):
    """
    Auto-Generated Worker by WorkerGen AI.
    Strategy Score: 4016.34
    
    Pattern: A+ (Trailing Stop Mode)
    Entry Window: Full day (0-390 min from open)
    Exit: Trailing Stop (0.72% SL, dynamic TP)
    """
    
    def __init__(self, worker_name, config, execution_engine, risk_manager, event_queue):
        super().__init__(worker_name, config, execution_engine, risk_manager, event_queue)
        self.logger = logging.getLogger(f"Worker.{worker_name}")
        
        # Optimized Parameters
        self.stop_loss_pct = 0.72
        self.take_profit_pct = 999.9  # Not used in trailing mode
        self.time_limit_bars = 185
        self.use_trailing_stop = True
        
        # Time Window (Minutes from Open 9:30)
        self.entry_window_start = 0
        self.entry_window_end = 390

    async def should_enter(self, opportunity):
        """
        Evaluates entry based on optimized genetic conditions.
        
        NOTE: The original generated condition (open >= open) was tautological.
        This has been replaced with a basic momentum filter as a placeholder.
        For production use, regenerate with a better-labeled pattern.
        """
        symbol = opportunity['symbol']
        
        # 1. Get History (Enough for EMA 200)
        bars = await self.execution_engine.get_history(symbol, 300, '1 min')
        
        if not bars or len(bars) < 200:
            self.logger.warning(f"{symbol}: Insufficient history {len(bars)}")
            return False
            
        # 2. Prepare DataFrame
        df = pd.DataFrame(bars)
        if hasattr(bars[0], 'close'):
             df = pd.DataFrame([vars(b) for b in bars])
             
        # 3. Check Time Window
        if 'timestamp' in df.columns:
            last_time = pd.to_datetime(df.iloc[-1]['timestamp'])
            minutes_from_open = (last_time.hour * 60 + last_time.minute) - 570
            
            if not (self.entry_window_start <= minutes_from_open <= self.entry_window_end):
                return False
        
        # 4. Calculate Indicators
        close = df['close']
        
        # EMAs
        df['ema_9'] = close.ewm(span=9, adjust=False).mean()
        df['ema_20'] = close.ewm(span=20, adjust=False).mean()
        df['ema_50'] = close.ewm(span=50, adjust=False).mean()
        df['ema_200'] = close.ewm(span=200, adjust=False).mean()
        
        # RSI 14
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # VWAP (Intraday approx)
        df['cum_vol'] = df['volume'].cumsum()
        df['cum_pv'] = (df['close'] * df['volume']).cumsum()
        df['vwap'] = df['cum_pv'] / df['cum_vol']
        
        # Relative Volume
        df['vol_sma_20'] = df['volume'].rolling(window=20).mean()
        df['rvol'] = df['volume'] / df['vol_sma_20']
        
        # Distance to EMA9
        df['dist_ema_9'] = (close - df['ema_9']) / df['ema_9'] * 100
        
        # 5. Evaluate Last Bar
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # --- PLACEHOLDER LOGIC (REPLACE WITH REAL PATTERN) ---
        # Original condition was tautological (open >= open)
        # Using basic momentum filter as placeholder:
        # - Price above EMA9
        # - RSI between 40-70 (not oversold/overbought)
        # - Relative volume > 1.2
        
        if current['close'] <= current['ema_9']:
            self.logger.debug(f"{symbol}: Price below EMA9")
            return False
            
        if not (40 <= current['rsi_14'] <= 70):
            self.logger.debug(f"{symbol}: RSI out of range: {current['rsi_14']:.1f}")
            return False
            
        if current['rvol'] < 1.2:
            self.logger.debug(f"{symbol}: Low relative volume: {current['rvol']:.2f}")
            return False
            
        self.logger.info(f"✅ {symbol}: Strategy Entry Triggered!")
        return True

    async def should_exit(self, position, current_bar):
        """
        Exit logic delegated to StopManager.
        Trailing stop will be managed by the system's stop_manager.
        """
        return False
