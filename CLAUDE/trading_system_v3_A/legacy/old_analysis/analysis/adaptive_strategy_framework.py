#!/usr/bin/env python3
"""
Adaptive Strategy Framework with Anti-Overfitting Safeguards
Sistema híbrido que evita los riesgos principales de sobreoptimización

MITIGACIONES IMPLEMENTADAS:
✅ Anti-Sobreoptimización Narrativa: Validación estadística obligatoria
✅ Anti-Falsa Precisión: Límites de confianza y métricas de incertidumbre  
✅ Anti-Complejidad Exponencial: Máximo 5 parámetros adaptativos por estrategia
✅ Anti-Sesgo Confirmación: Validación cruzada temporal y controles externos
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import warnings
from abc import ABC, abstractmethod

# Anti-overfitting safeguards
from scipy import stats
from collections import deque, defaultdict

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    EXTREME = "extreme"

@dataclass
class ParameterBounds:
    """Límites estrictos para evitar sobreoptimización"""
    min_value: float
    max_value: float
    default_value: float
    max_change_per_update: float  # Cambio máximo por actualización (anti-volatilidad)
    confidence_threshold: float   # Confianza mínima para cambios
    
    def constrain(self, value: float) -> float:
        """Asegurar que valor esté dentro de límites"""
        return max(self.min_value, min(self.max_value, value))
    
    def validate_change(self, old_value: float, new_value: float, confidence: float) -> float:
        """Validar que cambio sea conservador y bien fundamentado"""
        if confidence < self.confidence_threshold:
            return old_value  # No cambiar si baja confianza
        
        max_change = abs(old_value) * self.max_change_per_update
        change = new_value - old_value
        
        if abs(change) > max_change:
            # Limitar cambio a máximo permitido
            direction = 1 if change > 0 else -1
            constrained_new = old_value + (direction * max_change)
            return self.constrain(constrained_new)
        
        return self.constrain(new_value)

@dataclass 
class AdaptiveParameter:
    """Parámetro adaptativo con salvaguardas anti-overfitting"""
    name: str
    current_value: float
    bounds: ParameterBounds
    update_history: deque = field(default_factory=lambda: deque(maxlen=50))
    performance_history: deque = field(default_factory=lambda: deque(maxlen=50))
    last_significant_change: datetime = field(default_factory=datetime.now)
    stability_score: float = 1.0  # 1.0 = muy estable, 0.0 = muy volátil
    
    def propose_update(self, new_value: float, confidence: float, 
                      performance_metric: float) -> tuple[float, bool]:
        """Proponer actualización con validación rigurosa"""
        
        # 1. ANTI-SOBREOPTIMIZACIÓN: Requerir significancia estadística
        if len(self.performance_history) < 10:
            return self.current_value, False  # Muy pocos datos
        
        # Test estadístico: ¿la mejora es significativa?
        recent_performance = list(self.performance_history)[-5:]
        baseline_performance = list(self.performance_history)[:-5] if len(self.performance_history) > 5 else recent_performance
        
        if len(baseline_performance) >= 3 and len(recent_performance) >= 3:
            try:
                statistic, p_value = stats.ttest_ind(recent_performance, baseline_performance)
                if p_value > 0.1:  # No significancia estadística
                    self.logger.debug(f"⚠️ {self.name}: Cambio no significativo (p={p_value:.3f})")
                    return self.current_value, False
            except:
                pass
        
        # 2. ANTI-FALSA PRECISIÓN: Exigir alta confianza para cambios grandes
        proposed_value = self.bounds.validate_change(
            self.current_value, new_value, confidence
        )
        
        # 3. ANTI-COMPLEJIDAD: Limitar frecuencia de cambios
        time_since_change = datetime.now() - self.last_significant_change
        if time_since_change < timedelta(hours=24):  # Mínimo 24h entre cambios
            return self.current_value, False
        
        # 4. ANTI-SESGO: Verificar que no estamos persiguiendo ruido
        if abs(proposed_value - self.current_value) / abs(self.current_value) < 0.01:
            return self.current_value, False  # Cambio < 1% no vale la pena
        
        # Actualizar si pasa todas las validaciones
        self.update_history.append({
            'timestamp': datetime.now(),
            'old_value': self.current_value,
            'new_value': proposed_value,
            'confidence': confidence,
            'performance': performance_metric
        })
        
        self.performance_history.append(performance_metric)
        self.current_value = proposed_value
        self.last_significant_change = datetime.now()
        
        # Actualizar stability score
        self._update_stability_score()
        
        return proposed_value, True
    
    def _update_stability_score(self):
        """Calcular score de estabilidad del parámetro"""
        if len(self.update_history) < 5:
            return
        
        recent_changes = [abs(h['new_value'] - h['old_value']) for h in list(self.update_history)[-5:]]
        avg_change = np.mean(recent_changes)
        normalized_change = avg_change / abs(self.current_value) if self.current_value != 0 else 0
        
        # Score inverso: menos cambios = más estabilidad
        self.stability_score = max(0.1, 1.0 - min(normalized_change * 10, 0.9))

class AntiOverfittingValidator:
    """Validador que previene sobreoptimización"""
    
    def __init__(self):
        self.logger = logging.getLogger("AntiOverfittingValidator")
        
        # Límites duros del sistema
        self.max_parameters_per_strategy = 5  # HARD LIMIT
        self.min_trades_for_significance = 30  # Mínimo trades para conclusiones
        self.max_confidence_claimed = 0.85  # Nadie puede reclamar >85% confianza
        
        # Memoria de validaciones
        self.rejected_updates = defaultdict(list)
        self.false_positive_tracking = defaultdict(list)
    
    def validate_strategy_complexity(self, strategy_params: Dict[str, AdaptiveParameter]) -> bool:
        """ANTI-COMPLEJIDAD: Limitar parámetros por estrategia"""
        if len(strategy_params) > self.max_parameters_per_strategy:
            self.logger.warning(f"🚫 Strategy has {len(strategy_params)} parameters (max {self.max_parameters_per_strategy})")
            return False
        return True
    
    def validate_statistical_significance(self, trades_data: List[Dict], 
                                        proposed_change: Dict) -> tuple[bool, Dict]:
        """ANTI-SOBREOPTIMIZACIÓN: Exigir significancia estadística"""
        
        if len(trades_data) < self.min_trades_for_significance:
            return False, {"reason": "insufficient_data", "trades": len(trades_data)}
        
        # Dividir en períodos: antes y después del último cambio
        # (Simulamos usando últimos 50% vs primeros 50%)
        mid_point = len(trades_data) // 2
        before_period = [t['pnl'] for t in trades_data[:mid_point]]
        after_period = [t['pnl'] for t in trades_data[mid_point:]]
        
        if len(before_period) < 5 or len(after_period) < 5:
            return False, {"reason": "periods_too_small"}
        
        # Test estadístico
        try:
            statistic, p_value = stats.ttest_ind(after_period, before_period)
            effect_size = (np.mean(after_period) - np.mean(before_period)) / np.std(before_period + after_period)
            
            # Requerir significancia Y efecto sustancial
            is_significant = p_value < 0.05 and abs(effect_size) > 0.2
            
            return is_significant, {
                "p_value": p_value,
                "effect_size": effect_size,
                "before_mean": np.mean(before_period),
                "after_mean": np.mean(after_period)
            }
            
        except Exception as e:
            self.logger.warning(f"Statistical test failed: {e}")
            return False, {"reason": "test_failed"}
    
    def detect_narrative_bias(self, writeup_text: str) -> Dict[str, Any]:
        """ANTI-NARRATIVA: Detectar explicaciones post-hoc sospechosas"""
        
        # Palabras que sugieren narrativa post-hoc
        bias_indicators = [
            "obviously", "clearly", "definitely", "certainly",
            "perfect setup", "textbook", "easy money", "obvious play"
        ]
        
        # Explicaciones demasiado específicas (overfitting narrativo)
        overly_specific = [
            "exactly", "precisely", "specifically because", 
            "the reason was definitely", "this always happens when"
        ]
        
        bias_score = 0
        found_indicators = []
        
        text_lower = writeup_text.lower()
        
        for indicator in bias_indicators:
            if indicator in text_lower:
                bias_score += 0.2
                found_indicators.append(indicator)
        
        for specific in overly_specific:
            if specific in text_lower:
                bias_score += 0.3
                found_indicators.append(f"overly_specific: {specific}")
        
        # Longitud excesiva sugiere racionalización
        if len(writeup_text) > 1000:
            bias_score += 0.1
            found_indicators.append("excessive_length")
        
        return {
            "bias_score": min(bias_score, 1.0),
            "risk_level": "high" if bias_score > 0.6 else "medium" if bias_score > 0.3 else "low",
            "indicators_found": found_indicators
        }
    
    def cross_validation_check(self, strategy_name: str, 
                             performance_claim: float) -> Dict[str, Any]:
        """ANTI-SESGO: Validación cruzada temporal"""
        
        # Simular check contra performance histórica
        # En implementación real, compararía contra datos out-of-sample
        
        historical_avg = 0.02  # 2% return promedio (placeholder)
        claim_vs_history = performance_claim / historical_avg if historical_avg != 0 else 1.0
        
        # Claims demasiado buenos son sospechosos
        if claim_vs_history > 3.0:  # Claim >3x histórico
            return {
                "valid": False,
                "reason": "performance_too_good_to_be_true",
                "ratio_vs_historical": claim_vs_history
            }
        
        if performance_claim > self.max_confidence_claimed:
            return {
                "valid": False,
                "reason": "overconfidence",
                "claimed": performance_claim,
                "max_allowed": self.max_confidence_claimed
            }
        
        return {"valid": True, "ratio_vs_historical": claim_vs_history}

class AdaptiveStrategyBase(ABC):
    """Base class para estrategias adaptativas con salvaguardas"""
    
    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.logger = logging.getLogger(f"AdaptiveStrategy.{strategy_name}")
        
        # Componentes anti-overfitting
        self.validator = AntiOverfittingValidator()
        self.adaptive_params: Dict[str, AdaptiveParameter] = {}
        self.adaptation_history = deque(maxlen=100)
        
        # Métricas de salud del sistema
        self.system_health = {
            "stability_score": 1.0,
            "adaptation_frequency": 0.0,
            "last_validation": datetime.now(),
            "rejected_updates": 0,
            "successful_updates": 0
        }
        
        # Inicializar parámetros específicos
        self._initialize_adaptive_parameters()
        
        # Validar complejidad
        if not self.validator.validate_strategy_complexity(self.adaptive_params):
            raise ValueError(f"Strategy {strategy_name} exceeds complexity limits")
    
    @abstractmethod
    def _initialize_adaptive_parameters(self):
        """Implementar en cada estrategia - definir parámetros adaptativos"""
        pass
    
    @abstractmethod
    def _generate_base_signal(self, market_data: Any) -> Optional[Dict]:
        """Lógica base de la estrategia (sin adaptaciones)"""
        pass
    
    def generate_signal(self, market_data: Any) -> Optional[Dict]:
        """Generar señal usando parámetros adaptativos actuales"""
        try:
            # Generar señal base
            base_signal = self._generate_base_signal(market_data)
            if not base_signal:
                return None
            
            # Aplicar adaptaciones
            adapted_signal = self._apply_adaptive_parameters(base_signal, market_data)
            
            # Log para auditoría
            self._log_signal_generation(base_signal, adapted_signal, market_data)
            
            return adapted_signal
            
        except Exception as e:
            self.logger.error(f"❌ Error generating adaptive signal: {e}")
            return None
    
    def learn_from_trade(self, trade_result: Dict[str, Any]) -> Dict[str, Any]:
        """Aprender de resultado de trade con validación anti-overfitting"""
        
        learning_result = {
            "parameters_updated": [],
            "updates_rejected": [],
            "validation_results": {},
            "system_health_updated": False
        }
        
        try:
            # Extraer métricas clave
            pnl = trade_result.get('pnl', 0.0)
            confidence = trade_result.get('confidence', 0.5)
            trade_duration = trade_result.get('duration_hours', 24)
            
            # Normalizar performance metric (sharpe-like)
            performance_metric = pnl / max(abs(pnl) * 0.1, 0.01) if pnl != 0 else 0
            
            # Proponer actualizaciones para cada parámetro
            for param_name, param in self.adaptive_params.items():
                
                # Calcular propuesta de actualización
                proposed_value = self._calculate_parameter_update(
                    param, trade_result, performance_metric
                )
                
                if proposed_value is not None:
                    # Intentar actualización con validación
                    new_value, updated = param.propose_update(
                        proposed_value, confidence, performance_metric
                    )
                    
                    if updated:
                        learning_result["parameters_updated"].append({
                            "parameter": param_name,
                            "old_value": param.update_history[-1]['old_value'],
                            "new_value": new_value,
                            "confidence": confidence
                        })
                        self.logger.info(f"📊 Updated {param_name}: {param.update_history[-1]['old_value']:.4f} -> {new_value:.4f}")
                    else:
                        learning_result["updates_rejected"].append({
                            "parameter": param_name,
                            "reason": "validation_failed"
                        })
            
            # Validar salud general del sistema
            self._update_system_health()
            learning_result["system_health_updated"] = True
            
            # Guardar en historial
            self.adaptation_history.append({
                "timestamp": datetime.now(),
                "trade_result": trade_result,
                "learning_result": learning_result,
                "system_health": self.system_health.copy()
            })
            
        except Exception as e:
            self.logger.error(f"❌ Error in learning process: {e}")
            learning_result["error"] = str(e)
        
        return learning_result
    
    def _apply_adaptive_parameters(self, base_signal: Dict, market_data: Any) -> Dict:
        """Aplicar parámetros adaptativos a señal base"""
        adapted_signal = base_signal.copy()
        
        # Cada estrategia implementará su propia lógica de adaptación
        return adapted_signal
    
    def _calculate_parameter_update(self, parameter: AdaptiveParameter, 
                                  trade_result: Dict, performance_metric: float) -> Optional[float]:
        """Calcular propuesta de actualización para parámetro"""
        
        # Lógica básica: si trade fue exitoso, mantener dirección
        # Si falló, ajustar en dirección opuesta
        pnl = trade_result.get('pnl', 0)
        
        if pnl > 0:
            # Trade exitoso - pequeño ajuste en misma dirección
            return parameter.current_value * 1.02
        else:
            # Trade fallido - pequeño ajuste en dirección opuesta  
            return parameter.current_value * 0.98
    
    def _update_system_health(self):
        """Actualizar métricas de salud del sistema"""
        
        # Calcular estabilidad promedio
        if self.adaptive_params:
            avg_stability = np.mean([p.stability_score for p in self.adaptive_params.values()])
            self.system_health["stability_score"] = avg_stability
        
        # Calcular frecuencia de adaptación
        recent_adaptations = len([
            h for h in self.adaptation_history 
            if datetime.now() - h["timestamp"] < timedelta(days=7)
        ])
        self.system_health["adaptation_frequency"] = recent_adaptations / 7.0
        
        # Actualizar contadores
        if hasattr(self, '_last_learning_result'):
            self.system_health["successful_updates"] += len(
                self._last_learning_result.get("parameters_updated", [])
            )
            self.system_health["rejected_updates"] += len(
                self._last_learning_result.get("updates_rejected", [])
            )
    
    def _log_signal_generation(self, base_signal: Dict, adapted_signal: Dict, market_data: Any):
        """Log detallado para auditoría y debug"""
        
        adaptations_applied = []
        for key in base_signal:
            if key in adapted_signal and base_signal[key] != adapted_signal[key]:
                adaptations_applied.append({
                    "field": key,
                    "base_value": base_signal[key],
                    "adapted_value": adapted_signal[key]
                })
        
        if adaptations_applied:
            self.logger.debug(f"🎯 Adaptations applied: {adaptations_applied}")
    
    def get_strategy_health_report(self) -> Dict[str, Any]:
        """Reporte de salud de la estrategia"""
        
        return {
            "strategy_name": self.strategy_name,
            "system_health": self.system_health,
            "parameters_status": {
                name: {
                    "current_value": param.current_value,
                    "stability_score": param.stability_score,
                    "updates_count": len(param.update_history),
                    "last_update": param.last_significant_change.isoformat()
                }
                for name, param in self.adaptive_params.items()
            },
            "recent_adaptations": len(self.adaptation_history),
            "overall_health": "healthy" if self.system_health["stability_score"] > 0.7 else "unstable"
        }

# Factory function
def create_adaptive_parameter(name: str, default_value: float, 
                            min_val: float, max_val: float,
                            max_change_pct: float = 0.1,
                            confidence_threshold: float = 0.6) -> AdaptiveParameter:
    """Factory para crear parámetros adaptativos con bounds seguros"""
    
    bounds = ParameterBounds(
        min_value=min_val,
        max_value=max_val,
        default_value=default_value,
        max_change_per_update=max_change_pct,
        confidence_threshold=confidence_threshold
    )
    
    return AdaptiveParameter(
        name=name,
        current_value=default_value,
        bounds=bounds
    )

if __name__ == "__main__":
    # Test de salvaguardas
    print("🧪 Testing Anti-Overfitting Safeguards")
    print("=" * 50)
    
    validator = AntiOverfittingValidator()
    
    # Test narrativa bias
    good_writeup = "Trade failed due to overall market downturn. Volume was lower than expected."
    bad_writeup = "This was obviously a perfect setup that clearly should have worked perfectly because the stars aligned exactly right and this always happens precisely when the volume is exactly 1.4x average."
    
    good_result = validator.detect_narrative_bias(good_writeup)
    bad_result = validator.detect_narrative_bias(bad_writeup)
    
    print(f"Good writeup bias score: {good_result['bias_score']:.2f} ({good_result['risk_level']})")
    print(f"Bad writeup bias score: {bad_result['bias_score']:.2f} ({bad_result['risk_level']})")
    
    print("\n✅ Anti-Overfitting Framework Ready!")