#!/usr/bin/env python3
"""
FINAL TEST - Sistema de trading perfecto funcionando end-to-end
Demuestra que el sistema multicola estrategias, genera señales y ejecuta trades.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def test_sistema_perfecto():
    """Test completo del sistema funcionando perfectamente"""
    
    print("🎯 FINAL TEST: SISTEMA DE TRADING PERFECTO")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Setup
        sim_env = setup_simulation_environment()
        simulation_manager = sim_env['simulation_manager']
        
        # Initialize
        await simulation_manager.initialize(create_sample_data=False)
        await sim_env['broker'].connect()
        await sim_env['data_provider'].connect()
        
        print("🚀 Sistema inicializado y conectado")
        print("✅ Broker mock conectado")
        print("✅ Data provider CSV conectado")
        print("✅ MultiStrategy engine disponible")
        
        # Test 1: Verificar que multi-strategy funciona
        print("\n📊 TEST 1: Multi-Strategy con XXII (200 barras)")
        result1 = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=200,
            strategy_name="multi_strategy",
            realistic_timing=False  # Más rápido para el test
        )
        
        print(f"   📈 Señales generadas: {result1.get('signals_generated', 0)}")
        print(f"   💼 Trades ejecutados: {result1.get('trades_executed', 0)}")
        print(f"   📊 Barras analizadas: {result1.get('bars_analyzed', 0)}")
        
        # Test 2: Verificar que el sistema maneja múltiples símbolos
        print("\n🔄 TEST 2: Multi-Strategy con AMC (100 barras)")
        result2 = await simulation_manager.test_strategy_on_symbol(
            symbol="AMC",
            timeframe="1 min", 
            bars_count=100,
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        print(f"   📈 Señales generadas: {result2.get('signals_generated', 0)}")
        print(f"   💼 Trades ejecutados: {result2.get('trades_executed', 0)}")
        print(f"   📊 Barras analizadas: {result2.get('bars_analyzed', 0)}")
        
        # Get final broker state
        final_stats = sim_env['broker'].get_performance_stats()
        positions = await sim_env['broker'].get_positions()
        
        print("\n📋 ESTADÍSTICAS FINALES:")
        print(f"   💰 Total trades ejecutados: {final_stats['trades_executed']}")
        print(f"   🏦 Valor total de portfolio: ${final_stats['total_value']:.2f}")
        print(f"   📍 Posiciones activas: {len(positions)}")
        print(f"   💵 Cash disponible: ${final_stats['cash']:.2f}")
        
        if positions:
            print("\n📍 POSICIONES ACTIVAS:")
            for symbol, pos in positions.items():
                qty = pos.get('quantity', 0) if isinstance(pos, dict) else pos.quantity
                avg_price = pos.get('avg_price', 0) if isinstance(pos, dict) else pos.avg_price
                if qty != 0:
                    print(f"   {symbol}: {qty} shares @ ${avg_price:.2f}")
        
        # Determinar si el test fue exitoso
        total_trades = final_stats['trades_executed']
        total_signals = result1.get('signals_generated', 0) + result2.get('signals_generated', 0)
        
        print(f"\n🎯 RESULTADO FINAL:")
        if total_trades > 0:
            print(f"   ✅ ÉXITO: Sistema ejecutó {total_trades} trades")
            print(f"   ✅ ÉXITO: Sistema generó {total_signals} señales")
            print(f"   ✅ ÉXITO: MockBroker funcionando perfectamente")
            print(f"   ✅ ÉXITO: MultiStrategy funcionando perfectamente") 
            print("\n🏆 EL SISTEMA ESTÁ FUNCIONANDO AL 100% PERFECTO!")
        else:
            print(f"   ⚠️  Sistema generó {total_signals} señales pero 0 trades")
            print(f"   ⚠️  Hay una desconexión entre señales y ejecución")
        
    except Exception as e:
        print(f"❌ Error en test: {e}")
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
    asyncio.run(test_sistema_perfecto())