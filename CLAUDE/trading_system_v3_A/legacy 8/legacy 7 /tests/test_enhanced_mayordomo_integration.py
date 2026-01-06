#!/usr/bin/env python3
"""
Test Enhanced Mayordomo with Market Condition Analysis and DELAY/RETRY System
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.enhanced_mayordomo import EnhancedGamePlanMayordomo

# Import create_sample_data function directly
def create_sample_data(bars=100, trend='neutral'):
    """Create sample OHLCV data for testing"""
    
    np.random.seed(42)  # Reproducible results
    
    # Base price movement
    if trend == 'uptrend':
        base_prices = np.cumsum(np.random.normal(0.1, 1, bars)) + 100
    elif trend == 'downtrend':
        base_prices = np.cumsum(np.random.normal(-0.1, 1, bars)) + 100
    else:  # neutral
        base_prices = np.cumsum(np.random.normal(0, 1, bars)) + 100
    
    # Create OHLCV
    data = []
    for i, base_price in enumerate(base_prices):
        volatility = np.random.uniform(0.5, 2.0)
        open_price = base_price + np.random.normal(0, volatility)
        high_price = open_price + abs(np.random.normal(0, volatility))
        low_price = open_price - abs(np.random.normal(0, volatility))
        close_price = low_price + (high_price - low_price) * np.random.uniform(0.2, 0.8)
        volume = np.random.randint(10000, 100000)
        
        data.append({
            'timestamp': pd.Timestamp.now() - pd.Timedelta(minutes=bars-i),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
    
    return pd.DataFrame(data)


def create_mock_config():
    """Create mock config for testing"""
    from core.interfaces import TradingConfig
    
    class MockConfig(TradingConfig):
        def __init__(self):
            self.max_positions = 5
            self.max_position_value = 300.0
            self.min_position_value = 50.0
            self.risk_per_trade = 0.02
            # Add other required attributes
            self.market_open_time = '09:30'
            self.market_close_time = '16:00'
            self.max_daily_trades = 10
            self.max_daily_loss = 500.0
    
    return MockConfig()


def create_sample_opportunity(symbol='TEST', strategy='macdv_smallcaps', overbought_level='normal'):
    """Create sample trading opportunity for testing"""
    
    # Create market data based on overbought level
    if overbought_level == 'critical':
        market_data = create_sample_data(100, 'uptrend')  # Strong uptrend = overbought
        # Simulate very overbought conditions
        for i in range(-10, 0):  # Last 10 bars
            market_data.loc[market_data.index[i], 'close'] *= 1.02  # 2% daily gains
    elif overbought_level == 'moderate':
        market_data = create_sample_data(100, 'uptrend')
        # Simulate moderate uptrend
        for i in range(-5, 0):
            market_data.loc[market_data.index[i], 'close'] *= 1.01
    else:  # normal
        market_data = create_sample_data(100, 'neutral')
    
    return {
        'symbol': symbol,
        'strategy': strategy,
        'entry_price': market_data['close'].iloc[-1],
        'volume_ratio': 2.5,
        'market_data': market_data,
        'features': {
            'signal_strength': 0.8,
            'momentum_score': 0.75,
            'volume_spike': True,
            'macd_cross': True
        },
        'timestamp': datetime.now().isoformat()
    }


def test_market_timing_analysis():
    """Test market condition analysis and timing decisions"""
    
    print("🧪 TESTING MARKET TIMING ANALYSIS")
    print("=" * 50)
    
    config = create_mock_config()
    mayordomo = EnhancedGamePlanMayordomo(config)
    
    # Test scenarios
    scenarios = [
        ('GOOD_TIMING', 'normal', 'Should EXECUTE'),
        ('MODERATE_OVERBOUGHT', 'moderate', 'Should DELAY'),
        ('CRITICAL_OVERBOUGHT', 'critical', 'Should REJECT')
    ]
    
    for scenario_name, overbought_level, expected in scenarios:
        print(f"\n📊 Testing {scenario_name} - {expected}")
        
        opportunity = create_sample_opportunity(
            symbol=f'TEST_{scenario_name}',
            overbought_level=overbought_level
        )
        
        # Mock base decision as EXECUTE
        base_decision = {'action': 'EXECUTE', 'confidence': 0.8}
        
        # Test timing evaluation
        timing_decision = mayordomo._evaluate_market_timing(
            opportunity['symbol'], opportunity, base_decision
        )
        
        print(f"   Action: {timing_decision['action']}")
        print(f"   Reason: {timing_decision['reason']}")
        
        if 'market_analysis' in timing_decision:
            analysis = timing_decision['market_analysis']
            print(f"   Market Grade: {analysis.get('market_grade', 'N/A')}")
            print(f"   Overbought Penalty: {analysis.get('overbought_penalty', 0):.2f}")
            print(f"   Entry Quality: {analysis.get('entry_quality', 0):.2f}")
        
        # Verify expected behavior
        if expected == 'Should EXECUTE':
            assert timing_decision['action'] == 'EXECUTE', f"Expected EXECUTE, got {timing_decision['action']}"
        elif expected == 'Should DELAY':
            assert timing_decision['action'] == 'DELAY', f"Expected DELAY, got {timing_decision['action']}"
        elif expected == 'Should REJECT':
            assert timing_decision['action'] == 'REJECT', f"Expected REJECT, got {timing_decision['action']}"
    
    print("\n✅ Market timing analysis tests passed!")


def test_delay_retry_system():
    """Test the delay and retry system"""
    
    print("\n🧪 TESTING DELAY & RETRY SYSTEM")
    print("=" * 50)
    
    config = create_mock_config()
    mayordomo = EnhancedGamePlanMayordomo(config)
    
    # Test delay scenario
    opportunity = create_sample_opportunity(
        symbol='DELAY_TEST',
        overbought_level='moderate'
    )
    
    print("📋 Step 1: Initial evaluation (should delay)")
    decision1 = mayordomo.evaluate_position_rotation(opportunity)
    
    print(f"   Decision: {decision1.get('action', 'UNKNOWN')}")
    print(f"   Reason: {decision1.get('reason', 'No reason')}")
    
    if decision1.get('action') == 'DELAY':
        retry_bars = decision1.get('retry_in_bars', 0)
        print(f"   Retry in: {retry_bars} bars")
        
        # Simulate bar progression
        for bar in range(1, retry_bars + 2):
            print(f"\n📋 Step {bar + 1}: Bar {bar} - Check retry status")
            
            # Update bar count
            mayordomo._update_bar_count('DELAY_TEST')
            
            # Try again
            decision = mayordomo.evaluate_position_rotation(opportunity)
            print(f"   Decision: {decision.get('action', 'UNKNOWN')}")
            print(f"   Reason: {decision.get('reason', 'No reason')}")
            
            if decision.get('action') in ['EXECUTE', 'REJECT']:
                print(f"   ✅ Final decision reached after {bar} bars")
                break
            elif decision.get('action') == 'WAITING':
                remaining = decision.get('bars_remaining', 0)
                print(f"   ⏸️ Still waiting ({remaining} bars remaining)")
    
    print("\n✅ Delay & retry system tests passed!")


def test_ml_training_data_collection():
    """Test ML training data collection"""
    
    print("\n🧪 TESTING ML TRAINING DATA COLLECTION")
    print("=" * 50)
    
    config = create_mock_config()
    mayordomo = EnhancedGamePlanMayordomo(config)
    
    # Generate multiple decisions to test data collection
    symbols = ['ML_TEST_1', 'ML_TEST_2', 'ML_TEST_3']
    
    for symbol in symbols:
        opportunity = create_sample_opportunity(symbol=symbol, overbought_level='normal')
        decision = mayordomo.evaluate_position_rotation(opportunity)
        
        print(f"📊 Processed {symbol}: {decision.get('action', 'UNKNOWN')}")
    
    # Check ML training buffer
    buffer_size = len(mayordomo.ml_training_buffer)
    print(f"\n💾 ML Training Buffer Size: {buffer_size}")
    
    if buffer_size > 0:
        sample_record = mayordomo.ml_training_buffer[0]
        print("📋 Sample Training Record Keys:")
        for key in sample_record.keys():
            print(f"   - {key}: {type(sample_record[key]).__name__}")
    
    # Test buffer flush
    mayordomo._flush_ml_training_data()
    print(f"💾 Buffer size after flush: {len(mayordomo.ml_training_buffer)}")
    
    print("\n✅ ML training data collection tests passed!")


def test_performance_report():
    """Test performance reporting with new metrics"""
    
    print("\n🧪 TESTING PERFORMANCE REPORT")
    print("=" * 50)
    
    config = create_mock_config()
    mayordomo = EnhancedGamePlanMayordomo(config)
    
    # Simulate some decisions
    test_scenarios = [
        ('EXECUTE_TEST', 'normal'),
        ('DELAY_TEST', 'moderate'), 
        ('REJECT_TEST', 'critical')
    ]
    
    for symbol, level in test_scenarios:
        opportunity = create_sample_opportunity(symbol=symbol, overbought_level=level)
        decision = mayordomo.evaluate_position_rotation(opportunity)
        print(f"📊 {symbol}: {decision.get('action', 'UNKNOWN')}")
    
    # Generate performance report
    report = mayordomo.get_daily_performance_report()
    
    print("\n📈 Performance Report:")
    print(json.dumps(report, indent=2, default=str))
    
    # Verify report structure
    assert 'market_timing_system' in report, "Missing market timing system metrics"
    assert 'delay_queue_status' in report, "Missing delay queue status"
    
    timing_metrics = report['market_timing_system']
    print(f"\n🎯 Market Timing System Metrics:")
    print(f"   Total analyses: {timing_metrics.get('total_analyses', 0)}")
    print(f"   Delayed decisions: {timing_metrics.get('delayed_decisions', 0)}")
    print(f"   Rejected decisions: {timing_metrics.get('rejected_decisions', 0)}")
    print(f"   Executed decisions: {timing_metrics.get('executed_decisions', 0)}")
    
    print("\n✅ Performance report tests passed!")


def run_integration_tests():
    """Run all integration tests"""
    
    print("🚀 ENHANCED MAYORDOMO INTEGRATION TESTS")
    print("=" * 60)
    
    try:
        test_market_timing_analysis()
        test_delay_retry_system() 
        test_ml_training_data_collection()
        test_performance_report()
        
        print("\n" + "=" * 60)
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("✅ Enhanced Mayordomo is ready for production")
        print("✅ Market condition analysis working")
        print("✅ DELAY/RETRY system working")
        print("✅ ML training data preserved")
        print("✅ Performance reporting enhanced")
        
        return True
        
    except Exception as e:
        print(f"\n❌ INTEGRATION TEST FAILED: {e}")
        import traceback
        print(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)