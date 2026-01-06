#!/usr/bin/env python3
"""
Clear mock broker trade history to see fresh results with strategy names
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def clear_trade_history():
    """Clear all old trade history from mock broker"""
    
    print("🧹 CLEARING OLD TRADE HISTORY")
    print("=" * 40)
    
    # Setup environment
    sim_env = setup_simulation_environment()
    broker = sim_env['broker']
    
    await broker.connect()
    
    # Get current state
    positions = await broker.get_positions()
    orders = getattr(broker, '_orders', {})
    trade_history = getattr(broker, '_trade_history', [])
    open_positions = getattr(broker, '_open_positions_tracking', {})
    
    print(f"📊 Current state:")
    print(f"   Positions: {len(positions)}")
    print(f"   Orders: {len(orders)}")
    print(f"   Trade history: {len(trade_history)}")
    print(f"   Open position tracking: {len(open_positions)}")
    
    # Clear all trade-related data
    if hasattr(broker, '_orders'):
        broker._orders.clear()
        print("   ✅ Cleared orders")
        
    if hasattr(broker, '_trade_history'):
        broker._trade_history.clear()
        print("   ✅ Cleared trade history")
        
    if hasattr(broker, '_open_positions_tracking'):
        broker._open_positions_tracking.clear()
        print("   ✅ Cleared open positions tracking")
        
    if hasattr(broker, '_positions'):
        broker._positions.clear()
        print("   ✅ Cleared positions")
    
    # Reset account to initial state
    if hasattr(broker, '_account_info'):
        broker._account_info['cash'] = 10000.0
        broker._account_info['total_value'] = 10000.0
        print("   ✅ Reset account balance to $10,000")
    
    # Reset counters
    if hasattr(broker, '_total_commissions_paid'):
        broker._total_commissions_paid = 0.0
        print("   ✅ Reset commission counter")
        
    if hasattr(broker, '_total_pnl'):
        broker._total_pnl = 0.0
        print("   ✅ Reset PnL counter")
    
    print("\n🎯 Trade history cleared! Next simulation will show fresh results with strategy names.")
    print("💡 Run your simulation again to see strategy names in the trade report.")

if __name__ == "__main__":
    asyncio.run(clear_trade_history())