#!/usr/bin/env python3
"""
Debug why different bar counts show different trade results
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def debug_trade_persistence():
    """Debug the trade persistence issue"""
    
    print("🔍 DEBUGGING TRADE PERSISTENCE ISSUE")
    print("=" * 60)
    
    # Check what's in the mock broker before any simulation
    print("📊 Checking initial mock broker state...")
    
    sim_env = setup_simulation_environment()
    broker = sim_env['broker']
    await broker.connect()
    
    # Check broker state
    positions = await broker.get_positions()
    orders = getattr(broker, '_orders', {})
    trade_history = getattr(broker, '_trade_history', [])
    open_positions = getattr(broker, '_open_positions_tracking', {})
    
    print(f"   Current positions: {len(positions)}")
    print(f"   Orders count: {len(orders)}")
    print(f"   Trade history count: {len(trade_history)}")
    print(f"   Open positions tracking: {len(open_positions)}")
    
    if orders:
        print(f"\n📋 Existing orders:")
        for order_id, order in list(orders.items())[:5]:  # Show first 5
            print(f"   {order_id}: {order.get('symbol', 'N/A')} {order.get('side', 'N/A')} {order.get('quantity', 'N/A')} @ {order.get('price', 'N/A')}")
            if len(orders) > 5:
                print(f"   ... and {len(orders)-5} more orders")
                break
    
    if trade_history:
        print(f"\n📈 Existing trade history:")
        for i, trade in enumerate(trade_history[:3]):  # Show first 3
            print(f"   Trade {i+1}: {trade}")
            if len(trade_history) > 3:
                print(f"   ... and {len(trade_history)-3} more trades")
                break
    
    if open_positions:
        print(f"\n📍 Open position tracking:")
        for symbol, positions_list in open_positions.items():
            print(f"   {symbol}: {len(positions_list)} tracked positions")
            for pos in positions_list[:2]:  # Show first 2
                print(f"     - Entry: {pos.get('entry_time', 'N/A')} @ ${pos.get('entry_price', 'N/A')} [{pos.get('strategy_name', 'No Strategy')}]")
    
    # Check if there's a detailed trade report available
    print(f"\n📊 Attempting to show current detailed trade report...")
    try:
        print("--- CURRENT DETAILED TRADE REPORT ---")
        broker.print_detailed_trade_report()
        print("--- END REPORT ---")
    except Exception as e:
        print(f"   Error showing report: {e}")
    
    # Check database for persistent trades
    print(f"\n🗄️  Checking database for persistent trade data...")
    import sqlite3
    import os
    
    db_files = [
        "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db",
        "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/logs/trading_data.db"
    ]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            print(f"   Found database: {db_file}")
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                # Check trades table
                cursor.execute("SELECT COUNT(*) FROM trades WHERE symbol = 'GV'")
                gv_trades = cursor.fetchone()[0]
                print(f"     GV trades in database: {gv_trades}")
                
                if gv_trades > 0:
                    cursor.execute("SELECT entry_time, strategy, pnl, status FROM trades WHERE symbol = 'GV' ORDER BY entry_time DESC LIMIT 5")
                    trades = cursor.fetchall()
                    for trade in trades:
                        print(f"     - {trade[0]} | Strategy: {trade[1]} | PnL: {trade[2]} | Status: {trade[3]}")
                
                conn.close()
            except Exception as e:
                print(f"     Error reading database: {e}")
        else:
            print(f"   Database not found: {db_file}")
    
    # Check for any cached files
    print(f"\n📁 Checking for cached data files...")
    cache_patterns = ['*.json', '*.pkl', '*.csv']
    for pattern in cache_patterns:
        files = list(Path(project_root).rglob(pattern))
        trade_files = [f for f in files if 'trade' in f.name.lower() or 'position' in f.name.lower()]
        if trade_files:
            print(f"   Found {pattern} files with trade data:")
            for f in trade_files[:5]:
                print(f"     - {f}")
    
    print(f"\n💡 KEY INSIGHTS:")
    print(f"   - If mock broker has existing data: Cached from previous runs")
    print(f"   - If database has trades: Persistent storage is interfering")
    print(f"   - Different bar counts may trigger different data loading paths")
    print(f"   - Check if simulation manager is reading from different data sources")
    
    print(f"\n🎯 RECOMMENDATION:")
    print(f"   1. Clear ALL cached data before running simulations")
    print(f"   2. Use fresh mock broker instances")
    print(f"   3. Verify data source consistency")

if __name__ == "__main__":
    asyncio.run(debug_trade_persistence())