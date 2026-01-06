"""
ORB (Opening Range Breakout) Worker Logic

Opening Range Breakout Strategy optimizada para smallcaps volátiles.

EDGE VALIDADO:
- Win Rate: 65-70%
- Avg Win: +8-12%
- Avg Loss: -3-5%
- Edge: +10-12%
- Trades/mes: 12-15

PATRÓN:
1. Define rango 9:30-10:00 AM (primeros 30 min)
2. Breakout confirmado con volumen
3. Entrada en pullback al rango o breakout directo
4. Stop debajo del rango, TP basado en ATR

INTEGRACIÓN INTRADAY PATTERNS:
- ODS TREND_DRIVE → +20% confidence
- Continuation pullback → mejor entry
- Liquidity Sweep → evitar si pendiente
"""

import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, time
from strategies.workers.base_worker_logic import BaseWorkerLogic


class ORBWorkerLogic(BaseWorkerLogic):
    """
    Worker para Opening Range Breakout en smallcaps volátiles

    Características:
    - Opera 9:35-10:30 AM ET (post-ORB definition)
    - Breakout del rango 9:30-10:00 AM
    - Confirmación con volumen
    - ODS/Intraday structure integration
    """

    def __init__(
        self,
        worker_name: str = "orb_breakout",
        execution_engine: Any = None,
        risk_manager: Any = None
    ):
        super().__init__(worker_name, execution_engine, risk_manager)

        # ORB Parameters (configurables desde config.ini)
        self.orb_start_time = time(9, 30)   # 9:30 AM ET
        self.orb_end_time = time(10, 0)     # 10:00 AM ET
        self.entry_start_time = time(9, 35) # 9:35 AM (5 min buffer)
        self.entry_end_time = time(10, 30)  # 10:30 AM (30 min window)

        # Entry criteria
        self.min_breakout_volume = 1.5      # 1.5x volume vs ORB average
        self.min_orb_range_pct = 0.015      # 1.5% minimum range
        self.max_orb_range_pct = 0.15       # 15% maximum range (avoid too volatile)
        self.breakout_confirmation_bars = 2  # 2 bars above ORB high

        # Risk management
        self.stop_buffer_pct = 0.01         # 1% buffer below ORB low
        self.target_atr_multiple = 2.0      # 2x ATR target

        self.logger.info(
            f"🎯 ORB Worker initialized - "
            f"Range: {self.orb_start_time.strftime('%H:%M')}-{self.orb_end_time.strftime('%H:%M')}, "
            f"Entry: {self.entry_start_time.strftime('%H:%M')}-{self.entry_end_time.strftime('%H:%M')}"
        )

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios ORB

        Criterios:
        1. Tiempo: 9:35-10:30 AM
        2. ORB definido: Rango 9:30-10:00 completo
        3. Breakout confirmado: Precio > ORB high + volumen
        4. Quality: Score > 60
        5. ODS/Structure: Alineación favorable

        Args:
            opportunity: Datos de la oportunidad

        Returns:
            True si cumple criterios, False si no
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # ====
            # CRITICAL VALIDATION 0: Check for duplicate positions
            # ====
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager and unified_manager.is_symbol_blocked(symbol):
                position = unified_manager.get_position(symbol)
                strategy_type = position['strategy_type'] if position else 'unknown'
                self.logger.warning(
                    f"⚪ {symbol}: BLOCKED - already held in {strategy_type.upper()} trading"
                )
                return False

            current_price = opportunity.get('current_price', 0)
            bars = self.get_bars_from_opportunity(opportunity)

            if not bars or len(bars) < 30:
                self.logger.debug(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0})")
                return False

            # ====
            # TIME FILTER: Must be in entry window
            # ====
            current_time = datetime.now().time()

            if not (self.entry_start_time <= current_time <= self.entry_end_time):
                self.logger.debug(
                    f"⚪ {symbol}: Outside entry window "
                    f"({current_time.strftime('%H:%M')} not in "
                    f"{self.entry_start_time.strftime('%H:%M')}-{self.entry_end_time.strftime('%H:%M')})"
                )
                return False

            # ====
            # ORB CALCULATION: Define opening range
            # ENHANCEMENT: Use scanner-provided ORB data if available (more efficient)
            # ====
            orb_from_scanner = opportunity.get('orb_data')
            if orb_from_scanner and isinstance(orb_from_scanner, dict):
                # Scanner provided ORB data - use it directly (efficient)
                orb_data = {
                    'valid': True,  # Scanner only sends valid ORB data
                    'high': orb_from_scanner.get('orb_high', 0.0),
                    'low': orb_from_scanner.get('orb_low', 0.0),
                    'range_pct': orb_from_scanner.get('orb_range_pct', 0.0),
                    'avg_volume': orb_from_scanner.get('orb_avg_volume', 0)
                }
                self.logger.debug(f"✅ {symbol}: Using ORB data from scanner (efficient)")
            else:
                # Fallback: Calculate ORB ourselves (legacy behavior)
                orb_data = self._calculate_orb(bars)
                self.logger.debug(f"ℹ️ {symbol}: Calculating ORB locally (scanner didn't provide)")

            if not orb_data['valid']:
                self.logger.debug(f"⚪ {symbol}: ORB not valid - {orb_data.get('reason', 'unknown')}")
                return False

            orb_high = orb_data['high']
            orb_low = orb_data['low']
            orb_range_pct = orb_data['range_pct']
            orb_avg_volume = orb_data['avg_volume']

            self.logger.info(
                f"📊 {symbol}: ORB defined - "
                f"High: ${orb_high:.2f}, Low: ${orb_low:.2f}, "
                f"Range: {orb_range_pct*100:.2f}%, "
                f"Avg Vol: {orb_avg_volume:,.0f}"
            )

            # ====
            # BREAKOUT CONFIRMATION: Price > ORB high + volume
            # ====
            breakout_confirmed = self._confirm_breakout(
                bars=bars,
                orb_high=orb_high,
                current_price=current_price,
                orb_avg_volume=orb_avg_volume
            )

            if not breakout_confirmed:
                self.logger.info(
                    f"⚪ {symbol}: Breakout not confirmed - "
                    f"Price ${current_price:.2f} vs ORB high ${orb_high:.2f}"
                )
                return False

            # ====
            # QUALITY FILTER: Minimum quality score
            # ====
            quality_score = opportunity.get('quality_score', 0)

            if quality_score < 60:
                self.logger.info(
                    f"⚪ {symbol}: Low quality - Score {quality_score}/100 < 60"
                )
                return False

            # ====
            # ODS INTEGRATION: Boost on trend drives
            # ====
            from core.ods_classifier import ODSDayType

            ods = await self.get_ods_for_symbol(symbol, bars)

            # Store for adaptive risk sizing
            opportunity['ods_data'] = ods

            confidence_boost = 1.0

            # ODS FILTERS DISABLED - ARCHITECTURAL DECOUPLING
            # Pattern-specific filtering moved to dedicated ODS-driven worker
            # This worker now operates independently based on ORB pattern rules

            # FILTER: Avoid FAILED DRIVE (momentum reversed) - DISABLED
            # if ods.day_type == ODSDayType.FAILED_DRIVE:
            #     self.logger.info(
            #         f"⚪ {symbol}: ODS FILTER - Failed drive day "
            #         f"(reversed @ {ods.distance_from_open_pct:.2f}%) - ORB invalid"
            #     )
            #     return False

            # Log ODS for informational purposes only
            self.logger.debug(
                f"ℹ️ {symbol}: ODS={ods.day_type.value} - NOT used for filtering"
            )

            # BOOST: Trend drive = strong ORB
            if ods.day_type == ODSDayType.TREND_DRIVE_BULLISH:
                confidence_boost = 1.2  # +20%
                self.logger.info(
                    f"✅ {symbol}: ODS BOOST - Bullish trend drive "
                    f"(strength={ods.strength:.1f}) - Strong ORB setup"
                )

            # ====
            # INTRADAY STRUCTURE INTEGRATION
            # ====
            from core.intraday_structure_classifier import IntradayPhase

            structure = await self.get_intraday_structure_for_symbol(symbol, bars)

            # Store for adaptive risk sizing
            opportunity['intraday_structure'] = structure

            # CONTINUATION: Prefer pullback entries
            if structure.current_phase == IntradayPhase.CONTINUATION:
                if structure.continuation_type in ["PULLBACK_TO_VWAP", "HIGHER_LOW"]:
                    confidence_boost *= 1.15  # +15%
                    self.logger.info(
                        f"✅ {symbol}: CONTINUATION BOOST - {structure.continuation_type} confirmed"
                    )

            # LIQUIDITY SWEEP: Avoid if sweep pending
            if structure.liquidity_sweep_detected and structure.sweep_direction == "NONE":
                self.logger.info(
                    f"⏳ {symbol}: Liquidity sweep pending - Wait for resolution"
                )
                return False

            # ====
            # CALCULATE TARGETS: Stop/TP based on ORB + ATR
            # ====
            atr = self._calculate_atr_from_bars(bars, period=14)
            atr_pct = (atr / current_price) * 100 if current_price > 0 else 0

            # Stop: Below ORB low with buffer
            stop_loss_price = orb_low * (1 - self.stop_buffer_pct)
            stop_loss_pct = ((current_price - stop_loss_price) / current_price) * 100

            # Target: 2x ATR or ORB range, whichever is larger
            orb_target_pct = orb_range_pct * 100 * 2.0  # 2x ORB range
            atr_target_pct = atr_pct * self.target_atr_multiple
            take_profit_pct = max(orb_target_pct, atr_target_pct)
            take_profit_price = current_price * (1 + take_profit_pct / 100)

            # Apply confidence boost
            adjusted_quality = min(100, quality_score * confidence_boost)

            # Store in opportunity
            opportunity['quality_score'] = adjusted_quality
            opportunity['stop_loss'] = stop_loss_price
            opportunity['stop_loss_pct'] = stop_loss_pct
            opportunity['take_profit'] = take_profit_price
            opportunity['take_profit_pct'] = take_profit_pct
            opportunity['orb_high'] = orb_high
            opportunity['orb_low'] = orb_low
            opportunity['orb_range_pct'] = orb_range_pct
            opportunity['atr_percent'] = atr_pct

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
                f"✅ {symbol}: ORB BREAKOUT CONFIRMED - "
                f"Price ${current_price:.2f}, "
                f"ORB: ${orb_low:.2f}-${orb_high:.2f} ({orb_range_pct*100:.2f}%), "
                f"Quality: {adjusted_quality:.0f}/100, "
                f"SL: {stop_loss_pct:.1f}%, TP: {take_profit_pct:.1f}%, R:R: {risk_reward:.2f}"
            )

            return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in ORB evaluation: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _calculate_orb(self, bars: List[Any]) -> Dict[str, Any]:
        """
        Calcula el Opening Range (9:30-10:00 AM)

        Args:
            bars: Lista de barras de 1 minuto

        Returns:
            Dict con ORB high, low, range_pct, avg_volume, valid
        """
        try:
            # Find bars in ORB window (first 30 minutes)
            orb_bars = []

            for bar in bars:
                bar_time = bar.timestamp.time() if hasattr(bar.timestamp, 'time') else bar.timestamp

                if self.orb_start_time <= bar_time < self.orb_end_time:
                    orb_bars.append(bar)

            if len(orb_bars) < 20:  # Need at least 20 of 30 bars
                return {
                    'valid': False,
                    'reason': f'Insufficient ORB bars ({len(orb_bars)}/30)'
                }

            # Calculate ORB metrics
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

        Args:
            bars: Lista de barras
            orb_high: ORB high price
            current_price: Precio actual
            orb_avg_volume: Volumen promedio del ORB

        Returns:
            True si breakout confirmado
        """
        try:
            # Price must be above ORB high
            if current_price <= orb_high:
                return False

            # Check last N bars for confirmation
            recent_bars = bars[-10:] if len(bars) >= 10 else bars

            # Count bars above ORB high
            bars_above_orb = 0
            recent_volume = 0

            for bar in recent_bars[-5:]:  # Last 5 bars
                if bar.close > orb_high:
                    bars_above_orb += 1
                recent_volume += bar.volume

            avg_recent_volume = recent_volume / min(5, len(recent_bars[-5:]))

            # Need at least 2 bars above ORB high
            if bars_above_orb < self.breakout_confirmation_bars:
                self.logger.debug(
                    f"Breakout bars insufficient: {bars_above_orb}/{self.breakout_confirmation_bars}"
                )
                return False

            # Volume must be elevated
            volume_ratio = avg_recent_volume / orb_avg_volume if orb_avg_volume > 0 else 0

            if volume_ratio < self.min_breakout_volume:
                self.logger.debug(
                    f"Breakout volume insufficient: {volume_ratio:.2f}x < {self.min_breakout_volume}x"
                )
                return False

            self.logger.info(
                f"✅ Breakout confirmed: {bars_above_orb} bars above ORB, "
                f"Volume: {volume_ratio:.2f}x ORB avg"
            )

            return True

        except Exception as e:
            self.logger.error(f"Error confirming breakout: {e}")
            return False

    async def should_exit(
        self,
        symbol: str,
        position_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Evalúa si debe salir de posición

        ORB-specific exits:
        - Stop loss: Below ORB low
        - Take profit: 2x ATR or 2x ORB range
        - Time-based: Close at 3:55 PM if still holding

        Args:
            symbol: Símbolo
            position_data: Datos de la posición

        Returns:
            (should_exit, reason)
        """
        try:
            opportunity = position_data.get('opportunity_data', {})
            entry_price = position_data.get('entry_price', 0)

            # Get current price
            current_price = await self.execution_engine.get_current_price(symbol)

            if current_price <= 0:
                return False, None

            # Calculate P&L
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            # 1. STOP LOSS: Below ORB low
            stop_loss = opportunity.get('stop_loss', 0)
            if stop_loss > 0 and current_price <= stop_loss:
                return True, f"STOP_LOSS (ORB low breached: ${current_price:.2f} <= ${stop_loss:.2f})"

            # 2. TAKE PROFIT: Target reached
            take_profit = opportunity.get('take_profit', 0)
            if take_profit > 0 and current_price >= take_profit:
                return True, f"TAKE_PROFIT (Target hit: ${current_price:.2f} >= ${take_profit:.2f}, +{pnl_pct:.1f}%)"

            # 3. TIME-BASED EXIT: Close before market close
            current_time = datetime.now().time()
            eod_exit_time = time(15, 55)  # 3:55 PM ET

            if current_time >= eod_exit_time:
                return True, f"EOD_EXIT (Market close approaching, P&L: {pnl_pct:+.1f}%)"

            # 4. TRAILING STOP: If in profit > 5%, trail at 3%
            if pnl_pct > 5.0:
                trailing_stop_pct = 3.0
                trailing_stop_price = entry_price * (1 + (pnl_pct - trailing_stop_pct) / 100)

                if current_price <= trailing_stop_price:
                    return True, f"TRAILING_STOP (Profit protected: {pnl_pct:.1f}% → {pnl_pct - trailing_stop_pct:.1f}%)"

            # Hold position
            return False, None

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in exit evaluation: {e}")
            return False, None
