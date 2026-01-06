#!/usr/bin/env python3
"""
Validación de Fidelidad del Sistema de Replay

Este script compara trades reales ejecutados vs replay simulado para validar
que el sistema de replay replica fielmente el comportamiento del sistema real.

Analiza:
1. Decisiones de entry: ¿El replay entraría en los mismos trades?
2. Decisiones de exit: ¿El replay saldría al mismo precio/tiempo?
3. Precios: ¿Usa los mismos precios que IBKR?
4. Stop loss: ¿Respeta los mismos stops?
5. Pattern completion: ¿Calcula lo mismo que el worker real?
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import sys
from typing import Dict, List, Tuple

# Definir umbrales de tolerancia
PRICE_TOLERANCE_PCT = 2.0  # 2% diferencia aceptable en precios
TIME_TOLERANCE_MINUTES = 5  # 5 minutos diferencia aceptable en timing
PNL_TOLERANCE_PCT = 5.0  # 5% diferencia aceptable en P&L


class ReplayFidelityValidator:
    """Valida la fidelidad del sistema de replay"""

    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)

    def get_recent_real_trades(self, days: int = 7, worker: str = None) -> pd.DataFrame:
        """
        Obtiene trades reales recientes de la DB

        Args:
            days: Últimos N días
            worker: Filtrar por worker específico (opcional)

        Returns:
            DataFrame con trades reales
        """
        query = """
        SELECT
            trade_id,
            symbol,
            strategy,
            entry_price,
            actual_entry_price,
            exit_price,
            actual_exit_price,
            entry_time,
            actual_entry_time,
            exit_time,
            actual_exit_time,
            quantity,
            side,
            pnl,
            actual_pnl,
            stop_loss_price,
            trailing_stop_price,
            exit_reason,
            status
        FROM trades
        WHERE status = 'CLOSED'
          AND exit_time >= datetime('now', '-{} days')
          AND actual_pnl IS NOT NULL
        """.format(days)

        if worker:
            query += f" AND strategy = '{worker}'"

        query += " ORDER BY exit_time DESC"

        df = pd.read_sql_query(query, self.conn)
        return df

    def get_replay_trades_for_date(self, date: str, worker: str) -> pd.DataFrame:
        """
        Obtiene trades de replay para una fecha específica

        NOTA: Esto requiere que hayas ejecutado replay_testing previamente
        y guardado los resultados en una tabla replay_trades

        Args:
            date: Fecha en formato YYYY-MM-DD
            worker: Nombre del worker

        Returns:
            DataFrame con trades de replay
        """
        # Primero verificamos si existe la tabla replay_trades
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='replay_trades'
        """)

        if not cursor.fetchone():
            print("⚠️  WARNING: Tabla 'replay_trades' no encontrada")
            print("   Necesitas ejecutar el replay primero y guardar resultados")
            return pd.DataFrame()

        query = """
        SELECT
            symbol,
            strategy,
            entry_price,
            exit_price,
            entry_time,
            exit_time,
            quantity,
            pnl,
            stop_loss_price,
            exit_reason,
            status
        FROM replay_trades
        WHERE date(entry_time) = '{}'
          AND strategy = '{}'
        ORDER BY entry_time
        """.format(date, worker)

        df = pd.read_sql_query(query, self.conn)
        return df

    def compare_entry_decisions(
        self,
        real_trades: pd.DataFrame,
        replay_trades: pd.DataFrame
    ) -> Dict:
        """
        Compara decisiones de entrada entre real y replay

        Returns:
            Dict con análisis de comparación
        """
        results = {
            'total_real_trades': len(real_trades),
            'total_replay_trades': len(replay_trades),
            'matched_entries': 0,
            'missing_in_replay': [],
            'extra_in_replay': [],
            'price_discrepancies': [],
            'timing_discrepancies': []
        }

        # Intentar matchear cada trade real con replay
        for _, real_trade in real_trades.iterrows():
            symbol = real_trade['symbol']
            real_time = pd.to_datetime(real_trade['actual_entry_time'] or real_trade['entry_time'])
            real_price = real_trade['actual_entry_price'] or real_trade['entry_price']

            # Buscar match en replay (mismo símbolo, tiempo cercano)
            matches = replay_trades[
                (replay_trades['symbol'] == symbol) &
                (abs((pd.to_datetime(replay_trades['entry_time']) - real_time).dt.total_seconds()) < TIME_TOLERANCE_MINUTES * 60)
            ]

            if len(matches) == 0:
                results['missing_in_replay'].append({
                    'symbol': symbol,
                    'entry_time': str(real_time),
                    'entry_price': real_price
                })
            else:
                results['matched_entries'] += 1

                # Comparar precio
                replay_price = matches.iloc[0]['entry_price']
                price_diff_pct = abs(replay_price - real_price) / real_price * 100

                if price_diff_pct > PRICE_TOLERANCE_PCT:
                    results['price_discrepancies'].append({
                        'symbol': symbol,
                        'real_price': real_price,
                        'replay_price': replay_price,
                        'diff_pct': price_diff_pct
                    })

                # Comparar timing
                replay_time = pd.to_datetime(matches.iloc[0]['entry_time'])
                time_diff_seconds = abs((replay_time - real_time).total_seconds())

                if time_diff_seconds > TIME_TOLERANCE_MINUTES * 60:
                    results['timing_discrepancies'].append({
                        'symbol': symbol,
                        'real_time': str(real_time),
                        'replay_time': str(replay_time),
                        'diff_seconds': time_diff_seconds
                    })

        # Buscar trades en replay que NO están en real (falsos positivos)
        for _, replay_trade in replay_trades.iterrows():
            symbol = replay_trade['symbol']
            replay_time = pd.to_datetime(replay_trade['entry_time'])

            matches = real_trades[
                (real_trades['symbol'] == symbol) &
                (abs((pd.to_datetime(real_trades['actual_entry_time'] or real_trades['entry_time']) - replay_time).dt.total_seconds()) < TIME_TOLERANCE_MINUTES * 60)
            ]

            if len(matches) == 0:
                results['extra_in_replay'].append({
                    'symbol': symbol,
                    'entry_time': str(replay_time),
                    'entry_price': replay_trade['entry_price']
                })

        # Calcular métricas de fidelidad
        if results['total_real_trades'] > 0:
            results['match_rate'] = results['matched_entries'] / results['total_real_trades'] * 100
        else:
            results['match_rate'] = 0.0

        results['false_positive_rate'] = len(results['extra_in_replay']) / max(results['total_replay_trades'], 1) * 100
        results['missing_rate'] = len(results['missing_in_replay']) / max(results['total_real_trades'], 1) * 100

        return results

    def compare_pnl(
        self,
        real_trades: pd.DataFrame,
        replay_trades: pd.DataFrame
    ) -> Dict:
        """
        Compara P&L entre real y replay
        """
        results = {
            'real_total_pnl': real_trades['actual_pnl'].sum(),
            'replay_total_pnl': 0,
            'pnl_difference': 0,
            'pnl_diff_pct': 0,
            'trade_by_trade': []
        }

        if len(replay_trades) > 0:
            results['replay_total_pnl'] = replay_trades['pnl'].sum()
            results['pnl_difference'] = results['replay_total_pnl'] - results['real_total_pnl']

            if results['real_total_pnl'] != 0:
                results['pnl_diff_pct'] = abs(results['pnl_difference']) / abs(results['real_total_pnl']) * 100

        return results

    def print_validation_report(self, worker: str, results: Dict):
        """Imprime reporte de validación"""
        print("=" * 80)
        print(f"REPLAY FIDELITY VALIDATION REPORT - {worker}")
        print("=" * 80)
        print()

        print("📊 ENTRY DECISIONS COMPARISON")
        print("-" * 80)
        print(f"Real trades executed:      {results['total_real_trades']}")
        print(f"Replay trades executed:    {results['total_replay_trades']}")
        print(f"Matched entries:           {results['matched_entries']}")
        print(f"Match rate:                {results['match_rate']:.1f}%")
        print()

        if results['match_rate'] >= 95:
            print("✅ EXCELENTE: Match rate >95% - Replay es muy fiel")
        elif results['match_rate'] >= 80:
            print("⚠️  ACEPTABLE: Match rate 80-95% - Algunas discrepancias")
        else:
            print("❌ POBRE: Match rate <80% - Replay NO es confiable")
        print()

        print("🔍 DISCREPANCIES ANALYSIS")
        print("-" * 80)
        print(f"Missing in replay:         {len(results['missing_in_replay'])} ({results['missing_rate']:.1f}%)")
        print(f"Extra in replay (FP):      {len(results['extra_in_replay'])} ({results['false_positive_rate']:.1f}%)")
        print(f"Price discrepancies:       {len(results['price_discrepancies'])}")
        print(f"Timing discrepancies:      {len(results['timing_discrepancies'])}")
        print()

        # Mostrar detalles de trades missing
        if results['missing_in_replay']:
            print("⚠️  MISSING IN REPLAY (Real trades NOT replicated):")
            for trade in results['missing_in_replay'][:5]:  # Top 5
                print(f"   - {trade['symbol']}: ${trade['entry_price']:.2f} at {trade['entry_time']}")
            if len(results['missing_in_replay']) > 5:
                print(f"   ... and {len(results['missing_in_replay']) - 5} more")
            print()

        # Mostrar detalles de trades extra
        if results['extra_in_replay']:
            print("⚠️  EXTRA IN REPLAY (False positives):")
            for trade in results['extra_in_replay'][:5]:  # Top 5
                print(f"   - {trade['symbol']}: ${trade['entry_price']:.2f} at {trade['entry_time']}")
            if len(results['extra_in_replay']) > 5:
                print(f"   ... and {len(results['extra_in_replay']) - 5} more")
            print()

        # Mostrar price discrepancies
        if results['price_discrepancies']:
            print("💰 PRICE DISCREPANCIES:")
            for disc in results['price_discrepancies'][:5]:
                print(f"   - {disc['symbol']}: Real ${disc['real_price']:.2f} vs Replay ${disc['replay_price']:.2f} ({disc['diff_pct']:.1f}% diff)")
            if len(results['price_discrepancies']) > 5:
                print(f"   ... and {len(results['price_discrepancies']) - 5} more")
            print()

        print("=" * 80)
        print()

    def validate_worker(self, worker: str, days: int = 7):
        """
        Valida fidelidad para un worker específico

        Args:
            worker: Nombre del worker (ej: 'daily_plays', 'vcp_smallcap')
            days: Días hacia atrás para analizar
        """
        print(f"\n🔍 Validating replay fidelity for worker: {worker}")
        print(f"   Analyzing last {days} days of trades...")
        print()

        # Obtener trades reales
        real_trades = self.get_recent_real_trades(days=days, worker=worker)

        if len(real_trades) == 0:
            print(f"❌ No real trades found for {worker} in last {days} days")
            return None

        print(f"✅ Found {len(real_trades)} real trades for {worker}")

        # NOTA: Aquí necesitarías tener los trades de replay guardados
        # Por ahora, vamos a asumir que NO hay tabla replay_trades
        # y daremos instrucciones de cómo generarla

        replay_trades = pd.DataFrame()  # Placeholder

        print("\n⚠️  WARNING: Replay comparison requires running replay first")
        print("   To generate replay data:")
        print(f"   1. Run: python replay_testing/test_{worker}_replay.py")
        print("   2. Save results to replay_trades table")
        print("   3. Re-run this validation")
        print()

        # Por ahora, solo analizamos los trades reales
        self.analyze_real_trades_quality(real_trades, worker)

        return real_trades

    def analyze_real_trades_quality(self, trades: pd.DataFrame, worker: str):
        """
        Analiza calidad de trades reales (sin comparar con replay)
        """
        print("=" * 80)
        print(f"REAL TRADES QUALITY ANALYSIS - {worker}")
        print("=" * 80)
        print()

        # Análisis básico
        total_pnl = trades['actual_pnl'].sum()
        avg_pnl = trades['actual_pnl'].mean()
        winners = (trades['actual_pnl'] > 0).sum()
        losers = (trades['actual_pnl'] < 0).sum()
        win_rate = winners / len(trades) * 100 if len(trades) > 0 else 0

        avg_winner = trades[trades['actual_pnl'] > 0]['actual_pnl'].mean() if winners > 0 else 0
        avg_loser = trades[trades['actual_pnl'] < 0]['actual_pnl'].mean() if losers > 0 else 0

        print(f"Total Trades:      {len(trades)}")
        print(f"Total P&L:         ${total_pnl:.2f}")
        print(f"Avg P&L/Trade:     ${avg_pnl:.2f}")
        print(f"Win Rate:          {win_rate:.1f}% ({winners}W / {losers}L)")
        print(f"Avg Winner:        ${avg_winner:.2f}")
        print(f"Avg Loser:         ${avg_loser:.2f}")

        if avg_loser != 0:
            rr_ratio = abs(avg_winner / avg_loser)
            print(f"R/R Ratio:         {rr_ratio:.2f}:1")

        print()

        # Análisis de slippage
        slippage_data = trades[
            (trades['actual_entry_price'].notna()) &
            (trades['entry_price'].notna())
        ]

        if len(slippage_data) > 0:
            slippage_data['entry_slippage_pct'] = (
                (slippage_data['actual_entry_price'] - slippage_data['entry_price']) /
                slippage_data['entry_price'] * 100
            )

            avg_slippage = slippage_data['entry_slippage_pct'].mean()
            max_slippage = slippage_data['entry_slippage_pct'].abs().max()

            print(f"SLIPPAGE ANALYSIS:")
            print(f"Avg Entry Slippage: {avg_slippage:+.2f}%")
            print(f"Max Entry Slippage: {max_slippage:.2f}%")

            # Identificar trades con slippage >5%
            high_slippage = slippage_data[slippage_data['entry_slippage_pct'].abs() > 5]
            if len(high_slippage) > 0:
                print(f"\n⚠️  {len(high_slippage)} trades with >5% slippage:")
                for _, trade in high_slippage.head(5).iterrows():
                    print(f"   {trade['symbol']}: {trade['entry_slippage_pct']:.1f}% slippage")

        print()
        print("=" * 80)
        print()


def main():
    """Main validation script"""
    validator = ReplayFidelityValidator()

    print("=" * 80)
    print("REPLAY FIDELITY VALIDATION SYSTEM")
    print("=" * 80)
    print()
    print("Este script valida que el sistema de replay replica fielmente")
    print("el comportamiento del sistema real de trading.")
    print()

    # Obtener top 3 workers por volumen de trades
    conn = sqlite3.connect("trading_data.db")
    top_workers = pd.read_sql_query("""
        SELECT
            strategy,
            COUNT(*) as trades,
            SUM(COALESCE(actual_pnl, pnl, 0)) as total_pnl,
            ROUND(AVG(COALESCE(actual_pnl, pnl, 0)), 2) as avg_pnl
        FROM trades
        WHERE status = 'CLOSED'
          AND actual_pnl IS NOT NULL
          AND exit_time >= datetime('now', '-30 days')
        GROUP BY strategy
        ORDER BY trades DESC
        LIMIT 3
    """, conn)
    conn.close()

    print("📊 Top 3 workers by volume (last 30 days):")
    print(top_workers.to_string(index=False))
    print()

    # Validar cada worker
    for _, row in top_workers.iterrows():
        worker = row['strategy']
        validator.validate_worker(worker, days=30)

    print("\n✅ Validation complete!")
    print("\nNEXT STEPS:")
    print("1. Review quality metrics above")
    print("2. If quality is good, run replay tests to generate comparison data")
    print("3. Re-run this script to compare replay vs real")


if __name__ == "__main__":
    main()
