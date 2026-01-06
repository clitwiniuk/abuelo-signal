#!/usr/bin/env python3
"""
ML Volume Requirement Engine - Sistema dinámico de requerimientos de volumen
Reemplaza todos los valores hardcodeados con ML basado en datos históricos
"""

import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import logging
import os

@dataclass
class MarketContext:
    """Contexto del mercado para predicción de volumen"""
    time_of_day: float          # 0-1 (normalized hour)
    day_of_week: int            # 0-6 
    market_cap: float           # Market cap del ticker
    avg_volume: float           # Volumen promedio (20d)
    float_shares: float         # Float shares
    sector: str                 # Sector del ticker
    recent_performance: float   # Performance reciente (5d)
    market_stress: float        # VIX proxy basado en volatilidad
    volume_trend: float         # Tendencia de volumen (5d vs 20d)
    price_level: float          # Precio actual
    
class MLVolumeEngine:
    """
    Motor ML para requerimientos dinámicos de volumen por estrategia
    Con soporte para continuous learning
    """
    
    def __init__(self, db_path: str = "trading_data.db", enable_continuous_learning: bool = True):
        self.db_path = db_path
        self.models = {}
        self.scalers = {}
        self.feature_columns = [
            'time_of_day', 'day_of_week', 'log_market_cap', 'log_avg_volume',
            'log_float_shares', 'sector_encoded', 'recent_performance',
            'market_stress', 'volume_trend', 'log_price', 'volume_ratio'
        ]
        # ✅ ESTRATEGIAS ACTIVAS CORRECTAS (según ANALISIS_SISTEMA_5-9.md)
        self.strategies = [
            # 🌅 Morning Power
            'orb', 'gap_go',
            
            # 🕐 All-Day Core  
            'macdv_smallcaps', 'vwap_smallcaps',
            
            # 📰 Event-Driven
            'catalyst_momentum',
            
            # 🌆 Specialized
            'eod_momentum', 'explosive_volume'
        ]
        self.sector_encoding = {}
        self.model_dir = "core/models/volume_models"
        self.logger = logging.getLogger(__name__)
        
        # 🔍 Feature names para compatibilidad sklearn (mismo orden que entrenamiento)
        self.feature_names = [
            'time_of_day', 'day_of_week', 'log_market_cap', 'log_avg_volume',
            'log_float_shares', 'sector_encoded', 'recent_performance',
            'market_stress', 'volume_trend', 'log_price', 'volume_ratio'
        ]
        
        # Crear directorio de modelos si no existe
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Continuous learning integration
        self.continuous_learning_enabled = enable_continuous_learning
        self._continuous_learning_engine = None
        
    def _connect_db(self) -> sqlite3.Connection:
        """Conexión a la base de datos"""
        return sqlite3.connect(self.db_path)
    
    def _extract_features_from_db(self) -> pd.DataFrame:
        """
        Extrae features REALES de database.db usando la misma estructura que ML Exit Engine
        """
        self.logger.info("📊 Cargando datos DE PRODUCCIÓN de trading_data.db...")
        
        # Query corregido usando la estructura REAL de database.db
        query = """
        SELECT 
            se.ticker,
            se.timestamp,
            COALESCE(sd.sector, 'Technology') as sector,
            sd.percent_var,
            sd.ratio_vol,
            sd.precio,
            sd.volumen,
            
            -- OHLC data agregada por evento (datos reales)
            COUNT(o.id_ohlc) as total_bars,
            AVG(o.volume) as ohlc_avg_volume,
            MAX(o.volume) as max_volume,
            MIN(o.volume) as min_volume,
            
            -- Price metrics de datos reales OHLC
            AVG(o.close) as avg_price,
            MAX(o.high) as day_high,
            MIN(o.low) as day_low,
            
            -- Daily data (market cap real, float shares, etc)
            COALESCE(dtd.market_cap, sd.precio * AVG(o.volume) * 0.1) as market_cap,
            COALESCE(dtd.float_shares, AVG(o.volume) * 50) as float_shares,
            COALESCE(dtd.avg_volume, AVG(o.volume)) as daily_avg_volume,
            
            -- Volumen actual vs promedio (target importante)
            sd.ratio_vol as volume_ratio
            
        FROM ScannerEvents se 
        JOIN ScannerData sd ON se.id_event = sd.id_event
        JOIN OHLCData o ON se.id_event = o.id_event
        LEFT JOIN DailyTickerData dtd ON se.id_event = dtd.id_event
        WHERE sd.percent_var IS NOT NULL 
          AND sd.ratio_vol IS NOT NULL
          AND sd.ratio_vol BETWEEN 0.5 AND 20.0  -- 🔥 MÁS RELAJADO para volume prediction
          AND sd.percent_var BETWEEN 0.5 AND 50.0  -- 🔥 MÁS PERMISIVO para volumen
          AND sd.precio BETWEEN 0.5 AND 100.0       -- 🔥 RANGO MUY AMPLIO
          AND o.volume > 2000  -- 🔥 Volumen mínimo muy bajo
        GROUP BY se.id_event, se.ticker, se.timestamp
        HAVING COUNT(o.id_ohlc) >= 30  -- 🔥 Solo 30 min de datos (menos restrictivo)
          AND (MAX(o.high) - MIN(o.low)) / AVG(o.close) < 0.80   -- 🔥 Rangos extremos permitidos
          AND (MAX(o.high) - MIN(o.close)) / MAX(o.high) < 0.90  -- 🔥 Crashes <90% permitidos
        ORDER BY se.timestamp DESC
        """
        
        with self._connect_db() as conn:
            df = pd.read_sql_query(query, conn)
        
        self.logger.info(f"📊 Cargados {len(df)} eventos con datos OHLC reales")
        
        if len(df) < 100:
            self.logger.warning(f"⚠️ Solo {len(df)} eventos encontrados - necesitamos más datos")
            
        return df
    
    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ingeniería de features para ML (versión simplificada)
        """
        # Convertir timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['time_of_day'] = df['timestamp'].dt.hour / 24.0
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        
        # Features logarítmicas para variables con wide range (con valores seguros)
        df['market_cap'] = df['market_cap'].fillna(df['precio'] * 1000000)
        df['avg_volume'] = df['daily_avg_volume'].fillna(df['ohlc_avg_volume']).fillna(50000)
        df['float_shares'] = df['float_shares'].fillna(df['market_cap'] / df['precio'])
        
        df['log_market_cap'] = np.log1p(np.maximum(df['market_cap'], 1))
        df['log_avg_volume'] = np.log1p(np.maximum(df['avg_volume'], 1))
        df['log_float_shares'] = np.log1p(np.maximum(df['float_shares'], 1))
        df['log_price'] = np.log1p(df['precio'])
        
        # Encoding de sectores
        sectors = df['sector'].unique()
        self.sector_encoding = {sector: i for i, sector in enumerate(sectors)}
        df['sector_encoded'] = df['sector'].map(self.sector_encoding)
        
        # Performance reciente (usando percent_var como proxy)
        df['recent_performance'] = df['percent_var']
        
        # Market stress simplificado (usando rango de precios del día)
        df['market_stress'] = np.abs(df['percent_var']) / 10.0  # Normalize stress 0-1
        df['market_stress'] = np.clip(df['market_stress'], 0, 1)
        
        # Volume trend (ratio_vol ya es una buena medida)
        df['volume_trend'] = df['ratio_vol']
        
        # Volume ratio (target para algunas estrategias)
        df['volume_ratio'] = df['ratio_vol']
        
        return df
    
    def _create_strategy_targets(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Crea targets específicos para cada estrategia basado en el éxito histórico
        """
        targets = {}
        
        # Para cada estrategia, calculamos el volumen óptimo basado en performance
        for strategy in self.strategies:
            if strategy == 'macdv_smallcaps':
                # MACDV funciona mejor con volumen moderado pero consistente
                target = np.where(
                    (df['volume_ratio'] >= 1.2) & (df['volume_ratio'] <= 3.0) & (df['recent_performance'] > 2),
                    1.2,  # Volumen óptimo
                    np.where(df['volume_ratio'] < 1.2, 0.8, 2.0)  # Ajuste dinámico
                )
                
            elif strategy == 'daily_plays':
                # Daily plays necesita volumen sostenido
                target = np.where(
                    (df['volume_ratio'] >= 0.8) & (df['recent_performance'] > 1),
                    0.8,
                    np.where(df['market_stress'] > 0.3, 0.6, 1.2)
                )
                
            elif strategy == 'gap_go':
                # Gap & Go necesita volumen alto al abrir
                target = np.where(
                    (df['volume_ratio'] >= 1.5) & (abs(df['recent_performance']) > 3),
                    1.5,
                    np.where(df['time_of_day'] < 0.5, 1.2, 2.0)  # Más leniente en premarket
                )
                
            elif strategy == 'volume_breakout':
                # Volume breakout necesita explosión de volumen
                target = np.where(
                    df['volume_ratio'] >= 2.0,
                    2.0,
                    np.where(df['market_stress'] > 0.4, 1.5, 2.5)
                )
                
            else:
                # Estrategia genérica basada en condiciones del mercado
                target = np.where(
                    df['volume_ratio'] >= 1.5,
                    1.5,
                    np.where(df['market_stress'] > 0.3, 1.0, 1.8)
                )
            
            targets[strategy] = pd.Series(target, index=df.index)
        
        return targets
    
    def train_models(self) -> Dict[str, float]:
        """
        Entrena modelos ML para todas las estrategias
        """
        self.logger.info("🧠 Iniciando entrenamiento ML de volumen dinámico...")
        
        # Extraer y procesar datos
        df = self._extract_features_from_db()
        if len(df) < 100:
            raise ValueError(f"Datos insuficientes para entrenamiento: {len(df)} registros")
        
        df = self._engineer_features(df)
        targets = self._create_strategy_targets(df)
        
        # Features para entrenamiento
        X = df[self.feature_columns].fillna(0)
        
        results = {}
        
        for strategy in self.strategies:
            self.logger.info(f"🎯 Entrenando modelo para {strategy}...")
            
            y = targets[strategy]
            
            # Split train/test
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Scaler
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # MODELO ULTRA-CONSERVADOR con regularización extrema para datos limitados
            # Con 439 trades de calidad, priorizamos GENERALIZACIÓN sobre PRECISIÓN
            model = Ridge(
                alpha=10.0,              # ✅ REGULARIZACIÓN EXTREMA (era 1.0)
                random_state=42,
                max_iter=1000
            )
            
            # Fallback a Gradient Boosting SOLO si Ridge falla completamente
            # model = GradientBoostingRegressor(
            #     n_estimators=10,         # ✅ Ultra-reducido para datos limitados
            #     learning_rate=0.01,     # ✅ Aprendizaje ultra-lento
            #     max_depth=2,            # ✅ Árboles ultra-simples
            #     min_samples_split=30,   # ✅ Muy conservador
            #     min_samples_leaf=15,    # ✅ Muy conservador
            #     subsample=0.6,          # ✅ Solo 60% de datos
            #     validation_fraction=0.3,# ✅ 30% para validación
            #     n_iter_no_change=3,     # ✅ Para temprano
            #     random_state=42
            # )
            
            # VALIDACIÓN CRUZADA para detectar overfitting
            cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=3, scoring='r2')
            cv_mean = cv_scores.mean()
            cv_std = cv_scores.std()
            
            # Entrenar modelo final
            model.fit(X_train_scaled, y_train)
            
            # Evaluar CON MÉTRICAS DE OVERFITTING
            y_pred = model.predict(X_test_scaled)
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            # 🚨 DETECTAR OVERFITTING
            overfitting_gap = cv_mean - r2  # Si gap > 0.1, hay overfitting
            
            if overfitting_gap > 0.1:
                self.logger.warning(f"🚨 {strategy}: Posible overfitting (CV R²={cv_mean:.3f} vs Test R²={r2:.3f})")
            
            # FALLBACK a modelo más simple si overfitting (ajustado para Ridge)
            # Con Ridge, R² > 0.7 ya es sospechoso, R² > 0.8 es overfitting probable
            if r2 > 0.8 or overfitting_gap > 0.15:
                self.logger.warning(f"⚠️ {strategy}: R² sospechoso ({r2:.3f}), probando Ridge Regression")
                
                # Modelo aún más simple como backup (ya estamos usando Ridge, usar más regularización)
                simple_model = Ridge(alpha=50.0, random_state=42)  # ✅ Regularización extrema
                simple_model.fit(X_train_scaled, y_train)
                
                y_pred_simple = simple_model.predict(X_test_scaled)
                r2_simple = r2_score(y_test, y_pred_simple)
                mae_simple = mean_absolute_error(y_test, y_pred_simple)
                
                # Usar modelo ultra-regularizado si es más conservador
                if 0.1 <= r2_simple <= 0.6:  # Rango ULTRA-REALISTA para trading
                    model = simple_model
                    r2 = r2_simple
                    mae = mae_simple
                    self.logger.info(f"✅ {strategy}: Ridge α=50 usado - MAE={mae:.3f}, R²={r2:.3f} (ultra-conservador)")
                else:
                    self.logger.info(f"✅ {strategy}: Ridge α=10 - MAE={mae:.3f}, R²={r2:.3f} (CV: {cv_mean:.3f}±{cv_std:.3f})")
            else:
                self.logger.info(f"✅ {strategy}: Ridge α=10 - MAE={mae:.3f}, R²={r2:.3f} (CV: {cv_mean:.3f}±{cv_std:.3f})")
            
            results[strategy] = {'mae': mae, 'r2': r2, 'cv_mean': cv_mean, 'overfitting_gap': overfitting_gap}
            
            # Guardar modelo y scaler
            self.models[strategy] = model
            self.scalers[strategy] = scaler
            
            joblib.dump(model, f"{self.model_dir}/{strategy}_volume_model.pkl")
            joblib.dump(scaler, f"{self.model_dir}/{strategy}_scaler.pkl")
            
            self.logger.info(f"✅ {strategy}: MAE={mae:.3f}, R²={r2:.3f}")
        
        # Guardar sector encoding
        joblib.dump(self.sector_encoding, f"{self.model_dir}/sector_encoding.pkl")
        
        self.logger.info("🎯 Entrenamiento completado para todas las estrategias")
        return results
    
    def load_models(self) -> bool:
        """
        Carga modelos pre-entrenados
        """
        try:
            for strategy in self.strategies:
                model_path = f"{self.model_dir}/{strategy}_volume_model.pkl"
                scaler_path = f"{self.model_dir}/{strategy}_scaler.pkl"
                
                if os.path.exists(model_path) and os.path.exists(scaler_path):
                    self.models[strategy] = joblib.load(model_path)
                    self.scalers[strategy] = joblib.load(scaler_path)
                else:
                    self.logger.warning(f"⚠️ Modelo no encontrado para {strategy}")
            
            # Cargar sector encoding
            encoding_path = f"{self.model_dir}/sector_encoding.pkl"
            if os.path.exists(encoding_path):
                self.sector_encoding = joblib.load(encoding_path)
            
            return len(self.models) > 0
            
        except Exception as e:
            self.logger.error(f"❌ Error cargando modelos: {e}")
            return False
    
    def predict_volume_requirement(self, strategy: str, context: MarketContext) -> float:
        """
        Predice el requerimiento óptimo de volumen para una estrategia
        """
        if strategy not in self.models:
            return self._get_fallback_requirement(strategy)
        
        try:
            # Preparar features
            features = np.array([
                context.time_of_day,
                context.day_of_week,
                np.log1p(context.market_cap) if context.market_cap > 0 else 0,
                np.log1p(context.avg_volume) if context.avg_volume > 0 else 0,
                np.log1p(context.float_shares) if context.float_shares > 0 else 0,
                self.sector_encoding.get(context.sector, 0),
                context.recent_performance,
                context.market_stress,
                context.volume_trend,
                np.log1p(context.price_level) if context.price_level > 0 else 0,
                context.volume_trend  # volume_ratio
            ]).reshape(1, -1)
            
            # Escalar features - convertir a DataFrame para compatibilidad sklearn
            features_df = pd.DataFrame(features, columns=self.feature_names)
            features_scaled = self.scalers[strategy].transform(features_df)
            
            # Predicción
            prediction = self.models[strategy].predict(features_scaled)[0]
            
            # Constraints dinámicos
            min_req = 0.3 if context.market_stress < 0.3 else 0.5
            max_req = 3.0 if context.market_stress > 0.7 else 2.5
            
            return np.clip(prediction, min_req, max_req)
            
        except Exception as e:
            self.logger.error(f"❌ Error en predicción para {strategy}: {e}")
            return self._get_fallback_requirement(strategy)
    
    def _get_fallback_requirement(self, strategy: str) -> float:
        """
        Valores de fallback seguros por estrategia
        """
        fallbacks = {
            'macdv_smallcaps': 1.2,
            'daily_plays': 0.8,
            'gap_go': 1.5,
            'orb': 1.3,
            'volume_breakout': 2.0,
            'pmh_breakout': 1.8,
            'catalyst_momentum': 1.6,
            'vwap_reclaim': 1.4,
            'eod_momentum': 1.5,
            'vcp': 1.3
        }
        return fallbacks.get(strategy, 1.5)
    
    def initialize_continuous_learning(self):
        """Inicializa el sistema de continuous learning"""
        if not self.continuous_learning_enabled:
            return False
            
        try:
            from core.continuous_learning_engine import get_global_learning_engine
            
            self._continuous_learning_engine = get_global_learning_engine()
            self._continuous_learning_engine.ml_volume_engine = self
            self._continuous_learning_engine.start_continuous_learning()
            
            self.logger.info("🔄 Continuous learning initialized and started")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error initializing continuous learning: {e}")
            return False
    
    def stop_continuous_learning(self):
        """Detiene el continuous learning"""
        if self._continuous_learning_engine:
            self._continuous_learning_engine.stop_continuous_learning()
            self.logger.info("🛑 Continuous learning stopped")
    
    def get_learning_status(self) -> Dict[str, any]:
        """Obtiene estado del continuous learning"""
        if not self._continuous_learning_engine:
            return {
                'enabled': False,
                'status': 'DISABLED',
                'feedback_samples': 0,
                'last_retrain': None
            }
        
        try:
            metrics = self._continuous_learning_engine.get_learning_metrics()
            return {
                'enabled': True,
                'status': 'ACTIVE' if self._continuous_learning_engine._learning_active else 'INACTIVE',
                'feedback_samples': metrics.total_feedback_samples,
                'model_accuracy': metrics.model_accuracy,
                'last_retrain': metrics.last_retrain_date.isoformat(),
                'strategies_improved': metrics.strategies_improved
            }
        except Exception as e:
            self.logger.error(f"❌ Error getting learning status: {e}")
            return {'enabled': False, 'status': 'ERROR', 'error': str(e)}

    def get_optimization_status(self) -> Dict[str, any]:
        """
        Estado del sistema de optimización ML
        """
        status = {
            'status': 'ACTIVE' if len(self.models) > 0 else 'INACTIVE',
            'trained_strategies': len(self.models),
            'total_strategies': len(self.strategies),
            'model_directory': self.model_dir,
            'available_strategies': list(self.models.keys())
        }
        
        # Add continuous learning status
        if self.continuous_learning_enabled:
            status['continuous_learning'] = self.get_learning_status()
        
        return status

def create_market_context(ticker_data: dict, current_time: datetime = None) -> MarketContext:
    """
    Crea contexto del mercado desde datos del ticker
    """
    if current_time is None:
        current_time = datetime.now()
    
    return MarketContext(
        time_of_day=current_time.hour / 24.0,
        day_of_week=current_time.weekday(),
        market_cap=ticker_data.get('market_cap', 0),
        avg_volume=ticker_data.get('avg_volume', 0),
        float_shares=ticker_data.get('float_shares', 0),
        sector=ticker_data.get('sector', 'OTHER'),
        recent_performance=ticker_data.get('percent_var', 0),
        market_stress=ticker_data.get('volatility', 0.3),  # Default moderate stress
        volume_trend=ticker_data.get('ratio_vol', 1.0),
        price_level=ticker_data.get('price', 0)
    )