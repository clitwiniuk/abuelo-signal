#!/usr/bin/env python3
"""
Bias-Aware Trade Write-up System
Sistema de análisis post-trade con detección activa de sesgos y narrativas falsas

PREVIENE:
✅ Sobreoptimización Narrativa
✅ Falsa Precisión  
✅ Sesgo de Confirmación
✅ Racionalización Post-hoc
"""

import asyncio
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import re
from pathlib import Path

from analysis.adaptive_strategy_framework import AntiOverfittingValidator

class BiasType(Enum):
    CONFIRMATION = "confirmation_bias"
    HINDSIGHT = "hindsight_bias"
    NARRATIVE_FALLACY = "narrative_fallacy"
    OVERCONFIDENCE = "overconfidence_bias"
    CHERRY_PICKING = "cherry_picking"

@dataclass
class WriteUpQuality:
    """Métricas de calidad del análisis"""
    objectivity_score: float  # 0-1, qué tan objetivo es
    bias_risk: str           # "low", "medium", "high"
    evidence_quality: float  # 0-1, calidad de evidencia
    actionable_insights: int # Número de insights accionables
    statistical_validity: float  # 0-1, validez estadística
    
    def overall_score(self) -> float:
        """Score general de calidad"""
        return (self.objectivity_score * 0.3 + 
                self.evidence_quality * 0.4 + 
                self.statistical_validity * 0.3)

@dataclass
class TradeWriteUpV2:
    """Trade Write-up con detección de sesgos integrada"""
    
    # Identificación básica
    trade_id: str
    timestamp: datetime
    symbol: str
    strategy_used: str
    
    # Datos objetivos (no opiniones)
    entry_price: float
    exit_price: float
    pnl: float
    duration_minutes: int
    volume_at_entry: int
    volume_avg_comparison: float  # vs promedio
    
    # Contexto verificable
    market_conditions: Dict[str, float]  # SPY, VIX, etc.
    time_of_entry: str  # "09:45", "14:30", etc.
    news_events: List[str]  # Solo eventos verificables
    
    # Análisis objetivo (medible)
    signal_strength: float   # Basado en indicadores técnicos
    risk_reward_planned: float
    risk_reward_actual: float
    
    # OBLIGATORIO: Auto-evaluación de sesgos
    potential_biases_present: List[BiasType]
    confidence_in_analysis: float  # 0-1, forzar humildad
    uncertainty_factors: List[str]  # Qué NO sabemos
    
    # Lecciones (limitadas y específicas)
    max_lessons: int = 3  # HARD LIMIT para evitar narrativas largas
    lessons_learned: List[str] = field(default_factory=list)
    
    # Validación externa
    quality_metrics: Optional[WriteUpQuality] = None
    validation_flags: List[str] = field(default_factory=list)

class BiasDetector:
    """Detector avanzado de sesgos cognitivos en análisis"""
    
    def __init__(self):
        self.logger = logging.getLogger("BiasDetector")
        
        # Patrones de sesgos
        self.bias_patterns = {
            BiasType.CONFIRMATION: [
                r"as expected", r"obviously", r"clearly shows", 
                r"confirms my thesis", r"validates the approach"
            ],
            BiasType.HINDSIGHT: [
                r"should have seen", r"it was obvious", r"in retrospect",
                r"clearly going to happen", r"saw it coming"
            ],
            BiasType.NARRATIVE_FALLACY: [
                r"the reason was", r"this happened because", r"clearly caused by",
                r"the market realized", r"investors understood", r"it was about"
            ],
            BiasType.OVERCONFIDENCE: [
                r"definitely", r"certainly", r"without a doubt", 
                r"guaranteed", r"always works", r"never fails"
            ],
            BiasType.CHERRY_PICKING: [
                r"except for", r"ignoring", r"not counting",
                r"aside from", r"excluding the"
            ]
        }
        
        # Palabras de incertidumbre (buenas)
        self.uncertainty_indicators = [
            "might", "could", "possibly", "uncertain", "unclear",
            "unknown factors", "market randomness", "unpredictable"
        ]
    
    def analyze_text_for_bias(self, text: str) -> Dict[BiasType, float]:
        """Analizar texto para detectar sesgos"""
        
        bias_scores = {}
        text_lower = text.lower()
        
        for bias_type, patterns in self.bias_patterns.items():
            score = 0
            matches = []
            
            for pattern in patterns:
                matches_found = re.findall(pattern, text_lower)
                score += len(matches_found) * 0.2
                matches.extend(matches_found)
            
            # Penalizar si no hay indicadores de incertidumbre
            uncertainty_count = sum(1 for indicator in self.uncertainty_indicators if indicator in text_lower)
            if uncertainty_count == 0 and len(text) > 200:
                score += 0.3  # Penalización por overconfidence
            
            bias_scores[bias_type] = min(score, 1.0)
        
        return bias_scores
    
    def evaluate_writeup_quality(self, writeup: TradeWriteUpV2) -> WriteUpQuality:
        """Evaluar calidad general del write-up"""
        
        # Combinar todo el texto analizable
        analysis_text = " ".join([
            " ".join(writeup.lessons_learned),
            " ".join(writeup.uncertainty_factors),
            f"confidence: {writeup.confidence_in_analysis}"
        ])
        
        # Detectar sesgos
        bias_scores = self.analyze_text_for_bias(analysis_text)
        max_bias_score = max(bias_scores.values()) if bias_scores else 0
        
        # Objectivity score (inverso del bias máximo)
        objectivity_score = max(0.1, 1.0 - max_bias_score)
        
        # Evidence quality (basado en datos vs opiniones)
        evidence_score = self._calculate_evidence_quality(writeup)
        
        # Statistical validity
        statistical_score = self._calculate_statistical_validity(writeup)
        
        # Riesgo de bias
        if max_bias_score > 0.7:
            bias_risk = "high"
        elif max_bias_score > 0.4:
            bias_risk = "medium"  
        else:
            bias_risk = "low"
        
        # Insights accionables
        actionable_count = len([lesson for lesson in writeup.lessons_learned 
                              if any(word in lesson.lower() for word in 
                                   ["next time", "adjust", "change", "improve", "avoid"])])
        
        return WriteUpQuality(
            objectivity_score=objectivity_score,
            bias_risk=bias_risk,
            evidence_quality=evidence_score,
            actionable_insights=actionable_count,
            statistical_validity=statistical_score
        )
    
    def _calculate_evidence_quality(self, writeup: TradeWriteUpV2) -> float:
        """Calcular calidad de evidencia (datos vs opiniones)"""
        
        evidence_points = 0
        
        # Puntos por datos objetivos presentes
        if writeup.volume_avg_comparison != 0:
            evidence_points += 0.2
        if writeup.market_conditions:
            evidence_points += 0.2
        if writeup.signal_strength != 0:
            evidence_points += 0.2
        if writeup.uncertainty_factors:
            evidence_points += 0.2  # Reconocer incertidumbre es bueno
        
        # Penalizar lecciones vagas
        vague_lessons = sum(1 for lesson in writeup.lessons_learned 
                           if len(lesson.split()) < 5)  # Muy cortas
        evidence_points -= vague_lessons * 0.1
        
        return max(0.1, min(1.0, evidence_points))
    
    def _calculate_statistical_validity(self, writeup: TradeWriteUpV2) -> float:
        """Evaluar validez estadística del análisis"""
        
        validity_score = 0.5  # Base neutral
        
        # Bonificar reconocimiento de limitaciones
        if writeup.uncertainty_factors:
            validity_score += 0.2
        
        # Bonificar confianza moderada (ni muy alta ni muy baja)
        if 0.3 <= writeup.confidence_in_analysis <= 0.7:
            validity_score += 0.2
        else:
            validity_score -= 0.1  # Penalizar over/under confidence
        
        # Penalizar análisis demasiado largos (señal de racionalización)
        total_text_length = sum(len(lesson) for lesson in writeup.lessons_learned)
        if total_text_length > 500:
            validity_score -= 0.2
        
        return max(0.1, min(1.0, validity_score))

class ObjectiveWriteUpGenerator:
    """Generador de write-ups objetivos con anti-sesgos"""
    
    def __init__(self):
        self.logger = logging.getLogger("ObjectiveWriteUpGenerator")
        self.bias_detector = BiasDetector()
        self.validator = AntiOverfittingValidator()
        
        # Templates objetivos
        self.objective_templates = {
            "market_context": "Market conditions: SPY {spy_change:+.1%}, VIX {vix_level:.1f}",
            "volume_analysis": "Volume: {volume_ratio:.1f}x average ({volume} vs {avg_volume})",
            "timing_analysis": "Entry time: {entry_time}, duration: {duration_hours:.1f}h",
            "performance": "P&L: ${pnl:+.2f} ({pnl_pct:+.1%}), R:R planned {planned_rr:.1f}, actual {actual_rr:.1f}"
        }
    
    async def generate_objective_writeup(self, trade_data: Dict[str, Any]) -> TradeWriteUpV2:
        """Generar write-up objetivo con mínimo sesgo"""
        
        try:
            # Extraer datos objetivos
            writeup = TradeWriteUpV2(
                trade_id=trade_data.get('trade_id', f"trade_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                timestamp=datetime.now(),
                symbol=trade_data.get('symbol', ''),
                strategy_used=trade_data.get('strategy', ''),
                
                # Datos numéricos verificables
                entry_price=trade_data.get('entry_price', 0.0),
                exit_price=trade_data.get('exit_price', 0.0),
                pnl=trade_data.get('pnl', 0.0),
                duration_minutes=trade_data.get('duration_minutes', 0),
                volume_at_entry=trade_data.get('volume', 0),
                volume_avg_comparison=trade_data.get('volume_ratio', 1.0),
                
                # Contexto medible
                market_conditions={
                    'spy_change': trade_data.get('spy_change', 0.0),
                    'vix_level': trade_data.get('vix_level', 20.0)
                },
                time_of_entry=trade_data.get('entry_time', ''),
                news_events=trade_data.get('news_events', []),
                
                # Métricas objetivas
                signal_strength=trade_data.get('signal_strength', 0.5),
                risk_reward_planned=trade_data.get('planned_rr', 0.0),
                risk_reward_actual=trade_data.get('actual_rr', 0.0),
                
                # Anti-sesgo: forzar reconocimiento de limitaciones
                potential_biases_present=await self._identify_potential_biases(trade_data),
                confidence_in_analysis=min(0.8, trade_data.get('confidence', 0.5)),  # Cap at 80%
                uncertainty_factors=await self._identify_uncertainty_factors(trade_data),
                
                # Lecciones limitadas y específicas
                lessons_learned=await self._generate_objective_lessons(trade_data)
            )
            
            # Validar calidad
            quality = self.bias_detector.evaluate_writeup_quality(writeup)
            writeup.quality_metrics = quality
            
            # Añadir flags de validación si hay problemas
            if quality.bias_risk == "high":
                writeup.validation_flags.append("HIGH_BIAS_RISK")
            if quality.objectivity_score < 0.5:
                writeup.validation_flags.append("LOW_OBJECTIVITY")
            if quality.statistical_validity < 0.4:
                writeup.validation_flags.append("WEAK_STATISTICAL_BASIS")
            
            self.logger.info(f"📝 Generated writeup for {writeup.symbol}: Quality={quality.overall_score():.2f}, Bias Risk={quality.bias_risk}")
            
            return writeup
            
        except Exception as e:
            self.logger.error(f"❌ Error generating writeup: {e}")
            raise
    
    async def _identify_potential_biases(self, trade_data: Dict) -> List[BiasType]:
        """Identificar sesgos que podrían estar presentes"""
        
        potential_biases = []
        
        # Si el trade fue muy exitoso, riesgo de overconfidence
        pnl = trade_data.get('pnl', 0)
        if abs(pnl) > trade_data.get('typical_pnl', 100):
            potential_biases.append(BiasType.OVERCONFIDENCE)
        
        # Si fue muy malo, riesgo de hindsight bias
        if pnl < 0 and abs(pnl) > trade_data.get('typical_loss', 50):
            potential_biases.append(BiasType.HINDSIGHT)
        
        # Siempre hay riesgo de narrative fallacy
        potential_biases.append(BiasType.NARRATIVE_FALLACY)
        
        return potential_biases
    
    async def _identify_uncertainty_factors(self, trade_data: Dict) -> List[str]:
        """Identificar factores de incertidumbre (obligatorio)"""
        
        uncertainties = [
            "Market microstructure effects unknown",
            "Other participants' motivations unclear", 
            "Macro event timing unpredictable"
        ]
        
        # Añadir incertidumbres específicas
        if trade_data.get('volume', 0) < 1000:
            uncertainties.append("Low volume - price action may be random")
        
        if not trade_data.get('news_events'):
            uncertainties.append("No clear fundamental catalyst")
        
        # Máximo 5 incertidumbres para evitar lista infinita
        return uncertainties[:5]
    
    async def _generate_objective_lessons(self, trade_data: Dict) -> List[str]:
        """Generar lecciones objetivas y accionables"""
        
        lessons = []
        pnl = trade_data.get('pnl', 0)
        
        # Lección basada en resultado
        if pnl > 0:
            lessons.append(f"Entry timing worked - consider similar setups at {trade_data.get('entry_time', 'unknown time')}")
        else:
            lessons.append(f"Review entry criteria - signal strength was {trade_data.get('signal_strength', 0):.1f}")
        
        # Lección basada en execution
        planned_rr = trade_data.get('planned_rr', 0)
        actual_rr = trade_data.get('actual_rr', 0)
        if abs(actual_rr - planned_rr) > 0.5:
            lessons.append("Improve trade management - R:R deviated significantly from plan")
        
        # Lección basada en contexto
        volume_ratio = trade_data.get('volume_ratio', 1.0)
        if volume_ratio < 0.8:
            lessons.append("Consider higher volume threshold - this was below average volume")
        
        # Limitar a máximo 3 lecciones
        return lessons[:3]

class BiasAwareAnalysisEngine:
    """Motor principal que combina write-ups con análisis adaptativo"""
    
    def __init__(self):
        self.logger = logging.getLogger("BiasAwareAnalysisEngine")
        self.writeup_generator = ObjectiveWriteUpGenerator()
        self.writeup_history = []
        
        # Configuración anti-overfitting
        self.min_trades_for_pattern = 10
        self.max_confidence_ever = 0.85
        self.quality_threshold = 0.6
    
    async def analyze_trade_with_safeguards(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Análisis completo con todas las salvaguardas"""
        
        analysis_result = {
            "writeup": None,
            "adaptive_insights": {},
            "safeguard_results": {},
            "recommendations": [],
            "system_health": "unknown"
        }
        
        try:
            # 1. Generar write-up objetivo
            writeup = await self.writeup_generator.generate_objective_writeup(trade_data)
            analysis_result["writeup"] = writeup
            
            # 2. Validar calidad
            if writeup.quality_metrics.overall_score() < self.quality_threshold:
                analysis_result["recommendations"].append(
                    f"⚠️ Analysis quality low ({writeup.quality_metrics.overall_score():.2f})"
                )
            
            # 3. Extraer insights adaptativos (solo si calidad suficiente)
            if writeup.quality_metrics.overall_score() >= self.quality_threshold:
                adaptive_insights = await self._extract_adaptive_insights(writeup, trade_data)
                analysis_result["adaptive_insights"] = adaptive_insights
            
            # 4. Validar contra overfitting
            safeguard_results = await self._run_safeguard_checks(writeup, trade_data)
            analysis_result["safeguard_results"] = safeguard_results
            
            # 5. Generar recomendaciones finales
            recommendations = await self._generate_final_recommendations(writeup, safeguard_results)
            analysis_result["recommendations"].extend(recommendations)
            
            # 6. Evaluar salud del sistema
            system_health = self._evaluate_system_health()
            analysis_result["system_health"] = system_health
            
            # Guardar en historia
            self.writeup_history.append(writeup)
            if len(self.writeup_history) > 100:  # Límite de memoria
                self.writeup_history.pop(0)
            
        except Exception as e:
            self.logger.error(f"❌ Error in bias-aware analysis: {e}")
            analysis_result["error"] = str(e)
        
        return analysis_result
    
    async def _extract_adaptive_insights(self, writeup: TradeWriteUpV2, trade_data: Dict) -> Dict[str, Any]:
        """Extraer insights para adaptación de estrategias"""
        
        insights = {}
        
        # Solo generar insights si hay evidencia sólida
        if writeup.quality_metrics.evidence_quality > 0.6:
            
            # Insight sobre timing
            if writeup.time_of_entry:
                insights["timing_preference"] = {
                    "time_of_day": writeup.time_of_entry,
                    "success": writeup.pnl > 0,
                    "confidence": writeup.confidence_in_analysis * 0.8  # Reducir confianza
                }
            
            # Insight sobre volumen
            if writeup.volume_avg_comparison != 1.0:
                insights["volume_threshold"] = {
                    "ratio_used": writeup.volume_avg_comparison,
                    "success": writeup.pnl > 0,
                    "suggested_adjustment": 0.05 if writeup.pnl > 0 else -0.05
                }
        
        return insights
    
    async def _run_safeguard_checks(self, writeup: TradeWriteUpV2, trade_data: Dict) -> Dict[str, Any]:
        """Ejecutar todas las validaciones anti-overfitting"""
        
        results = {}
        
        # Check 1: Bias detection
        results["bias_analysis"] = {
            "risk_level": writeup.quality_metrics.bias_risk,
            "objectivity_score": writeup.quality_metrics.objectivity_score,
            "validation_flags": writeup.validation_flags
        }
        
        # Check 2: Statistical significance (simulado)
        results["statistical_check"] = {
            "sufficient_data": len(self.writeup_history) >= self.min_trades_for_pattern,
            "confidence_reasonable": writeup.confidence_in_analysis <= self.max_confidence_ever
        }
        
        # Check 3: Complexity check
        results["complexity_check"] = {
            "lessons_count": len(writeup.lessons_learned),
            "within_limits": len(writeup.lessons_learned) <= writeup.max_lessons
        }
        
        return results
    
    async def _generate_final_recommendations(self, writeup: TradeWriteUpV2, 
                                           safeguard_results: Dict) -> List[str]:
        """Generar recomendaciones finales basadas en análisis"""
        
        recommendations = []
        
        # Basado en calidad
        if writeup.quality_metrics.overall_score() > 0.8:
            recommendations.append("✅ High-quality analysis - insights can be trusted")
        elif writeup.quality_metrics.bias_risk == "high":
            recommendations.append("⚠️ High bias risk - treat insights with caution")
        
        # Basado en safeguards
        if not safeguard_results["statistical_check"]["sufficient_data"]:
            recommendations.append("📊 Insufficient data for reliable conclusions")
        
        if writeup.validation_flags:
            recommendations.append(f"🚫 Validation issues: {', '.join(writeup.validation_flags)}")
        
        return recommendations
    
    def _evaluate_system_health(self) -> str:
        """Evaluar salud general del sistema de análisis"""
        
        if len(self.writeup_history) < 5:
            return "initializing"
        
        # Evaluar calidad promedio reciente
        recent_quality = [w.quality_metrics.overall_score() 
                         for w in self.writeup_history[-10:]
                         if w.quality_metrics]
        
        if not recent_quality:
            return "unknown"
        
        avg_quality = np.mean(recent_quality)
        
        if avg_quality > 0.7:
            return "healthy"
        elif avg_quality > 0.5:
            return "moderate"
        else:
            return "degraded"

# Factory function
async def create_bias_aware_analyzer() -> BiasAwareAnalysisEngine:
    """Factory para crear analizador con todas las salvaguardas"""
    return BiasAwareAnalysisEngine()

if __name__ == "__main__":
    # Test del sistema anti-sesgos
    print("🧪 Testing Bias-Aware Analysis System")
    print("=" * 50)
    
    # Test datos
    good_trade_data = {
        'symbol': 'AAPL',
        'pnl': 150.0,
        'entry_price': 180.0,
        'exit_price': 182.5,
        'volume_ratio': 1.3,
        'signal_strength': 0.7,
        'confidence': 0.6
    }
    
    bad_trade_data = {
        'symbol': 'XYZ',
        'pnl': -75.0,
        'entry_price': 50.0,
        'exit_price': 48.5,
        'volume_ratio': 0.8,
        'signal_strength': 0.3,
        'confidence': 0.9  # Overconfident
    }
    
    bias_detector = BiasDetector()
    
    # Test bias detection
    biased_text = "This trade was obviously going to work perfectly because the setup was clearly bullish and definitely confirmed my thesis"
    objective_text = "Trade failed, possibly due to low volume. Uncertain if pattern will repeat. Market conditions unclear."
    
    biased_score = bias_detector.analyze_text_for_bias(biased_text)
    objective_score = bias_detector.analyze_text_for_bias(objective_text)
    
    print(f"Biased text max score: {max(biased_score.values()):.2f}")
    print(f"Objective text max score: {max(objective_score.values()):.2f}")
    
    print("\n✅ Bias-Aware Analysis System Ready!")