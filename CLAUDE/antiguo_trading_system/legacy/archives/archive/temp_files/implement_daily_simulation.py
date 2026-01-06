#!/usr/bin/env python3
"""
Implementar simulación día por día independiente para operativa intraday
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def simulate_daily_sessions(symbol: str, days_back: int = 30):
    """
    Simular operativa intraday día por día de forma independiente
    
    Args:
        symbol: Símbolo a simular (ej: "GV")
        days_back: Número de días hacia atrás a simular
    """
    
    print(f"🔄 SIMULACIÓN INTRADAY POR DÍAS INDEPENDIENTES")
    print(f"📊 Símbolo: {symbol} | Días a simular: {days_back}")
    print("=" * 60)
    
    # Calcular fechas
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_back)
    
    print(f"📅 Período: {start_date} a {end_date}")
    print(f"🎯 Cada día se simula INDEPENDIENTEMENTE (solo datos de ese día)")
    
    # Resultados consolidados
    all_results = {
        'total_days_simulated': 0,
        'days_with_trades': 0,
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'total_pnl': 0.0,
        'total_commissions': 0.0,
        'daily_results': []
    }
    
    current_date = start_date
    
    while current_date <= end_date:
        print(f"\n{'='*20} {current_date.strftime('%Y-%m-%d')} {'='*20}")
        
        # Crear entorno fresco para cada día
        sim_env = setup_simulation_environment()
        simulation_manager = sim_env['simulation_manager']
        broker = sim_env['broker']
        data_provider = sim_env['data_provider']
        
        await simulation_manager.initialize(create_sample_data=False)
        await broker.connect()
        await data_provider.connect()
        
        try:
            # Obtener datos SOLO de este día específico
            print(f"📊 Obteniendo datos intraday para {current_date.strftime('%Y-%m-%d')}...")
            
            # Aquí necesitaríamos el método para obtener datos de un día específico
            # Por ahora simularemos con datos de ejemplo
            daily_data = await get_daily_intraday_data(symbol, current_date, data_provider)
            
            if not daily_data:
                print(f"   ⚪ No hay datos para {current_date} - saltando día")
                current_date += timedelta(days=1)
                continue
            
            print(f"   📈 Encontradas {len(daily_data)} barras intraday")
            
            # Simular SOLO con datos de este día
            day_result = await simulate_single_day(
                simulation_manager, 
                broker,
                symbol, 
                current_date, 
                daily_data
            )
            
            # Procesar resultados del día
            all_results['total_days_simulated'] += 1
            
            if day_result['trades_executed'] > 0:
                all_results['days_with_trades'] += 1
                all_results['total_trades'] += day_result['trades_executed']
                all_results['winning_trades'] += day_result.get('winning_trades', 0)
                all_results['losing_trades'] += day_result.get('losing_trades', 0)
                all_results['total_pnl'] += day_result.get('pnl', 0.0)
                all_results['total_commissions'] += day_result.get('commissions', 0.0)
                
                print(f"   ✅ Día con trading:")
                print(f"      Trades: {day_result['trades_executed']}")
                print(f"      P&L: ${day_result.get('pnl', 0.0):.2f}")
                print(f"      Comisiones: ${day_result.get('commissions', 0.0):.2f}")
                
                # Mostrar reporte del día
                broker.print_detailed_trade_report()
            else:
                print(f"   ⚪ Día sin trades")
            
            # Guardar resultados del día
            day_summary = {
                'date': current_date.strftime('%Y-%m-%d'),
                'trades_executed': day_result['trades_executed'],
                'pnl': day_result.get('pnl', 0.0),
                'commissions': day_result.get('commissions', 0.0),
                'signals_generated': day_result.get('signals_generated', 0)
            }
            all_results['daily_results'].append(day_summary)
            
        except Exception as e:
            print(f"   ❌ Error simulando {current_date}: {e}")
            
        finally:
            # Limpiar conexiones
            try:
                await broker.disconnect()
                await data_provider.disconnect()
            except:
                pass
        
        current_date += timedelta(days=1)
    
    # Mostrar resumen consolidado
    print_consolidated_results(all_results)
    
    return all_results

async def get_daily_intraday_data(symbol: str, date: datetime.date, data_provider):
    """Obtener datos intraday SOLO de un día específico"""
    
    # Por ahora retornamos una lista vacía como placeholder
    # En la implementación real, esto consultaría la fuente de datos
    # filtrando solo las barras de la fecha específica
    
    try:
        # Ejemplo de cómo sería la lógica:
        # daily_bars = await data_provider.get_intraday_data(
        #     symbol=symbol,
        #     date=date,
        #     timeframe="1m"
        # )
        # return daily_bars
        
        # Placeholder - retornar lista vacía por ahora
        return []
        
    except Exception as e:
        print(f"Error obteniendo datos para {symbol} en {date}: {e}")
        return []

async def simulate_single_day(simulation_manager, broker, symbol: str, date: datetime.date, daily_data: List):
    """Simular un único día de operativa"""
    
    # Placeholder para la simulación de un día
    # En la implementación real, esto procesaría las barras del día
    # y ejecutaría la estrategia
    
    result = {
        'trades_executed': 0,
        'signals_generated': 0,
        'pnl': 0.0,
        'commissions': 0.0,
        'winning_trades': 0,
        'losing_trades': 0
    }
    
    # Aquí iría la lógica real de simulación
    # Por ahora retornamos resultado vacío
    
    return result

def print_consolidated_results(results: Dict[str, Any]):
    """Mostrar resultados consolidados de todos los días"""
    
    print(f"\n" + "="*60)
    print(f"📊 RESUMEN CONSOLIDADO - SIMULACIÓN INTRADAY")
    print(f"="*60)
    
    print(f"📅 Días simulados: {results['total_days_simulated']}")
    print(f"📈 Días con trades: {results['days_with_trades']}")
    print(f"💼 Total trades: {results['total_trades']}")
    
    if results['total_trades'] > 0:
        win_rate = (results['winning_trades'] / results['total_trades']) * 100
        print(f"✅ Trades ganadores: {results['winning_trades']}")
        print(f"❌ Trades perdedores: {results['losing_trades']}")
        print(f"📊 Win Rate: {win_rate:.1f}%")
        print(f"💰 P&L Total: ${results['total_pnl']:.2f}")
        print(f"💸 Comisiones: ${results['total_commissions']:.2f}")
        print(f"💵 P&L Neto: ${results['total_pnl'] - results['total_commissions']:.2f}")
    
    print(f"\n📋 BREAKDOWN POR DÍA:")
    print(f"{'Fecha':<12} {'Trades':<8} {'P&L':<10} {'Señales':<8}")
    print(f"-" * 40)
    
    for day in results['daily_results']:
        if day['trades_executed'] > 0:
            print(f"{day['date']:<12} {day['trades_executed']:<8} ${day['pnl']:>6.2f}   {day['signals_generated']:<8}")
    
    print(f"\n💡 VENTAJAS DE ESTA IMPLEMENTACIÓN:")
    print(f"   ✅ Cada día es independiente (no mezcla datos)")
    print(f"   ✅ Resultados consistentes y reproducibles") 
    print(f"   ✅ Apropiado para operativa intraday")
    print(f"   ✅ Fácil identificar días rentables vs no rentables")

if __name__ == "__main__":
    # Ejemplo de uso
    asyncio.run(simulate_daily_sessions("GV", days_back=30))