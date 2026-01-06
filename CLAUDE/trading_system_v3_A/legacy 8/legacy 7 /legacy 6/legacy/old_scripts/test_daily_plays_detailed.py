#!/usr/bin/env python3
"""
Test detallado para DailyPlaysStrategy - Verificar si realmente funciona
el breakout del high de 30 minutos.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interfaces import MarketData, Signal, SignalType, Position
from strategies.daily_plays_strategy import DailyPlaysStrategy


def create_market_data(symbol: str, timestamp: datetime, open_price: float,
                      high: float, low: float, close: float, volume: int) -> MarketData:
    """Crear datos de mercado simulados"""
    return MarketData(
        symbol=symbol,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        vwap=(high + low + close) / 3,
        bid=close * 0.999,
        ask=close * 1.001,
        bid_size=1000,
        ask_size=1000
    )


def simulate_daily_plays_scenario() -> List[MarketData]:
    """
    Simular un escenario típico de Daily Plays:
    - 9:30-10:00: Primeros 30 minutos con high en $10.50
    - 10:01+: Breakout por encima de $10.50 con volumen
    """
    symbol = "TEST"
    base_date = datetime(2024, 1, 15, 9, 30)  # 9:30 AM
    data = []

    # Primeros 30 minutos (9:30-10:00) - 6 barras de 5 minutos
    print("📊 SIMULANDO PRIMEROS 30 MINUTOS:")
    for i in range(6):
        timestamp = base_date + timedelta(minutes=i*5)

        if i == 0:  # Primera barra 9:30-9:35
            bar = create_market_data(symbol, timestamp, 10.00, 10.30, 9.95, 10.20, 150000)
            print(f"   {timestamp.strftime('%H:%M')}: O=${bar.open} H=${bar.high} L=${bar.low} C=${bar.close} V={bar.volume}")
        elif i == 1:  # 9:35-9:40
            bar = create_market_data(symbol, timestamp, 10.20, 10.50, 10.15, 10.45, 200000)
            print(f"   {timestamp.strftime('%H:%M')}: O=${bar.open} H=${bar.high} L=${bar.low} C=${bar.close} V={bar.volume} ← HIGH 30min")
        elif i == 2:  # 9:40-9:45
            bar = create_market_data(symbol, timestamp, 10.45, 10.48, 10.25, 10.35, 120000)
            print(f"   {timestamp.strftime('%H:%M')}: O=${bar.open} H=${bar.high} L=${bar.low} C=${bar.close} V={bar.volume}")
        elif i == 3:  # 9:45-9:50
            bar = create_market_data(symbol, timestamp, 10.35, 10.42, 10.20, 10.30, 100000)
            print(f"   {timestamp.strftime('%H:%M')}: O=${bar.open} H=${bar.high} L=${bar.low} C=${bar.close} V={bar.volume}")
        elif i == 4:  # 9:50-9:55
            bar = create_market_data(symbol, timestamp, 10.30, 10.40, 10.25, 10.35, 80000)
            print(f"   {timestamp.strftime('%H:%M')}: O=${bar.open} H=${bar.high} L=${bar.low} C=${bar.close} V={bar.volume}")
        else:  # 9:55-10:00
            bar = create_market_data(symbol, timestamp, 10.35, 10.45, 10.30, 10.40, 90000)
            print(f"   {timestamp.strftime('%H:%M')}: O=${bar.open} H=${bar.high} L=${bar.low} C=${bar.close} V={bar.volume}")

        data.append(bar)

    print(f"\n✅ PRIMEROS 30MIN COMPLETADOS - HIGH: $10.50")

    # Post 30 minutos - Breakout scenario
    print(f"\n🚀 SIMULANDO BREAKOUT POST-30MIN:")

    # 10:00-10:05 - Breakout attempt 1
    timestamp = base_date + timedelta(minutes=30)
    bar = create_market_data(symbol, timestamp, 10.40, 10.52, 10.38, 10.51, 250000)
    print(f"   {timestamp.strftime('%H:%M')}: O=${bar.open} H=${bar.high} L=${bar.low} C=${bar.close} V={bar.volume} ← BREAKOUT!")
    data.append(bar)

    # 10:05-10:10 - Confirmation
    timestamp = base_date + timedelta(minutes=35)
    bar = create_market_data(symbol, timestamp, 10.51, 10.65, 10.48, 10.60, 300000)
    print(f"   {timestamp.strftime('%H:%M')}: O=${bar.open} H=${bar.high} L=${bar.low} C=${bar.close} V={bar.volume} ← MOMENTUM")
    data.append(bar)

    return data


def test_daily_plays_logic():
    """Test específico para DailyPlaysStrategy"""
    print("🧪 TESTING DAILY PLAYS STRATEGY")
    print("=" * 60)

    # Configurar parámetros
    params = {
        'min_price': 1.0,
        'max_price': 15.0,
        'min_daily_volume': 100000,
        'ema_period': 9,
        'first_30_minutes': 30,
        'volume_multiple_threshold': 2.0,
        'min_volume_for_signal': 200000
    }

    # Inicializar estrategia
    strategy = DailyPlaysStrategy(params)
    print(f"✅ DailyPlaysStrategy inicializada")

    # Simular datos
    market_data = simulate_daily_plays_scenario()

    # Procesar cada barra
    print(f"\n🔍 PROCESANDO BARRAS CON DAILYPLAYS:")
    print("-" * 60)

    for i, bar in enumerate(market_data):
        print(f"\n📊 BARRA {i+1} - {bar.timestamp.strftime('%H:%M')}:")
        print(f"   Precio: ${bar.close:.2f}, High: ${bar.high:.2f}, Volume: {bar.volume:,}")

        # Analizar barra
        try:
            signal = strategy.analyze("TEST", market_data[:i+1], {})

            if signal:
                print(f"   🎯 SEÑAL GENERADA!")
                print(f"      Tipo: {signal.signal_type}")
                print(f"      Precio: ${signal.price:.2f}")
                print(f"      Strength: {signal.strength:.2f}")
                print(f"      Metadata: {signal.metadata}")
            else:
                print(f"   ❌ No hay señal")

            # Verificar estado interno
            if hasattr(strategy, 'first_half_hour_highs'):
                high_30min = strategy.first_half_hour_highs.get("TEST")
                tracked = strategy.first_half_hour_tracked.get("TEST", False)
                if high_30min is not None:
                    print(f"   📈 High 30min: ${high_30min:.2f}, Tracked: {tracked}")
                else:
                    print(f"   📈 High 30min: None, Tracked: {tracked}")

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            print(f"   {traceback.format_exc()}")

    return strategy


def test_volume_conditions():
    """Test específico de condiciones de volumen"""
    print(f"\n🔍 TESTING CONDICIONES DE VOLUMEN:")
    print("-" * 40)

    # Simular datos con diferentes volúmenes
    symbol = "TEST"
    base_date = datetime(2024, 1, 15, 10, 0)

    # Crear estrategia
    params = {
        'volume_multiple_threshold': 2.0,
        'min_volume_for_signal': 200000
    }
    strategy = DailyPlaysStrategy(params)

    # Simular historial de volumen bajo
    low_volume_data = []
    for i in range(10):
        timestamp = base_date - timedelta(days=i+1)
        bar = create_market_data(symbol, timestamp, 10.0, 10.2, 9.8, 10.1, 50000)  # Volumen bajo
        low_volume_data.append(bar)

    # Barra actual con volumen alto
    current_bar = create_market_data(symbol, base_date, 10.0, 10.6, 10.0, 10.55, 250000)

    # Test condición de volumen - Inicializar volume_history si no existe
    if not hasattr(strategy, 'volume_history'):
        strategy.volume_history = {}
    strategy.volume_history[symbol] = [bar.volume for bar in low_volume_data]

    volume_condition = strategy._check_volume_condition(symbol, low_volume_data + [current_bar])
    avg_volume = sum(strategy.volume_history[symbol]) / len(strategy.volume_history[symbol])
    volume_ratio = current_bar.volume / avg_volume

    print(f"   Volumen promedio: {avg_volume:,.0f}")
    print(f"   Volumen actual: {current_bar.volume:,}")
    print(f"   Ratio: {volume_ratio:.1f}x")
    print(f"   Umbral requerido: {params['volume_multiple_threshold']}x")
    print(f"   Condición cumplida: {volume_condition}")


def main():
    """Ejecutar tests completos"""
    print("🚀 TEST DETALLADO DAILY PLAYS STRATEGY")
    print("=" * 80)

    # Test principal
    strategy = test_daily_plays_logic()

    # Test de volumen
    test_volume_conditions()

    # Resumen
    print(f"\n📋 RESUMEN:")
    print("-" * 40)
    print(f"✅ Test completado")
    print(f"🎯 Verificar si la estrategia detecta correctamente:")
    print(f"   1. High de primeros 30 minutos")
    print(f"   2. Breakout por encima del high")
    print(f"   3. Condiciones de volumen 2x+")
    print(f"   4. Generación de señal LONG")


if __name__ == "__main__":
    main()