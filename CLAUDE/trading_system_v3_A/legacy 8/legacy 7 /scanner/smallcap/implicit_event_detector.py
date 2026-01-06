"""
Implicit Event Detector - Price-First Approach for SMALLCAPS
Detecta eventos basados en anomalías de precio ANTES de buscar noticias

OPTIMIZADO PARA SMALLCAPS ($1-$10):
- Gaps más grandes (10%+ vs 5% en large caps)
- Volumen explosivo más común (3x+ vs 2x)
- Mayor volatilidad intradía (rangos más amplios)

Este detector NO reemplaza el sistema actual, se integra como FILTRO ADICIONAL opcional.
Feature flag: enable_implicit_event_detection (default: False)
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ImplicitEventDetector:
    """
    Detecta eventos implícitos en SMALLCAPS basados en precio + volumen

    Filosofía:
    1. El PRECIO habla primero (gap, volumen, rango)
    2. El NLP valida después (filtro de basura)
    3. No dependemos de keywords frágiles

    SMALLCAP-SPECIFIC:
    - min_gap_pct: 10% (vs 5% large caps) - smallcaps tienen gaps más violentos
    - min_volume_ratio: 3.0x (vs 2x) - volumen explosivo es común
    - min_range_percentile: 85 (vs 90) - más tolerante a volatilidad
    - min_event_score: 2/4 (flexible para no perder oportunidades)

    Uso:
        detector = ImplicitEventDetector(config)
        anomaly = await detector.detect_anomaly(
            symbol='ABCD',
            current_price=5.50,
            previous_close=4.00,  # +37.5% gap
            current_volume=5000000,
            avg_volume=1000000,   # 5x volume
            current_range=2.0,
            historical_ranges=[0.3, 0.4, 0.5, ...]
        )

        if anomaly:
            # Evento implícito detectado → Fetch news
            news = await fetch_news(symbol)
            if validate_sentiment(news):
                # Evento confirmado → Enter trade
                enter_trade(symbol)
    """

    def __init__(self, config: Optional[Dict] = None):
        self.logger = logging.getLogger(f"{__name__}.ImplicitEventDetector")
        self.config = config or {}

        # Configuración SMALLCAP-SPECIFIC con fallbacks seguros
        self.min_gap_pct = self.config.get('min_gap_pct', 10.0)  # Smallcaps: 10%+
        self.min_volume_ratio = self.config.get('min_volume_ratio', 3.0)  # Smallcaps: 3x+
        self.min_range_percentile = self.config.get('min_range_percentile', 85)  # Más tolerante
        self.min_event_score = self.config.get('min_event_score', 2)  # 2/4 flexible

        self.logger.info(
            f"✅ ImplicitEventDetector (SMALLCAPS) initialized - "
            f"gap≥{self.min_gap_pct}%, vol≥{self.min_volume_ratio}x, "
            f"range≥P{self.min_range_percentile}, score≥{self.min_event_score}/4"
        )

    async def detect_anomaly(
        self,
        symbol: str,
        current_price: float,
        previous_close: float,
        current_volume: int,
        avg_volume: int,
        current_range: float,
        historical_ranges: List[float],
        bars: Optional[List[Dict]] = None
    ) -> Optional[Dict]:
        """
        Detecta anomalía de precio en SMALLCAPS (evento implícito)

        Args:
            symbol: Ticker del símbolo
            current_price: Precio actual/close
            previous_close: Cierre del día anterior
            current_volume: Volumen actual (acumulado o de la barra)
            avg_volume: Volumen promedio (20 días típico)
            current_range: Rango actual (high - low)
            historical_ranges: Rangos históricos últimos 60 días
            bars: Barras recientes (opcional, para detectar expansión)

        Returns:
            None si no hay evento
            Dict con métricas si SÍ hay evento implícito detectado

        Ejemplos:
            # Earnings beat con gap masivo
            >>> detect_anomaly('ABCD', 8.50, 5.00, 10M, 2M, 3.5, [...])
            {'gap_pct': 70.0, 'volume_ratio': 5.0, 'score': 4/4}  # ✅ EVENTO

            # Pump sin fundamento
            >>> detect_anomaly('SCAM', 1.50, 1.40, 500K, 400K, 0.2, [...])
            {'gap_pct': 7.1, 'volume_ratio': 1.25, 'score': 0/4}  # ❌ NO evento
        """
        try:
            # Validaciones básicas
            if previous_close <= 0:
                self.logger.warning(f"{symbol}: Invalid previous_close={previous_close}")
                return None

            if avg_volume <= 0:
                self.logger.warning(f"{symbol}: Invalid avg_volume={avg_volume}")
                return None

            # 1. GAP (más importante para eventos en smallcaps)
            gap_pct = ((current_price - previous_close) / previous_close) * 100

            # 2. VOLUME RATIO (en smallcaps, 3x+ es típico en eventos)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

            # 3. RANGE PERCENTILE (smallcaps son más volátiles)
            range_percentile = self._calculate_percentile(current_range, historical_ranges)

            # 4. EXPANSION (velas alcistas continuas, no chop)
            expansion = self._detect_expansion(bars) if bars else False

            # SCORING SYSTEM (cada señal = 1 punto, max 4)
            score = 0
            reasons = []

            if abs(gap_pct) >= self.min_gap_pct:
                score += 1
                reasons.append(f"Gap {gap_pct:+.1f}%")

            if volume_ratio >= self.min_volume_ratio:
                score += 1
                reasons.append(f"Vol {volume_ratio:.1f}x")

            if range_percentile >= self.min_range_percentile:
                score += 1
                reasons.append(f"Range P{range_percentile:.0f}")

            if expansion:
                score += 1
                reasons.append("Expansion")

            # EVENTO DETECTADO si score >= threshold (2/4 para smallcaps)
            if score >= self.min_event_score:
                self.logger.info(
                    f"🎯 {symbol}: IMPLICIT EVENT detected "
                    f"(score={score}/4) - {', '.join(reasons)}"
                )

                return {
                    'symbol': symbol,
                    'gap_pct': round(gap_pct, 2),
                    'volume_ratio': round(volume_ratio, 2),
                    'range_percentile': round(range_percentile, 1),
                    'expansion': expansion,
                    'score': score,
                    'max_score': 4,
                    'reasons': reasons,
                    'timestamp': datetime.now(),
                    'current_price': current_price,
                    'previous_close': previous_close,
                    'current_volume': current_volume,
                    'avg_volume': avg_volume,
                    'current_range': current_range,
                }
            else:
                self.logger.debug(
                    f"⏭️ {symbol}: No implicit event "
                    f"(score={score}/{self.min_event_score}, reasons: {reasons if reasons else 'none'})"
                )
                return None

        except Exception as e:
            self.logger.error(f"❌ Error detecting anomaly for {symbol}: {e}", exc_info=True)
            return None

    def _calculate_percentile(self, value: float, historical_values: List[float]) -> float:
        """
        Calcula percentile de un valor vs histórico

        Args:
            value: Valor actual
            historical_values: Lista de valores históricos

        Returns:
            Percentile (0-100)
        """
        if not historical_values or len(historical_values) == 0:
            return 50.0  # Neutral si no hay histórico

        try:
            # Cuenta cuántos valores históricos son menores
            count_below = sum(1 for v in historical_values if v < value)
            percentile = (count_below / len(historical_values)) * 100
            return percentile
        except Exception as e:
            self.logger.error(f"Error calculating percentile: {e}")
            return 50.0

    def _detect_expansion(self, bars: Optional[List[Dict]]) -> bool:
        """
        Detecta velas de expansión continua (no chop)

        En smallcaps, expansión significa:
        - Velas alcistas consecutivas (close > open) para gaps positivos
        - Rangos crecientes o estables (no contracción severa >30%)

        Args:
            bars: Lista de barras recientes (al menos 3 para análisis)

        Returns:
            True si hay expansión limpia
            False si hay chop o datos insuficientes
        """
        if not bars or len(bars) < 3:
            return False

        try:
            # Últimas 3 velas
            recent = bars[-3:]

            # Todas alcistas (close > open) - para gaps positivos
            all_bullish = all(
                b.get('close', 0) > b.get('open', 0)
                for b in recent
            )

            # Rangos no contraen significativamente
            ranges = [
                b.get('high', 0) - b.get('low', 0)
                for b in recent
            ]

            if ranges[0] <= 0:
                return False

            # Último rango >= 70% del primer rango (tolerante para smallcaps)
            no_severe_contraction = ranges[-1] >= ranges[0] * 0.7

            expansion_detected = all_bullish and no_severe_contraction

            if expansion_detected:
                self.logger.debug(
                    f"✅ Expansion detected: bullish={all_bullish}, "
                    f"ranges={[f'{r:.2f}' for r in ranges]}"
                )

            return expansion_detected

        except Exception as e:
            self.logger.error(f"Error detecting expansion: {e}")
            return False

    def get_config_summary(self) -> Dict:
        """
        Retorna resumen de configuración actual

        Returns:
            Dict con parámetros configurados para smallcaps
        """
        return {
            'asset_class': 'SMALLCAPS',
            'price_range': '$1-$10',
            'min_gap_pct': self.min_gap_pct,
            'min_volume_ratio': self.min_volume_ratio,
            'min_range_percentile': self.min_range_percentile,
            'min_event_score': self.min_event_score,
        }
