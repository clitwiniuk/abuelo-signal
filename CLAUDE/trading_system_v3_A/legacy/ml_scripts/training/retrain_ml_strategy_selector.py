#!/usr/bin/env python3
"""
Retrain ML Strategy Selector - Usando datos reales de strategy_outcomes
Ubicación: scripts/training/ (estructura organizada)

Este script reentrena el ML Strategy Selector usando los datos reales
de outcomes calculados desde database_quality.db.
"""

import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from strategies.ml_strategy_selector import ContextualBandit, ScannerEventContext

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def retrain_strategy_selector():
    """Retrain ML Strategy Selector con datos reales"""
    print("🧠 RETRAINING ML STRATEGY SELECTOR")
    print("=" * 60)
    print("📍 Desde: scripts/training/retrain_ml_strategy_selector.py")
    print("=" * 60)
    
    # Estrategias actuales del sistema (enabled_strategies from config.ini)
    strategies = [
        'gap_go',                 # GapGoStrategy
        'daily_plays',            # DailyPlaysStrategy
        'first_day_bounce',       # FirstDayBounceStrategy
        'macdv_smallcaps',        # MACDVStrategy (con parámetros actualizados)
        'gap_crap_reversal',      # GapCrapReversalStrategy
        'ascending_triangle',     # AscendingTriangleStrategy (nueva)
        'bull_flag',              # BullFlagStrategy (nueva)
        'falling_wedge'           # FallingWedgeStrategy (nueva)
    ]
    
    print(f"📊 Strategies: {strategies}")

    # Detectar dimensiones automáticamente desde los datos
    logger.info("🔍 Detecting feature dimensions from database...")
    temp_bandit = ContextualBandit(strategies=strategies, feature_dim=12)  # Temporary with larger dim
    sample_data = temp_bandit.load_training_data_from_db("database_quality.db")

    if sample_data:
        # Get actual feature dimension from first sample
        sample_context = sample_data[0][0]  # First context
        actual_feature_dim = len(sample_context.to_feature_vector())  # Use correct method
        print(f"📊 Detected feature dimensions: {actual_feature_dim}")
    else:
        actual_feature_dim = 12  # Default fallback
        print(f"📊 Using default feature dimensions: {actual_feature_dim}")

    # Crear modelo fresh con dimensiones correctas
    logger.info("🔄 Creating fresh ML Strategy Selector...")
    bandit = ContextualBandit(
        strategies=strategies,
        feature_dim=actual_feature_dim,
        alpha=10.0      # Regularización conservadora
    )
    
    # Entrenar con datos reales
    logger.info("📚 Training with real strategy outcomes...")
    bandit.train_from_database(
        db_path="database_quality.db",
        reset_model=True  # Fresh start
    )
    
    # Guardar modelo entrenado
    model_path = "data/ml_models/strategy_selector.json"
    logger.info(f"💾 Saving trained model to {model_path}")
    bandit.save_model(model_path)
    
    # Generar reporte de entrenamiento
    print("\n📈 TRAINING REPORT")
    print("-" * 40)
    
    for strategy in strategies:
        stats = bandit.strategy_stats[strategy]
        print(f"🎯 {strategy.upper()}:")
        print(f"   📊 Total trades: {stats.total_trades}")
        print(f"   ✅ Win rate: {stats.win_rate:.1%}")
        print(f"   💰 Avg reward: {stats.avg_pnl:.3f}")
        print()
    
    # Test rápido del modelo
    print("🧪 QUICK MODEL TEST")
    print("-" * 30)
    
    # Crear contexto de prueba
    test_event_data = {
        'id_event': 9999,
        'ticker': 'TEST',
        'timestamp': '2024-09-08 10:00:00',
        'percent_var': 5.2,
        'ratio_vol': 3.1,
        'precio': 12.45,
        'volumen': 250000,
        'sector': 'Technology'
    }
    
    test_context = ScannerEventContext.from_scanner_data(test_event_data)
    selected_strategy = bandit.select_strategy(test_context)
    rankings = bandit.get_strategy_rankings(test_context)
    
    print(f"📊 Test ticker: {test_context.symbol}")
    print(f"📈 Selected strategy: {selected_strategy}")
    print("📊 Strategy rankings:")
    for i, (strategy, score) in enumerate(rankings[:5]):
        print(f"   {i+1}. {strategy}: {score:.3f}")
    
    print("\n" + "=" * 60)
    print("✅ ML Strategy Selector retraining completed!")
    print("💡 Model now uses real strategy outcomes from database")
    print(f"💾 Saved to: {model_path}")

def verify_training_data():
    """Verificar que tenemos datos de entrenamiento"""
    print("\n🔍 VERIFYING TRAINING DATA")
    print("-" * 40)
    
    import sqlite3
    import pandas as pd
    
    try:
        conn = sqlite3.connect("database_quality.db")
        
        # Check strategy outcomes
        outcomes_count = pd.read_sql_query("""
            SELECT strategy_name, COUNT(*) as count
            FROM strategy_outcomes
            GROUP BY strategy_name
            ORDER BY count DESC
        """, conn)
        
        print("📊 Strategy outcomes in database:")
        for _, row in outcomes_count.iterrows():
            print(f"   {row['strategy_name']}: {row['count']} outcomes")
        
        # Check data completeness
        complete_data = pd.read_sql_query("""
            SELECT COUNT(*) as total_events
            FROM ScannerEvents se
            JOIN ScannerData sd ON se.id_event = sd.id_event
            JOIN strategy_outcomes so ON se.id_event = so.id_event
            WHERE sd.percent_var IS NOT NULL 
              AND sd.ratio_vol IS NOT NULL 
              AND sd.precio IS NOT NULL
        """, conn)
        
        total_events = complete_data['total_events'].iloc[0]
        print(f"📈 Complete training examples: {total_events}")
        
        conn.close()
        
        if total_events == 0:
            print("❌ No training data found!")
            return False
        else:
            print("✅ Training data looks good!")
            return True
            
    except Exception as e:
        print(f"❌ Error checking training data: {e}")
        return False

def main():
    """Función principal"""
    print("🧠 ML STRATEGY SELECTOR RETRAINING")
    print("=" * 50)
    
    # Verificar datos de entrenamiento
    if not verify_training_data():
        print("❌ Cannot proceed without training data")
        return
    
    # Proceder con retraining
    retrain_strategy_selector()

if __name__ == "__main__":
    main()