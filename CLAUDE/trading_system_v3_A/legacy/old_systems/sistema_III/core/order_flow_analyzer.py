#!/usr/bin/env python3
"""
Order Flow Analyzer - Señales Predictivas de Desequilibrio
Detecta presión compradora/vendedora ANTES del movimiento usando bid/ask data de IBKR
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timedelta
import statistics

try:
    from core.interfaces import MarketData
except ImportError:
    from collections import namedtuple
    MarketData = namedtuple('MarketData', ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'bid', 'ask', 'bid_size', 'ask_size'])

@dataclass
class OrderFlowSignal:
    """Señal de order flow detectada"""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'BULLISH_PRESSURE', 'BEARISH_PRESSURE', 'INSTITUTIONAL_ACTIVITY', etc.
    strength: float  # 0.0-1.0
    reason: str
    metadata: Dict
    confidence: float  # 0.0-1.0

class OrderFlowAnalyzer:
    """
    Analizador de Order Flow para detectar desequilibrios predictivos

    Detecta:
    1. Bid/Ask Imbalance - Presión compradora vs vendedora
    2. Spread Tightening - Actividad institucional
    3. Volume at Price - Agresividad en niveles específicos
    4. Pressure Building - Momentum acumulándose sin movimiento precio
    """

    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(f"{__name__}.OrderFlowAnalyzer")
        self.config = config or {}

        # Configuración de thresholds
        self.bid_pressure_threshold = self.config.get('bid_pressure_threshold', 0.75)  # 75% del flow
        self.spread_compression_threshold = self.config.get('spread_compression_threshold', 0.6)  # 60% de spread normal
        self.aggressive_volume_threshold = self.config.get('aggressive_volume_threshold', 0.65)  # 65% del volumen
        self.pressure_buildup_volume_mult = self.config.get('pressure_buildup_volume_mult', 2.0)  # 2x volumen
        self.pressure_buildup_price_max = self.config.get('pressure_buildup_price_max', 0.01)  # 1% movimiento precio

        # Historial para análisis
        self.market_data_history: Dict[str, deque] = {}
        self.spread_history: Dict[str, deque] = {}
        self.flow_history: Dict[str, deque] = {}

        # Configuración de ventanas
        self.history_window = self.config.get('history_window', 20)  # 20 barras de historial
        self.spread_avg_window = self.config.get('spread_avg_window', 10)  # Promedio spread 10 barras

        self.logger.info(f"🔍 OrderFlowAnalyzer initialized - predictive desequilibrium detection")

    def analyze_order_flow(self, symbol: str, market_data: MarketData) -> List[OrderFlowSignal]:
        """
        Analiza order flow y detecta señales predictivas

        Returns:
            List[OrderFlowSignal]: Señales detectadas
        """
        signals = []

        try:
            # Actualizar historial
            self._update_history(symbol, market_data)

            # Validar datos básicos
            if not self._validate_market_data(market_data):
                return signals

            # 1. ANÁLISIS BID/ASK IMBALANCE
            imbalance_signal = self._analyze_bid_ask_imbalance(symbol, market_data)
            if imbalance_signal:
                signals.append(imbalance_signal)

            # 2. ANÁLISIS SPREAD TIGHTENING
            spread_signal = self._analyze_spread_tightening(symbol, market_data)
            if spread_signal:
                signals.append(spread_signal)

            # 3. ANÁLISIS VOLUME AT PRICE
            volume_signal = self._analyze_volume_at_price(symbol, market_data)
            if volume_signal:
                signals.append(volume_signal)

            # 4. ANÁLISIS PRESSURE BUILDING
            pressure_signal = self._analyze_pressure_building(symbol, market_data)
            if pressure_signal:
                signals.append(pressure_signal)

            # Log señales detectadas
            if signals:
                signal_types = [s.signal_type for s in signals]
                self.logger.info(f"🎯 {symbol}: Order flow signals detected: {signal_types}")

            return signals

        except Exception as e:
            self.logger.error(f"❌ Error analyzing order flow for {symbol}: {e}")
            return signals

    def _update_history(self, symbol: str, market_data: MarketData):
        """Actualiza historial de datos de mercado"""
        if symbol not in self.market_data_history:
            self.market_data_history[symbol] = deque(maxlen=self.history_window)
            self.spread_history[symbol] = deque(maxlen=self.spread_avg_window)
            self.flow_history[symbol] = deque(maxlen=self.history_window)

        self.market_data_history[symbol].append(market_data)

        # Calcular y guardar spread
        if market_data.bid and market_data.ask and market_data.close:
            spread_pct = (market_data.ask - market_data.bid) / market_data.close
            self.spread_history[symbol].append(spread_pct)

        # Calcular y guardar flow ratio
        if market_data.bid_size and market_data.ask_size:
            total_size = market_data.bid_size + market_data.ask_size
            bid_pressure = market_data.bid_size / total_size if total_size > 0 else 0.5
            self.flow_history[symbol].append(bid_pressure)

    def _validate_market_data(self, market_data: MarketData) -> bool:
        """Valida que tenemos datos suficientes para análisis"""
        required_fields = ['bid', 'ask', 'bid_size', 'ask_size', 'close', 'volume']

        for field in required_fields:
            value = getattr(market_data, field, None)
            if value is None or value <= 0:
                return False

        return True

    def _analyze_bid_ask_imbalance(self, symbol: str, market_data: MarketData) -> Optional[OrderFlowSignal]:
        """
        Detecta desequilibrio bid/ask que indica presión direccional

        SEÑAL BULLISH: bid_size >> ask_size (más compradores que vendedores)
        SEÑAL BEARISH: ask_size >> bid_size (más vendedores que compradores)
        """
        try:
            total_size = market_data.bid_size + market_data.ask_size
            if total_size == 0:
                return None

            bid_pressure = market_data.bid_size / total_size

            # Calcular fuerza del desequilibrio
            if bid_pressure >= self.bid_pressure_threshold:
                # PRESIÓN BULLISH
                strength = min((bid_pressure - 0.5) * 2, 1.0)  # Normalizar 0.5-1.0 -> 0.0-1.0
                confidence = min(strength * 1.2, 1.0)

                return OrderFlowSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    signal_type='BULLISH_PRESSURE',
                    strength=strength,
                    reason=f"Bid pressure {bid_pressure:.1%} (threshold: {self.bid_pressure_threshold:.1%})",
                    metadata={
                        'bid_size': market_data.bid_size,
                        'ask_size': market_data.ask_size,
                        'bid_pressure': bid_pressure,
                        'bid_ask_ratio': market_data.bid_size / market_data.ask_size if market_data.ask_size > 0 else float('inf')
                    },
                    confidence=confidence
                )

            elif bid_pressure <= (1 - self.bid_pressure_threshold):
                # PRESIÓN BEARISH
                ask_pressure = 1 - bid_pressure
                strength = min((ask_pressure - 0.5) * 2, 1.0)
                confidence = min(strength * 1.2, 1.0)

                return OrderFlowSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    signal_type='BEARISH_PRESSURE',
                    strength=strength,
                    reason=f"Ask pressure {ask_pressure:.1%} (threshold: {self.bid_pressure_threshold:.1%})",
                    metadata={
                        'bid_size': market_data.bid_size,
                        'ask_size': market_data.ask_size,
                        'ask_pressure': ask_pressure,
                        'ask_bid_ratio': market_data.ask_size / market_data.bid_size if market_data.bid_size > 0 else float('inf')
                    },
                    confidence=confidence
                )

            return None

        except Exception as e:
            self.logger.error(f"Error analyzing bid/ask imbalance for {symbol}: {e}")
            return None

    def _analyze_spread_tightening(self, symbol: str, market_data: MarketData) -> Optional[OrderFlowSignal]:
        """
        Detecta spread tightening que indica actividad institucional

        Spread apretándose = institucionales activos, posible movimiento inminente
        """
        try:
            if symbol not in self.spread_history or len(self.spread_history[symbol]) < 5:
                return None

            current_spread = (market_data.ask - market_data.bid) / market_data.close
            avg_spread = statistics.mean(self.spread_history[symbol])

            if avg_spread == 0:
                return None

            spread_compression = current_spread / avg_spread

            if spread_compression <= self.spread_compression_threshold:
                # SPREAD APRETÁNDOSE - Actividad institucional
                strength = min((self.spread_compression_threshold - spread_compression) * 2, 1.0)
                confidence = min(strength * 1.5, 1.0)  # Alta confianza en señal spread

                return OrderFlowSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    signal_type='INSTITUTIONAL_ACTIVITY',
                    strength=strength,
                    reason=f"Spread compression {spread_compression:.2f} (avg: {avg_spread:.4f}, current: {current_spread:.4f})",
                    metadata={
                        'current_spread': current_spread,
                        'avg_spread': avg_spread,
                        'compression_ratio': spread_compression,
                        'bid': market_data.bid,
                        'ask': market_data.ask,
                        'last': market_data.close
                    },
                    confidence=confidence
                )

            return None

        except Exception as e:
            self.logger.error(f"Error analyzing spread tightening for {symbol}: {e}")
            return None

    def _analyze_volume_at_price(self, symbol: str, market_data: MarketData) -> Optional[OrderFlowSignal]:
        """
        Analiza dónde está ocurriendo el volumen más agresivo

        Volume at ask > volume at bid = comprando agresivamente
        Volume at bid > volume at ask = vendiendo agresivamente
        """
        try:
            # Estimamos volume at ask/bid basado en bid/ask sizes y volume total
            # Esta es una aproximación ya que no tenemos datos exactos de volume at price

            total_size = market_data.bid_size + market_data.ask_size
            if total_size == 0:
                return None

            # Estimación: si más size en ask, probablemente más volume hitting ask
            estimated_volume_at_ask_ratio = market_data.ask_size / total_size

            if estimated_volume_at_ask_ratio >= self.aggressive_volume_threshold:
                # COMPRANDO AGRESIVAMENTE
                strength = min((estimated_volume_at_ask_ratio - 0.5) * 2, 1.0)
                confidence = min(strength * 1.1, 1.0)

                return OrderFlowSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    signal_type='AGGRESSIVE_BUYING',
                    strength=strength,
                    reason=f"Aggressive buying detected {estimated_volume_at_ask_ratio:.1%} (threshold: {self.aggressive_volume_threshold:.1%})",
                    metadata={
                        'volume': market_data.volume,
                        'ask_size': market_data.ask_size,
                        'bid_size': market_data.bid_size,
                        'volume_at_ask_ratio': estimated_volume_at_ask_ratio
                    },
                    confidence=confidence
                )

            elif estimated_volume_at_ask_ratio <= (1 - self.aggressive_volume_threshold):
                # VENDIENDO AGRESIVAMENTE
                estimated_volume_at_bid_ratio = 1 - estimated_volume_at_ask_ratio
                strength = min((estimated_volume_at_bid_ratio - 0.5) * 2, 1.0)
                confidence = min(strength * 1.1, 1.0)

                return OrderFlowSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    signal_type='AGGRESSIVE_SELLING',
                    strength=strength,
                    reason=f"Aggressive selling detected {estimated_volume_at_bid_ratio:.1%} (threshold: {self.aggressive_volume_threshold:.1%})",
                    metadata={
                        'volume': market_data.volume,
                        'ask_size': market_data.ask_size,
                        'bid_size': market_data.bid_size,
                        'volume_at_bid_ratio': estimated_volume_at_bid_ratio
                    },
                    confidence=confidence
                )

            return None

        except Exception as e:
            self.logger.error(f"Error analyzing volume at price for {symbol}: {e}")
            return None

    def _analyze_pressure_building(self, symbol: str, market_data: MarketData) -> Optional[OrderFlowSignal]:
        """
        Detecta pressure building: momentum acumulándose sin movimiento de precio

        Señal: Volume alto + precio relativamente estable = presión acumulándose
        """
        try:
            if symbol not in self.market_data_history or len(self.market_data_history[symbol]) < 5:
                return None

            # Obtener datos históricos
            history = list(self.market_data_history[symbol])
            if len(history) < 5:
                return None

            # Calcular cambio de precio en últimas 5 barras
            price_5_ago = history[-5].close
            current_price = market_data.close
            price_change_pct = abs(current_price - price_5_ago) / price_5_ago

            # Calcular cambio de volumen
            avg_volume_5 = statistics.mean([bar.volume for bar in history[-5:]])
            current_volume = market_data.volume
            volume_multiplier = current_volume / avg_volume_5 if avg_volume_5 > 0 else 1.0

            # SEÑAL: Volume alto + precio estable = pressure building
            if (volume_multiplier >= self.pressure_buildup_volume_mult and
                price_change_pct <= self.pressure_buildup_price_max):

                # Strength basado en desequilibrio volume vs precio
                volume_strength = min((volume_multiplier - 1) / 2, 1.0)  # Normalizar
                price_stability = max(0, 1 - (price_change_pct / self.pressure_buildup_price_max))
                strength = (volume_strength + price_stability) / 2
                confidence = min(strength * 1.3, 1.0)

                return OrderFlowSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    signal_type='PRESSURE_BUILDING',
                    strength=strength,
                    reason=f"Pressure building: {volume_multiplier:.1f}x volume, {price_change_pct:.1%} price change",
                    metadata={
                        'volume_multiplier': volume_multiplier,
                        'price_change_pct': price_change_pct,
                        'current_volume': current_volume,
                        'avg_volume_5': avg_volume_5,
                        'price_5_ago': price_5_ago,
                        'current_price': current_price
                    },
                    confidence=confidence
                )

            return None

        except Exception as e:
            self.logger.error(f"Error analyzing pressure building for {symbol}: {e}")
            return None

    def get_flow_summary(self, symbol: str) -> Dict:
        """Obtiene resumen del order flow para un símbolo"""
        try:
            if symbol not in self.flow_history or not self.flow_history[symbol]:
                return {}

            recent_flow = list(self.flow_history[symbol])
            avg_bid_pressure = statistics.mean(recent_flow) if recent_flow else 0.5

            return {
                'avg_bid_pressure': avg_bid_pressure,
                'avg_ask_pressure': 1 - avg_bid_pressure,
                'flow_trend': 'BULLISH' if avg_bid_pressure > 0.6 else 'BEARISH' if avg_bid_pressure < 0.4 else 'NEUTRAL',
                'samples': len(recent_flow)
            }

        except Exception as e:
            self.logger.error(f"Error getting flow summary for {symbol}: {e}")
            return {}

    def reset_history(self, symbol: str = None):
        """Reset historial para un símbolo o todos"""
        if symbol:
            if symbol in self.market_data_history:
                del self.market_data_history[symbol]
            if symbol in self.spread_history:
                del self.spread_history[symbol]
            if symbol in self.flow_history:
                del self.flow_history[symbol]
        else:
            self.market_data_history.clear()
            self.spread_history.clear()
            self.flow_history.clear()

        self.logger.info(f"🔄 Order flow history reset for {symbol if symbol else 'all symbols'}")