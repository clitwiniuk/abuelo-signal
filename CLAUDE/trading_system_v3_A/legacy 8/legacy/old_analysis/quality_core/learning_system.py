"""
Learning System for Quality Trading
==================================

Sistema de aprendizaje automático que:
1. Trackea predicciones vs resultados reales
2. Ajusta pesos de factores basado en performance
3. Optimiza umbrales dinámicamente
4. Aprende sin sesgos usando solo datos históricos

NO usa look-ahead bias - solo aprende DESPUÉS de conocer resultados reales
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import json
import yfinance as yf
from pathlib import Path

logger = logging.getLogger(__name__)

class PredictionTracker:
    """
    Sistema de tracking de predicciones y resultados reales
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializar base de datos de learning"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de predicciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ticker TEXT NOT NULL,
                prediction_time TEXT NOT NULL,
                
                -- Inputs de la predicción
                current_price REAL NOT NULL,
                volume INTEGER NOT NULL,
                premarket_gap_pct REAL NOT NULL,
                
                -- Factores analizados
                consolidation_score REAL NOT NULL,
                timing_score REAL NOT NULL,
                volume_score REAL NOT NULL,
                news_score REAL NOT NULL,
                
                -- Predicción realizada
                predicted_grade TEXT NOT NULL,
                predicted_score INTEGER NOT NULL,
                recommendation TEXT NOT NULL,
                
                -- Pesos usados en la predicción
                weight_consolidation REAL NOT NULL,
                weight_timing REAL NOT NULL,
                weight_volume REAL NOT NULL,
                weight_news REAL NOT NULL,
                
                -- Estado del resultado
                result_tracked BOOLEAN DEFAULT FALSE,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de resultados reales
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prediction_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                
                -- Precios de seguimiento
                price_30min REAL,
                price_1h REAL,
                price_2h REAL,
                price_eod REAL,
                
                -- Performance calculada
                return_30min REAL,
                return_1h REAL,
                return_2h REAL,
                return_eod REAL,
                
                -- Métricas de éxito
                max_gain_pct REAL,
                max_loss_pct REAL,
                final_result TEXT,  -- 'win', 'loss', 'neutral'
                
                -- Timestamp de resultado
                result_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (prediction_id) REFERENCES predictions (id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def log_prediction(self, ticker: str, analysis_result: Dict, weights: Dict) -> int:
        """
        Guardar una predicción para tracking futuro
        
        Returns:
            int: ID de la predicción guardada
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        prediction_data = (
            datetime.now().isoformat(),
            ticker,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            analysis_result.get('price', 0),
            analysis_result.get('volume', 0),
            analysis_result.get('premarket_gap_pct', 0),
            analysis_result.get('consolidation_score', 0),
            analysis_result.get('timing_score', 0),
            analysis_result.get('volume_score', 0),
            analysis_result.get('news_score', 0),
            analysis_result.get('grade', 'C'),
            analysis_result.get('overall_score', 50),
            analysis_result.get('recommendation', 'ANALYZE'),
            weights.get('consolidation', 0.30),
            weights.get('timing', 0.25),
            weights.get('volume', 0.25),
            weights.get('news', 0.20)
        )
        
        cursor.execute("""
            INSERT INTO predictions (
                timestamp, ticker, prediction_time, current_price, volume, premarket_gap_pct,
                consolidation_score, timing_score, volume_score, news_score,
                predicted_grade, predicted_score, recommendation,
                weight_consolidation, weight_timing, weight_volume, weight_news
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, prediction_data)
        
        prediction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Prediction logged for {ticker} with ID {prediction_id}")
        return prediction_id
    
    def update_result(self, prediction_id: int, ticker: str, current_price: float) -> bool:
        """
        Actualizar el resultado real de una predicción
        """
        try:
            # Obtener datos de precios actuales
            stock = yf.Ticker(ticker)
            intraday = stock.history(period="1d", interval="1m")
            
            if intraday.empty:
                logger.warning(f"No intraday data available for {ticker}")
                return False
            
            # Obtener predicción original
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT current_price, prediction_time FROM predictions 
                WHERE id = ? AND ticker = ?
            """, (prediction_id, ticker))
            
            result = cursor.fetchone()
            if not result:
                logger.error(f"Prediction {prediction_id} not found")
                return False
            
            original_price, prediction_time = result
            prediction_dt = datetime.fromisoformat(prediction_time)
            
            # Calcular performance en diferentes timeframes
            current_time = datetime.now()
            time_diff = (current_time - prediction_dt).total_seconds() / 60  # minutos
            
            # Obtener precios en diferentes momentos (aproximados)
            price_30min = None
            price_1h = None
            price_2h = None
            price_eod = current_price
            
            # Si tenemos datos intraday, buscar precios específicos
            if len(intraday) > 30:  # Suficientes datos
                idx_30min = min(30, len(intraday) - 1)
                idx_1h = min(60, len(intraday) - 1)
                idx_2h = min(120, len(intraday) - 1)
                
                price_30min = intraday.iloc[idx_30min]['Close']
                price_1h = intraday.iloc[idx_1h]['Close']
                price_2h = intraday.iloc[idx_2h]['Close']
            
            # Calcular returns
            return_30min = ((price_30min - original_price) / original_price * 100) if price_30min else None
            return_1h = ((price_1h - original_price) / original_price * 100) if price_1h else None
            return_2h = ((price_2h - original_price) / original_price * 100) if price_2h else None
            return_eod = (price_eod - original_price) / original_price * 100
            
            # Calcular max gain/loss
            if len(intraday) > 0:
                highs = intraday['High'].values
                lows = intraday['Low'].values
                max_gain_pct = (max(highs) - original_price) / original_price * 100
                max_loss_pct = (min(lows) - original_price) / original_price * 100
            else:
                max_gain_pct = max(0, return_eod)
                max_loss_pct = min(0, return_eod)
            
            # Determinar resultado final
            if return_eod >= 10:
                final_result = 'win'
            elif return_eod <= -5:
                final_result = 'loss'
            else:
                final_result = 'neutral'
            
            # Guardar resultado
            cursor.execute("""
                INSERT INTO prediction_results (
                    prediction_id, ticker, price_30min, price_1h, price_2h, price_eod,
                    return_30min, return_1h, return_2h, return_eod,
                    max_gain_pct, max_loss_pct, final_result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction_id, ticker, price_30min, price_1h, price_2h, price_eod,
                return_30min, return_1h, return_2h, return_eod,
                max_gain_pct, max_loss_pct, final_result
            ))
            
            # Marcar predicción como resultado trackeado
            cursor.execute("""
                UPDATE predictions SET result_tracked = TRUE WHERE id = ?
            """, (prediction_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Result updated for prediction {prediction_id}: {final_result} ({return_eod:.1f}%)")
            return True
            
        except Exception as e:
            logger.error(f"Error updating result for prediction {prediction_id}: {e}")
            return False
    
    def get_untracked_predictions(self) -> List[Dict]:
        """Obtener predicciones que aún no tienen resultado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Obtener predicciones de más de 2 horas que no han sido trackeadas
        cutoff_time = (datetime.now() - timedelta(hours=2)).isoformat()
        
        cursor.execute("""
            SELECT id, ticker, current_price, prediction_time 
            FROM predictions 
            WHERE result_tracked = FALSE 
            AND timestamp < ?
            ORDER BY timestamp ASC
            LIMIT 50
        """, (cutoff_time,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'prediction_id': row[0],
                'ticker': row[1],
                'original_price': row[2],
                'prediction_time': row[3]
            })
        
        conn.close()
        return results


class WeightLearningSystem:
    """
    Sistema de aprendizaje de pesos basado en performance histórica
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.tracker = PredictionTracker(db_path)
        
        # Pesos iniciales (baseline)
        self.current_weights = {
            'consolidation': 0.30,
            'timing': 0.25,
            'volume': 0.25,
            'news': 0.20
        }
        
        # Configuración de aprendizaje
        self.learning_rate = 0.1
        self.min_samples_for_learning = 20
        self.weight_bounds = (0.05, 0.50)  # Límites de pesos
    
    def get_learning_data(self) -> pd.DataFrame:
        """Obtener datos para aprendizaje"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
        SELECT 
            p.ticker,
            p.consolidation_score,
            p.timing_score,
            p.volume_score,
            p.news_score,
            p.predicted_grade,
            p.predicted_score,
            p.weight_consolidation,
            p.weight_timing,
            p.weight_volume,
            p.weight_news,
            r.return_eod,
            r.final_result,
            r.max_gain_pct
        FROM predictions p
        JOIN prediction_results r ON p.id = r.prediction_id
        WHERE p.result_tracked = TRUE
        ORDER BY p.timestamp DESC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    
    def calculate_prediction_accuracy(self, data: pd.DataFrame) -> Dict:
        """Calcular métricas de precisión de predicciones"""
        if len(data) == 0:
            return {'accuracy': 0, 'precision': 0, 'win_rate': 0}
        
        # Accuracy: ¿Las predicciones A+/A realmente ganan?
        high_grade_predictions = data[data['predicted_grade'].isin(['A+', 'A'])]
        if len(high_grade_predictions) > 0:
            wins = len(high_grade_predictions[high_grade_predictions['final_result'] == 'win'])
            accuracy = wins / len(high_grade_predictions)
        else:
            accuracy = 0
        
        # Win rate general
        total_wins = len(data[data['final_result'] == 'win'])
        win_rate = total_wins / len(data)
        
        # Precision por grade
        precision_by_grade = {}
        for grade in ['A+', 'A', 'A-', 'B+', 'B', 'C']:
            grade_data = data[data['predicted_grade'] == grade]
            if len(grade_data) > 0:
                grade_wins = len(grade_data[grade_data['final_result'] == 'win'])
                precision_by_grade[grade] = grade_wins / len(grade_data)
        
        return {
            'accuracy': accuracy,
            'win_rate': win_rate,
            'precision_by_grade': precision_by_grade,
            'total_predictions': len(data)
        }
    
    def analyze_factor_importance(self, data: pd.DataFrame) -> Dict:
        """
        Analizar qué factores son más importantes para predecir éxito
        """
        if len(data) < self.min_samples_for_learning:
            return {'insufficient_data': True}
        
        # Correlación entre factores y éxito
        factor_columns = ['consolidation_score', 'timing_score', 'volume_score', 'news_score']
        
        # Crear variable de éxito binaria
        data['success'] = (data['final_result'] == 'win').astype(int)
        
        correlations = {}
        for factor in factor_columns:
            if factor in data.columns:
                corr = data[factor].corr(data['success'])
                correlations[factor.replace('_score', '')] = corr if not pd.isna(corr) else 0
        
        # Analizar performance por cuartiles de cada factor
        factor_performance = {}
        for factor in factor_columns:
            if factor in data.columns and len(data) >= 20:
                # Dividir en cuartiles
                quartiles = pd.qcut(data[factor], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'])
                perf_by_quartile = data.groupby(quartiles)['success'].mean()
                factor_performance[factor.replace('_score', '')] = perf_by_quartile.to_dict()
        
        return {
            'correlations': correlations,
            'factor_performance': factor_performance,
            'insufficient_data': False
        }
    
    def optimize_weights(self, data: pd.DataFrame) -> Dict:
        """
        Optimizar pesos basado en datos históricos usando gradient descent simple
        """
        if len(data) < self.min_samples_for_learning:
            logger.info(f"Insufficient data for learning: {len(data)} < {self.min_samples_for_learning}")
            return self.current_weights
        
        # Analizar importancia de factores
        importance = self.analyze_factor_importance(data)
        
        if importance.get('insufficient_data'):
            return self.current_weights
        
        correlations = importance.get('correlations', {})
        
        # Calcular nuevos pesos basados en correlaciones
        total_correlation = sum(abs(corr) for corr in correlations.values())
        
        if total_correlation == 0:
            logger.warning("No correlation found, keeping current weights")
            return self.current_weights
        
        new_weights = {}
        for factor, corr in correlations.items():
            # Peso proporcional a correlación absoluta
            new_weight = abs(corr) / total_correlation
            
            # Aplicar learning rate para cambio gradual
            current_weight = self.current_weights.get(factor, 0.25)
            updated_weight = current_weight + self.learning_rate * (new_weight - current_weight)
            
            # Aplicar límites
            updated_weight = max(self.weight_bounds[0], min(self.weight_bounds[1], updated_weight))
            new_weights[factor] = updated_weight
        
        # Normalizar para que sumen 1
        total_weight = sum(new_weights.values())
        if total_weight > 0:
            for factor in new_weights:
                new_weights[factor] /= total_weight
        
        logger.info(f"Weight optimization: {self.current_weights} -> {new_weights}")
        return new_weights
    
    def update_weights(self) -> Dict:
        """
        Actualizar pesos basado en data más reciente
        """
        data = self.get_learning_data()
        
        if len(data) < self.min_samples_for_learning:
            logger.info(f"Not enough data for weight update: {len(data)} samples")
            return {
                'updated': False,
                'reason': 'insufficient_data',
                'samples': len(data),
                'weights': self.current_weights
            }
        
        # Calcular métricas actuales
        accuracy_metrics = self.calculate_prediction_accuracy(data)
        
        # Optimizar pesos
        new_weights = self.optimize_weights(data)
        
        # Evaluar si los nuevos pesos son mejores
        # (En implementación real, harías backtesting)
        weight_change = sum(abs(new_weights[k] - self.current_weights[k]) for k in new_weights)
        
        if weight_change > 0.05:  # Solo actualizar si hay cambio significativo
            old_weights = self.current_weights.copy()
            self.current_weights = new_weights
            
            logger.info(f"Weights updated: {old_weights} -> {new_weights}")
            
            return {
                'updated': True,
                'old_weights': old_weights,
                'new_weights': new_weights,
                'accuracy_metrics': accuracy_metrics,
                'samples': len(data)
            }
        else:
            return {
                'updated': False,
                'reason': 'insufficient_change',
                'weight_change': weight_change,
                'weights': self.current_weights,
                'accuracy_metrics': accuracy_metrics
            }
    
    def get_learning_stats(self) -> Dict:
        """Obtener estadísticas del sistema de aprendizaje"""
        data = self.get_learning_data()
        
        if len(data) == 0:
            return {
                'total_predictions': 0,
                'accuracy_metrics': {'accuracy': 0, 'win_rate': 0, 'precision_by_grade': {}},
                'factor_importance': {'insufficient_data': True},
                'current_weights': self.current_weights,
                'learning_enabled': False
            }
        
        accuracy_metrics = self.calculate_prediction_accuracy(data)
        importance = self.analyze_factor_importance(data)
        
        return {
            'total_predictions': len(data),
            'accuracy_metrics': accuracy_metrics,
            'factor_importance': importance,
            'current_weights': self.current_weights,
            'learning_enabled': len(data) >= self.min_samples_for_learning
        }


class AutoLearningSystem:
    """
    Sistema automático que combina tracking y learning
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.tracker = PredictionTracker(db_path)
        self.learner = WeightLearningSystem(db_path)
    
    def log_and_learn(self, ticker: str, analysis_result: Dict) -> Tuple[int, Dict]:
        """
        Loggear predicción y obtener pesos actualizados para usar
        """
        # Usar pesos actuales del learner
        weights = self.learner.current_weights
        
        # Loggear predicción
        prediction_id = self.tracker.log_prediction(ticker, analysis_result, weights)
        
        return prediction_id, weights
    
    def update_results_and_learn(self) -> Dict:
        """
        Actualizar resultados pendientes y ejecutar aprendizaje
        """
        # Obtener predicciones pendientes
        untracked = self.tracker.get_untracked_predictions()
        
        results = {
            'updated_results': 0,
            'failed_updates': 0,
            'learning_update': None
        }
        
        # Actualizar resultados
        for pred in untracked:
            try:
                # Obtener precio actual
                stock = yf.Ticker(pred['ticker'])
                current_data = stock.history(period="1d")
                
                if not current_data.empty:
                    current_price = current_data['Close'].iloc[-1]
                    success = self.tracker.update_result(
                        pred['prediction_id'], 
                        pred['ticker'], 
                        current_price
                    )
                    
                    if success:
                        results['updated_results'] += 1
                    else:
                        results['failed_updates'] += 1
                
            except Exception as e:
                logger.error(f"Failed to update result for {pred['ticker']}: {e}")
                results['failed_updates'] += 1
        
        # Ejecutar aprendizaje si hay suficientes datos
        if results['updated_results'] > 0:
            learning_result = self.learner.update_weights()
            results['learning_update'] = learning_result
        
        return results
    
    def get_current_weights(self) -> Dict:
        """Obtener pesos actuales optimizados"""
        return self.learner.current_weights
    
    def get_system_stats(self) -> Dict:
        """Obtener estadísticas completas del sistema"""
        return self.learner.get_learning_stats()


# Función de integración para el analyzer existente
def get_learned_weights(db_path: str) -> Dict:
    """
    Función helper para obtener pesos aprendidos
    """
    try:
        learning_system = WeightLearningSystem(db_path)
        return learning_system.current_weights
    except Exception as e:
        logger.error(f"Error getting learned weights: {e}")
        # Fallback a pesos por defecto
        return {
            'consolidation': 0.30,
            'timing': 0.25,
            'volume': 0.25,
            'news': 0.20
        }


if __name__ == "__main__":
    # Test del sistema
    db_path = "learning_test.db"
    
    # Crear sistema
    auto_system = AutoLearningSystem(db_path)
    
    # Simular predicción
    test_analysis = {
        'ticker': 'TEST',
        'price': 5.0,
        'volume': 1000000,
        'premarket_gap_pct': 20.0,
        'consolidation_score': 80,
        'timing_score': 60,
        'volume_score': 70,
        'news_score': 50,
        'grade': 'A',
        'overall_score': 75,
        'recommendation': 'BUY'
    }
    
    # Log predicción
    pred_id, weights = auto_system.log_and_learn('TEST', test_analysis)
    print(f"Prediction logged with ID: {pred_id}")
    print(f"Current weights: {weights}")
    
    # Ver stats
    stats = auto_system.get_system_stats()
    print(f"System stats: {stats}")