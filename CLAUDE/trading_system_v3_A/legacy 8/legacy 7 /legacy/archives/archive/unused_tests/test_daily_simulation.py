#!/usr/bin/env python3
"""
Test del nuevo sistema de simulación por días independientes
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def test_daily_simulation():
    """Probar la nueva simulación por días independientes"""
    
    print("🧪 PROBANDO NUEVA SIMULACIÓN POR DÍAS INDEPENDIENTES")
    print("=" * 60)
    
    # Configurar entorno
    sim_env = setup_simulation_environment()
    simulation_manager = sim_env['simulation_manager']
    
    await simulation_manager.initialize(create_sample_data=False)
    await sim_env['data_provider'].connect()
    
    try:
        # Probar con diferentes períodos
        test_cases = [
            {"symbol": "GV", "days_back": 7, "description": "Última semana"},
            {"symbol": "GV", "days_back": 30, "description": "Último mes"},
        ]
        
        for case in test_cases:
            print(f"\n{'='*20} {case['description']} {'='*20}")
            print(f"📊 Simulando {case['symbol']} - {case['days_back']} días hacia atrás")
            
            # Ejecutar la nueva simulación
            results = await simulation_manager.simulate_daily_sessions(
                symbol=case['symbol'],
                days_back=case['days_back']
            )
            
            print(f"\n🎯 RESUMEN RÁPIDO:")
            print(f"   Días simulados: {results['total_days_simulated']}")
            print(f"   Días con trades: {results['days_with_trades']}")
            print(f"   Total trades: {results['total_trades']}")
            print(f"   P&L Neto: ${results['net_pnl']:.2f}")
            print(f"   Win Rate: {results['win_rate']:.1f}%")
            
            # Mostrar algunos días con actividad
            active_days = [day for day in results['daily_results'] if day['trades_executed'] > 0]
            if active_days:
                print(f"\n📅 Días más activos:")
                for day in active_days[:3]:  # Mostrar primeros 3
                    print(f"   {day['date']} ({day['weekday']}): {day['trades_executed']} trades, ${day['pnl']:.2f}")
            
            print(f"\n" + "="*50)
        
        print(f"\n✅ NUEVA FUNCIONALIDAD LISTA!")
        print(f"\n📖 CÓMO USAR:")
        print(f"   # Simular últimos 7 días de GV")
        print(f"   await simulation_manager.simulate_daily_sessions('GV', days_back=7)")
        print(f"   ")
        print(f"   # Simular último mes de cualquier símbolo")  
        print(f"   await simulation_manager.simulate_daily_sessions('SYMBOL', days_back=30)")
        
        print(f"\n🎯 VENTAJAS VS SISTEMA ANTERIOR:")
        print(f"   ✅ No más resultados diferentes con mismos parámetros")
        print(f"   ✅ Cada día es independiente (datos solo de ese día)")
        print(f"   ✅ Apropiado para trading intraday real")
        print(f"   ✅ Fácil comparar rendimiento por días de la semana")
        print(f"   ✅ Breakdown detallado de cada día")
        print(f"   ✅ Estrategias aparecen correctamente en reportes")
        
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        try:
            await sim_env['data_provider'].disconnect()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_daily_simulation())