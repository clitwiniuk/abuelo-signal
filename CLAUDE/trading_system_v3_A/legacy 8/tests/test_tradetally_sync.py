#!/usr/bin/env python3
"""
Test TradeTally sync to verify it detects the newly closed trades
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration

def test_sync():
    """Test TradeTally sync without actually sending to API"""
    
    # Use dummy credentials for testing
    API_KEY = "tt_live_test_key"
    BASE_URL = "https://test.tradetally.com/api/v2"
    DB_PATH = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db"
    
    # Create sync instance
    sync = TradeTallyIntegration(API_KEY, BASE_URL, DB_PATH)
    
    print("🔍 Testing TradeTally sync detection...")
    print("=" * 50)
    
    # Get trades that would be synced
    trades = sync.get_local_trades(only_new=True)
    
    print(f"📊 Trades found for sync: {len(trades)}")
    print("-" * 30)
    
    for trade in trades:
        print(f"• {trade.symbol} ({trade.trade_id})")
        print(f"  Entry: {trade.entry_price} -> Exit: {trade.exit_price}")
        print(f"  PnL: ${trade.pnl:.2f}")
        print(f"  Status: {trade.status}")
        print()
    
    # Show sync state
    print("📋 Current sync state:")
    status = sync.get_sync_status()
    print(f"• Last sync: {status['last_sync']}")
    print(f"• Total synced: {status['total_synced']}")
    print(f"• Failed syncs: {status['failed_syncs']}")
    
    print("=" * 50)
    print(f"✅ Test completed. Found {len(trades)} new trades to sync.")
    
    return len(trades)

if __name__ == "__main__":
    test_sync()
