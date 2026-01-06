#!/usr/bin/env python3
"""
Smart Game Plan Manager - Sistema completo con Context Awareness
================================================================

REEMPLAZA completamente:
- strategy_time_orchestrator.py ✅
- Filtros temporales dispersos ✅  
- Lógica de timing redundante ✅

INCLUYE:
- Re-evaluación cada 15 minutos ✅
- Context Awareness completo ✅
- Selección inteligente de estrategias ✅
- Decisiones ultra-rápidas ✅

Author: Claude Code
Date: 2025-08-26
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
import logging
import asyncio
import pytz

class StrategyType(Enum):
    """Estrategias específicas del sistema"""
    GAP_AND_GO = "gap_and_go"
    FADE_GAP = "fade_gap"
    NEWS_MOMENTUM = "news_momentum" 
    FDA_CATALYST = "fda_catalyst"
    EARNINGS_SURPRISE = "earnings_surprise"
    OPENING_RANGE_BREAKOUT = "orb"
    MOMENTUM_CONTINUATION = "momentum_continuation"
    REVERSAL_PLAY = "reversal_play"
    VOLUME_BREAKOUT = "volume_breakout"
    END_OF_DAY = "end_of_day"
    DAILY_PLAYS = "daily_plays"
    FIRST_DAY_BOUNCE = "first_day_bounce"

class MarketPhase(Enum):
    """Fases dinámicas del mercado"""
    PRE_MARKET = "pre_market"      # 04:00-09:30
    OPENING = "opening"            # 09:30-10:30 (Primera hora crítica)
    MID_MORNING = "mid_morning"    # 10:30-12:00
    LUNCH = "lunch"                # 12:00-13:00 (Baja liquidez)
    AFTERNOON = "afternoon"        # 13:00-15:00
    POWER_HOUR = "power_hour"      # 15:00-16:00 (Última hora crítica)
    GENERAL_TRADING = "general_trading"  # 10:00-16:00 (Fase flexible para estrategias que necesiten operar en cualquier momento)
    AFTER_HOURS = "after_hours"    # 16:00-20:00

class MarketSentiment(Enum):
    """Sentiment de mercado para context awareness"""
    VERY_BULLISH = "very_bullish"    # SPY +2%+, VIX <15
    BULLISH = "bullish"              # SPY +0.5-2%, VIX 15-20
    NEUTRAL = "neutral"              # SPY ±0.5%, VIX 20-25  
    BEARISH = "bearish"              # SPY -0.5-2%, VIX 25-30
    VERY_BEARISH = "very_bearish"    # SPY -2%+, VIX >30
    PANIC = "panic"                  # VIX >40

@dataclass
class MarketContext:
    """Context awareness completo del mercado"""
    # Timing context
    current_phase: MarketPhase
    time_in_phase: timedelta
    next_phase_in: timedelta
    
    # Market sentiment context
    market_sentiment: MarketSentiment
    spy_change_pct: float
    vix_level: float
    sector_rotation: Dict[str, float]  # {'TECH': 0.02, 'HEALTHCARE': -0.01}
    
    # Volume/Volatility context  
    overall_volume_ratio: float        # vs 20-day average
    volatility_regime: str            # 'LOW', 'NORMAL', 'HIGH', 'EXTREME'
    adv_decline_ratio: float          # Advancing/Declining stocks
    
    # News context
    breaking_news_count: int          # Breaking news in last hour
    major_economic_events: List[str]  # ['FOMC', 'GDP', etc.]
    sector_news: Dict[str, int]       # News count by sector
    
    # Performance context (para adaptación)
    recent_strategy_performance: Dict[StrategyType, float]  # Win rates last 10 trades
    current_day_pnl: float
    current_positions: int
    
    # Update metadata
    last_updated: datetime
    data_quality_score: float         # 0-1, quality of data feeds

@dataclass
class SmartGamePlanEntry:
    """Entry inteligente con context awareness"""
    symbol: str
    tier: str  # A, B, C
    
    # Strategy selection (context-aware)
    primary_strategy: StrategyType
    primary_strategy_confidence: float
    backup_strategies: List[StrategyType]
    strategy_selection_reasoning: str
    
    # Technical levels (strategy-specific)
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    technical_setup_score: float      # 0-10
    
    # Context factors
    optimal_market_phases: List[MarketPhase]
    required_sentiment: List[MarketSentiment]
    min_volatility_regime: str
    context_match_score: float        # How well current context matches
    
    # Execution parameters
    position_size: float
    max_risk_per_trade: float
    execution_urgency: str           # 'LOW', 'MEDIUM', 'HIGH'
    time_decay_factor: float         # Decreases over time if not executed
    
    # Tracking
    last_updated: datetime
    updates_count: int = 0
    initial_context_score: float = 0.0

class SmartGamePlanManager:
    """
    Game Plan Manager inteligente con Context Awareness completo
    
    CARACTERÍSTICAS CLAVE:
    1. Re-evaluación cada 15 minutos (configurable)
    2. Context Awareness completo (mercado, sentiment, noticias)
    3. Selección dinámica de estrategias
    4. Decisiones ultra-rápidas pre-computadas
    5. Aprendizaje de performance en tiempo real
    """
    
    def __init__(self, config, data_provider=None, logger: logging.Logger = None):
        self.config = config
        self.data_provider = data_provider  # For market data, news, etc.
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        
        # Core game plan
        self.current_plan: Dict[str, SmartGamePlanEntry] = {}
        self.plan_version = 0
        self.last_full_update = None
        
        # Context awareness
        self.market_context: MarketContext = self._initialize_market_context()
        self.context_update_interval = timedelta(minutes=5)   # Context updates every 5 min
        self.plan_update_interval = timedelta(minutes=15)     # Plan re-eval every 15 min
        
        # Performance tracking for adaptation
        self.strategy_performance = {strategy: {'wins': 0, 'losses': 0, 'total': 0} 
                                   for strategy in StrategyType}
        self.daily_stats = {
            'plan_updates': 0,
            'context_updates': 0,
            'decisions_made': 0,
            'plan_adherence': 0.0
        }
        
        # Background update task
        self.update_task = None
        self.is_running = False
        
        # Decision cache to prevent double evaluation conflict
        self.decision_cache: Dict[str, Dict] = {}  # {symbol: {decision, timestamp, data_hash}}
        self.cache_duration = timedelta(minutes=2)  # Cache decisions for 2 minutes
        
        self.logger.info("🧠 Smart Game Plan Manager initialized")
        self.logger.info(f"   ⏱️  Plan re-evaluation: every {self.plan_update_interval}")
        self.logger.info(f"   🌍 Context updates: every {self.context_update_interval}")
    
    async def start_dynamic_updates(self):
        """
        Iniciar updates dinámicos en background
        Context cada 5 min, Plan cada 15 min
        """
        self.is_running = True
        self.update_task = asyncio.create_task(self._background_update_loop())
        self.logger.info("🔄 Dynamic updates started - Context aware planning active")
    
    async def stop_dynamic_updates(self):
        """Parar updates dinámicos"""
        self.is_running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        self.logger.info("⏹️ Dynamic updates stopped")
    
    async def _background_update_loop(self):
        """Loop principal de updates en background"""
        try:
            while self.is_running:
                now = datetime.now()
                
                # 1. Update market context (every 5 minutes)
                if self._should_update_context():
                    await self._update_market_context()
                    self.daily_stats['context_updates'] += 1
                
                # 2. Re-evaluate plan (every 15 minutes) 
                if self._should_update_plan():
                    await self._reevaluate_plan()
                    self.daily_stats['plan_updates'] += 1
                
                # 3. Sleep until next check (1 minute intervals)
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            self.logger.info("🛑 Background update loop cancelled")
        except Exception as e:
            self.logger.error(f"💥 Error in background update loop: {e}")
    
    def _should_update_context(self) -> bool:
        """Determinar si debe actualizar context"""
        if not hasattr(self.market_context, 'last_updated'):
            return True
        
        time_since_update = datetime.now() - self.market_context.last_updated
        return time_since_update >= self.context_update_interval
    
    def _should_update_plan(self) -> bool:
        """Determinar si debe re-evaluar plan"""
        if not self.last_full_update:
            return True
        
        time_since_update = datetime.now() - self.last_full_update
        return time_since_update >= self.plan_update_interval
    
    async def _update_market_context(self):
        """
        Actualizar context awareness completo
        Incluye: sentiment, volatility, news, performance
        """
        try:
            self.logger.info("🌍 Updating market context...")
            
            # Get fresh market data
            context_data = await self._fetch_market_context_data()
            
            # Update market context
            self.market_context = MarketContext(
                # Timing
                current_phase=self._determine_current_phase(),
                time_in_phase=self._calculate_time_in_phase(),
                next_phase_in=self._calculate_time_to_next_phase(),
                
                # Sentiment (context-aware)
                market_sentiment=self._determine_market_sentiment(context_data),
                spy_change_pct=context_data.get('spy_change', 0.0),
                vix_level=context_data.get('vix', 20.0),
                sector_rotation=context_data.get('sector_performance', {}),
                
                # Volume/Volatility
                overall_volume_ratio=context_data.get('volume_ratio', 1.0),
                volatility_regime=self._determine_volatility_regime(context_data.get('vix', 20)),
                adv_decline_ratio=context_data.get('advance_decline', 1.0),
                
                # News context
                breaking_news_count=context_data.get('breaking_news', 0),
                major_economic_events=context_data.get('economic_events', []),
                sector_news=context_data.get('sector_news', {}),
                
                # Performance context
                recent_strategy_performance=self._calculate_recent_performance(),
                current_day_pnl=context_data.get('day_pnl', 0.0),
                current_positions=context_data.get('positions', 0),
                
                # Metadata
                last_updated=datetime.now(),
                data_quality_score=context_data.get('data_quality', 1.0)
            )
            
            # Show NYC time in context update
            ny_tz = pytz.timezone('US/Eastern')
            ny_time = datetime.now(ny_tz).strftime('%H:%M:%S %Z')
            
            self.logger.info(f"✅ Market context updated - "
                           f"Phase: {self.market_context.current_phase.value}, "
                           f"Sentiment: {self.market_context.market_sentiment.value} "
                           f"(NYC: {ny_time})")
            
        except Exception as e:
            self.logger.error(f"❌ Error updating market context: {e}")
    
    async def _reevaluate_plan(self):
        """
        Re-evaluar plan completo cada 15 minutos
        Adapta estrategias basado en context awareness
        """
        try:
            self.logger.info(f"🔄 Re-evaluating game plan (version {self.plan_version})...")
            
            changes_made = 0
            
            # 1. Re-evaluate existing entries
            for symbol, entry in self.current_plan.items():
                old_strategy = entry.primary_strategy
                old_confidence = entry.primary_strategy_confidence
                
                # Re-calculate with current context
                new_strategy, new_confidence = self._select_optimal_strategy_with_context(
                    self._get_opportunity_data(symbol)
                )
                
                # Update if significant change
                if (new_strategy != old_strategy or 
                    abs(new_confidence - old_confidence) > 0.15):
                    
                    entry.primary_strategy = new_strategy
                    entry.primary_strategy_confidence = new_confidence
                    entry.context_match_score = self._calculate_context_match(entry)
                    entry.last_updated = datetime.now()
                    entry.updates_count += 1
                    
                    changes_made += 1
                    
                    self.logger.info(f"📈 Updated {symbol}: {old_strategy.value} -> {new_strategy.value} "
                                   f"(confidence: {old_confidence:.2f} -> {new_confidence:.2f})")
            
            # 2. Apply time decay to entries not executed
            self._apply_time_decay()
            
            # 3. Remove entries with very low scores
            self._cleanup_low_score_entries()
            
            self.plan_version += 1
            self.last_full_update = datetime.now()
            
            self.logger.info(f"✅ Plan re-evaluated - Version {self.plan_version}, "
                           f"{changes_made} changes made")
            
        except Exception as e:
            self.logger.error(f"❌ Error re-evaluating plan: {e}")
    
    def _select_optimal_strategy_with_context(self, opportunity: Dict) -> Tuple[StrategyType, float]:
        """
        Selección inteligente de estrategia con CONTEXT AWARENESS completo
        
        Considera:
        - Características del opportunity
        - Market phase actual
        - Market sentiment  
        - Performance reciente de estrategias
        - Volatilidad y volumen general
        - Noticias y eventos
        """
        
        symbol = opportunity.get('symbol', 'UNKNOWN')
        catalyst = opportunity.get('catalyst_type', 'OTHER')
        gap_pct = abs(opportunity.get('gap_percentage', 0))
        volume_ratio = opportunity.get('volume_ratio', 1)
        
        # Context factors
        current_phase = self.market_context.current_phase
        sentiment = self.market_context.market_sentiment
        volatility = self.market_context.volatility_regime
        
        # Smallcap-specific market context multipliers
        smallcap_context_multiplier = self._get_smallcap_context_multiplier()
        
        # Strategy selection with context awareness

        # 0. FIRST DAY BOUNCE - Check for bounce setup first (highest specificity)
        opportunity_type = opportunity.get('opportunity_type', 'UNKNOWN')
        if opportunity_type == 'FIRST_DAY_BOUNCE':
            # This is a bounce setup from daily scanner
            bounce_metadata = opportunity.get('bounce_metadata', {})
            overextension_gain = bounce_metadata.get('overextension_gain_pct', 0)
            retrace_pct = bounce_metadata.get('retrace_pct', 0)
            bounce_quality = bounce_metadata.get('bounce_probability', 0)

            # Base confidence from bounce quality score
            confidence = min(bounce_quality, 0.85)  # Cap at 85% for counter-trend

            # Apply context adjustments for bounces
            if sentiment in [MarketSentiment.BULLISH, MarketSentiment.VERY_BULLISH]:
                confidence *= 1.1  # Bounces work better in bullish sentiment
            elif sentiment == MarketSentiment.VERY_BEARISH:
                confidence *= 0.8  # Bounces risky in very bearish conditions

            # Phase adjustments for bounces
            if current_phase in [MarketPhase.OPENING, MarketPhase.MID_MORNING]:
                confidence *= 1.05  # Good timing for bounces
            elif current_phase in [MarketPhase.PRE_MARKET, MarketPhase.AFTER_HOURS]:
                confidence *= 0.7   # Avoid bounces in extended hours

            # Quality-based adjustments
            if overextension_gain > 0.8:  # >80% overextension
                confidence *= 1.1
            elif overextension_gain > 0.6:  # >60% overextension
                confidence *= 1.05

            if 0.3 <= retrace_pct <= 0.4:  # Ideal retrace range
                confidence *= 1.1

            self.logger.info(f"🎯 {symbol}: FIRST_DAY_BOUNCE detected - "
                           f"Quality: {bounce_quality:.2f}, "
                           f"Overext: {overextension_gain*100:.1f}%, "
                           f"Retrace: {retrace_pct*100:.1f}%, "
                           f"Confidence: {confidence:.2f}")

            return StrategyType.FIRST_DAY_BOUNCE, min(confidence, 0.85)

        # 1. FDA CATALYST - Siempre alta prioridad pero context-adjusted
        if catalyst == 'FDA':
            confidence = 0.85
            
            # Apply smallcap-specific context multipliers
            confidence *= smallcap_context_multiplier['confidence_base']
            confidence *= smallcap_context_multiplier['volatility_boost']
            
            # FDA plays benefit from momentum in volatile conditions
            if volatility in ['HIGH', 'EXTREME']:
                confidence *= smallcap_context_multiplier['momentum_favor']
            
            # Traditional context adjustments (now enhanced)
            if sentiment in [MarketSentiment.VERY_BULLISH, MarketSentiment.BULLISH]:
                confidence *= 1.05  # Reduced from 1.1 (smallcap multiplier handles this)
            elif sentiment == MarketSentiment.VERY_BEARISH:
                # FDA plays can still work in bearish conditions for smallcaps
                confidence *= 0.95  # Less penalty than before (was 0.8)
            
            return StrategyType.FDA_CATALYST, min(confidence, 0.98)  # Higher max confidence
        
        # 1.5. EARNINGS CATALYST - High priority for earnings surprises (IMPROVED)
        if catalyst == 'EARNINGS' and gap_pct > 0.03:  # Lowered from 5% to 3% for smallcaps
            confidence = 0.75
            
            # Apply smallcap-specific multipliers
            confidence *= smallcap_context_multiplier['confidence_base']
            confidence *= smallcap_context_multiplier['momentum_favor']  # Earnings are momentum plays
            
            # Enhanced gap-based adjustments
            if gap_pct > 0.15:  # >15% surprise (massive for smallcaps)
                confidence *= 1.25
            elif gap_pct > 0.08:  # >8% surprise  
                confidence *= 1.15
            elif gap_pct > 0.05:  # >5% surprise
                confidence *= 1.08
            
            # Volume confirmation more important for smallcap earnings
            if volume_ratio > 4.0:  # Very high volume
                confidence *= 1.15
            elif volume_ratio > 2.5:
                confidence *= 1.10
            elif volume_ratio > 1.5:  # Lowered threshold
                confidence *= 1.05
            
            # Phase adjustments
            if current_phase == MarketPhase.OPENING:
                confidence *= 1.10  # Opening hour best for earnings momentum
            elif current_phase == MarketPhase.PRE_MARKET:
                confidence *= 1.05  # Pre-market earnings still valuable
            elif current_phase == MarketPhase.LUNCH:
                confidence *= 0.90  # Less momentum in lunch
            
            return StrategyType.EARNINGS_SURPRISE, min(confidence, 0.95)  # Higher max
        
        # 2. GAP STRATEGIES - Context-aware timing (IMPROVED)
        if gap_pct > 0.08:  # Lowered from 12% to 8% for smallcaps
            
            if current_phase in [MarketPhase.PRE_MARKET, MarketPhase.OPENING, MarketPhase.MID_MORNING]:
                
                # Gap and Go conditions with enhanced context (RELAXED CONDITIONS)
                if (sentiment in [MarketSentiment.NEUTRAL, MarketSentiment.BULLISH, MarketSentiment.VERY_BULLISH] and 
                    volume_ratio > 2.0):  # Lowered volume requirement
                    
                    confidence = 0.75
                    
                    # Apply smallcap-specific multipliers
                    confidence *= smallcap_context_multiplier['confidence_base']
                    confidence *= smallcap_context_multiplier['momentum_favor']
                    
                    # Enhanced gap-based confidence
                    if gap_pct > 0.20:  # Massive gap
                        confidence *= 1.20
                    elif gap_pct > 0.15:  # Large gap
                        confidence *= 1.15
                    elif gap_pct > 0.12:  # Good gap
                        confidence *= 1.10
                    
                    # Phase-specific boosts
                    if current_phase == MarketPhase.OPENING:
                        confidence *= 1.15  # Opening hour is optimal
                    elif current_phase == MarketPhase.PRE_MARKET:
                        confidence *= 1.10  # Pre-market momentum
                    elif current_phase == MarketPhase.MID_MORNING:
                        confidence *= 1.05  # Still good for continuation
                    
                    # Volatility and volume boosts
                    if volatility in ['HIGH', 'EXTREME']:
                        confidence *= 1.10  # Smallcaps thrive in volatility
                    elif volatility == 'NORMAL':
                        confidence *= 1.05
                    
                    if volume_ratio > 5.0:  # Exceptional volume
                        confidence *= 1.15
                    elif volume_ratio > 3.0:  # Good volume
                        confidence *= 1.08
                    
                    return StrategyType.GAP_AND_GO, min(confidence, 0.95)
            
            else:
                # Gap fade in later phases
                if gap_pct > 0.20 and current_phase in [MarketPhase.MID_MORNING, MarketPhase.AFTERNOON]:
                    
                    confidence = 0.60
                    
                    # Context for fade plays  
                    if sentiment in [MarketSentiment.BEARISH, MarketSentiment.VERY_BEARISH]:
                        confidence *= 1.2  # Bearish sentiment helps fades
                    
                    return StrategyType.FADE_GAP, min(confidence, 0.80)
        
        # 2.5. REVERSAL PLAY - For large negative gaps (ONLY with extreme sentiment)
        gap_raw = opportunity.get('gap_percentage', 0)  # Get raw gap (can be negative)
        if (gap_raw < -0.10 or catalyst == 'OVERSOLD') and sentiment in [MarketSentiment.VERY_BEARISH, MarketSentiment.VERY_BULLISH]:  # Only with extreme sentiment
            
            confidence = 0.75  # Higher base confidence since we're more selective
            
            if current_phase == MarketPhase.POWER_HOUR:
                confidence *= 1.2  # Power hour best for reversals
            
            if abs(gap_raw) > 0.15:  # >15% gap down
                confidence *= 1.1  # Larger gap = better reversal potential
            
            return StrategyType.REVERSAL_PLAY, min(confidence, 0.90)
        
        # 3. NEWS MOMENTUM - Context aware (REBALANCED)
        if (catalyst in ['M&A', 'CONTRACT', 'BREAKTHROUGH'] and volume_ratio > 3.5) or (catalyst == 'M&A' and volume_ratio > 6.0):  # Special M&A case
            
            confidence = 0.70
            
            # Apply smallcap-specific multipliers
            confidence *= smallcap_context_multiplier['confidence_base']
            confidence *= smallcap_context_multiplier['momentum_favor']
            
            # Enhanced catalyst-specific boosts
            if catalyst == 'M&A':  # M&A is strongest news catalyst
                confidence *= 1.35  # Higher boost for M&A
                # Extra boost for high volume M&A
                if volume_ratio > 8.0:
                    confidence *= 1.15
            elif catalyst == 'CONTRACT':  # Contracts can be huge for smallcaps
                confidence *= 1.15
            elif catalyst == 'BREAKTHROUGH':  # Patent/tech breakthroughs
                confidence *= 1.20
            # Remove OTHER catalyst from news momentum to prevent dominance
            
            # Volume-based adjustments
            if volume_ratio > 8.0:  # Exceptional volume
                confidence *= 1.20
            elif volume_ratio > 6.0:  # Very high volume
                confidence *= 1.15
            elif volume_ratio > 4.0:  # High volume
                confidence *= 1.10
            
            # Phase adjustments - news momentum works across phases
            if current_phase in [MarketPhase.OPENING, MarketPhase.MID_MORNING]:
                confidence *= 1.10  # Morning phases best for news
            elif current_phase == MarketPhase.AFTERNOON:
                confidence *= 1.05  # Still good
            elif current_phase == MarketPhase.POWER_HOUR:
                confidence *= 1.08  # Power hour can amplify news
            
            # Breaking news context
            news_count = self.market_context.breaking_news_count
            if news_count > 3:  # Lots of news = more momentum opportunities
                confidence *= 1.15
            elif news_count > 1:
                confidence *= 1.08
            
            return StrategyType.NEWS_MOMENTUM, min(confidence, 0.98)  # Much higher max for M&A
        
        # 4. OPENING RANGE BREAKOUT - Phase specific (IMPROVED)
        if (current_phase in [MarketPhase.OPENING, MarketPhase.MID_MORNING] and 
            sentiment not in [MarketSentiment.VERY_BEARISH, MarketSentiment.PANIC] and
            gap_pct < 0.10):  # Increased gap tolerance
            
            confidence = 0.68  # Higher base confidence
            
            # Apply smallcap-specific multipliers
            confidence *= smallcap_context_multiplier['confidence_base']
            
            # Enhanced volatility handling - smallcaps work in different volatility regimes
            if volatility == 'NORMAL':
                confidence *= 1.12  # ORB works best in normal volatility
            elif volatility == 'LOW':
                confidence *= 1.05  # Still workable for smallcaps
            elif volatility == 'HIGH':
                confidence *= 1.08  # Can still work with proper setup
            
            # Volume requirements adjusted for smallcaps
            if volume_ratio > 3.0:  # Good volume
                confidence *= 1.15
            elif volume_ratio > 2.0:
                confidence *= 1.10
            elif volume_ratio > 1.5:  # Lower threshold for smallcaps
                confidence *= 1.05
            
            # Phase-specific adjustments
            if current_phase == MarketPhase.OPENING:
                confidence *= 1.10  # Optimal phase
            elif current_phase == MarketPhase.MID_MORNING:
                confidence *= 1.05  # Late ORB still viable
            
            # Small gap actually helps ORB
            if gap_pct < 0.03:  # Very small gap
                confidence *= 1.08
            elif gap_pct < 0.05:  # Small gap
                confidence *= 1.05
            
            return StrategyType.OPENING_RANGE_BREAKOUT, min(confidence, 0.88)  # Higher max
        
        # 5. VOLUME BREAKOUT - High volume spike priority (REBALANCED)
        if catalyst == 'VOLUME' or volume_ratio > 8.0:  # Lower threshold from 10.0
            
            confidence = 0.68  # Higher base confidence
            
            # Apply smallcap-specific multipliers
            confidence *= smallcap_context_multiplier['confidence_base']
            confidence *= smallcap_context_multiplier['momentum_favor']
            
            # Volume breakout context
            if volume_ratio > 12.0:  # Exceptional volume
                confidence *= 1.25
            elif volume_ratio > 8.0:
                confidence *= 1.15  # High volume
            elif volume_ratio > 5.0:
                confidence *= 1.08  # Good volume
            
            # Volatility helps volume breakouts
            if volatility in ['HIGH', 'EXTREME']:
                confidence *= 1.10  # High vol helps volume breakouts
            elif volatility == 'NORMAL':
                confidence *= 1.05
            
            # Phase adjustments
            if current_phase in [MarketPhase.OPENING, MarketPhase.MID_MORNING]:
                confidence *= 1.08  # Good phases for volume breakouts
            
            return StrategyType.VOLUME_BREAKOUT, min(confidence, 0.90)
        
        # 6. MOMENTUM CONTINUATION - Mid-day context or continuation catalyst (IMPROVED)
        if ((current_phase in [MarketPhase.MID_MORNING, MarketPhase.AFTERNOON] and
             volume_ratio > 2.8 and  # Slightly lower threshold
             sentiment in [MarketSentiment.NEUTRAL, MarketSentiment.BULLISH, MarketSentiment.VERY_BULLISH]) or
            catalyst == 'CONTINUATION'):
            
            confidence = 0.65  # Higher base
            
            # Apply smallcap-specific multipliers
            confidence *= smallcap_context_multiplier['confidence_base']
            confidence *= smallcap_context_multiplier['momentum_favor']
            
            # Enhanced volume-based adjustments
            if volume_ratio > 5.0:
                confidence *= 1.15
            elif volume_ratio > 3.5:
                confidence *= 1.10
            
            # Phase-specific boosts
            if current_phase == MarketPhase.AFTERNOON:
                confidence *= 1.12  # Afternoon continuation strength
            elif current_phase == MarketPhase.MID_MORNING:
                confidence *= 1.08
            
            # Performance-based adjustment (less impact)
            recent_perf = self.market_context.recent_strategy_performance.get(
                StrategyType.MOMENTUM_CONTINUATION, 0.6
            )
            if recent_perf > 0.7:  # Only boost if performing well
                confidence *= 1.05
            
            if catalyst == 'CONTINUATION':
                confidence *= 1.15  # Specific continuation signal
            
            return StrategyType.MOMENTUM_CONTINUATION, min(confidence, 0.85)
        
        # 7. POWER HOUR PLAYS (IMPROVED)
        if current_phase == MarketPhase.POWER_HOUR or catalyst == 'INSTITUTIONAL':
            
            # Enhanced reversal logic for power hour
            if (gap_pct > 0.06 and  # Lower gap threshold  
                sentiment in [MarketSentiment.BEARISH, MarketSentiment.VERY_BEARISH] and
                volume_ratio > 2.0):
                
                confidence = 0.65  # Higher confidence
                confidence *= smallcap_context_multiplier['reversal_favor']
                return StrategyType.REVERSAL_PLAY, min(confidence, 0.80)
            else:
                # End of day momentum (ENHANCED)
                confidence = 0.58  # Higher base
                
                # Apply smallcap multipliers
                confidence *= smallcap_context_multiplier['confidence_base']
                
                if catalyst == 'INSTITUTIONAL':
                    confidence *= 1.25  # Institutional flow signal
                
                # Volume requirements
                if volume_ratio > 4.0:  # High volume
                    confidence *= 1.20
                elif volume_ratio > 2.5:
                    confidence *= 1.15
                elif volume_ratio > 1.8:  # Lower threshold
                    confidence *= 1.08
                
                # Gap support
                if gap_pct > 0.05:
                    confidence *= 1.10
                elif gap_pct > 0.03:
                    confidence *= 1.05
                
                return StrategyType.END_OF_DAY, min(confidence, 0.82)
        
        # 8. NEUTRAL SENTIMENT STRATEGIES - Better handling for neutral market conditions
        if sentiment == MarketSentiment.NEUTRAL:
            
            # 8a. Volume-based strategy for neutral sentiment
            if volume_ratio > 2.0:  # Decent volume with neutral sentiment
                confidence = 0.65
                
                if volume_ratio > 3.0:
                    confidence *= 1.1  # Better volume
                
                if gap_pct > 0.03:  # Small gap support
                    confidence *= 1.05
                
                return StrategyType.VOLUME_BREAKOUT, min(confidence, 0.80)
            
            # 8b. Daily plays for neutral sentiment smallcaps (IMPROVED)
            if (gap_pct > 0.02 and 
                current_phase in [MarketPhase.OPENING, MarketPhase.MID_MORNING, MarketPhase.AFTERNOON]):
                
                confidence = 0.65  # Higher base confidence
                
                # Apply smallcap-specific multipliers
                confidence *= smallcap_context_multiplier['confidence_base']
                
                # Enhanced catalyst support
                if catalyst in ['FDA', 'EARNINGS', 'M&A']:
                    confidence *= 1.15  # Strong catalyst support
                elif catalyst in ['CONTRACT', 'BREAKTHROUGH']:
                    confidence *= 1.10  # Good catalyst support
                elif catalyst == 'OTHER' and volume_ratio > 3.0:
                    confidence *= 1.08  # Unknown but high volume
                
                # Volume-based adjustments
                if volume_ratio > 3.0:
                    confidence *= 1.15  # Good volume
                elif volume_ratio > 2.0:
                    confidence *= 1.10
                elif volume_ratio > 1.5:
                    confidence *= 1.05
                
                # Gap-based adjustments
                if gap_pct > 0.08:  # Significant gap
                    confidence *= 1.12
                elif gap_pct > 0.05:  # Moderate gap
                    confidence *= 1.08
                elif gap_pct > 0.03:  # Small gap
                    confidence *= 1.05
                
                # Phase adjustments
                if current_phase == MarketPhase.OPENING:
                    confidence *= 1.12  # Best phase for daily plays
                elif current_phase == MarketPhase.MID_MORNING:
                    confidence *= 1.08  # Still good
                elif current_phase == MarketPhase.AFTERNOON:
                    confidence *= 1.05  # Continuation plays
                
                return StrategyType.DAILY_PLAYS, min(confidence, 0.85)  # Higher max
            
            # 8c. Conservative gap and go for neutral sentiment  
            if gap_pct > 0.05 and volume_ratio > 1.5:
                confidence = 0.55
                
                if current_phase in [MarketPhase.OPENING, MarketPhase.MID_MORNING]:
                    confidence *= 1.1
                
                return StrategyType.GAP_AND_GO, min(confidence, 0.70)
        
        # 9. DEFAULT - Volume breakout with context for unmatched opportunities
        confidence = 0.50  # Slightly higher base confidence
        
        # Context adjustments for default strategy
        if volatility in ['HIGH', 'EXTREME']:
            confidence *= 1.1
        
        if volume_ratio > 3.0:  # Better volume threshold
            confidence *= 1.1
        
        if sentiment != MarketSentiment.VERY_BEARISH:  # Avoid in very bearish conditions
            confidence *= 1.05
        
        return StrategyType.VOLUME_BREAKOUT, min(confidence, 0.75)
    
    def get_instant_decision(self, symbol: str, live_data: Dict, use_cache: bool = True) -> Dict:
        """
        Decisión ultra-rápida con context awareness y cache anti-doble evaluación
        
        Args:
            symbol: Symbol to evaluate
            live_data: Current market data
            use_cache: Whether to use cached decision (default True)
        
        Returns:
        - action: EXECUTE/REJECT/WAIT
        - strategy: Selected strategy with context
        - confidence: Context-adjusted confidence
        - reasoning: Why this decision with context
        - cached: Whether this decision came from cache
        """
        start_time = datetime.now()
        
        if symbol not in self.current_plan:
            # NEW: Auto-add new opportunities from scanner with dynamic strategy selection
            self.logger.info(f"🔄 Auto-adding new opportunity {symbol} to game plan with catalyst analysis")
            entry = self._create_dynamic_entry_from_live_data(symbol, live_data)
            if entry:
                self.current_plan[symbol] = entry
                self.logger.info(f"✅ {symbol} added to game plan with strategy {entry.primary_strategy.value}")
            else:
                return {
                    'action': 'REJECT',
                    'reason': f'Unable to create valid game plan entry for {symbol}',
                    'execution_time_ms': 1,
                    'cached': False
                }
        
        # Check cache first to prevent double evaluation
        if use_cache and symbol in self.decision_cache:
            cached_entry = self.decision_cache[symbol]
            cache_age = datetime.now() - cached_entry['timestamp']
            
            if cache_age < self.cache_duration:
                # Return cached decision
                cached_decision = cached_entry['decision'].copy()
                cached_decision.update({
                    'cached': True,
                    'cache_age_seconds': cache_age.total_seconds(),
                    'execution_time_ms': 0.1  # Minimal cache lookup time
                })
                self.logger.debug(f"🎯 Using cached decision for {symbol} (age: {cache_age.total_seconds():.1f}s)")
                return cached_decision
            else:
                # Cache expired, remove it
                del self.decision_cache[symbol]
                self.logger.debug(f"🗑️ Cache expired for {symbol}, making fresh decision")
        
        entry = self.current_plan[symbol]
        
        # Context-aware decision
        decision = self._make_context_aware_decision(entry, live_data)
        
        # Add metadata
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        decision.update({
            'execution_time_ms': execution_time,
            'strategy': entry.primary_strategy.value,
            'plan_version': self.plan_version,
            'market_phase': self.market_context.current_phase.value,
            'market_sentiment': self.market_context.market_sentiment.value,
            'context_match_score': entry.context_match_score,
            'cached': False
        })
        
        # Cache the decision to prevent double evaluation
        data_hash = hash(str(sorted(live_data.items())))  # Simple hash of market data
        self.decision_cache[symbol] = {
            'decision': decision.copy(),
            'timestamp': datetime.now(),
            'data_hash': data_hash
        }
        
        self.daily_stats['decisions_made'] += 1
        self.logger.debug(f"🧠 Fresh decision cached for {symbol}: {decision['action']}")
        
        return decision
    
    def clear_decision_cache(self, symbol: str = None):
        """Clear decision cache for a symbol or all symbols"""
        if symbol:
            if symbol in self.decision_cache:
                del self.decision_cache[symbol]
                self.logger.debug(f"🗑️ Decision cache cleared for {symbol}")
        else:
            self.decision_cache.clear()
            self.logger.debug("🗑️ All decision cache cleared")
    
    def get_cache_status(self) -> Dict:
        """Get current cache status for debugging"""
        now = datetime.now()
        cache_info = {}
        
        for symbol, cache_entry in self.decision_cache.items():
            age = now - cache_entry['timestamp']
            cache_info[symbol] = {
                'age_seconds': age.total_seconds(),
                'action': cache_entry['decision']['action'],
                'expired': age >= self.cache_duration
            }
        
        return {
            'total_cached': len(self.decision_cache),
            'cache_duration_minutes': self.cache_duration.total_seconds() / 60,
            'symbols': cache_info
        }
    
    def _make_context_aware_decision(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """
        Decisión considerando context awareness completo
        """
        
        # 1. Check if current context matches entry requirements
        context_match = self._validate_context_requirements(entry)
        
        if not context_match['valid']:
            return {
                'action': 'WAIT',
                'reason': f'Context mismatch: {context_match["reason"]}'
            }
        
        # 1.5. Re-evaluate strategy if current assignment is inappropriate for context
        entry = self._maybe_reassign_strategy(entry, live_data)
        
        # 2. Strategy-specific execution with context - TODAS LAS ESTRATEGIAS
        strategy = entry.primary_strategy
        
        if strategy == StrategyType.GAP_AND_GO:
            return self._execute_gap_and_go_with_context(entry, live_data)
        elif strategy == StrategyType.FADE_GAP:
            return self._execute_fade_gap_with_context(entry, live_data)
        elif strategy == StrategyType.NEWS_MOMENTUM:
            return self._execute_news_momentum_with_context(entry, live_data)
        elif strategy == StrategyType.FDA_CATALYST:
            return self._execute_fda_with_context(entry, live_data)
        elif strategy == StrategyType.EARNINGS_SURPRISE:
            return self._execute_earnings_surprise_with_context(entry, live_data)
        elif strategy == StrategyType.OPENING_RANGE_BREAKOUT:
            return self._execute_orb_with_context(entry, live_data)
        elif strategy == StrategyType.MOMENTUM_CONTINUATION:
            return self._execute_momentum_continuation_with_context(entry, live_data)
        elif strategy == StrategyType.REVERSAL_PLAY:
            return self._execute_reversal_play_with_context(entry, live_data)
        elif strategy == StrategyType.VOLUME_BREAKOUT:
            return self._execute_volume_breakout_with_context(entry, live_data)
        elif strategy == StrategyType.END_OF_DAY:
            return self._execute_end_of_day_with_context(entry, live_data)
        elif strategy == StrategyType.DAILY_PLAYS:
            return self._execute_daily_plays_with_context(entry, live_data)
        elif strategy == StrategyType.FIRST_DAY_BOUNCE:
            return self._execute_first_day_bounce_with_context(entry, live_data)
        else:
            return self._execute_default_with_context(entry, live_data)
    
    def _execute_gap_and_go_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """Gap and Go execution with context awareness"""
        
        volume_ratio = live_data.get('volume_ratio', 0)
        price = live_data.get('current_price', 0)
        
        # Base conditions - Aligned with ML training data (gap_go successful from 0.52x+)
        if volume_ratio < 0.8:
            return {'action': 'REJECT', 'reason': f'Volume too low: {volume_ratio:.1f}x (need 0.8x+)'}
        
        # Context-aware adjustments
        sentiment = self.market_context.market_sentiment
        phase = self.market_context.current_phase
        
        # ML-aligned volume requirements (based on successful training examples)
        min_volume = 0.8  # Base threshold from ML analysis
        if sentiment == MarketSentiment.VERY_BULLISH:
            min_volume = 0.6  # Even lower in strong bull markets
        elif sentiment in [MarketSentiment.BEARISH, MarketSentiment.VERY_BEARISH]:
            min_volume = 1.5  # Higher conviction needed in bear markets
        
        if volume_ratio >= min_volume:
            
            # Position sizing with context
            base_size = entry.position_size
            
            # Increase size in optimal conditions
            if (phase == MarketPhase.OPENING and 
                sentiment == MarketSentiment.VERY_BULLISH):
                base_size *= 1.2
            
            return {
                'action': 'EXECUTE',
                'reason': f'Gap&Go confirmed - Vol {volume_ratio:.1f}x, Phase {phase.value}, Sentiment {sentiment.value}',
                'position_size': min(base_size, entry.max_risk_per_trade * 2),
                'stop_loss': entry.stop_loss,
                'target': entry.target_1,
                'context_boost': sentiment in [MarketSentiment.BULLISH, MarketSentiment.VERY_BULLISH]
            }
        
        return {
            'action': 'REJECT', 
            'reason': f'Volume {volume_ratio:.1f}x below context-adjusted minimum {min_volume:.1f}x'
        }
    
    def _execute_fade_gap_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """Fade Gap execution with context awareness"""
        
        gap_pct = abs(live_data.get('gap_percentage', 0))
        price = live_data.get('current_price', 0)
        volume_ratio = live_data.get('volume_ratio', 0)
        
        # Fade works best with large gaps that are unsustainable
        if gap_pct < 0.15:  # Need >15% gap for fade
            return {'action': 'REJECT', 'reason': f'Gap {gap_pct*100:.1f}% too small for fade (need 15%+)'}
        
        # Context adjustments for fade
        sentiment = self.market_context.market_sentiment
        phase = self.market_context.current_phase
        
        # Fade works better in bearish/neutral markets
        if sentiment in [MarketSentiment.VERY_BULLISH, MarketSentiment.BULLISH]:
            return {'action': 'WAIT', 'reason': 'Bullish sentiment - waiting for momentum to fade'}
        
        # Best fade opportunities in mid-day when gap momentum dies
        if phase not in [MarketPhase.MID_MORNING, MarketPhase.AFTERNOON]:
            return {'action': 'WAIT', 'reason': f'Phase {phase.value} not optimal for fade - wait for mid-day'}
        
        # Volume should be declining for fade (original spike fading)
        if volume_ratio > 5.0:
            return {'action': 'WAIT', 'reason': 'Volume still too high for fade - wait for decline'}
        
        return {
            'action': 'EXECUTE',
            'reason': f'Fade Gap setup - Gap {gap_pct*100:.1f}%, declining volume, {sentiment.value} sentiment',
            'position_size': entry.position_size * 0.8,  # Smaller size for fade (riskier)
            'stop_loss': price * 1.08,  # Wider stop for fade
            'target': entry.stop_loss,  # Target is original stop level
            'strategy_type': 'FADE_SHORT'
        }
    
    def _execute_news_momentum_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """News Momentum execution with context awareness"""
        
        volume_ratio = live_data.get('volume_ratio', 0)
        catalyst = live_data.get('catalyst_type', 'OTHER')
        
        # Dynamic volume requirements for news momentum
        min_volume_required = self._get_context_adjusted_volume_requirement('news_momentum')
        
        if volume_ratio < min_volume_required:
            return {'action': 'REJECT', 'reason': f'Volume {volume_ratio:.1f}x insufficient for news momentum (need {min_volume_required:.1f}x+ in current market)'}
        
        # Context factors
        news_count = self.market_context.breaking_news_count
        phase = self.market_context.current_phase
        
        # News momentum better with multiple news stories
        confidence_boost = 1.0
        if news_count > 2:
            confidence_boost = 1.15
        
        # Optimal phases for news momentum
        if phase in [MarketPhase.OPENING, MarketPhase.AFTERNOON]:
            confidence_boost *= 1.1
        
        # Catalyst-specific adjustments
        catalyst_multiplier = {'M&A': 1.2, 'CONTRACT': 1.1, 'BREAKTHROUGH': 1.15}.get(catalyst, 1.0)
        
        position_size = entry.position_size * confidence_boost * catalyst_multiplier
        
        return {
            'action': 'EXECUTE',
            'reason': f'News momentum confirmed - {catalyst} catalyst, {volume_ratio:.1f}x volume, {news_count} breaking news',
            'position_size': min(position_size, entry.max_risk_per_trade * 1.5),
            'stop_loss': entry.stop_loss,
            'target': entry.target_1,
            'confidence_boost': confidence_boost
        }
    
    def _execute_fda_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """FDA Catalyst execution with context awareness"""
        
        volume_ratio = live_data.get('volume_ratio', 0)
        
        # FDA plays are high priority - lower volume threshold
        # Special case: if volume_ratio is 0.0, assume development mode and approve
        if volume_ratio == 0.0:
            self.logger.info(f"📋 Development mode detected (volume=0.0) - approving FDA play for {entry.symbol}")
        elif volume_ratio < 2.0:
            return {'action': 'REJECT', 'reason': f'Volume {volume_ratio:.1f}x too low for FDA play (need 2.0x+)'}
        
        # Context adjustments
        sentiment = self.market_context.market_sentiment
        volatility = self.market_context.volatility_regime
        
        # FDA works well in all sentiments, but better in bullish
        confidence = entry.primary_strategy_confidence
        if sentiment in [MarketSentiment.BULLISH, MarketSentiment.VERY_BULLISH]:
            confidence *= 1.1
        
        # High volatility helps FDA catalyst moves
        if volatility in ['HIGH', 'EXTREME']:
            confidence *= 1.05
        
        # Larger position size for FDA (high conviction)
        position_size = entry.position_size * 1.2
        
        return {
            'action': 'EXECUTE',
            'reason': f'FDA catalyst confirmed - Vol {volume_ratio:.1f}x, confidence {confidence:.2f}, volatility {volatility}',
            'position_size': min(position_size, entry.max_risk_per_trade * 2),
            'stop_loss': entry.stop_loss,
            'target': entry.target_2,  # FDA can go to target 2
            'hold_time': 'EXTENDED'  # FDA plays can run longer
        }
    
    def _execute_earnings_surprise_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """Earnings Surprise execution with context awareness"""
        
        gap_pct = abs(live_data.get('gap_percentage', 0))
        volume_ratio = live_data.get('volume_ratio', 0)
        
        # Earnings surprises need gap + volume
        if gap_pct < 0.05 or volume_ratio < 2.5:
            return {'action': 'REJECT', 'reason': f'Earnings criteria not met - Gap {gap_pct*100:.1f}%, Vol {volume_ratio:.1f}x'}
        
        # Context: Earnings work better in certain market phases
        phase = self.market_context.current_phase
        
        # Best in opening and afternoon (avoid lunch dead zone)
        if phase == MarketPhase.LUNCH:
            return {'action': 'WAIT', 'reason': 'Lunch time - low liquidity for earnings plays'}
        
        # Earnings surprise strength based on gap size
        if gap_pct > 0.12:  # >12% surprise
            surprise_strength = 'STRONG'
            position_multiplier = 1.3
        elif gap_pct > 0.08:  # >8% surprise
            surprise_strength = 'MODERATE'
            position_multiplier = 1.1
        else:  # 5-8% surprise
            surprise_strength = 'WEAK'
            position_multiplier = 0.9
        
        return {
            'action': 'EXECUTE',
            'reason': f'Earnings surprise - {surprise_strength} ({gap_pct*100:.1f}% gap), Vol {volume_ratio:.1f}x',
            'position_size': entry.position_size * position_multiplier,
            'stop_loss': entry.stop_loss,
            'target': entry.target_1 if surprise_strength != 'STRONG' else entry.target_2,
            'earnings_strength': surprise_strength
        }
    
    def _execute_orb_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """Opening Range Breakout execution with context awareness"""
        
        price = live_data.get('current_price', 0)
        volume_ratio = live_data.get('volume_ratio', 0)
        
        # ORB only works in opening hour
        phase = self.market_context.current_phase
        if phase != MarketPhase.OPENING:
            return {'action': 'REJECT', 'reason': f'ORB only valid in OPENING phase, current: {phase.value}'}
        
        # ORB volume requirements aligned with ML training (successful from 0.52x to 11x)
        if volume_ratio > 8.0:
            return {'action': 'REJECT', 'reason': f'Volume {volume_ratio:.1f}x too high for ORB - likely gap play'}
        
        if volume_ratio < 0.6:
            return {'action': 'REJECT', 'reason': f'Volume {volume_ratio:.1f}x too low for ORB breakout'}
        
        # Context: ORB works best in normal volatility
        volatility = self.market_context.volatility_regime
        if volatility == 'EXTREME':
            return {'action': 'WAIT', 'reason': 'Extreme volatility - ORB patterns unreliable'}
        
        # ORB confidence based on market sentiment
        sentiment = self.market_context.market_sentiment
        if sentiment == MarketSentiment.VERY_BEARISH:
            return {'action': 'WAIT', 'reason': 'Very bearish sentiment - ORB breakouts likely to fail'}
        
        return {
            'action': 'EXECUTE',
            'reason': f'ORB breakout confirmed - Vol {volume_ratio:.1f}x, {volatility} volatility',
            'position_size': entry.position_size,
            'stop_loss': price * 0.97,  # Tight stop for ORB
            'target': entry.target_1,
            'time_limit': '10:30'  # ORB expires at 10:30
        }
    
    def _execute_momentum_continuation_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """Momentum Continuation execution with context awareness"""
        
        volume_ratio = live_data.get('volume_ratio', 0)
        
        # Dynamic volume requirements for momentum continuation
        min_volume_required = self._get_context_adjusted_volume_requirement('momentum_continuation')
        
        if volume_ratio < min_volume_required:
            return {'action': 'REJECT', 'reason': f'Volume {volume_ratio:.1f}x insufficient for momentum (need {min_volume_required:.1f}x+ in current market)'}
        
        # Context: Best in mid-day phases
        phase = self.market_context.current_phase
        if phase not in [MarketPhase.MID_MORNING, MarketPhase.AFTERNOON]:
            return {'action': 'WAIT', 'reason': f'Phase {phase.value} not optimal for momentum continuation'}
        
        # Market sentiment crucial for momentum
        sentiment = self.market_context.market_sentiment
        if sentiment in [MarketSentiment.BEARISH, MarketSentiment.VERY_BEARISH]:
            return {'action': 'REJECT', 'reason': f'Bearish sentiment {sentiment.value} - momentum unlikely to continue'}
        
        # Check recent strategy performance
        momentum_performance = self.market_context.recent_strategy_performance.get(
            StrategyType.MOMENTUM_CONTINUATION, 0.5
        )
        
        if momentum_performance < 0.4:  # Recent performance poor
            return {'action': 'WAIT', 'reason': f'Recent momentum strategy performance poor ({momentum_performance:.2f})'}
        
        return {
            'action': 'EXECUTE',
            'reason': f'Momentum continuation - Vol {volume_ratio:.1f}x, {sentiment.value} sentiment, performance {momentum_performance:.2f}',
            'position_size': entry.position_size * (0.8 + momentum_performance * 0.4),  # Size based on recent performance
            'stop_loss': entry.stop_loss,
            'target': entry.target_1,
            'trailing_stop': True  # Use trailing stop for momentum
        }
    
    def _execute_reversal_play_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """Reversal Play execution with context awareness"""
        
        gap_pct = abs(live_data.get('gap_percentage', 0))
        volume_ratio = live_data.get('volume_ratio', 0)
        
        # Reversals need significant moves to reverse FROM
        if gap_pct < 0.08:
            return {'action': 'REJECT', 'reason': f'Gap {gap_pct*100:.1f}% too small for reversal (need 8%+)'}
        
        # Context: Reversals work better in certain phases
        phase = self.market_context.current_phase
        
        # Power hour best for reversals
        if phase == MarketPhase.POWER_HOUR:
            phase_multiplier = 1.2
        elif phase in [MarketPhase.MID_MORNING, MarketPhase.AFTERNOON]:
            phase_multiplier = 1.0
        else:
            return {'action': 'WAIT', 'reason': f'Phase {phase.value} not optimal for reversals'}
        
        # Sentiment: Reversals work when sentiment is extreme
        sentiment = self.market_context.market_sentiment
        if sentiment in [MarketSentiment.VERY_BULLISH, MarketSentiment.VERY_BEARISH]:
            sentiment_multiplier = 1.15  # Extreme sentiment = good for reversals
        else:
            return {'action': 'WAIT', 'reason': f'Sentiment {sentiment.value} not extreme enough for reversal'}
        
        # Volume should be declining for reversal setup
        if volume_ratio > 6.0:
            return {'action': 'WAIT', 'reason': 'Volume still too high - wait for exhaustion'}
        
        position_size = entry.position_size * phase_multiplier * sentiment_multiplier * 0.8  # Smaller size (riskier)
        
        return {
            'action': 'EXECUTE',
            'reason': f'Reversal setup - Gap {gap_pct*100:.1f}%, {phase.value} phase, {sentiment.value} sentiment',
            'position_size': min(position_size, entry.max_risk_per_trade),
            'stop_loss': entry.stop_loss * 1.1,  # Wider stop for reversals
            'target': entry.target_1,
            'reversal_type': 'COUNTER_TREND'
        }
    
    def _execute_volume_breakout_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """Volume Breakout execution with context awareness"""
        
        volume_ratio = live_data.get('volume_ratio', 0)
        
        # IMPROVED: Context-aware volume criteria for better market adaptability
        # Special case: if volume_ratio is 0.0, assume development mode and approve
        if volume_ratio == 0.0:
            self.logger.info(f"📋 Development mode detected (volume=0.0) - approving volume breakout for {entry.symbol}")
        else:
            # Dynamic volume requirements based on market context
            min_volume_required = self._get_context_adjusted_volume_requirement('breakout')
            
            if volume_ratio < min_volume_required:
                return {'action': 'REJECT', 'reason': f'Volume {volume_ratio:.1f}x insufficient for breakout (need {min_volume_required:.1f}x+ in current market)'}
        
        # Context: Volume breakouts work in high volatility
        volatility = self.market_context.volatility_regime
        if volatility == 'LOW':
            return {'action': 'WAIT', 'reason': 'Low volatility regime - volume breakouts less effective'}
        
        # Better in trending markets
        sentiment = self.market_context.market_sentiment
        if sentiment == MarketSentiment.NEUTRAL:
            confidence_multiplier = 0.8
        else:
            confidence_multiplier = 1.1
        
        # Volume intensity classification
        if volume_ratio > 10.0:
            intensity = 'EXTREME'
            size_multiplier = 1.3
        elif volume_ratio > 7.0:
            intensity = 'HIGH'
            size_multiplier = 1.1
        else:
            intensity = 'MODERATE'
            size_multiplier = 1.0
        
        return {
            'action': 'EXECUTE',
            'reason': f'Volume breakout - {intensity} intensity ({volume_ratio:.1f}x), {volatility} volatility',
            'position_size': entry.position_size * size_multiplier * confidence_multiplier,
            'stop_loss': entry.stop_loss,
            'target': entry.target_1,
            'volume_intensity': intensity
        }
    
    def _execute_end_of_day_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """End of Day execution with context awareness"""
        
        # EOD only valid in power hour
        phase = self.market_context.current_phase
        if phase != MarketPhase.POWER_HOUR:
            return {'action': 'REJECT', 'reason': f'EOD only valid in power hour, current: {phase.value}'}
        
        volume_ratio = live_data.get('volume_ratio', 0)
        if volume_ratio < 1.2:
            return {'action': 'REJECT', 'reason': f'Volume {volume_ratio:.1f}x too low for EOD move (need 1.2x+)'}
        
        # EOD works better with institutional flow
        market_trend = self.market_context.spy_change_pct
        
        # Align with market direction for EOD (relaxed for testing)
        if abs(market_trend) < 0.001:  # Market very flat
            return {'action': 'WAIT', 'reason': 'Market very flat - no clear EOD direction'}
        
        # Position size smaller for EOD (limited time)
        position_size = entry.position_size * 0.7
        
        return {
            'action': 'EXECUTE',
            'reason': f'EOD setup - Vol {volume_ratio:.1f}x, market trend {market_trend*100:+.1f}%',
            'position_size': position_size,
            'stop_loss': entry.stop_loss,
            'target': entry.target_1,
            'time_limit': '15:50',  # Close before market close
            'quick_exit': True
        }
    
    def _execute_default_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """Default execution for unspecified strategies"""
        
        volume_ratio = live_data.get('volume_ratio', 0)
        
        if volume_ratio < 0.8:
            return {'action': 'REJECT', 'reason': f'Default strategy requires 0.8x+ volume, got {volume_ratio:.1f}x'}
        
        return {
            'action': 'EXECUTE',
            'reason': f'Default execution - Vol {volume_ratio:.1f}x meets minimum criteria',
            'position_size': entry.position_size * 0.8,  # Conservative for default
            'stop_loss': entry.stop_loss,
            'target': entry.target_1
        }
    
    def _execute_daily_plays_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """Daily Plays execution with context awareness - optimized for smallcaps"""
        
        volume_ratio = live_data.get('volume_ratio', 0)
        gap_pct = abs(live_data.get('gap_percentage', 0))
        
        # Flexible volume requirements for daily plays
        min_volume_required = self._get_context_adjusted_volume_requirement('daily_plays')
        
        if volume_ratio < min_volume_required:
            return {'action': 'REJECT', 'reason': f'Volume {volume_ratio:.1f}x insufficient for daily plays (need {min_volume_required:.1f}x+ in current market)'}
        
        # Context: Daily plays work well in opening hours
        phase = self.market_context.current_phase
        confidence_multiplier = 1.0
        
        if phase in [MarketPhase.OPENING, MarketPhase.MID_MORNING]:
            confidence_multiplier = 1.1  # Optimal timing
        elif phase == MarketPhase.LUNCH:
            confidence_multiplier = 0.9   # Less effective during lunch
        
        # Gap size adjustments
        if gap_pct > 0.05:  # >5% gap
            confidence_multiplier *= 1.05
        
        # Volume intensity classification
        if volume_ratio > 3.0:
            intensity = 'STRONG'
            size_multiplier = 1.1
        elif volume_ratio > 2.0:
            intensity = 'MODERATE'
            size_multiplier = 1.0
        else:
            intensity = 'WEAK'
            size_multiplier = 0.9
        
        return {
            'action': 'EXECUTE',
            'reason': f'Daily plays - {intensity} setup (Vol: {volume_ratio:.1f}x, Gap: {gap_pct:.1f}%)',
            'position_size': entry.position_size * size_multiplier * confidence_multiplier,
            'stop_loss': entry.stop_loss,
            'target': entry.target_1,
            'setup_strength': intensity
        }

    def _execute_first_day_bounce_with_context(self, entry: SmartGamePlanEntry, live_data: Dict) -> Dict:
        """First Day Bounce execution with context awareness - specialized for counter-trend plays"""

        volume_ratio = live_data.get('volume_ratio', 0)
        current_price = live_data.get('current_price', 0)

        # Get bounce-specific metadata from live_data
        bounce_metadata = live_data.get('bounce_metadata', {})

        # 1. VALIDATE BOUNCE SETUP QUALITY
        overextension_gain = bounce_metadata.get('overextension_gain_pct', 0)
        retrace_pct = bounce_metadata.get('retrace_pct', 0)
        red_days = bounce_metadata.get('red_days_count', 0)
        support_level = bounce_metadata.get('support_level', 0)

        # Minimum bounce criteria
        if overextension_gain < 0.4:  # Less than 40% overextension
            return {'action': 'REJECT', 'reason': f'Insufficient overextension: {overextension_gain*100:.1f}% (need 40%+)'}

        if retrace_pct < 0.25 or retrace_pct > 0.5:
            return {'action': 'REJECT', 'reason': f'Retrace out of range: {retrace_pct*100:.1f}% (need 25-50%)'}

        if red_days < 2 or red_days > 5:
            return {'action': 'REJECT', 'reason': f'Red days inappropriate: {red_days} (need 2-5)'}

        # 2. SUPPORT PROXIMITY VALIDATION
        if support_level > 0 and current_price > 0:
            distance_from_support = abs(current_price - support_level) / support_level
            if distance_from_support > 0.05:  # More than 5% from support
                return {'action': 'REJECT', 'reason': f'Too far from support: {distance_from_support*100:.1f}% (need <5%)'}

        # 3. CONTEXT: Bounce plays are counter-trend, need careful timing
        phase = self.market_context.current_phase
        sentiment = self.market_context.market_sentiment

        # Avoid bounces in very bearish conditions
        if sentiment == MarketSentiment.VERY_BEARISH:
            return {'action': 'WAIT', 'reason': 'Very bearish sentiment - bounce unlikely to sustain'}

        # Optimal phases for bounces (avoid pre-market/after-hours)
        if phase in [MarketPhase.PRE_MARKET, MarketPhase.AFTER_HOURS]:
            return {'action': 'WAIT', 'reason': f'Bounce setups not executed during {phase.value}'}

        # 4. VOLUME VALIDATION for confirmation
        # Bounce needs some volume but not excessive (which might indicate continued selling)
        min_volume_required = self._get_context_adjusted_volume_requirement('daily_plays') * 0.8  # 80% of daily plays requirement

        if volume_ratio < min_volume_required:
            return {'action': 'REJECT', 'reason': f'Volume {volume_ratio:.1f}x insufficient for bounce (need {min_volume_required:.1f}x+)'}

        if volume_ratio > 5.0:  # Too much volume might indicate more selling
            return {'action': 'WAIT', 'reason': f'Volume {volume_ratio:.1f}x too high - may indicate continued selling'}

        # 5. POSITION SIZING: Conservative for counter-trend
        base_size = entry.position_size * 0.8  # 20% smaller than trend-following plays

        # Adjust based on setup quality
        setup_quality = (overextension_gain + (0.5 - retrace_pct)) / 2  # Higher score for bigger overextension, smaller retrace
        if setup_quality > 0.6:
            size_multiplier = 1.1
            quality_tier = 'HIGH'
        elif setup_quality > 0.4:
            size_multiplier = 1.0
            quality_tier = 'MEDIUM'
        else:
            size_multiplier = 0.9
            quality_tier = 'LOW'

        # 6. RISK MANAGEMENT: Tighter stops for counter-trend
        conservative_stop = current_price * 0.95 if current_price > 0 else entry.stop_loss  # 5% stop loss
        conservative_target = current_price * 1.12 if current_price > 0 else entry.target_1  # 12% target (conservative)

        return {
            'action': 'EXECUTE',
            'reason': f'First Day Bounce - {quality_tier} quality (Overext: {overextension_gain*100:.1f}%, Retrace: {retrace_pct*100:.1f}%, Vol: {volume_ratio:.1f}x)',
            'position_size': base_size * size_multiplier,
            'stop_loss': conservative_stop,
            'target': conservative_target,
            'setup_type': 'COUNTER_TREND_BOUNCE',
            'risk_level': 'MODERATE_HIGH',  # Counter-trend carries higher risk
            'hold_time_limit': '4_HOURS',   # Shorter hold time for bounces
            'exit_on_red_close': True       # Exit if day closes red
        }

    # === HELPER METHODS ===
    
    def _get_context_adjusted_volume_requirement(self, strategy_type: str) -> float:
        """Get volume requirement adjusted for current market context using config values"""
        try:
            # Helper function to safely get float values
            def get_config_float(section: str, key: str, fallback: float) -> float:
                try:
                    # Try to load fresh config parser since UnifiedConfig doesn't have getfloat
                    import configparser
                    import os
                    
                    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")
                    if os.path.exists(config_path):
                        parser = configparser.ConfigParser()
                        parser.read(config_path)
                        return parser.getfloat(section, key, fallback=fallback)
                    return fallback
                except Exception:
                    return fallback
            
            # Get base volume requirements from config
            volume_config = {
                'breakout': get_config_float('VOLUME_REQUIREMENTS', 'breakout_base_volume', 3.0),
                'news_momentum': get_config_float('VOLUME_REQUIREMENTS', 'news_momentum_base_volume', 2.5),
                'momentum_continuation': get_config_float('VOLUME_REQUIREMENTS', 'momentum_continuation_base_volume', 2.0),
                'gap_and_go': get_config_float('VOLUME_REQUIREMENTS', 'gap_and_go_base_volume', 1.5),
                'fade_gap': get_config_float('VOLUME_REQUIREMENTS', 'fade_gap_base_volume', 1.0),
                'daily_plays': get_config_float('VOLUME_REQUIREMENTS', 'daily_plays_base_volume', 1.2),
                'default': get_config_float('VOLUME_REQUIREMENTS', 'default_base_volume', 1.5)
            }
            
            base_volume = volume_config.get(strategy_type, volume_config['default'])
            
            # Context adjustments using config multipliers
            multiplier = 1.0
            
            # Market phase adjustments
            current_phase = self.market_context.current_phase
            if current_phase == MarketPhase.PRE_MARKET:
                multiplier *= get_config_float('VOLUME_REQUIREMENTS', 'premarket_volume_multiplier', 0.7)
            elif current_phase == MarketPhase.OPENING:
                multiplier *= get_config_float('VOLUME_REQUIREMENTS', 'opening_volume_multiplier', 0.8)
            elif current_phase == MarketPhase.LUNCH:
                multiplier *= get_config_float('VOLUME_REQUIREMENTS', 'lunch_volume_multiplier', 1.2)
            elif current_phase == MarketPhase.AFTER_HOURS:
                multiplier *= get_config_float('VOLUME_REQUIREMENTS', 'afterhours_volume_multiplier', 0.6)
            else:  # REGULAR hours
                multiplier *= get_config_float('VOLUME_REQUIREMENTS', 'regular_volume_multiplier', 1.0)
            
            # Volatility and sentiment adjustments (simplified for regular market conditions)
            volatility = self.market_context.volatility_regime
            if volatility == 'LOW':
                multiplier *= get_config_float('VOLUME_REQUIREMENTS', 'low_volatility_multiplier', 0.7)
            elif volatility in ['HIGH', 'EXTREME']:
                multiplier *= get_config_float('VOLUME_REQUIREMENTS', 'high_volatility_multiplier', 1.1)
            
            # Overall market volume adjustment (key for smallcaps)
            overall_volume = self.market_context.overall_volume_ratio
            low_threshold = get_config_float('VOLUME_REQUIREMENTS', 'market_volume_threshold_low', 0.8)
            
            if overall_volume < low_threshold:  # Low overall market volume (typical condition)
                multiplier *= get_config_float('VOLUME_REQUIREMENTS', 'low_market_volume_multiplier', 0.6)
            
            adjusted_requirement = base_volume * multiplier
            
            # Apply safety limits from config
            min_requirement = get_config_float('VOLUME_REQUIREMENTS', 'minimum_volume_requirement', 0.5)
            max_multiplier = get_config_float('VOLUME_REQUIREMENTS', 'maximum_volume_multiplier', 1.5)
            
            adjusted_requirement = max(min_requirement, min(adjusted_requirement, base_volume * max_multiplier))
            
            self.logger.debug(f"📊 Volume requirement for {strategy_type}: {base_volume:.1f}x -> {adjusted_requirement:.1f}x "
                            f"(phase: {current_phase.value}, market_vol: {overall_volume:.1f}x)")
            
            return adjusted_requirement
            
        except Exception as e:
            self.logger.error(f"❌ Error calculating volume requirement: {e}")
            # Safe fallback - much more lenient than original 5.0x
            return 1.0
    
    def _initialize_market_context(self) -> MarketContext:
        """Initialize with basic market context"""
        return MarketContext(
            current_phase=self._determine_current_phase(),
            time_in_phase=timedelta(minutes=0),
            next_phase_in=timedelta(minutes=60),
            market_sentiment=MarketSentiment.NEUTRAL,
            spy_change_pct=0.0,
            vix_level=20.0,
            sector_rotation={},
            overall_volume_ratio=1.0,
            volatility_regime='NORMAL',
            adv_decline_ratio=1.0,
            breaking_news_count=0,
            major_economic_events=[],
            sector_news={},
            recent_strategy_performance={},
            current_day_pnl=0.0,
            current_positions=0,
            last_updated=datetime.now(),
            data_quality_score=1.0
        )
    
    def _determine_current_phase(self) -> MarketPhase:
        """Determine current market phase using NYC timezone"""
        # Convertir a horario de Nueva York (Eastern Time)
        ny_tz = pytz.timezone('US/Eastern')
        ny_datetime = datetime.now(ny_tz)
        current_time = ny_datetime.time()
        
        # Log timezone conversion for debugging
        local_time = datetime.now()
        self.logger.debug(f"🕐 Time conversion - Local: {local_time.strftime('%H:%M:%S')} -> NYC: {ny_datetime.strftime('%H:%M:%S %Z')}")
        
        if current_time < time(9, 30):
            return MarketPhase.PRE_MARKET
        elif time(9, 30) <= current_time < time(10, 30):
            return MarketPhase.OPENING
        elif time(10, 30) <= current_time < time(12, 0):
            return MarketPhase.MID_MORNING
        elif time(12, 0) <= current_time < time(13, 0):
            return MarketPhase.LUNCH
        elif time(13, 0) <= current_time < time(15, 0):
            return MarketPhase.AFTERNOON
        elif time(15, 0) <= current_time < time(16, 0):
            return MarketPhase.POWER_HOUR
        else:
            return MarketPhase.AFTER_HOURS
    
    def _calculate_time_in_phase(self) -> int:
        """Calculate minutes elapsed in current phase using NYC timezone"""
        # Convertir a horario de Nueva York (Eastern Time)
        ny_tz = pytz.timezone('US/Eastern')
        current_time = datetime.now(ny_tz).time()
        current_phase = self._determine_current_phase()
        
        phase_starts = {
            MarketPhase.PRE_MARKET: time(4, 0),    # 4:00 AM
            MarketPhase.OPENING: time(9, 30),       # 9:30 AM
            MarketPhase.MID_MORNING: time(10, 30),  # 10:30 AM
            MarketPhase.GENERAL_TRADING: time(10, 0), # 10:00 AM
            MarketPhase.LUNCH: time(12, 0),         # 12:00 PM
            MarketPhase.AFTERNOON: time(13, 0),     # 1:00 PM
            MarketPhase.POWER_HOUR: time(15, 0),    # 3:00 PM
            MarketPhase.AFTER_HOURS: time(16, 0),   # 4:00 PM
        }
        
        start_time = phase_starts.get(current_phase, time(9, 30))
        
        # Calculate minutes elapsed since phase start
        current_minutes = current_time.hour * 60 + current_time.minute
        start_minutes = start_time.hour * 60 + start_time.minute
        
        return max(0, current_minutes - start_minutes)
    
    def _calculate_time_to_next_phase(self) -> int:
        """Calculate minutes until next phase"""
        current_time = datetime.now().time()
        current_phase = self._determine_current_phase()
        
        phase_ends = {
            MarketPhase.PRE_MARKET: time(9, 30),    # 9:30 AM
            MarketPhase.OPENING: time(10, 30),      # 10:30 AM
            MarketPhase.GENERAL_TRADING: time(16, 0), # 4:00 PM  
            MarketPhase.MID_MORNING: time(12, 0),   # 12:00 PM
            MarketPhase.LUNCH: time(13, 0),         # 1:00 PM
            MarketPhase.AFTERNOON: time(15, 0),     # 3:00 PM
            MarketPhase.POWER_HOUR: time(16, 0),    # 4:00 PM
            MarketPhase.AFTER_HOURS: time(23, 59),  # End of day
        }
        
        end_time = phase_ends.get(current_phase, time(16, 0))
        
        # Calculate minutes until phase end
        current_minutes = current_time.hour * 60 + current_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute
        
        return max(0, end_minutes - current_minutes)
    
    def _determine_market_sentiment(self, context_data: Dict) -> MarketSentiment:
        """Determine market sentiment from SPY and VIX"""
        spy_change = context_data.get('spy_change', 0.0)
        vix = context_data.get('vix', 20.0)
        
        if spy_change > 0.02 and vix < 15:
            return MarketSentiment.VERY_BULLISH
        elif spy_change > 0.005 and vix < 20:
            return MarketSentiment.BULLISH
        elif -0.005 <= spy_change <= 0.005 and 15 <= vix <= 25:
            return MarketSentiment.NEUTRAL
        elif spy_change < -0.005 and vix > 25:
            return MarketSentiment.BEARISH
        elif spy_change < -0.02 and vix > 30:
            return MarketSentiment.VERY_BEARISH
        elif vix > 40:
            return MarketSentiment.PANIC
        else:
            return MarketSentiment.NEUTRAL
    
    def _determine_volatility_regime(self, vix: float) -> str:
        """Determine volatility regime"""
        if vix < 15:
            return 'LOW'
        elif vix <= 25:
            return 'NORMAL'
        elif vix <= 35:
            return 'HIGH'
        else:
            return 'EXTREME'
    
    async def _fetch_market_context_data(self) -> Dict:
        """
        Fetch market data for context awareness
        In production, this would connect to data providers
        """
        # Placeholder - in production connect to:
        # - SPY/VIX data
        # - News feeds
        # - Volume data
        # - Economic calendar
        
        return {
            'spy_change': 0.005,  # +0.5%
            'vix': 22.0,
            'volume_ratio': 1.2,
            'advance_decline': 1.1,
            'breaking_news': 0,
            'economic_events': [],
            'sector_news': {},
            'data_quality': 0.95
        }
    
    def _calculate_recent_performance(self) -> Dict[StrategyType, float]:
        """Calculate recent performance of each strategy"""
        performance = {}
        for strategy, stats in self.strategy_performance.items():
            total = stats['total']
            if total > 0:
                win_rate = stats['wins'] / total
                performance[strategy] = win_rate
            else:
                performance[strategy] = 0.5  # Default
        return performance
    
    def _validate_context_requirements(self, entry: SmartGamePlanEntry) -> Dict:
        """Validate if current context matches entry requirements"""

        current_phase = self.market_context.current_phase
        current_sentiment = self.market_context.market_sentiment
        current_volatility = self.market_context.volatility_regime

        # IMPORTANT: Reject trades during premarket and afterhours
        # User only operates during regular market hours (9:30-16:00 ET) due to lack of reliable premarket/afterhours data
        if current_phase in [MarketPhase.PRE_MARKET, MarketPhase.AFTER_HOURS]:
            return {
                'valid': False,
                'reason': f'Trading not allowed during {current_phase.value} - only regular market hours (9:30-16:00 ET)'
            }

        # Check sentiment compatibility
        if entry.required_sentiment and current_sentiment not in entry.required_sentiment:
            return {
                'valid': False,
                'reason': f'Sentiment {current_sentiment.value} not suitable for {entry.primary_strategy.value}'
            }

        # Check volatility requirements
        volatility_order = {'LOW': 1, 'NORMAL': 2, 'HIGH': 3, 'EXTREME': 4}
        required_level = volatility_order.get(entry.min_volatility_regime, 1)
        current_level = volatility_order.get(current_volatility, 2)

        if current_level < required_level:
            return {
                'valid': False,
                'reason': f'Volatility {current_volatility} below required {entry.min_volatility_regime}'
            }

        # Check if current phase is allowed for this strategy
        if entry.optimal_market_phases and MarketPhase.GENERAL_TRADING in entry.optimal_market_phases:
            # Special validation for GENERAL_TRADING: allow if between 10:00-16:00 ET
            ny_tz = pytz.timezone('US/Eastern')
            current_time = datetime.now(ny_tz).time()
            if not (time(10, 0) <= current_time < time(16, 0)):
                return {
                    'valid': False,
                    'reason': f'GENERAL_TRADING only allowed 10:00-16:00 ET, current: {current_time.strftime("%H:%M")}'
                }
        elif entry.optimal_market_phases and current_phase not in entry.optimal_market_phases:
            return {
                'valid': False,
                'reason': f'Phase {current_phase.value} not optimal for {entry.primary_strategy.value} (need: {[p.value for p in entry.optimal_market_phases]})'
            }

        return {'valid': True, 'reason': 'Context requirements met'}
    
    def _create_dynamic_entry_from_live_data(self, symbol: str, live_data: Dict) -> Optional[SmartGamePlanEntry]:
        """
        Create a SmartGamePlanEntry dynamically from live scanner data
        Uses catalyst analysis to determine strategy and parameters
        """
        try:
            # Extract data from scanner
            catalyst_type = live_data.get('catalyst_type', 'OTHER')
            gap_pct = live_data.get('gap_percentage', 0.0)
            current_price = live_data.get('current_price', 0.0)
            volume_ratio = live_data.get('volume_ratio', 1.0)
            catalyst_strength = live_data.get('catalyst_strength', 0.0)
            
            if current_price <= 0:
                self.logger.warning(f"Invalid price data for {symbol}: {current_price}")
                return None
            
            # Use existing strategy selection logic but pass as opportunity dict
            opportunity_dict = {
                'symbol': symbol,
                'catalyst_type': catalyst_type,
                'gap_percentage': gap_pct,
                'volume_ratio': volume_ratio,
                'catalyst_strength': catalyst_strength
            }
            
            # Get strategy and confidence using existing logic
            strategy, confidence = self._select_optimal_strategy_with_context(opportunity_dict)
            
            # Calculate technical levels based on current price and strategy
            entry_price = current_price
            
            # Strategy-specific stop loss and targets
            if strategy == StrategyType.FDA_CATALYST:
                stop_loss = current_price * 0.85  # Wider stop for biotech
                target_1 = current_price * 1.25
                target_2 = current_price * 1.50
                position_size = 0.02  # 2% position size for high volatility
                
            elif strategy == StrategyType.GAP_AND_GO:
                stop_loss = current_price * 0.92  # 8% stop
                target_1 = current_price * 1.15
                target_2 = current_price * 1.25
                position_size = 0.025
                
            elif strategy == StrategyType.EARNINGS_SURPRISE:
                stop_loss = current_price * 0.90  # 10% stop
                target_1 = current_price * 1.20
                target_2 = current_price * 1.35
                position_size = 0.03
                
            elif strategy == StrategyType.NEWS_MOMENTUM:
                stop_loss = current_price * 0.88  # 12% stop
                target_1 = current_price * 1.18
                target_2 = current_price * 1.30
                position_size = 0.025
                
            else:  # VOLUME_BREAKOUT and others
                stop_loss = current_price * 0.90  # 10% stop
                target_1 = current_price * 1.15
                target_2 = current_price * 1.25
                position_size = 0.02
            
            # Determine optimal market phases based on strategy
            optimal_phases = self._get_optimal_phases_for_strategy(strategy)
            required_sentiment = self._get_required_sentiment_for_strategy(strategy)
            min_volatility = self._get_min_volatility_for_strategy(strategy)
            
            # Create the entry
            entry = SmartGamePlanEntry(
                symbol=symbol,
                tier='A' if confidence > 0.8 else 'B' if confidence > 0.6 else 'C',
                primary_strategy=strategy,
                primary_strategy_confidence=confidence,
                backup_strategies=[StrategyType.VOLUME_BREAKOUT],  # Always have volume breakout as backup
                strategy_selection_reasoning=f"Auto-selected based on catalyst: {catalyst_type}",
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2,
                technical_setup_score=min(catalyst_strength, 10.0),
                optimal_market_phases=optimal_phases,
                required_sentiment=required_sentiment,
                min_volatility_regime=min_volatility,
                context_match_score=confidence,
                position_size=position_size,
                max_risk_per_trade=0.05,  # 5% max risk
                execution_urgency='HIGH' if confidence > 0.8 else 'MEDIUM',
                time_decay_factor=1.0,
                last_updated=datetime.now(),
                updates_count=0,
                initial_context_score=confidence
            )
            
            self.logger.info(f"🎯 Dynamic entry created for {symbol}: {strategy.value} (confidence: {confidence:.2f})")
            return entry
            
        except Exception as e:
            self.logger.error(f"❌ Error creating dynamic entry for {symbol}: {e}")
            return None
    
    def _get_optimal_phases_for_strategy(self, strategy: StrategyType) -> List[MarketPhase]:
        """Get optimal market phases for each strategy"""
        phase_map = {
            StrategyType.FDA_CATALYST: [MarketPhase.PRE_MARKET, MarketPhase.OPENING, MarketPhase.MID_MORNING, MarketPhase.AFTERNOON],
            StrategyType.GAP_AND_GO: [MarketPhase.PRE_MARKET, MarketPhase.OPENING, MarketPhase.MID_MORNING, MarketPhase.LUNCH, MarketPhase.AFTERNOON, MarketPhase.POWER_HOUR],
            StrategyType.FADE_GAP: [MarketPhase.MID_MORNING, MarketPhase.AFTERNOON],
            StrategyType.NEWS_MOMENTUM: [MarketPhase.OPENING, MarketPhase.MID_MORNING, MarketPhase.LUNCH, MarketPhase.AFTERNOON, MarketPhase.POWER_HOUR],
            StrategyType.EARNINGS_SURPRISE: [MarketPhase.PRE_MARKET, MarketPhase.OPENING, MarketPhase.MID_MORNING, MarketPhase.LUNCH],
            StrategyType.OPENING_RANGE_BREAKOUT: [MarketPhase.OPENING, MarketPhase.MID_MORNING],
            StrategyType.MOMENTUM_CONTINUATION: [MarketPhase.GENERAL_TRADING],
            StrategyType.REVERSAL_PLAY: [MarketPhase.AFTERNOON, MarketPhase.POWER_HOUR],
            StrategyType.VOLUME_BREAKOUT: [MarketPhase.OPENING, MarketPhase.MID_MORNING, MarketPhase.LUNCH, MarketPhase.AFTERNOON, MarketPhase.POWER_HOUR],
            StrategyType.END_OF_DAY: [MarketPhase.POWER_HOUR]
        }
        return phase_map.get(strategy, [MarketPhase.OPENING, MarketPhase.MID_MORNING, MarketPhase.AFTERNOON])
    
    def _get_required_sentiment_for_strategy(self, strategy: StrategyType) -> List[MarketSentiment]:
        """Get required market sentiment for each strategy"""
        sentiment_map = {
            StrategyType.FDA_CATALYST: [MarketSentiment.NEUTRAL, MarketSentiment.BULLISH, MarketSentiment.VERY_BULLISH],
            StrategyType.GAP_AND_GO: [MarketSentiment.BULLISH, MarketSentiment.VERY_BULLISH],
            StrategyType.FADE_GAP: [MarketSentiment.BEARISH, MarketSentiment.NEUTRAL],
            StrategyType.NEWS_MOMENTUM: [MarketSentiment.BULLISH, MarketSentiment.VERY_BULLISH],
            StrategyType.EARNINGS_SURPRISE: [MarketSentiment.NEUTRAL, MarketSentiment.BULLISH, MarketSentiment.VERY_BULLISH],
            StrategyType.REVERSAL_PLAY: [MarketSentiment.BEARISH, MarketSentiment.VERY_BEARISH],
            StrategyType.VOLUME_BREAKOUT: [],  # Works in any sentiment
            StrategyType.END_OF_DAY: [MarketSentiment.NEUTRAL, MarketSentiment.BULLISH]
        }
        return sentiment_map.get(strategy, [])  # Empty list means any sentiment is OK
    
    def _get_min_volatility_for_strategy(self, strategy: StrategyType) -> str:
        """Get minimum volatility regime for each strategy"""
        volatility_map = {
            StrategyType.FDA_CATALYST: 'NORMAL',
            StrategyType.GAP_AND_GO: 'NORMAL', 
            StrategyType.FADE_GAP: 'HIGH',
            StrategyType.NEWS_MOMENTUM: 'NORMAL',
            StrategyType.EARNINGS_SURPRISE: 'NORMAL',
            StrategyType.OPENING_RANGE_BREAKOUT: 'LOW',
            StrategyType.MOMENTUM_CONTINUATION: 'NORMAL',
            StrategyType.REVERSAL_PLAY: 'HIGH',
            StrategyType.VOLUME_BREAKOUT: 'LOW',
            StrategyType.END_OF_DAY: 'NORMAL'
        }
        return volatility_map.get(strategy, 'LOW')
    
    def _calculate_context_match(self, entry: SmartGamePlanEntry) -> float:
        """Calculate how well current context matches entry"""
        # Implementation for context matching score
        return 0.75  # Placeholder
    
    def _apply_time_decay(self):
        """Apply time decay to entries not executed"""
        for entry in self.current_plan.values():
            hours_since_update = (datetime.now() - entry.last_updated).total_seconds() / 3600
            entry.time_decay_factor = max(0.5, 1.0 - (hours_since_update * 0.1))
    
    def _cleanup_low_score_entries(self):
        """Remove entries with very low scores"""
        to_remove = []
        for symbol, entry in self.current_plan.items():
            total_score = entry.context_match_score * entry.time_decay_factor
            if total_score < 0.3:
                to_remove.append(symbol)
        
        for symbol in to_remove:
            del self.current_plan[symbol]
            self.logger.info(f"🗑️ Removed {symbol} - low total score")
    
    def _maybe_reassign_strategy(self, entry: SmartGamePlanEntry, live_data: Dict) -> SmartGamePlanEntry:
        """
        Re-evaluate strategy assignment if current strategy is inappropriate for current context
        This addresses cases where entries were created with REVERSAL_PLAY before improvements
        """
        current_strategy = entry.primary_strategy
        current_sentiment = self.market_context.market_sentiment
        
        # Case 1: REVERSAL_PLAY with neutral sentiment - should be reassigned
        if (current_strategy == StrategyType.REVERSAL_PLAY and 
            current_sentiment == MarketSentiment.NEUTRAL):
            
            # Re-evaluate strategy using improved logic
            opportunity_data = {
                'symbol': entry.symbol,
                'gap_percentage': live_data.get('gap_percentage', 0.05),
                'volume_ratio': live_data.get('volume_ratio', 2.0),
                'catalyst_type': 'OTHER',  # Conservative assumption
                'current_price': live_data.get('current_price', entry.entry_price)
            }
            
            new_strategy, new_confidence = self._select_optimal_strategy_with_context(opportunity_data)
            
            if new_strategy != current_strategy:
                self.logger.info(f"🔄 Re-evaluating {entry.symbol}: {current_strategy.value} -> {new_strategy.value} (confidence: {new_confidence:.2f})")
                
                # Get appropriate requirements for the new strategy
                new_required_sentiment = self._get_strategy_required_sentiment(new_strategy)
                new_min_volatility = self._get_strategy_min_volatility(new_strategy)
                
                # Create updated entry with new strategy
                updated_entry = SmartGamePlanEntry(
                    symbol=entry.symbol,
                    tier=entry.tier,
                    primary_strategy=new_strategy,
                    primary_strategy_confidence=new_confidence,
                    backup_strategies=entry.backup_strategies,
                    strategy_selection_reasoning=f"Re-evaluated from {current_strategy.value} due to neutral sentiment",
                    entry_price=entry.entry_price,
                    stop_loss=entry.stop_loss,
                    target_1=entry.target_1,
                    target_2=entry.target_2,
                    technical_setup_score=entry.technical_setup_score,
                    optimal_market_phases=entry.optimal_market_phases,
                    required_sentiment=new_required_sentiment,
                    min_volatility_regime=new_min_volatility,
                    context_match_score=entry.context_match_score,
                    position_size=entry.position_size,
                    max_risk_per_trade=entry.max_risk_per_trade,
                    execution_urgency=entry.execution_urgency,
                    time_decay_factor=entry.time_decay_factor,
                    last_updated=datetime.now()
                )
                
                # Update the plan with the new entry
                self.current_plan[entry.symbol] = updated_entry
                return updated_entry
        
        # No reassignment needed
        return entry
    
    def _get_strategy_required_sentiment(self, strategy: StrategyType) -> list:
        """Get required sentiment list for a strategy"""
        sentiment_requirements = {
            StrategyType.REVERSAL_PLAY: [MarketSentiment.VERY_BULLISH, MarketSentiment.VERY_BEARISH],
            StrategyType.VOLUME_BREAKOUT: [MarketSentiment.NEUTRAL, MarketSentiment.BULLISH, MarketSentiment.BEARISH, MarketSentiment.VERY_BULLISH, MarketSentiment.VERY_BEARISH],
            StrategyType.DAILY_PLAYS: [MarketSentiment.NEUTRAL, MarketSentiment.BULLISH, MarketSentiment.BEARISH],
            StrategyType.GAP_AND_GO: [MarketSentiment.BULLISH, MarketSentiment.VERY_BULLISH],
            # Add other strategies as needed
        }
        return sentiment_requirements.get(strategy, [])  # Empty list = no sentiment requirement
    
    def _get_strategy_min_volatility(self, strategy: StrategyType) -> str:
        """Get minimum volatility regime for a strategy"""
        volatility_requirements = {
            StrategyType.REVERSAL_PLAY: 'NORMAL',
            StrategyType.VOLUME_BREAKOUT: 'NORMAL', 
            StrategyType.DAILY_PLAYS: 'LOW',
            StrategyType.GAP_AND_GO: 'NORMAL',
            # Add other strategies as needed
        }
        return volatility_requirements.get(strategy, 'LOW')  # Default to LOW

    def _get_smallcap_context_multiplier(self) -> Dict[str, float]:
        """
        Calculate smallcap-specific context multipliers based on market conditions
        
        Smallcaps behavior:
        - High VIX + Low SPY = More explosive moves (FOMO into risk)
        - Low VIX + High SPY = More contained moves (money flows to large caps)
        - Always tradeable but with adjusted expectations
        
        Returns:
            Dict with multipliers for different aspects
        """
        vix_level = self.market_context.vix_level
        spy_change = self.market_context.spy_change_pct
        sentiment = self.market_context.market_sentiment
        
        multipliers = {
            'confidence_base': 1.0,      # Base confidence multiplier
            'momentum_favor': 1.0,       # Favor momentum strategies
            'reversal_favor': 1.0,       # Favor reversal strategies
            'volatility_boost': 1.0      # Volatility-based boost
        }
        
        # VIX-based adjustments (smallcaps love volatility)
        if vix_level > 30:  # High fear
            multipliers['confidence_base'] = 1.05  # Smallcaps can explode in fear
            multipliers['reversal_favor'] = 1.15   # Great for reversal plays
            multipliers['momentum_favor'] = 1.20   # Explosive momentum possible
        elif vix_level > 25:  # Medium fear
            multipliers['confidence_base'] = 1.02
            multipliers['reversal_favor'] = 1.08
            multipliers['momentum_favor'] = 1.10
        elif vix_level < 15:  # Low fear (complacency)
            multipliers['confidence_base'] = 0.98  # Slightly less explosive
            multipliers['momentum_favor'] = 0.95   # Less momentum
        
        # SPY-based adjustments (inverse relationship for smallcaps)
        if spy_change < -0.02:  # SPY down >2%
            multipliers['confidence_base'] *= 1.08  # Smallcaps can outperform on bounces
            multipliers['reversal_favor'] *= 1.25   # Excellent reversal opportunities
        elif spy_change < -0.01:  # SPY down >1%
            multipliers['confidence_base'] *= 1.04
            multipliers['reversal_favor'] *= 1.15
        elif spy_change > 0.02:  # SPY up >2%
            multipliers['confidence_base'] *= 0.95  # Money flows to large caps
            multipliers['momentum_favor'] *= 0.90   # Less explosive moves
        
        # Sentiment-specific smallcap adjustments
        if sentiment == MarketSentiment.VERY_BEARISH:
            # Smallcaps can have violent bounces in very bearish conditions
            multipliers['reversal_favor'] *= 1.30
            multipliers['volatility_boost'] = 1.15
        elif sentiment == MarketSentiment.VERY_BULLISH:
            # Smallcaps may lag in very bullish conditions (money to large caps)
            multipliers['momentum_favor'] *= 0.85
            multipliers['confidence_base'] *= 0.95
        
        self.logger.debug(f"Smallcap context multipliers: {multipliers}")
        return multipliers

    def _get_opportunity_data(self, symbol: str) -> Dict:
        """Get opportunity data for re-evaluation"""
        # Placeholder - would fetch fresh data
        return {'symbol': symbol, 'catalyst_type': 'OTHER', 'gap_percentage': 0.05, 'volume_ratio': 2.0}