"""
Test Swing Position Restoration
Verifies that swing positions are correctly restored after trader restart
"""

import sys
import os
import sqlite3
from datetime import datetime, date

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.swing_scheduler import SwingScheduler


def setup_test_database():
    """Create test database with active swing position"""
    db_path = "test_trading_data.db"

    # Remove existing test database
    if os.path.exists(db_path):
        os.remove(db_path)

    # Create database with swing_trades table
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create swing_trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS swing_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            strategy TEXT DEFAULT 'swing_consolidation_breakout',
            scan_date DATE NOT NULL,
            entry_date DATE,
            entry_price REAL,
            quantity INTEGER,
            consolidation_days INTEGER,
            resistance_level REAL,
            support_level REAL,
            breakout_score REAL,
            pattern_type TEXT,
            exit_date DATE,
            exit_price REAL,
            exit_reason TEXT,
            pnl_gross REAL,
            pnl_net REAL,
            pnl_percentage REAL,
            days_held INTEGER,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert test active position
    test_date = date.today()
    cursor.execute("""
        INSERT INTO swing_trades (
            trade_id, symbol, scan_date, entry_date, entry_price, quantity,
            resistance_level, support_level, pattern_type, breakout_score,
            status, created_at
        ) VALUES (
            'TEST_AAPL_001', 'AAPL', ?, ?, 150.00, 2,
            155.00, 145.00, 'ASCENDING_TRIANGLE', 85.5,
            'ACTIVE', ?
        )
    """, (test_date, test_date, datetime.now()))

    cursor.execute("""
        INSERT INTO swing_trades (
            trade_id, symbol, scan_date, entry_date, entry_price, quantity,
            resistance_level, support_level, pattern_type, breakout_score,
            status, created_at
        ) VALUES (
            'TEST_TSLA_002', 'TSLA', ?, ?, 200.00, 1,
            210.00, 190.00, 'BULL_FLAG', 75.0,
            'ACTIVE', ?
        )
    """, (test_date, test_date, datetime.now()))

    conn.commit()
    conn.close()

    print(f"✅ Test database created: {db_path}")
    print(f"   - AAPL: $150.00 x 2 (ASCENDING_TRIANGLE)")
    print(f"   - TSLA: $200.00 x 1 (BULL_FLAG)")

    return db_path


def test_restoration():
    """Test swing position restoration"""
    print("\n" + "="*60)
    print("TEST: Swing Position Restoration After Restart")
    print("="*60)

    # Setup test database
    db_path = setup_test_database()

    # Create mock scanner and worker
    class MockScanner:
        pass

    class MockWorker:
        pass

    scanner = MockScanner()
    worker = MockWorker()

    # Create SwingScheduler (will trigger restoration in __init__)
    print("\n📅 Creating SwingScheduler (simulating restart)...")
    scheduler = SwingScheduler(scanner, worker)

    # Override db_path to use test database
    scheduler.db_path = db_path

    # Manually trigger restoration (since we set db_path after init)
    print("\n🔄 Restoring positions from database...")
    scheduler._restore_active_positions()

    # Verify restoration
    print("\n" + "-"*60)
    print("VERIFICATION")
    print("-"*60)

    success = True

    # Check 1: Active positions restored
    if len(scheduler.active_positions) == 2:
        print(f"✅ Active positions count: {len(scheduler.active_positions)} (expected: 2)")
    else:
        print(f"❌ Active positions count: {len(scheduler.active_positions)} (expected: 2)")
        success = False

    # Check 2: AAPL position
    if 'AAPL' in scheduler.active_positions:
        aapl = scheduler.active_positions['AAPL']
        print(f"✅ AAPL position restored:")
        print(f"   - Entry: ${aapl['entry_price']:.2f}")
        print(f"   - Quantity: {aapl['quantity']}")
        print(f"   - Pattern: {aapl['pattern_type']}")
        print(f"   - Support: ${aapl['support']:.2f}")
        print(f"   - Resistance: ${aapl['resistance']:.2f}")

        # Verify values
        if aapl['entry_price'] != 150.00:
            print(f"   ❌ Entry price mismatch: {aapl['entry_price']} != 150.00")
            success = False
        if aapl['quantity'] != 2:
            print(f"   ❌ Quantity mismatch: {aapl['quantity']} != 2")
            success = False
    else:
        print("❌ AAPL position NOT restored")
        success = False

    # Check 3: TSLA position
    if 'TSLA' in scheduler.active_positions:
        tsla = scheduler.active_positions['TSLA']
        print(f"✅ TSLA position restored:")
        print(f"   - Entry: ${tsla['entry_price']:.2f}")
        print(f"   - Quantity: {tsla['quantity']}")
        print(f"   - Pattern: {tsla['pattern_type']}")

        # Verify values
        if tsla['entry_price'] != 200.00:
            print(f"   ❌ Entry price mismatch: {tsla['entry_price']} != 200.00")
            success = False
        if tsla['quantity'] != 1:
            print(f"   ❌ Quantity mismatch: {tsla['quantity']} != 1")
            success = False
    else:
        print("❌ TSLA position NOT restored")
        success = False

    # Check 4: Required fields present
    print("\n📋 Checking required fields...")
    required_fields = ['entry_price', 'quantity', 'entry_time', 'support', 'resistance', 'pattern_type', 'strategy_type']

    for symbol, pos in scheduler.active_positions.items():
        missing = [field for field in required_fields if field not in pos]
        if missing:
            print(f"❌ {symbol}: Missing fields: {missing}")
            success = False
        else:
            print(f"✅ {symbol}: All required fields present")

    # Cleanup
    os.remove(db_path)
    print(f"\n🗑️  Test database removed: {db_path}")

    # Final result
    print("\n" + "="*60)
    if success:
        print("🎉 ALL TESTS PASSED - Restoration working correctly!")
        print("\nKey findings:")
        print("  ✅ Positions restored from database")
        print("  ✅ All required fields present")
        print("  ✅ Position data accurate")
        print("  ✅ Ready for monitoring and exit management")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Review errors above")
        return 1


def test_reregistration():
    """Test re-registration with UnifiedPositionManager"""
    print("\n" + "="*60)
    print("TEST: UnifiedPositionManager Re-registration")
    print("="*60)

    from core.unified_position_manager import UnifiedPositionManager

    # Create test positions
    test_positions = {
        'AAPL': {
            'symbol': 'AAPL',
            'entry_price': 150.0,
            'quantity': 2,
            'support': 145.0,
            'resistance': 155.0,
            'pattern_type': 'ASCENDING_TRIANGLE',
            'strategy_type': 'swing'
        },
        'TSLA': {
            'symbol': 'TSLA',
            'entry_price': 200.0,
            'quantity': 1,
            'support': 190.0,
            'resistance': 210.0,
            'pattern_type': 'BULL_FLAG',
            'strategy_type': 'swing'
        }
    }

    # Create UnifiedPositionManager
    manager = UnifiedPositionManager(total_capital=2000.0)

    # Simulate restoration and re-registration
    print("\n💼 Re-registering positions with UnifiedPositionManager...")

    for symbol, pos in test_positions.items():
        position_value = pos['entry_price'] * pos['quantity']

        success = manager.register_position(
            symbol=symbol,
            strategy_type='swing',
            position_data=pos
        )

        if success:
            print(f"   ✅ {symbol}: Registered (${position_value:.2f})")
        else:
            print(f"   ❌ {symbol}: Registration failed")

    # Verify blocking works
    print("\n🚫 Testing duplicate prevention...")

    # Try to open AAPL in day trading (should be blocked)
    can_open, reason = manager.can_open_position('AAPL', 'day', 200.0)
    if not can_open:
        print(f"   ✅ AAPL blocked for day trading: {reason}")
    else:
        print(f"   ❌ AAPL NOT blocked (should be blocked)")

    # Try to open NVDA in day trading (should work)
    can_open, reason = manager.can_open_position('NVDA', 'day', 200.0)
    if can_open:
        print(f"   ✅ NVDA allowed for day trading: {reason}")
    else:
        print(f"   ❌ NVDA blocked: {reason}")

    # Check capital summary
    summary = manager.get_capital_summary()
    print("\n📊 Capital Summary:")
    print(f"   Swing capital used: ${summary['swing_trading']['used']:.2f}")
    print(f"   Swing capital available: ${summary['swing_trading']['available']:.2f}")
    print(f"   Active swing positions: {summary['swing_trading']['positions_count']}")

    print("\n✅ Re-registration test complete")


if __name__ == "__main__":
    # Run tests
    exit_code = test_restoration()

    if exit_code == 0:
        test_reregistration()

    sys.exit(exit_code)
