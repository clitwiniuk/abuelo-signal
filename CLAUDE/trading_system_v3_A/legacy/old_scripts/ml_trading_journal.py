# strategies/ml_trading_journal.py
"""
ML Trading Journal - Sistema de Análisis Avanzado y Aprendizaje Profundo

Automatiza completamente la reflexión y análisis que hacen traders profesionales,
transformando cada trade en aprendizaje multi-dimensional para el ML.

Este sistema convierte nuestro ML básico en ML elite através de:
1. Feature engineering avanzado (50+ features vs 15 básicas)
2. Contextual learning profundo (reward multi-dimensional)
3. Pattern discovery automático (descubre nuevos edges)
4. Predicción de contexto holística
5. Auto-optimización continua de parámetros
6. Feedback loop sofisticado
"""

import logging
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import pickle
from collections import defaultdict, deque
import asyncio

# Imports del sistema existente
try:
    from core.interfaces import Signal, MarketData, Position, SignalType
    from strategies.ml_strategy_selector import TickerContext, StrategyPerformance
except ImportError:
    # Fallback para testing
    pass

logger = logging.getLogger(__name__)

@dataclass
class EnhancedTickerContext:
    """Contexto enriquecido para ML avanzado - 50+ features"""
    
    # === DATOS BASE ===
    symbol: str
    timestamp: datetime
    current_price: float
    
    # === FEATURES TÉCNICAS BÁSICAS (existentes) ===
    avg_volume_10: float
    avg_volume_50: float
    volatility_10: float
    volatility_50: float
    rsi_14: float
    hour_of_day: float
    minutes_from_open: int
    
    # === FEATURES AVANZADAS - DAILY CHART ANALYSIS ===
    daily_trend_strength: float  # -1 to 1, bearish to bullish trend strength
    daily_volume_pattern: str    # "accumulation", "distribution", "neutral", "explosion"
    support_proximity: float     # Distance to nearest support (0-1)
    resistance_proximity: float  # Distance to nearest resistance (0-1)
    breakout_potential: float    # 0-1, likelihood of breakout based on daily setup
    consolidation_days: int      # Days in current consolidation pattern
    
    # === FEATURES AVANZADAS - INTRADAY ANALYSIS ===
    intraday_momentum_quality: float  # 0-1, clean vs choppy momentum
    volume_acceleration: float         # Rate of volume increase
    price_action_quality: float       # 0-1, quality of price movement
    tape_strength: float              # 0-1, strength of tape reading signals
    
    # === FEATURES AVANZADAS - MARKET CONTEXT ===
    news_sentiment: float             # -1 to 1, negative to positive news sentiment
    social_sentiment: float           # -1 to 1, retail sentiment from social media
    institutional_flow: float         # -1 to 1, institutional selling to buying
    sector_relative_strength: float   # -1 to 1, sector underperform to outperform
    market_regime: str                # "trending", "range_bound", "volatile", "calm"
    
    # === FEATURES AVANZADAS - FUNDAMENTAL CONTEXT ===
    market_cap_category: str          # "nano", "micro", "small", "mid"
    float_size_category: str          # "tiny", "small", "medium", "large"
    short_interest_ratio: float       # 0-1, low to high short interest
    short_squeeze_probability: float  # 0-1, likelihood of squeeze
    insider_activity: str             # "buying", "selling", "neutral"
    
    # === FEATURES AVANZADAS - LEVEL 2 / ORDER FLOW ===
    bid_ask_spread_health: float      # 0-1, wide/poor to tight/healthy spread
    liquidity_depth: float            # 0-1, shallow to deep liquidity
    order_flow_imbalance: float       # -1 to 1, bid heavy to ask heavy
    large_order_presence: bool        # Institutional size orders detected
    
    # === FEATURES AVANZADAS - PATTERN HISTORY ===
    similar_pattern_success_rate: float  # 0-1, historical success of similar setups
    ticker_trading_history: str          # "frequent", "occasional", "first_time"
    previous_breakout_follow_through: float  # 0-1, how well breakouts follow through
    mean_reversion_tendency: float       # 0-1, tendency to revert vs trend
    
    # === FEATURES AVANZADAS - TIMING ===
    optimal_entry_timing: float       # 0-1, how close to optimal entry timing
    pattern_maturity: float           # 0-1, how mature the setup is
    time_decay_factor: float          # 0-1, setup deterioration over time
    session_position: str             # "early", "mid", "late" in trading session
    
    # === FEATURES AVANZADAS - RISK ASSESSMENT ===
    volatility_regime: str            # "low", "normal", "high", "extreme"
    liquidity_risk: float             # 0-1, low to high liquidity risk
    news_risk: float                  # 0-1, low to high news surprise risk
    overnight_risk: float             # 0-1, low to high overnight gap risk
    
    def to_advanced_feature_vector(self) -> np.ndarray:
        """Convierte a vector de 50+ features para ML avanzado"""
        
        # Features numéricas básicas
        basic_features = [
            self.current_price,
            self.avg_volume_10,
            self.avg_volume_50,
            self.volatility_10,
            self.volatility_50,
            self.rsi_14,
            self.hour_of_day,
            self.minutes_from_open
        ]
        
        # Features avanzadas numéricas
        advanced_features = [
            self.daily_trend_strength,
            self.support_proximity,
            self.resistance_proximity,
            self.breakout_potential,
            self.consolidation_days,
            self.intraday_momentum_quality,
            self.volume_acceleration,
            self.price_action_quality,
            self.tape_strength,
            self.news_sentiment,
            self.social_sentiment,
            self.institutional_flow,
            self.sector_relative_strength,
            self.short_interest_ratio,
            self.short_squeeze_probability,
            self.bid_ask_spread_health,
            self.liquidity_depth,
            self.order_flow_imbalance,
            float(self.large_order_presence),
            self.similar_pattern_success_rate,
            self.previous_breakout_follow_through,
            self.mean_reversion_tendency,
            self.optimal_entry_timing,
            self.pattern_maturity,
            self.time_decay_factor,
            self.liquidity_risk,
            self.news_risk,
            self.overnight_risk
        ]
        
        # Features categóricas one-hot encoded
        categorical_features = []
        
        # Daily volume pattern
        volume_patterns = ["accumulation", "distribution", "neutral", "explosion"]
        for pattern in volume_patterns:
            categorical_features.append(1.0 if self.daily_volume_pattern == pattern else 0.0)
        
        # Market regime
        regimes = ["trending", "range_bound", "volatile", "calm"]
        for regime in regimes:
            categorical_features.append(1.0 if self.market_regime == regime else 0.0)
        
        # Market cap category
        cap_categories = ["nano", "micro", "small", "mid"]
        for category in cap_categories:
            categorical_features.append(1.0 if self.market_cap_category == category else 0.0)
        
        # Float size category
        float_categories = ["tiny", "small", "medium", "large"]
        for category in float_categories:
            categorical_features.append(1.0 if self.float_size_category == category else 0.0)
        
        # Insider activity
        insider_activities = ["buying", "selling", "neutral"]
        for activity in insider_activities:
            categorical_features.append(1.0 if self.insider_activity == activity else 0.0)
        
        # Trading history
        histories = ["frequent", "occasional", "first_time"]
        for history in histories:
            categorical_features.append(1.0 if self.ticker_trading_history == history else 0.0)
        
        # Session position
        positions = ["early", "mid", "late"]
        for position in positions:
            categorical_features.append(1.0 if self.session_position == position else 0.0)
        
        # Volatility regime
        vol_regimes = ["low", "normal", "high", "extreme"]
        for regime in vol_regimes:
            categorical_features.append(1.0 if self.volatility_regime == regime else 0.0)
        
        # Combinar todas las features
        all_features = basic_features + advanced_features + categorical_features
        
        return np.array(all_features, dtype=np.float32)
    
    def get_feature_names(self) -> List[str]:
        """Retorna nombres de todas las features para interpretabilidad"""
        basic_names = [
            "current_price", "avg_volume_10", "avg_volume_50", "volatility_10", 
            "volatility_50", "rsi_14", "hour_of_day", "minutes_from_open"
        ]
        
        advanced_names = [
            "daily_trend_strength", "support_proximity", "resistance_proximity",
            "breakout_potential", "consolidation_days", "intraday_momentum_quality",
            "volume_acceleration", "price_action_quality", "tape_strength",
            "news_sentiment", "social_sentiment", "institutional_flow",
            "sector_relative_strength", "short_interest_ratio", "short_squeeze_probability",
            "bid_ask_spread_health", "liquidity_depth", "order_flow_imbalance",
            "large_order_presence", "similar_pattern_success_rate",
            "previous_breakout_follow_through", "mean_reversion_tendency",
            "optimal_entry_timing", "pattern_maturity", "time_decay_factor",
            "liquidity_risk", "news_risk", "overnight_risk"
        ]
        
        categorical_names = []
        
        # Categorical feature names
        for pattern in ["accumulation", "distribution", "neutral", "explosion"]:
            categorical_names.append(f"volume_pattern_{pattern}")
        
        for regime in ["trending", "range_bound", "volatile", "calm"]:
            categorical_names.append(f"market_regime_{regime}")
        
        for category in ["nano", "micro", "small", "mid"]:
            categorical_names.append(f"market_cap_{category}")
        
        for category in ["tiny", "small", "medium", "large"]:
            categorical_names.append(f"float_size_{category}")
        
        for activity in ["buying", "selling", "neutral"]:
            categorical_names.append(f"insider_activity_{activity}")
        
        for history in ["frequent", "occasional", "first_time"]:
            categorical_names.append(f"trading_history_{history}")
        
        for position in ["early", "mid", "late"]:
            categorical_names.append(f"session_position_{position}")
        
        for regime in ["low", "normal", "high", "extreme"]:
            categorical_names.append(f"volatility_regime_{regime}")
        
        return basic_names + advanced_names + categorical_names

@dataclass
class MultiDimensionalReward:
    """Reward multi-dimensional para aprendizaje sofisticado"""
    
    # Reward components (with default values for backward compatibility)
    pnl_magnitude: float = 0.0              # Raw PnL amount
    pnl_percentage: float = 0.0             # PnL as percentage of position
    risk_adjusted_return: float = 0.0       # Sharpe-like ratio
    entry_timing_quality: float = 0.5       # 0-1, how good was entry timing
    exit_timing_quality: float = 0.5        # 0-1, how good was exit timing
    pattern_adherence: float = 0.5           # 0-1, how well trade followed expected pattern
    market_context_favorability: float = 0.5 # 0-1, how favorable was market context
    execution_quality: float = 0.5          # 0-1, overall execution quality
    opportunity_cost: float = 0.0            # What was given up for this trade
    sustainability_score: float = 0.5       # 0-1, how repeatable is this pattern
    
    # Trade classification
    trade_category: str = "UNKNOWN"               # Auto-classified trade type
    confidence_level: float = 0.5           # 0-1, confidence in the setup
    
    # Backward compatibility for old parameter names
    def __init__(self, **kwargs):
        # Handle backward compatibility
        if 'financial_pnl' in kwargs:
            kwargs['pnl_magnitude'] = kwargs.pop('financial_pnl')
        if 'market_timing' in kwargs:
            kwargs['entry_timing_quality'] = kwargs.pop('market_timing')
        if 'psychology_factor' in kwargs:
            kwargs['pattern_adherence'] = kwargs.pop('psychology_factor')
        
        # Set defaults for any missing values
        for field in self.__dataclass_fields__:
            if field not in kwargs:
                kwargs[field] = self.__dataclass_fields__[field].default
        
        # Initialize with processed kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def calculate_composite_reward(self, weights: Dict[str, float] = None) -> float:
        """Calcula reward compuesto ponderado"""
        
        if weights is None:
            # Default weights optimized for smallcaps
            weights = {
                "pnl_magnitude": 0.25,
                "risk_adjusted_return": 0.20,
                "entry_timing_quality": 0.15,
                "pattern_adherence": 0.15,
                "sustainability_score": 0.10,
                "execution_quality": 0.10,
                "market_context_favorability": 0.05
            }
        
        composite = 0.0
        total_weight = 0.0
        
        for component, weight in weights.items():
            if hasattr(self, component):
                value = getattr(self, component)
                composite += value * weight
                total_weight += weight
        
        # Normalize by total weight
        if total_weight > 0:
            composite = composite / total_weight
        
        # Apply confidence scaling
        composite = composite * self.confidence_level
        
        return composite

@dataclass
class TradeJournalEntry:
    """Entrada completa del journal para un trade"""
    
    # Identificación del trade
    trade_id: str
    timestamp: datetime
    symbol: str
    
    # Datos del trade
    signal: Optional[Signal] = None
    position: Optional[Position] = None
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    quantity: int = 100
    pnl: Optional[float] = None
    
    # Contexto completo
    enhanced_context: Optional[EnhancedTickerContext] = None
    
    # Análisis automático (con defaults para testing)
    trade_classification: str = "UNKNOWN"
    technical_analysis: Dict[str, Any] = None
    market_context_analysis: Dict[str, Any] = None
    order_flow_analysis: Dict[str, Any] = None
    
    # Evaluación del sistema
    system_evaluation: Dict[str, Any] = None
    
    # Reward multi-dimensional
    reward_analysis: Optional[MultiDimensionalReward] = None
    
    # Lecciones aprendidas
    pattern_insights: Dict[str, Any] = None
    optimization_suggestions: Dict[str, Any] = None
    
    # Estado del trade
    trade_status: str = "open"  # "open", "closed", "stopped"
    
    def __post_init__(self):
        """Initialize default values"""
        if self.technical_analysis is None:
            self.technical_analysis = {}
        if self.market_context_analysis is None:
            self.market_context_analysis = {}
        if self.order_flow_analysis is None:
            self.order_flow_analysis = {}
        if self.system_evaluation is None:
            self.system_evaluation = {}
        if self.pattern_insights is None:
            self.pattern_insights = {}
        if self.optimization_suggestions is None:
            self.optimization_suggestions = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte entrada a diccionario para persistencia"""
        return {
            "trade_id": self.trade_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "pnl": self.pnl,
            "enhanced_context": asdict(self.enhanced_context),
            "trade_classification": self.trade_classification,
            "technical_analysis": self.technical_analysis,
            "market_context_analysis": self.market_context_analysis,
            "order_flow_analysis": self.order_flow_analysis,
            "system_evaluation": self.system_evaluation,
            "reward_analysis": asdict(self.reward_analysis),
            "pattern_insights": self.pattern_insights,
            "optimization_suggestions": self.optimization_suggestions,
            "trade_status": self.trade_status
        }

class MLTradingJournal:
    """
    ML Trading Journal - Sistema principal de análisis y aprendizaje avanzado
    
    Convierte cada trade en aprendizaje multi-dimensional para transformar
    el ML básico en ML elite con capacidades de trader profesional.
    """
    
    def __init__(self, config_path: str = "config.ini"):
        self.logger = logging.getLogger("MLTradingJournal")
        self.config_path = config_path
        
        # Storage
        self.journal_entries: Dict[str, TradeJournalEntry] = {}
        self.daily_summaries: Dict[str, Dict] = {}
        
        # Análisis avanzado
        self.trade_classifier = None
        self.technical_analyzer = None
        self.context_enhancer = None
        self.pattern_miner = None
        self.system_evaluator = None
        
        # Persistencia
        self.journal_file = Path("data/ml_trading_journal.json")
        self.journal_file.parent.mkdir(exist_ok=True)
        
        # Métricas de performance
        self.performance_metrics = defaultdict(lambda: defaultdict(float))
        self.pattern_success_rates = defaultdict(lambda: {"wins": 0, "total": 0})
        
        self.logger.info("🧠 ML Trading Journal initialized - Ready for elite learning")
    
    async def analyze_trade_entry(self, signal: Signal, enhanced_context: EnhancedTickerContext) -> str:
        """Analiza entrada de trade y genera ID único"""
        
        trade_id = f"{signal.symbol}_{signal.timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Crear entrada inicial
        entry = TradeJournalEntry(
            trade_id=trade_id,
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            signal=signal,
            position=None,
            entry_price=signal.price,
            exit_price=None,
            quantity=0,  # Se actualizará cuando se abra posición
            pnl=None,
            enhanced_context=enhanced_context,
            trade_classification="",
            technical_analysis={},
            market_context_analysis={},
            order_flow_analysis={},
            system_evaluation={},
            reward_analysis=None,
            pattern_insights={},
            optimization_suggestions={},
            trade_status="open"
        )
        
        # Análisis automático en background
        await self._perform_entry_analysis(entry)
        
        # Guardar entrada
        self.journal_entries[trade_id] = entry
        
        self.logger.info(f"📝 Journal entry created for {signal.symbol}: {trade_id}")
        return trade_id
    
    async def analyze_trade_exit(self, trade_id: str, exit_price: float, pnl: float, position: Position) -> MultiDimensionalReward:
        """Analiza salida de trade y calcula reward multi-dimensional"""
        
        if trade_id not in self.journal_entries:
            self.logger.error(f"Trade ID {trade_id} not found in journal")
            return None
        
        entry = self.journal_entries[trade_id]
        
        # Actualizar datos de salida
        entry.exit_price = exit_price
        entry.pnl = pnl
        entry.position = position
        entry.trade_status = "closed"
        entry.quantity = position.quantity if position else 0
        
        # Análisis completo de salida
        await self._perform_exit_analysis(entry)
        
        # Guardar cambios
        await self._save_journal()
        
        # Actualizar métricas de performance
        self._update_performance_metrics(entry)
        
        # Log resultado
        self.logger.info(f"📊 Trade completed: {entry.symbol} | PnL: ${pnl:.2f} | Category: {entry.trade_classification}")
        
        return entry.reward_analysis
    
    async def _perform_entry_analysis(self, entry: TradeJournalEntry):
        """Realiza análisis completo en entrada de trade"""
        
        # 1. Clasificación automática del trade
        entry.trade_classification = await self._classify_trade(entry)
        
        # 2. Análisis técnico automático
        entry.technical_analysis = await self._analyze_technical_setup(entry)
        
        # 3. Análisis de contexto de mercado
        entry.market_context_analysis = await self._analyze_market_context(entry)
        
        # 4. Análisis de order flow (si disponible)
        entry.order_flow_analysis = await self._analyze_order_flow(entry)
        
        # 5. Evaluación inicial del sistema
        entry.system_evaluation = await self._evaluate_system_entry(entry)
    
    async def _perform_exit_analysis(self, entry: TradeJournalEntry):
        """Realiza análisis completo en salida de trade"""
        
        # 1. Análisis de reward multi-dimensional
        entry.reward_analysis = await self._calculate_multidimensional_reward(entry)
        
        # 2. Insights de patrones
        entry.pattern_insights = await self._extract_pattern_insights(entry)
        
        # 3. Sugerencias de optimización
        entry.optimization_suggestions = await self._generate_optimization_suggestions(entry)
        
        # 4. Evaluación final del sistema
        entry.system_evaluation.update(await self._evaluate_system_exit(entry))
    
    async def _classify_trade(self, entry: TradeJournalEntry) -> str:
        """Clasificación automática del tipo de trade"""
        
        context = entry.enhanced_context
        
        # Pattern matching avanzado
        if context.volume_acceleration > 5.0 and context.short_squeeze_probability > 0.7:
            return "SHORT_SQUEEZE_EXPLOSION"
        elif context.daily_volume_pattern == "explosion" and context.news_sentiment > 0.5:
            return "NEWS_DRIVEN_VOLUME_EXPLOSION"
        elif context.breakout_potential > 0.8 and context.support_proximity < 0.1:
            return "TECHNICAL_BREAKOUT_SUPPORT"
        elif "vwap" in entry.signal.signal_type.value.lower() if entry.signal else False:
            return "VWAP_RECLAIM_MOMENTUM"
        elif context.intraday_momentum_quality > 0.8 and context.session_position == "early":
            return "OPENING_RANGE_BREAKOUT"
        elif context.mean_reversion_tendency > 0.7 and context.daily_trend_strength < -0.5:
            return "OVERSOLD_BOUNCE_REVERSAL"
        elif context.institutional_flow > 0.6 and context.market_cap_category == "small":
            return "INSTITUTIONAL_ACCUMULATION"
        else:
            return "GENERAL_MOMENTUM_TRADE"
    
    async def _analyze_technical_setup(self, entry: TradeJournalEntry) -> Dict[str, Any]:
        """Análisis técnico automático del setup"""
        
        context = entry.enhanced_context
        
        return {
            "setup_quality": (context.pattern_maturity + context.breakout_potential + context.optimal_entry_timing) / 3,
            "trend_alignment": context.daily_trend_strength,
            "volume_confirmation": context.volume_acceleration,
            "momentum_quality": context.intraday_momentum_quality,
            "support_resistance_context": {
                "support_proximity": context.support_proximity,
                "resistance_proximity": context.resistance_proximity,
                "breakout_potential": context.breakout_potential
            },
            "timing_analysis": {
                "optimal_timing_score": context.optimal_entry_timing,
                "session_timing": context.session_position,
                "pattern_maturity": context.pattern_maturity
            }
        }
    
    async def _analyze_market_context(self, entry: TradeJournalEntry) -> Dict[str, Any]:
        """Análisis del contexto de mercado"""
        
        context = entry.enhanced_context
        
        return {
            "overall_market_health": (1 + context.institutional_flow + context.sector_relative_strength) / 3,
            "news_environment": {
                "sentiment": context.news_sentiment,
                "social_sentiment": context.social_sentiment,
                "news_risk": context.news_risk
            },
            "sector_context": {
                "relative_strength": context.sector_relative_strength,
                "sector_trend": "bullish" if context.sector_relative_strength > 0.2 else "bearish" if context.sector_relative_strength < -0.2 else "neutral"
            },
            "market_regime": {
                "regime_type": context.market_regime,
                "volatility_regime": context.volatility_regime,
                "regime_favorability": 1.0 if context.market_regime in ["trending", "calm"] else 0.5
            }
        }
    
    async def _analyze_order_flow(self, entry: TradeJournalEntry) -> Dict[str, Any]:
        """Análisis de order flow y level 2"""
        
        context = entry.enhanced_context
        
        return {
            "liquidity_assessment": {
                "depth": context.liquidity_depth,
                "spread_health": context.bid_ask_spread_health,
                "liquidity_risk": context.liquidity_risk
            },
            "order_flow_signals": {
                "imbalance": context.order_flow_imbalance,
                "institutional_presence": context.large_order_presence,
                "flow_direction": "buying" if context.order_flow_imbalance > 0.2 else "selling" if context.order_flow_imbalance < -0.2 else "balanced"
            },
            "tape_reading": {
                "tape_strength": context.tape_strength,
                "interpretation": "strong" if context.tape_strength > 0.7 else "weak" if context.tape_strength < 0.3 else "neutral"
            }
        }
    
    async def _evaluate_system_entry(self, entry: TradeJournalEntry) -> Dict[str, Any]:
        """Evaluación del sistema en entrada"""
        
        context = entry.enhanced_context
        
        return {
            "setup_confidence": context.optimal_entry_timing * context.pattern_maturity,
            "risk_assessment": {
                "volatility_risk": 1.0 if context.volatility_regime == "extreme" else 0.5 if context.volatility_regime == "high" else 0.0,
                "liquidity_risk": context.liquidity_risk,
                "news_risk": context.news_risk,
                "overall_risk": (context.liquidity_risk + context.news_risk) / 2
            },
            "timing_evaluation": {
                "entry_timing_score": context.optimal_entry_timing,
                "session_timing_score": 1.0 if context.session_position == "early" else 0.7 if context.session_position == "mid" else 0.4
            }
        }
    
    async def _calculate_multidimensional_reward(self, entry: TradeJournalEntry) -> MultiDimensionalReward:
        """Calcula reward multi-dimensional sofisticado"""
        
        if not entry.pnl or not entry.exit_price or not entry.entry_price:
            return None
        
        # Calcular componentes del reward
        pnl_percentage = entry.pnl / (entry.entry_price * entry.quantity) if entry.quantity > 0 else 0
        
        # Risk-adjusted return (Sharpe-like)
        expected_volatility = entry.enhanced_context.volatility_10
        risk_adjusted = pnl_percentage / expected_volatility if expected_volatility > 0 else 0
        
        # Entry timing quality (basado en análisis técnico)
        entry_timing = entry.system_evaluation.get("timing_evaluation", {}).get("entry_timing_score", 0.5)
        
        # Exit timing quality (pendiente - requiere análisis de salida)
        exit_timing = 0.8 if entry.pnl > 0 else 0.3  # Placeholder
        
        # Pattern adherence (qué tan bien siguió el patrón esperado)
        pattern_adherence = entry.technical_analysis.get("setup_quality", 0.5)
        
        # Market context favorability
        market_favorability = entry.market_context_analysis.get("overall_market_health", 0.5)
        
        # Execution quality (placeholder - se puede mejorar)
        execution_quality = 0.8 if abs(pnl_percentage) > 0.02 else 0.5
        
        # Sustainability score (basado en historical success)
        sustainability = entry.enhanced_context.similar_pattern_success_rate
        
        return MultiDimensionalReward(
            pnl_magnitude=entry.pnl,
            pnl_percentage=pnl_percentage,
            risk_adjusted_return=risk_adjusted,
            entry_timing_quality=entry_timing,
            exit_timing_quality=exit_timing,
            pattern_adherence=pattern_adherence,
            market_context_favorability=market_favorability,
            execution_quality=execution_quality,
            opportunity_cost=0.0,  # Placeholder
            sustainability_score=sustainability,
            trade_category=entry.trade_classification,
            confidence_level=entry.system_evaluation.get("setup_confidence", 0.5)
        )
    
    async def _extract_pattern_insights(self, entry: TradeJournalEntry) -> Dict[str, Any]:
        """Extrae insights de patrones para aprendizaje futuro"""
        
        return {
            "successful_pattern_components": self._identify_success_factors(entry),
            "pattern_optimization_potential": self._assess_optimization_potential(entry),
            "similar_historical_performance": self._get_similar_pattern_stats(entry),
            "pattern_reliability_score": self._calculate_pattern_reliability(entry)
        }
    
    async def _generate_optimization_suggestions(self, entry: TradeJournalEntry) -> Dict[str, Any]:
        """Genera sugerencias de optimización del sistema"""
        
        suggestions = {
            "parameter_adjustments": {},
            "filter_improvements": {},
            "timing_optimizations": {},
            "risk_management_tweaks": {}
        }
        
        # Análisis basado en resultado
        if entry.pnl and entry.pnl > 0:
            # Trade ganador - qué repetir
            suggestions["successful_factors"] = {
                "context_factors": self._extract_winning_factors(entry),
                "timing_factors": entry.enhanced_context.session_position,
                "setup_quality": entry.technical_analysis.get("setup_quality", 0)
            }
        else:
            # Trade perdedor - qué mejorar
            suggestions["improvement_areas"] = {
                "risk_management": "Consider tighter stops" if abs(entry.pnl or 0) > 100 else "Appropriate risk",
                "entry_timing": "Earlier entry" if entry.enhanced_context.optimal_entry_timing < 0.5 else "Good timing",
                "market_context": "Avoid similar contexts" if entry.market_context_analysis.get("overall_market_health", 0) < 0.3 else "Context was fine"
            }
        
        return suggestions
    
    def _identify_success_factors(self, entry: TradeJournalEntry) -> List[str]:
        """Identifica factores que contribuyeron al éxito"""
        factors = []
        
        if entry.enhanced_context.volume_acceleration > 3.0:
            factors.append("high_volume_acceleration")
        if entry.enhanced_context.news_sentiment > 0.5:
            factors.append("positive_news_sentiment")
        if entry.enhanced_context.breakout_potential > 0.7:
            factors.append("strong_breakout_setup")
        if entry.enhanced_context.session_position == "early":
            factors.append("early_session_timing")
        
        return factors
    
    def _assess_optimization_potential(self, entry: TradeJournalEntry) -> float:
        """Evalúa potencial de optimización del patrón"""
        
        # Factores que indican alto potencial de optimización
        factors = [
            entry.enhanced_context.pattern_maturity,
            entry.enhanced_context.similar_pattern_success_rate,
            entry.enhanced_context.breakout_potential,
            entry.system_evaluation.get("setup_confidence", 0.5)
        ]
        
        return sum(factors) / len(factors)
    
    def _get_similar_pattern_stats(self, entry: TradeJournalEntry) -> Dict[str, Any]:
        """Obtiene estadísticas de patrones similares"""
        
        pattern_key = f"{entry.trade_classification}_{entry.enhanced_context.market_cap_category}"
        stats = self.pattern_success_rates[pattern_key]
        
        return {
            "total_trades": stats["total"],
            "win_rate": stats["wins"] / stats["total"] if stats["total"] > 0 else 0,
            "pattern_maturity": "high" if stats["total"] > 10 else "medium" if stats["total"] > 3 else "low"
        }
    
    def _calculate_pattern_reliability(self, entry: TradeJournalEntry) -> float:
        """Calcula confiabilidad del patrón"""
        
        # Combina múltiples factores de confiabilidad
        factors = [
            entry.enhanced_context.similar_pattern_success_rate,
            entry.enhanced_context.pattern_maturity,
            entry.system_evaluation.get("setup_confidence", 0.5),
            entry.technical_analysis.get("setup_quality", 0.5)
        ]
        
        return sum(factors) / len(factors)
    
    def _extract_winning_factors(self, entry: TradeJournalEntry) -> Dict[str, float]:
        """Extrae factores que contribuyeron a trade ganador"""
        
        return {
            "volume_acceleration": entry.enhanced_context.volume_acceleration,
            "news_sentiment": entry.enhanced_context.news_sentiment,
            "breakout_potential": entry.enhanced_context.breakout_potential,
            "momentum_quality": entry.enhanced_context.intraday_momentum_quality,
            "pattern_maturity": entry.enhanced_context.pattern_maturity
        }
    
    def _update_performance_metrics(self, entry: TradeJournalEntry):
        """Actualiza métricas de performance para ML"""
        
        # Métricas por categoría de trade
        category = entry.trade_classification
        
        if entry.pnl:
            self.performance_metrics[category]["total_pnl"] += entry.pnl
            self.performance_metrics[category]["total_trades"] += 1
            
            if entry.pnl > 0:
                self.performance_metrics[category]["winning_trades"] += 1
        
        # Métricas por patrón
        pattern_key = f"{category}_{entry.enhanced_context.market_cap_category}"
        self.pattern_success_rates[pattern_key]["total"] += 1
        
        if entry.pnl and entry.pnl > 0:
            self.pattern_success_rates[pattern_key]["wins"] += 1
    
    async def _save_journal(self):
        """Guarda journal en persistencia"""
        try:
            # Convertir entradas a formato serializable
            serializable_data = {
                "entries": {tid: entry.to_dict() for tid, entry in self.journal_entries.items()},
                "performance_metrics": dict(self.performance_metrics),
                "pattern_success_rates": dict(self.pattern_success_rates),
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.journal_file, 'w') as f:
                json.dump(serializable_data, f, indent=2, default=str)
                
            self.logger.debug(f"Journal saved: {len(self.journal_entries)} entries")
            
        except Exception as e:
            self.logger.error(f"Error saving journal: {e}")
    
    async def load_journal(self):
        """Carga journal desde persistencia"""
        try:
            if self.journal_file.exists():
                with open(self.journal_file, 'r') as f:
                    data = json.load(f)
                
                # Cargar métricas
                self.performance_metrics.update(data.get("performance_metrics", {}))
                self.pattern_success_rates.update(data.get("pattern_success_rates", {}))
                
                self.logger.info(f"Journal loaded: {len(data.get('entries', {}))} entries")
            
        except Exception as e:
            self.logger.error(f"Error loading journal: {e}")
    
    def get_advanced_insights(self) -> Dict[str, Any]:
        """Obtiene insights avanzados del journal para ML"""
        
        insights = {
            "total_trades_analyzed": len(self.journal_entries),
            "pattern_performance": {},
            "optimization_opportunities": {},
            "feature_importance": {},
            "market_regime_performance": {}
        }
        
        # Análisis de performance por patrón
        for pattern, stats in self.pattern_success_rates.items():
            if stats["total"] > 0:
                insights["pattern_performance"][pattern] = {
                    "win_rate": stats["wins"] / stats["total"],
                    "total_trades": stats["total"],
                    "confidence": "high" if stats["total"] > 10 else "medium" if stats["total"] > 3 else "low"
                }
        
        return insights
    
    def format_daily_summary(self, date: datetime) -> str:
        """Genera resumen diario estilo trader profesional"""
        
        date_str = date.strftime("%Y-%m-%d")
        
        # Filtrar trades del día
        daily_trades = [
            entry for entry in self.journal_entries.values()
            if entry.timestamp.date() == date.date() and entry.trade_status == "closed"
        ]
        
        if not daily_trades:
            return f"📅 Daily Report Card {date_str} | No trades completed"
        
        # Calcular métricas
        total_pnl = sum(trade.pnl for trade in daily_trades if trade.pnl)
        winning_trades = len([t for t in daily_trades if t.pnl and t.pnl > 0])
        total_trades = len(daily_trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Determinar grade
        if win_rate >= 70 and total_pnl > 0:
            grade = "A+"
        elif win_rate >= 60 and total_pnl > 0:
            grade = "A"
        elif win_rate >= 50 and total_pnl >= 0:
            grade = "B"
        elif total_pnl >= 0:
            grade = "C"
        else:
            grade = "D"
        
        # Construir reporte
        report = f"""
📅 Daily Report Card {date_str} | {grade} | ${total_pnl:.2f}

📊 PERFORMANCE SUMMARY:
• Total Trades: {total_trades}
• Win Rate: {win_rate:.1f}%
• Total PnL: ${total_pnl:.2f}
• Average Trade: ${total_pnl/total_trades:.2f}

🎯 TOP PERFORMING PATTERNS:
"""
        
        # Análisis de patrones del día
        pattern_performance = defaultdict(lambda: {"pnl": 0, "count": 0, "wins": 0})
        
        for trade in daily_trades:
            pattern = trade.trade_classification
            pattern_performance[pattern]["pnl"] += trade.pnl or 0
            pattern_performance[pattern]["count"] += 1
            if trade.pnl and trade.pnl > 0:
                pattern_performance[pattern]["wins"] += 1
        
        # Top 3 patrones
        top_patterns = sorted(
            pattern_performance.items(),
            key=lambda x: x[1]["pnl"],
            reverse=True
        )[:3]
        
        for pattern, stats in top_patterns:
            pattern_wr = (stats["wins"] / stats["count"] * 100) if stats["count"] > 0 else 0
            report += f"• {pattern}: ${stats['pnl']:.2f} ({pattern_wr:.0f}% WR, {stats['count']} trades)\n"
        
        report += f"""
🧠 ML LEARNING STATUS:
• Total Patterns Discovered: {len(self.pattern_success_rates)}
• Features Analyzed: {len(EnhancedTickerContext(
    symbol="", timestamp=datetime.now(), current_price=0,
    avg_volume_10=0, avg_volume_50=0, volatility_10=0, volatility_50=0,
    rsi_14=0, hour_of_day=0, minutes_from_open=0,
    daily_trend_strength=0, daily_volume_pattern="", support_proximity=0,
    resistance_proximity=0, breakout_potential=0, consolidation_days=0,
    intraday_momentum_quality=0, volume_acceleration=0, price_action_quality=0,
    tape_strength=0, news_sentiment=0, social_sentiment=0, institutional_flow=0,
    sector_relative_strength=0, market_regime="", market_cap_category="",
    float_size_category="", short_interest_ratio=0, short_squeeze_probability=0,
    insider_activity="", bid_ask_spread_health=0, liquidity_depth=0,
    order_flow_imbalance=0, large_order_presence=False,
    similar_pattern_success_rate=0, ticker_trading_history="",
    previous_breakout_follow_through=0, mean_reversion_tendency=0,
    optimal_entry_timing=0, pattern_maturity=0, time_decay_factor=0,
    session_position="", volatility_regime="", liquidity_risk=0,
    news_risk=0, overnight_risk=0
).get_feature_names())}+
• System Evolution: Elite ML Learning Active

💡 INSIGHTS & IMPROVEMENTS:
"""
        
        # Mejores y peores trades
        if daily_trades:
            best_trade = max(daily_trades, key=lambda t: t.pnl or 0)
            worst_trade = min(daily_trades, key=lambda t: t.pnl or 0)
            
            report += f"• Best Trade: {best_trade.symbol} ${best_trade.pnl:.2f} ({best_trade.trade_classification})\n"
            report += f"• Learning Point: {worst_trade.symbol} ${worst_trade.pnl:.2f} ({worst_trade.trade_classification})\n"
        
        return report

# Export principal classes
__all__ = [
    "MLTradingJournal",
    "EnhancedTickerContext", 
    "MultiDimensionalReward",
    "TradeJournalEntry"
]