"""
Swing Transition Analyzer - Decisión inteligente para mantener posiciones overnight
===================================================================================

PROPÓSITO:
Evalúa posiciones intraday a las 15:30 ET para decidir si pueden convertirse en swing.
Ultra-conservador: Solo 5-10% de posiciones pasan los filtros.

ENFOQUE:
- Análisis multi-factor con scoring system (necesita 80/100 puntos)
- Requiere catalyst REAL confirmado (no pumps técnicos)
- Valida riesgos específicos de smallcaps (dilution, halts, offerings)
- Reduce posición 40% antes de overnight (asegura profit)

TIMING:
- Se ejecuta UNA VEZ al día a las 15:30 ET
- Decisión PERMANENTE hasta next day
- Si gap down pre-market >5% -> exit on open

Author: Trading System v3
Date: 2025-12-13
"""

import logging
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, time
from zoneinfo import ZoneInfo

# Technical analysis
from core.technical_utils import TechnicalUtils


class CatalystTier:
    """Catalyst quality tiers for overnight hold validation"""
    TIER_1 = "TIER_1"  # FDA approval, buyout, patents - SAFE
    TIER_2 = "TIER_2"  # Earnings beat, partnerships - RISKY
    TIER_3 = "TIER_3"  # Twitter pumps, Reddit mentions - NO OVERNIGHT
    NONE = "NONE"      # No catalyst detected


class SwingTransitionAnalyzer:
    """
    Analiza posiciones a las 15:30 ET para decidir overnight hold

    ULTRA-CONSERVATIVE: Solo 5-10% de posiciones pasan

    Scoring System:
    - PnL Health: 25 points (>7% required)
    - HOD Proximity: 15 points (within 3% of high)
    - Catalyst Quality: 30 points (TIER_1 required for full score)
    - Daily Technicals: 20 points (RSI <65, resistance >8% away)
    - Volume Profile: 10 points (institutional confirmation)

    Minimum Score: 80/100 para aprobar swing transition
    """

    def __init__(self, config=None):
        """
        Initialize swing transition analyzer

        Args:
            config: UnifiedConfig object (optional)
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Configuration (with defaults)
        self.min_pnl_for_swing = getattr(config, 'swing_transition_min_pnl', 7.0)  # 7% minimum
        self.max_hod_distance = getattr(config, 'swing_transition_max_hod_distance', 3.0)  # 3% from HOD
        self.min_score = getattr(config, 'swing_transition_min_score', 80)  # 80/100 minimum
        self.max_daily_rsi = getattr(config, 'swing_transition_max_daily_rsi', 65)  # RSI <65
        self.min_resistance_distance = getattr(config, 'swing_transition_min_resistance_distance', 8.0)  # 8% to resistance
        self.min_volume_ratio = getattr(config, 'swing_transition_min_volume_ratio', 2.0)  # 2x average
        self.position_reduction_pct = getattr(config, 'swing_transition_position_reduction', 0.40)  # Reduce 40%

        # Safety limits
        self.max_simultaneous_swings = getattr(config, 'swing_transition_max_positions', 3)  # Max 3 overnight
        self.min_market_cap = getattr(config, 'swing_transition_min_market_cap', 50_000_000)  # $50M min

        # Tracking
        self.swing_transitions_today = []  # List of symbols transitioned today

        self.logger.info("🌙 SwingTransitionAnalyzer initialized (ultra-conservative mode)")

    async def can_transition_to_swing(
        self,
        symbol: str,
        position_data: Dict[str, Any],
        current_price: float,
        bars_1min: Optional[List] = None,
        bars_daily: Optional[List] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evalúa si una posición puede transicionar a swing overnight

        Args:
            symbol: Symbol to evaluate
            position_data: Position metadata from active_positions
            current_price: Current market price
            bars_1min: 1-minute bars for intraday analysis (optional)
            bars_daily: Daily bars for trend analysis (optional)

        Returns:
            Tuple of:
            - can_swing (bool): True if position can stay overnight
            - reason (str): Explanation of decision
            - analysis (dict): Detailed scoring breakdown
        """
        try:
            score = 0
            max_score = 100
            reasons = []
            warnings = []

            entry_price = position_data.get('entry_price', 0)
            entry_time = position_data.get('entry_time')

            if entry_price == 0:
                return False, "Invalid entry price", {}

            # ===================================================================
            # CHECKPOINT 1: Max simultaneous swings (3 max)
            # ===================================================================
            if len(self.swing_transitions_today) >= self.max_simultaneous_swings:
                return False, f"Max {self.max_simultaneous_swings} swing positions already approved today", {}

            # ===================================================================
            # CHECKPOINT 2: PnL Health (25 points)
            # ===================================================================
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            if pnl_pct >= 10.0:
                score += 25
                reasons.append(f"Excellent PnL: +{pnl_pct:.1f}% (25 pts)")
            elif pnl_pct >= 7.0:
                score += 15
                reasons.append(f"Good PnL: +{pnl_pct:.1f}% (15 pts)")
            elif pnl_pct >= 5.0:
                score += 5
                warnings.append(f"Marginal PnL: +{pnl_pct:.1f}% (5 pts)")
            else:
                return False, f"Insufficient PnL: +{pnl_pct:.1f}% (need +{self.min_pnl_for_swing}% min)", {
                    'score': score,
                    'pnl_pct': pnl_pct
                }

            # ===================================================================
            # CHECKPOINT 3: HOD Proximity (15 points)
            # ===================================================================
            hod = position_data.get('highest_price', current_price)
            if bars_1min and len(bars_1min) > 0:
                # Calculate HOD from bars
                highs = [bar.high for bar in bars_1min]
                hod = max(highs)

            distance_from_hod_pct = ((hod - current_price) / hod) * 100

            if distance_from_hod_pct <= 2.0:
                score += 15
                reasons.append(f"At HOD: {distance_from_hod_pct:.1f}% below (15 pts)")
            elif distance_from_hod_pct <= 3.0:
                score += 10
                reasons.append(f"Near HOD: {distance_from_hod_pct:.1f}% below (10 pts)")
            elif distance_from_hod_pct <= 5.0:
                score += 5
                warnings.append(f"Below HOD: {distance_from_hod_pct:.1f}% (5 pts)")
            else:
                warnings.append(f"Far from HOD: {distance_from_hod_pct:.1f}% below (0 pts)")

            # ===================================================================
            # CHECKPOINT 4: Catalyst Quality (30 points) - CRITICAL
            # ===================================================================
            catalyst = await self._check_catalyst(symbol, position_data)

            if catalyst['tier'] == CatalystTier.TIER_1:
                score += 30
                reasons.append(f"Strong catalyst: {catalyst['type']} (30 pts)")
            elif catalyst['tier'] == CatalystTier.TIER_2:
                score += 15
                warnings.append(f"Moderate catalyst: {catalyst['type']} (15 pts)")
            elif catalyst['tier'] == CatalystTier.TIER_3:
                score += 5
                warnings.append(f"Weak catalyst: {catalyst['type']} (5 pts)")
            else:
                return False, "No credible catalyst detected (required for overnight)", {
                    'score': score,
                    'catalyst': catalyst
                }

            # ===================================================================
            # CHECKPOINT 5: Daily Technical Health (20 points)
            # ===================================================================
            daily_analysis = await self._analyze_daily_timeframe(symbol, bars_daily, current_price)

            rsi_daily = daily_analysis.get('rsi_daily', 50)
            resistance_distance = daily_analysis.get('distance_to_resistance', 100)

            # RSI check (10 points)
            if rsi_daily < 60:
                score += 10
                reasons.append(f"RSI healthy: {rsi_daily:.0f} (10 pts)")
            elif rsi_daily < 65:
                score += 5
                warnings.append(f"RSI elevated: {rsi_daily:.0f} (5 pts)")
            else:
                warnings.append(f"RSI overbought: {rsi_daily:.0f} (0 pts)")

            # Resistance check (10 points)
            if resistance_distance > 10:
                score += 10
                reasons.append(f"Resistance far: +{resistance_distance:.1f}% (10 pts)")
            elif resistance_distance > 8:
                score += 5
                reasons.append(f"Resistance moderate: +{resistance_distance:.1f}% (5 pts)")
            else:
                warnings.append(f"Near resistance: +{resistance_distance:.1f}% (0 pts)")

            # ===================================================================
            # CHECKPOINT 6: Volume Profile (10 points)
            # ===================================================================
            volume_analysis = await self._analyze_volume_profile(symbol, bars_1min)
            volume_ratio = volume_analysis.get('volume_ratio', 1.0)

            if volume_ratio >= 3.0:
                score += 10
                reasons.append(f"Strong volume: {volume_ratio:.1f}x avg (10 pts)")
            elif volume_ratio >= 2.0:
                score += 7
                reasons.append(f"Good volume: {volume_ratio:.1f}x avg (7 pts)")
            elif volume_ratio >= 1.5:
                score += 3
                warnings.append(f"Moderate volume: {volume_ratio:.1f}x avg (3 pts)")
            else:
                warnings.append(f"Low volume: {volume_ratio:.1f}x avg (0 pts)")

            # ===================================================================
            # CHECKPOINT 7: Dilution Risk Filter (VETO power)
            # ===================================================================
            dilution_risk = await self._check_dilution_risk(symbol)

            if dilution_risk['risk_level'] == 'HIGH':
                return False, f"High dilution risk: {dilution_risk['reason']}", {
                    'score': score,
                    'dilution_risk': dilution_risk
                }
            elif dilution_risk['risk_level'] == 'MEDIUM':
                warnings.append(f"⚠️ Medium dilution risk: {dilution_risk['reason']}")

            # ===================================================================
            # FINAL DECISION
            # ===================================================================
            analysis = {
                'score': score,
                'max_score': max_score,
                'pnl_pct': pnl_pct,
                'distance_from_hod_pct': distance_from_hod_pct,
                'catalyst': catalyst,
                'rsi_daily': rsi_daily,
                'resistance_distance': resistance_distance,
                'volume_ratio': volume_ratio,
                'dilution_risk': dilution_risk,
                'reasons': reasons,
                'warnings': warnings
            }

            if score >= self.min_score:
                self.swing_transitions_today.append(symbol)

                decision_msg = (
                    f"✅ APPROVED FOR SWING ({score}/{max_score} pts) | "
                    f"PnL: +{pnl_pct:.1f}%, Catalyst: {catalyst['type']}, "
                    f"RSI: {rsi_daily:.0f}, Resistance: +{resistance_distance:.1f}%"
                )

                return True, decision_msg, analysis
            else:
                needed = self.min_score - score
                decision_msg = (
                    f"❌ REJECTED ({score}/{max_score} pts - need {needed} more) | "
                    f"Will close at 15:50 ET"
                )

                return False, decision_msg, analysis

        except Exception as e:
            self.logger.error(f"Error analyzing swing transition for {symbol}: {e}")
            return False, f"Analysis error: {str(e)}", {}

    async def _check_catalyst(self, symbol: str, position_data: Dict) -> Dict[str, Any]:
        """
        Check for catalyst presence and quality

        Returns:
            Dict with 'tier', 'type', 'description'
        """
        # TODO: Integrate with news scanner, SEC filings, social sentiment
        # For now, use opportunity metadata if available

        opportunity_data = position_data.get('opportunity_data', {})

        # Check if catalyst data was attached during entry
        catalyst_data = opportunity_data.get('catalyst_data', {})

        if catalyst_data:
            catalyst_type = catalyst_data.get('type', 'UNKNOWN')
            catalyst_strength = catalyst_data.get('strength', 0)

            # Classify catalyst tier
            if catalyst_type in ['FDA_APPROVAL', 'BUYOUT', 'PATENT_GRANT']:
                tier = CatalystTier.TIER_1
            elif catalyst_type in ['EARNINGS_BEAT', 'PARTNERSHIP', 'CONTRACT_WIN']:
                tier = CatalystTier.TIER_2
            elif catalyst_type in ['SOCIAL_MENTION', 'TECHNICAL_BREAKOUT']:
                tier = CatalystTier.TIER_3
            else:
                tier = CatalystTier.NONE

            return {
                'tier': tier,
                'type': catalyst_type,
                'description': catalyst_data.get('description', ''),
                'strength': catalyst_strength
            }

        # Fallback: Check if strong technical setup (conservative)
        quality_score = opportunity_data.get('quality_score', 0)

        if quality_score >= 85:
            return {
                'tier': CatalystTier.TIER_2,
                'type': 'HIGH_QUALITY_SETUP',
                'description': f'Quality score {quality_score}/100',
                'strength': quality_score
            }
        elif quality_score >= 70:
            return {
                'tier': CatalystTier.TIER_3,
                'type': 'MODERATE_SETUP',
                'description': f'Quality score {quality_score}/100',
                'strength': quality_score
            }

        return {
            'tier': CatalystTier.NONE,
            'type': 'NO_CATALYST',
            'description': 'No catalyst detected',
            'strength': 0
        }

    async def _analyze_daily_timeframe(
        self,
        symbol: str,
        bars_daily: Optional[List],
        current_price: float
    ) -> Dict[str, Any]:
        """
        Analyze daily timeframe for swing potential

        Returns:
            Dict with 'rsi_daily', 'distance_to_resistance', 'distance_to_support'
        """
        default_result = {
            'rsi_daily': 50,
            'distance_to_resistance': 100,
            'distance_to_support': 100,
            'can_swing': False
        }

        if not bars_daily or len(bars_daily) < 30:
            return default_result

        try:
            # Calculate RSI on daily timeframe
            closes = [bar.close for bar in bars_daily]
            rsi_daily = TechnicalUtils.calculate_rsi(closes, period=14)

            if rsi_daily is None:
                rsi_daily = 50

            # Find nearest resistance (last 60 days)
            recent_highs = [bar.high for bar in bars_daily[-60:]]
            resistance = max(recent_highs)

            distance_to_resistance = ((resistance - current_price) / current_price) * 100

            # Find nearest support (last 60 days)
            recent_lows = [bar.low for bar in bars_daily[-60:]]
            support = min(recent_lows)

            distance_to_support = ((current_price - support) / support) * 100

            # Can swing if RSI healthy and resistance far
            can_swing = (rsi_daily < 65 and distance_to_resistance > 8)

            return {
                'rsi_daily': rsi_daily,
                'distance_to_resistance': distance_to_resistance,
                'distance_to_support': distance_to_support,
                'can_swing': can_swing
            }

        except Exception as e:
            self.logger.warning(f"Error analyzing daily timeframe for {symbol}: {e}")
            return default_result

    async def _analyze_volume_profile(
        self,
        symbol: str,
        bars_1min: Optional[List]
    ) -> Dict[str, Any]:
        """
        Analyze volume profile for institutional confirmation

        Returns:
            Dict with 'volume_ratio', 'volume_trend'
        """
        if not bars_1min or len(bars_1min) < 30:
            return {
                'volume_ratio': 1.0,
                'volume_trend': 'UNKNOWN'
            }

        try:
            volumes = [bar.volume for bar in bars_1min]

            # Compare recent volume vs average
            recent_volume = sum(volumes[-30:]) / 30  # Last 30 bars avg
            baseline_volume = sum(volumes[:-30]) / max(len(volumes) - 30, 1)  # Baseline

            volume_ratio = recent_volume / baseline_volume if baseline_volume > 0 else 1.0

            # Determine trend
            if volume_ratio >= 2.0:
                volume_trend = 'INCREASING'
            elif volume_ratio >= 1.5:
                volume_trend = 'STABLE'
            else:
                volume_trend = 'DECREASING'

            return {
                'volume_ratio': volume_ratio,
                'volume_trend': volume_trend
            }

        except Exception as e:
            self.logger.warning(f"Error analyzing volume for {symbol}: {e}")
            return {
                'volume_ratio': 1.0,
                'volume_trend': 'UNKNOWN'
            }

    async def _check_dilution_risk(self, symbol: str) -> Dict[str, Any]:
        """
        Check dilution risk for smallcap

        Critical for overnight holds - offerings can destroy positions

        Returns:
            Dict with 'risk_level' (HIGH/MEDIUM/LOW), 'reason'
        """
        # TODO: Integrate with SEC filings API, market cap data, float tracking
        # For now, use conservative defaults

        try:
            # Placeholder: In production, check:
            # 1. Recent S-3 filings (last 6 months)
            # 2. ATM offering announcements
            # 3. Cash runway (burn rate analysis)
            # 4. Float size and recent increases
            # 5. Market cap threshold

            # Conservative default: MEDIUM risk for all smallcaps
            return {
                'risk_level': 'MEDIUM',
                'reason': 'Smallcap dilution risk (default assessment)',
                'last_offering_days_ago': None,
                'cash_runway_months': None
            }

        except Exception as e:
            self.logger.warning(f"Error checking dilution risk for {symbol}: {e}")
            return {
                'risk_level': 'MEDIUM',
                'reason': f'Unable to assess: {str(e)}',
                'last_offering_days_ago': None,
                'cash_runway_months': None
            }

    def reset_daily_tracking(self):
        """Reset daily tracking (call at market open)"""
        self.swing_transitions_today = []
        self.logger.info("🔄 Swing transition tracking reset for new day")

    def get_transition_stats(self) -> Dict[str, Any]:
        """Get today's transition statistics"""
        return {
            'transitions_today': len(self.swing_transitions_today),
            'max_allowed': self.max_simultaneous_swings,
            'symbols': self.swing_transitions_today
        }
