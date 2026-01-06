#!/usr/bin/env python3
"""
Earnings Enhanced Engine - Wrapper addon for earnings intelligence
Adds earnings context WITHOUT modifying core hybrid engine logic
"""

import logging
from typing import Optional
from dataclasses import dataclass

from core.hybrid_volume_engine import HybridVolumeEngine, VolumeDecision
from core.ml_volume_engine import MarketContext
from core.earnings_context_provider import earnings_context_provider, EarningsContext

@dataclass
class EnhancedVolumeDecision:
    """Extended volume decision with earnings context"""
    original_decision: VolumeDecision
    earnings_context: Optional[EarningsContext]
    final_requirement: float
    earnings_adjustment: float
    earnings_reasoning: str
    is_earnings_enhanced: bool

class EarningsEnhancedEngine:
    """
    Wrapper around HybridVolumeEngine that adds earnings intelligence
    WITHOUT modifying core engine logic
    """
    
    def __init__(self, hybrid_engine: Optional[HybridVolumeEngine] = None):
        self.hybrid_engine = hybrid_engine or HybridVolumeEngine()
        self.logger = logging.getLogger(__name__)
        
        # Earnings adjustment multipliers (conservative rules)
        self.earnings_multipliers = {
            'POST_EARNINGS_MISS': 2.2,          # Very conservative
            'POST_EARNINGS_SURPRISE': 1.8,      # Cautious (may be pump)
            'PRE_EARNINGS': 1.3,                # Moderate uncertainty
            'POST_EARNINGS_BEAT': 0.95,         # Slightly permissive
            'NORMAL': 1.0                       # No adjustment
        }
    
    def predict_volume_requirement(self, strategy: str, context: MarketContext) -> VolumeDecision:
        """
        Original method - unchanged behavior
        Maintains full compatibility with existing system
        """
        return self.hybrid_engine.predict_volume_requirement(strategy, context)
    
    async def predict_with_earnings_context(self, strategy: str, context: MarketContext, symbol: str) -> EnhancedVolumeDecision:
        """
        NEW METHOD: Enhanced prediction with earnings context
        This is an ADDITION, not a replacement
        """
        
        # Get original decision from unchanged hybrid engine
        original_decision = self.hybrid_engine.predict_volume_requirement(strategy, context)
        
        try:
            # Get earnings context (Scanner-First approach)
            earnings_context = await earnings_context_provider.get_earnings_context(symbol)
            
            if not earnings_context or earnings_context.confidence < 0.5:
                # No reliable earnings data - return original decision
                return EnhancedVolumeDecision(
                    original_decision=original_decision,
                    earnings_context=earnings_context,
                    final_requirement=original_decision.requirement,
                    earnings_adjustment=1.0,
                    earnings_reasoning="no earnings data",
                    is_earnings_enhanced=False
                )
            
            # Apply earnings adjustments as overlay
            earnings_multiplier = self._get_earnings_multiplier(earnings_context, context)
            final_requirement = original_decision.requirement * earnings_multiplier
            
            # Generate earnings reasoning
            earnings_reasoning = self._generate_earnings_reasoning(earnings_context, earnings_multiplier)
            
            return EnhancedVolumeDecision(
                original_decision=original_decision,
                earnings_context=earnings_context,
                final_requirement=final_requirement,
                earnings_adjustment=earnings_multiplier,
                earnings_reasoning=earnings_reasoning,
                is_earnings_enhanced=True
            )
            
        except Exception as e:
            self.logger.error(f"Error in earnings enhancement for {symbol}: {e}")
            # Graceful fallback to original decision
            return EnhancedVolumeDecision(
                original_decision=original_decision,
                earnings_context=None,
                final_requirement=original_decision.requirement,
                earnings_adjustment=1.0,
                earnings_reasoning="earnings error fallback",
                is_earnings_enhanced=False
            )
    
    def _get_earnings_multiplier(self, earnings_context: EarningsContext, market_context: MarketContext) -> float:
        """Calculate earnings-based multiplier"""
        
        base_multiplier = self.earnings_multipliers.get(earnings_context.phase, 1.0)
        
        # Adjust based on specific conditions
        if earnings_context.phase == "POST_EARNINGS_MISS":
            # More conservative for major misses
            if earnings_context.surprise_percent and earnings_context.surprise_percent < -20:
                return base_multiplier * 1.2  # 2.64x total
            return base_multiplier
            
        elif earnings_context.phase == "POST_EARNINGS_SURPRISE":
            # Extra caution for penny stock "surprises"
            if market_context.market_cap < 50_000_000 and market_context.price_level < 2.0:
                return base_multiplier * 1.3  # 2.34x for penny pumps
            elif market_context.market_cap < 100_000_000:
                return base_multiplier * 1.1  # 1.98x for micro caps
            return base_multiplier * 0.8  # 1.44x for legitimate large surprises
            
        return base_multiplier
    
    def _generate_earnings_reasoning(self, earnings_context: EarningsContext, multiplier: float) -> str:
        """Generate human-readable earnings reasoning"""
        
        if earnings_context.phase == "POST_EARNINGS_MISS":
            severity = "major" if earnings_context.surprise_percent and earnings_context.surprise_percent < -20 else "minor"
            return f"{severity} earnings miss protection"
            
        elif earnings_context.phase == "POST_EARNINGS_SURPRISE":
            return "earnings surprise caution (potential pump)"
            
        elif earnings_context.phase == "PRE_EARNINGS":
            return "pre-earnings uncertainty"
            
        elif earnings_context.phase == "POST_EARNINGS_BEAT":
            return "earnings beat momentum"
            
        return "earnings context applied"
    
    # Proxy methods to maintain full compatibility
    def __getattr__(self, name):
        """Proxy all other methods to hybrid engine"""
        return getattr(self.hybrid_engine, name)

# Factory function for easy integration
def create_earnings_enhanced_engine() -> EarningsEnhancedEngine:
    """Create earnings enhanced engine with default hybrid engine"""
    return EarningsEnhancedEngine()

# Singleton for global use while maintaining compatibility
enhanced_engine = EarningsEnhancedEngine()