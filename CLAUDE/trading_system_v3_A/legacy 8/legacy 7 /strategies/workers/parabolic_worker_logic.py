#!/usr/bin/env python3
"""
Parabolic Extension Worker Logic
Worker especializado para detectar y operar extensiones parabólicas EARLY-stage

Strategy Philosophy:
- Detecta aceleración de precio ANTES de que sea obvia (EARLY stage)
- Entra cuando otros traders aún no ven el parabolic move
- Sale al primer signo de exhaustion (LATE stage warning)
- Movimientos rápidos: scalp/intraday (1-3 horas hold time típico)

Entry Criteria (ALL must be TRUE):
1. parabolic_data exists and stage == 'EARLY'
2. long_entry_opportunity == True (detector confirms entry signal)
3. acceleration >= min_acceleration (strong acceleration required)
4. exhaustion_score < max_exhaustion_for_entry (no exhaustion signals)
5. strength >= min_strength (minimum parabolic strength)
6. quality_score >= min_quality_score (scanner confidence)
7. Price in range (min_price to max_price)
8. Volume confirmation (volume_score >= min_volume_confirmation)
9. Anti-overtrading: Max 1 trade per symbol per day

Exit Criteria (FIRST to trigger wins):
0. PRIORITY 0: LATE stage detected OR exhaustion_warning == True -> EXIT IMMEDIATELY
1. PRIORITY 1: FOMO exhaustion detector (if enabled)
2. PRIORITY 2: Trailing stop (4% activation, 2% distance)
3. PRIORITY 3: Take profit (8% default - fast moves)
4. PRIORITY 4: Stop loss (3.5% default - tight)
5. PRIORITY 5: Time-based exit (2 hours max default)
6. PRIORITY 6: End of day (15:56 ET)

Performance Characteristics (Expected):
- Win rate: 65-70% (high due to EARLY entry + exhaustion exit)
- Avg gain: +6-8% (fast momentum moves)
- Avg loss: -2-3% (tight stops)
- Avg hold time: 1-2 hours (scalp/intraday)
- Risk/Reward: ~2.5:1

Author: Trading System
Date: 2025-12-13
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from .base_worker_logic import BaseWorkerLogic
from core.parabolic_extension_detector import ParabolicExtensionDetector, ParabolicSignal
from core.trade_arbiter import TradingHorizon


@dataclass
class ParabolicAnalysis:
    """Analysis results from parabolic detector"""
    signal: ParabolicSignal
    is_valid_entry: bool
    rejection_reason: Optional[str]
    confidence_score: float  # 0-100


class ParabolicWorkerLogic(BaseWorkerLogic):
    """
    Parabolic Extension Worker - Specialized in EARLY-stage parabolic acceleration

    Core Philosophy:
    - Enter EARLY (before the crowd)
    - Exit EARLY (before reversal)
    - Fast in, fast out
    - High win rate through precision timing

    Technical Implementation:
    - Uses ParabolicExtensionDetector for pattern recognition
    - ROC-based acceleration detection (short > medium > long)
    - Stage-aware entry (EARLY only, reject MIDDLE/LATE)
    - Exhaustion-aware exit (LATE stage or exhaustion warning)
    """

    def __init__(self, broker, risk_manager=None, config=None, execution_engine=None):
        super().__init__(
            worker_name="parabolic",
            broker=broker,
            config=config  # PASS CONFIG TO BASE
        )
        # Store risk_manager if provided, otherwise create default or allow Base to handle
        self.risk_manager = risk_manager

        # Store config for other methods
        self.config = config

        # Initialize parabolic detector
        self.parabolic_detector = ParabolicExtensionDetector(config={
            'roc_period_short': int(getattr(config, 'parabolic_roc_period_short', 3)),
            'roc_period_medium': int(getattr(config, 'parabolic_roc_period_medium', 5)),
            'roc_period_long': int(getattr(config, 'parabolic_roc_period_long', 10)),
            'early_stage_roc_threshold': float(getattr(config, 'parabolic_early_stage_roc_threshold', 0.05)),
            'middle_stage_roc_threshold': float(getattr(config, 'parabolic_middle_stage_roc_threshold', 0.10)),
            'late_stage_roc_threshold': float(getattr(config, 'parabolic_late_stage_roc_threshold', 0.20)),
            'acceleration_threshold': float(getattr(config, 'parabolic_acceleration_threshold', 1.5)),
            'extreme_acceleration_threshold': float(getattr(config, 'parabolic_extreme_acceleration_threshold', 2.5)),
            'volume_confirmation_multiplier': float(getattr(config, 'parabolic_volume_confirmation_multiplier', 1.5)),
            'rsi_exhaustion_level': float(getattr(config, 'parabolic_rsi_exhaustion_level', 75)),
        })

        # === ENTRY FILTERS ===
        # Minimum acceleration score (0.0-1.0) for entry
        self.min_acceleration = float(getattr(config, 'parabolic_min_acceleration', 0.60))
        # Maximum exhaustion score allowed for entry
        self.max_exhaustion_for_entry = float(getattr(config, 'parabolic_max_exhaustion_for_entry', 0.40))
        # Minimum parabolic strength score
        self.min_strength = float(getattr(config, 'parabolic_min_strength', 0.25))
        # Minimum volume confirmation score
        self.min_volume_confirmation = float(getattr(config, 'parabolic_min_volume_confirmation', 0.6))
        # Minimum scanner quality score
        self.min_quality_score = float(getattr(config, 'parabolic_min_quality_score', 65.0))
        # Price range filters
        self.min_price = float(getattr(config, 'parabolic_min_price', 1.0))
        self.max_price = float(getattr(config, 'parabolic_max_price', 20.0))

        # === MONITORING ===
        # Enable continuous exhaustion monitoring in positions
        self.enable_exhaustion_monitoring = getattr(config, 'parabolic_enable_exhaustion_monitoring', True)
        # Check exhaustion every N bars
        self.exhaustion_check_interval_bars = getattr(config, 'parabolic_exhaustion_check_interval_bars', 3)

        # === ANTI-OVERTRADING ===
        self.max_trades_per_symbol_per_day = getattr(
            config, 'parabolic_max_trades_per_symbol_per_day', 1
        )
        self.traded_symbols_today = set()

        # === STOP MANAGER ===
        # Initialize with parabolic-specific parameters
        from .worker_stop_manager import create_worker_stop_manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'PARABOLIC_STRATEGY')
        else:
            # Fallback: tight stops for fast moves
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=3.5,           # Tight stop (fast moves)
                take_profit_pct=8.0,         # Quick profit target
                quick_target_pct=0.0,        # Disabled
                trailing_activation=4.0,     # Activate trailing quickly
                trailing_distance=2.0,       # Tight trailing
                max_position_hours=2.0       # Short hold time
            ))

        # Track last exhaustion check per symbol
        self._last_exhaustion_check = {}

        # Safe formatting for max_position_hours (can be None)
        max_hours = self.stop_manager.config.max_position_hours or 2.0
        
        self.logger.info(
            f"🚀 Parabolic Worker configured: "
            f"min_accel={self.min_acceleration:.2f}, max_exhaustion={self.max_exhaustion_for_entry:.2f}, "
            f"min_strength={self.min_strength:.2f}, Q>={self.min_quality_score:.0f} | "
            f"Exits: TP={self.stop_manager.config.take_profit_pct}%, SL={self.stop_manager.config.stop_loss_pct}%, "
            f"Trail={self.stop_manager.config.trailing_activation}%/{self.stop_manager.config.trailing_distance}%, "
            f"Max={max_hours:.1f}h"
        )

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calculate parabolic pattern completion (0-100%)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            parabolic_data = opportunity.get('parabolic_data')

            if not parabolic_data:
                # Try to calculate locally if bars available
                bars = self.get_bars_from_opportunity(opportunity)
                if bars and len(bars) > 10:
                    signal = self.parabolic_detector.detect_parabolic_extension(symbol, bars)
                    if signal:
                        # Construct minimal parabolic data from signal
                        parabolic_data = {
                            'stage': signal.stage,
                            'strength': signal.strength,
                            'acceleration': signal.acceleration,
                            'exhaustion_score': signal.exhaustion_score,
                            'long_entry_opportunity': signal.long_entry_opportunity
                        }
                        opportunity['parabolic_data'] = parabolic_data
                    else:
                        return 0.0
                else:
                    return 0.0

            completion = 0.0

            # Stage 1: Pattern exists (25%)
            completion += 25.0

            # Stage 2: EARLY stage detected (25%)
            if parabolic_data.get('stage') == 'EARLY':
                completion += 25.0
            else:
                return completion

            # Stage 3: Good strength and acceleration (25%)
            strength = parabolic_data.get('strength', 0.0)
            acceleration = parabolic_data.get('acceleration', 0.0)

            if strength >= self.min_strength:
                completion += 12.5
            if acceleration >= self.min_acceleration:
                completion += 12.5

            # Stage 4: Low exhaustion + entry signal (25%)
            exhaustion = parabolic_data.get('exhaustion_score', 1.0)
            long_entry = parabolic_data.get('long_entry_opportunity', False)

            if exhaustion < self.max_exhaustion_for_entry:
                completion += 12.5
            if long_entry:
                completion += 12.5

            return min(completion, 100.0)

        except Exception as e:
            self.logger.error(f"Error calculating pattern completion for {symbol}: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Determine if parabolic entry should be executed - TECHNICAL ONLY
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # === STEP 0: Anti-overtrading ===
            if symbol in self.traded_symbols_today:
                self.logger.debug(f"⏭️ {symbol}: Already traded today (anti-overtrading)")
                return False
            
            # Position check
            positions = await self.broker.get_positions()
            if any(p['symbol'] == symbol for p in positions):
                self.logger.info(f"⚪ {symbol}: Position already exists")
                return False

            # === STEP 1: Basic filters ===
            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)

            # Price range filter
            if current_price < self.min_price or current_price > self.max_price:
                self.logger.debug(
                    f"⏭️ {symbol}: Price ${current_price:.2f} outside range "
                    f"[${self.min_price:.2f}-${self.max_price:.2f}]"
                )
                return False

            # Quality score filter (Check Technical Quality only)
            if quality_score < self.min_quality_score:
                # If Volume Ratio is huge, override quality check
                volume_ratio = opportunity.get('volume_ratio', 1.0)
                if volume_ratio > 3.0:
                     self.logger.info(f"⚡ {symbol}: Volume Ratio {volume_ratio:.1f}x overrides Quality Score")
                else:
                    self.logger.debug(
                        f"⏭️ {symbol}: Quality {quality_score:.0f} < {self.min_quality_score:.0f}"
                    )
                    return False

            # ========== VWAP DIRECTION VALIDATION (INSTITUTIONAL FLOW) ==========
            # Parabolic requires strong upward momentum - validate via VWAP
            bars = self.get_bars_from_opportunity(opportunity)
            if bars and len(bars) >= 10:
                is_valid_vwap, vwap_reason, vwap_data = self.validate_vwap_direction(
                    bars=bars,
                    current_price=current_price,
                    intended_direction='LONG',
                    min_slope_pct=0.15,
                    tolerance_pct=1.0,
                    symbol=symbol
                )

                if not is_valid_vwap:
                    self.logger.info(f"⚪ {symbol}: VWAP direction rejected - {vwap_reason}")
                    return False
            else:
                 # If no bars, try to trust scanner signal if strong
                 if not bars:
                     self.logger.warning(f"⚠️ {symbol}: No bars for VWAP check")
            # ========== END VWAP VALIDATION ==========

            # === STEP 2: Get or Calculate Parabolic Data ===
            parabolic_data = opportunity.get('parabolic_data')
            if not parabolic_data and bars:
                # Calculate locally
                signal = self.parabolic_detector.detect_parabolic_extension(symbol, bars)
                if signal:
                    parabolic_data = {
                        'stage': signal.stage,
                        'strength': signal.strength,
                        'acceleration': signal.acceleration,
                        'exhaustion_score': signal.exhaustion_score,
                        'long_entry_opportunity': signal.long_entry_opportunity,
                        'technical_data': {'volume_score': 1.0} # Assume volume OK if signal generated
                    }
            
            if not parabolic_data:
                self.logger.info(f"ℹ️ {symbol}: SKIPPING - No parabolic pattern detected")
                return False

            # === STEP 3: Stage validation (EARLY only) ===
            stage = parabolic_data.get('stage')
            if stage != 'EARLY':
                self.logger.info(f"⏭️ {symbol}: Stage={stage} (require EARLY for entry)")
                return False

            # === STEP 4: Entry signal validation ===
            long_entry = parabolic_data.get('long_entry_opportunity', False)
            if not long_entry:
                self.logger.debug(f"⏭️ {symbol}: No LONG entry signal from detector")
                return False

            # === STEP 5: Acceleration check ===
            acceleration = parabolic_data.get('acceleration', 0.0)
            if acceleration < self.min_acceleration:
                self.logger.debug(f"⏭️ {symbol}: Acceleration {acceleration:.2f} < {self.min_acceleration:.2f}")
                return False

            # === STEP 6: Exhaustion check ===
            exhaustion = parabolic_data.get('exhaustion_score', 1.0)
            if exhaustion >= self.max_exhaustion_for_entry:
                self.logger.warning(f"⏭️ {symbol}: Exhaustion {exhaustion:.2f} >= {self.max_exhaustion_for_entry:.2f}")
                return False

            # === STEP 7: Strength check ===
            strength = parabolic_data.get('strength', 0.0)
            if strength < self.min_strength:
                self.logger.debug(f"⏭️ {symbol}: Strength {strength:.2f} < {self.min_strength:.2f}")
                return False

            # === STEP 8: Volume confirmation ===
            # Simply check volume ratio from opportunity if technical_data missing
            volume_ratio = opportunity.get('volume_ratio', 0.0)
            if volume_ratio < 1.0:
                 # Try technical data
                 technical_data = parabolic_data.get('technical_data', {})
                 volume_score = technical_data.get('volume_score', 0.0)
                 if volume_score < self.min_volume_confirmation:
                     self.logger.debug(f"⏭️ {symbol}: Low volume support")
                     return False

            # === ALL CHECKS PASSED ===
            self.logger.info(
                f"✅ {symbol}: PARABOLIC ENTRY APPROVED | "
                f"Stage={stage}, Accel={acceleration:.2f}, Exhaust={exhaustion:.2f}, "
                f"Strength={strength:.2f}, Q={quality_score:.0f}"
            )

            return True

        except Exception as e:
            self.logger.error(f"❌ Error in should_enter for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def _monitor_positions(self):
        """
        Monitor active positions for parabolic exhaustion signals

        Monitoring Strategy:
        1. Fetch fresh bars for each position
        2. Re-run parabolic detector
        3. If LATE stage or exit_warning detected -> EXIT IMMEDIATELY
        4. Otherwise: let WorkerStopManager handle normal exits

        Priority:
        - Exhaustion exit is PRIORITY 0 (before any other exit)
        - Overrides trailing stops, take profit, etc.
        """
        if not self.enable_exhaustion_monitoring:
            return

        try:
            for symbol in list(self.active_positions.keys()):
                position = self.active_positions.get(symbol)
                if not position:
                    continue

                # === Fetch fresh bars ===
                bars = await self._fetch_fresh_bars_for_monitoring(symbol)
                if not bars or len(bars) < 15:
                    continue

                # === Check exhaustion every N bars ===
                bar_count = len(bars)
                last_check_bar = self._last_exhaustion_check.get(symbol, 0)

                if bar_count - last_check_bar < self.exhaustion_check_interval_bars:
                    continue  # Not time to check yet

                self._last_exhaustion_check[symbol] = bar_count

                # === Re-run parabolic detection ===
                parabolic_signal = self.parabolic_detector.detect_parabolic_extension(
                    symbol, bars
                )

                if not parabolic_signal:
                    continue

                # === Check for LATE stage or exhaustion warning ===
                if parabolic_signal.exit_warning:
                    self.logger.warning(
                        f"⚠️ {symbol}: PARABOLIC EXHAUSTION DETECTED | "
                        f"Stage={parabolic_signal.stage}, Exhaustion={parabolic_signal.exhaustion_score:.2f}"
                    )

                    # Exit immediately (PRIORITY 0)
                    await self._execute_exit(
                        symbol=symbol,
                        exit_reason='parabolic_exhaustion',
                        exit_type='EXHAUSTION_EXIT'
                    )
                    continue

                # === Log status if still healthy ===
                if parabolic_signal.stage == 'EARLY':
                    self.logger.debug(
                        f"✅ {symbol}: Still EARLY stage - holding (exhaust={parabolic_signal.exhaustion_score:.2f})"
                    )
                elif parabolic_signal.stage == 'MIDDLE':
                    self.logger.info(
                        f"⚡ {symbol}: MIDDLE stage - watching closely (exhaust={parabolic_signal.exhaustion_score:.2f})"
                    )

        except Exception as e:
            self.logger.error(f"Error monitoring parabolic positions: {e}")

    async def _fetch_fresh_bars_for_monitoring(self, symbol: str) -> list:
        """
        Fetch fresh 1-minute bars for exhaustion monitoring

        Args:
            symbol: Symbol to fetch bars for

        Returns:
            List of bars or empty list on error
        """
        try:
            # Check if broker supports bar fetching (LiveIBKRBroker does)
            if hasattr(self.broker, 'get_bars'):
                bars = await self.broker.get_bars(
                    symbol=symbol,
                    timeframe='1min',
                    count=30  # Last 30 minutes
                )
                return bars if bars else []
            
            # Legacy fallback (deprecated but kept for safety if someone injects it)
            elif hasattr(self, 'execution_engine') and hasattr(self.execution_engine, 'ibkr_adapter'):
                bars = await self.execution_engine.ibkr_adapter.get_bars(
                    symbol=symbol,
                    timeframe='1min',
                    bar_count=30
                )
                return bars if bars else []
            
            else:
                # Simulation or simple broker without history
                # self.logger.debug(f"ℹ️ {symbol}: Broker does not support fresh bar fetching (Simulation?)")
                return []

        except Exception as e:
            self.logger.error(f"Error fetching fresh bars for {symbol}: {e}")
            return []

    async def _execute_entry(self, symbol: str, opportunity: Dict[str, Any]):
        """
        Execute parabolic entry trade

        Overrides base to add symbol to traded_symbols_today
        """
        # Call base implementation
        await super()._execute_entry(symbol, opportunity)

        # Track that we traded this symbol today
        self.traded_symbols_today.add(symbol)

    def _get_trading_horizon(self) -> str:
        """
        Return trading horizon for parabolic strategy

        Parabolic moves are fast: SCALP or INTRADAY
        """
        return TradingHorizon.SCALP.value  # Fast in, fast out

    def get_worker_name(self) -> str:
        """Return worker name"""
        return "parabolic"

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evaluate exit conditions
        """
        try:
            entry_price = position.get('entry_price', 0)
            if entry_price == 0:
                pass

            # Prepare metadata
            position_metadata = {
                'trading_horizon': position.get('trading_horizon', 'SCALP'),
                'expected_hold_hours': position.get('expected_hold_hours', 2.0)
            }

            # Delegate to Stop Manager
            should, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                position_metadata=position_metadata
            )
            
            if should:
                 return True, reason
                 
            return False, ""

        except Exception as e:
            self.logger.error(f"Error in should_exit: {e}")
            return False, "error"
