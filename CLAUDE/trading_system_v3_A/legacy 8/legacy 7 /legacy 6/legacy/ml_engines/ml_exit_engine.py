#!/usr/bin/env python3
"""
ML Exit Engine - Sistema de salidas inteligentes basado en Machine Learning
========================================================================

Reemplaza todas las salidas estáticas con ML dinámico por estrategia.
Optimiza timing de salida para maximizar beneficios y minimizar pérdidas.
"""

import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_absolute_error
import joblib
import logging
import os
import json

from core.fomo_detector import FOMODetector
from core.interfaces import MarketData, Position

@dataclass
class ExitPrediction:
    """Predicción de salida del ML"""
    should_exit: bool
    confidence: float
    exit_type: str  # 'PROFIT_OPTIMAL', 'FOMO_EXIT', 'STOP_PROTECTION', 'TIME_DECAY'
    expected_value: float
    probability_higher_5min: float
    probability_higher_15min: float
    optimal_hold_minutes: int
    reasons: List[str]

@dataclass
class ExitFeatures:
    """Features para ML de salidas"""
    # Position context
    entry_price: float
    current_price: float
    current_pnl_pct: float
    time_in_position_minutes: int
    entry_volume_ratio: float
    
    # Market context
    current_volume_ratio: float
    rsi: float
    price_vs_vwap: float
    fomo_score: float
    time_of_day: float
    market_stress: float
    
    # Strategy specific
    strategy: str
    catalyst_age_minutes: Optional[int] = None
    gap_fill_pct: Optional[float] = None
    breakout_strength: Optional[float] = None
    volume_declining_bars: int = 0
    
    # Momentum indicators  
    price_momentum_5min: float = 0.0
    volume_momentum: float = 0.0
    sector_performance: float = 0.0

class MLExitEngine:
    """
    Motor de salidas inteligentes con ML por estrategia
    Aprende patrones óptimos de salida para maximizar beneficios
    OPTIMIZADO PARA SMALLCAP TRADING
    """
    
    def __init__(self, 
                 trading_db_path: str = "trading_data.db",
                 market_db_path: str = "trading_data.db",  # ✅ Base de datos de producción
                 models_dir: str = "core/models/exit_models",
                 smallcap_mode: bool = True):
        
        self.trading_db_path = trading_db_path
        self.market_db_path = market_db_path
        self.models_dir = models_dir
        self.smallcap_mode = smallcap_mode
        self.logger = logging.getLogger(__name__)
        
        # ML models by strategy
        self.exit_models = {}
        self.profit_predictors = {}
        self.scalers = {}
        
        # ML LEARNING FLAGS - No static parameters, ML learns everything
        self.smallcap_learning_enabled = smallcap_mode
        
        # Strategy list
        # ✅ SOLO ESTRATEGIAS HABILITADAS EN config.ini (7 estrategias activas)
        self.strategies = [
            # 🌅 Morning Power
            'orb', 'gap_go',
            
            # 🕐 All-Day Core  
            'macdv_smallcaps', 'vwap_reclaim',
            
            # 📰 Event-Driven
            'catalyst_momentum',
            
            # 🌆 Specialized
            'eod_momentum', 'volume_breakout'
        ]
        
        # FOMO integration
        self.fomo_detector = FOMODetector()
        
        # Feature columns
        self.feature_columns = [
            'current_pnl_pct', 'time_in_position_minutes', 'entry_volume_ratio',
            'current_volume_ratio', 'rsi', 'price_vs_vwap', 'fomo_score',
            'time_of_day', 'market_stress', 'volume_declining_bars',
            'price_momentum_5min', 'volume_momentum', 'sector_performance',
            # SMALLCAP LEARNING FEATURES - ML will automatically learn patterns
            'price_level', 'is_smallcap_price', 'volatility_per_minute',
            'day_of_week', 'is_lunch_time', 'is_friday', 'market_cap_proxy'
        ]
        
        # Create models directory
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Setup database tables
        self._setup_exit_feedback_tables()
        
        # Track delayed positions for synchronization
        self.delayed_positions = {}  # symbol -> delayed_position_info
        
        self.logger.info("🎯 MLExitEngine initialized")
        if self.smallcap_learning_enabled:
            self.logger.info("🧠 SMALLCAP LEARNING: ML will automatically learn smallcap patterns")
        
    def _setup_exit_feedback_tables(self):
        """Crear tablas para feedback de salidas"""
        with sqlite3.connect(self.trading_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS exit_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    exit_time TIMESTAMP NOT NULL,
                    exit_price REAL NOT NULL,
                    exit_type TEXT NOT NULL,
                    actual_profit_pct REAL NOT NULL,
                    max_profit_after_exit REAL,
                    regret_pct REAL,
                    was_optimal BOOLEAN,
                    hold_time_minutes INTEGER,
                    exit_features TEXT,  -- JSON serialized features
                    ml_prediction_accuracy REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS exit_model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy TEXT NOT NULL,
                    model_type TEXT NOT NULL,  -- 'exit_classifier', 'profit_predictor'
                    accuracy REAL,
                    precision REAL,
                    recall REAL,
                    mae REAL,  -- Mean Absolute Error for profit prediction
                    training_samples INTEGER,
                    evaluation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    model_version TEXT,
                    UNIQUE(strategy, model_type, evaluation_date)
                )
            """)
            
            conn.commit()
    
    def register_delayed_position(self, symbol: str, delayed_info: Dict) -> None:
        """Register a position that was delayed and should be tracked when entry executes"""
        self.delayed_positions[symbol] = {
            'delayed_info': delayed_info,
            'registered_time': datetime.now(),
            'should_track': True
        }
        
        self.logger.info(f"🧠 ML Exit Engine: Registered delayed position for {symbol}")
    
    def should_delay_ml_exit(self, symbol: str) -> bool:
        """Check if ML exit processing should be delayed due to pending entry"""
        return symbol in self.delayed_positions
    
    def should_exit(self, position: Position, current_data: MarketData, 
                   bars_history: List[MarketData]) -> Dict[str, Any]:
        """
        Decisión principal de salida usando ML
        
        Args:
            position: Posición actual
            current_data: Datos de mercado actuales
            bars_history: Historial de barras para análisis
            
        Returns:
            Dict con decisión de salida y análisis
        """
        # Quick check: If ML exits disabled, return no exit
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read('config.ini')
            if not config.getboolean('GLOBAL', 'enable_ml_exits', fallback=True):
                return {'should_exit': False, 'reason': 'ML exits disabled in config'}
        except:
            pass
            
        try:
            # Check if this position should have delayed ML exit processing
            if self.should_delay_ml_exit(position.symbol):
                self.logger.debug(f"🧠 ML exit for {position.symbol} delayed due to pending entry synchronization")
                return {'should_exit': False, 'reason': 'ML exit delayed - entry synchronization pending'}
            
            strategy = position.strategy
            
            # Extract features
            features = self._extract_exit_features(position, current_data, bars_history)
            
            if not features:
                return {'should_exit': False, 'reason': 'Insufficient data for ML exit analysis'}
            
            # Get ML prediction
            prediction = self._predict_exit(strategy, features)
            
            # Integrate FOMO detection
            fomo_result = self.fomo_detector.detect_fomo_exit(
                position.symbol, current_data, position, bars_history
            )
            
            # Combine ML + FOMO for final decision
            final_decision = self._combine_ml_fomo_decision(prediction, fomo_result, features)
            
            # Log decision
            if final_decision['should_exit']:
                self.logger.info(
                    f"🎯 ML EXIT SIGNAL: {position.symbol} | "
                    f"Type: {final_decision['exit_type']} | "
                    f"Confidence: {final_decision['confidence']:.2f} | "
                    f"Expected Value: {final_decision['expected_value']:.3f}"
                )
                
            return final_decision
            
        except Exception as e:
            self.logger.error(f"Error in ML exit decision for {position.symbol}: {e}")
            return {'should_exit': False, 'reason': f'ML exit error: {e}'}
    
    def _extract_exit_features(self, position: Position, current_data: MarketData,
                              bars_history: List[MarketData]) -> Optional[ExitFeatures]:
        """Extrae features para ML de salidas"""
        try:
            # AJUSTE: Reducir requisito mínimo de barras para decisiones más ágiles
            min_bars_required = 3  # Reducido de 10 a 3 para evaluaciones más frecuentes
            if len(bars_history) < min_bars_required:
                self.logger.debug(f"Insufficient bars: {len(bars_history)} < {min_bars_required}")
                return None
                
            # Basic position metrics
            current_pnl_pct = (current_data.close - position.entry_price) / position.entry_price
            
            # Handle timezone issues - ensure both timestamps are timezone-aware
            entry_time = position.entry_time
            current_time = current_data.timestamp
            
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)
                
            holding_time = (current_time - entry_time).total_seconds() / 60
            
            # Volume analysis - adaptable a historial corto
            recent_volumes = [bar.volume for bar in bars_history[-min(10, len(bars_history)):]]
            # Para avg_volume usar lo que tengamos disponible
            if len(bars_history) >= 15:
                avg_volume = np.mean([bar.volume for bar in bars_history[-15:-3]])
            elif len(bars_history) >= 5:
                avg_volume = np.mean([bar.volume for bar in bars_history[:-1]])  # Excluir última barra
            else:
                avg_volume = np.mean(recent_volumes) if recent_volumes else current_data.volume
            current_volume_ratio = current_data.volume / avg_volume if avg_volume > 0 else 1.0
            
            # Technical indicators - adaptables a historial corto
            rsi = self._calculate_rsi(bars_history)
            # VWAP con datos disponibles
            vwap_bars = bars_history[-min(20, len(bars_history)):]
            vwap = self._calculate_vwap(vwap_bars)
            price_vs_vwap = current_data.close / vwap if vwap > 0 else 1.0
            
            # FOMO score
            fomo_analysis = self.fomo_detector.detect_fomo_exit(
                position.symbol, current_data, position, bars_history
            )
            fomo_score = fomo_analysis.get('analysis', {}).get('fomo_score', 0.0)
            
            # Time context
            time_of_day = current_data.timestamp.hour + current_data.timestamp.minute / 60.0
            time_of_day_normalized = time_of_day / 24.0
            
            # Volume declining pattern
            volume_declining_bars = 0
            if len(recent_volumes) >= 5:
                for i in range(1, min(5, len(recent_volumes))):
                    if recent_volumes[-i] < recent_volumes[-(i+1)]:
                        volume_declining_bars += 1
                    else:
                        break
            
            # Momentum indicators - adaptables a datos disponibles  
            momentum_bars = min(5, len(bars_history))
            price_momentum_5min = self._calculate_price_momentum(bars_history[-momentum_bars:]) if momentum_bars >= 2 else 0.0
            volume_momentum_bars = min(10, len(bars_history))
            volume_momentum = self._calculate_volume_momentum(bars_history[-volume_momentum_bars:]) if volume_momentum_bars >= 3 else 0.0
            
            # Market stress (simplified VIX proxy) - adaptable
            stress_bars = min(10, len(bars_history))
            recent_ranges = [(bar.high - bar.low) / bar.close for bar in bars_history[-stress_bars:] if bar.close > 0]
            market_stress = np.mean(recent_ranges) if recent_ranges else 0.02
            
            # SMALLCAP LEARNING FEATURES - Let ML discover patterns automatically
            price_level = current_data.close
            is_smallcap_price = 1.0 if (0.5 <= price_level <= 15.0) else 0.0
            volatility_per_minute = abs(current_pnl_pct) / max(holding_time, 1) if holding_time > 0 else 0.0
            day_of_week = current_data.timestamp.weekday()  # 0=Monday, 6=Sunday
            is_lunch_time = 1.0 if (12 <= current_data.timestamp.hour < 14) else 0.0
            is_friday = 1.0 if (day_of_week == 4) else 0.0
            # Simple market cap proxy based on price * volume
            market_cap_proxy = np.log1p(price_level * current_volume_ratio * 1000000)
            
            return ExitFeatures(
                entry_price=position.entry_price,
                current_price=current_data.close,
                current_pnl_pct=current_pnl_pct,
                time_in_position_minutes=int(holding_time),
                entry_volume_ratio=getattr(position, 'entry_volume_ratio', 1.0),
                current_volume_ratio=current_volume_ratio,
                rsi=rsi,
                price_vs_vwap=price_vs_vwap,
                fomo_score=fomo_score,
                time_of_day=time_of_day_normalized,
                market_stress=market_stress,
                strategy=position.strategy,
                volume_declining_bars=volume_declining_bars,
                price_momentum_5min=price_momentum_5min,
                volume_momentum=volume_momentum,
                sector_performance=0.0,
                # Additional smallcap learning features
                catalyst_age_minutes=None,
                gap_fill_pct=None,
                breakout_strength=None
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting exit features: {e}")
            return None
    
    def _predict_exit(self, strategy: str, features: ExitFeatures) -> ExitPrediction:
        """Predice salida usando ML models"""
        try:
            # Load models if not available
            if strategy not in self.exit_models:
                self._load_or_create_models(strategy)
            
            # Prepare feature vector
            feature_vector = self._features_to_vector(features)
            
            if strategy in self.exit_models and self.exit_models[strategy] is not None:
                # Predict with trained model
                should_exit_prob = self.exit_models[strategy].predict_proba([feature_vector])[0]
                should_exit = should_exit_prob[1] > 0.6  # 60% threshold
                confidence = max(should_exit_prob)
                
                # Predict expected profit if holding - FIXED: usar solo las 8 features base
                if strategy in self.profit_predictors and self.profit_predictors[strategy] is not None:
                    # Use same feature vector as classification (our regressor was trained on expected_value_hold)
                    expected_profit_5min = self.profit_predictors[strategy].predict([feature_vector])[0]
                    expected_profit_15min = expected_profit_5min * 0.95  # Slight decay for longer horizon
                else:
                    expected_profit_5min = features.current_pnl_pct * 0.95  # Slight decay assumption
                    expected_profit_15min = features.current_pnl_pct * 0.90
                
            else:
                # Fallback to heuristic rules
                should_exit, confidence, expected_profit_5min, expected_profit_15min = self._heuristic_exit_decision(features)
            
            # Determine exit type and reasons
            exit_type, reasons = self._determine_exit_type(features, should_exit)
            
            # Calculate expected value of exiting now vs holding
            current_value = features.current_pnl_pct
            expected_value_hold = (expected_profit_5min + expected_profit_15min) / 2
            expected_value = current_value if should_exit else expected_value_hold
            
            # Estimate optimal hold time
            optimal_hold_minutes = self._estimate_optimal_hold_time(features, strategy)
            
            return ExitPrediction(
                should_exit=should_exit,
                confidence=confidence,
                exit_type=exit_type,
                expected_value=expected_value,
                probability_higher_5min=max(0, (expected_profit_5min - features.current_pnl_pct) * 10),
                probability_higher_15min=max(0, (expected_profit_15min - features.current_pnl_pct) * 10),
                optimal_hold_minutes=optimal_hold_minutes,
                reasons=reasons
            )
            
        except Exception as e:
            self.logger.error(f"Error in ML exit prediction: {e}")
            return ExitPrediction(
                should_exit=False, confidence=0.5, exit_type='ERROR',
                expected_value=features.current_pnl_pct, probability_higher_5min=0.5,
                probability_higher_15min=0.5, optimal_hold_minutes=60, reasons=[f"Prediction error: {e}"]
            )
    
    def _heuristic_exit_decision(self, features: ExitFeatures) -> Tuple[bool, float, float, float]:
        """Reglas heurísticas de salida cuando no hay modelo ML - AJUSTADAS PARA SMALLCAPS"""
        should_exit = False
        confidence = 0.5
        
        # AJUSTADAS: Reglas más agresivas para smallcaps - profits menores pero más frecuentes
        
        # Profit protection - REDUCIDO para smallcaps
        if features.current_pnl_pct > 0.08:  # 8%+ profit (reducido de 15%)
            if features.fomo_score > 0.6 or features.volume_declining_bars >= 2:  # Más sensible
                should_exit = True
                confidence = 0.8
                self.logger.info(f"🎯 Heuristic exit: 8%+ profit with FOMO {features.fomo_score:.2f} or volume decline")
        
        # Medium profit with time/volume concerns - MÁS AGRESIVO
        elif features.current_pnl_pct > 0.04:  # 4%+ profit 
            if (features.time_in_position_minutes > 30 and features.fomo_score > 0.3) or features.volume_declining_bars >= 2 or features.time_of_day > 0.62:  # After 15:00 ET
                should_exit = True
                confidence = 0.7
                self.logger.info(f"🎯 Heuristic exit: 4%+ profit with time {features.time_in_position_minutes}min, FOMO {features.fomo_score:.2f}, or market time")
        
        # Small profit near close - NUEVO
        elif features.current_pnl_pct > 0.02 and features.time_of_day > 0.64:  # 2%+ profit after 15:24 ET
            should_exit = True
            confidence = 0.8
            self.logger.info(f"🎯 Heuristic exit: 2%+ profit near market close {features.time_of_day:.2f}")
                
        # Loss protection - AJUSTADO  
        elif features.current_pnl_pct < -0.06:  # 6% loss (reducido de 8%)
            should_exit = True
            confidence = 0.9
            self.logger.info(f"🎯 Heuristic exit: 6% loss protection")
            
        # Time decay - MÁS AGRESIVO para smallcaps
        elif features.time_in_position_minutes > 120:  # 2+ hours (reducido de 3)
            if features.current_pnl_pct > 0.01:  # Any small profit
                should_exit = True
                confidence = 0.7
                self.logger.info(f"🎯 Heuristic exit: Time decay 2h+ with {features.current_pnl_pct:.2%} profit")
        
        # End of day approach (near market close)
        elif features.time_of_day > 0.65:  # After ~15:36 ET (0.65 * 24 = 15.6)
            if features.current_pnl_pct > 0.005:  # Any profit near close
                should_exit = True
                confidence = 0.8
                self.logger.info(f"🎯 Heuristic exit: Near market close with profit")
        
        # Basic future profit estimation
        expected_profit_5min = features.current_pnl_pct * 0.98
        expected_profit_15min = features.current_pnl_pct * 0.95
        
        return should_exit, confidence, expected_profit_5min, expected_profit_15min
    
    def _combine_ml_fomo_decision(self, ml_prediction: ExitPrediction, 
                                 fomo_result: Dict, features: ExitFeatures) -> Dict[str, Any]:
        """Combina decisión ML + FOMO para decisión final"""
        
        # FOMO override - if critical FOMO, force exit
        if fomo_result.get('should_exit') and fomo_result.get('analysis', {}).get('urgency') == 'CRITICAL':
            return {
                'should_exit': True,
                'exit_type': 'FOMO_CRITICAL',
                'confidence': 0.95,
                'expected_value': features.current_pnl_pct,
                'reasons': ['Critical FOMO detected'] + fomo_result.get('analysis', {}).get('reasons', []),
                'ml_prediction': ml_prediction,
                'fomo_analysis': fomo_result
            }
        
        # ML primary decision
        primary_exit = ml_prediction.should_exit
        
        # FOMO weight in decision
        fomo_weight = 0.3 if fomo_result.get('should_exit') else 0.0
        ml_weight = 0.7
        
        # Combined confidence
        combined_confidence = (
            ml_prediction.confidence * ml_weight + 
            fomo_result.get('analysis', {}).get('confidence', 0.5) * fomo_weight
        )
        
        # Final decision
        should_exit = primary_exit or (
            fomo_result.get('should_exit') and 
            combined_confidence > 0.75
        )
        
        exit_type = ml_prediction.exit_type
        if fomo_result.get('should_exit') and should_exit:
            exit_type = f"{exit_type}_WITH_FOMO"
        
        return {
            'should_exit': should_exit,
            'exit_type': exit_type,
            'confidence': combined_confidence,
            'expected_value': ml_prediction.expected_value,
            'reasons': ml_prediction.reasons + fomo_result.get('analysis', {}).get('reasons', []),
            'ml_prediction': ml_prediction,
            'fomo_analysis': fomo_result,
            'optimal_hold_minutes': ml_prediction.optimal_hold_minutes
        }
    
    def record_exit_feedback(self, trade_id: str, symbol: str, strategy: str,
                           exit_price: float, exit_type: str, actual_profit_pct: float,
                           features: ExitFeatures, prediction_accuracy: float = None):
        """Registra feedback de salida para continuous learning"""
        try:
            with sqlite3.connect(self.trading_db_path) as conn:
                conn.execute("""
                    INSERT INTO exit_feedback (
                        trade_id, symbol, strategy, exit_time, exit_price,
                        exit_type, actual_profit_pct, hold_time_minutes,
                        exit_features, ml_prediction_accuracy
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id, symbol, strategy, datetime.now(), exit_price,
                    exit_type, actual_profit_pct, features.time_in_position_minutes,
                    json.dumps(features.__dict__, default=str), prediction_accuracy
                ))
                
            self.logger.debug(f"📝 Recorded exit feedback: {symbol} | {strategy} | {actual_profit_pct:.3f}")
            
        except Exception as e:
            self.logger.error(f"Error recording exit feedback: {e}")
    
    def train_models(self, strategy: str = None):
        """Entrena modelos ML para estrategias"""
        strategies_to_train = [strategy] if strategy else self.strategies
        
        for strat in strategies_to_train:
            try:
                self.logger.info(f"🎯 Training ML exit models for {strat}...")
                
                # Get training data
                training_data = self._get_training_data(strat)
                
                if len(training_data) < 50:
                    self.logger.warning(f"Insufficient training data for {strat}: {len(training_data)} samples")
                    continue
                
                # Train exit classifier
                self._train_exit_classifier(strat, training_data)
                
                # Train profit predictor
                self._train_profit_predictor(strat, training_data)
                
                self.logger.info(f"✅ Models trained for {strat}")
                
            except Exception as e:
                self.logger.error(f"Error training models for {strat}: {e}")
    
    def _get_training_data(self, strategy: str) -> pd.DataFrame:
        """Obtiene datos de entrenamiento desde feedback histórico"""
        # TODO: Implement data extraction from historical trades
        # For now, return empty DataFrame
        return pd.DataFrame()
    
    def _train_exit_classifier(self, strategy: str, data: pd.DataFrame):
        """Entrena clasificador de salidas"""
        # TODO: Implement exit classifier training
        pass
    
    def _train_profit_predictor(self, strategy: str, data: pd.DataFrame):
        """Entrena predictor de beneficios futuros"""
        # TODO: Implement profit predictor training
        pass
    
    def _load_or_create_models(self, strategy: str):
        """Carga modelos existentes o crea nuevos - UPDATED para usar modelos entrenados"""
        # NEW: Try to load from trained models directory structure first
        strategy_model_dir = os.path.join(self.models_dir, "smallcap_exit")  # From our trainer
        
        exit_model_path = os.path.join(strategy_model_dir, "exit_classifier.pkl")
        profit_model_path = os.path.join(strategy_model_dir, "profit_regressor.pkl") 
        scaler_path = os.path.join(strategy_model_dir, "scaler.pkl")
        metadata_path = os.path.join(strategy_model_dir, "metadata.json")
        
        try:
            # Try to load trained models first
            if os.path.exists(exit_model_path) and os.path.exists(profit_model_path):
                self.exit_models[strategy] = joblib.load(exit_model_path)
                self.profit_predictors[strategy] = joblib.load(profit_model_path)
                
                if os.path.exists(scaler_path):
                    self.scalers[strategy] = joblib.load(scaler_path)
                else:
                    self.scalers[strategy] = StandardScaler()
                
                # Log successful loading
                self.logger.info(f"✅ Loaded trained models for {strategy} from {strategy_model_dir}")
                
                # Load and log metadata if available
                if os.path.exists(metadata_path):
                    import json
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    self.logger.info(f"📊 Model trained at: {metadata.get('trained_at', 'Unknown')}")
                
                return  # Successfully loaded trained models
            
            # FALLBACK: Try old format for backwards compatibility
            old_exit_path = os.path.join(self.models_dir, f"{strategy}_exit_classifier.joblib")
            old_profit_path = os.path.join(self.models_dir, f"{strategy}_profit_predictor.joblib")
            old_scaler_path = os.path.join(self.models_dir, f"{strategy}_scaler.joblib")
            
            if os.path.exists(old_exit_path):
                self.exit_models[strategy] = joblib.load(old_exit_path)
            else:
                self.exit_models[strategy] = None
                
            if os.path.exists(old_profit_path):
                self.profit_predictors[strategy] = joblib.load(old_profit_path)
            else:
                self.profit_predictors[strategy] = None
                
            if os.path.exists(old_scaler_path):
                self.scalers[strategy] = joblib.load(old_scaler_path)
            else:
                self.scalers[strategy] = StandardScaler()
            
            # Log what was loaded
            if self.exit_models[strategy] or self.profit_predictors[strategy]:
                self.logger.info(f"✅ Loaded legacy models for {strategy}")
            else:
                self.logger.info(f"⚠️ No trained models found for {strategy}, using heuristic fallback")
                
        except Exception as e:
            self.logger.error(f"Error loading models for {strategy}: {e}")
            self.exit_models[strategy] = None
            self.profit_predictors[strategy] = None
            self.scalers[strategy] = StandardScaler()
    
    def _features_to_vector(self, features: ExitFeatures) -> List[float]:
        """
        Convierte features a vector numérico para ML - UPDATED para coincidir con el entrenamiento
        
        DEBE coincidir EXACTAMENTE con las features del trainer:
        ['current_pnl_pct', 'time_in_position_minutes', 'current_volume_ratio',
         'rsi', 'price_vs_vwap', 'time_of_day', 'price_momentum', 'volume_trend']
        """
        
        # Calculate volume trend (simplified approximation of training logic)
        volume_trend = features.volume_declining_bars * -0.1  # Rough approximation
        
        return [
            features.current_pnl_pct,                    # 0: Most important feature (75.4%)
            features.time_in_position_minutes,           # 1: Time in position 
            features.current_volume_ratio,               # 2: Volume ratio
            features.rsi,                                # 3: RSI
            features.price_vs_vwap,                      # 4: Price vs VWAP (13.1% importance)
            features.time_of_day,                        # 5: Time of day
            features.price_momentum_5min,                # 6: Price momentum
            volume_trend                                 # 7: Volume trend
        ]
    
    def _determine_exit_type(self, features: ExitFeatures, should_exit: bool) -> Tuple[str, List[str]]:
        """Determina tipo de salida y razones"""
        if not should_exit:
            return 'HOLD', ['ML recommends holding position']
        
        reasons = []
        
        if features.current_pnl_pct > 0.10:
            exit_type = 'PROFIT_OPTIMAL'
            reasons.append(f'Optimal profit taking at {features.current_pnl_pct:.1%}')
        elif features.current_pnl_pct < -0.05:
            exit_type = 'STOP_PROTECTION'
            reasons.append(f'Stop loss protection at {features.current_pnl_pct:.1%}')
        elif features.time_in_position_minutes > 180:
            exit_type = 'TIME_DECAY'
            reasons.append(f'Time decay after {features.time_in_position_minutes} minutes')
        elif features.fomo_score > 0.7:
            exit_type = 'FOMO_EXIT'
            reasons.append(f'Market FOMO detected: {features.fomo_score:.2f}')
        else:
            exit_type = 'ML_OPTIMAL'
            reasons.append('ML model recommends exit')
        
        return exit_type, reasons
    
    def _estimate_optimal_hold_time(self, features: ExitFeatures, strategy: str) -> int:
        """Estima tiempo óptimo de holding en minutos"""
        base_hold_time = {
            'catalyst_momentum': 60,
            'gap_go': 45,
            'orb': 90,
            'volume_breakout': 75,
        }.get(strategy, 60)
        
        # Adjust based on current performance
        if features.current_pnl_pct > 0.08:
            return int(base_hold_time * 1.5)  # Hold winners longer
        elif features.current_pnl_pct < 0:
            return int(base_hold_time * 0.7)  # Cut losers faster
        
        return base_hold_time
    
    # Technical calculation helpers
    def _calculate_rsi(self, bars_history: List[MarketData], period: int = 14) -> float:
        """Calculate RSI"""
        if len(bars_history) < period + 1:
            return 50.0
        
        closes = [bar.close for bar in bars_history[-(period+1):]]
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_vwap(self, bars_history: List[MarketData]) -> float:
        """Calculate VWAP"""
        if not bars_history:
            return 0.0
        
        total_volume = 0
        total_price_volume = 0
        
        for bar in bars_history:
            typical_price = (bar.high + bar.low + bar.close) / 3
            total_price_volume += typical_price * bar.volume
            total_volume += bar.volume
        
        return total_price_volume / total_volume if total_volume > 0 else 0.0
    
    def _calculate_price_momentum(self, bars_history: List[MarketData]) -> float:
        """Calculate price momentum"""
        if len(bars_history) < 2:
            return 0.0
        
        first_price = bars_history[0].close
        last_price = bars_history[-1].close
        
        return (last_price - first_price) / first_price if first_price > 0 else 0.0
    
    def _calculate_volume_momentum(self, bars_history: List[MarketData]) -> float:
        """Calculate volume momentum"""
        if len(bars_history) < 5:
            return 0.0
        
        recent_vol = np.mean([bar.volume for bar in bars_history[-3:]])
        older_vol = np.mean([bar.volume for bar in bars_history[-8:-3]])
        
        return (recent_vol - older_vol) / older_vol if older_vol > 0 else 0.0

# Global ML exit engine instance
_global_ml_exit_engine = None

def get_global_ml_exit_engine() -> MLExitEngine:
    """Obtiene la instancia global del ML exit engine"""
    global _global_ml_exit_engine
    if _global_ml_exit_engine is None:
        _global_ml_exit_engine = MLExitEngine()
    return _global_ml_exit_engine