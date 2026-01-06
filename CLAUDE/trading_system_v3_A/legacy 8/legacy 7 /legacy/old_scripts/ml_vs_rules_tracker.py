"""
ML vs Rules Performance Tracker
Tracks and compares performance between ML-based and rule-based strategy selections
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import logging
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SelectionComparison:
    """Data structure for tracking a single selection comparison"""
    timestamp: datetime
    symbol: str
    ml_choice: List[str]
    rule_choice: List[str]
    actual_choice: List[str]
    selection_method: str  # "ML_VALIDATED", "RULES_FALLBACK", "ML_OVERRIDE"
    context_data: Dict[str, Any]

    # Performance data (filled later)
    trade_executed: bool = False
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl_percent: Optional[float] = None
    pnl_dollars: Optional[float] = None
    trade_duration_minutes: Optional[int] = None
    exit_reason: Optional[str] = None


class MLvsRulesTracker:
    """
    Tracks performance comparison between ML and rule-based strategy selection
    """

    def __init__(self, data_dir: str = "data/ml_vs_rules"):
        self.logger = logging.getLogger(__name__)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.selections: List[SelectionComparison] = []
        self.performance_data: Dict[str, Any] = {
            'ml_stats': {'wins': 0, 'losses': 0, 'total_pnl': 0.0, 'avg_pnl': 0.0},
            'rules_stats': {'wins': 0, 'losses': 0, 'total_pnl': 0.0, 'avg_pnl': 0.0},
            'agreement_rate': 0.0,
            'ml_vs_rules_accuracy': {}
        }

    def record_selection(self,
                        symbol: str,
                        ml_choice: List[str],
                        rule_choice: List[str],
                        actual_choice: List[str],
                        selection_method: str,
                        context_data: Dict[str, Any]) -> None:
        """
        Record a strategy selection comparison

        Args:
            symbol: Stock symbol
            ml_choice: Strategies selected by ML
            rule_choice: Strategies selected by rules
            actual_choice: Strategies actually used
            selection_method: How the final decision was made
            context_data: Market context data for analysis
        """
        try:
            comparison = SelectionComparison(
                timestamp=datetime.now(),
                symbol=symbol,
                ml_choice=ml_choice,
                rule_choice=rule_choice,
                actual_choice=actual_choice,
                selection_method=selection_method,
                context_data=context_data
            )

            self.selections.append(comparison)

            # Log the comparison for immediate visibility
            agreement = "✅" if set(ml_choice) == set(rule_choice) else "❌"
            self.logger.info(f"📊 {symbol}: ML={ml_choice}, Rules={rule_choice}, Used={actual_choice} {agreement}")
            self.logger.info(f"   Method: {selection_method}")

            # Save periodically
            if len(self.selections) % 50 == 0:
                self._save_data()

        except Exception as e:
            self.logger.error(f"Error recording selection for {symbol}: {e}")

    def record_trade_result(self,
                           symbol: str,
                           entry_price: float,
                           exit_price: float,
                           trade_duration_minutes: int,
                           exit_reason: str,
                           position_size: float = 100) -> None:
        """
        Record the result of a trade to evaluate strategy performance

        Args:
            symbol: Stock symbol
            entry_price: Entry price
            exit_price: Exit price
            trade_duration_minutes: How long trade was held
            exit_reason: Why trade was closed
            position_size: Position size in shares
        """
        try:
            # Find the most recent selection for this symbol
            recent_selection = None
            for selection in reversed(self.selections):
                if (selection.symbol == symbol and
                    not selection.trade_executed and
                    (datetime.now() - selection.timestamp) < timedelta(hours=6)):
                    recent_selection = selection
                    break

            if not recent_selection:
                self.logger.warning(f"No recent selection found for trade result: {symbol}")
                return

            # Calculate PnL
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            pnl_dollars = (exit_price - entry_price) * position_size

            # Update the selection with trade results
            recent_selection.trade_executed = True
            recent_selection.entry_price = entry_price
            recent_selection.exit_price = exit_price
            recent_selection.pnl_percent = pnl_percent
            recent_selection.pnl_dollars = pnl_dollars
            recent_selection.trade_duration_minutes = trade_duration_minutes
            recent_selection.exit_reason = exit_reason

            # Update performance stats
            self._update_performance_stats()

            self.logger.info(f"💰 {symbol}: Trade result recorded - "
                           f"PnL: {pnl_percent:.2f}% (${pnl_dollars:.2f}), "
                           f"Duration: {trade_duration_minutes}min, Reason: {exit_reason}")

        except Exception as e:
            self.logger.error(f"Error recording trade result for {symbol}: {e}")

    def _update_performance_stats(self) -> None:
        """Update performance statistics for ML vs Rules comparison"""
        try:
            executed_trades = [s for s in self.selections if s.trade_executed and s.pnl_percent is not None]

            if not executed_trades:
                return

            # Reset stats
            ml_wins = ml_losses = rules_wins = rules_losses = 0
            ml_total_pnl = rules_total_pnl = 0.0
            agreement_count = 0

            # Analyze each trade
            for trade in executed_trades:
                pnl = trade.pnl_percent
                is_win = pnl > 0

                # Count agreement rate
                if set(trade.ml_choice) == set(trade.rule_choice):
                    agreement_count += 1

                # Attribute performance based on selection method
                if trade.selection_method in ["ML_VALIDATED", "ML_OVERRIDE"]:
                    # This trade used ML selection
                    if is_win:
                        ml_wins += 1
                    else:
                        ml_losses += 1
                    ml_total_pnl += pnl

                elif trade.selection_method == "RULES_FALLBACK":
                    # This trade used rules fallback
                    if is_win:
                        rules_wins += 1
                    else:
                        rules_losses += 1
                    rules_total_pnl += pnl

            # Calculate statistics
            total_trades = len(executed_trades)
            ml_trades = ml_wins + ml_losses
            rules_trades = rules_wins + rules_losses

            self.performance_data = {
                'ml_stats': {
                    'wins': ml_wins,
                    'losses': ml_losses,
                    'total_trades': ml_trades,
                    'win_rate': (ml_wins / ml_trades * 100) if ml_trades > 0 else 0.0,
                    'total_pnl': ml_total_pnl,
                    'avg_pnl': (ml_total_pnl / ml_trades) if ml_trades > 0 else 0.0
                },
                'rules_stats': {
                    'wins': rules_wins,
                    'losses': rules_losses,
                    'total_trades': rules_trades,
                    'win_rate': (rules_wins / rules_trades * 100) if rules_trades > 0 else 0.0,
                    'total_pnl': rules_total_pnl,
                    'avg_pnl': (rules_total_pnl / rules_trades) if rules_trades > 0 else 0.0
                },
                'agreement_rate': (agreement_count / total_trades * 100) if total_trades > 0 else 0.0,
                'total_selections': len(self.selections),
                'executed_trades': total_trades
            }

        except Exception as e:
            self.logger.error(f"Error updating performance stats: {e}")

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get current performance summary"""
        self._update_performance_stats()
        return self.performance_data.copy()

    def get_detailed_analysis(self) -> Dict[str, Any]:
        """Get detailed analysis of ML vs Rules performance"""
        try:
            executed_trades = [s for s in self.selections if s.trade_executed]

            if not executed_trades:
                return {"error": "No executed trades to analyze"}

            # Strategy-specific analysis
            strategy_performance = {}
            for trade in executed_trades:
                for strategy in trade.actual_choice:
                    if strategy not in strategy_performance:
                        strategy_performance[strategy] = {
                            'ml_selected': 0, 'rules_selected': 0, 'total_trades': 0,
                            'ml_pnl': 0.0, 'rules_pnl': 0.0
                        }

                    strategy_performance[strategy]['total_trades'] += 1

                    if strategy in trade.ml_choice:
                        strategy_performance[strategy]['ml_selected'] += 1
                        strategy_performance[strategy]['ml_pnl'] += trade.pnl_percent or 0

                    if strategy in trade.rule_choice:
                        strategy_performance[strategy]['rules_selected'] += 1
                        strategy_performance[strategy]['rules_pnl'] += trade.pnl_percent or 0

            # Time-based analysis
            recent_trades = [t for t in executed_trades
                           if (datetime.now() - t.timestamp) < timedelta(days=7)]

            return {
                'performance_summary': self.get_performance_summary(),
                'strategy_breakdown': strategy_performance,
                'recent_performance': {
                    'last_7_days_trades': len(recent_trades),
                    'recent_agreement_rate': self._calculate_agreement_rate(recent_trades),
                    'recent_avg_pnl': sum(t.pnl_percent or 0 for t in recent_trades) / len(recent_trades) if recent_trades else 0
                },
                'selection_methods': self._analyze_selection_methods()
            }

        except Exception as e:
            self.logger.error(f"Error generating detailed analysis: {e}")
            return {"error": str(e)}

    def _calculate_agreement_rate(self, trades: List[SelectionComparison]) -> float:
        """Calculate agreement rate between ML and rules for given trades"""
        if not trades:
            return 0.0

        agreements = sum(1 for t in trades if set(t.ml_choice) == set(t.rule_choice))
        return (agreements / len(trades)) * 100

    def _analyze_selection_methods(self) -> Dict[str, Any]:
        """Analyze how often each selection method is used"""
        method_counts = {}
        for selection in self.selections:
            method = selection.selection_method
            method_counts[method] = method_counts.get(method, 0) + 1

        total = len(self.selections)
        return {
            'counts': method_counts,
            'percentages': {method: (count / total * 100) for method, count in method_counts.items()} if total > 0 else {}
        }

    def _save_data(self) -> None:
        """Save selection data to disk"""
        try:
            data_file = self.data_dir / f"ml_vs_rules_data_{datetime.now().strftime('%Y%m%d')}.json"

            # Convert selections to serializable format
            serializable_data = []
            for selection in self.selections:
                data = {
                    'timestamp': selection.timestamp.isoformat(),
                    'symbol': selection.symbol,
                    'ml_choice': selection.ml_choice,
                    'rule_choice': selection.rule_choice,
                    'actual_choice': selection.actual_choice,
                    'selection_method': selection.selection_method,
                    'context_data': selection.context_data,
                    'trade_executed': selection.trade_executed,
                    'entry_price': selection.entry_price,
                    'exit_price': selection.exit_price,
                    'pnl_percent': selection.pnl_percent,
                    'pnl_dollars': selection.pnl_dollars,
                    'trade_duration_minutes': selection.trade_duration_minutes,
                    'exit_reason': selection.exit_reason
                }
                serializable_data.append(data)

            with open(data_file, 'w') as f:
                json.dump({
                    'selections': serializable_data,
                    'performance_data': self.performance_data
                }, f, indent=2)

            self.logger.info(f"💾 Saved ML vs Rules data: {len(serializable_data)} selections")

        except Exception as e:
            self.logger.error(f"Error saving data: {e}")

    def print_summary_report(self) -> None:
        """Print a comprehensive summary report"""
        try:
            analysis = self.get_detailed_analysis()

            print("\n" + "="*60)
            print("🤖 ML vs 📋 RULES PERFORMANCE COMPARISON")
            print("="*60)

            perf = analysis['performance_summary']

            print(f"\n📊 OVERALL STATISTICS:")
            print(f"   Total Selections: {perf['total_selections']}")
            print(f"   Executed Trades: {perf['executed_trades']}")
            print(f"   Agreement Rate: {perf['agreement_rate']:.1f}%")

            print(f"\n🤖 ML PERFORMANCE:")
            ml = perf['ml_stats']
            print(f"   Trades: {ml['total_trades']} | Win Rate: {ml['win_rate']:.1f}%")
            print(f"   Total PnL: {ml['total_pnl']:.2f}% | Avg PnL: {ml['avg_pnl']:.2f}%")

            print(f"\n📋 RULES PERFORMANCE:")
            rules = perf['rules_stats']
            print(f"   Trades: {rules['total_trades']} | Win Rate: {rules['win_rate']:.1f}%")
            print(f"   Total PnL: {rules['total_pnl']:.2f}% | Avg PnL: {rules['avg_pnl']:.2f}%")

            if 'strategy_breakdown' in analysis:
                print(f"\n📈 STRATEGY BREAKDOWN:")
                for strategy, data in analysis['strategy_breakdown'].items():
                    print(f"   {strategy}: {data['total_trades']} trades")

            print("\n" + "="*60)

        except Exception as e:
            self.logger.error(f"Error printing summary report: {e}")