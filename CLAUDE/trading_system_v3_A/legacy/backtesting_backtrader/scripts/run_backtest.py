#!/usr/bin/env python3
"""
Script para ejecutar backtests con las estrategias de Backtrader
"""

import sys
import os
import argparse
from datetime import datetime
import logging

# Agregar el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest_runner import run_single_backtest
from config.backtest_config import TEST_SYMBOLS, TEST_PERIODS, STRATEGY_CONFIGS
import sqlite3
import os

def main():
    parser = argparse.ArgumentParser(description='Ejecutar backtests con Backtrader')
    parser.add_argument('--strategy', '-s',
                       choices=list(STRATEGY_CONFIGS.keys()),
                       help='Nombre de la estrategia (no requerido con --all)')
    parser.add_argument('--symbol', '-sym',
                       help='Símbolo para backtest (ej: RR, ASST)')
    parser.add_argument('--event-id', '-eid', type=int,
                       help='ID del evento (requerido si no se usa --all-symbols)')
    parser.add_argument('--start-date', '-start',
                       help='Fecha inicio (YYYY-MM-DD)')
    parser.add_argument('--end-date', '-end',
                       help='Fecha fin (YYYY-MM-DD)')
    parser.add_argument('--all-events', action='store_true',
                       help='Ejecutar para todos los eventos disponibles en database.db')
    parser.add_argument('--all-periods', action='store_true',
                       help='Ejecutar para todos los períodos de prueba')
    parser.add_argument('--all', action='store_true',
                       help='Ejecutar TODAS las estrategias para TODOS los símbolos y TODOS los períodos')

    args = parser.parse_args()

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    try:
        # Comando simple para ejecutar TODO
        if args.all:
            run_complete_backtest()
            return

        # Validar argumentos para modos no --all
        if not args.strategy and not args.symbol:
            parser.error("Debe especificar --strategy o --symbol (o usar --all para ejecutar todo)")

        # Si se especifica símbolo, no requerir event-id
        if not args.symbol and not args.all_events and not args.event_id:
            parser.error("Debe especificar --event-id, --all-events, o --symbol")

        if args.all_events:
            # Ejecutar para todos los eventos
            run_for_all_events(args.strategy)
        elif args.all_periods:
            # Ejecutar para todos los períodos con el símbolo especificado
            if not args.symbol:
                parser.error("--all-periods requiere --symbol")
            run_for_all_periods(args.strategy, args.symbol)
        elif args.symbol:
            # Ejecutar backtest para un símbolo específico con estrategia específica
            print(f"Ejecutando backtest para {args.symbol} con estrategia {args.strategy}")
            try:
                # Usar período por defecto o especificado
                start_date = args.start_date or "2025-10-01"
                end_date = args.end_date or "2025-10-18"
                result = run_single_backtest(args.strategy, args.symbol, start_date, end_date)
                print(f"✅ Backtest completado para {args.strategy} - {args.symbol}")
                print(f"   Retorno total: {result['total_return']:.2f}%")
                print(f"   Sharpe Ratio: {result.get('sharpe_ratio', 'N/A')}")
                print(f"   Max Drawdown: {result.get('max_drawdown', 'N/A')}%")
                print(f"   Win Rate: {result.get('win_rate', 'N/A')}%")
            except Exception as e:
                print(f"❌ Error ejecutando backtest: {e}")
                sys.exit(1)
        else:
            # Ejecutar backtest individual
            if not args.event_id:
                parser.error("Backtest individual requiere --event-id")
            result = run_single_backtest(
                args.strategy,
                args.event_id,
                args.start_date,
                args.end_date
            )
            print(f"Backtest completado para {args.strategy} - event_{args.event_id}")

    except Exception as e:
        logging.error(f"Error ejecutando backtest: {e}")
        sys.exit(1)

def run_all_combinations(strategy_name):
    """Ejecutar backtest para todas las combinaciones símbolo-período"""
    print(f"Ejecutando {strategy_name} para todas las combinaciones...")

    results = []
    for symbol in TEST_SYMBOLS:
        for start_date, end_date in TEST_PERIODS:
            try:
                print(f"\n--- {strategy_name} - {symbol} - {start_date} a {end_date} ---")
                result = run_single_backtest(strategy_name, symbol, start_date, end_date)
                results.append({
                    'strategy': strategy_name,
                    'symbol': symbol,
                    'period': f"{start_date}_{end_date}",
                    'result': result
                })
            except Exception as e:
                print(f"Error con {symbol} {start_date}-{end_date}: {e}")
                continue

    # Resumen final
    print("\n" + "="*80)
    print("RESUMEN DE RESULTADOS")
    print("="*80)

    for result in results:
        total_return = result['result']['total_return']
        print(f"{result['strategy']} - {result['symbol']} - {result['period']}: {total_return:.2f}%")

def get_available_symbols():
    """Obtener lista de símbolos disponibles en market_data.db"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'market_data.db')
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM intraday_bars ORDER BY symbol")
        symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f"Encontrados {len(symbols)} símbolos en la base de datos")
        return symbols
    except Exception as e:
        print(f"Error obteniendo símbolos: {e}")
        # Intentar con ruta absoluta
        try:
            abs_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'market_data.db'))
            print(f"Intentando con ruta absoluta: {abs_db_path}")
            conn = sqlite3.connect(abs_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT symbol FROM intraday_bars ORDER BY symbol")
            symbols = [row[0] for row in cursor.fetchall()]
            conn.close()
            print(f"Encontrados {len(symbols)} símbolos con ruta absoluta")
            return symbols
        except Exception as e2:
            print(f"Error también con ruta absoluta: {e2}")
            return []  # fallback vacío

def get_available_events():
    """Obtener lista de eventos disponibles en database.db"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'clasificador_trades', 'database.db')
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT id_event FROM OHLCData ORDER BY id_event")
        events = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f"Encontrados {len(events)} eventos en la base de datos")
        return events
    except Exception as e:
        print(f"Error obteniendo eventos: {e}")
        print(f"Ruta intentada: {db_path}")
        return []

def run_for_all_events(strategy_name):
    """Ejecutar backtest para todos los eventos disponibles en database.db"""
    events = get_available_events()
    print(f"Ejecutando {strategy_name} para {len(events)} eventos disponibles...")

    results = []
    for i, event_id in enumerate(events[:50], 1):  # Procesar 50 eventos para testing rápido
        try:
            print(f"\n--- [{i}/{min(10, len(events))}] {strategy_name} - Event {event_id} ---")
            result = run_single_backtest(strategy_name, event_id)
            results.append({
                'event_id': event_id,
                'result': result
            })
        except Exception as e:
            print(f"Error con Event {event_id}: {e}")
            continue

    # Resumen final
    print(f"\n{'='*60}")
    total_events = 50
    print(f"RESUMEN - {strategy_name} (primeros {total_events} eventos)")
    print(f"{'='*60}")
    print(f"Total eventos procesados: {len(results)}/{total_events}")

    if results:
        total_returns = [r['result']['total_return'] for r in results]
        avg_return = sum(total_returns) / len(total_returns)
        profitable_trades = sum(1 for r in total_returns if r > 0)
        win_rate = profitable_trades / len(total_returns) * 100

        print(f"Retorno promedio: {avg_return:.2f}%")
        print(f"Win rate: {win_rate:.1f}%")
        print(f"Mejor resultado: {max(total_returns):.2f}%")
        print(f"Peor resultado: {min(total_returns):.2f}%")

def run_complete_backtest():
    """Ejecutar backtest completo: todas las estrategias, todos los símbolos, todos los períodos"""
    strategies = list(STRATEGY_CONFIGS.keys())
    symbols = get_available_symbols()

    print(f"🚀 INICIANDO BACKTEST COMPLETO (DAYTRADING)")
    print(f"Estrategias: {len(strategies)}")
    print(f"Símbolos: {len(symbols)}")
    print(f"Días de trading: {len(TEST_PERIODS)}")
    print(f"Total combinaciones: {len(strategies) * len(symbols) * len(TEST_PERIODS)}")
    print(f"{'='*80}")

    overall_results = {}

    for strategy_idx, strategy_name in enumerate(strategies, 1):
        print(f"\n📊 ESTRATEGIA {strategy_idx}/{len(strategies)}: {strategy_name}")
        print("-" * 60)

        strategy_results = []
        for symbol_idx, symbol in enumerate(symbols, 1):
            print(f"\n  🔄 Símbolo {symbol_idx}/{len(symbols)}: {symbol}")

            for period_idx, (start_date, end_date) in enumerate(TEST_PERIODS, 1):
                try:
                    print(f"    ⏱️  Día {period_idx}/{len(TEST_PERIODS)}: {start_date}")
                    result = run_single_backtest(strategy_name, symbol, start_date, end_date)

                    strategy_results.append({
                        'symbol': symbol,
                        'period': f"{start_date}_{end_date}",
                        'result': result
                    })

                except ValueError as e:
                    if "No hay datos disponibles" in str(e):
                        print(f"    ⚠️  Sin datos para {symbol} {start_date}-{end_date}")
                        continue
                    else:
                        print(f"    ❌ Error con {symbol} {start_date}-{end_date}: {e}")
                        continue
                except Exception as e:
                    print(f"    ❌ Error con {symbol} {start_date}-{end_date}: {e}")
                    continue

        # Resumen por estrategia
        if strategy_results:
            total_returns = [r['result']['total_return'] for r in strategy_results]
            avg_return = sum(total_returns) / len(total_returns)
            profitable_trades = sum(1 for r in total_returns if r > 0)
            win_rate = profitable_trades / len(total_returns) * 100

            overall_results[strategy_name] = {
                'total_backtests': len(strategy_results),
                'avg_return': avg_return,
                'win_rate': win_rate,
                'best_return': max(total_returns),
                'worst_return': min(total_returns)
            }

            print(f"\n  📈 RESULTADOS {strategy_name}:")
            print(f"    Total backtests: {len(strategy_results)}")
            print(f"    Retorno promedio: {avg_return:.2f}%")
            print(f"    Win rate: {win_rate:.1f}%")
            print(f"    Mejor: {max(total_returns):.2f}%")
            print(f"    Peor: {min(total_returns):.2f}%")

    # Resumen final completo
    print(f"\n{'='*80}")
    print("🏆 RESUMEN FINAL COMPLETO")
    print(f"{'='*80}")

    for strategy_name, results in overall_results.items():
        print(f"{strategy_name}:")
        print(f"  Retorno promedio: {results['avg_return']:.2f}%")
        print(f"  Win rate: {results['win_rate']:.1f}%")
        print(f"  Mejor resultado: {results['best_return']:.2f}%")
        print()

    print("✅ BACKTEST COMPLETO FINALIZADO")

def run_for_all_periods(strategy_name, symbol):
    """Ejecutar backtest para todos los períodos con un símbolo"""
    print(f"Ejecutando {strategy_name} para {symbol} en todos los períodos...")

    for start_date, end_date in TEST_PERIODS:
        try:
            print(f"\n--- {strategy_name} - {symbol} - {start_date} a {end_date} ---")
            result = run_single_backtest(strategy_name, symbol, start_date, end_date)
        except Exception as e:
            print(f"Error con período {start_date}-{end_date}: {e}")
            continue

if __name__ == "__main__":
    main()