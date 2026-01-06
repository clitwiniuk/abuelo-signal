
"""
VCP Strict LONG Worker Logic
Worker especializado en VCP LONG con validación ESTRICTA de VWAP
"""

import logging
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timedelta
from .base_worker_logic import BaseWorkerLogic
from core.trade_arbiter import TradingHorizon


class VCPStrictLongWorkerLogic(BaseWorkerLogic):
    """
    VCP LONG Worker con validación ESTRICTA de VWAP slope
    
    REGLA DE ORO:
    - Solo LARGOS (Acumulación)
    - VWAP slope > +0.10% (acumulación activa)
    """

    def __init__(self, worker_name='vcp_strict_long', execution_engine=None, risk_manager=None, config=None):
        super().__init__(
            worker_name=worker_name,
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración VCP Strict
        self.min_contractions = getattr(config, 'vcp_strict_min_contractions', 2)
        self.entry_threshold_pct = getattr(config, 'vcp_strict_entry_threshold', 98.0)
        self.min_price = getattr(config, 'vcp_strict_min_price', 1.0)
        self.max_price = getattr(config, 'vcp_strict_max_price', 25.0)
        self.min_volume_ratio = getattr(config, 'vcp_strict_min_volume_ratio', 1.0)
        self.min_quality_score = getattr(config, 'vcp_strict_min_quality_score', 60.0)

        # VWAP STRICT SETTINGS
        self.min_vwap_slope_long = getattr(config, 'vcp_strict_min_vwap_slope_long', 0.10)  # +0.10% mínimo
        self.vwap_slope_lookback_minutes = getattr(config, 'vcp_strict_vwap_slope_lookback', 10)  # 10 min lookback

        # ODS Filters
        self.enable_ods_filters = getattr(config, 'enable_ods_filters', True)

        # Catalyst requirements
        self.require_catalyst = getattr(config, 'vcp_strict_require_catalyst', False)
        self.accepted_catalysts = ['NEWS', 'EARNINGS', 'HALT', 'RUNNER', 'FDA', 'CONTRACT', 'OTHER', 'TECHNICAL']

        self.config = config

        # Initialize stop manager with LONG strategy config
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
            f"🎯 VCP STRICT LONG Worker configured: "
            f"contractions>={self.min_contractions}, "
            f"slope>+{self.min_vwap_slope_long:.2f}%"
        )

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> Tuple[float, float]:
        """Public interface for pattern completion"""
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            current_price = opportunity.get('current_price', 0)
            bars = self.get_bars_from_opportunity(opportunity)

            if not bars:
                return 0.0, 0.0

            return await self._calculate_vcp_completion(bars, current_price, symbol)
        except Exception as e:
            self.logger.error(f"Error in calculate_pattern_completion: {e}")
            return 0.0, 0.0

    async def _calculate_vcp_completion(self, bars: list, current_price: float, symbol: str) -> Tuple[float, float]:
        """Calcula % de completitud del patrón VCP (0-100%)"""
        try:
            if len(bars) < 20:
                return 0.0, 0.0

            # Detect contractions
            contractions = self._detect_contractions(bars)

            if len(contractions) == 0:
                return 20.0, 0.0

            # Filter overlapping contractions
            contractions = self._filter_overlapping_contractions(contractions)

            if len(contractions) < self.min_contractions:
                completion = 20.0 + (len(contractions) * 20.0)
                support = contractions[-1]['low'] if contractions else 0.0
                return completion, support

            if not self._validate_contractions_decreasing(contractions):
                return 50.0, contractions[-1]['low']

            num_contractions = len(contractions)
            base_completion = min(60.0 + (num_contractions - 2) * 10.0, 80.0)

            recent_high = max(bar.high for bar in bars[-20:]) if len(bars) >= 20 else current_price
            proximity_pct = (current_price / recent_high) * 100 if recent_high > 0 else 0

            if proximity_pct >= 98.0:
                proximity_bonus = min((proximity_pct - 98.0) * 10.0, 20.0)
                completion = min(base_completion + proximity_bonus, 100.0)
            else:
                completion = base_completion

            support_level = contractions[-1]['low'] if contractions else 0.0
            return completion, support_level

        except Exception as e:
            self.logger.error(f"Error calculating VCP completion for {symbol}: {e}")
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
        """Evalúa entrada VCP STRICT LONG"""
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            daily_potential = await self._analyze_daily_potential_for_signal(opportunity)
            is_blue_sky = daily_potential.get('is_52_week_high', False)

            if is_blue_sky:
                self.logger.info(f"🌤️ {symbol}: Blue Sky detected")

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

            # VWAP SLOPE CHECK (LONG ONLY)
            vwap_slope_pct, current_vwap = self._determine_vwap_slope(bars)
            
            if vwap_slope_pct < self.min_vwap_slope_long:
                self.logger.info(f"⚪ {symbol}: VWAP slope {vwap_slope_pct:+.2f}% < min {self.min_vwap_slope_long:.2f}%")
                return False
                
            # Price must be near/above VWAP
            if current_price < current_vwap * 0.98:
                self.logger.info(f"⚪ {symbol}: Price below VWAP support zone")
                return False

            opportunity['trade_direction'] = 'LONG'

            # ODS Filter
            is_ods_allowed, confidence_boost = await self.check_ods_filters(symbol, bars, opportunity)
            if not is_ods_allowed:
                return False

            if 'confidence' in opportunity:
                 opportunity['confidence'] *= confidence_boost

            # VCP Pattern Detection
            completion, support_level = await self._calculate_vcp_completion(bars, current_price, symbol)

            if completion < 40.0:
                return False

            contractions = self._detect_contractions(bars)
            if len(contractions) < self.min_contractions:
                return False

            if not self._validate_volume_pattern(contractions, allow_flat_volume=False):
                return False

            pivot_detected, pivot_details, level = self._detect_vcp_pivot(
                bars, contractions, current_price, symbol, allow_breakout_buy=False
            )

            if not pivot_detected:
                return False

            opportunity['support_level'] = level
            
            # Time check
            is_valid_hours, _ = self.is_within_entry_hours(symbol, timestamp=opportunity.get('timestamp'))
            if not is_valid_hours:
                return False

            self.logger.info(f"✅ {symbol}: VCP STRICT LONG APPROVED! {pivot_details}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error evaluating VCP STRICT LONG for {symbol}: {e}")
            return False

    async def should_exit(self, symbol: str, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        """Exit logic for VCP LONG"""
        try:
            entry_price = position.get('entry_price', 0)

            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 0),
                'opportunity_data': position.get('opportunity_data', {}),
                'side': 'LONG', # Explicit LONG side
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
            self.logger.error(f"❌ Error evaluating VCP STRICT LONG exit: {e}")
            return True, "ERROR_EXIT"

    def _detect_contractions(self, bars: List) -> List[Dict[str, Any]]:
        """Detect contractions in VCP pattern"""
        try:
            if len(bars) < 20: return []
            contractions = []
            window_size = 10
            for i in range(0, len(bars) - window_size, 5):
                window_bars = bars[i:i + window_size]
                window_high = max(bar.high for bar in window_bars)
                window_low = min(bar.low for bar in window_bars)
                window_range_pct = ((window_high - window_low) / window_low) * 100
                avg_volume = sum(bar.volume for bar in window_bars) / len(window_bars)

                if 1.5 <= window_range_pct < 5.0:
                    contractions.append({
                        'start_idx': i, 'end_idx': i + window_size,
                        'range_pct': window_range_pct, 'avg_volume': avg_volume,
                        'high': window_high, 'low': window_low
                    })
            return contractions
        except Exception: return []

    def _filter_overlapping_contractions(self, contractions: List[Dict]) -> List[Dict]:
        """Filter overlapping contractions"""
        if len(contractions) <= 1: return contractions
        filtered = []
        skip_until = -1
        for i, contraction in enumerate(contractions):
            if i < skip_until: continue
            overlapping = [contraction]
            for j in range(i + 1, len(contractions)):
                if contractions[j]['start_idx'] < contraction['end_idx']:
                    overlapping.append(contractions[j])
                else: break
            tightest = min(overlapping, key=lambda c: c['range_pct'])
            filtered.append(tightest)
            skip_until = max(c['end_idx'] for c in overlapping)
        return filtered

    def _validate_contractions_decreasing(self, contractions: List[Dict]) -> bool:
        if len(contractions) < 2: return True
        for i in range(len(contractions) - 1):
            if contractions[i + 1]['range_pct'] >= contractions[i]['range_pct']: return False
        return True

    def _validate_volume_pattern(self, contractions: List[Dict], allow_flat_volume: bool = False) -> bool:
        if len(contractions) < 2: return True
        for i in range(len(contractions) - 1):
            next_vol = contractions[i + 1]['avg_volume']
            current_vol = contractions[i]['avg_volume']
            if allow_flat_volume:
                if next_vol > current_vol * 1.2: return False
            else:
                if next_vol >= current_vol: return False
        return True

    def _detect_vcp_pivot(self, bars: List, contractions: List[Dict], current_price: float, symbol: str, allow_breakout_buy: bool = False) -> Tuple[bool, str, float]:
        try:
            if not contractions: return False, "No contractions", 0.0
            last_contraction = contractions[-1]
            recent_high = max(bar.high for bar in bars[-20:]) if len(bars) >= 20 else current_price
            recent_low = min(bar.low for bar in bars[-10:]) if len(bars) >= 10 else current_price
            recovery_pct = ((current_price - recent_low) / recent_low) * 100 if recent_low > 0 else 0
            proximity_to_high = (current_price / recent_high) * 100 if recent_high > 0 else 0
            
            last_10_bars = bars[-10:] if len(bars) >= 10 else bars
            avg_recent_volume = sum(bar.volume for bar in last_10_bars) / len(last_10_bars)
            volume_ratio = avg_recent_volume / last_contraction['avg_volume'] if last_contraction['avg_volume'] > 0 else 0

            if recovery_pct >= 2.0 and proximity_to_high >= 90.0:
                return True, f"Pivot {proximity_to_high:.1f}% of high, VolRatio {volume_ratio:.2f}", recent_low
            return False, "No pivot", last_contraction['low']
        except Exception: return False, "Error", 0.0
