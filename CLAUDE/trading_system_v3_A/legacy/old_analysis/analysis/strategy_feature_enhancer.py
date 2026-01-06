#!/usr/bin/env python3
"""
Strategy Feature Enhancer
Integrates market condition features into existing ML pipeline
Zero breaking changes - only adds features
"""

import pandas as pd
from typing import Dict, Any, Optional
import logging
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from analysis.market_condition_analyzer import analyze_market_conditions, MarketConditionAnalyzer


class StrategyFeatureEnhancer:
    """
    Enhances existing strategy features with universal market condition analysis
    Designed for zero breaking changes - only adds features
    """
    
    def __init__(self, timeframe_minutes=1):
        self.logger = logging.getLogger(__name__)
        # Initialize market analyzer with timeframe-aware parameters
        self.market_analyzer = MarketConditionAnalyzer(timeframe_minutes=timeframe_minutes)
        
    def enhance_strategy_features(self, 
                                existing_features: Dict[str, Any],
                                market_data: pd.DataFrame,
                                strategy_name: str,
                                symbol: str = None,
                                previous_day_data: pd.DataFrame = None) -> Dict[str, Any]:
        """
        Add market condition features to existing strategy features
        
        Args:
            existing_features: Current features from strategy
            market_data: OHLCV data for analysis
            strategy_name: Name of strategy (macdv, breakout, etc.)
            symbol: Symbol being analyzed
            
        Returns:
            Enhanced features dictionary with original + market condition features
        """
        
        try:
            # Get market condition features using instance analyzer with previous day support
            market_features = self.market_analyzer.analyze_market_conditions(
                data=market_data,
                symbol=symbol,
                previous_day_data=previous_day_data
            )
            
            # Create enhanced features (original + new)
            enhanced_features = existing_features.copy()
            
            # Add market condition features with prefix to avoid conflicts
            for key, value in market_features.items():
                enhanced_key = f"market_condition_{key}"
                enhanced_features[enhanced_key] = value
            
            # Add strategy-specific interpretations
            enhanced_features.update(
                self._get_strategy_specific_features(
                    market_features, strategy_name, existing_features
                )
            )
            
            self.logger.debug(f"Enhanced {strategy_name} features for {symbol}: "
                            f"added {len(market_features)} market condition features")
            
            return enhanced_features
            
        except Exception as e:
            self.logger.error(f"Error enhancing features for {strategy_name}/{symbol}: {e}")
            # Return original features unchanged if enhancement fails
            return existing_features
    
    def _get_strategy_specific_features(self, 
                                      market_features: Dict[str, float],
                                      strategy_name: str,
                                      existing_features: Dict[str, Any]) -> Dict[str, float]:
        """
        Create strategy-specific interpretations of market conditions
        """
        
        strategy_features = {}
        
        # Universal features for all strategies
        strategy_features.update({
            'entry_quality_score': market_features.get('entry_timing_score', 0.5),
            'overbought_penalty': market_features.get('overbought_risk', 0.0),
            'timing_confidence_multiplier': self._calculate_timing_multiplier(market_features)
        })
        
        # Strategy-specific features
        if strategy_name.lower() in ['macdv', 'macdv_smallcaps']:
            strategy_features.update(self._get_macdv_specific_features(market_features))
        elif strategy_name.lower() in ['breakout', 'volume_breakout']:
            strategy_features.update(self._get_breakout_specific_features(market_features))
        elif strategy_name.lower() in ['orb', 'opening_range']:
            strategy_features.update(self._get_orb_specific_features(market_features))
        
        return strategy_features
    
    def _get_macdv_specific_features(self, market_features: Dict[str, float]) -> Dict[str, float]:
        """MACDV-specific market condition features"""
        
        macd_position = market_features.get('macd_position', 0.5)
        rsi_risk = market_features.get('rsi_risk', 0.3)
        
        return {
            'macdv_ideal_entry_zone': 1.0 if macd_position < 0.3 else 0.5 if macd_position < 0.6 else 0.0,
            'macdv_overbought_warning': 1.0 if (macd_position > 0.7 and rsi_risk > 0.5) else 0.0,
            'macdv_pullback_opportunity': 1.0 if (macd_position < 0.4 and rsi_risk < 0.3) else 0.0
        }
    
    def _get_breakout_specific_features(self, market_features: Dict[str, float]) -> Dict[str, float]:
        """Breakout-specific market condition features"""
        
        resistance_risk = market_features.get('resistance_proximity_risk', 0.3)
        volume_quality = market_features.get('volume_quality', 0.5)
        rsi_risk = market_features.get('rsi_risk', 0.3)
        
        return {
            'breakout_resistance_clear': 1.0 if resistance_risk < 0.3 else 0.0,
            'breakout_volume_sustainable': 1.0 if volume_quality > 0.7 else 0.5 if volume_quality > 0.4 else 0.0,
            'breakout_not_exhausted': 1.0 if rsi_risk < 0.6 else 0.5 if rsi_risk < 0.8 else 0.0
        }
    
    def _get_orb_specific_features(self, market_features: Dict[str, float]) -> Dict[str, float]:
        """ORB-specific market condition features"""
        
        volume_quality = market_features.get('volume_quality', 0.5)
        timing_quality = market_features.get('timing_quality', 0.5)
        
        return {
            'orb_early_strength': 1.0 if (volume_quality > 0.6 and timing_quality > 0.6) else 0.0,
            'orb_sustainable_move': 1.0 if volume_quality > 0.7 else 0.0
        }
    
    def _calculate_timing_multiplier(self, market_features: Dict[str, float]) -> float:
        """
        Calculate a multiplier for signal confidence based on market timing
        1.0 = neutral, >1.0 = boost confidence, <1.0 = reduce confidence
        """
        
        timing_quality = market_features.get('timing_quality', 0.5)
        overbought_risk = market_features.get('overbought_risk', 0.3)
        
        # Base multiplier from timing quality
        base_multiplier = 0.5 + timing_quality  # 0.5 to 1.5 range
        
        # Penalty for overbought conditions
        overbought_penalty = overbought_risk * 0.3  # Up to 0.3 penalty
        
        # Final multiplier
        multiplier = base_multiplier - overbought_penalty
        
        # Clamp to reasonable range
        return max(0.2, min(1.5, multiplier))
    
    def create_ml_training_features(self, 
                                  strategy_features: Dict[str, Any],
                                  market_data: pd.DataFrame,
                                  strategy_name: str,
                                  symbol: str,
                                  trade_outcome: Optional[float] = None) -> Dict[str, Any]:
        """
        Create comprehensive feature set for ML training
        Includes both strategy features and market condition features
        
        Args:
            strategy_features: Features from the trading strategy
            market_data: OHLCV data
            strategy_name: Strategy name
            symbol: Symbol being traded
            trade_outcome: Actual trade P&L (for training labels)
            
        Returns:
            Complete feature set for ML training
        """
        
        # Enhance with market conditions
        enhanced_features = self.enhance_strategy_features(
            strategy_features, market_data, strategy_name, symbol
        )
        
        # Add metadata for ML
        enhanced_features.update({
            'strategy_name': strategy_name,
            'symbol': symbol,
            'timestamp': pd.Timestamp.now().isoformat(),
            'data_bars_available': len(market_data)
        })
        
        # Add trade outcome if provided (for training)
        if trade_outcome is not None:
            enhanced_features['trade_outcome_pnl'] = trade_outcome
            enhanced_features['trade_outcome_success'] = 1.0 if trade_outcome > 0 else 0.0
        
        return enhanced_features


# Convenience functions for easy integration
def enhance_macdv_features(existing_features: Dict[str, Any],
                          market_data: pd.DataFrame,
                          symbol: str = None,
                          previous_day_data: pd.DataFrame = None) -> Dict[str, Any]:
    """Convenience function for MACDV strategy"""
    enhancer = StrategyFeatureEnhancer(timeframe_minutes=1)
    return enhancer.enhance_strategy_features(
        existing_features, market_data, 'macdv_smallcaps', symbol, previous_day_data
    )


def enhance_breakout_features(existing_features: Dict[str, Any],
                            market_data: pd.DataFrame,
                            symbol: str = None,
                            previous_day_data: pd.DataFrame = None) -> Dict[str, Any]:
    """Convenience function for breakout strategies"""
    enhancer = StrategyFeatureEnhancer(timeframe_minutes=1)
    return enhancer.enhance_strategy_features(
        existing_features, market_data, 'volume_breakout', symbol, previous_day_data
    )


def enhance_orb_features(existing_features: Dict[str, Any],
                        market_data: pd.DataFrame,
                        symbol: str = None,
                        previous_day_data: pd.DataFrame = None) -> Dict[str, Any]:
    """Convenience function for ORB strategy"""
    enhancer = StrategyFeatureEnhancer(timeframe_minutes=1)
    return enhancer.enhance_strategy_features(
        existing_features, market_data, 'orb', symbol, previous_day_data
    )


def get_market_condition_summary(market_data: pd.DataFrame, symbol: str = None) -> str:
    """
    Get human-readable market condition summary
    Useful for logging and debugging
    """
    
    try:
        features = analyze_market_conditions(market_data, symbol)
        
        grade = chr(ord('A') + int(features.get('market_condition_grade_numeric', 2)))
        timing_score = features.get('overall_entry_timing_quality', 0.5)
        overbought_risk = features.get('overbought_risk_composite', 0.3)
        macd_percentile = features.get('macd_percentile_20d', 50)
        
        return (f"Market Condition Grade: {grade} | "
                f"Timing: {timing_score:.2f} | "
                f"Overbought Risk: {overbought_risk:.2f} | "
                f"MACD Percentile: {macd_percentile:.0f}")
                
    except Exception as e:
        return f"Market condition analysis failed: {e}"