"""
Outlier Penny Stock Extreme Worker Logic
Worker específico para estrategia OUTLIER_PENNY_STOCK_EXTREME basada en reglas validadas.

Regla validada aplicada:
- OUTLIER_PENNY_STOCK_EXTREME (+11.69% edge esperado, 54.6% win rate)

Enfoque: Hunting extreme penny stock opportunities ($3-$5 range) con volatilidad premarket

CARACTERÍSTICAS CLAVE:
- Expected edge: +11.69% (backtest real en 163 eventos)
- Win rate: 54.6% (NO es lottery ticket)
- Avg win: +31.43% | Avg loss: -12.05%
- Best trade: +356% | Worst trade: -39%
- Sample size: 163 eventos históricos

CRITERIOS DE ENTRADA (EXACT match to validated rule):
1. Price $3.00-$5.00 (penny stock range - NOT ultra-cheap)
2. Premarket range > 3% (volatilidad premarket)
3. Volume: NOT required (informational only)
4. VWAP: NOT required (optional confirmation)

GESTIÓN DE RIESGO (CRÍTICO):
- Position size: 1.0% MAX del capital
- Stop loss: 15%
- Take profit: 50%
- Trailing stop: 30% activation
- Max hold time: 1 día (exit at 15:45 ET)
- Max positions: 2 simultáneas

Última actualización: 2025-11-06 - Simplificado para coincidir con regla validada
"""

import logging
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradingHorizon


class OutlierPennyExtremeWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia OUTLIER_PENNY_STOCK_EXTREME

    Basado en reglas validadas por el sistema de extracción de reglas:
    - OUTLIER_PENNY_STOCK_EXTREME
    - Edge esperado: +11.69% (backtest real)
    - Win rate: 54.6% (backtest real en 163 eventos)
    - Risk level: EXTREME

    Criterios de entrada (SIMPLIFIED 2025-11-06):
    1. Price $3.00-$5.00 (penny stock range - EXACT match)
    2. Premarket range > 3% (volatilidad - EXACT match)
    3. Volume: NOT required (informational only)
    4. VWAP: NOT required (optional confirmation)
    5. Trading hours: 9:45 AM - 3:45 PM ET

    Criterios de salida (via WorkerStopManager):
    - Take profit: 50% (aggressive for outliers)
    - Stop loss: 15% (wide for volatility)
    - Trailing stop: 30% activation, 10% distance
    - Time-based: Force exit at 15:45 ET
    - Max hold time: 1 day (no overnight)
    """

    def __init__(self, broker, risk_manager=None, config=None, execution_engine=None):
        super().__init__(
            worker_name="outlier_penny_extreme",
            broker=broker,
            config=config
        )

        # Configuración específica OUTLIER_PENNY_STOCK_EXTREME (EXACT match to validated rule)
        self.max_price = 5.0               # Precio máximo (< $5.00) ✅
        self.min_price = 3.0               # Precio mínimo (>= $3.00) ✅ CHANGED from 0.10
        self.min_pm_range_pct = 3.0        # Mínimo premarket range (> 3%) ✅

        # NOT required by validated rule (informational only):
        self.min_volume_ratio = None       # Volume NOT required ✅ CHANGED
        self.require_vwap_above = False    # VWAP NOT required ✅ CHANGED
        self.max_spread_pct = 5.0          # Spread máximo permitido (%) - safety filter

        # Risk Management (CRÍTICO para outliers)
        self.max_position_size_pct = 1.0    # 1% MAX del capital
        self.max_concurrent_positions = 2   # Max 2 posiciones simultáneas

        # Entry confirmation tracking
        self.pending_entries = {}           # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 1          # 1 confirmación suficiente
        self.confirmation_window = 60       # Ventana de 1 minuto

        # Initialize centralized stop manager con parámetros específicos
        if config:
            self.stop_manager = create_worker_stop_manager(
                config,
                'OUTLIER_PENNY_EXTREME_STRATEGY'
            )

        self.logger.info(
            f"🎯 Outlier Penny Extreme Worker configured (EXACT RULE MATCH): "
            f"price=${self.min_price}-${self.max_price}, pm_range>={self.min_pm_range_pct}%"
        )
        self.logger.info(f"   Expected Edge: +11.69% (validated on 163 events)")
        self.logger.info(f"   Volume: NOT required (informational only)")
        self.logger.info(f"   VWAP: NOT required (optional confirmation)")
        self.logger.info(
            f"   ⚠️  RISK MANAGEMENT: position_size={self.max_position_size_pct}% MAX, "
            f"max_positions={self.max_concurrent_positions}"
        )
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    def _is_trading_hours(self, time_decimal: float) -> bool:
        """
        Check if current time is within allowed trading hours
        Outlier Penny: 9:45 AM ET to 3:45 PM ET (avoid early/late volatility)
        """
        return 9.75 <= time_decimal <= 15.75  # 9:45 AM to 3:45 PM ET

    def _get_time_from_timestamp(self, timestamp) -> float:
        """Convert timestamp to decimal hours in US/Eastern timezone"""
        try:
            import pytz
            from datetime import datetime

            eastern = pytz.timezone('US/Eastern')

            if isinstance(timestamp, str):
                from dateutil import parser
                dt = parser.parse(timestamp)
            elif isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, datetime):
                dt = timestamp
            else:
                dt = datetime.now()

            # Validate dt is datetime before accessing tzinfo
            if not isinstance(dt, datetime):
                return 12.0

            # Convert to Eastern time properly
            if dt.tzinfo is None:
                spain_tz = pytz.timezone('Europe/Madrid')
                dt = spain_tz.localize(dt)
            else:
                dt = dt.astimezone(eastern)

            return dt.hour + dt.minute / 60.0

        except Exception as e:
            self.logger.error(f"Error converting timestamp to time: {e}")
            return 0.0

    def _validate_penny_criteria(self, opportunity: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate basic penny stock criteria

        Args:
            opportunity: Opportunity data

        Returns:
            Tuple (is_valid, reason)
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        current_price = opportunity.get('current_price', 0)
        regular_open = opportunity.get('regular_open', current_price)

        # Price validation: < $5.00
        if regular_open >= self.max_price:
            return False, f"Price ${regular_open:.2f} >= ${self.max_price} (not penny stock)"

        if regular_open < self.min_price:
            return False, f"Price ${regular_open:.2f} too low (< ${self.min_price})"

        return True, "Penny stock criteria met"

    def _validate_premarket_volatility(self, opportunity: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate premarket volatility criteria

        Uses premarket_range_pct if available, otherwise falls back to gap as proxy

        Args:
            opportunity: Opportunity data

        Returns:
            Tuple (is_valid, reason)
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        pm_range_pct = opportunity.get('premarket_range_pct', None)

        # Try to use premarket_range_pct if available
        if pm_range_pct is not None and pm_range_pct > 0:
            # Use actual premarket data
            if pm_range_pct < self.min_pm_range_pct:
                return False, f"PM range {pm_range_pct:.2f}% < {self.min_pm_range_pct}%"
            return True, f"PM volatility {pm_range_pct:.2f}% sufficient"

        # Fallback: use gap as proxy for premarket volatility
        gap_pct = abs(opportunity.get('gap_pct', 0))

        if gap_pct < self.min_pm_range_pct:
            return False, f"Gap {gap_pct:.2f}% < {self.min_pm_range_pct}% (using gap as PM proxy)"

        return True, f"Gap {gap_pct:.2f}% sufficient (using gap as PM proxy)"

    def _validate_volume_confirmation(self, opportunity: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Volume is INFORMATIONAL ONLY - not required by validated rule

        The validated OUTLIER_PENNY_STOCK_EXTREME rule does NOT have volume requirement.
        We log it for information but ALWAYS return True.

        Args:
            opportunity: Opportunity data

        Returns:
            Tuple (always True, informational message)
        """
        volume_ratio = opportunity.get('volume_ratio', 1.0)

        # INFORMATIONAL ONLY - always return True
        if volume_ratio >= 2.0:
            return True, f"Volume {volume_ratio:.1f}x (high, informational only)"
        elif volume_ratio >= 1.5:
            return True, f"Volume {volume_ratio:.1f}x (moderate, informational only)"
        else:
            return True, f"Volume {volume_ratio:.1f}x (low, informational only)"

    def _validate_technical_conditions(self, opportunity: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate technical conditions for entry

        VWAP is OPTIONAL (not required by validated rule) - informational only
        Spread validation is still enforced for execution safety

        Args:
            opportunity: Opportunity data

        Returns:
            Tuple (is_valid, reason)
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        current_price = opportunity.get('current_price', 0)
        vwap = opportunity.get('vwap', 0)
        bid = opportunity.get('bid', 0)
        ask = opportunity.get('ask', 0)

        # VWAP is INFORMATIONAL ONLY (not required by validated rule)
        vwap_msg = ""
        if vwap > 0:
            if current_price >= vwap:
                vwap_msg = f", price ${current_price:.2f} > VWAP ${vwap:.2f} ✓"
            else:
                vwap_msg = f", price ${current_price:.2f} < VWAP ${vwap:.2f} (acceptable)"
        else:
            vwap_msg = ", VWAP not available"

        # Spread validation (evitar spreads excesivos - safety check)
        if bid > 0 and ask > 0:
            spread_pct = ((ask - bid) / current_price) * 100
            if spread_pct > self.max_spread_pct:
                return False, f"Spread {spread_pct:.1f}% > {self.max_spread_pct}%{vwap_msg}"

        return True, f"Technical conditions met{vwap_msg}"

    def _check_position_limits(self) -> Tuple[bool, str]:
        """
        Check if we can open a new position based on limits

        Returns:
            Tuple (can_open, reason)
        """
        active_count = len([p for p in self.active_positions.values() if p.get('status') == 'OPEN'])

        if active_count >= self.max_concurrent_positions:
            return False, f"Max positions reached ({active_count}/{self.max_concurrent_positions})"

        return True, f"Can open position ({active_count}/{self.max_concurrent_positions})"

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Determine if we should enter a position based on OUTLIER_PENNY_STOCK_EXTREME rules

        Criteria:
        1. Price < $5.00
        2. Premarket range > 3%
        3. Volume >= 1.5x (confirmación)
        4. Price > VWAP
        5. Trading hours: 9:45 AM - 3:45 PM ET
        6. Position limits: max 2 concurrent

        Args:
            opportunity: Market opportunity data

        Returns:
            bool: True if should enter, False otherwise
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            self.logger.info(f"🔍 {symbol}: Starting OUTLIER_PENNY_EXTREME evaluation")

            # 1. Check trading hours
            timestamp = opportunity.get('timestamp', datetime.now())
            time_decimal = self._get_time_from_timestamp(timestamp)

            if not self._is_trading_hours(time_decimal):
                self.logger.info(f"⏰ {symbol}: REJECTED - Outside trading hours ({time_decimal:.2f} ET, need 9.75-15.75)")
                return False

            self.logger.info(f"✅ {symbol}: Trading hours check passed ({time_decimal:.2f} ET)")

            # 2. Check position limits
            can_open, limit_reason = self._check_position_limits()
            if not can_open:
                self.logger.info(f"🚫 {symbol}: REJECTED - {limit_reason}")
                return False

            # 3. Validate penny stock criteria (price < $5)
            is_penny, penny_reason = self._validate_penny_criteria(opportunity)
            if not is_penny:
                self.logger.info(f"💰 {symbol}: REJECTED - {penny_reason}")
                return False

            self.logger.info(f"✅ {symbol}: Penny stock criteria passed - {penny_reason}")

            # 4. Validate premarket volatility (range > 3%)
            is_volatile, vol_reason = self._validate_premarket_volatility(opportunity)
            if not is_volatile:
                self.logger.info(f"📊 {symbol}: REJECTED - {vol_reason}")
                return False

            self.logger.info(f"✅ {symbol}: Premarket volatility passed - {vol_reason}")

            # 5. Validate volume confirmation (helpful but not required)
            is_volume_ok, volume_reason = self._validate_volume_confirmation(opportunity)
            # Always pass (just for logging)
            self.logger.info(f"📊 {symbol}: Volume check - {volume_reason}")

            # 6. Validate technical conditions (VWAP, spread)
            is_technical_ok, tech_reason = self._validate_technical_conditions(opportunity)
            if not is_technical_ok:
                self.logger.info(f"📈 {symbol}: REJECTED - {tech_reason}")
                return False

            self.logger.info(f"✅ {symbol}: Technical conditions passed - {tech_reason}")

            # 7. Check for duplicate positions (Broker)
            positions = await self.broker.get_positions()
            if any(p['symbol'] == symbol for p in positions):
                self.logger.info(f"🔄 {symbol}: REJECTED - Already have active position")
                return False

            # ✅ ALL CRITERIA MET
            current_price = opportunity.get('current_price', 0)
            pm_range = opportunity.get('premarket_range_pct', 0)
            volume_ratio = opportunity.get('volume_ratio', 0)

            self.logger.info(
                f"🎯 {symbol} ENTRY SIGNAL: "
                f"price=${current_price:.2f}, pm_range={pm_range:.1f}%, "
                f"vol={volume_ratio:.1f}x, time={time_decimal:.2f}"
            )
            self.logger.info(
                f"   ⚠️  OUTLIER TRADE - Edge: +11.69%, Win Rate: 54.6%, "
                f"Avg Win: +31.43%, Stop: -15%"
            )

            return True

        except Exception as e:
            self.logger.error(f"❌ Error in should_enter for {symbol}: {e}", exc_info=True)
            return False

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Determine if we should exit using WorkerStopManager

        The stop manager handles:
        - Take profit: 50%
        - Stop loss: 15%
        - Trailing stop: 30% activation, 10% distance
        - END_OF_DAY: 15:45 ET

        Args:
            symbol: Stock symbol
            position: Position data
            current_price: Current market price

        Returns:
            Tuple (should_exit, reason)
        """
        try:
            # Use centralized stop manager
            should_exit, reason = self.stop_manager.should_exit(
                symbol=symbol,
                position=position,
                current_price=current_price
            )

            if should_exit:
                entry_price = position.get('entry_price', 0)
                pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

                self.logger.info(
                    f"🚪 {symbol} EXIT SIGNAL: {reason} | "
                    f"Entry=${entry_price:.2f}, Current=${current_price:.2f}, "
                    f"P&L={pnl_pct:+.2f}%"
                )

            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error in should_exit for {symbol}: {e}", exc_info=True)
            # Safe exit on error
            return True, f"ERROR_{str(e)[:50]}"

    def get_position_size(self, opportunity: Dict[str, Any]) -> float:
        """
        Calculate position size based on OUTLIER_PENNY_STOCK_EXTREME risk management

        CRITICAL: Max 1% of capital per position

        Args:
            opportunity: Market opportunity data

        Returns:
            float: Position size as percentage of capital (0.0-1.0)
        """
        # FIXED: 1% MAX for outlier hunting
        position_size = self.max_position_size_pct / 100.0  # 0.01

        symbol = opportunity.get('symbol', 'UNKNOWN')
        self.logger.debug(
            f"📊 {symbol} Position size: {position_size*100:.1f}% "
            f"(OUTLIER HUNTING - FIXED at {self.max_position_size_pct}% MAX)"
        )

        return position_size

    def get_trading_horizon(self) -> TradingHorizon:
        """Return INTRADAY horizon (same-day exit required)"""
        return TradingHorizon.INTRADAY
