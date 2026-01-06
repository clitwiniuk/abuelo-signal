"""
Simple Strategy Engine - ZERO ML Dependencies
Replaces ALL ML components with pure rule-based strategy selection
100% predictable, 100% debuggable, 100% controllable
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, time
import configparser

from core.interfaces import IStrategy, Signal, MarketData
from core.pipeline import PipelineStage
from strategies.base import BaseStrategy


class SimpleStrategyEngine(BaseStrategy):
    """
    Simple rule-based multi-strategy engine
    NO ML, NO black boxes - just clear IF/ELSE rules
    """

    def __init__(self, parameters: Dict[str, Any] = None):
        super().__init__(name="SimpleStrategyEngine", parameters=parameters)
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

        # Available strategies mapping
        self.strategy_mapping = {
            'gap_go': 'strategies.gap_go_strategy',
            'daily_plays': 'strategies.daily_plays_strategy',
            'macdv_smallcaps': 'strategies.macdv_smallcaps_strategy',
            'first_day_bounce': 'strategies.first_day_bounce_strategy',
            'red_to_green': 'strategies.red_to_green_strategy',
            'gap_crap_reversal': 'strategies.gap_crap_reversal_strategy',
            'ascending_triangle': 'strategies.ascending_triangle_strategy',
            'bull_flag': 'strategies.bull_flag_strategy',
            'falling_wedge': 'strategies.falling_wedge_strategy',
            'catalyst_momentum': 'strategies.catalyst_momentum_strategy',
            'explosive_volume': 'strategies.explosive_volume_strategy'
        }

        # Load simple configuration - NO ML CONFIGS
        self.max_strategies_per_ticker = self.config.getint('SIMPLE_STRATEGY', 'max_strategies_per_ticker', fallback=2)
        self.min_gap_for_gap_go = self.config.getfloat('SIMPLE_STRATEGY', 'min_gap_for_gap_go', fallback=8.0)
        self.min_volume_ratio = self.config.getfloat('SIMPLE_STRATEGY', 'min_volume_ratio', fallback=1.5)
        self.max_smallcap_price = self.config.getfloat('SIMPLE_STRATEGY', 'max_smallcap_price', fallback=15.0)
        self.news_volume_threshold = self.config.getfloat('SIMPLE_STRATEGY', 'news_volume_threshold', fallback=3.0)

        self.logger.info(f"✅ Simple Strategy Engine initialized - ZERO ML")
        self.logger.info(f"📊 Max strategies per ticker: {self.max_strategies_per_ticker}")
        self.logger.info(f"💰 Smallcap threshold: ${self.max_smallcap_price}")
        self.logger.info(f"🎯 Gap Go min gap: {self.min_gap_for_gap_go}%")
        self.logger.info(f"📢 News volume threshold: {self.news_volume_threshold}x")

    # Abstract methods implementation
    async def _analyze_bar(self, symbol: str, bar: MarketData) -> List[Signal]:
        """Implementation of abstract method - use analyze method"""
        return await self.analyze(symbol, bar)

    def should_exit(self, symbol: str, position: 'Position', current_price: float) -> bool:
        """Simple exit logic - let strategies handle their own exits"""
        return False  # Let individual strategies handle exits

    def on_position_update(self, symbol: str, position: 'Position'):
        """Handle position updates - minimal implementation"""
        self.logger.debug(f"📊 Position update for {symbol}: {position.quantity} shares")

    async def initialize(self, event_bus=None):
        """Initialize the strategy engine"""
        self.event_bus = event_bus
        self.logger.info("🚀 Simple Strategy Engine ready - NO ML DEPENDENCIES")
        return True

    async def analyze(self, symbol: str, data: MarketData) -> List[Signal]:
        """
        Main analysis - pure rule-based strategy selection
        """
        try:
            # Get symbol context
            context = self._get_symbol_context(symbol, data)

            # Select strategies using SIMPLE RULES
            selected_strategies = self._rule_based_selection(symbol, context)

            if not selected_strategies:
                self.logger.debug(f"⚪ {symbol}: No strategies selected")
                return []

            self.logger.info(f"🎯 {symbol}: RULE-BASED selection: {selected_strategies}")
            self._log_selection_reason(symbol, context, selected_strategies)

            # Execute selected strategies
            all_signals = []
            for strategy_name in selected_strategies:
                try:
                    strategy = await self._get_strategy_instance(strategy_name)
                    if strategy:
                        signals = await strategy.analyze(symbol, data)
                        if signals:
                            all_signals.extend(signals)
                            self.logger.info(f"✅ {symbol}: {strategy_name} -> {len(signals)} signals")
                except Exception as e:
                    self.logger.error(f"❌ {symbol}: {strategy_name} failed: {e}")

            return all_signals

        except Exception as e:
            self.logger.error(f"❌ Error analyzing {symbol}: {e}")
            return []

    def _get_symbol_context(self, symbol: str, data: MarketData) -> Dict[str, Any]:
        """Extract symbol context - TRANSPARENT DATA"""
        try:
            current_price = data.close
            prev_close = getattr(data, 'prev_close', current_price)
            volume = getattr(data, 'volume', 0)
            avg_volume = getattr(data, 'avg_volume', volume)

            # Calculate key metrics - SIMPLE MATH
            gap_percent = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
            volume_ratio = (volume / avg_volume) if avg_volume > 0 else 1.0

            # Market time context
            now = datetime.now()
            market_hour = now.hour
            is_market_hours = 9 <= market_hour <= 16
            is_premarket = 4 <= market_hour < 9

            # Simple news detection - NO ML
            has_news = volume_ratio >= self.news_volume_threshold or abs(gap_percent) >= 5.0

            context = {
                'symbol': symbol,
                'current_price': current_price,
                'prev_close': prev_close,
                'gap_percent': gap_percent,
                'volume_ratio': volume_ratio,
                'market_hour': market_hour,
                'is_market_hours': is_market_hours,
                'is_premarket': is_premarket,
                'has_news': has_news,
                'is_smallcap': current_price <= self.max_smallcap_price,
                'volume': volume,
                'avg_volume': avg_volume
            }

            return context

        except Exception as e:
            self.logger.error(f"Error getting context for {symbol}: {e}")
            return {}

    def _rule_based_selection(self, symbol: str, context: Dict[str, Any]) -> List[str]:
        """
        SIMPLE RULE-BASED STRATEGY SELECTION
        Clear IF/ELSE logic - NO BLACK BOXES
        """
        try:
            selected = []

            gap_pct = context.get('gap_percent', 0)
            vol_ratio = context.get('volume_ratio', 1.0)
            price = context.get('current_price', 0)
            has_news = context.get('has_news', False)
            is_smallcap = context.get('is_smallcap', True)
            hour = context.get('market_hour', 10)

            # RULE 1: Gap Go - Big gaps with volume
            if abs(gap_pct) >= self.min_gap_for_gap_go and vol_ratio >= 2.0:
                selected.append('gap_go')

            # RULE 2: Daily Plays - News + High Volume
            elif has_news and vol_ratio >= self.news_volume_threshold and is_smallcap:
                selected.append('daily_plays')

            # RULE 3: MACDV - Technical without major news
            elif (abs(gap_pct) <= 5.0 and vol_ratio >= self.min_volume_ratio
                  and not has_news and 9 <= hour <= 15):
                selected.append('macdv_smallcaps')

            # RULE 4: Reversal - Gap down scenarios
            elif gap_pct <= -5.0 and vol_ratio >= 2.0 and is_smallcap:
                selected.append('first_day_bounce')
                if gap_pct <= -8.0:
                    selected.append('gap_crap_reversal')

            # RULE 5: Volume explosion
            elif vol_ratio >= 5.0 and is_smallcap:
                selected.append('explosive_volume')

            # RULE 6: Pattern recognition - calm moves
            elif vol_ratio >= 1.8 and is_smallcap and abs(gap_pct) <= 3.0 and 9 <= hour <= 15:
                selected.append('ascending_triangle')

            # FALLBACK: Conservative default
            if not selected and is_smallcap and vol_ratio >= 1.2:
                selected.append('macdv_smallcaps')

            # Limit strategies
            if len(selected) > self.max_strategies_per_ticker:
                selected = selected[:self.max_strategies_per_ticker]

            return selected

        except Exception as e:
            self.logger.error(f"Error in rule selection for {symbol}: {e}")
            return ['macdv_smallcaps']

    def _log_selection_reason(self, symbol: str, context: Dict[str, Any], strategies: List[str]):
        """Log WHY strategies were selected - FULL TRANSPARENCY"""
        gap = context.get('gap_percent', 0)
        vol = context.get('volume_ratio', 1.0)
        price = context.get('current_price', 0)
        news = context.get('has_news', False)

        reason = f"📋 {symbol} Selection Logic:"
        reason += f"\n   💰 Price: ${price:.2f} (smallcap: {price <= self.max_smallcap_price})"
        reason += f"\n   📊 Gap: {gap:.1f}% | Volume: {vol:.1f}x | News: {news}"
        reason += f"\n   ⏰ Hour: {context.get('market_hour', 0)}"
        reason += f"\n   ✅ Selected: {strategies}"

        self.logger.info(reason)

    async def _get_strategy_instance(self, strategy_name: str) -> Optional[IStrategy]:
        """Get strategy instance with config parameters"""
        try:
            # Return cached
            if strategy_name in self.strategy_instances:
                return self.strategy_instances[strategy_name]

            # Load strategy class
            if strategy_name not in self.strategy_mapping:
                self.logger.error(f"Unknown strategy: {strategy_name}")
                return None

            module_path = self.strategy_mapping[strategy_name]
            module_name, class_name_part = module_path.rsplit('.', 1)

            # Convert to class name
            class_name = ''.join(word.capitalize() for word in class_name_part.split('_'))
            if not class_name.endswith('Strategy'):
                class_name += 'Strategy'

            # Import
            module = __import__(module_name, fromlist=[class_name])
            strategy_class = getattr(module, class_name)

            # Load config parameters
            config_section = f"{strategy_name.upper()}_STRATEGY"
            params = {}
            if self.config.has_section(config_section):
                params = dict(self.config.items(config_section))
                # Convert numeric values
                for key, value in params.items():
                    try:
                        if '.' in str(value):
                            params[key] = float(value)
                        elif str(value).isdigit():
                            params[key] = int(value)
                    except (ValueError, AttributeError):
                        pass

            # Create instance
            strategy = strategy_class(params)

            # Initialize
            if hasattr(strategy, 'initialize'):
                await strategy.initialize(self.event_bus)

            # Cache
            self.strategy_instances[strategy_name] = strategy

            self.logger.info(f"✅ Loaded {strategy_name} with {len(params)} config params")
            return strategy

        except Exception as e:
            self.logger.error(f"❌ Failed loading {strategy_name}: {e}")
            return None

    # IStrategy interface
    def get_name(self) -> str:
        return "SimpleStrategyEngine"

    def get_description(self) -> str:
        return "Rule-based strategy engine - ZERO ML dependencies"

    # PipelineStage interface
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process pipeline data"""
        try:
            symbol = data.get('symbol')
            market_data = data.get('market_data')

            if symbol and market_data:
                signals = await self.analyze(symbol, market_data)
                data['signals'] = signals
                data['strategy_engine'] = 'SimpleStrategyEngine'

            return data

        except Exception as e:
            self.logger.error(f"Pipeline processing error: {e}")
            return data

    def clear_cache(self):
        """Clear strategy cache"""
        self.strategy_instances.clear()
        self.logger.info("🧹 Strategy cache cleared")


# Factory function
def create_simple_strategy_engine(parameters: Dict[str, Any] = None) -> SimpleStrategyEngine:
    """Create Simple Strategy Engine - NO ML"""
    return SimpleStrategyEngine(parameters)


if __name__ == "__main__":
    print("🧪 Simple Strategy Engine Test - NO ML")
    print("=" * 50)

    engine = create_simple_strategy_engine()
    print(f"✅ Engine: {engine.get_name()}")
    print(f"📝 Description: {engine.get_description()}")
    print("=" * 50)
    print("🎉 Ready - 100% predictable, 100% controllable!")