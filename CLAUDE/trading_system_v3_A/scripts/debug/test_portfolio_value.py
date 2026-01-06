#!/usr/bin/env python3
"""
Test portfolio value calculation fix
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def test_portfolio_value():
    """Test portfolio value calculation"""
    
    print("🔍 TESTING PORTFOLIO VALUE CALCULATION")
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
        
        # Test con LOBO
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="LOBO",
            timeframe="1 min",
            bars_count=100,
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        final_stats = result.get('final_stats', {})
        
        print(f"\n📊 RESULTADO:")
        print(f"   ✅ Trades: {result.get('trades_executed', 0)}")
        print(f"   💰 P&L Total: ${final_stats.get('total_pnl', 0):.2f}")
        print(f"   💵 Cash: ${final_stats.get('cash', 0):.2f}")
        print(f"   💼 Portfolio Value: ${final_stats.get('total_value', 0):.2f}")
        
        # Verificar consistencia
        cash = final_stats.get('cash', 0)
        portfolio_value = final_stats.get('total_value', 0)
        
        if abs(cash - portfolio_value) < 0.01:  # Deberían ser iguales si no hay posiciones abiertas
            print(f"✅ ARREGLADO: Portfolio Value = Cash = ${portfolio_value:.2f}")
        else:
            print(f"❌ AÚN HAY PROBLEMA: Cash=${cash:.2f} vs Portfolio=${portfolio_value:.2f}")
            
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
    asyncio.run(test_portfolio_value())