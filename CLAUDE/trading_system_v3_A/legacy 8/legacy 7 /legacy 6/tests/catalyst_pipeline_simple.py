#!/usr/bin/env python3
"""
Catalyst Incremental Pipeline - Versión simplificada para testing
"""

import sqlite3
import json
import configparser
from datetime import datetime
from typing import Dict, Optional

class CatalystIncrementalPipeline:
    
    def __init__(self):
        self.database_path = "database_quality.db"
        self.config_path = "config.ini"
        self.models_dir = "core/models/exit_models"
        self.min_samples_for_activation = 50
    
    def setup_catalyst_tables(self):
        """Crea tablas necesarias para datos de catalizador"""
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Tabla de outcomes
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Estado del modelo
        conn.execute("""
        CREATE TABLE IF NOT EXISTS CatalystModelStatus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_samples INTEGER,
            last_retrain_date TEXT,
            model_accuracy REAL,
            is_active BOOLEAN DEFAULT FALSE,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        conn.close()
        print("✅ Catalyst tables created")
    
    def inject_catalyst_data(self,
                           ticker: str,
                           catalyst_type: str,
                           finbert_score: float,
                           finbert_confidence: float,
                           headline: str,
                           news_age_minutes: int,
                           strength_score: float,
                           id_event: Optional[int] = None):
        """Inyecta datos de catalizador"""
        conn = sqlite3.connect(self.database_path)
        
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
        conn.close()
        
        print(f"📊 Catalyst injected: {ticker} | {catalyst_type} | Score: {finbert_score:.2f}")
        return catalyst_id
    
    def get_status(self) -> Dict:
        """Estado actual del pipeline"""
        conn = sqlite3.connect(self.database_path)
        
        # Datos de catalizador
        cursor = conn.execute("SELECT COUNT(*) FROM CatalystData")
        result = cursor.fetchone()
        total_catalyst_data = result[0] if result else 0
        
        cursor = conn.execute("""
        SELECT COUNT(*) FROM CatalystData cd
        LEFT JOIN CatalystOutcomes co ON cd.id = co.catalyst_id
        WHERE co.pnl_pct IS NOT NULL
        """)
        result = cursor.fetchone()
        training_ready_samples = result[0] if result else 0
        
        conn.close()
        
        # Config status
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path)
            config_active = config.getboolean('STRATEGIES', 'catalyst_momentum', fallback=False)
        except:
            config_active = False
        
        return {
            'total_catalyst_data': total_catalyst_data,
            'training_ready_samples': training_ready_samples,
            'min_required_samples': self.min_samples_for_activation,
            'config_active': config_active,
            'ready_for_activation': training_ready_samples >= self.min_samples_for_activation
        }

def main():
    print("🚀 CATALYST INCREMENTAL PIPELINE")
    print("=" * 50)
    
    pipeline = CatalystIncrementalPipeline()
    pipeline.setup_catalyst_tables()
    
    # Estado inicial
    status = pipeline.get_status()
    print(f"📊 Estado inicial:")
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    # Test injection
    print(f"\n🧪 Testing data injection...")
    
    catalyst_id = pipeline.inject_catalyst_data(
        ticker="BNZI",
        catalyst_type="FDA",
        finbert_score=0.85,
        finbert_confidence=0.90,
        headline="Company announces positive Phase II results",
        news_age_minutes=30,
        strength_score=8.5
    )
    
    print(f"✅ Test catalyst injected: ID {catalyst_id}")
    
    # Estado después
    status = pipeline.get_status()
    print(f"\n📊 Estado después de test:")
    for key, value in status.items():
        print(f"   {key}: {value}")

if __name__ == "__main__":
    main()