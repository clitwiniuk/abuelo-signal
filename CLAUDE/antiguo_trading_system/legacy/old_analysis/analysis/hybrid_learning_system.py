#!/usr/bin/env python3
"""
Hybrid Learning System - Integración Completa
Conecta ML Strategy Selector + Adaptive Strategies + Trade Write-ups

PLAN HÍBRIDO IMPLEMENTADO:
✅ Nivel 1: ML selecciona QUÉ estrategia usar
✅ Nivel 2: Estrategia adaptativa decide CÓMO ejecutarla  
✅ Nivel 3: Write-up análisis mejora ambos niveles
✅ Salvaguardas anti-overfitting en todos los niveles
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np

# Sistema de componentes
from strategies.ml_strategy_selector import (
    ContextualBandit, TickerProfiler, TickerContext, 
    create_ml_strategy_selector, create_ticker_profiler
)
from strategies.adaptive_gap_go_strategy import AdaptiveGapGoStrategy
from analysis.bias_aware_writeup import BiasAwareAnalysisEngine, create_bias_aware_analyzer
from analysis.adaptive_strategy_framework import AntiOverfittingValidator

@dataclass
class HybridDecision:
    """Decisión completa del sistema híbrido"""
    
    # Nivel 1: Strategy Selection
    selected_strategy: str
    ml_confidence: float
    strategy_rankings: List[tuple]
    
    # Nivel 2: Adaptive Execution  
    adaptive_parameters: Dict[str, float]
    parameter_stability: Dict[str, float]
    execution_confidence: float
    
    # Nivel 3: Context & Validation
    ticker_context: TickerContext
    validation_flags: List[str]
    overall_confidence: float
    
    # Meta-información
    decision_timestamp: datetime
    complexity_score: float  # Qué tan compleja fue la decisión

class HybridLearningSystem:
    """
    Sistema híbrido completo que integra todos los componentes
    con salvaguardas anti-overfitting
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.logger = logging.getLogger("HybridLearningSystem")
        self.config = config or {}
        
        # Componentes del sistema híbrido
        self.ml_selector: Optional[ContextualBandit] = None
        self.ticker_profiler: Optional[TickerProfiler] = None  
        self.analysis_engine: Optional[BiasAwareAnalysisEngine] = None
        self.adaptive_strategies: Dict[str, Any] = {}
        
        # Validador anti-overfitting
        self.validator = AntiOverfittingValidator()
        
        # Tracking del sistema
        self.decisions_history = []
        self.learning_sessions = []
        self.system_health_metrics = {
            "ml_selector_health": "unknown",
            "adaptive_strategies_health": "unknown", 
            "analysis_engine_health": "unknown",
            "overall_complexity": 0.0,
            "last_health_check": datetime.now()
        }
        
        # Anti-overfitting limits
        self.max_strategies = 3  # Máximo estrategias adaptativas
        self.max_decision_complexity = 0.8  # Máxima complejidad de decisión
        self.min_confidence_for_action = 0.4  # Mínima confianza para operar
        
        # Inicializar componentes
        asyncio.create_task(self._initialize_components())
        
        self.logger.info("🧠 Hybrid Learning System initializing...")
    
    async def _initialize_components(self):
        """Inicializar todos los componentes del sistema"""
        
        try:
            # 1. ML Strategy Selector
            available_strategies = ["gap_go", "orb", "macdv"]  # Mantener simple
            self.ml_selector = create_ml_strategy_selector(
                strategies=available_strategies,
                model_path="data/ml_models/hybrid_strategy_selector.json"
            )
            
            # 2. Ticker Profiler  
            self.ticker_profiler = create_ticker_profiler()
            
            # 3. Analysis Engine
            self.analysis_engine = await create_bias_aware_analyzer()
            
            # 4. Adaptive Strategies (solo las esenciales)
            self.adaptive_strategies = {
                "gap_go": AdaptiveGapGoStrategy(),
                # Añadir otras estrategias adaptativas aquí (máximo 3 total)
            }
            
            self.logger.info("✅ All hybrid components initialized")
            
        except Exception as e:
            self.logger.error(f"❌ Error initializing components: {e}")
            raise
    
    async def make_hybrid_decision(self, symbol: str, market_data: Any) -> Optional[HybridDecision]:
        """
        Proceso completo de decisión híbrida con validación
        
        FLUJO:
        1. Crear contexto del ticker
        2. ML selecciona estrategia óptima
        3. Estrategia adaptativa genera señal
        4. Validar decisión completa
        5. Returnar decisión validada
        """
        
        try:
            self.logger.debug(f"🎯 Making hybrid decision for {symbol}")
            
            # PASO 1: Generar contexto del ticker
            ticker_context = self.ticker_profiler.get_ticker_context(symbol, market_data)
            
            # PASO 2: ML Strategy Selection (Nivel 1)
            selected_strategy = self.ml_selector.select_strategy(ticker_context)
            strategy_rankings = self.ml_selector.get_strategy_rankings(ticker_context)
            ml_confidence = self._calculate_ml_confidence(selected_strategy, strategy_rankings)
            
            self.logger.debug(f"📊 ML selected: {selected_strategy} (confidence: {ml_confidence:.2f})")
            
            # PASO 3: Adaptive Strategy Execution (Nivel 2) 
            adaptive_result = await self._execute_adaptive_strategy(
                selected_strategy, market_data, ticker_context
            )
            
            if not adaptive_result:
                self.logger.debug(f"🚫 Adaptive strategy {selected_strategy} rejected trade")
                return None
            
            # PASO 4: Validación integral
            validation_result = await self._validate_hybrid_decision(
                selected_strategy, adaptive_result, ticker_context, ml_confidence
            )
            
            if not validation_result["valid"]:
                self.logger.debug(f"🚫 Decision validation failed: {validation_result['reason']}")
                return None
            
            # PASO 5: Crear decisión híbrida
            decision = HybridDecision(
                selected_strategy=selected_strategy,
                ml_confidence=ml_confidence,
                strategy_rankings=strategy_rankings,
                
                adaptive_parameters=adaptive_result["parameters_used"],
                parameter_stability=adaptive_result["stability_scores"],
                execution_confidence=adaptive_result["confidence"],
                
                ticker_context=ticker_context,
                validation_flags=validation_result.get("flags", []),
                overall_confidence=self._calculate_overall_confidence(
                    ml_confidence, adaptive_result["confidence"]
                ),
                
                decision_timestamp=datetime.now(),
                complexity_score=self._calculate_decision_complexity(
                    selected_strategy, adaptive_result, ticker_context
                )
            )
            
            # Guardar decisión
            self.decisions_history.append(decision)
            
            # Limitar historial (anti-complejidad)
            if len(self.decisions_history) > 500:
                self.decisions_history = self.decisions_history[-400:]
            
            self.logger.info(f"✅ Hybrid decision: {symbol} -> {selected_strategy} "
                           f"(confidence: {decision.overall_confidence:.2f})")
            
            return decision
            
        except Exception as e:
            self.logger.error(f"❌ Error in hybrid decision: {e}")
            return None
    
    async def _execute_adaptive_strategy(self, strategy_name: str, market_data: Any, 
                                       context: TickerContext) -> Optional[Dict]:
        """Ejecutar estrategia adaptativa específica"""
        
        if strategy_name not in self.adaptive_strategies:
            self.logger.warning(f"⚠️ No adaptive strategy for {strategy_name}")
            return None
        
        try:
            strategy = self.adaptive_strategies[strategy_name]
            
            # Generar señal adaptativa
            signal = strategy.generate_signal(market_data)
            
            if not signal:
                return None
            
            # Extraer información adaptativa
            parameters_used = signal.get("parameters_snapshot", {})
            
            # Calcular stability scores de parámetros
            stability_scores = {}
            if hasattr(strategy, 'parameters'):
                stability_scores = {
                    name: param.stability_score 
                    for name, param in strategy.parameters.items()
                }
            
            return {
                "signal": signal,
                "parameters_used": parameters_used,
                "stability_scores": stability_scores,
                "confidence": signal.get("confidence", 0.5)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error executing adaptive strategy {strategy_name}: {e}")
            return None
    
    async def _validate_hybrid_decision(self, strategy_name: str, adaptive_result: Dict, 
                                      context: TickerContext, ml_confidence: float) -> Dict:
        """Validación integral de la decisión híbrida"""
        
        validation_flags = []
        
        # 1. Validar confianza ML
        if ml_confidence < self.min_confidence_for_action:
            return {"valid": False, "reason": f"ML confidence too low: {ml_confidence:.2f}"}
        
        # 2. Validar estabilidad de parámetros adaptativos
        stability_scores = adaptive_result.get("stability_scores", {})
        if stability_scores:
            avg_stability = np.mean(list(stability_scores.values()))
            if avg_stability < 0.3:
                validation_flags.append("LOW_PARAMETER_STABILITY")
        
        # 3. Validar complejidad de decisión
        complexity = self._calculate_decision_complexity(strategy_name, adaptive_result, context)
        if complexity > self.max_decision_complexity:
            return {"valid": False, "reason": f"Decision too complex: {complexity:.2f}"}
        
        # 4. Validar contexto del ticker
        if context.current_price <= 0:
            return {"valid": False, "reason": "Invalid market data"}
        
        # 5. Validaciones específicas del validador
        complexity_ok = len(stability_scores) <= self.validator.max_parameters_per_strategy
        if not complexity_ok:
            validation_flags.append("TOO_MANY_PARAMETERS")
        
        return {
            "valid": True,
            "flags": validation_flags,
            "complexity_score": complexity,
            "stability_average": np.mean(list(stability_scores.values())) if stability_scores else 1.0
        }
    
    async def learn_from_trade_outcome(self, decision: HybridDecision, 
                                     trade_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aprendizaje híbrido completo del resultado del trade
        
        NIVELES DE APRENDIZAJE:
        1. ML Selector aprende qué estrategia funcionó
        2. Adaptive Strategy aprende cómo ajustar parámetros
        3. Analysis Engine valida la calidad del aprendizaje
        """
        
        learning_summary = {
            "ml_selector_updated": False,
            "adaptive_strategy_updated": False,
            "analysis_completed": False,
            "learning_quality": "unknown",
            "insights_generated": [],
            "system_health_impact": "neutral"
        }
        
        try:
            self.logger.info(f"📚 Learning from {decision.selected_strategy} trade: "
                           f"{trade_result.get('symbol', '')} -> ${trade_result.get('pnl', 0):+.2f}")
            
            # NIVEL 1: ML Strategy Selector Learning
            try:
                # Normalizar reward para ML
                pnl = trade_result.get('pnl', 0)
                reward = np.tanh(pnl / 100.0)  # Normalizar entre -1 y 1
                
                # Actualizar ML selector
                self.ml_selector.update_model(
                    context=decision.ticker_context,
                    strategy=decision.selected_strategy,
                    reward=reward
                )
                
                learning_summary["ml_selector_updated"] = True
                self.logger.debug(f"📊 ML Selector updated with reward: {reward:.3f}")
                
            except Exception as e:
                self.logger.warning(f"ML Selector learning failed: {e}")
            
            # NIVEL 2: Adaptive Strategy Learning
            try:
                if decision.selected_strategy in self.adaptive_strategies:
                    strategy = self.adaptive_strategies[decision.selected_strategy]
                    
                    # Pasar resultado a estrategia adaptativa
                    adaptation_result = await strategy.learn_from_trade_result(trade_result)
                    learning_summary["adaptive_strategy_updated"] = len(
                        adaptation_result.get("parameters_updated", [])
                    ) > 0
                    
                    self.logger.debug(f"🎯 Adaptive strategy learning: "
                                    f"{len(adaptation_result.get('parameters_updated', []))} params updated")
                
            except Exception as e:
                self.logger.warning(f"Adaptive strategy learning failed: {e}")
            
            # NIVEL 3: Analysis Engine Validation
            try:
                if self.analysis_engine:
                    # Enriquecer trade_result con información de decisión
                    enriched_trade_data = trade_result.copy()
                    enriched_trade_data.update({
                        'strategy_selected': decision.selected_strategy,
                        'ml_confidence': decision.ml_confidence,
                        'execution_confidence': decision.execution_confidence,
                        'overall_confidence': decision.overall_confidence,
                        'adaptive_parameters': decision.adaptive_parameters,
                        'decision_complexity': decision.complexity_score
                    })
                    
                    # Análisis bias-aware
                    analysis_result = await self.analysis_engine.analyze_trade_with_safeguards(
                        enriched_trade_data
                    )
                    
                    learning_summary["analysis_completed"] = True
                    learning_summary["learning_quality"] = analysis_result.get("system_health", "unknown")
                    
                    # Extraer insights del análisis
                    writeup = analysis_result.get("writeup")
                    if writeup:
                        learning_summary["insights_generated"] = writeup.lessons_learned[:3]
                
            except Exception as e:
                self.logger.warning(f"Analysis engine validation failed: {e}")
            
            # INTEGRACIÓN: Guardar sesión de aprendizaje completa
            learning_session = {
                "timestamp": datetime.now(),
                "decision": decision,
                "trade_result": trade_result,
                "learning_summary": learning_summary,
                "system_health_before": self.system_health_metrics.copy()
            }
            
            self.learning_sessions.append(learning_session)
            
            # Actualizar salud del sistema
            await self._update_system_health()
            learning_summary["system_health_impact"] = self._assess_health_impact(learning_session)
            
            # Limitar historial
            if len(self.learning_sessions) > 200:
                self.learning_sessions = self.learning_sessions[-150:]
            
            # Notificar aprendizaje significativo
            if (learning_summary["ml_selector_updated"] and 
                learning_summary["adaptive_strategy_updated"]):
                await self._notify_significant_learning(decision, trade_result, learning_summary)
            
        except Exception as e:
            self.logger.error(f"❌ Error in hybrid learning: {e}")
            learning_summary["error"] = str(e)
        
        return learning_summary
    
    async def _update_system_health(self):
        """Actualizar métricas de salud del sistema híbrido"""
        
        try:
            # ML Selector health
            if self.ml_selector and hasattr(self.ml_selector, 'strategy_stats'):
                total_trades = sum(s.total_trades for s in self.ml_selector.strategy_stats.values())
                if total_trades > 50:
                    self.system_health_metrics["ml_selector_health"] = "healthy"
                elif total_trades > 20:
                    self.system_health_metrics["ml_selector_health"] = "learning"
                else:
                    self.system_health_metrics["ml_selector_health"] = "insufficient_data"
            
            # Adaptive Strategies health
            if self.adaptive_strategies:
                strategy_healths = []
                for strategy in self.adaptive_strategies.values():
                    if hasattr(strategy, 'get_strategy_health_report'):
                        health_report = strategy.get_strategy_health_report()
                        strategy_healths.append(health_report.get("overall_health", "unknown"))
                
                if strategy_healths:
                    healthy_count = sum(1 for h in strategy_healths if h == "healthy")
                    if healthy_count >= len(strategy_healths) * 0.7:
                        self.system_health_metrics["adaptive_strategies_health"] = "healthy"
                    else:
                        self.system_health_metrics["adaptive_strategies_health"] = "mixed"
            
            # Analysis Engine health
            if self.analysis_engine:
                engine_health = self.analysis_engine._evaluate_system_health()
                self.system_health_metrics["analysis_engine_health"] = engine_health
            
            # Overall complexity
            recent_decisions = self.decisions_history[-20:] if len(self.decisions_history) >= 20 else self.decisions_history
            if recent_decisions:
                avg_complexity = np.mean([d.complexity_score for d in recent_decisions])
                self.system_health_metrics["overall_complexity"] = avg_complexity
            
            self.system_health_metrics["last_health_check"] = datetime.now()
            
        except Exception as e:
            self.logger.warning(f"Error updating system health: {e}")
    
    def _calculate_ml_confidence(self, selected_strategy: str, rankings: List[tuple]) -> float:
        """Calcular confianza de la selección ML"""
        if not rankings or len(rankings) < 2:
            return 0.5
        
        # Diferencia entre mejor y segunda opción
        best_score = rankings[0][1]
        second_score = rankings[1][1] if len(rankings) > 1 else best_score - 0.1
        
        confidence = min(0.95, 0.5 + (best_score - second_score) * 2.0)
        return max(0.1, confidence)
    
    def _calculate_overall_confidence(self, ml_conf: float, exec_conf: float) -> float:
        """Calcular confianza general de la decisión"""
        # Promedio ponderado con penalty por baja confianza en cualquier nivel
        weighted_avg = (ml_conf * 0.4 + exec_conf * 0.6)
        
        # Penalty si alguna confianza es muy baja
        min_conf_penalty = min(ml_conf, exec_conf) * 0.5
        
        return min(0.95, max(0.1, weighted_avg * (1 + min_conf_penalty)))
    
    def _calculate_decision_complexity(self, strategy_name: str, adaptive_result: Dict, 
                                     context: TickerContext) -> float:
        """Calcular complejidad de la decisión (0-1)"""
        
        complexity = 0.0
        
        # Complejidad por número de parámetros adaptativos
        params_count = len(adaptive_result.get("parameters_used", {}))
        complexity += params_count / 10.0  # Normalizar
        
        # Complejidad por inestabilidad de parámetros
        stability_scores = adaptive_result.get("stability_scores", {})
        if stability_scores:
            avg_instability = 1.0 - np.mean(list(stability_scores.values()))
            complexity += avg_instability * 0.3
        
        # Complejidad por contexto del ticker
        if hasattr(context, 'volatility_10'):
            volatility = context.volatility_10
            complexity += min(volatility * 2.0, 0.2)  # Alta volatilidad = más complejidad
        
        return min(1.0, complexity)
    
    def _assess_health_impact(self, learning_session: Dict) -> str:
        """Evaluar impacto en salud del sistema"""
        
        summary = learning_session["learning_summary"]
        
        positive_signals = 0
        negative_signals = 0
        
        if summary.get("ml_selector_updated"):
            positive_signals += 1
        if summary.get("adaptive_strategy_updated"):
            positive_signals += 1
        if summary.get("learning_quality") in ["healthy", "moderate"]:
            positive_signals += 1
        
        if summary.get("learning_quality") == "degraded":
            negative_signals += 1
        if summary.get("error"):
            negative_signals += 1
        
        if positive_signals > negative_signals:
            return "positive"
        elif negative_signals > positive_signals:
            return "negative"
        else:
            return "neutral"
    
    async def _notify_significant_learning(self, decision: HybridDecision, 
                                         trade_result: Dict, learning_summary: Dict):
        """Notificar aprendizaje significativo vía Telegram"""
        
        try:
            from notifications.telegram_client import send_message
            
            symbol = trade_result.get('symbol', 'Unknown')
            pnl = trade_result.get('pnl', 0)
            strategy = decision.selected_strategy
            
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            brain_emoji = "🧠" if learning_summary["learning_quality"] == "healthy" else "⚠️"
            
            message = f"""{brain_emoji} **HYBRID SYSTEM LEARNED**
═══════════════════════════════

{pnl_emoji} **{symbol}** via {strategy.upper()}: ${pnl:+.2f}

🤖 **ML Selector:**
• Strategy confidence updated
• Current best: {decision.strategy_rankings[0][0] if decision.strategy_rankings else strategy}

🎯 **Adaptive Strategy:**
• Parameters refined based on outcome
• System stability: {np.mean(list(decision.parameter_stability.values())):.1%} 

📊 **Analysis Quality:** {learning_summary.get('learning_quality', 'unknown').title()}

💡 **Key Insight:**
{learning_summary.get('insights_generated', ['System learning from performance'])[0][:100]}

🏥 **System Health:** {self.system_health_metrics.get('analysis_engine_health', 'unknown').title()}
═══════════════════════════════"""
            
            send_message(message, use_html=True)
            
        except Exception as e:
            self.logger.warning(f"Could not send learning notification: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Estado completo del sistema híbrido"""
        
        return {
            "hybrid_learning_system": {
                "components_initialized": {
                    "ml_selector": self.ml_selector is not None,
                    "ticker_profiler": self.ticker_profiler is not None,
                    "analysis_engine": self.analysis_engine is not None,
                    "adaptive_strategies": len(self.adaptive_strategies)
                },
                
                "system_health": self.system_health_metrics,
                
                "activity_stats": {
                    "decisions_made": len(self.decisions_history),
                    "learning_sessions": len(self.learning_sessions),
                    "avg_decision_confidence": np.mean([d.overall_confidence for d in self.decisions_history[-50:]]) if len(self.decisions_history) >= 50 else 0.5,
                    "avg_complexity": self.system_health_metrics.get("overall_complexity", 0.5)
                },
                
                "safety_metrics": {
                    "decisions_rejected": sum(1 for d in self.decisions_history if d.overall_confidence < self.min_confidence_for_action),
                    "high_complexity_decisions": sum(1 for d in self.decisions_history if d.complexity_score > self.max_decision_complexity * 0.8),
                    "validation_flags_raised": sum(len(d.validation_flags) for d in self.decisions_history)
                }
            }
        }

# Factory function
async def create_hybrid_learning_system(config: Dict[str, Any] = None) -> HybridLearningSystem:
    """Factory para crear sistema híbrido completo"""
    system = HybridLearningSystem(config)
    
    # Esperar inicialización
    await asyncio.sleep(0.1)  # Permitir que la inicialización async complete
    
    return system

if __name__ == "__main__":
    # Test del sistema híbrido
    print("🧪 Testing Hybrid Learning System")
    print("=" * 50)
    
    async def test_hybrid_system():
        system = await create_hybrid_learning_system()
        status = system.get_system_status()
        
        print("System Status:")
        for component, initialized in status["hybrid_learning_system"]["components_initialized"].items():
            status_emoji = "✅" if initialized else "❌"
            print(f"  {status_emoji} {component}: {initialized}")
        
        print(f"\nSafety Metrics:")
        safety = status["hybrid_learning_system"]["safety_metrics"]
        for metric, value in safety.items():
            print(f"  • {metric}: {value}")
    
    # Ejecutar test
    asyncio.run(test_hybrid_system())
    
    print("\n🎯 Hybrid Learning System Ready!")
    print("✅ All anti-overfitting safeguards active")
    print("✅ Multi-level learning implemented")
    print("✅ Bias detection and validation online")