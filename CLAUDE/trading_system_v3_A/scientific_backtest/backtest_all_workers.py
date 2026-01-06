#!/usr/bin/env python3
"""
Backtesting Multi-Worker - Comparación Masiva

Ejecuta backtests para TODOS los workers y genera reporte comparativo
para tomar decisión sobre cuáles mantener/eliminar.
"""

import asyncio
import sys
import os
import json
from datetime import datetime
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_worker_scientific import ScientificBacktester


class MultiWorkerBacktester:
    """Ejecuta y compara backtests de múltiples workers"""

    def __init__(self):
        self.backtester = ScientificBacktester()
        self.results = {}

    async def backtest_all_workers(
        self,
        workers: list,
        start_date: str = None,
        end_date: str = None,
        period_months: int = 2
    ):
        """
        Ejecuta backtest para lista de workers

        Args:
            workers: Lista de nombres de workers
            start_date: Fecha inicio
            end_date: Fecha fin
            period_months: Meses por período
        """
        print("=" * 100)
        print("BACKTESTING MULTI-WORKER - ANÁLISIS COMPARATIVO")
        print("=" * 100)
        print(f"\nWorkers a analizar: {', '.join(workers)}")
        print(f"Períodos: {period_months} meses por período\n")

        for worker in workers:
            print(f"\n{'='*100}")
            print(f"🔄 Processing worker: {worker}")
            print(f"{'='*100}\n")

            try:
                result = await self.backtester.backtest_worker(
                    worker_name=worker,
                    start_date=start_date,
                    end_date=end_date,
                    period_months=period_months
                )
                self.results[worker] = result

            except Exception as e:
                print(f"❌ Error with {worker}: {e}")
                self.results[worker] = {'error': str(e)}

        self.generate_comparison_report()

    def generate_comparison_report(self):
        """Genera reporte comparativo de todos los workers"""
        print("\n" + "=" * 100)
        print("📊 COMPARATIVE ANALYSIS - ALL WORKERS")
        print("=" * 100)
        print()

        # Crear DataFrame para comparación
        comparison_data = []

        for worker, result in self.results.items():
            if 'error' in result:
                continue

            rec = result.get('recommendation', {})

            comparison_data.append({
                'Worker': worker,
                'Action': rec.get('action', 'N/A'),
                'Total P&L': rec.get('total_pnl', 0),
                'Total Trades': rec.get('total_trades', 0),
                'Consistency %': rec.get('consistency_score', 0),
                'Avg WR %': rec.get('avg_win_rate', 0),
                'Avg PF': rec.get('avg_profit_factor', 0),
                'Size Adj': f"{rec.get('size_adjustment', 0)}x",
                'Periods': rec.get('periods_tested', 0)
            })

        if not comparison_data:
            print("⚠️  No valid results to compare")
            return

        df = pd.DataFrame(comparison_data)

        # Ordenar por P&L
        df = df.sort_values('Total P&L', ascending=False)

        print("RANKING BY PERFORMANCE:")
        print("-" * 100)
        print(df.to_string(index=False))
        print()

        # Resumen por acción
        print("\nSUMMARY BY ACTION:")
        print("-" * 100)

        actions = {
            'mantener': df[df['Action'].str.contains('MANTENER Y ESCALAR')],
            'revisar': df[df['Action'].str.contains('MONITOREAR')],
            'eliminar': df[df['Action'].str.contains('DESHABILITAR')]
        }

        for action_name, action_df in actions.items():
            if len(action_df) > 0:
                print(f"\n{action_name.upper()} ({len(action_df)} workers):")
                for worker in action_df['Worker'].values:
                    pnl = action_df[action_df['Worker'] == worker]['Total P&L'].values[0]
                    consistency = action_df[action_df['Worker'] == worker]['Consistency %'].values[0]
                    print(f"  - {worker}: ${pnl:,.2f} | {consistency:.0f}% consistency")

        print()
        print("=" * 100)
        print()

        # Recomendaciones finales
        print("🎯 NEXT ACTIONS:")
        print("-" * 100)

        mantener = len(actions['mantener'])
        eliminar = len(actions['eliminar'])

        if mantener > 0:
            print(f"\n✅ ESCALAR ({mantener} workers):")
            for worker in actions['mantener']['Worker'].values:
                print(f"   python scripts/update_worker_size.py --worker {worker} --multiplier 2")

        if eliminar > 0:
            print(f"\n❌ DESHABILITAR ({eliminar} workers):")
            for worker in actions['eliminar']['Worker'].values:
                print(f"   # Editar config.ini: set {worker}.enabled = false")

        print()
        print("=" * 100)
        print()

    def save_comparison_report(self, output_file: str = "backtest_comparison.json"):
        """Guarda reporte completo en JSON"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'workers_tested': len(self.results),
            'results': self.results
        }

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"✅ Full report saved to: {output_file}")

    def generate_html_report(self, output_file: str = "backtest_comparison.html"):
        """Genera reporte HTML interactivo"""
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Worker Backtest Comparison</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            margin: 40px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 30px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th {
            background: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
        }
        td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover {
            background: #f8f9fa;
        }
        .pass {
            color: #27ae60;
            font-weight: bold;
        }
        .fail {
            color: #e74c3c;
            font-weight: bold;
        }
        .marginal {
            color: #f39c12;
            font-weight: bold;
        }
        .positive {
            color: #27ae60;
        }
        .negative {
            color: #e74c3c;
        }
        .recommendation {
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .rec-keep {
            background: #d4edda;
            border-left: 4px solid #28a745;
        }
        .rec-review {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
        }
        .rec-remove {
            background: #f8d7da;
            border-left: 4px solid #dc3545;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 Worker Backtest Comparison Report</h1>
        <p>Generated: {timestamp}</p>

        <h2>📊 Performance Ranking</h2>
        {table}

        <h2>🎯 Recommendations</h2>
        {recommendations}
    </div>
</body>
</html>
"""

        # Generar tabla
        comparison_data = []
        for worker, result in self.results.items():
            if 'error' in result:
                continue
            rec = result.get('recommendation', {})
            comparison_data.append({
                'Worker': worker,
                'P&L': rec.get('total_pnl', 0),
                'Trades': rec.get('total_trades', 0),
                'Consistency': rec.get('consistency_score', 0),
                'WR': rec.get('avg_win_rate', 0),
                'PF': rec.get('avg_profit_factor', 0),
                'Action': rec.get('action', 'N/A')
            })

        df = pd.DataFrame(comparison_data)
        df = df.sort_values('P&L', ascending=False)

        # Formatear tabla
        table_html = df.to_html(
            index=False,
            classes='',
            escape=False,
            formatters={
                'P&L': lambda x: f'<span class="{"positive" if x > 0 else "negative"}">${x:,.2f}</span>',
                'Consistency': lambda x: f'{x:.1f}%',
                'WR': lambda x: f'{x:.1f}%',
                'PF': lambda x: f'{x:.2f}'
            }
        )

        # Generar recomendaciones
        recommendations_html = ""
        for _, row in df.iterrows():
            if 'MANTENER Y ESCALAR' in row['Action']:
                rec_class = 'rec-keep'
            elif 'MONITOREAR' in row['Action']:
                rec_class = 'rec-review'
            else:
                rec_class = 'rec-remove'

            recommendations_html += f"""
            <div class="recommendation {rec_class}">
                <strong>{row['Worker']}</strong>: {row['Action']}<br>
                P&L: ${row['P&L']:,.2f} | Consistency: {row['Consistency']:.0f}% | {row['Trades']} trades
            </div>
            """

        # Sustituir en template
        html = html.format(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            table=table_html,
            recommendations=recommendations_html
        )

        with open(output_file, 'w') as f:
            f.write(html)

        print(f"✅ HTML report saved to: {output_file}")


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Backtest all workers')
    parser.add_argument(
        '--workers',
        nargs='+',
        help='List of workers (space separated). If not provided, uses top workers from DB'
    )
    parser.add_argument('--start-date', help='Start date YYYY-MM-DD')
    parser.add_argument('--end-date', help='End date YYYY-MM-DD')
    parser.add_argument('--period-months', type=int, default=2, help='Months per period')
    parser.add_argument('--output-json', default='backtest_comparison.json', help='Output JSON file')
    parser.add_argument('--output-html', default='backtest_comparison.html', help='Output HTML file')

    args = parser.parse_args()

    # Si no se especifican workers, obtener top workers de la DB
    if not args.workers:
        import sqlite3
        conn = sqlite3.connect('trading_data.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT strategy, COUNT(*) as trades
            FROM trades
            WHERE status = 'CLOSED'
            GROUP BY strategy
            ORDER BY trades DESC
            LIMIT 10
        """)

        args.workers = [row[0] for row in cursor.fetchall()]
        conn.close()

        print(f"Auto-detected top workers: {', '.join(args.workers)}\n")

    # Ejecutar backtests
    multi_backtester = MultiWorkerBacktester()

    await multi_backtester.backtest_all_workers(
        workers=args.workers,
        start_date=args.start_date,
        end_date=args.end_date,
        period_months=args.period_months
    )

    # Guardar reportes
    multi_backtester.save_comparison_report(args.output_json)
    multi_backtester.generate_html_report(args.output_html)

    print("\n✅ All backtests complete!")
    print(f"   JSON: {args.output_json}")
    print(f"   HTML: {args.output_html}")


if __name__ == "__main__":
    asyncio.run(main())
