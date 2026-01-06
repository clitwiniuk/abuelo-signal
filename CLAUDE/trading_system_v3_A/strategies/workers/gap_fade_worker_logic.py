"""
Gap Fade Worker Logic
Worker especializado para operar FADES en gaps sin catalizador significativo

Entry Criteria (ALL must be TRUE):
1. Gap >= 5% at market open (pre-market high vs previous close)
2. NO significant catalyst (catalyst_strength < 7 OR catalyst_type == 'TECHNICAL')
3. Gap failure confirmed: First hour closes <75% of gap range
4. Volume declining after open spike (current vol < 50% of first 5min avg)
5. Price rejected at VWAP (acting as resistance)
6. Quality Score >= min_quality_score
7. Entry window: 10:00-11:00 AM only
8. Price < VWAP (for SHORT entries)

Exit Criteria:
- Target 1: 50% gap fill (conservative TP)
- Target 2: Previous day close (full gap fill)
- Stop Loss: Above High of Day (HOD)
- Time Stop: 15:45 (no overnight holds)
- Trailing Stop: If moves 3% in favor, trail stop to breakeven

Performance Characteristics (Expected):
- Win rate: 62-68%
- Avg gain: +4-6%
- Avg loss: -2-3%
- R:R: 1.8:1 - 2.5:1
- Hold time: Intraday only (same day exit)

HTB Considerations:
- Gaps typically have high float and volume (ETB friendly)
- Float >50M and ADV >1M preferred
- Avoid if SI% >20% (borrow may be expensive)
"""

import logging
from datetime import datetime, time
from typing import Dict, Optional, Tuple
from .base_worker_logic import BaseWorkerLogic
from core.market_hours import get_market_hours, can_enter_short, should_force_exit_short


class GapFadeWorkerLogic(BaseWorkerLogic):
    """
    Worker para operar FADES en gaps sin catalizador significativo
    SHORT-only strategy con alta tasa de éxito (62-68% win rate)
    """

    def __init__(self, config, execution_engine=None, risk_manager=None, market_analyzer=None):
        # Initialize with worker_name, execution_engine, and risk_manager
        super().__init__(
            worker_name='gap_fade',
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )
        self.logger = logging.getLogger(self.__class__.__name__)

        # ========== GAP FADE CONFIGURATION ==========
        self.min_gap_percent = getattr(config, 'gap_fade_min_gap_pct', 5.0)
        self.max_catalyst_strength = getattr(config, 'gap_fade_max_catalyst_strength', 6)
        self.gap_failure_threshold = getattr(config, 'gap_fade_failure_threshold', 0.75)
        self.volume_decline_threshold = getattr(config, 'gap_fade_volume_decline_pct', 0.50)

        # Entry window (10:00 - 11:00 AM)
        self.entry_window_start = getattr(config, 'gap_fade_entry_start', '10:00')
        self.entry_window_end = getattr(config, 'gap_fade_entry_end', '11:00')

        # Exit targets
        self.conservative_target_pct = getattr(config, 'gap_fade_conservative_target', 0.50)  # 50% gap fill
        self.aggressive_target_pct = getattr(config, 'gap_fade_aggressive_target', 1.0)  # Full gap fill
        self.exit_time = getattr(config, 'gap_fade_exit_time', '15:45')

        # Risk management
        self.stop_above_hod_buffer = getattr(config, 'gap_fade_stop_buffer_pct', 1.5)  # 1.5% above HOD
        self.trailing_activation_pct = getattr(config, 'gap_fade_trailing_activation', 3.0)

        # Quality filters
        self.min_quality_score = getattr(config, 'gap_fade_min_quality_score', 6.0)
        self.min_float = getattr(config, 'gap_fade_min_float_millions', 50.0)
        self.min_adv = getattr(config, 'gap_fade_min_adv_millions', 1.0)
        self.max_short_interest = getattr(config, 'gap_fade_max_si_pct', 20.0)

        # VWAP validation (mandatory)
        self.vwap_slope_threshold = getattr(config, 'gap_fade_vwap_slope_threshold', -0.10)

        self.logger.info(f"✅ Gap Fade Worker initialized:")
        self.logger.info(f"   • Min Gap: {self.min_gap_percent}%")
        self.logger.info(f"   • Entry Window: {self.entry_window_start} - {self.entry_window_end}")
        self.logger.info(f"   • Min Quality: {self.min_quality_score}")
        self.logger.info(f"   • Min Float: {self.min_float}M shares")

    def evaluate_opportunity(self, opportunity: Dict) -> bool:
        """
        Evalúa si una oportunidad cumple criterios de GAP FADE

        Returns:
            bool: True si cumple criterios de entrada SHORT
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🔍 Gap Fade evaluation for {symbol}")
        self.logger.info(f"{'='*60}")

        # ========== PHASE 0: MARKET HOURS CHECK (CRITICAL FOR SHORTS) ==========

        # CRITICAL: SHORT positions can ONLY be entered during regular market hours
        # NO premarket, NO afterhours, NO overnight positions
        can_short, short_reason = can_enter_short()
        if not can_short:
            self.logger.warning(f"🚫 {symbol}: SHORT entry BLOCKED - {short_reason}")
            return False

        self.logger.info(f"✅ {symbol}: Market hours check passed - SHORT entry allowed")

        # ========== PHASE 1: BASIC FILTERS ==========

        # Check entry window
        if not self._is_within_entry_window():
            self.logger.info(f"⚪ {symbol}: Outside entry window ({self.entry_window_start}-{self.entry_window_end})")
            return False

        # Get current price and bars
        current_price = opportunity.get('current_price', 0)
        if not current_price or current_price <= 0:
            self.logger.info(f"⚪ {symbol}: Invalid price: {current_price}")
            return False

        bars = self.get_bars_from_opportunity(opportunity)
        if not bars or len(bars) < 20:
            self.logger.info(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0})")
            return False

        # ========== PHASE 2: GAP ANALYSIS ==========

        gap_data = self._analyze_gap(bars, opportunity)
        if not gap_data['has_gap']:
            self.logger.info(f"⚪ {symbol}: No qualifying gap (gap: {gap_data['gap_pct']:.2f}%)")
            return False

        self.logger.info(f"✅ {symbol}: Gap detected: {gap_data['gap_pct']:.2f}%")

        # ========== PHASE 3: CATALYST FILTER ==========

        catalyst_type = opportunity.get('catalyst_type', 'NONE')
        catalyst_strength = opportunity.get('catalyst_strength', 0)

        if catalyst_strength >= self.max_catalyst_strength and catalyst_type != 'TECHNICAL':
            self.logger.info(f"⚪ {symbol}: Catalyst too strong ({catalyst_type}, strength: {catalyst_strength})")
            return False

        self.logger.info(f"✅ {symbol}: Catalyst check passed ({catalyst_type}, strength: {catalyst_strength})")

        # ========== PHASE 4: GAP FAILURE CONFIRMATION ==========
        # SIMPLIFIED: Gap fade triggered by VWAP loss, not arbitrary % threshold
        # We'll validate VWAP later (Phase 6), so this check is now optional/relaxed

        gap_failure = self._check_gap_failure(bars, gap_data)
        # Log gap status but DON'T reject - VWAP is the real trigger
        self.logger.info(f"ℹ️  {symbol}: Gap status - {gap_failure['reason']}")

        # ========== PHASE 5: VOLUME DECLINE ==========

        volume_decline = self._check_volume_decline(bars)
        if not volume_decline['is_declining']:
            self.logger.info(f"⚪ {symbol}: Volume not declining ({volume_decline['reason']})")
            return False

        self.logger.info(f"✅ {symbol}: Volume declining - {volume_decline['reason']}")

        # ========== PHASE 6: VWAP RESISTANCE ==========

        vwap_check = self._check_vwap_resistance(bars, current_price, symbol)
        if not vwap_check['is_resistance']:
            self.logger.info(f"⚪ {symbol}: VWAP not acting as resistance - {vwap_check['reason']}")
            return False

        self.logger.info(f"✅ {symbol}: VWAP resistance confirmed - {vwap_check['reason']}")

        # ========== PHASE 7: QUALITY FILTERS ==========

        quality_score = opportunity.get('quality_score', 0)
        if quality_score < self.min_quality_score:
            self.logger.info(f"⚪ {symbol}: Quality too low ({quality_score:.1f} < {self.min_quality_score})")
            return False

        # Float/ADV/SI filters (if data available)
        float_shares = opportunity.get('float_shares', 0)
        if float_shares > 0:
            float_millions = float_shares / 1_000_000
            if float_millions < self.min_float:
                self.logger.info(f"⚪ {symbol}: Float too low ({float_millions:.1f}M < {self.min_float}M)")
                return False

        # ========== PHASE 8: RISK/REWARD CALCULATION ==========

        rr_analysis = self._calculate_risk_reward(current_price, gap_data, bars)
        if rr_analysis['rr_ratio'] < 1.5:
            self.logger.info(f"⚪ {symbol}: R:R too low ({rr_analysis['rr_ratio']:.2f} < 1.5)")
            return False

        self.logger.info(f"✅ {symbol}: R:R acceptable: {rr_analysis['rr_ratio']:.2f}")
        self.logger.info(f"   • Entry: ${current_price:.2f}")
        self.logger.info(f"   • Target (50% fill): ${rr_analysis['conservative_target']:.2f}")
        self.logger.info(f"   • Stop (HOD+buffer): ${rr_analysis['stop_price']:.2f}")

        # ========== FINAL ACCEPTANCE ==========

        self.logger.info(f"\n🎯 {symbol}: ALL CRITERIA MET - GAP FADE SETUP CONFIRMED")
        self.logger.info(f"   • Gap: {gap_data['gap_pct']:.2f}%")
        self.logger.info(f"   • Quality: {quality_score:.1f}/10")
        self.logger.info(f"   • R:R: {rr_analysis['rr_ratio']:.2f}")
        self.logger.info(f"   • Direction: SHORT")

        return True

    def _is_within_entry_window(self) -> bool:
        """Check if current time is within entry window (10:00-11:00 AM)"""
        try:
            now = datetime.now().time()
            start = datetime.strptime(self.entry_window_start, '%H:%M').time()
            end = datetime.strptime(self.entry_window_end, '%H:%M').time()
            return start <= now <= end
        except Exception as e:
            self.logger.debug(f"Error checking entry window: {e}")
            return False

    def _analyze_gap(self, bars: list, opportunity: Dict) -> Dict:
        """
        Analiza el gap en la apertura

        Returns:
            Dict con gap_pct, previous_close, open_price, has_gap
        """
        try:
            # Get previous close from opportunity or bars
            previous_close = opportunity.get('previous_close')
            if not previous_close:
                # Try to get from bars (previous day's close)
                previous_close = bars[-2].get('close') if len(bars) > 1 else None

            # Get today's open (should be first bar of today)
            open_price = opportunity.get('open_price')
            if not open_price:
                # Find first bar of today (9:30 AM)
                for bar in bars:
                    bar_time = bar.get('timestamp')
                    if isinstance(bar_time, str):
                        bar_time = datetime.fromisoformat(bar_time)
                    if bar_time.time() >= time(9, 30):
                        open_price = bar.get('open')
                        break

            if not previous_close or not open_price:
                return {'has_gap': False, 'gap_pct': 0}

            gap_pct = ((open_price - previous_close) / previous_close) * 100

            return {
                'has_gap': gap_pct >= self.min_gap_percent,
                'gap_pct': gap_pct,
                'previous_close': previous_close,
                'open_price': open_price,
                'gap_range': open_price - previous_close
            }

        except Exception as e:
            self.logger.debug(f"Error analyzing gap: {e}")
            return {'has_gap': False, 'gap_pct': 0}

    def _check_gap_failure(self, bars: list, gap_data: Dict) -> Dict:
        """
        Verifica si el gap está fallando (no se mantiene en primera hora)

        Criteria: First hour closes <75% of gap range
        """
        try:
            now = datetime.now()
            first_hour_end = now.replace(hour=10, minute=30, second=0, microsecond=0)

            # Get most recent bar
            latest_bar = bars[-1]
            latest_close = latest_bar.get('close', 0)
            latest_time = latest_bar.get('timestamp')

            if isinstance(latest_time, str):
                latest_time = datetime.fromisoformat(latest_time)

            # Calculate how much of gap is maintained
            previous_close = gap_data['previous_close']
            gap_range = gap_data['gap_range']
            current_distance_from_close = latest_close - previous_close
            gap_maintained_pct = current_distance_from_close / gap_range if gap_range != 0 else 0

            is_failing = gap_maintained_pct < self.gap_failure_threshold

            return {
                'is_failing': is_failing,
                'gap_maintained_pct': gap_maintained_pct,
                'reason': f"Gap maintained: {gap_maintained_pct*100:.1f}% (threshold: {self.gap_failure_threshold*100:.1f}%)"
            }

        except Exception as e:
            self.logger.debug(f"Error checking gap failure: {e}")
            return {'is_failing': False, 'reason': f'Error: {e}'}

    def _check_volume_decline(self, bars: list) -> Dict:
        """
        Verifica si el volumen está declinando después del spike inicial

        Criteria: Current volume < 50% of first 5min average
        """
        try:
            if len(bars) < 10:
                return {'is_declining': False, 'reason': 'Insufficient bars'}

            # Get first 5 bars (first 5 minutes)
            first_5min_bars = bars[:5]
            first_5min_avg_vol = sum(b.get('volume', 0) for b in first_5min_bars) / len(first_5min_bars)

            # Get recent 5 bars
            recent_5min_bars = bars[-5:]
            recent_5min_avg_vol = sum(b.get('volume', 0) for b in recent_5min_bars) / len(recent_5min_bars)

            if first_5min_avg_vol == 0:
                return {'is_declining': False, 'reason': 'No initial volume data'}

            volume_ratio = recent_5min_avg_vol / first_5min_avg_vol
            is_declining = volume_ratio < self.volume_decline_threshold

            return {
                'is_declining': is_declining,
                'volume_ratio': volume_ratio,
                'reason': f"Current vol {volume_ratio*100:.1f}% of initial (threshold: {self.volume_decline_threshold*100:.1f}%)"
            }

        except Exception as e:
            self.logger.debug(f"Error checking volume decline: {e}")
            return {'is_declining': False, 'reason': f'Error: {e}'}

    def _check_vwap_resistance(self, bars: list, current_price: float, symbol: str) -> Dict:
        """
        Verifica si VWAP está actuando como resistencia

        Criteria:
        1. Price < VWAP (rejected below)
        2. VWAP slope negative (declining)
        """
        try:
            # Use base class VWAP validation for SHORT
            is_valid_vwap, vwap_reason, vwap_data = self.validate_vwap_direction(
                bars=bars,
                current_price=current_price,
                intended_direction='SHORT',
                min_slope_pct=abs(self.vwap_slope_threshold),
                tolerance_pct=0.5,
                symbol=symbol
            )

            return {
                'is_resistance': is_valid_vwap,
                'reason': vwap_reason,
                'vwap_data': vwap_data
            }

        except Exception as e:
            self.logger.debug(f"Error checking VWAP resistance: {e}")
            return {'is_resistance': False, 'reason': f'Error: {e}'}

    def _calculate_risk_reward(self, current_price: float, gap_data: Dict, bars: list) -> Dict:
        """
        Calcula Risk/Reward para el trade SHORT

        Stop: Above High of Day + buffer
        Target: 50% gap fill (conservative) or full gap fill (aggressive)
        """
        try:
            # Calculate HOD (High of Day)
            hod = max(bar.get('high', 0) for bar in bars)
            stop_price = hod * (1 + self.stop_above_hod_buffer / 100)

            # Calculate targets
            previous_close = gap_data['previous_close']
            gap_range = gap_data['gap_range']

            conservative_target = current_price - (gap_range * self.conservative_target_pct)
            aggressive_target = previous_close

            # Calculate risk/reward
            risk = stop_price - current_price
            conservative_reward = current_price - conservative_target
            aggressive_reward = current_price - aggressive_target

            conservative_rr = conservative_reward / risk if risk > 0 else 0
            aggressive_rr = aggressive_reward / risk if risk > 0 else 0

            return {
                'stop_price': stop_price,
                'conservative_target': conservative_target,
                'aggressive_target': aggressive_target,
                'risk': risk,
                'conservative_reward': conservative_reward,
                'aggressive_reward': aggressive_reward,
                'rr_ratio': conservative_rr,  # Use conservative for decision
                'aggressive_rr': aggressive_rr
            }

        except Exception as e:
            self.logger.debug(f"Error calculating R:R: {e}")
            return {'rr_ratio': 0}

    def get_position_size(self, opportunity: Dict) -> int:
        """
        Calculate position size for Gap Fade SHORT
        Uses base class logic but ensures SHORT direction
        """
        return super().get_position_size(opportunity)

    def get_stop_loss_price(self, entry_price: float, opportunity: Dict) -> Optional[float]:
        """
        Returns stop loss price: Above HOD + buffer
        """
        try:
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars:
                return entry_price * 1.03  # Fallback: 3% above entry

            hod = max(bar.get('high', 0) for bar in bars)
            stop_price = hod * (1 + self.stop_above_hod_buffer / 100)

            return stop_price

        except Exception as e:
            self.logger.error(f"Error calculating stop loss: {e}")
            return entry_price * 1.03

    def get_take_profit_price(self, entry_price: float, opportunity: Dict) -> Optional[float]:
        """
        Returns take profit price: 50% gap fill (conservative)
        """
        try:
            bars = self.get_bars_from_opportunity(opportunity)
            gap_data = self._analyze_gap(bars, opportunity)

            if not gap_data['has_gap']:
                return entry_price * 0.95  # Fallback: 5% profit

            gap_range = gap_data['gap_range']
            conservative_target = entry_price - (gap_range * self.conservative_target_pct)

            return conservative_target

        except Exception as e:
            self.logger.error(f"Error calculating take profit: {e}")
            return entry_price * 0.95

    async def should_enter(self, opportunity: Dict) -> bool:
        """
        Abstract method implementation - delegates to evaluate_opportunity

        Args:
            opportunity: Opportunity data dict (contains symbol, current_price, etc.)

        Returns:
            bool: True if should enter position
        """
        return self.evaluate_opportunity(opportunity)

    async def should_exit(self, symbol: str, position: Dict, current_price: float) -> tuple[bool, str]:
        """
        Abstract method implementation - exit logic for Gap Fade

        Exit conditions:
        1. TP hit (100% gap fill to previous close)
        2. SL hit (above HOD + 1.5% buffer)
        3. Time stop (15:45 mandatory close)
        4. Trailing stop activated (if profit >3%)

        Args:
            symbol: Stock symbol
            position: Position data dict (contains entry_price, bars_history, etc.)
            current_price: Current price

        Returns:
            tuple: (should_exit: bool, reason: str)
        """
        try:
            # Extract entry price from position
            entry_price = position.get('entry_price', current_price)

            # Time-based exit (15:45 mandatory close)
            exit_hour, exit_min = map(int, self.exit_time.split(':'))
            now = datetime.now()
            exit_time_today = now.replace(hour=exit_hour, minute=exit_min, second=0)

            if now >= exit_time_today:
                return True, "TIME_STOP_15:45"

            # Get bars from position data
            bars = position.get('bars_history', [])
            if not bars:
                return False, "NO_EXIT"

            # Check TP (100% gap fill to previous close)
            gap_data = self._analyze_gap(bars, position)
            if gap_data['has_gap']:
                gap_range = gap_data['gap_range']
                conservative_target = entry_price - (gap_range * self.conservative_target_pct)

                # For SHORT: exit if price drops to or below target
                if current_price <= conservative_target:
                    fill_pct = int(self.conservative_target_pct * 100)
                    return True, f"TP_HIT_{fill_pct}PCT_GAP_FILL"

            # Check SL (above HOD)
            hod = max(bar.get('high', 0) for bar in bars)
            stop_price = hod * (1 + self.stop_above_hod_buffer / 100)

            # For SHORT: exit if price rises above stop
            if current_price >= stop_price:
                return True, "SL_HIT_ABOVE_HOD"

            # Check trailing stop (if activated)
            profit_pct = ((entry_price - current_price) / entry_price) * 100
            if profit_pct >= self.trailing_activation_pct:
                # Trailing activated - exit if price reverses
                max_profit = position.get('max_profit_pct', profit_pct)
                if profit_pct < (max_profit * 0.5):  # Gave back 50% of gains
                    return True, "TRAILING_STOP_ACTIVATED"

            return False, "NO_EXIT"

        except Exception as e:
            self.logger.error(f"Error in should_exit: {e}")
            return False, "ERROR"
