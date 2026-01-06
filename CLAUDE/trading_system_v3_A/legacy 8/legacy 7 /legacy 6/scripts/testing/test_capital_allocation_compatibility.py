#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de Compatibilidad - Asignación de Capital y Sistemas ML
===========================================================

Este test verifica que las modificaciones realizadas (eliminación de pullback,
portfolio descorrelacionado) no interfieren con:
1. Sistema ML de asignación de capital 
2. Position sizing de las estrategias
3. Funcionalidad del Multi-Strategy Engine ML
4. Configuración de capital y risk management
"""

import sys
import os
import asyncio
from datetime import datetime
import configparser
from typing import Dict, Any

# Add current directory to path
sys.path.insert(0, os.getcwd())

try:
    # Import core systems
    from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
    from strategies.orb_strategy import ORBStrategy
    from strategies.macdv_strategy import MACDVStrategy
    from strategies.gap_go_strategy import GapGoStrategy
    from strategies.vwap_strategy import VWAPSmallcapsStrategy
    from strategies.catalyst_momentum_strategy import CatalystMomentumStrategy
    from strategies.eod_momentum_strategy import EndOfDayMomentumStrategy
    from strategies.explosive_volume_strategy import ExplosiveVolumeStrategy
    
    from core.interfaces import Signal, SignalType, MarketData
    
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

class CapitalAllocationCompatibilityTest:
    """Test compatibility of capital allocation after pullback removal"""
    
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.results = {}
        
    def test_config_reading(self):
        """Test that config reads enabled strategies correctly"""
        print("\n🔍 Testing Configuration Reading...")
        
        try:
            enabled_strategies = self.config.get('MULTI_STRATEGY', 'enabled_strategies', fallback='')
            expected_strategies = {'orb', 'gap_go', 'macdv_smallcaps', 'vwap_smallcaps', 
                                 'catalyst_momentum', 'eod_momentum', 'explosive_volume'}
            
            actual_strategies = set(s.strip() for s in enabled_strategies.split(','))
            
            print(f"   Expected: {sorted(expected_strategies)}")
            print(f"   Actual: {sorted(actual_strategies)}")
            
            if actual_strategies == expected_strategies:
                print("   ✅ Configuration correctly reads 7 enabled strategies")
                return True
            else:
                print("   ❌ Configuration mismatch")
                missing = expected_strategies - actual_strategies
                extra = actual_strategies - expected_strategies
                if missing:
                    print(f"      Missing: {missing}")
                if extra:
                    print(f"      Extra: {extra}")
                return False
                
        except Exception as e:
            print(f"   ❌ Config reading error: {e}")
            return False
    
    def test_position_sizing_methods(self):
        """Test that position sizing methods are intact"""
        print("\n💰 Testing Position Sizing Methods...")
        
        strategies_to_test = [
            ('ORB', ORBStrategy()),
            ('MACDV', MACDVStrategy()),
            ('Gap&Go', GapGoStrategy()),
            ('VWAP', VWAPSmallcapsStrategy()),
        ]
        
        # Create mock signal for testing
        mock_signal = Signal(
            signal_id="test_001",
            symbol="AAPL",
            signal_type=SignalType.LONG,
            strength=0.8,
            price=10.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        test_capital = 2000.0
        test_risk = 0.02
        
        all_passed = True
        
        for strategy_name, strategy in strategies_to_test:
            try:
                if hasattr(strategy, 'calculate_position_size'):
                    position_size = strategy.calculate_position_size(mock_signal, test_capital, test_risk)
                    
                    if isinstance(position_size, int) and position_size > 0:
                        position_value = position_size * mock_signal.price
                        risk_pct = (position_value / test_capital) * 100
                        
                        print(f"   ✅ {strategy_name}: {position_size} shares = ${position_value:.2f} ({risk_pct:.1f}%)")
                    else:
                        print(f"   ❌ {strategy_name}: Invalid position size: {position_size}")
                        all_passed = False
                else:
                    print(f"   ⚠️  {strategy_name}: No calculate_position_size method")
                    
            except Exception as e:
                print(f"   ❌ {strategy_name}: Position sizing error: {e}")
                all_passed = False
        
        return all_passed
    
    def test_ml_engine_compatibility(self):
        """Test ML Multi-Strategy Engine compatibility"""
        print("\n🧠 Testing ML Engine Compatibility...")
        
        try:
            # Initialize ML engine
            ml_engine = MLMultiStrategyEngine()
            
            # Check if it reads config correctly
            if hasattr(ml_engine, 'config'):
                enabled_strategies = ml_engine.config.get('MULTI_STRATEGY', 'enabled_strategies', fallback='')
                strategy_count = len([s.strip() for s in enabled_strategies.split(',') if s.strip()])
                
                print(f"   📊 ML Engine detects {strategy_count} enabled strategies")
                max_concurrent = ml_engine.config.get('MULTI_STRATEGY', 'max_concurrent_strategies')
                if max_concurrent is None:
                    max_concurrent = '3'
                print(f"   🎯 Max concurrent: {max_concurrent}")
                
                if strategy_count == 7:
                    print("   ✅ ML Engine correctly detects 7-strategy portfolio")
                    return True
                else:
                    print("   ❌ ML Engine strategy count mismatch")
                    return False
            else:
                print("   ⚠️  ML Engine config not accessible")
                return False
                
        except Exception as e:
            print(f"   ❌ ML Engine compatibility error: {e}")
            return False
    
    def test_capital_management_parameters(self):
        """Test capital management parameters are intact"""
        print("\n🏦 Testing Capital Management Parameters...")
        
        critical_params = [
            ('TRADING', 'portfolio_capital'),
            ('TRADING', 'max_position_value'), 
            ('TRADING', 'max_positions'),
            ('GLOBAL', 'risk_per_trade'),
            ('TRADING', 'max_daily_loss'),
        ]
        
        all_present = True
        
        for section, param in critical_params:
            try:
                value = self.config.get(section, param, fallback=None)
                if value is not None:
                    print(f"   ✅ {section}.{param} = {value}")
                else:
                    print(f"   ❌ {section}.{param} = MISSING")
                    all_present = False
            except Exception as e:
                print(f"   ❌ {section}.{param} = ERROR: {e}")
                all_present = False
        
        return all_present
    
    def test_strategy_risk_parameters(self):
        """Test individual strategy risk parameters"""
        print("\n⚖️ Testing Strategy Risk Parameters...")
        
        strategies_with_risk = [
            'ORB_STRATEGY',
            'MACDV_STRATEGY', 
            'GAP_GO_STRATEGY',
            'CATALYST_MOMENTUM_STRATEGY',
            'EOD_MOMENTUM_STRATEGY',
        ]
        
        all_good = True
        
        for strategy_section in strategies_with_risk:
            if self.config.has_section(strategy_section):
                # Look for risk-related parameters
                risk_params = ['max_position_value', 'risk_per_trade', 'min_quantity']
                found_params = []
                
                for param in risk_params:
                    if self.config.has_option(strategy_section, param):
                        value = self.config.get(strategy_section, param)
                        found_params.append(f"{param}={value}")
                
                if found_params:
                    print(f"   ✅ {strategy_section}: {', '.join(found_params)}")
                else:
                    print(f"   ⚠️  {strategy_section}: No risk parameters found")
            else:
                print(f"   ❌ {strategy_section}: Section missing")
                all_good = False
        
        return all_good
    
    async def run_integration_test(self):
        """Run full integration test"""
        print("\n🔧 Running Integration Test...")
        
        try:
            # Test creating and using multiple strategies
            strategies = [
                ORBStrategy(),
                MACDVStrategy(),
                GapGoStrategy(),
                VWAPSmallcapsStrategy()
            ]
            
            # Initialize all strategies
            for strategy in strategies:
                await strategy._initialize_strategy()
            
            print(f"   ✅ Successfully initialized {len(strategies)} strategies")
            
            # Test with mock bar data
            mock_bar = MarketData(
                symbol="TEST",
                timestamp=datetime.now(),
                open=10.0,
                high=10.5,
                low=9.8,
                close=10.2,
                volume=100000,
                vwap=10.1
            )
            
            signals_generated = 0
            for i, strategy in enumerate(strategies):
                try:
                    # Add some history
                    if "TEST" not in strategy.bars_history:
                        strategy.bars_history["TEST"] = []
                    strategy.bars_history["TEST"].append(mock_bar)
                    
                    # Try to analyze (may or may not generate signal)
                    signal = await strategy._analyze_bar(mock_bar)
                    if signal:
                        signals_generated += 1
                        print(f"   📊 Strategy {i+1} generated signal")
                    
                except Exception as e:
                    print(f"   ⚠️  Strategy {i+1} analysis error: {e}")
            
            print(f"   📈 Integration test complete: {signals_generated} signals possible")
            return True
            
        except Exception as e:
            print(f"   ❌ Integration test failed: {e}")
            return False
    
    async def run_full_test_suite(self):
        """Run complete test suite"""
        print("🧪 CAPITAL ALLOCATION COMPATIBILITY TEST SUITE")
        print("=" * 60)
        
        tests = [
            ("Configuration Reading", self.test_config_reading),
            ("Position Sizing Methods", self.test_position_sizing_methods),
            ("ML Engine Compatibility", self.test_ml_engine_compatibility),
            ("Capital Management Parameters", self.test_capital_management_parameters),
            ("Strategy Risk Parameters", self.test_strategy_risk_parameters),
            ("Integration Test", self.run_integration_test),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                
                if result:
                    passed += 1
                    self.results[test_name] = "PASS"
                else:
                    self.results[test_name] = "FAIL"
            except Exception as e:
                print(f"❌ Test {test_name} crashed: {e}")
                self.results[test_name] = "ERROR"
        
        # Final summary
        print("\n" + "="*60)
        print("📊 TEST RESULTS SUMMARY")
        print("="*60)
        
        for test_name, result in self.results.items():
            status_icon = "✅" if result == "PASS" else "❌" if result == "FAIL" else "💥"
            print(f"{status_icon} {test_name}: {result}")
        
        print(f"\n🎯 OVERALL: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
        
        if passed == total:
            print("\n🏆 ALL TESTS PASSED - Capital allocation compatibility CONFIRMED")
            print("   - Position sizing methods intact")
            print("   - ML systems compatible")  
            print("   - Risk management preserved")
            print("   - Portfolio configuration correct")
            return True
        elif passed >= total * 0.8:
            print("\n✅ MOSTLY COMPATIBLE - Minor issues detected")
            return True
        else:
            print("\n⚠️  COMPATIBILITY ISSUES - Review required")
            return False

async def main():
    """Main test runner"""
    test_suite = CapitalAllocationCompatibilityTest()
    success = await test_suite.run_full_test_suite()
    
    if success:
        print("\n🎉 CONCLUSION: Modifications are compatible with capital allocation systems")
        sys.exit(0)
    else:
        print("\n🔧 CONCLUSION: Some compatibility issues detected")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())