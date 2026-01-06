#!/usr/bin/env python3
"""
Test Smart ML Strategy Selector - Detección automática y reentrenamiento
Ubicación: scripts/testing/ (estructura organizada)

Este script demuestra la nueva funcionalidad inteligente del ML Strategy Selector:
- Detección automática de base de datos (trading_data.db > database_quality.db)
- Reentrenamiento automático cuando hay nuevos datos
- Configuración production vs development
"""

import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from strategies.ml_strategy_selector import create_ml_strategy_selector, ScannerEventContext

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_database_detection():
    """Test automatic database detection"""
    print("🔍 TESTING DATABASE DETECTION")
    print("=" * 50)
    
    strategies = [
        'orb', 'gap_go', 'macdv_smallcaps', 'vwap_smallcaps',
        'catalyst_momentum', 'eod_momentum', 'explosive_volume'
    ]
    
    # Create selector with auto-detection
    selector = create_ml_strategy_selector(
        strategies=strategies,
        auto_retrain=True
    )
    
    print(f"📊 Current database: {selector.current_db}")
    print(f"🤖 Auto-retrain enabled: {selector.auto_retrain}")
    print(f"📈 Retrain threshold: {selector.retrain_threshold} new outcomes")
    print(f"📋 Last training count: {selector.last_training_count}")

def test_smart_selection():
    """Test smart strategy selection with auto-retraining"""
    print("\n🧠 TESTING SMART STRATEGY SELECTION")
    print("=" * 50)
    
    strategies = [
        'orb', 'gap_go', 'macdv_smallcaps', 'vwap_smallcaps',
        'catalyst_momentum', 'eod_momentum', 'explosive_volume'
    ]
    
    # Create selector
    selector = create_ml_strategy_selector(strategies)
    
    # Create test contexts
    test_contexts = [
        {
            'id_event': 9991,
            'ticker': 'AAPL',
            'timestamp': '2024-09-08 10:00:00',
            'percent_var': 3.2,
            'ratio_vol': 2.1,
            'precio': 150.25,
            'volumen': 1000000,
            'sector': 'Technology'
        },
        {
            'id_event': 9992,
            'ticker': 'MSFT',
            'timestamp': '2024-09-08 14:30:00',
            'percent_var': -2.8,
            'ratio_vol': 4.5,
            'precio': 310.50,
            'volumen': 500000,
            'sector': 'Technology'
        },
        {
            'id_event': 9993,
            'ticker': 'TSLA',
            'timestamp': '2024-09-08 09:45:00',
            'percent_var': 8.7,
            'ratio_vol': 6.2,
            'precio': 245.80,
            'volumen': 2000000,
            'sector': 'Consumer Cyclical'
        }
    ]
    
    print("📊 Testing smart selection on multiple contexts:")
    for test_data in test_contexts:
        context = ScannerEventContext.from_scanner_data(test_data)
        
        # Use smart selection (with auto-retraining check)
        selected_strategy = selector.smart_select_strategy(context)
        
        print(f"   🎯 {context.symbol}: {selected_strategy}")
        print(f"      Var: {context.percent_var}%, Vol Ratio: {context.ratio_vol}x")

def test_retrain_threshold():
    """Test retrain threshold functionality"""
    print("\n🔄 TESTING RETRAIN THRESHOLD")
    print("=" * 40)
    
    strategies = ['orb', 'gap_go', 'macdv_smallcaps']
    
    # Create selector with low threshold for testing
    selector = create_ml_strategy_selector(strategies)
    selector.retrain_threshold = 5  # Very low threshold for testing
    
    print(f"📈 Retrain threshold set to: {selector.retrain_threshold}")
    
    # Check current state
    should_retrain = selector.should_retrain(selector.current_db)
    print(f"🤔 Should retrain now? {should_retrain}")
    
    if should_retrain:
        print("✅ Auto-retrain would be triggered!")
    else:
        print("⏳ No retrain needed yet")

def test_production_vs_development():
    """Test production vs development database selection"""
    print("\n🏭 TESTING PRODUCTION vs DEVELOPMENT MODE")
    print("=" * 50)
    
    strategies = ['orb', 'gap_go']
    
    # Create selector and check database priority
    selector = create_ml_strategy_selector(strategies)
    
    print(f"🎯 Primary DB (production): {selector.primary_db}")
    print(f"📊 Fallback DB (development): {selector.fallback_db}")
    print(f"💾 Currently using: {selector.current_db}")
    
    # Check if production database exists
    if os.path.exists("trading_data.db"):
        print("✅ Production database (trading_data.db) found")
    else:
        print("❌ Production database not found - using development DB")
    
    if os.path.exists("database_quality.db"):
        print("✅ Development database (database_quality.db) found")
    else:
        print("❌ Development database not found")

def demonstrate_configuration_options():
    """Demonstrate different configuration options"""
    print("\n⚙️ CONFIGURATION OPTIONS")
    print("=" * 40)
    
    strategies = ['orb', 'gap_go', 'macdv_smallcaps']
    
    print("1️⃣ Production Mode (auto-retrain enabled):")
    prod_selector = create_ml_strategy_selector(
        strategies=strategies,
        auto_retrain=True
    )
    print(f"   Database: {prod_selector.current_db}")
    print(f"   Auto-retrain: {prod_selector.auto_retrain}")
    
    print("\n2️⃣ Development Mode (auto-retrain disabled):")
    dev_selector = create_ml_strategy_selector(
        strategies=strategies,
        auto_retrain=False
    )
    print(f"   Database: {dev_selector.current_db}")
    print(f"   Auto-retrain: {dev_selector.auto_retrain}")

def main():
    """Función principal de testing"""
    print("🧪 SMART ML STRATEGY SELECTOR TESTING")
    print("=" * 60)
    print("📍 Desde: scripts/testing/test_smart_ml_selector.py")
    print("=" * 60)
    
    # Run all tests
    test_database_detection()
    test_smart_selection()
    test_retrain_threshold()
    test_production_vs_development()
    demonstrate_configuration_options()
    
    print("\n" + "=" * 60)
    print("✅ Smart ML Strategy Selector testing completed!")
    print("💡 Features demonstrated:")
    print("   🔍 Automatic database detection")
    print("   🔄 Auto-retraining with new data")
    print("   🏭 Production vs Development modes")
    print("   🧠 Smart strategy selection")

if __name__ == "__main__":
    main()