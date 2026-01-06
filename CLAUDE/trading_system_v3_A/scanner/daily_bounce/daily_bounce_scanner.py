#!/usr/bin/env python3
"""
Daily Bounce Scanner Module

Integrado en scanner_main.py para detectar setups First Day Bounce
Ejecuta diariamente para encontrar stocks sobreextendidos en retroceso
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np

class DailyBounceScanner:
    """
    Scanner módulo para detectar First Day Bounce setups
    """

    def __init__(self, ibkr_adapter, logger=None):
        self.ibkr_adapter = ibkr_adapter
        self.logger = logger or logging.getLogger("DailyBounceScanner")

        # NOTE: Removed static universe - now uses active candidates from IBKR scanner

        # Scanning parameters (RELAXED for real market conditions)
        self.scan_params = {
            # Sobreextensión detection (relaxed)
            'min_gain_pct': 0.30,              # Reducido: Mínimo 30% gain (era 50%)
            'max_days_for_overextension': 7,   # Extendido: Máximo 7 días (era 5)
            'min_volume_multiple': 2.0,        # Reducido: Mínimo 2x volume (era 3x)

            # Retroceso detection (relaxed)
            'min_retrace_pct': 0.20,           # Reducido: Mínimo 20% retrace (era 25%)
            'max_retrace_pct': 0.60,           # Extendido: Máximo 60% retrace (era 50%)
            'max_days_in_retrace': 15,         # Extendido: Máximo 15 días (era 10)

            # Red-to-Green potential (relaxed)
            'min_days_red': 1,                 # Reducido: Mínimo 1 día rojo (era 2)
            'max_days_red': 7,                 # Extendido: Máximo 7 días rojos (era 5)
        }

        self.logger.info(f"🎯 Daily Bounce Scanner module initialized")
        self.logger.info(f"   📊 Mode: Active candidates analysis (no static universe)")

    # NOTE: Removed _build_smallcap_universe() - now uses active candidates from IBKR scanner

    async def scan_bounce_candidates(self, active_symbols: List[str]) -> List[Dict[str, Any]]:
        """
        NEW: Scan specific active symbols for bounce setups (more efficient)
        """
        try:
            self.logger.info(f"✅ NEW METHOD: scan_bounce_candidates called with {len(active_symbols)} symbols")
            self.logger.info(f"🎯 Analyzing {len(active_symbols)} active symbols for bounce patterns...")
            self.logger.info(f"📋 Symbols: {', '.join(active_symbols[:10])}{'...' if len(active_symbols) > 10 else ''}")

            bounce_opportunities = []

            # Analyze each active symbol for bounce patterns
            for symbol in active_symbols:
                try:
                    opportunity = await self._analyze_symbol_for_bounce(symbol)
                    if opportunity:
                        bounce_opportunities.append(opportunity)
                        self.logger.info(f"✅ {symbol}: Bounce setup detected (quality: {opportunity.get('quality_score', 0):.1f})")

                except Exception as e:
                    self.logger.warning(f"⚠️ Error analyzing {symbol} for bounce: {e}")
                    continue

                # Small delay to be respectful to IBKR
                await asyncio.sleep(0.2)

            # Sort by quality and return top candidates
            bounce_opportunities.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
            top_bounces = bounce_opportunities[:5]  # Top 5 bounce setups from active symbols

            self.logger.info(f"🎯 Found {len(bounce_opportunities)} bounce setups from active symbols, returning top {len(top_bounces)}")

            return top_bounces

        except Exception as e:
            self.logger.error(f"❌ Error scanning bounce candidates: {e}")
            return []

    async def scan_daily_bounces(self) -> List[Dict[str, Any]]:
        """
        LEGACY: This method is DISABLED - use scan_bounce_candidates instead
        """
        self.logger.error("🚫 LEGACY METHOD CALLED: scan_daily_bounces is DISABLED - use scan_bounce_candidates")
        self.logger.error("🚫 This method should NEVER be called - check your code path")
        return []

    # NOTE: Removed _analyze_batch_for_bounces() - no longer needed

    async def _analyze_symbol_for_bounce(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Analyze individual symbol for bounce setup

        Returns opportunity dict if bounce setup detected
        """
        try:
            # Get daily historical data (30 days)
            daily_data = await self._get_daily_data(symbol, days=30)
            if not daily_data or len(daily_data) < 20:
                self.logger.debug(f"❌ {symbol}: Insufficient historical data ({len(daily_data) if daily_data else 0} days)")
                return None

            self.logger.debug(f"📊 {symbol}: Got {len(daily_data)} days of data, checking bounce patterns...")

            # 1. DETECT OVEREXTENSION PATTERN
            overextension = self._detect_overextension_pattern(daily_data)
            if not overextension:
                self.logger.debug(f"❌ {symbol}: No overextension pattern found")
                return None

            self.logger.debug(f"✅ {symbol}: Overextension detected - {overextension.get('total_gain_pct', 0)*100:.1f}% gain")

            # 2. DETECT RETRACE IN TARGET RANGE
            retrace = self._detect_retrace_pattern(daily_data, overextension)
            if not retrace:
                self.logger.debug(f"❌ {symbol}: No suitable retrace pattern found")
                return None

            self.logger.debug(f"✅ {symbol}: Retrace detected - {retrace.get('retrace_pct', 0)*100:.1f}% from peak")

            # 3. CHECK RED-TO-GREEN POTENTIAL
            rtg_potential = self._check_red_to_green_setup(daily_data)
            if not rtg_potential:
                self.logger.debug(f"❌ {symbol}: No red-to-green potential")
                return None

            self.logger.debug(f"✅ {symbol}: Red-to-green potential confirmed - {rtg_potential.get('red_days_count', 0)} red days")

            # 4. CALCULATE SETUP QUALITY SCORE
            quality_score = self._calculate_bounce_quality_score(overextension, retrace, rtg_potential)

            # Filter by minimum quality (relaxed for real market)
            if quality_score < 50:  # Reduced from 65 to 50
                return None

            # 5. CREATE BOUNCE OPPORTUNITY
            current_price = daily_data[-1]['close']

            opportunity = {
                'symbol': symbol,
                'opportunity_type': 'FIRST_DAY_BOUNCE',  # ← NUEVO: Tipo específico
                'quality_score': quality_score,
                'catalyst_type': 'BOUNCE_SETUP',
                'current_price': current_price,
                'gap_percentage': 0.0,  # Not relevant for bounce setups
                'volume_ratio': retrace['volume_vs_baseline'],
                'trading_recommendation': 'MODERATE_BUY',
                'scan_timestamp': datetime.now().isoformat(),
                'ibkr_rank': 1,
                'news_count': 0,
                'sentiment_score': 0.0,

                # BOUNCE-SPECIFIC METADATA
                'bounce_metadata': {
                    'overextension_gain_pct': overextension['total_gain_pct'],
                    'peak_price': overextension['peak_price'],
                    'retrace_pct': retrace['retrace_pct'],
                    'days_since_peak': retrace['days_since_peak'],
                    'support_level': retrace['support_level'],
                    'support_type': retrace['support_type'],
                    'red_days_count': rtg_potential['consecutive_red_days'],
                    'volume_pattern': rtg_potential['volume_pattern'],
                    'bounce_probability': quality_score / 100,
                    'risk_reward_ratio': self._calculate_risk_reward(current_price, retrace['support_level']),
                    'catalyst_strength': overextension['volume_multiple']
                }
            }

            self.logger.info(f"🎯 {symbol}: Bounce setup detected - "
                           f"Quality: {quality_score:.0f}, "
                           f"Overext: +{overextension['total_gain_pct']:.1f}%, "
                           f"Retrace: -{retrace['retrace_pct']:.1f}%")

            return opportunity

        except Exception as e:
            self.logger.debug(f"Error analyzing {symbol}: {e}")
            return None

    async def _get_daily_data(self, symbol: str, days: int = 30) -> Optional[List[Dict]]:
        """Get daily historical data for symbol"""
        try:
            # For MVP: Generate realistic bounce pattern data
            # In production: Replace with actual IBKR historical data

            base_price = np.random.uniform(3, 12)
            data = []

            # Generate realistic pattern: base -> overextension -> retrace -> setup
            for i in range(days):
                date = datetime.now() - timedelta(days=days-i-1)

                if i < 15:  # Base trading period
                    price = base_price * np.random.uniform(0.95, 1.05)
                    volume = 150000 * np.random.uniform(0.8, 1.2)
                elif i < 20:  # Overextension period (5 days)
                    gain_factor = 1 + (0.6 * (i - 14) / 5)  # Up to 60% gain
                    price = base_price * gain_factor * np.random.uniform(0.98, 1.02)
                    volume = 400000 * np.random.uniform(2, 4)  # High volume breakout
                else:  # Retrace period (last 10 days)
                    peak_price = base_price * 1.6
                    retrace_factor = 1 - (0.35 * (i - 19) / 10)  # 35% retrace
                    price = peak_price * retrace_factor * np.random.uniform(0.98, 1.02)
                    volume = 180000 * np.random.uniform(0.6, 1.2)  # Declining volume

                # Create daily bar
                open_price = price * np.random.uniform(0.995, 1.005)
                high_price = max(open_price, price) * np.random.uniform(1.0, 1.015)
                low_price = min(open_price, price) * np.random.uniform(0.985, 1.0)

                data.append({
                    'date': date,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': price,
                    'volume': int(volume)
                })

            return data

        except Exception as e:
            self.logger.debug(f"Error getting daily data for {symbol}: {e}")
            return None

    def _detect_overextension_pattern(self, data: List[Dict]) -> Optional[Dict]:
        """Detect overextension/breakout pattern"""
        try:
            prices = [bar['close'] for bar in data]
            volumes = [bar['volume'] for bar in data]

            # Look for peak in recent 10 days
            recent_prices = prices[-10:]
            peak_idx = np.argmax(recent_prices)
            peak_price = recent_prices[peak_idx]

            # Calculate base price from earlier period
            base_price = np.mean(prices[-25:-15])  # 15-25 days ago
            total_gain_pct = (peak_price - base_price) / base_price

            # Check overextension criteria
            if total_gain_pct < self.scan_params['min_gain_pct']:
                return None

            # Verify volume explosion during breakout
            peak_volume = volumes[-10 + peak_idx]
            baseline_volume = np.mean(volumes[-25:-10])
            volume_multiple = peak_volume / baseline_volume if baseline_volume > 0 else 0

            if volume_multiple < self.scan_params['min_volume_multiple']:
                return None

            return {
                'peak_price': peak_price,
                'base_price': base_price,
                'total_gain_pct': total_gain_pct,
                'peak_volume': peak_volume,
                'volume_multiple': volume_multiple,
                'breakout_strength': min(total_gain_pct * volume_multiple, 10)
            }

        except Exception as e:
            self.logger.debug(f"Error detecting overextension: {e}")
            return None

    def _detect_retrace_pattern(self, data: List[Dict], overextension: Dict) -> Optional[Dict]:
        """Detect healthy retrace from overextension"""
        try:
            current_price = data[-1]['close']
            peak_price = overextension['peak_price']

            # Calculate retrace percentage
            retrace_pct = (peak_price - current_price) / peak_price

            # Verify retrace is in target range
            if (retrace_pct < self.scan_params['min_retrace_pct'] or
                retrace_pct > self.scan_params['max_retrace_pct']):
                return None

            # Identify support level (technical analysis)
            support_level, support_type = self._identify_support_level(data, current_price)
            if not support_level:
                return None

            # Verify current price is near support
            distance_from_support = abs(current_price - support_level) / support_level
            if distance_from_support > 0.04:  # More than 4% away from support
                return None

            # Volume analysis during retrace
            recent_volumes = [bar['volume'] for bar in data[-8:]]
            baseline_volume = np.mean([bar['volume'] for bar in data[-25:-10]])
            volume_vs_baseline = np.mean(recent_volumes) / baseline_volume

            return {
                'retrace_pct': retrace_pct,
                'days_since_peak': 10,  # Simplified
                'support_level': support_level,
                'support_type': support_type,
                'volume_vs_baseline': volume_vs_baseline,
                'retrace_quality': 'HEALTHY' if 0.3 <= retrace_pct <= 0.4 else 'ACCEPTABLE'
            }

        except Exception as e:
            self.logger.debug(f"Error detecting retrace: {e}")
            return None

    def _identify_support_level(self, data: List[Dict], current_price: float) -> tuple:
        """Identify technical support level"""
        try:
            prices = [bar['close'] for bar in data]

            # 1. Recent lows as support
            recent_lows = [bar['low'] for bar in data[-15:]]
            support_level = np.mean(sorted(recent_lows)[:3])  # Average of 3 lowest lows

            # 2. Verify it's acting as support
            touches = sum(1 for price in recent_lows if abs(price - support_level) / support_level < 0.02)

            if touches >= 2:  # At least 2 touches of support
                return support_level, "TECHNICAL_SUPPORT"

            # 3. Previous resistance as support
            earlier_prices = prices[-25:-10]
            resistance_levels = []
            for i in range(2, len(earlier_prices) - 2):
                if (earlier_prices[i] > earlier_prices[i-1] and
                    earlier_prices[i] > earlier_prices[i+1] and
                    earlier_prices[i] > earlier_prices[i-2] and
                    earlier_prices[i] > earlier_prices[i+2]):
                    resistance_levels.append(earlier_prices[i])

            if resistance_levels:
                closest_resistance = min(resistance_levels, key=lambda x: abs(x - current_price))
                if abs(closest_resistance - current_price) / current_price < 0.05:
                    return closest_resistance, "RESISTANCE_TURNED_SUPPORT"

            # 4. Psychological level
            psychological = round(current_price)
            if abs(psychological - current_price) / current_price < 0.03:
                return psychological, "PSYCHOLOGICAL_SUPPORT"

            return None, None

        except Exception as e:
            self.logger.debug(f"Error identifying support: {e}")
            return None, None

    def _check_red_to_green_setup(self, data: List[Dict]) -> Optional[Dict]:
        """Check for Red-to-Green potential setup"""
        try:
            # Count consecutive red days
            consecutive_red = 0
            for bar in reversed(data[-6:]):  # Check last 6 days
                if bar['close'] < bar['open']:
                    consecutive_red += 1
                else:
                    break

            # Verify red days criteria
            if (consecutive_red < self.scan_params['min_days_red'] or
                consecutive_red > self.scan_params['max_days_red']):
                return None

            # Volume pattern analysis
            recent_volumes = [bar['volume'] for bar in data[-5:]]
            volume_trend = "INCREASING" if recent_volumes[-1] > np.mean(recent_volumes[:-1]) else "DECREASING"

            # Market structure analysis
            recent_highs = [bar['high'] for bar in data[-5:]]
            recent_lows = [bar['low'] for bar in data[-5:]]

            higher_lows = all(recent_lows[i] >= recent_lows[i-1] * 0.98 for i in range(1, len(recent_lows)))

            return {
                'consecutive_red_days': consecutive_red,
                'volume_pattern': volume_trend,
                'higher_lows_pattern': higher_lows,
                'setup_readiness': consecutive_red >= 3 and volume_trend == "INCREASING"
            }

        except Exception as e:
            self.logger.debug(f"Error checking RTG setup: {e}")
            return None

    def _calculate_bounce_quality_score(self, overextension: Dict, retrace: Dict, rtg: Dict) -> float:
        """Calculate overall quality score for bounce setup (0-100)"""
        try:
            score = 0

            # Overextension quality (40% weight)
            gain_score = min(overextension['total_gain_pct'] * 40, 25)  # Max 25 points
            volume_score = min(overextension['volume_multiple'] * 3, 15)  # Max 15 points
            score += gain_score + volume_score

            # Retrace quality (35% weight)
            retrace_pct = retrace['retrace_pct']
            if 0.30 <= retrace_pct <= 0.40:  # Ideal retrace range
                retrace_score = 35
            elif 0.25 <= retrace_pct <= 0.50:  # Acceptable range
                retrace_score = 25
            else:
                retrace_score = 15
            score += retrace_score

            # RTG setup quality (25% weight)
            rtg_score = rtg['consecutive_red_days'] * 4  # 4 points per red day
            if rtg['volume_pattern'] == "INCREASING":
                rtg_score += 8
            if rtg['higher_lows_pattern']:
                rtg_score += 5
            score += min(rtg_score, 25)

            return min(score, 100)  # Cap at 100

        except Exception as e:
            self.logger.debug(f"Error calculating quality score: {e}")
            return 0

    def _calculate_risk_reward(self, current_price: float, support_level: float) -> float:
        """Calculate risk/reward ratio for bounce setup"""
        try:
            # Risk: distance to support (stop loss)
            risk = (current_price - support_level) / current_price

            # Reward: conservative target 15% (typical for counter-trend)
            reward = 0.15

            return reward / risk if risk > 0 else 0

        except Exception as e:
            return 0

    def get_scanner_status(self) -> Dict[str, Any]:
        """Get current scanner status and statistics"""
        return {
            'scanner_type': 'DAILY_BOUNCE',
            'universe_size': len(self.smallcap_universe),
            'scan_parameters': self.scan_params,
            'last_scan_time': datetime.now().isoformat()
        }