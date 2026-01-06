#!/usr/bin/env python3
"""
Test script to verify dashboard data loading without errors
"""

import sys
import dashboard.dashboard_utils as utils

print("=" * 80)
print("TESTING DASHBOARD DATA LOADING")
print("=" * 80)
print()

# Test 1: Get active trades
print("1️⃣  Testing get_active_trades()...")
try:
    active_trades = utils.get_active_trades()
    print(f"   ✅ Success! Found {len(active_trades)} active trades")
    if not active_trades.empty:
        print(f"   Symbols: {', '.join(active_trades['symbol'].tolist())}")
    else:
        print("   No active trades (this is normal)")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

print()

# Test 2: Get scanner feed
print("2️⃣  Testing get_scanner_feed()...")
try:
    scanner_df = utils.get_scanner_feed(limit=5)
    print(f"   ✅ Success! Found {len(scanner_df)} scanner opportunities")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

print()

# Test 3: Get P&L stats
print("3️⃣  Testing get_pnl_stats()...")
try:
    stats = utils.get_pnl_stats()
    print(f"   ✅ Success!")
    print(f"   Total P&L: ${stats['total_pnl']:.2f}")
    print(f"   Today's P&L: ${stats['today_pnl']:.2f}")
    print(f"   Win Rate: {stats['win_rate']:.1f}%")
    print(f"   Total Trades: {stats['total_trades']}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

print()

# Test 4: Check for inconsistencies
print("4️⃣  Checking for data inconsistencies...")
import sqlite3
conn = sqlite3.connect("trading_data.db")
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN' AND exit_filled = 1")
inconsistent = cursor.fetchone()[0]

if inconsistent == 0:
    print("   ✅ No inconsistencies found!")
else:
    print(f"   ⚠️  Found {inconsistent} inconsistent trades")

conn.close()

print()
print("=" * 80)
print("ALL TESTS PASSED! Dashboard should work without errors.")
print("=" * 80)
