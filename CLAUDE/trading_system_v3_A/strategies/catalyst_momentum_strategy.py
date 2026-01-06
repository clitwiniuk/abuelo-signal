#!/usr/bin/env python3
"""
Catalyst Momentum Strategy
==========================

Nueva estrategia que combina detección de catalizadores (FinBERT) con entrada en momentum temprano.
No espera consolidación - entra durante el impulso inicial del catalizador.

Key Features:
- Integra con scanner de catalizadores existente
- Entra en momentum inicial, no pullbacks
- Diseñada para smallcaps event-driven
- Optimizada para capture de impulso completo

Author: Claude Code
Date: 2025-08-21
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass
import logging

from strategies.base import BaseStrategy
from core.interfaces import MarketData, Signal, SignalType


@dataclass
class CatalystInfo:
    """Information about detected catalyst"""
    catalyst_type: str
    strength: float
    confidence: float
    finbert_score: float
    news_age_minutes: int
    detected_at: datetime


class CatalystMomentumStrategy(BaseStrategy):
    """
    Catalyst Momentum Strategy
    
    Combina catalizadores detectados por FinBERT con entrada inmediata en momentum.
    No espera consolidación - captura el impulso completo del evento.
    """

    def __init__(self, parameters: Dict[str, Any] = None):
        # Fallback defaults (only used if config.ini fails)
        fallback_defaults = {
            'min_catalyst_strength': 0.6,
            'min_finbert_confidence': 0.7,
            'min_price_move_pct': 0.02,
            'min_volume_multiplier': 3.0,
            'entry_window_minutes': 30,
            'stop_loss_pct': 0.08,
            'take_profit_pct': 0.15,
            'max_entries_per_day': 3
        }
        
        # Initialize with name first, following MACDVStrategy pattern
        super().__init__("catalyst_momentum", fallback_defaults)
        self.strategy_name = "catalyst_momentum"
        
        # Load config from config.ini like MACDVStrategy
        try:
            config_params = self._load_strategy_config('CATALYST_MOMENTUM_STRATEGY', fallback_defaults)
            
            # Parameters passed to constructor have highest priority
            if parameters:
                config_params.update(parameters)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for catalyst_momentum strategy: {e}")
            # Keep fallback defaults
        
        # Catalyst detection parameters (from config)
        self.min_catalyst_strength = self._parameters.get('min_catalyst_strength', 0.6)
        self.min_finbert_confidence = self._parameters.get('min_finbert_confidence', 0.7)
        self.max_news_age_minutes = self._parameters.get('max_news_age_minutes', 15)
        
        # Momentum confirmation parameters
        self.min_price_move_pct = self._parameters.get('min_price_move_pct', 0.02)  # 2%
        self.min_volume_multiplier = self._parameters.get('min_volume_multiplier', 3.0)  # 3x avg
        self.momentum_timeframe_minutes = self._parameters.get('momentum_timeframe_minutes', 5)
        
        # Entry timing parameters
        self.entry_window_minutes = self._parameters.get('entry_window_minutes', 20)  # Max time since catalyst
        self.max_entries_per_day = self._parameters.get('max_entries_per_day', 3)
        
        # Risk management
        self.stop_loss_pct = self._parameters.get('stop_loss_pct', 0.08)  # 8%
        self.take_profit_pct = self._parameters.get('take_profit_pct', 0.15)  # 15%
        self.trailing_stop_activation = self._parameters.get('trailing_stop_activation', 0.06)  # 6%
        self.trailing_stop_distance = self._parameters.get('trailing_stop_distance', 0.03)  # 3%
        
        # Enable FOMO detection for CatalystMomentum (very sensitive - catalysts create instant FOMO)
        fomo_config = {
            'fomo_threshold': 0.65,  # Lower threshold - catalyst momentum creates FOMO fast
            'critical_threshold': 0.85,
            'volume_explosion_multiplier': 5.0,  # 5x for catalyst plays
            'consecutive_green_bars': 3,  # 3 consecutive for catalyst momentum
            'rsi_overbought_level': 75  # Lower RSI - catalyst moves peak faster
        }
        
        if self.enable_fomo_exit(fomo_config):
            self.logger.info("🎪 FOMO Detection enabled for Catalyst Momentum Strategy")
        else:
            self.logger.warning("⚠️ FOMO Detection could not be enabled")
        
        # Internal tracking
        self.detected_catalysts = {}  # symbol -> CatalystInfo
        self.daily_entries = 0
        self.last_reset_date = datetime.now().date()
        
        self.logger = logging.getLogger(f"{__name__}.{self.strategy_name}")
        self.logger.info(f"🔥 Catalyst Momentum Strategy initialized")
        self.logger.info(f"   └─ Catalyst: strength≥{self.min_catalyst_strength}, confidence≥{self.min_finbert_confidence}")
        self.logger.info(f"   └─ Momentum: price≥{self.min_price_move_pct:.1%}, volume≥{self.min_volume_multiplier}x")

    def analyze(self, data: MarketData) -> Optional[Dict[str, Any]]:
        """
        Analyze for catalyst + momentum combination
        
        Returns:
            Analysis dict with catalyst and momentum information
        """
        try:
            self._reset_daily_counters_if_needed()
            
            # Check if we've hit daily limit
            if self.daily_entries >= self.max_entries_per_day:
                return None
                
            symbol = data.symbol
            current_bar = data.current_bar
            
            # Step 1: Check for fresh catalyst detection
            catalyst_info = self._get_catalyst_info(symbol, current_bar)
            if not catalyst_info:
                return None
                
            # Step 2: Confirm price momentum
            momentum_analysis = self._analyze_price_momentum(data)
            if not momentum_analysis['confirmed']:
                return None
                
            # Step 3: Verify volume surge
            volume_analysis = self._analyze_volume_surge(data)
            if not volume_analysis['confirmed']:
                return None
                
            # Step 4: Check entry timing window
            timing_analysis = self._analyze_entry_timing(catalyst_info, current_bar)
            if not timing_analysis['valid']:
                return None
                
            # Calculate composite score
            composite_score = self._calculate_composite_score(
                catalyst_info, momentum_analysis, volume_analysis, timing_analysis
            )
            
            analysis = {
                'qualified': True,
                'signal_type': 'LONG',  # Catalyst momentum is bullish-focused
                'strength': composite_score,
                'confidence': min(0.95, composite_score),
                'catalyst_info': {
                    'type': catalyst_info.catalyst_type,
                    'strength': catalyst_info.strength,
                    'finbert_confidence': catalyst_info.confidence,
                    'age_minutes': catalyst_info.news_age_minutes
                },
                'momentum_analysis': momentum_analysis,
                'volume_analysis': volume_analysis,
                'timing_analysis': timing_analysis,
                'entry_reason': f"Catalyst ({catalyst_info.catalyst_type}) + {momentum_analysis['price_move_pct']:.1%} momentum",
                'strategy_specific_data': {
                    'catalyst_detected_at': catalyst_info.detected_at.isoformat(),
                    'entry_window_remaining': timing_analysis['window_remaining_minutes'],
                    'momentum_quality': momentum_analysis['quality_score']
                }
            }
            
            self.logger.info(f"🔥 CATALYST MOMENTUM qualified for {symbol}")
            self.logger.info(f"   └─ Catalyst: {catalyst_info.catalyst_type} (strength: {catalyst_info.strength:.2f})")
            self.logger.info(f"   └─ Momentum: {momentum_analysis['price_move_pct']:+.1%} in {momentum_analysis['timeframe']}min")
            self.logger.info(f"   └─ Volume: {volume_analysis['volume_multiplier']:.1f}x average")
            self.logger.info(f"   └─ Score: {composite_score:.2f}")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing catalyst momentum for {data.symbol}: {e}")
            return None

    def generate_signals(self, data: MarketData, analysis: Optional[Dict] = None) -> List[Signal]:
        """
        Generate immediate entry signal based on catalyst + momentum
        """
        if not analysis or not analysis.get('qualified'):
            return []
            
        try:
            current_bar = data.current_bar
            
            # Create entry signal
            signal = Signal(
                symbol=data.symbol,
                signal_type=SignalType.LONG,
                price=current_bar.close,
                quantity=100,  # Will be calculated by position sizing
                timestamp=current_bar.timestamp,
                confidence=analysis['confidence'],
                strategy=self.strategy_name,
                metadata={
                    'catalyst_type': analysis['catalyst_info']['type'],
                    'catalyst_strength': analysis['catalyst_info']['strength'],
                    'momentum_pct': analysis['momentum_analysis']['price_move_pct'],
                    'volume_multiplier': analysis['volume_analysis']['volume_multiplier'],
                    'entry_reason': analysis['entry_reason'],
                    'stop_loss_pct': self.stop_loss_pct,
                    'take_profit_pct': self.take_profit_pct,
                    'trailing_activation': self.trailing_stop_activation,
                    'trailing_distance': self.trailing_stop_distance
                }
            )
            
            self.daily_entries += 1
            
            self.logger.info(f"🔥 CATALYST MOMENTUM SIGNAL generated for {data.symbol}")
            self.logger.info(f"   └─ Entry: ${current_bar.close:.2f} (confidence: {analysis['confidence']:.2f})")
            self.logger.info(f"   └─ Daily entries: {self.daily_entries}/{self.max_entries_per_day}")
            
            return [signal]
            
        except Exception as e:
            self.logger.error(f"Error generating catalyst momentum signal for {data.symbol}: {e}")
            return []

    def _get_catalyst_info(self, symbol: str, current_bar) -> Optional[CatalystInfo]:
        """
        Get catalyst information from the system's catalyst detection
        
        Integrates with existing FinBERT + Scanner system via metadata
        """
        try:
            # Check if we have catalyst information in the current bar's metadata
            # This gets populated by the smallcap scanner system
            metadata = getattr(current_bar, 'metadata', {})
            
            # Look for catalyst information from FinBERT analysis
            catalyst_data = metadata.get('catalyst_info')
            finbert_data = metadata.get('finbert_result')
            
            if not catalyst_data and not finbert_data:
                # Try alternative metadata keys
                catalyst_data = metadata.get('catalyst')
                finbert_data = metadata.get('sentiment_analysis')
            
            if not catalyst_data or not finbert_data:
                return None
                
            # Extract catalyst information
            catalyst_type = catalyst_data.get('catalyst_type', 'UNKNOWN')
            strength = catalyst_data.get('strength', 0.0)
            
            # Extract FinBERT information  
            finbert_confidence = finbert_data.get('confidence', 0.0)
            finbert_score = finbert_data.get('score', 0.0)
            
            # Check minimum thresholds
            if (strength < self.min_catalyst_strength or 
                finbert_confidence < self.min_finbert_confidence):
                return None
                
            # Calculate news age (from metadata or estimate)
            news_timestamp = catalyst_data.get('detected_at') or metadata.get('news_time')
            if news_timestamp:
                if isinstance(news_timestamp, str):
                    news_timestamp = datetime.fromisoformat(news_timestamp)
                news_age_minutes = (current_bar.timestamp - news_timestamp).total_seconds() / 60
            else:
                # If no timestamp, assume recent news (conservative)
                news_age_minutes = 5
                
            if news_age_minutes > self.max_news_age_minutes:
                return None
                
            return CatalystInfo(
                catalyst_type=catalyst_type,
                strength=strength,
                confidence=finbert_confidence,
                finbert_score=finbert_score,
                news_age_minutes=news_age_minutes,
                detected_at=news_timestamp or current_bar.timestamp
            )
            
        except Exception as e:
            self.logger.error(f"Error getting catalyst info for {symbol}: {e}")
            return None

    def _analyze_price_momentum(self, data: MarketData) -> Dict[str, Any]:
        """
        Analyze price momentum to confirm catalyst is driving movement
        """
        try:
            df = data.df
            if len(df) < 10:
                return {'confirmed': False, 'reason': 'Insufficient data'}
                
            current_price = data.current_bar.close
            
            # Look back N minutes for momentum calculation
            lookback_bars = min(self.momentum_timeframe_minutes, len(df) - 1)
            if lookback_bars < 2:
                return {'confirmed': False, 'reason': 'Insufficient lookback data'}
                
            price_start = df.iloc[-lookback_bars]['close']
            price_move_pct = (current_price - price_start) / price_start
            
            # Must be positive momentum above threshold
            momentum_confirmed = price_move_pct >= self.min_price_move_pct
            
            # Quality metrics
            price_volatility = df['close'].tail(lookback_bars).std() / df['close'].tail(lookback_bars).mean()
            directional_consistency = self._calculate_directional_consistency(df.tail(lookback_bars))
            
            quality_score = (
                min(1.0, abs(price_move_pct) / 0.05) * 0.4 +  # Size of move
                min(1.0, directional_consistency) * 0.3 +      # Consistency
                min(1.0, 1.0 - price_volatility) * 0.3        # Stability
            )
            
            return {
                'confirmed': momentum_confirmed,
                'price_move_pct': price_move_pct,
                'timeframe': lookback_bars,
                'quality_score': quality_score,
                'directional_consistency': directional_consistency,
                'volatility': price_volatility,
                'reason': f"{price_move_pct:+.1%} move in {lookback_bars}min"
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing price momentum: {e}")
            return {'confirmed': False, 'reason': f'Error: {e}'}

    def _analyze_volume_surge(self, data: MarketData) -> Dict[str, Any]:
        """
        Analyze volume surge to confirm institutional interest
        """
        try:
            df = data.df
            if len(df) < 20:
                return {'confirmed': False, 'reason': 'Insufficient volume data'}
                
            current_volume = data.current_bar.volume
            
            # Calculate average volume (exclude current bar)
            avg_volume = df['volume'].tail(20).mean()
            
            if avg_volume == 0:
                return {'confirmed': False, 'reason': 'Zero average volume'}
                
            volume_multiplier = current_volume / avg_volume
            volume_confirmed = volume_multiplier >= self.min_volume_multiplier
            
            # Additional volume quality metrics
            recent_volumes = df['volume'].tail(5).values
            volume_acceleration = np.mean(recent_volumes[-3:]) / np.mean(recent_volumes[:2]) if len(recent_volumes) >= 3 else 1.0
            
            return {
                'confirmed': volume_confirmed,
                'volume_multiplier': volume_multiplier,
                'current_volume': current_volume,
                'average_volume': avg_volume,
                'volume_acceleration': volume_acceleration,
                'reason': f"{volume_multiplier:.1f}x average volume"
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing volume surge: {e}")
            return {'confirmed': False, 'reason': f'Error: {e}'}

    def _analyze_entry_timing(self, catalyst_info: CatalystInfo, current_bar) -> Dict[str, Any]:
        """
        Analyze if we're still in valid entry window after catalyst
        """
        try:
            time_since_catalyst = (current_bar.timestamp - catalyst_info.detected_at).total_seconds() / 60
            window_remaining = self.entry_window_minutes - time_since_catalyst
            
            timing_valid = (
                time_since_catalyst <= self.entry_window_minutes and
                catalyst_info.news_age_minutes <= self.max_news_age_minutes
            )
            
            return {
                'valid': timing_valid,
                'time_since_catalyst_minutes': time_since_catalyst,
                'window_remaining_minutes': max(0, window_remaining),
                'news_age_minutes': catalyst_info.news_age_minutes,
                'reason': f"Entry window: {window_remaining:.1f}min remaining"
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing entry timing: {e}")
            return {'valid': False, 'reason': f'Error: {e}'}

    def _calculate_composite_score(
        self, 
        catalyst_info: CatalystInfo,
        momentum_analysis: Dict,
        volume_analysis: Dict,
        timing_analysis: Dict
    ) -> float:
        """
        Calculate composite opportunity score
        """
        try:
            # Base scores (0.0 - 1.0)
            catalyst_score = catalyst_info.strength * catalyst_info.confidence
            momentum_score = momentum_analysis['quality_score']
            volume_score = min(1.0, volume_analysis['volume_multiplier'] / 5.0)  # Cap at 5x
            timing_score = timing_analysis['window_remaining_minutes'] / self.entry_window_minutes
            
            # Weighted composite (prioritize catalyst and momentum)
            composite = (
                catalyst_score * 0.35 +    # Catalyst is key
                momentum_score * 0.35 +    # Momentum confirmation critical  
                volume_score * 0.20 +      # Volume confirmation important
                timing_score * 0.10        # Timing less critical but relevant
            )
            
            return min(0.95, composite)  # Cap at 95%
            
        except Exception as e:
            self.logger.error(f"Error calculating composite score: {e}")
            return 0.0

    def _calculate_directional_consistency(self, df: pd.DataFrame) -> float:
        """
        Calculate how consistent price movement direction is
        """
        try:
            if len(df) < 3:
                return 0.5
                
            price_changes = df['close'].diff().dropna()
            if len(price_changes) == 0:
                return 0.5
                
            # Count bars moving in same direction as overall trend
            overall_direction = 1 if df['close'].iloc[-1] > df['close'].iloc[0] else -1
            consistent_moves = sum(1 for change in price_changes if np.sign(change) == overall_direction)
            
            consistency = consistent_moves / len(price_changes)
            return consistency
            
        except Exception:
            return 0.5

    def _reset_daily_counters_if_needed(self):
        """Reset daily counters if it's a new day"""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_entries = 0
            self.last_reset_date = current_date
            self.logger.info(f"🔄 Daily counters reset for {current_date}")

    def get_strategy_status(self) -> Dict[str, Any]:
        """Get current strategy status and statistics"""
        return {
            'strategy_name': self.strategy_name,
            'daily_entries': self.daily_entries,
            'max_daily_entries': self.max_entries_per_day,
            'detected_catalysts': len(self.detected_catalysts),
            'parameters': {
                'min_catalyst_strength': self.min_catalyst_strength,
                'min_finbert_confidence': self.min_finbert_confidence,
                'min_price_move_pct': self.min_price_move_pct,
                'min_volume_multiplier': self.min_volume_multiplier,
                'entry_window_minutes': self.entry_window_minutes
            }
        }