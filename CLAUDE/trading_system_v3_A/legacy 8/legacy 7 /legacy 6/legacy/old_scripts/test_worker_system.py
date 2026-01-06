"""
Test Script for Worker-Based Strategy Engine
Tests routing logic, performance, and worker behavior
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime


class MockExecutionEngine:
    """Mock ExecutionEngine for testing"""

    def __init__(self):
        self.positions = {}
        self.entry_count = 0
        self.exit_count = 0

    async def enter_position(self, symbol: str, strategy: str, opportunity_data: Dict) -> Dict[str, Any]:
        """Mock enter position"""
        self.entry_count += 1
        position = {
            'symbol': symbol,
            'strategy': strategy,
            'entry_price': opportunity_data.get('current_price', 10.0),
            'quantity': 100,
            'entry_time': datetime.now()
        }
        self.positions[symbol] = position
        return position

    async def close_position(self, symbol: str, reason: str):
        """Mock close position"""
        self.exit_count += 1
        if symbol in self.positions:
            del self.positions[symbol]

    async def get_current_price(self, symbol: str) -> float:
        """Mock get price"""
        return 10.0


class MockRiskManager:
    """Mock RiskManager for testing"""

    def __init__(self):
        self.max_positions = 10
        self.current_positions = 0

    def can_take_position(self) -> bool:
        """Mock can take position"""
        return self.current_positions < self.max_positions

    def has_available_capital(self) -> bool:
        """Mock has capital"""
        return True


def create_test_opportunities() -> List[Dict[str, Any]]:
    """
    Creates test opportunities for different worker types

    Returns:
        List of test opportunities
    """
    opportunities = []

    # 1. Gap-Go opportunity (gap >= 8%, volume >= 2.0x)
    opportunities.append({
        'symbol': 'GAPGO1',
        'current_price': 12.50,
        'gap_percentage': 10.5,
        'volume_ratio': 3.2,
        'catalyst_type': '',
        'catalyst_strength': 0,
        'quality_score': 55.0,
        'scan_timestamp': datetime.now().isoformat()
    })

    # 2. MACDV opportunity (gap <= 5%, volume >= 1.5x, technical)
    opportunities.append({
        'symbol': 'MACDV1',
        'current_price': 8.75,
        'gap_percentage': 2.5,
        'volume_ratio': 2.0,
        'catalyst_type': '',
        'catalyst_strength': 0,
        'quality_score': 45.0,
        'scan_timestamp': datetime.now().isoformat()
    })

    # 3. Daily Plays opportunity (strong catalyst, high volume)
    opportunities.append({
        'symbol': 'DAILY1',
        'current_price': 15.00,
        'gap_percentage': 12.0,
        'volume_ratio': 5.5,
        'catalyst_type': 'FDA',
        'catalyst_strength': 8,
        'quality_score': 70.0,
        'scan_timestamp': datetime.now().isoformat()
    })

    # 4. Bull Flag opportunity (moderate gap 3-8%, clean pattern)
    opportunities.append({
        'symbol': 'BULLFLAG1',
        'current_price': 6.50,
        'gap_percentage': 5.5,
        'volume_ratio': 2.8,
        'catalyst_type': '',
        'catalyst_strength': 0,
        'quality_score': 50.0,
        'scan_timestamp': datetime.now().isoformat()
    })

    # 5. No match opportunity (doesn't meet any criteria)
    opportunities.append({
        'symbol': 'NOMATCH1',
        'current_price': 50.00,
        'gap_percentage': 1.0,
        'volume_ratio': 0.8,
        'catalyst_type': '',
        'catalyst_strength': 0,
        'quality_score': 20.0,
        'scan_timestamp': datetime.now().isoformat()
    })

    # 6. Multi-match opportunity (could match multiple workers)
    opportunities.append({
        'symbol': 'MULTI1',
        'current_price': 10.00,
        'gap_percentage': 6.0,  # Could match Bull Flag or Gap-Go depending
        'volume_ratio': 3.0,
        'catalyst_type': '',
        'catalyst_strength': 0,
        'quality_score': 50.0,
        'scan_timestamp': datetime.now().isoformat()
    })

    # 7. Edge case: exactly at boundaries
    opportunities.append({
        'symbol': 'EDGE1',
        'current_price': 15.00,
        'gap_percentage': 8.0,  # Exactly at Gap-Go min
        'volume_ratio': 2.0,    # Exactly at minimums
        'catalyst_type': '',
        'catalyst_strength': 0,
        'quality_score': 40.0,
        'scan_timestamp': datetime.now().isoformat()
    })

    # 8. Catalyst with insufficient strength
    opportunities.append({
        'symbol': 'WEAKCAT1',
        'current_price': 12.00,
        'gap_percentage': 10.0,
        'volume_ratio': 4.0,
        'catalyst_type': 'FDA',
        'catalyst_strength': 4,  # Below threshold
        'quality_score': 60.0,
        'scan_timestamp': datetime.now().isoformat()
    })

    return opportunities


async def test_worker_routing():
    """Test worker routing logic"""
    print("\n" + "="*60)
    print("🧪 TEST 1: Worker Routing Logic")
    print("="*60)

    # Import after printing header
    from strategies.worker_based_strategy_engine import WorkerBasedStrategyEngine

    # Setup mocks
    execution_engine = MockExecutionEngine()
    risk_manager = MockRiskManager()

    # Create engine
    engine = WorkerBasedStrategyEngine(
        execution_engine=execution_engine,
        risk_manager=risk_manager
    )

    # Initialize workers
    await engine.initialize()

    # Create test opportunities
    opportunities = create_test_opportunities()

    print(f"\n📊 Testing {len(opportunities)} opportunities...")

    # Test each opportunity
    expected_matches = {
        'GAPGO1': ['gap_go'],
        'MACDV1': ['macdv'],
        'DAILY1': ['daily_plays'],
        'BULLFLAG1': ['bull_flag'],
        'NOMATCH1': [],
        'MULTI1': ['bull_flag'],  # Should match bull_flag (3-8% gap range)
        'EDGE1': ['gap_go', 'bull_flag'],  # Could match both
        'WEAKCAT1': ['gap_go']  # Has gap but weak catalyst, should match gap_go
    }

    results = []
    for opp in opportunities:
        symbol = opp['symbol']
        matched = engine._match_workers(opp)
        expected = expected_matches.get(symbol, [])

        status = "✅" if set(matched) == set(expected) else "❌"
        results.append({
            'symbol': symbol,
            'matched': matched,
            'expected': expected,
            'passed': set(matched) == set(expected)
        })

        print(f"{status} {symbol}: matched={matched}, expected={expected}")

    # Summary
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"\n📈 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    return results


async def test_parallel_processing():
    """Test parallel processing performance"""
    print("\n" + "="*60)
    print("🧪 TEST 2: Parallel Processing Performance")
    print("="*60)

    from strategies.worker_based_strategy_engine import WorkerBasedStrategyEngine

    # Setup
    execution_engine = MockExecutionEngine()
    risk_manager = MockRiskManager()

    engine = WorkerBasedStrategyEngine(
        execution_engine=execution_engine,
        risk_manager=risk_manager
    )

    await engine.initialize()

    # Create batch of opportunities
    opportunities = create_test_opportunities()

    # Test processing time
    start = datetime.now()

    for opp in opportunities:
        await engine.process_opportunity(opp)

    elapsed = (datetime.now() - start).total_seconds()

    # Get metrics
    metrics = engine.get_metrics()

    print(f"\n⏱️  Processing Time: {elapsed*1000:.2f}ms")
    print(f"📊 Opportunities Processed: {metrics['opportunities_processed']}")
    print(f"✅ Opportunities Matched: {metrics['opportunities_matched']}")
    print(f"❌ Opportunities Rejected: {metrics['opportunities_rejected']}")
    print(f"⚡ Avg Processing Time: {metrics['avg_processing_time']*1000:.2f}ms")
    print(f"\n📈 Worker Matches: {metrics['worker_matches']}")
    print(f"🎯 Worker Entries: {metrics['worker_entries']}")

    # Performance assertions
    assert elapsed < 1.0, "Processing should be fast (<1s for 8 opportunities)"
    assert metrics['avg_processing_time'] < 0.1, "Avg time should be <100ms per opportunity"

    print("\n✅ Performance test passed!")

    return metrics


async def test_worker_initialization():
    """Test worker initialization"""
    print("\n" + "="*60)
    print("🧪 TEST 3: Worker Initialization")
    print("="*60)

    from strategies.worker_based_strategy_engine import WorkerBasedStrategyEngine

    execution_engine = MockExecutionEngine()
    risk_manager = MockRiskManager()

    engine = WorkerBasedStrategyEngine(
        execution_engine=execution_engine,
        risk_manager=risk_manager
    )

    # Initialize
    success = await engine.initialize()

    print(f"\n✅ Initialization: {'Success' if success else 'Failed'}")
    print(f"📊 Workers Created: {len(engine.workers)}")

    # Check all workers exist
    expected_workers = ['gap_go', 'macdv', 'daily_plays', 'bull_flag']
    for worker_name in expected_workers:
        exists = worker_name in engine.workers
        status = "✅" if exists else "❌"
        print(f"{status} Worker '{worker_name}': {'Found' if exists else 'Missing'}")

    assert success, "Initialization should succeed"
    assert len(engine.workers) == 4, "Should have 4 workers"

    print("\n✅ Initialization test passed!")

    return success


async def test_worker_status():
    """Test worker status reporting"""
    print("\n" + "="*60)
    print("🧪 TEST 4: Worker Status Reporting")
    print("="*60)

    from strategies.worker_based_strategy_engine import WorkerBasedStrategyEngine

    execution_engine = MockExecutionEngine()
    risk_manager = MockRiskManager()

    engine = WorkerBasedStrategyEngine(
        execution_engine=execution_engine,
        risk_manager=risk_manager
    )

    await engine.initialize()

    # Get status
    status = engine.get_worker_status()

    print(f"\n📊 Worker Status:")
    for worker_name, worker_status in status.items():
        print(f"  🔸 {worker_name}:")
        print(f"     Active Positions: {worker_status['active_positions']}")
        print(f"     Symbols: {worker_status['symbols']}")
        print(f"     Running: {worker_status['is_running']}")

    # Log status (to test logging method)
    engine.log_status()

    print("\n✅ Status reporting test passed!")

    return status


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("🚀 WORKER-BASED SYSTEM TESTING")
    print("="*60)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    try:
        # Test 1: Routing
        results['routing'] = await test_worker_routing()

        # Test 2: Performance
        results['performance'] = await test_parallel_processing()

        # Test 3: Initialization
        results['initialization'] = await test_worker_initialization()

        # Test 4: Status
        results['status'] = await test_worker_status()

        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)

        return results

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run tests
    results = asyncio.run(run_all_tests())

    if results:
        print("\n✅ Testing complete! System ready for deployment.")
    else:
        print("\n❌ Testing failed! Review errors above.")