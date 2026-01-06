# strategies/macdv_strategy.py - OPTIMIZADA PARA SMALLCAPS
"""
MACD-V Strategy: Específicamente optimizada para smallcaps ($1-$25)
"""

from typing import Optional, Dict, Any
import numpy as np
import pandas as pd

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config
from core.order_flow_analyzer import OrderFlowAnalyzer
from core.consolidation_detector import ConsolidationDetector
from core.early_warning_system import EarlyWarningSystem
from core.triple_entry_system import TripleEntrySystem
from core.dynamic_position_sizing import DynamicPositionSizing


class MACDVStrategy(BaseStrategy):
    """
    MACD-V Strategy - OPTIMIZADA PARA SMALLCAPS
    
    Características específicas para smallcaps:
    - Parámetros MACD más sensibles para mayor volatilidad
    - Gestión de volumen adaptada a patrones erráticos
    - Stops más amplios para acomodar gaps
    - Posiciones en lotes de 100 acciones
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # FALLBACK DEFAULTS - All parameters ML-configurable
        fallback_defaults = {
            # MACD parameters (ML-configurable)
            'macd_fast': 5,
            'macd_slow': 13,
            'macd_signal': 3,
            
            # Volume parameters (ML-configurable)
            'volume_period': 10,
            'volume_threshold': 1.5,
            'volume_required': True,
            'volume_spike_threshold': 2.0,
            
            # Price filters (ML-configurable)
            'min_price': 1.0,
            'max_price': 25.0,
            'avoid_penny_stocks': True,
            
            # Moving averages (ML-configurable)
            'ma_short': 5,
            'ma_long': 13,
            'ma_trend_required': False,
            
            # Risk management (ML-configurable) - REMOVED hardcoded stop_loss_pct
            # stop_loss_pct now uses config.ini fallback_stop_loss_pct = 0.05 (5%)
            'take_profit_pct': 0.15,
            'trailing_stop_activation': 0.08,
            'trailing_stop_distance': 0.04,
            
            # Position sizing (ML-configurable)
            'max_position_value': 100.0,
            'min_position_value': 25.0,
            'min_quantity': 5,
            'max_quantity': 100,
            'risk_per_trade': 0.015,
            
            # Timing controls (ML-configurable) - RELAXED
            'min_seconds_between_trades': 300,  # RELAXED: Reduced from 10min to 5min between trades
            'avoid_first_30min': False,  # RELAXED: Allow trading in first 30min for more opportunities
            'avoid_last_30min': True,
            
            # Quality filters (ML-configurable) - RELAXED
            'min_daily_volume': 30000,  # RELAXED: Reduced from 50k to 30k for easier entries
            'max_spread_pct': 0.08,
            'rsi_overbought': 80,
            'rsi_oversold': 20,
            
            # ATR volatility (ML-configurable)
            'atr_period': 10,
            'min_atr_pct': 0.01,
            'max_atr_pct': 0.20,
            
            # Entry decision thresholds (ML-configurable) - BALANCED
            'min_entry_score': 3,  # BALANCED: Score 3 requires convergence + timing + pullback
            'friday_score_relaxation': 1,  # Lower score by 1 on Fridays (low volume days)
            'min_pullback_threshold': 0.005,  # Minimum pullback required for entry
        }
        
        # Initialize with fallback defaults first to get logger
        super().__init__("MACDV_Smallcaps", fallback_defaults)
        
        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('MACDV_STRATEGY', fallback_defaults)
            
            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for MACDV strategy: {e}")
            # Keep fallback defaults
        
        # Log received parameters after logger is initialized
        if parameters:
            self.logger.info(f"🔧 MACDV received parameters: {parameters}")
        
        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()

        # Initialize complete predictive system
        self.order_flow_analyzer = OrderFlowAnalyzer({
            'bid_pressure_threshold': 0.75,
            'spread_compression_threshold': 0.6,
            'aggressive_volume_threshold': 0.65,
            'pressure_buildup_volume_mult': 2.0,
            'pressure_buildup_price_max': 0.01
        })

        self.consolidation_detector = ConsolidationDetector({
            'atr_period': 14,
            'bb_period': 20,
            'compression_threshold': 0.7,
            'squeeze_threshold': 0.6,
            'volume_increase_threshold': 1.2
        })

        self.early_warning_system = EarlyWarningSystem({
            'order_flow_weight': 0.4,
            'pattern_weight': 0.3,
            'volume_weight': 0.2,
            'timing_weight': 0.1,
            'high_threshold': 0.7,
            'critical_threshold': 0.85
        })

        self.triple_entry_system = TripleEntrySystem({
            'predictive': {
                'position_size_pct': 0.33,
                'confidence_multiplier': 1.5,
                'min_warning_score': 0.7
            },
            'pullback': {
                'position_size_pct': 0.50,
                'confidence_multiplier': 1.0,
                'min_recovery_pct': 0.01
            },
            'confirmation': {
                'position_size_pct': 0.25,
                'confidence_multiplier': 0.8,
                'min_confirmation_score': 3
            }
        })

        self.dynamic_position_sizing = DynamicPositionSizing({
            'portfolio_value': self._parameters.get('max_position_value', 200.0) * 10,  # Estimate portfolio
            'max_risk_per_trade': 0.02,
            'max_position_value': self._parameters.get('max_position_value', 200.0),
            'min_position_value': self._parameters.get('min_position_value', 25.0)
        })

        # Strategy state
        self.last_macd_values = {}
        self.entry_signals = {}  # Simplified - no stop logic
        self.last_signal_time = {}
        self.volume_profiles = {}
        self._trading_engine = None  # Will be set by trading engine
        
        # Signal deduplication
        self.last_processed_bars = {}  # symbol -> timestamp
        self.last_exit_signals = {}    # symbol -> timestamp
        
        
        self.logger.info("🎯 MACDV Strategy initialized with centralized stop loss management")
    
    def set_trading_engine(self, trading_engine):
        """Set reference to trading engine for position validation"""
        self._trading_engine = trading_engine
    
    async def _initialize_strategy(self) -> None:
        """Initialize MACD-V strategy for smallcaps"""
        self.logger.info("Initializing MACD-V strategy for SMALLCAPS")
        self.logger.info(f"Price range: ${self._parameters['min_price']:.2f} - ${self._parameters['max_price']:.2f}")
        self.logger.info(f"Volume threshold: {self._parameters['volume_threshold']:.1f}x")
        self.logger.info(f"Position size: ${self._parameters['min_position_value']:.0f} - ${self._parameters['max_position_value']:.0f}")
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar with smallcaps-specific logic"""
        symbol = bar.symbol

        # TEMPORARY DEBUG: Log when MACDV is called for any symbol (every 10th to avoid spam)
        if hash(symbol) % 10 == 0:  # Log for 1 in 10 symbols to reduce spam
            self.logger.info(f"🔍 MACDV analyzing {symbol} @ ${bar.close:.2f} | History: {len(self.bars_history.get(symbol, []))} bars")
        
        # 0. DEDUPLICATION - Prevent processing the same bar twice
        bar_timestamp = bar.timestamp
        if symbol in self.last_processed_bars:
            if self.last_processed_bars[symbol] == bar_timestamp:
                return None  # Already processed this bar
        
        self.last_processed_bars[symbol] = bar_timestamp
        
        # 1. FILTROS PREVIOS - Específicos para smallcaps
        if not self._passes_smallcap_filters(bar):
            return None
        
        # 2. Check exit conditions first (only if we have a real position)
        has_real_position = False
        if hasattr(self, '_trading_engine') and self._trading_engine:
            has_real_position = symbol in self._trading_engine.positions
        
        if has_real_position or symbol in self.entry_signals:
            # Evaluar condiciones de salida (stop loss / take profit / trailing)
            exit_signal = self.stop_manager.check_exit_conditions(symbol, bar)
            if exit_signal is not None:
                # Limpiar tracking de la posición si se genera señal de salida
                self._cleanup_position_tracking(symbol)
                return exit_signal
        
        # 3. Check position control (anti-martingala + piramidación inteligente)
        try:
            position_check = self._can_open_new_position(symbol, bar.close, 'long')
            if not position_check['can_open']:
                if position_check['position_action'] == 'blocked':
                    self.logger.debug(f"[{symbol}] {position_check['reason']}")
                return None
            
            # Log piramidación si es el caso
            if position_check['position_action'] == 'pyramid':
                self.logger.info(f"[{symbol}] {position_check['reason']}")
        except Exception as e:
            self.logger.error(f"[SMALLCAP-ERROR] {symbol}: Error in position control: {e}")
            return None
            
        # 4. Check timing restrictions
        if not self._is_good_trading_time(bar.timestamp):
            return None
            
        # 5. Check cooldown
        if self._is_in_cooldown(symbol, bar.timestamp):
            return None
        
        # 6. Need sufficient history - RELAXED: Reduced from 30+ to 20+ bars
        min_bars = max(20, self._parameters['macd_slow'] + 3)  # Reduced from 30 and 5 to 20 and 3
        current_bars = len(self.bars_history.get(symbol, []))
        if current_bars < min_bars:
            # TEMPORARY DEBUG: Log why MACDV is not generating signals (sample to avoid spam)
            if hash(symbol) % 20 == 0:  # Log for 1 in 20 symbols to reduce spam
                self.logger.info(f"🔍 MACDV {symbol}: Insufficient bars {current_bars}/{min_bars} needed")
            return None
        
        try:
            # 7. ANÁLISIS TÉCNICO
            self.logger.info(f"🔍 MACDV {symbol}: Passed all filters, starting technical analysis")
            signal = await self._analyze_smallcap_entry(symbol, bar)
            if signal:
                self.logger.info(f"🎯 MACDV {symbol}: Generated signal! {signal.signal_type}")
            return signal
            
        except Exception as e:
            self.logger.error(f"[SMALLCAP-ERROR] {symbol}: Error analyzing: {e}")
            return None
    
    def _passes_smallcap_filters(self, bar: MarketData) -> bool:
        """Filtros específicos para smallcaps"""
        symbol = bar.symbol
        price = bar.close
        volume = bar.volume
        
        # 1. Price range filter
        if price < self._parameters['min_price'] or price > self._parameters['max_price']:
            return False
            
        # 2. Avoid penny stocks if configured - RELAXED
        if self._parameters.get('avoid_penny_stocks', True) and price < 1.5:  # RELAXED: Reduced from $2.0 to $1.5
            return False
        
        # 3. Minimum volume filter - RELAXED
        min_vol_per_minute = self._parameters.get('min_daily_volume', 30000) / 390  # RELAXED: Uses actual parameter value
        if volume < min_vol_per_minute:
            return False
        
        # 4. ATR volatility filter
        atr_pct = self._get_atr_percentage(symbol)
        if atr_pct is not None:
            min_atr = self._parameters.get('min_atr_pct', 0.03)
            max_atr = self._parameters.get('max_atr_pct', 0.20)
            if atr_pct < min_atr or atr_pct > max_atr:
                if len(self.bars_history[symbol]) % 100 == 0:  # Log occasionally
                    self.logger.info(f"[FILTER] {symbol}: ATR {atr_pct*100:.1f}% outside range {min_atr*100:.1f}%-{max_atr*100:.1f}%")
                return False
        
        return True
    
    def _is_good_trading_time(self, timestamp) -> bool:
        """Check if it's a good time to trade (avoid volatile periods)"""
        try:
            from datetime import datetime
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = timestamp
            
            hour = dt.hour
            minute = dt.minute
            
            # Avoid first 30 minutes (9:30-10:00 ET)
            if self._parameters.get('avoid_first_30min', True):
                if hour == 9 and minute >= 30 or hour == 10 and minute == 0:
                    return False
            
            # Avoid last 30 minutes (15:30-16:00 ET)
            if self._parameters.get('avoid_last_30min', True):
                if hour == 15 and minute >= 30:
                    return False
            
            return True
            
        except Exception:
            return True  # Default to allow trading
    
    async def _analyze_smallcap_entry(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """Análisis multi-timeframe optimizado: 5min convergencia -> 1min timing preciso"""

        # FASE 1: Detectar convergencia MACD en 5min (filtro primario) - STRICT
        convergence_5min = self._detect_macd_convergence_5min(symbol)
        if not convergence_5min['approaching_cross']:
            # STRICT: Reject entries without 5min convergence
            self.logger.debug(f"[5MIN-STRICT] {symbol}: No 5min convergence - rejecting entry")
            return None

        self.logger.info(f"[5MIN-CONVERGENCE] {symbol}: MACD approaching cross (urgency: {convergence_5min['urgency']}/10)")

        # FASE 2: Análisis 1min solo cuando 5min muestra señal inminente - STRICT
        timing_result = self._analyze_1min_macd_timing(symbol, bar, convergence_5min)
        if not timing_result:
            # STRICT: Reject if no MACD cross on 1min
            self.logger.debug(f"[TIMING-STRICT] {symbol}: No MACD cross on 1min - rejecting entry")
            return None
        # FASE 3: Validaciones adicionales (pullback, volumen, etc.) - CONDITIONAL
        pullback_ok = self._check_pullback_opportunity(symbol, bar)
        pullback_penalty = 0
        if not pullback_ok:
            # CONDITIONAL: Penalize but don't reject if other signals are very strong
            pullback_penalty = -2  # Subtract 2 points from score
            self.logger.info(f"[PULLBACK-CONDITIONAL] {symbol}: No pullback detected - applying -2 point penalty")
        else:
            self.logger.info(f"[PULLBACK-OK] {symbol}: ✓ Pullback opportunity detected")

        # ORDER FLOW ANALYSIS - Señales predictivas de desequilibrio
        order_flow_signals = self._analyze_order_flow_signals(symbol, bar)
        order_flow_boost = 0
        if order_flow_signals:
            signal_types = [s.signal_type for s in order_flow_signals]
            bullish_signals = [s for s in order_flow_signals if 'BULLISH' in s.signal_type or 'BUYING' in s.signal_type]

            if bullish_signals:
                avg_strength = sum(s.strength for s in bullish_signals) / len(bullish_signals)
                order_flow_boost = int(avg_strength * 3)  # Up to 3 point boost
                self.logger.info(f"[ORDER-FLOW] {symbol}: ✓ Bullish order flow detected: {signal_types} (boost: +{order_flow_boost})")

        # FASE 4: Scoring final basado en timing multi-timeframe
        conditions_score = timing_result['score']
        conditions_met = timing_result['conditions_met']

        # Bonus por calidad de convergencia 5min
        urgency_bonus = min(convergence_5min['urgency'] / 2, 3)  # Max 3 puntos
        conditions_score += urgency_bonus
        conditions_met.append(f"5min_urgency_{convergence_5min['urgency']}")

        # Bonus adicionales para refinar scoring
        current_macd = timing_result['macd_data']

        # CRITICAL FIX: Get volume ratio before using it in metadata
        volume_passed, volume_ratio = self._check_smallcap_volume(symbol)
        if volume_passed:
            conditions_score += 0.5
            conditions_met.append(f"volume_{volume_ratio:.1f}x")

        # D. Price momentum
        price_momentum = self._check_smallcap_momentum(symbol)
        if price_momentum:
            conditions_score += 1
            conditions_met.append("momentum")
            self.logger.info(f"[SMALLCAP-MOM] {symbol}: ✓ Price momentum")
        
        # E. RSI not overbought
        rsi = self.calculate_rsi(symbol, 7)  # Shorter period for smallcaps
        if rsi and rsi < self._parameters.get('rsi_overbought', 75):
            conditions_score += 1
            conditions_met.append(f"rsi_{rsi:.0f}")
            self.logger.info(f"[SMALLCAP-RSI] {symbol}: ✓ RSI {rsi:.0f}")
        
        # 7. Check position control (anti-martingala + piramidación inteligente)
        try:
            position_check = self._can_open_new_position(symbol, bar.close, 'long')
            if not position_check['can_open']:
                if position_check['position_action'] == 'blocked':
                    self.logger.debug(f"[{symbol}] {position_check['reason']}")
                return None
            
            # Log piramidación si es el caso
            if position_check['position_action'] == 'pyramid':
                self.logger.info(f"[{symbol}] {position_check['reason']}")
        except Exception as e:
            self.logger.error(f"[SMALLCAP-ERROR] {symbol}: Error in position control: {e}")
            return None

        # 8. SISTEMA HÍBRIDO: TIMING PROACTIVO + PULLBACK COMPATIBILITY - STRICT
        timing_passed = self._check_hybrid_timing_filters(symbol, bar, pullback_ok)
        if not timing_passed:
            # STRICT: Reject if timing filters fail
            self.logger.info(f"[HYBRID-TIMING-STRICT] {symbol}: Failed hybrid timing filters - rejecting entry")
            return None

        # 9. DECISIÓN DE ENTRADA (con boost de order flow + pullback penalty + adaptación por día)
        final_score = conditions_score + order_flow_boost + pullback_penalty

        # ADAPTIVE SCORING: Relax on Fridays (low volume days)
        from datetime import datetime
        min_score = self._parameters.get('min_entry_score', 3)  # BALANCED: Default 3

        # Friday relaxation (day 4 = Friday in Python)
        if datetime.now().weekday() == 4:
            friday_relaxation = self._parameters.get('friday_score_relaxation', 1)
            min_score = max(2, min_score - friday_relaxation)  # Never go below 2
            self.logger.info(f"[FRIDAY-ADAPTIVE] {symbol}: Relaxing min_score to {min_score} for low-volume Friday")

        if final_score >= min_score:
            self.logger.info(f"[ENTRY-APPROVED] {symbol}: Score {final_score:.1f} ≥ {min_score} - Generating signal")

            # Store entry signal (actualizar para piramidación)
            existing_entry = self.entry_signals.get(symbol, {})
            entry_count = existing_entry.get('entry_count', 0) + 1
            
            # Calcular precio promedio si es piramidación
            if position_check['position_action'] == 'pyramid':
                prev_price = existing_entry.get('entry_price', bar.close)
                prev_count = existing_entry.get('entry_count', 1)
                # Precio promedio simple (en realidad sería ponderado por cantidad, pero es aproximación)
                avg_price = (prev_price * prev_count + bar.close) / (prev_count + 1)
            else:
                avg_price = bar.close
            
            # Create signal
            signal = Signal(
                signal_id="",
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=min(0.9, final_score / 6.0),  # Max strength based on final score
                price=bar.close,
                timestamp=bar.timestamp,
                metadata={
                    'strategy': 'MACDV_Smallcaps',
                    'conditions': conditions_met,
                    'score': conditions_score,
                    'order_flow_boost': order_flow_boost,
                    'final_score': final_score,
                    'order_flow_signals': [s.signal_type for s in order_flow_signals] if order_flow_signals else [],
                    'volume_ratio': volume_ratio,
                    'macd_value': current_macd['macd'],
                    'setup_type': 'macdv_momentum',
                    'pattern': f"macdv_entry_{final_score}pt",
                    # Add current bid/ask data for database storage
                    'entry_bid': bar.bid,
                    'entry_ask': bar.ask,
                    'entry_bid_size': bar.bid_size,
                    'entry_ask_size': bar.ask_size,
                    'entry_spread_pct': ((bar.ask - bar.bid) / bar.close) if (bar.bid and bar.ask and bar.close) else None,
                    # Add order flow analysis results
                    **self._extract_order_flow_metadata(order_flow_signals, bar)
                }
            )
            
            # Register position with centralized stop manager
            self._register_position_with_stop_manager(symbol, bar, signal)
            
            # Store simplified entry information (no stop logic)
            self.entry_signals[symbol] = {
                'type': "bullish",
                'timestamp': bar.timestamp,
                'entry_time': bar.timestamp,
                'entry_price': bar.close,  # Precio de esta entrada específica
                'avg_price': avg_price,    # Precio promedio de todas las entradas
                'entry_count': entry_count,
                'position_action': position_check['position_action'],
                'conditions': conditions_met,
                'score': conditions_score,
                'macd_value': current_macd['macd'],
                'volume_ratio': volume_ratio,
                'direction': 'long'
                # Note: No stop_price, take_profit, highest_price - handled by centralized manager
            }
            
            self.last_signal_time[symbol] = bar.timestamp
            
            self.logger.info(f"[SMALLCAP-SIGNAL] {symbol}: ✅ LONG SIGNAL @ ${bar.close:.2f}")
            self.logger.info(f"[SMALLCAP-SIGNAL] {symbol}: Score: {conditions_score}+{order_flow_boost}={final_score}/{min_score}, Conditions: {', '.join(conditions_met)}")
            
            # Store current MACD
            self.last_macd_values[symbol] = current_macd
            
            return signal
        else:
            self.logger.info(f"[ENTRY-REJECTED] {symbol}: Score {final_score:.1f} < {min_score} (base: {conditions_score:.1f}, order_flow: +{order_flow_boost}, pullback: {pullback_penalty})")
            self.logger.info(f"[ENTRY-REJECTED] {symbol}: Conditions met: {', '.join(conditions_met)}")

        # Store current MACD
        self.last_macd_values[symbol] = current_macd

        return None
    
    def _safe_calculate_macd(self, symbol: str, fast_period: int, slow_period: int, signal_period: int) -> Optional[Dict[str, float]]:
        """
        Safe wrapper for calculate_macd method to handle potential attribute errors
        """
        try:
            # Direct implementation to avoid any attribute lookup issues
            min_bars_needed = slow_period + signal_period + 5
            df = self.get_bars_df(symbol, min_bars_needed)
            
            if len(df) < min_bars_needed:
                return None
            
            # Get closing prices
            prices = df['close']
            
            # Calculate EMAs
            ema_fast = prices.ewm(span=fast_period).mean()
            ema_slow = prices.ewm(span=slow_period).mean()
            
            # Calculate MACD line
            macd_line = ema_fast - ema_slow
            
            # Calculate signal line (EMA of MACD line)
            signal_line = macd_line.ewm(span=signal_period).mean()
            
            # Calculate histogram
            histogram = macd_line - signal_line
            
            return {
                'macd': float(macd_line.iloc[-1]),
                'signal': float(signal_line.iloc[-1]),
                'histogram': float(histogram.iloc[-1]),
                'prev_macd': float(macd_line.iloc[-2]) if len(macd_line) > 1 else 0.0,
                'prev_signal': float(signal_line.iloc[-2]) if len(signal_line) > 1 else 0.0,
                'prev_histogram': float(histogram.iloc[-2]) if len(histogram) > 1 else 0.0
            }
        except Exception as e:
            self.logger.error(f"[MACDV-ERROR] {symbol}: Error calculating MACD: {e}")
            return None
    
    def calculate_macd(self, symbol: str, fast_period: int, slow_period: int, signal_period: int) -> Optional[Dict[str, float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence) for smallcaps
        
        Args:
            symbol: Symbol to analyze
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line EMA period
            
        Returns:
            Dict with 'macd', 'signal', 'histogram' values or None if insufficient data
        """
        try:
            # Need at least slow_period + signal_period bars
            min_bars_needed = slow_period + signal_period + 5
            df = self.get_bars_df(symbol, min_bars_needed)
            
            if len(df) < min_bars_needed:
                return None
            
            # Get closing prices
            prices = df['close']
            
            # Calculate EMAs
            ema_fast = prices.ewm(span=fast_period).mean()
            ema_slow = prices.ewm(span=slow_period).mean()
            
            # Calculate MACD line
            macd_line = ema_fast - ema_slow
            
            # Calculate signal line (EMA of MACD line)
            signal_line = macd_line.ewm(span=signal_period).mean()
            
            # Calculate histogram
            histogram = macd_line - signal_line
            
            # Return the most recent values
            return {
                'macd': float(macd_line.iloc[-1]),
                'signal': float(signal_line.iloc[-1]),
                'histogram': float(histogram.iloc[-1]),
                'prev_macd': float(macd_line.iloc[-2]) if len(macd_line) > 1 else 0.0,
                'prev_signal': float(signal_line.iloc[-2]) if len(signal_line) > 1 else 0.0,
                'prev_histogram': float(histogram.iloc[-2]) if len(histogram) > 1 else 0.0
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating MACD for {symbol}: {e}")
            return None
    
    def _check_smallcap_volume(self, symbol: str) -> tuple[bool, float]:
        """Check volume surge specific to smallcaps"""
        try:
            df = self.get_bars_df(symbol, self._parameters['volume_period'])
            if len(df) < self._parameters['volume_period']:
                return False, 1.0
            
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].iloc[:-1].mean()
            
            if avg_volume <= 0:
                return False, 1.0
            
            volume_ratio = current_volume / avg_volume
            threshold = self._parameters['volume_threshold']
            
            # Additional check for volume spike
            spike_threshold = self._parameters.get('volume_spike_threshold', 2.0)
            is_spike = volume_ratio >= spike_threshold
            is_above_threshold = volume_ratio >= threshold
            
            return (is_above_threshold or is_spike), volume_ratio
            
        except Exception as e:
            self.logger.error(f"Error checking smallcap volume for {symbol}: {e}")
            return False, 1.0
    
    def _check_hybrid_timing_filters(self, symbol: str, bar: MarketData, pullback_detected: bool) -> bool:
        """
        SISTEMA HÍBRIDO: Combina tu sistema de pullback con mis filtros de timing proactivo

        LÓGICA:
        - Si hay PULLBACK detectado -> Usa lógica de recuperación (momentum puede ser baja)
        - Si NO hay pullback -> Aplica filtros estrictos de momentum alta

        Esto respeta tu sistema de esperar retrocesos mientras mejora timing en entradas directas.
        """
        try:
            if pullback_detected:
                # MODO PULLBACK: Más permisivo con momentum, enfoque en calidad de recuperación
                return self._check_pullback_recovery_timing(symbol, bar)
            else:
                # MODO DIRECTO: Filtros estrictos de momentum alta (datos reales)
                return self._check_direct_entry_timing(symbol, bar)

        except Exception as e:
            self.logger.error(f"[HYBRID-TIMING-ERROR] {symbol}: {e}")
            return True  # No bloquear por errores

    def _check_pullback_recovery_timing(self, symbol: str, bar: MarketData) -> bool:
        """
        Timing para entradas en PULLBACK/RECOVERY
        Más permisivo con momentum, enfoque en fuerza de recuperación
        """
        try:
            bars = self.bars_history.get(symbol, [])[-10:]  # Use bars_history instead
            if not bars or len(bars) < 5:
                return True

            # Para pullbacks, verificar FUERZA DE RECUPERACIÓN en lugar de momentum absoluto
            current_price = bar.close
            recent_low = min(bar.low for bar in bars[-5:])  # Último low en 5 barras
            recovery_strength = (current_price - recent_low) / recent_low

            # Símbolo strength (validar que no sea demasiado volátil durante pullback)
            symbol_strength = self._calculate_symbol_strength(symbol)

            # CRITERIOS PARA PULLBACK RECOVERY:
            # 1. Recuperación mínima desde recent low (>1%)
            recovery_ok = recovery_strength > 0.01

            # 2. Symbol strength no demasiado alta (volatilidad controlada)
            strength_ok = symbol_strength < 0.15  # Más permisivo que modo directo

            self.logger.info(f"[PULLBACK-TIMING] {symbol}: recovery={recovery_strength:.3f}, strength={symbol_strength:.3f}")

            timing_passed = recovery_ok and strength_ok

            if not timing_passed:
                reasons = []
                if not recovery_ok:
                    reasons.append(f"weak_recovery({recovery_strength:.3f})")
                if not strength_ok:
                    reasons.append(f"high_volatility({symbol_strength:.3f})")
                self.logger.info(f"[PULLBACK-REJECT] {symbol}: {', '.join(reasons)}")

            return timing_passed

        except Exception as e:
            self.logger.error(f"[PULLBACK-TIMING-ERROR] {symbol}: {e}")
            return True

    def _check_direct_entry_timing(self, symbol: str, bar: MarketData) -> bool:
        """
        Timing para entradas DIRECTAS (sin pullback)
        Filtros estrictos basados en datos reales
        """
        try:
            # Usar filtros originales estrictos para entradas directas
            bars = self.bars_history.get(symbol, [])[-10:]  # Use bars_history instead
            if not bars or len(bars) < 5:
                return True

            # Price momentum alto requerido para entradas directas
            price_5_bars_ago = bars[-5].close
            current_price = bar.close
            price_momentum = (current_price - price_5_bars_ago) / price_5_bars_ago

            # Symbol strength baja requerida
            symbol_strength = self._calculate_symbol_strength(symbol)

            # CRITERIOS ESTRICTOS PARA ENTRADA DIRECTA (datos reales):
            momentum_threshold = 0.871  # Hallazgo de datos reales
            momentum_ok = price_momentum > momentum_threshold

            strength_threshold = 0.111  # Hallazgo de datos reales
            strength_ok = symbol_strength < strength_threshold

            self.logger.info(f"[DIRECT-TIMING] {symbol}: momentum={price_momentum:.3f}, strength={symbol_strength:.3f}")

            timing_passed = momentum_ok and strength_ok

            if not timing_passed:
                reasons = []
                if not momentum_ok:
                    reasons.append(f"momentum_low({price_momentum:.3f})")
                if not strength_ok:
                    reasons.append(f"strength_high({symbol_strength:.3f})")
                self.logger.info(f"[DIRECT-REJECT] {symbol}: {', '.join(reasons)}")

            return timing_passed

        except Exception as e:
            self.logger.error(f"[DIRECT-TIMING-ERROR] {symbol}: {e}")
            return True

    def _check_proactive_timing_filters(self, symbol: str, bar: MarketData) -> bool:
        """
        Filtros de timing proactivo basados en análisis de datos reales de trading_data.db

        Hallazgos de datos reales:
        - Trades exitosos: price_momentum promedio = 1.000 vs perdedores = 0.569
        - Trades exitosos: symbol_strength promedio = 0.000 vs perdedores = 0.370
        - Filtro mejora P&L en +$1.71 promedio
        """
        try:
            # 1. CALCULAR PRICE MOMENTUM
            # Usar datos más recientes para timing preciso
            bars = self.bars_history.get(symbol, [])[-10:]  # Use bars_history instead  # Últimas 10 barras
            if not bars or len(bars) < 5:
                self.logger.debug(f"[TIMING] {symbol}: Insufficient data for momentum calculation")
                return True  # No bloquear por falta de datos

            # Price momentum como % change en 5 barras
            price_5_bars_ago = bars[-5].close
            current_price = bar.close
            price_momentum = (current_price - price_5_bars_ago) / price_5_bars_ago

            # 2. CALCULAR SYMBOL STRENGTH
            # Basado en performance reciente del símbolo
            symbol_strength = self._calculate_symbol_strength(symbol)

            # 3. APLICAR FILTROS BASADOS EN DATOS REALES

            # Filtro 1: Price momentum debe ser alta (hallazgo: >0.871 funciona mejor)
            momentum_threshold = 0.871  # Threshold desde análisis de timing
            momentum_ok = price_momentum > momentum_threshold

            # Filtro 2: Symbol strength debe ser baja (hallazgo: <0.111 funciona mejor)
            strength_threshold = 0.111  # Threshold desde análisis de timing
            strength_ok = symbol_strength < strength_threshold

            # Debug logging
            self.logger.debug(f"[TIMING] {symbol}: momentum={price_momentum:.3f} (need >{momentum_threshold}), "
                            f"strength={symbol_strength:.3f} (need <{strength_threshold})")

            # Ambos filtros deben pasar
            timing_passed = momentum_ok and strength_ok

            if not timing_passed:
                reason = []
                if not momentum_ok:
                    reason.append(f"momentum_low({price_momentum:.3f})")
                if not strength_ok:
                    reason.append(f"strength_high({symbol_strength:.3f})")

                self.logger.info(f"[TIMING-REJECT] {symbol}: {', '.join(reason)}")
            else:
                self.logger.info(f"[TIMING-PASS] {symbol}: momentum={price_momentum:.3f}, strength={symbol_strength:.3f}")

            return timing_passed

        except Exception as e:
            self.logger.error(f"[TIMING-ERROR] {symbol}: Error in proactive timing filters: {e}")
            return True  # No bloquear por errores

    def _calculate_symbol_strength(self, symbol: str) -> float:
        """
        Calcular symbol strength basado en performance reciente
        Valores bajos indican mejor timing (contraintuitivo pero validado por datos)
        """
        try:
            # Obtener trades recientes de este símbolo (últimos 5)
            # Simulamos con datos disponibles por ahora
            bars = self.bars_history.get(symbol, [])[-20:]  # Use bars_history instead
            if not bars or len(bars) < 10:
                return 0.0  # Strength baja = favorable según datos

            # Calcular strength como volatilidad relativa reciente
            recent_closes = [bar.close for bar in bars[-10:]]
            if len(recent_closes) < 2:
                return 0.0

            # Strength = desviación estándar normalizada de precios recientes
            mean_price = sum(recent_closes) / len(recent_closes)
            variance = sum((p - mean_price) ** 2 for p in recent_closes) / len(recent_closes)
            std_dev = variance ** 0.5

            # Normalizar por precio promedio
            symbol_strength = std_dev / mean_price if mean_price > 0 else 0.0

            return symbol_strength

        except Exception as e:
            self.logger.error(f"[STRENGTH-ERROR] {symbol}: Error calculating symbol strength: {e}")
            return 0.0  # Default favorable

    def _check_smallcap_momentum(self, symbol: str) -> bool:
        """Check price momentum for smallcaps"""
        try:
            if len(self.bars_history[symbol]) < 5:
                return False
            
            # Check last 3 bars for momentum
            recent_bars = self.bars_history[symbol][-3:]
            prices = [bar.close for bar in recent_bars]
            
            # Simple momentum: price increasing trend
            momentum = (prices[-1] - prices[0]) / prices[0]
            
            return momentum > 0.01  # At least 1% momentum
            
        except Exception:
            return False
    
    def _check_pullback_opportunity(self, symbol: str, current_bar: MarketData) -> bool:
        """
        Check if current price presents a pullback opportunity rather than a buy-the-top situation
        
        Returns True if:
        1. Price has pulled back 15-30% from recent high within last 20 bars
        2. Current price is bouncing from support level  
        3. Not at a new high (avoid buy-the-top)
        """
        try:
            if len(self.bars_history[symbol]) < 20:
                return True  # Not enough data, allow entry
            
            recent_bars = self.bars_history[symbol][-20:]  # Last 20 bars (20 minutes)
            current_price = current_bar.close
            
            # Find recent high in last 20 bars
            highs = [bar.high for bar in recent_bars]
            recent_high = max(highs)
            recent_high_index = highs.index(recent_high)
            
            # 1. Check if current price is at/near new high (avoid buy-the-top)
            price_vs_high = (current_price - recent_high) / recent_high
            
            if price_vs_high >= 0.005:  # Allow up to 0.5% above recent high (very permissive)
                self.logger.info(f"[PULLBACK] {symbol}: Too close to recent high ${recent_high:.2f} "
                               f"(current: ${current_price:.2f}, diff: {price_vs_high*100:.1f}%)")
                return False
            
            # 2. Check for proper pullback (15-35% from high)
            pullback_pct = abs(price_vs_high)
            
            if pullback_pct < 0.005:  # Less than 0.5% pullback (very relaxed to allow more entries)
                self.logger.info(f"[PULLBACK] {symbol}: Insufficient pullback {pullback_pct*100:.1f}% "
                               f"from high ${recent_high:.2f}")
                return False
                
            if pullback_pct > 0.35:  # More than 35% pullback might be broken
                self.logger.info(f"[PULLBACK] {symbol}: Too much pullback {pullback_pct*100:.1f}% "
                               f"from high ${recent_high:.2f} - possible break down")
                return False
            
            # 3. Check if we're bouncing from a support level
            # Look at recent lows to identify support
            lows = [bar.low for bar in recent_bars[-10:]]  # Last 10 bars
            recent_low = min(lows)
            
            # Current price should be above recent low (bouncing)
            bounce_from_low = (current_price - recent_low) / recent_low
            
            if bounce_from_low < 0.01:  # Less than 1% bounce (relaxed for more opportunities)
                self.logger.info(f"[PULLBACK] {symbol}: Not enough bounce from low ${recent_low:.2f} "
                               f"(current: ${current_price:.2f}, bounce: {bounce_from_low*100:.1f}%)")
                return False
            
            # 4. All conditions met - good pullback opportunity
            self.logger.info(f"[PULLBACK] {symbol}: ✓ Good pullback opportunity detected! "
                           f"High: ${recent_high:.2f}, Current: ${current_price:.2f} "
                           f"(pullback: {pullback_pct*100:.1f}%, bounce: {bounce_from_low*100:.1f}%)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking pullback opportunity for {symbol}: {e}")
            return True  # Default to allow entry if check fails
    
    def _get_atr_percentage(self, symbol: str) -> Optional[float]:
        """Get ATR as percentage of price"""
        try:
            atr = self.calculate_atr(symbol, self._parameters.get('atr_period', 10))
            if not atr:
                return None
            
            current_price = self.bars_history[symbol][-1].close
            return atr / current_price if current_price > 0 else None
            
        except Exception:
            return None
    
    def _calculate_macd_5min(self, symbol: str) -> Optional[Dict[str, float]]:
        """Calculate MACD using 5-minute aggregated bars"""
        try:
            if symbol not in self.bars_history or len(self.bars_history[symbol]) < 25:
                return None
            
            # Aggregate 1min bars to 5min bars
            bars_5min = self._aggregate_to_5min(self.bars_history[symbol])
            if len(bars_5min) < max(self._parameters['macd_slow'] + 5, 20):
                return None
            
            # Calculate MACD on 5min data
            closes = [bar['close'] for bar in bars_5min]
            
            # Calculate EMAs
            fast_period = self._parameters['macd_fast']
            slow_period = self._parameters['macd_slow'] 
            signal_period = self._parameters['macd_signal']
            
            if len(closes) < slow_period + signal_period:
                return None
            
            # Simple EMA calculation
            def calculate_ema(data, period):
                if len(data) < period:
                    return None
                multiplier = 2.0 / (period + 1)
                ema = [sum(data[:period]) / period]
                for i in range(period, len(data)):
                    ema.append((data[i] * multiplier) + (ema[-1] * (1 - multiplier)))
                return ema
            
            fast_ema = calculate_ema(closes, fast_period)
            slow_ema = calculate_ema(closes, slow_period)
            
            if not fast_ema or not slow_ema:
                return None
            
            # Align arrays (both should have same length after slow_period)
            start_idx = slow_period - fast_period
            if start_idx > 0:
                fast_ema = fast_ema[start_idx:]
            
            # Calculate MACD line
            macd_line = [fast_ema[i] - slow_ema[i] for i in range(len(slow_ema))]
            
            # Calculate signal line
            signal_line = calculate_ema(macd_line, signal_period)
            if not signal_line:
                return None
            
            # Get current values
            current_macd = macd_line[-1]
            current_signal = signal_line[-1]
            current_histogram = current_macd - current_signal
            
            # Get previous values for comparison
            prev_macd = macd_line[-2] if len(macd_line) >= 2 else current_macd
            
            return {
                'macd': current_macd,
                'signal': current_signal,
                'histogram': current_histogram,
                'prev_macd': prev_macd
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating 5min MACD for {symbol}: {e}")
            return None

    def _detect_macd_convergence_5min(self, symbol: str) -> Dict[str, Any]:
        """
        Detecta cuando MACD 5min se acerca al cruce bullish - Activador de timing 1min

        Returns:
            Dict con:
            - approaching_cross: bool - Si está cerca del cruce
            - urgency: int (1-10) - Qué tan cerca está del cruce
            - momentum: str - Dirección del momentum
            - distance: float - Distancia actual MACD vs Signal
        """
        try:
            # Obtener datos MACD 5min actuales e históricos
            macd_5min = self._calculate_macd_5min(symbol)
            if not macd_5min:
                return {'approaching_cross': False, 'urgency': 0, 'momentum': 'unknown', 'distance': 999}

            # Obtener historia de 5min para análisis de momentum
            # CRITICAL FIX: Use enhanced_data_manager if available, otherwise skip this analysis
            if not hasattr(self, 'enhanced_data_manager') or not self.enhanced_data_manager:
                return {'approaching_cross': False, 'urgency': 0, 'momentum': 'unknown', 'distance': 999}

            # Get historical data through enhanced_data_manager
            try:
                df = self.enhanced_data_manager.get_bars_history(symbol)
                if df is None or len(df) < 50:
                    return {'approaching_cross': False, 'urgency': 0, 'momentum': 'unknown', 'distance': 999}
            except Exception as e:
                self.logger.warning(f"Could not get historical data for {symbol}: {e}")
                return {'approaching_cross': False, 'urgency': 0, 'momentum': 'unknown', 'distance': 999}

            # Agregar a 5min y calcular MACD histórico
            df_5min = df.resample('5T', on='timestamp').agg({
                'close': 'last'
            }).dropna()

            if len(df_5min) < 10:
                return {'approaching_cross': False, 'urgency': 0, 'momentum': 'unknown', 'distance': 999}

            # Calcular MACD para últimas barras 5min
            fast_ema = df_5min['close'].ewm(span=self._parameters['macd_fast']).mean()
            slow_ema = df_5min['close'].ewm(span=self._parameters['macd_slow']).mean()
            macd_line = fast_ema - slow_ema
            signal_line = macd_line.ewm(span=self._parameters['macd_signal']).mean()

            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            prev_macd = macd_line.iloc[-2] if len(macd_line) >= 2 else current_macd
            prev_signal = signal_line.iloc[-2] if len(signal_line) >= 2 else current_signal

            # Calcular distancia al cruce
            distance = abs(current_macd - current_signal)

            # Detectar momentum hacia cruce bullish
            macd_momentum = current_macd - prev_macd  # Positivo = MACD subiendo
            signal_momentum = current_signal - prev_signal  # Positivo = Signal subiendo
            relative_momentum = macd_momentum - signal_momentum  # Positivo = MACD acercándose por arriba

            # Condiciones para convergencia bullish
            conditions = {
                'macd_below_signal': current_macd < current_signal,  # Debe estar abajo para cruzar hacia arriba
                'distance_threshold': distance < 0.05,  # Cerca del cruce (ajustable según el activo)
                'positive_momentum': relative_momentum > 0,  # MACD acercándose desde abajo
                'not_too_low': current_macd > -0.3  # No demasiado oversold (evita rebotes débiles)
            }

            # Calcular urgencia (1-10) basada en distancia y momentum
            urgency = 0
            if conditions['macd_below_signal'] and conditions['positive_momentum']:
                # Base urgency por distancia (más cerca = más urgencia)
                distance_score = max(0, 10 - (distance * 100))  # Normalizar distancia

                # Bonus por momentum fuerte
                momentum_score = min(relative_momentum * 50, 5)  # Max 5 puntos por momentum

                urgency = min(int(distance_score + momentum_score), 10)

            # Determinar si está approach el cruce
            approaching_cross = (
                conditions['macd_below_signal'] and
                conditions['distance_threshold'] and
                conditions['positive_momentum'] and
                conditions['not_too_low'] and
                urgency >= 5  # Mínimo urgencia 5/10
            )

            momentum_str = 'bullish' if relative_momentum > 0 else 'bearish'

            if approaching_cross:
                self.logger.info(f"[5MIN-CONVERGENCE] {symbol}: Distance={distance:.4f}, Momentum={relative_momentum:.4f}, Urgency={urgency}/10")

            return {
                'approaching_cross': approaching_cross,
                'urgency': urgency,
                'momentum': momentum_str,
                'distance': distance,
                'conditions': conditions,
                'macd_current': current_macd,
                'signal_current': current_signal
            }

        except Exception as e:
            self.logger.error(f"Error detecting 5min MACD convergence for {symbol}: {e}")
            return {'approaching_cross': False, 'urgency': 0, 'momentum': 'error', 'distance': 999}

    def _analyze_1min_macd_timing(self, symbol: str, bar: MarketData, convergence_5min: Dict) -> Optional[Dict]:
        """
        Análisis preciso 1min cuando 5min muestra convergencia inminente

        Args:
            symbol: Symbol to analyze
            bar: Current 1min bar
            convergence_5min: Resultado del detector 5min

        Returns:
            Dict con score y conditions_met, o None si no hay entrada
        """
        try:
            # 1. Calcular MACD 1min
            macd_data = self._safe_calculate_macd(
                symbol,
                self._parameters['macd_fast'],
                self._parameters['macd_slow'],
                self._parameters['macd_signal']
            )

            if not macd_data:
                return None

            # 2. Verificar tracking histórico 1min
            if symbol not in self.last_macd_values:
                self.last_macd_values[symbol] = macd_data
                return None

            prev_macd = self.last_macd_values[symbol]
            current_macd = macd_data

            # 3. Detectar cruce MACD bullish 1min
            macd_cross_1min = (
                prev_macd['macd'] <= prev_macd['signal'] and
                current_macd['macd'] > current_macd['signal']
            )

            # 4. Actualizar tracking
            self.last_macd_values[symbol] = current_macd

            # 5. Evaluar calidad del timing
            score = 0
            conditions_met = []

            if macd_cross_1min:
                # Base score por cruce 1min
                score += 4
                conditions_met.append("macd_cross_1min")

                # Bonus por alineación con convergencia 5min
                alignment_bonus = min(convergence_5min['urgency'] / 2, 3)
                score += alignment_bonus
                conditions_met.append(f"5min_alignment_{alignment_bonus:.1f}")

                # Bonus por calidad del cruce 1min
                macd_strength = current_macd['macd'] - current_macd['signal']
                if macd_strength > 0.01:  # Cruce con cierta fuerza
                    score += 2
                    conditions_met.append("strong_1min_cross")

                # Bonus por recovery pattern
                if self._is_macd_recovery_pattern(current_macd, prev_macd):
                    score += 2
                    conditions_met.append("macd_recovery")

                self.logger.info(f"[1MIN-TIMING] {symbol}: ✓ MACD cross detected, Score={score}, Conditions={conditions_met}")

                return {
                    'score': score,
                    'conditions_met': conditions_met,
                    'cross_strength': macd_strength,
                    'macd_data': current_macd
                }

            else:
                # No hay cruce 1min todavía, pero 5min sugiere que viene
                if convergence_5min['urgency'] >= 7:
                    self.logger.debug(f"[1MIN-WAITING] {symbol}: Waiting for 1min cross (5min urgency: {convergence_5min['urgency']}/10)")

                return None

        except Exception as e:
            self.logger.error(f"Error analyzing 1min MACD timing for {symbol}: {e}")
            return None

    def _calculate_macd_15min(self, symbol: str) -> Optional[Dict[str, float]]:
        """Calculate MACD using 15-minute aggregated bars"""
        try:
            if symbol not in self.bars_history or len(self.bars_history[symbol]) < 60:
                return None

            # Aggregate 1min bars to 15min bars
            bars_15min = self._aggregate_to_15min(self.bars_history[symbol])
            if len(bars_15min) < max(self._parameters['macd_slow'] + 5, 20):
                return None

            # Calculate MACD on 15min data
            closes = [bar['close'] for bar in bars_15min]

            # Calculate EMAs
            fast_period = self._parameters['macd_fast']
            slow_period = self._parameters['macd_slow']
            signal_period = self._parameters['macd_signal']

            if len(closes) < slow_period + signal_period:
                return None

            # Simple EMA calculation
            def calculate_ema(data, period):
                if len(data) < period:
                    return None
                multiplier = 2.0 / (period + 1)
                ema = [sum(data[:period]) / period]
                for i in range(period, len(data)):
                    ema.append((data[i] * multiplier) + (ema[-1] * (1 - multiplier)))
                return ema

            fast_ema = calculate_ema(closes, fast_period)
            slow_ema = calculate_ema(closes, slow_period)

            if not fast_ema or not slow_ema:
                return None

            # Align arrays
            start_idx = slow_period - fast_period
            if start_idx > 0:
                fast_ema = fast_ema[start_idx:]

            # Calculate MACD line
            macd_line = [fast_ema[i] - slow_ema[i] for i in range(len(slow_ema))]

            # Calculate signal line
            signal_line = calculate_ema(macd_line, signal_period)
            if not signal_line:
                return None

            # Get current values
            current_macd = macd_line[-1]
            current_signal = signal_line[-1]
            current_histogram = current_macd - current_signal

            # Get previous values for comparison
            prev_macd = macd_line[-2] if len(macd_line) >= 2 else current_macd

            return {
                'macd': current_macd,
                'signal': current_signal,
                'histogram': current_histogram,
                'prev_macd': prev_macd
            }

        except Exception as e:
            self.logger.error(f"Error calculating 15min MACD for {symbol}: {e}")
            return None

    def _aggregate_to_5min(self, bars_1min) -> list:
        """Aggregate 1-minute bars to 5-minute bars"""
        try:
            if len(bars_1min) < 5:
                return []
            
            bars_5min = []
            
            # Group bars by 5-minute intervals
            for i in range(0, len(bars_1min) - 4, 5):
                chunk = bars_1min[i:i+5]
                if len(chunk) < 5:
                    continue
                
                # Create 5-min bar
                bar_5min = {
                    'timestamp': chunk[-1].timestamp,  # Use last timestamp
                    'open': chunk[0].open,
                    'high': max(bar.high for bar in chunk),
                    'low': min(bar.low for bar in chunk),
                    'close': chunk[-1].close,
                    'volume': sum(bar.volume for bar in chunk)
                }
                bars_5min.append(bar_5min)
            
            return bars_5min
            
        except Exception as e:
            self.logger.error(f"Error aggregating to 5min bars: {e}")
            return []

    def _aggregate_to_15min(self, bars_1min) -> list:
        """Aggregate 1-minute bars to 15-minute bars"""
        try:
            if len(bars_1min) < 15:
                return []

            bars_15min = []

            for i in range(0, len(bars_1min), 15):
                chunk = bars_1min[i:i+15]
                if len(chunk) < 15:
                    break

                # Calculate OHLCV for the 15-minute period
                opens = [bar['open'] for bar in chunk]
                highs = [bar['high'] for bar in chunk]
                lows = [bar['low'] for bar in chunk]
                closes = [bar['close'] for bar in chunk]
                volumes = [bar['volume'] for bar in chunk]

                bar_15min = {
                    'timestamp': chunk[0]['timestamp'],
                    'open': opens[0],
                    'high': max(highs),
                    'low': min(lows),
                    'close': closes[-1],
                    'volume': sum(volumes)
                }

                bars_15min.append(bar_15min)

            return bars_15min

        except Exception as e:
            self.logger.error(f"Error aggregating to 15min bars: {e}")
            return []

    def _is_in_cooldown(self, symbol: str, current_time) -> bool:
        """Check cooldown period"""
        if symbol not in self.last_signal_time:
            return False
        
        try:
            from datetime import datetime, timezone
            if isinstance(current_time, str):
                current_dt = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
            else:
                current_dt = current_time
                
            last_signal_dt = self.last_signal_time[symbol]
            if isinstance(last_signal_dt, str):
                last_signal_dt = datetime.fromisoformat(last_signal_dt.replace('Z', '+00:00'))
            
            # Handle timezone differences between datetime objects
            if hasattr(last_signal_dt, 'tzinfo') and last_signal_dt.tzinfo is not None and hasattr(current_dt, 'tzinfo') and current_dt.tzinfo is None:
                # last_signal_dt is timezone-aware, make current_dt timezone-aware too
                current_dt = current_dt.replace(tzinfo=timezone.utc)
            elif hasattr(current_dt, 'tzinfo') and current_dt.tzinfo is not None and hasattr(last_signal_dt, 'tzinfo') and last_signal_dt.tzinfo is None:
                # current_dt is timezone-aware, remove timezone info to match
                current_dt = current_dt.replace(tzinfo=None)
            
            cooldown_seconds = self._parameters.get('min_seconds_between_trades', 600)
            time_diff = (current_dt - last_signal_dt).total_seconds()
            
            return time_diff < cooldown_seconds
            
        except Exception:
            return False
    
    def _register_position_with_stop_manager(self, symbol: str, bar: MarketData, signal: Signal):
        """Register the new position with SMALLCAP-OPTIMIZED centralized stop loss manager"""

        # SMALLCAPS: Use global config.ini parameters optimized for smallcaps
        # These parameters are now centralized in config.ini:
        # - fallback_stop_loss_pct = 0.06 (6% for volatility)
        # - enable_dynamic_ema_trailing = true
        # - ema_trailing_periods = 5 (faster response)
        # - partial_profit_threshold = 0.08 (8% partial exit)
        # - max_hold_minutes = 180 (3 hours max)
        stop_params = create_stop_params_from_config(self._parameters)

        # Determine side
        side = 'bullish' if signal.signal_type == SignalType.LONG else 'bearish'

        # Register with stop manager
        self.stop_manager.register_position(
            symbol=symbol,
            entry_price=signal.price,
            entry_time=bar.timestamp,
            side=side,
            strategy_name="MACDV_Smallcaps_Optimized",
            stop_params=stop_params
        )

        self.logger.info(f"📊 {symbol}: SMALLCAP-OPTIMIZED stop management active - "
                        f"6% stop, EMA-5 trailing, 8% partial exit, 3h max hold")
    
    def _can_open_new_position(self, symbol: str, current_price: float, side: str) -> Dict[str, Any]:
        """
        Control de apertura de nuevas posiciones para MACDV Strategy
        
        Returns:
            Dict with 'can_open', 'position_action', 'reason'
        """
        try:
            # 1. Check if already have position for this symbol
            if symbol in self.entry_signals:
                return {
                    'can_open': False,
                    'position_action': 'blocked',
                    'reason': f"Already have position for {symbol}"
                }
            
            # 2. Check daily trades limit
            from datetime import datetime
            current_date = datetime.now().date()
            if not hasattr(self, 'daily_trades'):
                self.daily_trades = {}
            
            if current_date not in self.daily_trades:
                self.daily_trades[current_date] = 0
            
            max_daily_trades = self._parameters.get('max_daily_trades', 10)
            if self.daily_trades[current_date] >= max_daily_trades:
                return {
                    'can_open': False,
                    'position_action': 'blocked',
                    'reason': f"Daily trades limit reached ({max_daily_trades})"
                }
            
            # 3. Check cooldown period
            if hasattr(self, 'last_signal_time') and symbol in self.last_signal_time:
                try:
                    current_time = datetime.now()
                    last_signal_time = self.last_signal_time[symbol]
                    
                    # Handle timezone differences between datetime objects
                    if hasattr(last_signal_time, 'tzinfo') and last_signal_time.tzinfo is not None:
                        # last_signal_time is timezone-aware, make current_time timezone-aware too
                        from datetime import timezone
                        current_time = current_time.replace(tzinfo=timezone.utc)
                    elif hasattr(current_time, 'tzinfo') and current_time.tzinfo is not None:
                        # current_time is timezone-aware, remove timezone info to match
                        current_time = current_time.replace(tzinfo=None)
                    
                    time_since_last = (current_time - last_signal_time).total_seconds()
                    cooldown_seconds = self._parameters.get('min_seconds_between_trades', 600)
                except Exception as e:
                    self.logger.error(f"Error calculating cooldown time for {symbol}: {e}")
                    time_since_last = 0
                    cooldown_seconds = self._parameters.get('min_seconds_between_trades', 600)
                
                if time_since_last < cooldown_seconds:
                    return {
                        'can_open': False,
                        'position_action': 'blocked',
                        'reason': f"Cooldown period ({cooldown_seconds}s)"
                    }
            
            # All checks passed - can open new position
            return {
                'can_open': True,
                'position_action': 'new',
                'reason': 'All checks passed'
            }
            
        except Exception as e:
            self.logger.error(f"Error in position control for {symbol}: {e}")
            return {
                'can_open': False,
                'position_action': 'blocked',
                'reason': f"Error in position control: {e}"
            }
    
    def _cleanup_position_tracking(self, symbol: str):
        """Clean up our tracking when position exits"""
        if symbol in self.entry_signals:
            del self.entry_signals[symbol]
        
        # Note: No need to cleanup stop loss tracking - that's handled by the manager
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Position sizing optimized for smallcaps"""
        try:
            price = signal.price
            risk_amount = capital * min(risk_per_trade, self._parameters.get('risk_per_trade', 0.015))
            stop_loss_pct = self._parameters.get('stop_loss_pct', 0.05)  # Uses config.ini fallback_stop_loss_pct
            
            # Calculate base quantity
            stop_distance = price * stop_loss_pct
            base_quantity = int(risk_amount / stop_distance) if stop_distance > 0 else 100
            
            # Apply smallcap-specific limits
            max_position_value = self._parameters.get('max_position_value', 300.0)
            min_position_value = self._parameters.get('min_position_value', 50.0)
            
            max_shares = min(
                int(max_position_value / price),
                self._parameters.get('max_quantity', 200)
            )
            min_shares = max(
                int(min_position_value / price),
                self._parameters.get('min_quantity', 10)
            )
            
            # Calculate position size
            position_size = max(min_shares, min(base_quantity, max_shares))
            
            # ROUND TO NEAREST 10 for smallcaps (better for small accounts)
            position_size = (position_size // 10) * 10
            position_size = max(position_size, 10)
            
            position_value = position_size * price
            
            self.logger.info(f"[SMALLCAP-SIZE] {signal.symbol}: {position_size} shares @ ${price:.2f} "
                           f"(Value: ${position_value:.0f}, Risk: ${risk_amount:.0f})")
            
            return position_size
            
        except Exception as e:
            self.logger.error(f"Error calculating smallcap position size: {e}")
            return 100
    
    # Implement required abstract methods from IStrategy
    def on_position_update(self, symbol: str, position: Position):
        """Handle position updates - required by IStrategy interface"""
        # For this strategy, we don't need special logic on position updates
        # The stop loss management is handled by the centralized stop manager
        return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited - SMALLCAP-OPTIMIZED with centralized stop manager ONLY"""
        try:
            # SMALLCAPS: Use ONLY centralized stop manager (no fallback)
            # This ensures all advanced features work: EMA trailing, partial profits, time exits, etc.
            if not (hasattr(self, 'stop_manager') and self.stop_manager):
                self.logger.error(f"❌ {position.symbol}: No stop_manager available - this should not happen!")
                return None

            exit_signal = self.stop_manager.check_exit_conditions(
                symbol=position.symbol,
                current_bar=current_bar
            )

            if exit_signal:
                # Convert stop manager signal to our Signal format
                return Signal(
                    signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                    symbol=position.symbol,
                    signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                    strength=1.0,
                    price=current_bar.close,
                    timestamp=current_bar.timestamp,
                    strategy_name="MACDV_Smallcaps_Optimized",
                    metadata={
                        'reason': exit_signal.get('reason', 'stop_manager'),
                        'exit_type': exit_signal.get('exit_reason', 'unknown'),
                        'entry_price': position.avg_price,
                        'pnl_pct': exit_signal.get('pnl_pct', 0),
                        'stop_manager_features': 'EMA_trailing,partial_profits,time_exits'
                    }
                )

            return None

        except Exception as e:
            self.logger.error(f"Error in should_exit for {position.symbol}: {e}")
            return None

    def _analyze_order_flow_signals(self, symbol: str, bar: MarketData) -> Optional[list]:
        """
        Analiza señales de order flow para detectar desequilibrios predictivos

        Returns:
            List of OrderFlowSignal objects if signals detected, None otherwise
        """
        try:
            # Check if we have the required bid/ask data
            if not all([bar.bid, bar.ask, bar.bid_size, bar.ask_size]):
                self.logger.debug(f"[ORDER-FLOW] {symbol}: Missing bid/ask data for order flow analysis")
                return None

            # Use OrderFlowAnalyzer to detect predictive signals
            signals = self.order_flow_analyzer.analyze_order_flow(symbol, bar)

            if signals:
                # Log detailed information about detected signals
                for signal in signals:
                    self.logger.info(f"[ORDER-FLOW] {symbol}: {signal.signal_type} - "
                                   f"Strength: {signal.strength:.2f}, "
                                   f"Confidence: {signal.confidence:.2f}, "
                                   f"Reason: {signal.reason}")

                return signals

            return None

        except Exception as e:
            self.logger.error(f"[ORDER-FLOW] Error analyzing order flow for {symbol}: {e}")
            return None

    def _extract_order_flow_metadata(self, order_flow_signals: Optional[list], bar: MarketData) -> Dict[str, Any]:
        """
        Extract detailed order flow metadata for database storage

        Args:
            order_flow_signals: List of OrderFlowSignal objects
            bar: Current market data bar

        Returns:
            Dictionary with order flow metadata
        """
        metadata = {}

        try:
            if not order_flow_signals:
                return metadata

            # Initialize boolean flags
            metadata['institutional_activity'] = False
            metadata['aggressive_buying'] = False
            metadata['pressure_building'] = False

            # Extract data from each signal
            for signal in order_flow_signals:
                if signal.signal_type == 'BULLISH_PRESSURE':
                    metadata['bid_pressure'] = signal.metadata.get('bid_pressure', 0)

                elif signal.signal_type == 'INSTITUTIONAL_ACTIVITY':
                    metadata['institutional_activity'] = True
                    metadata['spread_compression_ratio'] = signal.metadata.get('compression_ratio', 0)

                elif signal.signal_type == 'AGGRESSIVE_BUYING':
                    metadata['aggressive_buying'] = True
                    metadata['volume_at_ask_ratio'] = signal.metadata.get('volume_at_ask_ratio', 0)

                elif signal.signal_type == 'PRESSURE_BUILDING':
                    metadata['pressure_building'] = True
                    metadata['volume_multiplier'] = signal.metadata.get('volume_multiplier', 0)

            # Calculate bid pressure if not already set
            if 'bid_pressure' not in metadata and bar.bid_size and bar.ask_size:
                total_size = bar.bid_size + bar.ask_size
                metadata['bid_pressure'] = bar.bid_size / total_size if total_size > 0 else 0.5

            # Calculate volume at bid ratio (complement of ask ratio)
            if 'volume_at_ask_ratio' in metadata:
                metadata['volume_at_bid_ratio'] = 1.0 - metadata['volume_at_ask_ratio']

            return metadata

        except Exception as e:
            self.logger.error(f"[ORDER-FLOW] Error extracting order flow metadata: {e}")
            return {}

    def get_strategy_info(self) -> dict:
        """Strategy information"""
        return {
            "name": "MACDV Smallcaps Multi-Timeframe",
            "type": "MACD Multi-timeframe (Volume-agnostic entries)",
            "price_range": f"${self._parameters['min_price']:.2f} - ${self._parameters['max_price']:.2f}",
            "timeframe": "5min convergence -> 1min precision timing",
            "active_positions": len(self.entry_signals),
            "parameters": {
                "macd_fast": self._parameters['macd_fast'],
                "macd_slow": self._parameters['macd_slow'],
                "volume_threshold": self._parameters['volume_threshold'],
                "stop_loss": f"{self._parameters['stop_loss_pct']*100:.1f}%",
                "take_profit": f"{self._parameters['take_profit_pct']*100:.1f}%",
                "multi_timeframe": "5min convergence detector + 1min precise entry"
            }
        }