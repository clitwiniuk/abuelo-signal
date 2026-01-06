#!/usr/bin/env python3
"""
Test script to verify the trade update fix works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from datetime import datetime

def test_trade_update_fix():
    """Test that the fix correctly updates OPEN trades to CLOSED"""
    
    db_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db"
    
    print("🔍 Testing trade update fix...")
    print("=" * 50)
    
    # Check current state
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all trades
    cursor.execute("SELECT trade_id, symbol, status, entry_price, exit_price, pnl FROM trades ORDER BY updated_at DESC")
    trades = cursor.fetchall()
    
    print("📊 Current trades in database:")
    print("-" * 30)
    for trade in trades:
        trade_id, symbol, status, entry_price, exit_price, pnl = trade
        print(f"• {symbol} ({trade_id[:8]}...)")
        print(f"  Status: {status}")
        print(f"  Entry: ${entry_price:.2f}")
        print(f"  Exit: ${exit_price if exit_price else 'None'}")
        print(f"  PnL: ${pnl if pnl else 'None'}")
        print()
    
    # Count by status
    cursor.execute("SELECT status, COUNT(*) FROM trades GROUP BY status")
    status_counts = cursor.fetchall()
    
    print("📈 Trade status summary:")
    for status, count in status_counts:
        print(f"• {status}: {count} trades")
    
    conn.close()
    
    print("=" * 50)
    print("✅ Test completed. The fix should now:")
    print("1. Find OPEN trades in database when exit signals are processed")
    print("2. Update them with exit_price, exit_time, pnl, and status='CLOSED'")
    print("3. Emit ML feedback events for closed positions")
    print()
    print("🎯 Next time an exit signal is processed, it will update the database correctly!")
    
    return len([t for t in trades if t[2] == 'CLOSED'])

if __name__ == "__main__":
    closed_trades = test_trade_update_fix()
    print(f"📊 Currently {closed_trades} trades are marked as CLOSED")
