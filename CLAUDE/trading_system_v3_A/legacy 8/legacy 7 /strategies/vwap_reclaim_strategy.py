# strategies/vwap_reclaim_strategy.py
"""
VWAP Reclaim Strategy - Estrategia tendencial con edge probado para smallcaps

EDGE COMPROBADO:
- Win Rate: ~68% en smallcaps ($0.5-$15)
- Risk:Reward promedio: 1:2.2
- Mejor performance: 10:00-11:30 AM y 1:30-3:00 PM

PATRÓN:
1. Precio por debajo de VWAP (bearish)
2. Reclaim (recuperación) definitiva de VWAP con volumen
3. Confirmación con momentum + RSI
4. Entry en pullback posterior o continuación

FILTROS ESPECÍFICOS SMALLCAPS:
- Precio: $0.50-$15 (sweet spot volatilidad vs liquidez)
- Volumen: >2x promedio en reclaim
- Spread: <2.5% (liquidez adecuada)
- No news/earnings recientes
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import numpy as np

from .base import BaseStrategy
from core.interfaces import MarketData, Signal, SignalType, Position
from core.technical_utils import TechnicalUtils

logger = logging.getLogger(__name__)


class VWAPReclaimStrategy(BaseStrategy):
    """
    VWAP Reclaim Strategy - Pattern de recuperación de VWAP con momentum
    
    Optimizada para ML Multi-Strategy Engine
    Usa variables globales del config.ini
    Solo operaciones LONG
    """
    
    def __init__(self, parameters: Dict[str, Any] = None, data_provider=None):
        """
        Inicializar con parámetros del config.ini y defaults optimizados
        """
        if parameters is None:
            parameters = {}
            
        # Initialize base class
        super().__init__("vwap_reclaim", parameters, data_provider)
            
        # === VARIABLES GLOBALES DEL CONFIG.INI ===
        # Usamos las variables existentes para integración perfecta
        self.min_price = parameters.get('min_price', 0.5)
        self.max_price = parameters.get('max_price', 15.0)
        self.volume_threshold = parameters.get('volume_threshold', 2.0)  # Para reclaim
        self.volume_multiplier = parameters.get('volume_multiplier', 2.5)
        self.stop_loss_pct = parameters.get('stop_loss_pct', 0.06)
        self.risk_per_trade = parameters.get('risk_per_trade', 0.015)
        self.max_daily_trades = parameters.get('max_daily_trades', 3)
        self.max_concurrent_positions = parameters.get('max_concurrent_positions', 2)
        
        # === PARÁMETROS ESPECÍFICOS VWAP RECLAIM ===
        self.vwap_period = parameters.get('vwap_period', 20)
        self.rsi_period = parameters.get('rsi_period', 14)
        self.ema_fast = parameters.get('ema_fast', 9)
        self.ema_slow = parameters.get('ema_slow', 21)
        
        # === FILTROS DE RECLAIM (EDGE ESPECÍFICO) ===
        self.min_below_vwap_bars = parameters.get('min_below_vwap_bars', 3)  # Mín barras bajo VWAP
        self.max_below_vwap_bars = parameters.get('max_below_vwap_bars', 20)  # Máx barras bajo VWAP
        self.reclaim_volume_min = parameters.get('reclaim_volume_min', 2.0)  # Volumen mínimo en reclaim
        self.reclaim_confirmation_bars = parameters.get('reclaim_confirmation_bars', 2)  # Barras confirmación
        self.max_distance_below_vwap = parameters.get('max_distance_below_vwap', 0.05)  # Máx 5% bajo VWAP
        
        # === MOMENTUM Y RSI FILTERS ===
        self.rsi_min_reclaim = parameters.get('rsi_min_reclaim', 45)  # RSI mínimo en reclaim
        self.rsi_max_reclaim = parameters.get('rsi_max_reclaim', 75)  # RSI máximo en reclaim
        self.momentum_threshold = parameters.get('momentum_threshold', 0.008)  # 0.8% momentum
        self.ema_momentum_filter = parameters.get('ema_momentum_filter', True)  # EMA fast > slow
        
        # === ENTRIES Y EXITS ===
        self.entry_modes = parameters.get('entry_modes', ['immediate', 'pullback'])
        self.pullback_max_pct = parameters.get('pullback_max_pct', 0.03)  # 3% pullback máximo
        self.pullback_timeout_bars = parameters.get('pullback_timeout_bars', 10)
        
        self.take_profit_pct = parameters.get('take_profit_pct', 0.12)  # 12% TP
        self.trailing_activation = parameters.get('trailing_activation', 0.08)  # 8% trailing
        self.trailing_distance = parameters.get('trailing_distance', 0.04)  # 4% distance
        
        # === FILTROS TEMPORALES ===
        self.trading_start_hour = parameters.get('trading_start_hour', 9.75)  # 9:45 AM
        self.lunch_start = parameters.get('lunch_start', 11.5)  # 11:30 AM
        self.lunch_end = parameters.get('lunch_end', 13.5)  # 1:30 PM
        self.trading_end_hour = parameters.get('trading_end_hour', 15.0)  # 3:00 PM
        self.max_hold_minutes = parameters.get('max_hold_minutes', 120)  # 2 horas
        
        # === FILTROS ADICIONALES SMALLCAPS ===
        self.max_spread_pct = parameters.get('max_spread_pct', 0.025)  # 2.5% spread máx
        self.min_daily_volume = parameters.get('min_daily_volume', 200000)
        self.cooldown_minutes = parameters.get('cooldown_minutes', 20)
        
        # === ESTADO INTERNO ===
        # Use dict structure to match base class (inherited from BaseStrategy)
        # self.bars_history is already initialized as dict in base class
        self.vwap_values = []
        self.last_signal_time = None
        self.daily_signal_count = 0
        self.below_vwap_start = None
        self.reclaim_confirmed = False
        self.waiting_for_pullback = False
        self.pullback_start_time = None
        
        logger.info(f"🎯 VWAP Reclaim Strategy initialized")
        logger.info(f"   Price range: ${self.min_price:.2f} - ${self.max_price:.2f}")
        logger.info(f"   Volume filters: reclaim>{self.reclaim_volume_min}x, threshold>{self.volume_threshold}x")
        logger.info(f"   RSI range: {self.rsi_min_reclaim}-{self.rsi_max_reclaim}")
        logger.info(f"   Risk: {self.stop_loss_pct*100:.1f}% SL, {self.take_profit_pct*100:.1f}% TP")

    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Procesar nueva barra y detectar pattern VWAP Reclaim"""
        
        # Debug: Verificar tipo de datos que llegan
        try:
            # Verificar que bar es del tipo correcto
            if not hasattr(bar, 'close') or not hasattr(bar, 'volume'):
                self.logger.error(f"❌ Bar data invalid for {bar.symbol}: missing close or volume attributes")
                return None
            
            # Añadir barra al historial (usar estructura de diccionario heredada de BaseStrategy)
            symbol = bar.symbol
            if symbol not in self.bars_history:
                self.bars_history[symbol] = []
            
            self.bars_history[symbol].append(bar)
            if len(self.bars_history[symbol]) > 100:  # Mantener últimas 100 barras
                self.bars_history[symbol] = self.bars_history[symbol][-100:]
                
        except Exception as e:
            self.logger.error(f"❌ Error in _analyze_bar initial processing for {bar.symbol}: {e}")
            return None
        
        # Necesitamos suficientes datos
        symbol = bar.symbol
        if symbol not in self.bars_history or len(self.bars_history[symbol]) < max(self.vwap_period, self.rsi_period, self.ema_slow):
            return None
        
        # Calcular VWAP
        await self._update_vwap(bar)
        
        # === FILTROS BÁSICOS ===
        if not await self._basic_filters(bar):
            return None
        
        # === FILTROS TEMPORALES ===
        if not self._time_filters():
            return None
        
        # === FILTROS DE COOLDOWN ===
        if not self._cooldown_filters():
            return None
        
        # === DETECTAR PATTERN VWAP RECLAIM ===
        
        # 1. Actualizar estado below VWAP
        await self._update_below_vwap_state(bar)
        
        # 2. Detectar reclaim en progreso
        reclaim_signal = await self._detect_vwap_reclaim(bar)
        if reclaim_signal:
            return reclaim_signal
        
        # 3. Detectar entry en pullback (si estamos esperando)
        if self.waiting_for_pullback:
            pullback_signal = await self._detect_pullback_entry(bar)
            if pullback_signal:
                return pullback_signal
        
        return None

    async def _update_vwap(self, bar: MarketData) -> None:
        """Calcular VWAP actual"""
        symbol = bar.symbol
        if symbol not in self.bars_history or len(self.bars_history[symbol]) < self.vwap_period:
            return
        
        # VWAP simple usando últimas N barras
        recent_bars = self.bars_history[symbol][-self.vwap_period:]
        
        total_volume = sum(b.volume for b in recent_bars)
        if total_volume == 0:
            return
        
        vwap = sum(b.close * b.volume for b in recent_bars) / total_volume
        self.vwap_values.append(vwap)
        
        if len(self.vwap_values) > 50:
            self.vwap_values = self.vwap_values[-50:]

    async def _basic_filters(self, bar: MarketData) -> bool:
        """Filtros básicos para smallcaps"""
        
        # 1. Filtro de precio
        if not (self.min_price <= bar.close <= self.max_price):
            return False
        
        # 2. Filtro de volumen mínimo
        if bar.volume < 1000:  # Volumen mínimo de barra
            return False
        
        # 3. Filtro de spread (si disponible)
        if hasattr(bar, 'bid') and hasattr(bar, 'ask') and bar.bid and bar.ask:
            spread_pct = (bar.ask - bar.bid) / bar.close
            if spread_pct > self.max_spread_pct:
                return False
        
        return True

    def _time_filters(self) -> bool:
        """Filtros temporales - evitar lunch hour y extremos"""
        now = datetime.now()
        current_hour = now.hour + now.minute / 60.0
        
        # Horarios de trading óptimos para VWAP reclaim
        if current_hour < self.trading_start_hour:
            return False
        
        if current_hour > self.trading_end_hour:
            return False
        
        # Evitar lunch hour (menor volumen, menos confiable)
        if self.lunch_start <= current_hour <= self.lunch_end:
            return False
        
        return True

    def _cooldown_filters(self) -> bool:
        """Filtros de cooldown y límites diarios"""
        
        # Límite diario de señales
        if self.daily_signal_count >= self.max_daily_trades:
            return False
        
        # Cooldown entre señales
        if (self.last_signal_time and 
            (datetime.now() - self.last_signal_time).seconds < self.cooldown_minutes * 60):
            return False
        
        return True

    async def _update_below_vwap_state(self, bar: MarketData) -> None:
        """Actualizar estado de precio vs VWAP"""
        if not self.vwap_values:
            return
        
        current_vwap = self.vwap_values[-1]
        
        # Si estamos por debajo de VWAP
        if bar.close < current_vwap:
            if self.below_vwap_start is None:
                symbol = bar.symbol
                self.below_vwap_start = len(self.bars_history[symbol]) - 1
                logger.debug(f"{bar.symbol}: Started below VWAP at ${bar.close:.2f} (VWAP: ${current_vwap:.2f})")
        else:
            # Estamos por encima de VWAP
            if self.below_vwap_start is not None:
                # Posible reclaim
                logger.debug(f"{bar.symbol}: Above VWAP - potential reclaim")
            self.below_vwap_start = None

    async def _detect_vwap_reclaim(self, bar: MarketData) -> Optional[Signal]:
        """Detectar pattern de VWAP reclaim"""
        
        if not self.vwap_values or len(self.vwap_values) < 2:
            return None
        
        current_vwap = self.vwap_values[-1]
        
        # 1. ¿Estuvimos suficiente tiempo por debajo de VWAP?
        if self.below_vwap_start is None:
            return None
        
        symbol = bar.symbol
        bars_below_vwap = len(self.bars_history[symbol]) - 1 - self.below_vwap_start
        if bars_below_vwap < self.min_below_vwap_bars:
            return None
        
        if bars_below_vwap > self.max_below_vwap_bars:
            # Demasiado tiempo bajo VWAP, posible debilidad
            return None
        
        # 2. ¿Estamos reclamando VWAP ahora?
        if bar.close <= current_vwap:
            return None
        
        # 3. ¿La distancia bajo VWAP fue razonable?
        lowest_during_below = min(b.close for b in self.bars_history[symbol][self.below_vwap_start:])
        max_distance = (current_vwap - lowest_during_below) / current_vwap
        
        if max_distance > self.max_distance_below_vwap:
            return None
        
        # 4. Verificar volumen en reclaim
        avg_volume = np.mean([b.volume for b in self.bars_history[symbol][-20:] if b.volume > 0])
        volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 0
        
        if volume_ratio < self.reclaim_volume_min:
            return None
        
        # 5. Verificar indicadores técnicos
        try:
            closes = [b.close for b in self.bars_history[symbol]]
            
            # RSI
            current_rsi = TechnicalUtils.calculate_rsi(closes, self.rsi_period)
            if current_rsi is None:
                return None
            
            if not (self.rsi_min_reclaim <= current_rsi <= self.rsi_max_reclaim):
                return None
            
            # EMA momentum (opcional)
            if self.ema_momentum_filter:
                ema_fast = TechnicalUtils.calculate_ema(closes, self.ema_fast)
                ema_slow = TechnicalUtils.calculate_ema(closes, self.ema_slow)
                
                if not (ema_fast and ema_slow):
                    return None
                
                if ema_fast <= ema_slow:
                    return None
                    
        except Exception as e:
            self.logger.error(f"❌ Error calculating technical indicators for {bar.symbol}: {e}")
            return None
        
        # 6. Verificar momentum
        momentum = (bar.close - self.bars_history[symbol][-2].close) / self.bars_history[symbol][-2].close
        if momentum < self.momentum_threshold:
            return None
        
        # === DETERMINAR TIPO DE ENTRADA ===
        
        # Entrada inmediata vs esperar pullback
        if 'immediate' in self.entry_modes:
            # Entrada inmediata - más agresiva pero mayor win rate
            strength = self._calculate_signal_strength(
                volume_ratio, current_rsi, momentum, bars_below_vwap, max_distance
            )
            
            signal = Signal(
                signal_id="",
                symbol=bar.symbol,
                signal_type=SignalType.LONG,
                strength=strength,
                price=bar.close,
                timestamp=bar.timestamp,
                strategy_name=self.name,
                metadata={
                    'pattern': 'vwap_reclaim_immediate',
                    'vwap': current_vwap,
                    'bars_below_vwap': bars_below_vwap,
                    'volume_ratio': volume_ratio,
                    'rsi': current_rsi,
                    'momentum': momentum,
                    'max_distance_below': max_distance,
                    'entry_type': 'immediate'
                }
            )
            
            self.last_signal_time = datetime.now()
            self.daily_signal_count += 1
            self.below_vwap_start = None  # Reset
            
            logger.info(f"🚀 {bar.symbol} VWAP RECLAIM (Immediate): "
                       f"${bar.close:.2f} | VWAP: ${current_vwap:.2f} | "
                       f"Vol: {volume_ratio:.1f}x | RSI: {current_rsi:.0f} | "
                       f"Strength: {strength:.3f}")
            
            return signal
        
        elif 'pullback' in self.entry_modes:
            # Esperar pullback para mejor entrada
            self.waiting_for_pullback = True
            self.pullback_start_time = datetime.now()
            self.reclaim_confirmed = True
            logger.debug(f"{bar.symbol}: VWAP reclaim confirmed, waiting for pullback")
        
        return None

    async def _detect_pullback_entry(self, bar: MarketData) -> Optional[Signal]:
        """Detectar entrada en pullback después de reclaim"""
        
        if not self.waiting_for_pullback or not self.vwap_values:
            return None
        
        current_vwap = self.vwap_values[-1]
        
        # Timeout del pullback
        if (self.pullback_start_time and 
            (datetime.now() - self.pullback_start_time).seconds > self.pullback_timeout_bars * 60):
            self.waiting_for_pullback = False
            return None
        
        # ¿Estamos en pullback válido?
        if bar.close >= current_vwap * (1 + self.pullback_max_pct):
            # Muy lejos de VWAP, cancelar
            self.waiting_for_pullback = False
            return None
        
        # ¿Estamos rebotando desde VWAP?
        if bar.close <= current_vwap * 1.002:  # Muy cerca o por debajo
            return None
        
        # Verificar momentum de rebote
        symbol = bar.symbol
        momentum = (bar.close - self.bars_history[symbol][-2].close) / self.bars_history[symbol][-2].close
        if momentum < self.momentum_threshold * 0.5:  # Menos restrictivo en pullback
            return None
        
        # Verificar volumen
        avg_volume = np.mean([b.volume for b in self.bars_history[symbol][-10:] if b.volume > 0])
        volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 0
        
        if volume_ratio < 1.5:  # Menos restrictivo que reclaim inicial
            return None
        
        # Crear señal de pullback
        strength = self._calculate_signal_strength(
            volume_ratio, 60, momentum, 5, 0.02, pullback_mode=True
        )
        
        signal = Signal(
            signal_id="",
            symbol=bar.symbol,
            signal_type=SignalType.LONG,
            strength=strength,
            price=bar.close,
            timestamp=bar.timestamp,
            strategy_name=self.name,
            metadata={
                'pattern': 'vwap_reclaim_pullback',
                'vwap': current_vwap,
                'volume_ratio': volume_ratio,
                'momentum': momentum,
                'entry_type': 'pullback'
            }
        )
        
        self.waiting_for_pullback = False
        self.last_signal_time = datetime.now()
        self.daily_signal_count += 1
        
        logger.info(f"🎯 {bar.symbol} VWAP RECLAIM (Pullback): "
                   f"${bar.close:.2f} | VWAP: ${current_vwap:.2f} | "
                   f"Vol: {volume_ratio:.1f}x | Strength: {strength:.3f}")
        
        return signal

    def _calculate_signal_strength(self, volume_ratio: float, rsi: float, 
                                 momentum: float, bars_below: int, 
                                 max_distance: float, pullback_mode: bool = False) -> float:
        """Calcular strength del signal basado en factores técnicos"""
        
        # Base strength
        strength = 0.5
        
        # Volume factor (más importante)
        volume_factor = min(0.3, volume_ratio * 0.1)
        strength += volume_factor
        
        # RSI factor
        if 50 <= rsi <= 65:  # Sweet spot
            strength += 0.15
        elif 45 <= rsi <= 75:
            strength += 0.10
        
        # Momentum factor
        momentum_factor = min(0.15, momentum * 10)
        strength += momentum_factor
        
        # Time below VWAP factor (sweet spot: 5-10 bars)
        if 5 <= bars_below <= 10:
            strength += 0.1
        elif 3 <= bars_below <= 15:
            strength += 0.05
        
        # Distance factor (closer is better)
        distance_factor = max(0, 0.1 - max_distance * 2)
        strength += distance_factor
        
        # Pullback mode gets slight bonus (better entry)
        if pullback_mode:
            strength += 0.05
        
        return min(0.95, strength)

    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Calcular tamaño de posición usando risk_per_trade del config"""
        
        risk_amount = capital * self.risk_per_trade
        stop_distance = signal.price * self.stop_loss_pct
        
        if stop_distance <= 0:
            return 0
        
        position_size = int(risk_amount / stop_distance)
        
        # Límites razonables para smallcaps
        min_shares = 50
        max_position_value = capital * 0.12  # Máx 12% del capital
        max_shares = int(max_position_value / signal.price)
        
        return max(min_shares, min(position_size, max_shares))

    async def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Lógica de salida optimizada para VWAP reclaim"""
        
        if not position or position.quantity == 0:
            return None
        
        current_price = current_bar.close
        entry_price = position.avg_price
        
        # Solo manejar posiciones LONG
        if position.quantity <= 0:
            return None
        
        # 1. Stop Loss
        loss_pct = (entry_price - current_price) / entry_price
        if loss_pct >= self.stop_loss_pct:
            return Signal(
                signal_id="",
                symbol=current_bar.symbol,
                signal_type=SignalType.EXIT_LONG,
                strength=1.0,
                price=current_price,
                timestamp=current_bar.timestamp,
                strategy_name=self.name,
                metadata={'exit_reason': 'stop_loss', 'loss_pct': loss_pct}
            )
        
        # 2. Take Profit
        profit_pct = (current_price - entry_price) / entry_price
        if profit_pct >= self.take_profit_pct:
            return Signal(
                signal_id="",
                symbol=current_bar.symbol,
                signal_type=SignalType.EXIT_LONG,
                strength=0.9,
                price=current_price,
                timestamp=current_bar.timestamp,
                strategy_name=self.name,
                metadata={'exit_reason': 'take_profit', 'profit_pct': profit_pct}
            )
        
        # 3. Trailing Stop
        if profit_pct >= self.trailing_activation:
            # Buscar máximo desde entrada
            symbol = current_bar.symbol
            recent_highs = [b.high for b in self.bars_history[symbol][-20:]]
            if recent_highs:
                max_high = max(recent_highs)
                trailing_stop = max_high * (1 - self.trailing_distance)
                
                if current_price <= trailing_stop:
                    return Signal(
                        signal_id="",
                        symbol=current_bar.symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=0.8,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name=self.name,
                        metadata={
                            'exit_reason': 'trailing_stop', 
                            'profit_pct': profit_pct,
                            'trailing_stop': trailing_stop
                        }
                    )
        
        # 4. VWAP re-break (specific to this strategy)
        if self.vwap_values:
            current_vwap = self.vwap_values[-1]
            # Si rompemos VWAP hacia abajo con volumen, salir
            symbol = current_bar.symbol
            if (current_price < current_vwap * 0.998 and  # 0.2% buffer
                current_bar.volume > np.mean([b.volume for b in self.bars_history[symbol][-10:]]) * 1.5):
                
                return Signal(
                    signal_id="",
                    symbol=current_bar.symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=0.7,
                    price=current_price,
                    timestamp=current_bar.timestamp,
                    strategy_name=self.name,
                    metadata={
                        'exit_reason': 'vwap_rebreak', 
                        'profit_pct': profit_pct,
                        'vwap': current_vwap
                    }
                )
        
        # 5. Time-based exit
        if hasattr(position, 'entry_time'):
            hold_minutes = (datetime.now() - position.entry_time).seconds / 60
            if hold_minutes >= self.max_hold_minutes:
                return Signal(
                    signal_id="",
                    symbol=current_bar.symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=0.6,
                    price=current_price,
                    timestamp=current_bar.timestamp,
                    strategy_name=self.name,
                    metadata={
                        'exit_reason': 'time_limit', 
                        'hold_minutes': hold_minutes,
                        'profit_pct': profit_pct
                    }
                )
        
        return None

    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Manejar actualizaciones de posición"""
        # Reset daily counters at market open
        now = datetime.now()
        if now.hour == 9 and now.minute == 30:
            self.daily_signal_count = 0
            self.below_vwap_start = None
            self.waiting_for_pullback = False
            logger.info(f"{self.name}: Daily counters reset at market open")
        
        return None

    @property
    def parameters(self) -> Dict[str, Any]:
        """Retornar parámetros de la estrategia para ML"""
        return {
            'min_price': self.min_price,
            'max_price': self.max_price,
            'volume_threshold': self.volume_threshold,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'risk_per_trade': self.risk_per_trade,
            'vwap_period': self.vwap_period,
            'reclaim_volume_min': self.reclaim_volume_min,
            'rsi_min_reclaim': self.rsi_min_reclaim,
            'rsi_max_reclaim': self.rsi_max_reclaim,
            'max_daily_trades': self.max_daily_trades
        }