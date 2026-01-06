"""
ODS Universal Worker Logic
Universal pattern-driven worker for ODS (Opening Drive Structure) signals

ARCHITECTURAL PHILOSOPHY:
- Pattern engines (ODS) = Weather stations (report conditions)
- Workers = Pilots (execute based on conditions reported)
- Worker doesn't care HOW pattern was detected, only WHAT to do with it

This worker receives ODS signals and executes trades based on:
- Label (TREND_DRIVE_BULLISH, FAILED_DRIVE, etc.)
- Bias (bullish/bearish direction)
- Intensity (strength 0-100)
- Invalidation zone (stop loss)
- Target zone (take profit)

DECOUPLED ARCHITECTURE:
✅ Add new ODS patterns -> No worker changes needed
✅ Disable specific patterns -> Turn off in ODS engine
✅ Version patterns independently -> Worker unaffected
✅ Reduce system fragility -> Low coupling

Entry Criteria:
1. Valid ODS signal from pattern engine
2. Signal type in allowed list (TREND_DRIVE_BULLISH, STRONG_BULLISH, etc.)
3. Minimum intensity/strength threshold
4. Price within valid range
5. Volume confirmation
6. Risk management approval

Exit Criteria (via WorkerStopManager):
- Stop loss: Based on ODS invalidation zone
- Take profit: Based on ODS target zone
- Trailing stop: Dynamic based on strength
- Time-based: Maximum holding period
- END_OF_DAY: 15:56 ET
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, time
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradingHorizon
from core.ods_classifier import ODSDayType


class ODSUniversalWorkerLogic(BaseWorkerLogic):
    """
    Universal worker that executes trades based on ODS pattern signals

    Receives:
    - ODS pattern classification (from ODS engine)
    - Bias/direction (bullish/bearish)
    - Strength/intensity (0-100)
    - Invalidation zone (stop)
    - Target zone (profit)

    Executes:
    - Universal trade logic based on signal context
    - Adaptive position sizing based on strength
    - Risk management based on invalidation zone
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="ods_universal",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuration from config.ini
        from core.service_locator import get_service_locator
        config = get_service_locator().get_config()

        # ODS Pattern Filtering (which patterns to trade)
        # PHASE 1: Intensity-based patterns enabled
        self.allowed_ods_patterns = [
            # Original patterns
            ODSDayType.TREND_DRIVE_BULLISH,

            # PHASE 1: Intensity-based (granular classification)
            ODSDayType.STRONG_BULLISH_OPEN,      # Strength >= 85 (high conviction)
            ODSDayType.MODERATE_BULLISH_OPEN,    # Strength 60-85 (medium conviction)
            # ODSDayType.WEAK_BULLISH_OPEN,      # Strength 40-60 (optional, low conviction)

            # Add more patterns as ODS engine evolves
        ]

        # Minimum thresholds
        self.min_ods_strength = 60.0  # Minimum strength to trade
        self.min_volume_ratio = 1.5   # Minimum volume vs average
        self.min_price = 1.0          # Minimum stock price
        self.max_price = 50.0         # Maximum stock price
        self.min_quality_score = 60.0 # Minimum scanner quality

        # Trading hours (ODS patterns are morning-focused)
        self.trading_start_time = time(9, 42)  # After ODS calculation (9:42 AM ET)
        self.trading_end_time = time(15, 30)   # Before close

        # Entry confirmation
        self.pending_entries = {}
        self.min_confirmations = 1
        self.confirmation_window = 60

        # Initialize stop manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'ODS_UNIVERSAL_STRATEGY')
        else:
            # Default stops
            self.stop_loss_pct = 3.0
            self.take_profit_pct = 8.0
            self.trailing_stop_activation = 4.0
            self.trailing_stop_distance = 2.0

        self.logger.info(
            f"🎯 ODS Universal Worker initialized - "
            f"Patterns: {[p.value for p in self.allowed_ods_patterns]}, "
            f"Min strength: {self.min_ods_strength}"
        )


    async def meets_entry_criteria(self, opportunity: Dict[str, Any]) -> bool:
        """
        Universal entry logic based on ODS signal

        Worker doesn't care about specific pattern mechanics
        Only cares about:
        - Is signal valid?
        - Is strength sufficient?
        - Is context favorable?
        """
        symbol = opportunity.get('symbol')

        try:
            # ====
            # PHASE 1: Extract ODS Signal (from Pattern Engine)
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
            # PHASE 2: Filter by Pattern Type (Pattern Engine decides what's valid)
            # ====
            if ods.day_type not in self.allowed_ods_patterns:
                self.logger.debug(
                    f"⚪ {symbol}: ODS pattern {ods.day_type.value} not in allowed list"
                )
                return False

            # ====
            # PHASE 3: Filter by Signal Strength/Intensity
            # ====
            if ods.strength < self.min_ods_strength:
                self.logger.info(
                    f"⚪ {symbol}: ODS strength {ods.strength:.1f} < {self.min_ods_strength} "
                    f"(pattern={ods.day_type.value})"
                )
                return False

            self.logger.info(
                f"✅ {symbol}: ODS SIGNAL VALID - Pattern: {ods.day_type.value}, "
                f"Strength: {ods.strength:.1f}, Direction: {ods.direction}"
            )

            # ====
            # PHASE 4: Basic Validation (price, volume, quality)
            # ====
            price = opportunity.get('price', 0.0)
            volume_ratio = opportunity.get('volume_ratio', 0.0)
            quality_score = opportunity.get('quality_score', 0.0)

            if not (self.min_price <= price <= self.max_price):
                self.logger.info(
                    f"⚪ {symbol}: Price ${price:.2f} outside range "
                    f"[${self.min_price}-${self.max_price}]"
                )
                return False

            if volume_ratio < self.min_volume_ratio:
                self.logger.info(
                    f"⚪ {symbol}: Volume {volume_ratio:.1f}x < {self.min_volume_ratio}x"
                )
                return False

            if quality_score < self.min_quality_score:
                self.logger.info(
                    f"⚪ {symbol}: Quality {quality_score:.1f} < {self.min_quality_score}"
                )
                return False

            # ====
            # PHASE 5: Trading Hours Validation
            # ====
            current_time = datetime.now().time()
            if not (self.trading_start_time <= current_time <= self.trading_end_time):
                self.logger.info(
                    f"⚪ {symbol}: Outside trading hours ({current_time} not in "
                    f"{self.trading_start_time}-{self.trading_end_time})"
                )
                return False

            # ====
            # SUCCESS: All criteria met
            # ====
            self.logger.info(
                f"✅ {symbol}: ODS UNIVERSAL ENTRY APPROVED - "
                f"Pattern: {ods.day_type.value}, Strength: {ods.strength:.1f}, "
                f"Price: ${price:.2f}, Vol: {volume_ratio:.1f}x, Q: {quality_score:.1f}"
            )

            return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in ODS universal entry criteria: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False


    def calculate_position_size(self, opportunity: Dict[str, Any]) -> int:
        """
        Calculate position size based on ODS signal strength
        Stronger signals = larger positions (within risk limits)
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

        # Adaptive risk based on ODS strength
        # Strength 60-70 -> 1.0% risk
        # Strength 70-80 -> 1.3% risk
        # Strength 80-90 -> 1.6% risk
        # Strength 90-100 -> 2.0% risk
        if strength >= 90:
            risk_pct = 2.0
        elif strength >= 80:
            risk_pct = 1.6
        elif strength >= 70:
            risk_pct = 1.3
        else:
            risk_pct = 1.0

        self.logger.info(
            f"💰 {symbol}: ODS Adaptive Risk = {risk_pct:.1f}% (strength={strength:.1f})"
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


    async def should_exit(self, symbol: str, position: dict, bars: list) -> tuple:
        """
        Exit logic handled by WorkerStopManager
        Returns: (should_exit: bool, reason: str)
        """
        # Delegate to stop manager (centralized exit logic)
        if hasattr(self, 'stop_manager') and self.stop_manager:
            return await self.stop_manager.should_exit(symbol, position, bars)

        # Fallback: No exit
        return False, None
