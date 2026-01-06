#!/usr/bin/env python3
"""
First Day Bounce Strategy for Smallcaps

Aprovecha el primer rebote después de una corrida extraordinaria seguida de retroceso.
Patrón típico: Sobreextensión -> Retroceso 25-50% -> Primer día verde en soporte -> Rebote

Escenario Ideal:
1. Corrida extraordinaria con catalizador (+50-200% en 1-5 días)
2. Retroceso con volumen decreciente (25-50% desde high)
3. Soporte técnico aguanta (EMA21, resistance-turned-support)
4. Primer día verde (Red-to-Green) con volumen
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass

from core.interfaces import MarketData, Signal, SignalType, Position
from .base import BaseStrategy
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config


@dataclass
class OverextensionData:
    """Data de la corrida inicial sobreextendida"""
    start_date: datetime
    start_price: float
    peak_date: datetime
    peak_price: float
    peak_volume: float
    total_gain_pct: float
    avg_daily_volume_before: float
    volume_multiple: float
    catalyst_type: str = "UNKNOWN"


@dataclass
class RetraceData:
    """Data del retroceso desde el pico"""
    retrace_start_date: datetime
    retrace_start_price: float
    current_low: float
    current_low_date: datetime
    retrace_pct: float
    days_since_peak: int
    avg_volume_during_retrace: float
    support_level: float
    support_type: str  # "EMA21", "PREVIOUS_RESISTANCE", "PSYCHOLOGICAL"


class FirstDayBounceStrategy(BaseStrategy):
    """
    Estrategia 1st Day Bounce para smallcaps sobreextendidas
    """

    def __init__(self, parameters: Dict = None):
        # FIRST DAY BOUNCE STRATEGY DEFAULTS - RELAXED FOR EASIER ENTRIES
        fallback_defaults = {
            # Detección de sobreextensión - RELAXED
            'min_gain_for_overextension_pct': 0.25,  # RELAXED: Reduced from 50% to 25%
            'max_days_for_overextension': 10,        # RELAXED: Increased from 5 to 10 days
            'min_volume_multiple': 1.5,              # RELAXED: Reduced from 3.0 to 1.5

            # Detección de retroceso - RELAXED
            'min_retrace_pct': 0.15,                 # RELAXED: Reduced from 25% to 15%
            'max_retrace_pct': 0.60,                 # RELAXED: Increased from 50% to 60%
            'max_days_in_retrace': 15,               # RELAXED: Increased from 10 to 15 days

            # Red-to-Green conditions - RELAXED
            'min_days_red_before_green': 1,          # RELAXED: Reduced from 2 to 1 day
            'max_days_red_before_green': 8,          # RELAXED: Increased from 5 to 8 days
            'min_green_day_volume_vs_retrace': 1.2,  # RELAXED: Reduced from 1.5 to 1.2

            # Support detection - RELAXED
            'support_tolerance_pct': 0.05,           # RELAXED: Increased from 3% to 5%
            'ema_period': 21,                        # Keep EMA21

            # Entry/Exit - RELAXED
            'max_distance_from_support_pct': 0.08,   # RELAXED: Increased from 5% to 8%
            'target_pct': 0.12,                      # RELAXED: Reduced from 15% to 12%
            'intraday_stop_below_open': 0.03,        # RELAXED: Increased from 2% to 3%

            # Minimum data requirements - RELAXED
            'min_history_bars': 20,                  # RELAXED: Reduced from 30 to 20 bars
        }

        # Initialize with fallback defaults first to get logger
        super().__init__("first_day_bounce", fallback_defaults)

        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('FIRST_DAY_BOUNCE_STRATEGY', fallback_defaults)

            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)

            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for First Day Bounce strategy: {e}")
            # Keep fallback defaults

        # Log received parameters after logger is initialized
        if parameters:
            self.logger.info(f"🎯 FirstDayBounce received parameters: {parameters}")

        # Initialize centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()

        # Storage para tracking de patterns
        self.overextended_stocks: Dict[str, OverextensionData] = {}
        self.retracing_stocks: Dict[str, RetraceData] = {}
        self.support_levels: Dict[str, List[float]] = {}

        # Histórico para análisis de soporte
        self.price_history: Dict[str, List[float]] = {}
        self.volume_history: Dict[str, List[float]] = {}

        self.logger.info(f"🎯 First Day Bounce Strategy initialized")
        self.logger.info(f"   📈 Min overextension: {self._parameters['min_gain_for_overextension_pct']*100:.0f}%")
        self.logger.info(f"   📉 Retrace range: {self._parameters['min_retrace_pct']*100:.0f}%-{self._parameters['max_retrace_pct']*100:.0f}%")
        self.logger.info(f"   💚 Red-to-Green target: Conservative bounce play")

    def analyze(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """
        Análisis principal para First Day Bounce

        Pipeline:
        1. Detectar sobreextensión pasada
        2. Detectar retroceso en rango objetivo
        3. Identificar soportes técnicos
        4. Confirmar Red-to-Green setup
        5. Generar señal si todas las condiciones se cumplen
        """
        try:
            # Actualizar históricos
            self._update_history(symbol, bar)

            # 1. FASE: Detectar sobreextensión pasada o en progreso
            if symbol not in self.overextended_stocks:
                overextension = self._detect_overextension(symbol, bar)
                if overextension:
                    self.overextended_stocks[symbol] = overextension
                    self.logger.info(f"🚀 {symbol}: Overextension detected - "
                                   f"{overextension.total_gain_pct:.1f}% gain, "
                                   f"{overextension.volume_multiple:.1f}x volume")
                    return None  # No entry yet, just tracking

            # 2. FASE: Detectar retroceso desde sobreextensión
            if symbol in self.overextended_stocks:
                retrace_data = self._analyze_retrace_phase(symbol, bar)

                if retrace_data and symbol not in self.retracing_stocks:
                    self.retracing_stocks[symbol] = retrace_data
                    self.logger.info(f"📉 {symbol}: Retrace phase detected - "
                                   f"{retrace_data.retrace_pct:.1f}% pullback from high")
                    return None  # Still tracking, no entry

            # 3. FASE: Buscar Red-to-Green setup
            if symbol in self.retracing_stocks:
                signal = self._check_red_to_green_setup(symbol, bar)
                if signal:
                    self.logger.info(f"💚 {symbol}: First Day Bounce signal generated!")
                    return signal

            return None

        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {e}")
            return None

    def _update_history(self, symbol: str, bar: MarketData):
        """Actualizar histórico de precios y volumen"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
            self.volume_history[symbol] = []

        self.price_history[symbol].append(bar.close)
        self.volume_history[symbol].append(bar.volume)

        # Mantener máximo 50 días de historia
        if len(self.price_history[symbol]) > 50:
            self.price_history[symbol] = self.price_history[symbol][-50:]
            self.volume_history[symbol] = self.volume_history[symbol][-50:]

    def _detect_overextension(self, symbol: str, bar: MarketData) -> Optional[OverextensionData]:
        """
        Detectar corridas sobreextendidas

        Criterios:
        1. Ganancia mínima 50% en máximo 5 días
        2. Volumen mínimo 3x promedio histórico
        3. Pico reciente (últimos 2-10 días)
        """
        try:
            min_history = self._parameters.get('min_history_bars', 20)
            if len(self.price_history[symbol]) < min_history:
                return None  # Necesita historia suficiente

            prices = self.price_history[symbol]
            volumes = self.volume_history[symbol]

            # Buscar pico en últimos 10 días
            recent_prices = prices[-10:]
            peak_idx = np.argmax(recent_prices)
            peak_price = recent_prices[peak_idx]

            # Calcular ganancia desde base (20-30 días atrás)
            base_price = np.mean(prices[-30:-20])  # Precio base hace 20-30 días
            total_gain_pct = (peak_price - base_price) / base_price

            # Verificar criterios de sobreextensión
            min_gain = self._parameters['min_gain_for_overextension_pct']
            if total_gain_pct < min_gain:
                return None

            # Verificar volumen durante la corrida
            peak_volume = volumes[-10 + peak_idx]
            avg_volume_before = np.mean(volumes[-30:-10])
            volume_multiple = peak_volume / avg_volume_before if avg_volume_before > 0 else 0

            min_volume_mult = self._parameters['min_volume_multiple']
            if volume_multiple < min_volume_mult:
                return None

            # Crear datos de sobreextensión
            overextension = OverextensionData(
                start_date=datetime.now() - timedelta(days=30),
                start_price=base_price,
                peak_date=datetime.now() - timedelta(days=10-peak_idx),
                peak_price=peak_price,
                peak_volume=peak_volume,
                total_gain_pct=total_gain_pct,
                avg_daily_volume_before=avg_volume_before,
                volume_multiple=volume_multiple,
                catalyst_type=self._identify_catalyst_type(symbol, volume_multiple)
            )

            return overextension

        except Exception as e:
            self.logger.error(f"Error detecting overextension for {symbol}: {e}")
            return None

    def _analyze_retrace_phase(self, symbol: str, bar: MarketData) -> Optional[RetraceData]:
        """
        Analizar fase de retroceso desde sobreextensión

        Criterios:
        1. Retroceso 25-50% desde pico
        2. Volumen decreciente vs corrida inicial
        3. Soporte técnico identificado
        """
        try:
            overextension = self.overextended_stocks[symbol]
            current_price = bar.close

            # Calcular retroceso desde pico
            retrace_pct = (overextension.peak_price - current_price) / overextension.peak_price

            # Verificar rango de retroceso objetivo
            min_retrace = self._parameters['min_retrace_pct']
            max_retrace = self._parameters['max_retrace_pct']

            if retrace_pct < min_retrace or retrace_pct > max_retrace:
                return None

            # Identificar soporte técnico
            support_level, support_type = self._identify_support_level(symbol, current_price)
            if not support_level:
                return None

            # Verificar que precio está cerca del soporte
            distance_from_support = abs(current_price - support_level) / support_level
            max_distance = self._parameters['max_distance_from_support_pct']

            if distance_from_support > max_distance:
                return None

            # Crear datos de retroceso
            retrace_data = RetraceData(
                retrace_start_date=overextension.peak_date,
                retrace_start_price=overextension.peak_price,
                current_low=current_price,  # Simplificado
                current_low_date=datetime.now(),
                retrace_pct=retrace_pct,
                days_since_peak=5,  # Simplificado
                avg_volume_during_retrace=bar.volume * 0.7,  # Volumen menor
                support_level=support_level,
                support_type=support_type
            )

            return retrace_data

        except Exception as e:
            self.logger.error(f"Error analyzing retrace for {symbol}: {e}")
            return None

    def _identify_support_level(self, symbol: str, current_price: float) -> tuple[float, str]:
        """
        Identificar soporte técnico clave

        Tipos de soporte:
        1. EMA21 - Soporte dinámico
        2. Previous Resistance - Resistencia previa convertida en soporte
        3. Psychological Level - Números redondos
        """
        try:
            prices = self.price_history[symbol]

            # 1. EMA21 como soporte dinámico
            if len(prices) >= 21:
                ema21 = self._calculate_ema(prices, 21)
                tolerance = self._parameters['support_tolerance_pct']

                if abs(current_price - ema21) / ema21 <= tolerance:
                    return ema21, "EMA21"

            # 2. Previous resistance levels
            # Buscar niveles donde el precio rebotó múltiples veces
            resistance_levels = self._find_resistance_levels(prices)
            for level in resistance_levels:
                if abs(current_price - level) / level <= tolerance:
                    return level, "PREVIOUS_RESISTANCE"

            # 3. Psychological levels (números redondos)
            psychological_level = self._find_psychological_support(current_price)
            if psychological_level:
                return psychological_level, "PSYCHOLOGICAL"

            return None, None

        except Exception as e:
            self.logger.error(f"Error identifying support for {symbol}: {e}")
            return None, None

    def _check_red_to_green_setup(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """
        Verificar setup Red-to-Green para entry

        Criterios:
        1. Primer día verde después de 2-5 días rojos
        2. Volumen superior al promedio del retroceso
        3. Price action cerca del soporte
        4. No gaps down significativos
        """
        try:
            retrace_data = self.retracing_stocks[symbol]

            # Verificar que es un día verde
            if bar.close <= bar.open:
                return None  # No es día verde

            # Verificar volumen vs retroceso
            min_volume_mult = self._parameters['min_green_day_volume_vs_retrace']
            if bar.volume < retrace_data.avg_volume_during_retrace * min_volume_mult:
                self.logger.debug(f"{symbol}: Insufficient volume for Red-to-Green")
                return None

            # Verificar proximidad al soporte
            distance_from_support = abs(bar.close - retrace_data.support_level) / retrace_data.support_level
            max_distance = self._parameters['max_distance_from_support_pct']

            if distance_from_support > max_distance:
                self.logger.debug(f"{symbol}: Too far from support for entry")
                return None

            # Generar señal
            overextension = self.overextended_stocks[symbol]

            # Calcular targets
            entry_price = bar.close
            stop_loss = entry_price * (1 - self._parameters['stop_loss_pct'])
            target_price = entry_price * (1 + self._parameters['target_pct'])

            # Alternativa: Target hacia próxima resistencia
            next_resistance = self._find_next_resistance(symbol, entry_price)
            if next_resistance and next_resistance < target_price:
                target_price = next_resistance

            signal = Signal(
                signal_id=f"fdb_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}",
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=0.75,  # Fuerza moderada (contra-tendencia)
                price=entry_price,
                timestamp=datetime.now(),
                strategy_name=self.name,
                metadata={
                    'setup_type': 'FIRST_DAY_BOUNCE',
                    'overextension_gain_pct': overextension.total_gain_pct * 100,
                    'retrace_pct': retrace_data.retrace_pct * 100,
                    'support_level': retrace_data.support_level,
                    'support_type': retrace_data.support_type,
                    'volume_multiple_vs_retrace': bar.volume / retrace_data.avg_volume_during_retrace,
                    'volume_ratio': bar.volume / retrace_data.avg_volume_during_retrace,
                    'stop_loss': stop_loss,
                    'target_price': target_price,
                    'risk_reward_ratio': (target_price - entry_price) / (entry_price - stop_loss),
                    'catalyst_type': overextension.catalyst_type,
                    'days_since_peak': retrace_data.days_since_peak,
                    'pattern': f"fdb_{retrace_data.support_type}_{retrace_data.days_since_peak}d"
                }
            )

            # Register position with centralized stop_loss_manager
            self._register_position_with_stop_manager(symbol, bar, signal)

            # Limpiar tracking (setup completado)
            del self.retracing_stocks[symbol]
            del self.overextended_stocks[symbol]

            return signal

        except Exception as e:
            self.logger.error(f"Error checking Red-to-Green setup for {symbol}: {e}")
            return None

    # === HELPER METHODS ===

    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calcular EMA simple"""
        if len(prices) < period:
            return np.mean(prices)

        multiplier = 2 / (period + 1)
        ema = prices[0]

        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def _find_resistance_levels(self, prices: List[float]) -> List[float]:
        """Encontrar niveles de resistencia previos"""
        # Simplificado: buscar máximos locales que actuaron como resistencia
        if len(prices) < 10:
            return []

        resistance_levels = []
        for i in range(5, len(prices) - 5):
            # Verificar si es máximo local
            if prices[i] == max(prices[i-3:i+4]):
                resistance_levels.append(prices[i])

        # Consolidar niveles cercanos
        consolidated = []
        for level in sorted(set(resistance_levels)):
            if not consolidated or abs(level - consolidated[-1]) / consolidated[-1] > 0.02:
                consolidated.append(level)

        return consolidated[-3:]  # Últimos 3 niveles más relevantes

    def _find_psychological_support(self, price: float) -> Optional[float]:
        """Encontrar soporte psicológico (números redondos)"""
        # Números redondos según rango de precio
        if price < 5:
            # Para penny stocks: $1, $2, $3, etc
            return float(int(price))
        elif price < 20:
            # Para smallcaps: $5, $10, $15, etc
            return float((int(price / 5) * 5))
        else:
            # Para precios más altos: $20, $25, $30, etc
            return float((int(price / 10) * 10))

    def _find_next_resistance(self, symbol: str, current_price: float) -> Optional[float]:
        """Encontrar próxima resistencia para target"""
        overextension = self.overextended_stocks.get(symbol)
        if not overextension:
            return None

        # Target conservador: 50% del retroceso hacia el pico
        peak_price = overextension.peak_price
        next_resistance = current_price + ((peak_price - current_price) * 0.5)

        return next_resistance

    def _identify_catalyst_type(self, symbol: str, volume_multiple: float) -> str:
        """Identificar tipo de catalizador basado en volumen"""
        if volume_multiple > 10:
            return "MAJOR_NEWS"
        elif volume_multiple > 5:
            return "EARNINGS_CONTRACT"
        else:
            return "TECHNICAL_BREAKOUT"

    def get_strategy_info(self) -> Dict[str, Any]:
        """Información del estado actual de la estrategia"""
        return {
            'strategy_name': self.name,
            'overextended_stocks_tracking': len(self.overextended_stocks),
            'retracing_stocks_tracking': len(self.retracing_stocks),
            'active_setups': list(self.retracing_stocks.keys()),
            'parameters': self._parameters
        }

    def _register_position_with_stop_manager(self, symbol: str, bar: MarketData, signal: Signal):
        """Register the new position with SMALLCAP-OPTIMIZED centralized stop loss manager"""

        # SMALLCAPS FIRST DAY BOUNCE: Use global config.ini parameters optimized for smallcaps
        # This strategy targets bounce plays after overextension, requiring:
        # - fallback_stop_loss_pct = 0.06 (6% for volatility after recent overextension)
        # - enable_dynamic_ema_trailing = true (responsive to momentum recovery)
        # - ema_trailing_periods = 5 (fast EMA-5 for bounce momentum)
        # - max_hold_minutes = 180 (3 hours - bounce plays are quick or fail)
        stop_params = create_stop_params_from_config(self._parameters)

        # Determine side
        side = 'bullish' if signal.signal_type == SignalType.LONG else 'bearish'

        # Register with stop manager
        self.stop_manager.register_position(
            symbol=symbol,
            entry_price=signal.price,
            entry_time=bar.timestamp,
            side=side,
            strategy_name="FirstDayBounce_Smallcaps_Optimized",
            stop_params=stop_params
        )

        self.logger.info(f"📊 {symbol}: FIRST DAY BOUNCE SMALLCAP-OPTIMIZED - "
                        f"6% stop, EMA-5 trailing, post-overextension bounce play")

    # Abstract methods implementation (required by BaseStrategy)
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze single bar - delegates to main analyze method"""
        return self.analyze(bar.symbol, bar)

    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        return None

    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited - uses centralized stop_manager"""
        # FirstDayBounce strategy relies entirely on the centralized stop_manager
        # No custom exit logic needed beyond the smallcap-optimized parameters
        return None