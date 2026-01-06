"""
Advanced Setup Analyzer - Quality Trading System
===============================================

Comprehensive rule-based analysis that considers:
1. Historical consolidation and accumulation patterns
2. Premarket vs Regular hours movement timing
3. Volume profile and institutional interest
4. Historical resistance levels and room to run
5. Technical pattern quality assessment

NO ML/AI - Pure rule-based system to avoid biases.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import requests
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import learning system
try:
    from .learning_system import AutoLearningSystem, get_learned_weights
    LEARNING_SYSTEM_AVAILABLE = True
except ImportError:
    LEARNING_SYSTEM_AVAILABLE = False
    logger.warning("Learning system not available - using static weights")

@dataclass
class SetupAnalysis:
    """Complete setup analysis result"""
    ticker: str
    overall_score: int
    grade: str
    consolidation_quality: Dict
    timing_analysis: Dict
    volume_analysis: Dict
    technical_analysis: Dict
    risk_assessment: Dict
    recommendation: str
    key_factors: List[str]
    red_flags: List[str]

class AdvancedSetupAnalyzer:
    """
    Advanced setup analyzer combining all quality factors with learning capabilities
    """
    
    def __init__(self, learning_db_path: str = None):
        self.lookback_days = 120  # 4 months for consolidation analysis
        
        # Initialize learning system if available
        self.learning_system = None
        if LEARNING_SYSTEM_AVAILABLE and learning_db_path:
            try:
                self.learning_system = AutoLearningSystem(learning_db_path)
                logger.info("Learning system initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize learning system: {e}")
                self.learning_system = None
        
        # Default weights (will be overridden by learning system if available)
        self.default_weights = {
            'consolidation': 0.30,
            'timing': 0.25,
            'volume': 0.25,
            'news': 0.20
        }
        
    def get_comprehensive_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """Get comprehensive historical data"""
        try:
            stock = yf.Ticker(ticker)
            
            # Get 4 months of daily data for consolidation analysis
            hist = stock.history(period="4mo", interval="1d")
            
            if hist.empty:
                logger.warning(f"No historical data available for {ticker}")
                return None
                
            return hist
            
        except Exception as e:
            logger.error(f"Error getting comprehensive data for {ticker}: {e}")
            return None
    
    def get_intraday_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """Get today's intraday data"""
        try:
            stock = yf.Ticker(ticker)
            
            # Get today's 1-minute data
            intraday = stock.history(period="1d", interval="1m")
            
            if intraday.empty:
                # Fallback to recent daily data
                intraday = stock.history(period="2d", interval="1d")
            
            return intraday
            
        except Exception as e:
            logger.warning(f"Could not get intraday data for {ticker}: {e}")
            return None
    
    def analyze_consolidation_pattern(self, data: pd.DataFrame, current_price: float) -> Dict:
        """
        Analyze historical consolidation and accumulation patterns
        Key insight: Long consolidation = Strong setup potential
        """
        if data is None or len(data) < 30:
            return {'quality': 'insufficient_data', 'score': 0}
        
        closes = data['Close'].values
        highs = data['High'].values
        lows = data['Low'].values
        volumes = data['Volume'].values
        
        # Find consolidation periods (low volatility periods)
        consolidation_analysis = {}
        
        # Calculate rolling volatility (20-day windows)
        returns = np.diff(closes) / closes[:-1]
        rolling_volatility = []
        
        for i in range(19, len(returns)):
            window_vol = np.std(returns[i-19:i+1])
            rolling_volatility.append(window_vol)
        
        # Identify low volatility periods (bottom 30% of volatility)
        if len(rolling_volatility) > 30:
            vol_threshold = np.percentile(rolling_volatility, 30)
            low_vol_periods = np.array(rolling_volatility) <= vol_threshold
            
            # Count consecutive low volatility days
            consolidation_days = 0
            max_consolidation = 0
            
            for is_low_vol in low_vol_periods:
                if is_low_vol:
                    consolidation_days += 1
                    max_consolidation = max(max_consolidation, consolidation_days)
                else:
                    consolidation_days = 0
            
            # Convert to months
            consolidation_months = max_consolidation / 22  # ~22 trading days per month
            
        else:
            consolidation_months = 0
        
        # Find historical highs and accumulation zones
        historical_highs = []
        
        # Look for significant highs (local maxima with 10+ day separation)
        for i in range(10, len(highs) - 10):
            if (highs[i] == max(highs[i-10:i+11]) and 
                highs[i] > current_price * 1.1):  # At least 10% above current
                
                days_ago = len(highs) - i - 1
                historical_highs.append({
                    'price': highs[i],
                    'days_ago': days_ago,
                    'distance_pct': (highs[i] - current_price) / current_price * 100
                })
        
        # Sort by distance from current price
        historical_highs.sort(key=lambda x: x['distance_pct'])
        
        # Calculate consolidation quality score
        score = 0
        
        # Consolidation duration scoring (40 points max)
        if consolidation_months >= 4:
            score += 40
        elif consolidation_months >= 3:
            score += 30
        elif consolidation_months >= 2:
            score += 20
        elif consolidation_months >= 1:
            score += 10
        
        # Room to run scoring (40 points max)
        if historical_highs:
            nearest_high = historical_highs[0]
            distance = nearest_high['distance_pct']
            
            if distance >= 100:  # 100%+ room to run
                score += 40
            elif distance >= 80:  # 80%+ room to run
                score += 35
            elif distance >= 50:  # 50%+ room to run
                score += 25
            elif distance >= 30:  # 30%+ room to run
                score += 15
            elif distance >= 20:  # 20%+ room to run
                score += 10
        
        # Volume consistency during consolidation (20 points max)
        if len(volumes) >= 60:  # At least 3 months of data
            recent_vol = np.mean(volumes[-60:])  # Last 3 months
            older_vol = np.mean(volumes[-120:-60])  # Previous 3 months
            
            vol_ratio = recent_vol / older_vol if older_vol > 0 else 1
            
            # Steady or increasing volume during consolidation is good
            if 0.8 <= vol_ratio <= 1.5:  # Steady volume
                score += 20
            elif 1.5 < vol_ratio <= 2.5:  # Increasing volume (accumulation)
                score += 15
            elif vol_ratio > 2.5:  # Too much volume (maybe distribution)
                score += 5
        
        return {
            'consolidation_months': consolidation_months,
            'historical_highs': historical_highs[:3],  # Top 3
            'nearest_target': historical_highs[0] if historical_highs else None,
            'score': min(100, score),
            'quality': self._score_to_quality(score)
        }
    
    def analyze_timing_and_movement(self, ticker: str, current_price: float) -> Dict:
        """
        Analyze premarket vs regular hours movement timing
        Key insight: Moves exhausted in premarket are poor setups
        """
        intraday_data = self.get_intraday_data(ticker)
        historical_data = self.get_comprehensive_data(ticker)
        
        if historical_data is None or len(historical_data) < 2:
            return {'quality': 'insufficient_data', 'score': 0}
        
        # Get yesterday's close
        yesterday_close = historical_data['Close'].iloc[-2]
        
        # Calculate premarket gap
        premarket_gap = (current_price - yesterday_close) / yesterday_close
        
        timing_analysis = {
            'yesterday_close': yesterday_close,
            'current_price': current_price,
            'premarket_gap_pct': premarket_gap * 100
        }
        
        # If we have intraday data, calculate regular hours performance
        if intraday_data is not None and len(intraday_data) > 0:
            # Find market open (9:30 AM)
            market_open_price = None
            regular_hours_data = intraday_data.between_time('09:30', '16:00') if hasattr(intraday_data, 'between_time') else intraday_data
            
            if len(regular_hours_data) > 0:
                market_open_price = regular_hours_data['Open'].iloc[0]
                current_regular_price = regular_hours_data['Close'].iloc[-1]
                
                # Calculate regular hours movement
                if market_open_price:
                    regular_hours_move = (current_regular_price - market_open_price) / market_open_price
                    timing_analysis.update({
                        'market_open_price': market_open_price,
                        'regular_hours_move_pct': regular_hours_move * 100,
                        'premarket_vs_regular_ratio': abs(premarket_gap) / abs(regular_hours_move) if regular_hours_move != 0 else float('inf')
                    })
        
        # Score timing quality
        score = 0
        red_flags = []
        
        # RED FLAG: Too much movement in premarket
        if abs(premarket_gap) > 0.8:  # 80%+ move in premarket
            score -= 30
            red_flags.append("Excessive premarket movement - likely exhausted")
        
        # GOOD SIGN: Moderate premarket gap with room for regular hours expansion
        if 0.1 <= abs(premarket_gap) <= 0.5:  # 10-50% premarket gap
            score += 20
        
        # If we have regular hours data
        if 'regular_hours_move_pct' in timing_analysis:
            regular_move = timing_analysis['regular_hours_move_pct'] / 100
            premarket_move = timing_analysis['premarket_gap_pct'] / 100
            
            # GOOD SIGN: Continued strength in regular hours
            if regular_move > 0 and regular_move >= premarket_move * 0.3:
                score += 25
            
            # RED FLAG: Weakness in regular hours after strong premarket
            elif premarket_move > 0.2 and regular_move < 0:
                score -= 25
                red_flags.append("Losing momentum in regular hours")
        
        # Base score for having any gap
        if abs(premarket_gap) >= 0.1:
            score += 10
        
        timing_analysis.update({
            'score': max(0, min(100, score + 50)),  # Base 50 + adjustments
            'quality': self._score_to_quality(score + 50),
            'red_flags': red_flags
        })
        
        return timing_analysis
    
    def analyze_volume_profile(self, ticker: str, current_volume: int) -> Dict:
        """
        Advanced volume analysis for institutional interest detection
        """
        data = self.get_comprehensive_data(ticker)
        if data is None:
            return {'quality': 'insufficient_data', 'score': 0}
        
        volumes = data['Volume'].values
        closes = data['Close'].values
        
        # Calculate volume metrics
        avg_volume_20 = np.mean(volumes[-20:]) if len(volumes) >= 20 else current_volume
        avg_volume_60 = np.mean(volumes[-60:]) if len(volumes) >= 60 else current_volume
        
        volume_analysis = {
            'current_volume': current_volume,
            'avg_volume_20d': avg_volume_20,
            'avg_volume_60d': avg_volume_60,
            'volume_ratio_20d': current_volume / avg_volume_20 if avg_volume_20 > 0 else 1,
            'volume_ratio_60d': current_volume / avg_volume_60 if avg_volume_60 > 0 else 1
        }
        
        # Volume quality scoring
        score = 0
        vol_ratio = volume_analysis['volume_ratio_20d']
        
        # Exceptional volume
        if vol_ratio >= 10:
            score += 40
        elif vol_ratio >= 5:
            score += 35
        elif vol_ratio >= 3:
            score += 25
        elif vol_ratio >= 2:
            score += 15
        elif vol_ratio >= 1.5:
            score += 10
        
        # Volume trend analysis
        if len(volumes) >= 60:
            recent_trend = np.mean(volumes[-20:]) / np.mean(volumes[-40:-20])
            if recent_trend > 1.2:  # Increasing volume trend
                score += 15
        
        # Accumulation vs Distribution detection
        if len(volumes) >= 20 and len(closes) >= 20:
            # Price-volume relationship
            price_changes = np.diff(closes[-20:])
            volume_changes = np.diff(volumes[-20:])
            
            # Positive correlation = accumulation, negative = distribution
            correlation = np.corrcoef(price_changes, volume_changes[:-1])[0,1] if len(price_changes) > 1 else 0
            
            if correlation > 0.3:  # Good accumulation pattern
                score += 10
                volume_analysis['pattern'] = 'accumulation'
            elif correlation < -0.3:  # Distribution pattern
                score -= 10
                volume_analysis['pattern'] = 'distribution'
            else:
                volume_analysis['pattern'] = 'neutral'
        
        volume_analysis.update({
            'score': min(100, score),
            'quality': self._score_to_quality(score)
        })
        
        return volume_analysis
    
    def get_news_sentiment(self, ticker: str) -> Dict:
        """
        Basic news sentiment analysis to detect negative catalysts
        """
        # This is a simplified version - in practice you'd use a news API
        negative_keywords = [
            'offering', 'reverse split', 'dilution', 'bankruptcy', 
            'investigation', 'lawsuit', 'delisting', 'fraud',
            'sec investigation', 'class action', 'going concern'
        ]
        
        positive_keywords = [
            'approval', 'partnership', 'merger', 'acquisition',
            'breakthrough', 'patent', 'fda approval', 'earnings beat'
        ]
        
        # Placeholder - would integrate with actual news API
        sentiment_score = 0  # Neutral by default
        
        return {
            'sentiment_score': sentiment_score,
            'has_negative_news': False,  # Would be determined by actual news analysis
            'has_positive_news': False,
            'news_quality': 'neutral'
        }
    
    def get_current_weights(self) -> Dict:
        """Get current weights (learned or default)"""
        if self.learning_system:
            try:
                return self.learning_system.get_current_weights()
            except Exception as e:
                logger.warning(f"Failed to get learned weights: {e}")
        
        return self.default_weights
    
    def comprehensive_setup_analysis(self, ticker: str, current_price: float, 
                                   current_volume: int, premarket_gap_pct: float) -> SetupAnalysis:
        """
        Complete comprehensive setup analysis with learning integration
        """
        try:
            # Perform all analyses
            consolidation = self.analyze_consolidation_pattern(
                self.get_comprehensive_data(ticker), current_price
            )
            
            timing = self.analyze_timing_and_movement(ticker, current_price)
            
            volume = self.analyze_volume_profile(ticker, current_volume)
            
            news = self.get_news_sentiment(ticker)
            
            # Get current weights (learned or default)
            weights = self.get_current_weights()
            
            logger.info(f"Using weights for {ticker}: {weights}")
            
            # Calculate weighted overall score using learned weights
            overall_score = (
                consolidation.get('score', 0) * weights['consolidation'] +
                timing.get('score', 0) * weights['timing'] +
                volume.get('score', 0) * weights['volume'] +
                (news.get('sentiment_score', 50) + 50) * weights['news']  # Normalize news to 0-100
            )
            
            # Determine grade
            grade = self._score_to_grade(overall_score)
            
            # Prepare analysis result for learning system
            analysis_result = {
                'ticker': ticker,
                'price': current_price,
                'volume': current_volume,
                'premarket_gap_pct': premarket_gap_pct,
                'consolidation_score': consolidation.get('score', 0),
                'timing_score': timing.get('score', 0),
                'volume_score': volume.get('score', 0),
                'news_score': news.get('sentiment_score', 50) + 50,
                'overall_score': overall_score,
                'grade': grade,
                'weights_used': weights
            }
            
            # Log prediction to learning system if available
            prediction_id = None
            if self.learning_system:
                try:
                    prediction_id, updated_weights = self.learning_system.log_and_learn(ticker, analysis_result)
                    logger.info(f"Prediction logged with ID: {prediction_id} for {ticker}")
                    # Update weights for next analysis if they changed
                    if updated_weights != weights:
                        logger.info(f"Weights updated from learning system: {updated_weights}")
                except Exception as e:
                    logger.warning(f"Failed to log prediction to learning system: {e}")
            
            # Compile key factors and red flags
            key_factors = []
            red_flags = []
            
            # Key factors
            if consolidation.get('consolidation_months', 0) >= 3:
                key_factors.append(f"Strong {consolidation['consolidation_months']:.1f}-month consolidation")
            
            if consolidation.get('nearest_target'):
                target = consolidation['nearest_target']
                key_factors.append(f"Target: ${target['price']:.2f} (+{target['distance_pct']:.0f}%)")
            
            if volume.get('volume_ratio_20d', 0) >= 3:
                key_factors.append(f"High volume: {volume['volume_ratio_20d']:.1f}x average")
            
            if timing.get('regular_hours_move_pct', 0) > 5:
                key_factors.append("Continued strength in regular hours")
            
            # Red flags
            red_flags.extend(timing.get('red_flags', []))
            
            if overall_score < 40:
                red_flags.append("Low overall quality score")
            
            if consolidation.get('score', 0) < 30:
                red_flags.append("Weak or no consolidation pattern")
            
            if volume.get('pattern') == 'distribution':
                red_flags.append("Distribution pattern detected")
            
            # Generate recommendation
            recommendation = self._generate_recommendation(overall_score, red_flags, key_factors)
            
            # Calculate risk assessment
            risk_assessment = self._calculate_risk_assessment(consolidation, timing, volume)
            
            return SetupAnalysis(
                ticker=ticker,
                overall_score=int(overall_score),
                grade=grade,
                consolidation_quality=consolidation,
                timing_analysis=timing,
                volume_analysis=volume,
                technical_analysis={'news_sentiment': news},
                risk_assessment=risk_assessment,
                recommendation=recommendation,
                key_factors=key_factors,
                red_flags=red_flags
            )
            
        except Exception as e:
            logger.error(f"Error in comprehensive analysis for {ticker}: {e}")
            return self._fallback_analysis(ticker, current_price)
    
    def _score_to_quality(self, score: int) -> str:
        """Convert score to quality description"""
        if score >= 80:
            return 'excellent'
        elif score >= 70:
            return 'very_good'
        elif score >= 60:
            return 'good'
        elif score >= 50:
            return 'average'
        elif score >= 40:
            return 'below_average'
        else:
            return 'poor'
    
    def _score_to_grade(self, score: float) -> str:
        """Convert overall score to letter grade"""
        if score >= 85:
            return 'A+'
        elif score >= 75:
            return 'A'
        elif score >= 65:
            return 'A-'
        elif score >= 55:
            return 'B+'
        elif score >= 45:
            return 'B'
        elif score >= 35:
            return 'C'
        else:
            return 'D'
    
    def _generate_recommendation(self, score: float, red_flags: List[str], key_factors: List[str]) -> str:
        """Generate trading recommendation"""
        if score >= 80 and not red_flags:
            return "STRONG BUY - High quality setup with multiple positive factors"
        elif score >= 70 and len(red_flags) <= 1:
            return "BUY - Good quality setup, manageable risks"
        elif score >= 60:
            return "CONDITIONAL BUY - Average setup, monitor closely"
        elif score >= 50:
            return "WATCH - Below average setup, wait for better entry"
        else:
            return "AVOID - Poor setup quality, high risk"
    
    def _calculate_risk_assessment(self, consolidation: Dict, timing: Dict, volume: Dict) -> Dict:
        """Calculate risk metrics for the setup"""
        risk_score = 50  # Start with neutral risk
        
        # Lower risk for strong consolidation
        if consolidation.get('consolidation_months', 0) >= 3:
            risk_score -= 15
        
        # Higher risk for timing issues
        if len(timing.get('red_flags', [])) > 0:
            risk_score += 20
        
        # Lower risk for strong volume
        if volume.get('volume_ratio_20d', 0) >= 5:
            risk_score -= 10
        
        # Calculate position sizing recommendation
        if risk_score <= 30:
            position_size = 'large'
        elif risk_score <= 50:
            position_size = 'medium'
        else:
            position_size = 'small'
        
        return {
            'risk_score': max(0, min(100, risk_score)),
            'risk_level': 'low' if risk_score <= 40 else 'medium' if risk_score <= 60 else 'high',
            'recommended_position_size': position_size
        }
    
    def _fallback_analysis(self, ticker: str, current_price: float) -> SetupAnalysis:
        """Fallback analysis when data is insufficient"""
        return SetupAnalysis(
            ticker=ticker,
            overall_score=40,
            grade='C',
            consolidation_quality={'quality': 'insufficient_data', 'score': 40},
            timing_analysis={'quality': 'insufficient_data', 'score': 40},
            volume_analysis={'quality': 'insufficient_data', 'score': 40},
            technical_analysis={'news_sentiment': {'news_quality': 'unknown'}},
            risk_assessment={'risk_level': 'high', 'recommended_position_size': 'small'},
            recommendation="INSUFFICIENT DATA - Cannot analyze properly",
            key_factors=[],
            red_flags=["Insufficient historical data for analysis"]
        )


# Integration function for the main quality system
def analyze_setup_comprehensive(ticker: str, current_price: float, 
                              current_volume: int, premarket_gap_pct: float,
                              learning_db_path: str = None) -> Dict:
    """
    Main function to analyze a setup comprehensively
    Returns dictionary compatible with existing quality system
    """
    # Use default learning database path if not provided
    if learning_db_path is None:
        current_dir = Path(__file__).parent.parent
        learning_db_path = str(current_dir / "learning_system.db")
    
    analyzer = AdvancedSetupAnalyzer(learning_db_path=learning_db_path)
    analysis = analyzer.comprehensive_setup_analysis(
        ticker, current_price, current_volume, premarket_gap_pct
    )
    
    # Convert to format expected by quality system
    return {
        'ticker': analysis.ticker,
        'overall_score': analysis.overall_score,
        'grade': analysis.grade,
        'consolidation_months': analysis.consolidation_quality.get('consolidation_months', 0),
        'nearest_target': analysis.consolidation_quality.get('nearest_target'),
        'volume_ratio': analysis.volume_analysis.get('volume_ratio_20d', 1),
        'volume_quality': analysis.volume_analysis.get('quality', 'unknown'),
        'timing_quality': analysis.timing_analysis.get('quality', 'unknown'),
        'recommendation': analysis.recommendation,
        'key_factors': analysis.key_factors,
        'red_flags': analysis.red_flags,
        'risk_level': analysis.risk_assessment.get('risk_level', 'medium'),
        'position_size': analysis.risk_assessment.get('recommended_position_size', 'small')
    }


# Test function
if __name__ == "__main__":
    # Test with PPSI example
    result = analyze_setup_comprehensive("PPSI", 4.42, 80_600_000, 42.1)
    
    print(f"\n=== COMPREHENSIVE ANALYSIS FOR PPSI ===")
    print(f"Overall Score: {result['overall_score']}/100")
    print(f"Grade: {result['grade']}")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Position Size: {result['position_size']}")
    
    if result['key_factors']:
        print(f"\nKey Factors:")
        for factor in result['key_factors']:
            print(f"  ✅ {factor}")
    
    if result['red_flags']:
        print(f"\nRed Flags:")
        for flag in result['red_flags']:
            print(f"  ⚠️ {flag}")
    
    if result['nearest_target']:
        target = result['nearest_target']
        print(f"\nNearest Target: ${target['price']:.2f} (+{target['distance_pct']:.0f}%)")