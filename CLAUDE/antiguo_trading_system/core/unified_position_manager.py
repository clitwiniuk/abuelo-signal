"""
Unified Position Manager

Centralized position registry to prevent duplicate positions across:
- Day trading workers (gap_go, macdv, daily_plays, bull_flag)
- Swing trading workers (consolidation_breakout)

Also manages capital allocation:
- Day trading: 60% of total capital ($1,200 from $2,000)
- Swing trading: 40% of total capital ($800 from $2,000)
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Set
import threading


class UnifiedPositionManager:
    """
    Manages ALL positions (day + swing) to prevent duplicates and enforce capital limits

    Thread-safe implementation for concurrent worker access.
    """

    def __init__(self, total_capital: float = 2000.0, config: Dict = None):
        self.logger = logging.getLogger(f"{__name__}.UnifiedPositionManager")

        # Capital allocation
        self.total_capital = total_capital
        config = config or {}

        self.day_capital_pct = config.get('day_capital_percentage', 0.60)  # 60%
        self.swing_capital_pct = config.get('swing_capital_percentage', 0.40)  # 40%

        self.day_capital = total_capital * self.day_capital_pct
        self.swing_capital = total_capital * self.swing_capital_pct

        # Position registries (symbol -> position_data)
        self.day_positions: Dict[str, Dict] = {}
        self.swing_positions: Dict[str, Dict] = {}

        # Capital tracking
        self.day_capital_used = 0.0
        self.swing_capital_used = 0.0

        # Post-exit cooldown system (prevent revenge trading)
        self.post_exit_cooldowns: Dict[str, Dict] = {}  # symbol -> {'until': datetime, 'reason': str}

        # Thread safety
        self._lock = threading.RLock()

        # Worker names -> 'day' or 'swing' strategy types
        self._strategy_mapping = {
            # Day trading workers (actual worker classes)
            'gap_go': 'day',
            'macdv': 'day',
            'daily_plays': 'day',
            'bull_flag': 'day',
            'vwap_breakout': 'day',
            'vwap': 'day',
            'momentum_breakout': 'day',
            'generic_01': 'day',
            'volume_absorption': 'day',
            'vcp_smallcap': 'day',
            'smallcaps_long': 'day',
            # Swing trading workers (future)
            'swing_consolidation': 'swing',
            'swing_momentum': 'swing',
        }

        # Worker display names for clean logging (only actual workers)
        self._worker_display_names = {
            'gap_go': 'Gap&Go',
            'macdv': 'MACDV',
            'daily_plays': 'Daily Plays',
            'bull_flag': 'Bull Flag',
            'vwap_breakout': 'VWAP-Break',
            'vwap': 'VWAP',
            'momentum_breakout': 'MomBreak',
            'generic_01': 'Generic-01',
            'volume_absorption': 'VolAbsorb',
            'vcp_smallcap': 'VCP',
            'smallcaps_long': 'SmallCaps',
            'swing_consolidation': 'Swing-Cons',
            'swing_momentum': 'Swing-Mom',
        }

    def _get_worker_display_name(self, worker_name: str) -> str:
        """
        Get clean display name for a worker

        Args:
            worker_name: Worker name or 'day'/'swing'

        Returns:
            Display name for logging
        """
        if worker_name in ['day', 'swing']:
            return f"{worker_name} trading"
        return self._worker_display_names.get(worker_name, worker_name)

        self.logger.info("💼 UnifiedPositionManager initialized")
        self.logger.info(f"   📊 Total capital: ${total_capital:.2f}")
        self.logger.info(f"   📈 Day trading: ${self.day_capital:.2f} ({self.day_capital_pct*100:.0f}%)")
        self.logger.info(f"   📉 Swing trading: ${self.swing_capital:.2f} ({self.swing_capital_pct*100:.0f}%)")

    def can_open_position(
        self,
        symbol: str,
        strategy_type: str,
        position_value: float
    ) -> tuple[bool, str]:
        """
        Check if position can be opened without conflicts

        Args:
            symbol: Ticker symbol
            strategy_type: 'day', 'swing', or specific worker name (auto-mapped)
            position_value: Dollar value of position

        Returns:
            (can_open: bool, reason: str)
        """
        with self._lock:
            # Map strategy type for consistent checking
            actual_strategy_type = self._map_strategy_type(strategy_type)

            # Check 1: Symbol already held in ANY trading (prevent duplicates across all strategies)?
            if symbol in self.day_positions or symbol in self.swing_positions:
                existing_position = self.get_position(symbol)
                existing_worker = existing_position.get('strategy', 'unknown') if existing_position else 'unknown'

                # SPECIAL CASE: Allow claiming UNKNOWN positions (from premarket/crashes/restarts)
                if existing_worker == 'UNKNOWN':
                    self.logger.info(
                        f"🔄 {symbol}: UNKNOWN position detected - allowing {strategy_type} to claim it"
                    )
                    return True, "CLAIMABLE_UNKNOWN_POSITION"

                new_worker = self._get_worker_display_name(strategy_type)

                # Get clean display names for logging
                existing_display = self._get_worker_display_name(existing_worker)

                reason = (
                    f"⚠️ DUPLICATE BLOCKED: {symbol} already held by {existing_display} "
                    f"(attempted by {new_worker})"
                )
                self.logger.warning(reason)
                return False, reason

            # Check 2: Post-exit cooldown active? (PREVENT REVENGE TRADING)
            if symbol in self.post_exit_cooldowns:
                cooldown_data = self.post_exit_cooldowns[symbol]
                cooldown_until = cooldown_data['until']
                current_time = datetime.now()

                if current_time < cooldown_until:
                    remaining_minutes = (cooldown_until - current_time).total_seconds() / 60
                    reason = (
                        f"🛡️ {symbol} in POST-EXIT COOLDOWN "
                        f"({remaining_minutes:.1f} min remaining) - "
                        f"Reason: {cooldown_data['reason']}"
                    )
                    self.logger.info(reason)
                    return False, reason
                else:
                    # Cooldown expired, remove it
                    del self.post_exit_cooldowns[symbol]
                    self.logger.info(f"✅ {symbol} post-exit cooldown expired")

            # Check 3: Sufficient capital available?
            if actual_strategy_type == 'day':
                available = self.day_capital - self.day_capital_used
                if position_value > available:
                    reason = (
                        f"⚠️ Insufficient DAY capital: "
                        f"${available:.2f} available, ${position_value:.2f} needed"
                    )
                    self.logger.warning(reason)
                    return False, reason
            else:  # swing
                available = self.swing_capital - self.swing_capital_used
                if position_value > available:
                    reason = (
                        f"⚠️ Insufficient SWING capital: "
                        f"${available:.2f} available, ${position_value:.2f} needed"
                    )
                    self.logger.warning(reason)
                    return False, reason

            # All checks passed
            return True, "OK"

    def register_position(
        self,
        symbol: str,
        strategy_type: str,
        position_data: Dict
    ) -> bool:
        """
        Register a new position

        Args:
            symbol: Ticker symbol
            strategy_type: 'day', 'swing', or specific worker name (auto-mapped to 'day'/'swing')
            position_data: Dict with position details
                Required: 'position_value' (can auto-calculate from entry_price * quantity if missing)

        Returns:
            True if registered successfully
        """
        with self._lock:
            # AUTO-MAP strategy types: Map specific worker names to 'day' or 'swing'
            actual_strategy_type = self._map_strategy_type(strategy_type)

            # Calculate position_value if not provided
            if 'position_value' not in position_data:
                if 'entry_price' in position_data and 'quantity' in position_data:
                    position_data['position_value'] = position_data['entry_price'] * position_data['quantity']
                else:
                    self.logger.error(f"Invalid position data: missing position_value and cannot calculate it")
                    return False

            position_value = position_data['position_value']

            # Check if sufficient capital is available BEFORE registering
            # This prevents over-allocation when re-registering existing positions
            if actual_strategy_type == 'day':
                available = self.day_capital - self.day_capital_used
                if position_value > available:
                    self.logger.error(
                        f"❌ Cannot register DAY position {symbol}: "
                        f"Insufficient capital (${available:.2f} available, ${position_value:.2f} needed). "
                        f"This indicates potential position tracking issue - check if positions were properly unregistered."
                    )
                    return False
            else:  # swing
                available = self.swing_capital - self.swing_capital_used
                if position_value > available:
                    self.logger.error(
                        f"❌ Cannot register SWING position {symbol}: "
                        f"Insufficient capital (${available:.2f} available, ${position_value:.2f} needed). "
                        f"This indicates potential position tracking issue - check if positions were properly unregistered."
                    )
                    return False

            # Check if symbol already exists (prevent duplicates regardless of worker)
            if symbol in self.day_positions or symbol in self.swing_positions:
                existing_position = self.get_position(symbol)
                existing_worker = existing_position.get('strategy', 'unknown') if existing_position else 'unknown'
                new_worker = position_data.get('strategy', strategy_type)

                # SPECIAL CASE: Claiming UNKNOWN position - UPDATE instead of blocking
                if existing_worker == 'UNKNOWN':
                    self.logger.info(
                        f"🔄 {symbol}: Claiming UNKNOWN position - updating with {new_worker} data"
                    )

                    # Update the existing position with new strategy data
                    if symbol in self.day_positions:
                        self.day_positions[symbol].update(position_data)
                        self.day_positions[symbol]['strategy_type'] = actual_strategy_type
                        self.day_positions[symbol]['strategy'] = position_data.get('strategy', strategy_type)
                        self.day_positions[symbol]['claimed_at'] = datetime.now()

                        worker_display = self._get_worker_display_name(new_worker)
                        self.logger.info(
                            f"✅ Claimed DAY position: {symbol} (now owned by {worker_display})"
                        )
                        return True
                    elif symbol in self.swing_positions:
                        self.swing_positions[symbol].update(position_data)
                        self.swing_positions[symbol]['strategy_type'] = actual_strategy_type
                        self.swing_positions[symbol]['strategy'] = position_data.get('strategy', strategy_type)
                        self.swing_positions[symbol]['claimed_at'] = datetime.now()

                        worker_display = self._get_worker_display_name(new_worker)
                        self.logger.info(
                            f"✅ Claimed SWING position: {symbol} (now owned by {worker_display})"
                        )
                        return True

                # Get clean display names for logging
                existing_display = self._get_worker_display_name(existing_worker)
                new_display = self._get_worker_display_name(new_worker)

                self.logger.warning(
                    f"⚠️ DUPLICATE POSITION BLOCKED: {symbol} already held by {existing_display} "
                    f"(attempted by {new_display})"
                )
                return False

            # Add metadata
            position_data['registered_at'] = datetime.now()
            position_data['strategy_type'] = actual_strategy_type  # Store mapped type

            # IMPORTANT: Only set 'strategy' if not already present in position_data
            # This preserves UNKNOWN strategy from position_data if explicitly provided
            if 'strategy' not in position_data:
                position_data['strategy'] = strategy_type  # Keep original worker name for consistency

            # DEBUG: Validate position data has required fields
            required_fields = ['strategy_type', 'strategy']
            for field in required_fields:
                if field not in position_data:
                    self.logger.warning(f"⚠️ Position data for {symbol} missing '{field}' field - adding default")
                    position_data[field] = 'UNKNOWN'

            # Register position
            if actual_strategy_type == 'day':
                self.day_positions[symbol] = position_data
                self.day_capital_used += position_value
                worker_name = position_data.get('strategy', strategy_type)
                worker_display = self._get_worker_display_name(worker_name)
                self.logger.info(
                    f"✅ Registered DAY position: {symbol} ({worker_display}) "
                    f"(${position_value:.2f}, "
                    f"capital used: ${self.day_capital_used:.2f}/${self.day_capital:.2f})"
                )
                self.logger.debug(f"📊 DAY positions after registration: {list(self.day_positions.keys())}")
            else:  # swing
                self.swing_positions[symbol] = position_data
                self.swing_capital_used += position_value
                worker_name = position_data.get('strategy', strategy_type)
                worker_display = self._get_worker_display_name(worker_name)
                self.logger.info(
                    f"✅ Registered SWING position: {symbol} ({worker_display}) "
                    f"(${position_value:.2f}, "
                    f"capital used: ${self.swing_capital_used:.2f}/${self.swing_capital:.2f})"
                )
                self.logger.debug(f"📊 SWING positions after registration: {list(self.swing_positions.keys())}")

            return True

    def unregister_position(self, symbol: str, strategy_type: str, exit_pnl_pct: Optional[float] = None, exit_reason: Optional[str] = None) -> bool:
        """
        Unregister a position (when closed)

        Args:
            symbol: Ticker symbol
            strategy_type: 'day', 'swing', or specific worker name (auto-mapped)
            exit_pnl_pct: Optional exit PnL percentage for cooldown calculation
            exit_reason: Optional exit reason for cooldown logging

        Returns:
            True if unregistered successfully
        """
        with self._lock:
            # AUTO-MAP strategy types for consistency
            actual_strategy_type = self._map_strategy_type(strategy_type)

            position = None

            if actual_strategy_type == 'day':
                if symbol not in self.day_positions:
                    self.logger.warning(f"⚠️ {symbol} not found in day positions - checking if exists elsewhere")
                    # DEBUG: Check if position exists in swing or if this is a state inconsistency
                    if symbol in self.swing_positions:
                        self.logger.error(f"❌ STATE ERROR: {symbol} found in SWING positions but trying to unregister from DAY")
                        return False
                    else:
                        self.logger.warning(f"⚠️ {symbol} not found in any positions - may be already unregistered or state inconsistency")
                        # Check if in cooldown (indicates previous exit)
                        if symbol in self.post_exit_cooldowns:
                            self.logger.debug(f"🔍 DEBUG {symbol}: Found in cooldown - position was previously exited")
                        # FIX: If position not found but we're trying to unregister, assume it's already done
                        # This prevents the "UNKNOWN" state from persisting
                        self.logger.info(f"ℹ️ {symbol} position already unregistered or not found - treating as successful")
                        return True

                position = self.day_positions.pop(symbol)
                self.day_capital_used -= position['position_value']
                worker_name = position.get('strategy', strategy_type)
                worker_display = self._get_worker_display_name(worker_name)
                self.logger.info(
                    f"✅ Unregistered DAY position: {symbol} ({worker_display}) "
                    f"(freed ${position['position_value']:.2f})"
                )
            else:  # swing
                if symbol not in self.swing_positions:
                    self.logger.warning(f"⚠️ {symbol} not found in swing positions - checking if exists elsewhere")
                    # DEBUG: Check if position exists in day or if this is a state inconsistency
                    if symbol in self.day_positions:
                        self.logger.error(f"❌ STATE ERROR: {symbol} found in DAY positions but trying to unregister from SWING")
                        return False
                    else:
                        self.logger.warning(f"⚠️ {symbol} not found in any positions - may be already unregistered or state inconsistency")
                        # Check if in cooldown (indicates previous exit)
                        if symbol in self.post_exit_cooldowns:
                            self.logger.debug(f"🔍 DEBUG {symbol}: Found in cooldown - position was previously exited")
                        # FIX: If position not found but we're trying to unregister, assume it's already done
                        # This prevents the "UNKNOWN" state from persisting
                        self.logger.info(f"ℹ️ {symbol} position already unregistered or not found - treating as successful")
                        return True

                position = self.swing_positions.pop(symbol)
                self.swing_capital_used -= position['position_value']
                worker_name = position.get('strategy', strategy_type)
                worker_display = self._get_worker_display_name(worker_name)
                self.logger.info(
                    f"✅ Unregistered SWING position: {symbol} ({worker_display}) "
                    f"(freed ${position['position_value']:.2f})"
                )

            # DEBUG: Log position state after unregistration
            self.logger.debug(f"📊 DEBUG {symbol}: Positions after unregister - DAY: {list(self.day_positions.keys())}, SWING: {list(self.swing_positions.keys())}")

            # Register post-exit cooldown if profitable exit data provided
            if exit_pnl_pct is not None and exit_reason is not None:
                self.register_post_exit_cooldown(symbol, actual_strategy_type, exit_pnl_pct, exit_reason)

            return True

    def register_post_exit_cooldown(
        self,
        symbol: str,
        strategy_type: str,
        exit_pnl_pct: float,
        exit_reason: str
    ) -> bool:
        """
        Register a post-exit cooldown to prevent revenge trading

        Args:
            symbol: Ticker symbol
            strategy_type: 'day' or 'swing'
            exit_pnl_pct: Exit PnL percentage (e.g., 20.26 for +20.26%)
            exit_reason: Reason for exit (e.g., 'TAKE_PROFIT_20.0%')

        Returns:
            True if cooldown registered
        """
        with self._lock:
            # Only apply cooldown for profitable exits (prevent revenge trading)
            if exit_pnl_pct <= 0:
                return False

            # Calculate cooldown duration based on profitability
            # More profitable = longer cooldown
            if exit_pnl_pct >= 20.0:  # Big winners (>=20%)
                cooldown_minutes = 60  # 1 hour cooldown
            elif exit_pnl_pct >= 15.0:  # Good winners (15-20%)
                cooldown_minutes = 45  # 45 minutes
            elif exit_pnl_pct >= 10.0:  # Decent winners (10-15%)
                cooldown_minutes = 30  # 30 minutes
            else:  # Small winners (0-10%)
                cooldown_minutes = 15  # 15 minutes

            from datetime import timedelta
            cooldown_until = datetime.now() + timedelta(minutes=cooldown_minutes)

            self.post_exit_cooldowns[symbol] = {
                'until': cooldown_until,
                'reason': f"Post-{exit_reason} cooldown ({exit_pnl_pct:.1f}% PnL)",
                'exit_pnl_pct': exit_pnl_pct,
                'strategy_type': strategy_type
            }

            self.logger.info(
                f"🛡️ Registered POST-EXIT COOLDOWN for {symbol}: "
                f"{cooldown_minutes}min until {cooldown_until.strftime('%H:%M:%S')} "
                f"(Reason: {exit_pnl_pct:.1f}% {exit_reason})"
            )

            return True

    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get position details for a symbol (checks both day and swing)

        Returns:
            Position dict or None if not found
        """
        with self._lock:
            if symbol in self.day_positions:
                position = self.day_positions[symbol]
                # DEBUG: Ensure position has required fields
                if 'strategy_type' not in position:
                    self.logger.warning(f"⚠️ {symbol} position missing 'strategy_type' field")
                    position['strategy_type'] = 'UNKNOWN'
                if 'strategy' not in position:
                    self.logger.warning(f"⚠️ {symbol} position missing 'strategy' field")
                    position['strategy'] = 'UNKNOWN'
                return position
            if symbol in self.swing_positions:
                position = self.swing_positions[symbol]
                # DEBUG: Ensure position has required fields
                if 'strategy_type' not in position:
                    self.logger.warning(f"⚠️ {symbol} position missing 'strategy_type' field")
                    position['strategy_type'] = 'UNKNOWN'
                if 'strategy' not in position:
                    self.logger.warning(f"⚠️ {symbol} position missing 'strategy' field")
                    position['strategy'] = 'UNKNOWN'
                return position
            return None

    def get_all_symbols(self) -> Set[str]:
        """
        Get set of all symbols with open positions (day + swing)
        """
        with self._lock:
            return set(self.day_positions.keys()) | set(self.swing_positions.keys())

    def get_day_positions(self) -> Dict[str, Dict]:
        """Get all day trading positions"""
        with self._lock:
            return self.day_positions.copy()

    def get_swing_positions(self) -> Dict[str, Dict]:
        """Get all swing trading positions"""
        with self._lock:
            return self.swing_positions.copy()

    def get_capital_summary(self) -> Dict:
        """
        Get capital allocation summary

        Returns:
            Dict with capital stats
        """
        with self._lock:
            return {
                'total_capital': self.total_capital,
                'day_trading': {
                    'allocated': self.day_capital,
                    'used': self.day_capital_used,
                    'available': self.day_capital - self.day_capital_used,
                    'utilization_pct': (self.day_capital_used / self.day_capital * 100) if self.day_capital > 0 else 0,
                    'positions_count': len(self.day_positions)
                },
                'swing_trading': {
                    'allocated': self.swing_capital,
                    'used': self.swing_capital_used,
                    'available': self.swing_capital - self.swing_capital_used,
                    'utilization_pct': (self.swing_capital_used / self.swing_capital * 100) if self.swing_capital > 0 else 0,
                    'positions_count': len(self.swing_positions)
                }
            }

    def _map_strategy_type(self, strategy_type: str) -> str:
        """
        Map specific worker names to 'day' or 'swing' strategy types

        Args:
            strategy_type: Worker name or 'day'/'swing'

        Returns:
            Mapped strategy type ('day' or 'swing')
        """
        # If already a base type, return as-is
        if strategy_type in ['day', 'swing']:
            return strategy_type

        # Map specific worker names
        return self._strategy_mapping.get(strategy_type, 'day')  # Default to 'day' for unknown workers

    def get_available_capital(self, strategy_type: str) -> float:
        """
        Get available capital for a strategy type

        Args:
            strategy_type: 'day', 'swing', or specific worker name (auto-mapped)

        Returns:
            Available capital in dollars
        """
        with self._lock:
            actual_type = self._map_strategy_type(strategy_type)
            if actual_type == 'day':
                return self.day_capital - self.day_capital_used
            else:  # swing
                return self.swing_capital - self.swing_capital_used

    def is_symbol_blocked(self, symbol: str) -> bool:
        """
        Check if symbol is blocked (exists in either day or swing positions OR in post-exit cooldown)

        IMPORTANT: UNKNOWN positions are NOT considered blocked (they can be claimed)

        Args:
            symbol: Ticker symbol

        Returns:
            True if symbol already has a position or is in cooldown
        """
        with self._lock:
            # Check active positions
            has_position = symbol in self.day_positions or symbol in self.swing_positions

            # SPECIAL CASE: UNKNOWN positions are claimable (not blocked)
            if has_position:
                position = self.get_position(symbol)
                strategy_name = position.get('strategy', 'UNKNOWN') if position else 'UNKNOWN'

                if strategy_name == 'UNKNOWN':
                    self.logger.debug(f"🔄 {symbol}: Has UNKNOWN position - NOT blocking (claimable)")
                    return False  # Not blocked, can be claimed

            # Check post-exit cooldown
            in_cooldown = False
            if symbol in self.post_exit_cooldowns:
                cooldown_data = self.post_exit_cooldowns[symbol]
                if datetime.now() < cooldown_data['until']:
                    in_cooldown = True
                else:
                    # Expired cooldown, remove it
                    del self.post_exit_cooldowns[symbol]
                    self.logger.debug(f"✅ {symbol} cooldown expired and removed")

            # DEBUG: Log blocking reason for diagnosis
            if has_position or in_cooldown:
                if has_position:
                    position = self.get_position(symbol)
                    strategy_type = position.get('strategy_type', 'UNKNOWN') if position else 'UNKNOWN'
                    strategy_name = position.get('strategy', 'UNKNOWN') if position else 'UNKNOWN'
                    self.logger.debug(f"🔍 DEBUG {symbol}: BLOCKED by active position (type: {strategy_type}, strategy: {strategy_name})")
                elif in_cooldown:
                    cooldown_data = self.post_exit_cooldowns.get(symbol)
                    if cooldown_data:
                        remaining_minutes = (cooldown_data['until'] - datetime.now()).total_seconds() / 60
                        self.logger.debug(f"🔍 DEBUG {symbol}: BLOCKED by cooldown ({remaining_minutes:.1f}min remaining, reason: {cooldown_data.get('reason', 'N/A')})")

            return has_position or in_cooldown

    def get_active_cooldowns(self) -> Dict[str, Dict]:
        """
        Get all currently active post-exit cooldowns

        Returns:
            Dict of symbol -> cooldown data for active cooldowns
        """
        with self._lock:
            active_cooldowns = {}
            current_time = datetime.now()

            for symbol, cooldown_data in self.post_exit_cooldowns.items():
                if current_time < cooldown_data['until']:
                    active_cooldowns[symbol] = cooldown_data.copy()
                else:
                    # Remove expired cooldown
                    del self.post_exit_cooldowns[symbol]

            return active_cooldowns

    def print_summary(self):
        """Print detailed position summary"""
        summary = self.get_capital_summary()

        print("\n" + "=" * 60)
        print("💼 UNIFIED POSITION MANAGER - SUMMARY")
        print("=" * 60)

        print(f"\n📊 TOTAL CAPITAL: ${summary['total_capital']:.2f}")

        print(f"\n📈 DAY TRADING (60%):")
        day = summary['day_trading']
        print(f"   Allocated: ${day['allocated']:.2f}")
        print(f"   Used:      ${day['used']:.2f} ({day['utilization_pct']:.1f}%)")
        print(f"   Available: ${day['available']:.2f}")
        print(f"   Positions: {day['positions_count']}")
        if self.day_positions:
            for symbol, pos in self.day_positions.items():
                worker_name = pos.get('strategy', 'unknown')
                worker_display = self._get_worker_display_name(worker_name)
                print(f"      • {symbol}: ${pos['position_value']:.2f} ({worker_display})")

        print(f"\n📉 SWING TRADING (40%):")
        swing = summary['swing_trading']
        print(f"   Allocated: ${swing['allocated']:.2f}")
        print(f"   Used:      ${swing['used']:.2f} ({swing['utilization_pct']:.1f}%)")
        print(f"   Available: ${swing['available']:.2f}")
        print(f"   Positions: {swing['positions_count']}")
        if self.swing_positions:
            for symbol, pos in self.swing_positions.items():
                worker_name = pos.get('strategy', 'unknown')
                worker_display = self._get_worker_display_name(worker_name)
                print(f"      • {symbol}: ${pos['position_value']:.2f} ({worker_display})")

        # Show active post-exit cooldowns
        active_cooldowns = self.get_active_cooldowns()
        if active_cooldowns:
            print(f"\n🛡️ POST-EXIT COOLDOWNS ({len(active_cooldowns)}):")
            for symbol, cooldown_data in active_cooldowns.items():
                remaining_minutes = (cooldown_data['until'] - datetime.now()).total_seconds() / 60
                print(f"      • {symbol}: {remaining_minutes:.1f}min remaining")
                print(f"        Reason: {cooldown_data['reason']}")

        print("\n" + "=" * 60 + "\n")


# Test function
def test_unified_position_manager():
    """Test the unified position manager"""
    print("🧪 Testing UnifiedPositionManager")
    print("=" * 60)

    # Create manager with $2000 total capital
    manager = UnifiedPositionManager(total_capital=2000.0)

    # Test 1: Open day position
    print("\n📋 Test 1: Open DAY position (AAPL)")
    can_open, reason = manager.can_open_position('AAPL', 'day', 200.0)
    print(f"   Can open: {can_open} - {reason}")

    if can_open:
        manager.register_position('AAPL', 'day', {
            'entry_price': 150.0,
            'quantity': 1,
            'position_value': 200.0
        })

    # Test 2: Try to open swing position on same symbol (should fail)
    print("\n📋 Test 2: Try SWING position on AAPL (should fail)")
    can_open, reason = manager.can_open_position('AAPL', 'swing', 300.0)
    print(f"   Can open: {can_open} - {reason}")

    # Test 3: Open swing position on different symbol
    print("\n📋 Test 3: Open SWING position (TSLA)")
    can_open, reason = manager.can_open_position('TSLA', 'swing', 350.0)
    print(f"   Can open: {can_open} - {reason}")

    if can_open:
        manager.register_position('TSLA', 'swing', {
            'entry_price': 700.0,
            'quantity': 1,
            'position_value': 350.0
        })

    # Test 4: Check capital limits
    print("\n📋 Test 4: Try to open position exceeding capital")
    can_open, reason = manager.can_open_position('NVDA', 'swing', 600.0)
    print(f"   Can open: {can_open} - {reason}")

    # Test 5: Close position
    print("\n📋 Test 5: Close DAY position (AAPL)")
    manager.unregister_position('AAPL', 'day')

    # Test 6: Now can open AAPL in swing?
    print("\n📋 Test 6: Now can open AAPL in SWING?")
    can_open, reason = manager.can_open_position('AAPL', 'swing', 300.0)
    print(f"   Can open: {can_open} - {reason}")

    # Print final summary
    manager.print_summary()


if __name__ == "__main__":
    test_unified_position_manager()
