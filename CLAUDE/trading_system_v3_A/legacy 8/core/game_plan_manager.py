#!/usr/bin/env python3
"""
Game Plan Manager - Implementa Game Planning profesional para SmallCap Trading

Basado en metodología de traders profesionales (SMB Capital):
- Pre-planificación antes de apertura del mercado
- Sistema de Tiers (A, B, C) para priorización
- Escenarios "What If" pre-definidos
- Ejecución más rápida con decisiones pre-computadas
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, time
import logging
from enum import Enum

class TierLevel(Enum):
    """Niveles de prioridad para oportunidades"""
    TIER_A = "A"  # Principal focus - highest probability
    TIER_B = "B"  # Secondary - moderate probability  
    TIER_C = "C"  # Low probability - correlated plays

class SetupType(Enum):
    """Tipos de setups en nuestro playbook"""
    GAP_AND_GO = "gap_and_go"
    FADE_GAP = "fade_gap"
    NEWS_MOMENTUM = "news_momentum"
    TECHNICAL_BREAKOUT = "technical_breakout"
    FDA_CATALYST = "fda_catalyst"
    EARNINGS_SURPRISE = "earnings_surprise"

@dataclass
class TechnicalLevels:
    """Niveles técnicos pre-calculados"""
    support_1: float
    support_2: float
    resistance_1: float
    resistance_2: float
    pivot: float
    stop_loss: float
    target_1: float
    target_2: float

@dataclass
class WhatIfScenario:
    """Escenario 'What If' pre-definido"""
    condition: str  # "Si rompe resistencia X con volumen Y"
    action: str     # "Entrar con tamaño Z"
    position_size: float
    stop_loss: float
    target: float
    probability: float  # 0.0 - 1.0

@dataclass
class GamePlanEntry:
    """Entry en el Game Plan diario"""
    symbol: str
    tier: TierLevel
    setup_type: SetupType
    technical_levels: TechnicalLevels
    scenarios: List[WhatIfScenario]
    catalyst_info: Dict
    quality_score: float
    priority_rank: int
    pre_computed_decision: Optional[Dict]
    notes: str

class GamePlanManager:
    """
    Manager principal del Game Planning
    Se ejecuta PRE-MARKET para preparar el día
    """
    
    def __init__(self, config, logger: logging.Logger = None):
        self.config = config
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        
        # Game Plan diario (se resetea cada día)
        self.daily_game_plan: Dict[str, GamePlanEntry] = {}
        self.market_context: Dict = {}
        self.tier_a_symbols: List[str] = []
        self.tier_b_symbols: List[str] = []
        self.tier_c_symbols: List[str] = []
        
        # Performance tracking
        self.daily_stats = {
            'planned_trades': 0,
            'executed_trades': 0,
            'plan_adherence': 0.0,
            'tier_a_hit_rate': 0.0,
            'tier_b_hit_rate': 0.0,
            'average_execution_time': 0.0
        }
    
    def create_daily_game_plan(self, scanner_watchlist: List[Dict]) -> Dict[str, GamePlanEntry]:
        """
        Crear Game Plan diario PRE-MARKET
        
        Args:
            scanner_watchlist: Lista de oportunidades pre-identificadas
            
        Returns:
            Game plan completo organizado por tiers
        """
        self.logger.info("🎯 CREANDO GAME PLAN DIARIO PRE-MARKET")
        
        # 1. Analizar contexto de mercado
        self.market_context = self._analyze_market_context()
        
        # 2. Evaluar y clasificar cada símbolo
        classified_entries = []
        for opportunity in scanner_watchlist:
            entry = self._create_game_plan_entry(opportunity)
            if entry:
                classified_entries.append(entry)
        
        # 3. Organizar por tiers
        self._organize_by_tiers(classified_entries)
        
        # 4. Pre-computar decisiones para ejecución rápida
        self._pre_compute_decisions()
        
        self.logger.info(f"📊 GAME PLAN CREADO:")
        self.logger.info(f"   🔥 Tier A (Primary Focus): {len(self.tier_a_symbols)} symbols")
        self.logger.info(f"   ⚡ Tier B (Secondary): {len(self.tier_b_symbols)} symbols") 
        self.logger.info(f"   📈 Tier C (Correlated): {len(self.tier_c_symbols)} symbols")
        
        return self.daily_game_plan
    
    def _create_game_plan_entry(self, opportunity: Dict) -> Optional[GamePlanEntry]:
        """Crear entrada del game plan para un símbolo"""
        try:
            symbol = opportunity['symbol']
            
            # Calcular technical levels
            tech_levels = self._calculate_technical_levels(opportunity)
            
            # Determinar setup type
            setup_type = self._identify_setup_type(opportunity)
            
            # Crear escenarios What-If
            scenarios = self._create_what_if_scenarios(opportunity, tech_levels)
            
            # Calcular tier basado en múltiples factores
            tier = self._determine_tier(opportunity, setup_type)
            
            # Pre-computar quality score mejorado
            quality_score = self._calculate_enhanced_quality_score(opportunity)
            
            entry = GamePlanEntry(
                symbol=symbol,
                tier=tier,
                setup_type=setup_type,
                technical_levels=tech_levels,
                scenarios=scenarios,
                catalyst_info=opportunity.get('catalyst_info', {}),
                quality_score=quality_score,
                priority_rank=0,  # Se asigna después
                pre_computed_decision=None,  # Se calcula después
                notes=self._generate_notes(opportunity, setup_type)
            )
            
            return entry
            
        except Exception as e:
            self.logger.error(f"Error creando game plan entry para {opportunity.get('symbol', 'unknown')}: {e}")
            return None
    
    def _calculate_technical_levels(self, opportunity: Dict) -> TechnicalLevels:
        """Calcular niveles técnicos pre-market"""
        price = opportunity.get('current_price', 0)
        gap_pct = opportunity.get('gap_percentage', 0)
        
        # Niveles basados en price action y gap
        support_1 = price * 0.95  # -5%
        support_2 = price * 0.90  # -10%
        resistance_1 = price * 1.05  # +5%
        resistance_2 = price * 1.15  # +15%
        pivot = price
        
        # Stop loss inteligente basado en setup
        if abs(gap_pct) > 0.10:  # Gap >10%
            stop_loss = price * 0.92  # Más conservador
        else:
            stop_loss = price * 0.95
            
        # Targets basados en riesgo/recompensa
        target_1 = price * 1.10  # R:R 2:1 mínimo
        target_2 = price * 1.20  # R:R 4:1 objetivo
        
        return TechnicalLevels(
            support_1=support_1,
            support_2=support_2,
            resistance_1=resistance_1,
            resistance_2=resistance_2,
            pivot=pivot,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2
        )
    
    def _create_what_if_scenarios(self, opportunity: Dict, levels: TechnicalLevels) -> List[WhatIfScenario]:
        """Crear escenarios What-If específicos"""
        symbol = opportunity['symbol']
        price = opportunity['current_price']
        scenarios = []
        
        # Escenario 1: Breakout alcista
        scenarios.append(WhatIfScenario(
            condition=f"Si {symbol} rompe ${levels.resistance_1:.2f} con volumen >2x",
            action="Entrada larga inmediata",
            position_size=0.02,  # 2% del portfolio
            stop_loss=levels.support_1,
            target=levels.target_1,
            probability=0.65
        ))
        
        # Escenario 2: Pullback a soporte
        scenarios.append(WhatIfScenario(
            condition=f"Si {symbol} hace pullback a ${levels.support_1:.2f}",
            action="Entrada gradual en soporte",
            position_size=0.015,  # 1.5% del portfolio
            stop_loss=levels.support_2,
            target=levels.target_1,
            probability=0.45
        ))
        
        # Escenario 3: Gap fade (si gap >15%)
        gap_pct = abs(opportunity.get('gap_percentage', 0))
        if gap_pct > 0.15:
            scenarios.append(WhatIfScenario(
                condition=f"Si {symbol} no sostiene gap y rompe ${levels.support_1:.2f}",
                action="Short o salida inmediata",
                position_size=-0.01,  # Short 1%
                stop_loss=price,
                target=levels.support_2,
                probability=0.30
            ))
        
        return scenarios
    
    def _determine_tier(self, opportunity: Dict, setup_type: SetupType) -> TierLevel:
        """Determinar tier basado en probabilidad y calidad"""
        
        # Factores para tier classification
        catalyst_strength = {
            'FDA': 9, 'M&A': 8, 'CONTRACT': 7,
            'EARNINGS': 6, 'TECHNICAL': 4, 'OTHER': 3
        }
        
        catalyst_score = catalyst_strength.get(
            opportunity.get('catalyst_type', 'OTHER'), 3
        )
        
        gap_score = min(abs(opportunity.get('gap_percentage', 0)) * 20, 10)
        volume_score = min(opportunity.get('volume_ratio', 1), 10)
        quality_score = opportunity.get('quality_score', 5)
        
        # Score total (0-40)
        total_score = catalyst_score + gap_score + volume_score + quality_score
        
        # Clasificación por tiers
        if total_score >= 32:  # Top 80%
            return TierLevel.TIER_A
        elif total_score >= 24:  # Top 60%
            return TierLevel.TIER_B
        else:
            return TierLevel.TIER_C
    
    def _organize_by_tiers(self, entries: List[GamePlanEntry]):
        """Organizar entries por tiers y asignar priority ranks"""
        
        # Separar por tiers
        tier_a = [e for e in entries if e.tier == TierLevel.TIER_A]
        tier_b = [e for e in entries if e.tier == TierLevel.TIER_B]
        tier_c = [e for e in entries if e.tier == TierLevel.TIER_C]
        
        # Ordenar cada tier por quality score (descendente)
        tier_a.sort(key=lambda x: x.quality_score, reverse=True)
        tier_b.sort(key=lambda x: x.quality_score, reverse=True)
        tier_c.sort(key=lambda x: x.quality_score, reverse=True)
        
        # Asignar priority ranks
        rank = 1
        for entries_list in [tier_a, tier_b, tier_c]:
            for entry in entries_list:
                entry.priority_rank = rank
                self.daily_game_plan[entry.symbol] = entry
                rank += 1
        
        # Guardar listas por tier para acceso rápido
        self.tier_a_symbols = [e.symbol for e in tier_a]
        self.tier_b_symbols = [e.symbol for e in tier_b]
        self.tier_c_symbols = [e.symbol for e in tier_c]
    
    def get_instant_decision(self, symbol: str, live_data: Dict) -> Dict:
        """
        EJECUCIÓN ULTRA RÁPIDA - Decisión pre-computada
        
        Esta función se ejecuta cuando llega una oportunidad del scanner
        NO hace cálculos complejos - usa decisiones PRE-COMPUTADAS
        """
        
        if symbol not in self.daily_game_plan:
            return {
                'action': 'REJECT',
                'reason': 'Symbol not in daily game plan',
                'execution_time_ms': 1
            }
        
        start_time = datetime.now()
        entry = self.daily_game_plan[symbol]
        
        # Decisión basada en tier y escenarios pre-computados
        if entry.tier == TierLevel.TIER_A:
            # Tier A: Entrada agresiva
            decision = self._execute_tier_a_logic(entry, live_data)
        elif entry.tier == TierLevel.TIER_B:
            # Tier B: Entrada selectiva
            decision = self._execute_tier_b_logic(entry, live_data)
        else:
            # Tier C: Solo si condiciones excepcionales
            decision = self._execute_tier_c_logic(entry, live_data)
        
        # Tracking de performance
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        decision['execution_time_ms'] = execution_time
        decision['tier'] = entry.tier.value
        decision['priority_rank'] = entry.priority_rank
        
        self.logger.info(f"⚡ INSTANT DECISION for {symbol}: {decision['action']} "
                        f"(Tier {entry.tier.value}, {execution_time:.1f}ms)")
        
        return decision
    
    def _execute_tier_a_logic(self, entry: GamePlanEntry, live_data: Dict) -> Dict:
        """Lógica de ejecución para Tier A - Más agresiva"""
        
        # Tier A symbols tienen prioridad - entrada más rápida
        price = live_data.get('current_price', 0)
        volume_ratio = live_data.get('volume_ratio', 0)
        
        # Condiciones relajadas para Tier A
        if volume_ratio >= 2.0 and price > entry.technical_levels.support_1:
            return {
                'action': 'EXECUTE',
                'reason': f'Tier A priority execution - Strong setup confirmed',
                'confidence': min(entry.quality_score / 10.0, 0.95),
                'position_size': 0.025,  # 2.5% - más agresivo
                'stop_loss': entry.technical_levels.stop_loss,
                'target': entry.technical_levels.target_1
            }
        
        return {
            'action': 'WAIT',
            'reason': 'Tier A - waiting for volume confirmation'
        }
    
    def _execute_tier_b_logic(self, entry: GamePlanEntry, live_data: Dict) -> Dict:
        """Lógica de ejecución para Tier B - Selectiva"""
        
        price = live_data.get('current_price', 0)
        volume_ratio = live_data.get('volume_ratio', 0)
        
        # Condiciones más estrictas para Tier B
        if volume_ratio >= 3.0 and price > entry.technical_levels.resistance_1:
            return {
                'action': 'EXECUTE',
                'reason': f'Tier B selective execution - Breakout confirmed',
                'confidence': min(entry.quality_score / 10.0, 0.85),
                'position_size': 0.015,  # 1.5% - más conservador
                'stop_loss': entry.technical_levels.stop_loss,
                'target': entry.technical_levels.target_1
            }
        
        return {
            'action': 'REJECT',
            'reason': 'Tier B - strict criteria not met'
        }
    
    def _execute_tier_c_logic(self, entry: GamePlanEntry, live_data: Dict) -> Dict:
        """Lógica de ejecución para Tier C - Solo oportunidades excepcionales"""
        
        volume_ratio = live_data.get('volume_ratio', 0)
        gap_pct = abs(live_data.get('gap_percentage', 0))
        
        # Solo si condiciones excepcionales para Tier C
        if volume_ratio >= 5.0 and gap_pct >= 0.20:  # Volume 5x+ y Gap 20%+
            return {
                'action': 'EXECUTE',
                'reason': f'Tier C exceptional opportunity - Massive volume/gap',
                'confidence': min(entry.quality_score / 10.0, 0.75),
                'position_size': 0.01,  # 1% - muy conservador
                'stop_loss': entry.technical_levels.stop_loss,
                'target': entry.technical_levels.target_1
            }
        
        return {
            'action': 'REJECT',
            'reason': 'Tier C - exceptional criteria not met'
        }
    
    # ... [Métodos adicionales de análisis, reporting, etc.]
    
    def _analyze_market_context(self) -> Dict:
        """Analizar contexto general del mercado"""
        return {
            'market_sentiment': 'NEUTRAL',  # Se podría calcular desde SPY, VIX, etc.
            'sector_rotation': {},
            'volatility_regime': 'NORMAL',
            'time_of_day': datetime.now().time()
        }
    
    def _identify_setup_type(self, opportunity: Dict) -> SetupType:
        """Identificar tipo de setup"""
        catalyst = opportunity.get('catalyst_type', 'OTHER')
        gap_pct = abs(opportunity.get('gap_percentage', 0))
        
        if catalyst == 'FDA':
            return SetupType.FDA_CATALYST
        elif gap_pct > 0.10:
            return SetupType.GAP_AND_GO
        elif catalyst in ['M&A', 'CONTRACT']:
            return SetupType.NEWS_MOMENTUM
        else:
            return SetupType.TECHNICAL_BREAKOUT
    
    def _calculate_enhanced_quality_score(self, opportunity: Dict) -> float:
        """Score mejorado que incluye más factores"""
        # Tu lógica de scoring actual + mejoras
        base_score = opportunity.get('quality_score', 5.0)
        
        # Factores adicionales para game planning
        catalyst_multiplier = {
            'FDA': 1.2, 'M&A': 1.15, 'CONTRACT': 1.1,
            'EARNINGS': 1.0, 'OTHER': 0.9
        }
        
        multiplier = catalyst_multiplier.get(
            opportunity.get('catalyst_type', 'OTHER'), 0.9
        )
        
        enhanced_score = base_score * multiplier
        return min(enhanced_score, 10.0)
    
    def _generate_notes(self, opportunity: Dict, setup_type: SetupType) -> str:
        """Generar notas específicas del setup"""
        catalyst = opportunity.get('catalyst_type', 'OTHER')
        gap = opportunity.get('gap_percentage', 0) * 100
        
        return f"Setup: {setup_type.value} | Catalyst: {catalyst} | Gap: {gap:+.1f}%"
    
    def _pre_compute_decisions(self):
        """Pre-computar decisiones para ejecución rápida"""
        for symbol, entry in self.daily_game_plan.items():
            # Pre-computar decision tree para cada entry
            # Esto hace que get_instant_decision() sea ultra-rápido
            pass  # Implementar lógica de pre-cómputo
    
    def generate_daily_report(self) -> Dict:
        """Generar reporte de adherencia al plan"""
        return {
            'plan_adherence': self.daily_stats['plan_adherence'],
            'tier_performance': {
                'tier_a_hit_rate': self.daily_stats['tier_a_hit_rate'],
                'tier_b_hit_rate': self.daily_stats['tier_b_hit_rate']
            },
            'execution_speed': self.daily_stats['average_execution_time'],
            'planned_vs_executed': {
                'planned': self.daily_stats['planned_trades'],
                'executed': self.daily_stats['executed_trades']
            }
        }
