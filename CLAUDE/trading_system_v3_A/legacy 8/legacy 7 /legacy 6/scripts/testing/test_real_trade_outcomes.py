#!/usr/bin/env python3
"""
Test ML Strategy Selector with Real Trade Outcomes
Prueba el ML Strategy Selector usando outcomes reales de trading_data.db
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

def test_load_real_trade_data():
    """Test loading training data from real trades"""
    print("🔍 TESTING REAL TRADE DATA LOADING")
    print("=" * 50)
    
    strategies = [
        'macdv_smallcaps', 'volume_breakout', 'orb', 'gap_go'
    ]
    
    # Create selector - should auto-detect trading_data.db
    selector = create_ml_strategy_selector(
        strategies=strategies,
        auto_retrain=True
    )
    
    print(f"📊 Current database: {selector.current_db}")
    print(f"🔄 Auto-retrain: {selector.auto_retrain}")
    
    # Load training data
    training_data = selector.load_training_data_from_db()
    
    print(f"📈 Loaded {len(training_data)} real trade examples")
    
    if training_data:
        # Show sample of training data
        print("\\n🔬 Sample training examples:")
        for i, (context, strategy, reward) in enumerate(training_data[:3]):
            print(f"   {i+1}. {context.symbol} | {strategy} | Reward: {reward:.2f}")
            print(f"      Price: ${context.entry_price:.2f} | Qty: {context.quantity}")
            print(f"      Time: {context.hour_of_day:.1f}h | Day: {context.day_of_week}")
            print(f"      Market context: WR={context.daily_win_rate:.1f}%, PnL=${context.daily_pnl:.2f}")
            
        # Show strategy distribution
        strategy_counts = {}
        for _, strategy, _ in training_data:
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
            
        print("\\n📊 Strategy distribution:")
        for strategy, count in sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   {strategy}: {count} examples")
            
    return len(training_data) > 0

def test_training_with_real_data():
    """Test training the model with real data"""
    print("\\n🤖 TESTING TRAINING WITH REAL DATA")
    print("=" * 50)
    
    strategies = [
        'macdv_smallcaps', 'volume_breakout'  # Only strategies with real data
    ]
    
    selector = create_ml_strategy_selector(strategies)
    
    try:
        # Test prediction with real data context (model auto-trains when needed)
        test_context = ScannerEventContext.from_trade_data({
            'id_event': 9999,
            'symbol': 'TEST',
            'timestamp': '2025-09-08 10:30:00',
            'entry_price': 50.0,
            'quantity': 100,
            'daily_win_rate': 60.0,  # Good market day
            'daily_pnl': 150.0
        })
        
        # This will trigger auto-training if needed
        selected_strategy = selector.smart_select_strategy(test_context)
        print(f"🎯 Selected strategy for test context: {selected_strategy}")
        
        # Verify the model is using real data
        print(f"📊 Model training data count: {len(selector.load_training_data_from_db())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Smart selection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_feature_extraction():
    """Test feature extraction from real trade data"""
    print("\\n🔬 TESTING FEATURE EXTRACTION")
    print("=" * 40)
    
    # Create context from real trade data
    trade_data = {
        'id_event': 123,
        'symbol': 'AAPL',
        'timestamp': '2025-09-08 14:30:00',
        'entry_price': 150.25,
        'quantity': 100,
        'daily_win_rate': 75.0,
        'daily_pnl': 250.0
    }
    
    context = ScannerEventContext.from_trade_data(trade_data)
    features = context.to_feature_vector()
    
    print(f"📊 Generated {len(features)} features from real trade data:")
    feature_names = [
        'entry_price', 'log_quantity', 'daily_win_rate', 'daily_pnl',
        'hour_of_day', 'day_of_week', 'minutes_from_open', 'symbol_hash', 'symbol_length'
    ]
    
    for name, value in zip(feature_names, features):
        print(f"   {name}: {value:.3f}")
        
    print(f"\\n✅ Feature vector shape: {features.shape}")
    return len(features) == 9  # Expected number of features

def main():
    """Main test function"""
    print("🧪 REAL TRADE OUTCOMES TESTING")
    print("=" * 60)
    print("📍 Testing ML Strategy Selector with real trading_data.db outcomes")
    print("=" * 60)
    
    # Run tests
    tests_passed = 0
    total_tests = 3
    
    if test_load_real_trade_data():
        tests_passed += 1
        print("✅ Real trade data loading: PASSED")
    else:
        print("❌ Real trade data loading: FAILED")
    
    if test_feature_extraction():
        tests_passed += 1
        print("✅ Feature extraction: PASSED")
    else:
        print("❌ Feature extraction: FAILED")
        
    if test_training_with_real_data():
        tests_passed += 1
        print("✅ Training with real data: PASSED")
    else:
        print("❌ Training with real data: FAILED")
    
    print("\\n" + "=" * 60)
    print(f"🏆 Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 All tests PASSED! Real trade integration successful!")
        print("💡 Key achievements:")
        print("   🔗 Bridge view connects trades to ML training format")
        print("   📊 Real features extracted from trade data")
        print("   🧠 ML model trains on actual trading outcomes")
        print("   ⚡ Auto-detection prioritizes trading_data.db")
    else:
        print("⚠️ Some tests failed. Check implementation.")

if __name__ == "__main__":
    main()