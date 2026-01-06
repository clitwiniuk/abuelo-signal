#!/usr/bin/env python3
"""
Volume Explosion Pullback Strategy
==================================

Estrategia simple y efectiva para smallcaps:
1. Detectar explosión de volumen + movimiento de precio
2. Esperar retroceso/pullback (evita slippage)
3. Entrar en pullback con confirmación de volumen
4. Dejar que el sistema centralizado maneje todas las salidas

VENTAJAS:
- Solo 3 condiciones simples
- Evita slippage al no entrar en breakout
- Mejor risk/reward al entrar en pullback
- Sistema centralizado maneja stops/profits
- Específicamente diseñada para datos de explosiones de volumen
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np

from core.interfaces import IStrategy, Signal, SignalType, Position, MarketData
from .base import BaseStrategy


class VolumeExplosionPullbackStrategy(BaseStrategy):
    """
    Estrategia simple de explosión de volumen con entrada en pullback
    
    FILOSOFÍA: 
    - Volumen = Smart Money
    - Explosión + Pullback = Oportunidad con menos riesgo
    - Simple = Menos errores
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # Initialize with name
        self._name = "VolumeExplosionPullback"
        self.logger = logging.getLogger(f"Strategy.{self._name}")
        
        # Parámetros SUPER SIMPLES
        default_params = {
            # Detección de explosión
            'volume_explosion_threshold': 2.5,    # 2.5x volumen para detectar explosión
            'price_move_threshold': 0.015,        # 1.5% movimiento mínimo para explosión
            
            # Entrada en pullback
            'pullback_entry_pct': 0.97,           # Entrar 3% debajo del high de explosión
            'volume_confirmation': 1.8,           # 1.8x volumen para confirmar entrada
            'max_wait_minutes': 45,               # Máximo esperar 45min para pullback
            
            # Configuración básica
            'volume_lookback': 10,                # Barras para promedio de volumen
            'min_history_bars': 15,               # Mínimo barras necesarias
            'max_position_value': 500.0,          # Tamaño máximo posición
            
            # Control de operativa
            'cooldown_minutes': 10,               # 10min cooldown entre señales del mismo símbolo
            'max_daily_signals': 8,               # Máximo 8 señales por día
            
            # Horarios (permisivo para explosiones)
            'enable_premarket': False,            # Solo regular hours para simplicidad
            'enable_afterhours': False,
            'start_hour': 9.5,                    # 9:30 AM
            'end_hour': 15.5,                     # 3:30 PM (evitar último 30min)
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__("VolumeExplosionPullback", default_params)
        
        # Estado interno MÍNIMO
        self.bars_history: Dict[str, List[MarketData]] = {}
        self.explosion_radar: Dict[str, Dict] = {}  # Símbolos en radar para pullback
        self.last_signal_time: Dict[str, datetime] = {}
        self.daily_signals_count = 0
        self.last_date = None
        
        self.logger.info("🎯 Volume Explosion Pullback Strategy initialized - hunting pullbacks after explosions!")
    
    async def _initialize_strategy(self) -> None:
        """Initialize strategy - required by BaseStrategy"""
        self.logger.info("🚀 Initializing Volume Explosion Pullback Strategy")
        self.logger.info(f"💥 Volume explosion threshold: {self._parameters['volume_explosion_threshold']:.1f}x")
        self.logger.info(f"📈 Price movement threshold: {self._parameters['price_move_threshold']:.1f}%")
        self.logger.info(f"🎯 Pullback entry: {(1-self._parameters['pullback_entry_pct'])*100:.1f}% below high")
        self.logger.info(f"✅ Volume confirmation: {self._parameters['volume_confirmation']:.1f}x")
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar - required by BaseStrategy (delegates to on_bar)"""
        return await self.on_bar(bar)
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """Procesar nueva barra con lógica SUPER SIMPLE"""
        
        symbol = bar.symbol
        
        # Reset contador diario
        self._reset_daily_counter(bar.timestamp)
        
        # Limitar señales diarias
        if self.daily_signals_count >= self._parameters['max_daily_signals']:
            return None
        
        # Solo horario regular
        if not self._is_trading_hours(bar.timestamp):
            return None
        
        # Mantener historial de barras
        self._update_bars_history(bar)
        
        # Necesitamos historial mínimo
        if len(self.bars_history.get(symbol, [])) < self._parameters['min_history_bars']:
            return None
        
        # Cooldown entre señales del mismo símbolo
        if self._is_in_cooldown(symbol, bar.timestamp):
            return None
        
        # PASO 1: Detectar nueva explosión de volumen
        self._detect_volume_explosion(bar)
        
        # PASO 2: Buscar entrada en pullback
        return self._check_pullback_entry(bar)
    
    def _detect_volume_explosion(self, bar: MarketData) -> None:
        """PASO 1: Detectar explosión de volumen"""
        
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        if len(bars) < self._parameters['volume_lookback'] + 1:
            return
        
        # Calcular volumen promedio (excluyendo barra actual)
        volume_history = [b.volume for b in bars[:-1]]  # Sin la barra actual
        avg_volume = np.mean(volume_history[-self._parameters['volume_lookback']:])
        
        if avg_volume <= 0:
            return
        
        # Ratio de volumen actual
        volume_ratio = bar.volume / avg_volume
        
        # Movimiento de precio vs barra anterior
        prev_close = bars[-2].close if len(bars) > 1 else bar.close
        price_change_pct = (bar.close - prev_close) / prev_close
        
        # CONDICIÓN DE EXPLOSIÓN: Volumen alto + Movimiento significativo
        explosion_detected = (
            volume_ratio >= self._parameters['volume_explosion_threshold'] and
            abs(price_change_pct) >= self._parameters['price_move_threshold']
        )
        
        if explosion_detected:
            # Agregar al radar para pullback
            self.explosion_radar[symbol] = {
                'explosion_time': bar.timestamp,
                'explosion_high': bar.high,
                'explosion_close': bar.close,
                'explosion_volume_ratio': volume_ratio,
                'price_movement': price_change_pct,
                'direction': 'bullish' if price_change_pct > 0 else 'bearish'
            }
            
            self.logger.info(
                f"💥 EXPLOSION DETECTED: {symbol} | "
                f"Volume: {volume_ratio:.1f}x | "
                f"Move: {price_change_pct:+.2%} | "
                f"Direction: {self.explosion_radar[symbol]['direction']}"
            )
    
    def _check_pullback_entry(self, bar: MarketData) -> Optional[Signal]:
        """PASO 2: Buscar entrada en pullback"""
        
        symbol = bar.symbol
        
        # No hay explosión en radar
        if symbol not in self.explosion_radar:
            return None
        
        explosion_data = self.explosion_radar[symbol]
        
        # Timeout: Explosión muy antigua
        time_since_explosion = bar.timestamp - explosion_data['explosion_time']
        if time_since_explosion.total_seconds() / 60 > self._parameters['max_wait_minutes']:
            # Remover del radar
            del self.explosion_radar[symbol]
            return None
        
        # Solo operamos bullish explosions para simplicidad
        if explosion_data['direction'] != 'bullish':
            return None
        
        # CONDICIÓN DE PULLBACK: Precio por debajo del high de explosión
        explosion_high = explosion_data['explosion_high']
        pullback_threshold = explosion_high * self._parameters['pullback_entry_pct']
        
        if bar.close > pullback_threshold:
            # Aún no hay pullback suficiente
            return None
        
        # CONDICIÓN DE CONFIRMACIÓN: Aún hay volumen
        bars = self.bars_history[symbol]
        volume_history = [b.volume for b in bars[:-1]]
        avg_volume = np.mean(volume_history[-self._parameters['volume_lookback']:])
        
        current_volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 0
        
        if current_volume_ratio < self._parameters['volume_confirmation']:
            # No hay suficiente volumen para confirmar
            return None
        
        # ✅ TODAS LAS CONDICIONES CUMPLIDAS - GENERAR SEÑAL
        
        signal = Signal(
            signal_type=SignalType.LONG,
            symbol=symbol,
            timestamp=bar.timestamp,
            price=bar.close,
            volume=bar.volume,
            confidence=self._calculate_confidence(bar, explosion_data),
            metadata={
                'strategy': 'VolumeExplosionPullback',
                'explosion_time': explosion_data['explosion_time'].isoformat(),
                'explosion_volume_ratio': explosion_data['explosion_volume_ratio'],
                'explosion_price_move': explosion_data['price_movement'],
                'current_volume_ratio': current_volume_ratio,
                'pullback_from_high': (explosion_high - bar.close) / explosion_high,
                'entry_type': 'pullback_entry'
            }
        )
        
        # Actualizar contadores
        self.last_signal_time[symbol] = bar.timestamp
        self.daily_signals_count += 1
        
        # Remover del radar (entrada completada)
        del self.explosion_radar[symbol]
        
        self.logger.info(
            f"🎯 PULLBACK ENTRY: {symbol} @ ${bar.close:.2f} | "
            f"Pullback: {((explosion_high - bar.close) / explosion_high * 100):.1f}% | "
            f"Vol: {current_volume_ratio:.1f}x | "
            f"Confidence: {signal.confidence:.0%}"
        )
        
        return signal
    
    def _calculate_confidence(self, bar: MarketData, explosion_data: Dict) -> float:
        """Calcular confianza de la señal"""
        
        confidence = 0.6  # Base confidence
        
        # Bonus por explosión fuerte
        vol_ratio = explosion_data['explosion_volume_ratio']
        if vol_ratio > 4.0:
            confidence += 0.2
        elif vol_ratio > 3.0:
            confidence += 0.1
        
        # Bonus por movimiento fuerte en explosión
        price_move = abs(explosion_data['price_movement'])
        if price_move > 0.03:  # >3%
            confidence += 0.15
        elif price_move > 0.02:  # >2%
            confidence += 0.1
        
        # Bonus por pullback ideal (no demasiado profundo)
        explosion_high = explosion_data['explosion_high']
        pullback_pct = (explosion_high - bar.close) / explosion_high
        if 0.02 <= pullback_pct <= 0.05:  # Pullback entre 2-5%
            confidence += 0.1
        
        return min(confidence, 0.95)
    
    def _update_bars_history(self, bar: MarketData) -> None:
        """Mantener historial de barras eficientemente"""
        symbol = bar.symbol
        
        if symbol not in self.bars_history:
            self.bars_history[symbol] = []
        
        self.bars_history[symbol].append(bar)
        
        # Mantener solo las barras necesarias (eficiencia de memoria)
        max_history = self._parameters['volume_lookback'] + 10
        if len(self.bars_history[symbol]) > max_history:
            self.bars_history[symbol] = self.bars_history[symbol][-max_history:]
    
    def _is_trading_hours(self, timestamp: datetime) -> bool:
        """Verificar horario de trading"""
        
        # Solo días de semana
        if timestamp.weekday() >= 5:  # Sábado=5, Domingo=6
            return False
        
        hour_decimal = timestamp.hour + timestamp.minute / 60.0
        
        return (self._parameters['start_hour'] <= hour_decimal <= self._parameters['end_hour'])
    
    def _is_in_cooldown(self, symbol: str, current_time: datetime) -> bool:
        """Verificar cooldown entre señales"""
        
        if symbol not in self.last_signal_time:
            return False
        
        time_diff = current_time - self.last_signal_time[symbol]
        return time_diff.total_seconds() / 60 < self._parameters['cooldown_minutes']
    
    def _reset_daily_counter(self, current_time: datetime) -> None:
        """Reset contador diario"""
        current_date = current_time.date()
        
        if self.last_date != current_date:
            self.daily_signals_count = 0
            self.last_date = current_date
            self.logger.info(f"📅 Daily counter reset for {current_date}")
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Información de la estrategia"""
        return {
            'name': 'VolumeExplosionPullbackStrategy',
            'version': '1.0',
            'description': 'Explosión de volumen + entrada en pullback (evita slippage)',
            'complexity_score': 8,  # MUY SIMPLE
            'conditions_count': 3,   # Solo 3 condiciones principales
            'parameters': {
                'volume_explosion_threshold': self._parameters['volume_explosion_threshold'],
                'price_move_threshold': self._parameters['price_move_threshold'],
                'pullback_entry_pct': self._parameters['pullback_entry_pct'],
                'volume_confirmation': self._parameters['volume_confirmation'],
                'max_wait_minutes': self._parameters['max_wait_minutes'],
                'cooldown_minutes': self._parameters['cooldown_minutes']
            },
            'radar_symbols': list(self.explosion_radar.keys()),
            'daily_signals_used': f"{self.daily_signals_count}/{self._parameters['max_daily_signals']}",
            'optimal_for': [
                'smallcaps_explosions',
                '1min_timeframe', 
                'regular_hours',
                'pullback_entries',
                'volume_events'
            ],
            'risk_profile': 'medium',
            'entry_style': 'pullback',
            'exit_management': 'centralized_system'
        }

# Helper functions for easy testing
def create_pullback_strategy(custom_params: Dict[str, Any] = None) -> VolumeExplosionPullbackStrategy:
    """Crear instancia con parámetros por defecto"""
    return VolumeExplosionPullbackStrategy(custom_params)

def get_conservative_params() -> Dict[str, Any]:
    """Parámetros conservadores (menos señales, más calidad)"""
    return {
        'volume_explosion_threshold': 3.0,    # Más restrictivo
        'price_move_threshold': 0.02,         # 2% mínimo
        'pullback_entry_pct': 0.96,           # Pullback más profundo
        'volume_confirmation': 2.0,           # Más confirmación
        'max_wait_minutes': 30,               # Menos tiempo de espera
        'max_daily_signals': 5                # Menos señales
    }

def get_aggressive_params() -> Dict[str, Any]:
    """Parámetros agresivos (más señales)"""
    return {
        'volume_explosion_threshold': 2.0,    # Más permisivo  
        'price_move_threshold': 0.01,         # 1% mínimo
        'pullback_entry_pct': 0.98,           # Pullback menor
        'volume_confirmation': 1.5,           # Menos confirmación
        'max_wait_minutes': 60,               # Más tiempo
        'max_daily_signals': 12               # Más señales
    }
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For VolumeExplosionPullback strategy, we don't need special logic on position updates
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
                        strategy_name="VolumeExplosionPullback",
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
                        strategy_name="VolumeExplosionPullback",
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
