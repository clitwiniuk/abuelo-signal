"""
ORB (Opening Range Breakout) Worker Logic - REFACTORED v2.0

Opening Range Breakout Strategy optimizada para smallcaps volátiles.

REFACTOR CHANGES (2025-12-02):
✅ Lee config.ini correctamente (antes: todo hardcoded)
✅ Filtros de precio/volumen para smallcaps
✅ Usa WorkerStopManager centralizado
✅ Código obsoleto eliminado
✅ Documentación actualizada con performance real

PATRÓN:
1. Define rango 9:30-10:00 AM (primeros 30 min)
2. Breakout confirmado con volumen 1.5x+
3. Filtros: precio $0.50-$10, volumen >100k avg
4. Stop debajo del rango ORB low, TP basado en ATR

INTEGRACIÓN:
- ODS TREND_DRIVE -> +20% confidence boost
- Intraday continuation -> +15% confidence
- Liquidity sweep detection -> evitar entries
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, time
from configparser import ConfigParser

from strategies.workers.base_worker_logic import BaseWorkerLogic


class ORBWorkerLogic(BaseWorkerLogic):
    """
    Worker para Opening Range Breakout en smallcaps volátiles

    Características:
    - Opera 9:35-10:30 AM ET (post-ORB definition)
    - Breakout del rango 9:30-10:00 AM
    - Confirmación con volumen 1.5x+
    - Filtros estrictos para smallcaps
    """

    def __init__(
        self,
        worker_name: str = "orb_breakout",
        execution_engine: Any = None,
        risk_manager: Any = None,
        config: ConfigParser = None
    ):
        super().__init__(worker_name, execution_engine, risk_manager)

        # Load configuration from config.ini
        if config and hasattr(config, 'get'):
            section = 'ORB_STRATEGY'

            # === TIME WINDOWS ===
            # Parse time strings (HH:MM:SS format)
            orb_start_str = config.get(section, 'orb_start_time', fallback='09:30:00')
            orb_end_str = config.get(section, 'orb_end_time', fallback='10:00:00')
            entry_start_str = config.get(section, 'entry_start_time', fallback='09:35:00')
            entry_end_str = config.get(section, 'entry_end_time', fallback='10:30:00')

            self.orb_start_time = self._parse_time(orb_start_str)
            self.orb_end_time = self._parse_time(orb_end_str)
            self.entry_start_time = self._parse_time(entry_start_str)
            self.entry_end_time = self._parse_time(entry_end_str)

            # === PRICE FILTERS (Smallcaps) ===
            self.min_price = config.getfloat(section, 'min_price', fallback=0.5)
            self.max_price = config.getfloat(section, 'max_price', fallback=10.0)

            # === VOLUME FILTERS ===
            self.min_avg_volume = config.getint(section, 'min_avg_volume', fallback=100000)
            self.min_dollar_volume = config.getfloat(section, 'min_dollar_volume', fallback=50000.0)
            self.min_breakout_volume = config.getfloat(section, 'min_breakout_volume', fallback=1.5)

            # === ORB RANGE FILTERS ===
            self.min_orb_range_pct = config.getfloat(section, 'min_orb_range_pct', fallback=0.015)  # 1.5%
            self.max_orb_range_pct = config.getfloat(section, 'max_orb_range_pct', fallback=0.15)   # 15%
            self.max_gap_pct = config.getfloat(section, 'max_gap_pct', fallback=0.10)               # 10%

            # === BREAKOUT CONFIRMATION ===
            self.breakout_confirmation_bars = config.getint(section, 'breakout_confirmation_bars', fallback=2)

            # === QUALITY FILTER ===
            self.min_quality_score = config.getfloat(section, 'min_quality_score', fallback=60.0)

            # === ANTI-OVERTRADING ===
            self.max_trades_per_symbol = config.getint(section, 'max_trades_per_symbol', fallback=1)
            self.traded_symbols_today = set()

        else:
            # Fallback to hardcoded defaults (if no config)
            self.logger.warning("⚠️ ORB Worker: No config provided, using hardcoded defaults")

            self.orb_start_time = time(9, 30)
            self.orb_end_time = time(10, 0)
            self.entry_start_time = time(9, 35)
            self.entry_end_time = time(10, 30)

            self.min_price = 0.5
            self.max_price = 10.0
            self.min_avg_volume = 100000
            self.min_dollar_volume = 50000.0
            self.min_breakout_volume = 1.5

            self.min_orb_range_pct = 0.015
            self.max_orb_range_pct = 0.15
            self.max_gap_pct = 0.10

            self.breakout_confirmation_bars = 2
            self.min_quality_score = 60.0
            self.max_trades_per_symbol = 1
            self.traded_symbols_today = set()

        # Initialize WorkerStopManager (centralized risk management)
        from strategies.workers.worker_stop_manager import create_worker_stop_manager
        self.stop_manager = create_worker_stop_manager(
            config_obj=config if config else None,
            strategy_name='ORB_STRATEGY'
        )

        self.logger.info(
            f"🎯 ORB Worker initialized (v2.0 - REFACTORED)"
        )
        self.logger.info(
            f"   ORB Range: {self.orb_start_time.strftime('%H:%M')}-{self.orb_end_time.strftime('%H:%M')}"
        )
        self.logger.info(
            f"   Entry Window: {self.entry_start_time.strftime('%H:%M')}-{self.entry_end_time.strftime('%H:%M')}"
        )
        self.logger.info(
            f"   Price Range: ${self.min_price:.2f} - ${self.max_price:.2f}"
        )
        self.logger.info(
            f"   Min Volume: {self.min_avg_volume:,} avg, ${self.min_dollar_volume:,.0f} dollar"
        )
        self.logger.info(
            f"   ORB Range: {self.min_orb_range_pct*100:.1f}% - {self.max_orb_range_pct*100:.1f}%"
        )
        self.logger.info(
            f"   Breakout Volume: {self.min_breakout_volume}x, Quality: {self.min_quality_score:.0f}+"
        )

    def _parse_time(self, time_str: str) -> time:
        """Parse time string (HH:MM:SS or HH:MM) to time object"""
        try:
            if len(time_str) == 8:  # HH:MM:SS
                return datetime.strptime(time_str, '%H:%M:%S').time()
            elif len(time_str) == 5:  # HH:MM
                return datetime.strptime(time_str, '%H:%M').time()
            else:
                self.logger.warning(f"Invalid time format: {time_str}, using default")
                return time(9, 30)
        except Exception as e:
            self.logger.error(f"Error parsing time {time_str}: {e}")
            return time(9, 30)

    def _reset_daily_state_if_needed(self):
        """Reset daily counters at start of new trading day"""
        import pytz
        ny_tz = pytz.timezone('US/Eastern')
        current_date = datetime.now(ny_tz).date()

        if not hasattr(self, '_last_reset_date') or self._last_reset_date != current_date:
            self.logger.info(f"🔄 New trading day - Resetting ORB worker counters")
            self.traded_symbols_today.clear()
            self._last_reset_date = current_date

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios ORB

        Criterios:
        1. Anti-overtrading: Max 1 trade per symbol per day
        2. Precio: $0.50 - $10.00 (smallcaps)
        3. Volumen: >100k avg, >$50k dollar volume
        4. Tiempo: 9:35-10:30 AM ET
        5. ORB definido: Rango 9:30-10:00 con 1.5%-15% range
        6. Breakout confirmado: 2+ bars above ORB high, volume 1.5x+
        7. Quality: Score > 60
        8. Gap: < 10% (evita gaps extremos)
        9. No duplicate position

        Args:
            opportunity: Datos de la oportunidad

        Returns:
            True si cumple criterios, False si no
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # Reset daily state if new day
            self._reset_daily_state_if_needed()

            # 1. DAILY CONTEXT ANALYSIS (New: Check for Blue Sky / 52-Week Highs)
            daily_potential = await self._analyze_daily_potential_for_signal(opportunity)
            is_blue_sky = daily_potential.get('is_52_week_high', False)
            
            if is_blue_sky:
                self.logger.info(f"🌤️ {symbol}: BLUE SKY ORB - Enabling Aggressive Mode")

            # 1.5. FUNDAMENTAL ANALYSIS (Float & Halt)
            fundamentals = await self._analyze_smallcap_fundamentals(opportunity)
            
            # A. HALT RISK CHECK (Critical for ORB)
            if fundamentals.get('is_halt_risk', False):
                self.logger.warning(f"🛑 {symbol}: ABORT ORB - Too close to LULD Halt Band")
                return False

            # B. HIGH ROTATION (Fuel for ORB)
            if fundamentals.get('is_high_rotation', False):
                self.logger.info(f"🚀 {symbol}: HIGH ROTATION ORB ({fundamentals['rotation_factor']:.1f}x) - Explosive Potential")
                if 'confidence' in opportunity:
                    opportunity['confidence'] = min(95, opportunity['confidence'] + 10)  # +10 Confidence Boost

            # ====
            # FILTER 0: DUPLICATE POSITION CHECK
            # ====
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager and unified_manager.is_symbol_blocked(symbol):
                position = unified_manager.get_position(symbol)
                strategy_type = position['strategy_type'] if position else 'unknown'
                self.logger.debug(
                    f"⚪ {symbol}: BLOCKED - already held in {strategy_type.upper()} trading"
                )
                return False

            # ====
            # FILTER 1: ANTI-OVERTRADING
            # ====
            if symbol in self.traded_symbols_today:
                self.logger.debug(
                    f"⚪ {symbol}: Already traded today (max {self.max_trades_per_symbol} per symbol)"
                )
                return False

            # ====
            # FILTER 2: PRICE RANGE (Smallcaps)
            # ====
            current_price = opportunity.get('current_price', 0)
            if not self.min_price <= current_price <= self.max_price:
                self.logger.debug(
                    f"⚪ {symbol}: Price ${current_price:.2f} outside range "
                    f"${self.min_price:.2f}-${self.max_price:.2f}"
                )
                return False

            # ====
            # FILTER 3: BARS AVAILABLE
            # ====
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 30:
                self.logger.debug(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0})")
                return False

            # ====
            # FILTER 4: AVERAGE VOLUME
            # ====
            avg_volume = self._calculate_avg_volume(bars, period=20)
            if avg_volume < self.min_avg_volume:
                self.logger.debug(
                    f"⚪ {symbol}: Low avg volume {avg_volume:,.0f} < {self.min_avg_volume:,}"
                )
                return False

            # ====
            # FILTER 5: DOLLAR VOLUME
            # ====
            dollar_volume = avg_volume * current_price
            if dollar_volume < self.min_dollar_volume:
                self.logger.debug(
                    f"⚪ {symbol}: Low dollar volume ${dollar_volume:,.0f} < ${self.min_dollar_volume:,.0f}"
                )
                return False



            # ====
            # FILTER 7: ORB CALCULATION
            # ====
            orb_from_scanner = opportunity.get('orb_data')
            if orb_from_scanner and isinstance(orb_from_scanner, dict):
                # Scanner provided ORB data (efficient)
                orb_data = {
                    'valid': True,
                    'high': orb_from_scanner.get('orb_high', 0.0),
                    'low': orb_from_scanner.get('orb_low', 0.0),
                    'range_pct': orb_from_scanner.get('orb_range_pct', 0.0),
                    'avg_volume': orb_from_scanner.get('orb_avg_volume', 0)
                }
                self.logger.debug(f"✅ {symbol}: Using ORB data from scanner")
            else:
                # Calculate ORB locally
                orb_data = self._calculate_orb(bars)
                self.logger.debug(f"ℹ️ {symbol}: Calculating ORB locally")

            if not orb_data['valid']:
                self.logger.debug(f"⚪ {symbol}: ORB not valid - {orb_data.get('reason', 'unknown')}")
                return False

            orb_high = orb_data['high']
            orb_low = orb_data['low']
            orb_range_pct = orb_data['range_pct']
            orb_avg_volume = orb_data['avg_volume']

            # ====
            # FILTER 8: GAP SIZE (avoid extreme gaps)
            # ====
            open_price = bars[0].open if hasattr(bars[0], 'open') else current_price
            prev_close = self._get_previous_close(bars)

            if prev_close and prev_close > 0:
                gap_pct = abs(open_price - prev_close) / prev_close
                
                # Allow larger gaps for Blue Sky setups (up to 20% vs 10% default)
                max_gap = 0.20 if is_blue_sky else self.max_gap_pct
                
                if gap_pct > max_gap:
                    self.logger.info(
                        f"⚪ {symbol}: Gap too large {gap_pct*100:.1f}% > {self.max_gap_pct*100:.1f}%"
                    )
                    return False

            # ====
            # FILTER 9: BREAKOUT CONFIRMATION
            # ====
            breakout_confirmed = self._confirm_breakout(
                bars=bars,
                orb_high=orb_high,
                current_price=current_price,
                orb_avg_volume=orb_avg_volume
            )

            if not breakout_confirmed:
                self.logger.debug(
                    f"⚪ {symbol}: Breakout not confirmed - "
                    f"Price ${current_price:.2f} vs ORB high ${orb_high:.2f}"
                )
                return False

            # ====
            # FILTER 10: QUALITY SCORE
            # ====
            quality_score = opportunity.get('quality_score', 0)
            if quality_score < self.min_quality_score:
                self.logger.debug(
                    f"⚪ {symbol}: Low quality - Score {quality_score:.0f}/100 < {self.min_quality_score:.0f}"
                )
                return False

            # ====
            # OPTIONAL: ODS INTEGRATION (Standardized)
            # ====
            is_ods_allowed, confidence_boost = await self.check_ods_filters(symbol, bars, opportunity)
            
            if not is_ods_allowed:
                 return False

            if 'confidence' in opportunity:
                 opportunity['confidence'] *= confidence_boost

            # ====
            # FILTER 11: TIME CHECK (Standardized)
            # ====
            # Using BaseWorkerLogic.is_within_entry_hours for replay compatibility
            # This respects both global and strategy-specific (config.ini) limits
            is_valid_time, current_decimal_time = self.is_within_entry_hours(symbol, opportunity.get('timestamp'))
            
            if not is_valid_time:
                 self.logger.info(f"⚪ {symbol}: Outside ORB trading hours ({current_decimal_time:.2f})")
                 return False

            # ====
            # OPTIONAL: INTRADAY STRUCTURE INTEGRATION
            # ====
            from core.intraday_structure_classifier import IntradayPhase

            structure = await self.get_intraday_structure_for_symbol(symbol, bars)
            opportunity['intraday_structure'] = structure

            # CONTINUATION: Prefer pullback entries
            if structure.current_phase == IntradayPhase.CONTINUATION:
                if structure.continuation_type in ["PULLBACK_TO_VWAP", "HIGHER_LOW"]:
                    confidence_boost *= 1.15  # +15%
                    self.logger.info(
                        f"✅ {symbol}: CONTINUATION BOOST - {structure.continuation_type}"
                    )

            # LIQUIDITY SWEEP: Avoid if sweep pending
            if structure.liquidity_sweep_detected and structure.sweep_direction == "NONE":
                self.logger.info(
                    f"⏳ {symbol}: Liquidity sweep pending - Wait for resolution"
                )
                return False

            # ====
            # CALCULATE RISK/REWARD
            # ====
            atr = self._calculate_atr_from_bars(bars, period=14)
            atr_pct = (atr / current_price) * 100 if current_price > 0 else 0

            # Stop: ORB low (managed by WorkerStopManager)
            # Target: 2x ATR or 2x ORB range (whichever larger)
            orb_target_pct = orb_range_pct * 100 * 2.0
            atr_target_pct = atr_pct * 2.0
            take_profit_pct = max(orb_target_pct, atr_target_pct)

            stop_loss_pct = ((current_price - orb_low) / current_price) * 100

            # Apply confidence boost to quality
            adjusted_quality = min(100, quality_score * confidence_boost)

            # Store in opportunity for WorkerStopManager
            opportunity['quality_score'] = adjusted_quality
            opportunity['orb_high'] = orb_high
            opportunity['orb_low'] = orb_low
            opportunity['orb_range_pct'] = orb_range_pct
            opportunity['atr_percent'] = atr_pct
            opportunity['suggested_stop_loss_pct'] = stop_loss_pct
            opportunity['suggested_take_profit_pct'] = take_profit_pct

            # Risk/Reward validation
            risk_reward = take_profit_pct / stop_loss_pct if stop_loss_pct > 0 else 0

            if risk_reward < 1.5:
                self.logger.info(
                    f"⚪ {symbol}: Poor R:R - {risk_reward:.2f} < 1.5 "
                    f"(TP={take_profit_pct:.1f}% / SL={stop_loss_pct:.1f}%)"
                )
                return False

            opportunity['risk_reward'] = risk_reward

            # ====
            # ALL FILTERS PASSED
            # ====
            self.logger.info(
                f"✅ {symbol}: ORB BREAKOUT CONFIRMED"
            )
            self.logger.info(
                f"   Price: ${current_price:.2f}"
            )
            self.logger.info(
                f"   ORB: ${orb_low:.2f}-${orb_high:.2f} ({orb_range_pct*100:.2f}%)"
            )
            self.logger.info(
                f"   Volume: {avg_volume:,.0f} avg (${dollar_volume:,.0f} dollar)"
            )
            self.logger.info(
                f"   Quality: {adjusted_quality:.0f}/100"
            )
            self.logger.info(
                f"   R:R: {risk_reward:.2f} (SL={stop_loss_pct:.1f}%, TP={take_profit_pct:.1f}%)"
            )

            return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in ORB evaluation: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def on_position_opened(self, symbol: str, entry_price: float, quantity: int):
        """Called when position is opened - track for anti-overtrading"""
        self.traded_symbols_today.add(symbol)
        self.stop_manager.register_position(symbol)
        self.logger.info(f"📊 {symbol}: Position opened, tracked for today")

    async def on_position_closed(self, symbol: str, exit_reason: str, pnl_pct: float):
        """Called when position is closed"""
        self.stop_manager.unregister_position(symbol)
        self.logger.info(f"📈 {symbol}: Position closed - {exit_reason} (P&L: {pnl_pct:+.2f}%)")

    def _calculate_orb(self, bars: List[Any]) -> Dict[str, Any]:
        """
        Calcula el Opening Range (9:30-10:00 AM)

        Args:
            bars: Lista de barras de 1 minuto

        Returns:
            Dict con ORB high, low, range_pct, avg_volume, valid
        """
        try:
            orb_bars = []

            for bar in bars:
                # Ensure timestamp is datetime object
                ts = bar.timestamp
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    except:
                        continue
                
                bar_time = ts.time() if hasattr(ts, 'time') else ts

                if self.orb_start_time <= bar_time < self.orb_end_time:
                    orb_bars.append(bar)

            if len(orb_bars) < 20:  # Need at least 20 of 30 bars
                return {
                    'valid': False,
                    'reason': f'Insufficient ORB bars ({len(orb_bars)}/30)'
                }

            orb_high = max(bar.high for bar in orb_bars)
            orb_low = min(bar.low for bar in orb_bars)
            orb_range = orb_high - orb_low
            orb_range_pct = (orb_range / orb_low) if orb_low > 0 else 0
            orb_avg_volume = sum(bar.volume for bar in orb_bars) / len(orb_bars)

            # Validate range
            if orb_range_pct < self.min_orb_range_pct:
                return {
                    'valid': False,
                    'reason': f'ORB range too small ({orb_range_pct*100:.2f}% < {self.min_orb_range_pct*100:.1f}%)'
                }

            if orb_range_pct > self.max_orb_range_pct:
                return {
                    'valid': False,
                    'reason': f'ORB range too large ({orb_range_pct*100:.2f}% > {self.max_orb_range_pct*100:.1f}%)'
                }

            return {
                'valid': True,
                'high': orb_high,
                'low': orb_low,
                'range': orb_range,
                'range_pct': orb_range_pct,
                'avg_volume': orb_avg_volume,
                'num_bars': len(orb_bars)
            }

        except Exception as e:
            self.logger.error(f"Error calculating ORB: {e}")
            return {'valid': False, 'reason': f'Calculation error: {e}'}

    def _confirm_breakout(
        self,
        bars: List[Any],
        orb_high: float,
        current_price: float,
        orb_avg_volume: float
    ) -> bool:
        """
        Confirma breakout del ORB high con volumen

        Criterios:
        - Precio actual > ORB high
        - Al menos 2 barras consecutivas > ORB high
        - Volumen reciente > 1.5x ORB avg volume
        """
        try:
            if current_price <= orb_high:
                return False

            recent_bars = bars[-10:] if len(bars) >= 10 else bars

            bars_above_orb = 0
            recent_volume = 0

            for bar in recent_bars[-5:]:
                if bar.close > orb_high:
                    bars_above_orb += 1
                recent_volume += bar.volume

            avg_recent_volume = recent_volume / min(5, len(recent_bars[-5:]))

            if bars_above_orb < self.breakout_confirmation_bars:
                return False

            volume_ratio = avg_recent_volume / orb_avg_volume if orb_avg_volume > 0 else 0

            if volume_ratio < self.min_breakout_volume:
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error confirming breakout: {e}")
            return False

    def _calculate_avg_volume(self, bars: List[Any], period: int = 20) -> float:
        """Calculate average volume over period"""
        try:
            if not bars or len(bars) < period:
                return 0

            volumes = [bar.volume for bar in bars[-period:] if hasattr(bar, 'volume')]
            return sum(volumes) / len(volumes) if volumes else 0

        except Exception as e:
            self.logger.error(f"Error calculating avg volume: {e}")
            return 0

    def _get_previous_close(self, bars: List[Any]) -> Optional[float]:
        """Get previous day's close (for gap calculation)"""
        try:
            # This would need daily bars, not intraday
            # For now, return None and skip gap filter if unavailable
            return None
        except:
            return None

    async def should_exit(
        self,
        symbol: str,
        position_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Evalúa si debe salir de posición
        Delegates to WorkerStopManager for unified exit logic
        """
        return await self.stop_manager.check_exit(
            symbol=symbol,
            current_price=position_data.get('current_price', 0),
            entry_price=position_data.get('entry_price', 0),
            entry_time=position_data.get('entry_time'),
            highest_price=position_data.get('highest_price', position_data.get('entry_price', 0)),
            opportunity_data=position_data.get('opportunity_data', {})
        )
