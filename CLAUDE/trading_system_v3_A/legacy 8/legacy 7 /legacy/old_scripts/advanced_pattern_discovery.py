# strategies/advanced_pattern_discovery.py
"""
Advanced Pattern Discovery & Trade Classification System

Sistema avanzado de descubrimiento de patrones y clasificación automática de trades
que permite al ML encontrar nuevos edges automáticamente y clasificar trades con
precisión profesional.

Características:
1. Trade Classifier - Clasificación automática sofisticada
2. Pattern Miner - Descubrimiento automático de nuevos patrones
3. Edge Discovery - Identificación de nuevos edges rentables
4. Feature Importance Analysis - Análisis de importancia de features
5. Market Regime Detection - Detección automática de regímenes de mercado
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set, Any
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass
import logging
try:
    from sklearn.cluster import KMeans
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    # Mock classes for when sklearn is not available
    class KMeans:
        def __init__(self, *args, **kwargs):
            pass
        def fit_predict(self, X):
            # Simple mock clustering
            return np.random.randint(0, min(3, len(X)), len(X))
    
    class RandomForestClassifier:
        def __init__(self, *args, **kwargs):
            self.feature_importances_ = None
        def fit(self, X, y):
            self.feature_importances_ = np.random.random(X.shape[1])
        def predict(self, X):
            return np.array(["MOCK_PATTERN"])
        def predict_proba(self, X):
            return np.array([[0.6, 0.4]])
import json
from pathlib import Path

try:
    from .ml_trading_journal import EnhancedTickerContext, TradeJournalEntry, MultiDimensionalReward
except ImportError:
    # For standalone testing
    pass

logger = logging.getLogger(__name__)

@dataclass
class PatternSignature:
    """Firma única de un patrón de trading"""
    
    pattern_id: str
    pattern_name: str
    key_features: Dict[str, float]  # Features principales que definen el patrón
    feature_ranges: Dict[str, Tuple[float, float]]  # Rangos válidos para cada feature
    success_rate: float
    total_trades: int
    avg_pnl: float
    confidence_level: float
    market_regime_dependency: str  # "any", "trending", "range_bound", "volatile"
    time_of_day_dependency: List[str]  # ["early", "mid", "late"] or specific hours
    
    def matches_context(self, context: EnhancedTickerContext, tolerance: float = 0.2) -> float:
        """Calcula qué tan bien un contexto coincide con este patrón (0-1)"""
        
        match_score = 0.0
        total_features = 0
        
        feature_vector = context.to_advanced_feature_vector()
        feature_names = context.get_feature_names()
        
        for i, feature_name in enumerate(feature_names):
            if feature_name in self.key_features:
                expected_value = self.key_features[feature_name]
                actual_value = feature_vector[i]
                
                # Calcular similaridad normalizada
                if feature_name in self.feature_ranges:
                    min_val, max_val = self.feature_ranges[feature_name]
                    range_size = max_val - min_val
                    if range_size > 0:
                        diff = abs(expected_value - actual_value)
                        similarity = max(0, 1 - (diff / (range_size * tolerance)))
                        match_score += similarity
                        total_features += 1
        
        return match_score / total_features if total_features > 0 else 0.0

class AdvancedTradeClassifier:
    """
    Clasificador avanzado de trades que identifica automáticamente 
    patrones complejos y los categoriza para aprendizaje ML
    """
    
    def __init__(self):
        self.logger = logging.getLogger("AdvancedTradeClassifier")
        
        # Patrones base conocidos
        self.base_patterns = {
            "EXPLOSIVE_VOLUME_GAP": {
                "volume_acceleration": (5.0, float('inf')),
                "news_sentiment": (0.3, 1.0),
                "breakout_potential": (0.6, 1.0),
                "session_position": ["early", "mid"]
            },
            "SHORT_SQUEEZE_SETUP": {
                "short_squeeze_probability": (0.7, 1.0),
                "volume_acceleration": (3.0, float('inf')),
                "float_size_category": ["tiny", "small"],
                "order_flow_imbalance": (0.3, 1.0)
            },
            "VWAP_RECLAIM_MOMENTUM": {
                "daily_trend_strength": (-0.8, 0.3),
                "intraday_momentum_quality": (0.6, 1.0),
                "volume_acceleration": (1.5, float('inf')),
                "support_proximity": (0.0, 0.3)
            },
            "INSTITUTIONAL_ACCUMULATION": {
                "institutional_flow": (0.5, 1.0),
                "large_order_presence": [True],
                "market_cap_category": ["small", "mid"],
                "liquidity_depth": (0.6, 1.0)
            },
            "NEWS_DRIVEN_MOMENTUM": {
                "news_sentiment": (0.5, 1.0),
                "social_sentiment": (0.3, 1.0),
                "volume_acceleration": (2.0, float('inf')),
                "daily_volume_pattern": ["explosion"]
            },
            "TECHNICAL_BREAKOUT": {
                "breakout_potential": (0.8, 1.0),
                "pattern_maturity": (0.7, 1.0),
                "resistance_proximity": (0.0, 0.1),
                "daily_trend_strength": (0.2, 1.0)
            },
            "OVERSOLD_BOUNCE": {
                "mean_reversion_tendency": (0.6, 1.0),
                "daily_trend_strength": (-1.0, -0.3),
                "support_proximity": (0.0, 0.2),
                "rsi_14": (0.0, 0.35)
            },
            "OPENING_RANGE_BREAKOUT": {
                "session_position": ["early"],
                "intraday_momentum_quality": (0.7, 1.0),
                "volume_acceleration": (1.8, float('inf')),
                "minutes_from_open": (10, 60)
            }
        }
        
        # Clasificador ML para patrones complejos
        self.ml_classifier = None
        self.feature_importance = {}
        
        # Historial de clasificaciones para mejora continua
        self.classification_history = []
        
    def classify_trade_advanced(self, context: EnhancedTickerContext, 
                              confidence_threshold: float = 0.6) -> Tuple[str, float]:
        """
        Clasificación avanzada usando tanto rules-based como ML
        
        Returns:
            Tuple[str, float]: (classification, confidence)
        """
        
        # 1. Intentar clasificación rules-based primero
        rule_classification, rule_confidence = self._classify_rules_based(context)
        
        if rule_confidence >= confidence_threshold:
            return rule_classification, rule_confidence
        
        # 2. Usar ML classifier para patrones complejos
        if self.ml_classifier is not None:
            ml_classification, ml_confidence = self._classify_ml_based(context)
            
            if ml_confidence >= confidence_threshold:
                return ml_classification, ml_confidence
        
        # 3. Fallback a clasificación general
        return self._classify_general_fallback(context)
    
    def _classify_rules_based(self, context: EnhancedTickerContext) -> Tuple[str, float]:
        """Clasificación basada en reglas predefinidas"""
        
        best_match = "UNKNOWN"
        best_score = 0.0
        
        feature_vector = context.to_advanced_feature_vector()
        feature_names = context.get_feature_names()
        
        # Crear diccionario de features para fácil acceso
        features = dict(zip(feature_names, feature_vector))
        
        for pattern_name, pattern_rules in self.base_patterns.items():
            score = self._calculate_pattern_match_score(features, pattern_rules, context)
            
            if score > best_score:
                best_score = score
                best_match = pattern_name
        
        return best_match, best_score
    
    def _calculate_pattern_match_score(self, features: Dict[str, float], 
                                     pattern_rules: Dict[str, Any], 
                                     context: EnhancedTickerContext) -> float:
        """Calcula score de match para un patrón específico"""
        
        total_score = 0.0
        total_weights = 0.0
        
        for rule_name, rule_value in pattern_rules.items():
            weight = 1.0  # Peso base
            
            if rule_name in features:
                feature_value = features[rule_name]
                
                if isinstance(rule_value, tuple):  # Rango numérico
                    min_val, max_val = rule_value
                    if min_val <= feature_value <= max_val:
                        total_score += weight
                    else:
                        # Score parcial basado en qué tan cerca está
                        if feature_value < min_val:
                            distance = min_val - feature_value
                            max_distance = min_val  # Normalization factor
                        else:
                            distance = feature_value - max_val
                            max_distance = max_val
                        
                        partial_score = max(0, 1 - (distance / max_distance)) * weight
                        total_score += partial_score
                    
                    total_weights += weight
                
                elif isinstance(rule_value, list):  # Lista de valores válidos
                    if isinstance(feature_value, (int, float)):
                        # Para valores booleanos convertidos a float
                        if rule_name == "large_order_presence":
                            if (feature_value > 0.5 and True in rule_value) or \
                               (feature_value <= 0.5 and False in rule_value):
                                total_score += weight
                    else:
                        # Para valores categóricos, necesitamos acceso al contexto original
                        context_value = getattr(context, rule_name, None)
                        if context_value in rule_value:
                            total_score += weight
                    
                    total_weights += weight
        
        return total_score / total_weights if total_weights > 0 else 0.0
    
    def _classify_ml_based(self, context: EnhancedTickerContext) -> Tuple[str, float]:
        """Clasificación usando ML para patrones complejos"""
        
        if self.ml_classifier is None:
            return "ML_NOT_READY", 0.0
        
        try:
            feature_vector = context.to_advanced_feature_vector().reshape(1, -1)
            
            # Predicción con probabilidades
            prediction = self.ml_classifier.predict(feature_vector)[0]
            probabilities = self.ml_classifier.predict_proba(feature_vector)[0]
            
            # Confidence es la probabilidad máxima
            confidence = max(probabilities)
            
            return f"ML_{prediction}", confidence
            
        except Exception as e:
            self.logger.error(f"Error in ML classification: {e}")
            return "ML_ERROR", 0.0
    
    def _classify_general_fallback(self, context: EnhancedTickerContext) -> Tuple[str, float]:
        """Clasificación general de fallback"""
        
        # Clasificación simple basada en características principales
        if context.volume_acceleration > 3.0:
            if context.news_sentiment > 0.3:
                return "GENERAL_NEWS_MOMENTUM", 0.4
            else:
                return "GENERAL_VOLUME_SPIKE", 0.4
        
        elif context.breakout_potential > 0.6:
            return "GENERAL_BREAKOUT", 0.4
        
        elif context.mean_reversion_tendency > 0.6:
            return "GENERAL_MEAN_REVERSION", 0.4
        
        else:
            return "GENERAL_MOMENTUM", 0.3
    
    def train_ml_classifier(self, historical_data: List[Tuple[EnhancedTickerContext, str]]):
        """Entrena el clasificador ML con datos históricos"""
        
        if len(historical_data) < 50:
            self.logger.warning("Insufficient data for ML classifier training")
            return
        
        try:
            # Preparar datos de entrenamiento
            X = []
            y = []
            
            for context, classification in historical_data:
                X.append(context.to_advanced_feature_vector())
                y.append(classification)
            
            X = np.array(X)
            y = np.array(y)
            
            # Entrenar Random Forest
            self.ml_classifier = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                class_weight='balanced'
            )
            
            self.ml_classifier.fit(X, y)
            
            # Calcular importancia de features
            feature_names = historical_data[0][0].get_feature_names()
            self.feature_importance = dict(zip(
                feature_names, 
                self.ml_classifier.feature_importances_
            ))
            
            self.logger.info(f"ML classifier trained with {len(historical_data)} samples")
            
        except Exception as e:
            self.logger.error(f"Error training ML classifier: {e}")

class PatternMiner:
    """
    Sistema de descubrimiento automático de patrones rentables
    usando técnicas de clustering y análisis estadístico
    """
    
    def __init__(self, min_pattern_trades: int = 5, min_success_rate: float = 0.6):
        self.logger = logging.getLogger("PatternMiner")
        self.min_pattern_trades = min_pattern_trades
        self.min_success_rate = min_success_rate
        
        # Discovered patterns
        self.discovered_patterns: Dict[str, PatternSignature] = {}
        
        # Mining history
        self.mining_sessions = []
        
    def mine_patterns_from_journal(self, journal_entries: Dict[str, TradeJournalEntry]) -> List[PatternSignature]:
        """
        Descubre nuevos patrones automáticamente analizando el journal de trades
        
        Returns:
            List[PatternSignature]: Lista de nuevos patrones descubiertos
        """
        
        self.logger.info(f"Mining patterns from {len(journal_entries)} journal entries...")
        
        # 1. Preparar datos para clustering
        successful_trades = self._extract_successful_trades(journal_entries)
        
        if len(successful_trades) < self.min_pattern_trades * 2:
            self.logger.warning("Insufficient successful trades for pattern mining")
            return []
        
        # 2. Clustering de trades exitosos
        clusters = self._cluster_successful_trades(successful_trades)
        
        # 3. Analizar cada cluster para identificar patrones
        new_patterns = []
        
        for cluster_id, cluster_trades in clusters.items():
            if len(cluster_trades) >= self.min_pattern_trades:
                pattern = self._analyze_cluster_for_pattern(cluster_id, cluster_trades)
                
                if pattern and pattern.success_rate >= self.min_success_rate:
                    new_patterns.append(pattern)
                    self.discovered_patterns[pattern.pattern_id] = pattern
        
        self.logger.info(f"Discovered {len(new_patterns)} new patterns")
        return new_patterns
    
    def _extract_successful_trades(self, journal_entries: Dict[str, TradeJournalEntry]) -> List[TradeJournalEntry]:
        """Extrae trades exitosos para análisis de patrones"""
        
        successful_trades = []
        
        for entry in journal_entries.values():
            if (entry.trade_status == "closed" and 
                entry.pnl is not None and 
                entry.pnl > 0 and
                entry.reward_analysis is not None and
                entry.reward_analysis.risk_adjusted_return > 0.5):
                
                successful_trades.append(entry)
        
        return successful_trades
    
    def _cluster_successful_trades(self, successful_trades: List[TradeJournalEntry]) -> Dict[int, List[TradeJournalEntry]]:
        """Agrupa trades exitosos usando clustering"""
        
        # Extraer features para clustering
        feature_matrix = []
        
        for trade in successful_trades:
            features = trade.enhanced_context.to_advanced_feature_vector()
            feature_matrix.append(features)
        
        feature_matrix = np.array(feature_matrix)
        
        # Determinar número óptimo de clusters
        n_clusters = min(max(len(successful_trades) // self.min_pattern_trades, 2), 10)
        
        # K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(feature_matrix)
        
        # Agrupar trades por cluster
        clusters = defaultdict(list)
        for trade, label in zip(successful_trades, cluster_labels):
            clusters[label].append(trade)
        
        return dict(clusters)
    
    def _analyze_cluster_for_pattern(self, cluster_id: int, cluster_trades: List[TradeJournalEntry]) -> Optional[PatternSignature]:
        """Analiza un cluster para identificar patrones comunes"""
        
        try:
            # Calcular estadísticas del cluster
            total_trades = len(cluster_trades)
            total_pnl = sum(trade.pnl for trade in cluster_trades if trade.pnl)
            avg_pnl = total_pnl / total_trades
            
            # Todos los trades en el cluster son exitosos por definición
            success_rate = 1.0
            
            # Extraer features comunes
            feature_vectors = [trade.enhanced_context.to_advanced_feature_vector() for trade in cluster_trades]
            feature_matrix = np.array(feature_vectors)
            
            # Calcular medias y rangos de features
            feature_means = np.mean(feature_matrix, axis=0)
            feature_stds = np.std(feature_matrix, axis=0)
            feature_mins = np.min(feature_matrix, axis=0)
            feature_maxs = np.max(feature_matrix, axis=0)
            
            feature_names = cluster_trades[0].enhanced_context.get_feature_names()
            
            # Identificar features distintivas (alta varianza dentro del cluster, baja entre clusters)
            key_features = {}
            feature_ranges = {}
            
            for i, (name, mean, std, min_val, max_val) in enumerate(zip(
                feature_names, feature_means, feature_stds, feature_mins, feature_maxs
            )):
                # Feature es clave si tiene baja varianza (std) y valor consistente
                if std < 0.3 and abs(mean) > 0.1:  # Thresholds ajustables
                    key_features[name] = float(mean)
                    feature_ranges[name] = (float(min_val), float(max_val))
            
            # Analizar dependencias de contexto
            market_regimes = [trade.enhanced_context.market_regime for trade in cluster_trades]
            regime_counter = Counter(market_regimes)
            most_common_regime = regime_counter.most_common(1)[0][0] if regime_counter else "any"
            
            session_positions = [trade.enhanced_context.session_position for trade in cluster_trades]
            session_counter = Counter(session_positions)
            common_sessions = [session for session, count in session_counter.items() 
                             if count / total_trades >= 0.3]  # Al menos 30% de trades
            
            # Generar nombre descriptivo del patrón
            pattern_name = self._generate_pattern_name(key_features, most_common_regime)
            pattern_id = f"DISCOVERED_{cluster_id}_{pattern_name}"
            
            # Calcular confidence basado en consistencia
            confidence = self._calculate_pattern_confidence(cluster_trades, key_features)
            
            return PatternSignature(
                pattern_id=pattern_id,
                pattern_name=pattern_name,
                key_features=key_features,
                feature_ranges=feature_ranges,
                success_rate=success_rate,
                total_trades=total_trades,
                avg_pnl=avg_pnl,
                confidence_level=confidence,
                market_regime_dependency=most_common_regime,
                time_of_day_dependency=common_sessions
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing cluster {cluster_id}: {e}")
            return None
    
    def _generate_pattern_name(self, key_features: Dict[str, float], regime: str) -> str:
        """Genera nombre descriptivo para el patrón"""
        
        descriptors = []
        
        # Analizar features más importantes
        if "volume_acceleration" in key_features and key_features["volume_acceleration"] > 3.0:
            descriptors.append("HIGH_VOLUME")
        
        if "news_sentiment" in key_features and key_features["news_sentiment"] > 0.5:
            descriptors.append("POSITIVE_NEWS")
        
        if "breakout_potential" in key_features and key_features["breakout_potential"] > 0.7:
            descriptors.append("BREAKOUT")
        
        if "short_squeeze_probability" in key_features and key_features["short_squeeze_probability"] > 0.6:
            descriptors.append("SQUEEZE")
        
        if "institutional_flow" in key_features and key_features["institutional_flow"] > 0.5:
            descriptors.append("INSTITUTIONAL")
        
        # Agregar contexto de régimen si es específico
        if regime != "any":
            descriptors.append(regime.upper())
        
        # Construir nombre
        if descriptors:
            return "_".join(descriptors)
        else:
            return "MOMENTUM_PATTERN"
    
    def _calculate_pattern_confidence(self, cluster_trades: List[TradeJournalEntry], 
                                    key_features: Dict[str, float]) -> float:
        """Calcula confidence del patrón basado en consistencia"""
        
        if not cluster_trades:
            return 0.0
        
        # Factores de confidence
        factors = []
        
        # 1. Número de trades (más trades = más confidence)
        trade_count_factor = min(len(cluster_trades) / 20.0, 1.0)  # Max confidence at 20 trades
        factors.append(trade_count_factor)
        
        # 2. Consistencia de PnL
        pnls = [trade.pnl for trade in cluster_trades if trade.pnl]
        if pnls:
            pnl_consistency = 1.0 - (np.std(pnls) / np.mean(pnls)) if np.mean(pnls) > 0 else 0.0
            pnl_consistency = max(0.0, min(1.0, pnl_consistency))
            factors.append(pnl_consistency)
        
        # 3. Diversidad de símbolos (pattrón no específico a un stock)
        symbols = set(trade.symbol for trade in cluster_trades)
        symbol_diversity = min(len(symbols) / len(cluster_trades), 0.8)  # Max 80% diversity
        factors.append(symbol_diversity)
        
        # 4. Consistencia temporal (patrón funciona en diferentes días)
        dates = set(trade.timestamp.date() for trade in cluster_trades)
        temporal_diversity = min(len(dates) / 10.0, 1.0)  # Max confidence at 10 different days
        factors.append(temporal_diversity)
        
        # Promedio ponderado
        weights = [0.3, 0.3, 0.2, 0.2]  # Ajustable
        confidence = sum(f * w for f, w in zip(factors, weights)) / sum(weights)
        
        return confidence
    
    def get_pattern_insights(self) -> Dict[str, Any]:
        """Obtiene insights de los patrones descubiertos"""
        
        insights = {
            "total_patterns_discovered": len(self.discovered_patterns),
            "pattern_summary": {},
            "feature_importance_global": {},
            "regime_preferences": {},
            "session_preferences": {}
        }
        
        if not self.discovered_patterns:
            return insights
        
        # Analizar cada patrón
        for pattern_id, pattern in self.discovered_patterns.items():
            insights["pattern_summary"][pattern_id] = {
                "name": pattern.pattern_name,
                "success_rate": pattern.success_rate,
                "total_trades": pattern.total_trades,
                "avg_pnl": pattern.avg_pnl,
                "confidence": pattern.confidence_level,
                "regime_dependency": pattern.market_regime_dependency
            }
        
        # Feature importance global
        all_features = defaultdict(list)
        for pattern in self.discovered_patterns.values():
            for feature, importance in pattern.key_features.items():
                all_features[feature].append(importance)
        
        for feature, values in all_features.items():
            insights["feature_importance_global"][feature] = {
                "frequency": len(values),
                "avg_importance": np.mean(values),
                "consistency": 1.0 - np.std(values) if len(values) > 1 else 1.0
            }
        
        # Preferencias de régimen
        regime_counts = Counter(p.market_regime_dependency for p in self.discovered_patterns.values())
        insights["regime_preferences"] = dict(regime_counts)
        
        return insights

class EdgeDiscoveryEngine:
    """
    Motor de descubrimiento de nuevos edges rentables
    combinando pattern mining con análisis estadístico
    """
    
    def __init__(self):
        self.logger = logging.getLogger("EdgeDiscoveryEngine")
        self.pattern_miner = PatternMiner()
        self.trade_classifier = AdvancedTradeClassifier()
        
        # Discovered edges
        self.discovered_edges = {}
        
    def discover_new_edges(self, journal_entries: Dict[str, TradeJournalEntry]) -> List[Dict[str, Any]]:
        """
        Descubre nuevos edges analizando el journal completo
        
        Returns:
            List[Dict]: Lista de nuevos edges descobrertos con métricas
        """
        
        self.logger.info("Starting edge discovery process...")
        
        # 1. Mine new patterns
        new_patterns = self.pattern_miner.mine_patterns_from_journal(journal_entries)
        
        # 2. Analyze statistical edges
        statistical_edges = self._discover_statistical_edges(journal_entries)
        
        # 3. Analyze feature correlations
        feature_edges = self._discover_feature_correlation_edges(journal_entries)
        
        # 4. Analyze temporal edges
        temporal_edges = self._discover_temporal_edges(journal_entries)
        
        # Combine all discoveries
        all_edges = []
        
        # Convert patterns to edges
        for pattern in new_patterns:
            edge = {
                "type": "pattern",
                "id": pattern.pattern_id,
                "name": pattern.pattern_name,
                "success_rate": pattern.success_rate,
                "total_trades": pattern.total_trades,
                "avg_pnl": pattern.avg_pnl,
                "confidence": pattern.confidence_level,
                "description": f"Discovered pattern: {pattern.pattern_name}",
                "key_features": pattern.key_features
            }
            all_edges.append(edge)
        
        all_edges.extend(statistical_edges)
        all_edges.extend(feature_edges)
        all_edges.extend(temporal_edges)
        
        self.logger.info(f"Discovered {len(all_edges)} new edges")
        return all_edges
    
    def _discover_statistical_edges(self, journal_entries: Dict[str, TradeJournalEntry]) -> List[Dict[str, Any]]:
        """Descubre edges estadísticos"""
        
        edges = []
        
        # Analizar performance por diferentes dimensiones
        dimensions = {
            "market_cap_category": lambda e: e.enhanced_context.market_cap_category,
            "volatility_regime": lambda e: e.enhanced_context.volatility_regime,
            "session_position": lambda e: e.enhanced_context.session_position,
            "news_sentiment_range": lambda e: "positive" if e.enhanced_context.news_sentiment > 0.3 else "negative" if e.enhanced_context.news_sentiment < -0.3 else "neutral"
        }
        
        for dimension_name, extractor in dimensions.items():
            edge = self._analyze_dimension_performance(journal_entries, dimension_name, extractor)
            if edge:
                edges.append(edge)
        
        return edges
    
    def _discover_feature_correlation_edges(self, journal_entries: Dict[str, TradeJournalEntry]) -> List[Dict[str, Any]]:
        """Descubre edges basados en correlaciones de features"""
        
        edges = []
        
        try:
            # Preparar datos
            completed_trades = [e for e in journal_entries.values() if e.trade_status == "closed" and e.pnl is not None]
            
            if len(completed_trades) < 20:
                return edges
            
            # Extraer features y outcomes
            feature_matrix = []
            outcomes = []
            
            for trade in completed_trades:
                features = trade.enhanced_context.to_advanced_feature_vector()
                feature_matrix.append(features)
                outcomes.append(1 if trade.pnl > 0 else 0)
            
            feature_matrix = np.array(feature_matrix)
            outcomes = np.array(outcomes)
            feature_names = completed_trades[0].enhanced_context.get_feature_names()
            
            # Calcular correlaciones
            correlations = []
            for i, feature_name in enumerate(feature_names):
                corr = np.corrcoef(feature_matrix[:, i], outcomes)[0, 1]
                if not np.isnan(corr):
                    correlations.append((feature_name, abs(corr), corr))
            
            # Identificar features con alta correlación
            correlations.sort(key=lambda x: x[1], reverse=True)
            
            for feature_name, abs_corr, corr in correlations[:5]:  # Top 5
                if abs_corr > 0.3:  # Threshold significativo
                    edge = {
                        "type": "feature_correlation",
                        "id": f"CORR_{feature_name}",
                        "name": f"Feature Correlation: {feature_name}",
                        "correlation": corr,
                        "abs_correlation": abs_corr,
                        "significance": "high" if abs_corr > 0.5 else "medium",
                        "description": f"Feature {feature_name} shows {abs_corr:.2f} correlation with success",
                        "recommendation": f"{'Favor' if corr > 0 else 'Avoid'} trades with high {feature_name}"
                    }
                    edges.append(edge)
            
        except Exception as e:
            self.logger.error(f"Error in feature correlation analysis: {e}")
        
        return edges
    
    def _discover_temporal_edges(self, journal_entries: Dict[str, TradeJournalEntry]) -> List[Dict[str, Any]]:
        """Descubre edges temporales"""
        
        edges = []
        
        try:
            completed_trades = [e for e in journal_entries.values() if e.trade_status == "closed" and e.pnl is not None]
            
            # Analizar performance por hora del día
            hourly_performance = defaultdict(lambda: {"wins": 0, "total": 0, "total_pnl": 0})
            
            for trade in completed_trades:
                hour = int(trade.enhanced_context.hour_of_day)
                hourly_performance[hour]["total"] += 1
                hourly_performance[hour]["total_pnl"] += trade.pnl
                if trade.pnl > 0:
                    hourly_performance[hour]["wins"] += 1
            
            # Identificar horas con edge significativo
            for hour, stats in hourly_performance.items():
                if stats["total"] >= 5:  # Mínimo 5 trades
                    win_rate = stats["wins"] / stats["total"]
                    avg_pnl = stats["total_pnl"] / stats["total"]
                    
                    if win_rate > 0.65 or avg_pnl > 50:  # Thresholds para edge
                        edge = {
                            "type": "temporal",
                            "id": f"HOUR_{hour}",
                            "name": f"Hour {hour}:00 Edge",
                            "hour": hour,
                            "win_rate": win_rate,
                            "avg_pnl": avg_pnl,
                            "total_trades": stats["total"],
                            "description": f"Hour {hour}:00 shows exceptional performance",
                            "recommendation": f"Favor trades during {hour}:00-{hour+1}:00"
                        }
                        edges.append(edge)
            
        except Exception as e:
            self.logger.error(f"Error in temporal analysis: {e}")
        
        return edges
    
    def _analyze_dimension_performance(self, journal_entries: Dict[str, TradeJournalEntry], 
                                     dimension_name: str, extractor) -> Optional[Dict[str, Any]]:
        """Analiza performance en una dimensión específica"""
        
        try:
            completed_trades = [e for e in journal_entries.values() if e.trade_status == "closed" and e.pnl is not None]
            
            # Agrupar por dimensión
            dimension_performance = defaultdict(lambda: {"wins": 0, "total": 0, "total_pnl": 0})
            
            for trade in completed_trades:
                dimension_value = extractor(trade)
                dimension_performance[dimension_value]["total"] += 1
                dimension_performance[dimension_value]["total_pnl"] += trade.pnl
                if trade.pnl > 0:
                    dimension_performance[dimension_value]["wins"] += 1
            
            # Encontrar el valor con mejor performance
            best_value = None
            best_score = 0
            
            for value, stats in dimension_performance.items():
                if stats["total"] >= 3:  # Mínimo 3 trades
                    win_rate = stats["wins"] / stats["total"]
                    avg_pnl = stats["total_pnl"] / stats["total"]
                    
                    # Score combinado
                    score = win_rate * 0.7 + (avg_pnl / 100.0) * 0.3  # Ponderado
                    
                    if score > best_score and win_rate > 0.6:
                        best_score = score
                        best_value = value
            
            if best_value is not None:
                stats = dimension_performance[best_value]
                return {
                    "type": "statistical",
                    "id": f"STAT_{dimension_name}_{best_value}",
                    "name": f"{dimension_name.title()} Edge: {best_value}",
                    "dimension": dimension_name,
                    "best_value": best_value,
                    "win_rate": stats["wins"] / stats["total"],
                    "avg_pnl": stats["total_pnl"] / stats["total"],
                    "total_trades": stats["total"],
                    "score": best_score,
                    "description": f"{dimension_name} = {best_value} shows superior performance",
                    "recommendation": f"Favor trades with {dimension_name} = {best_value}"
                }
        
        except Exception as e:
            self.logger.error(f"Error analyzing dimension {dimension_name}: {e}")
        
        return None

# Export classes
__all__ = [
    "AdvancedTradeClassifier",
    "PatternMiner", 
    "EdgeDiscoveryEngine",
    "PatternSignature"
]