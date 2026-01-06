#!/usr/bin/env python3
"""
Test to reproduce the bar count vs trade results issue
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def test_bar_count_consistency():
    """Test simulation with different bar counts to reproduce the issue"""
    
    print("🔍 TESTING BAR COUNT CONSISTENCY")
    print("=" * 50)
    
    test_cases = [1000, 3000]
    
    for bar_count in test_cases:
        print(f"\n{'='*20} TESTING {bar_count} BARS {'='*20}")
        
        # Create fresh simulation environment for each test
        sim_env = setup_simulation_environment()
        simulation_manager = sim_env['simulation_manager']
        broker = sim_env['broker']
        
        await simulation_manager.initialize(create_sample_data=False)
        await broker.connect()
        await sim_env['data_provider'].connect()
        
        print(f"📊 Starting simulation with {bar_count} bars...")
        
        try:
            # This should be similar to how you're running your simulation
            # I'm guessing you have a method that accepts bar count parameter
            
            # Check if there's a method for testing strategy on symbol
            if hasattr(simulation_manager, 'test_strategy_on_symbol'):
                result = await simulation_manager.test_strategy_on_symbol(
                    symbol="GV",
                    timeframe="1 min", 
                    bars_count=bar_count,
                    strategy_name="multi_strategy"
                )
                print(f"   ✅ Simulation completed")
                print(f"   📈 Signals generated: {result.get('signals_generated', 0)}")
                print(f"   💼 Trades executed: {result.get('trades_executed', 0)}")
                
            elif hasattr(simulation_manager, 'run_simulation'):
                # Alternative method name
                result = await simulation_manager.run_simulation(
                    symbols=["GV"],
                    bars_count=bar_count
                )
                print(f"   ✅ Simulation completed")
                
            else:
                print(f"   ❌ Could not find simulation method")
                continue
                
        except Exception as e:
            print(f"   ❌ Error during simulation: {e}")
            continue
        
        # Show the trade report
        print(f"\n📊 TRADE REPORT FOR {bar_count} BARS:")
        print("-" * 40)
        try:
            broker.print_detailed_trade_report()
        except Exception as e:
            print(f"Error showing report: {e}")
        
        # Get broker state details
        positions = await broker.get_positions() 
        orders = getattr(broker, '_orders', {})
        trade_history = getattr(broker, '_trade_history', [])
        
        print(f"\n🔍 Broker state after {bar_count} bars simulation:")
        print(f"   Positions: {len(positions)}")
        print(f"   Orders: {len(orders)}")
        print(f"   Trade history: {len(trade_history)}")
        
        # Show first order details if any
        if orders:
            first_order = list(orders.values())[0]
            print(f"   First order: {first_order.get('symbol', 'N/A')} @ ${first_order.get('price', 'N/A')} ({first_order.get('side', 'N/A')})")
        
        # Clean up
        try:
            await broker.disconnect()
            await sim_env['data_provider'].disconnect()
        except:
            pass
        
        print(f"\n" + "="*50)
    
    print(f"\n🎯 ANALYSIS:")
    print(f"   - If both simulations show different trades, there's a data consistency issue")
    print(f"   - If dates are different, different data sets are being processed")
    print(f"   - If trade details vary, the simulation logic may have randomness or state issues")
    print(f"\n💡 EXPECTED: Both simulations should show IDENTICAL results for same symbol/timeframe")

if __name__ == "__main__":
    asyncio.run(test_bar_count_consistency())