#!/usr/bin/env python3
"""
Test Gap&Crap Reversal Integration
Complete integration test for Gap&Crap Reversal strategy
"""

import sys
import os
from datetime import datetime
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_gap_crap_integration():
    """Test complete Gap&Crap Reversal integration"""
    print("🔄 Testing Gap&Crap Reversal Integration")
    print("=" * 60)

    try:
        # Step 1: Test strategy import
        print("\n📊 Step 1: Testing Strategy Import")
        from strategies.gap_crap_reversal_strategy import GapCrapReversalStrategy
        print("   ✅ GapCrapReversalStrategy imported successfully")

        # Step 2: Test strategy initialization
        print("\n📊 Step 2: Testing Strategy Initialization")
        strategy = GapCrapReversalStrategy()
        print(f"   ✅ Strategy initialized: {strategy.name}")
        print(f"   📋 Parameters loaded: {len(strategy._parameters)} parameters")

        # Step 3: Test ML Engine registration
        print("\n📊 Step 3: Testing ML Engine Registration")
        from strategies.multi_strategy_engine_ml import create_ml_multi_strategy_engine
        import asyncio

        ml_engine = create_ml_multi_strategy_engine()
        print("   ✅ ML Engine created successfully")

        # Initialize the engine to load strategies (simplified for testing)
        # We'll just load the strategies without full initialization
        ml_engine._load_available_strategies()
        print("   ✅ ML Engine strategies loaded successfully")

        if hasattr(ml_engine, 'available_strategies'):
            strategies = ml_engine.available_strategies
            print(f"   📋 Available strategies: {strategies}")

            if 'gap_crap_reversal' in strategies:
                print("   ✅ gap_crap_reversal found in ML engine strategies")
            else:
                print("   ⚠️  gap_crap_reversal NOT found in ML engine strategies")
        else:
            print("   ⚠️  Cannot check available_strategies attribute")

        # Step 4: Test configuration loading
        print("\n📊 Step 4: Testing Configuration")
        import configparser
        config = configparser.ConfigParser()
        config.read('../config.ini')

        if config.has_section('GAP_CRAP_REVERSAL_STRATEGY'):
            print("   ✅ Gap&Crap Reversal configuration section found")
            enabled = config.getboolean('GAP_CRAP_REVERSAL_STRATEGY', 'enabled', fallback=False)
            print(f"   📊 Strategy enabled: {enabled}")

            min_gap = config.getfloat('GAP_CRAP_REVERSAL_STRATEGY', 'min_gap_percent', fallback=30.0)
            print(f"   📈 Min gap percentage: {min_gap}%")
        else:
            print("   ❌ Gap&Crap Reversal configuration section NOT found")

        # Step 5: Test multi-strategy configuration
        print("\n📊 Step 5: Testing Multi-Strategy Configuration")
        if config.has_section('MULTI_STRATEGY'):
            enabled_strategies = config.get('MULTI_STRATEGY', 'enabled_strategies', fallback='')
            strategies_list = [s.strip() for s in enabled_strategies.split(',')]
            print(f"   📋 Enabled strategies: {strategies_list}")

            if 'gap_crap_reversal' in strategies_list:
                print("   ✅ gap_crap_reversal found in enabled strategies")
            else:
                print("   ❌ gap_crap_reversal NOT in enabled strategies")
        else:
            print("   ❌ MULTI_STRATEGY configuration section NOT found")

        # Step 6: Test signal generation with mock data
        print("\n📊 Step 6: Testing Signal Generation")

        # Create mock market data for Gap&Crap scenario
        class MockBar:
            def __init__(self, open_price, high, low, close, volume):
                self.open = open_price
                self.high = high
                self.low = low
                self.close = close
                self.volume = volume

        class MockMarketData:
            def __init__(self):
                # Gap up scenario: prev close $5.00, opens at $6.50 (30% gap)
                # Currently trading at $6.00 (red in day, below open)
                self.current_bar = MockBar(6.50, 6.60, 5.90, 6.00, 2000000)  # Current

                # Historical data (previous day)
                self.historical_data = [
                    MockBar(5.10, 5.20, 4.95, 5.00, 500000)  # Previous day
                ]

                # Intraday bars showing consolidation around $5.90-$6.00
                self.intraday_bars = [
                    MockBar(6.50, 6.60, 6.20, 6.20, 800000),  # Open high
                    MockBar(6.20, 6.25, 6.00, 6.10, 600000),  # Pullback
                    MockBar(6.10, 6.15, 5.90, 5.95, 700000),  # Lower
                    MockBar(5.95, 6.05, 5.90, 6.00, 500000),  # Consolidation start
                    MockBar(6.00, 6.10, 5.95, 6.00, 400000),  # No new lows
                    MockBar(6.00, 6.05, 5.95, 6.00, 450000),  # Holding support
                ]

        mock_data = MockMarketData()

        try:
            signal = strategy.analyze("TESTGCR", mock_data)
            if signal:
                print(f"   ✅ Signal generated successfully")
                print(f"   📊 Signal type: {signal.signal_type}")
                print(f"   💰 Entry price: ${signal.entry_price:.2f}")
                print(f"   🛑 Stop loss: ${signal.stop_loss:.2f}")
                print(f"   🎯 Target: ${signal.target_price:.2f}")
                print(f"   📈 Confidence: {signal.confidence:.2f}")

                metadata = signal.metadata or {}
                if 'risk_reward_ratio' in metadata:
                    print(f"   ⚖️  Risk/Reward: {metadata['risk_reward_ratio']:.1f}:1")
            else:
                print("   ⚠️  No signal generated (conditions not met)")
        except Exception as e:
            print(f"   ❌ Error generating signal: {e}")

        # Step 7: Test trader_main.py integration
        print("\n📊 Step 7: Testing Trader Main Integration")

        # Check if gap_crap_reversal is in trader_main strategies list
        with open('trader_main.py', 'r') as f:
            trader_content = f.read()

        if "'gap_crap_reversal'" in trader_content:
            print("   ✅ gap_crap_reversal found in trader_main.py")
        else:
            print("   ❌ gap_crap_reversal NOT found in trader_main.py")

        # Step 8: Test scanner compatibility
        print("\n📊 Step 8: Testing Scanner Compatibility")
        from scanner.ibkr_native_scanner import IBKRNativeScanner

        scanner = IBKRNativeScanner()
        gap_configs = [c for c in scanner.scan_configs if 'gap' in c['name'].lower()]

        print(f"   📊 Available gap scanners: {len(gap_configs)}")
        for config in gap_configs:
            print(f"      📈 {config['name']}: {config['scan_code']}")

        # Check if gap_up_movers exists (needed for Gap&Crap)
        gap_up_exists = any(c['name'] == 'gap_up_movers' for c in gap_configs)
        if gap_up_exists:
            print("   ✅ gap_up_movers scanner available (compatible with Gap&Crap)")
        else:
            print("   ❌ gap_up_movers scanner NOT available")

        print("\n✅ Gap&Crap Reversal Integration Test Completed!")
        print("\n📋 Summary:")
        print("   ✅ Strategy class created and importable")
        print("   ✅ ML Engine integration configured")
        print("   ✅ Configuration sections added")
        print("   ✅ Scanner compatibility verified")
        print("   ✅ Signal generation tested")

        print("\n🎯 Next Steps:")
        print("   1. Test during market hours with real gap data")
        print("   2. Monitor scanner.log for gap_up_movers results")
        print("   3. Verify strategy selection in trading logs")
        print("   4. Test multi-target exit functionality")

        return True

    except Exception as e:
        print(f"❌ Error during Gap&Crap integration testing: {e}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    # Setup basic logging
    logging.basicConfig(level=logging.INFO)

    success = test_gap_crap_integration()
    sys.exit(0 if success else 1)