# core/technical_utils.py
"""
Technical Utils - Utilidades técnicas compartidas OPCIONALES
============================================================

ENFOQUE HÍBRIDO:
✅ Proporciona: Cálculos técnicos estándar (SMA, EMA, volatilidad)
✅ Flexible: Las estrategias pueden usar estos O implementar propios
✅ Stateless: Solo funciones puras, no mantiene estado

Principio: Herramientas disponibles, uso opcional
"""

from typing import List, Optional, Tuple
import numpy as np
from core.interfaces import MarketData


class TechnicalUtils:
    """
    Utilidades técnicas estándar para estrategias
    
    IMPORTANTE: Estas son OPCIONALES
    - Las estrategias pueden usarlas para consistencia
    - O implementar sus propios cálculos si necesitan algo específico
    - Son stateless (funciones puras)
    """
    
    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> Optional[float]:
        """
        Simple Moving Average estándar
        
        Args:
            prices: Lista de precios
            period: Período para el promedio
            
        Returns:
            SMA o None si no hay suficientes datos
        """
        if len(prices) < period:
            return None
        
        return np.mean(prices[-period:])
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> Optional[float]:
        """
        Exponential Moving Average estándar
        
        Args:
            prices: Lista de precios
            period: Período para EMA
            
        Returns:
            EMA o None si no hay suficientes datos
        """
        if len(prices) < period:
            return None
        
        multiplier = 2.0 / (period + 1)
        
        # Comenzar con SMA para los primeros valores
        ema = np.mean(prices[:period])
        
        # Calcular EMA para el resto
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    @staticmethod
    def calculate_volatility(prices: List[float]) -> float:
        """
        Volatilidad estándar (desviación estándar de returns)
        
        Args:
            prices: Lista de precios
            
        Returns:
            Volatilidad (0.0 si no hay suficientes datos)
        """
        if len(prices) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)
        
        return np.std(returns) if returns else 0.0
    
    @staticmethod
    def calculate_volume_ratio(volumes: List[float], comparison_periods: int = 3) -> float:
        """
        Ratio de volumen actual vs promedio de períodos anteriores
        
        Args:
            volumes: Lista de volúmenes
            comparison_periods: Períodos para comparación
            
        Returns:
            Ratio (1.0 si no hay suficientes datos)
        """
        if len(volumes) < comparison_periods + 1:
            return 1.0
        
        current_volume = volumes[-1]
        avg_volume = np.mean(volumes[-(comparison_periods + 1):-1])
        
        return current_volume / avg_volume if avg_volume > 0 else 1.0
    
    @staticmethod
    def calculate_momentum(prices: List[float], periods: int) -> float:
        """
        Momentum (cambio porcentual) sobre N períodos
        
        Args:
            prices: Lista de precios
            periods: Número de períodos para calcular momentum
            
        Returns:
            Momentum como decimal (0.0 si no hay suficientes datos)
        """
        if len(prices) < periods + 1:
            return 0.0
        
        old_price = prices[-(periods + 1)]
        current_price = prices[-1]
        
        return (current_price - old_price) / old_price if old_price > 0 else 0.0
    
    @staticmethod
    def calculate_atr(bars: List[MarketData], period: int = 14) -> float:
        """
        Average True Range
        
        Args:
            bars: Lista de barras de mercado
            period: Período para ATR
            
        Returns:
            ATR o 0.0 si no hay suficientes datos
        """
        if len(bars) < period + 1:
            return 0.0
        
        true_ranges = []
        
        for i in range(1, len(bars)):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i-1].close
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            
            true_ranges.append(max(tr1, tr2, tr3))
        
        if len(true_ranges) < period:
            return 0.0
        
        return np.mean(true_ranges[-period:])
    
    @staticmethod
    def is_uptrend(prices: List[float], short_period: int = 5, long_period: int = 20) -> bool:
        """
        Detectar tendencia alcista simple (SMA corta > SMA larga)
        
        Args:
            prices: Lista de precios
            short_period: Período corto
            long_period: Período largo
            
        Returns:
            True si está en tendencia alcista
        """
        if len(prices) < long_period:
            return False
        
        sma_short = np.mean(prices[-short_period:])
        sma_long = np.mean(prices[-long_period:])
        
        return bool(sma_short > sma_long)
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """
        Relative Strength Index estándar
        
        Args:
            prices: Lista de precios
            period: Período para RSI
            
        Returns:
            RSI (0-100) o None si no hay suficientes datos
        """
        if len(prices) < period + 1:
            return None
        
        # Calcular cambios de precio
        changes = []
        for i in range(1, len(prices)):
            changes.append(prices[i] - prices[i-1])
        
        if len(changes) < period:
            return None
        
        # Separar ganancias y pérdidas
        gains = [max(change, 0) for change in changes[-period:]]
        losses = [abs(min(change, 0)) for change in changes[-period:]]
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0  # No hay pérdidas
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def extract_prices(bars: List[MarketData], price_type: str = 'close') -> List[float]:
        """
        Extraer lista de precios desde barras
        
        Args:
            bars: Lista de barras
            price_type: 'close', 'open', 'high', 'low'
            
        Returns:
            Lista de precios
        """
        if price_type == 'close':
            return [bar.close for bar in bars]
        elif price_type == 'open':
            return [bar.open for bar in bars]
        elif price_type == 'high':
            return [bar.high for bar in bars]
        elif price_type == 'low':
            return [bar.low for bar in bars]
        else:
            return [bar.close for bar in bars]  # Default a close
    
    @staticmethod
    def extract_volumes(bars: List[MarketData]) -> List[float]:
        """Extraer lista de volúmenes desde barras"""
        return [bar.volume for bar in bars]


# Instancia global para fácil acceso (opcional)
tech_utils = TechnicalUtils()