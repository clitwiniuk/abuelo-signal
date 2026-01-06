# strategies/explosive_volume_strategy.py
"""
Explosive Volume Strategy - Detector de explosiones de volumen

Diseñado específicamente para detectar oportunidades como la explosión de GV:
- Volumen >15x promedio = entrada inmediata
- Volumen >10x + movimiento >2% = momentum explosion
- Volumen >5x en zona de acumulación = recovery pattern

Esta estrategia funciona independientemente de VWAP y otros filtros técnicos.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime as dt, timezone
import configparser
from pathlib import Path

from core.interfaces import IStrategy, Signal, Position, MarketData, SignalType
from .base import BaseStrategy


class ExplosiveVolumeStrategy(BaseStrategy):
    """
    Detector de explosiones de volumen para smallcaps
    
    Funciona como un "safety net" que captura oportunidades que otros
    sistemas podrían perderse por ser demasiado conservadores.
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # FALLBACK DEFAULTS - All parameters ML-configurable
        fallback_defaults = {
            # Thresholds de volumen explosivo (ML-configurable)
            'explosive_volume_min': 6.0,
            'high_volume_min': 4.0,
            'moderate_volume_min': 2.5,
            
            # Thresholds de momentum (ML-configurable)
            'explosive_momentum_min': 2.0,
            'high_momentum_min': 1.0,
            'moderate_momentum_min': 0.3,
            
            # Lookback periods (ML-configurable)
            'volume_lookback': 10,
            'momentum_lookback': 3,
            'min_history_bars': 5,
            
            # Position configuration (ML-configurable)
            'min_price': 0.15,
            'max_price': 120.0,
            'max_position_value': 250.0,
            'min_position_value': 30.0,
            'risk_per_trade': 0.03,
            
            # Risk management (ML-configurable)
            'stop_loss_pct': 0.12,
            'take_profit_pct': 0.25,
            'trailing_activation': 0.08,
            'trailing_distance': 0.06,
            
            # Trading control (ML-configurable)
            'max_daily_signals': 10,
            'cooldown_minutes': 5,
            'max_concurrent_positions': 5,
            
            # Market hours (ML-configurable)
            'enable_premarket': True,
            'enable_afterhours': True,
            'avoid_first_30min': False,
            'avoid_last_30min': False,
            
            # FOMO detection parameters (ML-configurable)
            'fomo_threshold': 0.65,
            'fomo_critical_threshold': 0.85,
            'fomo_volume_explosion_multiplier': 5.0,
            'fomo_consecutive_green_bars': 3,
            'fomo_rsi_overbought_level': 75,
        }
        
        # Initialize with fallback defaults first to get logger
        super().__init__("ExplosiveVolume", fallback_defaults)
        
        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('EXPLOSIVE_VOLUME_STRATEGY', fallback_defaults)
            
            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for ExplosiveVolume strategy: {e}")
            # Keep fallback defaults
        
        # Enable FOMO detection for ExplosiveVolume (ML-configurable)
        fomo_config = {
            'fomo_threshold': self._parameters.get('fomo_threshold', 0.65),
            'critical_threshold': self._parameters.get('fomo_critical_threshold', 0.85),
            'volume_explosion_multiplier': self._parameters.get('fomo_volume_explosion_multiplier', 5.0),
            'consecutive_green_bars': self._parameters.get('fomo_consecutive_green_bars', 3),
            'rsi_overbought_level': self._parameters.get('fomo_rsi_overbought_level', 75)
        }
        
        if self.enable_fomo_exit(fomo_config):
            self.logger.info("🎪 FOMO Detection enabled for Explosive Volume Strategy")
        else:
            self.logger.warning("⚠️ FOMO Detection could not be enabled")
        
        # Tracking específico para explosiones
        self.daily_signals_count = 0
        self.last_explosion_time = {}      # symbol -> timestamp
        self.explosion_tracking = {}       # symbol -> explosion_data
        
        self.logger.info("💥 Explosive Volume Strategy initialized - ready to catch volume explosions!")
    
    def _load_global_config(self) -> Dict[str, Any]:
        """Load global configuration from config.ini"""
        try:
            config_path = Path(__file__).parent.parent / 'config.ini'
            if not config_path.exists():
                self.logger.warning("config.ini not found, using defaults")
                return {}
            
            config = configparser.ConfigParser()
            config.read(config_path)
            
            global_config = {}
            if config.has_section('GLOBAL'):
                global_config['min_price'] = config.getfloat('GLOBAL', 'min_price', fallback=0.20)
                global_config['max_price'] = config.getfloat('GLOBAL', 'max_price', fallback=100.0)
                global_config['commission_per_share'] = config.getfloat('GLOBAL', 'commission_per_share', fallback=0.005)
                global_config['min_commission'] = config.getfloat('GLOBAL', 'min_commission', fallback=1.0)
                global_config['slippage_bps'] = config.getfloat('GLOBAL', 'slippage_bps', fallback=5.0)
                
                self.logger.info(f"📋 Global config loaded: min_price=${global_config['min_price']:.2f}, max_price=${global_config['max_price']:.0f}")
            
            return global_config
            
        except Exception as e:
            self.logger.error(f"Error loading global config: {e}")
            return {}
    
    async def _initialize_strategy(self) -> None:
        """Initialize explosive volume strategy"""
        self.logger.info("🚀 Initializing Explosive Volume Strategy for smallcaps")
        self.logger.info(f"💥 Explosive Volume thresholds:")
        self.logger.info(f"   EXTREME: {self._parameters.get('explosive_volume_min', 15.0):.0f}x volume (bypasses all filters)")
        self.logger.info(f"   HIGH: {self._parameters.get('high_volume_min', 10.0):.0f}x volume + {self._parameters.get('high_momentum_min', 2.0):.1f}% momentum")
        self.logger.info(f"   MODERATE: {self._parameters.get('moderate_volume_min', 5.0):.0f}x volume + {self._parameters.get('moderate_momentum_min', 1.0):.1f}% momentum")
        self.logger.info(f"⚙️ Risk management: {self._parameters.get('stop_loss_pct', 0.15)*100:.0f}% stop, {self._parameters.get('take_profit_pct', 0.30)*100:.0f}% target")
        self.logger.info(f"🎯 Daily limits: {self._parameters.get('max_daily_signals', 3)} signals, {self._parameters.get('cooldown_minutes', 30)}min cooldown")
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar for explosive volume conditions"""
        symbol = bar.symbol
        
        try:
            # 1. Basic filters
            if not self._passes_basic_filters(bar):
                return None
            
            # 2. Check daily limits
            if self.daily_signals_count >= self._parameters.get('max_daily_signals', 3):
                return None
            
            # 3. Check cooldown
            if self._is_in_cooldown(symbol, bar.timestamp):
                return None
            
            # 4. Need minimum history
            if len(self.bars_history[symbol]) < self._parameters.get('min_history_bars', 5):
                return None
            
            # 5. Detect explosive conditions
            volume_spike, momentum, explosion_type = self._analyze_explosive_conditions(symbol, bar)
            
            if explosion_type is None:
                return None  # No explosive conditions detected
            
            # 6. Generate explosive signal
            signal = await self._generate_explosive_signal(symbol, bar, volume_spike, momentum, explosion_type)
            return signal
            
        except Exception as e:
            self.logger.error(f"💥 Error analyzing explosive volume for {symbol}: {e}")
            return None
    
    def _passes_basic_filters(self, bar: MarketData) -> bool:
        """Basic filters - very permissive for explosions"""
        price = bar.close
        volume = bar.volume
        
        # Price range (very wide) - use .get() for safety
        min_price = self._parameters.get('min_price', 0.10)  # Global fallback
        max_price = self._parameters.get('max_price', 100.0)
        if price < min_price or price > max_price:
            return False
        
        # Must have some volume
        if volume <= 0:
            return False
        
        return True
    
    def _is_in_cooldown(self, symbol: str, current_timestamp: dt = None) -> bool:
        """Check if symbol is in cooldown period"""
        if symbol not in self.last_explosion_time:
            return False
        
        cooldown_minutes = self._parameters.get('cooldown_minutes', 5)
        
        # Use current bar timestamp if provided (for simulation), otherwise use real time
        if current_timestamp:
            time_diff = (current_timestamp - self.last_explosion_time[symbol]).total_seconds() / 60
        else:
            time_diff = (dt.now(timezone.utc) - self.last_explosion_time[symbol]).total_seconds() / 60
        
        return time_diff < cooldown_minutes
    
    def _analyze_explosive_conditions(self, symbol: str, bar: MarketData) -> tuple[float, float, Optional[str]]:
        """
        Analyze for explosive volume and momentum conditions
        OPTIMIZED FOR EARLY ENTRY - Detects building explosions before peak
        
        Returns:
            tuple: (volume_spike_ratio, momentum_pct, explosion_type)
            explosion_type: 'EXTREME', 'HIGH', 'MODERATE', 'PRE_EXPLOSION' or None
        """
        try:
            bars = self.bars_history[symbol]
            current_bar = bar
            
            # Calculate volume spike
            lookback = min(self._parameters.get('volume_lookback', 10), len(bars) - 1)
            if lookback < 2:
                return 1.0, 0.0, None
                
            recent_bars = bars[-lookback:]
            avg_volume = sum(b.volume for b in recent_bars) / lookback
            volume_spike = current_bar.volume / max(avg_volume, 1)
            
            # Calculate momentum (best of 1-3 bars)
            momentum_pct = 0.0
            lookback_momentum = min(self._parameters.get('momentum_lookback', 3), len(bars))
            
            for i in range(1, min(lookback_momentum + 1, len(bars))):
                price_change = ((current_bar.close - bars[-i-1].close) / bars[-i-1].close) * 100
                if abs(price_change) > abs(momentum_pct):
                    momentum_pct = price_change
            
            # 🚀 NEW: Detect PRE-EXPLOSION conditions for early entry
            # Look for volume building + price compression before major moves
            pre_explosion_detected = False
            if len(bars) >= 5:
                last_5_volumes = [b.volume for b in bars[-5:]]
                volume_trend = (current_bar.volume - last_5_volumes[0]) / max(last_5_volumes[0], 1)
                
                # Pre-explosion: Volume increasing + price near support/resistance
                if (volume_spike >= 2.0 and volume_trend > 0.5 and 
                    abs(momentum_pct) >= 0.5 and current_bar.volume > avg_volume * 1.5):
                    pre_explosion_detected = True
            
            # Determine explosion type - PRIORITIZE EARLY ENTRY
            explosion_type = None
            
            # PRE-EXPLOSION: Early entry signal (NEW - highest priority)
            if pre_explosion_detected and volume_spike < 5.0:  # Before major spike
                explosion_type = 'PRE_EXPLOSION'
                self.logger.warning(f"🎯 {symbol}: PRE-EXPLOSION DETECTED - {volume_spike:.1f}x volume building, {momentum_pct:.1f}% momentum")
            
            # EXTREME: Volume >6x (ML híbrido - detectar antes)
            elif volume_spike >= self._parameters.get('explosive_volume_min', 6.0):
                explosion_type = 'EXTREME'
                self.logger.warning(f"💥 {symbol}: EXTREME EXPLOSION - {volume_spike:.1f}x volume, {momentum_pct:.1f}% momentum")
            
            # HIGH: Volume >4x + momentum (ML híbrido - más sensible)
            elif (volume_spike >= self._parameters.get('high_volume_min', 4.0) and 
                  abs(momentum_pct) >= self._parameters.get('high_momentum_min', 1.0)):
                explosion_type = 'HIGH'  
                self.logger.info(f"🔥 {symbol}: HIGH EXPLOSION - {volume_spike:.1f}x volume + {momentum_pct:.1f}% momentum")
            
            # MODERATE: Volume >2.5x + micromovimiento (ML híbrido - muy sensible)
            elif (volume_spike >= self._parameters.get('moderate_volume_min', 2.5) and
                  abs(momentum_pct) >= self._parameters.get('moderate_momentum_min', 0.3)):
                explosion_type = 'MODERATE'
                self.logger.info(f"⚡ {symbol}: MODERATE EXPLOSION - {volume_spike:.1f}x volume + {momentum_pct:.1f}% momentum")
            
            return volume_spike, momentum_pct, explosion_type
            
        except Exception as e:
            self.logger.error(f"Error analyzing explosive conditions for {symbol}: {e}")
            return 1.0, 0.0, None
    
    async def _generate_explosive_signal(self, symbol: str, bar: MarketData, volume_spike: float, 
                                       momentum: float, explosion_type: str) -> Optional[Signal]:
        """Generate signal for explosive conditions"""
        try:
            # For explosive volume, direction matters less than the explosion itself
            # Always generate LONG signals for explosive volume regardless of momentum direction
            # The idea is that explosive volume often precedes major moves up
            signal_type = SignalType.LONG
            
            # Log the original momentum direction for analysis
            momentum_direction = "bullish" if momentum >= 0 else "bearish"
            self.logger.info(f"💥 {symbol}: Explosive signal with {momentum_direction} momentum ({momentum:.1f}%)")
            
            # Calculate confidence based on explosion type
            confidence_map = {
                'PRE_EXPLOSION': 2.5,  # HIGHEST - Early entry advantage
                'EXTREME': 2.0,        # Maximum confidence for extreme explosions
                'HIGH': 1.5,           # High confidence 
                'MODERATE': 1.0        # Standard confidence
            }
            confidence = confidence_map.get(explosion_type, 1.0)
            
            # Boost confidence for very high volume
            if volume_spike >= 20.0:
                confidence *= 1.2
            
            # Position sizing based on explosion strength
            position_multiplier_map = {
                'PRE_EXPLOSION': 1.8,  # Largest positions - early entry advantage
                'EXTREME': 1.5,        # Larger positions for extreme explosions
                'HIGH': 1.2,           # Slightly larger positions
                'MODERATE': 1.0        # Standard position size
            }
            position_multiplier = position_multiplier_map.get(explosion_type, 1.0)
            
            # Create signal with explosion metadata
            signal = Signal(
                signal_id=f"explosive_{symbol}_{explosion_type.lower()}_{int(dt.now(timezone.utc).timestamp())}",
                symbol=symbol,
                signal_type=signal_type,
                strength=confidence,
                price=bar.close,
                timestamp=bar.timestamp,
                strategy_name="Explosive_Volume",
                metadata={
                    'strategy_name': 'explosive_volume',
                    'setup_type': f'{explosion_type.lower()}_explosion',
                    'pattern': f'explosive_vol_{explosion_type}',
                    'volume_ratio': volume_spike,
                    'confidence': confidence,
                    'explosion_type': explosion_type,
                    'momentum': momentum,
                    'position_multiplier': position_multiplier,
                    
                    # Risk management
                    'stop_loss_pct': self._parameters.get('stop_loss_pct', 0.15),
                    'take_profit_pct': self._parameters.get('take_profit_pct', 0.30),
                    'trailing_activation': self._parameters.get('trailing_activation', 0.10),
                    'trailing_distance': self._parameters.get('trailing_distance', 0.08),
                    
                    # Special flags
                    'is_explosive': True,
                    'bypass_vwap': True,  # This strategy bypasses VWAP filters
                    'priority_signal': True,  # High priority signal
                }
            )
            
            # Update tracking
            self.daily_signals_count += 1
            self.last_explosion_time[symbol] = bar.timestamp
            self.explosion_tracking[symbol] = {
                'explosion_type': explosion_type,
                'volume_spike': volume_spike,
                'momentum': momentum,
                'timestamp': bar.timestamp,
                'price': bar.close
            }
            
            self.logger.warning(f"💥 EXPLOSIVE SIGNAL GENERATED: {symbol} {explosion_type} - {volume_spike:.1f}x volume, {momentum:.1f}% momentum ({momentum_direction}), confidence {confidence:.1f}")
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Error generating explosive signal for {symbol}: {e}")
            return None
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get explosive volume strategy statistics"""
        return {
            'strategy_name': 'explosive_volume',
            'daily_signals': self.daily_signals_count,
            'active_explosions': len(self.explosion_tracking),
            'explosion_symbols': list(self.explosion_tracking.keys()),
            'parameters': {
                'explosive_threshold': self._parameters.get('explosive_volume_min', 15.0),
                'high_threshold': self._parameters.get('high_volume_min', 10.0),
                'moderate_threshold': self._parameters.get('moderate_volume_min', 5.0),
                'max_daily_signals': self._parameters.get('max_daily_signals', 3),
                'cooldown_minutes': self._parameters.get('cooldown_minutes', 30)
            }
        }
    
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For explosive volume strategy, we don't need special logic on position updates
        return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited with FOMO detection priority"""
        try:
            # PRIORITY 1: Check FOMO exit first (overrides traditional exits)
            fomo_analysis = self.check_fomo_exit(position.symbol, position, current_bar)
            if fomo_analysis and fomo_analysis.get('should_exit', False):
                fomo_signal = fomo_analysis.get('fomo_signal')
                
                return Signal(
                    signal_id=f"fomo_exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                    symbol=position.symbol,
                    signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                    strength=fomo_signal.confidence,
                    price=current_bar.close,
                    timestamp=current_bar.timestamp,
                    strategy_name="ExplosiveVolume",
                    metadata={
                        'reason': 'fomo_top_detection',
                        'fomo_score': fomo_signal.fomo_score,
                        'urgency': fomo_signal.exit_urgency,
                        'fomo_reasons': fomo_signal.fomo_reasons,
                        'entry_price': position.avg_price,
                        'exit_type': 'FOMO_EXIT'
                    }
                )
            
            # PRIORITY 2: Traditional stop loss (if no FOMO exit)
            if position.quantity > 0:  # Long position
                stop_loss_pct = 0.05  # 5% stop loss
                stop_price = position.avg_price * (1 - stop_loss_pct)
                
                if current_bar.close <= stop_price:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="ExplosiveVolume",
                        metadata={
                            'reason': 'stop_loss',
                            'entry_price': position.avg_price,
                            'stop_price': stop_price
                        }
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in should_exit for {position.symbol}: {e}")
            return None