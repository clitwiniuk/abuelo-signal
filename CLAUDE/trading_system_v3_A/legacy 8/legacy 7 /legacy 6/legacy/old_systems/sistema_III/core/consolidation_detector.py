#!/usr/bin/env python3
"""
Consolidation Pattern Detector - Detecta Patrones de Consolidación Pre-Breakout

Detecta:
1. Range Compression - ATR decreciente + volumen creciente (coiling)
2. Bollinger Band Squeeze - Bandas apretándose (volatilidad a punto de explotar)
3. Triangle/Flag Patterns - Highs descendentes + lows ascendentes
"""

import logging
import statistics
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timedelta
import numpy as np

try:
    from core.interfaces import MarketData
except ImportError:
    from collections import namedtuple
    MarketData = namedtuple('MarketData', ['timestamp', 'open', 'high', 'low', 'close', 'volume'])

@dataclass
class ConsolidationSignal:
    """Señal de consolidación detectada"""
    symbol: str
    timestamp: datetime
    pattern_type: str  # 'RANGE_COMPRESSION', 'BOLLINGER_SQUEEZE', 'TRIANGLE', 'FLAG'
    strength: float  # 0.0-1.0
    reason: str
    metadata: Dict
    breakout_probability: float  # 0.0-1.0 probabilidad de breakout inminente
    expected_direction: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'

class ConsolidationDetector:
    """
    Detector de Patrones de Consolidación para anticipar breakouts

    Identifica:
    1. Range Compression - Coiling pattern (baja volatilidad + alto volumen)
    2. Bollinger Squeeze - Bandas Bollinger comprimiéndose
    3. Triangle Formation - Highs bajando + lows subiendo
    4. Flag Pattern - Retroceso después de movimiento fuerte
    """

    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(f"{__name__}.ConsolidationDetector")
        self.config = config or {}

        # Configuración de parámetros
        self.atr_period = self.config.get('atr_period', 14)
        self.bb_period = self.config.get('bb_period', 20)
        self.bb_std_dev = self.config.get('bb_std_dev', 2.0)
        self.volume_period = self.config.get('volume_period', 20)

        # Thresholds para detección
        self.compression_threshold = self.config.get('compression_threshold', 0.7)  # 70% de ATR normal
        self.squeeze_threshold = self.config.get('squeeze_threshold', 0.6)  # 60% de BB width normal
        self.volume_increase_threshold = self.config.get('volume_increase_threshold', 1.2)  # 20% más volumen
        self.triangle_min_touches = self.config.get('triangle_min_touches', 4)  # Mínimo 4 toques

        # Historial para análisis
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        self.atr_history: Dict[str, deque] = {}
        self.bb_width_history: Dict[str, deque] = {}

        # Configuración de ventanas
        self.history_window = self.config.get('history_window', 50)  # 50 barras de historial
        self.analysis_window = self.config.get('analysis_window', 20)  # Ventana de análisis

        self.logger.info(f"📊 ConsolidationDetector initialized - pattern recognition enabled")

    def detect_consolidation_patterns(self, symbol: str, market_data: MarketData) -> List[ConsolidationSignal]:
        """
        Detecta patrones de consolidación pre-breakout

        Returns:
            List[ConsolidationSignal]: Patrones detectados
        """
        signals = []

        try:
            # Actualizar historial
            self._update_history(symbol, market_data)

            # Validar datos suficientes
            if not self._has_sufficient_data(symbol):
                return signals

            # 1. RANGE COMPRESSION ANALYSIS
            compression_signal = self._detect_range_compression(symbol, market_data)
            if compression_signal:
                signals.append(compression_signal)

            # 2. BOLLINGER SQUEEZE ANALYSIS
            squeeze_signal = self._detect_bollinger_squeeze(symbol, market_data)
            if squeeze_signal:
                signals.append(squeeze_signal)

            # 3. TRIANGLE PATTERN ANALYSIS
            triangle_signal = self._detect_triangle_pattern(symbol, market_data)
            if triangle_signal:
                signals.append(triangle_signal)

            # 4. FLAG PATTERN ANALYSIS
            flag_signal = self._detect_flag_pattern(symbol, market_data)
            if flag_signal:
                signals.append(flag_signal)

            # Log señales detectadas
            if signals:
                pattern_types = [s.pattern_type for s in signals]
                self.logger.info(f"🎯 {symbol}: Consolidation patterns detected: {pattern_types}")

            return signals

        except Exception as e:
            self.logger.error(f"❌ Error detecting consolidation patterns for {symbol}: {e}")
            return signals

    def _update_history(self, symbol: str, market_data: MarketData):
        """Actualiza historial de datos de mercado"""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.history_window)
            self.volume_history[symbol] = deque(maxlen=self.history_window)
            self.atr_history[symbol] = deque(maxlen=self.analysis_window)
            self.bb_width_history[symbol] = deque(maxlen=self.analysis_window)

        # Añadir datos actuales
        self.price_history[symbol].append(market_data)
        self.volume_history[symbol].append(market_data.volume)

        # Calcular y guardar ATR si tenemos suficientes datos
        if len(self.price_history[symbol]) >= self.atr_period:
            atr = self._calculate_atr(symbol)
            if atr:
                self.atr_history[symbol].append(atr)

        # Calcular y guardar BB Width si tenemos suficientes datos
        if len(self.price_history[symbol]) >= self.bb_period:
            bb_width = self._calculate_bollinger_width(symbol)
            if bb_width:
                self.bb_width_history[symbol].append(bb_width)

    def _has_sufficient_data(self, symbol: str) -> bool:
        """Verifica si tenemos datos suficientes para análisis"""
        return (symbol in self.price_history and
                len(self.price_history[symbol]) >= self.analysis_window)

    def _detect_range_compression(self, symbol: str, market_data: MarketData) -> Optional[ConsolidationSignal]:
        """
        Detecta compresión de rango (coiling pattern)

        Señal: ATR decreciente + volumen creciente = energía acumulándose
        """
        try:
            if len(self.atr_history[symbol]) < 10:
                return None

            # Analizar tendencia de ATR (debe estar decreciendo)
            recent_atr = list(self.atr_history[symbol])[-10:]
            atr_trend = self._calculate_trend(recent_atr)

            # Analizar tendencia de volumen (debe estar creciendo)
            recent_volume = list(self.volume_history[symbol])[-10:]
            volume_trend = self._calculate_trend(recent_volume)

            # Calcular compresión actual vs promedio
            current_atr = recent_atr[-1]
            avg_atr = statistics.mean(recent_atr[:-5])  # Promedio de 5 barras anteriores

            compression_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0

            # SEÑAL: ATR decreciente + volumen creciente + compresión significativa
            if (atr_trend < -0.05 and  # ATR bajando al menos 5%
                volume_trend > 0.1 and  # Volumen subiendo al menos 10%
                compression_ratio <= self.compression_threshold):  # ATR comprimido

                # Calcular fuerza del patrón
                compression_strength = max(0, (self.compression_threshold - compression_ratio) * 2)
                volume_strength = min(1.0, volume_trend)
                atr_strength = min(1.0, abs(atr_trend))

                strength = (compression_strength + volume_strength + atr_strength) / 3
                breakout_probability = min(0.95, strength * 1.2)

                return ConsolidationSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    pattern_type='RANGE_COMPRESSION',
                    strength=strength,
                    reason=f"ATR compression {compression_ratio:.2f}, trend: {atr_trend:.2%}, volume: {volume_trend:.2%}",
                    metadata={
                        'current_atr': current_atr,
                        'avg_atr': avg_atr,
                        'compression_ratio': compression_ratio,
                        'atr_trend': atr_trend,
                        'volume_trend': volume_trend,
                        'analysis_period': len(recent_atr)
                    },
                    breakout_probability=breakout_probability,
                    expected_direction='NEUTRAL'  # Dirección pendiente de determinar
                )

            return None

        except Exception as e:
            self.logger.error(f"Error detecting range compression for {symbol}: {e}")
            return None

    def _detect_bollinger_squeeze(self, symbol: str, market_data: MarketData) -> Optional[ConsolidationSignal]:
        """
        Detecta Bollinger Band Squeeze

        Señal: BB Width muy bajo = volatilidad a punto de explotar
        """
        try:
            if len(self.bb_width_history[symbol]) < 10:
                return None

            # Analizar BB Width actual vs histórico
            recent_bb_width = list(self.bb_width_history[symbol])
            current_width = recent_bb_width[-1]
            avg_width = statistics.mean(recent_bb_width[:-5])  # Promedio histórico

            width_ratio = current_width / avg_width if avg_width > 0 else 1.0

            # SEÑAL: BB Width muy comprimido
            if width_ratio <= self.squeeze_threshold:

                # Calcular cuán extremo es el squeeze
                min_width = min(recent_bb_width)
                squeeze_extremity = current_width / min_width if min_width > 0 else 1.0

                # Calcular fuerza del squeeze
                strength = min(1.0, (self.squeeze_threshold - width_ratio) * 2)
                breakout_probability = min(0.90, strength * 1.5)

                # Determinar dirección probable basada en posición del precio
                bb_bands = self._calculate_bollinger_bands(symbol)
                if bb_bands:
                    upper, middle, lower = bb_bands
                    price_position = (market_data.close - lower) / (upper - lower) if upper > lower else 0.5

                    if price_position > 0.7:
                        expected_direction = 'BULLISH'
                    elif price_position < 0.3:
                        expected_direction = 'BEARISH'
                    else:
                        expected_direction = 'NEUTRAL'
                else:
                    expected_direction = 'NEUTRAL'

                return ConsolidationSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    pattern_type='BOLLINGER_SQUEEZE',
                    strength=strength,
                    reason=f"BB width {width_ratio:.2f} of normal, squeeze extremity: {squeeze_extremity:.2f}",
                    metadata={
                        'current_width': current_width,
                        'avg_width': avg_width,
                        'width_ratio': width_ratio,
                        'squeeze_extremity': squeeze_extremity,
                        'bb_bands': bb_bands,
                        'price_position': price_position if bb_bands else None
                    },
                    breakout_probability=breakout_probability,
                    expected_direction=expected_direction
                )

            return None

        except Exception as e:
            self.logger.error(f"Error detecting Bollinger squeeze for {symbol}: {e}")
            return None

    def _detect_triangle_pattern(self, symbol: str, market_data: MarketData) -> Optional[ConsolidationSignal]:
        """
        Detecta patrones de triángulo

        Señal: Highs descendentes + Lows ascendentes = triángulo convergente
        """
        try:
            recent_data = list(self.price_history[symbol])[-20:]  # Últimas 20 barras
            if len(recent_data) < 15:
                return None

            # Identificar highs y lows significativos
            highs = self._find_significant_highs(recent_data)
            lows = self._find_significant_lows(recent_data)

            if len(highs) < 3 or len(lows) < 3:
                return None

            # Analizar tendencia de highs (debe ser descendente)
            high_prices = [h[1] for h in highs[-4:]]  # Últimos 4 highs
            high_trend = self._calculate_trend(high_prices)

            # Analizar tendencia de lows (debe ser ascendente)
            low_prices = [l[1] for l in lows[-4:]]  # Últimos 4 lows
            low_trend = self._calculate_trend(low_prices)

            # SEÑAL: Highs bajando + Lows subiendo = triángulo convergente
            if high_trend < -0.02 and low_trend > 0.02:  # Al menos 2% de pendiente

                # Calcular convergencia
                latest_high = high_prices[-1]
                latest_low = low_prices[-1]
                initial_high = high_prices[0]
                initial_low = low_prices[0]

                initial_range = initial_high - initial_low
                current_range = latest_high - latest_low
                convergence = 1 - (current_range / initial_range) if initial_range > 0 else 0

                # Calcular fuerza del patrón
                trend_strength = (abs(high_trend) + abs(low_trend)) / 2
                convergence_strength = min(1.0, convergence * 2)
                strength = (trend_strength + convergence_strength) / 2

                breakout_probability = min(0.85, strength * 1.3)

                # Dirección probable basada en momentum reciente
                recent_closes = [bar.close for bar in recent_data[-5:]]
                price_momentum = self._calculate_trend(recent_closes)
                expected_direction = 'BULLISH' if price_momentum > 0 else 'BEARISH'

                return ConsolidationSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    pattern_type='TRIANGLE',
                    strength=strength,
                    reason=f"Triangle convergence {convergence:.2%}, high trend: {high_trend:.2%}, low trend: {low_trend:.2%}",
                    metadata={
                        'highs_count': len(highs),
                        'lows_count': len(lows),
                        'high_trend': high_trend,
                        'low_trend': low_trend,
                        'convergence': convergence,
                        'current_range': current_range,
                        'initial_range': initial_range,
                        'price_momentum': price_momentum
                    },
                    breakout_probability=breakout_probability,
                    expected_direction=expected_direction
                )

            return None

        except Exception as e:
            self.logger.error(f"Error detecting triangle pattern for {symbol}: {e}")
            return None

    def _detect_flag_pattern(self, symbol: str, market_data: MarketData) -> Optional[ConsolidationSignal]:
        """
        Detecta patrones de bandera

        Señal: Movimiento fuerte seguido de consolidación lateral
        """
        try:
            recent_data = list(self.price_history[symbol])[-30:]  # Últimas 30 barras
            if len(recent_data) < 20:
                return None

            # Buscar movimiento fuerte previo (últimas 10-20 barras)
            trend_period = recent_data[-20:-10]  # Barras 20-10 hacia atrás
            consolidation_period = recent_data[-10:]  # Últimas 10 barras

            if len(trend_period) < 8 or len(consolidation_period) < 8:
                return None

            # Calcular movimiento en período de tendencia
            trend_start = trend_period[0].close
            trend_end = trend_period[-1].close
            trend_move = (trend_end - trend_start) / trend_start

            # Verificar que hubo movimiento significativo (>3%)
            if abs(trend_move) < 0.03:
                return None

            # Analizar consolidación (debe ser lateral)
            consolidation_highs = [bar.high for bar in consolidation_period]
            consolidation_lows = [bar.low for bar in consolidation_period]
            consolidation_closes = [bar.close for bar in consolidation_period]

            # Calcular rango de consolidación
            max_high = max(consolidation_highs)
            min_low = min(consolidation_lows)
            consolidation_range = (max_high - min_low) / min_low

            # Calcular tendencia en consolidación (debe ser mínima)
            consolidation_trend = self._calculate_trend(consolidation_closes)

            # SEÑAL: Movimiento fuerte + consolidación lateral
            if (abs(trend_move) > 0.05 and  # Movimiento > 5%
                consolidation_range < 0.08 and  # Rango consolidación < 8%
                abs(consolidation_trend) < 0.02):  # Tendencia consolidación < 2%

                # Determinar dirección del flag
                flag_direction = 'BULLISH' if trend_move > 0 else 'BEARISH'

                # Calcular fuerza del patrón
                move_strength = min(1.0, abs(trend_move) * 10)  # Normalizar movimiento
                consolidation_quality = max(0, 1 - (consolidation_range * 5))  # Mejor si rango es menor
                trend_quality = max(0, 1 - (abs(consolidation_trend) * 20))  # Mejor si es más lateral

                strength = (move_strength + consolidation_quality + trend_quality) / 3
                breakout_probability = min(0.80, strength * 1.1)

                return ConsolidationSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    pattern_type='FLAG',
                    strength=strength,
                    reason=f"Flag after {trend_move:.1%} move, consolidation range: {consolidation_range:.1%}",
                    metadata={
                        'trend_move': trend_move,
                        'consolidation_range': consolidation_range,
                        'consolidation_trend': consolidation_trend,
                        'trend_start_price': trend_start,
                        'trend_end_price': trend_end,
                        'current_price': market_data.close,
                        'move_strength': move_strength,
                        'consolidation_quality': consolidation_quality
                    },
                    breakout_probability=breakout_probability,
                    expected_direction=flag_direction
                )

            return None

        except Exception as e:
            self.logger.error(f"Error detecting flag pattern for {symbol}: {e}")
            return None

    def _calculate_atr(self, symbol: str) -> Optional[float]:
        """Calcula Average True Range"""
        try:
            data = list(self.price_history[symbol])[-self.atr_period:]
            if len(data) < 2:
                return None

            true_ranges = []
            for i in range(1, len(data)):
                high_low = data[i].high - data[i].low
                high_close_prev = abs(data[i].high - data[i-1].close)
                low_close_prev = abs(data[i].low - data[i-1].close)
                true_range = max(high_low, high_close_prev, low_close_prev)
                true_ranges.append(true_range)

            return statistics.mean(true_ranges) if true_ranges else None

        except Exception as e:
            self.logger.error(f"Error calculating ATR for {symbol}: {e}")
            return None

    def _calculate_bollinger_width(self, symbol: str) -> Optional[float]:
        """Calcula ancho de Bandas Bollinger como % del precio"""
        try:
            data = list(self.price_history[symbol])[-self.bb_period:]
            if len(data) < self.bb_period:
                return None

            closes = [bar.close for bar in data]
            mean_price = statistics.mean(closes)
            std_dev = statistics.stdev(closes)

            bb_width = (2 * self.bb_std_dev * std_dev) / mean_price
            return bb_width

        except Exception as e:
            self.logger.error(f"Error calculating Bollinger width for {symbol}: {e}")
            return None

    def _calculate_bollinger_bands(self, symbol: str) -> Optional[Tuple[float, float, float]]:
        """Calcula Bandas Bollinger (upper, middle, lower)"""
        try:
            data = list(self.price_history[symbol])[-self.bb_period:]
            if len(data) < self.bb_period:
                return None

            closes = [bar.close for bar in data]
            middle = statistics.mean(closes)
            std_dev = statistics.stdev(closes)

            upper = middle + (self.bb_std_dev * std_dev)
            lower = middle - (self.bb_std_dev * std_dev)

            return (upper, middle, lower)

        except Exception as e:
            self.logger.error(f"Error calculating Bollinger bands for {symbol}: {e}")
            return None

    def _calculate_trend(self, values: List[float]) -> float:
        """Calcula tendencia usando regresión lineal simple"""
        try:
            if len(values) < 2:
                return 0.0

            n = len(values)
            x = list(range(n))
            y = values

            # Regresión lineal simple
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))

            if n * sum_x2 - sum_x ** 2 == 0:
                return 0.0

            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)

            # Normalizar slope como % de cambio por período
            if values[0] != 0:
                return slope / values[0]
            return 0.0

        except Exception as e:
            self.logger.error(f"Error calculating trend: {e}")
            return 0.0

    def _find_significant_highs(self, data: List[MarketData]) -> List[Tuple[int, float]]:
        """Encuentra highs significativos en los datos"""
        highs = []
        for i in range(2, len(data) - 2):
            current_high = data[i].high
            if (current_high > data[i-1].high and current_high > data[i-2].high and
                current_high > data[i+1].high and current_high > data[i+2].high):
                highs.append((i, current_high))
        return highs

    def _find_significant_lows(self, data: List[MarketData]) -> List[Tuple[int, float]]:
        """Encuentra lows significativos en los datos"""
        lows = []
        for i in range(2, len(data) - 2):
            current_low = data[i].low
            if (current_low < data[i-1].low and current_low < data[i-2].low and
                current_low < data[i+1].low and current_low < data[i+2].low):
                lows.append((i, current_low))
        return lows

    def get_pattern_summary(self, symbol: str) -> Dict:
        """Obtiene resumen de patrones para un símbolo"""
        try:
            if symbol not in self.price_history or not self.price_history[symbol]:
                return {}

            # Calcular métricas actuales
            current_atr = self._calculate_atr(symbol) if len(self.atr_history.get(symbol, [])) > 0 else None
            current_bb_width = self._calculate_bollinger_width(symbol)

            return {
                'symbol': symbol,
                'data_points': len(self.price_history[symbol]),
                'current_atr': current_atr,
                'current_bb_width': current_bb_width,
                'atr_history_length': len(self.atr_history.get(symbol, [])),
                'bb_width_history_length': len(self.bb_width_history.get(symbol, []))
            }

        except Exception as e:
            self.logger.error(f"Error getting pattern summary for {symbol}: {e}")
            return {}

    def reset_history(self, symbol: str = None):
        """Reset historial para un símbolo o todos"""
        if symbol:
            for history_dict in [self.price_history, self.volume_history,
                               self.atr_history, self.bb_width_history]:
                if symbol in history_dict:
                    del history_dict[symbol]
        else:
            self.price_history.clear()
            self.volume_history.clear()
            self.atr_history.clear()
            self.bb_width_history.clear()

        self.logger.info(f"🔄 Consolidation pattern history reset for {symbol if symbol else 'all symbols'}")