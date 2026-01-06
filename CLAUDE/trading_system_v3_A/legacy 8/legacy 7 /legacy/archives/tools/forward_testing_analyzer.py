#!/usr/bin/env python3
"""
Forward Testing Analyzer - Análisis detallado de trades con datos OHLC
======================================================================

Herramienta para analizar trades históricos con su contexto completo de datos OHLC
para optimización de estrategias y forward testing.
"""

import sqlite3
import json
import pandas as pd
import matplotlib.pyplot as plt
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import numpy as np

from core.trade_ohlc_recorder import get_trade_ohlc_recorder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ForwardTesting")


class ForwardTestingAnalyzer:
    """Analizador para forward testing con datos OHLC completos"""

    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = Path(db_path)
        self.recorder = get_trade_ohlc_recorder(str(db_path))

    def analyze_trade_performance(self, trade_id: str) -> Optional[Dict]:
        """
        Análisis completo de performance de un trade específico

        Args:
            trade_id: ID del trade a analizar

        Returns:
            Dict con análisis completo o None si no existe
        """
        try:
            trade_data = self.recorder.get_trade_ohlc_data(trade_id)
            if not trade_data:
                logger.error(f"❌ Trade {trade_id} not found")
                return None

            snapshot = trade_data['snapshot']
            intraday_bars = trade_data['intraday_bars']

            # Análisis básico
            entry_price = snapshot['entry_price']
            exit_price = snapshot['exit_price']
            day_high = snapshot['day_high']
            day_low = snapshot['day_low']

            if exit_price:
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                max_favorable = ((day_high - entry_price) / entry_price) * 100
                max_adverse = ((day_low - entry_price) / entry_price) * 100
            else:
                pnl_pct = None
                max_favorable = None
                max_adverse = None

            # Análisis de timing
            entry_time = datetime.fromisoformat(snapshot['entry_time'].replace('Z', '+00:00'))
            market_open = entry_time.replace(hour=9, minute=30, second=0, microsecond=0)
            minutes_from_open = (entry_time - market_open).total_seconds() / 60

            # Análisis de barras intraday
            bars_analysis = self._analyze_intraday_bars(intraday_bars, entry_time,
                                                      datetime.fromisoformat(snapshot['exit_time'].replace('Z', '+00:00')) if snapshot['exit_time'] else None)

            return {
                'trade_id': trade_id,
                'symbol': snapshot['symbol'],
                'trading_date': snapshot['trading_date'],
                'strategy': 'Unknown',  # Se puede obtener de la tabla trades

                # Performance
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl_percentage': pnl_pct,
                'max_favorable_excursion': max_favorable,
                'max_adverse_excursion': max_adverse,

                # Timing
                'minutes_from_open': minutes_from_open,
                'entry_timing_quality': self._rate_entry_timing(minutes_from_open),

                # Context
                'day_range_percentage': ((day_high - day_low) / day_low) * 100,
                'entry_position_in_range': ((entry_price - day_low) / (day_high - day_low)) * 100,
                'gap_percentage': snapshot.get('gap_percent'),

                # Detailed analysis
                'bars_analysis': bars_analysis,
                'total_bars': len(intraday_bars),
                'volume_profile': self._analyze_volume_profile(intraday_bars)
            }

        except Exception as e:
            logger.error(f"❌ Error analyzing trade {trade_id}: {e}")
            return None

    def analyze_strategy_performance(self, strategy_name: str, date_from: str, date_to: str) -> Dict:
        """
        Análisis completo de performance de una estrategia

        Args:
            strategy_name: Nombre de la estrategia
            date_from: Fecha inicio (YYYY-MM-DD)
            date_to: Fecha fin (YYYY-MM-DD)

        Returns:
            Dict con análisis completo de la estrategia
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Obtener trades de la estrategia con datos OHLC
                trades = conn.execute("""
                    SELECT t.*, tos.*
                    FROM trades t
                    JOIN trade_ohlc_snapshots tos ON t.trade_id = tos.trade_id
                    WHERE t.strategy = ? AND tos.trading_date BETWEEN ? AND ?
                    ORDER BY t.entry_time
                """, (strategy_name, date_from, date_to)).fetchall()

            if not trades:
                return {'error': f'No trades found for strategy {strategy_name}'}

            # Análisis detallado
            analysis = {
                'strategy': strategy_name,
                'period': f"{date_from} to {date_to}",
                'total_trades': len(trades),
                'trades': []
            }

            winning_trades = 0
            total_pnl = 0
            max_favorable_sum = 0
            max_adverse_sum = 0
            entry_timing_scores = []

            for trade in trades:
                trade_dict = dict(trade)

                # Calcular métricas
                if trade_dict['exit_price'] and trade_dict['entry_price']:
                    pnl_pct = ((trade_dict['exit_price'] - trade_dict['entry_price']) / trade_dict['entry_price']) * 100
                    total_pnl += pnl_pct

                    if pnl_pct > 0:
                        winning_trades += 1

                    # Max favorable/adverse excursion
                    max_fav = ((trade_dict['day_high'] - trade_dict['entry_price']) / trade_dict['entry_price']) * 100
                    max_adv = ((trade_dict['day_low'] - trade_dict['entry_price']) / trade_dict['entry_price']) * 100

                    max_favorable_sum += max_fav
                    max_adverse_sum += abs(max_adv)

                # Timing analysis
                entry_time = datetime.fromisoformat(trade_dict['entry_time'].replace('Z', '+00:00'))
                market_open = entry_time.replace(hour=9, minute=30, second=0, microsecond=0)
                minutes_from_open = (entry_time - market_open).total_seconds() / 60
                entry_timing_scores.append(self._rate_entry_timing(minutes_from_open))

                analysis['trades'].append({
                    'trade_id': trade_dict['trade_id'],
                    'symbol': trade_dict['symbol'],
                    'pnl_percentage': pnl_pct if trade_dict['exit_price'] else None,
                    'minutes_from_open': minutes_from_open,
                    'gap_percent': trade_dict.get('gap_percent'),
                    'day_range_pct': ((trade_dict['day_high'] - trade_dict['day_low']) / trade_dict['day_low']) * 100
                })

            # Estadísticas agregadas
            analysis.update({
                'win_rate': (winning_trades / len(trades)) * 100,
                'avg_pnl_per_trade': total_pnl / len(trades),
                'avg_max_favorable': max_favorable_sum / len(trades),
                'avg_max_adverse': max_adverse_sum / len(trades),
                'avg_entry_timing_score': np.mean(entry_timing_scores),
                'best_entry_time_window': self._find_best_entry_window([t['minutes_from_open'] for t in analysis['trades']]),
                'recommendations': self._generate_strategy_recommendations(analysis)
            })

            return analysis

        except Exception as e:
            logger.error(f"❌ Error analyzing strategy {strategy_name}: {e}")
            return {'error': str(e)}

    def find_optimal_exit_points(self, symbol: str, days_back: int = 30) -> Dict:
        """
        Análisis para encontrar puntos de salida óptimos

        Args:
            symbol: Símbolo a analizar
            days_back: Días hacia atrás para analizar

        Returns:
            Dict con análisis de puntos de salida óptimos
        """
        date_from = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        date_to = datetime.now().strftime('%Y-%m-%d')

        trades_data = self.recorder.get_forward_testing_data(symbol, date_from, date_to)

        if not trades_data:
            return {'error': f'No trade data found for {symbol}'}

        optimal_exits = []

        for trade in trades_data:
            if not trade.get('intraday_bars'):
                continue

            try:
                bars = json.loads(trade['intraday_bars'])
                entry_price = trade['entry_price']
                entry_time = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00'))

                # Encontrar el mejor momento de salida post-entrada
                best_exit_pct = 0
                best_exit_minutes = 0

                for bar in bars:
                    bar_time = datetime.fromisoformat(bar['timestamp'].replace('Z', '+00:00'))
                    if bar_time <= entry_time:
                        continue

                    minutes_held = (bar_time - entry_time).total_seconds() / 60
                    exit_pct = ((bar['high'] - entry_price) / entry_price) * 100

                    if exit_pct > best_exit_pct:
                        best_exit_pct = exit_pct
                        best_exit_minutes = minutes_held

                optimal_exits.append({
                    'trade_id': trade['trade_id'],
                    'actual_pnl': trade.get('pnl', 0),
                    'optimal_pnl': best_exit_pct,
                    'optimal_hold_minutes': best_exit_minutes,
                    'missed_opportunity': best_exit_pct - (trade.get('pnl', 0) or 0)
                })

            except Exception as e:
                logger.warning(f"Error processing trade {trade.get('trade_id', 'unknown')}: {e}")
                continue

        # Análisis agregado
        if optimal_exits:
            avg_optimal_hold = np.mean([e['optimal_hold_minutes'] for e in optimal_exits])
            avg_missed_opportunity = np.mean([e['missed_opportunity'] for e in optimal_exits])

            return {
                'symbol': symbol,
                'period': f"{date_from} to {date_to}",
                'trades_analyzed': len(optimal_exits),
                'avg_optimal_hold_minutes': avg_optimal_hold,
                'avg_missed_opportunity_pct': avg_missed_opportunity,
                'recommendations': {
                    'suggested_hold_time': f"{int(avg_optimal_hold)} minutes",
                    'potential_improvement': f"{avg_missed_opportunity:.1f}% per trade",
                    'exit_strategy': self._suggest_exit_strategy(avg_optimal_hold)
                },
                'detailed_trades': optimal_exits
            }
        else:
            return {'error': 'No valid trades found for analysis'}

    def _analyze_intraday_bars(self, bars: List[Dict], entry_time: datetime, exit_time: Optional[datetime]) -> Dict:
        """Análisis detallado de barras intraday"""
        if not bars:
            return {}

        # Convertir a DataFrame para análisis
        df = pd.DataFrame(bars)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Filtrar barras relevantes (post-entrada)
        post_entry = df[df['timestamp'] >= entry_time].copy()

        if len(post_entry) == 0:
            return {'error': 'No bars found after entry time'}

        # Análisis de movimiento
        entry_price = post_entry.iloc[0]['open_price']
        max_gain = post_entry['high_price'].max()
        max_loss = post_entry['low_price'].min()

        return {
            'bars_post_entry': len(post_entry),
            'max_gain_pct': ((max_gain - entry_price) / entry_price) * 100,
            'max_loss_pct': ((max_loss - entry_price) / entry_price) * 100,
            'avg_volume': post_entry['volume'].mean(),
            'volume_trend': 'increasing' if post_entry['volume'].iloc[-1] > post_entry['volume'].iloc[0] else 'decreasing'
        }

    def _analyze_volume_profile(self, bars: List[Dict]) -> Dict:
        """Análisis del perfil de volumen"""
        if not bars:
            return {}

        volumes = [bar['volume'] for bar in bars]

        return {
            'total_volume': sum(volumes),
            'avg_volume': np.mean(volumes),
            'volume_spike_bars': len([v for v in volumes if v > np.mean(volumes) * 2]),
            'volume_concentration': 'front_loaded' if volumes[0] > np.mean(volumes) else 'distributed'
        }

    def _rate_entry_timing(self, minutes_from_open: float) -> float:
        """
        Calificar la calidad del timing de entrada (0-1)

        Args:
            minutes_from_open: Minutos desde apertura de mercado

        Returns:
            Score de 0 a 1 (1 = timing perfecto)
        """
        # Mejor timing: primeros 30 minutos
        if 0 <= minutes_from_open <= 30:
            return 1.0
        # Buen timing: 30-60 minutos
        elif 30 < minutes_from_open <= 60:
            return 0.8
        # Timing regular: 60-120 minutos
        elif 60 < minutes_from_open <= 120:
            return 0.6
        # Timing malo: después de 2 horas
        else:
            return 0.3

    def _find_best_entry_window(self, entry_times: List[float]) -> str:
        """Encontrar la mejor ventana de entrada"""
        if not entry_times:
            return "No data"

        # Agrupar por ventanas de 30 minutos
        windows = {
            "0-30 min": [t for t in entry_times if 0 <= t <= 30],
            "30-60 min": [t for t in entry_times if 30 < t <= 60],
            "60-120 min": [t for t in entry_times if 60 < t <= 120],
            "120+ min": [t for t in entry_times if t > 120]
        }

        # Encontrar ventana con más trades
        best_window = max(windows.items(), key=lambda x: len(x[1]))
        return f"{best_window[0]} ({len(best_window[1])} trades)"

    def _suggest_exit_strategy(self, avg_hold_minutes: float) -> str:
        """Sugerir estrategia de salida basada en análisis"""
        if avg_hold_minutes <= 15:
            return "Scalping strategy - very quick exits"
        elif avg_hold_minutes <= 60:
            return "Short-term momentum - hold for first hour"
        elif avg_hold_minutes <= 120:
            return "Medium-term swing - hold for 1-2 hours"
        else:
            return "Long-term position - hold for multiple hours"

    def _generate_strategy_recommendations(self, analysis: Dict) -> List[str]:
        """Generar recomendaciones para mejorar la estrategia"""
        recommendations = []

        win_rate = analysis.get('win_rate', 0)
        avg_timing_score = analysis.get('avg_entry_timing_score', 0)

        if win_rate < 50:
            recommendations.append("Consider tightening entry criteria - win rate below 50%")

        if avg_timing_score < 0.7:
            recommendations.append("Focus on earlier entries - average timing score is low")

        if analysis.get('avg_max_adverse', 0) > 5:
            recommendations.append("Consider tighter stop losses - high adverse excursion")

        return recommendations


def main():
    """Función principal para ejecutar análisis de ejemplo"""
    analyzer = ForwardTestingAnalyzer()

    print("🔍 Forward Testing Analyzer")
    print("=" * 50)

    # Obtener estadísticas del recorder
    stats = analyzer.recorder.get_statistics()
    print(f"📊 Available data:")
    print(f"  - Total trades with OHLC: {stats['total_snapshots']}")
    print(f"  - Total bars recorded: {stats['total_bars_recorded']}")
    print(f"  - Active recordings: {stats['active_recordings']}")

    # Ejemplo de análisis si hay datos
    if stats['total_snapshots'] > 0:
        print(f"\n🎯 Running sample analysis...")

        # Analizar últimos 30 días
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        date_to = datetime.now().strftime('%Y-%m-%d')

        print(f"Period: {date_from} to {date_to}")


if __name__ == "__main__":
    main()