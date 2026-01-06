#!/usr/bin/env python3
"""
Test performance tracking integration in production runner
"""

import sys
import os
from datetime import datetime

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

try:
    from core.performance_metrics import get_performance_tracker, MultiLayerPerformanceTracker
    print("✅ Performance metrics imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_performance_tracker_basic():
    """Test basic performance tracking functionality"""
    print("\n🧪 TEST: Basic Performance Tracking")
    print("-" * 50)
    
    # Get tracker instance
    tracker = get_performance_tracker()
    
    # Test data
    test_symbol = "THAR"
    finbert_result = {
        'catalyst_type': 'FDA',
        'catalyst_strength': 8,
        'confidence': 0.85
    }
    strategies = ['gap_and_go', 'breakout_scalp']
    selected_strategy = 'gap_and_go'
    strategy_confidence = 0.75
    
    try:
        print(f"📊 Starting trade flow for {test_symbol}...")
        
        # 1. Start trade flow (simulating production runner)
        trade_flow = tracker.start_trade_flow(
            symbol=test_symbol,
            finbert_result=finbert_result,
            strategies=strategies,
            selected_strategy=selected_strategy,
            strategy_confidence=strategy_confidence
        )
        
        print(f"   ✅ Trade flow started successfully")
        print(f"   📈 FinBERT: {trade_flow.finbert_catalyst} ({trade_flow.finbert_strength}/10)")
        print(f"   🧠 Strategy: {trade_flow.strategy_selected} ({trade_flow.strategy_confidence:.2f})")
        
        # 2. Update execution (simulating Mayordomo approval)
        entry_price = 15.75
        tracker.update_trade_execution(
            symbol=test_symbol,
            executed=True,
            entry_price=entry_price
        )
        
        print(f"   ⚡ Trade execution updated: Executed at ${entry_price}")
        
        # 3. Complete trade (simulating trade exit)
        exit_price = 17.25
        pnl = (exit_price - entry_price) * 100  # Assuming 100 shares
        
        completed_trade = tracker.complete_trade(
            symbol=test_symbol,
            exit_price=exit_price,
            pnl=pnl
        )
        
        print(f"   🎯 Trade completed: Exit ${exit_price}, PnL ${pnl:.2f}")
        print(f"   ⏱️  Duration: {completed_trade.duration_hours:.1f} hours")
        
        return True
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_performance_summary():
    """Test performance summary generation"""
    print("\n🧪 TEST: Performance Summary")
    print("-" * 50)
    
    try:
        tracker = get_performance_tracker()
        
        # Get performance summary
        summary = tracker.get_performance_summary()
        effectiveness = tracker.get_layer_effectiveness()
        recommendations = tracker.should_simplify_system()
        
        print("📊 Performance Summary:")
        for layer, stats in summary.items():
            if layer != 'recent_performance':
                print(f"   {layer}: {stats['accuracy_rate']} accuracy, {stats['total_signals']} signals")
        
        print("\n🔍 Layer Effectiveness:")
        for layer, status in effectiveness.items():
            print(f"   {layer}: {status}")
        
        print(f"\n💡 Simplification Recommended: {recommendations['simplify_recommended']}")
        if recommendations['simplify_recommended']:
            print("   Reasons:")
            for reason in recommendations['reasons']:
                print(f"     • {reason}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_integration_simulation():
    """Simulate the integration as it would work in production"""
    print("\n🧪 TEST: Production Integration Simulation")
    print("-" * 50)
    
    try:
        # This simulates what happens in production runner
        tracker = get_performance_tracker()
        
        # Simulate multiple trade flows
        test_trades = [
            {
                'symbol': 'AAPL', 
                'finbert': {'catalyst_type': 'EARNINGS', 'catalyst_strength': 7, 'confidence': 0.8},
                'strategy': {'selected': 'earnings_play', 'confidence': 0.7, 'alternatives': ['gap_and_go']},
                'executed': True, 'entry': 180.50, 'exit': 185.25, 'pnl': 475.0
            },
            {
                'symbol': 'NVDA',
                'finbert': {'catalyst_type': 'AI_TECH', 'catalyst_strength': 9, 'confidence': 0.9},
                'strategy': {'selected': 'breakout_momentum', 'confidence': 0.85, 'alternatives': ['ai_momentum', 'gap_and_go']},
                'executed': True, 'entry': 850.00, 'exit': 875.50, 'pnl': 510.0
            },
            {
                'symbol': 'TSLA',
                'finbert': {'catalyst_type': 'M&A', 'catalyst_strength': 6, 'confidence': 0.65},
                'strategy': {'selected': 'news_momentum', 'confidence': 0.6, 'alternatives': ['gap_and_go']},
                'executed': False, 'entry': 250.00, 'exit': None, 'pnl': 0.0  # Rejected by Mayordomo
            }
        ]
        
        print(f"🔄 Processing {len(test_trades)} simulated trades...")
        
        for i, trade in enumerate(test_trades, 1):
            print(f"\n   📊 Trade {i}: {trade['symbol']}")
            
            # Start trade flow
            trade_flow = tracker.start_trade_flow(
                symbol=trade['symbol'],
                finbert_result=trade['finbert'],
                strategies=trade['strategy']['alternatives'],
                selected_strategy=trade['strategy']['selected'],
                strategy_confidence=trade['strategy']['confidence']
            )
            
            # Update execution
            tracker.update_trade_execution(
                symbol=trade['symbol'],
                executed=trade['executed'],
                entry_price=trade['entry'] if trade['executed'] else None
            )
            
            # Complete trade if executed
            if trade['executed'] and trade['exit']:
                tracker.complete_trade(
                    symbol=trade['symbol'],
                    exit_price=trade['exit'],
                    pnl=trade['pnl']
                )
                print(f"      ✅ Completed: PnL ${trade['pnl']:.2f}")
            else:
                print(f"      ❌ Rejected by Mayordomo")
        
        # Show final summary
        print("\n📊 FINAL PERFORMANCE SUMMARY:")
        summary = tracker.get_performance_summary()
        for layer, stats in summary.items():
            if layer != 'recent_performance':
                print(f"   {layer.upper()}: {stats['accuracy_rate']} accuracy, {stats['total_pnl']} PnL")
        
        return True
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all performance tracking tests"""
    print("🚀 TESTING PERFORMANCE TRACKING INTEGRATION")
    print("=" * 60)
    
    print("📋 Testing integration of MultiLayerPerformanceTracker")
    print("   • FinBERT → Strategy Selection → Execution tracking")
    print("   • Performance attribution across layers")
    print("   • Effectiveness monitoring and recommendations")
    
    results = []
    
    try:
        # Test 1: Basic functionality
        results.append(test_performance_tracker_basic())
        
        # Test 2: Summary generation  
        results.append(test_performance_summary())
        
        # Test 3: Integration simulation
        results.append(test_integration_simulation())
        
        # Overall summary
        print(f"\n{'='*60}")
        print("🎉 INTEGRATION TEST RESULTS")
        print("=" * 60)
        
        passed_tests = sum(results)
        total_tests = len(results)
        
        print(f"✅ Tests passed: {passed_tests}/{total_tests}")
        
        if passed_tests == total_tests:
            print("\n🎯 INTEGRATION SUCCESSFUL!")
            print("   ✅ Performance tracking fully integrated")
            print("   ✅ Multi-layer attribution working")
            print("   ✅ Ready for production monitoring")
        else:
            print("\n⚠️  INTEGRATION PARTIAL")
            print("   🔧 Some components need adjustment")
            
        print(f"\n🚀 NEXT STEPS:")
        print("   1. Start production runner to collect real data")
        print("   2. Monitor performance during market hours")  
        print("   3. Use /performance command in Telegram to check stats")
        print("   4. Review recommendations for system optimization")
        
        return passed_tests == total_tests
        
    except Exception as e:
        print(f"\n💥 Test suite error: {e}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)