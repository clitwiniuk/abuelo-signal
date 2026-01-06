"""
Trend Filters Module - Anti-Reversal Filters for Workers

Este módulo proporciona filtros anti-reversal reutilizables para evitar
entradas en picos de MACD/RSI con tendencias bajistas.

Casos de uso:
- MSAI (Vol Absorption): Entry @ $1.43 en pico MACD -> pérdida -$12.13
- SAGT (Low Vol Accum): Entry @ $2.50 con RSI 74.8 -> pérdida -$11.12

Filtros implementados:
1. MACD Downtrend: Rechaza si MACD < Signal y ambos descendiendo
2. EMA20 Downtrend: Rechaza si precio < EMA20 descendente
3. RSI Overbought: Rechaza si RSI > 75 (sobrecompra extrema)

Uso:
    from strategies.workers.trend_filters import TrendFilters

    filters = TrendFilters(logger=self.logger)
    is_valid, reason = filters.check_trend_filters(bars, current_price)

    if not is_valid:
        logger.info(f"⚪ {symbol}: REJECTED - {reason}")
        return False
"""

import logging
from typing import List, Tuple, Optional


class TrendFilters:
    """
    Filtros anti-reversal para workers

    Evita entradas en:
    - Picos de MACD con tendencia bajista
    - Precio bajo EMA20 descendente
    - RSI en sobrecompra extrema (>75)
    """

    def __init__(self, logger: Optional[logging.Logger] = None,
                 enable_macd: bool = True,
                 enable_ema: bool = True,
                 enable_rsi: bool = True,
                 rsi_overbought_extreme: float = 75.0,
                 rsi_overbought_warning: float = 70.0):
        """
        Inicializa los filtros de tendencia

        Args:
            logger: Logger para mensajes (opcional)
            enable_macd: Habilitar filtro MACD (default True)
            enable_ema: Habilitar filtro EMA20 (default True)
            enable_rsi: Habilitar filtro RSI (default True)
            rsi_overbought_extreme: Umbral RSI rechazo (default 75)
            rsi_overbought_warning: Umbral RSI advertencia (default 70)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.enable_macd = enable_macd
        self.enable_ema = enable_ema
        self.enable_rsi = enable_rsi
        self.rsi_overbought_extreme = rsi_overbought_extreme
        self.rsi_overbought_warning = rsi_overbought_warning

    def check_trend_filters(self, bars: List, current_price: float,
                           surveillance_mode: bool = False) -> Tuple[bool, str]:
        """
        FILTRO ANTI-REVERSAL: Evita entradas en tendencias bajistas claras

        Verifica:
        1. MACD no debe estar en tendencia bajista (MACD < Signal y ambos descendiendo)
        2. Precio no debe estar por debajo de EMA20 descendente
        3. RSI no debe estar en zona de sobrecompra extrema (>75)

        Args:
            bars: Lista de barras de precio
            current_price: Precio actual
            surveillance_mode: Si está en modo vigilante (más flexible con EMA)

        Returns:
            Tuple (is_valid, reason)
        """
        try:
            if len(bars) < 30:
                # No hay suficientes datos para calcular indicadores
                return True, "Insufficient data for trend analysis"

            # Extraer precios de cierre
            closes = [bar.close for bar in bars]

            # ===== FILTRO 1: MACD Trend =====
            if self.enable_macd:
                macd_line, signal_line, _ = self.calculate_macd(closes)

                if len(macd_line) >= 3 and len(signal_line) >= 3:
                    # Verificar si MACD está en tendencia bajista
                    macd_current = macd_line[-1]
                    signal_current = signal_line[-1]
                    macd_prev = macd_line[-2]
                    signal_prev = signal_line[-2]
                    macd_prev2 = macd_line[-3]
                    signal_prev2 = signal_line[-3]

                    macd_descending = macd_current < macd_prev < macd_prev2
                    signal_descending = signal_current < signal_prev < signal_prev2
                    macd_below_signal = macd_current < signal_current

                    if macd_below_signal and macd_descending and signal_descending:
                        return False, f"MACD downtrend (MACD={macd_current:.4f} < Signal={signal_current:.4f}, both falling)"

            # ===== FILTRO 2: EMA20 Trend =====
            if self.enable_ema:
                ema20 = self.calculate_ema(closes, period=20)

                if len(ema20) >= 3:
                    ema_current = ema20[-1]
                    ema_prev = ema20[-2]
                    ema_prev2 = ema20[-3]

                    ema_descending = ema_current < ema_prev < ema_prev2
                    price_below_ema = current_price < ema_current

                    if price_below_ema and ema_descending:
                        # En modo vigilante, solo advertir pero no rechazar
                        if surveillance_mode:
                            self.logger.warning(
                                f"⚠️ Price below descending EMA20 "
                                f"(${current_price:.2f} < ${ema_current:.2f})"
                            )
                        else:
                            return False, (
                                f"Price below descending EMA20 "
                                f"(${current_price:.2f} < ${ema_current:.2f})"
                            )

            # ===== FILTRO 3: RSI Overbought =====
            rsi_current = 50.0  # Default RSI value for logging
            if self.enable_rsi:
                rsi = self.calculate_rsi(closes, period=14)

                if len(rsi) > 0:
                    rsi_current = rsi[-1]

                    # Rechazar si RSI > threshold extreme
                    if rsi_current > self.rsi_overbought_extreme:
                        return False, (
                            f"RSI overbought "
                            f"(RSI={rsi_current:.1f} > {self.rsi_overbought_extreme})"
                        )

                    # Advertir si RSI > threshold warning
                    if rsi_current > self.rsi_overbought_warning:
                        self.logger.warning(f"⚠️ RSI elevated (RSI={rsi_current:.1f})")

            # Todos los filtros pasados
            filters_enabled = []
            if self.enable_macd:
                filters_enabled.append("MACD OK")
            if self.enable_ema:
                filters_enabled.append("EMA OK")
            if self.enable_rsi:
                filters_enabled.append(f"RSI={rsi_current:.1f}")

            return True, f"Trend filters passed ({', '.join(filters_enabled)})"

        except Exception as e:
            self.logger.error(f"Error in trend filters: {e}")
            # En caso de error, permitir la entrada (fail-safe)
            return True, f"Trend filter error: {str(e)}"

    @staticmethod
    def calculate_macd(closes: List[float], fast: int = 12, slow: int = 26,
                       signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
        """
        Calcula MACD (Moving Average Convergence Divergence)

        Args:
            closes: Lista de precios de cierre
            fast: Período EMA rápida (default 12)
            slow: Período EMA lenta (default 26)
            signal: Período señal (default 9)

        Returns:
            Tuple (macd_line, signal_line, histogram)
        """
        if len(closes) < slow + signal:
            return [], [], []

        # Calcular EMAs
        ema_fast = TrendFilters.calculate_ema(closes, fast)
        ema_slow = TrendFilters.calculate_ema(closes, slow)

        if not ema_fast or not ema_slow:
            return [], [], []

        # MACD line = EMA_fast - EMA_slow
        # Alinear las listas (EMA_slow es más corta)
        offset = len(ema_fast) - len(ema_slow)
        macd_line = [ema_fast[i + offset] - ema_slow[i] for i in range(len(ema_slow))]

        # Signal line = EMA9 of MACD
        signal_line = TrendFilters.calculate_ema(macd_line, signal)

        # Histogram = MACD - Signal
        # Alinear las listas
        offset = len(macd_line) - len(signal_line)
        histogram = [macd_line[i + offset] - signal_line[i] for i in range(len(signal_line))]

        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_ema(values: List[float], period: int) -> List[float]:
        """
        Calcula Exponential Moving Average

        Args:
            values: Lista de valores
            period: Período de la EMA

        Returns:
            Lista de valores EMA
        """
        if len(values) < period:
            return []

        ema = []
        multiplier = 2 / (period + 1)

        # Primera EMA es un SMA
        sma = sum(values[:period]) / period
        ema.append(sma)

        # Calcular EMAs subsiguientes
        for i in range(period, len(values)):
            ema_value = (values[i] - ema[-1]) * multiplier + ema[-1]
            ema.append(ema_value)

        return ema

    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> List[float]:
        """
        Calcula Relative Strength Index (RSI)

        Args:
            closes: Lista de precios de cierre
            period: Período del RSI (default 14)

        Returns:
            Lista de valores RSI
        """
        if len(closes) < period + 1:
            return []

        rsi_values = []

        # Calcular cambios de precio
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]

        # Separar ganancias y pérdidas
        gains = [delta if delta > 0 else 0 for delta in deltas]
        losses = [-delta if delta < 0 else 0 for delta in deltas]

        # Calcular RSI para cada punto
        avg_gain = 0.0
        avg_loss = 0.0

        for i in range(period, len(gains)):
            if i == period:
                # Primera media: SMA
                avg_gain = sum(gains[:period]) / period
                avg_loss = sum(losses[:period]) / period
            else:
                # Medias subsiguientes: EMA (Wilder's smoothing)
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            rsi_values.append(rsi)

        return rsi_values


# Función helper para crear filtros desde config
def create_trend_filters_from_config(config, section: str,
                                     logger: Optional[logging.Logger] = None) -> TrendFilters:
    """
    Crea TrendFilters desde configuración INI

    Args:
        config: Objeto ConfigParser
        section: Sección del config (ej: 'VOLUME_ABSORPTION_WORKER')
        logger: Logger opcional

    Returns:
        TrendFilters configurado

    Ejemplo config.ini:
        [VOLUME_ABSORPTION_WORKER]
        enable_trend_filters = true
        enable_macd_filter = true
        enable_ema_filter = true
        enable_rsi_filter = true
        rsi_overbought_extreme = 75.0
        rsi_overbought_warning = 70.0
    """
    if config and hasattr(config, 'getboolean'):
        enable_trend = config.getboolean(section, 'enable_trend_filters', fallback=True)

        if not enable_trend:
            # Retornar filtros deshabilitados
            return TrendFilters(
                logger=logger,
                enable_macd=False,
                enable_ema=False,
                enable_rsi=False
            )

        return TrendFilters(
            logger=logger,
            enable_macd=config.getboolean(section, 'enable_macd_filter', fallback=True),
            enable_ema=config.getboolean(section, 'enable_ema_filter', fallback=True),
            enable_rsi=config.getboolean(section, 'enable_rsi_filter', fallback=True),
            rsi_overbought_extreme=config.getfloat(section, 'rsi_overbought_extreme', fallback=75.0),
            rsi_overbought_warning=config.getfloat(section, 'rsi_overbought_warning', fallback=70.0)
        )
    else:
        # Fallback: usar defaults
        return TrendFilters(logger=logger)
