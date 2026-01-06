# strategies/daily_plays_strategy.py
"""
Daily Plays Strategy - Breakout Intraday Strategy

Condiciones de entrada LONG:
1. Precio rompe el máximo de la primera media hora post apertura (9:30-10:00)
2. Volumen de la vela de ruptura es al menos 2× el volumen medio de las 10 velas anteriores  
3. EMA9 (1m timeframe) está por debajo del precio
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, time
import logging

try:
    from .base import BaseStrategy
    from core.interfaces import Signal, SignalType, Position, MarketData
    from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config
except ImportError:
    # For standalone execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from strategies.base import BaseStrategy
    from core.interfaces import Signal, SignalType, Position, MarketData
    from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config

logger = logging.getLogger(__name__)

class DailyPlaysConfig:
    """Configuración para Daily Plays Strategy - DEPRECATED - Use fallback_defaults instead"""
    
    def __init__(self):
        # This class is kept for backward compatibility but parameters are now handled via fallback_defaults
        pass

class DailyPlaysStrategy(BaseStrategy):
    """
    Daily Plays Strategy - Breakout intraday con condiciones específicas
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # FALLBACK DEFAULTS - All parameters ML-configurable
        fallback_defaults = {
            # Market timing parameters (ML-configurable)
            'market_open_hour': 9.5,  # 9:30 AM in decimal
            'first_half_hour_end': 10.0,  # 10:00 AM in decimal
            
            # Technical parameters (ML-configurable)
            'ema_period': 9,
            'volume_multiplier': 1.5,
            'lookback_bars': 8,
            
            # Risk management (ML-configurable) - REMOVED hardcoded stop_loss_pct
            # stop_loss_pct now uses config.ini fallback_stop_loss_pct = 0.05 (5%)
            'max_position_size': 1000,
            'take_profit_pct': 0.06,
            
            # Entry validation (ML-configurable)
            'min_price': 1.0,
            'max_price': 50.0,
            'min_volume': 100000,
            
            # FOMO detection parameters (ML-configurable)
            'fomo_threshold': 0.70,
            'fomo_critical_threshold': 0.88,
            'fomo_volume_explosion_multiplier': 6.0,
            'fomo_consecutive_green_bars': 4,
            'fomo_rsi_overbought_level': 80,
        }
        
        # Initialize with fallback defaults first to get logger
        super().__init__("DailyPlaysStrategy", fallback_defaults)
        
        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('DAILY_PLAYS_STRATEGY', fallback_defaults)
            
            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for Daily Plays strategy: {e}")
            # Keep fallback defaults
        
        self.strategy_name = "DailyPlaysStrategy"
        
        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()
        
        # Enable FOMO detection for DailyPlays (ML-configurable)
        fomo_config = {
            'fomo_threshold': self._parameters.get('fomo_threshold', 0.70),
            'critical_threshold': self._parameters.get('fomo_critical_threshold', 0.88),
            'volume_explosion_multiplier': self._parameters.get('fomo_volume_explosion_multiplier', 6.0),
            'consecutive_green_bars': self._parameters.get('fomo_consecutive_green_bars', 4),
            'rsi_overbought_level': self._parameters.get('fomo_rsi_overbought_level', 80)
        }
        
        if self.enable_fomo_exit(fomo_config):
            self.logger.info("🎪 FOMO Detection enabled for Daily Plays Strategy")
        else:
            self.logger.warning("⚠️ FOMO Detection could not be enabled")
        
        # Strategy state tracking
        self.first_half_hour_highs = {}  # ticker -> high price
        self.first_half_hour_tracked = {}  # ticker -> bool
        self.daily_volume_avg = {}  # ticker -> average volume
        
        logger.info(f"✅ {self.strategy_name} initialized with centralized stop loss management")
        logger.info(f"   Market open: {self._parameters.get('market_open_hour', 9.5)}")
        logger.info(f"   First 30min end: {self._parameters.get('first_half_hour_end', 10.0)}")
        logger.info(f"   EMA period: {self._parameters.get('ema_period', 9)}")
        logger.info(f"   Volume multiplier: {self._parameters.get('volume_multiplier', 1.5)}x")
    
    def _get_bar_value(self, bar, field: str):
        """Universal helper to get bar values from different data types"""
        if hasattr(bar, field):
            return getattr(bar, field)
        elif isinstance(bar, dict):
            return bar.get(field)
        else:
            raise ValueError(f"Cannot get {field} from bar of type {type(bar)}")
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return np.mean(prices) if prices else 0.0
        
        # Convert to pandas Series for EMA calculation
        price_series = pd.Series(prices)
        ema = price_series.ewm(span=period, adjust=False).mean()
        return float(ema.iloc[-1])
    
    def _get_current_time(self, bar: MarketData) -> time:
        """Get market time from bar timestamp (not system time)"""
        # FIXED: Use bar timestamp instead of system time for correct market hours detection
        return bar.timestamp.time()
    
    def _is_market_hours(self, current_time: time) -> bool:
        """Check if current time is during market hours"""
        market_open_hour = self._parameters.get('market_open_hour', 9.5)
        market_open = time(int(market_open_hour), int((market_open_hour % 1) * 60))
        market_close = time(16, 0)  # 4:00 PM
        
        return market_open <= current_time <= market_close
    
    def _is_first_half_hour(self, current_time: time) -> bool:
        """Check if we're in the first 30 minutes after market open"""
        market_open_hour = self._parameters.get('market_open_hour', 9.5)
        first_half_hour_end_hour = self._parameters.get('first_half_hour_end', 10.0)
        market_open_time = time(int(market_open_hour), int((market_open_hour % 1) * 60))
        first_half_hour_end_time = time(int(first_half_hour_end_hour), int((first_half_hour_end_hour % 1) * 60))
        return market_open_time <= current_time <= first_half_hour_end_time
    
    def _track_first_half_hour_high(self, ticker: str, bar: Any) -> None:
        """Track the high of the first 30 minutes after market open"""
        current_time = self._get_current_time(bar)

        # DEBUG: Print what's happening
        print(f"    DEBUG: _track_first_half_hour_high - {ticker} at {current_time}")
        print(f"    DEBUG: _is_first_half_hour({current_time}) = {self._is_first_half_hour(current_time)}")

        if self._is_first_half_hour(current_time):
            high_price = self._get_bar_value(bar, 'high')
            print(f"    DEBUG: In first 30min, high_price = ${high_price:.2f}")

            if ticker not in self.first_half_hour_highs:
                self.first_half_hour_highs[ticker] = high_price
                print(f"    DEBUG: First time setting high for {ticker}: ${high_price:.2f}")
            else:
                # Update if new high
                old_high = self.first_half_hour_highs[ticker]
                self.first_half_hour_highs[ticker] = max(old_high, high_price)
                print(f"    DEBUG: Updated high for {ticker}: ${old_high:.2f} -> ${self.first_half_hour_highs[ticker]:.2f}")
        elif current_time > time(int(self._parameters.get('first_half_hour_end', 10.0)), int((self._parameters.get('first_half_hour_end', 10.0) % 1) * 60)):
            # Mark first half hour as complete
            if ticker not in self.first_half_hour_tracked:
                self.first_half_hour_tracked[ticker] = True
                logger.debug(f"{ticker}: First 30min high tracked: ${self.first_half_hour_highs.get(ticker, 0):.2f}")
    
    def _check_volume_condition(self, ticker: str, current_bars: List[Any]) -> bool:
        """Check if current volume is at least 2x the average of last 10 bars"""
        if len(current_bars) < self._parameters.get('lookback_bars', 8) + 1:
            return False
        
        # Get current bar volume
        current_volume = self._get_bar_value(current_bars[-1], 'volume')
        
        # Calculate average volume of previous 10 bars
        previous_volumes = []
        for bar in current_bars[-self._parameters.get('lookback_bars', 8)-1:-1]:  # Exclude current bar
            volume = self._get_bar_value(bar, 'volume')
            previous_volumes.append(volume)
        
        avg_volume = np.mean(previous_volumes) if previous_volumes else 0
        
        # Check 2x condition
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        meets_condition = volume_ratio >= self._parameters.get('volume_multiplier', 1.5)
        
        if meets_condition:
            logger.info(f"{ticker}: Volume condition met - {current_volume:,.0f} vs avg {avg_volume:,.0f} ({volume_ratio:.1f}x)")
        else:
            logger.debug(f"{ticker}: Volume condition NOT met - {current_volume:,.0f} vs avg {avg_volume:,.0f} ({volume_ratio:.1f}x, need {self._parameters.get('volume_multiplier', 1.5)}x)")
        
        return meets_condition
    
    def _check_ema_condition(self, ticker: str, current_bars: List[Any]) -> bool:
        """Check if EMA9 is below current price"""
        if len(current_bars) < self._parameters.get('ema_period', 9):
            return False
        
        # Extract prices for EMA calculation
        prices = []
        for bar in current_bars[-self._parameters.get('ema_period', 9):]:
            close_price = self._get_bar_value(bar, 'close')
            prices.append(close_price)
        
        # Calculate EMA9
        ema9 = self._calculate_ema(prices, self._parameters.get('ema_period', 9))
        current_price = self._get_bar_value(current_bars[-1], 'close')
        
        meets_condition = current_price > ema9
        
        if meets_condition:
            logger.info(f"{ticker}: EMA condition met - Price ${current_price:.2f} > EMA9 ${ema9:.2f}")
        else:
            logger.debug(f"{ticker}: EMA condition NOT met - Price ${current_price:.2f} <= EMA9 ${ema9:.2f}")
        
        return meets_condition
    
    def _check_price_breakout(self, ticker: str, bar: Any) -> bool:
        """Check if current price breaks the first 30-minute high"""
        if ticker not in self.first_half_hour_highs:
            return False
        
        if not self.first_half_hour_tracked.get(ticker, False):
            return False  # Still in first 30 minutes
        
        current_high = self._get_bar_value(bar, 'high')
        first_half_hour_high = self.first_half_hour_highs[ticker]
        
        # Check for breakout
        breakout = current_high > first_half_hour_high
        
        if breakout:
            logger.info(f"{ticker}: BREAKOUT! Current high ${current_high:.2f} > First 30min high ${first_half_hour_high:.2f}")
        
        return breakout
    
    def _validate_entry_conditions(self, ticker: str, bar: Any) -> bool:
        """Validate basic entry conditions (price range, volume, etc.)"""
        current_price = self._get_bar_value(bar, 'close')
        current_volume = self._get_bar_value(bar, 'volume')
        
        # Price range check
        min_price = self._parameters.get('min_price', 1.0)
        max_price = self._parameters.get('max_price', 50.0)
        if not (min_price <= current_price <= max_price):
            logger.debug(f"{ticker}: Price ${current_price:.2f} outside range ${min_price}-${max_price}")
            return False
        
        # Minimum volume check
        min_volume = self._parameters.get('min_volume', 100000)
        if current_volume < min_volume:
            logger.debug(f"{ticker}: Volume {current_volume:,} below minimum {min_volume:,}")
            return False
        
        # Market hours check
        current_time = self._get_current_time(bar)
        if not self._is_market_hours(current_time):
            logger.debug(f"{ticker}: Outside market hours {current_time}")
            return False
        
        # Must be after first 30 minutes
        first_half_hour_end_hour = self._parameters.get('first_half_hour_end', 10.0)
        first_half_hour_end_time = time(int(first_half_hour_end_hour), int((first_half_hour_end_hour % 1) * 60))
        if current_time <= first_half_hour_end_time:
            logger.debug(f"{ticker}: Still in first 30 minutes {current_time}")
            return False
        
        return True
    
    def analyze(self, ticker: str, data: List[MarketData], 
                current_positions: Dict[str, Position]) -> Optional[Signal]:
        """
        Analyze market data for Daily Plays Strategy entry signals
        """
        try:
            if not data:
                return None

            current_bar = data[-1]

            # ALWAYS track first 30-minute high regardless of data length
            self._track_first_half_hour_high(ticker, current_bar)

            # For signal generation, we need enough data for EMA and volume analysis
            ema_period = self._parameters.get('ema_period', 9)
            lookback_bars = self._parameters.get('lookback_bars', 8)
            if len(data) < ema_period + lookback_bars:
                logger.debug(f"{ticker}: Insufficient data for signal generation - need {ema_period + lookback_bars}, got {len(data)}")
                return None
            
            # Skip if already have position
            if ticker in current_positions:
                return None
            
            # Validate basic entry conditions
            if not self._validate_entry_conditions(ticker, current_bar):
                logger.debug(f"{ticker}: Basic entry conditions not met")
                return None
            
            # Check all three main conditions
            conditions_met = []

            # 1. Price breakout condition
            breakout_condition = self._check_price_breakout(ticker, current_bar)
            conditions_met.append(("Breakout", breakout_condition))
            print(f"    DEBUG: Breakout condition = {breakout_condition}")

            # 2. Volume condition (and get volume info for metadata)
            volume_condition = self._check_volume_condition(ticker, data)
            conditions_met.append(("Volume 2x", volume_condition))
            print(f"    DEBUG: Volume condition = {volume_condition}")

            # Get volume info for metadata
            current_volume = self._get_bar_value(current_bar, 'volume')
            if len(data) >= self._parameters.get('lookback_bars', 8) + 1:
                previous_volumes = [self._get_bar_value(bar, 'volume') for bar in data[-self._parameters.get('lookback_bars', 8)-1:-1]]
                avg_volume = np.mean(previous_volumes) if previous_volumes else 0
            else:
                avg_volume = current_volume  # Fallback

            # 3. EMA condition
            ema_condition = self._check_ema_condition(ticker, data)
            conditions_met.append(("EMA9 below price", ema_condition))
            print(f"    DEBUG: EMA condition = {ema_condition}")

            # Log condition status
            current_price = self._get_bar_value(current_bar, 'close')
            print(f"    DEBUG: All conditions: {[name + '=' + str(met) for name, met in conditions_met]}")
            logger.debug(f"{ticker} @ ${current_price:.2f}: " +
                        " | ".join([f"{name}: {'✅' if met else '❌'}" for name, met in conditions_met]))
            
            # All conditions must be met
            if all(met for _, met in conditions_met):
                print(f"    DEBUG: ✅ ALL CONDITIONS MET! Creating signal...")
                # Calculate position size
                position_size = min(self._parameters.get('max_position_size', 1000),
                                  int(10000 / current_price))  # $10k position max
                print(f"    DEBUG: Position size calculated: {position_size}")
                
                # Create signal
                signal = Signal(
                    signal_id=f"daily_plays_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    symbol=ticker,
                    signal_type=SignalType.LONG,
                    price=current_price,
                    timestamp=datetime.now(),
                    strength=0.8,  # High confidence when all conditions met
                    strategy_name=self.strategy_name,
                    metadata={
                        'strategy': 'DailyPlays',
                        'entry_type': 'breakout',
                        'setup_type': 'first_30min_breakout',
                        'pattern': 'daily_plays_breakout',
                        'first_30min_high': self.first_half_hour_highs.get(ticker),
                        'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 1.0,
                        'conditions_met': dict(conditions_met)
                    }
                )
                
                # Register position with centralized stop manager
                self._register_position_with_stop_manager(ticker, current_bar, signal)
                
                print(f"    DEBUG: 🎯 SIGNAL CREATED! Returning signal...")
                logger.info(f"🚀 {ticker}: DAILY PLAYS ENTRY SIGNAL!")
                logger.info(f"   Entry: ${current_price:.2f}")
                logger.info(f"   Size: {position_size} shares")
                logger.info(f"   Registered with centralized stop manager")

                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error in DailyPlaysStrategy analysis for {ticker}: {e}")
            return None
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Required method from BaseStrategy - analyze individual bar"""
        symbol = bar.symbol
        
        # Get historical bars from multi-strategy engine
        if hasattr(self, 'bars_history') and symbol in self.bars_history:
            all_bars = self.bars_history[symbol]
        else:
            all_bars = [bar]
        
        return self.analyze(symbol, all_bars, self.positions)
    
    def on_position_update(self, symbol: str, position: Position):
        """Handle position updates"""
        self.positions[symbol] = position
        self.logger.debug(f"Position updated for {symbol}: {position.quantity} shares @ ${position.avg_price:.2f}")
    
    def _register_position_with_stop_manager(self, symbol: str, bar, signal: Signal):
        """Register the new position with SMALLCAP-OPTIMIZED centralized stop loss manager"""

        # SMALLCAPS DAILY PLAYS: Use global config.ini parameters optimized for smallcaps
        # Daily plays are momentum-based intraday trades requiring:
        # - fallback_stop_loss_pct = 0.06 (6% for volatility)
        # - enable_dynamic_ema_trailing = true (responsive to momentum)
        # - ema_trailing_periods = 5 (fast EMA-5 for intraday)
        # - max_hold_minutes = 180 (3 hours max for momentum plays)
        stop_params = create_stop_params_from_config(self._parameters)

        # Register with stop manager
        self.stop_manager.register_position(
            symbol=symbol,
            entry_price=signal.price,
            entry_time=bar.timestamp,
            side='bullish',
            strategy_name="DailyPlays_Smallcaps_Optimized",
            stop_params=stop_params
        )
        logger.info(f"📊 {symbol}: DAILY PLAYS SMALLCAP-OPTIMIZED - "
                   f"6% stop, EMA-5 trailing, 3h momentum window")
    
    def should_exit(self, symbol: str, current_bar: MarketData,
                   position: Position) -> Optional[Signal]:
        """SMALLCAP-OPTIMIZED exit with centralized stop manager"""
        # SMALLCAPS: Use centralized stop_manager with smallcap-optimized parameters
        if hasattr(self, 'stop_manager') and self.stop_manager:
            exit_signal = self.stop_manager.check_exit_conditions(
                symbol=symbol,
                current_bar=current_bar
            )
            if exit_signal:
                return Signal(
                    symbol=symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=1.0,
                    price=current_bar.close,
                    timestamp=current_bar.timestamp,
                    strategy_name="DailyPlays_Smallcaps_Optimized",
                    metadata={
                        'reason': exit_signal.get('reason', 'stop_manager'),
                        'exit_type': exit_signal.get('exit_reason', 'advanced_stop'),
                        'entry_price': position.avg_price,
                        'pnl_pct': exit_signal.get('pnl_pct', 0),
                        'smallcap_features': 'EMA_trailing,time_exits,volatility_filter'
                    }
                )
        return None

    def get_strategy_info(self) -> Dict[str, Any]:
        """Return strategy information"""
        return {
            'name': self.strategy_name,
            'type': 'Intraday Breakout',
            'timeframe': '1m',
            'description': 'Breakout strategy based on first 30-minute high with volume and EMA confirmation',
            'parameters': {
                'ema_period': self._parameters.get('ema_period', 9),
                'volume_multiplier': self._parameters.get('volume_multiplier', 1.5),
                # stop_loss_pct removed - uses config.ini fallback_stop_loss_pct = 0.05
                'take_profit_pct': self._parameters.get('take_profit_pct', 0.06),
                'first_30min_window': f"{self._parameters.get('market_open_hour', 9.5)} - {self._parameters.get('first_half_hour_end', 10.0)}"
            },
            'conditions': [
                'Price breaks first 30-minute high',
                f'Volume >= {self._parameters.get("volume_multiplier", 1.5)}x average of last {self._parameters.get("lookback_bars", 8)} bars',
                'EMA9 below current price'
            ]
        }

# Register strategy for dynamic loading
def get_strategy_class():
    """Return the strategy class for dynamic loading"""
    return DailyPlaysStrategy

def get_default_config():
    """Return default configuration for this strategy"""
    return DailyPlaysConfig()

if __name__ == "__main__":
    # Test strategy initialization
    strategy = DailyPlaysStrategy()
    info = strategy.get_strategy_info()
    
    print("🧪 Daily Plays Strategy Test")
    print("=" * 50)
    print(f"Strategy: {info['name']}")
    print(f"Type: {info['type']}")
    print(f"Description: {info['description']}")
    print("\nConditions:")
    for i, condition in enumerate(info['conditions'], 1):
        print(f"  {i}. {condition}")
    print("\nParameters:")
    for key, value in info['parameters'].items():
        print(f"  {key}: {value}")
    print("=" * 50)
    print("✅ Daily Plays Strategy ready!")