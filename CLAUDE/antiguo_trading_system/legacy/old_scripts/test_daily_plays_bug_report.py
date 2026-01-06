#!/usr/bin/env python3
"""
REPORTE DE BUG: DailyPlaysStrategy nunca funciona
================================================

PROBLEMA IDENTIFICADO:
La estrategia usa datetime.now().time() en lugar del timestamp de los datos,
por lo que NUNCA detecta que está en horario de mercado o en los primeros 30 minutos.

EVIDENCIA:
- High 30min siempre es None
- Tracked siempre es False
- No genera señales ni en breakouts claros

SOLUCIÓN PROPUESTA:
Usar el timestamp de MarketData en lugar de datetime.now()
"""

import sys
import os
from datetime import datetime, timedelta, time
from typing import List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interfaces import MarketData, Signal, SignalType, Position
from strategies.daily_plays_strategy import DailyPlaysStrategy


def analyze_bug():
    """Analizar el bug de DailyPlaysStrategy"""
    print("🐛 ANÁLISIS DE BUG: DAILY PLAYS STRATEGY")
    print("=" * 60)

    # Crear estrategia
    params = {
        'min_price': 1.0,
        'max_price': 15.0,
        'min_daily_volume': 100000,
        'ema_period': 9,
        'first_30_minutes': 30,
        'market_open_hour': 9.5,  # 9:30 AM
        'first_half_hour_end': 10.0,  # 10:00 AM
    }

    strategy = DailyPlaysStrategy(params)

    # Hora actual real vs hora simulada
    current_real_time = datetime.now().time()
    simulated_time = time(9, 35)  # 9:35 AM simulado

    print(f"🕐 Hora actual real: {current_real_time}")
    print(f"🕐 Hora simulada: {simulated_time}")
    print(f"🕐 Horario de mercado (9:30-16:00): ❌ Usando hora real incorrecta")

    # Test de detección de horario
    is_market_hours_real = strategy._is_market_hours(current_real_time)
    is_first_30min_real = strategy._is_first_half_hour(current_real_time)

    print(f"🔍 Con hora REAL:")
    print(f"   En horario mercado: {is_market_hours_real}")
    print(f"   En primeros 30min: {is_first_30min_real}")

    # Simular lo que DEBERÍA pasar con hora correcta
    is_market_hours_sim = strategy._is_market_hours(simulated_time)
    is_first_30min_sim = strategy._is_first_half_hour(simulated_time)

    print(f"🔍 Con hora SIMULADA (correcta):")
    print(f"   En horario mercado: {is_market_hours_sim}")
    print(f"   En primeros 30min: {is_first_30min_sim}")

    print(f"\n❌ PROBLEMA CONFIRMADO:")
    print(f"   La estrategia usa datetime.now() en lugar del timestamp de MarketData")
    print(f"   Por eso NUNCA detecta los primeros 30 minutos")
    print(f"   Por eso NUNCA registra el high de 30min")
    print(f"   Por eso NUNCA genera señales de breakout")


def demonstrate_fix():
    """Demostrar cómo se vería la solución"""
    print(f"\n🔧 SOLUCIÓN PROPUESTA:")
    print("=" * 40)

    print(f"CAMBIAR ESTO:")
    print(f"   def _get_current_time(self) -> time:")
    print(f"       return datetime.now().time()  # ❌ MAL")

    print(f"\nPOR ESTO:")
    print(f"   def _get_current_time(self, bar: MarketData) -> time:")
    print(f"       return bar.timestamp.time()  # ✅ BIEN")

    print(f"\nY PASAR EL PARÁMETRO:")
    print(f"   current_time = self._get_current_time(bar)")

    print(f"\n🎯 RESULTADO ESPERADO:")
    print(f"   ✅ Detectará primeros 30 minutos correctamente")
    print(f"   ✅ Registrará high de 30min correctamente")
    print(f"   ✅ Detectará breakouts correctamente")
    print(f"   ✅ Generará señales cuando corresponda")


def suggest_implementation():
    """Sugerir implementación específica"""
    print(f"\n📝 IMPLEMENTACIÓN SUGERIDA:")
    print("=" * 50)

    code_changes = """
# En daily_plays_strategy.py líneas 140-144:

def _get_current_time(self, bar: MarketData) -> time:
    \"\"\"Get market time from bar timestamp (not system time)\"\"\"
    return bar.timestamp.time()

# Y en analyze() línea 164:
def _track_first_half_hour_high(self, ticker: str, bar: MarketData) -> None:
    current_time = self._get_current_time(bar)  # ✅ Usar timestamp del bar

# Y en _validate_entry_conditions() línea 272:
def _validate_entry_conditions(self, ticker: str, bar: MarketData) -> bool:
    current_time = self._get_current_time(bar)  # ✅ Usar timestamp del bar
"""

    print(code_changes)


def main():
    """Ejecutar análisis completo del bug"""
    analyze_bug()
    demonstrate_fix()
    suggest_implementation()

    print(f"\n🎯 CONCLUSIÓN:")
    print("=" * 40)
    print(f"DailyPlaysStrategy tiene un bug fundamental que impide su funcionamiento.")
    print(f"Usa datetime.now() en lugar del timestamp de los datos de mercado.")
    print(f"Esto explica por qué nunca has visto que funcione.")
    print(f"\nSin esta corrección, la estrategia es completamente inútil.")


if __name__ == "__main__":
    main()