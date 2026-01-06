#!/usr/bin/env python3
"""
Test completo del sistema con reporte detallado integrado
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def test_complete_system_with_reports():
    """Test completo del sistema con reportes detallados"""
    
    print("🔍 TESTING COMPLETE SYSTEM WITH DETAILED REPORTS")
    print("=" * 70)
    
    # Setup logging
    logging.basicConfig(level=logging.ERROR)  # Solo mostrar errores críticos
    
    try:
        # Setup
        sim_env = setup_simulation_environment()
        simulation_manager = sim_env['simulation_manager']
        
        # Initialize
        await simulation_manager.initialize(create_sample_data=False)
        await sim_env['broker'].connect()
        await sim_env['data_provider'].connect()
        
        print("✅ Sistema inicializado")
        
        # Test con XXII - símbolo que sabemos genera trades
        print(f"\n🎯 TEST CON XXII (500 barras)")
        print("-" * 50)
        
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=500,
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        final_stats = result.get('final_stats', {})
        trades_executed = result.get('trades_executed', 0)
        total_pnl = final_stats.get('total_pnl', 0)
        realized_pnl = final_stats.get('realized_pnl', 0)
        unrealized_pnl = final_stats.get('unrealized_pnl', 0)
        total_pnl_pct = final_stats.get('total_pnl_pct', 0)
        
        print(f"\n📊 RESULTADOS PARA XXII:")
        print(f"   ✅ Trades ejecutados: {trades_executed}")
        if realized_pnl != 0 or total_pnl != 0:
            print(f"   💰 P&L Total: ${total_pnl:.2f} ({total_pnl_pct:.2f}%)")
            print(f"   💵 P&L Realizado: ${realized_pnl:.2f}")
            print(f"   📊 P&L No Realizado: ${unrealized_pnl:.2f}")
        else:
            print(f"   💰 P&L Final: $0.00")
            
        print(f"   💼 Portfolio Value: ${final_stats.get('total_value', 2000):.2f}")
        print(f"   💵 Cash: ${final_stats.get('cash', 2000):.2f}")
        print(f"   📈 Win Rate: {final_stats.get('win_rate', 0):.2f}%")
        print(f"   📉 Max Drawdown: ${final_stats.get('max_drawdown', 0):.2f}")
        
        # Mostrar reporte detallado de trades si hay trades ejecutados
        if trades_executed > 0:
            print(f"\n" + "="*80)
            print("📋 REPORTE DETALLADO DE TRADES - XXII")
            print("="*80)
            simulation_manager.mock_broker.print_detailed_trade_report()
        
        print(f"\n" + "="*70)
        print("🔄 TEST CON LOBO (Segundo símbolo)")
        print("-" * 50)
        
        # Reset para segundo test
        simulation_manager.mock_broker.reset_simulation()
        
        result2 = await simulation_manager.test_strategy_on_symbol(
            symbol="LOBO",
            timeframe="1 min",
            bars_count=300,
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        final_stats2 = result2.get('final_stats', {})
        trades_executed2 = result2.get('trades_executed', 0)
        total_pnl2 = final_stats2.get('total_pnl', 0)
        realized_pnl2 = final_stats2.get('realized_pnl', 0)
        
        print(f"\n📊 RESULTADOS PARA LOBO:")
        print(f"   ✅ Trades ejecutados: {trades_executed2}")
        print(f"   💰 P&L Total: ${total_pnl2:.2f}")
        print(f"   💵 P&L Realizado: ${realized_pnl2:.2f}")
        print(f"   📈 Win Rate: {final_stats2.get('win_rate', 0):.2f}%")
        
        # Mostrar reporte detallado para LOBO
        if trades_executed2 > 0:
            print(f"\n" + "="*80)
            print("📋 REPORTE DETALLADO DE TRADES - LOBO")
            print("="*80)
            simulation_manager.mock_broker.print_detailed_trade_report()
            
        print(f"\n🎉 TESTS COMPLETADOS!")
        print(f"📈 Total de trades analizados: {trades_executed + trades_executed2}")
            
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
    asyncio.run(test_complete_system_with_reports())