#!/usr/bin/env python3
"""
Debug TradeTally Sync - Test individual trade sync to see exact payload
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration

def main():
    # Configuration from config.ini
    API_KEY = "tt_live_RKiO1wDZz6kNEek5OJei6645U8FGpXtb"
    BASE_URL = "http://localhost:8001/api/v2"
    DB_PATH = str(project_root / "trading_data.db")

    print("🔍 DEBUG TRADETALLY SYNC")
    print("=" * 50)
    print(f"API Key: {API_KEY[:20]}...")
    print(f"Base URL: {BASE_URL}")
    print(f"DB Path: {DB_PATH}")
    print()

    # Create integration
    try:
        sync = TradeTallyIntegration(API_KEY, BASE_URL, DB_PATH)
        print("✅ TradeTallyIntegration created successfully")
    except Exception as e:
        print(f"❌ Error creating TradeTallyIntegration: {e}")
        return

    # Test connection
    print("\n🔗 Testing connection...")
    if not sync.test_connection():
        print("❌ Connection test failed")
        return
    print("✅ Connection test passed")

    # Get one trade to test
    print("\n📊 Getting test trade...")
    trades = sync.get_local_trades(only_new=True, only_today=False)
    if not trades:
        print("❌ No trades found for testing")
        return

    trade = trades[0]
    print(f"📈 Test trade: {trade.symbol} - {trade.trade_id}")

    # Create payload
    print("\n📋 Creating payload...")
    payload = sync.create_tradetally_payload(trade)

    print("🔍 PAYLOAD DETAILS:")
    print("=" * 30)
    import json
    print(json.dumps(payload, indent=2))

    # Check for signalStrength
    if 'signalStrength' in payload:
        print(f"\n⚠️  WARNING: signalStrength found in payload: {payload['signalStrength']}")
    else:
        print("\n✅ signalStrength NOT found in payload")

    # Try to sync
    print("\n🔄 Attempting sync...")
    success, message = sync.sync_trade_to_tradetally(trade)

    if success:
        print("✅ Sync successful")
    else:
        print(f"❌ Sync failed: {message}")

if __name__ == "__main__":
    main()