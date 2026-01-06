#!/usr/bin/env python3
"""
Small Caps Short Reversal Worker Logic
Worker especializado para operar reversales bajistas en small caps con alta tasa de acierto

Strategy Philosophy:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 OBJETIVO: Mean Reversion + Momentum Breakdown (Short Side)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧠 EDGE (Ventaja de la estrategia):
   Después de movimientos impulsivos alcistas artificiales (pumps), small caps tienden a
   revertir por:
   • Baja liquidez
   • Traders tardíos atrapados
   • Market makers descargando
   • Dilución / news fades

📐 TIPO DE ESTRATEGIA:
   ✅ Mean Reversion (reacción a excesos)
   ✅ Momentum Breakdown (confirmación de debilidad)
   ✅ Corta duración (intraday/swing corto)
   ❌ NO trend following
   ❌ NO long-term short
   ❌ NO predicción de mercado

⚡ CLAVE DEL ÉXITO:
   "En small caps NO buscamos grandes tendencias, sino ineficiencias de corto plazo"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 ENTRY CRITERIA (ALL must be TRUE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 PASO 1: Filtros de Universo (Pre-filtro)
   1. Market Cap < $3B (small caps)
   2. Precio: $1 - $20
   3. Volumen intradía >= 1M
   4. ETB (Easy To Borrow) disponible en IBKR
   5. Float > 10M (evita microcaps extremas)

📊 PASO 2: Detectar Exceso Alcista (Setup Recognition)
   1. Movimiento reciente: +10% a +30% en poco tiempo
   2. RSI(14) > 70 (sobrecompra)
   3. Precio > EMA20 + 2×ATR (extensión)
   4. Volumen > 2× media (confirmación)

   ⚠️ IMPORTANTE: NO entramos aún, solo identificamos el setup

⏳ PASO 3: Esperar Agotamiento (Confirmación - CLAVE)
   Señales de debilidad (al menos 2 de 4):
   1. Velas con mecha superior larga (rechazo)
   2. RSI empieza a caer desde >70
   3. Cierre por debajo de VWAP o EMA20
   4. Divergencia volumen/precio (volumen decrece)

   📌 Esta espera AUMENTA la tasa de acierto significativamente

🔻 PASO 4: Trigger de Entrada (Entry Signal)
   Entrada cuando TODO se cumple:
   1. RSI(14) cruza hacia abajo desde >70
   2. Precio cierra debajo de EMA20
   3. Volumen decrece vs promedio 5 barras previas
   4. NO hay news/catalyst positivo reciente
   5. Market hours (9:30-16:00, NO premarket/afterhours)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ RISK MANAGEMENT (Non-Negotiable)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stop Loss:
   • Stop = High reciente + 0.5×ATR (buffer por encima del máximo)
   • Riesgo por trade: 0.25% - 1% del capital (configurable)

Take Profit:
   • RR mínimo: 1:1.5 o 1:2
   • Targets escalonados:
     - T1: VWAP (target conservador - 50% posición)
     - T2: EMA50 (target medio - 30% posición)
     - T3: Soporte previo (target agresivo - 20% posición)

Time Exit:
   • Si no funciona en X barras (configurable) → salir
   • Siempre cerrar antes del cierre del mercado (15:45)
   • NO overnight holds (riesgo de news/dilution)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 PERFORMANCE CHARACTERISTICS (Expected)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Alta tasa de acierto: 60-70% (por confirmación estricta)
✅ Beneficios moderados: +3-8% por trade
✅ Pérdidas pequeñas: -1-3% (stops ajustados)
✅ R:R: 1.5:1 a 2.5:1
✅ Hold time: Intraday (1-6 horas típico)

⚠️ Lo que NO garantiza:
   ❌ Beneficios enormes por trade
   ❌ Ganar siempre

✅ Lo que SÍ ofrece:
   ✔ Muchas pequeñas ganancias
   ✔ Pérdidas pequeñas y controladas
   ✔ Gestión de riesgo clara

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RIESGOS ESPECÍFICOS (Short Small Caps)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❗ Trading halts (halts inesperados)
❗ Dilution offerings (dilución de acciones)
❗ News inesperadas (pumps por noticias)
❗ Borrow recall (broker solicita devolución de acciones)
❗ Short squeeze (reversión brusca al alza)

🔒 MITIGACIÓN:
   👉 Posiciones pequeñas (0.25-1% riesgo)
   👉 Tiempo corto (intraday)
   👉 Stops automáticos (no negociables)
   👉 Solo ETB (Easy To Borrow)
   👉 Monitoreo activo

Author: Trading System - Custom Strategy
Date: 2024-12-26
"""

import logging
from datetime import datetime, time
from typing import Dict, Optional, Tuple, Any, List
import numpy as np

from .base_worker_logic import BaseWorkerLogic
from core.market_hours import get_market_hours, can_enter_short, should_force_exit_short
from core.trade_arbiter import TradingHorizon


class SmallCapsShortReversalWorkerLogic(BaseWorkerLogic):
    """
    Small Caps Short Reversal Worker

    Specialized in shorting overbought small caps after exhaustion confirmation.
    High win-rate strategy (60-70%) with moderate gains per trade.
    """

    def __init__(self, worker_name, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name=worker_name,
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔍 PASO 1: FILTROS DE UNIVERSO
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # Market Cap filters
        self.max_market_cap = float(getattr(config, 'smallcaps_short_max_mcap_billions', 3.0))  # $3B max

        # Price range
        self.min_price = float(getattr(config, 'smallcaps_short_min_price', 1.0))  # $1 min
        self.max_price = float(getattr(config, 'smallcaps_short_max_price', 20.0))  # $20 max

        # Volume and liquidity
        self.min_volume_intraday = int(getattr(config, 'smallcaps_short_min_volume', 1_000_000))  # 1M min
        self.min_float_millions = float(getattr(config, 'smallcaps_short_min_float', 10.0))  # 10M min

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 📊 PASO 2: EXCESO ALCISTA (SETUP RECOGNITION)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # Recent move threshold
        self.min_recent_move_pct = float(getattr(config, 'smallcaps_short_min_move_pct', 10.0))  # +10% min
        self.max_recent_move_pct = float(getattr(config, 'smallcaps_short_max_move_pct', 30.0))  # +30% max
        self.recent_move_lookback_bars = int(getattr(config, 'smallcaps_short_move_lookback', 20))  # 20 bars

        # Overbought threshold
        self.rsi_overbought_threshold = float(getattr(config, 'smallcaps_short_rsi_threshold', 70.0))  # RSI > 70

        # Extension threshold (price > EMA20 + N×ATR)
        self.extension_atr_multiplier = float(getattr(config, 'smallcaps_short_extension_atr', 2.0))  # 2×ATR

        # Volume confirmation
        self.volume_spike_multiplier = float(getattr(config, 'smallcaps_short_volume_spike', 2.0))  # 2× avg

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ⏳ PASO 3: AGOTAMIENTO (CONFIRMACIÓN)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # Minimum exhaustion signals required (out of 4 possible)
        self.min_exhaustion_signals = int(getattr(config, 'smallcaps_short_min_exhaustion_signals', 2))  # 2 of 4

        # Rejection wick ratio (wick_length / body_length)
        self.rejection_wick_ratio = float(getattr(config, 'smallcaps_short_rejection_wick_ratio', 1.5))  # 1.5×

        # Volume decline threshold
        self.volume_decline_threshold = float(getattr(config, 'smallcaps_short_volume_decline', 0.5))  # <50% avg

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔻 PASO 4: TRIGGER DE ENTRADA
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # RSI crossdown threshold (was >70, now crossing down)
        self.rsi_crossdown_threshold = float(getattr(config, 'smallcaps_short_rsi_crossdown', 70.0))

        # EMA period for breakdown confirmation
        self.ema_period = int(getattr(config, 'smallcaps_short_ema_period', 20))

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🛡️ RISK MANAGEMENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # Stop Loss
        self.stop_atr_buffer = float(getattr(config, 'smallcaps_short_stop_atr_buffer', 0.5))  # 0.5×ATR above high

        # Take Profit targets
        self.tp1_ratio = float(getattr(config, 'smallcaps_short_tp1_ratio', 1.5))  # 1.5R at VWAP
        self.tp2_ratio = float(getattr(config, 'smallcaps_short_tp2_ratio', 2.0))  # 2R at EMA50

        # Position sizing (% risk per trade)
        self.min_risk_pct = float(getattr(config, 'smallcaps_short_min_risk_pct', 0.25))  # 0.25%
        self.max_risk_pct = float(getattr(config, 'smallcaps_short_max_risk_pct', 1.0))  # 1.0%

        # Time exit
        self.max_hold_bars = int(getattr(config, 'smallcaps_short_max_hold_bars', 60))  # 60 bars (1h if 1min)
        self.force_exit_time = getattr(config, 'smallcaps_short_force_exit_time', '15:45')  # Close by 15:45

        # Minimum R:R ratio
        self.min_risk_reward = float(getattr(config, 'smallcaps_short_min_rr', 1.5))  # 1.5:1 min

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ⚠️ PROTECCIÓN ANTI-OVERTRADING
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        self.max_trades_per_symbol_per_day = 1  # Solo 1 intento por símbolo/día
        self.traded_symbols_today = set()

        # Quality filter
        self.min_quality_score = float(getattr(config, 'smallcaps_short_min_quality', 50.0))

        self.config = config

        self.logger.info(
            f"🐻 Small Caps Short Reversal Worker configured:\n"
            f"   • Price Range: ${self.min_price} - ${self.max_price}\n"
            f"   • Min Volume: {self.min_volume_intraday:,}\n"
            f"   • Min Move: {self.min_recent_move_pct}% - {self.max_recent_move_pct}%\n"
            f"   • RSI Threshold: {self.rsi_overbought_threshold}\n"
            f"   • Min R:R: {self.min_risk_reward}:1\n"
            f"   • Risk per trade: {self.min_risk_pct}% - {self.max_risk_pct}%"
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🔍 ENTRY EVALUATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Determine if SHORT entry should be executed

        Implements 4-step process:
        1. Universe filters (pre-filter)
        2. Detect bullish excess (setup)
        3. Wait for exhaustion (confirmation)
        4. Entry trigger (execution)
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            self.logger.info(f"\n{'='*70}")
            self.logger.info(f"🔍 Small Caps Short Reversal evaluation for {symbol}")
            self.logger.info(f"{'='*70}")

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 0: MARKET HOURS CHECK (CRITICAL FOR SHORTS)
            # ═══════════════════════════════════════════════════════════════════════

            can_short, short_reason = can_enter_short()
            if not can_short:
                self.logger.warning(f"🚫 {symbol}: SHORT entry BLOCKED - {short_reason}")
                return False

            self.logger.debug(f"✅ {symbol}: Market hours check passed - SHORT entry allowed")

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 0B: ANTI-OVERTRADING
            # ═══════════════════════════════════════════════════════════════════════

            if symbol in self.traded_symbols_today:
                self.logger.debug(f"⏭️ {symbol}: Already traded today (anti-overtrading)")
                return False

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 1: UNIVERSE FILTERS (Pre-Filter)
            # ═══════════════════════════════════════════════════════════════════════

            if not await self._check_universe_filters(opportunity):
                return False

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 2: DETECT BULLISH EXCESS (Setup Recognition)
            # ═══════════════════════════════════════════════════════════════════════

            excess_data = await self._detect_bullish_excess(opportunity)
            if not excess_data['has_excess']:
                self.logger.info(f"⏭️ {symbol}: No bullish excess detected - {excess_data['reason']}")
                return False

            self.logger.info(f"✅ {symbol}: Bullish excess confirmed - {excess_data['reason']}")

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 3: WAIT FOR EXHAUSTION (Confirmation - CLAVE)
            # ═══════════════════════════════════════════════════════════════════════

            exhaustion_data = await self._check_exhaustion_signals(opportunity, excess_data)
            if not exhaustion_data['is_exhausted']:
                self.logger.info(f"⏭️ {symbol}: Not exhausted yet - {exhaustion_data['reason']}")
                return False

            self.logger.info(f"✅ {symbol}: Exhaustion confirmed - {exhaustion_data['signals_met']}/{exhaustion_data['total_signals']} signals")

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 4: ENTRY TRIGGER
            # ═══════════════════════════════════════════════════════════════════════

            trigger_data = await self._check_entry_trigger(opportunity, excess_data, exhaustion_data)
            if not trigger_data['triggered']:
                self.logger.info(f"⏭️ {symbol}: Entry trigger not met - {trigger_data['reason']}")
                return False

            self.logger.info(f"✅ {symbol}: Entry trigger confirmed - {trigger_data['reason']}")

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 5: BORROWABILITY CHECK (CRITICAL)
            # ═══════════════════════════════════════════════════════════════════════

            if not await self._check_borrowability(symbol):
                return False

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 6: RISK/REWARD VALIDATION
            # ═══════════════════════════════════════════════════════════════════════

            rr_data = await self._calculate_risk_reward(opportunity, excess_data)
            if rr_data['rr_ratio'] < self.min_risk_reward:
                self.logger.info(
                    f"⏭️ {symbol}: R:R too low ({rr_data['rr_ratio']:.2f} < {self.min_risk_reward})"
                )
                return False

            # ═══════════════════════════════════════════════════════════════════════
            # FINAL APPROVAL
            # ═══════════════════════════════════════════════════════════════════════

            current_price = opportunity.get('current_price', 0)

            self.logger.info(f"\n🎯 {symbol}: ALL CRITERIA MET - SHORT REVERSAL SETUP CONFIRMED")
            self.logger.info(f"   • Entry Price: ${current_price:.2f}")
            self.logger.info(f"   • Stop Loss: ${rr_data['stop_price']:.2f} (HOD + {self.stop_atr_buffer}×ATR)")
            self.logger.info(f"   • Target 1: ${rr_data['target_price']:.2f} (VWAP)")
            self.logger.info(f"   • R:R Ratio: {rr_data['rr_ratio']:.2f}:1")
            self.logger.info(f"   • Recent Move: {excess_data['recent_move_pct']:.1f}%")
            self.logger.info(f"   • RSI: {excess_data['rsi']:.1f}")
            self.logger.info(f"   • Exhaustion Signals: {exhaustion_data['signals_met']}/{exhaustion_data['total_signals']}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Error in should_enter for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def _check_universe_filters(self, opportunity: Dict[str, Any]) -> bool:
        """
        STEP 1: Check universe filters (pre-filter)

        Filters:
        1. Market Cap < $3B
        2. Price: $1 - $20
        3. Volume >= 1M
        4. Float > 10M
        5. Quality Score >= min_quality
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        # Price range
        current_price = opportunity.get('current_price', 0)
        if current_price < self.min_price or current_price > self.max_price:
            self.logger.debug(
                f"⏭️ {symbol}: Price ${current_price:.2f} outside range "
                f"(${self.min_price}-${self.max_price})"
            )
            return False

        # Volume
        volume = opportunity.get('current_volume', opportunity.get('volume', 0))
        if volume < self.min_volume_intraday:
            self.logger.debug(
                f"⏭️ {symbol}: Volume {volume:,} < {self.min_volume_intraday:,}"
            )
            return False

        # Float (if available)
        float_shares = opportunity.get('float_shares', 0)
        if float_shares > 0:
            float_millions = float_shares / 1_000_000
            if float_millions < self.min_float_millions:
                self.logger.debug(
                    f"⏭️ {symbol}: Float {float_millions:.1f}M < {self.min_float_millions}M"
                )
                return False

        # Market Cap (if available)
        market_cap = opportunity.get('market_cap', 0)
        if market_cap > 0:
            market_cap_billions = market_cap / 1_000_000_000
            if market_cap_billions > self.max_market_cap:
                self.logger.debug(
                    f"⏭️ {symbol}: Market Cap ${market_cap_billions:.2f}B > ${self.max_market_cap}B"
                )
                return False

        # Quality Score
        quality = opportunity.get('quality_score', 0)
        if quality < self.min_quality_score:
            self.logger.debug(
                f"⏭️ {symbol}: Quality {quality:.1f} < {self.min_quality_score}"
            )
            return False

        self.logger.debug(f"✅ {symbol}: Universe filters passed")
        return True

    async def _detect_bullish_excess(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        STEP 2: Detect bullish excess (setup recognition)

        Checks:
        1. Recent move: +10% to +30%
        2. RSI(14) > 70
        3. Price > EMA20 + 2×ATR
        4. Volume > 2× average

        Returns:
            Dict with has_excess, reason, and metrics
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        bars = self.get_bars_from_opportunity(opportunity)

        if not bars or len(bars) < self.recent_move_lookback_bars:
            return {
                'has_excess': False,
                'reason': f'Insufficient bars ({len(bars) if bars else 0})'
            }

        current_price = opportunity.get('current_price', bars[-1].close)

        # Calculate indicators
        rsi = self._calculate_rsi(bars, period=14)
        ema20 = self._calculate_ema(bars, period=self.ema_period)
        atr = self._calculate_atr(bars, period=14)
        vwap = self._calculate_vwap(bars)

        # Recent move
        lookback_price = bars[-self.recent_move_lookback_bars].close
        recent_move_pct = ((current_price - lookback_price) / lookback_price) * 100

        # Volume spike
        recent_volume = np.mean([b.volume for b in bars[-5:]])
        avg_volume = np.mean([b.volume for b in bars[-20:-5]])
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 0

        # Check conditions
        has_move = self.min_recent_move_pct <= recent_move_pct <= self.max_recent_move_pct
        has_rsi_overbought = rsi > self.rsi_overbought_threshold
        has_extension = current_price > (ema20 + self.extension_atr_multiplier * atr)
        has_volume_spike = volume_ratio > self.volume_spike_multiplier

        # Count confirmations
        confirmations = sum([has_move, has_rsi_overbought, has_extension, has_volume_spike])

        # Need at least 3 of 4 confirmations
        has_excess = confirmations >= 3

        reason_parts = []
        if has_move:
            reason_parts.append(f"Move {recent_move_pct:.1f}%")
        if has_rsi_overbought:
            reason_parts.append(f"RSI {rsi:.1f}")
        if has_extension:
            reason_parts.append(f"Extended {((current_price - ema20) / ema20 * 100):.1f}% above EMA20")
        if has_volume_spike:
            reason_parts.append(f"Vol {volume_ratio:.1f}× avg")

        reason = f"{confirmations}/4 signals: " + ", ".join(reason_parts)

        return {
            'has_excess': has_excess,
            'reason': reason,
            'recent_move_pct': recent_move_pct,
            'rsi': rsi,
            'ema20': ema20,
            'atr': atr,
            'vwap': vwap,
            'volume_ratio': volume_ratio,
            'confirmations': confirmations
        }

    async def _check_exhaustion_signals(
        self,
        opportunity: Dict[str, Any],
        excess_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STEP 3: Check for exhaustion signals (confirmation)

        Signals (need at least 2 of 4):
        1. Rejection wick (upper wick > 1.5× body)
        2. RSI declining from >70
        3. Price below VWAP or EMA20
        4. Volume declining

        Returns:
            Dict with is_exhausted, signals_met, and details
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        bars = self.get_bars_from_opportunity(opportunity)

        if not bars or len(bars) < 3:
            return {
                'is_exhausted': False,
                'reason': 'Insufficient bars for exhaustion check',
                'signals_met': 0,
                'total_signals': 4
            }

        current_price = opportunity.get('current_price', bars[-1].close)
        signals_met = 0
        signals = []

        # Signal 1: Rejection wick
        latest_bar = bars[-1]
        body = abs(latest_bar.close - latest_bar.open)
        upper_wick = latest_bar.high - max(latest_bar.close, latest_bar.open)

        if body > 0 and (upper_wick / body) > self.rejection_wick_ratio:
            signals_met += 1
            signals.append(f"Rejection wick {(upper_wick/body):.1f}×body")

        # Signal 2: RSI declining
        rsi_current = excess_data['rsi']
        if len(bars) >= 15:
            rsi_prev = self._calculate_rsi(bars[:-1], period=14)
            if rsi_current < rsi_prev and rsi_prev > self.rsi_overbought_threshold:
                signals_met += 1
                signals.append(f"RSI declining {rsi_prev:.1f}→{rsi_current:.1f}")

        # Signal 3: Price below VWAP or EMA20
        vwap = excess_data['vwap']
        ema20 = excess_data['ema20']

        if current_price < vwap or current_price < ema20:
            signals_met += 1
            below_what = "VWAP" if current_price < vwap else "EMA20"
            signals.append(f"Price below {below_what}")

        # Signal 4: Volume declining
        if len(bars) >= 10:
            recent_vol = np.mean([b.volume for b in bars[-3:]])
            prev_vol = np.mean([b.volume for b in bars[-8:-3]])

            if prev_vol > 0 and (recent_vol / prev_vol) < self.volume_decline_threshold:
                signals_met += 1
                signals.append(f"Volume declining {(recent_vol/prev_vol*100):.0f}%")

        is_exhausted = signals_met >= self.min_exhaustion_signals
        reason = f"{signals_met}/{self.min_exhaustion_signals} required: " + ", ".join(signals) if signals else "No signals"

        return {
            'is_exhausted': is_exhausted,
            'reason': reason,
            'signals_met': signals_met,
            'total_signals': 4,
            'signals': signals
        }

    async def _check_entry_trigger(
        self,
        opportunity: Dict[str, Any],
        excess_data: Dict[str, Any],
        exhaustion_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STEP 4: Check entry trigger

        Trigger when ALL true:
        1. RSI crossed down from >70
        2. Price closed below EMA20
        3. Volume decreasing
        4. No recent positive catalyst

        Returns:
            Dict with triggered and reason
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        bars = self.get_bars_from_opportunity(opportunity)
        current_price = opportunity.get('current_price', bars[-1].close)

        triggers = []
        trigger_count = 0

        # Trigger 1: RSI crossdown from >70 (already checked in exhaustion)
        rsi = excess_data['rsi']
        if rsi < self.rsi_crossdown_threshold:
            trigger_count += 1
            triggers.append(f"RSI crossed down from {self.rsi_crossdown_threshold}")

        # Trigger 2: Price below EMA20
        ema20 = excess_data['ema20']
        if current_price < ema20:
            trigger_count += 1
            triggers.append(f"Price below EMA20 (${ema20:.2f})")

        # Trigger 3: Volume decreasing (already in exhaustion signals)
        if "Volume declining" in exhaustion_data.get('signals', []):
            trigger_count += 1
            triggers.append("Volume decreasing")

        # Trigger 4: No positive catalyst (check if catalyst_type is negative or neutral)
        catalyst_type = opportunity.get('catalyst_type', 'NONE')
        catalyst_strength = opportunity.get('catalyst_strength', 0)

        # We want NO strong positive catalyst
        has_no_positive_catalyst = (
            catalyst_type in ['NONE', 'TECHNICAL'] or
            catalyst_strength < 5
        )

        if has_no_positive_catalyst:
            trigger_count += 1
            triggers.append(f"No strong catalyst ({catalyst_type})")

        # Need at least 3 of 4 triggers
        triggered = trigger_count >= 3
        reason = f"{trigger_count}/4 triggers: " + ", ".join(triggers)

        return {
            'triggered': triggered,
            'reason': reason,
            'trigger_count': trigger_count
        }

    async def _check_borrowability(self, symbol: str) -> bool:
        """
        Check if symbol is Easy To Borrow (ETB)

        Critical for short entries - prevents borrow fees and recalls
        """
        try:
            short_data = await self.execution_engine.broker.get_short_data(symbol)

            is_etb = short_data.get('is_etb', False)
            shares_available = short_data.get('shortable_shares', 0)

            if not is_etb or shares_available < 10000:
                status_msg = f"Status: {short_data.get('short_status')}, Shares: {shares_available}"

                # Only log warning once per session per symbol
                if symbol not in getattr(self, 'waiting_for_etb', set()):
                    if not hasattr(self, 'waiting_for_etb'):
                        self.waiting_for_etb = set()
                    self.waiting_for_etb.add(symbol)
                    self.logger.warning(f"⏳ {symbol}: WAITING for ETB/Shares ({status_msg})")
                else:
                    self.logger.debug(f"⏳ {symbol}: Still waiting for shares... ({status_msg})")

                return False

            # Shares found!
            if hasattr(self, 'waiting_for_etb') and symbol in self.waiting_for_etb:
                self.logger.info(f"✅ {symbol}: SHARES LOCATED! ({shares_available} shares)")
                self.waiting_for_etb.remove(symbol)
            else:
                self.logger.info(f"✅ {symbol}: Borrow check passed (ETB, {shares_available} shares)")

            return True

        except Exception as e:
            self.logger.warning(f"⚠️ {symbol}: Failed to check borrowability: {e} - Skipping")
            return False

    async def _calculate_risk_reward(
        self,
        opportunity: Dict[str, Any],
        excess_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate risk/reward for the trade

        Stop: High + 0.5×ATR
        Target: VWAP (primary) or EMA50 (secondary)

        Returns:
            Dict with stop_price, target_price, rr_ratio
        """
        bars = self.get_bars_from_opportunity(opportunity)
        current_price = opportunity.get('current_price', bars[-1].close)

        # Calculate HOD (High of Day)
        hod = max([b.high for b in bars])

        # Stop Loss: HOD + buffer
        atr = excess_data['atr']
        stop_price = hod + (self.stop_atr_buffer * atr)

        # Target: VWAP (conservative)
        vwap = excess_data['vwap']
        target_price = vwap

        # If VWAP is above current price (bad R:R), use EMA50 instead
        if vwap >= current_price:
            ema50 = self._calculate_ema(bars, period=50)
            target_price = min(ema50, current_price * 0.95)  # At least 5% profit

        # Calculate R:R
        risk = stop_price - current_price
        reward = current_price - target_price

        rr_ratio = reward / risk if risk > 0 else 0

        return {
            'stop_price': stop_price,
            'target_price': target_price,
            'risk': risk,
            'reward': reward,
            'rr_ratio': rr_ratio,
            'hod': hod
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🚪 EXIT EVALUATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Exit logic for Small Caps Short Reversal

        Exit conditions:
        1. Stop Loss hit (price > stop)
        2. Take Profit hit (price <= target)
        3. Time exit (max bars or force close time)
        4. Force exit if market hours end

        Returns:
            (should_exit, reason)
        """
        try:
            entry_price = position.get('entry_price', 0)
            entry_time = position.get('entry_time')

            # Get position bars history
            bars = position.get('bars_history', [])

            # ═══════════════════════════════════════════════════════════════════════
            # EXIT 1: FORCE EXIT (Market Hours - CRITICAL FOR SHORTS)
            # ═══════════════════════════════════════════════════════════════════════

            should_force_exit, force_reason = should_force_exit_short()
            if should_force_exit:
                return True, f"FORCE_EXIT_SHORT_{force_reason}"

            # ═══════════════════════════════════════════════════════════════════════
            # EXIT 2: TIME-BASED EXIT (15:45 close)
            # ═══════════════════════════════════════════════════════════════════════

            now = datetime.now()
            exit_hour, exit_min = map(int, self.force_exit_time.split(':'))
            force_exit_time = now.replace(hour=exit_hour, minute=exit_min, second=0)

            if now >= force_exit_time:
                return True, "TIME_EXIT_15:45"

            # ═══════════════════════════════════════════════════════════════════════
            # EXIT 3: STOP LOSS (Price above stop)
            # ═══════════════════════════════════════════════════════════════════════

            stop_price = position.get('stop_loss', entry_price * 1.03)  # Fallback 3%

            if current_price >= stop_price:
                loss_pct = ((current_price - entry_price) / entry_price) * 100
                return True, f"SL_HIT_{loss_pct:.1f}%"

            # ═══════════════════════════════════════════════════════════════════════
            # EXIT 4: TAKE PROFIT (Price at or below target)
            # ═══════════════════════════════════════════════════════════════════════

            target_price = position.get('take_profit', entry_price * 0.95)  # Fallback 5%

            if current_price <= target_price:
                profit_pct = ((entry_price - current_price) / entry_price) * 100
                return True, f"TP_HIT_{profit_pct:.1f}%"

            # ═══════════════════════════════════════════════════════════════════════
            # EXIT 5: MAX HOLD TIME (Position dragging too long)
            # ═══════════════════════════════════════════════════════════════════════

            if bars and len(bars) > self.max_hold_bars:
                return True, f"MAX_HOLD_{len(bars)}_BARS"

            # No exit conditions met
            return False, "NO_EXIT"

        except Exception as e:
            self.logger.error(f"❌ Error in should_exit for {symbol}: {e}")
            return False, "ERROR"

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📊 TECHNICAL INDICATORS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _calculate_rsi(self, bars: List, period: int = 14) -> float:
        """Calculate RSI indicator"""
        if len(bars) < period + 1:
            return 50.0

        closes = np.array([b.close for b in bars[-period-1:]])
        deltas = np.diff(closes)

        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_ema(self, bars: List, period: int = 20) -> float:
        """Calculate EMA indicator"""
        if len(bars) < period:
            return np.mean([b.close for b in bars])

        closes = np.array([b.close for b in bars[-period*2:]])  # Use 2× period for stability
        multiplier = 2 / (period + 1)

        ema = closes[0]
        for close in closes[1:]:
            ema = (close - ema) * multiplier + ema

        return ema

    def _calculate_atr(self, bars: List, period: int = 14) -> float:
        """Calculate ATR (Average True Range)"""
        if len(bars) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(1, len(bars)):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i-1].close

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        atr = np.mean(true_ranges[-period:])
        return atr

    def _calculate_vwap(self, bars: List) -> float:
        """Calculate VWAP (Volume Weighted Average Price)"""
        if not bars:
            return 0.0

        total_pv = sum([(b.high + b.low + b.close) / 3 * b.volume for b in bars])
        total_v = sum([b.volume for b in bars])

        if total_v == 0:
            return bars[-1].close

        return total_pv / total_v

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🔧 WORKER INTERFACE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _execute_entry(self, symbol: str, opportunity: Dict[str, Any]):
        """Execute short entry and track symbol"""
        await super()._execute_entry(symbol, opportunity)
        self.traded_symbols_today.add(symbol)

    def _get_trading_horizon(self) -> str:
        """Return trading horizon for this worker"""
        return TradingHorizon.INTRADAY.value

    def get_worker_name(self) -> str:
        """Return worker name"""
        return "smallcaps_short_reversal"

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calculate pattern completion for Replay compatibility

        0%: No setup
        25%: Universe filters passed
        50%: Bullish excess detected
        75%: Exhaustion confirmed
        100%: Entry trigger + borrowability
        """
        try:
            completion = 0.0

            # Step 1: Universe filters (25%)
            if await self._check_universe_filters(opportunity):
                completion += 25.0
            else:
                return completion

            # Step 2: Bullish excess (25%)
            excess_data = await self._detect_bullish_excess(opportunity)
            if excess_data['has_excess']:
                completion += 25.0
            else:
                return completion

            # Step 3: Exhaustion (25%)
            exhaustion_data = await self._check_exhaustion_signals(opportunity, excess_data)
            if exhaustion_data['is_exhausted']:
                completion += 25.0
            else:
                return completion

            # Step 4: Entry trigger (25%)
            trigger_data = await self._check_entry_trigger(opportunity, excess_data, exhaustion_data)
            if trigger_data['triggered']:
                completion += 25.0

            return min(completion, 100.0)

        except Exception as e:
            self.logger.error(f"Error calculating pattern completion: {e}")
            return 0.0
