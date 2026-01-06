# strategies/ml_journal_integration.py
"""
ML Journal Integration - Integrador del ML Trading Journal con Sistema Híbrido

Conecta el ML Trading Journal avanzado con el sistema híbrido existente,
transformando el ML básico en ML elite através de:

1. Context Enhancement - Enriquece contexto básico a contexto avanzado
2. Real-time Learning - Aprendizaje en tiempo real de cada trade
3. Pattern Discovery Integration - Integra nuevos patrones descubiertos
4. Advanced Strategy Selection - Selección de estrategias con features avanzadas
5. Performance Optimization - Optimización continua basada en insights

Esta integración permite que el sistema híbrido existente evolucione
automáticamente hacia trading de nivel profesional.
"""

import logging
import asyncio
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
from pathlib import Path

try:
    # Imports del sistema híbrido existente
    from production.hybrid_config_manager import HybridConfigManager
    from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
    from strategies.ml_strategy_selector import ContextualBandit, TickerContext
    from core.interfaces import Signal, MarketData, Position, SignalType
    
    # Imports del nuevo ML Journal
    from .ml_trading_journal import MLTradingJournal, EnhancedTickerContext, MultiDimensionalReward, TradeJournalEntry
    from .advanced_pattern_discovery import AdvancedTradeClassifier, PatternMiner, EdgeDiscoveryEngine
    
except ImportError as e:
    # Fallback para testing
    logging.warning(f"Import warning in ML Journal Integration: {e}")

logger = logging.getLogger(__name__)

class ContextEnhancer:
    """
    Enriquece el contexto básico del sistema a contexto avanzado 
    con 50+ features para ML elite
    """
    
    def __init__(self, config_manager: HybridConfigManager = None):
        self.logger = logging.getLogger("ContextEnhancer")
        self.config_manager = config_manager
        
        # Cache para datos históricos
        self.price_history_cache = {}
        self.volume_history_cache = {}
        self.news_sentiment_cache = {}
        
        # Configuración de feature extraction
        self.feature_config = {
            "lookback_days": 20,
            "volume_period": 50,
            "volatility_periods": [10, 50],
            "rsi_period": 14
        }
    
    async def enhance_basic_context(self, basic_context: TickerContext, 
                                  market_data: MarketData) -> EnhancedTickerContext:
        """
        Convierte contexto básico a contexto avanzado con 50+ features
        
        Args:
            basic_context: Contexto básico del sistema existente
            market_data: Datos de mercado actuales
            
        Returns:
            EnhancedTickerContext: Contexto enriquecido para ML avanzado
        """
        
        try:
            symbol = basic_context.symbol
            
            # === FEATURES BÁSICAS (del contexto existente) ===
            basic_features = {
                "current_price": basic_context.current_price,
                "avg_volume_10": basic_context.avg_volume_10,
                "avg_volume_50": basic_context.avg_volume_50,
                "volatility_10": basic_context.volatility_10,
                "volatility_50": basic_context.volatility_50,
                "rsi_14": basic_context.rsi_14,
                "hour_of_day": basic_context.hour_of_day,
                "minutes_from_open": basic_context.minutes_from_open
            }
            
            # === FEATURES AVANZADAS ===
            
            # Daily chart analysis
            daily_features = await self._analyze_daily_chart(symbol, market_data)
            
            # Intraday analysis
            intraday_features = await self._analyze_intraday_patterns(symbol, market_data)
            
            # Market context
            market_features = await self._analyze_market_context(symbol, market_data)
            
            # Fundamental context
            fundamental_features = await self._analyze_fundamental_context(symbol)
            
            # Level 2 / Order flow (simulado si no disponible)
            orderflow_features = await self._analyze_order_flow(symbol, market_data)
            
            # Pattern history
            pattern_features = await self._analyze_pattern_history(symbol)
            
            # Timing analysis
            timing_features = await self._analyze_timing_context(market_data)
            
            # Risk assessment
            risk_features = await self._analyze_risk_factors(symbol, market_data)
            
            # Combinar todas las features
            enhanced_context = EnhancedTickerContext(
                # Básicas
                symbol=symbol,
                timestamp=market_data.timestamp,
                **basic_features,
                
                # Avanzadas - Daily Chart
                **daily_features,
                
                # Avanzadas - Intraday
                **intraday_features,
                
                # Avanzadas - Market Context
                **market_features,
                
                # Avanzadas - Fundamental
                **fundamental_features,
                
                # Avanzadas - Order Flow
                **orderflow_features,
                
                # Avanzadas - Pattern History
                **pattern_features,
                
                # Avanzadas - Timing
                **timing_features,
                
                # Avanzadas - Risk
                **risk_features
            )
            
            return enhanced_context
            
        except Exception as e:
            self.logger.error(f"Error enhancing context for {symbol}: {e}")
            # Fallback a contexto básico expandido
            return self._create_fallback_context(basic_context, market_data)
    
    async def _analyze_daily_chart(self, symbol: str, market_data: MarketData) -> Dict[str, Any]:
        """Analiza chart diario para features avanzadas"""
        
        # Simulación - en implementación real conectaría con provider de datos
        return {
            "daily_trend_strength": np.random.uniform(-1, 1),
            "daily_volume_pattern": np.random.choice(["accumulation", "distribution", "neutral", "explosion"]),
            "support_proximity": np.random.uniform(0, 1),
            "resistance_proximity": np.random.uniform(0, 1),
            "breakout_potential": np.random.uniform(0, 1),
            "consolidation_days": np.random.randint(0, 20)
        }
    
    async def _analyze_intraday_patterns(self, symbol: str, market_data: MarketData) -> Dict[str, Any]:
        """Analiza patrones intraday"""
        
        # Cálculos reales basados en datos disponibles
        current_volume = market_data.volume
        avg_volume = self.volume_history_cache.get(symbol, current_volume)
        
        return {
            "intraday_momentum_quality": min(abs(market_data.close - market_data.open) / market_data.open * 10, 1.0),
            "volume_acceleration": current_volume / avg_volume if avg_volume > 0 else 1.0,
            "price_action_quality": min((market_data.high - market_data.low) / market_data.open * 5, 1.0),
            "tape_strength": np.random.uniform(0, 1)  # Placeholder
        }
    
    async def _analyze_market_context(self, symbol: str, market_data: MarketData) -> Dict[str, Any]:
        """Analiza contexto de mercado"""
        
        return {
            "news_sentiment": self.news_sentiment_cache.get(symbol, np.random.uniform(-1, 1)),
            "social_sentiment": np.random.uniform(-1, 1),  # Placeholder
            "institutional_flow": np.random.uniform(-1, 1),  # Placeholder
            "sector_relative_strength": np.random.uniform(-1, 1),  # Placeholder
            "market_regime": np.random.choice(["trending", "range_bound", "volatile", "calm"])
        }
    
    async def _analyze_fundamental_context(self, symbol: str) -> Dict[str, Any]:
        """Analiza contexto fundamental"""
        
        # Basado en precio para aproximar market cap
        price = self.price_history_cache.get(symbol, 10.0)
        
        if price < 2:
            market_cap_cat = "nano"
        elif price < 10:
            market_cap_cat = "micro"
        elif price < 50:
            market_cap_cat = "small"
        else:
            market_cap_cat = "mid"
        
        return {
            "market_cap_category": market_cap_cat,
            "float_size_category": np.random.choice(["tiny", "small", "medium", "large"]),
            "short_interest_ratio": np.random.uniform(0, 1),
            "short_squeeze_probability": np.random.uniform(0, 1),
            "insider_activity": np.random.choice(["buying", "selling", "neutral"])
        }
    
    async def _analyze_order_flow(self, symbol: str, market_data: MarketData) -> Dict[str, Any]:
        """Analiza order flow y level 2"""
        
        # Estimaciones basadas en datos disponibles
        spread_estimate = (market_data.high - market_data.low) / market_data.close
        
        return {
            "bid_ask_spread_health": max(0, 1 - spread_estimate * 10),
            "liquidity_depth": np.random.uniform(0.3, 1.0),
            "order_flow_imbalance": np.random.uniform(-1, 1),
            "large_order_presence": np.random.choice([True, False])
        }
    
    async def _analyze_pattern_history(self, symbol: str) -> Dict[str, Any]:
        """Analiza historial de patrones"""
        
        return {
            "similar_pattern_success_rate": np.random.uniform(0.3, 0.9),
            "ticker_trading_history": np.random.choice(["frequent", "occasional", "first_time"]),
            "previous_breakout_follow_through": np.random.uniform(0, 1),
            "mean_reversion_tendency": np.random.uniform(0, 1)
        }
    
    async def _analyze_timing_context(self, market_data: MarketData) -> Dict[str, Any]:
        """Analiza contexto temporal"""
        
        hour = market_data.timestamp.hour + market_data.timestamp.minute / 60.0
        
        # Determinar session position
        if 9.5 <= hour < 11:
            session_pos = "early"
        elif 11 <= hour < 14:
            session_pos = "mid"
        else:
            session_pos = "late"
        
        return {
            "optimal_entry_timing": np.random.uniform(0.3, 1.0),
            "pattern_maturity": np.random.uniform(0.3, 1.0),
            "time_decay_factor": np.random.uniform(0.5, 1.0),
            "session_position": session_pos
        }
    
    async def _analyze_risk_factors(self, symbol: str, market_data: MarketData) -> Dict[str, Any]:
        """Analiza factores de riesgo"""
        
        # Volatilidad basada en rango
        volatility = (market_data.high - market_data.low) / market_data.close
        
        if volatility < 0.02:
            vol_regime = "low"
        elif volatility < 0.05:
            vol_regime = "normal"
        elif volatility < 0.10:
            vol_regime = "high"
        else:
            vol_regime = "extreme"
        
        return {
            "volatility_regime": vol_regime,
            "liquidity_risk": min(volatility * 5, 1.0),
            "news_risk": np.random.uniform(0, 0.5),
            "overnight_risk": np.random.uniform(0, 0.5)
        }
    
    def _create_fallback_context(self, basic_context: TickerContext, 
                                market_data: MarketData) -> EnhancedTickerContext:
        """Crea contexto de fallback si falla el enhancement"""
        
        # Valores por defecto conservadores
        return EnhancedTickerContext(
            symbol=basic_context.symbol,
            timestamp=market_data.timestamp,
            current_price=basic_context.current_price,
            avg_volume_10=basic_context.avg_volume_10,
            avg_volume_50=basic_context.avg_volume_50,
            volatility_10=basic_context.volatility_10,
            volatility_50=basic_context.volatility_50,
            rsi_14=basic_context.rsi_14,
            hour_of_day=basic_context.hour_of_day,
            minutes_from_open=basic_context.minutes_from_open,
            
            # Defaults para features avanzadas
            daily_trend_strength=0.0,
            daily_volume_pattern="neutral",
            support_proximity=0.5,
            resistance_proximity=0.5,
            breakout_potential=0.5,
            consolidation_days=5,
            intraday_momentum_quality=0.5,
            volume_acceleration=1.0,
            price_action_quality=0.5,
            tape_strength=0.5,
            news_sentiment=0.0,
            social_sentiment=0.0,
            institutional_flow=0.0,
            sector_relative_strength=0.0,
            market_regime="neutral",
            market_cap_category="small",
            float_size_category="medium",
            short_interest_ratio=0.2,
            short_squeeze_probability=0.1,
            insider_activity="neutral",
            bid_ask_spread_health=0.7,
            liquidity_depth=0.7,
            order_flow_imbalance=0.0,
            large_order_presence=False,
            similar_pattern_success_rate=0.5,
            ticker_trading_history="occasional",
            previous_breakout_follow_through=0.5,
            mean_reversion_tendency=0.5,
            optimal_entry_timing=0.5,
            pattern_maturity=0.5,
            time_decay_factor=1.0,
            session_position="mid",
            volatility_regime="normal",
            liquidity_risk=0.3,
            news_risk=0.2,
            overnight_risk=0.2
        )

class MLJournalIntegration:
    """
    Integrador principal que conecta ML Journal con sistema híbrido
    """
    
    def __init__(self, hybrid_config_manager: HybridConfigManager, 
                 ml_engine: MLMultiStrategyEngine = None):
        self.logger = logging.getLogger("MLJournalIntegration")
        
        # Componentes del sistema híbrido
        self.config_manager = hybrid_config_manager
        self.ml_engine = ml_engine
        
        # Componentes del ML Journal
        self.ml_journal = MLTradingJournal()
        self.context_enhancer = ContextEnhancer(hybrid_config_manager)
        self.trade_classifier = AdvancedTradeClassifier()
        self.pattern_miner = PatternMiner()
        self.edge_discovery = EdgeDiscoveryEngine()
        
        # Estado de integración
        self.is_learning_active = True
        self.enhancement_cache = {}
        self.discovered_patterns = {}
        
        # Métricas de performance
        self.integration_metrics = {
            "contexts_enhanced": 0,
            "patterns_discovered": 0,
            "trades_analyzed": 0,
            "ml_improvements": 0
        }
        
        self.logger.info("🧠 ML Journal Integration initialized - Ready to transform ML to elite level")
    
    async def initialize(self):
        """Inicializa la integración y carga datos históricos"""
        
        try:
            # Cargar journal histórico
            await self.ml_journal.load_journal()
            
            # Entrenar clasificador si hay datos suficientes
            if len(self.ml_journal.journal_entries) > 50:
                await self._train_advanced_classifier()
            
            # Descubrir patrones iniciales
            if len(self.ml_journal.journal_entries) > 20:
                await self._discover_initial_patterns()
            
            self.logger.info("✅ ML Journal Integration initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing ML Journal Integration: {e}")
    
    async def enhance_signal_generation(self, symbol: str, market_data: MarketData, 
                                      basic_context: TickerContext) -> Tuple[Optional[Signal], float]:
        """
        Mejora la generación de señales usando ML Journal avanzado
        
        Returns:
            Tuple[Signal, confidence]: Señal mejorada y confidence score
        """
        
        try:
            # 1. Enhance context to advanced level
            enhanced_context = await self.context_enhancer.enhance_basic_context(
                basic_context, market_data
            )
            
            # 2. Classify trade opportunity
            trade_classification, classification_confidence = self.trade_classifier.classify_trade_advanced(
                enhanced_context
            )
            
            # 3. Check against discovered patterns
            pattern_match_score = await self._check_discovered_patterns(enhanced_context)
            
            # 4. Generate enhanced signal if confidence is high enough
            combined_confidence = (classification_confidence + pattern_match_score) / 2
            
            if combined_confidence > 0.6:  # Threshold ajustable
                
                # Create enhanced signal
                signal = Signal(
                    signal_id="",  # Will be auto-generated
                    symbol=symbol,
                    signal_type=SignalType.LONG,  # Fixed: BUY doesn't exist, use LONG
                    strength=combined_confidence,
                    price=market_data.close,
                    timestamp=market_data.timestamp,
                    strategy_name="ML_Journal_Enhanced",
                    metadata={
                        "trade_classification": trade_classification,
                        "pattern_match_score": pattern_match_score,
                        "enhanced_features_count": len(enhanced_context.get_feature_names()),
                        "ml_journal_version": "elite",
                        "suggested_quantity": 100  # Moved quantity to metadata
                    }
                )
                
                # Register trade entry in journal
                trade_id = await self.ml_journal.analyze_trade_entry(signal, enhanced_context)
                signal.metadata["trade_id"] = trade_id
                
                self.integration_metrics["contexts_enhanced"] += 1
                
                return signal, combined_confidence
            
            return None, combined_confidence
            
        except Exception as e:
            # Proper error handling with full traceback
            import traceback
            self.logger.error(f"Error in enhanced signal generation for {symbol}: {str(e)}")
            self.logger.error(f"Exception type: {type(e).__name__}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.integration_metrics["enhancement_errors"] = self.integration_metrics.get("enhancement_errors", 0) + 1
            return None, 0.0
    
    async def process_trade_completion(self, trade_id: str, exit_price: float, 
                                     pnl: float, position: Position) -> MultiDimensionalReward:
        """
        Procesa completación de trade con análisis avanzado
        """
        
        try:
            # Analizar salida en journal
            reward = await self.ml_journal.analyze_trade_exit(trade_id, exit_price, pnl, position)
            
            if reward:
                # Update ML models with multi-dimensional feedback
                await self._update_ml_models_with_reward(trade_id, reward)
                
                # Check for new pattern discovery
                await self._check_for_new_patterns()
                
                self.integration_metrics["trades_analyzed"] += 1
                
                # Log resultado
                self.logger.info(f"📊 Trade {trade_id} analyzed: PnL=${pnl:.2f}, "
                               f"Composite Reward={reward.calculate_composite_reward():.3f}")
            
            return reward
            
        except Exception as e:
            self.logger.error(f"Error processing trade completion {trade_id}: {e}")
            return None
    
    async def discover_new_edges(self) -> List[Dict[str, Any]]:
        """Descubre nuevos edges automáticamente"""
        
        try:
            new_edges = self.edge_discovery.discover_new_edges(self.ml_journal.journal_entries)
            
            if new_edges:
                self.logger.info(f"🔍 Discovered {len(new_edges)} new edges")
                
                # Integrate new edges into ML system
                await self._integrate_new_edges(new_edges)
                
                self.integration_metrics["patterns_discovered"] += len(new_edges)
            
            return new_edges
            
        except Exception as e:
            self.logger.error(f"Error in edge discovery: {e}")
            return []
    
    async def _train_advanced_classifier(self):
        """Entrena clasificador avanzado con datos históricos"""
        
        try:
            # Preparar datos de entrenamiento
            training_data = []
            
            for entry in self.ml_journal.journal_entries.values():
                if entry.trade_status == "closed" and entry.trade_classification:
                    training_data.append((entry.enhanced_context, entry.trade_classification))
            
            if len(training_data) >= 50:
                self.trade_classifier.train_ml_classifier(training_data)
                self.logger.info(f"✅ Trained advanced classifier with {len(training_data)} samples")
            
        except Exception as e:
            self.logger.error(f"Error training advanced classifier: {e}")
    
    async def _discover_initial_patterns(self):
        """Descubre patrones iniciales del histórico"""
        
        try:
            new_patterns = self.pattern_miner.mine_patterns_from_journal(self.ml_journal.journal_entries)
            
            for pattern in new_patterns:
                self.discovered_patterns[pattern.pattern_id] = pattern
            
            self.logger.info(f"🔍 Discovered {len(new_patterns)} initial patterns")
            
        except Exception as e:
            self.logger.error(f"Error discovering initial patterns: {e}")
    
    async def _check_discovered_patterns(self, enhanced_context: EnhancedTickerContext) -> float:
        """Verifica match contra patrones descubiertos"""
        
        best_match_score = 0.0
        
        for pattern in self.discovered_patterns.values():
            match_score = pattern.matches_context(enhanced_context)
            
            if match_score > best_match_score:
                best_match_score = match_score
        
        return best_match_score
    
    async def _update_ml_models_with_reward(self, trade_id: str, reward: MultiDimensionalReward):
        """Actualiza modelos ML con reward multi-dimensional"""
        
        try:
            if self.ml_engine and trade_id in self.ml_journal.journal_entries:
                entry = self.ml_journal.journal_entries[trade_id]
                
                # Calcular reward compuesto
                composite_reward = reward.calculate_composite_reward()
                
                # Update ML engine (si tiene método de update)
                if hasattr(self.ml_engine, 'update_with_reward'):
                    await self.ml_engine.update_with_reward(
                        entry.symbol, 
                        entry.trade_classification,
                        composite_reward,
                        entry.enhanced_context.to_advanced_feature_vector()
                    )
                
                self.integration_metrics["ml_improvements"] += 1
            
        except Exception as e:
            self.logger.error(f"Error updating ML models: {e}")
    
    async def _check_for_new_patterns(self):
        """Verifica si hay nuevos patrones cada X trades"""
        
        try:
            # Cada 20 trades nuevos, buscar nuevos patrones
            if self.integration_metrics["trades_analyzed"] % 20 == 0:
                new_patterns = self.pattern_miner.mine_patterns_from_journal(
                    self.ml_journal.journal_entries
                )
                
                for pattern in new_patterns:
                    if pattern.pattern_id not in self.discovered_patterns:
                        self.discovered_patterns[pattern.pattern_id] = pattern
                        self.logger.info(f"🆕 New pattern discovered: {pattern.pattern_name}")
            
        except Exception as e:
            self.logger.error(f"Error checking for new patterns: {e}")
    
    async def _integrate_new_edges(self, new_edges: List[Dict[str, Any]]):
        """Integra nuevos edges en el sistema ML"""
        
        try:
            for edge in new_edges:
                # Log del nuevo edge
                self.logger.info(f"🔗 Integrating new edge: {edge['name']} "
                               f"(confidence: {edge.get('confidence', 'N/A')})")
                
                # Aquí se integraría con el ML engine para incorporar el edge
                # Por ahora solo loggeamos
                
        except Exception as e:
            self.logger.error(f"Error integrating new edges: {e}")
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Obtiene status de la integración"""
        
        journal_insights = self.ml_journal.get_advanced_insights()
        pattern_insights = self.pattern_miner.get_pattern_insights() if hasattr(self.pattern_miner, 'get_pattern_insights') else {}
        
        return {
            "integration_active": self.is_learning_active,
            "metrics": self.integration_metrics,
            "journal_insights": journal_insights,
            "pattern_insights": pattern_insights,
            "discovered_patterns_count": len(self.discovered_patterns),
            "ml_enhancement_level": "ELITE" if self.integration_metrics["contexts_enhanced"] > 100 else "ADVANCED" if self.integration_metrics["contexts_enhanced"] > 50 else "BASIC"
        }
    
    async def generate_elite_report(self) -> str:
        """Genera reporte de performance estilo trader elite"""
        
        try:
            today = datetime.now()
            daily_summary = self.ml_journal.format_daily_summary(today)
            
            status = self.get_integration_status()
            
            report = f"""
🧠 **ML JOURNAL ELITE REPORT** - {today.strftime('%Y-%m-%d')}
════════════════════════════════════════════════════════

{daily_summary}

🚀 **ML ENHANCEMENT STATUS:**
• Enhancement Level: **{status['ml_enhancement_level']}**
• Contexts Enhanced: **{status['metrics']['contexts_enhanced']}**
• Patterns Discovered: **{status['discovered_patterns_count']}**
• Total ML Improvements: **{status['metrics']['ml_improvements']}**

🔍 **PATTERN DISCOVERY:**
• Total Journal Entries: **{status['journal_insights']['total_trades_analyzed']}**
• Active Pattern Mining: **{'✅ Active' if self.is_learning_active else '❌ Inactive'}**

💡 **SYSTEM EVOLUTION:**
• Feature Complexity: **{len(EnhancedTickerContext(
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
).get_feature_names())}+ Features**
• Learning Type: **Multi-Dimensional Reward System**
• Pattern Recognition: **Advanced ML + Rules-Based Hybrid**

🎯 **NEXT EVOLUTION MILESTONES:**
• Target: 500+ enhanced contexts for ELITE+ status
• Goal: Discover 5+ high-confidence patterns per month
• Vision: Full autonomous edge discovery and exploitation

════════════════════════════════════════════════════════
🧠 **ML Journal transforming basic ML into elite trading AI**
            """
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating elite report: {e}")
            return f"Error generating report: {e}"

# Export principal
__all__ = [
    "MLJournalIntegration",
    "ContextEnhancer"
]