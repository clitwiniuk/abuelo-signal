#!/usr/bin/env python3
"""
Test de la nueva configuración de horarios de trading
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, time

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def test_trading_hours_config():
    """Test de la configuración de horarios de trading"""
    
    print("🕐 TESTING TRADING HOURS CONFIGURATION")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(level=logging.ERROR)  # Solo errores críticos
    
    try:
        # Setup
        sim_env = setup_simulation_environment()
        config = sim_env['config']
        
        print(f"📊 Configuración cargada:")
        print(f"   Modo: {config.trading_hours_mode}")
        print(f"   Horario regular: {config.market_open_time}-{config.market_close_time} ET")
        
        if config.trading_hours_mode == "EXTENDED_HOURS":
            print(f"   Premarket: {config.premarket_start}-{config.premarket_end} ET")
            print(f"   Afterhours: {config.afterhours_start}-{config.afterhours_end} ET")
        
        # Test varios timestamps (en hora española - como vienen del CSV)
        test_times = [
            (datetime(2025, 7, 29, 8, 30), "02:30 ET - Cerrado"),    # 8:30 ES = 2:30 ET - Cerrado
            (datetime(2025, 7, 29, 10, 0), "04:00 ET - Premarket"),  # 10:00 ES = 4:00 ET - Premarket
            (datetime(2025, 7, 29, 16, 30), "10:30 ET - Regular"),   # 16:30 ES = 10:30 ET - Regular
            (datetime(2025, 7, 29, 20, 0), "14:00 ET - Regular"),    # 20:00 ES = 14:00 ET - Regular
            (datetime(2025, 7, 29, 23, 0), "17:00 ET - Afterhours"), # 23:00 ES = 17:00 ET - Afterhours
        ]
        
        print(f"\n🔍 TESTING HORARIOS (CSV en hora española):")
        print("-" * 60)
        
        for test_time, description in test_times:
            is_trading = config.is_trading_time(test_time)
            status = "✅ TRADING" if is_trading else "❌ CERRADO"
            print(f"   {test_time.strftime('%H:%M')} ES ({description}): {status}")
        
        # Test con datos reales
        print(f"\n🎯 TEST CON DATOS REALES - XXII")
        print("-" * 50)
        
        await sim_env['broker'].connect()
        await sim_env['data_provider'].connect()
        
        result = await sim_env['simulation_manager'].test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=100,  # Menos barras para test rápido
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        final_stats = result.get('final_stats', {})
        trades_executed = result.get('trades_executed', 0)
        
        print(f"\n📊 RESULTADOS:")
        print(f"   ✅ Trades ejecutados: {trades_executed}")
        print(f"   💰 P&L Total: ${final_stats.get('total_pnl', 0):.2f}")
        print(f"   📈 Win Rate: {final_stats.get('win_rate', 0):.2f}%")
        
        if trades_executed > 0:
            print(f"\n✅ SISTEMA FUNCIONA CON HORARIOS CONFIGURADOS")
        else:
            print(f"\n⚠️ Sin trades - verificar si los datos están en horario permitido")
            
        # Mostrar información de configuración
        print(f"\n📋 PARA CAMBIAR A HORARIO EXTENDIDO:")
        print(f"   1. Editar config.ini")
        print(f"   2. Cambiar: trading_hours_mode = EXTENDED_HOURS")
        print(f"   3. Reiniciar el sistema")
        print(f"\n💡 MODO ACTUAL: Solo mercado regular (9:30-16:00 ET)")
        print(f"   - Ideal para datos básicos sin suscripción ETH")
        print(f"   - Filtra automáticamente datos fuera de horario")
            
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
    asyncio.run(test_trading_hours_config())