from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import pandas as pd
try:
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False

from strategies.workers.base_worker_logic import BaseWorkerLogic

class HolyGrailWorkerLogic(BaseWorkerLogic):
    """
    The Holy Grail Strategy Worker
    Based on Linda Raschke/L. Connors Strategy.

    Logic:
    1. Trend Identification: ADX(14) > 30 (Strong Trend)
    2. Direction: +DI > -DI (Uptrend Only)
    3. Setup: Retracement to EMA(20)
    4. Trigger: Breakout of High of the setup bar (Buy Stop simulation)

    Risk Management:
    - Inherits checks from BaseWorkerLogic (Stop Loss, Take Profit, Trailing)
    - Stop Loss: Initial Swing Low
    """

    def __init__(self, execution_engine, risk_manager=None, config=None):
        super().__init__(
            worker_name="holy_grail",
            execution_engine=execution_engine,
            risk_manager=risk_manager,
            config=config
        )
        self.target_profit_pct = 10.0
        self.stop_loss_pct = 5.0
        self.adx_period = 14
        self.adx_threshold = getattr(config, 'adx_threshold', 30) if config else 30
        self.ema_period = 20

        # Initialize stop manager with Holy Grail specific parameters
        from .worker_stop_manager import create_worker_stop_manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'HOLY_GRAIL_STRATEGY')
        else:
            # Fallback: create with default parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=5.0,           # 5% stop loss (based on swing low)
                take_profit_pct=10.0,        # 10% profit target
                quick_target_pct=0.0,        # No quick target
                trailing_activation=6.0,     # Activate trailing at 6%
                trailing_distance=3.0,       # 3% trailing distance
                max_position_hours=4.0       # 4 hours max (240 minutes)
            ))

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evaluate entry criteria for Holy Grail strategy.
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            current_price = opportunity.get('current_price', 0)
            
            if not PANDAS_TA_AVAILABLE:
                self.logger.warning(f"⚠️ {symbol}: pandas_ta not available - skipping Holy Grail analysis")
                return False
            
            # 1. Get Bars
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 50: # Need enough data for ADX/EMA
                return False

            # ========== VWAP DIRECTION VALIDATION (PHASE 1: INSTITUTIONAL FLOW) ==========
            # Holy Grail requires strong trend - validate institutional accumulation via VWAP
            is_valid_vwap, vwap_reason, vwap_data = self.validate_vwap_direction(
                bars=bars,
                current_price=current_price,
                intended_direction='LONG',
                min_slope_pct=0.10,  # Require institutional accumulation
                tolerance_pct=0.5,   # Tight tolerance (price near/above VWAP)
                symbol=symbol
            )

            if not is_valid_vwap:
                self.logger.info(f"⚪ {symbol}: VWAP direction rejected - {vwap_reason}")
                return False

            self.logger.info(f"✅ {symbol}: VWAP validation passed - {vwap_reason}")
            # ========== END VWAP VALIDATION ==========

            # Convert to DataFrame for TA-Lib
            df = self._bars_to_dataframe(bars)
            if df.empty:
                return False

            # 2. Calculate Indicators
            # ADX
            adx_df = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            if adx_df is None or adx_df.empty:
                return False
            
            # ADX returns 3 columns: ADX_14, DMP_14 (+DI), DMN_14 (-DI)
            adx_col = f"ADX_{self.adx_period}"
            dmp_col = f"DMP_{self.adx_period}"
            dmn_col = f"DMN_{self.adx_period}"
            
            current_adx = adx_df[adx_col].iloc[-1]
            current_dmp = adx_df[dmp_col].iloc[-1]
            current_dmn = adx_df[dmn_col].iloc[-1]
            prev_adx = adx_df[adx_col].iloc[-2]

            # EMA
            df['ema20'] = ta.ema(df['close'], length=self.ema_period)
            current_ema = df['ema20'].iloc[-1]
            
            # 3. Logic Checks
            
            # A. Trend Strength Check
            # ADX must be > 30 and Prefer Rising (or very high)
            if current_adx <= self.adx_threshold:
                self.logger.info(f"⚪ {symbol}: Trend too weak (ADX={current_adx:.1f} <= {self.adx_threshold})")
                return False

            # B. Direction Check (Only Longs)
            if current_dmp <= current_dmn:
                 self.logger.info(f"⚪ {symbol}: Wrong direction (+DI < -DI)")
                 return False

            # C. Setup Check: Retracement to EMA20
            # We look for a recent touch of EMA20 in the last few bars
            # Ideally, the Low of the current or previous bar touched/went below EMA
            # OR we are currently sitting on it.
            
            # Check last 3 bars for touch
            touched_ema = False
            touch_index = -1
            
            # Using verify touch logic
            for i in range(1, 4): # Last 3 closed bars + current
                low = df['low'].iloc[-i]
                high = df['high'].iloc[-i]
                ema = df['ema20'].iloc[-i]
                
                if low <= ema <= high: # Touched EMA range
                    touched_ema = True
                    touch_index = -i
                    break
                elif low <= ema: # Pierced below
                    touched_ema = True
                    touch_index = -i
                    break
            
            if not touched_ema:
                self.logger.info(f"⚪ {symbol}: No EMA20 retracement detected")
                return False

            # D. Trigger Check: Breakout of High of the touch bar (Buy Stop simulation)
            # Strategy says: "Place buy stop above the high of the previous bar (the one that touched)"
            # If we are live, we execute IF current price > High of Touch Bar
            
            touch_bar_high = df['high'].iloc[touch_index]
            
            # Trigger buffer (e.g., 0.1% or 1 cent)
            trigger_price = touch_bar_high * 1.001 
            
            if current_price < trigger_price:
                 self.logger.info(f"⚪ {symbol}: Waiting for trigger (Price {current_price:.2f} < {trigger_price:.2f})")
                 return False

            # ============================================================
            # ALL CRITERIA MET
            # ============================================================
            
            # Calculate dynamic Support Level for Stop Loss (Recent Swing Low)
            # Use Low of the touch bar or lowest of last 5
            swing_low = min(df['low'].iloc[-5:])
            
            opportunity['support_level'] = swing_low
            opportunity['invalid_price'] = swing_low # Set as invalidation for Priority 1 Stop Loss
            opportunity['pattern_completion'] = 90.0 # High confidence if trigger hit
            
            self.logger.info(
                f"✅ {symbol}: HOLY GRAIL SETUP APPROVED - "
                f"ADX={current_adx:.1f}, Touched EMA20, Triggered > {touch_bar_high:.2f}"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Error in Holy Grail logic for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def should_exit(self, symbol: str, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        """
        Evaluate exit criteria.
        Holy Grail relies on structural stops (Swing Low) and Trailing Stops managed
        by WorkerStopManager.

        However, we can force an exit if ADX drops significantly or trend reverses.
        For now, we delegate to WorkerStopManager for Stop Loss / Take Profit / Trailing.
        """
        # Delegate to WorkerStopManager for standard exit logic (SL, TP, Trailing, Time, EOD)
        entry_price = position.get('entry_price', 0)

        if entry_price <= 0:
            return False, "Invalid entry price"

        # Call WorkerStopManager to check all exit conditions
        should_exit, reason = self.stop_manager.check_exit(
            symbol=symbol,
            current_price=current_price,
            entry_price=entry_price,
            market_data=None,  # Could pass market data for FOMO detection if available
            position_metadata=position
        )

        return should_exit, reason

    def _bars_to_dataframe(self, bars: List) -> pd.DataFrame:
        """Helper to convert bars list to DataFrame"""
        data = {
            'timestamp': [b.timestamp for b in bars],
            'open': [b.open for b in bars],
            'high': [b.high for b in bars],
            'low': [b.low for b in bars],
            'close': [b.close for b in bars],
            'volume': [b.volume for b in bars]
        }
        return pd.DataFrame(data)
