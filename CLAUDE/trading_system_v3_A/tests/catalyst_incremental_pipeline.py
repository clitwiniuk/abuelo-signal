#!/usr/bin/env python3
"""
Catalyst Incremental Pipeline - Entrenamiento en segundo plano para catalyst_momentum
====================================================================================

Sistema que permite:
1. Catalyst_momentum desactivada inicialmente 
2. Scanner genera datos de catalizador en tiempo real
3. Entrenamiento incremental en segundo plano
4. Activación automática cuando hay suficientes datos
"""

import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
import os
import json
import threading
import time
from typing import Dict, List, Optional, Tuple
import configparser
from dataclasses import dataclass
import joblib
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_absolute_error

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CatalystDataPoint:
    """Punto de datos de catalizador recolectado"""
    timestamp: datetime
    ticker: str
    catalyst_type: str
    finbert_score: float
    news_age_minutes: int
    strength_score: float
    confidence: float
    price_data: Dict  # OHLC data at time of catalyst
    outcome_pnl: Optional[float] = None  # Se calcula después

class CatalystIncrementalPipeline:
    """
    Pipeline incremental para catalyst_momentum
    
    Funciona en background mientras el sistema opera con otras 6 estrategias
    """
    
    def __init__(self, 
                 database_path: str = "database_quality.db",
                 config_path: str = "config.ini",
                 models_dir: str = "core/models/exit_models"):
        
        self.database_path = database_path
        self.config_path = config_path
        self.models_dir = models_dir
        
        # Estado del pipeline
        self.is_running = False
        self.background_thread = None
        self.last_update = datetime.now()
        
        # Datos de catalizador acumulados
        self.catalyst_data: List[CatalystDataPoint] = []
        self.min_samples_for_activation = 50  # Mínimo para activar estrategia
        self.retrain_threshold = 20  # Nuevas muestras para re-entrenar
        
        # Configuración de entrenamiento
        self.update_interval_minutes = 60  # Verificar cada hora
        
        logger.info("🚀 Catalyst Incremental Pipeline initialized")
    
    def setup_catalyst_tables(self):
        """Crea las tablas necesarias para datos de catalizador"""
        conn = sqlite3.connect(self.database_path)
        
        # Tabla principal de catalizadores
        conn.execute("""
        CREATE TABLE IF NOT EXISTS CatalystData (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            id_event INTEGER,
            ticker TEXT NOT NULL,
            catalyst_type TEXT,
            finbert_score REAL,
            finbert_confidence REAL,
            news_age_minutes INTEGER,
            strength_score REAL,
            headline TEXT,
            news_source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_event) REFERENCES ScannerEvents (id_event)
        )
        """)
        
        # Tabla de resultados de trades con catalizador
        conn.execute("""
        CREATE TABLE IF NOT EXISTS CatalystOutcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            catalyst_id INTEGER,
            entry_price REAL,
            exit_price REAL,
            entry_time TEXT,
            exit_time TEXT,
            hold_duration_minutes INTEGER,
            pnl_pct REAL,
            exit_reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (catalyst_id) REFERENCES CatalystData (id)
        )
        """)
        
        # Tabla de estado del modelo
        conn.execute("""
        CREATE TABLE IF NOT EXISTS CatalystModelStatus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_samples INTEGER,
            last_retrain_date TEXT,
            model_accuracy REAL,
            is_active BOOLEAN DEFAULT FALSE,
            performance_metrics TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Catalyst tables created/verified")
    
    def inject_catalyst_data(self, 
                           ticker: str,
                           catalyst_type: str,
                           finbert_score: float,
                           finbert_confidence: float,
                           headline: str,
                           news_age_minutes: int,
                           strength_score: float,
                           id_event: Optional[int] = None):
        """
        Inyecta datos de catalizador desde el scanner en tiempo real
        Esta función debe ser llamada desde el scanner cuando detecte un catalizador
        """
        conn = sqlite3.connect(self.database_path)
        
        try:
            cursor = conn.execute("""
            INSERT INTO CatalystData (
                timestamp, id_event, ticker, catalyst_type, 
                finbert_score, finbert_confidence, news_age_minutes, 
                strength_score, headline, news_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                id_event,
                ticker,
                catalyst_type,
                finbert_score,
                finbert_confidence,
                news_age_minutes,
                strength_score,
                headline,
                'scanner_realtime'
            ))
            
            catalyst_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"📊 Catalyst data injected: {ticker} | {catalyst_type} | Score: {finbert_score:.2f}")
            
            # Trigger check para entrenamiento si se acumulan suficientes datos
            self._check_training_trigger()
            
            return catalyst_id
            
        except Exception as e:
            logger.error(f"❌ Error injecting catalyst data: {e}")
            return None
        finally:
            conn.close()
    
    def record_catalyst_outcome(self, 
                               catalyst_id: int,
                               entry_price: float,
                               exit_price: float,
                               entry_time: datetime,
                               exit_time: datetime,
                               exit_reason: str):
        """Registra el resultado de un trade basado en catalizador"""
        conn = sqlite3.connect(self.database_path)
        
        try:
            hold_duration = (exit_time - entry_time).total_seconds() / 60  # minutes
            pnl_pct = (exit_price - entry_price) / entry_price
            
            conn.execute("""
            INSERT INTO CatalystOutcomes (
                catalyst_id, entry_price, exit_price, 
                entry_time, exit_time, hold_duration_minutes,
                pnl_pct, exit_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                catalyst_id,
                entry_price,
                exit_price,
                entry_time.isoformat(),
                exit_time.isoformat(),
                hold_duration,
                pnl_pct,
                exit_reason
            ))
            
            conn.commit()
            logger.info(f"📈 Catalyst outcome recorded: ID {catalyst_id} | PnL: {pnl_pct:.2%}")
            
        except Exception as e:
            logger.error(f"❌ Error recording catalyst outcome: {e}")
        finally:
            conn.close()
    
    def get_catalyst_training_data(self) -> pd.DataFrame:
        """Obtiene datos de entrenamiento de catalizadores con outcomes"""
        conn = sqlite3.connect(self.database_path)
        
        query = """
        SELECT 
            cd.timestamp,
            cd.ticker,
            cd.catalyst_type,
            cd.finbert_score,
            cd.finbert_confidence,
            cd.news_age_minutes,
            cd.strength_score,
            co.pnl_pct,
            co.hold_duration_minutes,
            co.exit_reason,
            -- Features técnicas de ScannerEvents/Data si están disponibles
            COALESCE(sd.percent_var, 0) as percent_var,
            COALESCE(sd.ratio_vol, 0) as ratio_vol,
            COALESCE(sd.precio, 0) as precio
        FROM CatalystData cd
        LEFT JOIN CatalystOutcomes co ON cd.id = co.catalyst_id
        LEFT JOIN ScannerEvents se ON cd.id_event = se.id_event
        LEFT JOIN ScannerData sd ON se.id_event = sd.id_event
        WHERE co.pnl_pct IS NOT NULL  -- Solo registros con outcome conocido
        ORDER BY cd.timestamp DESC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        logger.info(f"📊 Loaded {len(df)} catalyst training samples")
        return df\n    \n    def train_catalyst_model(self) -> Tuple[bool, Dict]:\n        \"\"\"Entrena modelo específico para catalyst_momentum\"\"\"\n        try:\n            # Obtener datos\n            df = self.get_catalyst_training_data()\n            \n            if len(df) < self.min_samples_for_activation:\n                logger.info(f\"⏳ Insufficient data: {len(df)}/{self.min_samples_for_activation} samples\")\n                return False, {'samples': len(df), 'required': self.min_samples_for_activation}\n            \n            # Preparar features\n            feature_columns = [\n                'finbert_score', 'finbert_confidence', 'news_age_minutes',\n                'strength_score', 'percent_var', 'ratio_vol'\n            ]\n            \n            X = df[feature_columns].fillna(0)\n            \n            # Labels: Exit decision (binary) y Expected PnL (regression)\n            # Exit = 1 si PnL > 2% o PnL < -5%\n            y_exit = ((df['pnl_pct'] > 0.02) | (df['pnl_pct'] < -0.05)).astype(int)\n            y_pnl = df['pnl_pct']\n            \n            # Split\n            X_train, X_test, y_exit_train, y_exit_test, y_pnl_train, y_pnl_test = train_test_split(\n                X, y_exit, y_pnl, test_size=0.3, random_state=42\n            )\n            \n            # Scaler\n            scaler = StandardScaler()\n            X_train_scaled = scaler.fit_transform(X_train)\n            X_test_scaled = scaler.transform(X_test)\n            \n            # Modelos ultra-conservadores\n            exit_classifier = LogisticRegression(\n                C=0.1,  # Regularización fuerte\n                random_state=42,\n                class_weight='balanced'\n            )\n            \n            profit_regressor = Ridge(\n                alpha=10.0,  # Regularización extrema\n                random_state=42\n            )\n            \n            # Entrenar\n            exit_classifier.fit(X_train_scaled, y_exit_train)\n            profit_regressor.fit(X_train_scaled, y_pnl_train)\n            \n            # Evaluar\n            exit_pred = exit_classifier.predict(X_test_scaled)\n            exit_accuracy = accuracy_score(y_exit_test, exit_pred)\n            \n            pnl_pred = profit_regressor.predict(X_test_scaled)\n            pnl_mae = mean_absolute_error(y_pnl_test, pnl_pred)\n            \n            # Guardar modelo\n            catalyst_models_dir = os.path.join(self.models_dir, 'catalyst_exit')\n            os.makedirs(catalyst_models_dir, exist_ok=True)\n            \n            joblib.dump(exit_classifier, os.path.join(catalyst_models_dir, 'exit_classifier.pkl'))\n            joblib.dump(profit_regressor, os.path.join(catalyst_models_dir, 'profit_regressor.pkl'))\n            joblib.dump(scaler, os.path.join(catalyst_models_dir, 'scaler.pkl'))\n            \n            # Metadata\n            metadata = {\n                'trained_at': datetime.now().isoformat(),\n                'strategy': 'catalyst_exit',\n                'feature_names': feature_columns,\n                'samples_used': len(df),\n                'exit_accuracy': exit_accuracy,\n                'pnl_mae': pnl_mae\n            }\n            \n            with open(os.path.join(catalyst_models_dir, 'metadata.json'), 'w') as f:\n                json.dump(metadata, f, indent=2)\n            \n            # Actualizar estado en database\n            self._update_model_status(len(df), exit_accuracy, metadata)\n            \n            logger.info(f\"✅ Catalyst model trained: Accuracy {exit_accuracy:.3f}, MAE {pnl_mae:.3f}\")\n            \n            return True, {\n                'samples': len(df),\n                'exit_accuracy': exit_accuracy,\n                'pnl_mae': pnl_mae,\n                'ready_for_activation': exit_accuracy > 0.6  # Threshold conservador\n            }\n            \n        except Exception as e:\n            logger.error(f\"❌ Error training catalyst model: {e}\")\n            return False, {'error': str(e)}\n    \n    def _update_model_status(self, samples: int, accuracy: float, metadata: Dict):\n        \"\"\"Actualiza estado del modelo en database\"\"\"\n        conn = sqlite3.connect(self.database_path)\n        \n        # Check if ready for activation\n        is_ready = (samples >= self.min_samples_for_activation and \n                   accuracy > 0.6)  # 60% accuracy threshold\n        \n        conn.execute(\"\"\"\n        INSERT OR REPLACE INTO CatalystModelStatus (\n            id, total_samples, last_retrain_date, model_accuracy,\n            is_active, performance_metrics, updated_at\n        ) VALUES (\n            1, ?, ?, ?, ?, ?, ?\n        )\"\"\", (\n            samples,\n            datetime.now().isoformat(),\n            accuracy,\n            is_ready,\n            json.dumps(metadata),\n            datetime.now().isoformat()\n        ))\n        \n        conn.commit()\n        conn.close()\n        \n        if is_ready:\n            logger.info(f\"🚀 Catalyst model ready for activation!\")\n            self._try_activate_catalyst_strategy()\n    \n    def _try_activate_catalyst_strategy(self):\n        \"\"\"Intenta activar catalyst_momentum en config.ini\"\"\"\n        try:\n            config = configparser.ConfigParser()\n            config.read(self.config_path)\n            \n            # Check current status\n            if config.has_section('STRATEGIES'):\n                current_status = config.getboolean('STRATEGIES', 'catalyst_momentum', fallback=False)\n                \n                if not current_status:\n                    # Activar estrategia\n                    config.set('STRATEGIES', 'catalyst_momentum', 'True')\n                    \n                    with open(self.config_path, 'w') as f:\n                        config.write(f)\n                    \n                    logger.info(\"✅ Catalyst_momentum ACTIVATED in config.ini\")\n                    \n                    # Enviar notificación (opcional)\n                    self._send_activation_notification()\n                else:\n                    logger.info(\"ℹ️ Catalyst_momentum already active\")\n        \n        except Exception as e:\n            logger.error(f\"❌ Error activating catalyst_momentum: {e}\")\n    \n    def _send_activation_notification(self):\n        \"\"\"Envía notificación de activación (placeholder)\"\"\"\n        # Aquí podrías integrar Telegram, email, Slack, etc.\n        logger.info(\"📨 NOTIFICATION: Catalyst Momentum Strategy is now ACTIVE!\")\n    \n    def _check_training_trigger(self):\n        \"\"\"Verifica si es momento de entrenar/re-entrenar\"\"\"\n        conn = sqlite3.connect(self.database_path)\n        \n        # Contar nuevas muestras desde último entrenamiento\n        cursor = conn.execute(\"\"\"\n        SELECT COUNT(*) FROM CatalystData cd\n        LEFT JOIN CatalystOutcomes co ON cd.id = co.catalyst_id\n        WHERE co.pnl_pct IS NOT NULL\n        \"\"\")\n        \n        total_samples = cursor.fetchone()[0]\n        conn.close()\n        \n        if total_samples >= self.retrain_threshold:\n            logger.info(f\"🎯 Training trigger: {total_samples} samples available\")\n            \n            # Entrenar en thread separado para no bloquear\n            if not hasattr(self, '_training_in_progress') or not self._training_in_progress:\n                self._training_in_progress = True\n                thread = threading.Thread(target=self._background_training)\n                thread.daemon = True\n                thread.start()\n    \n    def _background_training(self):\n        \"\"\"Entrenamiento en background thread\"\"\"\n        try:\n            logger.info(\"🔄 Starting background catalyst training...\")\n            success, results = self.train_catalyst_model()\n            \n            if success:\n                logger.info(f\"✅ Background training completed: {results}\")\n            else:\n                logger.warning(f\"⚠️ Background training failed: {results}\")\n                \n        except Exception as e:\n            logger.error(f\"❌ Background training error: {e}\")\n        finally:\n            self._training_in_progress = False\n    \n    def get_status(self) -> Dict:\n        \"\"\"Obtiene estado actual del pipeline\"\"\"\n        conn = sqlite3.connect(self.database_path)\n        \n        # Datos de catalizador\n        cursor = conn.execute(\"SELECT COUNT(*) FROM CatalystData\")\n        total_catalyst_data = cursor.fetchone()[0]\n        \n        cursor = conn.execute(\"\"\"\n        SELECT COUNT(*) FROM CatalystData cd\n        LEFT JOIN CatalystOutcomes co ON cd.id = co.catalyst_id\n        WHERE co.pnl_pct IS NOT NULL\n        \"\"\")\n        training_ready_samples = cursor.fetchone()[0]\n        \n        # Estado del modelo\n        cursor = conn.execute(\"\"\"\n        SELECT total_samples, model_accuracy, is_active, last_retrain_date\n        FROM CatalystModelStatus WHERE id = 1\n        \"\"\")\n        model_status = cursor.fetchone()\n        \n        conn.close()\n        \n        # Check config status\n        config = configparser.ConfigParser()\n        config.read(self.config_path)\n        config_active = config.getboolean('STRATEGIES', 'catalyst_momentum', fallback=False)\n        \n        return {\n            'total_catalyst_data': total_catalyst_data,\n            'training_ready_samples': training_ready_samples,\n            'min_required_samples': self.min_samples_for_activation,\n            'model_trained': model_status is not None,\n            'model_accuracy': model_status[1] if model_status else 0.0,\n            'model_active_in_db': model_status[2] if model_status else False,\n            'config_active': config_active,\n            'last_retrain': model_status[3] if model_status else None,\n            'ready_for_activation': training_ready_samples >= self.min_samples_for_activation\n        }\n    \n    def start_monitoring(self):\n        \"\"\"Inicia monitoreo en background\"\"\"\n        if self.is_running:\n            logger.warning(\"⚠️ Pipeline already running\")\n            return\n        \n        self.is_running = True\n        self.background_thread = threading.Thread(target=self._monitoring_loop)\n        self.background_thread.daemon = True\n        self.background_thread.start()\n        \n        logger.info(\"🚀 Catalyst Incremental Pipeline started\")\n    \n    def stop_monitoring(self):\n        \"\"\"Detiene monitoreo\"\"\"\n        self.is_running = False\n        if self.background_thread and self.background_thread.is_alive():\n            self.background_thread.join(timeout=5)\n        \n        logger.info(\"⏹️ Catalyst Incremental Pipeline stopped\")\n    \n    def _monitoring_loop(self):\n        \"\"\"Loop principal de monitoreo\"\"\"\n        while self.is_running:\n            try:\n                # Verificar cada hora si hay datos nuevos\n                self._check_training_trigger()\n                \n                # Sleep por intervalo configurado\n                time.sleep(self.update_interval_minutes * 60)\n                \n            except Exception as e:\n                logger.error(f\"❌ Error in monitoring loop: {e}\")\n                time.sleep(300)  # 5 min delay on error\n\n# Funciones de utilidad para integrar con scanner\ndef inject_scanner_catalyst(ticker: str, \n                          catalyst_type: str,\n                          finbert_score: float,\n                          finbert_confidence: float,\n                          headline: str,\n                          news_age_minutes: int,\n                          strength_score: float,\n                          id_event: Optional[int] = None):\n    \"\"\"Función helper para inyectar desde scanner\"\"\"\n    pipeline = CatalystIncrementalPipeline()\n    return pipeline.inject_catalyst_data(\n        ticker=ticker,\n        catalyst_type=catalyst_type,\n        finbert_score=finbert_score,\n        finbert_confidence=finbert_confidence,\n        headline=headline,\n        news_age_minutes=news_age_minutes,\n        strength_score=strength_score,\n        id_event=id_event\n    )\n\ndef get_pipeline_status() -> Dict:\n    \"\"\"Obtiene estado del pipeline\"\"\"\n    pipeline = CatalystIncrementalPipeline()\n    return pipeline.get_status()\n\ndef main():\n    \"\"\"Función principal para testing\"\"\"\n    print(\"🚀 CATALYST INCREMENTAL PIPELINE\")\n    print(\"=\" * 50)\n    \n    pipeline = CatalystIncrementalPipeline()\n    \n    # Setup inicial\n    pipeline.setup_catalyst_tables()\n    \n    # Estado actual\n    status = pipeline.get_status()\n    print(f\"📊 Estado actual:\")\n    for key, value in status.items():\n        print(f\"   {key}: {value}\")\n    \n    # Simular inyección de datos (para testing)\n    print(f\"\\n🧪 Testing data injection...\")\n    \n    catalyst_id = pipeline.inject_catalyst_data(\n        ticker=\"BNZI\",\n        catalyst_type=\"FDA\",\n        finbert_score=0.85,\n        finbert_confidence=0.90,\n        headline=\"Company announces positive Phase II results\",\n        news_age_minutes=30,\n        strength_score=8.5\n    )\n    \n    print(f\"✅ Test catalyst injected: ID {catalyst_id}\")\n    \n    # Estado después de inyección\n    status = pipeline.get_status()\n    print(f\"\\n📊 Estado después de test:\")\n    print(f\"   Catalyst data points: {status['total_catalyst_data']}\")\n    print(f\"   Training ready: {status['training_ready_samples']}/{status['min_required_samples']}\")\n    \nif __name__ == \"__main__\":\n    main()