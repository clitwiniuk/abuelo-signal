#!/usr/bin/env python3
"""
ODS (Opening Drive Structure) Classifier

Clasifica el tipo de día basándose en los primeros 12 minutos del mercado (9:30-9:42 AM ET).

Tipos de día:
- TREND_DRIVE_BULLISH: Impulso alcista sostenido desde el open
- TREND_DRIVE_BEARISH: Impulso bajista sostenido desde el open
- FAILED_DRIVE: Impulso inicial que revierte completamente
- BALANCE_DAY: Sin impulso claro, oscilación en rango
- PENDING: Aún no han pasado 12 minutos
- INSUFFICIENT_DATA: No hay suficientes datos para clasificar

Uso:
    ods_classifier = get_service_locator().get_ods_classifier()
    ods_data = await ods_classifier.classify_symbol_ods(symbol, bars, premarket_data)

    if ods_data.day_type == ODSDayType.FAILED_DRIVE:
        # Skip trade
        return False
"""

import logging
from datetime import datetime, time
from typing import Dict, Optional, List, Any
from enum import Enum
from dataclasses import dataclass
import pytz


class ODSDayType(Enum):
    """Tipos de día detectados por ODS"""
    TREND_DRIVE_BULLISH = "TREND_DRIVE_BULLISH"
    TREND_DRIVE_BEARISH = "TREND_DRIVE_BEARISH"
    FAILED_DRIVE = "FAILED_DRIVE"
    BALANCE_DAY = "BALANCE_DAY"
    PENDING = "PENDING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

    # Intensity-based patterns (PHASE 1 - Granular classification)
    STRONG_BULLISH_OPEN = "STRONG_BULLISH_OPEN"          # Strength >= 85, high conviction
    MODERATE_BULLISH_OPEN = "MODERATE_BULLISH_OPEN"      # Strength 60-85, medium conviction
    WEAK_BULLISH_OPEN = "WEAK_BULLISH_OPEN"              # Strength 40-60, low conviction
    STRONG_BEARISH_OPEN = "STRONG_BEARISH_OPEN"          # Strength >= 85, high conviction short
    MODERATE_BEARISH_OPEN = "MODERATE_BEARISH_OPEN"      # Strength 60-85, medium conviction short


@dataclass
class ODSData:
    """Datos de Opening Drive Structure"""
    day_type: ODSDayType
    direction: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    strength: float = 0.0  # 0-100
    open_price: float = 0.0
    high_12min: float = 0.0
    low_12min: float = 0.0
    close_12min: float = 0.0
    range_pct: float = 0.0
    distance_from_open_pct: float = 0.0
    volume_ratio: float = 1.0
    upside_move_pct: float = 0.0
    downside_move_pct: float = 0.0
    classification_time: Optional[datetime] = None
    classification_pending: bool = False


class ODSClassifier:
    """
    Opening Drive Structure Classifier

    Singleton service que clasifica el tipo de día para cada símbolo
    basándose en los primeros 12 minutos del mercado (9:30-9:42 AM ET).

    Integración con ServiceLocator para estado compartido entre workers.
    """

    def __init__(self):
        self.logger = logging.getLogger("ODSClassifier")

        # Cache de ODS por símbolo (se resetea diariamente)
        self.ods_cache: Dict[str, ODSData] = {}
        self.last_reset_date = datetime.now().date()

        # Timezone
        self.eastern = pytz.timezone('US/Eastern')

        self.logger.info("🕐 ODSClassifier initialized - Opening Drive Structure analysis")

    def _reset_cache_if_new_day(self):
        """Resetea cache si es un nuevo día de trading"""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.logger.info(f"📅 New trading day - resetting ODS cache")
            self.ods_cache.clear()
            self.last_reset_date = current_date

    def _is_after_ods_window(self) -> bool:
        """Verifica si ya pasó la ventana ODS (9:42 AM ET)"""
        now_et = datetime.now(self.eastern)
        ods_end_time = time(9, 42)
        return now_et.time() >= ods_end_time

    def _filter_ods_bars(self, bars: List[Any]) -> List[Any]:
        """
        Filtra bars para obtener solo los de 9:30-9:42 AM ET

        Args:
            bars: Lista de bars con timestamp

        Returns:
            Lista de bars entre 9:30 y 9:42 AM ET
        """
        ods_bars = []

        for bar in bars:
            # Get bar timestamp
            if hasattr(bar, 'timestamp'):
                bar_time = bar.timestamp
            elif isinstance(bar, dict):
                bar_time = bar.get('timestamp')
            else:
                continue

            # Convert to datetime if needed
            if isinstance(bar_time, str):
                try:
                    bar_time = datetime.fromisoformat(bar_time.replace('Z', '+00:00'))
                except:
                    continue

            # Convert to Eastern time
            if bar_time.tzinfo is None:
                bar_time = self.eastern.localize(bar_time)
            else:
                bar_time = bar_time.astimezone(self.eastern)

            # Filter 9:30-9:42 AM ET
            bar_hour = bar_time.hour
            bar_minute = bar_time.minute

            if bar_hour == 9 and 30 <= bar_minute < 42:
                ods_bars.append(bar)

        return ods_bars

    def _classify_drive(
        self,
        ods_bars: List[Any],
        premarket_data: Optional[Dict] = None
    ) -> ODSData:
        """
        Clasifica Opening Drive Structure

        Criterios:
        1. TREND DRIVE BULLISH:
           - Impulso alcista > 0.5%
           - Mantiene > 0.3% sobre open al cierre 12min
           - Volumen fuerte (> 1.5x premarket)

        2. TREND DRIVE BEARISH:
           - Impulso bajista > 0.5%
           - Mantiene > 0.3% bajo open al cierre 12min
           - Volumen fuerte (> 1.5x premarket)

        3. FAILED DRIVE:
           - Impulso inicial > 0.5%
           - Reversión completa (cruza open)
           - Volumen en reversión

        4. BALANCE DAY:
           - Rango < 0.5%
           - Volumen bajo (< 1.2x premarket)

        Args:
            ods_bars: Bars filtrados 9:30-9:42
            premarket_data: Datos de premarket (opcional)

        Returns:
            ODSData con clasificación
        """
        if len(ods_bars) < 12:
            return ODSData(
                day_type=ODSDayType.INSUFFICIENT_DATA,
                classification_time=datetime.now()
            )

        # Extract price data
        open_price = ods_bars[0].open if hasattr(ods_bars[0], 'open') else ods_bars[0].get('open')
        high_12min = max(b.high if hasattr(b, 'high') else b.get('high') for b in ods_bars)
        low_12min = min(b.low if hasattr(b, 'low') else b.get('low') for b in ods_bars)
        close_12min = ods_bars[-1].close if hasattr(ods_bars[-1], 'close') else ods_bars[-1].get('close')

        # Volume data
        volume_12min = sum(b.volume if hasattr(b, 'volume') else b.get('volume', 0) for b in ods_bars)
        premarket_volume = premarket_data.get('volume', 0) if premarket_data else 0
        volume_ratio = volume_12min / premarket_volume if premarket_volume > 0 else 1.5

        # Calculate metrics
        upside_move = ((high_12min - open_price) / open_price) * 100
        downside_move = ((open_price - low_12min) / open_price) * 100
        range_pct = ((high_12min - low_12min) / open_price) * 100
        distance_from_open = ((close_12min - open_price) / open_price) * 100

        # Classification thresholds
        IMPULSE_THRESHOLD = 0.5  # 0.5% minimum impulse
        HOLD_THRESHOLD = 0.3     # 0.3% minimum hold from open
        VOLUME_STRONG = 1.5      # 1.5x premarket = strong
        VOLUME_WEAK = 1.2        # < 1.2x premarket = weak
        RANGE_NARROW = 0.5       # < 0.5% range = narrow

        # TREND DRIVE BULLISH with Intensity Classification
        if (upside_move > IMPULSE_THRESHOLD and
            distance_from_open > HOLD_THRESHOLD and
            volume_ratio > VOLUME_STRONG and
            close_12min > open_price):

            strength = min(100, (upside_move / 2) * 100)  # Scale 0-100

            # PHASE 1: Intensity-based classification
            # Determine specific pattern type based on strength
            if strength >= 85:
                day_type = ODSDayType.STRONG_BULLISH_OPEN
            elif strength >= 60:
                day_type = ODSDayType.MODERATE_BULLISH_OPEN
            elif strength >= 40:
                day_type = ODSDayType.WEAK_BULLISH_OPEN
            else:
                day_type = ODSDayType.TREND_DRIVE_BULLISH  # Fallback for low strength

            return ODSData(
                day_type=day_type,
                direction="BULLISH",
                strength=strength,
                open_price=open_price,
                high_12min=high_12min,
                low_12min=low_12min,
                close_12min=close_12min,
                range_pct=range_pct,
                distance_from_open_pct=distance_from_open,
                volume_ratio=volume_ratio,
                upside_move_pct=upside_move,
                downside_move_pct=downside_move,
                classification_time=datetime.now()
            )

        # TREND DRIVE BEARISH with Intensity Classification
        if (downside_move > IMPULSE_THRESHOLD and
            distance_from_open < -HOLD_THRESHOLD and
            volume_ratio > VOLUME_STRONG and
            close_12min < open_price):

            strength = min(100, (downside_move / 2) * 100)

            # PHASE 1: Intensity-based classification (bearish)
            # Determine specific pattern type based on strength
            if strength >= 85:
                day_type = ODSDayType.STRONG_BEARISH_OPEN
            elif strength >= 60:
                day_type = ODSDayType.MODERATE_BEARISH_OPEN
            else:
                day_type = ODSDayType.TREND_DRIVE_BEARISH  # Fallback

            return ODSData(
                day_type=day_type,
                direction="BEARISH",
                strength=strength,
                open_price=open_price,
                high_12min=high_12min,
                low_12min=low_12min,
                close_12min=close_12min,
                range_pct=range_pct,
                distance_from_open_pct=distance_from_open,
                volume_ratio=volume_ratio,
                upside_move_pct=upside_move,
                downside_move_pct=downside_move,
                classification_time=datetime.now()
            )

        # FAILED DRIVE (impulso inicial que revierte)
        if (max(upside_move, downside_move) > IMPULSE_THRESHOLD and
            abs(distance_from_open) < 0.1 and  # Cerró cerca del open (reversión)
            volume_ratio > VOLUME_STRONG):

            strength = min(100, max(upside_move, downside_move) * 20)

            return ODSData(
                day_type=ODSDayType.FAILED_DRIVE,
                direction="REVERSAL",
                strength=strength,
                open_price=open_price,
                high_12min=high_12min,
                low_12min=low_12min,
                close_12min=close_12min,
                range_pct=range_pct,
                distance_from_open_pct=distance_from_open,
                volume_ratio=volume_ratio,
                upside_move_pct=upside_move,
                downside_move_pct=downside_move,
                classification_time=datetime.now()
            )

        # BALANCE DAY (rango estrecho, bajo volumen)
        if (range_pct < RANGE_NARROW and
            volume_ratio < VOLUME_WEAK):

            return ODSData(
                day_type=ODSDayType.BALANCE_DAY,
                direction="NEUTRAL",
                strength=0,
                open_price=open_price,
                high_12min=high_12min,
                low_12min=low_12min,
                close_12min=close_12min,
                range_pct=range_pct,
                distance_from_open_pct=distance_from_open,
                volume_ratio=volume_ratio,
                upside_move_pct=upside_move,
                downside_move_pct=downside_move,
                classification_time=datetime.now()
            )

        # UNCLEAR (no cumple criterios claros, trata como balance)
        return ODSData(
            day_type=ODSDayType.BALANCE_DAY,
            direction="NEUTRAL",
            strength=0,
            open_price=open_price,
            high_12min=high_12min,
            low_12min=low_12min,
            close_12min=close_12min,
            range_pct=range_pct,
            distance_from_open_pct=distance_from_open,
            volume_ratio=volume_ratio,
            upside_move_pct=upside_move,
            downside_move_pct=downside_move,
            classification_time=datetime.now()
        )

    async def classify_symbol_ods(
        self,
        symbol: str,
        bars: List[Any],
        premarket_data: Optional[Dict] = None
    ) -> ODSData:
        """
        Clasifica Opening Drive Structure para un símbolo

        Args:
            symbol: Símbolo a clasificar
            bars: Bars históricos (incluyen 9:30-9:42)
            premarket_data: Datos de premarket (opcional)

        Returns:
            ODSData con tipo de día, dirección, strength, etc.
        """
        # Reset cache si es nuevo día
        self._reset_cache_if_new_day()

        # Check cache (evita recalcular mismo símbolo)
        if symbol in self.ods_cache:
            return self.ods_cache[symbol]

        # Solo clasificar después de 9:42 AM ET
        if not self._is_after_ods_window():
            return ODSData(
                day_type=ODSDayType.PENDING,
                classification_pending=True
            )

        # Filtrar bars 9:30-9:42
        ods_bars = self._filter_ods_bars(bars)

        if len(ods_bars) < 12:
            return ODSData(
                day_type=ODSDayType.INSUFFICIENT_DATA,
                classification_time=datetime.now()
            )

        # Clasificar
        ods_data = self._classify_drive(ods_bars, premarket_data)

        # Cachear resultado
        self.ods_cache[symbol] = ods_data

        self.logger.info(
            f"🕐 {symbol}: ODS={ods_data.day_type.value}, "
            f"direction={ods_data.direction}, strength={ods_data.strength:.1f}, "
            f"range={ods_data.range_pct:.2f}%, vol_ratio={ods_data.volume_ratio:.1f}x"
        )

        return ods_data

    def get_ods(self, symbol: str) -> Optional[ODSData]:
        """
        Obtener ODS cacheado sin reclasificar

        Args:
            symbol: Símbolo

        Returns:
            ODSData si existe en cache, None si no
        """
        self._reset_cache_if_new_day()
        return self.ods_cache.get(symbol)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del cache"""
        total = len(self.ods_cache)
        by_type = {}

        for ods_data in self.ods_cache.values():
            day_type = ods_data.day_type.value
            by_type[day_type] = by_type.get(day_type, 0) + 1

        return {
            'total_symbols': total,
            'by_type': by_type,
            'cache_date': self.last_reset_date
        }
