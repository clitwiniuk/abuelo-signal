
"""
VCP Strict SHORT Worker Logic
Worker especializado en VCP SHORT (Inverse) con validación ESTRICTA de VWAP
"""

import logging
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timedelta
from .base_worker_logic import BaseWorkerLogic


class VCPStrictShortWorkerLogic(BaseWorkerLogic):
    """
    VCP SHORT Worker con validación ESTRICTA de VWAP slope
    
    REGLA DE ORO:
    - Solo CORTOS (Distribución)
    - VWAP slope < -0.10% (distribución activa)
    """

    def __init__(self, worker_name='vcp_strict_short', execution_engine=None, risk_manager=None, config=None):
        super().__init__(
            worker_name=worker_name,
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración VCP Strict Short
        self.entry_threshold_pct = getattr(config, 'vcp_strict_entry_threshold', 98.0)
        self.min_price = getattr(config, 'vcp_strict_min_price', 1.0)
        self.max_price = getattr(config, 'vcp_strict_max_price', 25.0)
        self.min_volume_ratio = getattr(config, 'vcp_strict_min_volume_ratio', 1.0)
        self.min_quality_score = getattr(config, 'vcp_strict_min_quality_score', 60.0)

        # VWAP STRICT SHORT SETTINGS
        self.max_vwap_slope_short = getattr(config, 'vcp_strict_max_vwap_slope_short', -0.10)  # -0.10% máximo
        self.vwap_slope_lookback_minutes = getattr(config, 'vcp_strict_vwap_slope_lookback', 10)  # 10 min lookback
        self.min_expansions = getattr(config, 'vcp_strict_min_expansions', 2)

        # ODS Filters
        self.enable_ods_filters = getattr(config, 'enable_ods_filters', True)

        # Catalyst requirements
        self.require_catalyst = getattr(config, 'vcp_strict_require_catalyst', False)
        self.accepted_catalysts = ['NEWS', 'EARNINGS', 'HALT', 'RUNNER', 'FDA', 'CONTRACT', 'OTHER', 'TECHNICAL']

        self.config = config

        # Initialize stop manager with SHORT config
        from .worker_stop_manager import create_worker_stop_manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'VCP_STRICT_STRATEGY')
        else:
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=5.0,
                take_profit_pct=15.0,
                quick_target_pct=0.0,
                trailing_activation=8.0,
                trailing_distance=4.0,
                max_position_hours=6.0
            ))

        self.logger.info(
            f"🎯 VCP STRICT SHORT Worker configured: "
            f"expansions>={self.min_expansions}, "
            f"slope<={self.max_vwap_slope_short:.2f}%"
        )

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> Tuple[float, float]:
        """Public interface for completion (Low priority for Shorts)"""
        return 0.0, 0.0

    def _determine_vwap_slope(self, bars: list, vwap_window_minutes: int = 60) -> Tuple[float, float]:
        """Calcula pendiente de VWAP"""
        try:
            if not bars or len(bars) < self.vwap_slope_lookback_minutes:
                return 0.0, 0.0

            recent_bars = bars[-vwap_window_minutes:] if len(bars) >= vwap_window_minutes else bars
            current_vwap = self.calculate_vwap_from_bars(recent_bars)

            if current_vwap is None:
                return 0.0, 0.0

            bars_until_lookback = recent_bars[:-self.vwap_slope_lookback_minutes]
            previous_vwap = self.calculate_vwap_from_bars(bars_until_lookback)

            if previous_vwap is None:
                return 0.0, current_vwap

            vwap_slope_pct = ((current_vwap - previous_vwap) / previous_vwap) * 100
            return vwap_slope_pct, current_vwap

        except Exception as e:
            self.logger.error(f"Error in VWAP slope: {e}")
            return 0.0, 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """Evalúa entrada VCP STRICT SHORT"""
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            fundamentals = await self._analyze_smallcap_fundamentals(opportunity)
            if fundamentals.get('is_halt_risk', False):
                return False

            # Check duplicate positions
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()
            if unified_manager and unified_manager.is_symbol_blocked(symbol):
                return False

            current_price = opportunity.get('current_price', 0)
            volume_ratio = opportunity.get('volume_ratio', 1.0)
            quality_score = opportunity.get('quality_score', 0)

            if not (self.min_price <= current_price <= self.max_price):
                return False

            if volume_ratio < self.min_volume_ratio:
                return False

            if quality_score < self.min_quality_score:
                return False

            if self.require_catalyst:
                catalyst = opportunity.get('catalyst_type', 'NONE')
                if catalyst not in self.accepted_catalysts:
                    return False

            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 15:
                return False

            # VWAP SLOPE CHECK (SHORT ONLY)
            vwap_slope_pct, current_vwap = self._determine_vwap_slope(bars)
            
            if vwap_slope_pct > self.max_vwap_slope_short:
                self.logger.info(f"⚪ {symbol}: VWAP slope {vwap_slope_pct:+.2f}% > max {self.max_vwap_slope_short:.2f}% (too bullish)")
                return False
                
            # Price must be near/below VWAP
            if current_price > current_vwap * 1.02:
                self.logger.info(f"⚪ {symbol}: Price above VWAP resistance zone")
                return False

            opportunity['trade_direction'] = 'SHORT'  # Explicit

            # ODS Filter
            is_ods_allowed, confidence_boost = await self.check_ods_filters(symbol, bars, opportunity)
            if not is_ods_allowed:
                return False

            if 'confidence' in opportunity:
                 opportunity['confidence'] *= confidence_boost

            # VCP Pattern Detection (Expansions)
            expansions = self._detect_expansions(bars)

            if len(expansions) < self.min_expansions:
                return False

            if not self._validate_expansions_increasing(expansions):
                return False

            # Pivot detection (SHORT)
            pivot_detected, pivot_details, resistance_level = self._detect_inverse_vcp_pivot(
                bars, expansions, current_price, symbol
            )

            if not pivot_detected:
                return False

            opportunity['resistance_level'] = resistance_level
            
            # Time check
            is_valid_hours, _ = self.is_within_entry_hours(symbol, timestamp=opportunity.get('timestamp'))
            if not is_valid_hours:
                return False

            self.logger.info(f"✅ {symbol}: VCP STRICT SHORT APPROVED! {pivot_details}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error evaluating VCP STRICT SHORT for {symbol}: {e}")
            return False

    async def should_exit(self, symbol: str, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        """Exit logic for VCP SHORT"""
        try:
            entry_price = position.get('entry_price', 0)

            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 0),
                'opportunity_data': position.get('opportunity_data', {}),
                'side': 'SHORT',  # Explicit SHORT side -> BLOCKS OVERNIGHT PROMOTION
                'strategy': self.worker_name
            }

            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=None,
                position_metadata=position_metadata
            )

            if should_exit:
                return True, reason

            return False, "HOLDING"

        except Exception as e:
            self.logger.error(f"❌ Error evaluating VCP STRICT SHORT exit: {e}")
            return True, "ERROR_EXIT"

    def _detect_expansions(self, bars: List) -> List[Dict[str, Any]]:
        """Detect expansions (Inverse VCP)"""
        try:
            if len(bars) < 20: return []
            expansions = []
            window_size = 10
            for i in range(0, len(bars) - window_size, 5):
                window_bars = bars[i:i + window_size]
                window_high = max(bar.high for bar in window_bars)
                window_low = min(bar.low for bar in window_bars)
                window_range_pct = ((window_high - window_low) / window_low) * 100
                avg_volume = sum(bar.volume for bar in window_bars) / len(window_bars)

                if 1.5 <= window_range_pct < 8.0:
                    expansions.append({
                        'start_idx': i, 'end_idx': i + window_size,
                        'range_pct': window_range_pct, 'avg_volume': avg_volume,
                        'high': window_high, 'low': window_low
                    })
            return expansions
        except Exception: return []

    def _validate_expansions_increasing(self, expansions: List[Dict]) -> bool:
        """Validate expansions getting WIDER"""
        if len(expansions) < 2: return True
        for i in range(len(expansions) - 1):
            if expansions[i + 1]['range_pct'] <= expansions[i]['range_pct']: return False
        return True

    def _detect_inverse_vcp_pivot(self, bars: List, expansions: List[Dict], current_price: float, symbol: str) -> Tuple[bool, str, float]:
        """Detect SHORT pivot"""
        try:
            if not expansions: return False, "No expansions", 0.0
            last_expansion = expansions[-1]
            recent_high = max(bar.high for bar in bars[-10:]) if len(bars) >= 10 else current_price
            recent_low = min(bar.low for bar in bars[-20:]) if len(bars) >= 20 else current_price
            decline_pct = ((recent_high - current_price) / recent_high) * 100 if recent_high > 0 else 0
            proximity_to_low = (current_price / recent_low) * 100 if recent_low > 0 else 0

            last_10_bars = bars[-10:] if len(bars) >= 10 else bars
            avg_recent_volume = sum(bar.volume for bar in last_10_bars) / len(last_10_bars)
            volume_ratio = avg_recent_volume / last_expansion['avg_volume'] if last_expansion['avg_volume'] > 0 else 0

            if decline_pct >= 2.0 and proximity_to_low <= 110.0:
                return True, f"SHORT Pivot {proximity_to_low:.1f}% of low, VolRatio {volume_ratio:.2f}", recent_high
            return False, "No pivot", last_expansion['high']
        except Exception: return False, "Error", 0.0
