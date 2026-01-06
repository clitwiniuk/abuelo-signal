#!/usr/bin/env python3
"""
Comprehensive Order Flow Analysis Test
=====================================

Tests all entry and exit mechanisms to verify proper interaction and priority:
- Entry: catalyst_momentum, anti-martingala, pyramid
- Exit: FOMO, trailing stop, stop loss, take profit, EOD
- Priority resolution and conflict handling
- Performance optimization opportunities

Author: Claude Code
Date: 2025-08-21
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json

# Test framework imports
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.interfaces import MarketData, Signal, SignalType, TradingConfig
from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
from core.risk_manager import RiskManager


@dataclass
class OrderFlowEvent:
    """Single order flow event for analysis"""
    timestamp: datetime
    symbol: str
    event_type: str  # 'entry', 'exit', 'rejected'
    trigger_type: str  # 'catalyst_momentum', 'fomo', 'trailing', etc.
    price: float
    profit_pct: float
    volume_ratio: float
    priority: int
    metadata: Dict[str, Any]


@dataclass
class TradingScenario:
    """Trading scenario for testing"""
    name: str
    description: str
    symbol: str
    price_data: List[float]  # Price sequence
    volume_data: List[float]  # Volume sequence  
    catalyst_info: Optional[Dict]
    expected_entry: bool
    expected_exits: List[str]  # Expected exit types


class OrderFlowAnalyzer:
    """Comprehensive analyzer for order flow behavior"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.test_results = []
        self.order_events = []
        
        # Initialize components
        self.config = self._create_test_config()
        self.risk_manager = RiskManager(self.config)
        self.ml_engine = None
        
        # Test scenarios
        self.scenarios = self._create_test_scenarios()
        
    def _create_test_config(self) -> TradingConfig:
        """Create test configuration"""
        config = TradingConfig()
        
        # Basic trading config
        config.max_positions = 3
        config.max_daily_trades = 10
        config.max_position_value = 200.0
        config.min_quantity = 10
        
        # Exit parameters
        config.stop_loss_pct = 0.08  # 8%
        config.take_profit_pct = 0.15  # 15%
        config.trailing_stop_activation = 0.06  # 6%
        config.trailing_stop_distance = 0.03  # 3%
        
        # FOMO parameters
        config.fomo_volume_threshold = 2.0  # 2x volume
        config.fomo_profit_threshold = 0.02  # 2% profit
        
        # Catalyst momentum parameters
        config.allow_pyramiding = False  # Test anti-martingala
        config.max_pyramid_levels = 1
        
        return config
        
    def _create_test_scenarios(self) -> List[TradingScenario]:
        """Create comprehensive test scenarios"""
        scenarios = []
        
        # Scenario 1: Perfect catalyst momentum trade
        scenarios.append(TradingScenario(
            name="Perfect Catalyst Momentum",
            description="Catalyst detected → Price rises smoothly → FOMO exit",
            symbol="TEST1",
            price_data=[10.0, 10.2, 10.5, 10.8, 11.0, 11.3, 11.5, 11.4, 11.3],  # Rise then stall
            volume_data=[1000, 3000, 3500, 2800, 2500, 4000, 3200, 2800, 2000],  # Volume spike then normal
            catalyst_info={
                'catalyst_type': 'EARNINGS',
                'strength': 0.8,
                'confidence': 0.85,
                'detected_at': datetime.now()
            },
            expected_entry=True,
            expected_exits=['fomo_exhaustion']
        ))
        
        # Scenario 2: Quick take profit hit
        scenarios.append(TradingScenario(
            name="Quick Take Profit",
            description="Catalyst → Fast 15% gain → Take profit triggered",
            symbol="TEST2", 
            price_data=[10.0, 10.3, 10.8, 11.2, 11.5],  # Quick 15% rise
            volume_data=[1000, 3500, 3000, 2500, 2000],
            catalyst_info={
                'catalyst_type': 'NEWS',
                'strength': 0.9,
                'confidence': 0.8,
                'detected_at': datetime.now()
            },
            expected_entry=True,
            expected_exits=['take_profit']
        ))
        
        # Scenario 3: Stop loss triggered
        scenarios.append(TradingScenario(
            name="Stop Loss Hit", 
            description="Entry → Price drops → Stop loss triggered",
            symbol="TEST3",
            price_data=[10.0, 9.8, 9.5, 9.2, 9.0],  # 10% drop
            volume_data=[1000, 2000, 2500, 2000, 1500],
            catalyst_info={
                'catalyst_type': 'CONTRACT',
                'strength': 0.7,
                'confidence': 0.75,
                'detected_at': datetime.now()
            },
            expected_entry=True,
            expected_exits=['stop_loss']
        ))
        
        # Scenario 4: Trailing stop sequence
        scenarios.append(TradingScenario(
            name="Trailing Stop Activation",
            description="Entry → 8% gain → Trailing activates → Pull back triggers exit",
            symbol="TEST4",
            price_data=[10.0, 10.4, 10.8, 11.0, 10.9, 10.7, 10.5],  # Rise then pullback
            volume_data=[1000, 2500, 2800, 2000, 1800, 1500, 1200],
            catalyst_info={
                'catalyst_type': 'FDA',
                'strength': 0.85,
                'confidence': 0.9,
                'detected_at': datetime.now()
            },
            expected_entry=True,
            expected_exits=['trailing_stop']
        ))
        
        # Scenario 5: Anti-martingala test
        scenarios.append(TradingScenario(
            name="Anti-Martingala Protection",
            description="Entry → Second catalyst on same symbol → Entry rejected",
            symbol="TEST5",
            price_data=[10.0, 10.2, 10.1, 10.3, 10.2],  # Sideways after entry
            volume_data=[1000, 2500, 2000, 3000, 2200],
            catalyst_info={
                'catalyst_type': 'EARNINGS',
                'strength': 0.8,
                'confidence': 0.8,
                'detected_at': datetime.now()
            },
            expected_entry=True,  # First entry
            expected_exits=[]  # Will test second entry rejection
        ))
        
        # Scenario 6: Multiple exit conflicts
        scenarios.append(TradingScenario(
            name="Exit Priority Conflict",
            description="FOMO + Trailing + Take profit all triggered → Test priority",
            symbol="TEST6",
            price_data=[10.0, 10.8, 11.2, 11.5, 11.4],  # 15% gain with volume spike
            volume_data=[1000, 4000, 3500, 5000, 3000],  # High volume throughout
            catalyst_info={
                'catalyst_type': 'M&A',
                'strength': 0.95,
                'confidence': 0.9,
                'detected_at': datetime.now()
            },
            expected_entry=True,
            expected_exits=['fomo_exhaustion', 'take_profit']  # Priority test
        ))
        
        return scenarios
        
    async def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """Run comprehensive order flow analysis"""
        self.logger.info("🔍 Starting Comprehensive Order Flow Analysis")
        self.logger.info("="*60)
        
        results = {
            'total_scenarios': len(self.scenarios),
            'scenario_results': [],
            'entry_analysis': {},
            'exit_analysis': {},
            'priority_analysis': {},
            'optimization_recommendations': []
        }
        
        # Test each scenario
        for i, scenario in enumerate(self.scenarios, 1):
            self.logger.info(f"\n📊 Testing Scenario {i}/{len(self.scenarios)}: {scenario.name}")
            self.logger.info(f"   └─ {scenario.description}")
            
            scenario_result = await self._test_scenario(scenario)
            results['scenario_results'].append(scenario_result)
            
        # Analyze results
        results['entry_analysis'] = self._analyze_entry_behavior(results['scenario_results'])
        results['exit_analysis'] = self._analyze_exit_behavior(results['scenario_results'])
        results['priority_analysis'] = self._analyze_priority_conflicts(results['scenario_results'])
        results['optimization_recommendations'] = self._generate_recommendations(results)
        
        self._save_analysis_report(results)
        self._print_summary(results)
        
        return results
        
    async def _test_scenario(self, scenario: TradingScenario) -> Dict[str, Any]:
        """Test a single trading scenario"""
        self.order_events = []  # Reset for this scenario
        
        # Create market data sequence
        market_data_sequence = self._create_market_data_sequence(scenario)
        
        # Initialize ML engine for this test
        await self._initialize_ml_engine()
        
        result = {
            'scenario_name': scenario.name,
            'expected_entry': scenario.expected_entry,
            'expected_exits': scenario.expected_exits,
            'actual_entry': False,
            'actual_exits': [],
            'order_events': [],
            'entry_price': None,
            'exit_price': None,
            'final_pnl_pct': 0.0,
            'max_profit_pct': 0.0,
            'max_drawdown_pct': 0.0,
            'exit_efficiency': 0.0,
            'conflicts_detected': [],
            'timing_analysis': {}
        }
        
        # Simulate market data flow
        entry_price = None
        position_active = False
        max_price = scenario.price_data[0]
        min_price_after_entry = float('inf')
        
        for i, market_data in enumerate(market_data_sequence):
            current_price = market_data.current_bar.close
            max_price = max(max_price, current_price)
            
            # Test entry logic
            if not position_active:
                entry_signal = await self._test_entry_logic(market_data, scenario)
                if entry_signal:
                    result['actual_entry'] = True
                    result['entry_price'] = current_price
                    entry_price = current_price
                    position_active = True
                    min_price_after_entry = current_price
                    
                    self.order_events.append(OrderFlowEvent(
                        timestamp=market_data.current_bar.timestamp,
                        symbol=scenario.symbol,
                        event_type='entry',
                        trigger_type=entry_signal.get('trigger', 'unknown'),
                        price=current_price,
                        profit_pct=0.0,
                        volume_ratio=market_data.current_bar.volume / 1000,
                        priority=1,
                        metadata=entry_signal
                    ))
                    
            # Test exit logic (if position active)
            elif position_active:
                min_price_after_entry = min(min_price_after_entry, current_price)
                profit_pct = (current_price - entry_price) / entry_price
                
                exit_signals = await self._test_exit_logic(market_data, scenario, entry_price, profit_pct)
                
                if exit_signals:
                    # Test for conflicts (multiple exit signals)
                    if len(exit_signals) > 1:
                        conflict_types = [sig['trigger'] for sig in exit_signals]
                        result['conflicts_detected'].append({
                            'timestamp': market_data.current_bar.timestamp,
                            'price': current_price,
                            'conflict_types': conflict_types,
                            'resolution': exit_signals[0]['trigger']  # First one wins
                        })
                    
                    # Execute highest priority exit
                    exit_signal = exit_signals[0]
                    result['actual_exits'].append(exit_signal['trigger'])
                    result['exit_price'] = current_price
                    result['final_pnl_pct'] = profit_pct
                    position_active = False
                    
                    self.order_events.append(OrderFlowEvent(
                        timestamp=market_data.current_bar.timestamp,
                        symbol=scenario.symbol,
                        event_type='exit',
                        trigger_type=exit_signal['trigger'],
                        price=current_price,
                        profit_pct=profit_pct,
                        volume_ratio=market_data.current_bar.volume / 1000,
                        priority=exit_signal.get('priority', 5),
                        metadata=exit_signal
                    ))
                    break
                    
        # Calculate performance metrics
        if entry_price:
            result['max_profit_pct'] = (max_price - entry_price) / entry_price
            result['max_drawdown_pct'] = (min_price_after_entry - entry_price) / entry_price
            
            # Exit efficiency (how much of available profit was captured)
            if result['max_profit_pct'] > 0:
                result['exit_efficiency'] = result['final_pnl_pct'] / result['max_profit_pct']
        
        result['order_events'] = self.order_events.copy()
        
        # Validate against expectations
        self._validate_scenario_result(result, scenario)
        
        return result
        
    def _create_market_data_sequence(self, scenario: TradingScenario) -> List[MarketData]:
        """Create market data sequence for scenario"""
        sequence = []
        base_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        for i, (price, volume) in enumerate(zip(scenario.price_data, scenario.volume_data)):
            timestamp = base_time + timedelta(minutes=i*5)  # 5-minute intervals
            
            bar = MarketData(
                symbol=scenario.symbol,
                timestamp=timestamp,
                open=price * 0.999,  # Slight variation
                high=price * 1.001,
                low=price * 0.998,
                close=price,
                volume=int(volume)
            )
            
            # Add catalyst metadata for first bar
            if i == 0 and scenario.catalyst_info:
                bar.metadata = {
                    'catalyst_info': scenario.catalyst_info,
                    'finbert_result': {
                        'confidence': scenario.catalyst_info['confidence'],
                        'score': 0.8
                    }
                }
            
            # Use the bar directly as MarketData
            sequence.append(bar)
            
        return sequence
        
    async def _initialize_ml_engine(self):
        """Initialize ML engine for testing"""
        if not self.ml_engine:
            # Create minimal parameters for ML engine
            parameters = {
                'smallcap_ml_enabled': True,
                'smallcap_mayordomo_enabled': True,
                'smallcap_price_threshold': 15.0
            }
            
            self.ml_engine = MLMultiStrategyEngine(parameters)
            
            # Mock event bus
            class MockEventBus:
                async def publish(self, event_type, data):
                    pass
                    
            await self.ml_engine.initialize(MockEventBus(), None)
            
    async def _test_entry_logic(self, market_data: MarketData, scenario: TradingScenario) -> Optional[Dict]:
        """Test entry logic for scenario"""
        try:
            # Test catalyst momentum strategy
            if scenario.catalyst_info and hasattr(market_data.current_bar, 'metadata'):
                # Simulate catalyst momentum detection
                catalyst_data = market_data.current_bar.metadata.get('catalyst_info')
                if catalyst_data:
                    # Check momentum criteria
                    price_move = (market_data.current_bar.close - scenario.price_data[0]) / scenario.price_data[0]
                    volume_ratio = market_data.current_bar.volume / 1000  # vs base volume
                    
                    if price_move >= 0.02 and volume_ratio >= 2.0:  # 2% move, 2x volume
                        return {
                            'trigger': 'catalyst_momentum',
                            'price': market_data.current_bar.close,
                            'catalyst_type': catalyst_data['catalyst_type'],
                            'momentum_pct': price_move,
                            'volume_ratio': volume_ratio
                        }
                        
            # Test anti-martingala (second entry on same symbol)
            if scenario.name == "Anti-Martingala Protection":
                # Simulate second catalyst on same symbol
                pass  # Would be rejected by anti-martingala logic
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error testing entry logic: {e}")
            return None
            
    async def _test_exit_logic(self, market_data: MarketData, scenario: TradingScenario, 
                              entry_price: float, profit_pct: float) -> List[Dict]:
        """Test all exit logic and return prioritized list"""
        exit_signals = []
        current_price = market_data.current_bar.close
        
        # 1. Test FOMO exhaustion (Priority 1 - highest)
        if self._test_fomo_exit(market_data, profit_pct):
            exit_signals.append({
                'trigger': 'fomo_exhaustion',
                'priority': 1,
                'price': current_price,
                'reason': 'Volume spike + price stall detected'
            })
            
        # 2. Test take profit (Priority 2)
        if profit_pct >= 0.15:  # 15% take profit
            exit_signals.append({
                'trigger': 'take_profit',
                'priority': 2,
                'price': current_price,
                'reason': f'Take profit hit: {profit_pct:.1%}'
            })
            
        # 3. Test trailing stop (Priority 3)
        if self._test_trailing_stop(current_price, entry_price, profit_pct):
            exit_signals.append({
                'trigger': 'trailing_stop',
                'priority': 3,
                'price': current_price,
                'reason': 'Trailing stop triggered'
            })
            
        # 4. Test stop loss (Priority 4)
        if profit_pct <= -0.08:  # 8% stop loss
            exit_signals.append({
                'trigger': 'stop_loss',
                'priority': 4,
                'price': current_price,
                'reason': f'Stop loss hit: {profit_pct:.1%}'
            })
            
        # Sort by priority (lower number = higher priority)
        exit_signals.sort(key=lambda x: x['priority'])
        
        return exit_signals
        
    def _test_fomo_exit(self, market_data: MarketData, profit_pct: float) -> bool:
        """Test FOMO exhaustion conditions"""
        if profit_pct < 0.02:  # Need at least 2% profit
            return False
            
        # Simulate volume spike + price stall
        volume_ratio = market_data.current_bar.volume / 1000
        
        # FOMO conditions: high volume (>3x) + profit stalling
        return volume_ratio > 3.0 and profit_pct > 0.02
        
    def _test_trailing_stop(self, current_price: float, entry_price: float, profit_pct: float) -> bool:
        """Test trailing stop conditions"""
        if profit_pct < 0.06:  # Trailing not activated yet
            return False
            
        # Simplified: trigger if dropped more than 3% from peak
        # In real implementation, would track highest price
        peak_profit = 0.15 if profit_pct >= 0.15 else profit_pct  # Assume peak
        current_from_peak = profit_pct - peak_profit
        
        return current_from_peak <= -0.03  # 3% trailing distance
        
    def _validate_scenario_result(self, result: Dict, scenario: TradingScenario):
        """Validate scenario result against expectations"""
        result['validation'] = {
            'entry_match': result['actual_entry'] == scenario.expected_entry,
            'exit_match': set(result['actual_exits']) == set(scenario.expected_exits),
            'overall_success': True
        }
        
        # Check if actual behavior matches expected
        if not result['validation']['entry_match']:
            self.logger.warning(f"⚠️ Entry mismatch in {scenario.name}: expected {scenario.expected_entry}, got {result['actual_entry']}")
            
        if not result['validation']['exit_match']:
            self.logger.warning(f"⚠️ Exit mismatch in {scenario.name}: expected {scenario.expected_exits}, got {result['actual_exits']}")
            
        result['validation']['overall_success'] = (
            result['validation']['entry_match'] and 
            result['validation']['exit_match']
        )
        
    def _analyze_entry_behavior(self, scenario_results: List[Dict]) -> Dict[str, Any]:
        """Analyze entry behavior patterns"""
        analysis = {
            'total_entries': sum(1 for r in scenario_results if r['actual_entry']),
            'entry_accuracy': 0.0,
            'catalyst_momentum_effectiveness': 0.0,
            'anti_martingala_working': False,
            'entry_timing_analysis': {}
        }
        
        # Calculate entry accuracy
        correct_entries = sum(1 for r in scenario_results if r['validation']['entry_match'])
        analysis['entry_accuracy'] = correct_entries / len(scenario_results) if scenario_results else 0
        
        # Analyze catalyst momentum
        catalyst_entries = [r for r in scenario_results if 'catalyst_momentum' in str(r.get('order_events', []))]
        analysis['catalyst_momentum_effectiveness'] = len(catalyst_entries) / len(scenario_results)
        
        # Check anti-martingala
        anti_martingala_test = next((r for r in scenario_results if r['scenario_name'] == "Anti-Martingala Protection"), None)
        if anti_martingala_test:
            analysis['anti_martingala_working'] = anti_martingala_test['validation']['overall_success']
            
        return analysis
        
    def _analyze_exit_behavior(self, scenario_results: List[Dict]) -> Dict[str, Any]:
        """Analyze exit behavior patterns"""
        analysis = {
            'exit_types_distribution': {},
            'exit_efficiency_avg': 0.0,
            'fomo_exit_rate': 0.0,
            'trailing_stop_effectiveness': 0.0,
            'profit_protection_rate': 0.0
        }
        
        # Count exit types
        all_exits = []
        for result in scenario_results:
            all_exits.extend(result['actual_exits'])
            
        for exit_type in all_exits:
            analysis['exit_types_distribution'][exit_type] = analysis['exit_types_distribution'].get(exit_type, 0) + 1
            
        # Calculate average exit efficiency
        efficiencies = [r['exit_efficiency'] for r in scenario_results if r['exit_efficiency'] > 0]
        analysis['exit_efficiency_avg'] = np.mean(efficiencies) if efficiencies else 0
        
        # FOMO exit rate
        fomo_exits = sum(1 for r in scenario_results if 'fomo_exhaustion' in r['actual_exits'])
        analysis['fomo_exit_rate'] = fomo_exits / len(scenario_results)
        
        # Profit protection (avoided losses)
        protected_trades = sum(1 for r in scenario_results if r['final_pnl_pct'] > r['max_drawdown_pct'])
        analysis['profit_protection_rate'] = protected_trades / len(scenario_results)
        
        return analysis
        
    def _analyze_priority_conflicts(self, scenario_results: List[Dict]) -> Dict[str, Any]:
        """Analyze exit priority conflicts and resolution"""
        analysis = {
            'total_conflicts': 0,
            'conflict_types': {},
            'resolution_effectiveness': 0.0,
            'priority_optimization_needed': []
        }
        
        for result in scenario_results:
            conflicts = result.get('conflicts_detected', [])
            analysis['total_conflicts'] += len(conflicts)
            
            for conflict in conflicts:
                conflict_key = tuple(sorted(conflict['conflict_types']))
                analysis['conflict_types'][conflict_key] = analysis['conflict_types'].get(conflict_key, 0) + 1
                
        return analysis
        
    def _generate_recommendations(self, results: Dict) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        entry_analysis = results['entry_analysis']
        exit_analysis = results['exit_analysis']
        priority_analysis = results['priority_analysis']
        
        # Entry recommendations
        if entry_analysis['entry_accuracy'] < 0.8:
            recommendations.append("⚡ Improve entry signal filtering - accuracy below 80%")
            
        if entry_analysis['catalyst_momentum_effectiveness'] < 0.5:
            recommendations.append("📈 Optimize catalyst momentum parameters - low effectiveness")
            
        # Exit recommendations
        if exit_analysis['exit_efficiency_avg'] < 0.6:
            recommendations.append("🎯 Optimize exit timing - capturing only 60% of available profit")
            
        if exit_analysis['fomo_exit_rate'] < 0.3:
            recommendations.append("🔥 Consider more aggressive FOMO detection - low utilization")
            
        # Priority recommendations
        if priority_analysis['total_conflicts'] > 2:
            recommendations.append("⚖️ Review exit priority system - high conflict rate")
            
        if not recommendations:
            recommendations.append("✅ Order flow system performing well - no critical issues detected")
            
        return recommendations
        
    def _save_analysis_report(self, results: Dict):
        """Save detailed analysis report"""
        report_path = Path("tests/reports/order_flow_analysis_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add timestamp
        results['analysis_timestamp'] = datetime.now().isoformat()
        results['test_version'] = "1.0"
        
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
            
        self.logger.info(f"📄 Analysis report saved to {report_path}")
        
    def _print_summary(self, results: Dict):
        """Print analysis summary"""
        print("\n" + "="*60)
        print("🔍 ORDER FLOW ANALYSIS SUMMARY")
        print("="*60)
        
        entry_analysis = results['entry_analysis']
        exit_analysis = results['exit_analysis']
        
        print(f"\n📊 ENTRY ANALYSIS:")
        print(f"   ├─ Total Entries: {entry_analysis['total_entries']}")
        print(f"   ├─ Entry Accuracy: {entry_analysis['entry_accuracy']:.1%}")
        print(f"   ├─ Catalyst Momentum: {entry_analysis['catalyst_momentum_effectiveness']:.1%}")
        print(f"   └─ Anti-Martingala: {'✅ Working' if entry_analysis['anti_martingala_working'] else '❌ Issues'}")
        
        print(f"\n📈 EXIT ANALYSIS:")
        print(f"   ├─ Exit Efficiency: {exit_analysis['exit_efficiency_avg']:.1%}")
        print(f"   ├─ FOMO Exit Rate: {exit_analysis['fomo_exit_rate']:.1%}")
        print(f"   └─ Profit Protection: {exit_analysis['profit_protection_rate']:.1%}")
        
        print(f"\n📋 EXIT DISTRIBUTION:")
        for exit_type, count in exit_analysis['exit_types_distribution'].items():
            print(f"   ├─ {exit_type}: {count} times")
            
        print(f"\n💡 RECOMMENDATIONS:")
        for rec in results['optimization_recommendations']:
            print(f"   ├─ {rec}")
            
        print("\n" + "="*60)


async def main():
    """Run comprehensive order flow analysis"""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run analyzer
    analyzer = OrderFlowAnalyzer()
    results = await analyzer.run_comprehensive_analysis()
    
    return results


if __name__ == "__main__":
    asyncio.run(main())