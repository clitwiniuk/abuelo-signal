"""
Volume Absorption Breakout Worker

Edge: Detecta acumulación institucional ANTES del breakout mediante análisis
de absorción de volumen en zonas clave.

Modo: Scanner-Assisted (monitorea tickers con quality_score > 70)
"""

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .base_worker_logic import BaseWorkerLogic
from core.trade_arbiter import TradingHorizon


@dataclass
class AbsorptionEvent:
    """Representa un evento de absorción detectado"""
    bar_index: int
    timestamp: datetime
    price: float
    volume: float
    volume_ratio: float
    body_pct: float
    close_position_pct: float


class VolumeAbsorptionWorkerLogic(BaseWorkerLogic):
    """
    Worker que detecta acumulación institucional mediante análisis de absorción de volumen

    Estrategia:
    1. Detecta zona de consolidación con volumen elevado
    2. Identifica "absorption events" (volumen alto, indecisión, cierre alcista)
    3. Espera breakout confirmado con volumen
    4. Entra cuando todas las condiciones se cumplen
    """

    def __init__(self, execution_engine, risk_manager=None, config=None):
        super().__init__(
            worker_name='volume_absorption',
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Store config for parameter reading
        self.config = config

        # Read parameters from config.ini [VOLUME_ABSORPTION_WORKER]
        # If config not available, use defaults
        if config and hasattr(config, 'getfloat'):
            section = 'VOLUME_ABSORPTION_WORKER'

            # Parámetros de filtro inicial
            self.min_price = config.getfloat(section, 'min_price', fallback=2.0)
            self.max_price = config.getfloat(section, 'max_price', fallback=20.0)
            self.min_avg_volume = config.getint(section, 'min_avg_volume', fallback=200000)
            self.max_spread_pct = config.getfloat(section, 'max_spread_pct', fallback=0.03)
            self.max_gap_pct = config.getfloat(section, 'max_gap_pct', fallback=0.15)

            # Parámetros de zona de acumulación
            self.consolidation_range_pct = config.getfloat(section, 'consolidation_range_pct', fallback=0.02)
            self.consolidation_lookback = config.getint(section, 'consolidation_lookback', fallback=10)
            self.volume_ratio_consolidation = config.getfloat(section, 'volume_ratio_consolidation', fallback=1.8)
            self.vwap_tolerance = config.getfloat(section, 'vwap_tolerance', fallback=0.005)
            self.min_absorption_events = config.getint(section, 'min_absorption_events', fallback=2)

            # Parámetros de absorption event
            self.absorption_volume_mult = config.getfloat(section, 'absorption_volume_mult', fallback=2.0)
            self.absorption_body_pct = config.getfloat(section, 'absorption_body_pct', fallback=0.40)
            self.absorption_close_top_pct = config.getfloat(section, 'absorption_close_top_pct', fallback=0.30)

            # Parámetros de breakout
            self.breakout_buffer = config.getfloat(section, 'breakout_buffer', fallback=0.0015)
            self.breakout_volume_mult = config.getfloat(section, 'breakout_volume_mult', fallback=3.0)
            self.vwap_slope_min = config.getfloat(section, 'vwap_slope_min', fallback=0.0001)

            # Timing
            self.trading_start_hour = config.getfloat(section, 'trading_start_hour', fallback=10.0)
            self.trading_end_hour = config.getfloat(section, 'trading_end_hour', fallback=15.5)

            # MODO VIGILANTE: Parámetros para detectar volumen inusual independientemente del scanner
            self.surveillance_mode_enabled = config.getboolean(section, 'surveillance_mode_enabled', fallback=True)
            self.surveillance_volume_threshold = config.getfloat(section, 'surveillance_volume_threshold', fallback=1.5)  # 1.5x avg volume
            self.surveillance_min_price = config.getfloat(section, 'surveillance_min_price', fallback=1.0)  # Más bajo para smallcaps
            self.surveillance_max_price = config.getfloat(section, 'surveillance_max_price', fallback=25.0)  # Más alto para smallcaps
            self.surveillance_check_interval = config.getint(section, 'surveillance_check_interval', fallback=300)  # 5 minutos

            # FILTROS ANTI-REVERSAL: Usar módulo común
            from .trend_filters import create_trend_filters_from_config
            self.trend_filters = create_trend_filters_from_config(config, section, logger=self.logger)
        else:
            # Fallback to hardcoded defaults if config not available
            self.min_price = 2.0
            self.max_price = 20.0
            self.min_avg_volume = 200000
            self.max_spread_pct = 0.03
            self.max_gap_pct = 0.15
            self.consolidation_range_pct = 0.02
            self.consolidation_lookback = 10
            self.volume_ratio_consolidation = 1.8
            self.vwap_tolerance = 0.005
            self.min_absorption_events = 2
            self.absorption_volume_mult = 2.0
            self.absorption_body_pct = 0.40
            self.absorption_close_top_pct = 0.30
            self.breakout_buffer = 0.0015
            self.breakout_volume_mult = 3.0
            self.vwap_slope_min = 0.0001
            self.trading_start_hour = 10.0
            self.trading_end_hour = 15.5

            # MODO VIGILANTE: Defaults para smallcaps
            self.surveillance_mode_enabled = True
            self.surveillance_volume_threshold = 1.5  # 1.5x avg volume para detectar movimientos
            self.surveillance_min_price = 1.0  # Más bajo para smallcaps
            self.surveillance_max_price = 25.0  # Más alto para smallcaps
            self.surveillance_check_interval = 300  # 5 minutos

            # FILTROS ANTI-REVERSAL: Usar módulo común con defaults
            from .trend_filters import TrendFilters
            self.trend_filters = TrendFilters(logger=self.logger)

        # Estado del modo vigilante
        self.last_surveillance_check = datetime.now()
        self.surveillance_candidates = set()  # Tickers con volumen inusual detectados

        # Initialize centralized stop manager from config.ini
        from strategies.workers.worker_stop_manager import create_worker_stop_manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'VOLUME_ABSORPTION_STRATEGY')
        else:
            # Fallback: create with conservative defaults if config not available
            from strategies.workers.worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=5.0,        # Conservative SL
                take_profit_pct=8.0,      # Conservative TP
                trailing_activation=6.0,  # Activate trailing AFTER TP
                trailing_distance=2.0,    # 2% trailing from peak
                max_position_hours=6.0    # Max 6 hours hold
            ))

        self.logger.info("✅ Volume Absorption Worker initialized (Scanner-Assisted + Surveillance Mode)")
        self.logger.info(f"   Config: Price ${self.min_price}-${self.max_price}, "
                        f"Vol {self.min_avg_volume:,}, Absorption events {self.min_absorption_events}")
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")
        if self.surveillance_mode_enabled:
            self.logger.info(f"   👁️ Surveillance Mode: Enabled - Volume >{self.surveillance_volume_threshold}x, "
                           f"Price ${self.surveillance_min_price}-{self.surveillance_max_price}, "
                           f"Check every {self.surveillance_check_interval}s")

    async def should_enter(self, opportunity: Dict) -> bool:
        """
        Determina si debe entrar en una posición basándose en absorción de volumen

        Args:
            opportunity: Dictionary with opportunity data

        Returns:
            bool: True if should enter, False otherwise
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
                existing_worker = position.get('strategy', 'unknown') if position else 'unknown'
                self.logger.warning(
                    f"⚪ {symbol}: BLOCKED - already held in {strategy_type.upper()} trading (strategy: {existing_worker})"
                )
                return False

            # Get bars using BaseWorkerLogic method (handles both scanner and direct opportunities)
            bars = self.get_bars_from_opportunity(opportunity)

            if not bars or len(bars) < 30:
                self.logger.info(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0} < 30)")
                return False

            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)

            # MODO VIGILANTE: Si viene del scanner pero no pasa filtros iniciales,
            # verificar si tiene volumen inusual para análisis vigilante
            surveillance_mode = False
            if self.surveillance_mode_enabled:
                surveillance_mode = self._check_surveillance_criteria(opportunity, bars)

            # STEP 1: Filtro inicial (más relajado en modo vigilante)
            passed, reason = self._check_initial_filters(opportunity, current_price, bars, surveillance_mode)
            if not passed:
                # En modo vigilante, log diferente pero no rechazamos aún
                if surveillance_mode:
                    self.logger.info(f"👁️ {symbol}: Surveillance mode - bypassing strict filters ({reason})")
                else:
                    self.logger.info(f"⚪ {symbol}: {reason}")
                    return False

            # STEP 2: Trading hours
            if not self._is_trading_hours():
                self.logger.info(f"⚪ {symbol}: Outside trading hours (10:00-15:30 ET)")
                return False

            # STEP 3: Detectar zona de acumulación (más flexible en modo vigilante)
            in_accumulation, accum_reason = self._detect_accumulation_zone(bars, current_price, surveillance_mode)
            if not in_accumulation:
                if surveillance_mode:
                    self.logger.info(f"👁️ {symbol}: Surveillance mode - accumulation check failed but continuing ({accum_reason})")
                else:
                    self.logger.info(f"⚪ {symbol}: Not in accumulation zone - {accum_reason}")
                    return False

            # STEP 4: Detectar absorption events (más flexible en modo vigilante)
            absorption_events = self._detect_absorption_events(bars)
            min_events_required = 1 if surveillance_mode else self.min_absorption_events  # Solo 1 evento en vigilante
            if len(absorption_events) < min_events_required:
                if surveillance_mode:
                    self.logger.info(f"👁️ {symbol}: Surveillance mode - only {len(absorption_events)} absorption events (need {min_events_required}) but continuing")
                else:
                    self.logger.info(f"⚪ {symbol}: Insufficient absorption events ({len(absorption_events)} < {min_events_required})")
                    return False

            # STEP 5: Verificar Time & Sales (volumen agresivo) - más flexible en vigilante
            ts_confirmed, ts_reason = self._check_time_and_sales(bars, surveillance_mode)
            if not ts_confirmed:
                if surveillance_mode:
                    self.logger.info(f"👁️ {symbol}: Surveillance mode - T&S not confirmed but continuing ({ts_reason})")
                else:
                    self.logger.info(f"⚪ {symbol}: Time & Sales not confirmed - {ts_reason}")
                    return False

            # STEP 5.5: FILTRO ANTI-REVERSAL - Evitar entradas en tendencias bajistas claras
            # Este filtro previene entradas en picos de MACD con tendencia descendente
            is_trend_valid, trend_reason = self.trend_filters.check_trend_filters(bars, current_price, surveillance_mode)
            if not is_trend_valid:
                if surveillance_mode:
                    self.logger.info(f"👁️ {symbol}: Surveillance mode - trend filter failed but continuing ({trend_reason})")
                else:
                    self.logger.info(f"⚪ {symbol}: REJECTED - {trend_reason}")
                    return False

            # STEP 6: Detectar breakout (más flexible en modo vigilante)
            is_breaking_out, breakout_reason = self._detect_breakout(bars, current_price, surveillance_mode)
            if not is_breaking_out:
                if surveillance_mode:
                    self.logger.info(f"👁️ {symbol}: Surveillance mode - no breakout detected but continuing ({breakout_reason})")
                else:
                    self.logger.info(f"⚪ {symbol}: No breakout - {breakout_reason}")
                    return False

            # STEP 7: Calcular pattern completion
            pattern_completion = self._calculate_pattern_completion(
                quality_score=quality_score,
                absorption_events=absorption_events,
                in_accumulation=in_accumulation,
                is_breaking_out=is_breaking_out
            )

            # Log successful setup con modo
            mode_indicator = "👁️ SURVEILLANCE" if surveillance_mode else "🔍 SCANNER"
            self.logger.info(
                f"✅ {symbol}: ABSORPTION SETUP CONFIRMED ({mode_indicator}) - "
                f"Events: {len(absorption_events)}, "
                f"Quality: {quality_score:.1f}, "
                f"Pattern: {pattern_completion:.0f}%"
            )

            return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in should_enter: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _check_initial_filters(self, opportunity: Dict, current_price: float, bars: List, surveillance_mode: bool = False) -> Tuple[bool, str]:
        """Verifica filtros iniciales de precio, volumen, spread, gap"""

        # Precio (más flexible en modo vigilante)
        min_price_check = self.surveillance_min_price if surveillance_mode else self.min_price
        max_price_check = self.surveillance_max_price if surveillance_mode else self.max_price

        if current_price < min_price_check or current_price > max_price_check:
            return False, f"Price ${current_price:.2f} outside range ${min_price_check}-{max_price_check}"

        # Volumen promedio (calculado desde los bars, últimos 20 días/barras)
        if len(bars) >= 20:
            avg_volume = sum(bar.volume for bar in bars[-20:]) / 20
        elif len(bars) > 0:
            avg_volume = sum(bar.volume for bar in bars) / len(bars)
        else:
            avg_volume = 0

        # En modo vigilante, no requerimos volumen mínimo alto
        min_volume_check = 50000 if surveillance_mode else self.min_avg_volume  # 50k mínimo en vigilante

        if avg_volume < min_volume_check:
            return False, f"Avg volume {int(avg_volume):,} < {min_volume_check:,}"

        # Gap (más flexible en modo vigilante)
        gap_pct = abs(opportunity.get('gap_percent', 0)) / 100
        max_gap_check = 0.25 if surveillance_mode else self.max_gap_pct  # 25% gap máximo en vigilante
        if gap_pct > max_gap_check:
            return False, f"Gap {gap_pct*100:.1f}% > {max_gap_check*100:.0f}%"

        return True, "Initial filters passed"

    def _is_trading_hours(self) -> bool:
        """Verifica si está dentro del horario de trading (10:00-15:30 ET)"""
        import pytz
        eastern = pytz.timezone('US/Eastern')
        # FIX: Use current time in Spain timezone, then convert to Eastern
        # Since we're in Spain (Europe/Madrid), datetime.now() gives Spain time
        spain_tz = pytz.timezone('Europe/Madrid')
        current_spain_time = datetime.now(spain_tz)
        now_et = current_spain_time.astimezone(eastern)
        current_hour = now_et.hour + now_et.minute / 60.0

        return self.trading_start_hour <= current_hour <= self.trading_end_hour

    def _detect_accumulation_zone(self, bars: List, current_price: float, surveillance_mode: bool = False) -> Tuple[bool, str]:
        """
        Detecta zona de acumulación:
        - Precio en rango de 2% durante últimas 10 velas
        - Volumen elevado (1.8x promedio)
        - Precio cerca de VWAP (±0.5%)

        Args:
            bars: Lista de barras históricas
            current_price: Precio actual
            surveillance_mode: Si True, aplica criterios más flexibles
        """
        if len(bars) < self.consolidation_lookback + 20:
            return False, "Insufficient bars for accumulation detection"

        recent_bars = bars[-self.consolidation_lookback:]

        # 1. Verificar rango de consolidación
        highs = [bar.high for bar in recent_bars]
        lows = [bar.low for bar in recent_bars]
        high_price = max(highs)
        low_price = min(lows)

        price_range_pct = ((high_price - low_price) / low_price) if low_price > 0 else 1.0

        if price_range_pct > self.consolidation_range_pct:
            return False, f"Range too wide ({price_range_pct*100:.1f}% > {self.consolidation_range_pct*100:.0f}%)"

        # 2. Verificar volumen elevado en consolidación vs promedio anterior
        recent_volume = sum([bar.volume for bar in recent_bars]) / len(recent_bars)
        earlier_bars = bars[-(self.consolidation_lookback + 20):-self.consolidation_lookback]
        earlier_volume = sum([bar.volume for bar in earlier_bars]) / len(earlier_bars)

        volume_ratio = recent_volume / earlier_volume if earlier_volume > 0 else 0

        if volume_ratio < self.volume_ratio_consolidation:
            return False, f"Volume ratio {volume_ratio:.1f}x < {self.volume_ratio_consolidation}x"

        # 3. Verificar precio cerca de VWAP
        vwap = self._calculate_vwap(recent_bars)
        if vwap > 0:
            distance_from_vwap_pct = abs((current_price - vwap) / vwap)
            if distance_from_vwap_pct > self.vwap_tolerance:
                return False, f"Price {distance_from_vwap_pct*100:.1f}% from VWAP (> {self.vwap_tolerance*100:.1f}%)"

        self.logger.info(
            f"📊 Accumulation zone detected: Range={price_range_pct*100:.1f}%, "
            f"Vol ratio={volume_ratio:.1f}x, VWAP dist={distance_from_vwap_pct*100:.1f}%"
        )

        return True, "Accumulation zone confirmed"

    def _detect_absorption_events(self, bars: List) -> List[AbsorptionEvent]:
        """
        Detecta eventos de absorción en las últimas 15 velas

        Absorption Event:
        - Volumen > 2x promedio
        - Cuerpo < 40% del rango (indecisión)
        - Cierre en top 30% del rango (compradores ganando)
        """
        absorption_events = []
        lookback = 15

        if len(bars) < lookback + 10:
            return absorption_events

        recent_bars = bars[-lookback:]

        # Calcular volumen promedio de referencia
        reference_bars = bars[-(lookback + 10):-lookback]
        avg_volume = sum([bar.volume for bar in reference_bars]) / len(reference_bars)

        for i, bar in enumerate(recent_bars):
            # Condición 1: Volumen > 2x promedio
            volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 0
            if volume_ratio < self.absorption_volume_mult:
                continue

            # Condición 2: Cuerpo < 40% del rango
            bar_range = bar.high - bar.low
            if bar_range == 0:
                continue

            body = abs(bar.close - bar.open)
            body_pct = body / bar_range

            if body_pct > self.absorption_body_pct:
                continue

            # Condición 3: Cierre en top 30% del rango
            close_position = (bar.close - bar.low) / bar_range if bar_range > 0 else 0

            if close_position < (1.0 - self.absorption_close_top_pct):
                continue

            # Evento confirmado
            event = AbsorptionEvent(
                bar_index=len(bars) - lookback + i,
                timestamp=bar.date if hasattr(bar, 'date') else datetime.now(),
                price=bar.close,
                volume=bar.volume,
                volume_ratio=volume_ratio,
                body_pct=body_pct,
                close_position_pct=close_position
            )

            absorption_events.append(event)

            self.logger.debug(
                f"  📊 Absorption event #{len(absorption_events)}: "
                f"Vol={volume_ratio:.1f}x, Body={body_pct*100:.0f}%, "
                f"Close@{close_position*100:.0f}% of range"
            )

        return absorption_events

    def _check_time_and_sales(self, bars: List, surveillance_mode: bool = False) -> Tuple[bool, str]:
        """
        Simula análisis de Time & Sales usando datos de barras

        Como IBKR tiene limitaciones en tick data para smallcaps, usamos proxy:
        - Actividad reciente: últimas 5 velas deben tener volumen > promedio
        - Agresividad compradora: cierre cerca del high (compradores agresivos)
        - Sin distribución: no hay velas con cierre bajo y volumen alto

        Returns:
            Tuple[bool, str]: (confirmed, reason)
        """
        lookback = 5

        if len(bars) < lookback + 10:
            return False, "Insufficient bars for T&S analysis"

        recent_bars = bars[-lookback:]
        reference_bars = bars[-(lookback + 10):-lookback]

        # 1. Actividad: volumen promedio reciente > referencia (más flexible en vigilante)
        recent_volume = sum([bar.volume for bar in recent_bars]) / len(recent_bars)
        reference_volume = sum([bar.volume for bar in reference_bars]) / len(reference_bars)

        activity_ratio = recent_volume / reference_volume if reference_volume > 0 else 0

        min_activity_ratio = 1.0 if surveillance_mode else 1.2  # 1.0x en vigilante vs 1.2x normal
        if activity_ratio < min_activity_ratio:
            return False, f"Low activity ({activity_ratio:.1f}x < {min_activity_ratio}x)"

        # 2. Agresividad compradora: cierre en top 50% del rango (más flexible en vigilante)
        bullish_closes = 0
        for bar in recent_bars:
            bar_range = bar.high - bar.low
            if bar_range == 0:
                continue

            close_position = (bar.close - bar.low) / bar_range
            if close_position >= 0.5:  # Cierre en mitad superior
                bullish_closes += 1

        min_bullish_closes = 2 if surveillance_mode else 3  # Solo 2 de 5 en vigilante vs 3 de 5 normal
        if bullish_closes < min_bullish_closes:
            return False, f"Not enough bullish closes ({bullish_closes}/5 < {min_bullish_closes})"

        # 3. Sin distribución: no velas con cierre bajo + volumen muy alto
        for bar in recent_bars:
            bar_range = bar.high - bar.low
            if bar_range == 0:
                continue

            close_position = (bar.close - bar.low) / bar_range
            volume_ratio = bar.volume / reference_volume if reference_volume > 0 else 0

            # Vela bajista con volumen extremo = distribución
            if close_position < 0.3 and volume_ratio > 3.0:
                return False, "Distribution detected (bearish close + high volume)"

        self.logger.info(
            f"✅ T&S confirmed: Activity={activity_ratio:.1f}x, "
            f"Bullish closes={bullish_closes}/5"
        )

        return True, "Time & Sales confirmed"

    def _detect_breakout(self, bars: List, current_price: float, surveillance_mode: bool = False) -> Tuple[bool, str]:
        """
        Detecta breakout:
        - Precio > máximo últimas 15 velas + 0.15%
        - Volumen vela actual > 3x promedio
        - VWAP slope positivo
        - Precio > VWAP
        """
        lookback = 15

        if len(bars) < lookback + 10:
            return False, "Insufficient bars for breakout detection"

        recent_bars = bars[-lookback:]
        current_bar = bars[-1]

        # 1. Precio > máximo reciente + buffer (más flexible en vigilante)
        recent_high = max([bar.high for bar in recent_bars[:-1]])  # Exclude current bar
        breakout_buffer_pct = self.breakout_buffer if not surveillance_mode else self.breakout_buffer * 2  # Buffer doble en vigilante
        breakout_level = recent_high * (1 + breakout_buffer_pct)

        if current_price < breakout_level:
            return False, f"Price ${current_price:.2f} < breakout ${breakout_level:.2f}"

        # 2. Volumen breakout (más flexible en vigilante)
        avg_volume = sum([bar.volume for bar in recent_bars[:-1]]) / (len(recent_bars) - 1)
        volume_ratio = current_bar.volume / avg_volume if avg_volume > 0 else 0

        min_volume_mult = 2.0 if surveillance_mode else self.breakout_volume_mult  # 2x en vigilante vs 3x normal
        if volume_ratio < min_volume_mult:
            return False, f"Volume {volume_ratio:.1f}x < {min_volume_mult}x"

        # 3. VWAP slope positivo
        vwap_current = self._calculate_vwap(bars[-5:])
        vwap_previous = self._calculate_vwap(bars[-10:-5])

        vwap_slope = (vwap_current - vwap_previous) / vwap_previous if vwap_previous > 0 else 0

        if vwap_slope < self.vwap_slope_min:
            return False, f"VWAP slope {vwap_slope*100:.3f}% < {self.vwap_slope_min*100:.3f}%"

        # 4. Precio > VWAP
        if current_price < vwap_current:
            return False, f"Price ${current_price:.2f} < VWAP ${vwap_current:.2f}"

        self.logger.info(
            f"🚀 Breakout confirmed: Price=${current_price:.2f} > ${breakout_level:.2f}, "
            f"Vol={volume_ratio:.1f}x, VWAP slope={vwap_slope*100:.2f}%"
        )

        return True, "Breakout confirmed"

    def _calculate_vwap(self, bars: List) -> float:
        """Calcula VWAP para un conjunto de barras"""
        if not bars:
            return 0.0

        total_volume = 0
        total_vwap = 0

        for bar in bars:
            typical_price = (bar.high + bar.low + bar.close) / 3
            total_vwap += typical_price * bar.volume
            total_volume += bar.volume

        return total_vwap / total_volume if total_volume > 0 else 0.0

    def _calculate_pattern_completion(
        self,
        quality_score: float,
        absorption_events: List[AbsorptionEvent],
        in_accumulation: bool,
        is_breaking_out: bool
    ) -> float:
        """
        Calcula el porcentaje de completitud del patrón

        Componentes:
        - Quality score del scanner: 0-40%
        - Número de absorption events: 0-30%
        - Zona de acumulación: 0-15%
        - Breakout confirmado: 0-15%
        """
        completion = 0.0

        # 1. Quality score (0-40%)
        quality_pct = min(quality_score, 100) / 100
        completion += quality_pct * 40

        # 2. Absorption events (0-30%)
        # 2 events = 20%, 3+ events = 30%
        num_events = len(absorption_events)
        if num_events >= 3:
            completion += 30
        elif num_events == 2:
            completion += 20

        # 3. Zona de acumulación (15%)
        if in_accumulation:
            completion += 15

        # 4. Breakout (15%)
        if is_breaking_out:
            completion += 15

        return min(completion, 100)

    def _determine_trading_horizon(self, signal_data: Dict) -> Tuple[TradingHorizon, float]:
        """
        Determina horizonte temporal para Volume Absorption

        SIEMPRE usa INTRADAY para asegurar TP mínimo de 10%
        (base_tp_pct = 10% para INTRADAY en quality_based_targets.py)

        Para smallcaps, necesitamos objetivos realistas:
        - TP base: 10% (no 5% como SCALP)
        - Hold time: 2-6 horas (no 30min)
        - Esto permite capturar movimientos institucionales completos
        """
        # FORZAR INTRADAY para TP mínimo 10%
        return TradingHorizon.INTRADAY, 4.0  # 4 horas hold time esperado

    def calculate_position_size(self, symbol: str, opportunity: Dict) -> int:
        """
        Calcula el tamaño de posición basado en riesgo del 1.5%

        Hereda de BaseWorkerLogic pero puede ajustarse si es necesario
        """
        return super().calculate_position_size(symbol, opportunity)

    async def should_exit(
        self,
        symbol: str,
        position: Dict,
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir usando WorkerStopManager para manejo de exits
        
        CRITICAL FIX: Ahora evalúa exit conditions usando stop_manager.check_exit()
        
        Args:
            symbol: Símbolo de la posición
            position: Datos de la posición
            current_price: Precio actual

        Returns:
            Tuple[bool, str]: (should_exit, reason)
        """
        try:
            entry_price = position.get('entry_price', 0)
            if entry_price == 0:
                self.logger.warning(f"⚠️ {symbol}: Invalid entry price in position data")
                return False, "Invalid entry price"

            # Get market data for FOMO detection (similar a daily_plays)
            market_data = None
            try:
                from ib_insync import Stock
                contract = Stock(symbol, 'SMART', 'USD')
                bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime='',
                    durationStr='300 S',  # 5 minutes
                    barSizeSetting='1 min',
                    whatToShow='TRADES',
                    useRTH=True
                )
                if bars:
                    market_data = {
                        'bars': bars,
                        'symbol': symbol,
                        'current_price': current_price
                    }
            except Exception as e:
                self.logger.debug(f"Could not get market data for FOMO detection: {e}")

            # Prepare position metadata for EOD check
            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 0)
            }

            # CRITICAL FIX: Use centralized stop manager to check exit conditions
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=market_data,
                position_metadata=position_metadata
            )

            self.logger.debug(f"📊 {symbol}: stop_manager.check_exit() = {should_exit}, reason = '{reason}'")
            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating exit for {symbol}: {e}")
            # In case of error, unregister and exit for safety
            self.stop_manager.unregister_position(symbol)
            return True, "ERROR_EXIT"

    def _check_surveillance_criteria(self, opportunity: Dict, bars: List) -> bool:
        """
        Verifica si un ticker cumple criterios para modo vigilante:
        - Volumen actual > 1.5x promedio (configurable)
        - Precio dentro del rango de smallcaps
        - No requiere pasar filtros del scanner
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        current_price = opportunity.get('current_price', 0)

        # Verificar precio en rango de smallcaps
        if current_price < self.surveillance_min_price or current_price > self.surveillance_max_price:
            return False

        # Verificar volumen inusual
        if len(bars) >= 20:
            avg_volume = sum(bar.volume for bar in bars[-20:]) / 20
            current_volume = bars[-1].volume if bars else 0
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

            if volume_ratio >= self.surveillance_volume_threshold:
                self.logger.info(f"👁️ {symbol}: Surveillance triggered - Volume {volume_ratio:.1f}x > {self.surveillance_volume_threshold}x threshold")
                return True

        return False

    async def run_surveillance_mode(self):
        """
        Modo vigilante: Monitorea tickers con volumen inusual independientemente del scanner
        Se ejecuta periódicamente para detectar movimientos que el scanner podría perder
        """
        if not self.surveillance_mode_enabled:
            return

        current_time = datetime.now()
        time_since_last_check = (current_time - self.last_surveillance_check).total_seconds()

        if time_since_last_check < self.surveillance_check_interval:
            return  # Aún no es tiempo de revisar

        self.last_surveillance_check = current_time
        self.logger.info("👁️ Running surveillance mode check...")

        try:
            # Aquí iría la lógica para obtener tickers con volumen inusual
            # Por ahora, es un placeholder que se integraría con IBKR scanner
            # para obtener tickers con movimientos de volumen altos

            surveillance_candidates = await self._get_high_volume_candidates()

            for symbol in surveillance_candidates:
                if symbol not in self.surveillance_candidates:
                    self.logger.info(f"👁️ New surveillance candidate: {symbol}")
                    self.surveillance_candidates.add(symbol)

                    # Crear oportunidad "sintética" para análisis
                    opportunity = {
                        'symbol': symbol,
                        'current_price': 0,  # Se obtendría de IBKR
                        'volume_ratio': 0,   # Se calcularía
                        'gap_percentage': 0,
                        'quality_score': 50.0,  # Score base para vigilante
                        'catalyst_type': 'SURVEILLANCE',
                        'scan_timestamp': datetime.now().isoformat()
                    }

                    # Intentar analizar con criterios de vigilante
                    should_enter = await self.should_enter(opportunity)
                    if should_enter:
                        self.logger.info(f"🚨 {symbol}: SURVEILLANCE ALERT - Absorption pattern detected!")

        except Exception as e:
            self.logger.error(f"❌ Error in surveillance mode: {e}")

    async def _get_high_volume_candidates(self) -> List[str]:
        """
        Obtiene tickers con volumen inusual desde IBKR
        Placeholder - se implementaría con IBKR scanner calls
        """
        # TODO: Integrar con IBKR scanner para obtener tickers con alto volumen
        # Por ahora retorna lista vacía
        return []

    async def _execute_entry(self, opportunity: Dict) -> bool:
        """
        Sobrescribe el método base para registro DUAL: stop_manager + unified manager
        
        FIX CRÍTICO: Registra posición en WorkerStopManager para monitoring de exits
        Y en UnifiedPositionManager para prevenir duplicates
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # USAR LÓGICA BASE para todo el proceso de entrada
            entry_success = await super()._execute_entry(opportunity)
            
            if not entry_success:
                return False

            # 🛡️ CRITICAL FIX #1: Registrar con WorkerStopManager para monitoring de exits
            try:
                self.stop_manager.register_position(symbol, datetime.now())
                self.logger.info(f"📝 {symbol}: Registered with WorkerStopManager for exit monitoring")
            except Exception as e:
                self.logger.error(f"❌ {symbol}: Failed to register with WorkerStopManager: {e}")
                # Continue anyway, don't fail the entry
            
            # 🛡️ CRITICAL FIX #2: Registrar con UnifiedPositionManager para prevenir duplicates
            try:
                from core.service_locator import get_unified_position_manager
                unified_manager = await get_unified_position_manager()
                
                if unified_manager:
                    # Obtener datos de la posición
                    entry_price = opportunity.get('entry_price', 0.0)
                    quantity = opportunity.get('position_size', 0)
                    
                    if entry_price > 0 and quantity > 0:
                        position_value = entry_price * quantity
                        strategy_type = 'day'  # volume_absorption es day trading
                        
                        position_data = {
                            'entry_price': entry_price,
                            'quantity': quantity,
                            'position_value': position_value,
                            'strategy': self.worker_name,
                            'strategy_type': strategy_type,
                            'opened_at': datetime.now().isoformat()
                        }
                        
                        success = unified_manager.register_position(
                            symbol=symbol,
                            strategy_type=strategy_type,
                            position_data=position_data
                        )
                        
                        if success:
                            self.logger.info(f"💼 {symbol}: Registered with UnifiedPositionManager")
                        else:
                            self.logger.warning(f"⚠️ {symbol}: Failed to register with UnifiedPositionManager")
                
            except Exception as e:
                self.logger.warning(f"⚠️ {symbol}: Error with UnifiedPositionManager: {e}")
                # Don't fail the entry for this

            return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in _execute_entry: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
