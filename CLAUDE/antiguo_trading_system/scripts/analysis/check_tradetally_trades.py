#!/usr/bin/env python3
"""
Check what trades are actually in TradeTally
"""

import requests
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration

def check_tradetally_trades():
    """Check what trades are in TradeTally"""
    print("🔍 CHECKING TRADES IN TRADETALLY")
    print("=" * 50)
    
    # Load config
    try:
        from integrations.tradetally.config.tradetally_config import config
        
        integration = TradeTallyIntegration(
            api_key=config.api_key,
            base_url=config.base_url,
            db_path="trading_data.db"
        )
        
        # Test connection
        if not integration.test_connection():
            print("❌ Cannot connect to TradeTally")
            return
            
        print("✅ Connected to TradeTally")
        
        # Get trades from TradeTally
        print("\n📊 Querying trades from TradeTally...")
        
        response = requests.get(
            f"{integration.base_url}/trades?limit=50",
            headers=integration.headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            trades = data.get('trades', [])
            
            print(f"✅ Found {len(trades)} trades in TradeTally:")
            
            if trades:
                print("\n🔸 Recent trades:")
                for i, trade in enumerate(trades[:10]):  # Show first 10
                    symbol = trade.get('symbol', 'N/A')
                    side = trade.get('side', 'N/A')
                    entry_time = trade.get('entryTime', 'N/A')
                    entry_price = trade.get('entryPrice', 'N/A')
                    exit_price = trade.get('exitPrice', 'N/A')
                    quantity = trade.get('quantity', 'N/A')
                    pnl = trade.get('pnl', 'N/A')
                    notes = trade.get('notes', 'N/A')[:50]  # First 50 chars
                    
                    print(f"   {i+1:2d}. {symbol} {side} {quantity}@${entry_price} → ${exit_price} (PnL: {pnl})")
                    print(f"       Time: {entry_time}")
                    print(f"       Notes: {notes}...")
                    print()
                    
                # Look for our specific trades
                print("🔍 Looking for our recent trades (RR, NUKK):")
                found_rr = False
                found_nukk = False
                
                for trade in trades:
                    symbol = trade.get('symbol', '')
                    notes = trade.get('notes', '')
                    
                    if symbol == 'RR' or 'RR_20250826' in notes:
                        found_rr = True
                        print(f"   ✅ Found RR trade: {trade.get('entryTime')} - ${trade.get('entryPrice')} → ${trade.get('exitPrice')}")
                        
                    if symbol == 'NUKK' or 'NUKK_20250826' in notes:
                        found_nukk = True
                        print(f"   ✅ Found NUKK trade: {trade.get('entryTime')} - ${trade.get('entryPrice')} → ${trade.get('exitPrice')}")
                
                if not found_rr:
                    print("   ⚠️  RR trade not found")
                if not found_nukk:
                    print("   ⚠️  NUKK trade not found")
                    
            else:
                print("   📭 No trades found in TradeTally")
                
        else:
            print(f"❌ Error querying trades: {response.status_code}")
            print(f"Response: {response.text}")
            
        # Check with different date filters
        print(f"\n🔍 Checking trades for last 7 days...")
        from datetime import datetime, timedelta
        
        last_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{integration.base_url}/trades?startDate={last_week}&limit=50",
            headers=integration.headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            trades_week = data.get('trades', [])
            print(f"   📅 Found {len(trades_week)} trades in last 7 days")
            
            # Look specifically for 2025-08-26 trades
            for trade in trades_week:
                entry_time = trade.get('entryTime', '')
                if '2025-08-26' in entry_time or '2025-08-27' in entry_time:
                    symbol = trade.get('symbol', 'N/A')
                    print(f"   📌 Recent trade: {symbol} at {entry_time}")
                    
        else:
            print(f"   ❌ Error querying weekly trades: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_tradetally_trades()