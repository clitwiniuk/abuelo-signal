#!/usr/bin/env python3
"""
Hybrid Volume Engine - Sistema híbrido ML + Rules-based
Combina ML donde funciona bien con reglas inteligentes donde el ML es limitado
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from core.ml_volume_engine import MLVolumeEngine, MarketContext, create_market_context

@dataclass
class MarketConditions:
    """Análisis de condiciones del mercado para rules-based logic"""
    volatility_regime: str      # 'LOW', 'NORMAL', 'HIGH', 'EXTREME'
    market_cap_category: str    # 'MICRO', 'SMALL', 'MID', 'LARGE'
    volume_regime: str          # 'DRY', 'NORMAL', 'ACTIVE', 'EXPLOSIVE'
    time_period: str            # 'PREMARKET', 'OPEN', 'NORMAL', 'LUNCH', 'CLOSE'
    sector_risk: str            # 'LOW', 'MODERATE', 'HIGH', 'VOLATILE'
    
@dataclass
class VolumeDecision:
    """Decisión final de volumen con explicación"""
    requirement: float
    source: str                 # 'ML', 'RULES', 'HYBRID'
    confidence: float           # 0-1
    reasoning: str
    adjustments: Dict[str, float]

class HybridVolumeEngine:
    """
    Motor híbrido que combina ML con reglas inteligentes
    """
    
    def __init__(self, ml_engine: Optional[MLVolumeEngine] = None):
        self.logger = logging.getLogger(__name__)
        
        # ML Engine para casos donde funciona bien
        self.ml_engine = ml_engine or MLVolumeEngine()
        
        # Configuración del sistema híbrido - CORREGIDO
        self.use_ml_for = {
            'base_prediction': True,       # ML para predicción base
            'volume_extremes': True,       # ML detecta volúmenes extremos bien
            'volatility_adaptation': False, # Rules mejor para volatilidad
            'market_cap_sensitivity': False, # Rules mejor para market cap
            'sector_awareness': False,      # Rules mejor para sectores
            'time_sensitivity': False       # Rules mejor para tiempo - CORREGIDO
        }
        
        # Rules-based parameters (basados en análisis de mercado real)
        self.volatility_multipliers = {
            'LOW': 0.8,      # Mercado calmado, menos restrictivo
            'NORMAL': 1.0,   # Multiplier neutral
            'HIGH': 1.2,     # Reducido de 1.3 a 1.2 (menos restrictivo)
            'EXTREME': 1.4   # Reducido de 1.6 a 1.4 (menos restrictivo)
        }
        
        self.market_cap_multipliers = {
            'MICRO': 1.2,    # Micro caps - reducido de 1.4 a 1.2 (menos restrictivo)
            'SMALL': 1.0,    # Small caps - reducido de 1.1 a 1.0 (neutral)
            'MID': 0.9,      # Mid caps menos restrictivas
            'LARGE': 0.8     # Large caps menos restrictivas
        }
        
        self.time_multipliers = {
            'PREMARKET': 0.7,   # Pre-market más leniente
            'OPEN': 1.2,        # Market open más restrictivo
            'NORMAL': 1.0,      # Horas normales
            'LUNCH': 1.1,       # Lunch time ligeramente restrictivo
            'CLOSE': 1.3,       # Near close más restrictivo
            'AFTERHOURS': 1.5   # After hours muy restrictivo
        }
        
        self.sector_multipliers = {
            'Technology': 1.0,
            'Healthcare': 1.1,   # Reducido de 1.2 a 1.1 (catalyst plays legítimos)
            'Energy': 1.3,       # Muy volátil por commodities  
            'Finance': 0.9,      # Más estable
            'Consumer': 1.0,
            'Materials': 1.1,
            'Utilities': 0.8,    # Muy estable
            'Other': 1.0,
            'OTHER': 1.0
        }
        
        # Strategy base requirements (optimizados basado en análisis real)
        self.strategy_base_requirements = {
            'macdv_smallcaps': 1.0,      # Funciona bien con volumen moderado
            'daily_plays': 0.7,          # Más leniente para intraday
            'gap_go': 1.4,               # Necesita momentum
            'volume_breakout': 1.8,      # Necesita confirmación de volumen
            'orb': 1.1,                  # ORB moderado
            'pmh_breakout': 1.6,         # Pre-market high breakout
            'catalyst_momentum': 1.3,    # Catalyst plays
            'vwap_reclaim': 1.2,         # VWAP reclaim
            'eod_momentum': 1.4,         # End of day momentum
            'vcp': 1.3                   # Volatility Contraction Pattern
        }
        
    async def predict_volume_requirement_with_earnings(self, strategy: str, context: MarketContext, symbol: str) -> VolumeDecision:
        """
        Predice requerimiento de volumen con earnings context (Scanner-First)
        """
        # Obtener earnings context
        from core.earnings_context_provider import earnings_context_provider
        earnings_context = await earnings_context_provider.get_earnings_context(symbol)
        
        # Llamar método principal con earnings context
        return self._predict_with_earnings_context(strategy, context, earnings_context)
    
    def predict_volume_requirement(self, strategy: str, context: MarketContext) -> VolumeDecision:
        """
        Predice requerimiento de volumen usando sistema híbrido (sin earnings context)
        """
        return self._predict_with_earnings_context(strategy, context, None)
    
    def _predict_with_earnings_context(self, strategy: str, context: MarketContext, earnings_context) -> VolumeDecision:
        """
        Método principal que maneja predicción con o sin earnings context
        """
        try:
            # VALIDACIÓN DE DATOS DE ENTRADA
            validation_error = self._validate_inputs(strategy, context)
            if validation_error:
                self.logger.error(f"Input validation failed: {validation_error}")
                return self._create_fallback_decision(strategy, validation_error)
            
            # Analizar condiciones del mercado
            conditions = self._analyze_market_conditions(context)
            
            # Obtener requerimiento base
            base_requirement = self._get_base_requirement(strategy)
            
            # NUEVO SISTEMA HÍBRIDO - Combinación inteligente
            adjustments = {}
            
            # Decidir predicción base (ML vs Rules)
            if self._should_use_ml_base(strategy, context, conditions):
                ml_requirement = self._get_ml_prediction(strategy, context)
                final_requirement = ml_requirement
                source = "ML_BASE"
                reasoning = "ML base prediction"
            else:
                final_requirement = base_requirement
                source = "RULES_BASE"
                reasoning = "Rules base prediction"
            
            # EARNINGS CONTEXT ADJUSTMENTS (Conservative rules for negative earnings)
            if earnings_context:
                earnings_mult, earnings_reasoning = self._apply_earnings_adjustments(earnings_context, context)
                final_requirement *= earnings_mult
                adjustments['earnings'] = earnings_mult
                reasoning += f" + {earnings_reasoning}"
            
            # SIEMPRE aplicar ajustes rules-based contextuales
            
            # Ajuste por volatilidad
            if not self.use_ml_for['volatility_adaptation']:
                vol_mult = self.volatility_multipliers[conditions.volatility_regime]
                final_requirement *= vol_mult
                adjustments['volatility'] = vol_mult
            
            # Ajuste por market cap
            if not self.use_ml_for['market_cap_sensitivity']:
                cap_mult = self.market_cap_multipliers[conditions.market_cap_category]
                final_requirement *= cap_mult
                adjustments['market_cap'] = cap_mult
            
            # Ajuste por tiempo - AHORA SIEMPRE SE APLICA
            if not self.use_ml_for['time_sensitivity']:
                time_mult = self.time_multipliers[conditions.time_period]
                final_requirement *= time_mult
                adjustments['time'] = time_mult
            
            # Ajuste por sector
            sector_mult = self.sector_multipliers.get(context.sector, 1.0)
            final_requirement *= sector_mult
            adjustments['sector'] = sector_mult
            
            # Ajuste por volumen INTELIGENTE - Distinguir catalyst plays de pumps
            if conditions.volume_regime == 'EXPLOSIVE':
                # Análisis inteligente del volumen extremo
                vol_ratio = getattr(context, 'volume_trend', 5.0)  # Ratio actual
                
                if vol_ratio > 50.0:
                    # Pump and dump obvio (> 50x normal)
                    vol_extreme_mult = 2.0  # Muy restrictivo
                    reasoning += " + pump detection"
                elif vol_ratio > 15.0:
                    # Volumen muy alto, sospechoso
                    vol_extreme_mult = 1.6  # Restrictivo
                    reasoning += " + high volume caution"
                elif vol_ratio > 5.0:
                    # Catalyst play potencial (5-15x normal)
                    vol_extreme_mult = 1.2  # Ligeramente restrictivo
                    reasoning += " + catalyst volume"
                else:
                    # Volumen normal alto
                    vol_extreme_mult = 1.1
                    reasoning += " + normal high volume"
                
                final_requirement *= vol_extreme_mult
                adjustments['volume_extreme'] = vol_extreme_mult
                
            elif conditions.volume_regime == 'DRY':
                vol_dry_mult = 0.8  # Volumen bajo, más leniente
                final_requirement *= vol_dry_mult
                adjustments['volume_dry'] = vol_dry_mult
                reasoning += " + low volume adjustment"
            
            # DETERMINAR SOURCE CORRECTO basado en la lógica real
            final_source = self._determine_final_source(source, adjustments)
            final_reasoning = self._build_reasoning(source, adjustments, reasoning)
            
            # LÍMITES RACIONALES - Control de multiplicadores acumulativos
            final_requirement = self._apply_rational_limits(final_requirement, adjustments, strategy)
            
            # Calcular confidence
            confidence = self._calculate_confidence(final_source, conditions, adjustments)
            
            decision = VolumeDecision(
                requirement=final_requirement,
                source=final_source,
                confidence=confidence,
                reasoning=final_reasoning,
                adjustments=adjustments
            )
            
            self.logger.debug(
                f"🧠 Hybrid decision for {strategy}: {final_requirement:.2f}x "
                f"({final_source}) - {final_reasoning}"
            )
            
            return decision
            
        except Exception as e:
            # MANEJO DE ERRORES ROBUSTO
            return self._handle_prediction_error(e, strategy, context)
    
    def _apply_earnings_adjustments(self, earnings_context, market_context: MarketContext) -> tuple:
        """
        Aplicar reglas conservadoras para earnings
        Retorna (multiplier, reasoning)
        """
        
        # Reglas conservadoras específicas por phase
        if earnings_context.phase == "POST_EARNINGS_MISS":
            # POST-EARNINGS MISS: MUY CONSERVADOR 
            # Earnings miss + high volume = probable continued selling
            if earnings_context.surprise_percent and earnings_context.surprise_percent < -15:
                # Miss significativo (>15%)
                return (2.5, "major earnings miss protection")
            else:
                # Miss menor
                return (2.0, "earnings miss caution")
                
        elif earnings_context.phase == "POST_EARNINGS_SURPRISE":
            # EARNINGS SURPRISE: Distinguir si es penny stock pump
            if market_context.market_cap < 100_000_000:  # Micro/Nano caps
                if market_context.price_level < 2.0:  # Penny stock
                    return (2.2, "penny stock earnings surprise caution")
                else:
                    return (1.8, "micro cap earnings surprise")
            else:
                return (1.4, "legitimate earnings surprise")
                
        elif earnings_context.phase == "PRE_EARNINGS":
            # PRE-EARNINGS: Moderadamente conservador
            return (1.3, "pre-earnings uncertainty")
            
        elif earnings_context.phase == "POST_EARNINGS_BEAT":
            # POST-EARNINGS BEAT: Normal o ligeramente permisivo
            if earnings_context.surprise_percent and earnings_context.surprise_percent > 20:
                return (0.9, "strong earnings beat momentum")
            else:
                return (1.0, "earnings beat")
        
        # Fase normal o desconocida
        return (1.0, "normal earnings context")
    
    def _analyze_market_conditions(self, context: MarketContext) -> MarketConditions:
        """Analiza condiciones del mercado para rules-based logic"""
        
        # Volatility regime
        if context.market_stress < 0.2:
            volatility_regime = 'LOW'
        elif context.market_stress < 0.4:
            volatility_regime = 'NORMAL'
        elif context.market_stress < 0.7:
            volatility_regime = 'HIGH'
        else:
            volatility_regime = 'EXTREME'
        
        # Market cap category
        if context.market_cap < 50_000_000:
            market_cap_category = 'MICRO'
        elif context.market_cap < 500_000_000:
            market_cap_category = 'SMALL'
        elif context.market_cap < 5_000_000_000:
            market_cap_category = 'MID'
        else:
            market_cap_category = 'LARGE'
        
        # Volume regime - AJUSTADO para small caps
        if context.volume_trend < 0.7:
            volume_regime = 'DRY'
        elif context.volume_trend < 2.0:
            volume_regime = 'NORMAL'
        elif context.volume_trend < 8.0:  # Aumentado de 4.0 a 8.0
            volume_regime = 'ACTIVE'       # Catalyst plays normales
        else:
            volume_regime = 'EXPLOSIVE'     # Solo pumps extremos (>8x)
        
        # Time period - CORREGIDO: Lógica secuencial correcta
        hour = context.time_of_day * 24
        if hour < 9.5:
            time_period = 'PREMARKET'
        elif hour < 10.5:
            time_period = 'OPEN'
        elif hour < 12.0:
            time_period = 'NORMAL'
        elif hour < 14.0:
            time_period = 'LUNCH'
        elif hour < 16.0:
            time_period = 'CLOSE'
        else:
            time_period = 'AFTERHOURS'
        
        # Sector risk (simplified)
        high_risk_sectors = ['Energy', 'Healthcare']
        low_risk_sectors = ['Utilities', 'Finance']
        
        if context.sector in high_risk_sectors:
            sector_risk = 'HIGH'
        elif context.sector in low_risk_sectors:
            sector_risk = 'LOW'
        else:
            sector_risk = 'MODERATE'
        
        return MarketConditions(
            volatility_regime=volatility_regime,
            market_cap_category=market_cap_category,
            volume_regime=volume_regime,
            time_period=time_period,
            sector_risk=sector_risk
        )
    
    def _should_use_ml_base(self, strategy: str, context: MarketContext, 
                           conditions: MarketConditions) -> bool:
        """Decide si usar ML para predicción base"""
        
        # Usar ML para predicción base si disponible y configurado
        if self.use_ml_for['base_prediction'] and self.ml_engine:
            return True
        
        # Casos especiales donde ML es particularmente bueno
        if (self.use_ml_for['volume_extremes'] and 
            conditions.volume_regime in ['EXPLOSIVE']):
            return True
        
        # Por defecto, usar rules-based
        return False
    
    def _get_ml_prediction(self, strategy: str, context: MarketContext) -> float:
        """Obtiene predicción ML"""
        try:
            return self.ml_engine.predict_volume_requirement(strategy, context)
        except Exception as e:
            self.logger.warning(f"ML prediction failed: {e}")
            return self.strategy_base_requirements.get(strategy, 1.5)
    
    def _get_base_requirement(self, strategy: str) -> float:
        """Obtiene requerimiento base para la estrategia"""
        return self.strategy_base_requirements.get(strategy, 1.5)
    
    def _calculate_confidence(self, source: str, conditions: MarketConditions, 
                            adjustments: Dict[str, float]) -> float:
        """Calcula confidence de la decisión"""
        base_confidence = {
            'ML': 0.7,
            'RULES': 0.8,
            'HYBRID': 0.9,
            'FALLBACK': 0.5
        }.get(source, 0.6)
        
        # Ajustar confidence basado en condiciones
        if conditions.volatility_regime == 'EXTREME':
            base_confidence *= 0.9  # Menos confident en condiciones extremas
        
        if len(adjustments) > 3:
            base_confidence *= 0.95  # Muchos ajustes, ligeramente menos confident
        
        return np.clip(base_confidence, 0.3, 1.0)
    
    def _determine_final_source(self, base_source: str, adjustments: Dict[str, float]) -> str:
        """Determina el source final basado en la lógica real aplicada"""
        
        if len(adjustments) == 0:
            return base_source
        elif base_source in ['ML_BASE', 'RULES_BASE'] and len(adjustments) >= 1:
            # Base prediction + contextual adjustments = HYBRID
            return "HYBRID"
        elif base_source == "FALLBACK":
            return "FALLBACK"
        else:
            return "HYBRID"  # Por defecto para casos complejos
    
    def _build_reasoning(self, base_source: str, adjustments: Dict[str, float], 
                        base_reasoning: str) -> str:
        """Construye reasoning descriptivo y preciso"""
        
        if len(adjustments) == 0:
            return base_reasoning
        
        # Construir descripción de ajustes
        adj_descriptions = []
        for adj_name, adj_value in adjustments.items():
            effect = "restrictive" if adj_value > 1.0 else "lenient"
            adj_descriptions.append(f"{adj_name} ({adj_value:.2f}x {effect})")
        
        adj_text = ", ".join(adj_descriptions)
        
        if base_source == "ML_BASE":
            return f"ML base + contextual rules: {adj_text}"
        elif base_source == "RULES_BASE":
            return f"Rules base + contextual adjustments: {adj_text}"
        else:
            return f"{base_reasoning} with adjustments: {adj_text}"
    
    def _apply_rational_limits(self, requirement: float, adjustments: Dict[str, float], 
                              strategy: str) -> float:
        """Aplica límites racionales basados en lógica de trading real"""
        
        # Calcular multiplicador acumulativo total
        total_multiplier = 1.0
        for adj_name, adj_value in adjustments.items():
            total_multiplier *= adj_value
        
        # Límites por estrategia (basados en realidad del trading)
        strategy_max_limits = {
            'macdv_smallcaps': 2.5,     # Small caps pueden tener requirements altos
            'daily_plays': 2.0,         # Plays intraday más conservadores
            'gap_go': 3.0,              # Gap plays pueden necesitar más confirmación  
            'volume_breakout': 3.5,     # Volume breakouts necesitan más volumen
            'orb': 2.2,                 # ORB moderadamente conservador
            'pmh_breakout': 2.8,        # Pre-market high breakouts
            'catalyst_momentum': 3.0,    # Catalyst plays
            'vwap_reclaim': 2.5,        # VWAP reclaims
            'eod_momentum': 2.0,        # End of day más conservador
            'vcp': 2.3                  # VCP patterns
        }
        
        strategy_min_limits = {
            'macdv_smallcaps': 0.4,
            'daily_plays': 0.3, 
            'gap_go': 0.5,
            'volume_breakout': 0.8,  # Volume breakout necesita mínimo volumen
            'orb': 0.4,
            'pmh_breakout': 0.6,
            'catalyst_momentum': 0.5,
            'vwap_reclaim': 0.4,
            'eod_momentum': 0.5,
            'vcp': 0.4
        }
        
        # Obtener límites para esta estrategia
        max_limit = strategy_max_limits.get(strategy, 2.5)  # Default conservador
        min_limit = strategy_min_limits.get(strategy, 0.3)  # Default mínimo
        
        # Si los multiplicadores son demasiado extremos, aplicar dampening inteligente
        if total_multiplier > 2.5:
            # Para small caps, mantener protección pero no sobre-dampen
            # Usar raíz cuadrada en lugar de logaritmo para dampening más suave
            dampening_factor = np.sqrt(total_multiplier) / total_multiplier
            requirement *= dampening_factor
            self.logger.warning(
                f"Applied smart dampening for extreme multipliers: {total_multiplier:.2f}x -> dampening factor {dampening_factor:.2f}x"
            )
            # PERO: Si es claramente pump and dump (> 10x multiplicador), mantener restricción alta
            if total_multiplier > 10.0:
                requirement = max(requirement, 2.0)  # Mínimo 2.0x para pumps obvios
        
        # Aplicar límites finales
        final_requirement = np.clip(requirement, min_limit, max_limit)
        
        # Log si se aplicaron límites
        if final_requirement != requirement:
            self.logger.info(
                f"Applied rational limits to {strategy}: {requirement:.2f}x -> {final_requirement:.2f}x"
            )
        
        return final_requirement
    
    def _handle_prediction_error(self, error: Exception, strategy: str, 
                                context: MarketContext) -> VolumeDecision:
        """Manejo robusto de errores con logging detallado y fallback inteligente"""
        
        import traceback
        
        # Log detallado del error
        error_type = type(error).__name__
        error_msg = str(error)
        stack_trace = traceback.format_exc()
        
        self.logger.error(f"🚨 HYBRID SYSTEM ERROR")
        self.logger.error(f"   Error Type: {error_type}")
        self.logger.error(f"   Error Message: {error_msg}")
        self.logger.error(f"   Strategy: {strategy}")
        self.logger.error(f"   Context: sector={getattr(context, 'sector', 'unknown')}, "
                         f"price=${getattr(context, 'price_level', 0):.2f}, "
                         f"market_cap=${getattr(context, 'market_cap', 0):,.0f}")
        self.logger.debug(f"   Stack Trace:\n{stack_trace}")
        
        # Determinar tipo de fallback basado en el error
        if "ML" in error_msg or "model" in error_msg.lower():
            fallback_type = "ML_FAILURE"
            fallback_confidence = 0.6  # Rules-based más confiable
            self.logger.warning("🔄 ML engine failed, using rules-based fallback")
        elif "context" in error_msg.lower() or "validation" in error_msg.lower():
            fallback_type = "DATA_VALIDATION_FAILURE"
            fallback_confidence = 0.4  # Datos problemáticos
            self.logger.warning("🔄 Data validation failed, using conservative fallback")
        elif "memory" in error_msg.lower() or "resource" in error_msg.lower():
            fallback_type = "RESOURCE_FAILURE"
            fallback_confidence = 0.5
            self.logger.error("🔄 System resource error, using basic fallback")
        else:
            fallback_type = "UNKNOWN_FAILURE"
            fallback_confidence = 0.3
            self.logger.error("🔄 Unknown error, using minimal fallback")
        
        # Fallback requirement inteligente
        base_fallback = self.strategy_base_requirements.get(strategy, 1.5)
        
        # Aplicar conservadurismo adicional para errores graves
        if fallback_type == "DATA_VALIDATION_FAILURE":
            fallback_requirement = base_fallback * 1.3  # Más conservador
        elif fallback_type == "UNKNOWN_FAILURE":
            fallback_requirement = base_fallback * 1.5  # Muy conservador
        else:
            fallback_requirement = base_fallback
        
        # Límites de seguridad
        fallback_requirement = np.clip(fallback_requirement, 0.5, 2.5)
        
        # Logging de fallback
        self.logger.info(f"✅ Fallback applied: {fallback_requirement:.2f}x "
                        f"(confidence: {fallback_confidence:.1%})")
        
        return VolumeDecision(
            requirement=fallback_requirement,
            source="FALLBACK",
            confidence=fallback_confidence,
            reasoning=f"Fallback due to {fallback_type}: {error_msg[:100]}",
            adjustments={}
        )
    
    def _validate_inputs(self, strategy: str, context: MarketContext) -> Optional[str]:
        """Valida datos de entrada y retorna error si hay problemas"""
        
        # Validar estrategia
        if not isinstance(strategy, str) or not strategy.strip():
            return "Strategy must be a non-empty string"
        
        # Validar context
        if context is None:
            return "Context cannot be None"
        
        # Validar campos requeridos de MarketContext (ajustados al ML engine)
        required_fields = ['price_level', 'market_cap', 'avg_volume', 'sector']
        for field in required_fields:
            if not hasattr(context, field):
                return f"Context missing required field: {field}"
            
            value = getattr(context, field)
            if value is None:
                return f"Context field {field} cannot be None"
        
        # Validar rangos de valores
        if context.price_level <= 0:
            return f"Price must be positive, got: {context.price_level}"
        
        if context.market_cap <= 0:
            return f"Market cap must be positive, got: {context.market_cap}"
        
        if context.avg_volume <= 0:
            return f"Average volume must be positive, got: {context.avg_volume}"
        
        # Validar rangos razonables
        if context.price_level > 10000:  # $10k per share parece irreal
            return f"Price seems unrealistic: ${context.price_level:,.2f}"
        
        if context.market_cap > 50_000_000_000_000:  # $50T parece irreal
            return f"Market cap seems unrealistic: ${context.market_cap:,.0f}"
        
        # Validar campos opcionales si existen
        if hasattr(context, 'volume_trend') and context.volume_trend is not None:
            if context.volume_trend < 0:
                return f"Volume trend cannot be negative: {context.volume_trend}"
        
        if hasattr(context, 'time_of_day') and context.time_of_day is not None:
            if not (0 <= context.time_of_day <= 1):
                return f"Time of day must be between 0-1: {context.time_of_day}"
        
        return None  # No errors
    
    def _create_fallback_decision(self, strategy: str, error_msg: str) -> VolumeDecision:
        """Crea decisión fallback cuando hay errores de validación"""
        
        fallback_requirement = self.strategy_base_requirements.get(strategy, 2.0)
        
        return VolumeDecision(
            requirement=fallback_requirement,
            source="FALLBACK",
            confidence=0.3,
            reasoning=f"Fallback due to validation error: {error_msg}",
            adjustments={}
        )
    
    def get_decision_explanation(self, decision: VolumeDecision, strategy: str) -> str:
        """Genera explicación detallada de la decisión"""
        explanation = [
            f"Strategy: {strategy}",
            f"Final Requirement: {decision.requirement:.2f}x",
            f"Decision Source: {decision.source}",
            f"Confidence: {decision.confidence:.1%}",
            f"Reasoning: {decision.reasoning}"
        ]
        
        if decision.adjustments:
            explanation.append("Adjustments Applied:")
            for adj_type, multiplier in decision.adjustments.items():
                effect = "increased" if multiplier > 1 else "decreased"
                explanation.append(f"  • {adj_type}: {multiplier:.2f}x ({effect})")
        
        return "\n".join(explanation)
    
    def get_system_status(self) -> Dict[str, any]:
        """Estado del sistema híbrido"""
        return {
            'type': 'HYBRID_ML_RULES',
            'ml_engine_available': self.ml_engine is not None,
            'ml_used_for': [k for k, v in self.use_ml_for.items() if v],
            'rules_used_for': [k for k, v in self.use_ml_for.items() if not v],
            'base_strategies': len(self.strategy_base_requirements),
            'volatility_regimes': len(self.volatility_multipliers),
            'market_cap_categories': len(self.market_cap_multipliers),
            'time_periods': len(self.time_multipliers),
            'sectors_supported': len(self.sector_multipliers)
        }

# Integration function to replace ML engine seamlessly
def create_hybrid_volume_engine(ml_engine: Optional[MLVolumeEngine] = None) -> HybridVolumeEngine:
    """Factory function para crear hybrid engine"""
    return HybridVolumeEngine(ml_engine)