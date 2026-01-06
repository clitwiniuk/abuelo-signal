#!/usr/bin/env python3
"""
Adaptive Cache Manager - Sistema de caché adaptativo para trading
Ajusta intervalos de refresh según horarios del mercado y volatilidad
"""

import logging
from datetime import datetime, time, timezone
from typing import Dict, Any, Tuple
import pytz

logger = logging.getLogger(__name__)

class AdaptiveCacheManager:
    """
    Maneja refresh intervals adaptativos basados en horarios de mercado
    Optimizado para smallcaps con balance entre detección y carga API
    """
    
    def __init__(self):
        # Timezone para mercado US (EST/EDT)
        self.market_tz = pytz.timezone('US/Eastern')
        
        # Configuración de períodos del mercado (horario EST/EDT)
        self.market_periods = {
            'premarket': {
                'start': time(4, 0),     # 4:00 AM EST
                'end': time(9, 30),      # 9:30 AM EST  
                'refresh_minutes': 5,    # Gaps importantes
                'priority': 'HIGH'
            },
            'market_open': {
                'start': time(9, 30),    # 9:30 AM EST
                'end': time(10, 30),     # 10:30 AM EST
                'refresh_minutes': 5,    # OPTIMIZADO - Balance entre detección y carga API
                'priority': 'CRITICAL'
            },
            'morning_session': {
                'start': time(10, 30),   # 10:30 AM EST
                'end': time(12, 0),      # 12:00 PM EST
                'refresh_minutes': 8,    # Balance medio
                'priority': 'MEDIUM'
            },
            'lunch_time': {
                'start': time(12, 0),    # 12:00 PM EST
                'end': time(14, 0),      # 2:00 PM EST
                'refresh_minutes': 15,   # Mercado tranquilo
                'priority': 'LOW'
            },
            'afternoon': {
                'start': time(14, 0),    # 2:00 PM EST
                'end': time(15, 30),     # 3:30 PM EST
                'refresh_minutes': 8,    # Balance medio
                'priority': 'MEDIUM'
            },
            'power_hour': {
                'start': time(15, 30),   # 3:30 PM EST
                'end': time(16, 0),      # 4:00 PM EST
                'refresh_minutes': 8,    # OPTIMIZADO - Menos agresivo para reducir carga
                'priority': 'HIGH'
            },
            'after_hours': {
                'start': time(16, 0),    # 4:00 PM EST
                'end': time(20, 0),      # 8:00 PM EST
                'refresh_minutes': 12,   # Después de mercado
                'priority': 'LOW'
            }
        }
        
        # Fallback para fuera de horario
        self.default_refresh_minutes = 20
        
        logger.info("🕐 Adaptive Cache Manager initialized")
        logger.info("   📊 Market periods configured for EST/EDT timezone")
        logger.info(f"   🔄 Default refresh (off-hours): {self.default_refresh_minutes}min")
    
    def get_current_market_period(self, current_time: datetime = None) -> Tuple[str, Dict[str, Any]]:
        """
        Determina el período actual del mercado
        
        Returns:
            Tuple[period_name, period_config]
        """
        if current_time is None:
            current_time = datetime.now(self.market_tz)
        
        # Convertir a timezone del mercado si es necesario
        if current_time.tzinfo != self.market_tz:
            current_time = current_time.astimezone(self.market_tz)
        
        current_time_only = current_time.time()
        current_weekday = current_time.weekday()  # 0=Monday, 6=Sunday
        
        # Verificar si es día hábil (Monday=0 to Friday=4)
        if current_weekday > 4:  # Weekend
            return 'weekend', {
                'refresh_minutes': self.default_refresh_minutes,
                'priority': 'OFF',
                'reason': 'Weekend - market closed'
            }
        
        # Buscar período actual
        for period_name, period_config in self.market_periods.items():
            start_time = period_config['start']
            end_time = period_config['end']
            
            if start_time <= current_time_only < end_time:
                return period_name, period_config
        
        # Si no está en ningún período definido
        return 'off_hours', {
            'refresh_minutes': self.default_refresh_minutes,
            'priority': 'OFF',
            'reason': 'Outside market hours'
        }
    
    def get_optimal_refresh_interval(self, current_time: datetime = None) -> Dict[str, Any]:
        """
        Obtiene el intervalo de refresh óptimo para el momento actual
        
        Returns:
            Dict con refresh_minutes, period_name, priority, etc.
        """
        period_name, period_config = self.get_current_market_period(current_time)
        
        refresh_minutes = period_config['refresh_minutes']
        refresh_seconds = refresh_minutes * 60
        
        result = {
            'refresh_minutes': refresh_minutes,
            'refresh_seconds': refresh_seconds,
            'period_name': period_name,
            'priority': period_config['priority'],
            'market_time': current_time or datetime.now(self.market_tz),
            'reason': period_config.get('reason', f'Market period: {period_name}')
        }
        
        return result
    
    def should_refresh_cache(self, last_refresh: datetime, current_time: datetime = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Determina si el caché debe refrescarse basado en el timing adaptativo
        
        Args:
            last_refresh: Timestamp del último refresh
            current_time: Tiempo actual (opcional)
            
        Returns:
            Tuple[should_refresh, refresh_info]
        """
        if current_time is None:
            current_time = datetime.now(self.market_tz)
            
        # Asegurar timezone consistency
        if last_refresh.tzinfo != self.market_tz:
            last_refresh = last_refresh.astimezone(self.market_tz)
        if current_time.tzinfo != self.market_tz:
            current_time = current_time.astimezone(self.market_tz)
        
        # Obtener configuración actual
        optimal_config = self.get_optimal_refresh_interval(current_time)
        
        # Calcular tiempo transcurrido
        time_since_refresh = (current_time - last_refresh).total_seconds()
        required_interval = optimal_config['refresh_seconds']
        
        should_refresh = time_since_refresh >= required_interval
        
        refresh_info = {
            **optimal_config,
            'last_refresh': last_refresh,
            'time_since_refresh_minutes': time_since_refresh / 60,
            'required_interval_minutes': required_interval / 60,
            'should_refresh': should_refresh,
            'next_refresh_in_minutes': max(0, (required_interval - time_since_refresh) / 60)
        }
        
        return should_refresh, refresh_info
    
    def get_cache_status_report(self, last_refresh: datetime) -> str:
        """
        Genera un reporte legible del estado del caché adaptativo
        """
        should_refresh, info = self.should_refresh_cache(last_refresh)
        
        status = "🔄 REFRESH NEEDED" if should_refresh else "✅ CACHE FRESH"
        
        report = [
            f"{status} - Adaptive Cache Status",
            f"📅 Current period: {info['period_name']} ({info['priority']})",
            f"⏱️ Required interval: {info['required_interval_minutes']:.1f}min",
            f"🕐 Time since refresh: {info['time_since_refresh_minutes']:.1f}min",
        ]
        
        if not should_refresh:
            report.append(f"⏳ Next refresh in: {info['next_refresh_in_minutes']:.1f}min")
        
        return "\n".join(report)
    
    def get_daily_schedule_preview(self, target_date: datetime = None) -> str:
        """
        Muestra el horario adaptativo para un día específico
        """
        if target_date is None:
            target_date = datetime.now(self.market_tz)
            
        schedule = ["📅 ADAPTIVE CACHE SCHEDULE (EST/EDT)"]
        schedule.append("=" * 45)
        
        for period_name, config in self.market_periods.items():
            start = config['start'].strftime('%H:%M')
            end = config['end'].strftime('%H:%M')
            refresh = config['refresh_minutes']
            priority = config['priority']
            
            schedule.append(f"🕐 {start}-{end} | {period_name.upper()} ({priority}) | {refresh}min refresh")
        
        schedule.append("=" * 45)
        schedule.append(f"🌙 Off-hours: {self.default_refresh_minutes}min refresh")
        
        return "\n".join(schedule)

# Instancia global para uso en el sistema
adaptive_cache_manager = AdaptiveCacheManager()

def get_adaptive_refresh_interval() -> Dict[str, Any]:
    """Helper function para obtener el intervalo adaptativo actual"""
    return adaptive_cache_manager.get_optimal_refresh_interval()

def should_refresh_adaptive_cache(last_refresh: datetime) -> Tuple[bool, Dict[str, Any]]:
    """Helper function para verificar si debe refrescarse el caché"""
    return adaptive_cache_manager.should_refresh_cache(last_refresh)