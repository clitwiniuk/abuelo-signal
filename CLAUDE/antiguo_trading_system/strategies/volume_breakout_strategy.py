# strategies/volume_breakout_strategy.py
"""
Volume Breakout Strategy: ESTRATEGIA AUTÓNOMA PARA SMALLCAPS
Detecta aumentos súbitos de volumen junto con ruptura de niveles
PERFECTA PARA TRADING AUTOMÁTICO SIN INTERVENCIÓN MANUAL
"""

from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import deque

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config


class VolumeBreakoutStrategy(BaseStrategy):
    """
    Volume Breakout Strategy - COMPLETAMENTE AUTÓNOMA
    
    CARACTERÍSTICAS:
    1. Opera durante todo el horario de mercado
    2. No necesita datos externos ni pre-filtros
    3. Detecta automáticamente momentum + volumen
    4. Gestión de riesgo integrada
    5. Optimizada para smallcaps volátiles
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # FALLBACK DEFAULTS - All parameters ML-configurable
        fallback_defaults = {
            # Breakout Detection (ML-configurable)
            'lookback_periods': 20,
            'breakout_buffer': 0.008,
            'min_breakout_move': 0.012,
            'max_breakout_move': 0.08,
            
            # Volume Filters (ML-configurable)
            'volume_lookback': 20,
            'volume_multiplier': 1.5,
            'min_volume_threshold': 3000,
            'volume_spike_multiplier': 2.5,
            
            # Momentum Confirmation (ML-configurable)
            'momentum_periods': 10,
            'momentum_threshold': 0.005,
            'rsi_overbought': 75,
            'rsi_oversold': 25,
            'rsi_periods': 14,
            
            # Risk Management (ML-configurable)
            'stop_loss_pct': 0.025,
            'take_profit_pct': 0.08,
            
            # Trailing Stop Advanced (ML-configurable)
            'trailing_stop_pct': 0.015,
            'trailing_activation': 0.018,
            'aggressive_trailing_pct': 0.012,
            'aggressive_trailing_threshold': 0.05,
            
            # Take Profit Mobile (ML-configurable)
            'dynamic_take_profit': True,
            'tp_step_size': 0.025,
            'tp_move_ratio': 0.6,
            'max_take_profit': 0.25,
            'partial_profit_enabled': True,
            'partial_profit_threshold': 0.06,
            'partial_profit_size': 0.5,
            
            'max_hold_time': 150,
            
            # Price Filters (ML-configurable)
            'min_price': 1.2,
            'max_price': 85.0,
            'min_spread_pct': 0.001,
            'max_spread_pct': 0.035,
            
            # Trading Hours (ML-configurable)
            'market_open_hour': 9.5,
            'market_close_hour': 15.5,
            'avoid_first_minutes': 15,
            'avoid_last_minutes': 30,
            
            # Position Control (ML-configurable)
            'max_daily_trades': 8,
            'max_concurrent_positions': 4,
            'cooldown_minutes': 45,
            'daily_loss_limit': 100.0,
            'max_risk_per_trade': 0.025,
            
            # Position Sizing (ML-configurable)
            'base_position_value': 150.0,
            'min_position_value': 50.0,
            'max_position_value': 300.0,
            'volatility_adjustment': True,
            
            # Commissions (ML-configurable)
            'commission_per_share': 0.005,
            'min_commission': 1.0,
            'slippage_bps': 6,
            
            # Quality Filters (ML-configurable)
            'min_daily_volume': 75000,
            'min_price_change': 0.008,
            'exclude_earnings_days': False,
            
            # FOMO detection parameters (ML-configurable)
            'fomo_threshold': 0.75,
            'fomo_critical_threshold': 0.90,
            'fomo_volume_explosion_multiplier': 8.0,
            'fomo_consecutive_green_bars': 4,
            'fomo_rsi_overbought_level': 80,
            
            # Entry qualification threshold (ML-configurable)
            'min_qualified_score': 0.4,  # Minimum score to qualify for entry
        }
        
        # Initialize with fallback defaults first to get logger
        super().__init__("VolumeBreakout", fallback_defaults)
        
        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()
        
        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('VOLUME_BREAKOUT_STRATEGY', fallback_defaults)
            
            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for VolumeBreakout strategy: {e}")
            # Keep fallback defaults
        
        # Asignar parámetros como atributos - safely access _parameters
        params_to_use = self._parameters or config_params
        try:
            for key, value in params_to_use.items():
                setattr(self, key, value)
        except Exception as e:
            print(f"❌ Error setting parameters: {e}")
            print(f"   params_to_use type: {type(params_to_use)}")
            print(f"   params_to_use value: {params_to_use}")
            raise
        
        # Enable FOMO detection for VolumeBreakout (ML-configurable)
        fomo_config = {
            'fomo_threshold': self._parameters.get('fomo_threshold', 0.75),
            'critical_threshold': self._parameters.get('fomo_critical_threshold', 0.90),
            'volume_explosion_multiplier': self._parameters.get('fomo_volume_explosion_multiplier', 8.0),
            'consecutive_green_bars': self._parameters.get('fomo_consecutive_green_bars', 4),
            'rsi_overbought_level': self._parameters.get('fomo_rsi_overbought_level', 80)
        }
        
        if self.enable_fomo_exit(fomo_config):
            self.logger.info("🎪 FOMO Detection enabled for Volume Breakout Strategy")
        else:
            self.logger.warning("⚠️ FOMO Detection could not be enabled")
        
        # Estado de la estrategia
        self.active_positions = {}
        self.daily_trades = {}
        self.daily_pnl = {}
        self.last_trade_times = {}
        self.volume_history = {}            # Historia de volumen por símbolo
        self.price_history = {}             # Historia de precios para breakouts
        
        # Métricas de rendimiento
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        
        # Cache para cálculos
        self.rsi_cache = {}
        self.volume_avg_cache = {}
        
    async def _initialize_strategy(self) -> None:
        """Inicialización de la estrategia"""
        try:
            self.logger.info("🚀 Inicializando Volume Breakout Strategy")
            print(f"🔍 Debug: volume_multiplier = {getattr(self, 'volume_multiplier', 'NOT_SET')}")
            print(f"🔍 Debug: breakout_buffer = {getattr(self, 'breakout_buffer', 'NOT_SET')}")
            print(f"🔍 Debug: max_daily_trades = {getattr(self, 'max_daily_trades', 'NOT_SET')}")
            
            self.logger.info(f"Parámetros clave: vol_mult={self.volume_multiplier}x, "
                            f"breakout_buffer={self.breakout_buffer*100:.1f}%, "
                            f"max_trades={self.max_daily_trades}")
        except Exception as e:
            print(f"❌ Error in _initialize_strategy: {e}")
            import traceback
            print(f"📍 Full traceback: {traceback.format_exc()}")
            raise
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Análisis principal de cada barra"""
        symbol = bar.symbol
        
        # 1. Actualizar historiales
        self._update_histories(symbol, bar)
        
        # DEBUG: STOP LOSS DESACTIVADO - Comentado para debugging
        # exit_signal = await self._check_exit_conditions(symbol, bar)
        # if exit_signal:
        #     return exit_signal
        
        # 3. Si ya tiene posición, no analizar entrada
        if symbol in self.active_positions:
            return None
        
        # 4. Verificar si puede tomar nueva posición
        if not self._can_take_new_position(symbol, bar):
            return None
        
        # 5. Análisis de entrada
        entry_analysis = await self._analyze_entry_opportunity(symbol, bar)
        
        if entry_analysis['qualified']:
            return await self._create_entry_signal(symbol, bar, entry_analysis)
        
        return None
    
    def _update_histories(self, symbol: str, bar: MarketData) -> None:
        """Actualizar historiales de volumen y precio"""
        # Inicializar si no existe
        if symbol not in self.volume_history:
            self.volume_history[symbol] = deque(maxlen=self.volume_lookback + 5)
            self.price_history[symbol] = deque(maxlen=self.lookback_periods + 5)
        
        # Agregar datos actuales
        self.volume_history[symbol].append({
            'timestamp': bar.timestamp,
            'volume': bar.volume,
            'price': bar.close
        })
        
        self.price_history[symbol].append({
            'timestamp': bar.timestamp,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'open': bar.open,
            'volume': bar.volume
        })
    
    async def _analyze_entry_opportunity(self, symbol: str, bar: MarketData) -> Dict:
        """Analizar oportunidad de entrada con todos los filtros"""
        analysis = {
            'qualified': False,
            'score': 0.0,
            'signals': {},
            'breakout_direction': None,
            'strength': 0.0
        }
        
        # 1. Verificar datos suficientes
        if not self._has_sufficient_data(symbol):
            return analysis
        
        # 2. Detectar breakout de precio
        breakout_analysis = self._detect_price_breakout(symbol, bar)
        analysis['signals']['breakout'] = breakout_analysis
        
        if not breakout_analysis['detected']:
            return analysis
        
        # 3. Verificar volumen excepcional
        volume_analysis = self._analyze_volume_surge(symbol, bar)
        analysis['signals']['volume'] = volume_analysis
        
        if not volume_analysis['surge_detected']:
            return analysis
        
        # 4. Confirmar momentum
        momentum_analysis = self._analyze_momentum(symbol, bar, breakout_analysis['direction'])
        analysis['signals']['momentum'] = momentum_analysis
        
        # 5. Filtros adicionales
        quality_analysis = self._analyze_quality_filters(symbol, bar)
        analysis['signals']['quality'] = quality_analysis
        
        # 6. RSI para evitar extremos
        rsi_analysis = self._analyze_rsi_filter(symbol, bar, breakout_analysis['direction'])
        analysis['signals']['rsi'] = rsi_analysis
        
        # 7. Calcular score final
        score_components = [
            breakout_analysis.get('strength', 0) * 0.25,
            volume_analysis.get('strength', 0) * 0.30,
            momentum_analysis.get('strength', 0) * 0.20,
            quality_analysis.get('strength', 0) * 0.15,
            rsi_analysis.get('strength', 0) * 0.10
        ]
        
        analysis['score'] = sum(score_components)
        analysis['breakout_direction'] = breakout_analysis['direction']
        analysis['strength'] = analysis['score']
        
        # Requerimientos para calificar:
        required_signals = [
            breakout_analysis['detected'],
            volume_analysis['surge_detected'],
            momentum_analysis['confirmed'],
            quality_analysis['passed'],
            rsi_analysis['acceptable']
        ]
        
        analysis['qualified'] = all(required_signals) and analysis['score'] >= self._parameters.get('min_qualified_score', 0.4)  # ML-configurable threshold
        
        if analysis['qualified']:
            self.logger.info(f"🎯 [ENTRY QUALIFIED] {symbol}: Score={analysis['score']:.2f} "
                           f"Dir={analysis['breakout_direction']} @ ${bar.close:.2f}")
        
        return analysis
    
    def _detect_price_breakout(self, symbol: str, bar: MarketData) -> Dict:
        """Detectar breakout de precio"""
        history = self.price_history[symbol]
        if len(history) < self.lookback_periods:
            return {'detected': False, 'direction': None, 'strength': 0.0}
        
        # Calcular máximos y mínimos recientes (excluyendo barra actual)
        recent_bars = list(history)[-self.lookback_periods:-1] if len(history) > 1 else list(history)
        
        if not recent_bars:
            return {'detected': False, 'direction': None, 'strength': 0.0}
        
        recent_highs = [b['high'] for b in recent_bars]
        recent_lows = [b['low'] for b in recent_bars]
        
        resistance_level = max(recent_highs)
        support_level = min(recent_lows)
        
        current_price = bar.close
        
        # Detectar breakout alcista - REQUIERE PULLBACK
        breakout_resistance = resistance_level * (1 + self.breakout_buffer)
        if current_price >= breakout_resistance:
            move_pct = (current_price - resistance_level) / resistance_level
            if self.min_breakout_move <= move_pct <= self.max_breakout_move:
                # NUEVA LÓGICA: Verificar que ha habido pullback después del breakout inicial
                pullback_valid = self._check_volume_breakout_pullback(symbol, bar, resistance_level)
                if not pullback_valid:
                    return {'detected': False, 'direction': 'long', 'strength': 0.0, 'waiting_pullback': True}
                
                strength = min(move_pct / self.min_breakout_move, 3.0) / 3.0  # Normalizar
                return {
                    'detected': True,
                    'direction': 'long',
                    'strength': strength,
                    'resistance_level': resistance_level,
                    'breakout_price': breakout_resistance,
                    'move_pct': move_pct * 100,
                    'pullback_confirmed': True
                }
        
        # Detectar breakout bajista
        breakout_support = support_level * (1 - self.breakout_buffer)
        if current_price <= breakout_support:
            move_pct = (support_level - current_price) / support_level
            if self.min_breakout_move <= move_pct <= self.max_breakout_move:
                strength = min(move_pct / self.min_breakout_move, 3.0) / 3.0
                return {
                    'detected': True,
                    'direction': 'short',
                    'strength': strength,
                    'support_level': support_level,
                    'breakout_price': breakout_support,
                    'move_pct': move_pct * 100
                }
        
        return {'detected': False, 'direction': None, 'strength': 0.0}
    
    def _analyze_volume_surge(self, symbol: str, bar: MarketData) -> Dict:
        """Analizar surge de volumen"""
        volume_data = self.volume_history[symbol]
        if len(volume_data) < self.volume_lookback:
            return {'surge_detected': False, 'strength': 0.0}
        
        # Calcular volumen promedio (excluyendo barra actual)
        recent_volumes = [v['volume'] for v in list(volume_data)[:-1]]
        if not recent_volumes:
            return {'surge_detected': False, 'strength': 0.0}
        
        avg_volume = sum(recent_volumes) / len(recent_volumes)
        current_volume = bar.volume
        
        # Verificar condiciones de volumen
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        conditions = {
            'ratio_ok': volume_ratio >= self.volume_multiplier,
            'absolute_ok': current_volume >= self.min_volume_threshold,
            'not_extreme': volume_ratio <= self.volume_spike_multiplier * 2  # Evitar manipulación
        }
        
        surge_detected = all(conditions.values())
        
        # Calcular strength
        if surge_detected:
            # Normalizar ratio a 0-1 scale
            normalized_ratio = min((volume_ratio - self.volume_multiplier) / 
                                 (self.volume_spike_multiplier - self.volume_multiplier), 1.0)
            strength = max(0.3, normalized_ratio)  # Mínimo 0.3 si califica
        else:
            strength = 0.0
        
        return {
            'surge_detected': surge_detected,
            'strength': strength,
            'volume_ratio': volume_ratio,
            'avg_volume': avg_volume,
            'current_volume': current_volume,
            'conditions': conditions
        }
    
    def _analyze_momentum(self, symbol: str, bar: MarketData, direction: str) -> Dict:
        """Analizar momentum en la dirección del breakout"""
        history = self.price_history[symbol]
        if len(history) < self.momentum_periods:
            return {'confirmed': False, 'strength': 0.0}
        
        # Obtener precios recientes
        recent_bars = list(history)[-self.momentum_periods:]
        if len(recent_bars) < 2:
            return {'confirmed': False, 'strength': 0.0}
        
        start_price = recent_bars[0]['close']
        current_price = bar.close
        
        price_change_pct = (current_price - start_price) / start_price
        
        if direction == 'long':
            momentum_confirmed = price_change_pct >= self.momentum_threshold
        else:  # short
            momentum_confirmed = price_change_pct <= -self.momentum_threshold
        
        # Calcular strength basado en la magnitud del momentum
        if momentum_confirmed:
            strength = min(abs(price_change_pct) / (self.momentum_threshold * 3), 1.0)
            strength = max(strength, 0.4)  # Mínimo si confirma
        else:
            strength = 0.0
        
        return {
            'confirmed': momentum_confirmed,
            'strength': strength,
            'price_change_pct': price_change_pct * 100,
            'periods_analyzed': len(recent_bars)
        }
    
    def _analyze_quality_filters(self, symbol: str, bar: MarketData) -> Dict:
        """Verificar filtros de calidad del símbolo"""
        price = bar.close
        
        conditions = {
            'price_range': self.min_price <= price <= self.max_price,
            'sufficient_movement': True,  # Calculado después si hay datos
            'valid_spread': True  # Podría implementarse con bid/ask si disponible
        }
        
        # Verificar movimiento suficiente si hay historial
        history = self.price_history[symbol]
        if len(history) >= 10:
            recent_prices = [b['close'] for b in list(history)[-10:]]
            price_range = max(recent_prices) - min(recent_prices)
            avg_price = sum(recent_prices) / len(recent_prices)
            
            if avg_price > 0:
                price_volatility = price_range / avg_price
                conditions['sufficient_movement'] = price_volatility >= self.min_price_change
        
        passed = all(conditions.values())
        strength = 1.0 if passed else 0.0
        
        return {
            'passed': passed,
            'strength': strength,
            'conditions': conditions,
            'price': price
        }
    
    def _analyze_rsi_filter(self, symbol: str, bar: MarketData, direction: str) -> Dict:
        """Filtro RSI para evitar extremos"""
        rsi = self._calculate_rsi(symbol, bar)
        
        if rsi is None:
            return {'acceptable': True, 'strength': 0.5, 'rsi': None}
        
        if direction == 'long':
            # Para long, evitar RSI muy alto
            acceptable = rsi <= self.rsi_overbought
            if acceptable:
                # Mejor strength si RSI está en rango medio-alto
                if 45 <= rsi <= 65:
                    strength = 1.0
                elif rsi <= 45:
                    strength = 0.7
                else:  # 65 < rsi <= 75
                    strength = 0.5
            else:
                strength = 0.0
        else:  # short
            # Para short, evitar RSI muy bajo
            acceptable = rsi >= self.rsi_oversold
            if acceptable:
                if 35 <= rsi <= 55:
                    strength = 1.0
                elif rsi >= 55:
                    strength = 0.7
                else:  # 25 <= rsi < 35
                    strength = 0.5
            else:
                strength = 0.0
        
        return {
            'acceptable': acceptable,
            'strength': strength,
            'rsi': rsi,
            'direction': direction
        }
    
    def _calculate_rsi(self, symbol: str, bar: MarketData) -> Optional[float]:
        """Calcular RSI usando el historial de precios"""
        history = self.price_history[symbol]
        if len(history) < self.rsi_periods + 1:
            return None
        
        # Obtener precios de cierre
        closes = [b['close'] for b in list(history)[-self.rsi_periods-1:]]
        
        # Calcular cambios de precio
        price_changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        
        # Separar gains y losses
        gains = [max(0, change) for change in price_changes]
        losses = [max(0, -change) for change in price_changes]
        
        # Calcular promedios
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _has_sufficient_data(self, symbol: str) -> bool:
        """Verificar si tenemos datos suficientes para analizar"""
        return (symbol in self.price_history and 
                len(self.price_history[symbol]) >= self.lookback_periods and
                symbol in self.volume_history and 
                len(self.volume_history[symbol]) >= self.volume_lookback)
    
    def _can_take_new_position(self, symbol: str, bar: MarketData) -> bool:
        """Verificar si podemos tomar nueva posición"""
        current_time = bar.timestamp
        current_date = current_time.date()
        
        # 1. Ya tiene posición
        if symbol in self.active_positions:
            return False
        
        # 2. Verificar horario de trading
        if not self._is_valid_trading_time(current_time):
            return False
        
        # 3. Cooldown period
        if symbol in self.last_trade_times:
            time_since_last = (current_time - self.last_trade_times[symbol]).total_seconds() / 60
            if time_since_last < self.cooldown_minutes:
                return False
        
        # 4. Límite de trades diarios
        daily_trades = self.daily_trades.get(current_date, 0)
        if daily_trades >= self.max_daily_trades:
            return False
        
        # 5. Límite de posiciones concurrentes
        if len(self.active_positions) >= self.max_concurrent_positions:
            return False
        
        # 6. Límite de pérdida diaria
        daily_pnl = self.daily_pnl.get(current_date, 0.0)
        if daily_pnl <= -self.daily_loss_limit:
            return False
        
        return True
    
    def _is_valid_trading_time(self, timestamp: datetime) -> bool:
        """Verificar horario válido de trading"""
        hour_decimal = timestamp.hour + timestamp.minute / 60.0
        
        # Verificar horario general
        if not (self.market_open_hour <= hour_decimal <= self.market_close_hour):
            return False
        
        # Evitar primeros minutos - convert to US Eastern timezone
        if timestamp.tzinfo is None:
            # If timestamp has no timezone, assume it's already US Eastern
            us_timestamp = timestamp.replace(tzinfo=ZoneInfo("America/New_York"))
        else:
            us_timestamp = timestamp.astimezone(ZoneInfo("America/New_York"))
        
        market_open_time = us_timestamp.replace(hour=9, minute=30, second=0, microsecond=0)
        avoid_until = market_open_time + timedelta(minutes=self.avoid_first_minutes)
        if us_timestamp < avoid_until:
            return False
        
        # Evitar últimos minutos
        market_close_time = us_timestamp.replace(hour=15, minute=30, second=0, microsecond=0)
        avoid_after = market_close_time - timedelta(minutes=self.avoid_last_minutes)
        if us_timestamp > avoid_after:
            return False
        
        return True
    
    async def _create_entry_signal(self, symbol: str, bar: MarketData, analysis: Dict) -> Signal:
        """Crear señal de entrada"""
        direction = analysis['breakout_direction']
        signal_type = SignalType.LONG if direction == 'long' else SignalType.SHORT
        
        # Calcular niveles de stop y target
        entry_price = bar.close
        
        if direction == 'long':
            stop_loss = entry_price * (1 - self.stop_loss_pct)
            take_profit = entry_price * (1 + self.take_profit_pct)
        else:
            stop_loss = entry_price * (1 + self.stop_loss_pct)
            take_profit = entry_price * (1 - self.take_profit_pct)
        
        # Registrar posición
        self.active_positions[symbol] = {
            'entry_price': entry_price,
            'entry_time': bar.timestamp,
            'direction': direction,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'original_take_profit': take_profit,  # TP inicial para referencia
            'highest_price': entry_price,
            'lowest_price': entry_price,
            'analysis': analysis,
            'partial_profit_taken': False,       # Control de ganancias parciales
            'last_tp_adjustment': 0.0,           # Último ajuste de TP
            'trailing_activated': False          # Control de trailing
        }
        
        # Actualizar tracking
        self._update_trade_tracking(symbol, bar.timestamp)
        
        self.logger.info(f"🚀 [ENTRY] {symbol}: {direction.upper()} @ ${entry_price:.2f} "
                        f"SL: ${stop_loss:.2f} TP: ${take_profit:.2f} "
                        f"Score: {analysis['score']:.2f}")
        
        return Signal(
            signal_id=f"entry_{symbol}_{bar.timestamp.strftime('%H%M%S%f')}",
            symbol=symbol,
            signal_type=signal_type,
            strength=analysis['strength'],
            price=entry_price,
            timestamp=bar.timestamp,
            strategy_name="Volume_Breakout",
            metadata={
                'strategy': 'VolumeBreakout',
                'direction': direction,
                'setup_type': 'breakout',
                'volume_ratio': analysis.get('volume_analysis', {}).get('ratio', 0),
                'momentum_strength': analysis.get('momentum_analysis', {}).get('strength', 0),
                'pattern': f"{direction}_breakout",
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'analysis_score': analysis['score'],
                'breakout_signals': analysis['signals'],
                'is_entry': True
            }
        )
    
    async def _check_exit_conditions(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """Verificar condiciones de salida con TRAILING STOP y TP MÓVIL mejorados"""
        if symbol not in self.active_positions:
            return None
        
        position = self.active_positions[symbol]
        entry_price = position['entry_price']
        current_price = bar.close
        direction = position['direction']
        
        # Actualizar precios extremos
        position['highest_price'] = max(position['highest_price'], current_price)
        position['lowest_price'] = min(position['lowest_price'], current_price)
        
        # Calcular PnL
        if direction == 'long':
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        exit_reason = None
        exit_type = 'full'  # 'full' o 'partial'
        
        # === 1. STOP LOSS BÁSICO ===
        if direction == 'long' and current_price <= position['stop_loss']:
            exit_reason = 'stop_loss'
        elif direction == 'short' and current_price >= position['stop_loss']:
            exit_reason = 'stop_loss'
        
        # === 2. GANANCIAS PARCIALES ===
        elif (self.partial_profit_enabled and not position['partial_profit_taken'] and 
              pnl_pct >= self.partial_profit_threshold):
            exit_reason = 'partial_profit'
            exit_type = 'partial'
            position['partial_profit_taken'] = True
            
            # Ajustar TP después de venta parcial (más conservador)
            if direction == 'long':
                position['take_profit'] = current_price * (1 + (self.take_profit_pct * 0.7))
            else:
                position['take_profit'] = current_price * (1 - (self.take_profit_pct * 0.7))
            
            self.logger.info(f"💰 [PARTIAL] {symbol}: Selling {self.partial_profit_size*100}% @ ${current_price:.2f} "
                           f"(+{pnl_pct*100:.1f}%) | New TP: ${position['take_profit']:.2f}")
        
        # === 3. TAKE PROFIT DINÁMICO ===
        elif self._check_dynamic_take_profit(position, current_price, pnl_pct):
            exit_reason = 'take_profit_dynamic'
        
        # === 4. TRAILING STOP AVANZADO ===
        elif self._check_advanced_trailing_stop(position, current_price, pnl_pct):
            exit_reason = 'trailing_stop'
        
        # === 5. TAKE PROFIT TRADICIONAL ===
        elif direction == 'long' and current_price >= position['take_profit']:
            exit_reason = 'take_profit'
        elif direction == 'short' and current_price <= position['take_profit']:
            exit_reason = 'take_profit'
        
        # === 6. TIME LIMIT ===
        time_held = (bar.timestamp - position['entry_time']).total_seconds() / 60
        if time_held >= self.max_hold_time:
            exit_reason = 'time_limit'
        
        # === 7. MARKET CLOSE === (convert to US Eastern)
        if bar.timestamp.tzinfo is None:
            us_bar_time = bar.timestamp.replace(tzinfo=ZoneInfo("America/New_York"))
        else:
            us_bar_time = bar.timestamp.astimezone(ZoneInfo("America/New_York"))
        
        if us_bar_time.hour >= 15 and us_bar_time.minute >= 25:
            exit_reason = 'market_close'
        
        if exit_reason:
            return self._create_exit_signal(symbol, bar, position, exit_reason, exit_type, pnl_pct)
        
        # === ACTUALIZAR TAKE PROFIT MÓVIL ===
        if self.dynamic_take_profit and not exit_reason:
            self._update_dynamic_take_profit(position, current_price, pnl_pct)
        
        return None
    
    def _check_dynamic_take_profit(self, position: Dict, current_price: float, pnl_pct: float) -> bool:
        """Verificar take profit dinámico basado en momentum sostenido"""
        if not self.dynamic_take_profit:
            return False
        
        direction = position['direction']
        
        # Para movimientos grandes (>8%), usar TP dinámico más flexible
        if pnl_pct >= 0.08:
            # Permitir que el precio caiga hasta 40% desde el máximo antes de vender
            if direction == 'long':
                peak_price = position['highest_price']
                dynamic_exit_price = peak_price * (1 - 0.04)  # 4% desde máximo
                return current_price <= dynamic_exit_price
            else:
                lowest_price = position['lowest_price']
                dynamic_exit_price = lowest_price * (1 + 0.04)
                return current_price >= dynamic_exit_price
        
        return False
    
    def _check_advanced_trailing_stop(self, position: Dict, current_price: float, pnl_pct: float) -> bool:
        """Sistema de trailing stop avanzado con múltiples niveles"""
        direction = position['direction']
        
        # Activar trailing si alcanzamos el threshold
        if pnl_pct >= self.trailing_activation:
            position['trailing_activated'] = True
        
        if not position.get('trailing_activated', False):
            return False
        
        # Determinar qué trailing usar basado en las ganancias
        if pnl_pct >= self.aggressive_trailing_threshold:
            # Trailing más agresivo para ganancias grandes
            trailing_distance = self.aggressive_trailing_pct
        else:
            # Trailing normal
            trailing_distance = self.trailing_stop_pct
        
        # Calcular precio de trailing stop
        if direction == 'long':
            trailing_stop_price = position['highest_price'] * (1 - trailing_distance)
            return current_price <= trailing_stop_price
        else:
            trailing_stop_price = position['lowest_price'] * (1 + trailing_distance)
            return current_price >= trailing_stop_price
    
    def _update_dynamic_take_profit(self, position: Dict, current_price: float, pnl_pct: float) -> None:
        """Actualizar take profit dinámicamente basado en el progreso"""
        if pnl_pct <= position.get('last_tp_adjustment', 0):
            return  # No hay nuevo progreso
        
        # Verificar si debemos mover el TP
        progress_since_last = pnl_pct - position.get('last_tp_adjustment', 0)
        
        if progress_since_last >= self.tp_step_size:
            direction = position['direction']
            
            # Calcular nuevo TP basado en el progreso
            additional_target = progress_since_last * self.tp_move_ratio
            
            if direction == 'long':
                new_tp = current_price * (1 + additional_target)
                # No exceder el TP máximo
                max_tp = position['entry_price'] * (1 + self.max_take_profit)
                position['take_profit'] = min(new_tp, max_tp)
            else:
                new_tp = current_price * (1 - additional_target)
                max_tp = position['entry_price'] * (1 - self.max_take_profit)
                position['take_profit'] = max(new_tp, max_tp)
            
            position['last_tp_adjustment'] = pnl_pct
            
            self.logger.info(f"📈 [TP MOVED] {position['symbol'] if 'symbol' in position else 'SYMBOL'}: "
                           f"New TP: ${position['take_profit']:.2f} "
                           f"(Progress: +{progress_since_last*100:.1f}%)")
    
    def _create_exit_signal(self, symbol: str, bar: MarketData, position: Dict, 
                           exit_reason: str, exit_type: str, pnl_pct: float) -> Signal:
        """Crear señal de salida con información detallada"""
        entry_price = position['entry_price']
        current_price = bar.close
        direction = position['direction']
        
        # Calcular P&L
        position_size = self._calculate_position_size(entry_price)
        
        # Ajustar position size para venta parcial
        if exit_type == 'partial':
            position_size = int(position_size * self.partial_profit_size)
        
        if direction == 'long':
            trade_pnl = position_size * (current_price - entry_price)
        else:
            trade_pnl = position_size * (entry_price - current_price)
        
        # Restar comisiones
        commission = max(position_size * self.commission_per_share, self.min_commission)
        trade_pnl -= commission * 2
        
        # Actualizar tracking solo para salidas completas
        if exit_type == 'full':
            is_winner = trade_pnl > 0
            self._update_exit_tracking(symbol, bar.timestamp, trade_pnl, is_winner)
            # Limpiar posición
            self.active_positions.pop(symbol, None)
        else:
            # Para venta parcial, solo log
            self.logger.info(f"💰 [PARTIAL EXIT] {symbol}: ${trade_pnl:.2f}")
        
        time_held = (bar.timestamp - position['entry_time']).total_seconds() / 60
        
        self.logger.info(f"📤 [EXIT-{exit_type.upper()}] {symbol}: {exit_reason} @ ${current_price:.2f} "
                       f"PnL: {pnl_pct*100:.1f}% (${trade_pnl:.2f}) | Held: {time_held:.0f}min")
        
        # Crear señal
        signal_type = SignalType.EXIT_LONG if direction == 'long' else SignalType.EXIT_SHORT
        
        return Signal(
            signal_id=f"exit_{symbol}_{bar.timestamp.strftime('%H%M%S%f')}",
            symbol=symbol,
            signal_type=signal_type,
            strength=1.0,
            price=current_price,
            timestamp=bar.timestamp,
            strategy_name="Volume_Breakout",
            metadata={
                'reason': exit_reason,
                'exit_type': exit_type,
                'pnl_pct': pnl_pct * 100,
                'pnl_dollars': trade_pnl,
                'entry_price': entry_price,
                'position_size': position_size,
                'time_held_minutes': time_held,
                'highest_price': position['highest_price'],
                'lowest_price': position['lowest_price'],
                'is_exit': True,
                'strategy': 'VolumeBreakout'
            }
        )
    
    def _calculate_position_size(self, price: float) -> int:
        """Calcular tamaño de posición"""
        try:
            if price <= 0:
                return 5
            
            # Valor base ajustado por volatilidad si está habilitado
            target_value = self.base_position_value
            
            if self.volatility_adjustment:
                # Ajustar por precio (stocks más baratos = posiciones más grandes)
                if price < 5:
                    target_value *= 1.3
                elif price > 20:
                    target_value *= 0.8
            
            # Calcular cantidad
            quantity = int(target_value / price)
            
            # Aplicar límites
            max_qty = int(self.max_position_value / price)
            min_qty = max(int(self.min_position_value / price), 5)
            
            quantity = max(min_qty, min(quantity, max_qty))
            
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 5
    
    def _update_trade_tracking(self, symbol: str, timestamp: datetime):
        """Actualizar tracking de trades"""
        date = timestamp.date()
        
        # Incrementar contador diario
        self.daily_trades[date] = self.daily_trades.get(date, 0) + 1
        
        # Actualizar último trade del símbolo
        self.last_trade_times[symbol] = timestamp
        
        self.logger.info(f"📊 [TRACKING] {symbol}: Daily trades = {self.daily_trades[date]}")
    
    def _update_exit_tracking(self, symbol: str, timestamp: datetime, pnl: float, is_winner: bool):
        """Actualizar tracking al salir"""
        date = timestamp.date()
        
        # Actualizar totales
        self.total_trades += 1
        self.total_pnl += pnl
        
        if is_winner:
            self.winning_trades += 1
        
        # Actualizar P&L diario
        self.daily_pnl[date] = self.daily_pnl.get(date, 0.0) + pnl
        
        # Métricas
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        avg_pnl = self.total_pnl / self.total_trades if self.total_trades > 0 else 0
        
        self.logger.info(f"📈 [METRICS] Total: {self.total_trades} | WR: {win_rate:.1f}% | "
                        f"AvgPnL: ${avg_pnl:.2f} | DailyPnL: ${self.daily_pnl[date]:.2f}")
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Interface pública para calcular position size
        
        Esta función es llamada por el TradingEngine para determinar el tamaño de la posición.
        Debe usar los parámetros proporcionados por el motor para integrarse correctamente con el RiskManager.
        """
        try:
            price = signal.price
            if price <= 0:
                self.logger.error(f"Invalid price for position sizing: {price}")
                return 0
            
            # Usar el capital y riesgo proporcionados por el motor de trading
            # en lugar de los valores internos de la estrategia
            target_value = capital * risk_per_trade
            
            # Aplicar ajustes de volatilidad si está habilitado
            if self.volatility_adjustment:
                # Ajustar por precio (stocks más baratos = posiciones más grandes)
                if price < 5:
                    target_value *= 1.3
                elif price > 20:
                    target_value *= 0.8
            
            # Calcular cantidad
            quantity = int(target_value / price)
            
            # Aplicar límites
            max_qty = int(self.max_position_value / price)
            min_qty = max(int(self.min_position_value / price), 5)
            
            quantity = max(min_qty, min(quantity, max_qty))
            
            self.logger.info(f"Calculated position size: {quantity} shares at ${price:.2f} (capital=${capital:.2f}, risk={risk_per_trade:.2%})")
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0
    
    def get_strategy_status(self) -> Dict:
        """Obtener estado actual de la estrategia"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            'name': self.name,
            'active_positions': len(self.active_positions),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': win_rate,
            'total_pnl': self.total_pnl,
            'positions': list(self.active_positions.keys()),
            'daily_trades': dict(self.daily_trades),
            'daily_pnl': dict(self.daily_pnl),
            'parameters': {
                'volume_multiplier': self.volume_multiplier,
                'breakout_buffer': self.breakout_buffer,
                'max_daily_trades': self.max_daily_trades,
                'max_concurrent_positions': self.max_concurrent_positions
            }
        }
    
    def _check_volume_breakout_pullback(self, symbol: str, bar: MarketData, resistance_level: float) -> bool:
        """Check if we should enter after a pullback from volume breakout"""
        try:
            history = self.price_history[symbol]
            if len(history) < 10:
                return False
            
            # Get recent bars
            recent_bars = list(history)[-8:]
            if not recent_bars:
                return False
            
            current_price = bar.close
            
            # Look for pullback pattern after breakout
            # 1. Must have had a high above resistance recently
            recent_highs = [b['high'] for b in recent_bars]
            highest_recent = max(recent_highs)
            
            if highest_recent <= resistance_level * 1.005:  # Must be above resistance
                return False
            
            # 2. Must have pulled back from that high
            recent_lows = [b['low'] for b in recent_bars[-3:]]  # Last 3 bars
            lowest_recent = min(recent_lows)
            
            pullback_pct = (highest_recent - lowest_recent) / highest_recent
            if pullback_pct < 0.008:  # At least 0.8% pullback
                return False
            
            # 3. Current price should be recovering (above recent low)
            if current_price <= lowest_recent * 1.003:  # Must be recovering
                return False
            
            # 4. Don't enter too far from resistance level
            if current_price > resistance_level * 1.06:  # No more than 6% above resistance
                return False
            
            self.logger.info(f"[{symbol}] Volume breakout pullback confirmed: Resistance={resistance_level:.2f}, High={highest_recent:.2f}, Low={lowest_recent:.2f}, Current={current_price:.2f}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking volume breakout pullback for {symbol}: {e}")
            return False
    
    def debug_symbol_analysis(self, symbol: str) -> Dict:
        """Debug análisis detallado de un símbolo"""
        debug_info = {
            "symbol": symbol,
            "has_position": symbol in self.active_positions,
            "data_status": {
                "price_history_bars": len(self.price_history.get(symbol, [])),
                "volume_history_bars": len(self.volume_history.get(symbol, [])),
                "sufficient_data": self._has_sufficient_data(symbol)
            },
            "recent_analysis": {}
        }
        
        if symbol in self.active_positions:
            position = self.active_positions[symbol]
            debug_info["current_position"] = {
                "direction": position['direction'],
                "entry_price": position['entry_price'],
                "entry_time": str(position['entry_time']),
                "stop_loss": position['stop_loss'],
                "take_profit": position['take_profit'],
                "highest_price": position['highest_price'],
                "lowest_price": position['lowest_price']
            }
        
        # Historial reciente si disponible
        if symbol in self.price_history:
            recent_bars = list(self.price_history[symbol])[-5:]
            debug_info["recent_price_data"] = [
                {
                    "timestamp": str(bar['timestamp']),
                    "high": bar['high'],
                    "low": bar['low'],
                    "close": bar['close'],
                    "volume": bar['volume']
                }
                for bar in recent_bars
            ]
        
        if symbol in self.volume_history:
            recent_volumes = list(self.volume_history[symbol])[-5:]
            debug_info["recent_volume_data"] = [
                {
                    "timestamp": str(vol['timestamp']),
                    "volume": vol['volume'],
                    "price": vol['price']
                }
                for vol in recent_volumes
            ]
        
        return debug_info
    
    async def force_analyze_symbol(self, symbol: str, bar: MarketData) -> Dict:
        """Forzar análisis completo de un símbolo (para testing)"""
        self.logger.info(f"🔍 [FORCE ANALYZE] {symbol} at {bar.timestamp}")
        
        # Actualizar historiales
        self._update_histories(symbol, bar)
        
        # Análisis completo
        analysis = await self._analyze_entry_opportunity(symbol, bar)
        
        # Información adicional
        debug_info = {
            "symbol": symbol,
            "timestamp": str(bar.timestamp),
            "price": bar.close,
            "volume": bar.volume,
            "can_take_position": self._can_take_new_position(symbol, bar),
            "trading_time_valid": self._is_valid_trading_time(bar.timestamp),
            "sufficient_data": self._has_sufficient_data(symbol),
            "analysis": analysis
        }
        
        # Breakout details si detectado
        if 'breakout' in analysis.get('signals', {}):
            breakout = analysis['signals']['breakout']
            if breakout.get('detected'):
                debug_info["breakout_details"] = breakout
        
        # Volume details
        if 'volume' in analysis.get('signals', {}):
            debug_info["volume_details"] = analysis['signals']['volume']
        
        return debug_info
    
    def reset_daily_limits(self):
        """Resetear límites diarios (útil para testing)"""
        # Use US Eastern timezone for proper trading day boundaries
        us_now = datetime.now(ZoneInfo("America/New_York"))
        today = us_now.date()
        self.daily_trades[today] = 0
        self.daily_pnl[today] = 0.0
        self.logger.info(f"🔄 Daily limits reset for {today}")
    
    def get_performance_summary(self) -> Dict:
        """Resumen de rendimiento"""
        if self.total_trades == 0:
            return {"message": "No trades executed yet"}
        
        win_rate = (self.winning_trades / self.total_trades) * 100
        avg_pnl = self.total_pnl / self.total_trades
        losing_trades = self.total_trades - self.winning_trades
        
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(self.total_pnl, 2),
            "average_pnl_per_trade": round(avg_pnl, 2),
            "active_positions": len(self.active_positions),
            "strategy_parameters": {
                "volume_multiplier": self.volume_multiplier,
                "breakout_buffer": self.breakout_buffer,
                "stop_loss_pct": self.stop_loss_pct,
                "take_profit_pct": self.take_profit_pct,
                "max_daily_trades": self.max_daily_trades
            }
        }
    
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For volume breakout strategy, we don't need special logic on position updates
        return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited with FOMO detection priority"""
        try:
            symbol = position.symbol
            current_price = current_bar.close
            
            # PRIORITY 1: Check FOMO exit first (overrides traditional exits)
            fomo_analysis = self.check_fomo_exit(symbol, position, current_bar)
            if fomo_analysis and fomo_analysis.get('should_exit', False):
                fomo_signal = fomo_analysis.get('fomo_signal')
                
                return Signal(
                    signal_id=f"fomo_exit_{symbol}_{int(current_bar.timestamp.timestamp())}",
                    symbol=symbol,
                    signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                    strength=fomo_signal.confidence,
                    price=current_price,
                    timestamp=current_bar.timestamp,
                    strategy_name="VolumeBreakout",
                    metadata={
                        'reason': 'fomo_top_detection',
                        'fomo_score': fomo_signal.fomo_score,
                        'urgency': fomo_signal.exit_urgency,
                        'fomo_reasons': fomo_signal.fomo_reasons,
                        'entry_price': position.avg_price,
                        'exit_type': 'FOMO_EXIT'
                    }
                )
            
            # PRIORITY 2: Traditional exits (if no FOMO exit)
            # Check if we have position info
            if symbol in self.active_positions:
                position_info = self.active_positions[symbol]
                entry_price = position_info.get('entry_price', position.avg_price)
                stop_loss = position_info.get('stop_loss')
                take_profit = position_info.get('take_profit')
                
                # Stop loss check
                if stop_loss and current_price <= stop_loss:
                    return Signal(
                        signal_id=f"exit_{symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                        strength=1.0,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="VolumeBreakout",
                        metadata={
                            'reason': 'stop_loss',
                            'entry_price': entry_price,
                            'stop_price': stop_loss
                        }
                    )
                
                # Take profit check
                if take_profit and current_price >= take_profit:
                    return Signal(
                        signal_id=f"exit_{symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                        strength=1.0,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="VolumeBreakout",
                        metadata={
                            'reason': 'take_profit',
                            'entry_price': entry_price,
                            'target_price': take_profit
                        }
                    )
            
            # Fallback: Basic stop loss if no position info
            if position.quantity > 0:  # Long position
                stop_loss_pct = self.stop_loss_pct
                stop_price = position.avg_price * (1 - stop_loss_pct)
                
                if current_price <= stop_price:
                    return Signal(
                        signal_id=f"exit_{symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="VolumeBreakout",
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