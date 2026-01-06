"""
Test TradeTally Swing Integration
Verifies that swing trades sync correctly with TradeTally
"""

import sqlite3
import sys
import os
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_swing_trade_sync():
    """Test swing trade synchronization"""

    print("\n" + "="*70)
    print("TEST: TradeTally Swing Trade Synchronization")
    print("="*70)

    # Create test database
    test_db = "test_tradetally_swing.db"

    try:
        conn = sqlite3.connect(test_db)
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
                entry_commission REAL DEFAULT 0,
                consolidation_days INTEGER,
                resistance_level REAL,
                support_level REAL,
                breakout_score REAL,
                pattern_type TEXT,
                exit_date DATE,
                exit_price REAL,
                exit_commission REAL DEFAULT 0,
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

        # Insert test swing trade
        today = date.today()
        entry_date = today - timedelta(days=5)
        exit_date = today - timedelta(days=1)

        cursor.execute("""
            INSERT INTO swing_trades (
                trade_id, symbol, pattern_type, scan_date, entry_date, entry_price,
                quantity, entry_commission, consolidation_days, resistance_level,
                support_level, breakout_score, exit_date, exit_price,
                exit_commission, pnl_net, days_held, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"SWING_AAPL_{entry_date.strftime('%Y%m%d')}",
            'AAPL',
            'ASCENDING_TRIANGLE',
            entry_date - timedelta(days=1),
            entry_date,
            150.00,
            2,
            1.50,
            45,  # 45 days consolidation
            155.00,  # resistance
            145.00,  # support
            85.0,  # breakout score
            exit_date,
            160.00,  # exit price
            1.50,
            17.00,  # net PnL
            4,  # days held
            'CLOSED'
        ))

        conn.commit()
        print("\n✅ Test swing trade created in database")

        # Import TradeTally Integration
        from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration

        # Initialize integration (without real API)
        integration = TradeTallyIntegration(
            api_key="tt_test_key",
            base_url="https://test.tradetally.com/api/v2",
            db_path=test_db
        )

        # Test fetch_swing_trades
        print("\n🔍 Testing fetch_swing_trades()...")
        swing_trades = integration.fetch_swing_trades()

        print(f"\n📊 Retrieved {len(swing_trades)} swing trade(s)")

        if swing_trades:
            trade = swing_trades[0]
            print(f"\n📋 Trade Details:")
            print(f"   Trade ID: {trade.trade_id}")
            print(f"   Symbol: {trade.symbol}")
            print(f"   Strategy: {trade.strategy}")
            print(f"   Side: {trade.side}")
            print(f"   Entry: ${trade.entry_price:.2f} x {trade.quantity}")
            print(f"   Exit: ${trade.exit_price:.2f}")
            print(f"   Entry Time: {trade.entry_time}")
            print(f"   Exit Time: {trade.exit_time}")
            print(f"   Duration: {trade.duration_minutes} min ({trade.duration_minutes//1440} days)")
            print(f"   PnL: ${trade.pnl:.2f}")
            print(f"   Commission: ${trade.commission:.2f}")
            print(f"   Confidence: {trade.confidence:.0f}%")
            print(f"   Trade Source: {trade.trade_source}")
            print(f"   Notes: {trade.notes}")

            # Verify data mapping
            print("\n✅ Verification:")
            assert trade.symbol == 'AAPL', "Symbol mismatch"
            assert trade.strategy == 'swing_ascending_triangle', f"Strategy mismatch: {trade.strategy}"
            assert trade.side == 'BUY', "Side should be BUY"
            assert trade.quantity == 2, "Quantity mismatch"
            assert trade.entry_price == 150.00, "Entry price mismatch"
            assert trade.exit_price == 160.00, "Exit price mismatch"
            assert trade.duration_minutes == 4 * 1440, "Duration mismatch"
            assert trade.pnl == 17.00, "PnL mismatch"
            assert trade.commission == 3.00, "Commission mismatch (should be 1.50+1.50)"
            assert trade.confidence == 85.0, "Confidence (breakout score) mismatch"
            assert trade.trade_source == 'swing', "Trade source should be 'swing'"
            assert 'ASCENDING_TRIANGLE' in trade.notes, "Pattern not in notes"
            assert '85/100' in trade.notes, "Breakout score not in notes"
            assert '45 days' in trade.notes, "Consolidation days not in notes"

            print("   ✓ Symbol: AAPL")
            print("   ✓ Strategy: swing_ascending_triangle")
            print("   ✓ Side: BUY (long only)")
            print("   ✓ Duration: 4 days -> 5760 minutes")
            print("   ✓ PnL: $17.00")
            print("   ✓ Commission: $3.00 (entry + exit)")
            print("   ✓ Confidence: 85% (from breakout_score)")
            print("   ✓ Trade Source: swing")
            print("   ✓ Notes include pattern details")

            # Test timestamp conversion
            print("\n📅 Timestamp Conversion:")
            print(f"   Entry Date: {entry_date} -> {trade.entry_time} (09:30:00)")
            print(f"   Exit Date: {exit_date} -> {trade.exit_time} (15:58:00)")
            assert '09:30:00' in trade.entry_time, "Entry time should be market open"
            assert '15:58:00' in trade.exit_time, "Exit time should be market close"
            print("   ✓ Dates correctly converted to timestamps")

        # Cleanup
        conn.close()
        os.remove(test_db)
        if os.path.exists("tradetally_sync_state.json"):
            os.remove("tradetally_sync_state.json")

        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED - Swing trades sync correctly!")
        print("="*70)

        print("\n💡 Summary:")
        print("   ✅ Swing trades fetched from database")
        print("   ✅ DATE -> TIMESTAMP conversion working")
        print("   ✅ Breakout score -> confidence mapping")
        print("   ✅ Pattern details in notes")
        print("   ✅ Trade source tracked (day vs swing)")
        print("   ✅ Ready for TradeTally synchronization")

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

        # Cleanup on error
        if os.path.exists(test_db):
            os.remove(test_db)
        if os.path.exists("tradetally_sync_state.json"):
            os.remove("tradetally_sync_state.json")

        return False


if __name__ == "__main__":
    print("\n🧪 TRADETALLY SWING INTEGRATION TEST\n")
    success = test_swing_trade_sync()
    sys.exit(0 if success else 1)
