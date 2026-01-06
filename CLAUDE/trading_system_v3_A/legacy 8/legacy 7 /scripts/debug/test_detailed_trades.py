#!/usr/bin/env python3
"""
Test del sistema detallado de tracking de trades
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def test_detailed_trade_tracking():
    """Test del tracking detallado de trades"""
    
    print("🔍 TESTING DETAILED TRADE TRACKING")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(level=logging.WARNING)
    
    try:
        # Setup
        sim_env = setup_simulation_environment()
        simulation_manager = sim_env['simulation_manager']
        broker = sim_env['broker']
        
        # Initialize
        await simulation_manager.initialize(create_sample_data=False)
        await broker.connect()
        await sim_env['data_provider'].connect()
        
        print("✅ Sistema inicializado")
        
        # Test con XXII - 500 barras para ver varios trades
        print(f"\n🎯 Ejecutando test con XXII - 500 barras")
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=500,
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        final_stats = result.get('final_stats', {})
        trades_executed = result.get('trades_executed', 0)
        
        print(f"\n📊 RESULTADOS GENERALES:")
        print(f"   ✅ Trades ejecutados: {trades_executed}")
        print(f"   💰 P&L Total: ${final_stats.get('total_pnl', 0):.2f}")
        print(f"   🎯 Win Rate: {final_stats.get('win_rate', 0):.2f}%")
        
        # Obtener y mostrar el reporte detallado de trades
        print(f"\n" + "="*60)
        print("📋 REPORTE DETALLADO DE TRADES")
        print("="*60)
        
        # Llamar al método del broker para imprimir el reporte detallado
        broker.print_detailed_trade_report()
        
        # Obtener estadísticas de duración
        duration_stats = broker.get_trade_duration_stats()
        if duration_stats:
            print(f"\n📈 ESTADÍSTICAS DE DURACIÓN:")
            print(f"   ⏱️ Duración promedio: {duration_stats['avg_duration_minutes']:.1f} minutos")
            print(f"   ⏱️ Duración mín/máx: {duration_stats['min_duration_minutes']:.1f} - {duration_stats['max_duration_minutes']:.1f} min")
            print(f"   ✅ Duración trades ganadores: {duration_stats['avg_winning_duration']:.1f} min")
            print(f"   ❌ Duración trades perdedores: {duration_stats['avg_losing_duration']:.1f} min")
        
        # Test adicional con otro símbolo para comparar
        print(f"\n" + "="*60)
        print("🔄 TEST ADICIONAL CON LOBO")
        print("="*60)
        
        # Reset broker para nuevo test
        broker.reset_simulation()
        
        result2 = await simulation_manager.test_strategy_on_symbol(
            symbol="LOBO",
            timeframe="1 min", 
            bars_count=300,
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        print(f"\n📊 RESULTADOS LOBO:")
        final_stats2 = result2.get('final_stats', {})
        print(f"   ✅ Trades ejecutados: {result2.get('trades_executed', 0)}")
        print(f"   💰 P&L Total: ${final_stats2.get('total_pnl', 0):.2f}")
        
        # Reporte detallado para LOBO
        broker.print_detailed_trade_report()
            
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
    asyncio.run(test_detailed_trade_tracking())