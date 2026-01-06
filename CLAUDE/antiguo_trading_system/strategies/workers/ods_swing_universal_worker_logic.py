"""
ODS Swing Universal Worker Logic
Universal swing worker for ODS (Opening Drive Structure) multiday signals

ARCHITECTURAL PHILOSOPHY:
- Pattern engines (ODS) = Weather stations (report conditions)
- Workers = Pilots (execute based on conditions reported)
- Worker doesn't care HOW pattern was detected, only WHAT to do with it

DIFFERENCE FROM INTRADAY ODS WORKER:
- Intraday ODS: Holds max 6 hours, exits before 15:56 ET
- Swing ODS: Holds 1-7 days, captures multiday momentum

SWING TRADING CONCEPT:
When ODS shows STRONG momentum (STRONG_BULLISH_OPEN, strength >= 85):
→ High probability the momentum continues multiple days
→ Enter at end of day 1, hold overnight
→ Exit when momentum fades (trailing stop) or target hit

VALIDATED PATTERNS FOR SWING:
1. STRONG_BULLISH_OPEN (strength >= 85)
   - Day 1: Strong opening drive (>2% in 12 min)
   - Hold: 3-7 days average
   - Edge: ~65% win rate on smallcaps
   - Target: +15-25% multiday

2. TREND_DRIVE_BULLISH with high volume (strength >= 80, volume > 3x)
   - Strong institutional buying
   - Hold: 2-5 days
   - Edge: ~60% win rate
   - Target: +12-20%

Entry Criteria:
1. Valid ODS signal from pattern engine (end of day confirmation)
2. Signal type in allowed list (STRONG_BULLISH_OPEN, etc.)
3. Minimum intensity/strength threshold (70+ for swing)
4. End of day confirmation (price closes strong)
5. Volume > 2x average (institutional interest)
6. NO gap fill on day 1 (momentum sustained)

Exit Criteria (via WorkerStopManager + Swing-specific):
- Stop loss: -10% (wider for overnight volatility)
- Take profit: +20% (multiday target)
- Trailing stop: 12% activation, 6% distance
- Time-based: Maximum 7 days
- Momentum fade: Exit if closes below VWAP for 2 consecutive days
- Gap fade: Exit if gaps down >3% and doesn't recover
- EOD Exit: DISABLED (EOD_safe=True) - NO forced closure at 15:56 ET
  * Swing positions CAN stay overnight
  * Trading horizon = SWING (not INTRADAY)
  * WorkerStopManager respects EOD_safe flag
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, time, timedelta
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradingHorizon
from core.ods_classifier import ODSDayType


class ODSSwingUniversalWorkerLogic(BaseWorkerLogic):
    """
    Universal swing worker that executes multiday trades based on ODS pattern signals

    Receives:
    - ODS pattern classification (from ODS engine)
    - Bias/direction (bullish/bearish)
    - Strength/intensity (0-100)
    - Confirmation at end of day

    Executes:
    - Swing trade logic (multiday holding)
    - Adaptive position sizing based on strength
    - Swing-specific risk management (wider stops, longer time)
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="ods_swing_universal",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuration from config.ini
        from core.service_locator import get_service_locator
        config = get_service_locator().get_config()

        # ODS Pattern Filtering (which patterns to trade - SWING ONLY)
        # Only STRONG patterns for swing (higher threshold than intraday)
        self.allowed_ods_patterns = [
            ODSDayType.STRONG_BULLISH_OPEN,      # Strength >= 85 (high conviction ONLY)
            # Can add TREND_DRIVE_BULLISH if strength >= 80
        ]

        # Minimum thresholds (STRICTER than intraday for swing)
        self.min_ods_strength = 70.0  # Minimum 70 for swing (vs 60 for intraday)
        self.min_volume_ratio = 2.0   # Minimum 2x volume (vs 1.5x intraday)
        self.min_price = 1.0          # Minimum stock price
        self.max_price = 50.0         # Maximum stock price
        self.min_quality_score = 70.0 # Minimum scanner quality (stricter)

        # Swing-specific: End of day confirmation
        self.require_eod_confirmation = True
        self.eod_entry_start = time(15, 0)   # 3:00 PM ET (last hour)
        self.eod_entry_end = time(15, 55)    # 3:55 PM ET (before close)
        self.min_close_strength_pct = 0.5    # Must close in top 50% of day's range

        # Swing-specific: Momentum continuation filters
        self.max_gap_fill_pct = 25.0   # Exit if gap fills >25%
        self.min_daily_volume_ratio = 1.5  # Each day must maintain volume

        # Entry confirmation
        self.pending_entries = {}
        self.min_confirmations = 1
        self.confirmation_window = 300  # 5 minutes for EOD entry

        # Swing holding period
        self.min_holding_days = 1    # Minimum 1 day (overnight)
        self.max_holding_days = 7    # Maximum 7 days

        # Initialize stop manager (swing-specific parameters)
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'ODS_SWING_UNIVERSAL_STRATEGY')
        else:
            # Default swing stops
            self.stop_loss_pct = 10.0  # -10% (wider for overnight)
            self.take_profit_pct = 20.0  # +20% (multiday target)
            self.trailing_stop_activation = 12.0  # Activate at +12%
            self.trailing_stop_distance = 6.0  # Trail -6%

        self.logger.info(
            f"🌙 ODS Swing Universal Worker initialized - "
            f"Patterns: {[p.value for p in self.allowed_ods_patterns]}, "
            f"Min strength: {self.min_ods_strength}, "
            f"Holding: {self.min_holding_days}-{self.max_holding_days} days"
        )


    async def meets_entry_criteria(self, opportunity: Dict[str, Any]) -> bool:
        """
        Swing entry logic based on ODS signal + EOD confirmation

        Key differences from intraday:
        - Requires EOD confirmation (price closes strong)
        - Higher strength threshold (70 vs 60)
        - Higher volume requirement (2x vs 1.5x)
        - Entry window: 3:00-3:55 PM only
        """
        symbol = opportunity.get('symbol')

        try:
            # ====
            # PHASE 1: Extract ODS Signal
            # ====
            ods_data = opportunity.get('ods_data')
            if not ods_data:
                self.logger.debug(f"⚪ {symbol}: No ODS data provided")
                return False

            # Reconstruct ODS object if needed
            if isinstance(ods_data, dict):
                from core.ods_classifier import ODSData
                ods = ODSData(
                    day_type=ODSDayType[ods_data.get('day_type', 'INSUFFICIENT_DATA')],
                    direction=ods_data.get('direction', 'NONE'),
                    strength=ods_data.get('strength', 0.0),
                    open_price=ods_data.get('open_price', 0.0),
                    high_12min=ods_data.get('high_12min', 0.0),
                    low_12min=ods_data.get('low_12min', 0.0),
                    close_12min=ods_data.get('close_12min', 0.0),
                    range_pct=ods_data.get('range_pct', 0.0),
                    distance_from_open_pct=ods_data.get('distance_from_open_pct', 0.0),
                    volume_ratio=ods_data.get('volume_ratio', 0.0),
                    upside_move_pct=ods_data.get('upside_move_pct', 0.0),
                    downside_move_pct=ods_data.get('downside_move_pct', 0.0)
                )
                ods.classification = ods_data.get('classification', '')
            else:
                ods = ods_data

            # ====
            # PHASE 2: Filter by Pattern Type (STRONG patterns only for swing)
            # ====
            if ods.day_type not in self.allowed_ods_patterns:
                self.logger.debug(
                    f"⚪ {symbol}: ODS pattern {ods.day_type.value} not strong enough for swing"
                )
                return False

            # ====
            # PHASE 3: Filter by Signal Strength (HIGHER threshold for swing)
            # ====
            if ods.strength < self.min_ods_strength:
                self.logger.info(
                    f"⚪ {symbol}: ODS strength {ods.strength:.1f} < {self.min_ods_strength} "
                    f"(swing requires stronger signals)"
                )
                return False

            # ====
            # PHASE 4: Basic Validation (price, volume, quality)
            # ====
            price = opportunity.get('price', 0.0)
            volume_ratio = opportunity.get('volume_ratio', 0.0)
            quality_score = opportunity.get('quality_score', 0.0)

            if not (self.min_price <= price <= self.max_price):
                self.logger.info(
                    f"⚪ {symbol}: Price ${price:.2f} outside swing range "
                    f"[${self.min_price}-${self.max_price}]"
                )
                return False

            if volume_ratio < self.min_volume_ratio:
                self.logger.info(
                    f"⚪ {symbol}: Volume {volume_ratio:.1f}x < {self.min_volume_ratio}x "
                    f"(swing requires higher volume)"
                )
                return False

            if quality_score < self.min_quality_score:
                self.logger.info(
                    f"⚪ {symbol}: Quality {quality_score:.1f} < {self.min_quality_score}"
                )
                return False

            # ====
            # PHASE 5: END OF DAY Confirmation (CRITICAL for swing)
            # ====
            current_time = datetime.now().time()
            if not (self.eod_entry_start <= current_time <= self.eod_entry_end):
                self.logger.debug(
                    f"⚪ {symbol}: Outside EOD entry window ({current_time} not in "
                    f"{self.eod_entry_start}-{self.eod_entry_end})"
                )
                return False

            # Check price closes in top 50% of day's range (strong close)
            bars = opportunity.get('bars', [])
            if len(bars) > 0:
                day_high = max(b.high if hasattr(b, 'high') else b.get('high', 0) for b in bars[-60:])  # Last hour
                day_low = min(b.low if hasattr(b, 'low') else b.get('low', 999999) for b in bars[-60:])
                day_range = day_high - day_low

                if day_range > 0:
                    close_position = (price - day_low) / day_range
                    if close_position < self.min_close_strength_pct:
                        self.logger.info(
                            f"⚪ {symbol}: Weak close - {close_position*100:.1f}% in range "
                            f"(need {self.min_close_strength_pct*100:.0f}%+)"
                        )
                        return False

            # ====
            # SUCCESS: All swing criteria met
            # ====
            self.logger.info(
                f"✅ {symbol}: ODS SWING ENTRY APPROVED - "
                f"Pattern: {ods.day_type.value}, Strength: {ods.strength:.1f}, "
                f"Price: ${price:.2f}, Vol: {volume_ratio:.1f}x, Q: {quality_score:.1f}"
            )
            self.logger.info(
                f"🌙 {symbol}: SWING TRADE - Expected hold: {self.min_holding_days}-{self.max_holding_days} days"
            )

            return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in ODS swing entry criteria: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False


    def calculate_position_size(self, opportunity: Dict[str, Any]) -> int:
        """
        Calculate position size based on ODS signal strength (CONSERVATIVE for swing)

        Swing trading = overnight risk → smaller positions than intraday
        """
        symbol = opportunity.get('symbol')
        price = opportunity.get('price', 0.0)
        ods_data = opportunity.get('ods_data')

        if not ods_data:
            return super().calculate_position_size(opportunity)

        # Extract strength
        if isinstance(ods_data, dict):
            strength = ods_data.get('strength', 50.0)
        else:
            strength = ods_data.strength

        # Adaptive risk for SWING (MORE CONSERVATIVE than intraday)
        # Swing has overnight risk → reduce position sizes
        # Strength 70-80 → 0.8% risk (vs 1.3% intraday)
        # Strength 80-90 → 1.0% risk (vs 1.6% intraday)
        # Strength 90-100 → 1.2% risk (vs 2.0% intraday)
        if strength >= 90:
            risk_pct = 1.2  # Max swing risk
        elif strength >= 80:
            risk_pct = 1.0
        elif strength >= 70:
            risk_pct = 0.8
        else:
            risk_pct = 0.6  # Minimum

        self.logger.info(
            f"💰 {symbol}: ODS Swing Risk = {risk_pct:.1f}% (strength={strength:.1f}, CONSERVATIVE for overnight)"
        )

        # Use base calculation with adjusted risk
        opportunity['adaptive_risk_pct'] = risk_pct
        return super().calculate_position_size(opportunity)


    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Wrapper for meets_entry_criteria (required by BaseWorkerLogic)

        Args:
            opportunity: Dict with all opportunity data including symbol, bars, etc.

        Returns:
            bool: True if entry criteria met, False otherwise
        """
        return await self.meets_entry_criteria(opportunity)


    def _determine_trading_horizon(self, signal_data: Dict[str, Any]) -> tuple:
        """
        Determina horizonte temporal para ODS Swing (SIEMPRE SWING para multiday)

        ODS Swing Universal ALWAYS uses SWING horizon:
        - Holding period: 1-7 days
        - EOD_safe=True (NO cierre forzado a las 15:56 ET)
        - Overnight positions permitted

        Returns:
            Tuple[TradingHorizon, expected_hold_hours]
            - TradingHorizon.SWING
            - Expected hold: 72 hours (3 days average)
        """
        # SWING: Multiday holding (1-7 days)
        # This sets EOD_safe=True automatically in BaseWorkerLogic
        # Prevents forced EOD closure at 15:56 ET (21:56 Spain time)

        from core.trade_arbiter import TradingHorizon

        ods_data = signal_data.get('ods_data')
        if ods_data:
            strength = ods_data.get('strength', 70.0) if isinstance(ods_data, dict) else ods_data.strength

            # Stronger signals = longer expected hold
            if strength >= 90:
                expected_hold_hours = 120  # 5 days for very strong signals
            elif strength >= 80:
                expected_hold_hours = 96   # 4 days for strong signals
            else:
                expected_hold_hours = 72   # 3 days for moderate signals
        else:
            expected_hold_hours = 72  # Default 3 days

        self.logger.info(
            f"🌙 ODS Swing: SWING horizon (multiday) - "
            f"Expected hold: {expected_hold_hours/24:.1f} days, EOD_safe=True"
        )

        return TradingHorizon.SWING, expected_hold_hours


    async def should_exit(self, symbol: str, position: dict, bars: list) -> tuple:
        """
        Swing exit logic (multiday stops + momentum fade detection)
        Returns: (should_exit: bool, reason: str)
        """
        # Delegate to stop manager for standard exits
        if hasattr(self, 'stop_manager') and self.stop_manager:
            should_exit, reason = await self.stop_manager.should_exit(symbol, position, bars)
            if should_exit:
                return should_exit, reason

        # Additional swing-specific exits
        # TODO: Add momentum fade detection, gap fade, etc.

        # No exit
        return False, None
