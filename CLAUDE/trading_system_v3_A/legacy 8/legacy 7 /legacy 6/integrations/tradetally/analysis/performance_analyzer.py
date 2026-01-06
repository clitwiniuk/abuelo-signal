#!/usr/bin/env python3
"""
Performance Analyzer - Análisis de Rendimiento del Sistema
=========================================================

Analiza el rendimiento histórico del sistema de trading usando datos de SQLite.
Calcula métricas avanzadas como Sharpe ratio, profit factor, drawdown, etc.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import statistics
import math

logger = logging.getLogger(__name__)

class PerformanceAnalyzer:
    """
    Analizador de rendimiento que calcula métricas avanzadas
    desde los datos históricos de trades en SQLite.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(f"{__name__}.PerformanceAnalyzer")

    def calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """
        Calcular Sharpe Ratio

        Args:
            returns: Lista de retornos diarios
            risk_free_rate: Tasa libre de riesgo anual (2% por defecto)

        Returns:
            Sharpe ratio o 0.0 si no hay suficientes datos
        """
        if len(returns) < 2:
            return 0.0

        try:
            # Retorno promedio diario
            avg_return = statistics.mean(returns)

            # Volatilidad (desviación estándar)
            volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0

            if volatility == 0.0:
                return 0.0

            # Sharpe ratio anualizado
            daily_risk_free = risk_free_rate / 365
            sharpe_ratio = (avg_return - daily_risk_free) / volatility

            # Anualizar
            return sharpe_ratio * math.sqrt(365)  # ~19.1 (días de trading al año)

        except Exception as e:
            self.logger.warning(f"Error calculating Sharpe ratio: {e}")
            return 0.0

    def calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """
        Calcular Maximum Drawdown

        Args:
            equity_curve: Lista de valores de equity en orden cronológico

        Returns:
            Maximum drawdown como porcentaje (0.0-1.0)
        """
        if len(equity_curve) < 2:
            return 0.0

        try:
            max_drawdown = 0.0
            peak = equity_curve[0]

            for value in equity_curve:
                if value > peak:
                    peak = value

                drawdown = (peak - value) / peak if peak > 0 else 0.0
                max_drawdown = max(max_drawdown, drawdown)

            return max_drawdown

        except Exception as e:
            self.logger.warning(f"Error calculating max drawdown: {e}")
            return 0.0

    def calculate_profit_factor(self, winning_trades: List[float], losing_trades: List[float]) -> float:
        """
        Calcular Profit Factor

        Args:
            winning_trades: Lista de PnL de trades ganadores
            losing_trades: Lista de PnL de trades perdedores (valores positivos)

        Returns:
            Profit factor o 0.0 si no hay datos
        """
        total_wins = sum(winning_trades) if winning_trades else 0.0
        total_losses = sum(losing_trades) if losing_trades else 0.0

        if total_losses == 0.0:
            return float('inf') if total_wins > 0 else 0.0

        return total_wins / total_losses

    def calculate_win_streak_analysis(self, trades: List[Dict]) -> Dict[str, Any]:
        """
        Analizar rachas de ganancias y pérdidas

        Args:
            trades: Lista de trades ordenados por fecha

        Returns:
            Dict con estadísticas de rachas
        """
        if not trades:
            return {'max_win_streak': 0, 'max_loss_streak': 0, 'avg_win_streak': 0, 'avg_loss_streak': 0}

        win_streaks = []
        loss_streaks = []
        current_win_streak = 0
        current_loss_streak = 0

        for trade in trades:
            pnl = trade.get('pnl', 0)

            if pnl > 0:
                current_win_streak += 1
                if current_loss_streak > 0:
                    loss_streaks.append(current_loss_streak)
                    current_loss_streak = 0
            elif pnl < 0:
                current_loss_streak += 1
                if current_win_streak > 0:
                    win_streaks.append(current_win_streak)
                    current_win_streak = 0

        # Agregar rachas finales
        if current_win_streak > 0:
            win_streaks.append(current_win_streak)
        if current_loss_streak > 0:
            loss_streaks.append(current_loss_streak)

        return {
            'max_win_streak': max(win_streaks) if win_streaks else 0,
            'max_loss_streak': max(loss_streaks) if loss_streaks else 0,
            'avg_win_streak': statistics.mean(win_streaks) if win_streaks else 0,
            'avg_loss_streak': statistics.mean(loss_streaks) if loss_streaks else 0,
            'total_win_streaks': len(win_streaks),
            'total_loss_streaks': len(loss_streaks)
        }

    def analyze_strategy_performance(self, strategy_name: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Análisis completo de rendimiento para una estrategia específica

        Args:
            strategy_name: Nombre de la estrategia
            days_back: Días hacia atrás para analizar

        Returns:
            Dict con métricas completas de rendimiento
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

            # Obtener todos los trades de la estrategia
            query = """
                SELECT
                    pnl, entry_time, exit_time, duration_minutes,
                    entry_slippage_pct, total_slippage_impact
                FROM trades
                WHERE strategy = ?
                  AND status = 'CLOSED'
                  AND entry_time >= ?
                  AND pnl IS NOT NULL
                ORDER BY entry_time ASC
            """

            cursor.execute(query, (strategy_name, cutoff_date))
            rows = cursor.fetchall()

            if not rows:
                conn.close()
                return {
                    'strategy': strategy_name,
                    'error': 'No trades found',
                    'total_trades': 0
                }

            # Convertir a lista de dicts
            trades = [dict(row) for row in rows]
            conn.close()

            # Calcular métricas básicas
            pnls = [t['pnl'] for t in trades]
            winning_trades = [t['pnl'] for t in trades if t['pnl'] > 0]
            losing_trades = [abs(t['pnl']) for t in trades if t['pnl'] < 0]

            # Calcular retornos diarios (simplificado)
            daily_returns = self._calculate_daily_returns(trades)

            # Calcular equity curve
            equity_curve = self._calculate_equity_curve(pnls)

            # Métricas avanzadas
            sharpe_ratio = self.calculate_sharpe_ratio(daily_returns)
            max_drawdown = self.calculate_max_drawdown(equity_curve)
            profit_factor = self.calculate_profit_factor(winning_trades, losing_trades)
            streak_analysis = self.calculate_win_streak_analysis(trades)

            # Métricas de slippage
            avg_slippage = statistics.mean([t.get('entry_slippage_pct', 0) or 0 for t in trades])
            total_slippage_impact = sum([t.get('total_slippage_impact', 0) or 0 for t in trades])

            # Métricas de tiempo
            avg_duration = statistics.mean([t.get('duration_minutes', 0) or 0 for t in trades if t.get('duration_minutes')])

            result = {
                'strategy': strategy_name,
                'analysis_period_days': days_back,

                # Métricas básicas
                'total_trades': len(trades),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': len(winning_trades) / len(trades) if trades else 0,

                # Métricas financieras
                'total_pnl': sum(pnls),
                'avg_pnl_per_trade': statistics.mean(pnls) if pnls else 0,
                'median_pnl': statistics.median(pnls) if pnls else 0,
                'largest_win': max(pnls) if pnls else 0,
                'largest_loss': min(pnls) if pnls else 0,

                # Métricas avanzadas
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'profit_factor': profit_factor,

                # Rachas
                'streak_analysis': streak_analysis,

                # Slippage
                'avg_slippage_pct': avg_slippage,
                'total_slippage_impact': total_slippage_impact,

                # Tiempo
                'avg_duration_minutes': avg_duration,

                # Estadísticas adicionales
                'pnl_std_dev': statistics.stdev(pnls) if len(pnls) > 1 else 0,
                'win_loss_ratio': (sum(winning_trades) / len(winning_trades) if winning_trades else 0) / \
                                 (sum(losing_trades) / len(losing_trades) if losing_trades else 1),

                'analysis_timestamp': datetime.now().isoformat()
            }

            self.logger.info(f"✅ Performance analysis completed for {strategy_name}: {len(trades)} trades")
            return result

        except Exception as e:
            self.logger.error(f"❌ Error analyzing strategy {strategy_name}: {e}")
            return {
                'strategy': strategy_name,
                'error': str(e),
                'total_trades': 0
            }

    def analyze_portfolio_performance(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Análisis de rendimiento del portfolio completo

        Args:
            days_back: Días hacia atrás para analizar

        Returns:
            Dict con métricas de portfolio
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

            # Obtener todos los trades del período
            query = """
                SELECT pnl, entry_time, strategy
                FROM trades
                WHERE status = 'CLOSED'
                  AND entry_time >= ?
                  AND pnl IS NOT NULL
                ORDER BY entry_time ASC
            """

            cursor.execute(query, (cutoff_date,))
            rows = cursor.fetchall()
            trades = [dict(row) for row in rows]
            conn.close()

            if not trades:
                return {
                    'error': 'No trades found in period',
                    'total_trades': 0
                }

            # Calcular métricas de portfolio
            pnls = [t['pnl'] for t in trades]
            daily_returns = self._calculate_daily_returns(trades)
            equity_curve = self._calculate_equity_curve(pnls)

            winning_trades = [t['pnl'] for t in trades if t['pnl'] > 0]
            losing_trades = [abs(t['pnl']) for t in trades if t['pnl'] < 0]

            # Análisis por estrategia
            strategy_performance = {}
            strategies = set(t['strategy'] for t in trades if t.get('strategy'))

            for strategy in strategies:
                strategy_trades = [t for t in trades if t.get('strategy') == strategy]
                if strategy_trades:
                    strategy_pnls = [t['pnl'] for t in strategy_trades]
                    strategy_performance[strategy] = {
                        'trades': len(strategy_trades),
                        'total_pnl': sum(strategy_pnls),
                        'win_rate': len([t for t in strategy_trades if t['pnl'] > 0]) / len(strategy_trades),
                        'contribution_pct': sum(strategy_pnls) / sum(pnls) if sum(pnls) != 0 else 0
                    }

            result = {
                'analysis_period_days': days_back,
                'total_trades': len(trades),
                'total_pnl': sum(pnls),
                'win_rate': len(winning_trades) / len(trades),

                # Métricas avanzadas
                'sharpe_ratio': self.calculate_sharpe_ratio(daily_returns),
                'max_drawdown': self.calculate_max_drawdown(equity_curve),
                'profit_factor': self.calculate_profit_factor(winning_trades, losing_trades),

                # Estadísticas
                'avg_trade_pnl': statistics.mean(pnls) if pnls else 0,
                'median_trade_pnl': statistics.median(pnls) if pnls else 0,
                'pnl_volatility': statistics.stdev(pnls) if len(pnls) > 1 else 0,

                # Análisis por estrategia
                'strategy_breakdown': strategy_performance,
                'best_strategy': max(strategy_performance.items(), key=lambda x: x[1]['total_pnl']) if strategy_performance else None,
                'worst_strategy': min(strategy_performance.items(), key=lambda x: x[1]['total_pnl']) if strategy_performance else None,

                'analysis_timestamp': datetime.now().isoformat()
            }

            self.logger.info(f"✅ Portfolio performance analysis completed: {len(trades)} trades, ${sum(pnls):.2f} PnL")
            return result

        except Exception as e:
            self.logger.error(f"❌ Error analyzing portfolio performance: {e}")
            return {'error': str(e)}

    def _calculate_daily_returns(self, trades: List[Dict]) -> List[float]:
        """
        Calcular retornos diarios desde lista de trades

        Args:
            trades: Lista de trades ordenados por tiempo

        Returns:
            Lista de retornos diarios
        """
        if not trades:
            return []

        # Agrupar por día
        daily_pnl = {}
        for trade in trades:
            try:
                entry_time = datetime.fromisoformat(trade['entry_time'].replace('Z', ''))
                date_key = entry_time.date()

                if date_key not in daily_pnl:
                    daily_pnl[date_key] = 0.0
                daily_pnl[date_key] += trade['pnl']
            except:
                continue

        # Convertir a retornos (simplificado - asumiendo capital constante)
        daily_returns = []
        sorted_dates = sorted(daily_pnl.keys())

        for date in sorted_dates:
            pnl = daily_pnl[date]
            # Retorno diario simplificado (PnL / capital asumido)
            # En un sistema real, usarías el capital actual del día
            daily_return = pnl / 10000  # Asumiendo $10k capital base
            daily_returns.append(daily_return)

        return daily_returns

    def _calculate_equity_curve(self, pnls: List[float]) -> List[float]:
        """
        Calcular curva de equity desde lista de PnL

        Args:
            pnls: Lista de PnL en orden cronológico

        Returns:
            Lista de valores de equity
        """
        if not pnls:
            return []

        equity = 10000.0  # Capital inicial asumido
        equity_curve = [equity]

        for pnl in pnls:
            equity += pnl
            equity_curve.append(equity)

        return equity_curve