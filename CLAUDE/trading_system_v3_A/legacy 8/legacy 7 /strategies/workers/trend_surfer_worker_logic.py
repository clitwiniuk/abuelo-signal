"""
Trend Surfer Worker Logic
Un trabajador universal diseñado para operar tendencias intradía en Smallcaps,
filtrando mercados laterales y operando solo en condiciones óptimas.

Modos de operación:
1. PULLBACK (La Ola): Compra retrocesos a EMAs en tendencias fuertes.
2. BREAKOUT (El Cohete): Compra rupturas de volatilidad con volumen.
3. CROSS (Golden Cross): Compra cruces de medias confirmados.
"""

import logging
from typing import Dict, Any, Tuple
import pandas as pd
import pandas_ta as ta
from .base_worker_logic import BaseWorkerLogic

class TrendSurferWorkerLogic(BaseWorkerLogic):
    """
    Worker multimodo para operar tendencias alcistas en intradía (M1).
    """

    def __init__(self, broker, risk_manager=None, config=None, execution_engine=None):
        # Support variable initialization with and without worker_name argument for compatibility
        super().__init__(
            worker_name='trend_surfer',
            broker=broker,
            config=config
        )

        # Config Helper
        def get_cfg(key, default, type_func=float):
            section = 'TREND_SURFER'
            if not config: return default
            try:
                # Try standard configparser methods
                method_name = f'get{type_func.__name__}' if type_func != str else 'get'
                if hasattr(config, method_name):
                    method = getattr(config, method_name)
                    return method(section, key, fallback=default)
                elif hasattr(config, 'get'):
                    val = config.get(section, key)
                    return type_func(val) if val is not None else default
            except:
                return default
            return default

        # --- Configurations ---
        self.mode = get_cfg('mode', 'PULLBACK', str).upper() # PULLBACK, BREAKOUT, CROSS
        
        # Universal Filters (Anti-Chop)
        self.min_adx = get_cfg('min_adx', 20.0) # ADX min to confirm trend
        self.require_price_above_vwap = get_cfg('require_price_above_vwap', True, bool)
        self.min_volume_ratio = get_cfg('min_volume_ratio', 1.5)
        
        # EMA Settings
        self.fast_ema = get_cfg('fast_ema', 9, int)
        self.slow_ema = get_cfg('slow_ema', 20, int)
        self.trend_ema = get_cfg('trend_ema', 50, int)
        
        
        # Mode Specifics
        self.breakout_lookback = get_cfg('breakout_lookback', 20, int) # Bars for High of Day/Period
        
        # Initialize Stop Manager (CRITICAL for Exits)
        from .worker_stop_manager import create_worker_stop_manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'TREND_SURFER')
        else:
            # Fallback for testing without full config
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=get_cfg('stop_loss_pct', 2.0),
                take_profit_pct=get_cfg('take_profit_pct', 6.0),
                trailing_activation=get_cfg('trailing_activation', 1.5),
                trailing_distance=get_cfg('trailing_distance', 0.5)
            ))
        
        self.logger.info(f"🏄 TrendSurfer initialized in mode: {self.mode}")
        self.logger.info(f"   Filters: ADX>{self.min_adx}, Price>VWAP={self.require_price_above_vwap}")

    def _bars_to_dataframe(self, bars):
        """Helper to convert list of bars to DataFrame"""
        try:
            data = []
            for bar in bars:
                data.append({
                    'timestamp': bar.timestamp,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': float(bar.volume)
                })
            return pd.DataFrame(data)
        except Exception as e:
            self.logger.error(f"Error converting bars to DF: {e}")
            return pd.DataFrame()

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """Evaluates entry based on selected mode and filters."""
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            
            # 0. Check duplicate position
            # (Assuming broker checks are done or we check local state)
            if symbol in self.active_positions:
                return False

            # 1. Get Bars & Prepare Data
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 50:
                self.logger.info(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0})")
                return False

            df = self._bars_to_dataframe(bars)
            if df.empty: return False
            
            # 2. Calculate Common Indicators
            # ADX
            try:
                adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
                current_adx = adx_df['ADX_14'].iloc[-1]
            except:
                current_adx = 0
            
            # EMAs
            df['ema_fast'] = ta.ema(df['close'], length=self.fast_ema)
            df['ema_slow'] = ta.ema(df['close'], length=self.slow_ema)
            df['ema_trend'] = ta.ema(df['close'], length=self.trend_ema)
            
            # VWAP (using helper from BaseWorker)
            current_price = opportunity.get('current_price', bars[-1].close)
            vwap = self.calculate_vwap_from_bars(bars)
            
            current_bar = df.iloc[-1]
            prev_bar = df.iloc[-2]
            
            # 3. UNIVERSAL FILTERS (The "Anti-Chop" System)
            
            # A. ADX Filter (Must be trending)
            if current_adx < self.min_adx:
                self.logger.debug(f"⚪ {symbol}: Choppy Market (ADX {current_adx:.1f} < {self.min_adx})")
                return False
                
            # B. VWAP Filter (Must be in bullish territory)
            if self.require_price_above_vwap and vwap:
                if current_price < vwap:
                    self.logger.debug(f"⚪ {symbol}: Price below VWAP (Bearish)")
                    return False
            
            # C. Trend EMA Filter (Long term trend)
            if current_bar['ema_trend'] and current_price < current_bar['ema_trend']:
                 self.logger.debug(f"⚪ {symbol}: Price below Trend EMA {self.trend_ema}")
                 return False

            # 4. STRATEGY MODES
            
            if self.mode == 'PULLBACK':
                # Strategy: Price touches Fast/Slow EMA and holds
                # Logic: Low touched EMA, but Close > EMA (Rejection of lower prices)
                
                # Check touch of Fast EMA
                touched_fast = (current_bar['low'] <= current_bar['ema_fast']) and (current_bar['close'] > current_bar['ema_fast'])
                
                # Check touch of Slow EMA
                touched_slow = (current_bar['low'] <= current_bar['ema_slow']) and (current_bar['close'] > current_bar['ema_slow'])
                
                if touched_fast or touched_slow:
                    # Confirm we are not crashing down (Previous bar should not be a massive red candle engulfing everything)
                    # Simple check: Close > Open
                    is_bullish_candle = current_bar['close'] > current_bar['open']
                    
                    if is_bullish_candle:
                        self.logger.info(f"🌊 {symbol}: PULLBACK Entry! Touched EMA, Bullish Candle. ADX={current_adx:.1f}")
                        return True
            
            elif self.mode == 'BREAKOUT':
                # Strategy: Breakout of N-period High with Volume
                lookback = self.breakout_lookback
                recent_high = df['high'].iloc[-lookback:-1].max() # Exclude current bar to detect break
                
                if current_price > recent_high:
                    # Check Volume Surge
                    avg_vol = df['volume'].iloc[-20:-1].mean()
                    current_vol = current_bar['volume']
                    
                    if avg_vol > 0 and (current_vol / avg_vol) > self.min_volume_ratio:
                        self.logger.info(f"🚀 {symbol}: BREAKOUT Entry! Broken ${recent_high:.2f} with Vol {current_vol/avg_vol:.1f}x")
                        return True
                        
            elif self.mode == 'CROSS':
                # Strategy: Golden Cross (Fast crosses above Slow)
                # Check if cross happened in current bar
                
                curr_fast = current_bar['ema_fast']
                curr_slow = current_bar['ema_slow']
                prev_fast = prev_bar['ema_fast']
                prev_slow = prev_bar['ema_slow']
                
                # Cross UP: Prev Fast <= Prev Slow AND Curr Fast > Curr Slow
                golden_cross = (prev_fast <= prev_slow) and (curr_fast > curr_slow)
                
                if golden_cross:
                    self.logger.info(f"✨ {symbol}: GOLDEN CROSS Entry! EMA{self.fast_ema} crossed EMA{self.slow_ema}")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"❌ Error in TrendSurfer ({self.mode}): {e}")
            return False

    async def should_exit(self, symbol: str, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        """Exit logic using centralized StopManager."""
        try:
            entry_price = position.get('entry_price', 0)
            if entry_price == 0:
                return False, ""

            # Standard StopManager check (SL, TP, Time, Trailing)
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=None, # Passed if needed for advanced logic
                position_metadata=position
            )
            
            return should_exit, reason
        except Exception as e:
            self.logger.error(f"❌ Error in exit logic: {e}")
            return False, ""

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """Override to register position with stop manager"""
        # Execute normal entry
        success = await super()._execute_entry(opportunity)

        if success:
            from datetime import datetime
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Register with stop manager for tracking
            self.stop_manager.register_position(symbol, datetime.now())
            self.logger.debug(f"📝 Registered {symbol} with TrendSurfer stop manager")

        return success

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """Override to unregister position from stop manager"""
        # Unregister from stop manager
        self.stop_manager.unregister_position(symbol)

        # Execute normal exit
        await super()._execute_exit(symbol, reason, current_price)
