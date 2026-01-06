#!/usr/bin/env python3
"""
Universal Market Condition Analyzer
Provides timing and overbought/oversold features for ALL trading strategies
Zero breaking changes - only adds features for ML learning
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
import logging


@dataclass
class MarketConditionFeatures:
    """Universal market condition features for any strategy"""
    
    # MACD Position Analysis
    macd_percentile_20d: float  # 0-100, where 0=bottom, 100=top
    macd_percentile_50d: float  # Longer term position
    macd_signal_divergence: float  # Distance from signal line
    macd_momentum_direction: float  # -1 to 1, trend direction
    
    # RSI Overbought/Oversold Analysis
    rsi_overbought_risk: float  # 0-1, risk of reversal
    rsi_oversold_opportunity: float  # 0-1, potential for bounce
    rsi_trend_strength: float  # 0-1, trend persistence
    
    # Price Extension Analysis
    price_vs_sma20_extension: float  # % above/below SMA20
    price_vs_vwap_extension: float  # % above/below VWAP
    recent_high_distance: float  # % from recent high
    recent_low_distance: float  # % from recent low
    
    # Volume Quality Analysis
    volume_sustainability_score: float  # 0-1, can volume sustain move?
    volume_vs_avg_ratio: float  # Current vs average volume
    volume_trend_quality: float  # 0-1, volume pattern quality
    
    # Support/Resistance Analysis
    resistance_proximity_risk: float  # 0-1, risk of hitting resistance
    support_strength_score: float  # 0-1, strength of nearby support
    breakout_sustainability: float  # 0-1, if breakout, can it sustain?
    
    # Composite Scores
    overall_entry_timing_quality: float  # 0-1, overall entry attractiveness
    overbought_risk_composite: float  # 0-1, overall overbought risk
    market_condition_grade: str  # A, B, C, D, F for easy interpretation


class MarketConditionAnalyzer:
    """
    Universal analyzer for market conditions across all strategies
    """
    
    def __init__(self, timeframe_minutes=1):
        self.logger = logging.getLogger(__name__)
        
        # Adjust parameters based on timeframe for smallcaps trading
        self.timeframe_minutes = timeframe_minutes
        
        # RSI periods - balanced for smallcap intraday (reduce noise but stay responsive)
        self.rsi_period = int(45 / timeframe_minutes) if timeframe_minutes <= 5 else max(14, int(45 / timeframe_minutes))  # ~45min for 1min data
        
        # MACD periods - responsive for 15-20min smallcap trades  
        self.macd_fast = int(25 / timeframe_minutes) if timeframe_minutes <= 5 else max(12, int(25 / timeframe_minutes))  # ~25min
        self.macd_slow = int(50 / timeframe_minutes) if timeframe_minutes <= 5 else max(26, int(50 / timeframe_minutes)) # ~50min  
        self.macd_signal = int(12 / timeframe_minutes) if timeframe_minutes <= 5 else max(9, int(12 / timeframe_minutes)) # ~12min
        
        # SMA periods - short enough for smallcap moves
        self.sma_period = int(30 / timeframe_minutes) if timeframe_minutes <= 5 else max(20, int(30 / timeframe_minutes))  # ~30min for 1min data
        
        # Percentile lookback periods (keep in days)
        self.percentile_period_20d = int(20 * 390 / timeframe_minutes)  # 20 trading days
        self.percentile_period_50d = int(50 * 390 / timeframe_minutes)  # 50 trading days
        
        self.logger.info(f"Market analyzer initialized for {timeframe_minutes}min timeframe: "
                        f"RSI={self.rsi_period}, MACD={self.macd_fast}/{self.macd_slow}/{self.macd_signal}, "
                        f"SMA={self.sma_period}")
    
    def _prepare_extended_data(self, current_data: pd.DataFrame, previous_day_data: pd.DataFrame = None, symbol: str = None) -> pd.DataFrame:
        """
        Combine current session data with previous day data for complete analysis
        Ensures we have enough data for indicators even at market open (9:30 AM)
        """
        
        if previous_day_data is None or len(previous_day_data) == 0:
            self.logger.debug(f"No previous day data for {symbol}, using current data only: {len(current_data)} bars")
            return current_data.copy()
        
        try:
            # Ensure both dataframes have the same columns and datetime index
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            
            # Validate columns
            for df_name, df in [('current', current_data), ('previous', previous_day_data)]:
                missing_cols = [col for col in required_columns if col not in df.columns]
                if missing_cols:
                    self.logger.warning(f"{df_name} data missing columns {missing_cols} for {symbol}")
                    return current_data.copy()
            
            # Take last N bars from previous day (enough for our longest indicator)
            max_needed = max(self.rsi_period, self.macd_slow, self.sma_period, 100)  # Add buffer
            prev_bars_to_use = min(len(previous_day_data), max_needed)
            
            # Combine: previous day end + current day
            prev_subset = previous_day_data.tail(prev_bars_to_use).copy()
            combined_data = pd.concat([prev_subset, current_data], ignore_index=True)
            
            self.logger.debug(f"Extended data for {symbol}: {len(prev_subset)} previous + {len(current_data)} current = {len(combined_data)} total bars")
            
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error preparing extended data for {symbol}: {e}")
            return current_data.copy()
        
    def analyze_market_conditions(self, 
                                 data: pd.DataFrame,
                                 symbol: str = None,
                                 previous_day_data: pd.DataFrame = None) -> MarketConditionFeatures:
        """
        Analyze current market conditions for any symbol/strategy
        
        Args:
            data: OHLCV data for current session
            symbol: Symbol name for logging
            previous_day_data: Optional previous day data to extend analysis
            
        Returns:
            MarketConditionFeatures with all timing indicators
        """
        
        # Try to get sufficient data by combining current + previous day
        extended_data = self._prepare_extended_data(data, previous_day_data, symbol)
        
        if len(extended_data) < max(self.rsi_period, self.macd_slow, self.sma_period):
            self.logger.warning(f"Insufficient data for {symbol}: {len(extended_data)} bars, need {max(self.rsi_period, self.macd_slow, self.sma_period)}")
            return self._get_default_features()
            
        try:
            # Calculate all technical indicators using extended data
            macd_features = self._analyze_macd_position(extended_data)
            rsi_features = self._analyze_rsi_conditions(extended_data)
            price_features = self._analyze_price_extension(extended_data)
            volume_features = self._analyze_volume_quality(extended_data)
            support_resistance = self._analyze_support_resistance(extended_data)
            
            # Calculate composite scores
            composite_scores = self._calculate_composite_scores(
                macd_features, rsi_features, price_features, 
                volume_features, support_resistance
            )
            
            # Combine all features
            features = MarketConditionFeatures(
                **macd_features,
                **rsi_features,
                **price_features,
                **volume_features,
                **support_resistance,
                **composite_scores
            )
            
            return features
            
        except Exception as e:
            self.logger.error(f"Error analyzing market conditions for {symbol}: {e}")
            return self._get_default_features()
    
    def _analyze_macd_position(self, data: pd.DataFrame) -> Dict[str, float]:
        """Analyze MACD position and timing"""
        
        # Calculate MACD with adjusted periods
        close = data['close']
        ema_fast = close.ewm(span=self.macd_fast).mean()
        ema_slow = close.ewm(span=self.macd_slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal).mean()
        
        # Current values
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        
        # Position analysis with adjusted lookback periods
        lookback_20d = min(len(macd_line), self.percentile_period_20d)
        lookback_50d = min(len(macd_line), self.percentile_period_50d)
        macd_20d = macd_line.tail(lookback_20d)
        macd_50d = macd_line.tail(lookback_50d)
        
        percentile_20d = self._calculate_percentile_position(current_macd, macd_20d)
        percentile_50d = self._calculate_percentile_position(current_macd, macd_50d)
        
        # Signal divergence
        signal_divergence = abs(current_macd - current_signal) / abs(current_signal) if current_signal != 0 else 0
        signal_divergence = min(signal_divergence, 2.0)  # Cap at 2.0
        
        # Momentum direction
        macd_change = macd_line.diff().tail(5).mean()
        momentum_direction = np.tanh(macd_change * 100)  # -1 to 1
        
        return {
            'macd_percentile_20d': percentile_20d,
            'macd_percentile_50d': percentile_50d,
            'macd_signal_divergence': signal_divergence,
            'macd_momentum_direction': momentum_direction
        }
    
    def _analyze_rsi_conditions(self, data: pd.DataFrame) -> Dict[str, float]:
        """Analyze RSI overbought/oversold conditions"""
        
        # Calculate RSI with adjusted period
        close = data['close']
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        
        # Overbought risk (higher RSI = higher risk)
        if current_rsi > 70:
            overbought_risk = min((current_rsi - 70) / 30, 1.0)
        else:
            overbought_risk = 0.0
        
        # Oversold opportunity (lower RSI = higher opportunity)
        if current_rsi < 30:
            oversold_opportunity = min((30 - current_rsi) / 30, 1.0)
        else:
            oversold_opportunity = 0.0
        
        # Trend strength (how persistent is the RSI trend)
        rsi_slope = rsi.tail(10).diff().mean()
        trend_strength = min(abs(rsi_slope) / 10, 1.0)
        
        return {
            'rsi_overbought_risk': overbought_risk,
            'rsi_oversold_opportunity': oversold_opportunity,
            'rsi_trend_strength': trend_strength
        }
    
    def _analyze_price_extension(self, data: pd.DataFrame) -> Dict[str, float]:
        """Analyze how extended price is from key levels"""
        
        close = data['close']
        current_price = close.iloc[-1]
        
        # SMA extension with adjusted period
        sma = close.rolling(self.sma_period).mean().iloc[-1]
        sma_extension = (current_price - sma) / sma
        
        # VWAP calculation (simplified)
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        volume = data['volume']
        vwap = (typical_price * volume).rolling(self.sma_period).sum() / volume.rolling(self.sma_period).sum()
        current_vwap = vwap.iloc[-1]
        vwap_extension = (current_price - current_vwap) / current_vwap
        
        # Recent high/low analysis
        recent_high = data['high'].tail(20).max()
        recent_low = data['low'].tail(20).min()
        
        high_distance = (recent_high - current_price) / current_price
        low_distance = (current_price - recent_low) / current_price
        
        return {
            'price_vs_sma20_extension': sma_extension,
            'price_vs_vwap_extension': vwap_extension,
            'recent_high_distance': high_distance,
            'recent_low_distance': low_distance
        }
    
    def _analyze_volume_quality(self, data: pd.DataFrame) -> Dict[str, float]:
        """Analyze volume sustainability and quality"""
        
        volume = data['volume']
        current_volume = volume.iloc[-1]
        
        # Volume vs average
        avg_volume_20 = volume.tail(20).mean()
        volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0
        
        # Volume sustainability (can this volume level be maintained?)
        recent_volumes = volume.tail(5)
        volume_trend = recent_volumes.diff().mean()
        sustainability = 1.0 - min(abs(volume_trend) / current_volume, 1.0) if current_volume > 0 else 0.5
        
        # Volume pattern quality (consistent vs spiky)
        volume_std = volume.tail(20).std()
        volume_mean = volume.tail(20).mean()
        volume_cv = volume_std / volume_mean if volume_mean > 0 else 1.0
        quality = max(0, 1.0 - min(volume_cv, 2.0) / 2.0)  # Lower CV = higher quality
        
        return {
            'volume_sustainability_score': sustainability,
            'volume_vs_avg_ratio': volume_ratio,
            'volume_trend_quality': quality
        }
    
    def _analyze_support_resistance(self, data: pd.DataFrame) -> Dict[str, float]:
        """Analyze support/resistance levels"""
        
        high = data['high']
        low = data['low']
        close = data['close']
        current_price = close.iloc[-1]
        
        # Simple resistance (recent highs)
        recent_highs = high.tail(20)
        resistance_level = recent_highs.quantile(0.9)  # 90th percentile
        resistance_distance = (resistance_level - current_price) / current_price
        resistance_risk = max(0, 1.0 - resistance_distance * 10)  # Higher risk when closer
        
        # Simple support (recent lows)
        recent_lows = low.tail(20)
        support_level = recent_lows.quantile(0.1)  # 10th percentile
        support_distance = (current_price - support_level) / current_price
        support_strength = min(support_distance * 10, 1.0)  # Stronger when further above
        
        # Breakout sustainability (if above recent range)
        recent_range_high = high.tail(10).max()
        is_breakout = current_price > recent_range_high
        breakout_sustainability = 0.8 if is_breakout else 0.5
        
        return {
            'resistance_proximity_risk': min(resistance_risk, 1.0),
            'support_strength_score': support_strength,
            'breakout_sustainability': breakout_sustainability
        }
    
    def _calculate_composite_scores(self, macd_features, rsi_features, 
                                   price_features, volume_features, 
                                   support_resistance) -> Dict[str, Union[float, str]]:
        """Calculate composite scores from all features"""
        
        # Overall entry timing quality (0-1)
        timing_components = [
            (1.0 - macd_features['macd_percentile_20d'] / 100) * 0.3,  # Lower MACD = better
            rsi_features['rsi_oversold_opportunity'] * 0.2,  # Oversold = opportunity
            (1.0 - rsi_features['rsi_overbought_risk']) * 0.2,  # Not overbought = better
            min(volume_features['volume_sustainability_score'], 1.0) * 0.15,
            min(support_resistance['support_strength_score'], 1.0) * 0.15
        ]
        timing_quality = sum(timing_components)
        
        # Overall overbought risk (0-1)
        overbought_components = [
            macd_features['macd_percentile_20d'] / 100 * 0.4,  # High MACD = risk
            rsi_features['rsi_overbought_risk'] * 0.4,  # High RSI = risk
            max(price_features['price_vs_sma20_extension'], 0) * 2 * 0.2  # Above SMA = risk
        ]
        overbought_risk = min(sum(overbought_components), 1.0)
        
        # Market condition grade
        if timing_quality >= 0.8:
            grade = 'A'
        elif timing_quality >= 0.6:
            grade = 'B'
        elif timing_quality >= 0.4:
            grade = 'C'
        elif timing_quality >= 0.2:
            grade = 'D'
        else:
            grade = 'F'
        
        return {
            'overall_entry_timing_quality': timing_quality,
            'overbought_risk_composite': overbought_risk,
            'market_condition_grade': grade
        }
    
    def _calculate_percentile_position(self, current_value: float, 
                                     historical_values: pd.Series) -> float:
        """Calculate percentile position (0-100) of current value in historical range"""
        
        if len(historical_values) < 2:
            return 50.0
            
        min_val = historical_values.min()
        max_val = historical_values.max()
        
        if max_val == min_val:
            return 50.0
            
        percentile = ((current_value - min_val) / (max_val - min_val)) * 100
        return max(0, min(100, percentile))
    
    def _get_default_features(self) -> MarketConditionFeatures:
        """Return default features when analysis fails"""
        
        return MarketConditionFeatures(
            macd_percentile_20d=50.0,
            macd_percentile_50d=50.0,
            macd_signal_divergence=0.5,
            macd_momentum_direction=0.0,
            rsi_overbought_risk=0.3,
            rsi_oversold_opportunity=0.3,
            rsi_trend_strength=0.5,
            price_vs_sma20_extension=0.0,
            price_vs_vwap_extension=0.0,
            recent_high_distance=0.05,
            recent_low_distance=0.05,
            volume_sustainability_score=0.5,
            volume_vs_avg_ratio=1.0,
            volume_trend_quality=0.5,
            resistance_proximity_risk=0.3,
            support_strength_score=0.5,
            breakout_sustainability=0.5,
            overall_entry_timing_quality=0.5,
            overbought_risk_composite=0.5,
            market_condition_grade='C'
        )
    
    def get_strategy_weighted_features(self, 
                                     features: MarketConditionFeatures,
                                     strategy_type: str) -> Dict[str, float]:
        """
        Get features weighted for specific strategy type
        Each strategy cares about different aspects more
        """
        
        base_features = {
            'timing_quality': features.overall_entry_timing_quality,
            'overbought_risk': features.overbought_risk_composite,
            'macd_position': features.macd_percentile_20d / 100,
            'rsi_risk': features.rsi_overbought_risk,
            'price_extension': abs(features.price_vs_sma20_extension),
            'volume_quality': features.volume_sustainability_score
        }
        
        # Strategy-specific weightings
        if strategy_type.lower() in ['macdv', 'macdv_smallcaps']:
            # MACDV cares most about MACD position and RSI
            return {
                'entry_timing_score': (
                    features.overall_entry_timing_quality * 0.4 +
                    (1.0 - features.macd_percentile_20d / 100) * 0.4 +
                    (1.0 - features.rsi_overbought_risk) * 0.2
                ),
                **base_features
            }
            
        elif strategy_type.lower() in ['breakout', 'volume_breakout']:
            # Breakout cares about price extension and resistance
            return {
                'entry_timing_score': (
                    features.overall_entry_timing_quality * 0.3 +
                    (1.0 - features.rsi_overbought_risk) * 0.3 +
                    (1.0 - features.resistance_proximity_risk) * 0.2 +
                    features.breakout_sustainability * 0.2
                ),
                **base_features
            }
            
        elif strategy_type.lower() in ['orb', 'opening_range']:
            # ORB cares about early market conditions
            return {
                'entry_timing_score': (
                    features.overall_entry_timing_quality * 0.4 +
                    features.volume_sustainability_score * 0.3 +
                    (1.0 - features.resistance_proximity_risk) * 0.3
                ),
                **base_features
            }
            
        else:
            # Default weighting for unknown strategies
            return {
                'entry_timing_score': features.overall_entry_timing_quality,
                **base_features
            }


# Convenience function for easy integration
def analyze_market_conditions(data: pd.DataFrame, 
                            symbol: str = None,
                            previous_day_data: pd.DataFrame = None,
                            strategy_type: str = None,
                            timeframe_minutes: int = 1) -> Dict[str, float]:
    """
    Convenience function to get market condition features with previous day support
    
    Returns:
        Dictionary with all features ready for ML pipeline
    """
    
    analyzer = MarketConditionAnalyzer(timeframe_minutes=timeframe_minutes)
    features = analyzer.analyze_market_conditions(data, symbol, previous_day_data)
    
    if strategy_type:
        return analyzer.get_strategy_weighted_features(features, strategy_type)
    else:
        # Return all features as flat dictionary
        return {
            'macd_percentile_20d': features.macd_percentile_20d,
            'macd_percentile_50d': features.macd_percentile_50d,
            'rsi_overbought_risk': features.rsi_overbought_risk,
            'rsi_oversold_opportunity': features.rsi_oversold_opportunity,
            'price_vs_sma20_extension': features.price_vs_sma20_extension,
            'volume_sustainability_score': features.volume_sustainability_score,
            'resistance_proximity_risk': features.resistance_proximity_risk,
            'overall_entry_timing_quality': features.overall_entry_timing_quality,
            'overbought_risk_composite': features.overbought_risk_composite,
            'market_condition_grade_numeric': ord(features.market_condition_grade) - ord('A')  # A=0, B=1, etc.
        }