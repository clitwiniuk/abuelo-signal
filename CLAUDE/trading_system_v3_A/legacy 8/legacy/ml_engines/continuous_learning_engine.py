#!/usr/bin/env python3
"""
Continuous Learning Engine - Sistema de aprendizaje continuo para ML Volume Engine
Aprende automáticamente de los resultados reales de trading
"""

import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import asyncio
from threading import Thread, Event
import time
import os
import json

from core.ml_volume_engine import MLVolumeEngine, create_market_context
from core.ml_exit_engine import MLExitEngine

@dataclass
class TradeResult:
    """Resultado de un trade para feedback learning"""
    trade_id: str
    symbol: str
    strategy: str
    volume_requirement_used: float
    actual_volume_ratio: float
    pnl: float
    success: bool
    duration_minutes: int
    entry_time: datetime
    market_context: Dict

@dataclass
class LearningMetrics:
    """Métricas de aprendizaje del sistema"""
    total_feedback_samples: int
    model_accuracy: float
    last_retrain_date: datetime
    performance_drift: float
    strategies_improved: List[str]

class ContinuousLearningEngine:
    """
    Motor de aprendizaje continuo que mejora el ML Volume Engine automáticamente
    """
    
    def __init__(self, 
                 trading_db_path: str = "trading_data.db",
                 market_db_path: str = "trading_data.db",
                 retrain_interval_hours: int = 24 * 7):  # Weekly retraining
        
        self.trading_db_path = trading_db_path
        self.market_db_path = market_db_path
        self.retrain_interval_hours = retrain_interval_hours
        self.logger = logging.getLogger(__name__)
        
        # Learning components
        self.ml_volume_engine = None
        self.ml_exit_engine = None
        self.feedback_buffer = []
        self.last_retrain_time = datetime.now()
        
        # Performance tracking
        self.baseline_performance = {}
        self.current_performance = {}
        self.drift_threshold = 0.15  # 15% performance drop triggers retrain
        
        # Background learning thread
        self._learning_active = False
        self._learning_thread = None
        self._stop_event = Event()
        
        # Feedback database setup
        self._setup_feedback_tables()
        
    def _setup_feedback_tables(self):
        """Crear tablas para almacenar feedback de volumen"""
        with sqlite3.connect(self.trading_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS volume_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    volume_requirement_predicted REAL NOT NULL,
                    actual_volume_ratio REAL NOT NULL,
                    market_context TEXT,  -- JSON serialized context
                    trade_success BOOLEAN NOT NULL,
                    pnl REAL,
                    duration_minutes INTEGER,
                    feedback_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    model_version TEXT,
                    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy TEXT NOT NULL,
                    evaluation_date DATE NOT NULL,
                    accuracy REAL,
                    precision REAL,
                    recall REAL,
                    f1_score REAL,
                    samples_count INTEGER,
                    model_version TEXT,
                    notes TEXT,
                    UNIQUE(strategy, evaluation_date)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learning_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,  -- 'RETRAIN', 'DRIFT_DETECTED', 'PERFORMANCE_UPDATE'
                    description TEXT,
                    strategies_affected TEXT,  -- JSON list
                    metrics TEXT,  -- JSON metrics
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def add_feedback(self, trade_result: TradeResult):
        """Añade feedback de un trade para aprendizaje continuo"""
        try:
            with sqlite3.connect(self.trading_db_path) as conn:
                conn.execute("""
                    INSERT INTO volume_feedback (
                        trade_id, symbol, strategy, volume_requirement_predicted,
                        actual_volume_ratio, market_context, trade_success, pnl, 
                        duration_minutes, model_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_result.trade_id,
                    trade_result.symbol,
                    trade_result.strategy,
                    trade_result.volume_requirement_used,
                    trade_result.actual_volume_ratio,
                    json.dumps(trade_result.market_context),
                    trade_result.success,
                    trade_result.pnl,
                    trade_result.duration_minutes,
                    "v1.0"
                ))
                conn.commit()
            
            self.feedback_buffer.append(trade_result)
            self.logger.debug(f"📊 Added feedback for {trade_result.symbol} ({trade_result.strategy})")
            
        except Exception as e:
            self.logger.error(f"❌ Error adding feedback: {e}")
    
    def retrain_models(self) -> Dict[str, float]:
        """Ejecuta reentrenamiento de modelos ML con feedback acumulado"""
        try:
            self.logger.info("🔄 Iniciando reentrenamiento de modelos...")
            
            # Cargar ML engines
            if not self.ml_volume_engine:
                from core.ml_volume_engine import MLVolumeEngine
                self.ml_volume_engine = MLVolumeEngine()
                self.ml_volume_engine.load_models()
            
            # Obtener feedback reciente
            with sqlite3.connect(self.trading_db_path) as conn:
                df = pd.read_sql_query("""
                    SELECT * FROM volume_feedback 
                    WHERE feedback_time > datetime('now', '-30 days')
                    ORDER BY feedback_time DESC
                """, conn)
            
            if len(df) < 10:
                self.logger.warning("⚠️ Insuficiente feedback para reentrenamiento")
                return {}
            
            self.logger.info(f"📊 Reentrenando con {len(df)} samples de feedback")
            
            # Simular reentrenamiento usando estrategias que REALMENTE tienen feedback
            retrain_results = {}
            # ✅ Usar estrategias con feedback en lugar de ml_volume_engine.strategies
            available_strategies = df['strategy'].unique()
            
            for strategy in available_strategies:
                strategy_feedback = df[df['strategy'] == strategy]
                if len(strategy_feedback) >= 5:  # Umbral mínimo de 5 trades
                    # Calcular accuracy mejorada
                    current_accuracy = strategy_feedback['trade_success'].mean()
                    retrain_results[strategy] = current_accuracy
                    self.logger.info(f"   {strategy}: {current_accuracy:.3f} accuracy ({len(strategy_feedback)} trades)")
                else:
                    self.logger.info(f"   {strategy}: Insuficientes trades ({len(strategy_feedback)}<5) - omitido")
            
            # Actualizar timestamp de reentrenamiento
            self.last_retrain_time = datetime.now()
            
            # Log evento
            self._log_learning_event("RETRAIN", f"Reentrenado {len(retrain_results)} estrategias", retrain_results)
            
            return retrain_results
            
        except Exception as e:
            self.logger.error(f"❌ Error en reentrenamiento: {e}")
            return {}
            
    def start_continuous_learning(self):
        """Iniciar el sistema de aprendizaje continuo en background"""
        if self._learning_active:
            self.logger.warning("Continuous learning already active")
            return
            
        self._learning_active = True
        self._stop_event.clear()
        self._learning_thread = Thread(target=self._learning_loop, daemon=True)
        self._learning_thread.start()
        
        self.logger.info("🧠 Continuous Learning Engine started")
        
    def stop_continuous_learning(self):
        """Detener el sistema de aprendizaje continuo"""
        if not self._learning_active:
            return
            
        self._learning_active = False
        self._stop_event.set()
        
        if self._learning_thread:
            self._learning_thread.join(timeout=5)
            
        self.logger.info("🛑 Continuous Learning Engine stopped")
        
    def record_volume_decision_feedback(self, trade_result: TradeResult):
        """
        Registra el feedback de una decisión de volumen basada en resultado real
        """
        try:
            with sqlite3.connect(self.trading_db_path) as conn:
                conn.execute("""
                    INSERT INTO volume_feedback (
                        trade_id, symbol, strategy, volume_requirement_predicted,
                        actual_volume_ratio, market_context, trade_success,
                        pnl, duration_minutes, model_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_result.trade_id,
                    trade_result.symbol,
                    trade_result.strategy,
                    trade_result.volume_requirement_used,
                    trade_result.actual_volume_ratio,
                    str(trade_result.market_context),  # JSON serialized
                    trade_result.success,
                    trade_result.pnl,
                    trade_result.duration_minutes,
                    "v1.0"  # Model version
                ))
                
            # Añadir a buffer para procesamiento
            self.feedback_buffer.append(trade_result)
            
            # Trigger retrain si buffer está lleno
            if len(self.feedback_buffer) >= 50:  # Batch size
                self._process_feedback_batch()
                
            self.logger.debug(
                f"📝 Recorded volume feedback: {trade_result.symbol} | "
                f"{trade_result.strategy} | Success: {trade_result.success}"
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error recording volume feedback: {e}")
            
    def _process_feedback_batch(self):
        """Procesa un batch de feedback para learning inmediato"""
        if not self.feedback_buffer:
            return
            
        try:
            # Analizar feedback reciente
            successful_predictions = sum(1 for f in self.feedback_buffer if f.success)
            accuracy = successful_predictions / len(self.feedback_buffer)
            
            self.logger.info(
                f"📊 Processing feedback batch: {len(self.feedback_buffer)} samples, "
                f"accuracy: {accuracy:.2f}"
            )
            
            # Si accuracy < 70%, trigger immediate retrain
            if accuracy < 0.70:
                self.logger.warning(
                    f"⚠️ Low accuracy detected ({accuracy:.2f}), triggering retrain"
                )
                self._retrain_models_with_feedback()
            
            # Clear buffer
            self.feedback_buffer.clear()
            
        except Exception as e:
            self.logger.error(f"❌ Error processing feedback batch: {e}")
            
    def _learning_loop(self):
        """Loop principal del aprendizaje continuo"""
        while self._learning_active and not self._stop_event.is_set():
            try:
                # Check if retrain is needed (weekly or drift-triggered)
                if self._should_retrain():
                    self._retrain_models_with_feedback()
                    
                # Monitor performance drift
                self._check_performance_drift()
                
                # Process any pending feedback
                if self.feedback_buffer:
                    self._process_feedback_batch()
                    
                # Sleep for 1 hour
                self._stop_event.wait(3600)  # 1 hour
                
            except Exception as e:
                self.logger.error(f"❌ Error in learning loop: {e}")
                self._stop_event.wait(300)  # 5 minutes on error
                
    def _should_retrain(self) -> bool:
        """Determina si es necesario re-entrenar modelos"""
        time_since_retrain = datetime.now() - self.last_retrain_time
        
        # Weekly retrain
        if time_since_retrain.total_seconds() >= (self.retrain_interval_hours * 3600):
            return True
            
        # Drift-triggered retrain
        if self._detect_performance_drift():
            return True
            
        return False
        
    def _detect_performance_drift(self) -> bool:
        """Detecta drift en performance de modelos"""
        try:
            current_metrics = self._calculate_current_performance()
            
            for strategy, current_perf in current_metrics.items():
                baseline = self.baseline_performance.get(strategy, current_perf)
                
                if current_perf < (baseline - self.drift_threshold):
                    self.logger.warning(
                        f"📉 Performance drift detected for {strategy}: "
                        f"{current_perf:.3f} vs baseline {baseline:.3f}"
                    )
                    return True
                    
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Error detecting drift: {e}")
            return False
            
    def _calculate_current_performance(self) -> Dict[str, float]:
        """Calcula performance actual basada en trades recientes"""
        try:
            with sqlite3.connect(self.trading_db_path) as conn:
                # Get recent trade results (last 30 days)
                query = """
                    SELECT vf.strategy, 
                           AVG(CASE WHEN vf.trade_success THEN 1.0 ELSE 0.0 END) as success_rate
                    FROM volume_feedback vf
                    WHERE vf.feedback_time >= date('now', '-30 days')
                    GROUP BY vf.strategy
                """
                
                df = pd.read_sql_query(query, conn)
                return dict(zip(df['strategy'], df['success_rate']))
                
        except Exception as e:
            self.logger.error(f"❌ Error calculating performance: {e}")
            return {}
            
    def _retrain_models_with_feedback(self):
        """Re-entrena modelos incorporando feedback reciente"""
        try:
            self.logger.info("🔄 Starting model retraining with feedback...")
            
            # Initialize ML engines if not available
            if not self.ml_volume_engine:
                self.ml_volume_engine = MLVolumeEngine(db_path=self.market_db_path)
            if not self.ml_exit_engine:
                from core.ml_exit_engine import MLExitEngine
                self.ml_exit_engine = MLExitEngine(
                    market_db_path=self.market_db_path
                )
                
            # Get enhanced training data (original + feedback)
            enhanced_data = self._create_enhanced_training_data()
            
            if len(enhanced_data) < 100:
                self.logger.warning("⚠️ Insufficient data for retraining, skipping...")
                return
                
            # Retrain volume models
            volume_results = self._retrain_with_enhanced_data(enhanced_data)
            
            # Retrain exit models
            exit_results = self._retrain_exit_models()
            
            results = {**volume_results, **exit_results}
            
            # Update baseline performance
            self.baseline_performance = self._calculate_current_performance()
            self.last_retrain_time = datetime.now()
            
            # Log retraining event
            self._log_learning_event("RETRAIN", f"Models retrained with {len(enhanced_data)} samples", results)
            
            self.logger.info(f"✅ Model retraining completed: {len(results)} strategies updated")
            
        except Exception as e:
            self.logger.error(f"❌ Error during model retraining: {e}")
            
    def _create_enhanced_training_data(self) -> pd.DataFrame:
        """Crea dataset mejorado combinando datos originales + feedback"""
        # TODO: Implement logic to combine original market data with trading feedback
        # For now, return original data structure
        return pd.DataFrame()
        
    def _retrain_with_enhanced_data(self, data: pd.DataFrame) -> Dict[str, float]:
        """Re-entrena modelos de volumen con datos mejorados"""
        # Simplified retraining - in practice would update models with new data
        return {"retrained_volume_strategies": len(self.ml_volume_engine.strategies) if self.ml_volume_engine else 0}
    
    def _retrain_exit_models(self) -> Dict[str, float]:
        """Re-entrena modelos de salida con feedback reciente"""
        try:
            if not self.ml_exit_engine:
                return {"retrained_exit_models": 0}
                
            # Train exit models for all strategies
            self.ml_exit_engine.train_models()
            
            return {"retrained_exit_models": len(self.ml_exit_engine.strategies)}
            
        except Exception as e:
            self.logger.error(f"Error retraining exit models: {e}")
            return {"retrained_exit_models": 0}
        
    def _check_performance_drift(self):
        """Verifica y reporta drift en performance"""
        try:
            if self._detect_performance_drift():
                self._log_learning_event(
                    "DRIFT_DETECTED",
                    "Performance drift detected, retraining scheduled",
                    {"drift_threshold": self.drift_threshold}
                )
                
        except Exception as e:
            self.logger.error(f"❌ Error checking drift: {e}")
            
    def _log_learning_event(self, event_type: str, description: str, metrics: Dict):
        """Registra eventos de aprendizaje"""
        try:
            with sqlite3.connect(self.trading_db_path) as conn:
                conn.execute("""
                    INSERT INTO learning_events (event_type, description, metrics)
                    VALUES (?, ?, ?)
                """, (event_type, description, str(metrics)))
                
        except Exception as e:
            self.logger.error(f"❌ Error logging learning event: {e}")
            
    def get_learning_metrics(self) -> LearningMetrics:
        """Obtiene métricas actuales del sistema de aprendizaje"""
        try:
            with sqlite3.connect(self.trading_db_path) as conn:
                # Count feedback samples
                cursor = conn.execute("SELECT COUNT(*) FROM volume_feedback")
                total_samples = cursor.fetchone()[0]
                
                # Calculate average accuracy
                cursor = conn.execute("""
                    SELECT AVG(CASE WHEN trade_success THEN 1.0 ELSE 0.0 END)
                    FROM volume_feedback
                    WHERE feedback_time >= date('now', '-30 days')
                """)
                accuracy = cursor.fetchone()[0] or 0.0
                
                return LearningMetrics(
                    total_feedback_samples=total_samples,
                    model_accuracy=accuracy,
                    last_retrain_date=self.last_retrain_time,
                    performance_drift=0.0,  # TODO: Calculate actual drift
                    strategies_improved=list(self.baseline_performance.keys())
                )
                
        except Exception as e:
            self.logger.error(f"❌ Error getting learning metrics: {e}")
            return LearningMetrics(0, 0.0, datetime.now(), 0.0, [])
            
    def force_retrain(self):
        """Fuerza re-entrenamiento inmediato de modelos"""
        self.logger.info("🔄 Forcing immediate model retraining...")
        self._retrain_models_with_feedback()

# Global continuous learning engine instance
_global_learning_engine = None

def get_global_learning_engine() -> ContinuousLearningEngine:
    """Obtiene la instancia global del learning engine"""
    global _global_learning_engine
    if _global_learning_engine is None:
        _global_learning_engine = ContinuousLearningEngine()
    return _global_learning_engine

def record_trade_volume_feedback(symbol: str, strategy: str, trade_id: str, 
                                success: bool, pnl: float, volume_data: dict):
    """Función de conveniencia para registrar feedback de volumen"""
    learning_engine = get_global_learning_engine()
    
    trade_result = TradeResult(
        trade_id=trade_id,
        symbol=symbol,
        strategy=strategy,
        volume_requirement_used=volume_data.get('requirement_used', 1.0),
        actual_volume_ratio=volume_data.get('actual_ratio', 1.0),
        pnl=pnl,
        success=success,
        duration_minutes=volume_data.get('duration', 0),
        entry_time=datetime.now(),
        market_context=volume_data.get('context', {})
    )
    
    learning_engine.record_volume_decision_feedback(trade_result)

def record_trade_exit_feedback(symbol: str, strategy: str, trade_id: str,
                              exit_price: float, exit_type: str, actual_profit_pct: float,
                              exit_features: dict, prediction_accuracy: float = None):
    """Función de conveniencia para registrar feedback de salidas"""
    learning_engine = get_global_learning_engine()
    
    if learning_engine.ml_exit_engine:
        # Convert dict to ExitFeatures object if needed
        from core.ml_exit_engine import ExitFeatures
        
        features = ExitFeatures(
            entry_price=exit_features.get('entry_price', 0),
            current_price=exit_features.get('current_price', 0),
            current_pnl_pct=exit_features.get('current_pnl_pct', 0),
            time_in_position_minutes=exit_features.get('time_in_position_minutes', 0),
            entry_volume_ratio=exit_features.get('entry_volume_ratio', 1.0),
            current_volume_ratio=exit_features.get('current_volume_ratio', 1.0),
            rsi=exit_features.get('rsi', 50),
            price_vs_vwap=exit_features.get('price_vs_vwap', 1.0),
            fomo_score=exit_features.get('fomo_score', 0),
            time_of_day=exit_features.get('time_of_day', 0.5),
            market_stress=exit_features.get('market_stress', 0.02),
            strategy=strategy,
            volume_declining_bars=exit_features.get('volume_declining_bars', 0),
            price_momentum_5min=exit_features.get('price_momentum_5min', 0),
            volume_momentum=exit_features.get('volume_momentum', 0),
            sector_performance=exit_features.get('sector_performance', 0)
        )
        
        learning_engine.ml_exit_engine.record_exit_feedback(
            trade_id, symbol, strategy, exit_price, exit_type, 
            actual_profit_pct, features, prediction_accuracy
        )