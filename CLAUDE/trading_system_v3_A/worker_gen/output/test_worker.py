
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.workers.base_worker_logic import BaseWorkerLogic

class TestWorkerLogic(BaseWorkerLogic):
    """
    Auto-Generated Worker by WorkerGen AI.
    Strategy Score: 123.45
    """
    
    def __init__(self, worker_name, config, execution_engine, risk_manager, event_queue):
        super().__init__(worker_name, config, execution_engine, risk_manager, event_queue)
        self.logger = logging.getLogger(f"Worker.{worker_name}")
        
        # Optimized Parameters
        self.stop_loss_pct = 2.5
        self.take_profit_pct = 5.0
        self.time_limit_bars = 60

    async def should_enter(self, opportunity):
        """
        Evaluates entry based on optimized genetic conditions.
        """
        symbol = opportunity['symbol']
        
        # 1. Get History (Enough for EMA 200)
        # We request 300 bars to be safe for indicators
        bars = await self.execution_engine.get_history(symbol, 300, '1 min')
        
        if not bars or len(bars) < 200:
            self.logger.warning(f"{symbol}: Insufficient history {len(bars)}")
            return False
            
        # 2. Prepare DataFrame
        df = pd.DataFrame(bars)
        # Ensure standard columns (assuming bar objects or dicts)
        # If bars are objects, convert:
        if hasattr(bars[0], 'close'):
             df = pd.DataFrame([vars(b) for b in bars])
             
        # Normalize columns if needed
        # (Assuming standard names from system: open, high, low, close, volume)
        
        # 3. Calculate Indicators
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
        df['cum_pv'] = (df['close'] * df['volume']).cumsum() # Approx
        df['vwap'] = df['cum_pv'] / df['cum_vol']
        
        # Relative Volume
        df['vol_sma_20'] = df['volume'].rolling(window=20).mean()
        df['rvol'] = df['volume'] / df['vol_sma_20']
        
        # Distance to EMA9
        df['dist_ema_9'] = (close - df['ema_9']) / df['ema_9'] * 100
        
        # 4. Evaluate Last Bar
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # --- GENERATED CONDITIONS ---
        # Logic: rsi_14 < 30 AND close > vwap
        
        if not (current['rsi_14'] < 30):
            # Fail: rsi_14 < 30
            return False
        if not (current['close'] > current['vwap']):
            # Fail: close > vwap
            return False
            
        self.logger.info(f"✅ {symbol}: Strategy Entry Triggered!")
        return True

    async def should_exit(self, position, current_bar):
        """
        Simple SL/TP/Time exit logic.
        """
        # This is handled by StopManager usually, but if custom logic needed:
        # For V3, we rely on the stop_manager primarily, but can force exit here.
        # We will leave this flexible or delegate.
        return False
