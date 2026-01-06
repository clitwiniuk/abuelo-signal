"""
Realistic Strategy Engine - Industry-Proven Approach
Based on what successful hedge funds actually do:
- 3 core strategies maximum
- 5-minute evaluation intervals
- Conservative switching
- Focus on quality over quantity
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import configparser

from core.interfaces import IStrategy, Signal, MarketData
from strategies.base import BaseStrategy
from strategies.strategy_switch_limiter import StrategySwitchLimiter
from core.realistic_market_data import RealisticMarketData, get_realistic_enricher


class RealisticStrategyEngine(BaseStrategy):
    """
    Realistic strategy engine based on industry practices
    - Maximum 3 core strategies
    - 5-minute evaluation intervals
    - Conservative switching with high thresholds
    - Focus on proven setups only
    """

    def __init__(self, parameters: Dict[str, Any] = None):
        super().__init__(name="RealisticStrategyEngine", parameters=parameters)
        self.event_bus = None

        # Load configuration
        self.config = configparser.ConfigParser()
        try:
            self.config.read('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/config.ini')
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            self.config = configparser.ConfigParser()

        # CORE STRATEGIES ONLY (the 4 that work best)
        self.core_strategies = {
            'gap_go': 'strategies.gap_go_strategy',           # Clear gap plays
            'daily_plays': 'strategies.daily_plays_strategy', # News-driven moves
            'macdv': 'strategies.macdv_strategy',             # Technical baseline
            'bull_flag': 'strategies.bull_flag_strategy',     # Momentum continuation patterns
            'parabolic': 'strategies.parabolic_strategy'      # Parabolic extensions (Long)
        }

        # Strategy instances cache
        self.strategy_instances: Dict[str, IStrategy] = {}

        # REALISTIC CONFIGURATION
        self.max_active_tickers = self.config.getint('REALISTIC_SYSTEM', 'max_active_tickers', fallback=3)
        self.evaluation_interval_minutes = self.config.getint('REALISTIC_SYSTEM', 'evaluation_interval_minutes', fallback=5)
        self.min_switch_confidence_diff = self.config.getfloat('REALISTIC_SYSTEM', 'min_switch_confidence_diff', fallback=0.25)
        self.max_daily_switches = self.config.getint('REALISTIC_SYSTEM', 'max_daily_switches', fallback=2)

        # Essential thresholds (relaxed for real opportunities)
        self.min_gap_threshold = self.config.getfloat('REALISTIC_SYSTEM', 'min_gap_threshold', fallback=1.5)  # Reduced from 3.0 to 1.5
        self.min_volume_ratio = self.config.getfloat('REALISTIC_SYSTEM', 'min_volume_ratio', fallback=1.1)   # Reduced from 1.2 to 1.1
        self.min_confidence_threshold = self.config.getfloat('REALISTIC_SYSTEM', 'min_confidence_threshold', fallback=0.40)  # Reduced from 0.50 to 0.40

        # Switch limiter with conservative settings
        self.switch_limiter = StrategySwitchLimiter(self.config)
        self.switch_limiter.max_switches_per_day = self.max_daily_switches
        self.switch_limiter.min_confidence_difference = self.min_switch_confidence_diff
        self.switch_limiter.cooldown_minutes = 30  # Conservative cooldown

        # Data enricher
        self.data_enricher = get_realistic_enricher()

        # Tracking
        self.last_evaluation: Dict[str, datetime] = {}
        self.active_positions: Dict[str, str] = {}  # {symbol: active_strategy}
        self.evaluation_count = 0

        self.logger.info(f"✅ Realistic Strategy Engine initialized")
        self.logger.info(f"📊 Core strategies: {list(self.core_strategies.keys())}")
        self.logger.info(f"⏰ Evaluation interval: {self.evaluation_interval_minutes} minutes")
        self.logger.info(f"🎯 Max active tickers: {self.max_active_tickers}")
        self.logger.info(f"🔒 Max daily switches: {self.max_daily_switches}")
        self.logger.info(f"📈 Min confidence threshold: {self.min_confidence_threshold}")

    # Abstract methods implementation
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Implementation of abstract method - extract symbol from bar"""
        symbol = bar.symbol
        signals = await self.analyze(symbol, bar)
        return signals[0] if signals else None

    def should_exit(self, symbol: str, position: 'Position', current_price: float) -> bool:
        """Delegate exit logic to active strategy"""
        active_strategy = self.switch_limiter.get_current_strategy(symbol)
        if active_strategy and active_strategy in self.strategy_instances:
            strategy = self.strategy_instances[active_strategy]
            if hasattr(strategy, 'should_exit'):
                return strategy.should_exit(symbol, position, current_price)
        return False

    def on_position_update(self, symbol: str, position: 'Position'):
        """Handle position updates"""
        self.logger.debug(f"📊 Position update {symbol}: {position.quantity} shares")

    async def initialize(self, event_bus=None, broker=None):
        """Initialize the strategy engine"""
        self.event_bus = event_bus
        self.broker = broker  # Store broker reference if provided
        self.logger.info("🚀 Realistic Strategy Engine ready")
        return True

    async def analyze(self, symbol: str, data: MarketData) -> List[Signal]:
        """
        Main analysis with realistic approach:
        - Evaluate every 5 minutes (not every minute)
        - Use enriched data for intelligent selection
        - Conservative switching
        """
        try:
            # Check if evaluation is due (realistic timing)
            if not self._should_evaluate_now(symbol):
                # Return cached/current active strategy result if available
                return await self._execute_active_strategy(symbol, data)

            # Increment evaluation counter
            self.evaluation_count += 1

            # Enrich market data with essential indicators
            if not isinstance(data, RealisticMarketData):
                # This would be done by scanner in real implementation
                enriched_data = data  # Use basic data for now
            else:
                enriched_data = data

            # Perform realistic evaluation
            return await self._realistic_evaluation(symbol, enriched_data)

        except Exception as e:
            self.logger.error(f"❌ Error analyzing {symbol}: {e}")
            return []

    def _should_evaluate_now(self, symbol: str) -> bool:
        """Check if full evaluation is due (every 5 minutes)"""
        last_eval = self.last_evaluation.get(symbol)
        if not last_eval:
            return True

        minutes_since_eval = (datetime.now() - last_eval).total_seconds() / 60
        return minutes_since_eval >= self.evaluation_interval_minutes

    async def _execute_active_strategy(self, symbol: str, data: MarketData) -> List[Signal]:
        """Execute currently active strategy without re-evaluation"""
        try:
            active_strategy = self.switch_limiter.get_current_strategy(symbol)
            if not active_strategy:
                return []

            strategy = await self._get_strategy_instance(active_strategy)
            if strategy:
                signal = await strategy._analyze_bar(data)
                return [signal] if signal else []

            return []

        except Exception as e:
            self.logger.error(f"❌ Error executing active strategy for {symbol}: {e}")
            return []

    async def _realistic_evaluation(self, symbol: str, data: MarketData) -> List[Signal]:
        """Perform realistic strategy evaluation"""
        try:
            # Update last evaluation time
            self.last_evaluation[symbol] = datetime.now()

            # Get current active strategy
            current_strategy = self.switch_limiter.get_current_strategy(symbol)

            # If no active strategy, do initial selection
            if not current_strategy:
                return await self._initial_strategy_selection(symbol, data)

            # Check if we should consider switching (conservative approach)
            if self.evaluation_count % 3 == 0:  # Only consider switching every 15 minutes
                return await self._consider_strategy_switch(symbol, data, current_strategy)

            # Execute current strategy
            return await self._execute_active_strategy(symbol, data)

        except Exception as e:
            self.logger.error(f"❌ Error in realistic evaluation for {symbol}: {e}")
            return []

    async def _initial_strategy_selection(self, symbol: str, data: MarketData) -> List[Signal]:
        """Initial strategy selection using realistic criteria"""
        try:
            # Extract essential indicators
            if isinstance(data, RealisticMarketData):
                indicators = data.essential_indicators
                context = data.setup_context
            else:
                # Fallback to basic analysis
                indicators = self._extract_basic_indicators(data)
                context = None

            # REALISTIC STRATEGY SELECTION (conservative rules)
            selected_strategy = None

            # DEBUG: Log the calculated indicators
            self.logger.error(f"🔍 DEBUG {symbol} Indicators: Gap={indicators.gap_percent:.1f}%, Vol={indicators.volume_ratio:.1f}x, "
                             f"Time={indicators.minutes_since_open}min, OptimalTime={indicators.optimal_trading_time}")
            self.logger.error(f"🔍 DEBUG Thresholds: min_gap={self.min_gap_threshold}, min_vol={self.min_volume_ratio}")

            # Rule 1: Gap Go (only for clear, strong gaps)
            if (abs(indicators.gap_percent) >= self.min_gap_threshold and
                indicators.volume_ratio >= self.min_volume_ratio and
                indicators.optimal_trading_time):
                selected_strategy = 'gap_go'
                self.logger.error(f"✅ DEBUG {symbol}: Gap Go selected - {abs(indicators.gap_percent):.1f}% gap, {indicators.volume_ratio:.1f}x volume")

            # Rule 2: Bull Flag (momentum continuation patterns) - Check BEFORE Daily Plays
            elif (0.8 <= abs(indicators.gap_percent) < 2.0 and  # Small-medium gap (relaxed from 1.5-3.0)
                  1.3 <= indicators.volume_ratio < 3.0 and      # Good volume but not explosive (relaxed from 1.8-4.0)
                  indicators.optimal_trading_time and           # Good timing
                  indicators.price_trend_5min == 'bullish'):    # Bullish trend
                selected_strategy = 'bull_flag'
                self.logger.error(f"🏴 DEBUG {symbol}: Bull Flag selected - {indicators.gap_percent:.1f}% gap, {indicators.volume_ratio:.1f}x vol, bullish trend")

            # Rule 3: Daily Plays (news-driven with strong volume) - Relaxed for more opportunities
            elif (indicators.volume_ratio >= 2.5 and            # Strong volume (relaxed from 4.0)
                  indicators.minutes_since_open >= 15 and
                  (context is None or context.time_quality in ['good', 'fair'])):
                selected_strategy = 'daily_plays'
                self.logger.error(f"✅ DEBUG {symbol}: Daily Plays selected - {indicators.volume_ratio:.1f}x volume")

            # Rule 4: MACDV (technical baseline, always available)
            else:
                selected_strategy = 'macdv'
                self.logger.error(f"⚡ DEBUG {symbol}: MACDV baseline selected (gap={indicators.gap_percent:.1f}%, vol={indicators.volume_ratio:.1f}x)")

            # Execute selected strategy
            if selected_strategy:
                self.switch_limiter.set_initial_strategy(symbol, selected_strategy)
                self.active_positions[symbol] = selected_strategy

                strategy = await self._get_strategy_instance(selected_strategy)
                if strategy:
                    signal = await strategy._analyze_bar(data)
                    signals = [signal] if signal else []

                    # Apply realistic confidence threshold
                    filtered_signals = [s for s in signals if s.confidence >= self.min_confidence_threshold]

                    if filtered_signals:
                        self.logger.info(f"🎯 {symbol}: Initial strategy {selected_strategy} (confidence: {max(s.confidence for s in filtered_signals):.1%})")

                    return filtered_signals

            return []

        except Exception as e:
            self.logger.error(f"❌ Error in initial selection for {symbol}: {e}")
            return []

    async def _consider_strategy_switch(self, symbol: str, data: MarketData, current_strategy: str) -> List[Signal]:
        """Consider switching strategy with conservative approach"""
        try:
            # Evaluate all core strategies
            strategy_results = {}

            for strategy_name in self.core_strategies.keys():
                try:
                    strategy = await self._get_strategy_instance(strategy_name)
                    if strategy:
                        signal = await strategy._analyze_bar(data)
                        signals = [signal] if signal else []
                        if signals:
                            max_confidence = max(s.confidence for s in signals)
                            strategy_results[strategy_name] = {
                                'confidence': max_confidence,
                                'signals': signals
                            }
                        else:
                            strategy_results[strategy_name] = {
                                'confidence': 0.0,
                                'signals': []
                            }
                except Exception as e:
                    self.logger.debug(f"Strategy {strategy_name} evaluation failed for {symbol}: {e}")
                    strategy_results[strategy_name] = {'confidence': 0.0, 'signals': []}

            # Find best strategy
            if strategy_results:
                best_strategy = max(strategy_results.items(), key=lambda x: x[1]['confidence'])
                best_name, best_result = best_strategy
                current_confidence = strategy_results.get(current_strategy, {}).get('confidence', 0.0)

                confidence_diff = best_result['confidence'] - current_confidence

                # Conservative switching decision
                if (best_name != current_strategy and
                    confidence_diff >= self.min_switch_confidence_diff and
                    best_result['confidence'] >= self.min_confidence_threshold):

                    # Check if switch is allowed
                    can_switch, reason = self.switch_limiter.can_switch_strategy(
                        symbol, current_strategy, best_name, confidence_diff
                    )

                    if can_switch:
                        # Execute the switch
                        self.switch_limiter.record_strategy_switch(
                            symbol, current_strategy, best_name, confidence_diff,
                            f"Realistic evaluation: {best_name} ({best_result['confidence']:.1%}) > {current_strategy} ({current_confidence:.1%})"
                        )
                        self.active_positions[symbol] = best_name

                        # Return signals from new strategy
                        filtered_signals = [s for s in best_result['signals'] if s.confidence >= self.min_confidence_threshold]
                        return filtered_signals
                    else:
                        self.logger.debug(f"🚫 {symbol}: Switch blocked - {reason}")

                # Return current strategy signals
                current_result = strategy_results.get(current_strategy, {})
                if current_result.get('signals'):
                    filtered_signals = [s for s in current_result['signals'] if s.confidence >= self.min_confidence_threshold]
                    return filtered_signals

            return []

        except Exception as e:
            self.logger.error(f"❌ Error considering switch for {symbol}: {e}")
            return []

    def _extract_basic_indicators(self, data: MarketData) -> Any:
        """Extract basic indicators when enriched data not available"""
        # Simple fallback class
        class BasicIndicators:
            def __init__(self):
                self.gap_percent = 0.0
                self.volume_ratio = 1.0
                self.optimal_trading_time = True
                self.minutes_since_open = 60
                self.price_trend_5min = "neutral"

        indicators = BasicIndicators()

        # DEBUG: Log what data is available
        prev_close = getattr(data, 'prev_close', None)
        avg_volume = getattr(data, 'avg_volume', None)
        self.logger.error(f"🔍 DEBUG _extract_basic_indicators: symbol={data.symbol}, prev_close={prev_close}, avg_volume={avg_volume}")
        self.logger.error(f"🔍 DEBUG _extract_basic_indicators: open={data.open}, close={data.close}, volume={data.volume}")

        # Calculate gap if prev_close available
        if prev_close and prev_close > 0:
            indicators.gap_percent = (data.open - prev_close) / prev_close * 100
            self.logger.error(f"🔍 DEBUG: Gap calculated: {indicators.gap_percent:.2f}%")

        # Calculate volume ratio if avg_volume available
        if avg_volume and avg_volume > 0:
            indicators.volume_ratio = data.volume / avg_volume
            self.logger.error(f"🔍 DEBUG: Volume ratio calculated: {indicators.volume_ratio:.2f}x")

        # Basic price trend (simple calculation based on close vs open)
        if data.close > data.open * 1.02:  # +2% from open
            indicators.price_trend_5min = "bullish"
        elif data.close < data.open * 0.98:  # -2% from open
            indicators.price_trend_5min = "bearish"
        else:
            indicators.price_trend_5min = "neutral"

        # Basic timing - use bar timestamp if available, otherwise current time
        bar_time = getattr(data, 'timestamp', datetime.now())
        market_open = bar_time.replace(hour=9, minute=30, second=0, microsecond=0)

        if bar_time.date() == market_open.date() and bar_time >= market_open:
            indicators.minutes_since_open = max(0, int((bar_time - market_open).total_seconds() / 60))
            indicators.optimal_trading_time = 30 <= indicators.minutes_since_open <= 360
        else:
            # For testing or after hours - be more lenient
            indicators.minutes_since_open = 60  # Assume 1 hour into trading
            indicators.optimal_trading_time = True

        return indicators

    async def _get_strategy_instance(self, strategy_name: str) -> Optional[IStrategy]:
        """Get strategy instance (same logic as DynamicStrategyEngine)"""
        try:
            # Return cached
            if strategy_name in self.strategy_instances:
                return self.strategy_instances[strategy_name]

            if strategy_name not in self.core_strategies:
                self.logger.error(f"Unknown core strategy: {strategy_name}")
                return None

            module_path = self.core_strategies[strategy_name]
            module_name, class_name_part = module_path.rsplit('.', 1)

            # Special cases for specific strategies
            if class_name_part == 'macdv_strategy':
                class_name = 'MACDVStrategy'
            else:
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
        return "RealisticStrategyEngine"

    def get_description(self) -> str:
        return "Industry-proven strategy engine - 3 core strategies, 5-min intervals, conservative switching"

    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return {
            'engine_type': 'realistic',
            'core_strategies': list(self.core_strategies.keys()),
            'active_tickers': len(self.active_positions),
            'active_positions': dict(self.active_positions),
            'evaluation_count': self.evaluation_count,
            'evaluation_interval_minutes': self.evaluation_interval_minutes,
            'switch_limiter_stats': {
                'max_daily_switches': self.switch_limiter.max_switches_per_day,
                'cooldown_minutes': self.switch_limiter.cooldown_minutes
            }
        }


def create_realistic_strategy_engine(parameters: Dict[str, Any] = None) -> RealisticStrategyEngine:
    """Factory function to create Realistic Strategy Engine"""
    return RealisticStrategyEngine(parameters)


if __name__ == "__main__":
    print("🧪 Realistic Strategy Engine Test")
    print("=" * 50)

    engine = create_realistic_strategy_engine()
    print(f"✅ Engine: {engine.get_name()}")
    print(f"📝 Description: {engine.get_description()}")
    print(f"⏰ Evaluation interval: {engine.evaluation_interval_minutes} minutes")
    print(f"🎯 Core strategies: {list(engine.core_strategies.keys())}")
    print("=" * 50)
    print("🎉 Industry-proven approach ready!")