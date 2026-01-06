#!/usr/bin/env python3
"""
Análisis de zona horaria para DailyPlaysStrategy
"""

import sys
import os
from datetime import datetime, timedelta, time
import pytz

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.daily_plays_strategy import DailyPlaysStrategy


def analyze_timezone_issue():
    """Analizar el problema de zona horaria"""
    print("🌍 ANÁLISIS DE ZONA HORARIA")
    print("=" * 50)

    # Hora actual en diferentes zonas
    now_utc = datetime.now(pytz.UTC)
    now_madrid = now_utc.astimezone(pytz.timezone('Europe/Madrid'))
    now_ny = now_utc.astimezone(pytz.timezone('America/New_York'))
    now_local = datetime.now()

    print(f"🕐 Hora local (sistema): {now_local.time()}")
    print(f"🕐 Hora Madrid: {now_madrid.time()}")
    print(f"🕐 Hora Nueva York: {now_ny.time()}")
    print(f"🕐 Horario mercado US: 9:30-16:00 EST/EDT")

    # Test de la estrategia
    strategy = DailyPlaysStrategy({})

    # Lo que hace la estrategia actualmente
    strategy_time = strategy._get_current_time()
    is_market_hours = strategy._is_market_hours(strategy_time)
    is_first_30min = strategy._is_first_half_hour(strategy_time)

    print(f"\n🔍 LO QUE HACE LA ESTRATEGIA:")
    print(f"   Tiempo usado: {strategy_time}")
    print(f"   En horario mercado: {is_market_hours}")
    print(f"   En primeros 30min: {is_first_30min}")

    # Simular datos de mercado a las 9:35 EST
    market_time_935 = time(9, 35)  # 9:35 AM EST
    market_time_1030 = time(10, 30)  # 10:30 AM EST

    print(f"\n🔍 CON DATOS REALES DE MERCADO:")
    print(f"   A las 9:35 EST:")
    print(f"     En horario mercado: {strategy._is_market_hours(market_time_935)}")
    print(f"     En primeros 30min: {strategy._is_first_half_hour(market_time_935)}")

    print(f"   A las 10:30 EST:")
    print(f"     En horario mercado: {strategy._is_market_hours(market_time_1030)}")
    print(f"     En primeros 30min: {strategy._is_first_half_hour(market_time_1030)}")


def demonstrate_real_problem():
    """Demostrar el problema real"""
    print(f"\n❌ EL PROBLEMA REAL:")
    print("=" * 40)

    print(f"1. La estrategia usa datetime.now() (hora local del servidor)")
    print(f"2. Los datos de MarketData tienen timestamp en EST/EDT")
    print(f"3. Nunca van a coincidir las horas")
    print(f"4. Por eso nunca detecta los primeros 30 minutos")

    print(f"\n📊 EJEMPLO PRÁCTICO:")
    print(f"   Datos de mercado: 2024-01-15 09:35:00 EST (horario real del mercado)")
    print(f"   datetime.now(): {datetime.now()} (hora local del servidor)")
    print(f"   ❌ NO COINCIDEN -> No detecta primeros 30min")

    print(f"\n✅ SOLUCIÓN:")
    print(f"   Usar bar.timestamp.time() en lugar de datetime.now().time()")
    print(f"   Así siempre usa la hora real de los datos de mercado")


def main():
    """Ejecutar análisis completo"""
    analyze_timezone_issue()
    demonstrate_real_problem()

    print(f"\n🎯 CONCLUSIÓN:")
    print("=" * 40)
    print(f"El problema NO es la zona horaria de España vs Nueva York.")
    print(f"El problema ES que usa datetime.now() en lugar del timestamp de los datos.")
    print(f"Los datos de mercado YA están en la zona horaria correcta (EST/EDT).")
    print(f"Solo hay que USAR esos timestamps en lugar de la hora del sistema.")


if __name__ == "__main__":
    main()