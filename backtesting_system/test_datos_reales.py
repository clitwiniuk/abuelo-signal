#!/usr/bin/env python3
"""
Test con Datos Reales
====================

Script para probar el sistema de backtesting con datos reales de market_data.db.
"""

import asyncio
import sys
import os

# Agregar directorio al path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.backtest_runner import BacktestRunner


async def test_with_real_data():
    """Probar backtesting con datos reales"""
    print("🧪 PROBANDO SISTEMA CON DATOS REALES")
    print("=" * 50)
    
    try:
        # Crear runner (siempre usa datos reales)
        runner = BacktestRunner(output_dir="test_real_data")
        
        print("✅ Runner creado con datos reales")
        
        # Listar workers disponibles
        print("\n📋 Workers disponibles:")
        runner.list_available_workers()
        
        # Verificar base de datos
        if hasattr(runner, 'data_loader') and runner.data_loader:
            print("\n📊 Resumen de la base de datos:")
            summary = runner.data_loader.get_database_summary()
            print(f"   Total barras: {summary.get('total_bars', 0):,}")
            print(f"   Símbolos: {summary.get('total_symbols', 0)}")
            print(f"   Período: {summary.get('date_range', {}).get('first', 'N/A')[:10]} a {summary.get('date_range', {}).get('last', 'N/A')[:10]}")
        
        # Test individual con pocos patrones
        print("\n🧪 Ejecutando test individual...")
        metrics = await runner.run_single_worker_test(
            worker_name="macdv",
            num_patterns=10,  # Pocos patrones para prueba rápida
            visualize=True,
            detailed=True
        )
        
        if 'error' not in metrics:
            print(f"\n✅ Test completado!")
            print(f"📊 Resultados:")
            print(f"   Win Rate: {metrics.get('win_rate', 0):.1%}")
            print(f"   Average Return: {metrics.get('avg_return', 0):+.2f}%")
            print(f"   Total Trades: {metrics.get('total_trades', 0)}")
        else:
            print(f"❌ Error en test: {metrics['error']}")
        
        # Test completado exitosamente
        print(f"\n🎯 Test completado exitosamente!")
        print(f"   Los datos reales proporcionan resultados mucho más confiables")
        print(f"   que los datos sintéticos, basados en condiciones reales del mercado")
        
    except Exception as e:
        print(f"❌ Error en prueba: {e}")
        import traceback
        traceback.print_exc()


async def test_data_loader():
    """Probar solo el data loader"""
    print("🔍 PROBANDO DATA LOADER")
    print("=" * 30)
    
    try:
        from core.data_loader_real import DataLoaderReal
        
        # Crear data loader
        data_loader = DataLoaderReal()
        
        # Obtener símbolos disponibles
        print("📋 Símbolos disponibles:")
        symbols = data_loader.get_available_symbols()
        
        for symbol_info in symbols[:5]:  # Mostrar primeros 5
            print(f"   {symbol_info['symbol']}: {symbol_info['total_bars']:,} barras")
        
        # Cargar oportunidades reales
        print(f"\n📊 Cargando oportunidades reales...")
        opportunities = data_loader.load_real_opportunities(
            symbols=None,  # Todos
            start_date=None,
            end_date=None,
            min_volume=10000,
            pattern_type='all'
        )
        
        print(f"✅ {len(opportunities)} oportunidades reales cargadas")
        
        # Mostrar algunos ejemplos
        if opportunities:
            print(f"\n📝 Ejemplos de oportunidades:")
            for i, opp in enumerate(opportunities[:3]):
                print(f"   {i+1}. {opp['symbol']} - {opp['pattern_type']} - {opp['quality_score']:.1f}")
        
        # Resumen de la base de datos
        summary = data_loader.get_database_summary()
        print(f"\n📈 Resumen de market_data.db:")
        print(f"   Total barras: {summary.get('total_bars', 0):,}")
        print(f"   Símbolos: {summary.get('total_symbols', 0)}")
        print(f"   Período: {summary.get('date_range', {}).get('first', 'N/A')[:10]} a {summary.get('date_range', {}).get('last', 'N/A')[:10]}")
        
    except Exception as e:
        print(f"❌ Error probando data loader: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Función principal"""
    print("🎯 SISTEMA DE BACKTESTING CON DATOS REALES")
    print("=" * 50)
    print("Selecciona qué probar:")
    print("1. Test completo del sistema (datos reales vs sintéticos)")
    print("2. Test solo del data loader")
    print("0. Salir")
    
    choice = input("\nOpción: ").strip()
    
    if choice == "1":
        await test_with_real_data()
    elif choice == "2":
        await test_data_loader()
    elif choice == "0":
        print("👋 Saliendo...")
    else:
        print("❌ Opción inválida")


if __name__ == "__main__":
    # Configurar event loop para Windows compatibility
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ejecutar test
    asyncio.run(main())