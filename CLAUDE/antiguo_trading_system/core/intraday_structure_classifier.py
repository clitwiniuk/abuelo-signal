#!/usr/bin/env python3
"""
Intraday Structure Classifier - Complete Pattern Recognition System

Sistema completo de clasificación de patrones estructurales intraday para smallcaps.

6 PATRONES TEMPORALES:
1. ODS (0-12 min): Opening Drive Structure
2. Continuation (12-30 min): Pullbacks y VWAP rotation
3. Liquidity Sweep (30-120 min): Stop hunting y reclaim
4. Midday Balance (120-210 min): Consolidación y breakout
5. Trap Reversals (210-330 min): Manipulación de stops
6. Final Drive (330-390 min): Closing auction bias

Uso:
    classifier = get_service_locator().get_intraday_structure_classifier()
    structure = await classifier.classify_symbol(symbol, bars, current_time)

    if structure.current_phase == IntradayPhase.MIDDAY:
        if structure.midday_structure == "IMBALANCE_BULLISH":
            # Entry opportunity
"""

import logging
from datetime import datetime, time
from typing import Dict, Optional, List, Any
from enum import Enum
from dataclasses import dataclass, field
import pytz


class IntradayPhase(Enum):
    """Fases intradía del mercado (basado en minutos desde 9:30 AM ET)"""
    OPENING_DRIVE = "OPENING_DRIVE"              # 0-12 min
    CONTINUATION = "CONTINUATION"                # 12-30 min
    MID_MORNING = "MID_MORNING"                  # 30-120 min
    MIDDAY = "MIDDAY"                            # 120-210 min
    AFTERNOON = "AFTERNOON"                      # 210-330 min
    FINAL_DRIVE = "FINAL_DRIVE"                  # 330-390 min
    PREMARKET = "PREMARKET"                      # Antes de 9:30
    AFTERHOURS = "AFTERHOURS"                    # Después de 16:00


@dataclass
class IntradayStructureData:
    """Estructura completa intraday de un símbolo"""
    symbol: str
    current_phase: IntradayPhase

    # ODS (0-12 min) - Referencia a ODSData existente
    ods_day_type: str = "PENDING"  # TREND_DRIVE_BULLISH, FAILED_DRIVE, etc.
    ods_direction: str = "NEUTRAL"
    ods_strength: float = 0.0

    # Continuation/VWAP (12-30 min)
    continuation_type: str = "PENDING"  # PULLBACK_BULLISH, PULLBACK_BEARISH, VWAP_ROTATION, BREAKDOWN
    continuation_quality: float = 0.0  # 0-100
    pullback_to_vwap: bool = False
    pullback_to_ema: bool = False

    # Liquidity Sweep (30-120 min)
    liquidity_sweep_detected: bool = False
    sweep_direction: str = "NONE"  # BULLISH_RECLAIM, BEARISH_BREAKDOWN, NONE
    sweep_strength: float = 0.0  # 0-100
    sweep_price_level: float = 0.0

    # Midday Balance (120-210 min)
    midday_structure: str = "PENDING"  # BALANCE, IMBALANCE_BULLISH, IMBALANCE_BEARISH, RE_BALANCE
    compression_ratio: float = 0.0  # Cuánto comprimió el rango (0-1)
    breakout_confirmed: bool = False
    balance_range_pct: float = 0.0

    # Trap Reversals (210-330 min)
    trap_detected: bool = False
    trap_type: str = "NONE"  # BULL_TRAP, BEAR_TRAP, NONE
    stop_run_detected: bool = False
    fade_opportunity: bool = False

    # Final Drive (330-390 min)
    final_drive_type: str = "PENDING"  # CLOSING_RAMP, FADE_SETUP, NEUTRAL, PENDING
    closing_bias: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    final_drive_quality: float = 0.0

    # Metadatos
    last_update: Optional[datetime] = None
    cache_valid: bool = True
    minutes_since_open: int = 0

    # Context adicional
    vwap_price: float = 0.0
    ema9_price: float = 0.0
    current_price: float = 0.0


class IntradayStructureClassifier:
    """
    Singleton service que clasifica patrones estructurales intraday

    Arquitectura modular:
    - Integra ODS Classifier existente (9:30-9:42)
    - 5 sub-classifiers nuevos para resto del día
    - Caché compartida entre todos los workers
    - Actualización progresiva durante la sesión
    """

    def __init__(self):
        self.logger = logging.getLogger("IntradayStructure")

        # Caché por símbolo (se resetea diariamente)
        self.structure_cache: Dict[str, IntradayStructureData] = {}
        self.last_reset_date = datetime.now().date()

        # Timezone
        self.eastern = pytz.timezone('US/Eastern')

        # Referencias a otros services (se inyectan después)
        self.ods_classifier = None  # Se obtiene de ServiceLocator

        # Configuración de ventanas temporales (en minutos desde 9:30)
        self.PHASE_WINDOWS = {
            IntradayPhase.OPENING_DRIVE: (0, 12),
            IntradayPhase.CONTINUATION: (12, 30),
            IntradayPhase.MID_MORNING: (30, 120),
            IntradayPhase.MIDDAY: (120, 210),
            IntradayPhase.AFTERNOON: (210, 330),
            IntradayPhase.FINAL_DRIVE: (330, 390)
        }

        self.logger.info("✅ IntradayStructureClassifier initialized")

    def set_ods_classifier(self, ods_classifier):
        """Inject ODS Classifier from ServiceLocator"""
        self.ods_classifier = ods_classifier
        self.logger.debug("ODS Classifier injected into IntradayStructureClassifier")

    async def classify_symbol(
        self,
        symbol: str,
        bars: List[Any],
        current_time: Optional[datetime] = None
    ) -> IntradayStructureData:
        """
        Clasifica la estructura intraday completa del símbolo

        Args:
            symbol: Ticker symbol
            bars: Lista de barras 1-min desde 9:30 AM
            current_time: Tiempo actual (default: now)

        Returns:
            IntradayStructureData con clasificación completa
        """
        if current_time is None:
            current_time = datetime.now(self.eastern)

        # Reset cache si es nuevo día
        self._reset_cache_if_new_day()

        # Check cache
        if symbol in self.structure_cache:
            cached = self.structure_cache[symbol]
            # Retornar cache si aún válido (< 1 min old)
            if cached.last_update and (current_time - cached.last_update).total_seconds() < 60:
                return cached

        # Determinar fase actual
        phase = self._determine_current_phase(current_time)
        minutes_since_open = self._get_minutes_since_open(current_time)

        # Crear estructura base
        structure = IntradayStructureData(
            symbol=symbol,
            current_phase=phase,
            minutes_since_open=minutes_since_open,
            last_update=current_time
        )

        # Si no hay barras suficientes, retornar estructura vacía
        if not bars or len(bars) < 2:
            self.structure_cache[symbol] = structure
            return structure

        # Calcular VWAP y EMA9 (contexto necesario para todos los patrones)
        structure.vwap_price = self._calculate_vwap(bars)
        structure.ema9_price = self._calculate_ema(bars, period=9)
        structure.current_price = bars[-1].close if hasattr(bars[-1], 'close') else 0.0

        # Clasificar según fase (acumulativo - cada fase incluye análisis previos)

        # 1. ODS (0-12 min) - SIEMPRE se ejecuta si hay datos
        if len(bars) >= 2:
            await self._classify_opening_drive(structure, bars)

        # 2. Continuation (12-30 min)
        if phase.value in ['CONTINUATION', 'MID_MORNING', 'MIDDAY', 'AFTERNOON', 'FINAL_DRIVE']:
            if len(bars) >= 30:
                await self._classify_continuation(structure, bars)

        # 3. Liquidity Sweep (30-120 min)
        if phase.value in ['MID_MORNING', 'MIDDAY', 'AFTERNOON', 'FINAL_DRIVE']:
            if len(bars) >= 50:
                await self._classify_liquidity_sweep(structure, bars)

        # 4. Midday Balance (120-210 min)
        if phase.value in ['MIDDAY', 'AFTERNOON', 'FINAL_DRIVE']:
            if len(bars) >= 135:  # Al menos 15 min de ventana midday
                await self._classify_midday_balance(structure, bars)

        # 5. Trap Reversals (210-330 min)
        if phase.value in ['AFTERNOON', 'FINAL_DRIVE']:
            if len(bars) >= 220:
                await self._classify_trap_reversals(structure, bars)

        # 6. Final Drive (330-390 min)
        if phase == IntradayPhase.FINAL_DRIVE:
            if len(bars) >= 340:
                await self._classify_final_drive(structure, bars)

        # Guardar en cache
        self.structure_cache[symbol] = structure

        return structure

    def _determine_current_phase(self, current_time: datetime) -> IntradayPhase:
        """Determina fase actual basándose en hora del día"""
        # Asegurar timezone ET
        if current_time.tzinfo is None:
            current_time = self.eastern.localize(current_time)
        else:
            current_time = current_time.astimezone(self.eastern)

        current_hour = current_time.hour + current_time.minute / 60.0

        # Premarket: antes de 9:30
        if current_hour < 9.5:
            return IntradayPhase.PREMARKET

        # Regular hours: 9:30-16:00
        if current_hour >= 16.0:
            return IntradayPhase.AFTERHOURS

        # Calcular minutos desde 9:30
        minutes_since_open = self._get_minutes_since_open(current_time)

        # Determinar fase según minutos
        for phase, (start, end) in self.PHASE_WINDOWS.items():
            if start <= minutes_since_open < end:
                return phase

        # Default: FINAL_DRIVE si >= 330 min
        if minutes_since_open >= 330:
            return IntradayPhase.FINAL_DRIVE

        return IntradayPhase.OPENING_DRIVE

    def _get_minutes_since_open(self, current_time: datetime) -> int:
        """Calcula minutos transcurridos desde 9:30 AM ET"""
        if current_time.tzinfo is None:
            current_time = self.eastern.localize(current_time)
        else:
            current_time = current_time.astimezone(self.eastern)

        market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)

        if current_time < market_open:
            return -1

        delta = current_time - market_open
        return int(delta.total_seconds() / 60)

    def _reset_cache_if_new_day(self):
        """Resetea cache si es un nuevo día de trading"""
        today = datetime.now().date()

        if today != self.last_reset_date:
            self.structure_cache.clear()
            self.last_reset_date = today
            self.logger.info(f"🔄 Cache reset for new trading day: {today}")

    # =========================================================================
    # SUB-CLASSIFIERS (uno por cada patrón temporal)
    # =========================================================================

    async def _classify_opening_drive(self, structure: IntradayStructureData, bars: List[Any]):
        """
        Classify ODS (0-12 min) - Usa ODS Classifier existente
        """
        try:
            if self.ods_classifier is None:
                self.logger.warning("⚠️ ODS Classifier not available - skipping ODS classification")
                return

            # Llamar a ODS Classifier existente
            ods_data = await self.ods_classifier.classify_symbol_ods(
                symbol=structure.symbol,
                bars=bars,
                premarket_data=None
            )

            # Copiar datos de ODS a estructura
            structure.ods_day_type = ods_data.day_type.value if hasattr(ods_data.day_type, 'value') else str(ods_data.day_type)
            structure.ods_direction = ods_data.direction
            structure.ods_strength = ods_data.strength

        except Exception as e:
            self.logger.warning(f"⚠️ ODS classification failed for {structure.symbol}: {e}")

    async def _classify_continuation(self, structure: IntradayStructureData, bars: List[Any]):
        """
        Classify Continuation/VWAP Rotation (12-30 min)

        Detecta:
        - PULLBACK_BULLISH: Retroceso a VWAP/EMA9 tras ODS bullish
        - PULLBACK_BEARISH: Rebote a VWAP tras ODS bearish
        - VWAP_ROTATION: Rotación limpia en VWAP
        - BREAKDOWN: Fallo del drive inicial
        """
        try:
            # Filtrar barras 12-30 min
            if len(bars) < 30:
                return

            continuation_bars = bars[12:min(30, len(bars))]

            if len(continuation_bars) < 5:
                return

            # Calcular métricas
            vwap = structure.vwap_price
            ema9 = structure.ema9_price
            current_price = continuation_bars[-1].close if hasattr(continuation_bars[-1], 'close') else 0

            # Check pullback to VWAP
            touched_vwap = False
            for bar in continuation_bars[-5:]:
                low = bar.low if hasattr(bar, 'low') else bar.close
                high = bar.high if hasattr(bar, 'high') else bar.close

                if vwap > 0 and low <= vwap * 1.002 and high >= vwap * 0.998:
                    touched_vwap = True
                    structure.pullback_to_vwap = True
                    break

            # Check pullback to EMA9
            touched_ema = False
            for bar in continuation_bars[-5:]:
                low = bar.low if hasattr(bar, 'low') else bar.close
                high = bar.high if hasattr(bar, 'high') else bar.close

                if ema9 > 0 and low <= ema9 * 1.002 and high >= ema9 * 0.998:
                    touched_ema = True
                    structure.pullback_to_ema = True
                    break

            # Classify continuation type
            if structure.ods_day_type == "TREND_DRIVE_BULLISH":
                if touched_vwap or touched_ema:
                    # Check si rebotó
                    if current_price > vwap:
                        structure.continuation_type = "PULLBACK_BULLISH"
                        structure.continuation_quality = 85.0
                        return

            elif structure.ods_day_type == "TREND_DRIVE_BEARISH":
                if touched_vwap or touched_ema:
                    # Check si rechazó
                    if current_price < vwap:
                        structure.continuation_type = "PULLBACK_BEARISH"
                        structure.continuation_quality = 80.0
                        return

            # VWAP rotation (sin ODS clear)
            if touched_vwap:
                structure.continuation_type = "VWAP_ROTATION"
                structure.continuation_quality = 65.0
            else:
                structure.continuation_type = "CONTINUATION_WEAK"
                structure.continuation_quality = 40.0

        except Exception as e:
            self.logger.debug(f"Continuation classification error for {structure.symbol}: {e}")

    async def _classify_liquidity_sweep(self, structure: IntradayStructureData, bars: List[Any]):
        """
        Classify Liquidity Sweep (30-120 min)

        Detecta:
        - BULLISH_RECLAIM: Sweep de lows + reclaim rápido
        - BEARISH_BREAKDOWN: Sweep de highs + breakdown
        - FAKE_SWEEP: Sweep sin follow-through
        """
        try:
            # Filtrar barras 30-120 min
            start_idx = 30
            end_idx = min(120, len(bars))

            if end_idx - start_idx < 20:
                return

            mid_morning_bars = bars[start_idx:end_idx]

            # Calcular recent low/high (últimas 20 barras antes de ventana sweep)
            lookback_bars = bars[max(0, start_idx-20):start_idx]
            if len(lookback_bars) < 10:
                return

            recent_low = min([b.low if hasattr(b, 'low') else b.close for b in lookback_bars])
            recent_high = max([b.high if hasattr(b, 'high') else b.close for b in lookback_bars])

            # Calcular volumen promedio
            avg_volume = sum([b.volume if hasattr(b, 'volume') else 0 for b in lookback_bars]) / len(lookback_bars)

            # Buscar sweep pattern en últimas 10 barras de ventana
            for i in range(max(0, len(mid_morning_bars) - 10), len(mid_morning_bars)):
                bar = mid_morning_bars[i]
                bar_low = bar.low if hasattr(bar, 'low') else bar.close
                bar_high = bar.high if hasattr(bar, 'high') else bar.close
                bar_close = bar.close if hasattr(bar, 'close') else 0
                bar_volume = bar.volume if hasattr(bar, 'volume') else 0

                # BULLISH SWEEP: Broke low + reclaimed
                if bar_low < recent_low * 0.99:  # 1% sweep
                    if bar_close > recent_low * 1.005:  # Reclaimed 0.5%
                        if bar_volume > avg_volume * 1.5:
                            structure.liquidity_sweep_detected = True
                            structure.sweep_direction = "BULLISH_RECLAIM"
                            structure.sweep_strength = 85.0
                            structure.sweep_price_level = recent_low
                            return

                # BEARISH SWEEP: Broke high + breakdown
                if bar_high > recent_high * 1.01:  # 1% sweep
                    if bar_close < recent_high * 0.995:  # Breakdown 0.5%
                        if bar_volume > avg_volume * 1.5:
                            structure.liquidity_sweep_detected = True
                            structure.sweep_direction = "BEARISH_BREAKDOWN"
                            structure.sweep_strength = 80.0
                            structure.sweep_price_level = recent_high
                            return

        except Exception as e:
            self.logger.debug(f"Liquidity sweep detection error for {structure.symbol}: {e}")

    async def _classify_midday_balance(self, structure: IntradayStructureData, bars: List[Any]):
        """
        Classify Midday Balance-Imbalance-Balance (120-210 min)

        Estados:
        - BALANCE: Rango < 0.5%, volumen bajo
        - IMBALANCE_BULLISH: Breakout confirmado
        - IMBALANCE_BEARISH: Breakdown confirmado
        - RE_BALANCE: Nueva consolidación
        """
        try:
            # Filtrar 120-210 min (11:30-12:30 PM)
            start_idx = 120
            end_idx = min(210, len(bars))

            if end_idx - start_idx < 15:
                return

            midday_bars = bars[start_idx:end_idx]

            # Fase 1: Detectar BALANCE inicial (primeros 15 min)
            balance_window = midday_bars[:min(15, len(midday_bars))]

            if len(balance_window) < 10:
                return

            balance_high = max([b.high if hasattr(b, 'high') else b.close for b in balance_window])
            balance_low = min([b.low if hasattr(b, 'low') else b.close for b in balance_window])
            balance_open = balance_window[0].open if hasattr(balance_window[0], 'open') else balance_window[0].close

            if balance_open == 0:
                return

            balance_range = (balance_high - balance_low) / balance_open
            structure.balance_range_pct = balance_range * 100
            structure.compression_ratio = balance_range

            # Si rango < 0.5%, es BALANCE
            if balance_range < 0.005:
                structure.midday_structure = "BALANCE"

                # Fase 2: Buscar IMBALANCE (breakout del balance)
                if len(midday_bars) > 20:
                    breakout_window = midday_bars[15:min(len(midday_bars), 45)]

                    for bar in breakout_window:
                        bar_close = bar.close if hasattr(bar, 'close') else 0
                        bar_volume = bar.volume if hasattr(bar, 'volume') else 0

                        # Calcular avg volume
                        avg_vol = sum([b.volume if hasattr(b, 'volume') else 0 for b in balance_window]) / len(balance_window)

                        # BULLISH IMBALANCE
                        if bar_close > balance_high * 1.005:  # 0.5% breakout
                            if bar_volume > avg_vol * 1.3:
                                structure.midday_structure = "IMBALANCE_BULLISH"
                                structure.breakout_confirmed = True
                                return

                        # BEARISH IMBALANCE
                        if bar_close < balance_low * 0.995:  # 0.5% breakdown
                            if bar_volume > avg_vol * 1.3:
                                structure.midday_structure = "IMBALANCE_BEARISH"
                                structure.breakout_confirmed = True
                                return
            else:
                # Rango amplio - no es balance
                structure.midday_structure = "NO_BALANCE"

        except Exception as e:
            self.logger.debug(f"Midday balance classification error for {structure.symbol}: {e}")

    async def _classify_trap_reversals(self, structure: IntradayStructureData, bars: List[Any]):
        """
        Classify Trap Reversals / Stop Runs (210-330 min)

        Detecta:
        - BULL_TRAP: Fake breakout → reversión
        - BEAR_TRAP: Fake breakdown → reversión
        - STOP_RUN: Spike sin volumen
        """
        try:
            # Filtrar 210-330 min (12:30-3:00 PM)
            start_idx = 210
            end_idx = min(330, len(bars))

            if end_idx - start_idx < 20:
                return

            afternoon_bars = bars[start_idx:end_idx]

            # Calcular midday range
            midday_bars = bars[120:min(210, len(bars))]
            if len(midday_bars) < 10:
                return

            midday_high = max([b.high if hasattr(b, 'high') else b.close for b in midday_bars])
            midday_low = min([b.low if hasattr(b, 'low') else b.close for b in midday_bars])

            # Calcular avg volume
            avg_vol = sum([b.volume if hasattr(b, 'volume') else 0 for b in midday_bars]) / len(midday_bars)

            # Buscar traps en ventanas de 10 barras
            for i in range(0, len(afternoon_bars) - 10, 5):
                window = afternoon_bars[i:i+10]

                first_bar = window[0]
                last_bar = window[-1]

                first_close = first_bar.close if hasattr(first_bar, 'close') else 0
                first_high = first_bar.high if hasattr(first_bar, 'high') else first_close
                first_low = first_bar.low if hasattr(first_bar, 'low') else first_close
                first_volume = first_bar.volume if hasattr(first_bar, 'volume') else 0

                last_close = last_bar.close if hasattr(last_bar, 'close') else 0

                # BULL TRAP: Breakout → reversión
                if first_high > midday_high * 1.01:  # 1% breakout
                    if first_volume < avg_vol * 0.8:  # Low volume
                        if last_close < first_close:  # Reversión
                            structure.trap_detected = True
                            structure.trap_type = "BULL_TRAP"
                            structure.fade_opportunity = True
                            return

                # BEAR TRAP: Breakdown → reversión
                if first_low < midday_low * 0.99:  # 1% breakdown
                    if first_volume < avg_vol * 0.8:  # Low volume
                        if last_close > first_close:  # Reversión
                            structure.trap_detected = True
                            structure.trap_type = "BEAR_TRAP"
                            structure.fade_opportunity = True
                            return

        except Exception as e:
            self.logger.debug(f"Trap reversal detection error for {structure.symbol}: {e}")

    async def _classify_final_drive(self, structure: IntradayStructureData, bars: List[Any]):
        """
        Classify Final Drive / Closing Auction (330-390 min)

        Tipos:
        - CLOSING_RAMP: Compra institucional últimos 30 min
        - FADE_SETUP: Drive extremo sin volumen
        - NEUTRAL: Sin sesgo claro
        """
        try:
            # Filtrar 330-390 min (3:00-4:00 PM)
            start_idx = 330
            end_idx = min(390, len(bars))

            if end_idx - start_idx < 20:
                return

            final_bars = bars[start_idx:end_idx]

            # Últimos 30 min
            last_30 = final_bars[-min(30, len(final_bars)):]

            if len(last_30) < 15:
                return

            # Calcular avg volume
            avg_vol = sum([b.volume if hasattr(b, 'volume') else 0 for b in final_bars]) / len(final_bars)

            # Momentum check
            closes = [b.close if hasattr(b, 'close') else 0 for b in last_30]

            if len(closes) < 10:
                return

            # CLOSING RAMP: Precio sube consistentemente
            bullish_bars = sum(1 for i in range(1, len(closes)) if closes[i] >= closes[i-1])
            bullish_momentum = bullish_bars / (len(closes) - 1)

            # Volume check
            last_30_vol = sum([b.volume if hasattr(b, 'volume') else 0 for b in last_30]) / len(last_30)

            if bullish_momentum > 0.7:  # 70% barras alcistas
                if last_30_vol > avg_vol * 1.2:  # Volumen incrementado
                    structure.final_drive_type = "CLOSING_RAMP"
                    structure.closing_bias = "BULLISH"
                    structure.final_drive_quality = bullish_momentum * 100
                    return

            # FADE SETUP: Drive extremo sin volumen
            price_change = (closes[-1] - closes[0]) / closes[0] if closes[0] > 0 else 0

            if abs(price_change) > 0.03:  # 3% move
                if last_30_vol < avg_vol * 0.8:  # Low volume
                    structure.final_drive_type = "FADE_SETUP"
                    structure.closing_bias = "BEARISH" if price_change > 0 else "BULLISH"
                    structure.final_drive_quality = 75.0
                    return

            # Default: NEUTRAL
            structure.final_drive_type = "NEUTRAL"
            structure.closing_bias = "NEUTRAL"

        except Exception as e:
            self.logger.debug(f"Final drive classification error for {structure.symbol}: {e}")

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _calculate_vwap(self, bars: List[Any]) -> float:
        """Calcula VWAP desde apertura"""
        try:
            total_volume = 0.0
            total_pv = 0.0

            for bar in bars:
                close = bar.close if hasattr(bar, 'close') else 0
                volume = bar.volume if hasattr(bar, 'volume') else 0

                # Typical price
                if hasattr(bar, 'high') and hasattr(bar, 'low'):
                    typical = (bar.high + bar.low + close) / 3
                else:
                    typical = close

                total_pv += typical * volume
                total_volume += volume

            if total_volume > 0:
                return total_pv / total_volume

            return 0.0

        except Exception:
            return 0.0

    def _calculate_ema(self, bars: List[Any], period: int = 9) -> float:
        """Calcula EMA"""
        try:
            closes = [b.close if hasattr(b, 'close') else 0 for b in bars]

            if len(closes) < period:
                return sum(closes) / len(closes) if closes else 0.0

            # EMA multiplier
            multiplier = 2 / (period + 1)

            # SMA inicial
            ema = sum(closes[:period]) / period

            # Calcular EMA
            for close in closes[period:]:
                ema = (close - ema) * multiplier + ema

            return ema

        except Exception:
            return 0.0
