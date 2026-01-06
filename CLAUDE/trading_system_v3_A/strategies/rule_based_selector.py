"""
Rule-based Strategy Selector
Simple transparent rules for strategy selection to compare against ML performance
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging


class RuleBasedStrategySelector:
    """
    Transparent rule-based strategy selector for the 5 core strategies:
    - gap_go: Gap trading (4%+ gaps with volume)
    - red_to_green: Reversal patterns (3+ red candles)
    - first_day_bounce: IPO/new listing rebounds
    - macdv_smallcaps: MACD convergence timing
    - daily_plays: Catalyst momentum
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.selection_history = {}

        # Simple rule thresholds (easily adjustable)
        self.rules = {
            'gap_go': {
                'min_gap_percent': 4.0,
                'min_volume_ratio': 2.0,
                'trading_hours_start': 9.5,
                'trading_hours_end': 12.0,
                'max_price': 15.0,
                'min_price': 1.0
            },
            'red_to_green': {
                'min_consecutive_red': 3,
                'min_volume_spike': 1.5,
                'max_down_percent': -20.0,  # Don't catch falling knives
                'reversal_confirmation_needed': True
            },
            'first_day_bounce': {
                'min_down_percent': 8.0,
                # Removed max_days_since_listing - align with actual strategy logic
                'min_bounce_percent': 2.0,
                'min_volume_ratio': 1.8,
                'min_overextension_gain': 50.0,  # Match real strategy criteria
                'require_recent_peak': True      # Focus on recent overextensions
            },
            'macdv_smallcaps': {
                'require_convergence': True,
                'require_volume_confirmation': True,
                'avoid_first_30min': True,
                'min_timeframe_alignment': True
            },
            'daily_plays': {
                'require_catalyst': True,
                'min_momentum_score': 0.6,
                'min_volume_explosion': 3.0,
                'max_price': 20.0
            }
        }

    def select_strategies(self, symbol: str, context: Any) -> List[str]:
        """
        Select strategies based on simple transparent rules

        Args:
            symbol: Stock symbol
            context: Market context with relevant data

        Returns:
            List of strategy names that match criteria
        """
        selected_strategies = []
        selection_reasons = {}

        try:
            # Current time for time-based rules (use context time if available for testing)
            current_hour = getattr(context, 'current_hour', self._get_current_hour())

            # Rule 1: Gap Go Strategy
            gap_go_score, gap_go_reason = self._evaluate_gap_go(symbol, context, current_hour)
            if gap_go_score > 0:
                selected_strategies.append('gap_go')
                selection_reasons['gap_go'] = gap_go_reason

            # Rule 2: Red to Green Strategy
            r2g_score, r2g_reason = self._evaluate_red_to_green(symbol, context)
            if r2g_score > 0:
                selected_strategies.append('red_to_green')
                selection_reasons['red_to_green'] = r2g_reason

            # Rule 3: First Day Bounce Strategy
            fdb_score, fdb_reason = self._evaluate_first_day_bounce(symbol, context)
            if fdb_score > 0:
                selected_strategies.append('first_day_bounce')
                selection_reasons['first_day_bounce'] = fdb_reason

            # Rule 4: MACDV Smallcaps Strategy
            macdv_score, macdv_reason = self._evaluate_macdv_smallcaps(symbol, context)
            if macdv_score > 0:
                selected_strategies.append('macdv_smallcaps')
                selection_reasons['macdv_smallcaps'] = macdv_reason

            # Rule 5: Daily Plays Strategy
            plays_score, plays_reason = self._evaluate_daily_plays(symbol, context)
            if plays_score > 0:
                selected_strategies.append('daily_plays')
                selection_reasons['daily_plays'] = plays_reason

            # Log selection logic for transparency
            if selected_strategies:
                self.logger.info(f"📋 {symbol}: Rule-based selected: {selected_strategies}")
                for strategy, reason in selection_reasons.items():
                    self.logger.info(f"   ✅ {strategy}: {reason}")
            else:
                self.logger.debug(f"📋 {symbol}: No rule-based strategies selected")

            # Store selection history
            self.selection_history[symbol] = {
                'timestamp': datetime.now(),
                'selected': selected_strategies,
                'reasons': selection_reasons
            }

            return selected_strategies

        except Exception as e:
            self.logger.error(f"Error in rule-based selection for {symbol}: {e}")
            return []

    def _evaluate_gap_go(self, symbol: str, context: Any, current_hour: float) -> tuple[int, str]:
        """Evaluate Gap Go strategy criteria"""
        try:
            rules = self.rules['gap_go']

            # Check basic requirements
            gap_percent = getattr(context, 'gap_percent', 0)
            volume_ratio = getattr(context, 'volume_ratio', 0)
            price = getattr(context, 'current_price', 0)

            # Gap size check
            if abs(gap_percent) < rules['min_gap_percent']:
                return 0, f"Gap {gap_percent:.1f}% < {rules['min_gap_percent']}%"

            # Volume check
            if volume_ratio < rules['min_volume_ratio']:
                return 0, f"Volume {volume_ratio:.1f}x < {rules['min_volume_ratio']}x"

            # Time window check (gap go works best in morning)
            if not (rules['trading_hours_start'] <= current_hour <= rules['trading_hours_end']):
                return 0, f"Outside trading window {rules['trading_hours_start']}-{rules['trading_hours_end']}"

            # Price range check
            if not (rules['min_price'] <= price <= rules['max_price']):
                return 0, f"Price ${price:.2f} outside range ${rules['min_price']}-${rules['max_price']}"

            # Only gap up (positive gaps)
            if gap_percent <= 0:
                return 0, f"Gap down {gap_percent:.1f}% not suitable for gap_go"

            return 1, f"Gap {gap_percent:.1f}%, Vol {volume_ratio:.1f}x, Time {current_hour:.1f}h"

        except Exception as e:
            return 0, f"Error evaluating gap_go: {e}"

    def _evaluate_red_to_green(self, symbol: str, context: Any) -> tuple[int, str]:
        """Evaluate Red to Green strategy criteria"""
        try:
            rules = self.rules['red_to_green']

            consecutive_red = getattr(context, 'consecutive_red_candles', 0)
            volume_spike = getattr(context, 'volume_ratio', 0)
            down_percent = getattr(context, 'day_change_percent', 0)

            # Consecutive red candles check
            if consecutive_red < rules['min_consecutive_red']:
                return 0, f"Only {consecutive_red} red candles < {rules['min_consecutive_red']}"

            # Volume spike check
            if volume_spike < rules['min_volume_spike']:
                return 0, f"Volume {volume_spike:.1f}x < {rules['min_volume_spike']}x"

            # Avoid falling knives
            if down_percent < rules['max_down_percent']:
                return 0, f"Down {down_percent:.1f}% too much (falling knife)"

            # Look for reversal signs (simplified)
            has_reversal_signal = getattr(context, 'reversal_pattern', False) or volume_spike > 2.0
            if rules['reversal_confirmation_needed'] and not has_reversal_signal:
                return 0, "No reversal confirmation signal"

            return 1, f"{consecutive_red} red candles, Vol {volume_spike:.1f}x, Down {down_percent:.1f}%"

        except Exception as e:
            return 0, f"Error evaluating red_to_green: {e}"

    def _evaluate_first_day_bounce(self, symbol: str, context: Any) -> tuple[int, str]:
        """Evaluate First Day Bounce (Overextension Bounce) strategy criteria"""
        try:
            rules = self.rules['first_day_bounce']

            down_percent = abs(getattr(context, 'day_change_percent', 0))
            volume_ratio = getattr(context, 'volume_ratio', 0)
            bounce_percent = getattr(context, 'intraday_bounce_percent', 0)
            overextension_gain = getattr(context, 'recent_overextension_gain', 0)
            has_recent_peak = getattr(context, 'has_recent_peak', False)

            # Minimum down move check (retrace from highs)
            if down_percent < rules['min_down_percent']:
                return 0, f"Only down {down_percent:.1f}% < {rules['min_down_percent']}%"

            # Volume check
            if volume_ratio < rules['min_volume_ratio']:
                return 0, f"Volume {volume_ratio:.1f}x < {rules['min_volume_ratio']}x"

            # Bounce signal check
            if bounce_percent < rules['min_bounce_percent']:
                return 0, f"Bounce {bounce_percent:.1f}% < {rules['min_bounce_percent']}%"

            # Overextension check (align with real strategy)
            if overextension_gain < rules['min_overextension_gain']:
                return 0, f"No significant overextension ({overextension_gain:.1f}% < {rules['min_overextension_gain']}%)"

            # Recent peak check
            if rules['require_recent_peak'] and not has_recent_peak:
                return 0, "No recent peak detected for bounce setup"

            return 1, f"Overextension bounce: Down {down_percent:.1f}%, Bounce {bounce_percent:.1f}%, Vol {volume_ratio:.1f}x, Prev gain {overextension_gain:.1f}%"

        except Exception as e:
            return 0, f"Error evaluating first_day_bounce: {e}"

    def _evaluate_macdv_smallcaps(self, symbol: str, context: Any) -> tuple[int, str]:
        """Evaluate MACDV Smallcaps strategy criteria"""
        try:
            rules = self.rules['macdv_smallcaps']
            current_hour = getattr(context, 'current_hour', self._get_current_hour())

            macd_convergence = getattr(context, 'macd_convergence_5min', False)
            macd_timing = getattr(context, 'macd_timing_1min', False)
            volume_adequate = getattr(context, 'volume_adequate', False)

            # MACD convergence check
            if rules['require_convergence'] and not macd_convergence:
                return 0, "No MACD convergence detected"

            # Volume confirmation check
            if rules['require_volume_confirmation'] and not volume_adequate:
                return 0, "Volume confirmation missing"

            # Avoid first 30 minutes
            if rules['avoid_first_30min'] and current_hour < 10.0:
                return 0, f"Too early ({current_hour:.1f}h), avoiding first 30min"

            # Multi-timeframe alignment
            if rules['min_timeframe_alignment'] and not (macd_convergence and macd_timing):
                return 0, "Timeframe alignment missing"

            return 1, f"MACD convergence + timing aligned, Vol confirmed"

        except Exception as e:
            return 0, f"Error evaluating macdv_smallcaps: {e}"

    def _evaluate_daily_plays(self, symbol: str, context: Any) -> tuple[int, str]:
        """Evaluate Daily Plays strategy criteria"""
        try:
            rules = self.rules['daily_plays']

            has_catalyst = getattr(context, 'has_catalyst', False)
            momentum_score = getattr(context, 'momentum_score', 0)
            volume_explosion = getattr(context, 'volume_ratio', 0)
            price = getattr(context, 'current_price', 0)

            # Catalyst requirement
            if rules['require_catalyst'] and not has_catalyst:
                return 0, "No catalyst detected"

            # Momentum score check
            if momentum_score < rules['min_momentum_score']:
                return 0, f"Momentum {momentum_score:.2f} < {rules['min_momentum_score']}"

            # Volume explosion check
            if volume_explosion < rules['min_volume_explosion']:
                return 0, f"Volume {volume_explosion:.1f}x < {rules['min_volume_explosion']}x"

            # Price range check
            if price > rules['max_price']:
                return 0, f"Price ${price:.2f} > ${rules['max_price']}"

            return 1, f"Catalyst + momentum {momentum_score:.2f} + volume {volume_explosion:.1f}x"

        except Exception as e:
            return 0, f"Error evaluating daily_plays: {e}"

    def _get_current_hour(self) -> float:
        """Get current hour in decimal format (e.g., 10.5 for 10:30 AM)"""
        now = datetime.now()
        return now.hour + now.minute / 60.0

    def get_selection_stats(self) -> Dict[str, Any]:
        """Get statistics about rule-based selections"""
        if not self.selection_history:
            return {}

        strategy_counts = {}
        total_selections = len(self.selection_history)

        for selection_data in self.selection_history.values():
            for strategy in selection_data['selected']:
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

        return {
            'total_selections': total_selections,
            'strategy_counts': strategy_counts,
            'strategy_percentages': {
                strategy: (count / total_selections) * 100
                for strategy, count in strategy_counts.items()
            }
        }

    def update_rules(self, strategy: str, rule_updates: Dict[str, Any]) -> None:
        """Update rules for a specific strategy"""
        if strategy in self.rules:
            self.rules[strategy].update(rule_updates)
            self.logger.info(f"📝 Updated rules for {strategy}: {rule_updates}")
        else:
            self.logger.warning(f"Strategy {strategy} not found in rules")