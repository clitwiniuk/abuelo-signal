"""
Dynamic Strategy Engine - ZERO ML Dependencies + Continuous Re-evaluation
Replaces SimpleStrategyEngine with dynamic strategy switching capabilities
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import configparser

from core.interfaces import IStrategy, Signal, MarketData
from strategies.base import BaseStrategy
from strategies.strategy_switch_limiter import StrategySwitchLimiter


class DynamicStrategyEngine(BaseStrategy):
    """
    Dynamic multi-strategy engine with continuous re-evaluation
    - Monitors ALL strategies continuously
    - Switches strategies when better opportunities arise
    - Prevents over-switching with circuit breaker
    """

    def __init__(self, parameters: Dict[str, Any] = None):
        super().__init__(name="DynamicStrategyEngine", parameters=parameters)
        self.event_bus = None

        # Load configuration
        self.config = configparser.ConfigParser()
        try:
            self.config.read('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/config.ini')
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            self.config = configparser.ConfigParser()

        # Strategy instances cache
        self.strategy_instances: Dict[str, IStrategy] = {}

        # Available strategies mapping - ONLY ACTIVE ONES
        self.strategy_mapping = {
            'gap_go': 'strategies.gap_go_strategy',
            'daily_plays': 'strategies.daily_plays_strategy',
            'macdv_smallcaps': 'strategies.macdv_smallcaps_strategy',
            'first_day_bounce': 'strategies.first_day_bounce_strategy',
            'red_to_green': 'strategies.red_to_green_strategy',
            'gap_crap_reversal': 'strategies.gap_crap_reversal_strategy',
            'ascending_triangle': 'strategies.ascending_triangle_strategy',
            'bull_flag': 'strategies.bull_flag_strategy',
            'falling_wedge': 'strategies.falling_wedge_strategy'
        }

        # Configuration
        self.max_strategies_per_ticker = self.config.getint('SIMPLE_STRATEGY', 'max_strategies_per_ticker', fallback=3)
        self.min_gap_for_gap_go = self.config.getfloat('SIMPLE_STRATEGY', 'min_gap_for_gap_go', fallback=8.0)
        self.min_volume_ratio = self.config.getfloat('SIMPLE_STRATEGY', 'min_volume_ratio', fallback=1.5)
        self.max_smallcap_price = self.config.getfloat('SIMPLE_STRATEGY', 'max_smallcap_price', fallback=15.0)
        self.news_volume_threshold = self.config.getfloat('SIMPLE_STRATEGY', 'news_volume_threshold', fallback=3.0)

        # Dynamic configuration
        self.re_evaluation_interval = self.config.getint('DYNAMIC_STRATEGY', 're_evaluation_interval_seconds', fallback=300)
        self.parallel_monitoring = self.config.getboolean('DYNAMIC_STRATEGY', 'parallel_monitoring_enabled', fallback=True)

        # Switch limiter
        self.switch_limiter = StrategySwitchLimiter(self.config)

        # Tracking
        self.last_evaluation: Dict[str, datetime] = {}
        self.strategy_scores: Dict[str, Dict[str, float]] = {}  # {symbol: {strategy: confidence}}
        self.active_strategies: Dict[str, str] = {}  # {symbol: current_strategy}

        self.logger.info(f"✅ Dynamic Strategy Engine initialized - ZERO ML")
        self.logger.info(f"📊 Max strategies per ticker: {self.max_strategies_per_ticker}")
        self.logger.info(f"🔄 Re-evaluation interval: {self.re_evaluation_interval}s")
        self.logger.info(f"🎯 Parallel monitoring: {self.parallel_monitoring}")

    # Abstract methods implementation
    async def _analyze_bar(self, symbol: str, bar: MarketData) -> List[Signal]:
        """Implementation of abstract method - use analyze method"""
        return await self.analyze(symbol, bar)

    def should_exit(self, symbol: str, position: 'Position', current_price: float) -> bool:
        """Let active strategy handle exits"""
        active_strategy = self.switch_limiter.get_current_strategy(symbol)
        if active_strategy and active_strategy in self.strategy_instances:
            strategy = self.strategy_instances[active_strategy]
            if hasattr(strategy, 'should_exit'):
                return strategy.should_exit(symbol, position, current_price)
        return False

    def on_position_update(self, symbol: str, position: 'Position'):
        """Handle position updates"""
        self.logger.debug(f"📊 Position update for {symbol}: {position.quantity} shares")

    async def initialize(self, event_bus=None):
        """Initialize the strategy engine"""
        self.event_bus = event_bus
        self.logger.info("🚀 Dynamic Strategy Engine ready")
        return True

    async def analyze(self, symbol: str, data: MarketData) -> List[Signal]:
        """
        Main analysis method with dynamic re-evaluation
        """
        try:
            # Check if re-evaluation is needed
            if self._should_re_evaluate(symbol):
                await self._continuous_evaluation(symbol, data)

            # Get current active strategy
            active_strategy = self.switch_limiter.get_current_strategy(symbol)

            if not active_strategy:
                # First time - do initial strategy selection
                await self._initial_strategy_selection(symbol, data)
                active_strategy = self.switch_limiter.get_current_strategy(symbol)

            if not active_strategy:
                self.logger.warning(f"⚠️ {symbol}: No strategy selected")
                return []

            # Execute active strategy
            strategy = await self._get_strategy_instance(active_strategy)
            if strategy:
                signals = await strategy.analyze(symbol, data)
                if signals:
                    self.logger.info(f"✅ {symbol}: {active_strategy} generated {len(signals)} signals")
                return signals

            return []

        except Exception as e:
            self.logger.error(f"❌ Error analyzing {symbol}: {e}")
            return []

    async def _initial_strategy_selection(self, symbol: str, data: MarketData):
        """Initial strategy selection for new symbol"""
        try:
            context = self._get_symbol_context(symbol, data)
            initial_strategies = self._rule_based_selection(symbol, context)

            if initial_strategies:
                # Select best strategy from initial candidates
                best_strategy = await self._select_best_strategy(symbol, data, initial_strategies)
                if best_strategy:
                    self.switch_limiter.set_initial_strategy(symbol, best_strategy)
                    self.active_strategies[symbol] = best_strategy
                    self._log_initial_selection(symbol, context, best_strategy)

        except Exception as e:
            self.logger.error(f"❌ Error in initial selection for {symbol}: {e}")

    async def _continuous_evaluation(self, symbol: str, data: MarketData):
        """Continuously evaluate ALL strategies and switch if better found"""
        try:
            if not self.parallel_monitoring:
                return  # Skip if parallel monitoring disabled

            # Evaluate ALL available strategies
            strategy_scores = {}

            for strategy_name in self.strategy_mapping.keys():
                try:
                    strategy = await self._get_strategy_instance(strategy_name)
                    if strategy:
                        signals = await strategy.analyze(symbol, data)
                        if signals:
                            max_confidence = max(s.confidence for s in signals)
                            strategy_scores[strategy_name] = max_confidence
                        else:
                            strategy_scores[strategy_name] = 0.0
                except Exception as e:
                    self.logger.debug(f"Strategy {strategy_name} evaluation failed for {symbol}: {e}")
                    strategy_scores[strategy_name] = 0.0

            # Store scores for analysis
            self.strategy_scores[symbol] = strategy_scores

            # Find best strategy
            if strategy_scores:
                best_strategy = max(strategy_scores.items(), key=lambda x: x[1])
                await self._consider_strategy_switch(symbol, best_strategy, strategy_scores)

            # Update last evaluation time
            self.last_evaluation[symbol] = datetime.now()

        except Exception as e:
            self.logger.error(f"❌ Error in continuous evaluation for {symbol}: {e}")

    async def _consider_strategy_switch(self, symbol: str, best_strategy: tuple, all_scores: Dict[str, float]):
        """Consider switching to better strategy"""
        try:
            best_name, best_confidence = best_strategy
            current_strategy = self.switch_limiter.get_current_strategy(symbol)

            if not current_strategy:
                return

            current_confidence = all_scores.get(current_strategy, 0.0)
            confidence_diff = best_confidence - current_confidence

            # Check if switch is allowed
            can_switch, reason = self.switch_limiter.can_switch_strategy(
                symbol, current_strategy, best_name, confidence_diff
            )

            if can_switch and best_confidence > 0.6:  # Minimum threshold
                # Execute the switch
                self.switch_limiter.record_strategy_switch(
                    symbol, current_strategy, best_name, confidence_diff,
                    f"Better strategy found: {best_name} ({best_confidence:.1%}) vs {current_strategy} ({current_confidence:.1%})"
                )
                self.active_strategies[symbol] = best_name

                self.logger.info(f"🔄 {symbol}: Switched to {best_name} (confidence: {best_confidence:.1%})")

            elif not can_switch:
                self.logger.debug(f"🚫 {symbol}: Switch blocked - {reason}")

        except Exception as e:
            self.logger.error(f"❌ Error considering switch for {symbol}: {e}")

    async def _select_best_strategy(self, symbol: str, data: MarketData, candidates: List[str]) -> Optional[str]:
        """Select best strategy from candidates"""
        try:
            best_strategy = None
            best_confidence = 0.0

            for strategy_name in candidates:
                strategy = await self._get_strategy_instance(strategy_name)
                if strategy:
                    signals = await strategy.analyze(symbol, data)
                    if signals:
                        max_confidence = max(s.confidence for s in signals)
                        if max_confidence > best_confidence:
                            best_confidence = max_confidence
                            best_strategy = strategy_name

            return best_strategy

        except Exception as e:
            self.logger.error(f"❌ Error selecting best strategy for {symbol}: {e}")
            return candidates[0] if candidates else None

    def _should_re_evaluate(self, symbol: str) -> bool:
        """Check if symbol needs re-evaluation"""
        if not self.parallel_monitoring:
            return False

        last_eval = self.last_evaluation.get(symbol)
        if not last_eval:
            return True

        return datetime.now() - last_eval > timedelta(seconds=self.re_evaluation_interval)

    def _get_symbol_context(self, symbol: str, data: MarketData) -> Dict[str, Any]:
        """Extract symbol context for strategy selection"""
        try:
            current_price = data.close
            prev_close = getattr(data, 'prev_close', current_price)
            volume = getattr(data, 'volume', 0)
            avg_volume = getattr(data, 'avg_volume', volume)

            gap_percent = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
            volume_ratio = (volume / avg_volume) if avg_volume > 0 else 1.0

            now = datetime.now()
            market_hour = now.hour
            is_market_hours = 9 <= market_hour <= 16
            has_news = volume_ratio >= self.news_volume_threshold or abs(gap_percent) >= 5.0

            return {
                'symbol': symbol,
                'current_price': current_price,
                'prev_close': prev_close,
                'gap_percent': gap_percent,
                'volume_ratio': volume_ratio,
                'market_hour': market_hour,
                'is_market_hours': is_market_hours,
                'has_news': has_news,
                'is_smallcap': current_price <= self.max_smallcap_price
            }

        except Exception as e:
            self.logger.error(f"Error getting context for {symbol}: {e}")
            return {}

    def _rule_based_selection(self, symbol: str, context: Dict[str, Any]) -> List[str]:
        """Rule-based strategy selection - same logic as SimpleStrategyEngine"""
        try:
            selected = []
            gap_pct = context.get('gap_percent', 0)
            vol_ratio = context.get('volume_ratio', 1.0)
            price = context.get('current_price', 0)
            has_news = context.get('has_news', False)
            is_smallcap = context.get('is_smallcap', True)
            hour = context.get('market_hour', 10)

            # Same rules as SimpleStrategyEngine but return more candidates
            if abs(gap_pct) >= self.min_gap_for_gap_go and vol_ratio >= 2.0:
                selected.append('gap_go')

            if has_news and vol_ratio >= self.news_volume_threshold and is_smallcap:
                selected.append('daily_plays')

            if (abs(gap_pct) <= 5.0 and vol_ratio >= self.min_volume_ratio
                  and not has_news and 9 <= hour <= 15):
                selected.append('macdv_smallcaps')

            if gap_pct <= -5.0 and vol_ratio >= 2.0 and is_smallcap:
                selected.append('first_day_bounce')
                if gap_pct <= -8.0:
                    selected.append('gap_crap_reversal')

            if vol_ratio >= 1.8 and is_smallcap and abs(gap_pct) <= 3.0 and 9 <= hour <= 15:
                selected.append('ascending_triangle')
                if vol_ratio >= 2.5:
                    selected.append('bull_flag')

            # Fallback
            if not selected and is_smallcap and vol_ratio >= 1.2:
                selected.append('macdv_smallcaps')

            # Limit candidates
            if len(selected) > self.max_strategies_per_ticker:
                selected = selected[:self.max_strategies_per_ticker]

            return selected

        except Exception as e:
            self.logger.error(f"Error in rule selection for {symbol}: {e}")
            return ['macdv_smallcaps']

    def _log_initial_selection(self, symbol: str, context: Dict[str, Any], strategy: str):
        """Log initial strategy selection with reasoning"""
        gap = context.get('gap_percent', 0)
        vol = context.get('volume_ratio', 1.0)
        price = context.get('current_price', 0)
        news = context.get('has_news', False)

        self.logger.info(f"🎯 {symbol}: Initial strategy selected: {strategy}")
        self.logger.info(f"   💰 Price: ${price:.2f} | Gap: {gap:.1f}% | Vol: {vol:.1f}x | News: {news}")

    async def _get_strategy_instance(self, strategy_name: str) -> Optional[IStrategy]:
        """Get strategy instance with config parameters - same as SimpleStrategyEngine"""
        try:
            if strategy_name in self.strategy_instances:
                return self.strategy_instances[strategy_name]

            if strategy_name not in self.strategy_mapping:
                self.logger.error(f"Unknown strategy: {strategy_name}")
                return None

            module_path = self.strategy_mapping[strategy_name]
            module_name, class_name_part = module_path.rsplit('.', 1)
            class_name = ''.join(word.capitalize() for word in class_name_part.split('_'))
            if not class_name.endswith('Strategy'):
                class_name += 'Strategy'

            module = __import__(module_name, fromlist=[class_name])
            strategy_class = getattr(module, class_name)

            # Load config parameters
            config_section = f"{strategy_name.upper()}_STRATEGY"
            params = {}
            if self.config.has_section(config_section):
                params = dict(self.config.items(config_section))
                for key, value in params.items():
                    try:
                        if '.' in str(value):
                            params[key] = float(value)
                        elif str(value).isdigit():
                            params[key] = int(value)
                    except (ValueError, AttributeError):
                        pass

            strategy = strategy_class(params)

            if hasattr(strategy, 'initialize'):
                await strategy.initialize(self.event_bus)

            self.strategy_instances[strategy_name] = strategy
            return strategy

        except Exception as e:
            self.logger.error(f"❌ Failed loading {strategy_name}: {e}")
            return None

    def get_name(self) -> str:
        return "DynamicStrategyEngine"

    def get_description(self) -> str:
        return "Dynamic strategy engine with continuous re-evaluation - ZERO ML dependencies"

    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get statistics about strategy performance"""
        return {
            'active_symbols': len(self.active_strategies),
            'strategy_instances_loaded': len(self.strategy_instances),
            'current_strategies': dict(self.active_strategies),
            'switch_limiter_stats': self.switch_limiter.get_daily_stats() if hasattr(self.switch_limiter, 'get_daily_stats') else {},
            'last_evaluation_times': {k: v.isoformat() for k, v in self.last_evaluation.items()}
        }


def create_dynamic_strategy_engine(parameters: Dict[str, Any] = None) -> DynamicStrategyEngine:
    """Factory function to create Dynamic Strategy Engine"""
    return DynamicStrategyEngine(parameters)


if __name__ == "__main__":
    print("🧪 Dynamic Strategy Engine Test")
    print("=" * 50)

    engine = create_dynamic_strategy_engine()
    print(f"✅ Engine: {engine.get_name()}")
    print(f"📝 Description: {engine.get_description()}")
    print("=" * 50)
    print("🎉 Dynamic Strategy Engine ready - continuous re-evaluation enabled!")