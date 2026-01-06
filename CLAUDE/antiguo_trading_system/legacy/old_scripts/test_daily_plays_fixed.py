#!/usr/bin/env python3
"""
Test para verificar que DailyPlaysStrategy está CORREGIDA
=========================================================

Ahora debería:
1. ✅ Detectar primeros 30 minutos correctamente
2. ✅ Registrar high de 30min correctamente
3. ✅ Detectar breakouts correctamente
4. ✅ Generar señales cuando corresponda
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


def test_corrected_daily_plays():
    """Test que DailyPlaysStrategy ahora funciona correctamente"""
    print("🔧 TEST DAILY PLAYS STRATEGY - VERSIÓN CORREGIDA")
    print("=" * 60)

    # Configurar estrategia
    params = {
        'min_price': 1.0,
        'max_price': 15.0,
        'min_daily_volume': 100000,
        'ema_period': 9,
        'first_30_minutes': 30,
        'volume_multiple_threshold': 2.0,
        'min_volume_for_signal': 150000,
        'lookback_bars': 8
    }

    strategy = DailyPlaysStrategy(params)
    symbol = "TEST"

    # Simular datos de mercado con timestamps reales
    base_date = datetime(2024, 1, 15, 9, 30)  # 9:30 AM EST
    market_data = []

    print("📊 CREANDO DATOS DE MERCADO:")

    # Primeros 30 minutos (9:30-10:00) - 6 barras de 5 minutos
    # PLUS: Datos históricos adicionales para cumplir requisito de 17 barras

    # Agregar 12 barras históricas antes del mercado (para cumplir ema_period=9 + lookback_bars=8)
    for j in range(12):
        timestamp = base_date - timedelta(days=j+1, hours=6, minutes=30)  # Días anteriores
        historical_bar = create_market_data(symbol, timestamp, 9.80, 10.10, 9.70, 9.90, 60000)
        market_data.append(historical_bar)

    # Ordenar cronológicamente
    market_data.sort(key=lambda x: x.timestamp)
    historical_count = len(market_data)
    print(f"   📈 {historical_count} barras históricas agregadas para EMA/Volume")

    for i in range(6):
        timestamp = base_date + timedelta(minutes=i*5)

        if i == 0:  # 9:30-9:35
            bar = create_market_data(symbol, timestamp, 10.00, 10.30, 9.95, 10.20, 80000)
        elif i == 1:  # 9:35-9:40 - HIGH de 30min
            bar = create_market_data(symbol, timestamp, 10.20, 10.50, 10.15, 10.45, 90000)
            print(f"   {timestamp.strftime('%H:%M')}: HIGH 30min = $10.50")
        elif i == 2:  # 9:40-9:45
            bar = create_market_data(symbol, timestamp, 10.45, 10.48, 10.25, 10.35, 70000)
        elif i == 3:  # 9:45-9:50
            bar = create_market_data(symbol, timestamp, 10.35, 10.42, 10.20, 10.30, 60000)
        elif i == 4:  # 9:50-9:55
            bar = create_market_data(symbol, timestamp, 10.30, 10.40, 10.25, 10.35, 55000)
        else:  # 9:55-10:00
            bar = create_market_data(symbol, timestamp, 10.35, 10.45, 10.30, 10.40, 50000)

        market_data.append(bar)

    # Barra de transición justo después de 30min para activar tracking
    timestamp = base_date + timedelta(minutes=30)  # 10:00 AM exacto
    transition_bar = create_market_data(symbol, timestamp, 10.40, 10.42, 10.35, 10.38, 45000)
    market_data.append(transition_bar)
    print(f"   {timestamp.strftime('%H:%M')}: Fin de 30min - debería activar tracking")

    # Post 30 minutos - Breakout
    timestamp = base_date + timedelta(minutes=35)  # 10:05 AM
    breakout_bar = create_market_data(symbol, timestamp, 10.40, 10.65, 10.38, 10.60, 200000)
    market_data.append(breakout_bar)
    print(f"   {timestamp.strftime('%H:%M')}: BREAKOUT $10.65 > $10.50 con volumen 200k")

    # Procesar todas las barras
    print(f"\n🔍 PROCESANDO BARRAS:")
    print("-" * 50)

    for i, bar in enumerate(market_data):
        print(f"\n📊 BARRA {i+1} - {bar.timestamp.strftime('%H:%M')}:")
        print(f"   Precio: ${bar.close:.2f}, High: ${bar.high:.2f}, Vol: {bar.volume:,}")

        # Procesar barra con estrategia
        try:
            # Simular datos históricos para volume check
            historical_data = market_data[:i+1]

            signal = strategy.analyze(symbol, historical_data, {})

            # Verificar estado interno
            high_30min = strategy.first_half_hour_highs.get(symbol)
            tracked = strategy.first_half_hour_tracked.get(symbol, False)

            if high_30min is not None:
                print(f"   📈 High 30min detectado: ${high_30min:.2f}")
            else:
                print(f"   📈 High 30min: None")

            print(f"   📊 Tracking completo: {tracked}")

            # Test de condiciones específicas
            current_time = strategy._get_current_time(bar)
            is_market_hours = strategy._is_market_hours(current_time)
            is_first_30min = strategy._is_first_half_hour(current_time)

            print(f"   🕐 Hora: {current_time}, Mercado: {is_market_hours}, 30min: {is_first_30min}")

            if signal:
                print(f"   🎯 ¡SEÑAL GENERADA!")
                print(f"      Tipo: {signal.signal_type}")
                print(f"      Precio: ${signal.price:.2f}")
                print(f"      Strength: {signal.strength:.2f}")
                print(f"      Metadata: {signal.metadata.get('entry_type', 'N/A')}")

                # Verificar breakout
                if high_30min and bar.high > high_30min:
                    print(f"      ✅ Breakout confirmado: ${bar.high:.2f} > ${high_30min:.2f}")
            else:
                print(f"   ❌ No hay señal")

                # Debug por qué no hay señal
                if i >= 6:  # Post 30min
                    if high_30min:
                        breakout_condition = strategy._check_price_breakout(symbol, bar)
                        print(f"      Debug - Breakout: {breakout_condition}")
                        if len(historical_data) >= 9:
                            volume_condition = strategy._check_volume_condition(symbol, historical_data)
                            print(f"      Debug - Volume: {volume_condition}")

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            print(f"   {traceback.format_exc()[:200]}...")

    # Resumen final
    print(f"\n📋 RESUMEN DEL TEST:")
    print("=" * 40)

    final_high = strategy.first_half_hour_highs.get(symbol)
    final_tracked = strategy.first_half_hour_tracked.get(symbol, False)

    if final_high:
        print(f"✅ High 30min detectado correctamente: ${final_high:.2f}")
    else:
        print(f"❌ High 30min NO detectado")

    if final_tracked:
        print(f"✅ Tracking de 30min completado")
    else:
        print(f"❌ Tracking de 30min NO completado")

    # Verificar breakout final
    breakout_bar = market_data[-1]
    if final_high and breakout_bar.high > final_high:
        print(f"✅ Breakout claro: ${breakout_bar.high:.2f} > ${final_high:.2f}")

    return strategy


def main():
    """Ejecutar test corregido"""
    print("🚀 VERIFICANDO CORRECCIÓN DE DAILY PLAYS STRATEGY")
    print("=" * 70)

    strategy = test_corrected_daily_plays()

    print(f"\n🎯 RESULTADO:")
    print("=" * 30)
    print(f"Si ves '✅ High 30min detectado' y '✅ Tracking completado',")
    print(f"entonces el bug está CORREGIDO y la estrategia funciona.")


if __name__ == "__main__":
    main()