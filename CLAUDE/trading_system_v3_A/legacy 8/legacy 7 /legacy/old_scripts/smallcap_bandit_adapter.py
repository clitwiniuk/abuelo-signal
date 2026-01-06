# strategies/smallcap_bandit_adapter.py
"""
Smallcap Contextual Bandit Adapter
Extends existing ContextualBandit with smallcap-specific features and optimizations
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

from .ml_strategy_selector import ContextualBandit, TickerContext, StrategyPerformance

# Import smallcap components if available
try:
    from scanner.smallcap.smallcap_context import SmallcapContext
    from scanner.smallcap.catalyst_analyzer import CatalystInfo
    SMALLCAP_IMPORTS_AVAILABLE = True
except ImportError:
    SMALLCAP_IMPORTS_AVAILABLE = False
    SmallcapContext = None
    CatalystInfo = None

logger = logging.getLogger(__name__)

def calculate_pmh_resistance_strength(context: Any) -> float:
    """
    Calculate PMH resistance strength based on % gain from previous close to PMH

    Returns:
        0.0-1.0 where:
        - 0.0-0.3: PMH <50% gain (weak resistance)
        - 0.3-0.7: PMH 50-80% gain (moderate resistance)
        - 0.7-1.0: PMH >80% gain (strong resistance, good for retrocesos)
    """
    try:
        # Try to get PMH data from context
        pmh_high = getattr(context, 'premarket_high', None)
        prev_close = getattr(context, 'previous_close', None)

        if pmh_high is None or prev_close is None or prev_close <= 0:
            # Fallback: estimate from gap and current price
            gap_pct = getattr(context, 'gap_percentage', 0.0)
            current_price = getattr(context, 'current_price', 0.0)

            if gap_pct <= 0 or current_price <= 0:
                return 0.0  # No gap data available

            # Estimate PMH as gap + some additional percentage (smallcaps often run beyond gap)
            estimated_pmh_gain = abs(gap_pct) * 1.2  # Assume PMH is 20% higher than gap
        else:
            # Calculate actual PMH gain percentage
            estimated_pmh_gain = (pmh_high - prev_close) / prev_close

        # Convert to resistance strength score (0.0-1.0)
        if estimated_pmh_gain >= 0.80:  # 80%+ gain = very strong resistance
            return min(1.0, 0.7 + (estimated_pmh_gain - 0.80) * 0.5)  # 0.7-1.0 range
        elif estimated_pmh_gain >= 0.50:  # 50-80% gain = moderate resistance
            return 0.3 + (estimated_pmh_gain - 0.50) * 1.33  # 0.3-0.7 range
        else:  # <50% gain = weak resistance
            return estimated_pmh_gain * 0.6  # 0.0-0.3 range

    except Exception as e:
        logger.warning(f"Error calculating PMH resistance strength: {e}")
        return 0.0  # Default to no resistance data

@dataclass
class SmallcapTickerContext(TickerContext):
    """
    Simplified TickerContext for smallcaps - extends existing TickerContext
    Enhanced to 12 key smallcap features (including HTB status and trend strength)
    """
    # Override with smallcap-specific features (12 total vs 18+) 
    gap_percentage: float = 0.0        # Most critical for smallcaps
    volume_ratio: float = 1.0          # Second most critical
    catalyst_strength: float = 0.5     # 0.0-1.0 normalized
    news_age_hours: float = 2.0        # Hours since news (lower is better)
    catalyst_type_score: float = 0.3   # 0.0-1.0 encoded catalyst type
    price_tier: float = 0.5           # 0.0-1.0 for $0.50-$15 range
    time_of_day: float = 0.5          # 0.0-1.0 market session progress
    momentum_score: float = 0.5        # Combined momentum indicator
    premarket_factor: float = 0.0      # 1.0 if premarket, 0.0 otherwise
    volume_spike_confirmed: float = 0.0 # 1.0 if volume spike confirmed, 0.0 otherwise
    htb_status: float = 0.0           # 1.0 if hard to borrow, 0.0 otherwise
    trend_strength: float = 0.5       # 0.0-1.0 trend momentum (from price_momentum)
    pmh_resistance_strength: float = 0.0  # 0.0-1.0 PMH resistance quality (>80% gain = strong)
    
    def to_feature_vector(self) -> np.ndarray:
        """Convert to 13-feature vector for smallcaps (enhanced with PMH resistance)"""
        return np.array([
            self.gap_percentage,
            self.volume_ratio,
            self.catalyst_strength,
            self.news_age_hours,
            self.catalyst_type_score,
            self.price_tier,
            self.time_of_day,
            self.momentum_score,
            self.premarket_factor,
            self.volume_spike_confirmed,
            self.htb_status,        # HTB status as binary feature
            self.trend_strength,    # Trend strength from price momentum
            self.pmh_resistance_strength  # NEW: PMH resistance quality (0.0-1.0)
        ])
    
    @classmethod
    def from_smallcap_context(cls, context: Any, catalyst: Any = None) -> 'SmallcapTickerContext':
        """Create from SmallcapContext and CatalystInfo"""
        
        if not SMALLCAP_IMPORTS_AVAILABLE:
            return cls._create_fallback_context(context)
        
        try:
            # Encode catalyst type (FDA > M&A > CONTRACT > EARNINGS > OTHER > TECHNICAL)
            catalyst_type_scores = {
                'FDA': 1.0, 'M&A': 0.9, 'CONTRACT': 0.8,
                'EARNINGS': 0.6, 'OTHER': 0.3, 'TECHNICAL': 0.1
            }
            catalyst_type_score = catalyst_type_scores.get(
                catalyst.catalyst_type if catalyst else 'TECHNICAL', 0.1
            )
            
            # Normalize catalyst strength (1-10 scale to 0-1)
            catalyst_strength = (catalyst.strength if catalyst else 5) / 10.0
            
            # Price tier for smallcaps ($0.50-$15 to 0-1)
            price_tier = min(max((context.current_price - 0.5) / 14.5, 0.0), 1.0)
            
            # Time of day (market session progress)
            current_time = datetime.now()
            if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 30):
                time_of_day = 0.0  # Premarket
                premarket_factor = 1.0
                minutes_since_930 = 0
            elif current_time.hour >= 16:
                time_of_day = 1.0  # Aftermarket
                premarket_factor = 0.0
                minutes_since_930 = 390  # Full session
            else:
                # Regular hours: 9:30 AM = 0.0, 4:00 PM = 1.0
                minutes_since_930 = (current_time.hour - 9) * 60 + (current_time.minute - 30)
                time_of_day = min(max(minutes_since_930 / 390, 0.0), 1.0)  # 390 minutes = 6.5 hours
                premarket_factor = 0.0
            
            # Momentum score (combination of gap and volume)
            momentum_score = min(
                (abs(context.gap_percentage) * 3 + min(context.premarket_volume_ratio / 5, 1.0)) / 2,
                1.0
            )
            
            # HTB status (1.0 if hard to borrow, 0.0 otherwise)
            htb_status_val = 1.0 if getattr(context, 'htb_status', False) else 0.0
            
            # Volume spike confirmation
            volume_spike_val = 1.0 if getattr(context, 'volume_spike_confirmed', False) else 0.0
            
            # News age (from catalyst)
            news_age = catalyst.age_hours if catalyst else 2.0

            # PMH resistance strength calculation
            pmh_resistance = calculate_pmh_resistance_strength(context)

            return cls(
                symbol=context.symbol,
                
                # Smallcap-specific features
                gap_percentage=context.gap_percentage,
                volume_ratio=context.premarket_volume_ratio,
                catalyst_strength=catalyst_strength,
                news_age_hours=news_age,
                catalyst_type_score=catalyst_type_score,
                price_tier=price_tier,
                time_of_day=time_of_day,
                momentum_score=momentum_score,
                premarket_factor=premarket_factor,
                volume_spike_confirmed=volume_spike_val,
                htb_status=htb_status_val,
                pmh_resistance_strength=pmh_resistance,

                # Required parent fields (simplified)
                current_price=context.current_price,
                avg_volume_10=context.avg_daily_volume,
                avg_volume_50=context.avg_daily_volume,
                volatility_10=0.2,  # Default moderate volatility
                volatility_50=0.2,
                price_change_1h=context.gap_percentage,  # Approximate
                price_change_4h=context.gap_percentage,  # Approximate  
                rsi_14=50.0,  # Default neutral RSI
                volume_ratio_current=context.premarket_volume_ratio,
                volume_spike_frequency=0.1,  # Default low frequency
                hour_of_day=current_time.hour + current_time.minute/60.0,
                minutes_from_open=int(minutes_since_930),
                is_first_hour=time_of_day < 0.2,  # First 20% of session
                is_last_hour=time_of_day > 0.8,   # Last 20% of session
                market_trend=0.0,  # Default neutral
                sector_performance=0.0,  # Default
                breakout_success_rate=0.5,  # Default
                mean_reversion_tendency=0.5  # Default
            )
            
        except Exception as e:
            logger.warning(f"Error creating SmallcapTickerContext: {e}")
            return cls._create_fallback_context(context)
    
    @classmethod
    def _create_fallback_context(cls, context: Any) -> 'SmallcapTickerContext':
        """Create fallback context when smallcap imports fail"""
        current_time = datetime.now()
        
        return cls(
            symbol=getattr(context, 'symbol', 'UNKNOWN'),
            gap_percentage=getattr(context, 'gap_percentage', getattr(context, 'price_momentum', 1.0) - 1.0),  # Use price_momentum as gap approximation
            volume_ratio=getattr(context, 'volume_ratio', getattr(context, 'volume_trend', 1.0)),
            catalyst_strength=0.5,
            news_age_hours=2.0,  # Default news age
            catalyst_type_score=0.3,
            price_tier=0.5,
            time_of_day=0.5,
            momentum_score=0.5,
            premarket_factor=0.0,
            volume_spike_confirmed=0.0,  # Default no volume spike
            htb_status=0.0,  # Default no HTB
            trend_strength=max(0.0, min(1.0, getattr(context, 'price_momentum', 1.0) - 0.5)),  # Convert price_momentum to 0-1 trend strength
            pmh_resistance_strength=calculate_pmh_resistance_strength(context),  # Calculate PMH resistance

            # Parent class defaults
            current_price=getattr(context, 'current_price', 5.0),
            avg_volume_10=100000,
            avg_volume_50=100000,
            volatility_10=0.2,
            volatility_50=0.2,
            price_change_1h=0.0,
            price_change_4h=0.0,
            rsi_14=50.0,
            volume_ratio_current=1.0,
            volume_spike_frequency=0.1,
            hour_of_day=current_time.hour + current_time.minute/60.0,
            minutes_from_open=120,  # Default 2 hours from open
            is_first_hour=False,
            is_last_hour=False,
            market_trend=0.0,
            sector_performance=0.0,
            breakout_success_rate=0.5,
            mean_reversion_tendency=0.5
        )

class SmallcapContextualBandit(ContextualBandit):
    """
    Smallcap-optimized Contextual Bandit
    Extends existing ContextualBandit with smallcap-specific strategies and features
    """
    
    def __init__(self, strategies: List[str] = None, alpha: float = 1.0):
        # Smallcap-specific strategies
        if strategies is None:
            strategies = [
                'gap_go',              # Morning gap plays
                'volume_breakout',     # Volume surge plays
                'daily_plays',         # Catalyst-driven plays
                'explosive_volume',    # High volume spikes
                'macdv_smallcaps',     # Momentum confirmation
                'first_day_bounce'     # First day bounce plays
            ]
        
        # Initialize parent with 13 features (enhanced with PMH resistance)
        super().__init__(strategies=strategies, feature_dim=13, alpha=alpha)
        
        self.logger = logging.getLogger(f"{__name__}.SmallcapContextualBandit")
        
        # Smallcap-specific configuration
        self.smallcap_config = {
            'min_trades_per_strategy': 2,     # Reduced para dar oportunidades más rápido
            'exploration_rate': 0.4,          # Mayor exploración para balancear estrategias
            'catalyst_bonus_weight': 1.3,     # Reducido para no sobre-favorecer
            'time_decay_factor': 0.8,         # Reduce importance over time
            'momentum_threshold': 0.6,        # Threshold for momentum strategies
            'diversity_bonus': 1.2,           # Bonus para estrategias menos usadas
        }
        
        # Override parent config
        self.min_trades_per_strategy = self.smallcap_config['min_trades_per_strategy']
        
        self.logger.info("SmallcapContextualBandit initialized")
        self.logger.info(f"   Strategies: {strategies}")
        self.logger.info(f"   Feature dimension: 13 (enhanced smallcaps)")
    
    def select_strategy(self, context: SmallcapTickerContext, 
                       available_strategies: List[str] = None) -> str:
        """
        Enhanced strategy selection with smallcap-specific logic
        Includes diversity bonus para balancear uso de estrategias
        """
        if available_strategies is None:
            available_strategies = self.strategies
        
        try:
            # Add smallcap-specific pre-filtering
            filtered_strategies = self._filter_strategies_by_context(context, available_strategies)
            
            if not filtered_strategies:
                # Fallback to base selection if no strategies pass filters
                return super().select_strategy(context, available_strategies)
            
            # Aplicar diversity bonus antes de selección
            selected = self._select_with_diversity_bonus(context, filtered_strategies)
            
            self.logger.info(f"Selected strategy for {context.symbol}: {selected}")
            self.logger.info(f"   Gap: {context.gap_percentage:.1%}, Volume: {context.volume_ratio:.1f}x")
            self.logger.info(f"   Catalyst: {context.catalyst_strength:.1f}, Type: {context.catalyst_type_score:.1f}")
            
            return selected
            
        except Exception as e:
            self.logger.error(f"Error in smallcap strategy selection: {e}")
            return available_strategies[0] if available_strategies else 'gap_go'
    
    def _filter_strategies_by_context(self, context: SmallcapTickerContext, 
                                    strategies: List[str]) -> List[str]:
        """Apply smallcap-specific filters before ML selection"""
        filtered = []
        
        for strategy in strategies:
            include = True
            
            # Strategy-specific filters
            if strategy == 'explosive_volume':
                # Only consider for very high volume
                if context.volume_ratio < 3.0:
                    include = False
                    
            elif strategy == 'daily_plays':
                # Reducir filtros para daily_plays - permitir más oportunidades
                if context.catalyst_strength < 0.2:  # Reducido de 0.4 a 0.2
                    include = False
                    
            elif strategy == 'gap_go':
                # Best for morning with good gaps
                if abs(context.gap_percentage) < 0.05:  # Less than 5% gap
                    include = False
                    
            elif strategy == 'volume_breakout':
                # Need decent volume ratio
                if context.volume_ratio < 1.5:
                    include = False
            
            # Time-based filters
            if context.time_of_day > 0.8:  # Late in day
                if strategy in ['gap_go', 'explosive_volume']:
                    include = False  # These work better early
            
            if include:
                filtered.append(strategy)
        
        # Ensure we always have at least one strategy
        if not filtered and strategies:
            filtered = [strategies[0]]
        
        return filtered
    
    def _select_with_diversity_bonus(self, context: SmallcapTickerContext, 
                                   strategies: List[str]) -> str:
        """
        Selección con bonus de diversidad para balancear uso de estrategias
        """
        try:
            # Contar uso reciente de cada estrategia
            strategy_counts = {}
            total_recent_uses = 0
            
            for strategy in strategies:
                if strategy in self.strategy_stats:
                    # Usar total_trades en lugar de num_selections
                    recent_count = min(self.strategy_stats[strategy].total_trades, 20)
                    strategy_counts[strategy] = recent_count
                    total_recent_uses += recent_count
                else:
                    strategy_counts[strategy] = 0
            
            # Si no hay uso previo, usar selección estándar
            if total_recent_uses == 0:
                return super().select_strategy(context, strategies)
            
            # Calcular bonus de diversidad inverso al uso
            max_uses = max(strategy_counts.values()) if strategy_counts else 1
            diversity_bonuses = {}
            
            for strategy in strategies:
                uses = strategy_counts[strategy]
                # Bonus más alto para estrategias menos usadas
                if max_uses > 0:
                    diversity_factor = (max_uses - uses) / max_uses
                    diversity_bonuses[strategy] = 1.0 + (diversity_factor * (self.smallcap_config['diversity_bonus'] - 1.0))
                else:
                    diversity_bonuses[strategy] = 1.0
            
            # Aplicar bonuses temporalmente para selección
            original_rewards = {}
            for strategy in strategies:
                if strategy in self.strategy_stats:
                    original_rewards[strategy] = self.strategy_stats[strategy].average_reward
                    # Aplicar diversity bonus
                    self.strategy_stats[strategy].average_reward *= diversity_bonuses[strategy]
            
            # Seleccionar con bonuses aplicados
            selected = super().select_strategy(context, strategies)
            
            # Restaurar rewards originales
            for strategy, original_reward in original_rewards.items():
                self.strategy_stats[strategy].average_reward = original_reward
            
            self.logger.info(f"   Diversity bonuses: {diversity_bonuses}")
            self.logger.info(f"   Strategy uses: {strategy_counts}")
            
            return selected
            
        except Exception as e:
            self.logger.error(f"Error in diversity selection: {e}")
            return super().select_strategy(context, strategies)
    
    def update_reward(self, strategy: str, context: SmallcapTickerContext, 
                     reward: float, trade_duration_hours: float = None):
        """
        Enhanced reward update with smallcap-specific adjustments
        """
        try:
            # Apply smallcap-specific reward adjustments
            adjusted_reward = self._adjust_reward_for_smallcap(
                reward, context, strategy, trade_duration_hours
            )
            
            # Use parent's update mechanism (it's called update_model)
            super().update_model(context, strategy, adjusted_reward)
            
            self.logger.info(f"Updated {strategy} reward: {reward:.2f} -> {adjusted_reward:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error updating smallcap reward: {e}")
    
    def _adjust_reward_for_smallcap(self, base_reward: float, context: SmallcapTickerContext,
                                  strategy: str, duration_hours: float = None) -> float:
        """Apply smallcap-specific reward adjustments"""
        
        adjusted_reward = base_reward
        
        # Catalyst bonus: reward strategies that work well with catalysts
        if context.catalyst_strength > 0.7 and strategy == 'daily_plays':
            adjusted_reward *= self.smallcap_config['catalyst_bonus_weight']
        
        # Time-based adjustments
        if duration_hours:
            # Bonus for quick profits (smallcaps should be fast)
            if duration_hours < 2.0 and base_reward > 0:
                adjusted_reward *= 1.2
            # Penalty for holding too long
            elif duration_hours > 6.0:
                adjusted_reward *= 0.8
        
        # Volume-momentum alignment bonus
        if strategy == 'volume_breakout' and context.volume_ratio > 5.0:
            adjusted_reward *= 1.1
        
        # Gap alignment bonus
        if strategy == 'gap_go' and abs(context.gap_percentage) > 0.15:
            adjusted_reward *= 1.1
        
        return adjusted_reward
    
    def get_smallcap_strategy_insights(self) -> Dict[str, Any]:
        """Get smallcap-specific insights about strategy performance"""
        insights = {
            'total_strategies': len(self.strategies),
            'feature_dimension': 13,
            'strategy_performance': {},
            'smallcap_config': self.smallcap_config
        }
        
        for strategy in self.strategies:
            if strategy in self.strategy_stats:
                stats = self.strategy_stats[strategy]
                insights['strategy_performance'][strategy] = {
                    'total_trades': stats.total_trades,
                    'win_rate': stats.win_rate,
                    'avg_reward': stats.avg_pnl,
                    'confidence_level': 'High' if stats.total_trades >= 10 else 'Learning'
                }
        
        return insights
    
    def format_performance_summary(self) -> str:
        """Format smallcap bandit performance for display"""
        insights = self.get_smallcap_strategy_insights()
        
        output = f"🧠 SMALLCAP CONTEXTUAL BANDIT:\n\n"
        output += f"Features: {insights['feature_dimension']} (enhanced for smallcaps)\n"
        output += f"Strategies: {insights['total_strategies']}\n\n"
        
        output += "📊 STRATEGY PERFORMANCE:\n"
        for strategy, perf in insights['strategy_performance'].items():
            confidence = perf['confidence_level']
            icon = "✅" if confidence == "High" else "🔄"
            
            output += f"   {icon} {strategy}:\n"
            output += f"      Trades: {perf['total_trades']} | Win Rate: {perf['win_rate']:.1%}\n"
            output += f"      Avg Reward: {perf['avg_reward']:.2f} | Status: {confidence}\n\n"
        
        return output

# Factory function
def create_smallcap_bandit(strategies: List[str] = None) -> SmallcapContextualBandit:
    """Create SmallcapContextualBandit instance"""
    return SmallcapContextualBandit(strategies)