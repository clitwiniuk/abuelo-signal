#!/usr/bin/env python3
"""
Test específico del drawdown calculation
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def test_drawdown_calculation():
    """Test específico del drawdown"""
    
    print("🔍 TESTING DRAWDOWN CALCULATION")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.WARNING)
    
    try:
        # Setup
        sim_env = setup_simulation_environment()
        simulation_manager = sim_env['simulation_manager']
        
        # Initialize
        await simulation_manager.initialize(create_sample_data=False)
        await sim_env['broker'].connect()
        await sim_env['data_provider'].connect()
        
        print("✅ Sistema inicializado")
        
        # Test con XXII que sabemos tuvo problemas de drawdown
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=500,
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        final_stats = result.get('final_stats', {})
        
        print(f"\n📊 RESULTADO:")
        print(f"   ✅ Trades: {result.get('trades_executed', 0)}")
        print(f"   💰 P&L Total: ${final_stats.get('total_pnl', 0):.2f}")
        print(f"   💵 Cash: ${final_stats.get('cash', 0):.2f}")
        print(f"   💼 Portfolio Value: ${final_stats.get('total_value', 0):.2f}")
        print(f"   📉 Max Drawdown: ${final_stats.get('max_drawdown', 0):.2f}")
        print(f"   🎯 Win Rate: {final_stats.get('win_rate', 0):.2f}%")
        
        # Verificar si el drawdown es realista
        total_pnl = final_stats.get('total_pnl', 0)
        max_drawdown = final_stats.get('max_drawdown', 0)
        
        print(f"\n🔍 ANALYSIS:")
        if max_drawdown > abs(total_pnl) * 3:  # Drawdown more than 3x the loss
            print(f"❌ PROBLEMA: Max drawdown ${max_drawdown:.2f} es demasiado alto para P&L ${total_pnl:.2f}")
        else:
            print(f"✅ CORRECTO: Max drawdown ${max_drawdown:.2f} es razonable para P&L ${total_pnl:.2f}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            if 'sim_env' in locals():
                await sim_env['broker'].disconnect()
                await sim_env['data_provider'].disconnect()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_drawdown_calculation())