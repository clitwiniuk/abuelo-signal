# core/enhanced_data_manager.py
"""
Enhanced Data Manager - Manejo inteligente de datos con continuidad entre días
Soluciona el problema de falta de datos en apertura usando datos del día anterior
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from dataclasses import dataclass

from core.interfaces import MarketData, IDataProvider


@dataclass
class DataContinuityConfig:
    """Configuración para la continuidad de datos entre días"""
    # Cuántos períodos del día anterior usar máximo
    max_previous_periods: int = 50
    
    # Factor base de confianza para datos del día anterior (0.0 - 1.0)
    base_confidence_factor: float = 0.7
    
    # Tiempo mínimo después de apertura antes de operar (minutos)
    min_trading_delay_minutes: int = 15
    
    # Tiempo donde alcanza confianza máxima (minutos después de apertura)
    max_confidence_time_minutes: int = 30
    
    # Umbral de gap significativo (% del precio)
    significant_gap_threshold: float = 0.02  # 2%
    
    # Factor de reducción de confianza por gap grande
    gap_confidence_reduction: float = 0.3


class EnhancedDataManager:
    """
    Maneja datos de mercado con continuidad entre días para evitar
    problemas de falta de datos en apertura
    """
    
    def __init__(self, data_provider: IDataProvider, config: DataContinuityConfig = None):
        self.data_provider = data_provider
        self.config = config or DataContinuityConfig()
        self.logger = logging.getLogger("EnhancedDataManager")
        
        # Cache de datos del día anterior por símbolo
        self.previous_day_cache: Dict[str, List[MarketData]] = {}
        
        # Cache de datos del día actual
        self.current_day_cache: Dict[str, List[MarketData]] = {}
        
        # Metadatos de continuidad por símbolo
        self.continuity_metadata: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("🔧 Enhanced Data Manager initialized")
        self.logger.info(f"   Max previous periods: {self.config.max_previous_periods}")
        self.logger.info(f"   Min trading delay: {self.config.min_trading_delay_minutes} min")
        self.logger.info(f"   Max confidence time: {self.config.max_confidence_time_minutes} min")
    
    async def get_enhanced_market_data(self, symbol: str, bars: int = 100) -> Tuple[List[MarketData], float]:
        """
        Obtiene datos de mercado con continuidad entre días
        
        Returns:
            Tuple[List[MarketData], float]: (datos_combinados, factor_confianza)
        """
        current_time = datetime.now(timezone.utc)
        market_open_today = self._get_market_open_time(current_time.date())
        
        # Obtener datos del día actual
        current_data = await self._get_current_day_data(symbol, bars)
        
        # Determinar si necesitamos datos del día anterior
        minutes_since_open = self._minutes_since_market_open(current_time, market_open_today)
        need_previous_data = (
            minutes_since_open < self.config.min_trading_delay_minutes or
            len(current_data) < min(bars, 20)  # Muy pocos datos actuales
        )
        
        if need_previous_data:
            # Usar datos del día anterior + día actual
            previous_data = await self._get_previous_day_data(symbol)
            enhanced_data = self._combine_data(previous_data, current_data, bars)
            confidence = self._calculate_confidence_factor(current_time, market_open_today, current_data, previous_data, symbol)
        else:
            # Usar solo datos del día actual
            enhanced_data = current_data[-bars:] if len(current_data) > bars else current_data
            confidence = 1.0  # Confianza completa en datos del día actual
        
        # Actualizar metadatos
        self._update_continuity_metadata(symbol, current_time, len(current_data), len(enhanced_data), confidence)
        
        return enhanced_data, confidence
    
    async def _get_current_day_data(self, symbol: str, bars: int) -> List[MarketData]:
        """Obtiene datos del día actual"""
        try:
            # Usar el data provider existente
            data = await self.data_provider.get_market_data(symbol, bars)
            
            # Filtrar solo datos de hoy
            today = datetime.now(timezone.utc).date()
            current_day_data = [
                bar for bar in data 
                if bar.timestamp.date() == today
            ]
            
            # Actualizar cache
            self.current_day_cache[symbol] = current_day_data
            
            return current_day_data
            
        except Exception as e:
            self.logger.error(f"❌ Error getting current day data for {symbol}: {e}")
            return self.current_day_cache.get(symbol, [])
    
    async def _get_previous_day_data(self, symbol: str) -> List[MarketData]:
        """Obtiene datos del día anterior (últimos N períodos)"""
        if symbol in self.previous_day_cache:
            return self.previous_day_cache[symbol]
        
        try:
            # Pedir más datos para obtener día anterior
            extended_bars = 500  # Suficientes para cubrir día anterior
            all_data = await self.data_provider.get_market_data(symbol, extended_bars)
            
            if not all_data:
                return []
            
            # Encontrar datos del día anterior
            today = datetime.now(timezone.utc).date()
            yesterday = today - timedelta(days=1)
            
            # Buscar el último día de trading anterior (puede no ser ayer exacto)
            previous_day_data = []
            for i in range(5):  # Buscar hasta 5 días atrás
                check_date = today - timedelta(days=i+1)
                day_data = [bar for bar in all_data if bar.timestamp.date() == check_date]
                
                if day_data:
                    # Tomar los últimos N períodos de ese día
                    previous_day_data = day_data[-self.config.max_previous_periods:]
                    break
            
            # Cache para uso futuro
            self.previous_day_cache[symbol] = previous_day_data
            
            return previous_day_data
            
        except Exception as e:
            self.logger.error(f"❌ Error getting previous day data for {symbol}: {e}")
            return []
    
    def _combine_data(self, previous_data: List[MarketData], current_data: List[MarketData], total_bars: int) -> List[MarketData]:
        """Combina datos del día anterior con datos actuales"""
        if not previous_data and not current_data:
            return []
        
        if not previous_data:
            return current_data[-total_bars:] if len(current_data) > total_bars else current_data
        
        if not current_data:
            return previous_data[-total_bars:] if len(previous_data) > total_bars else previous_data
        
        # Combinar datos: día anterior + día actual
        combined = previous_data + current_data
        
        # Limitar al número total solicitado, priorizando datos actuales
        if len(combined) > total_bars:
            # Si tenemos suficientes datos actuales, usar menos del día anterior
            current_count = len(current_data)
            if current_count >= total_bars // 2:  # Al menos la mitad de datos actuales
                previous_count = total_bars - current_count
                combined = previous_data[-previous_count:] + current_data
            else:
                combined = combined[-total_bars:]
        
        return combined
    
    def _calculate_confidence_factor(self, current_time: datetime, market_open: datetime, 
                                   current_data: List[MarketData], previous_data: List[MarketData], 
                                   symbol: str) -> float:
        """Calcula el factor de confianza basado en tiempo y condiciones de mercado"""
        
        # Factor base por datos del día anterior
        base_confidence = self.config.base_confidence_factor
        
        # Factor temporal: aumenta con el tiempo desde apertura
        minutes_since_open = self._minutes_since_market_open(current_time, market_open)
        if minutes_since_open <= 0:
            time_factor = 0.5  # Pre-mercado, confianza reducida
        elif minutes_since_open < self.config.max_confidence_time_minutes:
            # Aumenta linealmente hasta el tiempo máximo
            time_factor = 0.5 + (minutes_since_open / self.config.max_confidence_time_minutes) * 0.5
        else:
            time_factor = 1.0  # Confianza completa después del tiempo máximo
        
        # Factor de gap: reduce confianza si hay gap significativo
        gap_factor = 1.0
        if current_data and previous_data:
            gap_percentage = self._calculate_gap_percentage(previous_data, current_data)
            if abs(gap_percentage) > self.config.significant_gap_threshold:
                gap_factor = 1.0 - self.config.gap_confidence_reduction
                self.logger.info(f"📊 {symbol}: Gap significativo detectado {gap_percentage:.2%}, reduciendo confianza")
        
        # Factor de cantidad de datos actuales
        data_factor = 1.0
        if current_data:
            current_data_ratio = len(current_data) / max(20, len(current_data) + len(previous_data))
            data_factor = 0.7 + (current_data_ratio * 0.3)  # Entre 0.7 y 1.0
        
        # Combinar factores
        final_confidence = base_confidence * time_factor * gap_factor * data_factor
        
        # Límites
        final_confidence = max(0.3, min(1.0, final_confidence))
        
        return final_confidence
    
    def _calculate_gap_percentage(self, previous_data: List[MarketData], current_data: List[MarketData]) -> float:
        """Calcula el porcentaje de gap entre el cierre anterior y apertura actual"""
        if not previous_data or not current_data:
            return 0.0
        
        last_close = previous_data[-1].close
        first_open = current_data[0].open
        
        if last_close == 0:
            return 0.0
        
        gap_percentage = (first_open - last_close) / last_close
        return gap_percentage
    
    def _get_market_open_time(self, date) -> datetime:
        """Obtiene la hora de apertura del mercado para una fecha"""
        # NYSE abre a las 9:30 AM ET
        return datetime.combine(date, datetime.min.time().replace(hour=14, minute=30)).replace(tzinfo=timezone.utc)
    
    def _minutes_since_market_open(self, current_time: datetime, market_open: datetime) -> int:
        """Calcula minutos transcurridos desde la apertura del mercado"""
        if current_time < market_open:
            return -1  # Pre-mercado
        
        delta = current_time - market_open
        return int(delta.total_seconds() / 60)
    
    def _update_continuity_metadata(self, symbol: str, timestamp: datetime, current_bars: int, 
                                  total_bars: int, confidence: float):
        """Actualiza metadatos de continuidad para tracking"""
        self.continuity_metadata[symbol] = {
            'last_update': timestamp,
            'current_day_bars': current_bars,
            'total_bars_used': total_bars,
            'confidence_factor': confidence,
            'using_previous_day': current_bars < 20,
            'minutes_since_open': self._minutes_since_market_open(timestamp, self._get_market_open_time(timestamp.date()))
        }
    
    def get_continuity_info(self, symbol: str) -> Dict[str, Any]:
        """Obtiene información de continuidad para un símbolo"""
        return self.continuity_metadata.get(symbol, {})
    
    def is_ready_for_trading(self, symbol: str) -> bool:
        """Determina si el símbolo está listo para trading basado en confianza"""
        metadata = self.get_continuity_info(symbol)
        if not metadata:
            return False
        
        confidence = metadata.get('confidence_factor', 0.0)
        minutes_since_open = metadata.get('minutes_since_open', 0)
        
        # Criterios para estar listo para trading
        ready = (
            confidence >= 0.7 and  # Confianza mínima
            minutes_since_open >= self.config.min_trading_delay_minutes  # Tiempo mínimo transcurrido
        )
        
        return ready
    
    def clear_cache(self):
        """Limpia caches (útil para nuevo día de trading)"""
        self.previous_day_cache.clear()
        self.current_day_cache.clear()
        self.continuity_metadata.clear()
        self.logger.info("🧹 Data caches cleared")