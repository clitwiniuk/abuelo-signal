# core/global_data_manager.py
"""
Global Data Manager - Gestión centralizada SOLO de datos históricos
==================================================================

ENFOQUE HÍBRIDO BALANCEADO:
✅ Centraliza: bars_history (elimina duplicación de memoria)
❌ No centraliza: Lógica de estrategias, cálculos específicos

Principio: Un solo lugar para datos, múltiples lugares para análisis
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from threading import Lock
from core.interfaces import MarketData


class GlobalDataManager:
    """
    Gestor global SOLO para datos históricos
    
    Responsabilidades:
    - Almacenar bars_history de forma unificada (elimina duplicación)
    - Gestión thread-safe de acceso a datos
    - Limpieza automática de datos antiguos
    
    NO responsable de:
    - Cálculos técnicos (cada estrategia decide)
    - Lógica de trading
    - Filtros específicos
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton para acceso global"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.logger = logging.getLogger("GlobalDataManager")
        
        # ÚNICA responsabilidad: almacenar bars_history
        self._bars_history: Dict[str, List[MarketData]] = {}
        self._data_lock = Lock()
        
        # Configuración
        self.max_bars_per_symbol = 1000  # Límite de memoria
        
        # Métricas simples
        self.total_updates = 0
        
        self._initialized = True
        self.logger.info("📊 Global Data Manager initialized - Hybrid approach")
    
    def update_bar(self, symbol: str, bar: MarketData) -> None:
        """
        Actualizar una barra de datos de forma thread-safe
        
        Args:
            symbol: Símbolo del instrumento
            bar: Nueva barra de datos
        """
        with self._data_lock:
            if symbol not in self._bars_history:
                self._bars_history[symbol] = []
            
            bars = self._bars_history[symbol]
            
            # Evitar duplicados por timestamp
            if bars and bar.timestamp <= bars[-1].timestamp:
                if bar.timestamp == bars[-1].timestamp:
                    bars[-1] = bar  # Actualizar barra existente
                return
            
            # Añadir nueva barra
            bars.append(bar)
            
            # Mantener límite de memoria
            if len(bars) > self.max_bars_per_symbol:
                self._bars_history[symbol] = bars[-self.max_bars_per_symbol:]
        
        self.total_updates += 1
    
    def get_bars(self, symbol: str, limit: Optional[int] = None) -> List[MarketData]:
        """
        Obtener barras históricas de forma thread-safe
        
        Args:
            symbol: Símbolo del instrumento
            limit: Número máximo de barras (None = todas)
            
        Returns:
            Lista de barras (copia para evitar modificaciones externas)
        """
        with self._data_lock:
            bars = self._bars_history.get(symbol, [])
            
            if limit and len(bars) > limit:
                return bars[-limit:].copy()
            
            return bars.copy()
    
    def get_latest_bar(self, symbol: str) -> Optional[MarketData]:
        """Obtener la barra más reciente para un símbolo"""
        with self._data_lock:
            bars = self._bars_history.get(symbol, [])
            return bars[-1] if bars else None
    
    def has_sufficient_data(self, symbol: str, min_bars: int) -> bool:
        """Verificar si hay suficientes datos para análisis"""
        with self._data_lock:
            bars = self._bars_history.get(symbol, [])
            return len(bars) >= min_bars
    
    def get_symbols(self) -> List[str]:
        """Obtener lista de símbolos con datos"""
        with self._data_lock:
            return list(self._bars_history.keys())
    
    def clear_old_data(self, older_than_hours: int = 24) -> None:
        """Limpiar datos antiguos para liberar memoria"""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        with self._data_lock:
            for symbol in list(self._bars_history.keys()):
                bars = self._bars_history[symbol]
                recent_bars = [b for b in bars if b.timestamp > cutoff_time]
                
                if recent_bars:
                    self._bars_history[symbol] = recent_bars
                else:
                    del self._bars_history[symbol]
        
        self.logger.info(f"📊 Cleared data older than {older_than_hours} hours")
    
    def get_memory_stats(self) -> Dict:
        """Estadísticas de uso de memoria"""
        with self._data_lock:
            total_bars = sum(len(bars) for bars in self._bars_history.values())
            
            return {
                'symbols_tracked': len(self._bars_history),
                'total_bars_stored': total_bars,
                'avg_bars_per_symbol': total_bars // max(len(self._bars_history), 1),
                'max_bars_per_symbol': self.max_bars_per_symbol,
                'memory_efficiency': f"{total_bars} bars vs {len(self._bars_history) * self.max_bars_per_symbol} max possible",
                'total_updates': self.total_updates
            }


# Instancia global para fácil acceso
data_manager = GlobalDataManager()