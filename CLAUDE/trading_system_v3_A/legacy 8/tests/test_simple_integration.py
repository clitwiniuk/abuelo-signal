#!/usr/bin/env python3
"""
Test básico para verificar que el sistema de market conditions funciona
Sin tocar el código de producción - solo test funcional
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_test_market_data():
    """Crea datos de mercado para testear"""
    np.random.seed(42)
    
    # Simulate overbought condition (strong uptrend)
    base_prices = np.cumsum(np.random.normal(0.15, 0.5, 100)) + 100
    
    data = []
    for i, base_price in enumerate(base_prices):
        volatility = 0.5
        open_price = base_price + np.random.normal(0, volatility)
        high_price = open_price + abs(np.random.normal(0, volatility))
        low_price = open_price - abs(np.random.normal(0, volatility))
        close_price = low_price + (high_price - low_price) * np.random.uniform(0.4, 0.8)
        volume = np.random.randint(50000, 200000)
        
        data.append({
            'timestamp': pd.Timestamp.now() - pd.Timedelta(minutes=100-i),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
    
    return pd.DataFrame(data)

def test_market_condition_analysis():
    """Test directo del análisis de condiciones de mercado"""
    
    print("🧪 TESTING MARKET CONDITION ANALYSIS")
    print("=" * 50)
    
    try:
        # Import the market condition functions
        from analysis.market_condition_analyzer import analyze_market_conditions
        
        # Create test data
        market_data = create_test_market_data()
        
        print(f"📊 Created test data: {len(market_data)} bars")
        print(f"   Price range: {market_data['close'].min():.2f} - {market_data['close'].max():.2f}")
        
        # Test market condition analysis - using the core function
        conditions = analyze_market_conditions(market_data)
        
        print(f"\n🎯 Market Condition Analysis Results:")
        print(f"   Market Grade: {conditions.get('market_condition_grade_numeric', 'N/A')}")
        print(f"   MACD Percentile: {conditions.get('macd_percentile_20d', 0):.1f}%")
        print(f"   Overbought Risk: {conditions.get('overbought_risk_composite', 0):.2f}")
        print(f"   Entry Timing: {conditions.get('overall_entry_timing_quality', 0):.2f}")
        print(f"   Volume Quality: {conditions.get('volume_momentum_quality', 0):.2f}")
        
        # Verify it returns expected structure
        expected_keys = ['market_condition_grade_numeric', 'macd_percentile_20d', 
                        'overbought_risk_composite', 'overall_entry_timing_quality']
        
        for key in expected_keys:
            assert key in conditions, f"Missing key: {key}"
        
        print("\n✅ Market condition analysis working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Market condition analysis failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def test_strategy_enhancement():
    """Test que las funciones de enhancement funcionan"""
    
    print("\n🧪 TESTING STRATEGY ENHANCEMENT")
    print("=" * 50)
    
    try:
        from analysis.strategy_feature_enhancer import enhance_macdv_features
        
        # Create basic opportunity
        market_data = create_test_market_data()
        opportunity = {
            'symbol': 'TEST',
            'strategy': 'macdv_smallcaps',
            'entry_price': market_data['close'].iloc[-1],
            'market_data': market_data,
            'features': {
                'macd_signal': 0.5,
                'volume_ratio': 2.0
            }
        }
        
        # Test enhancement - pass the correct parameters
        enhanced_features = enhance_macdv_features(
            opportunity['features'],
            opportunity['market_data'],
            opportunity['symbol']
        )
        
        # Create enhanced opportunity
        enhanced = opportunity.copy()
        enhanced['features'] = enhanced_features
        
        print(f"📈 Original features: {len(opportunity['features'])}")
        print(f"📈 Enhanced features: {len(enhanced['features'])}")
        
        # Check new features were added
        new_features = set(enhanced['features'].keys()) - set(opportunity['features'].keys())
        print(f"🆕 New features added: {list(new_features)}")
        
        # Should have market condition features
        market_features = [f for f in new_features if 'market_' in f or 'overbought' in f or 'grade' in f]
        print(f"🎯 Market-related features: {market_features}")
        
        assert len(new_features) > 0, "No new features were added"
        assert len(market_features) > 0, "No market condition features added"
        
        print("\n✅ Strategy enhancement working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Strategy enhancement failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def run_simple_tests():
    """Ejecuta tests básicos para verificar funcionalidad"""
    
    print("🚀 SIMPLE INTEGRATION TESTS")
    print("=" * 60)
    
    results = []
    
    # Test 1: Market Condition Analysis
    results.append(test_market_condition_analysis())
    
    # Test 2: Strategy Enhancement
    results.append(test_strategy_enhancement())
    
    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Market condition analysis is working")
        print("✅ Strategy enhancement is working")
        print("✅ System is ready for integration")
        return True
    else:
        print(f"❌ {total - passed} TESTS FAILED")
        return False

if __name__ == "__main__":
    success = run_simple_tests()
    sys.exit(0 if success else 1)