# core/strategy_coordinator.py
"""
Strategy Coordinator - Coordinación global entre estrategias
===========================================================

ENFOQUE HÍBRIDO:
✅ Centraliza: Control temporal (cooldowns, límites diarios)
✅ Descentraliza: Lógica específica de cada estrategia
✅ Coordina: Previene conflictos entre estrategias

Principio: Coordinación sin control excesivo
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from threading import Lock
from dataclasses import dataclass


@dataclass
class StrategySignalInfo:
    """Información de señal para coordinación"""
    strategy_name: str
    symbol: str
    timestamp: datetime
    signal_type: str
    strength: float


class StrategyCoordinator:
    """
    Coordinador global para evitar conflictos entre estrategias
    
    Responsabilidades:
    - Control temporal (cooldowns, límites diarios) 
    - Prevenir señales conflictivas simultáneas
    - Estadísticas globales de estrategias
    
    NO responsable de:
    - Lógica de entrada/salida de estrategias
    - Cálculos específicos
    - Parámetros individuales
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton para coordinación global"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.logger = logging.getLogger("StrategyCoordinator")
        
        # Control temporal por estrategia
        self._strategy_last_signal: Dict[str, Dict[str, datetime]] = {}  # strategy -> symbol -> time
        self._strategy_daily_count: Dict[str, int] = {}  # strategy -> count
        self._daily_reset_date: Optional[datetime] = None
        
        # Configuración por estrategia
        self._strategy_configs: Dict[str, Dict] = {}
        
        # Lock para operaciones thread-safe
        self._coord_lock = Lock()
        
        # Historial de señales para coordinación
        self._recent_signals: List[StrategySignalInfo] = []
        self._max_recent_signals = 1000  # Límite de memoria
        
        # Estadísticas globales
        self.total_signals_generated = 0
        self.signals_blocked_by_cooldown = 0
        self.signals_blocked_by_daily_limit = 0
        self.signals_blocked_by_conflicts = 0
        
        self._initialized = True
        self.logger.info("🎯 Strategy Coordinator initialized - Hybrid coordination")
    
    def register_strategy(self, strategy_name: str, config: Dict) -> None:
        """
        Registrar una estrategia con su configuración
        
        Args:
            strategy_name: Nombre único de la estrategia
            config: Configuración (cooldown_minutes, max_daily_signals, etc.)
        """
        with self._coord_lock:
            self._strategy_configs[strategy_name] = config
            self._strategy_last_signal[strategy_name] = {}
            self._strategy_daily_count[strategy_name] = 0
        
        self.logger.info(f"📝 Strategy '{strategy_name}' registered with coordinator")
    
    def can_generate_signal(self, strategy_name: str, symbol: str, current_time: datetime) -> Tuple[bool, str]:
        """
        Verificar si una estrategia puede generar señal
        
        Args:
            strategy_name: Nombre de la estrategia
            symbol: Símbolo del instrumento
            current_time: Tiempo actual
            
        Returns:
            Tuple[can_signal, reason]: (True/False, razón si es False)
        """
        with self._coord_lock:
            # Reset contador diario si es necesario
            self._reset_daily_counter(current_time)
            
            # Verificar si la estrategia está registrada
            if strategy_name not in self._strategy_configs:
                return False, f"Strategy '{strategy_name}' not registered"
            
            config = self._strategy_configs[strategy_name]
            
            # 1. Verificar límite diario
            max_daily = config.get('max_daily_signals', float('inf'))
            current_count = self._strategy_daily_count[strategy_name]
            
            if current_count >= max_daily:
                self.signals_blocked_by_daily_limit += 1
                return False, f"Daily limit reached ({current_count}/{max_daily})"
            
            # 2. Verificar cooldown
            cooldown_minutes = config.get('cooldown_minutes', 0)
            if cooldown_minutes > 0:
                last_signal_time = self._strategy_last_signal[strategy_name].get(symbol)
                
                if last_signal_time:
                    time_diff = current_time - last_signal_time
                    if time_diff.total_seconds() / 60 < cooldown_minutes:
                        self.signals_blocked_by_cooldown += 1
                        return False, f"Cooldown active ({time_diff.total_seconds()/60:.1f}/{cooldown_minutes} min)"
            
            # 3. Verificar conflictos con otras estrategias (opcional)
            if config.get('check_conflicts', False):
                conflict = self._check_strategy_conflicts(strategy_name, symbol, current_time)
                if conflict:
                    self.signals_blocked_by_conflicts += 1
                    return False, f"Conflict detected: {conflict}"
            
            return True, "OK"
    
    def record_signal(self, strategy_name: str, symbol: str, current_time: datetime, 
                     signal_type: str, strength: float) -> None:
        """
        Registrar una señal generada
        
        Args:
            strategy_name: Nombre de la estrategia
            symbol: Símbolo del instrumento
            current_time: Tiempo de la señal
            signal_type: Tipo de señal
            strength: Fuerza de la señal
        """
        with self._coord_lock:
            # Actualizar última señal y contador
            self._strategy_last_signal[strategy_name][symbol] = current_time
            self._strategy_daily_count[strategy_name] += 1
            
            # Agregar al historial reciente
            signal_info = StrategySignalInfo(
                strategy_name=strategy_name,
                symbol=symbol,
                timestamp=current_time,
                signal_type=signal_type,
                strength=strength
            )
            
            self._recent_signals.append(signal_info)
            
            # Mantener límite de memoria
            if len(self._recent_signals) > self._max_recent_signals:
                self._recent_signals = self._recent_signals[-self._max_recent_signals:]
            
            self.total_signals_generated += 1
        
        self.logger.debug(f"📊 Signal recorded: {strategy_name} -> {symbol} ({signal_type})")
    
    def _reset_daily_counter(self, current_time: datetime) -> None:
        """Reset contador diario si es un nuevo día"""
        current_date = current_time.date()
        
        if self._daily_reset_date is None or self._daily_reset_date != current_date:
            # Nuevo día - resetear contadores
            for strategy_name in self._strategy_daily_count:
                self._strategy_daily_count[strategy_name] = 0
            
            self._daily_reset_date = current_date
            self.logger.info(f"🆕 Daily counters reset for {current_date}")
    
    def _check_strategy_conflicts(self, strategy_name: str, symbol: str, current_time: datetime) -> Optional[str]:
        """
        Verificar conflictos con señales recientes de otras estrategias
        
        Args:
            strategy_name: Estrategia que quiere generar señal
            symbol: Símbolo
            current_time: Tiempo actual
            
        Returns:
            Descripción del conflicto o None si no hay conflictos
        """
        conflict_window = timedelta(minutes=5)  # Ventana de conflicto
        
        # Buscar señales recientes del mismo símbolo
        for signal in self._recent_signals:
            if (signal.symbol == symbol and 
                signal.strategy_name != strategy_name and
                current_time - signal.timestamp < conflict_window):
                
                return f"{signal.strategy_name} signaled {signal.symbol} {(current_time - signal.timestamp).total_seconds()/60:.1f}min ago"
        
        return None
    
    def get_strategy_stats(self, strategy_name: str) -> Dict:
        """Obtener estadísticas de una estrategia"""
        with self._coord_lock:
            if strategy_name not in self._strategy_configs:
                return {}
            
            config = self._strategy_configs[strategy_name]
            daily_count = self._strategy_daily_count[strategy_name]
            max_daily = config.get('max_daily_signals', float('inf'))
            
            # Contar señales recientes de esta estrategia
            recent_count = sum(1 for s in self._recent_signals 
                             if s.strategy_name == strategy_name)
            
            return {
                'daily_signals_used': f"{daily_count}/{max_daily if max_daily != float('inf') else '∞'}",
                'recent_signals_count': recent_count,
                'cooldown_minutes': config.get('cooldown_minutes', 0),
                'check_conflicts': config.get('check_conflicts', False),
                'symbols_with_signals': len(self._strategy_last_signal[strategy_name])
            }
    
    def get_global_stats(self) -> Dict:
        """Obtener estadísticas globales del coordinador"""
        with self._coord_lock:
            return {
                'registered_strategies': len(self._strategy_configs),
                'total_signals_generated': self.total_signals_generated,
                'signals_blocked': {
                    'by_cooldown': self.signals_blocked_by_cooldown,
                    'by_daily_limit': self.signals_blocked_by_daily_limit,
                    'by_conflicts': self.signals_blocked_by_conflicts
                },
                'recent_signals_stored': len(self._recent_signals),
                'daily_reset_date': str(self._daily_reset_date) if self._daily_reset_date else 'Not set'
            }
    
    def get_recent_signals(self, limit: int = 50) -> List[StrategySignalInfo]:
        """Obtener señales recientes para análisis"""
        with self._coord_lock:
            return self._recent_signals[-limit:].copy()
    
    def clear_history(self) -> None:
        """Limpiar historial (útil para nuevo día de trading)"""
        with self._coord_lock:
            self._recent_signals.clear()
            for strategy_name in self._strategy_last_signal:
                self._strategy_last_signal[strategy_name].clear()
        
        self.logger.info("🧹 Strategy coordination history cleared")


# Instancia global para fácil acceso
strategy_coordinator = StrategyCoordinator()