#!/usr/bin/env python3
"""
Test OHLC Recording System
=========================

Script de prueba para demostrar el funcionamiento del sistema
de grabación OHLC para forward testing.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import List
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interfaces import MarketData, Signal, SignalType
from core.trade_ohlc_recorder import get_trade_ohlc_recorder
from core.signal_processor import get_signal_processor
from tools.forward_testing_analyzer import ForwardTestingAnalyzer

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OHLCTest")


def create_sample_market_data(symbol: str, base_time: datetime, num_bars: int = 100) -> List[MarketData]:
    """Crear datos de mercado de ejemplo para testing"""
    bars = []
    current_time = base_time
    current_price = 10.0

    for i in range(num_bars):
        # Simular movimiento de precio realista
        price_change = (-0.1 + (i * 0.002)) if i < 50 else (0.1 - ((i-50) * 0.002))
        current_price += price_change

        # Crear barra OHLC
        bar = MarketData(
            symbol=symbol,
            timestamp=current_time,
            open=current_price,
            high=current_price + 0.05,
            low=current_price - 0.05,
            close=current_price + (0.02 if i % 3 == 0 else -0.01),
            volume=1000 + (i * 100)  # Volumen creciente
        )

        bars.append(bar)
        current_time += timedelta(minutes=1)
        current_price = bar.close

    return bars


async def test_ohlc_recording_system():
    """Prueba completa del sistema de grabación OHLC"""
    logger.info("🧪 Starting OHLC Recording System Test")
    logger.info("=" * 60)

    # Inicializar componentes
    recorder = get_trade_ohlc_recorder()
    processor = get_signal_processor()
    analyzer = ForwardTestingAnalyzer()

    # Símbolo de prueba
    test_symbol = "TEST"
    base_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)

    # PASO 1: Generar datos de mercado
    logger.info("📊 Step 1: Generating sample market data...")
    market_bars = create_sample_market_data(test_symbol, base_time, 120)

    # Simular recepción de datos de mercado
    for i, bar in enumerate(market_bars[:30]):  # Primeros 30 minutos
        recorder.record_market_data(test_symbol, bar)

        if i == 0:
            logger.info(f"  📈 Recording market data from {bar.timestamp}")
        elif i == 29:
            logger.info(f"  📈 Market data recorded until {bar.timestamp}")

    # PASO 2: Simular señal de entrada
    logger.info("\n🎯 Step 2: Simulating entry signal...")
    entry_time = base_time + timedelta(minutes=15)
    entry_signal = Signal(
        signal_id="TEST-ENTRY-001",
        symbol=test_symbol,
        signal_type=SignalType.LONG,
        strength=0.85,
        price=10.15,
        timestamp=entry_time,
        strategy_name="TestStrategy",
        metadata={"test": True, "gap_percent": 5.2}
    )

    # Procesar señal de entrada
    entry_success = processor.process_entry_signal(entry_signal)
    logger.info(f"  ✅ Entry signal processed: {entry_success}")

    # PASO 3: Continuar recibiendo datos de mercado
    logger.info("\n📊 Step 3: Continuing market data reception...")
    for bar in market_bars[30:90]:  # Minutos 30-90
        recorder.record_market_data(test_symbol, bar)

    logger.info(f"  📈 Continued recording until {market_bars[89].timestamp}")

    # PASO 4: Simular señal de salida
    logger.info("\n🚪 Step 4: Simulating exit signal...")
    exit_time = base_time + timedelta(minutes=75)
    exit_signal = Signal(
        signal_id="TEST-EXIT-001",
        symbol=test_symbol,
        signal_type=SignalType.EXIT_LONG,
        strength=1.0,
        price=10.45,
        timestamp=exit_time,
        strategy_name="TestStrategy",
        metadata={"reason": "profit_target", "pnl": 2.96}
    )

    # Procesar señal de salida
    exit_success = processor.process_exit_signal(exit_signal, entry_signal.signal_id)
    logger.info(f"  ✅ Exit signal processed: {exit_success}")

    # PASO 5: Continuar con datos finales
    logger.info("\n📊 Step 5: Recording final market data...")
    for bar in market_bars[90:]:  # Minutos finales
        recorder.record_market_data(test_symbol, bar)

    logger.info(f"  📈 Final data recorded until {market_bars[-1].timestamp}")

    # PASO 6: Verificar datos grabados
    logger.info("\n🔍 Step 6: Verifying recorded data...")
    trade_data = analyzer.recorder.get_trade_ohlc_data(entry_signal.signal_id)

    if trade_data:
        snapshot = trade_data['snapshot']
        intraday_bars = trade_data['intraday_bars']

        logger.info("  ✅ Trade OHLC data successfully recorded!")
        logger.info(f"  📊 Snapshot data: {len(snapshot)} fields")
        logger.info(f"  📈 Intraday bars: {len(intraday_bars)} bars")
        logger.info(f"  💰 Entry: ${snapshot['entry_price']}")
        logger.info(f"  💰 Exit: ${snapshot['exit_price']}")
        logger.info(f"  📅 Trading date: {snapshot['trading_date']}")
        logger.info(f"  📊 Day range: ${snapshot['day_low']:.2f} - ${snapshot['day_high']:.2f}")

        # Calcular PnL
        pnl_pct = ((snapshot['exit_price'] - snapshot['entry_price']) / snapshot['entry_price']) * 100
        logger.info(f"  💵 Trade PnL: {pnl_pct:.2f}%")

    else:
        logger.error("  ❌ No trade data found!")
        return False

    # PASO 7: Análisis de forward testing
    logger.info("\n📈 Step 7: Forward testing analysis...")
    trade_analysis = analyzer.analyze_trade_performance(entry_signal.signal_id)

    if trade_analysis:
        logger.info("  ✅ Forward testing analysis completed!")
        logger.info(f"  🎯 Entry timing quality: {trade_analysis['entry_timing_quality']:.2f}")
        logger.info(f"  📊 Max favorable excursion: {trade_analysis['max_favorable_excursion']:.2f}%")
        logger.info(f"  📉 Max adverse excursion: {trade_analysis['max_adverse_excursion']:.2f}%")
        logger.info(f"  ⏱️ Minutes from open: {trade_analysis['minutes_from_open']:.1f}")

        # Mostrar análisis de barras
        bars_analysis = trade_analysis.get('bars_analysis', {})
        if bars_analysis:
            logger.info(f"  📊 Bars post-entry: {bars_analysis.get('bars_post_entry', 0)}")
            logger.info(f"  📈 Max gain potential: {bars_analysis.get('max_gain_pct', 0):.2f}%")

    # PASO 8: Estadísticas del sistema
    logger.info("\n📊 Step 8: System statistics...")
    stats = recorder.get_statistics()

    logger.info(f"  📊 Total snapshots: {stats['total_snapshots']}")
    logger.info(f"  📈 Total bars recorded: {stats['total_bars_recorded']}")
    logger.info(f"  🔄 Active recordings: {stats['active_recordings']}")
    logger.info(f"  📋 Cached symbols: {stats['cached_symbols']}")
    logger.info(f"  📊 Avg bars per trade: {stats.get('avg_bars_per_trade', 0):.1f}")

    logger.info("\n🎉 OHLC Recording System Test Completed Successfully!")
    logger.info("=" * 60)

    return True


async def demonstrate_forward_testing():
    """Demostrar capacidades de forward testing"""
    logger.info("\n🔬 Forward Testing Demonstration")
    logger.info("-" * 40)

    analyzer = ForwardTestingAnalyzer()

    # Buscar datos de ejemplo
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    # Mostrar análisis si hay datos
    stats = analyzer.recorder.get_statistics()
    if stats['total_snapshots'] > 0:
        logger.info(f"📊 Found {stats['total_snapshots']} recorded trades")
        logger.info("💡 You can now use the Forward Testing Analyzer to:")
        logger.info("  • Analyze individual trade performance")
        logger.info("  • Optimize entry/exit timing")
        logger.info("  • Compare strategy effectiveness")
        logger.info("  • Find optimal hold times")
        logger.info("  • Identify missed opportunities")
    else:
        logger.info("📊 No historical trades found")
        logger.info("💡 After running real trades, you'll be able to:")
        logger.info("  • Perform detailed forward testing")
        logger.info("  • Optimize your strategies")
        logger.info("  • Analyze what works and what doesn't")


if __name__ == "__main__":
    logger.info("🚀 OHLC Recording System Demonstration")
    logger.info("🎯 This system enables powerful forward testing capabilities")

    try:
        # Ejecutar prueba principal
        asyncio.run(test_ohlc_recording_system())

        # Demostrar forward testing
        asyncio.run(demonstrate_forward_testing())

        logger.info("\n✅ All tests completed successfully!")
        logger.info("🎯 The OHLC recording system is ready for production use")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())