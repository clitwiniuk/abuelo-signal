#!/usr/bin/env python3
"""
Test específico de las reglas de day trading
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def test_daytrading_rules():
    """Test las reglas de day trading - no overnight positions"""
    
    print("🔍 TESTING DAY TRADING RULES")
    print("=" * 60)
    print("🎯 Verificando que no haya posiciones overnight")
    
    # Setup logging
    logging.basicConfig(level=logging.ERROR)  # Solo errores críticos
    
    try:
        # Setup
        sim_env = setup_simulation_environment()
        simulation_manager = sim_env['simulation_manager']
        
        # Initialize
        await simulation_manager.initialize(create_sample_data=False)
        await sim_env['broker'].connect()
        await sim_env['data_provider'].connect()
        
        print("✅ Sistema inicializado")
        
        # Test con XXII - 1000 barras para ver múltiples días
        print(f"\n🎯 TEST CON XXII (1000 barras - múltiples días)")
        print("-" * 50)
        
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=1000,  # Más barras para ver varios días
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        final_stats = result.get('final_stats', {})
        trades_executed = result.get('trades_executed', 0)
        
        print(f"\n📊 RESULTADOS:")
        print(f"   ✅ Trades ejecutados: {trades_executed}")
        print(f"   💰 P&L Total: ${final_stats.get('total_pnl', 0):.2f}")
        print(f"   🎯 Win Rate: {final_stats.get('win_rate', 0):.2f}%")
        
        # Mostrar reporte detallado y analizar duraciones
        if trades_executed > 0:
            print(f"\n" + "="*80)
            print("📋 VERIFICACIÓN DE REGLAS DAY TRADING")
            print("="*80)
            
            # Obtener historial detallado
            trade_history = simulation_manager.mock_broker.get_detailed_trade_history()
            
            print(f"\n🔍 ANÁLISIS DE DURACIONES:")
            overnight_trades = 0
            max_duration_minutes = 0
            
            for i, trade in enumerate(trade_history, 1):
                duration_hours = trade['duration_minutes'] / 60
                if duration_hours > 8:  # Más de 8 horas = overnight
                    overnight_trades += 1
                    print(f"❌ Trade #{i}: {duration_hours:.1f}h - OVERNIGHT! (Day trading violation)")
                else:
                    print(f"✅ Trade #{i}: {duration_hours:.1f}h - Dentro de sesión")
                
                if trade['duration_minutes'] > max_duration_minutes:
                    max_duration_minutes = trade['duration_minutes']
            
            print(f"\n📈 RESUMEN DAY TRADING:")
            print(f"   Total trades: {len(trade_history)}")
            print(f"   ❌ Trades overnight: {overnight_trades}")
            print(f"   ✅ Trades intraday: {len(trade_history) - overnight_trades}")
            print(f"   ⏱️ Duración máxima: {max_duration_minutes/60:.1f} horas")
            
            if overnight_trades == 0:
                print(f"\n🎉 ¡EXCELENTE! Todas las posiciones respetan las reglas de day trading")
            else:
                print(f"\n⚠️ PROBLEMA: {overnight_trades} trades violaron las reglas de day trading")
            
            # Mostrar reporte detallado
            print(f"\n" + "="*80)
            print("📋 REPORTE DETALLADO DE TRADES")
            print("="*80)
            simulation_manager.mock_broker.print_detailed_trade_report()
            
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
    asyncio.run(test_daytrading_rules())