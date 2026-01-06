#!/usr/bin/env python3
"""
Volume Requirement Manager - Interface para estrategias
Reemplaza todos los métodos de volumen hardcodeados con ML dinámico
"""

import logging
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass

from core.ml_volume_engine import MLVolumeEngine, create_market_context

@dataclass
class VolumeCheckResult:
    """Resultado de verificación de volumen"""
    meets_requirement: bool
    required_volume: float
    actual_volume: float
    strategy: str
    confidence: float = 0.0
    reason: str = ""

class VolumeRequirementManager:
    """
    Manager centralizado para requerimientos de volumen
    Reemplaza los métodos obsoletos scattered en las estrategias
    """
    
    def __init__(self, adapter=None):
        self.adapter = adapter
        self.logger = logging.getLogger(__name__)
        self._fallback_requirements = {
            'macdv_smallcaps': 1.2,
            'daily_plays': 0.8,
            'gap_go': 1.5,
            'orb': 1.3,
            'volume_breakout': 2.0,
            'pmh_breakout': 1.8,
            'catalyst_momentum': 1.6,
            'vwap_reclaim': 1.4,
            'eod_momentum': 1.5,
            'vcp': 1.3,
            'vwap_smallcaps': 1.4,
            'volume_momentum': 1.7,
            'explosive_volume': 2.5,
            'hybrid_explosion': 1.8
        }
        
    def check_volume_requirement(
        self, 
        strategy: str, 
        ticker_data: dict,
        current_volume: float = None
    ) -> VolumeCheckResult:
        """
        Verifica si un ticker cumple los requerimientos de volumen para una estrategia
        
        Args:
            strategy: Nombre de la estrategia
            ticker_data: Datos del ticker (price, sector, market_cap, etc.)
            current_volume: Volumen actual vs promedio (ratio)
            
        Returns:
            VolumeCheckResult con el resultado de la verificación
        """
        try:
            # Obtener volumen actual del ticker_data si no se proporciona
            if current_volume is None:
                current_volume = ticker_data.get('ratio_vol', ticker_data.get('volume_ratio', 1.0))
            
            # Obtener requerimiento dinámico ML
            required_volume = self._get_volume_requirement(strategy, ticker_data)
            
            # Verificar si cumple el requerimiento
            meets_requirement = current_volume >= required_volume
            
            # Calcular confidence basado en qué tan por encima/debajo está
            if meets_requirement:
                confidence = min(1.0, current_volume / required_volume)
            else:
                confidence = current_volume / required_volume
            
            # Razón del resultado
            if meets_requirement:
                reason = f"Volume {current_volume:.2f}x exceeds requirement {required_volume:.2f}x"
            else:
                reason = f"Volume {current_volume:.2f}x below requirement {required_volume:.2f}x"
            
            result = VolumeCheckResult(
                meets_requirement=meets_requirement,
                required_volume=required_volume,
                actual_volume=current_volume,
                strategy=strategy,
                confidence=confidence,
                reason=reason
            )
            
            self.logger.debug(
                f"🔍 {strategy} volume check: "
                f"{'✅' if meets_requirement else '❌'} "
                f"{current_volume:.2f}x vs {required_volume:.2f}x required"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error checking volume requirement: {e}")
            # Fallback seguro
            fallback_req = self._fallback_requirements.get(strategy, 1.5)
            return VolumeCheckResult(
                meets_requirement=current_volume >= fallback_req if current_volume else False,
                required_volume=fallback_req,
                actual_volume=current_volume or 0.0,
                strategy=strategy,
                confidence=0.5,
                reason=f"Fallback requirement used due to error: {e}"
            )
    
    def _get_volume_requirement(self, strategy: str, ticker_data: dict) -> float:
        """
        Obtiene el requerimiento de volumen para una estrategia usando ML
        """
        # Usar ML engine del adapter si está disponible
        if self.adapter and hasattr(self.adapter, 'get_dynamic_volume_requirement'):
            return self.adapter.get_dynamic_volume_requirement(strategy, ticker_data)
        
        # Fallback a valores predeterminados
        return self._fallback_requirements.get(strategy, 1.5)
    
    def get_volume_multiplier_for_time(self, base_requirement: float, current_time: datetime = None) -> float:
        """
        OBSOLETE: Este método era usado para multipliers de tiempo
        Ahora el ML engine considera el tiempo automáticamente
        Mantenido para compatibilidad backwards
        """
        self.logger.warning(
            "⚠️ get_volume_multiplier_for_time is OBSOLETE - "
            "ML system handles time-based adjustments automatically"
        )
        return base_requirement
    
    def is_volume_sufficient(self, strategy: str, ticker_data: dict, volume_ratio: float) -> bool:
        """
        Método simple para verificar si el volumen es suficiente
        Wrapper para check_volume_requirement
        """
        result = self.check_volume_requirement(strategy, ticker_data, volume_ratio)
        return result.meets_requirement
    
    def get_strategy_volume_stats(self, strategy: str) -> Dict[str, float]:
        """
        Obtiene estadísticas de volumen para una estrategia
        """
        fallback = self._fallback_requirements.get(strategy, 1.5)
        
        return {
            'fallback_requirement': fallback,
            'min_safe_volume': 0.2,
            'max_safe_volume': 3.5,
            'typical_volume': fallback * 1.2,
            'system_type': 'ML_DYNAMIC'
        }
    
    def log_volume_decision(self, result: VolumeCheckResult, ticker: str = "UNKNOWN"):
        """
        Log detallado de decisiones de volumen para análisis
        """
        status = "✅ PASS" if result.meets_requirement else "❌ FAIL"
        self.logger.info(
            f"📊 VOLUME CHECK {status} | "
            f"{ticker} | {result.strategy} | "
            f"Actual: {result.actual_volume:.2f}x | "
            f"Required: {result.required_volume:.2f}x | "
            f"Confidence: {result.confidence:.2f} | "
            f"Reason: {result.reason}"
        )

# Global instance para backward compatibility
_global_volume_manager = None

def get_global_volume_manager(adapter=None) -> VolumeRequirementManager:
    """
    Obtiene la instancia global del volume manager
    """
    global _global_volume_manager
    if _global_volume_manager is None:
        _global_volume_manager = VolumeRequirementManager(adapter)
    elif adapter is not None and _global_volume_manager.adapter is None:
        _global_volume_manager.adapter = adapter
    return _global_volume_manager

# Funciones de conveniencia para migration desde métodos obsoletos
def check_volume_requirement(strategy: str, ticker_data: dict, volume_ratio: float, adapter=None) -> bool:
    """Función de conveniencia para verificación rápida de volumen"""
    manager = get_global_volume_manager(adapter)
    result = manager.check_volume_requirement(strategy, ticker_data, volume_ratio)
    return result.meets_requirement

def get_dynamic_volume_requirement(strategy: str, ticker_data: dict, adapter=None) -> float:
    """Función de conveniencia para obtener requerimiento dinámico"""
    manager = get_global_volume_manager(adapter)
    return manager._get_volume_requirement(strategy, ticker_data)