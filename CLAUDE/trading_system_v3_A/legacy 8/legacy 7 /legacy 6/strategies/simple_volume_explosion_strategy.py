#!/usr/bin/env python3
"""
Simple Volume Explosion Strategy
=================================

Estrategia ultra simple que funciona directamente con los eventos de explosión:
1. Detectar explosión de volumen (>2x promedio)
2. Entrar inmediatamente si hay momentum positivo
3. Sistema centralizado maneja todas las salidas

FILOSOFÍA: 
- Datos sintéticos YA SON explosiones de volumen
- No necesitamos detectar - ya están pre-filtradas
- Solo confirmar que hay momentum y entrar
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np

from core.interfaces import IStrategy, Signal, SignalType, Position, MarketData
from .base import BaseStrategy


class SimpleVolumeExplosionStrategy(BaseStrategy):
    """
    Estrategia ultra simple para datos de explosiones pre-filtradas
    
    Diseñada específicamente para trabajar con datos sintéticos
    que YA contienen eventos de explosión de volumen.
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # FALLBACK DEFAULTS - Usado solo si config.ini no existe o está incompleto
        fallback_defaults = {
            # Detección mínima (datos ya están pre-filtrados)
            'volume_threshold': 1.5,              # Solo 1.5x para confirmar
            'momentum_threshold': 0.005,          # 0.5% momentum mínimo
            'momentum_bars': 2,                   # Solo 2 barras para momentum
            
            # Configuración básica
            'min_history_bars': 5,                # Solo 5 barras mínimas
            'max_position_value': 500.0,          
            
            # Control de operativa
            'cooldown_minutes': 5,                # 5min cooldown
            'max_daily_signals': 15,              # 15 señales por día
            
            # Horarios (permisivo)
            'start_hour': 9.5,                    # 9:30 AM
            'end_hour': 15.5,                     # 3:30 PM
        }
        
        # Initialize with fallback defaults first to get logger
        super().__init__("SimpleVolumeExplosion", fallback_defaults)
        
        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('SIMPLE_VOLUME_EXPLOSION_STRATEGY', fallback_defaults)
            
            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for SimpleVolumeExplosion strategy: {e}")
            # Keep fallback defaults
        
        # Estado mínimo
        self.bars_history: Dict[str, List[MarketData]] = {}
        self.last_signal_time: Dict[str, datetime] = {}
        self.daily_signals_count = 0
        self.last_date = None
        
        self.logger.info("🎯 Simple Volume Explosion Strategy initialized - direct entry on explosions!")
    
    async def _initialize_strategy(self) -> None:
        """Initialize strategy"""
        self.logger.info("🚀 Initializing Simple Volume Explosion Strategy")
        self.logger.info(f"💥 Volume threshold: {self._parameters['volume_threshold']:.1f}x")
        self.logger.info(f"📈 Momentum threshold: {self._parameters['momentum_threshold']:.1f}%")
        self.logger.info(f"🎯 Entry style: DIRECT (no pullback wait)")
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar - delegates to on_bar"""
        return await self.on_bar(bar)
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """Procesar nueva barra - LÓGICA ULTRA SIMPLE"""
        
        symbol = bar.symbol
        
        # Reset contador diario
        self._reset_daily_counter(bar.timestamp)
        
        # Limitar señales diarias
        if self.daily_signals_count >= self._parameters['max_daily_signals']:
            return None
        
        # Solo horario regular
        if not self._is_trading_hours(bar.timestamp):
            return None
        
        # Mantener historial
        self._update_bars_history(bar)
        
        # Historial mínimo
        if len(self.bars_history.get(symbol, [])) < self._parameters['min_history_bars']:
            return None
        
        # Cooldown
        if self._is_in_cooldown(symbol, bar.timestamp):
            return None
        
        # CONDICIÓN 1: Volume confirmación (datos ya están pre-filtrados)
        if not self._volume_confirms(bar):
            return None
        
        # CONDICIÓN 2: Momentum positivo
        if not self._momentum_positive(bar):
            return None
        
        # ✅ GENERAR SEÑAL INMEDIATA
        signal = Signal(
            signal_type=SignalType.LONG,
            symbol=symbol,
            timestamp=bar.timestamp,
            price=bar.close,
            volume=bar.volume,
            confidence=self._calculate_confidence(bar),
            metadata={
                'strategy': 'SimpleVolumeExplosion',
                'volume_ratio': self._get_volume_ratio(bar),
                'momentum': self._get_momentum(bar),
                'entry_type': 'explosion_direct'
            }
        )
        
        # Actualizar estado
        self.last_signal_time[symbol] = bar.timestamp
        self.daily_signals_count += 1
        
        self.logger.info(
            f"🎯 EXPLOSION ENTRY: {symbol} @ ${bar.close:.2f} | "
            f"Vol: {self._get_volume_ratio(bar):.1f}x | "
            f"Momentum: {self._get_momentum(bar):+.2%} | "
            f"Confidence: {signal.confidence:.0%}"
        )
        
        return signal
    
    def _volume_confirms(self, bar: MarketData) -> bool:
        """CONDICIÓN 1: Volume confirmación simple"""
        
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        if len(bars) < 3:
            return False
        
        # Volumen promedio últimas 3 barras (excluyendo actual)
        recent_volumes = [b.volume for b in bars[-4:-1]]  # 3 barras anteriores
        avg_volume = np.mean(recent_volumes)
        
        if avg_volume <= 0:
            return False
        
        # Confirmar que hay volumen por encima del threshold
        volume_ratio = bar.volume / avg_volume
        return volume_ratio >= self._parameters['volume_threshold']
    
    def _momentum_positive(self, bar: MarketData) -> bool:
        """CONDICIÓN 2: Momentum positivo simple"""
        
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        momentum_bars = self._parameters['momentum_bars']
        
        if len(bars) < momentum_bars + 1:
            return False
        
        # Precio de hace N barras vs precio actual
        old_price = bars[-(momentum_bars + 1)].close
        current_price = bar.close
        
        momentum = (current_price - old_price) / old_price
        
        return momentum >= self._parameters['momentum_threshold']
    
    def _calculate_confidence(self, bar: MarketData) -> float:
        """Calcular confianza simple"""
        
        confidence = 0.7  # Base alta (datos pre-filtrados)
        
        # Bonus por volumen
        volume_ratio = self._get_volume_ratio(bar)
        if volume_ratio > 3.0:
            confidence += 0.15
        elif volume_ratio > 2.0:
            confidence += 0.1
        
        # Bonus por momentum
        momentum = self._get_momentum(bar)
        if momentum > 0.02:  # >2%
            confidence += 0.1
        elif momentum > 0.01:  # >1%
            confidence += 0.05
        
        return min(confidence, 0.95)
    
    def _get_volume_ratio(self, bar: MarketData) -> float:
        """Helper: volumen ratio"""
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        if len(bars) < 3:
            return 1.0
        
        recent_volumes = [b.volume for b in bars[-4:-1]]
        avg_volume = np.mean(recent_volumes)
        
        return bar.volume / avg_volume if avg_volume > 0 else 1.0
    
    def _get_momentum(self, bar: MarketData) -> float:
        """Helper: momentum"""
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        momentum_bars = self._parameters['momentum_bars']
        
        if len(bars) < momentum_bars + 1:
            return 0.0
        
        old_price = bars[-(momentum_bars + 1)].close
        return (bar.close - old_price) / old_price
    
    def _update_bars_history(self, bar: MarketData) -> None:
        """Mantener historial eficientemente"""
        symbol = bar.symbol
        
        if symbol not in self.bars_history:
            self.bars_history[symbol] = []
        
        self.bars_history[symbol].append(bar)
        
        # Solo mantener barras necesarias
        max_history = max(self._parameters['momentum_bars'] + 2, 10)
        if len(self.bars_history[symbol]) > max_history:
            self.bars_history[symbol] = self.bars_history[symbol][-max_history:]
    
    def _is_trading_hours(self, timestamp: datetime) -> bool:
        """Verificar horario"""
        if timestamp.weekday() >= 5:
            return False
        
        hour_decimal = timestamp.hour + timestamp.minute / 60.0
        return (self._parameters['start_hour'] <= hour_decimal <= self._parameters['end_hour'])
    
    def _is_in_cooldown(self, symbol: str, current_time: datetime) -> bool:
        """Cooldown"""
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
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Info de estrategia"""
        return {
            'name': 'SimpleVolumeExplosionStrategy',
            'version': '1.0',
            'description': 'Entrada directa en explosiones de volumen (sin pullback)',
            'complexity_score': 3,  # ULTRA SIMPLE
            'conditions_count': 2,   # Solo 2 condiciones
            'parameters': {
                'volume_threshold': self._parameters['volume_threshold'],
                'momentum_threshold': self._parameters['momentum_threshold'],
                'momentum_bars': self._parameters['momentum_bars'],
                'min_history_bars': self._parameters['min_history_bars']
            },
            'daily_signals_used': f"{self.daily_signals_count}/{self._parameters['max_daily_signals']}",
            'optimal_for': [
                'pre_filtered_explosions',
                'synthetic_data',
                '1min_direct_entry',
                'high_frequency_signals'
            ],
            'entry_style': 'direct_explosion',
            'risk_profile': 'medium_aggressive'
        }

# Helper functions
def create_simple_explosion_strategy(custom_params: Dict[str, Any] = None) -> SimpleVolumeExplosionStrategy:
    """Crear instancia simple"""
    return SimpleVolumeExplosionStrategy(custom_params)

def get_conservative_params() -> Dict[str, Any]:
    """Parámetros conservadores"""
    return {
        'volume_threshold': 2.0,        # Más restrictivo
        'momentum_threshold': 0.01,     # 1% momentum
        'momentum_bars': 3,             # 3 barras lookback
        'max_daily_signals': 8          # Menos señales
    }

def get_aggressive_params() -> Dict[str, Any]:
    """Parámetros agresivos"""
    return {
        'volume_threshold': 1.2,        # Muy permisivo
        'momentum_threshold': 0.002,    # 0.2% momentum
        'momentum_bars': 1,             # Solo 1 barra
        'max_daily_signals': 25         # Muchas señales
    }
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For SimpleVolumeExplosion strategy, we don't need special logic on position updates
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
                        strategy_name="SimpleVolumeExplosion",
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
                        strategy_name="SimpleVolumeExplosion",
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
