#!/usr/bin/env python3
"""
Hybrid Explosion Strategy
=========================

Estrategia que usa el ENFOQUE HÍBRIDO BALANCEADO:
✅ USA componentes globales para evitar duplicación
✅ MANTIENE flexibilidad para lógica específica
✅ INTEGRA con enhanced data management

ARQUITECTURA HÍBRIDA:
- GlobalDataManager: Para bars_history unificado
- TechnicalUtils: Para cálculos estándar (opcional)
- StrategyCoordinator: Para control temporal global
- Lógica propia: Para detección específica de explosión
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np

from core.interfaces import IStrategy, Signal, MarketData, SignalType, IDataProvider
from .base import BaseStrategy

# Componentes híbridos globales
from core.global_data_manager import data_manager
from core.technical_utils import tech_utils
from core.strategy_coordinator import strategy_coordinator


class HybridExplosionStrategy(BaseStrategy):
    """
    Estrategia de explosión híbrida que aprovecha componentes globales
    manteniendo flexibilidad para lógica específica
    
    VENTAJAS DEL ENFOQUE HÍBRIDO:
    - Sin duplicación de memoria (usa GlobalDataManager)
    - Cálculos estandarizados disponibles (TechnicalUtils opcional)
    - Control temporal centralizado (StrategyCoordinator)
    - Flexibilidad total para lógica específica
    - Compatible con enhanced data management
    """
    
    def __init__(self, parameters: Dict[str, Any] = None, 
                 data_provider: IDataProvider = None):
        
        # Parámetros específicos de explosión - pueden ser únicos
        default_params = {
            # CORE explosion detection - específico de esta estrategia
            'volume_threshold': 2.5,              # 2.5x volume spike
            'momentum_threshold': 0.008,          # 0.8% momentum
            'momentum_bars': 3,                   # Confirmation period
            
            # CALIDAD - puede usar TechnicalUtils o implementar propio
            'use_standard_volatility': True,      # Usar TechnicalUtils.calculate_volatility
            'use_standard_sma': True,             # Usar TechnicalUtils.calculate_sma
            'max_volatility': 0.08,               # 8% max for smallcaps
            
            # TEMPORAL - delegado a StrategyCoordinator
            'cooldown_minutes': 15,               # Será manejado globalmente
            'max_daily_signals': 8,               # Será manejado globalmente
            'check_conflicts': False,             # No verificar conflictos con otras estrategias
            
            # ESPECÍFICOS - únicos de esta estrategia
            'min_price': 1.0,
            'max_price': 50.0,
            'min_volume_absolute': 10000,
            'explosion_confirmation_bars': 2,     # Confirmar explosión en N barras
        }
        
        if parameters:
            default_params.update(parameters)
        
        # Inicializar BaseStrategy con enhanced data management
        super().__init__("HybridExplosion", default_params, data_provider)
        
        # Registrar con el coordinador global
        strategy_coordinator.register_strategy("HybridExplosion", {
            'cooldown_minutes': default_params['cooldown_minutes'],
            'max_daily_signals': default_params['max_daily_signals'],
            'check_conflicts': default_params['check_conflicts']
        })
        
        # Estado mínimo - solo lo específico de esta estrategia
        self.explosion_cache: Dict[str, float] = {}  # Cache de strength de explosión
        
        self.logger.info("💥 Hybrid Explosion Strategy - Using global components")
        self.logger.info(f"   📊 Global data manager: {data_manager is not None}")
        self.logger.info(f"   🧮 Technical utils available: {tech_utils is not None}")
        self.logger.info(f"   🎯 Strategy coordinator: {strategy_coordinator is not None}")
    
    async def _initialize_strategy(self) -> None:
        """Initialize usando componentes globales"""
        self.logger.info("🚀 Initializing Hybrid Explosion Strategy")
        self.logger.info(f"💎 Volume threshold: {self._parameters['volume_threshold']:.1f}x")
        self.logger.info(f"📈 Momentum threshold: {self._parameters['momentum_threshold']:.1%}")
        self.logger.info(f"🎯 Daily limit: {self._parameters['max_daily_signals']}")
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """
        Procesamiento principal usando arquitectura híbrida
        """
        symbol = bar.symbol
        
        # 1. ACTUALIZAR GlobalDataManager (elimina duplicación de memoria)
        data_manager.update_bar(symbol, bar)
        
        # 2. VERIFICAR Enhanced Data Management (del BaseStrategy)
        if not self.should_generate_signals(symbol):
            return None
        
        # 3. VERIFICAR StrategyCoordinator (control temporal global)
        can_signal, reason = strategy_coordinator.can_generate_signal("HybridExplosion", symbol, bar.timestamp)
        if not can_signal:
            self.logger.debug(f"🚫 {symbol}: Signal blocked by coordinator - {reason}")
            return None
        
        # 4. VERIFICAR datos suficientes usando GlobalDataManager
        if not data_manager.has_sufficient_data(symbol, 10):
            return None
        
        # 5. FILTROS BÁSICOS específicos
        if not self._passes_basic_filters(bar):
            return None
        
        # 6. ANÁLISIS ESPECÍFICO de explosión usando datos globales
        explosion_strength = self._analyze_explosion(symbol, bar)
        if explosion_strength < 0.6:  # Umbral mínimo
            return None
        
        # ✅ GENERAR SEÑAL
        signal = self._create_explosion_signal(symbol, bar, explosion_strength)
        
        # 7. REGISTRAR con StrategyCoordinator
        strategy_coordinator.record_signal("HybridExplosion", symbol, bar.timestamp, "LONG", explosion_strength)
        
        return signal
    
    def _passes_basic_filters(self, bar: MarketData) -> bool:
        """Filtros básicos específicos de la estrategia"""
        
        # Rango de precio
        if not (self._parameters['min_price'] <= bar.close <= self._parameters['max_price']):
            return False
        
        # Volumen mínimo absoluto
        if bar.volume < self._parameters['min_volume_absolute']:
            return False
        
        # Horario de trading (puede implementar específico o usar estándar)
        if not self._is_good_trading_time(bar.timestamp):
            return False
        
        return True
    
    def _analyze_explosion(self, symbol: str, bar: MarketData) -> float:
        """
        Análisis específico de explosión usando componentes globales
        
        Returns:
            Explosion strength (0.0 - 1.0)
        """
        
        # Obtener datos desde GlobalDataManager (sin duplicación)
        bars = data_manager.get_bars(symbol, 20)
        if len(bars) < 10:
            return 0.0
        
        strength = 0.0
        
        # 1. ANÁLISIS DE VOLUMEN usando TechnicalUtils (opcional)
        volumes = tech_utils.extract_volumes(bars)
        volume_ratio = tech_utils.calculate_volume_ratio(volumes, 3)
        
        if volume_ratio >= self._parameters['volume_threshold']:
            strength += 0.4  # Base por volume explosion
            
            # Bonus por volume ratio alto
            if volume_ratio > 4.0:
                strength += 0.2
            elif volume_ratio > 3.0:
                strength += 0.1
        else:
            return 0.0  # No hay explosión de volumen
        
        # 2. ANÁLISIS DE MOMENTUM usando TechnicalUtils
        prices = tech_utils.extract_prices(bars, 'close')
        momentum = tech_utils.calculate_momentum(prices, self._parameters['momentum_bars'])
        
        if momentum >= self._parameters['momentum_threshold']:
            strength += 0.3  # Base por momentum
            
            # Bonus por momentum fuerte
            if momentum > 0.02:  # >2%
                strength += 0.1
        else:
            return 0.0  # No hay momentum suficiente
        
        # 3. ANÁLISIS DE VOLATILIDAD usando TechnicalUtils (opcional)
        if self._parameters['use_standard_volatility']:
            volatility = tech_utils.calculate_volatility(prices)
            if volatility > self._parameters['max_volatility']:
                strength -= 0.2  # Penalizar volatilidad excesiva
        
        # 4. CONFIRMACIÓN DE TENDENCIA usando TechnicalUtils (opcional)
        if self._parameters['use_standard_sma']:
            if tech_utils.is_uptrend(prices, 5, 10):
                strength += 0.1  # Bonus por tendencia alcista
        
        # 5. FACTOR DE CONFIANZA desde Enhanced Data Management
        confidence = self.confidence_factors.get(symbol, 1.0)
        strength *= confidence  # Ajustar por confianza de datos
        
        return min(max(strength, 0.0), 1.0)
    
    def _create_explosion_signal(self, symbol: str, bar: MarketData, strength: float) -> Signal:
        """Crear señal usando datos híbridos"""
        
        # Obtener métricas adicionales para metadata
        bars = data_manager.get_bars(symbol, 10)
        volumes = tech_utils.extract_volumes(bars)
        prices = tech_utils.extract_prices(bars)
        
        volume_ratio = tech_utils.calculate_volume_ratio(volumes, 3)
        momentum = tech_utils.calculate_momentum(prices, self._parameters['momentum_bars'])
        confidence = self.confidence_factors.get(symbol, 1.0)
        
        signal = Signal(
            signal_id=f"hybrid_{symbol}_{int(bar.timestamp.timestamp())}",
            signal_type=SignalType.LONG,
            symbol=symbol,
            strength=strength,
            price=bar.close,
            timestamp=bar.timestamp,
            strategy_name="HybridExplosion",
            metadata={
                'strategy': 'HybridExplosion',
                'approach': 'hybrid_global_components',
                'volume_ratio': volume_ratio,
                'momentum': momentum,
                'confidence_factor': confidence,
                'data_source': 'global_data_manager',
                'technical_utils_used': True,
                'coordinator_approved': True,
                'explosion_strength': strength
            }
        )
        
        # Log con información híbrida
        self.logger.info(
            f"💥 HYBRID EXPLOSION: {symbol} @ ${bar.close:.2f} | "
            f"Vol: {volume_ratio:.1f}x | Mom: {momentum:+.2%} | "
            f"Strength: {strength:.2f} | Conf: {confidence:.2f}"
        )
        
        return signal
    
    def _is_good_trading_time(self, timestamp: datetime) -> bool:
        """Horario de trading - puede ser específico o estándar"""
        if timestamp.weekday() >= 5:  # Weekend
            return False
        
        # Horario básico: 10:00 AM - 3:00 PM
        hour_decimal = timestamp.hour + timestamp.minute / 60.0
        return 10.0 <= hour_decimal <= 15.0
    
    # Override del BaseStrategy para usar GlobalDataManager
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Delegado a on_bar para arquitectura híbrida"""
        return await self.on_bar(bar)
    
    # Implementar métodos abstractos requeridos
    async def on_position_update(self, position) -> Optional[Signal]:
        """Handle position updates - implementación mínima"""
        # Para esta estrategia, no necesitamos lógica especial de position updates
        return None
    
    def should_exit(self, position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited - implementación básica"""
        # Implementar lógica básica de salida (stop loss, take profit, etc.)
        # Por ahora, delegamos al BaseStrategy si tiene lógica por defecto
        try:
            # Check basic stop loss (5% default)
            stop_loss_pct = 0.05
            if position.quantity > 0:  # Long position
                stop_price = position.avg_price * (1 - stop_loss_pct)
                if current_bar.close <= stop_price:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        signal_type=SignalType.EXIT_LONG,
                        symbol=position.symbol,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="HybridExplosion",
                        metadata={'exit_reason': 'stop_loss'}
                    )
            return None
        except:
            return None
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Información de estrategia híbrida"""
        
        # Obtener stats del coordinador
        coordinator_stats = strategy_coordinator.get_strategy_stats("HybridExplosion")
        
        # Obtener stats del data manager
        data_stats = data_manager.get_memory_stats()
        
        return {
            'name': 'HybridExplosionStrategy',
            'version': '1.0',
            'description': 'Explosion strategy using hybrid global components',
            'architecture': 'hybrid_balanced',
            'complexity_score': 4,  # Reducido por usar componentes globales
            'global_components_used': {
                'global_data_manager': True,
                'technical_utils': True,
                'strategy_coordinator': True,
                'enhanced_data_management': True
            },
            'memory_efficiency': {
                'bars_history_shared': True,
                'no_duplication': True,
                'symbols_tracked_globally': data_stats['symbols_tracked']
            },
            'coordination': coordinator_stats,
            'parameters': {
                'volume_threshold': self._parameters['volume_threshold'],
                'momentum_threshold': self._parameters['momentum_threshold'],
                'max_daily_signals': self._parameters['max_daily_signals']
            },
            'benefits': [
                'memory_efficient',
                'consistent_calculations',
                'global_coordination',
                'enhanced_data_ready',
                'flexible_specific_logic'
            ]
        }