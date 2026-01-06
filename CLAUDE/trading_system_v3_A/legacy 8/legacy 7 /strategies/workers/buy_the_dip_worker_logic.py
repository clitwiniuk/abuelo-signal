"""
Buy The Dip Worker Logic

Edge: Compra pullbacks/dips en tendencia alcista confirmada
Espera pacientemente al mejor punto de entrada antes de comprar

CONCEPTO CLAVE:
- NO compra en momentum fuerte (demasiado tarde)
- ESPERA a que haga un retroceso (dip)
- PREDICE el tamaño del dip usando volatilidad histórica
- ENTRA cuando el dip alcanza el nivel esperado + confirmación de rebote

TODOS LOS PARÁMETROS SON CONFIGURABLES EN CONFIG.INI
"""

import logging
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradingHorizon


@dataclass
class DipAnalysis:
    """Análisis del dip esperado"""
    symbol: str
    expected_dip_pct: float  # Tamaño esperado del dip (%)
    dip_min: float           # Dip mínimo para considerar (%)
    dip_max: float           # Dip máximo antes de invalidar (%)
    vwap: float              # VWAP actual
    vwap_slope: float        # Pendiente del VWAP
    atr_pct: float           # ATR como % del precio
    recent_high: float       # High reciente desde el cual retrocederá
    volatility_regime: str   # LOW, MEDIUM, HIGH


class BuyTheDipWorkerLogic(BaseWorkerLogic):
    """
    Worker que compra dips en tendencias alcistas confirmadas

    TODOS LOS PARÁMETROS SON CONFIGURABLES EN CONFIG.INI [BUY_THE_DIP_WORKER]

    Lógica de Entrada:

    1. SEÑAL DEL SCANNER (opportunity received)
       - Symbol con catalyst o momentum
       - Quality score inicial >= min_quality_score (config)

    2. ANÁLISIS DEL CONTEXTO ALCISTA:
       - Precio > VWAP + min_price_above_vwap_pct% (config)
       - VWAP con pendiente positiva >= min_vwap_slope (config)
       - No en máximo parabólico (RSI < max_rsi_entry - config)

    3. PREDICCIÓN DEL TAMAÑO DEL DIP (basado en volatilidad ATR):
       - VOLATILIDAD BAJA (ATR < low_vol_atr_threshold):
         Dip pequeño low_vol_dip_min - low_vol_dip_max%
       - VOLATILIDAD MEDIA (ATR < med_vol_atr_threshold):
         Dip medio med_vol_dip_min - med_vol_dip_max%
       - VOLATILIDAD ALTA (ATR > med_vol_atr_threshold):
         Dip grande high_vol_dip_min - high_vol_dip_max%

    4. ESPERAR EL DIP:
       - Trackear el high reciente
       - Calcular retroceso actual desde high
       - NO entrar hasta que alcance el dip esperado

    5. CONFIRMACIÓN DE REBOTE:
       - min_bounce_bars barras alcistas consecutivas (config)
       - Volumen aumenta >= min_bounce_volume_ratio (config)
       - Precio se mantiene > VWAP

    6. ENTRADA:
       - Comprar cuando dip alcanzado + rebote confirmado
       - Stop loss: debajo del low del dip
       - Take profit: según config (WorkerStopManager)

    Criterios de Salida (WorkerStopManager - configurable):
    - Trailing stop: trailing_activation%, trailing_distance%
    - Take profit: take_profit_pct%
    - Stop loss: stop_loss_pct%
    - Time-based: max_position_hours
    - END_OF_DAY: end_of_day_hour
    """

    def __init__(self, broker, risk_manager=None, config=None, execution_engine=None):
        super().__init__(
            worker_name='buy_the_dip',
            broker=broker,
            config=config
        )

        # Tracking de dips en progreso
        self.pending_dips: Dict[str, DipAnalysis] = {}  # Symbols esperando dip
        self.symbol_highs: Dict[str, float] = {}         # Recent high por symbol
        self.entry_attempts: Dict[str, int] = {}         # Intentos de entrada por symbol

        # Anti-overtrading
        self.traded_symbols_today = set()
        self._last_reset_date = None

        # ===== READ ALL PARAMS FROM CONFIG.INI =====
        # Helper for config reading (MockConfig or verify dict-like)
        def get_cfg(section, key, default, type_func=float):
            if not config:
                return default
            try:
                # Try standard configparser methods
                method_name = f'get{type_func.__name__}' if type_func != str else 'get'
                if hasattr(config, method_name):
                    method = getattr(config, method_name)
                    # Handle configparser signature (section, option, fallback)
                    return method(section, key, fallback=default)
                # Try dict-like access
                elif hasattr(config, 'get'):
                    val = config.get(section, key)
                    return type_func(val) if val is not None else default
            except Exception:
                return default
            return default

        section = 'BUY_THE_DIP_WORKER'

        # ===== FILTROS BÁSICOS =====
        self.min_price = get_cfg(section, 'min_price', 1.0)
        self.max_price = get_cfg(section, 'max_price', 15.0)
        self.min_quality_score = get_cfg(section, 'min_quality_score', 40.0)

        # ===== CONFIRMACIÓN DE TENDENCIA ALCISTA =====
        self.min_price_above_vwap_pct = get_cfg(section, 'min_price_above_vwap_pct', 1.0)
        self.min_vwap_slope = get_cfg(section, 'min_vwap_slope', 0.0001)
        self.max_rsi_entry = get_cfg(section, 'max_rsi_entry', 75.0)

        # ===== DUAL MODE: BUY THE DIP vs BUY AND HOLD =====
        self.strong_trend_threshold_pct = get_cfg(section, 'strong_trend_threshold_pct', 2.0)

        # ===== PREDICCIÓN DE DIP (volatilidad-based) =====
        # Low volatility (ATR < threshold)
        self.low_vol_atr_threshold = get_cfg(section, 'low_vol_atr_threshold', 3.0)
        self.low_vol_dip_min = get_cfg(section, 'low_vol_dip_min', 1.0)
        self.low_vol_dip_max = get_cfg(section, 'low_vol_dip_max', 3.0)

        # Medium volatility
        self.med_vol_atr_threshold = get_cfg(section, 'med_vol_atr_threshold', 6.0)
        self.med_vol_dip_min = get_cfg(section, 'med_vol_dip_min', 3.0)
        self.med_vol_dip_max = get_cfg(section, 'med_vol_dip_max', 5.0)

        # High volatility
        self.high_vol_dip_min = get_cfg(section, 'high_vol_dip_min', 5.0)
        self.high_vol_dip_max = get_cfg(section, 'high_vol_dip_max', 8.0)

        # ===== CONFIRMACIÓN DE REBOTE =====
        self.min_bounce_bars = get_cfg(section, 'min_bounce_bars', 2, int)
        self.min_bounce_volume_ratio = get_cfg(section, 'min_bounce_volume_ratio', 1.2)

        # ===== LÍMITES DE ESPERA =====
        self.max_wait_minutes = get_cfg(section, 'max_wait_minutes', 60, int)
        self.max_entry_attempts = get_cfg(section, 'max_entry_attempts', 2, int)

        # ===== DYNAMIC TAKE PROFIT (Hybrid: Resistance + ATR) =====
        self.low_vol_tp_pct = get_cfg(section, 'low_vol_tp_pct', 8.0)
        self.med_vol_tp_pct = get_cfg(section, 'med_vol_tp_pct', 12.0)
        self.high_vol_tp_pct = get_cfg(section, 'high_vol_tp_pct', 18.0)
        self.resistance_lookback_bars = get_cfg(section, 'resistance_lookback_bars', 50, int)
        self.resistance_margin_pct = get_cfg(section, 'resistance_margin_pct', 1.0)
        self.min_tp_pct = get_cfg(section, 'min_tp_pct', 6.0)
        self.max_tp_pct = get_cfg(section, 'max_tp_pct', 25.0)

        # ===== RISK MANAGEMENT (WorkerStopManager) =====
        # Use centralized stop manager
        from .worker_stop_manager import create_worker_stop_manager, WorkerStopManager, WorkerStopConfig
        if config:
            self.stop_manager = create_worker_stop_manager(config, section)
        else:
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=3.0,
                take_profit_pct=12.0,
                trailing_activation=8.0,
                trailing_distance=3.0,
                max_position_hours=2.0
            ))

        self.logger.info(f"🎯 Buy The Dip Worker configured:")
        self.logger.info(f"   Price Range: ${self.min_price:.2f} - ${self.max_price:.2f}")
        self.logger.info(f"   Min above VWAP: {self.min_price_above_vwap_pct}%")
        self.logger.info(f"   Dip Prediction: Low Vol {self.low_vol_dip_min}-{self.low_vol_dip_max}%, Med Vol {self.med_vol_dip_min}-{self.med_vol_dip_max}%, High Vol {self.high_vol_dip_min}-{self.high_vol_dip_max}%")
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    async def should_enter(self, opportunity: Dict) -> bool:
        """
        Determina si debe entrar AHORA en una posición

        Flujo:
        1. Check initial filters (price, quality, anti-overtrading)
        2. Check uptrend confirmation (price > VWAP, slope positive)
        3. Analyze expected dip size (based on volatility)
        4. Check if dip is happening NOW
        5. Wait for bounce confirmation
        6. Enter when all conditions met
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # ====
            # STEP 0: Anti-overtrading & Initial Checks
            # ====
            self._reset_daily_tracking()

            if symbol in self.traded_symbols_today:
                self.logger.info(f"⚪ {symbol}: Already traded today (anti-overtrading)")
                return False

            # Check entry attempts
            if self.entry_attempts.get(symbol, 0) >= self.max_entry_attempts:
                self.logger.info(f"⚪ {symbol}: Max entry attempts reached ({self.entry_attempts[symbol]}/{self.max_entry_attempts})")
                return False

            # =================
            # FILTER: TIME CHECK
            # =================
            is_valid_time, current_decimal_time = self.is_within_entry_hours(symbol, opportunity.get('timestamp'))
            if not is_valid_time:
                 self.logger.debug(f"⚪ {symbol}: Outside trading hours ({current_decimal_time:.2f})")
                 return False

            # =================
            # FILTER: POSITION CHECK (Broker)
            # =================
            # Check if we already hold this symbol in any capacity
            positions = await self.broker.get_positions()
            if any(p['symbol'] == symbol for p in positions):
                self.logger.warning(f"⚪ {symbol}: BLOCKED - Position already exists.")
                return False

            # ====
            # STEP 1: Get bars
            # ====
            bars = self.get_bars_from_opportunity(opportunity)

            if not bars or len(bars) < 30:
                self.logger.info(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0} < 30)")
                return False

            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)

            # ====
            # STEP 2: Basic filters
            # ====
            if not (self.min_price <= current_price <= self.max_price):
                self.logger.info(f"⚪ {symbol}: Price ${current_price:.2f} outside range ${self.min_price}-${self.max_price}")
                return False

            if quality_score < self.min_quality_score:
                self.logger.info(f"⚪ {symbol}: Quality score {quality_score:.1f} < {self.min_quality_score:.1f}")
                return False

            # ====
            # STEP 3: Calculate VWAP and check uptrend
            # ====
            vwap_result = self._calculate_vwap_and_slope(bars)
            if not vwap_result:
                self.logger.info(f"⚪ {symbol}: Could not calculate VWAP")
                return False

            vwap, vwap_slope = vwap_result

            # Check price > VWAP + margin
            if vwap > 0:
                price_above_vwap_pct = ((current_price - vwap) / vwap * 100)
                if price_above_vwap_pct < self.min_price_above_vwap_pct:
                    self.logger.info(f"⚪ {symbol}: Price only {price_above_vwap_pct:.2f}% above VWAP (need {self.min_price_above_vwap_pct}%)")
                    return False
            else:
                price_above_vwap_pct = 0.0

            # Check VWAP slope (positive trend)
            if vwap_slope < self.min_vwap_slope:
                self.logger.info(f"⚪ {symbol}: VWAP slope {vwap_slope:.6f} not positive enough")
                return False

            self.logger.info(f"✅ {symbol}: Uptrend confirmed - Price {price_above_vwap_pct:.1f}% above VWAP, Slope {vwap_slope:.6f}")

            # ====
            # STEP 4: Check RSI (not parabolic)
            # ====
            rsi = self._calculate_rsi(bars, period=14)
            if rsi and rsi > self.max_rsi_entry:
                self.logger.info(f"⚪ {symbol}: RSI {rsi:.1f} too high (parabolic, wait for cooldown)")
                return False

            # ====
            # STEP 5: Predict dip size based on volatility
            # ====
            dip_analysis = self._analyze_expected_dip(symbol, bars, current_price, vwap, vwap_slope)
            if not dip_analysis:
                self.logger.info(f"⚪ {symbol}: Could not analyze expected dip")
                return False

            self.logger.info(
                f"📊 {symbol}: Dip Analysis - "
                f"Expected: {dip_analysis.expected_dip_pct:.1f}% "
                f"(Range: {dip_analysis.dip_min:.1f}%-{dip_analysis.dip_max:.1f}%), "
                f"Volatility: {dip_analysis.volatility_regime}, ATR: {dip_analysis.atr_pct:.2f}%"
            )

            # ====
            # STEP 5.5: EARLY RESISTANCE VALIDATION (Technical)
            # ====
            # Calculate distance to recent high (local resistance)
            # We use local highs as resistance proxy instead of metadata
            recent_high = max([b.high for b in bars[-50:]]) if len(bars) >= 50 else current_price
            
            if recent_high > current_price:
                distance_to_resistance = ((recent_high - current_price) / current_price) * 100
            else:
                distance_to_resistance = 100.0 # No nearby resistance detected
                
            # If significant resistance is extremely close (< 1%), be cautious
            # But normally for 'buy the dip', we are buying pullback, so resistance is the previous high
            # We want to ensure there is room to run back to that high.
            
            # Simple R:R check: Reward (to recent high) vs Risk (stop below dip)
            estimated_reward = distance_to_resistance
            estimated_risk = dip_analysis.atr_pct * 1.5 # Proxy for stop risk
            
            if estimated_risk > 0:
                estimated_rr = estimated_reward / estimated_risk
                if estimated_rr < 1.0 and distance_to_resistance < 2.0:
                     # Only reject if resistance is VERY close and R:R is bad
                     self.logger.info(f"⚪ {symbol}: Resistance too close ({distance_to_resistance:.1f}%) for estimated risk ({estimated_risk:.1f}%)")
                     return False

            # ====
            # STEP 6: DUAL MODE - Strong Trend vs Dip Buying
            # ====
            # Si precio está MUY por encima del VWAP -> TENDENCIA FUERTE -> Entrar directamente
            # Si precio está CERCA del VWAP -> Esperar dip para mejor entrada

            if price_above_vwap_pct >= self.strong_trend_threshold_pct:
                # MODO: BUY AND HOLD (Tendencia fuerte)
                self.logger.info(
                    f"🚀 {symbol}: STRONG TREND MODE - Price {price_above_vwap_pct:.1f}% above VWAP "
                    f"(threshold: {self.strong_trend_threshold_pct}%) -> Entering directly without waiting for dip"
                )

                # Track attempt (but don't mark as traded yet - that happens after successful execution)
                self.entry_attempts[symbol] = self.entry_attempts.get(symbol, 0) + 1

                return True

            else:
                # MODO: BUY THE DIP (Tendencia débil/moderada)
                self.logger.info(
                    f"📊 {symbol}: DIP BUYING MODE - Price {price_above_vwap_pct:.1f}% above VWAP "
                    f"(below threshold: {self.strong_trend_threshold_pct}%) -> Waiting for dip"
                )

                # Track this symbol for dip waiting
                if symbol not in self.pending_dips:
                    self.pending_dips[symbol] = dip_analysis
                    self.symbol_highs[symbol] = dip_analysis.recent_high
                    self.logger.info(f"👀 {symbol}: Added to watchlist, waiting for dip from ${dip_analysis.recent_high:.2f}")

                # Check if dip is happening NOW
                is_in_dip, dip_pct, bounce_confirmed = self._check_dip_and_bounce(symbol, bars, dip_analysis)

                if not is_in_dip:
                    self.logger.info(f"⏳ {symbol}: Not in dip yet (current: {dip_pct:.2f}%, need: {dip_analysis.dip_min:.1f}%)")
                    return False

                # Wait for bounce confirmation
                if not bounce_confirmed:
                    self.logger.info(f"⏳ {symbol}: In dip ({dip_pct:.2f}%) but waiting for bounce confirmation")
                    return False

                # DIP ENTRY APPROVED
                self.logger.info(
                    f"✅ {symbol}: BUY THE DIP ENTRY APPROVED - "
                    f"Dip: {dip_pct:.2f}% (Expected: {dip_analysis.expected_dip_pct:.1f}%), "
                    f"Bounce confirmed!"
                )

                # Track attempt (but don't mark as traded yet - that happens after successful execution)
                self.entry_attempts[symbol] = self.entry_attempts.get(symbol, 0) + 1

                # Remove from pending
                if symbol in self.pending_dips:
                    del self.pending_dips[symbol]

                return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in should_enter: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _calculate_vwap_and_slope(self, bars: List) -> Optional[Tuple[float, float]]:
        """Calculate VWAP and its slope (trend direction)"""
        try:
            if len(bars) < 10:
                return None

            # Calculate VWAP for last 20 bars
            recent_bars = bars[-20:] if len(bars) >= 20 else bars

            total_pv = sum(bar.close * bar.volume for bar in recent_bars)
            total_volume = sum(bar.volume for bar in recent_bars)

            if total_volume == 0:
                return None

            vwap = total_pv / total_volume

            # Calculate slope using last 10 bars
            if len(bars) >= 10:
                # VWAP for bars[-10:-5] vs bars[-5:]
                mid_bars = bars[-10:-5]
                recent_bars = bars[-5:]

                vwap_mid = sum(b.close * b.volume for b in mid_bars) / sum(b.volume for b in mid_bars) if sum(b.volume for b in mid_bars) > 0 else vwap
                vwap_recent = sum(b.close * b.volume for b in recent_bars) / sum(b.volume for b in recent_bars) if sum(b.volume for b in recent_bars) > 0 else vwap

                vwap_slope = (vwap_recent - vwap_mid) / vwap_mid if vwap_mid > 0 else 0
            else:
                vwap_slope = 0

            return (vwap, vwap_slope)

        except Exception as e:
            self.logger.warning(f"Error calculating VWAP: {e}")
            return None

    def _analyze_expected_dip(
        self, symbol: str, bars: List, current_price: float,
        vwap: float, vwap_slope: float
    ) -> Optional[DipAnalysis]:
        """
        Predice el tamaño del dip esperado basado en volatilidad

        Usa ATR (Average True Range) para estimar volatilidad:
        - ATR < low_vol_atr_threshold: Volatilidad BAJA
        - ATR < med_vol_atr_threshold: Volatilidad MEDIA
        - ATR >= med_vol_atr_threshold: Volatilidad ALTA
        """
        try:
            # Calculate ATR (Average True Range) for volatility
            atr_pct = self._calculate_atr_percent(bars, period=14)
            if not atr_pct:
                return None

            # Determine volatility regime (todas las thresholds vienen de config)
            if atr_pct < self.low_vol_atr_threshold:
                volatility_regime = "LOW"
                dip_min = self.low_vol_dip_min
                dip_max = self.low_vol_dip_max
                expected_dip = (dip_min + dip_max) / 2
            elif atr_pct < self.med_vol_atr_threshold:
                volatility_regime = "MEDIUM"
                dip_min = self.med_vol_dip_min
                dip_max = self.med_vol_dip_max
                expected_dip = (dip_min + dip_max) / 2
            else:
                volatility_regime = "HIGH"
                dip_min = self.high_vol_dip_min
                dip_max = self.high_vol_dip_max
                expected_dip = (dip_min + dip_max) / 2

            # Find recent high (highest high in last 10 bars)
            recent_high = max(bar.high for bar in bars[-10:]) if len(bars) >= 10 else current_price

            return DipAnalysis(
                symbol=symbol,
                expected_dip_pct=expected_dip,
                dip_min=dip_min,
                dip_max=dip_max,
                vwap=vwap,
                vwap_slope=vwap_slope,
                atr_pct=atr_pct,
                recent_high=recent_high,
                volatility_regime=volatility_regime
            )

        except Exception as e:
            self.logger.warning(f"{symbol}: Error analyzing expected dip: {e}")
            return None

    def _calculate_atr_percent(self, bars: List, period: int = 14) -> Optional[float]:
        """Calculate ATR as percentage of price"""
        try:
            if len(bars) < period + 1:
                return None

            true_ranges = []
            for i in range(len(bars) - period, len(bars)):
                high = bars[i].high
                low = bars[i].low
                prev_close = bars[i-1].close if i > 0 else bars[i].open

                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)

            atr = sum(true_ranges) / len(true_ranges)
            current_price = bars[-1].close

            atr_pct = (atr / current_price * 100) if current_price > 0 else 0

            return atr_pct

        except Exception as e:
            self.logger.warning(f"Error calculating ATR: {e}")
            return None

    def _check_dip_and_bounce(
        self, symbol: str, bars: List, dip_analysis: DipAnalysis
    ) -> Tuple[bool, float, bool]:
        """
        Check if symbol is currently in a dip and if bounce is confirmed

        Returns:
            (is_in_dip, dip_pct, bounce_confirmed)
        """
        try:
            current_price = bars[-1].close
            recent_high = self.symbol_highs.get(symbol, dip_analysis.recent_high)

            # Update recent high if price made new high
            if current_price > recent_high:
                self.symbol_highs[symbol] = current_price
                self.logger.debug(f"{symbol}: New high ${current_price:.2f}")
                return (False, 0, False)  # No dip yet if making new highs

            # Calculate current dip %
            dip_pct = ((recent_high - current_price) / recent_high * 100)

            # Check if dip is within expected range
            is_in_dip = dip_analysis.dip_min <= dip_pct <= dip_analysis.dip_max

            if not is_in_dip:
                if dip_pct > dip_analysis.dip_max:
                    self.logger.info(f"⚠️ {symbol}: Dip too large ({dip_pct:.2f}% > {dip_analysis.dip_max:.1f}%), invalidated")
                    # Remove from pending if dip too large
                    if symbol in self.pending_dips:
                        del self.pending_dips[symbol]
                return (False, dip_pct, False)

            # Check bounce confirmation (last N bars are bullish)
            bounce_confirmed = False
            if len(bars) >= self.min_bounce_bars:
                recent_bars = bars[-self.min_bounce_bars:]

                # Check if bars are bullish (close > open)
                bullish_bars = sum(1 for bar in recent_bars if bar.close > bar.open)

                # Check volume increasing
                avg_volume = sum(bar.volume for bar in bars[-10:-self.min_bounce_bars]) / (10 - self.min_bounce_bars) if len(bars) >= 10 else 1
                recent_volume = sum(bar.volume for bar in recent_bars) / self.min_bounce_bars
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1

                bounce_confirmed = (
                    bullish_bars >= self.min_bounce_bars and  # All bars bullish
                    volume_ratio >= self.min_bounce_volume_ratio and  # Volume increasing
                    current_price > dip_analysis.vwap  # Still above VWAP
                )

            return (is_in_dip, dip_pct, bounce_confirmed)

        except Exception as e:
            self.logger.warning(f"{symbol}: Error checking dip and bounce: {e}")
            return (False, 0, False)

    def _calculate_rsi(self, bars: List, period: int = 14) -> Optional[float]:
        """Calculate RSI"""
        try:
            if len(bars) < period + 1:
                return None

            closes = [bar.close for bar in bars[-period-1:]]

            gains = []
            losses = []

            for i in range(1, len(closes)):
                change = closes[i] - closes[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

            avg_gain = sum(gains) / len(gains)
            avg_loss = sum(losses) / len(losses)

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi

        except Exception as e:
            self.logger.warning(f"Error calculating RSI: {e}")
            return None

    def _reset_daily_tracking(self):
        """Reset daily tracking at start of new day"""
        from datetime import date
        
        # Use replay date if available (for testing), otherwise use system date
        today = self._replay_date if self._replay_date else date.today()

        if self._last_reset_date != today:
            self.traded_symbols_today.clear()
            self.pending_dips.clear()
            self.symbol_highs.clear()
            self.entry_attempts.clear()
            self._last_reset_date = today
            self.logger.info(f"🔄 Daily tracking reset for {today}")

    def _calculate_dynamic_take_profit(
        self,
        symbol: str,
        entry_price: float,
        atr_pct: float,
        bars: List[Dict[str, Any]]
    ) -> float:
        """
        Calcula TP dinámico basado en resistencias técnicas + volatilidad (ATR)

        Lógica Híbrida:
        1. Calcula TP base según ATR (volatilidad)
        2. Busca resistencia próxima en las últimas N barras
        3. Si hay resistencia ANTES del TP base:
           - TP = resistencia - margen de seguridad
        4. Si NO hay resistencia:
           - TP = TP base (según volatilidad)
        5. Aplica límites min/max

        Args:
            symbol: Símbolo
            entry_price: Precio de entrada
            atr_pct: ATR en porcentaje
            bars: Lista de barras históricas para análisis de resistencias

        Returns:
            Take profit dinámico en porcentaje
        """
        try:
            # PASO 1: TP base según volatilidad (ATR)
            if atr_pct < self.low_vol_atr_threshold:
                tp_base = self.low_vol_tp_pct
                volatility_regime = "LOW"
            elif atr_pct < self.med_vol_atr_threshold:
                tp_base = self.med_vol_tp_pct
                volatility_regime = "MEDIUM"
            else:
                tp_base = self.high_vol_tp_pct
                volatility_regime = "HIGH"

            # PASO 2: Buscar resistencias próximas
            resistance_price = None
            if bars and len(bars) >= 10:
                # Tomar últimas N barras
                lookback_bars = bars[-self.resistance_lookback_bars:]

                # Encontrar pivots (máximos locales)
                highs = [bar.get('high', 0) for bar in lookback_bars if bar.get('high')]

                if len(highs) >= 5:
                    # Resistencia = promedio de los 3 máximos más altos
                    # (más robusto que usar un solo máximo)
                    sorted_highs = sorted(highs, reverse=True)
                    top_3_highs = sorted_highs[:3]
                    resistance_price = sum(top_3_highs) / len(top_3_highs)

            # PASO 3: Calcular TP target price
            tp_target_price = entry_price * (1 + tp_base / 100)

            # PASO 4: Ajustar por resistencia si existe
            if resistance_price and resistance_price > entry_price:
                # Resistencia está por encima de entrada
                resistance_pct = ((resistance_price - entry_price) / entry_price) * 100

                # Si resistencia está ANTES del TP base -> ajustar TP
                if resistance_pct < tp_base:
                    # TP = resistencia - margen de seguridad
                    adjusted_resistance = resistance_price * (1 - self.resistance_margin_pct / 100)
                    tp_final_pct = ((adjusted_resistance - entry_price) / entry_price) * 100

                    self.logger.info(
                        f"📊 {symbol}: TP ajustado por resistencia - "
                        f"Base: {tp_base:.1f}% -> Resistance: {resistance_pct:.1f}% -> "
                        f"TP Final: {tp_final_pct:.1f}% (margin: {self.resistance_margin_pct}%)"
                    )
                else:
                    # Resistencia está lejos -> usar TP base
                    tp_final_pct = tp_base
                    self.logger.info(
                        f"📊 {symbol}: TP base (resistencia lejana) - "
                        f"ATR: {atr_pct:.1f}% ({volatility_regime}) -> TP: {tp_final_pct:.1f}%"
                    )
            else:
                # No hay resistencia clara -> usar TP base
                tp_final_pct = tp_base
                self.logger.info(
                    f"📊 {symbol}: TP base (sin resistencia) - "
                    f"ATR: {atr_pct:.1f}% ({volatility_regime}) -> TP: {tp_final_pct:.1f}%"
                )

            # PASO 5: Aplicar límites min/max
            tp_final_pct = max(self.min_tp_pct, min(tp_final_pct, self.max_tp_pct))

            return tp_final_pct

        except Exception as e:
            self.logger.warning(f"Error calculating dynamic TP for {symbol}: {e}")
            # Fallback a TP conservador
            return self.min_tp_pct

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir de posición según criterios Buy The Dip

        Delega toda la lógica de salida al WorkerStopManager que maneja:
        - Stop Loss (3%)
        - Take Profit (6%)
        - Trailing Stop (activa al 4%, distance 2%)
        - Break-Even (activa al 3%)
        - Time-based exit (2 horas max)

        Args:
            symbol: Símbolo de la posición
            position: Datos de la posición
            current_price: Precio actual

        Returns:
            (should_exit, reason): Tupla con decisión y motivo
        """
        try:
            entry_price = position.get('entry_price', 0)

            if entry_price == 0:
                self.logger.warning(f"⚠️ {symbol}: Invalid entry price")
                return False, ""

            # Prepare position metadata
            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': 'intraday',
                'expected_hold_hours': 2.0
            }

            # Use centralized stop manager to check exit conditions
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=None,  # No custom market data needed
                position_metadata=position_metadata
            )

            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating exit for {symbol}: {e}")
            # In case of error, unregister and exit for safety
            self.stop_manager.unregister_position(symbol)
            return True, "ERROR_EXIT"

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """
        Override to mark symbol as traded after successful execution
        
        This ensures anti-overtrading tracking happens AFTER trade execution,
        not during should_enter() evaluation.
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        
        # Call parent's _execute_entry
        success = await super()._execute_entry(opportunity)
        
        # Only mark as traded if execution was successful
        if success:
            self.traded_symbols_today.add(symbol)
            self.logger.debug(f"✅ {symbol}: Marked as traded today (anti-overtrading)")
        
        return success

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calculate pattern completion for replay testing
        
        Pattern completion represents how well the current setup matches
        the ideal "buy the dip" scenario:
        
        - 100%: Perfect setup (strong uptrend + ideal entry point)
        - 80-99%: Good setup (uptrend confirmed, waiting for dip or in strong trend)
        - 60-79%: Developing setup (uptrend forming, not ready yet)
        - <60%: Incomplete (missing key criteria)
        
        Returns:
            Pattern completion percentage (0-100)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            
            # Get bars
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 30:
                return 0.0  # Not enough data
            
            current_price = opportunity.get('current_price', 0)
            if current_price == 0:
                return 0.0
            
            completion = 0.0
            
            # STEP 1: VWAP Analysis (40 points)
            vwap_result = self._calculate_vwap_and_slope(bars)
            if vwap_result:
                vwap, vwap_slope = vwap_result
                
                # Price above VWAP (20 points)
                price_above_vwap_pct = ((current_price - vwap) / vwap * 100) if vwap > 0 else 0
                if price_above_vwap_pct >= self.min_price_above_vwap_pct:
                    # Scale: 0.5% = 20pts, 2%+ = full 20pts
                    vwap_points = min(20, (price_above_vwap_pct / 2.0) * 20)
                    completion += vwap_points
                
                # VWAP slope positive (20 points)
                if vwap_slope >= self.min_vwap_slope:
                    # Scale: 0.0001 = 20pts, 0.01+ = full 20pts
                    slope_points = min(20, (vwap_slope / 0.01) * 20)
                    completion += slope_points
            
            # STEP 2: Volatility Analysis (20 points)
            atr_pct = self._calculate_atr_percent(bars, period=14)
            if atr_pct:
                # Ideal ATR is 2-5% (medium volatility)
                # Too low (<1%) or too high (>10%) reduces points
                if 2.0 <= atr_pct <= 5.0:
                    completion += 20  # Perfect volatility
                elif 1.0 <= atr_pct < 2.0 or 5.0 < atr_pct <= 7.0:
                    completion += 15  # Good volatility
                elif atr_pct < 1.0 or atr_pct > 10.0:
                    completion += 5   # Poor volatility
                else:
                    completion += 10  # Acceptable volatility
            
            # STEP 3: RSI Check (20 points)
            rsi = self._calculate_rsi(bars, period=14)
            if rsi:
                # Ideal RSI: 40-70 (not oversold, not overbought)
                if 40 <= rsi <= 70:
                    completion += 20  # Perfect RSI
                elif 30 <= rsi < 40 or 70 < rsi <= 75:
                    completion += 15  # Good RSI
                elif rsi > 75:
                    completion += 5   # Overbought (risky)
                else:
                    completion += 10  # Acceptable
            
            # STEP 4: Strong Trend Bonus (20 points)
            # If price is >2% above VWAP = strong trend = immediate entry
            if vwap_result:
                vwap, _ = vwap_result
                price_above_vwap_pct = ((current_price - vwap) / vwap * 100) if vwap > 0 else 0
                if price_above_vwap_pct >= self.strong_trend_threshold_pct:
                    completion += 20  # Strong trend = pattern complete
            
            # Cap at 100%
            completion = min(100.0, completion)
            
            self.logger.debug(f"📊 {symbol}: Pattern completion = {completion:.1f}%")
            
            return completion
            
        except Exception as e:
            self.logger.warning(f"Error calculating pattern completion for {symbol}: {e}")
            return 0.0


    def get_trading_horizon(self) -> TradingHorizon:
        """Define trading horizon for this worker"""
        return TradingHorizon.INTRADAY
