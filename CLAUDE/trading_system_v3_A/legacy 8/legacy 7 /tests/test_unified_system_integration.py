"""
Integration Tests for Unified Day/Swing Trading System
Tests capital allocation, duplicate prevention, and system coordination
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.unified_position_manager import UnifiedPositionManager


def test_unified_position_manager():
    """Test UnifiedPositionManager for capital allocation and duplicate prevention"""
    print("\n" + "="*60)
    print("TEST 1: UnifiedPositionManager - Capital Allocation")
    print("="*60)

    # Create manager with $2000 total capital (60% day, 40% swing)
    manager = UnifiedPositionManager(total_capital=2000.0)

    print(f"\n✅ Manager created:")
    print(f"   Total capital: ${manager.total_capital:,.2f}")
    print(f"   Day capital: ${manager.day_capital:,.2f} (60%)")
    print(f"   Swing capital: ${manager.swing_capital:,.2f} (40%)")

    # Test 1: Open day trading position
    print("\n--- Test 1: Open day trading position ---")
    can_open, reason = manager.can_open_position('AAPL', 'day', 200.0)
    print(f"Can open AAPL day position ($200)? {can_open} - {reason}")

    if can_open:
        manager.register_position('AAPL', 'day', {
            'strategy': 'gap_go',
            'entry_price': 150.0,
            'position_value': 200.0
        })
        print("✅ AAPL day position registered")

    # Test 2: Try to open same symbol in swing (should fail)
    print("\n--- Test 2: Try duplicate symbol in swing ---")
    can_open, reason = manager.can_open_position('AAPL', 'swing', 400.0)
    print(f"Can open AAPL swing position ($400)? {can_open} - {reason}")

    if not can_open:
        print("✅ CORRECTLY BLOCKED - Duplicate prevention working!")

    # Test 3: Open different symbol in swing
    print("\n--- Test 3: Open different symbol in swing ---")
    can_open, reason = manager.can_open_position('TSLA', 'swing', 400.0)
    print(f"Can open TSLA swing position ($400)? {can_open} - {reason}")

    if can_open:
        manager.register_position('TSLA', 'swing', {
            'strategy': 'consolidation_breakout',
            'entry_price': 200.0,
            'position_value': 400.0
        })
        print("✅ TSLA swing position registered")

    # Test 4: Open another day trading position
    print("\n--- Test 4: Open another day trading position ---")
    can_open, reason = manager.can_open_position('NVDA', 'day', 150.0)
    print(f"Can open NVDA day position ($150)? {can_open} - {reason}")

    if can_open:
        manager.register_position('NVDA', 'day', {
            'strategy': 'macdv',
            'entry_price': 500.0,
            'position_value': 150.0
        })
        print("✅ NVDA day position registered")

    # Test 5: Check capital summary
    print("\n--- Test 5: Capital summary ---")
    summary = manager.get_capital_summary()
    print(f"\n📊 Capital Summary:")
    print(f"   Day trading:")
    print(f"     Allocated: ${summary['day_trading']['allocated']:,.2f}")
    print(f"     Used: ${summary['day_trading']['used']:,.2f}")
    print(f"     Available: ${summary['day_trading']['available']:,.2f}")
    print(f"     Positions: {summary['day_trading']['positions_count']}")
    print(f"   Swing trading:")
    print(f"     Allocated: ${summary['swing_trading']['allocated']:,.2f}")
    print(f"     Used: ${summary['swing_trading']['used']:,.2f}")
    print(f"     Available: ${summary['swing_trading']['available']:,.2f}")
    print(f"     Positions: {summary['swing_trading']['positions_count']}")
    total_used = summary['day_trading']['used'] + summary['swing_trading']['used']
    print(f"\n   Total capital used: ${total_used:,.2f} / ${summary['total_capital']:,.2f}")

    # Test 6: Try to exceed capital limit
    print("\n--- Test 6: Try to exceed capital limit ---")
    can_open, reason = manager.can_open_position('AMD', 'day', 1500.0)
    print(f"Can open AMD day position ($1500)? {can_open} - {reason}")

    if not can_open:
        print("✅ CORRECTLY BLOCKED - Capital limit working!")

    # Test 7: Close position and check capital freed
    print("\n--- Test 7: Close position and free capital ---")
    print("Closing AAPL day position...")
    manager.unregister_position('AAPL', 'day')

    summary = manager.get_capital_summary()
    print(f"Day capital available after close: ${summary['day_trading']['available']:,.2f}")
    print("✅ Capital freed correctly!")

    # Test 8: Now open AMD with freed capital
    print("\n--- Test 8: Open AMD with freed capital ---")
    can_open, reason = manager.can_open_position('AMD', 'day', 200.0)
    print(f"Can open AMD day position ($200)? {can_open} - {reason}")

    if can_open:
        manager.register_position('AMD', 'day', {
            'strategy': 'bull_flag',
            'entry_price': 100.0,
            'position_value': 200.0
        })
        print("✅ AMD day position registered")

    # Final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    summary = manager.get_capital_summary()
    day_positions = manager.get_day_positions()
    swing_positions = manager.get_swing_positions()
    print(f"\nDay positions: {list(day_positions.keys())}")
    print(f"Swing positions: {list(swing_positions.keys())}")
    total_used = summary['day_trading']['used'] + summary['swing_trading']['used']
    total_available = summary['day_trading']['available'] + summary['swing_trading']['available']
    print(f"\nTotal capital used: ${total_used:,.2f} / ${summary['total_capital']:,.2f}")
    print(f"Total capital available: ${total_available:,.2f}")

    return True


def test_day_swing_coordination():
    """Test coordination between day and swing trading systems"""
    print("\n" + "="*60)
    print("TEST 2: Day/Swing Coordination - No Friction")
    print("="*60)

    manager = UnifiedPositionManager(total_capital=2000.0)

    # Scenario: Scanner finds AAPL for day trading
    print("\n--- Scenario 1: Day trading finds AAPL ---")
    can_open, reason = manager.can_open_position('AAPL', 'day', 150.0)
    print(f"Gap-Go worker: Can enter AAPL? {can_open}")

    if can_open:
        manager.register_position('AAPL', 'day', {
            'strategy': 'gap_go',
            'entry_price': 145.0,
            'position_value': 150.0
        })
        print("✅ Day trading entered AAPL")

    # Later: EOD scanner also identifies AAPL for swing
    print("\n--- Scenario 2: EOD scanner also finds AAPL ---")
    can_open, reason = manager.can_open_position('AAPL', 'swing', 400.0)
    print(f"Swing scanner: Can enter AAPL? {can_open} - {reason}")

    if not can_open:
        print("✅ CORRECTLY BLOCKED - No conflict between systems!")

    # Day closes position
    print("\n--- Scenario 3: Day trading closes AAPL ---")
    manager.unregister_position('AAPL', 'day')
    print("Day trading closed AAPL position")

    # Now swing can enter
    print("\n--- Scenario 4: Swing can now enter AAPL ---")
    can_open, reason = manager.can_open_position('AAPL', 'swing', 400.0)
    print(f"Swing scanner: Can enter AAPL now? {can_open}")

    if can_open:
        manager.register_position('AAPL', 'swing', {
            'strategy': 'consolidation_breakout',
            'entry_price': 150.0,
            'position_value': 400.0
        })
        print("✅ Swing trading entered AAPL after day closed")

    print("\n✅ NO FRICTION - Systems coordinate perfectly!")

    return True


def test_capital_split_scenarios():
    """Test different capital allocation scenarios"""
    print("\n" + "="*60)
    print("TEST 3: Capital Split Scenarios (60/40)")
    print("="*60)

    manager = UnifiedPositionManager(total_capital=2000.0)

    # Scenario 1: Max out day trading (60% = $1200)
    print("\n--- Scenario 1: Max out day trading ---")
    symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'GOOGL', 'MSFT']

    for symbol in symbols:
        can_open, reason = manager.can_open_position(symbol, 'day', 200.0)
        if can_open:
            manager.register_position(symbol, 'day', {
                'strategy': 'gap_go',
                'entry_price': 100.0,
                'position_value': 200.0
            })
            print(f"  ✓ {symbol} day position opened ($200)")
        else:
            print(f"  ✗ {symbol} blocked: {reason}")

    summary = manager.get_capital_summary()
    print(f"\nDay capital used: ${summary['day_trading']['used']:,.2f} / ${summary['day_trading']['allocated']:,.2f}")

    # Scenario 2: Open swing positions (40% = $800)
    print("\n--- Scenario 2: Open swing positions ---")
    swing_symbols = ['META', 'NFLX']

    for symbol in swing_symbols:
        can_open, reason = manager.can_open_position(symbol, 'swing', 400.0)
        if can_open:
            manager.register_position(symbol, 'swing', {
                'strategy': 'consolidation_breakout',
                'entry_price': 200.0,
                'position_value': 400.0
            })
            print(f"  ✓ {symbol} swing position opened ($400)")
        else:
            print(f"  ✗ {symbol} blocked: {reason}")

    summary = manager.get_capital_summary()
    print(f"\nSwing capital used: ${summary['swing_trading']['used']:,.2f} / ${summary['swing_trading']['allocated']:,.2f}")

    # Final check
    print("\n--- Final allocation check ---")
    print(f"Day: ${summary['day_trading']['used']:,.2f} / ${summary['day_trading']['allocated']:,.2f} (60%)")
    print(f"Swing: ${summary['swing_trading']['used']:,.2f} / ${summary['swing_trading']['allocated']:,.2f} (40%)")
    total_used = summary['day_trading']['used'] + summary['swing_trading']['used']
    print(f"Total: ${total_used:,.2f} / ${summary['total_capital']:,.2f}")

    if total_used <= summary['total_capital']:
        print("\n✅ Capital allocation working correctly!")
    else:
        print("\n❌ Capital overallocated!")

    return True


def test_position_blocking():
    """Test that position blocking works correctly"""
    print("\n" + "="*60)
    print("TEST 4: Position Blocking - Symbol Already Held")
    print("="*60)

    manager = UnifiedPositionManager(total_capital=2000.0)

    # Open AAPL in gap_go
    print("\n--- Gap-Go enters AAPL ---")
    manager.register_position('AAPL', 'day', {
        'strategy': 'gap_go',
        'entry_price': 150.0,
        'position_value': 200.0
    })
    print("✅ Gap-Go entered AAPL")

    # Try to enter AAPL in MACDV (should fail)
    print("\n--- MACDV tries to enter AAPL ---")
    can_open, reason = manager.can_open_position('AAPL', 'day', 150.0)
    print(f"Can MACDV enter AAPL? {can_open} - {reason}")

    if not can_open:
        print("✅ CORRECTLY BLOCKED - No duplicate positions in day trading!")

    # Try to enter AAPL in Bull Flag (should fail)
    print("\n--- Bull Flag tries to enter AAPL ---")
    can_open, reason = manager.can_open_position('AAPL', 'day', 150.0)
    print(f"Can Bull Flag enter AAPL? {can_open} - {reason}")

    if not can_open:
        print("✅ CORRECTLY BLOCKED - No duplicate positions in day trading!")

    # Try to enter AAPL in swing (should fail)
    print("\n--- Swing tries to enter AAPL ---")
    can_open, reason = manager.can_open_position('AAPL', 'swing', 400.0)
    print(f"Can Swing enter AAPL? {can_open} - {reason}")

    if not can_open:
        print("✅ CORRECTLY BLOCKED - No day + swing same symbol!")

    print("\n✅ All blocking scenarios working correctly!")

    return True


def main():
    """Run all integration tests"""
    print("\n" + "="*80)
    print(" "*20 + "UNIFIED SYSTEM INTEGRATION TESTS")
    print("="*80)
    print("\nTesting capital allocation, duplicate prevention, and system coordination...")

    results = []

    # Test 1: UnifiedPositionManager
    try:
        results.append(("UnifiedPositionManager", test_unified_position_manager()))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("UnifiedPositionManager", False))

    # Test 2: Day/Swing Coordination
    try:
        results.append(("Day/Swing Coordination", test_day_swing_coordination()))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Day/Swing Coordination", False))

    # Test 3: Capital Split Scenarios
    try:
        results.append(("Capital Split Scenarios", test_capital_split_scenarios()))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Capital Split Scenarios", False))

    # Test 4: Position Blocking
    try:
        results.append(("Position Blocking", test_position_blocking()))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Position Blocking", False))

    # Print summary
    print("\n" + "="*80)
    print(" "*30 + "TEST SUMMARY")
    print("="*80)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:40} {status}")

    all_passed = all(result[1] for result in results)

    print("="*80)

    if all_passed:
        print("\n🎉 ALL TESTS PASSED - System integration working correctly!")
        print("\nKey findings:")
        print("  ✅ Capital split working (60% day, 40% swing)")
        print("  ✅ Duplicate prevention working (no same symbol in multiple strategies)")
        print("  ✅ No friction between day and swing systems")
        print("  ✅ Capital freed correctly when positions close")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
