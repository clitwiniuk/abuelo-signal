# strategies/pmh_breakout_strategy.py
"""
Premarket High Breakout Strategy: Detecta breakouts del máximo del premarket 
con condiciones favorables para short squeeze en small caps.

La estrategia busca:
1. Spike premarket seguido de pullback/consolidación
2. Breakout del PMH con volumen explosivo
3. Condiciones que sugieren presión short (overhead, patrones bajistas previos)
4. Entrada en breakout + re-entradas en pullbacks durante squeeze
"""

from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config


class PremarketHighBreakoutStrategy(BaseStrategy):
    """
    Premarket High Breakout Strategy implementation.
    
    Condiciones de Setup:
    1. Premarket spike + pullback (indica interés pero también overhead)
    2. Patrón previo que sugiere sesgo bajista (multiple resistance tests, etc.)
    3. Volumen premarket significativo pero no extremo
    4. Breakout del PMH con volumen explosivo
    5. Pausa por volatilidad o pattern similar que confirme trampa short
    
    Condiciones de Entrada:
    1. INICIAL: Breakout del PMH con volumen > 3x average
    2. RE-ENTRADA: Pullbacks durante squeeze (dips comprados agresivamente)
    3. Confirmación de short squeeze: volumen sostenido + price action alcista
    
    Condiciones de Salida:
    1. Volumen se agota (squeeze termina)
    2. Multiple rejections en resistance
    3. Patrón de distribución (large caps selling)
    4. Trailing stop después de move significativo
    5. End of day exit
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # FALLBACK DEFAULTS - Usado solo si config.ini no existe o está incompleto
        fallback_defaults = {
            # Premarket análisis
            'premarket_start_hour': 4.0,      # 4:00 AM
            'premarket_end_hour': 9.5,        # 9:30 AM
            'min_premarket_volume': 50000,     # Mínimo volumen premarket
            'premarket_spike_min': 0.15,      # 15% mínimo spike premarket
            'premarket_pullback_min': 0.05,   # 5% mínimo pullback desde spike
            
            # Detección de overhead/resistance
            'lookback_days': 10,               # Días para buscar overhead
            'resistance_tolerance': 0.02,      # 2% tolerancia para niveles resistance
            'min_resistance_tests': 2,         # Mínimo # veces que tocó resistance
            
            # Breakout del PMH
            'pmh_breakout_buffer': 0.005,     # 0.5% buffer para confirmar breakout
            'breakout_volume_multiplier': 3.0, # Volumen debe ser 3x promedio
            'max_time_to_breakout': 60,       # Máximo 60 min después apertura
            
            # Confirmación de squeeze
            'squeeze_volume_sustain': 2.0,     # Volumen sostenido 2x average
            'squeeze_price_momentum': 0.02,    # 2% momentum mínimo post-breakout
            'volatility_pause_detection': True, # Detectar pausas por volatilidad
            
            # Filtros de calidad
            'min_price': 2.0,                 # Precio mínimo
            'max_price': 25.0,                # Precio máximo (small caps)
            'min_daily_volume': 500000,       # Volumen diario mínimo
            'max_market_cap': 2000000000,     # Max $2B market cap (small cap)
            
            # Re-entradas en pullbacks
            'allow_reentries': True,          # Permitir múltiples entradas
            'pullback_min': 0.03,             # 3% mínimo pullback para re-entrada
            'pullback_max': 0.08,             # 8% máximo pullback (más = exit)
            'max_reentries': 2,               # Máximo 2 re-entradas
            
            # Risk Management
            'initial_stop_loss': 0.08,        # 8% stop inicial
            'trailing_stop_activation': 0.15, # Activar trailing a 15% profit
            'trailing_stop_distance': 0.06,   # 6% trailing distance
            'profit_target_1': 0.25,          # 25% primer target
            'profit_target_2': 0.50,          # 50% segundo target
            
            # Position Sizing
            'max_position_value': 500.0,      # Valor máximo posición
            'min_position_value': 100.0,      # Valor mínimo posición
            'min_quantity': 10,               # Cantidad mínima
            'max_risk_per_trade': 0.015,     # 1.5% risk per trade
            'commission_per_share': 0.01,     # Comisión por acción
            'min_commission': 1.0,            # Comisión mínima
            
            # Timing
            'market_open_hour': 9.5,          # 9:30 AM
            'no_entry_after_hour': 14.0,     # No entradas después 2:00 PM
            'exit_before_close_hour': 15.5,  # Exit antes 3:30 PM
            
            # Data requirements
            'min_history_days': 15,
            'max_history_bars': 500
        }
        
        # Initialize with fallback defaults first to get logger
        super().__init__("PMH_Breakout", fallback_defaults)
        
        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()
        
        # Enable FOMO detection for PMH Breakout (bullish breakout momentum strategy)
        fomo_config = {
            'fomo_threshold': 0.75,  # Standard threshold for breakout plays
            'critical_threshold': 0.90,
            'volume_explosion_multiplier': 7.0,  # 7x for PMH breakouts
            'consecutive_green_bars': 4,
            'rsi_overbought_level': 80
        }
        
        if self.enable_fomo_exit(fomo_config):
            self.logger.info("🎪 FOMO Detection enabled for PMH Breakout Strategy")
        else:
            self.logger.warning("⚠️ FOMO Detection could not be enabled")
        
        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('PMH_BREAKOUT_STRATEGY', fallback_defaults)
            
            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for PMH_Breakout strategy: {e}")
            # Keep fallback defaults
        
        # Strategy state
        self.premarket_data = {}         # Datos premarket por símbolo
        self.pmh_levels = {}            # Niveles PMH por símbolo
        self.active_setups = {}         # Setups activos
        self.resistance_levels = {}     # Niveles de resistencia históricos
        self.entry_signals = {}         # Señales de entrada activas
        self.reentry_count = {}         # Contador de re-entradas
        
        # Signal timing control
        self.last_signal_times = {}
        self.signal_cooldown_minutes = 2
    
    async def _initialize_strategy(self) -> None:
        """Initialize PMH Breakout strategy"""
        self.logger.info("Initializing Premarket High Breakout strategy")
        self.logger.info(f"Parameters: {self.parameters}")
    
    def _ensure_strategy_dicts_initialized(self) -> None:
        """Ensure all strategy state dictionaries are properly initialized"""
        dict_attrs = [
            'premarket_data', 'pmh_levels', 'active_setups', 
            'resistance_levels', 'entry_signals', 'reentry_count', 'last_signal_times'
        ]
        
        for attr in dict_attrs:
            if not hasattr(self, attr) or not isinstance(getattr(self, attr), dict):
                self.logger.warning(f"FIXING {attr}: resetting to dict")
                setattr(self, attr, {})
    
    def _ensure_bars_history_is_list(self, symbol: str) -> None:
        """Ensure bars_history[symbol] is properly initialized as a list"""
        if symbol not in self.bars_history:
            self.bars_history[symbol] = []
        elif not isinstance(self.bars_history[symbol], list):
            self.logger.warning(f"FIXING bars_history for {symbol}: converting to list")
            try:
                if hasattr(self.bars_history[symbol], '__iter__') and not isinstance(self.bars_history[symbol], (str, bytes)):
                    self.bars_history[symbol] = list(self.bars_history[symbol])
                else:
                    self.bars_history[symbol] = []
            except:
                self.bars_history[symbol] = []
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar for PMH breakout signals"""
        symbol = bar.symbol
        
        try:
            self._ensure_bars_history_is_list(symbol)
            self._ensure_strategy_dicts_initialized()
            
            # DEBUG: STOP LOSS DESACTIVADO - Comentado para debugging
            # exit_signal = self._check_exit_conditions(symbol, bar)
            # if exit_signal:
            #     self._record_signal_time(symbol, bar.timestamp)
            #     return exit_signal
            
            # Prevent duplicate signals
            if self._is_signal_too_recent(symbol, bar.timestamp):
                return None
            
            # Need sufficient history
            if len(self.bars_history[symbol]) < self._parameters['min_history_days']:
                return None
            
            current_time = self._get_time_from_timestamp(bar.timestamp)
            
            # Skip if outside trading hours
            if not self._is_trading_hours(current_time):
                return None
            
            # 1. Analyze premarket data (once per day)
            if not self._has_premarket_data_today(symbol, bar.timestamp):
                self._analyze_premarket_setup(symbol, bar)
            
            # 2. Detect resistance levels (once per day)
            if symbol not in self.resistance_levels or not self._is_same_day(
                self.resistance_levels[symbol].get('date', datetime.min), bar.timestamp):
                self._detect_resistance_levels(symbol, bar)
            
            # 3. Check for PMH breakout setup
            if symbol not in self.active_setups:
                setup_quality = self._evaluate_pmh_setup_quality(symbol, bar)
                if setup_quality > 0.6:  # High quality setup required
                    self.active_setups[symbol] = {
                        'setup_time': bar.timestamp,
                        'quality_score': setup_quality,
                        'pmh_level': self.pmh_levels.get(symbol, {}).get('high', 0),
                        'triggered': False
                    }
                    self.logger.info(f"PMH setup detected for {symbol} (quality: {setup_quality:.2f})")
            
            # 4. Check for entry signals
            if symbol in self.active_setups and not self.active_setups[symbol]['triggered']:
                # Initial breakout entry
                entry_signal = self._check_pmh_breakout_entry(symbol, bar)
                if entry_signal:
                    self.active_setups[symbol]['triggered'] = True
                    self._record_signal_time(symbol, bar.timestamp)
                    return entry_signal
            
            # 5. Check for re-entry opportunities during squeeze
            if (self._parameters['allow_reentries'] and 
                symbol in self.entry_signals and 
                self.reentry_count.get(symbol, 0) < self._parameters['max_reentries']):
                
                reentry_signal = self._check_squeeze_reentry(symbol, bar)
                if reentry_signal:
                    self.reentry_count[symbol] = self.reentry_count.get(symbol, 0) + 1
                    self._record_signal_time(symbol, bar.timestamp)
                    return reentry_signal
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error analyzing bar for {symbol}: {e}")
            import traceback
            self.logger.error(f"Full stack trace: {traceback.format_exc()}")
            return None
    
    def _analyze_premarket_setup(self, symbol: str, bar: MarketData) -> None:
        """Analyze premarket price action to identify setup conditions"""
        try:
            # Get premarket bars (simulated from historical data)
            premarket_bars = self._get_premarket_bars(symbol, bar.timestamp)
            
            if not premarket_bars or len(premarket_bars) < 3:
                return
            
            # Find premarket high and analyze pattern
            pm_highs = [b.high for b in premarket_bars]
            pm_lows = [b.low for b in premarket_bars]
            pm_volumes = [b.volume for b in premarket_bars]
            
            pm_high = max(pm_highs)
            pm_low = min(pm_lows)
            pm_open = premarket_bars[0].open
            pm_close = premarket_bars[-1].close
            pm_volume = sum(pm_volumes)
            
            # Calculate premarket spike
            pm_spike = (pm_high - pm_open) / pm_open if pm_open > 0 else 0
            
            # Calculate pullback from high
            pm_pullback = (pm_high - pm_close) / pm_high if pm_high > 0 else 0
            
            # Store premarket analysis
            self.premarket_data[symbol] = {
                'date': bar.timestamp.date(),
                'pm_high': pm_high,
                'pm_low': pm_low,
                'pm_open': pm_open,
                'pm_close': pm_close,
                'pm_volume': pm_volume,
                'spike_percent': pm_spike * 100,
                'pullback_percent': pm_pullback * 100,
                'bars_count': len(premarket_bars),
                'quality_score': self._calculate_premarket_quality(pm_spike, pm_pullback, pm_volume)
            }
            
            # Store PMH level for breakout detection
            self.pmh_levels[symbol] = {
                'high': pm_high,
                'date': bar.timestamp.date(),
                'volume_at_high': max(pm_volumes) if pm_volumes else 0
            }
            
            self.logger.debug(f"Premarket analysis for {symbol}: "
                            f"High: {pm_high:.2f}, Spike: {pm_spike*100:.1f}%, "
                            f"Pullback: {pm_pullback*100:.1f}%, Volume: {pm_volume:,}")
                            
        except Exception as e:
            self.logger.error(f"Error analyzing premarket for {symbol}: {e}")
    
    def _get_premarket_bars(self, symbol: str, current_timestamp) -> List[MarketData]:
        """Get premarket bars (simulated from recent history)"""
        try:
            # For simulation, use early morning bars from historical data
            # In real implementation, this would fetch actual premarket data
            
            bars = self.bars_history[symbol]
            if not bars:
                return []
            
            # Take last few bars as "premarket" simulation
            # In reality, you'd filter by timestamp between 4:00-9:30 AM
            recent_bars = bars[-10:] if len(bars) >= 10 else bars
            
            # Filter to simulate premarket activity (early low-volume bars)
            premarket_simulation = []
            for bar in recent_bars:
                # Simulate premarket characteristics
                if bar.volume < self._get_average_volume(symbol) * 0.3:  # Lower volume
                    premarket_simulation.append(bar)
                    if len(premarket_simulation) >= 5:  # Enough premarket bars
                        break
            
            return premarket_simulation if len(premarket_simulation) >= 3 else []
            
        except Exception as e:
            self.logger.error(f"Error getting premarket bars for {symbol}: {e}")
            return []
    
    def _calculate_premarket_quality(self, spike: float, pullback: float, volume: int) -> float:
        """Calculate quality score for premarket setup"""
        score = 0.0
        
        # Spike quality (15-40% ideal)
        if 0.15 <= spike <= 0.40:
            score += 0.3
        elif 0.10 <= spike < 0.15 or 0.40 < spike <= 0.60:
            score += 0.15
        
        # Pullback quality (5-20% ideal)
        if 0.05 <= pullback <= 0.20:
            score += 0.25
        elif 0.02 <= pullback < 0.05 or 0.20 < pullback <= 0.35:
            score += 0.1
        
        # Volume quality
        if volume >= self._parameters['min_premarket_volume']:
            score += 0.2
            if volume >= self._parameters['min_premarket_volume'] * 2:
                score += 0.1
        
        # Pattern quality bonus
        if spike > 0.20 and pullback > 0.08:  # Strong spike with meaningful pullback
            score += 0.15
        
        return min(score, 1.0)
    
    def _detect_resistance_levels(self, symbol: str, bar: MarketData) -> None:
        """Detect overhead resistance levels from recent price history"""
        try:
            bars = self.bars_history[symbol]
            if len(bars) < self._parameters['lookback_days']:
                return
            
            # Get recent high points
            recent_bars = bars[-self._parameters['lookback_days']:]
            highs = [b.high for b in recent_bars]
            
            # Find significant resistance levels
            resistance_levels = []
            tolerance = self._parameters['resistance_tolerance']
            
            for i, high in enumerate(highs):
                # Count how many times price approached this level
                touches = 0
                for other_high in highs:
                    if abs(other_high - high) / high <= tolerance:
                        touches += 1
                
                if touches >= self._parameters['min_resistance_tests']:
                    resistance_levels.append({
                        'level': high,
                        'touches': touches,
                        'strength': touches / len(highs)
                    })
            
            # Remove duplicates and sort by strength
            unique_levels = []
            for level in resistance_levels:
                is_duplicate = False
                for existing in unique_levels:
                    if abs(existing['level'] - level['level']) / level['level'] <= tolerance:
                        if level['strength'] > existing['strength']:
                            unique_levels.remove(existing)
                            unique_levels.append(level)
                        is_duplicate = True
                        break
                if not is_duplicate:
                    unique_levels.append(level)
            
            self.resistance_levels[symbol] = {
                'levels': sorted(unique_levels, key=lambda x: x['strength'], reverse=True),
                'date': bar.timestamp,
                'current_price': bar.close
            }
            
            if unique_levels:
                level_strs = [f"{r['level']:.2f}({r['touches']})" for r in unique_levels[:3]]
                self.logger.debug(f"Resistance levels for {symbol}: {level_strs}")
                                
        except Exception as e:
            self.logger.error(f"Error detecting resistance levels for {symbol}: {e}")
    
    def _evaluate_pmh_setup_quality(self, symbol: str, bar: MarketData) -> float:
        """Evaluate overall setup quality for PMH breakout"""
        try:
            quality_score = 0.0
            
            # 1. Premarket setup quality (30%)
            pm_data = self.premarket_data.get(symbol, {})
            if pm_data:
                quality_score += pm_data.get('quality_score', 0) * 0.3
            
            # 2. Resistance overhead (25%)
            resistance_data = self.resistance_levels.get(symbol, {})
            if resistance_data and resistance_data['levels']:
                # Check if current price is near resistance
                current_price = bar.close
                resistance_nearby = False
                for level in resistance_data['levels'][:2]:  # Top 2 resistance levels
                    if level['level'] > current_price * 1.02:  # Above current price
                        resistance_nearby = True
                        quality_score += 0.15 * level['strength']
                        break
                
                if resistance_nearby:
                    quality_score += 0.1  # Bonus for overhead resistance
            
            # 3. Price and volume characteristics (25%)
            # Check if price is in acceptable range
            if (self._parameters['min_price'] <= bar.close <= self._parameters['max_price']):
                quality_score += 0.1
            
            # Check volume activity
            avg_volume = self._get_average_volume(symbol)
            if bar.volume >= avg_volume * 1.5:
                quality_score += 0.15
            
            # 4. Technical setup (20%)
            # Check if PMH level exists and is reasonable
            pmh_data = self.pmh_levels.get(symbol, {})
            if pmh_data and pmh_data['high'] > bar.close * 1.01:  # PMH above current price
                quality_score += 0.15
                
                # Bonus if price is consolidating near PMH
                distance_to_pmh = abs(bar.close - pmh_data['high']) / pmh_data['high']
                if distance_to_pmh < 0.05:  # Within 5% of PMH
                    quality_score += 0.05
            
            return min(quality_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error evaluating setup quality for {symbol}: {e}")
            return 0.0
    
    def _check_pmh_breakout_entry(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """Check for initial PMH breakout entry"""
        try:
            pmh_data = self.pmh_levels.get(symbol, {})
            if not pmh_data:
                return None
            
            pmh_level = pmh_data['high']
            breakout_level = pmh_level * (1 + self._parameters['pmh_breakout_buffer'])
            
            # Check if price broke above PMH
            if bar.close <= breakout_level:
                return None
            
            # Check volume confirmation
            avg_volume = self._get_average_volume(symbol)
            volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 0
            
            if volume_ratio < self._parameters['breakout_volume_multiplier']:
                return None
            
            # Check timing (not too late in day)
            current_time = self._get_time_from_timestamp(bar.timestamp)
            if current_time > self._parameters['no_entry_after_hour']:
                return None
            
            # All conditions met - create entry signal
            setup_data = self.active_setups[symbol]
            
            # Store entry info
            self.entry_signals[symbol] = {
                'entry_price': bar.close,
                'entry_time': bar.timestamp,
                'pmh_level': pmh_level,
                'setup_quality': setup_data['quality_score'],
                'entry_type': 'initial_breakout',
                'highest_price': bar.close,
                'volume_at_entry': bar.volume
            }
            
            # Initialize reentry counter
            self.reentry_count[symbol] = 0
            
            strength = min(setup_data['quality_score'] * volume_ratio / 3.0, 1.0)
            
            self.logger.info(f"PMH breakout entry for {symbol} at {bar.close:.2f} "
                           f"(PMH: {pmh_level:.2f}, Volume: {volume_ratio:.1f}x)")
            
            return Signal(
                signal_id=f"PMH-ENTRY-{symbol}-{bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=strength,
                price=bar.close,
                timestamp=bar.timestamp,
                strategy_name="PMH_Breakout",
                metadata={
                    'strategy': 'PMH_Breakout',
                    'pmh_level': pmh_level,
                    'volume_ratio': volume_ratio,
                    'setup_quality': setup_data['quality_score'],
                    'entry_type': 'initial_breakout',
                    'is_entry': True,
                    'stop_loss': bar.close * (1 - self._parameters['initial_stop_loss']),
                    'take_profit_1': bar.close * (1 + self._parameters['profit_target_1']),
                    'take_profit_2': bar.close * (1 + self._parameters['profit_target_2'])
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error checking PMH breakout for {symbol}: {e}")
            return None
    
    def _check_squeeze_reentry(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """Check for re-entry opportunities during short squeeze"""
        try:
            entry_info = self.entry_signals.get(symbol, {})
            if not entry_info:
                return None
            
            entry_price = entry_info['entry_price']
            current_price = bar.close
            
            # Update highest price seen
            entry_info['highest_price'] = max(entry_info.get('highest_price', entry_price), current_price)
            
            # Calculate pullback from recent high
            highest_price = entry_info['highest_price']
            pullback_pct = (highest_price - current_price) / highest_price
            
            # Check if we have a meaningful pullback
            if pullback_pct < self._parameters['pullback_min']:
                return None
            
            # Check if pullback is not too deep (suggests breakdown)
            if pullback_pct > self._parameters['pullback_max']:
                return None
            
            # Check if we're still above entry price (squeeze continues)
            if current_price < entry_price * 0.98:  # Allow 2% below entry
                return None
            
            # Check volume is still strong (squeeze continuation)
            avg_volume = self._get_average_volume(symbol)
            volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 0
            
            if volume_ratio < self._parameters['squeeze_volume_sustain']:
                return None
            
            # Check for buying pressure (price recovering from pullback)
            recent_bars = self.bars_history[symbol][-3:] if len(self.bars_history[symbol]) >= 3 else []
            if recent_bars:
                price_momentum = (current_price - recent_bars[0].close) / recent_bars[0].close
                if price_momentum < 0:  # Price still declining
                    return None
            
            # All conditions met for re-entry
            strength = min(volume_ratio / 2.0 * (1 - pullback_pct), 1.0)
            
            self.logger.info(f"PMH squeeze re-entry for {symbol} at {current_price:.2f} "
                           f"(Pullback: {pullback_pct*100:.1f}%, Count: {self.reentry_count.get(symbol, 0)+1})")
            
            return Signal(
                signal_id=f"PMH-REENTRY-{symbol}-{bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=strength,
                price=current_price,
                timestamp=bar.timestamp,
                metadata={
                    'strategy': 'PMH_Breakout',
                    'entry_type': 'squeeze_reentry',
                    'pullback_pct': pullback_pct * 100,
                    'reentry_number': self.reentry_count.get(symbol, 0) + 1,
                    'volume_ratio': volume_ratio,
                    'is_entry': True,
                    'original_entry': entry_price,
                    'stop_loss': current_price * (1 - self._parameters['initial_stop_loss']),
                    'take_profit_1': current_price * (1 + self._parameters['profit_target_1'])
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error checking squeeze re-entry for {symbol}: {e}")
            return None
    
    def _check_exit_conditions(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """Check exit conditions for active positions"""
        if symbol not in self.entry_signals:
            return None
        
        try:
            entry_info = self.entry_signals[symbol]
            entry_price = entry_info['entry_price']
            current_price = bar.close
            
            # Update highest price seen
            entry_info['highest_price'] = max(entry_info.get('highest_price', entry_price), current_price)
            highest_price = entry_info['highest_price']
            
            # Calculate current P&L
            current_pnl = (current_price - entry_price) / entry_price
            
            exit_reason = None
            
            # 1. Initial stop loss
            stop_price = entry_price * (1 - self._parameters['initial_stop_loss'])
            if current_price <= stop_price:
                exit_reason = 'initial_stop_loss'
            
            # 2. Trailing stop (if activated)
            elif current_pnl >= self._parameters['trailing_stop_activation']:
                trailing_stop = highest_price * (1 - self._parameters['trailing_stop_distance'])
                if current_price <= trailing_stop:
                    exit_reason = 'trailing_stop'
            
            # 3. Profit targets
            elif current_price >= entry_price * (1 + self._parameters['profit_target_2']):
                exit_reason = 'profit_target_2'
            elif current_price >= entry_price * (1 + self._parameters['profit_target_1']):
                # Partial exit at target 1, could continue for target 2
                exit_reason = 'profit_target_1'
            
            # 4. Volume exhaustion (squeeze ending)
            elif self._is_volume_exhausted(symbol, bar):
                exit_reason = 'volume_exhaustion'
            
            # 5. End of day exit
            elif self._is_near_close(bar.timestamp):
                exit_reason = 'end_of_day'
            
            # 6. Distribution pattern (large selling pressure)
            elif self._detect_distribution_pattern(symbol, bar):
                exit_reason = 'distribution_detected'
            
            if exit_reason:
                # Calculate time held
                time_held_minutes = 0
                if 'entry_time' in entry_info:
                    try:
                        time_diff = (bar.timestamp - entry_info['entry_time']).total_seconds() / 60
                        time_held_minutes = max(0, time_diff)
                    except:
                        time_held_minutes = 0
                
                # Calculate P&L
                pnl_dollars = (current_price - entry_price) * 100  # Assuming 100 shares
                
                self.logger.info(f"[PMH EXIT] {symbol}: {exit_reason} at {current_price:.2f} "
                               f"(Entry: {entry_price:.2f}, PnL: {current_pnl*100:.1f}%)")
                
                # Clean up all tracking data for this symbol
                self.entry_signals.pop(symbol, None)
                self.reentry_count.pop(symbol, None)
                if symbol in self.active_setups:
                    self.active_setups.pop(symbol, None)
                
                return Signal(
                    signal_id=f"PMH-EXIT-{symbol}-{bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                    symbol=symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=1.0,
                    price=current_price,
                    timestamp=bar.timestamp,
                    metadata={
                        'reason': exit_reason,
                        'strategy': 'PMH_Breakout',
                        'entry_price': entry_price,
                        'pnl': current_pnl,
                        'pnl_pct': current_pnl * 100,
                        'pnl_dollars': pnl_dollars,
                        'is_exit': True,
                        'time_held_minutes': time_held_minutes,
                        'highest_price': highest_price,
                        'reentries_used': self.reentry_count.get(symbol, 0)
                    }
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions for {symbol}: {e}")
            return None
    
    def _is_volume_exhausted(self, symbol: str, bar: MarketData) -> bool:
        """Detect if volume is exhausting (squeeze ending)"""
        try:
            avg_volume = self._get_average_volume(symbol)
            current_ratio = bar.volume / avg_volume if avg_volume > 0 else 0
            
            # Check recent volume trend
            recent_bars = self.bars_history[symbol][-5:] if len(self.bars_history[symbol]) >= 5 else []
            if len(recent_bars) < 3:
                return False
            
            recent_volumes = [b.volume for b in recent_bars]
            volume_trend = np.polyfit(range(len(recent_volumes)), recent_volumes, 1)[0]
            
            # Volume exhausted if:
            # 1. Current volume below sustain threshold
            # 2. Declining volume trend
            return (current_ratio < self._parameters['squeeze_volume_sustain'] and 
                    volume_trend < 0)
                    
        except Exception as e:
            self.logger.error(f"Error checking volume exhaustion for {symbol}: {e}")
            return False
    
    def _detect_distribution_pattern(self, symbol: str, bar: MarketData) -> bool:
        """Detect distribution pattern (large sellers entering)"""
        try:
            # Look for large volume with price stalling/declining
            recent_bars = self.bars_history[symbol][-3:] if len(self.bars_history[symbol]) >= 3 else []
            if len(recent_bars) < 3:
                return False
            
            # Check for high volume with poor price performance
            avg_volume = self._get_average_volume(symbol)
            high_volume_bars = [b for b in recent_bars if b.volume > avg_volume * 2]
            
            if len(high_volume_bars) >= 2:
                # Check price action during high volume
                price_change = (bar.close - recent_bars[0].close) / recent_bars[0].close
                if price_change < 0.01:  # Less than 1% gain despite high volume
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error detecting distribution for {symbol}: {e}")
            return False
    
    def _is_near_close(self, timestamp) -> bool:
        """Check if it's near market close"""
        current_time = self._get_time_from_timestamp(timestamp)
        return current_time >= self._parameters['exit_before_close_hour']
    
    def _get_average_volume(self, symbol: str) -> float:
        """Get average volume for symbol"""
        try:
            bars = self.bars_history[symbol]
            if len(bars) < 10:
                return 0
            
            volumes = [bar.volume for bar in bars[-20:]]  # Last 20 bars
            return sum(volumes) / len(volumes) if volumes else 0
            
        except Exception as e:
            self.logger.error(f"Error calculating average volume for {symbol}: {e}")
            return 0
    
    def _has_premarket_data_today(self, symbol: str, timestamp) -> bool:
        """Check if we already have premarket data for today"""
        pm_data = self.premarket_data.get(symbol, {})
        if not pm_data:
            return False
        
        return self._is_same_day(pm_data.get('date', datetime.min.date()), timestamp)
    
    def _is_signal_too_recent(self, symbol: str, timestamp) -> bool:
        """Check if signal is too recent"""
        if symbol not in self.last_signal_times:
            return False
        
        try:
            last_time = self.last_signal_times[symbol]
            current_time = timestamp
            
            if isinstance(last_time, (int, float)):
                last_time = datetime.fromtimestamp(last_time)
            if isinstance(current_time, (int, float)):
                current_time = datetime.fromtimestamp(current_time)
            
            time_diff = (current_time - last_time).total_seconds() / 60
            return time_diff < self.signal_cooldown_minutes
            
        except Exception as e:
            self.logger.error(f"Error checking signal timing for {symbol}: {e}")
            return False
    
    def _record_signal_time(self, symbol: str, timestamp) -> None:
        """Record signal time"""
        self.last_signal_times[symbol] = timestamp
    
    def _get_time_from_timestamp(self, timestamp) -> float:
        """Convert timestamp to decimal hour"""
        try:
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            else:
                dt = timestamp
            
            return dt.hour + dt.minute / 60.0
            
        except Exception as e:
            self.logger.error(f"Error converting timestamp: {e}")
            return 0.0
    
    def _is_trading_hours(self, time_decimal: float) -> bool:
        """Check if within trading hours"""
        return self._parameters['market_open_hour'] <= time_decimal <= 16.0
    
    def _is_same_day(self, date1, date2) -> bool:
        """Check if two dates are the same day"""
        try:
            if isinstance(date1, datetime):
                date1 = date1.date()
            if isinstance(date2, datetime):
                date2 = date2.date()
            elif isinstance(date2, (int, float)):
                date2 = datetime.fromtimestamp(date2).date()
                
            return date1 == date2
            
        except Exception as e:
            self.logger.error(f"Error comparing dates: {e}")
            return False
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Calculate position size for PMH Breakout strategy"""
        try:
            symbol = signal.symbol
            price = signal.price
            
            # Calculate risk amount
            risk_amount = capital * min(risk_per_trade, self._parameters['max_risk_per_trade'])
            stop_distance = price * self._parameters['initial_stop_loss']
            
            # Base calculation
            if stop_distance > 0:
                base_quantity = int(risk_amount / stop_distance)
            else:
                base_quantity = int(self._parameters['min_position_value'] / price)
            
            # Apply position limits
            max_shares_value = int(self._parameters['max_position_value'] / price)
            max_shares_risk = int((capital * 0.05) / price)  # Max 5% of capital
            
            max_shares = min(max_shares_value, max_shares_risk)
            quantity = min(base_quantity, max_shares)
            quantity = max(quantity, self._parameters['min_quantity'])
            
            # Calculate commission impact
            commission_per_share = self._parameters['commission_per_share']
            min_commission = self._parameters['min_commission']
            total_commission = (quantity * commission_per_share * 2) + (min_commission * 2)
            position_value = quantity * price
            commission_pct = (total_commission / position_value) * 100
            
            # Adjust for high-volume/high-volatility strategies
            if signal.metadata.get('volume_ratio', 1) > 5:  # Very high volume
                quantity = int(quantity * 1.2)  # Increase size for high-conviction setups
                quantity = min(quantity, max_shares)
            
            self.logger.info(
                f"PMH position size for {symbol}: {quantity} shares @ {price:.2f} "
                f"(Value: ${position_value:,.2f}, Comm: ${total_commission:.2f} = {commission_pct:.2f}%)"
            )
            
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size for {symbol}: {e}")
            return self._parameters['min_quantity']
    
    def get_strategy_info(self) -> dict:
        """Get strategy information"""
        return {
            "name": self.name,
            "type": "Premarket High Breakout",
            "timeframe": "Intraday (Small Caps)",
            "parameters": self.parameters,
            "active_setups": len(self.active_setups),
            "active_signals": len(self.entry_signals),
            "tracked_symbols": {
                "premarket_data": len(self.premarket_data),
                "pmh_levels": len(self.pmh_levels),
                "resistance_levels": len(self.resistance_levels)
            },
            "performance": self.get_performance_stats()
        }
    
    def get_current_setups(self) -> Dict[str, Any]:
        """Get current active setups for monitoring"""
        setups_info = {}
        
        for symbol in self.active_setups:
            setup = self.active_setups[symbol]
            pmh_data = self.pmh_levels.get(symbol, {})
            
            setups_info[symbol] = {
                'pmh_level': pmh_data.get('high', 0),
                'quality_score': setup.get('quality_score', 0),
                'triggered': setup.get('triggered', False),
                'setup_time': setup.get('setup_time'),
                'has_position': symbol in self.entry_signals,
                'reentries_used': self.reentry_count.get(symbol, 0)
            }
        
        return setups_info
    
    def cleanup_old_data(self, current_date) -> None:
        """Clean up old data to prevent memory issues"""
        try:
            cutoff_date = current_date - timedelta(days=2)
            
            # Clean premarket data
            to_remove = []
            for symbol, data in self.premarket_data.items():
                if data.get('date', current_date) < cutoff_date:
                    to_remove.append(symbol)
            
            for symbol in to_remove:
                self.premarket_data.pop(symbol, None)
                self.pmh_levels.pop(symbol, None)
                self.resistance_levels.pop(symbol, None)
                
                # Only clean active setups if no active position
                if symbol not in self.entry_signals:
                    self.active_setups.pop(symbol, None)
                    self.reentry_count.pop(symbol, None)
            
            if to_remove:
                self.logger.debug(f"Cleaned old data for {len(to_remove)} symbols")
                
        except Exception as e:
            self.logger.error(f"Error cleaning old data: {e}")

    # Additional helper methods for debugging and monitoring
    
    def get_symbol_state(self, symbol: str) -> Dict[str, Any]:
        """Get complete state for a specific symbol (for debugging)"""
        return {
            'premarket_data': self.premarket_data.get(symbol, {}),
            'pmh_level': self.pmh_levels.get(symbol, {}),
            'resistance_levels': self.resistance_levels.get(symbol, {}),
            'active_setup': self.active_setups.get(symbol, {}),
            'entry_signal': self.entry_signals.get(symbol, {}),
            'reentry_count': self.reentry_count.get(symbol, 0),
            'last_signal_time': self.last_signal_times.get(symbol, None)
        }
    
    def reset_symbol_state(self, symbol: str) -> None:
        """Reset all state for a symbol (for debugging/recovery)"""
        self.premarket_data.pop(symbol, None)
        self.pmh_levels.pop(symbol, None)
        self.resistance_levels.pop(symbol, None)
        self.active_setups.pop(symbol, None)
        self.entry_signals.pop(symbol, None)
        self.reentry_count.pop(symbol, None)
        self.last_signal_times.pop(symbol, None)
        
        self.logger.info(f"Reset all state for {symbol}")

    def validate_strategy_state(self) -> Dict[str, Any]:
        """Validate strategy state integrity"""
        issues = []
        
        # Check if all dictionaries are actually dictionaries
        dict_attrs = [
            'premarket_data', 'pmh_levels', 'resistance_levels',
            'active_setups', 'entry_signals', 'reentry_count', 'last_signal_times'
        ]
        
        for attr in dict_attrs:
            if not isinstance(getattr(self, attr, None), dict):
                issues.append(f"{attr} is not a dictionary")
        
        # Check for orphaned data
        all_symbols = set()
        for attr in dict_attrs:
            all_symbols.update(getattr(self, attr, {}).keys())
        
        # Check consistency
        for symbol in all_symbols:
            if symbol in self.entry_signals and symbol not in self.active_setups:
                issues.append(f"{symbol} has entry signal but no active setup")
        
        return {
            'issues_found': len(issues),
            'issues': issues,
            'symbols_tracked': len(all_symbols),
            'state_sizes': {attr: len(getattr(self, attr, {})) for attr in dict_attrs}
        }
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For PMHBreakout strategy, we don't need special logic on position updates
        return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited - required by IStrategy interface"""
        try:
            # Basic stop loss for positions
            if position.quantity > 0:  # Long position
                stop_loss_pct = 0.05  # 5% default stop loss
                stop_price = position.avg_price * (1 - stop_loss_pct)
                
                if current_bar.close <= stop_price:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="PMHBreakout",
                        metadata={
                            'reason': 'basic_stop_loss',
                            'entry_price': position.avg_price,
                            'stop_price': stop_price
                        }
                    )
            elif position.quantity < 0:  # Short position  
                stop_loss_pct = 0.05  # 5% default stop loss
                stop_price = position.avg_price * (1 + stop_loss_pct)
                
                if current_bar.close >= stop_price:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_SHORT,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="PMHBreakout",
                        metadata={
                            'reason': 'basic_stop_loss',
                            'entry_price': position.avg_price,
                            'stop_price': stop_price
                        }
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in should_exit for {position.symbol}: {e}")
            return None
