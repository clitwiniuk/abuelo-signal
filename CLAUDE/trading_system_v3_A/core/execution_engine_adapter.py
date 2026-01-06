"""
Execution Engine Adapter
Adapta TradingEngine para la interfaz que esperan los Workers
Los workers ejecutan directamente con el broker, sin pasar por el pipeline
"""

import logging
import asyncio
import math
from typing import Dict, Any, Optional
from datetime import datetime
from core.interfaces import Order, OrderSide, OrderType
from core.database_manager import DatabaseManager
from core.commission_calculator import IBKRCommissionCalculator
from core.extended_hours_manager import ExtendedHoursManager, MarketSession
from core.trade_ohlc_recorder import get_trade_ohlc_recorder
from core.time_provider import TimeProvider, SystemTimeProvider
from core.entry_competition import EntryCompetition
from notifications import telegram_client


class ExecutionEngineAdapter:
    """
    Wrapper que permite a los Workers ejecutar operaciones directamente
    con el broker, sin pasar por el pipeline de análisis del TradingEngine

    Los workers esperan:
    - enter_position(symbol, strategy, opportunity_data) -> position
    - exit_position(symbol, reason) -> success
    - get_current_price(symbol) -> price

    Este adapter:
    - Usa el broker directamente (trading_engine.broker)
    - Calcula position size basado en risk
    - Ejecuta órdenes de mercado
    - Rastrea posiciones abiertas por workers
    """

    def __init__(self, broker: Any = None, risk_manager: Any = None, trading_engine: Any = None, config: Dict[str, Any] = None, clock: TimeProvider = None):
        """
        Args:
            broker: IBKRAdapter instance (preferred)
            risk_manager: RiskManager instance (preferred)
            trading_engine: Legacy TradingEngine (deprecated, for backward compatibility)
            config: Configuration dictionary with extended hours settings
            clock: TimeProvider instance (optional, defaults to SystemTimeProvider)
        """
        # Support both new (broker+risk_manager) and legacy (trading_engine) initialization
        if trading_engine is not None:
            # Legacy mode: extract from trading_engine
            self.trading_engine = trading_engine
            self.broker = trading_engine.broker
            self.risk_manager = trading_engine.risk_manager
        elif broker is not None and risk_manager is not None:
            # New mode: direct injection
            self.trading_engine = None
            self.broker = broker
            self.risk_manager = risk_manager
        else:
            raise ValueError("Must provide either (broker + risk_manager) or trading_engine")

        # Store configuration for extended hours settings
        self.config = config or {}

        self.logger = logging.getLogger("ExecutionEngineAdapter")
        self.db_manager = DatabaseManager()

        # Time Provider
        self.clock = clock or SystemTimeProvider()
        
        # Initialize helper classes
        self.extended_hours_manager = ExtendedHoursManager(clock=self.clock)
        self.competition = EntryCompetition(clock=self.clock)
        
        # Initialize state
        # Telegram notifications
        self._telegram_enabled = telegram_client.is_enabled()
        self._send_telegram = telegram_client.send_message if self._telegram_enabled else lambda *args, **kwargs: None
        if self._telegram_enabled:
            self.logger.info("📨 Telegram notifications ENABLED for ExecutionEngine")
        else:
            self.logger.info("📨 Telegram notifications DISABLED for ExecutionEngine")

        # OHLC recorder for trade analysis
        try:
            self.ohlc_recorder = get_trade_ohlc_recorder()
            self.logger.info("📊 OHLC Recorder initialized for trade analysis")
        except Exception as e:
            self.logger.warning(f"⚠️ OHLC Recorder initialization failed: {e}")
            self.ohlc_recorder = None

        # Track worker positions (separate from TradingEngine pipeline)
        self.worker_positions: Dict[str, Dict[str, Any]] = {}  # {symbol: position_data}

        # Lock to prevent concurrent entries for the same symbol
        self._position_locks: Dict[str, asyncio.Lock] = {}

        # Pending entries for conflict resolution (when multiple workers want same symbol)
        # {symbol: [(strategy, opportunity_data, pattern_completion, timestamp), ...]}
        self._pending_entries: Dict[str, list] = {} # This is now managed by EntryCompetition

        # 🔒 ORDER DEDUPLICATION: Prevent duplicate orders for the same symbol
        # {symbol: {'order_id': str, 'timestamp': datetime, 'quantity': int, 'status': str}}
        self._pending_orders: Dict[str, Dict[str, Any]] = {}
        self._order_cooldown_seconds = 10  # No reorder within 10 seconds for same symbol

        # Restore worker positions from database on init
        self._restore_worker_positions_from_db()

    async def execute_entry(self, symbol: str, action: str, quantity: int, order_type: str, limit_price: float = None) -> Dict[str, Any]:
        """
        Alias for enter_position to support BaseSwingWorker interface.
        Constructs a minimal opportunity_data to pass to enter_position.
        """
        self.logger.debug(f"🔄 execute_entry alias called for {symbol}")
        
        # Construct minimal opportunity data
        opportunity_data = {
            'symbol': symbol,
            'current_price': limit_price if limit_price else 0, # Best guess
            'force_gtc': True # Assume swing workers want GTC
        }
        
        # Call enter_position
        # We need to infer strategy name... BaseSwingWorker doesn't pass it here.
        # But BaseSwingWorker calls this on self.execution_engine.
        # We can use a generic name or try to inspect stack (too complex).
        # Better: BaseSwingWorker should use enter_position.
        # But since I'm patching the adapter:
        return await self.enter_position(symbol, "swing_worker", opportunity_data)

    async def enter_position(
        self,
        symbol: str,
        strategy: str,
        opportunity_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Entra en posición ejecutando orden directamente con el broker

        Args:
            symbol: Símbolo a tradear
            strategy: Nombre de la estrategia/worker
            opportunity_data: Datos de la oportunidad

        Returns:
            Dict con datos de posición si exitoso, None si falla
        """
        # Get or create lock for this symbol
        if symbol not in self._position_locks:
            self._position_locks[symbol] = asyncio.Lock()

        # Acquire lock to prevent concurrent entries
        async with self._position_locks[symbol]:
            # Check if position already exists (another worker may have entered while we waited)
            if symbol in self.worker_positions:
                existing_strategy = self.worker_positions[symbol].get('strategy')
                self.logger.warning(
                    f"🚫 {strategy}: BLOCKED {symbol} - position already exists "
                    f"(opened by {existing_strategy}). Only one worker per symbol allowed."
                )
                return None

            # Get pattern completion score from opportunity_data
            pattern_completion = opportunity_data.get('pattern_completion', 0.0)

            # DETERMINISTIC COMPETITION: Register entry and wait for winner selection
            # This replaces the old asyncio.sleep(0.05) race condition
            # Note: register_entry() is synchronous, not async
            competition_result = self.competition.register_entry(
                symbol=symbol,
                strategy=strategy,
                opportunity=opportunity_data,
                pattern_completion=pattern_completion
            )
            
            if competition_result != 'WINNER':
                self.logger.info(f"Entry competition lost for {symbol} ({strategy})")
                return None

            try:
                # 🎯 CRITICAL FIX: Get REAL current price from broker, not from opportunity
                # Opportunity price may be stale (scanner data from minutes ago)
                # Example: CMBM opportunity showed $2.95 but market was at $3.17 (7.5% slippage)
                current_price_opportunity = opportunity_data.get('current_price', 0)
                current_price = current_price_opportunity  # Fallback

                # 🛡️ PROTECTION 0: Check extended hours trading permission
                # Note: Extended hours check is already done at WorkerBasedStrategyEngine level
                # This is a secondary validation to ensure consistency
                extended_hours_enabled = getattr(self.config, 'enable_extended_hours_trading', False)

                if not extended_hours_enabled:
                    # If extended hours are globally disabled, only allow regular hours
                    current_session = self.extended_hours_manager.get_market_session()
                    if current_session != MarketSession.REGULAR:
                        session_name = current_session.name if hasattr(current_session, 'name') else str(current_session)
                        self.logger.warning(
                            f"🚫 {strategy}: REJECTED {symbol} - Extended hours disabled. "
                            f"Current session: {session_name}"
                        )
                        return None

                # 🛡️ PROTECTION 1: Get REAL market data (price + spread check)
                # CRITICAL: We MUST have a fresh price before entering. Stale prices can cause 10%+ slippage
                price_validated = False
                market_data_error = None
                market_data = None  # Initialize to avoid "referenced before assignment" error

                # NEW APPROACH: Use BatchPriceManager for guaranteed fresh prices
                try:
                    # Check if BatchPriceManager is available and has fresh price
                    if hasattr(self.broker, 'batch_price_manager') and self.broker.batch_price_manager:
                        bpm = self.broker.batch_price_manager

                        # Check if price is fresh (< 5 seconds old)
                        if bpm.is_price_fresh(symbol, max_age_seconds=5):
                            current_price = bpm.get_current_price(symbol)
                            if current_price > 0:
                                price_validated = True
                                self.logger.info(f"✅ {strategy}: Using FRESH price from BatchPriceManager: ${current_price:.2f}")

                                # Check for significant price difference (still log for monitoring)
                                if abs(current_price - current_price_opportunity) / current_price_opportunity > 0.02:
                                    self.logger.warning(
                                        f"⚠️ {strategy}: PRICE DIFFERENCE - Opportunity: ${current_price_opportunity:.2f}, "
                                        f"BatchPriceManager: ${current_price:.2f} ({((current_price - current_price_opportunity) / current_price_opportunity * 100):+.1f}%)"
                                    )
                            else:
                                self.logger.warning(f"⚠️ {strategy}: BatchPriceManager returned invalid price for {symbol}")
                        else:
                            self.logger.warning(f"⚠️ {strategy}: BatchPriceManager price for {symbol} is stale, falling back to get_market_data")

                    # Fallback to traditional get_market_data if BatchPriceManager not available or stale
                    if not price_validated:
                        # Check if broker has get_market_data method
                        if hasattr(self.broker, 'get_market_data'):
                            market_data = await self.broker.get_market_data(symbol)
                            if market_data and hasattr(market_data, 'bid') and hasattr(market_data, 'ask'):
                                # Update current_price from REAL market data (most accurate)
                                if market_data.last and market_data.last > 0:
                                    current_price = market_data.last
                                    price_validated = True
                                    if abs(current_price - current_price_opportunity) / current_price_opportunity > 0.02:
                                        self.logger.warning(
                                            f"⚠️ {strategy}: STALE PRICE DETECTED - Opportunity: ${current_price_opportunity:.2f}, "
                                            f"Market: ${current_price:.2f} ({((current_price - current_price_opportunity) / current_price_opportunity * 100):+.1f}%)"
                                        )
                                elif (market_data.bid + market_data.ask) / 2 > 0:
                                    # Fallback: use midpoint if last is not available
                                    current_price = (market_data.bid + market_data.ask) / 2
                                    price_validated = True
                                    if abs(current_price - current_price_opportunity) / current_price_opportunity > 0.02:
                                        self.logger.warning(
                                            f"⚠️ {strategy}: STALE PRICE DETECTED - Opportunity: ${current_price_opportunity:.2f}, "
                                            f"Bid/Ask midpoint: ${current_price:.2f} ({((current_price - current_price_opportunity) / current_price_opportunity * 100):+.1f}%)"
                                        )
                        else:
                            self.logger.warning(f"⚠️ {strategy}: Broker does not have get_market_data method")

                        # Check bid-ask spread to avoid illiquid symbols
                        if hasattr(market_data, 'bid') and hasattr(market_data, 'ask') and market_data.bid and market_data.ask and market_data.bid > 0:
                            spread_pct = ((market_data.ask - market_data.bid) / market_data.bid) * 100

                            # Reject if spread > 3% (illiquid symbol)
                            MAX_SPREAD_PCT = 3.0
                            if spread_pct > MAX_SPREAD_PCT:
                                self.logger.warning(
                                    f"🚫 {strategy}: REJECTED {symbol} - Bid-Ask spread too wide: "
                                    f"{spread_pct:.2f}% (bid=${market_data.bid:.2f}, ask=${market_data.ask:.2f}). "
                                    f"Max allowed: {MAX_SPREAD_PCT}%"
                                )
                                return None
                            else:
                                self.logger.debug(
                                    f"✅ {strategy}: {symbol} spread check passed: {spread_pct:.2f}% "
                                    f"(bid=${market_data.bid:.2f}, ask=${market_data.ask:.2f})"
                                )
                        else:
                            self.logger.warning(f"⚠️ {strategy}: Could not check bid-ask spread for {symbol} - market_data missing bid/ask")
                except Exception as e:
                    market_data_error = str(e)
                    self.logger.error(f"❌ {strategy}: Failed to get market data for {symbol}: {e}")

                # FALLBACK: If we couldn't validate price through BatchPriceManager or get_market_data,
                # use opportunity price but log warning
                if not price_validated:
                    # Check if opportunity price is recent (from scanner)
                    # Scanner publishes with timestamp, so price should be relatively fresh
                    self.logger.warning(
                        f"⚠️ {strategy}: Could not validate price through BatchPriceManager or broker. "
                        f"Using opportunity price: ${current_price_opportunity:.2f}. "
                        f"Error: {market_data_error or 'No fresh market data available'}"
                    )

                    # Use opportunity price as fallback (scanner just published it)
                    current_price = current_price_opportunity
                    price_validated = True  # Mark as validated (fallback accepted)

                    self.logger.info(
                        f"📍 {strategy}: Using scanner opportunity price for {symbol}: ${current_price:.2f} "
                        f"(fallback - price validation unavailable)"
                    )
                else:
                    self.logger.info(f"✅ {strategy}: Price validated for {symbol}: ${current_price:.2f}")

                self.logger.info(
                    f"🎯 {strategy}: Entering position for {symbol} @ ${current_price:.2f}"
                )

                # ============================================================================
                # ADAPTIVE POSITION SIZING: Use adaptive_risk_percent from worker (if available)
                # This implements exponential sizing based on EV, Quality, R:R
                # Tier A (exceptional): ~4-5% of capital
                # Tier B (high quality): ~2.5-3% of capital
                # Tier C (good): ~1.5-2% of capital
                # Tier D (marginal): ~0.5-1% of capital
                # ============================================================================

                adaptive_risk_pct = opportunity_data.get('adaptive_risk_percent', None)

                if adaptive_risk_pct is not None:
                    # USE ADAPTIVE RISK SIZING (new exponential system)
                    portfolio_value = getattr(self.risk_manager.config, 'portfolio_value', 2500)
                    position_value = portfolio_value * adaptive_risk_pct
                    quantity = int(position_value / current_price) if current_price > 0 else 0

                    trade_tier = opportunity_data.get('trade_tier', 'Unknown')

                    self.logger.info(
                        f"💰 {strategy}: ADAPTIVE SIZING for {symbol} (Tier {trade_tier}): "
                        f"Risk={adaptive_risk_pct*100:.2f}% -> ${position_value:.2f} -> {quantity} shares"
                    )
                else:
                    # FALLBACK: Use legacy risk manager calculation (if adaptive_risk not available)
                    self.logger.warning(
                        f"⚠️ {strategy}: adaptive_risk_percent not found for {symbol}, "
                        f"using legacy position sizing"
                    )

                    position_size_data = self.risk_manager.calculate_smallcap_position_size(
                        symbol=symbol,
                        current_price=current_price,
                        gap_percentage=opportunity_data.get('gap_percentage', 0.0),
                        volume_ratio=opportunity_data.get('volume_ratio', 1.0),
                        catalyst_type=opportunity_data.get('catalyst_type', 'OTHER'),
                        catalyst_strength=opportunity_data.get('catalyst_strength', 5)
                    )

                    if not position_size_data or position_size_data.get('recommended_shares', 0) <= 0:
                        self.logger.warning(f"⚠️ {strategy}: Invalid position size for {symbol}")
                        return None

                    quantity = position_size_data['recommended_shares']
                    position_value = quantity * current_price

                # Respect max_position_value limit from config
                max_position_value = getattr(self.risk_manager.config, 'max_position_value', 200.0)
                if position_value > max_position_value:
                    # Adjust quantity to fit within max_position_value using proper floor division
                    adjusted_quantity = math.floor(max_position_value / current_price)

                    # Additional validation: ensure final position value doesn't exceed limit
                    final_position_value = adjusted_quantity * current_price
                    if final_position_value > max_position_value:
                        # If still exceeds (due to floating point precision), reduce by one more share
                        adjusted_quantity -= 1
                        final_position_value = adjusted_quantity * current_price

                    self.logger.info(
                        f"⚙️ {strategy}: Adjusting position size for {symbol}: "
                        f"{quantity} shares (${position_value:.2f}) -> {adjusted_quantity} shares (${final_position_value:.2f}) "
                        f"to respect max_position_value=${max_position_value:.2f}"
                    )
                    quantity = adjusted_quantity
                    position_value = final_position_value

                if quantity <= 0:
                    self.logger.warning(f"⚠️ {strategy}: Adjusted quantity is 0 for {symbol}")
                    return None

                # Log final position size (different format for adaptive vs legacy)
                if adaptive_risk_pct is not None:
                    portfolio_value = getattr(self.risk_manager.config, 'portfolio_value', 2500)
                    position_percent = position_value / portfolio_value if portfolio_value > 0 else 0
                    self.logger.info(
                        f"📊 {strategy}: Final position for {symbol}: {quantity} shares "
                        f"(${position_value:.2f}, {position_percent:.2%} of ${portfolio_value:.0f} portfolio)"
                    )
                else:
                    # Legacy path
                    self.logger.info(
                        f"💰 {strategy}: Position size for {symbol}: {quantity} shares "
                        f"(${position_value:.2f}, {position_size_data['recommended_percent']:.1%} of portfolio)"
                    )

                # Detect current market session for order type selection
                current_session = self.extended_hours_manager.get_market_session()

                if current_session in [MarketSession.PREMARKET, MarketSession.AFTERHOURS]:
                    # 🛡️ PROTECTION: Use ADAPTIVE LIMIT orders for extended hours
                    # Based on user feedback: "limite overnight + day, adaptative"
                    order_type = OrderType.LIMIT
                    # Use adaptive limit price: ±0.5% range for better execution (reduced from 2%)
                    # REASONING: 2% was too wide, orders were not executing. 0.5% is more aggressive.
                    adaptive_range_pct = 0.005  # 0.5% range (was 0.02 = 2%)
                    # Determine side for price adjustment
                    order_side_str = opportunity_data.get('side', 'BUY')
                    if order_side_str == 'SELL':
                        raw_limit_price = current_price * (1 - adaptive_range_pct)  # -0.5% for sells (SHORT)
                    else:
                        raw_limit_price = current_price * (1 + adaptive_range_pct)  # +0.5% for buys

                    # 🛡️ PROTECTION: Apply IBKR tick size validation
                    limit_price = self._round_to_ibkr_tick_size(raw_limit_price)

                    # 🛡️ ADDITIONAL VALIDATION: Ensure limit price is reasonable
                    min_limit_price = current_price * 0.95  # Max 5% below current price
                    max_limit_price = current_price * 1.10  # Max 10% above current price

                    if limit_price < min_limit_price or limit_price > max_limit_price:
                        self.logger.warning(
                            f"⚠️ {strategy}: Invalid limit price ${limit_price:.2f} for {symbol} "
                            f"(current: ${current_price:.2f}, range: ${min_limit_price:.2f}-${max_limit_price:.2f}). "
                            f"Using market order instead."
                        )
                        order_type = OrderType.MARKET
                        limit_price = current_price
                    else:
                        self.logger.info(f"⏰ {strategy}: Extended hours detected - using ADAPTIVE LIMIT order @ ${limit_price:.2f} (raw: ${raw_limit_price:.4f}, tick-adjusted)")
                else:
                    # REGULAR HOURS - CHECK CONFIG FOR ORDER TYPE
                    # Default is MARKET, but user can override to LIMIT in config.ini [EXECUTION]
                    default_order_type = getattr(self.config, 'default_order_type', 'MARKET').upper()
                    
                    if default_order_type == 'LIMIT':
                        order_type = OrderType.LIMIT
                        # Get limit offset (default 0.5% if not set)
                        # We use getattr with fallback because config might be flattened or not have the key
                        limit_offset = float(getattr(self.config, 'limit_price_offset_pct', 0.005))
                        
                        # Calculate limit price (Current + Offset) to ensure fill (Marketable Limit)
                        # For BUY orders, Limit Price > Current Price helps ensure fill while protecting against massive spikes
                        raw_limit_price = current_price * (1 + limit_offset)
                        
                        # Apply tick rounding
                        limit_price = self._round_to_ibkr_tick_size(raw_limit_price)
                        
                        self.logger.info(f"⏰ {strategy}: Regular hours - using LIMIT order @ ${limit_price:.2f} (offset {limit_offset*100:.1f}%)")
                    else:
                        order_type = OrderType.MARKET
                        limit_price = current_price
                        self.logger.debug(f"⏰ {strategy}: Regular hours - using MARKET order")

                # Create order with appropriate type and TIF (Time In Force)
                # 🛡️ PROTECTION: Use OVERNIGHT + DAY TIF for extended hours as suggested by user
                # Also respect force_gtc flag from opportunity_data (e.g. for Swing trades)
                force_gtc = opportunity_data.get('force_gtc', False)
                
                if current_session in [MarketSession.PREMARKET, MarketSession.AFTERHOURS] or force_gtc:
                    # Set Time In Force to GTC (Good Till Cancelled) for overnight + day execution
                    tif = "GTC"  # Good Till Cancelled - stays active until filled or cancelled
                    self.logger.info(f"⏰ {strategy}: Using GTC (Good Till Cancelled) TIF (Session: {current_session.name}, Force GTC: {force_gtc})")
                else:
                    tif = "DAY"  # Regular hours: Day order

                # Determine order side from opportunity_data (defaults to BUY for backwards compatibility)
                order_side_str = opportunity_data.get('side', 'BUY')
                order_side = OrderSide.SELL if order_side_str == 'SELL' else OrderSide.BUY

                order = Order(
                    order_id=f"{strategy}_{symbol}_{int(self.clock.now().timestamp())}",
                    symbol=symbol,
                    side=order_side,
                    quantity=quantity,
                    order_type=order_type,
                    price=limit_price,
                    tif=tif  # Add Time In Force parameter
                )


                # 🛡️ PROTECTION 2: Check for duplicate orders (prevent ECX-style double execution)
                if symbol in self._pending_orders:
                    pending = self._pending_orders[symbol]
                    time_since_last = (self.clock.now() - pending['timestamp']).total_seconds()

                    if time_since_last < self._order_cooldown_seconds:
                        self.logger.warning(
                            f"🚫 {strategy}: BLOCKED duplicate order for {symbol} - "
                            f"Order {pending['order_id']} sent {time_since_last:.1f}s ago (cooldown: {self._order_cooldown_seconds}s). "
                            f"Waiting for execution confirmation before retry."
                        )
                        return None
                    else:
                        # Cooldown expired - check if previous order actually executed
                        if pending['status'] in ['PENDING', 'SUBMITTED']:
                            # Previous order may have executed without confirmation
                            positions = await self.broker.get_positions()
                            if symbol in positions and positions[symbol].quantity > 0:
                                self.logger.warning(
                                    f"🚫 {strategy}: BLOCKED duplicate order for {symbol} - "
                                    f"Position already exists ({positions[symbol].quantity} shares). "
                                    f"Previous order {pending['order_id']} likely executed."
                                )
                                # Clean up pending order
                                del self._pending_orders[symbol]
                                return None

                # Validate order with risk manager
                is_valid = await self.risk_manager.validate_order(order)
                if not is_valid:
                    self.logger.warning(f"🚫 {strategy}: Order rejected by risk manager for {symbol}")
                    return None

                # Calculate entry commission BEFORE execution
                entry_commission, commission_breakdown = IBKRCommissionCalculator.calculate_commission(
                    quantity=quantity,
                    price=current_price,
                    side='BUY',
                    plan='tiered'
                )

                self.logger.debug(
                    f"💵 {strategy}: Entry commission for {symbol}: ${entry_commission:.2f} "
                    f"({commission_breakdown.get('description', 'tiered')})"
                )

                # Register order as pending BEFORE sending to IBKR
                self._pending_orders[symbol] = {
                    'order_id': None,  # Will be updated after place_order
                    'timestamp': self.clock.now(),
                    'quantity': quantity,
                    'status': 'PENDING'
                }

                # Execute order directly with broker
                order_id = await self.broker.place_order(order)

                if not order_id:
                    self.logger.warning(f"⚠️ {strategy}: Order execution failed for {symbol}")
                    # Clean up pending order on failure
                    if symbol in self._pending_orders:
                        del self._pending_orders[symbol]
                    return None

                # Update pending order with actual order_id
                self._pending_orders[symbol]['order_id'] = str(order_id)
                self._pending_orders[symbol]['status'] = 'SUBMITTED'
                self.logger.info(f"📝 {strategy}: Registered pending order {order_id} for {symbol} (anti-duplicate protection active)")

                # ============================================================
                # 🔧 FIX: Save trade IMMEDIATELY with expected price
                # This allows ExecutionTracker to find and update the trade
                # ============================================================
                trade_id = str(order_id)

                # Build initial trade data with EXPECTED price
                initial_trade_data = {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'strategy': strategy,
                    'side': 'BUY',
                    'quantity': quantity,
                    'entry_price': current_price,  # Expected price
                    'entry_time': self.clock.now(),
                    'status': 'PENDING',  # Will change to OPEN after confirmation
                    'commission': entry_commission,
                    'broker_order_id_entry': str(order_id),
                    'notes': f"Worker entry: {opportunity_data.get('catalyst_type', 'N/A')}"
                }

                # Add opportunity metrics
                if opportunity_data.get('quality_score') is not None:
                    quality = float(opportunity_data['quality_score'])
                    initial_trade_data['confidence'] = quality
                    initial_trade_data['strategy_confidence'] = quality

                if opportunity_data.get('volume_ratio') is not None:
                    initial_trade_data['volume_ratio'] = float(opportunity_data['volume_ratio'])

                if opportunity_data.get('gap_percentage') is not None:
                    initial_trade_data['gap_percentage'] = float(opportunity_data['gap_percentage'])

                # Trade Session
                current_session = self.extended_hours_manager.get_market_session()
                if current_session == MarketSession.PREMARKET:
                    initial_trade_data['trade_session'] = 'PRE_MARKET'
                elif current_session == MarketSession.REGULAR:
                    initial_trade_data['trade_session'] = 'REGULAR'
                elif current_session == MarketSession.AFTERHOURS:
                    initial_trade_data['trade_session'] = 'AFTER_HOURS'
                else:
                    initial_trade_data['trade_session'] = 'CLOSED'

                # CRITICAL FIX: Add missing fields to initial trade data to avoid NULLs
                # Confidence
                if opportunity_data.get('quality_score') is not None:
                    initial_trade_data['confidence'] = float(opportunity_data['quality_score'])
                    initial_trade_data['strategy_confidence'] = float(opportunity_data['quality_score'])
                else:
                    initial_trade_data['confidence'] = 70.0
                    initial_trade_data['strategy_confidence'] = 70.0

                # Market Context
                if opportunity_data.get('market_context') is not None:
                    initial_trade_data['market_context'] = str(opportunity_data['market_context'])
                else:
                    initial_trade_data['market_context'] = 'NEUTRAL'

                # Market Context Score
                if opportunity_data.get('market_context_score') is not None:
                    initial_trade_data['market_context_score'] = float(opportunity_data['market_context_score'])
                else:
                    initial_trade_data['market_context_score'] = 60.0

                # Signal Strength
                if opportunity_data.get('signal_strength') is not None:
                    initial_trade_data['signal_strength'] = float(opportunity_data['signal_strength'])
                else:
                    initial_trade_data['signal_strength'] = initial_trade_data['confidence']

                # CRITICAL FIX: Save exit parameters to DB columns (persistence)
                # Stop Loss & Take Profit
                if opportunity_data.get('stop_loss_pct') is not None:
                    initial_trade_data['stop_loss_pct'] = float(opportunity_data['stop_loss_pct'])
                if opportunity_data.get('take_profit_pct') is not None:
                    initial_trade_data['take_profit_pct'] = float(opportunity_data['take_profit_pct'])
                
                # Dynamic targets (prices)
                if opportunity_data.get('stop_loss') is not None:
                    initial_trade_data['stop_loss_price'] = float(opportunity_data['stop_loss'])
                if opportunity_data.get('take_profit') is not None:
                    initial_trade_data['take_profit_price'] = float(opportunity_data['take_profit'])

                # Trailing Stop (Handle both naming conventions)
                # Activation
                if opportunity_data.get('trailing_activation_pct') is not None:
                    initial_trade_data['trailing_activation_pct'] = float(opportunity_data['trailing_activation_pct'])
                elif opportunity_data.get('trailing_activation') is not None:
                     # Some strategies might pass '0.08' as 'trailing_activation'
                    initial_trade_data['trailing_activation_pct'] = float(opportunity_data['trailing_activation'])
                
                # Distance
                if opportunity_data.get('trailing_distance_pct') is not None:
                    initial_trade_data['trailing_distance_pct'] = float(opportunity_data['trailing_distance_pct'])
                elif opportunity_data.get('trailing_distance') is not None:
                    initial_trade_data['trailing_distance_pct'] = float(opportunity_data['trailing_distance'])

                # Save trade BEFORE waiting for execution
                self.db_manager.save_trade(initial_trade_data)
                self.logger.info(f"💾 {strategy}: Trade {trade_id} saved with expected price ${current_price:.2f} (status=PENDING)")

                # Wait for execution confirmation
                execution_confirmed = await self._wait_for_execution_confirmation(order_id, symbol, quantity, timeout=30.0)

                if not execution_confirmed:
                    self.logger.error(f"❌ {strategy}: Execution not confirmed for {symbol} within timeout")
                    try:
                        await self.broker.cancel_order(order_id)
                        self.logger.info(f"🛡️ {strategy}: Cancelled unconfirmed order {order_id} for {symbol}")
                    except Exception as e:
                        self.logger.warning(f"⚠️ Failed to cancel unconfirmed order {order_id}: {e}")

                    # Clean up pending order (not executed)
                    if symbol in self._pending_orders:
                        del self._pending_orders[symbol]
                        self.logger.debug(f"🧹 Cleaned up pending order for {symbol} (not executed)")

                    return None

                # Mark order as executed in pending tracker
                if symbol in self._pending_orders:
                    self._pending_orders[symbol]['status'] = 'EXECUTED'
                    self.logger.debug(f"✅ Marked pending order {order_id} for {symbol} as EXECUTED")

                # ============================================================
                # 🎯 SIMPLE & RELIABLE: Get actual fill price from IBKR positions
                # Poll up to 30 seconds for IBKR to update positions
                # ============================================================
                actual_fill_price = None
                max_wait_seconds = 30
                poll_interval = 1.0  # Check every 1 second
                elapsed = 0

                self.logger.info(f"⏳ {strategy}: Waiting for IBKR to update positions for {symbol}...")

                # Force cache invalidation after trade execution
                if hasattr(self.broker, 'smart_position_cache') and self.broker.smart_position_cache:
                    self.broker.smart_position_cache.clear_cache()
                    self.logger.debug(f"🔄 {strategy}: Forced position cache clear for fresh data")

                # PAPER MODE DETECTION: Skip IBKR position wait if in paper trading
                is_paper_mode = (hasattr(self.broker, 'paper_trading_mode') and self.broker.paper_trading_mode) or \
                                (hasattr(self.broker, 'is_paper_trading') and self.broker.is_paper_trading)
                if is_paper_mode:
                    self.logger.debug(f"📄 {strategy}: Paper trading mode detected - using simulated price")
                    actual_fill_price = current_price  # Use simulated price directly
                    max_wait_seconds = 0  # Skip wait loop

                while elapsed < max_wait_seconds and not actual_fill_price:
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval

                    # Get actual price directly from IBKR positions - THIS IS THE SOURCE OF TRUTH
                    try:
                        positions = await self.broker.get_positions()
                        if symbol in positions:
                            pos = positions[symbol]
                            # Support both LONG (positive quantity) and SHORT (negative quantity)
                            # For LONG: pos.quantity >= quantity
                            # For SHORT: pos.quantity <= -quantity (quantity is negative for SHORT)
                            has_position = (
                                (order_side == OrderSide.BUY and pos.quantity >= quantity) or
                                (order_side == OrderSide.SELL and pos.quantity <= -quantity)
                            )
                            if has_position and pos.avg_price > 0:
                                actual_fill_price = pos.avg_price
                                self.logger.info(
                                    f"✅ {strategy}: Got REAL fill price from IBKR positions after {elapsed:.1f}s: "
                                    f"{symbol} @ ${actual_fill_price:.2f} (qty: {pos.quantity}, side: {order_side.name})"
                                )
                                break
                    except Exception as e:
                        self.logger.debug(f"Position check attempt {elapsed:.0f}s: {e}")

                # Fallback: use expected price if positions not available after max wait
                if not actual_fill_price:
                    actual_fill_price = current_price
                    self.logger.error(
                        f"❌ {strategy}: Could not get actual fill price from IBKR positions for {symbol} "
                        f"after {max_wait_seconds}s, using expected price ${current_price:.2f} (MAY BE INACCURATE)"
                    )

                # Calculate slippage
                entry_slippage_pct = 0.0
                if actual_fill_price != current_price:
                    entry_slippage_pct = ((actual_fill_price - current_price) / current_price) * 100
                    self.logger.info(
                        f"💱 {strategy}: {symbol} slippage: {entry_slippage_pct:+.2f}% "
                        f"(expected ${current_price:.2f}, actual ${actual_fill_price:.2f})"
                    )

                # Use actual fill price for all calculations
                current_price = actual_fill_price
                trade_id = order_id

                # Build trade data with REAL price
                trade_data = {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'strategy': strategy,
                    'side': 'BUY',
                    'quantity': quantity,
                    'entry_price': actual_fill_price,  # ✅ REAL PRICE FROM IBKR
                    'entry_slippage_pct': entry_slippage_pct,
                    'entry_time': self.clock.now(),
                    'status': 'OPEN',
                    'commission': entry_commission,
                    'broker_order_id_entry': str(order_id),
                    'notes': f"Worker entry: {opportunity_data.get('catalyst_type', 'N/A')}"
                }

                # Add opportunity metrics for TradeTally analysis
                if opportunity_data.get('quality_score') is not None:
                    quality = float(opportunity_data['quality_score'])
                    trade_data['confidence'] = quality
                    trade_data['strategy_confidence'] = quality

                if opportunity_data.get('volume_ratio') is not None:
                    trade_data['volume_ratio'] = float(opportunity_data['volume_ratio'])

                if opportunity_data.get('gap_percentage') is not None:
                    trade_data['gap_percentage'] = float(opportunity_data['gap_percentage'])

                # Trade Session
                current_session = self.extended_hours_manager.get_market_session()
                if current_session == MarketSession.PREMARKET:
                    trade_data['trade_session'] = 'PRE_MARKET'
                elif current_session == MarketSession.REGULAR:
                    trade_data['trade_session'] = 'REGULAR'
                elif current_session == MarketSession.AFTERHOURS:
                    trade_data['trade_session'] = 'AFTER_HOURS'
                else:
                    trade_data['trade_session'] = 'CLOSED'

                # Market Context Score
                if opportunity_data.get('market_context_score') is not None:
                    trade_data['market_context_score'] = float(opportunity_data['market_context_score'])
                else:
                    quality = opportunity_data.get('quality_score', 70)
                    trade_data['market_context_score'] = min(100, max(0, quality))

                # Signal Strength
                if opportunity_data.get('signal_strength') is not None:
                    trade_data['signal_strength'] = float(opportunity_data['signal_strength'])
                elif opportunity_data.get('strength') is not None:
                    trade_data['signal_strength'] = float(opportunity_data['strength'])
                else:
                    quality = opportunity_data.get('quality_score', 70)
                    trade_data['signal_strength'] = quality

                # Market Context
                if opportunity_data.get('market_context') is not None:
                    trade_data['market_context'] = str(opportunity_data['market_context'])
                elif opportunity_data.get('market_sentiment') is not None:
                    trade_data['market_context'] = str(opportunity_data['market_sentiment'])
                else:
                    trade_data['market_context'] = 'NEUTRAL'

                # CRITICAL FIX: Ensure confidence is always set
                if 'confidence' not in trade_data:
                     trade_data['confidence'] = 70.0
                     trade_data['strategy_confidence'] = 70.0

                # CRITICAL FIX: Ensure market_context_score is always set
                if 'market_context_score' not in trade_data:
                    trade_data['market_context_score'] = 60.0

                # ============================================================================
                # ADAPTIVE RISK ANALYTICS: Store EV, R:R, Trade Tier, Adaptive Risk%
                # These fields enable post-trade analysis by tier and optimization
                # ============================================================================
                if opportunity_data.get('expected_value_pct') is not None:
                    trade_data['expected_value_pct'] = float(opportunity_data['expected_value_pct'])

                if opportunity_data.get('risk_reward') is not None:
                    trade_data['risk_reward_ratio'] = float(opportunity_data['risk_reward'])

                if opportunity_data.get('win_probability') is not None:
                    trade_data['win_probability'] = float(opportunity_data['win_probability'])

                if opportunity_data.get('trade_tier') is not None:
                    trade_data['trade_tier'] = str(opportunity_data['trade_tier'])

                if opportunity_data.get('adaptive_risk_percent') is not None:
                    trade_data['adaptive_risk_pct'] = float(opportunity_data['adaptive_risk_percent'])

                # Trading Horizon & Position Metadata (NEW)
                position_metadata = opportunity_data.get('position_metadata', {})
                if position_metadata:
                    # Store trading horizon
                    trading_horizon = position_metadata.get('trading_horizon', 'INTRADAY')
                    trade_data['trading_horizon'] = str(trading_horizon)

                    # Store expected hold time
                    expected_hold_hours = position_metadata.get('expected_hold_hours', 6.0)
                    trade_data['expected_hold_hours'] = float(expected_hold_hours)

                # Fallback: Check top-level opportunity data for horizon (used by MidCap Worker)
                if 'trading_horizon' not in trade_data and 'trading_horizon' in opportunity_data:
                    trade_data['trading_horizon'] = str(opportunity_data['trading_horizon'])

                # Capture EOD_safe flag (Critical for Swing Trades)
                if 'EOD_safe' in opportunity_data:
                    trade_data['EOD_safe'] = 1 if opportunity_data['EOD_safe'] else 0
                
                # Capture Worker Name
                trade_data['worker_name'] = strategy # Strategy arg is effectively the worker name

                # Store daily analysis metadata (if available) - Priority: position_metadata > daily_potential
                
                # 1. From position_metadata (explicitly passed by worker)
                if 'daily_rsi' in position_metadata:
                    trade_data['daily_rsi'] = float(position_metadata['daily_rsi'])
                if 'distance_to_resistance_pct' in position_metadata:
                    trade_data['distance_to_resistance_pct'] = float(position_metadata['distance_to_resistance_pct'])
                if 'resistance_price' in position_metadata:
                    trade_data['resistance_price'] = float(position_metadata['resistance_price'])

                # 2. From daily_potential (calculated by helper in BaseWorkerLogic)
                daily_potential = opportunity_data.get('daily_potential', {})
                if daily_potential:
                    if 'daily_rsi' not in trade_data and 'rsi_daily' in daily_potential:
                         trade_data['daily_rsi'] = float(daily_potential['rsi_daily'])
                    
                    if 'distance_to_resistance_pct' not in trade_data:
                        # Try 'distance_to_resistance' (legacy/context engine)
                        if 'distance_to_resistance' in daily_potential:
                             val = daily_potential['distance_to_resistance']
                             # normalized to pct if needed, usually comes as scalar e.g. 5.0 for 5%
                             # ContextEngine usually returns it as %
                             trade_data['distance_to_resistance_pct'] = float(val)

                    if 'resistance_price' not in trade_data:
                         # Try 'resistance_level' (legacy/context engine)
                         if 'resistance_level' in daily_potential:
                             trade_data['resistance_price'] = float(daily_potential['resistance_level'])
                         elif 'smart_resistance' in daily_potential and daily_potential['smart_resistance'].get('level'):
                             trade_data['resistance_price'] = float(daily_potential['smart_resistance']['level'])

                # TP/SL percentages
                if opportunity_data.get('take_profit_pct'):
                    trade_data['take_profit_pct'] = float(opportunity_data['take_profit_pct'])
                if opportunity_data.get('stop_loss_pct'):
                    trade_data['stop_loss_pct'] = float(opportunity_data['stop_loss_pct'])

                # ============================================================
                # 🔧 FIX: UPDATE existing trade with actual fill price
                # Trade was already saved with expected price (status=PENDING)
                # Now update with actual price and change status to OPEN
                # save_trade() handles updates if trade_id already exists
                # ============================================================

                # Update entry_price with actual fill price and change status to OPEN
                trade_data['entry_price'] = actual_fill_price  # Update to actual price
                trade_data['status'] = 'OPEN'  # Change from PENDING to OPEN

                # Save/Update the trade in database
                self.db_manager.save_trade(trade_data)
                
                # TRANSACTIONAL FILL MATCHING: Check if we have pending fills for this symbol
                # This handles race condition where fill arrived before trade was committed
                if hasattr(self, 'execution_tracker'):
                    self.execution_tracker.process_pending_fills(symbol)
                    
                self.logger.info(f"✅ {strategy}: Trade {trade_id} UPDATED with actual fill price ${actual_fill_price:.2f} (slippage: {entry_slippage_pct:+.2f}%, status=OPEN)")

                # ========================================================================
                # OBSOLETE CODE BLOCK - COMMENTED OUT TO PREVENT DUPLICATE DATABASE OPERATIONS
                # This block was duplicating the save_trade() logic above and could cause:
                # - Double database writes (performance impact)
                # - Potential data inconsistencies
                # - Race conditions in concurrent operations
                #
                # The DatabaseManager.save_trade() method already handles INSERT/UPDATE logic properly
                # ========================================================================
                """
                try:
                    import sqlite3
                    with sqlite3.connect(self.db_manager.db_path) as conn:
                        cursor = conn.cursor()

                        # Build UPDATE query dynamically based on what's in trade_data
                        set_clauses = []
                        values = []
                        for key, value in trade_data.items():
                            if key != 'trade_id':  # Don't update trade_id
                                set_clauses.append(f"{key} = ?")
                                values.append(value)

                        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                        values.append(trade_id)  # For WHERE clause

                        query = f"UPDATE trades SET {', '.join(set_clauses)} WHERE trade_id = ?"
                        cursor.execute(query, values)
                        conn.commit()

                        self.logger.debug(f"💾 {strategy}: Trade {trade_id} updated to OPEN with full metadata (order_id={order_id})")
                except Exception as e:
                    self.logger.error(f"❌ Failed to update trade {trade_id}: {e}")
                    # Try fallback: save as new trade if update failed
                    trade_data['trade_id'] = trade_id
                    trade_data['symbol'] = symbol
                    trade_data['strategy'] = strategy
                    trade_data['side'] = 'BUY'
                    trade_data['quantity'] = quantity
                    trade_data['entry_price'] = current_price
                    trade_data['expected_entry_price'] = current_price
                    trade_data['entry_slippage_pct'] = 0.0
                    trade_data['entry_time'] = self.clock.now()
                    trade_data['commission'] = entry_commission
                    trade_data['broker_order_id_entry'] = str(order_id)
                    self.db_manager.save_trade(trade_data)
                    self.logger.warning(f"⚠️ {strategy}: Fallback save_trade() used for {trade_id}")
                """

                # Track position with commission and entry_time
                position_data = {
                    'symbol': symbol,
                    'strategy': strategy,
                    'entry_price': actual_fill_price,  # Uses REAL fill price from IBKR positions
                    'quantity': quantity,
                    'order_id': order_id,
                    'trade_id': trade_id,
                    'entry_time': self.clock.now(),
                    'entry_commission': entry_commission,
                    'opportunity_data': opportunity_data
                }
                self.worker_positions[symbol] = position_data

                # 🧹 Clean up pending order (successfully executed and tracked)
                if symbol in self._pending_orders:
                    del self._pending_orders[symbol]
                    self.logger.debug(f"🧹 Cleaned up pending order for {symbol} (position successfully opened)")

                self.logger.info(
                    f"✅ {strategy}: Position opened - {symbol} @ ${actual_fill_price:.2f} x {quantity} shares "
                    f"(Trade ID: {trade_id[:16]}...)"
                )

                # Send Telegram notification
                try:
                    # Calculate confidence from opportunity data
                    confidence = opportunity_data.get('quality_score', 70.0)
                    if confidence <= 1.0:
                        confidence = confidence * 100

                    # Format strategy name for display
                    formatted_strategy = self._format_strategy_name(strategy)

                    # Determine system mode
                    implicit_event = opportunity_data.get('implicit_event')
                    system_mode = "🔬 EVENT-DRIVEN" if implicit_event else "📋 LEGACY"

                    # Determine worker type (Smallcap vs Midcap)
                    price = actual_fill_price
                    worker_type = ""
                    if strategy == "daily_plays":
                        if price <= 10.0:
                            worker_type = " (Smallcap $1-$10)"
                        else:
                            worker_type = " (Midcap $10-$100)"

                    # Build notification message with trading horizon info
                    notification = (
                        f"🎯 ENTRY: {symbol} @ ${actual_fill_price:.2f}\n"
                        f"Strategy: {formatted_strategy}{worker_type}\n"
                        f"Mode: {system_mode}\n"
                        f"Quantity: {quantity} shares (${position_value:.2f})\n"
                        f"Confidence: {confidence:.0f}%\n"
                        f"Commission: ${entry_commission:.2f}"
                    )

                    # Add catalyst info if available
                    catalyst = opportunity_data.get('catalyst_type')
                    if catalyst and catalyst != 'N/A':
                        notification += f"\nCatalyst: {catalyst}"

                    # Add implicit event data if available (EVENT-DRIVEN mode)
                    if implicit_event:
                        event_score = implicit_event.get('score', 0)
                        event_expansion = implicit_event.get('expansion', False)
                        event_gap = implicit_event.get('gap_pct', 0.0)
                        event_vol = implicit_event.get('volume_ratio', 0.0)

                        expansion_emoji = "✅" if event_expansion else "⚠️"
                        notification += f"\n📊 Event: {event_score}/4 | Gap: {event_gap:.1f}% | Vol: {event_vol:.1f}x | Exp: {expansion_emoji}"

                    # Add trading horizon info (from position_metadata)
                    position_metadata = opportunity_data.get('position_metadata', {})
                    if position_metadata:
                        trading_horizon = position_metadata.get('trading_horizon', 'N/A')
                        expected_hold = position_metadata.get('expected_hold_hours', 0)

                        if trading_horizon != 'N/A':
                            # Format horizon display
                            horizon_emoji = {
                                'SCALP': '⚡',
                                'INTRADAY': '📊',
                                'SWING_SHORT': '📈',
                                'SWING': '🚀'
                            }.get(trading_horizon, '📊')

                            notification += f"\n{horizon_emoji} Horizon: {trading_horizon}"
                            if expected_hold > 0:
                                notification += f" ({expected_hold:.1f}h)"

                    # Add TP/SL info if available
                    take_profit_pct = opportunity_data.get('take_profit_pct', 0)
                    stop_loss_pct = opportunity_data.get('stop_loss_pct', 0)

                    if take_profit_pct > 0 or stop_loss_pct > 0:
                        notification += "\n"
                        if take_profit_pct > 0:
                            tp_price = actual_fill_price * (1 + take_profit_pct / 100)
                            notification += f"\n🎯 TP: {take_profit_pct:.1f}% (${tp_price:.2f})"
                        if stop_loss_pct > 0:
                            sl_price = actual_fill_price * (1 - stop_loss_pct / 100)
                            notification += f"\n🛡️ SL: {stop_loss_pct:.1f}% (${sl_price:.2f})"

                    self._send_telegram(notification)
                    self.logger.debug(f"📨 Telegram notification sent for {symbol} entry")

                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to send Telegram notification: {e}")

                return position_data

            except Exception as e:
                self.logger.error(f"❌ {strategy}: Error entering position for {symbol}: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                return None

    async def exit_position(
        self,
        symbol: str,
        reason: str = "Worker requested exit"
    ) -> bool:
        """
        Sale de posición ejecutando orden de venta directamente con el broker

        Args:
            symbol: Símbolo a cerrar
            reason: Razón de salida

        Returns:
            True si exitoso, False si falla
        """
        try:
            self.logger.info(f"🚪 Exiting {symbol}: {reason}")

            # Get position data
            position = self.worker_positions.get(symbol)
            if not position:
                self.logger.warning(f"⚠️ No worker position found for {symbol}")
                return False

            quantity = position.get('quantity', 0)
            if quantity <= 0:
                self.logger.warning(f"⚠️ Invalid quantity for {symbol}")
                return False

            # Get current price
            current_price = await self.get_current_price(symbol)

            if current_price <= 0:
                self.logger.error(f"❌ Invalid exit price for {symbol}: {current_price}")
                return False

            # Detect current market session for order type selection
            strategy_name = position.get('strategy', 'unknown')
            current_session = self.extended_hours_manager.get_market_session()

            if current_session in [MarketSession.PREMARKET, MarketSession.AFTERHOURS]:
                # 🛡️ PROTECTION: Use ADAPTIVE LIMIT orders for extended hours exits
                # Based on user feedback: "limite overnight + day, adaptative"
                order_type = OrderType.LIMIT
                # Use adaptive limit price: ±2% range for better execution
                adaptive_range_pct = 0.02  # 2% range
                raw_limit_price = current_price * (1 - adaptive_range_pct)  # -2% for sells

                # 🛡️ PROTECTION: Apply IBKR tick size validation
                limit_price = self._round_to_ibkr_tick_size(raw_limit_price)

                # 🛡️ ADDITIONAL VALIDATION: Ensure limit price is reasonable for exits
                min_limit_price = current_price * 0.90  # Max 10% below current price (for aggressive exits)
                max_limit_price = current_price * 1.05  # Max 5% above current price

                if limit_price < min_limit_price or limit_price > max_limit_price:
                    self.logger.warning(
                        f"⚠️ {strategy_name}: Invalid exit limit price ${limit_price:.2f} for {symbol} "
                        f"(current: ${current_price:.2f}, range: ${min_limit_price:.2f}-${max_limit_price:.2f}). "
                        f"Using market order instead."
                    )
                    order_type = OrderType.MARKET
                    limit_price = current_price
                else:
                    self.logger.info(f"⏰ Extended hours detected - using ADAPTIVE LIMIT exit order @ ${limit_price:.2f} (raw: ${raw_limit_price:.4f}, tick-adjusted)")
            else:
                order_type = OrderType.MARKET
                limit_price = current_price

            # Create exit order with TIF (Time In Force)
            # 🛡️ PROTECTION: Use OVERNIGHT + DAY TIF for extended hours exits
            if current_session in [MarketSession.PREMARKET, MarketSession.AFTERHOURS]:
                # Set Time In Force to GTC (Good Till Cancelled) for overnight + day execution
                tif = "GTC"  # Good Till Cancelled - stays active until filled or cancelled
                self.logger.info(f"⏰ Using GTC (Good Till Cancelled) TIF for extended hours exit")
            else:
                tif = "DAY"  # Regular hours: Day order

            order = Order(
                order_id=f"{strategy_name}_{symbol}_exit_{int(self.clock.now().timestamp())}",
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=quantity,
                order_type=order_type,
                price=limit_price,
                tif=tif  # Add Time In Force parameter
            )

            # Calculate exit commission BEFORE execution
            exit_commission, commission_breakdown = IBKRCommissionCalculator.calculate_commission(
                quantity=quantity,
                price=current_price,
                side='SELL',
                plan='tiered'
            )

            self.logger.debug(
                f"💵 Exit commission for {symbol}: ${exit_commission:.2f} "
                f"({commission_breakdown.get('description', 'tiered')})"
            )

            # Get trade_id from position for database update
            trade_id = position.get('trade_id')
            if not trade_id:
                self.logger.warning(f"⚠️ No trade_id found for {symbol}, cannot update database")
                # Still try to execute exit even without trade_id
                exit_order_id = await self.broker.place_order(order)
                if exit_order_id:
                    del self.worker_positions[symbol]
                    return True
                return False

            entry_price = position.get('entry_price', current_price)
            entry_commission = position.get('entry_commission', 0)

            # Note: entry_price comes from position tracking, which was set from IBKR positions
            # during entry (lines 360-417). No need to re-validate with ExecutionTracker.

            # Calculate gross and net PnL
            gross_pnl = (current_price - entry_price) * quantity
            total_commission = entry_commission + exit_commission
            net_pnl = gross_pnl - total_commission

            # Calculate PnL percentage
            pnl_pct = (gross_pnl / (entry_price * quantity) * 100) if entry_price > 0 else 0

            # Get entry_time from position data (stored during entry)
            entry_time = position.get('entry_time')
            if not entry_time:
                # Fallback: try to get from database
                try:
                    existing_trades = self.db_manager.get_trades(symbol=symbol, limit=1)
                    if existing_trades:
                        entry_time = existing_trades.iloc[0]['entry_time']
                except Exception as e:
                    self.logger.warning(f"Could not retrieve entry_time for {symbol}: {e}")
                    entry_time = datetime.now()  # Last resort fallback

            # Execute exit order with broker
            exit_order_id = await self.broker.place_order(order)

            if not exit_order_id:
                self.logger.warning(f"⚠️ Exit order execution failed for {symbol}")
                return False

            # ============================================================
            # 🎯 SIMPLE & RELIABLE: Get actual exit price from IBKR order status
            # Poll up to 30 seconds for IBKR to confirm order filled
            # ============================================================
            actual_exit_price = None
            max_wait_seconds = 30
            poll_interval = 1.0  # Check every 1 second
            elapsed = 0

            self.logger.info(f"⏳ Waiting for IBKR to confirm exit for {symbol}...")

            while elapsed < max_wait_seconds and not actual_exit_price:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                # PRIORITY 1: Get actual fill price from order status (most accurate)
                try:
                    order_status = await self.broker.get_order_status(str(exit_order_id))
                    if order_status and order_status.get('status') == 'FILLED':
                        avg_fill_price = order_status.get('avg_fill_price', 0)
                        if avg_fill_price > 0:
                            actual_exit_price = avg_fill_price
                            self.logger.info(
                                f"✅ {symbol} exit REAL fill price from order status after {elapsed:.1f}s: "
                                f"${actual_exit_price:.2f} (order {exit_order_id})"
                            )
                            break
                except Exception as e:
                    self.logger.debug(f"Order status check attempt {elapsed:.0f}s: {e}")

                # PRIORITY 2: Verify position is closed AND order filled (fallback confirmation)
                if not actual_exit_price:
                    try:
                        # Check order status first to avoid false positives from pending orders
                        order_status = await self.broker.get_order_status(str(exit_order_id))
                        order_state = order_status.get('status', '') if order_status else ''

                        # Only confirm closure if order is FILLED or position is actually gone
                        if order_state == 'FILLED':
                            # Order filled but no avgFillPrice yet, use current_price
                            actual_exit_price = current_price
                            self.logger.warning(
                                f"⚠️ {symbol} exit FILLED after {elapsed:.1f}s, "
                                f"using estimated price ${actual_exit_price:.2f} (no avgFillPrice yet)"
                            )
                            break
                        elif order_state in ('PENDING', 'PRESUBMITTED', 'SUBMITTED'):
                            # Order still pending - DO NOT mark as closed
                            self.logger.debug(f"Exit order {exit_order_id} still {order_state}, waiting...")
                        else:
                            # Check position as additional confirmation
                            positions = await self.broker.get_positions()
                            if symbol not in positions or positions[symbol].quantity < quantity:
                                # Position gone but order not filled - likely cancelled/rejected
                                self.logger.warning(
                                    f"⚠️ {symbol} position closed after {elapsed:.1f}s but order {order_state}, "
                                    f"using estimated price ${current_price:.2f}"
                                )
                                actual_exit_price = current_price
                                break
                    except Exception as e:
                        self.logger.debug(f"Position/order check attempt {elapsed:.0f}s: {e}")

            # Check final order status to avoid closing if order is still pending
            if not actual_exit_price:
                try:
                    final_order_status = await self.broker.get_order_status(str(exit_order_id))
                    final_order_state = final_order_status.get('status', '') if final_order_status else ''

                    if final_order_state in ('PENDING', 'PRESUBMITTED', 'SUBMITTED'):
                        # Order is still pending - DO NOT close the trade
                        self.logger.error(
                            f"❌ {symbol} exit order {exit_order_id} still {final_order_state} after {max_wait_seconds}s - "
                            f"NOT closing trade in database (order may execute later)"
                        )
                        # Update trade with exit order ID but keep status OPEN
                        trade_data = {
                            'trade_id': trade_id,
                            'broker_order_id_exit': str(exit_order_id),
                            'notes': f"Exit order {exit_order_id} pending ({final_order_state}) - {reason}"
                        }
                        self.db_manager.save_trade(trade_data)
                        return None  # Don't report as closed
                except Exception as e:
                    self.logger.error(f"Failed to check final order status: {e}")

                # If we get here, use estimated price but log warning
                actual_exit_price = current_price
                self.logger.error(
                    f"❌ {symbol} exit not confirmed after {max_wait_seconds}s, "
                    f"using expected price ${current_price:.2f} (MAY BE INACCURATE)"
                )

            # Recalculate PnL with actual exit price
            gross_pnl = (actual_exit_price - entry_price) * quantity
            net_pnl = gross_pnl - total_commission
            pnl_pct = (gross_pnl / (entry_price * quantity) * 100) if entry_price > 0 else 0

            # Prepare trade data with ACTUAL exit price
            trade_data = {
                'trade_id': trade_id,
                'symbol': symbol,
                'strategy': strategy_name,
                'side': 'BUY',
                'quantity': quantity,
                'entry_price': entry_price,
                'entry_time': entry_time,
                'exit_price': actual_exit_price,  # ✅ REAL EXIT PRICE
                'exit_time': self.clock.now(),
                'status': 'CLOSED',
                'pnl': round(net_pnl, 2),
                'commission': round(total_commission, 2),
                'broker_order_id_exit': str(exit_order_id),
                'notes': f"Worker exit: {reason}"
            }

            # Save trade ONCE with actual exit price
            self.db_manager.save_trade(trade_data)

            self.logger.info(
                f"✅ {symbol} position closed: {quantity} shares @ ${actual_exit_price:.2f} "
                f"(Net PnL: ${net_pnl:.2f}, {pnl_pct:+.2f}%)"
            )

            # Send Telegram notification
            try:
                # Format strategy name for display
                formatted_strategy = self._format_strategy_name(strategy_name)

                # Determine emoji based on PnL
                emoji = "🟢" if net_pnl >= 0 else "🔴"

                # Build notification message
                notification = (
                    f"{emoji} EXIT: {symbol} @ ${actual_exit_price:.2f}\n"
                    f"Strategy: {formatted_strategy}\n"
                    f"Quantity: {quantity} shares\n"
                    f"Entry: ${entry_price:.2f}\n"
                    f"Gross PnL: ${gross_pnl:.2f} ({pnl_pct:+.2f}%)\n"
                    f"Commission: ${total_commission:.2f}\n"
                    f"Net PnL: ${net_pnl:.2f}\n"
                    f"Reason: {reason}"
                )

                self._send_telegram(notification)
                self.logger.debug(f"📨 Telegram notification sent for {symbol} exit")

            except Exception as e:
                self.logger.warning(f"⚠️ Failed to send Telegram notification: {e}")

            # Remove from tracking
            del self.worker_positions[symbol]

            return True

        except Exception as e:
            self.logger.error(f"❌ Error exiting position for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def close_position(
        self,
        symbol: str,
        reason: str = "Worker requested close"
    ) -> bool:
        """
        Cierra posición (alias de exit_position para compatibilidad)

        Args:
            symbol: Símbolo a cerrar
            reason: Razón de cierre

        Returns:
            True si exitoso, False si falla
        """
        return await self.exit_position(symbol, reason)

    def _format_strategy_name(self, strategy_name: str) -> str:
        """
        Format strategy name for display in Telegram messages

        Args:
            strategy_name: Raw strategy/worker name

        Returns:
            Formatted strategy name
        """
        strategy_map = {
            'gap_go': '🚀 Gap&Go',
            'macdv': '📊 MACDV',
            'daily_plays': '⚡ Daily Plays (Intraday)',
            'bull_flag': '🚩 Bull Flag',
            'short_squeeze': '🐻 Squeeze (Proactive)',
            'macdv_smallcaps': '📊 MACDV-SC',
            'volume_breakout': '📈 VolBreak',
            'explosive_volume': '💥 ExpVol',
            'optimized_gap_go': '🚀 OptGap',
            'catalyst_momentum': '🔥 CatMom',
            'orb': '🔔 ORB',
            'pmh_breakout': '🌆 PMH',
            'vwap_smallcaps': '📉 VWAP-SC',
            'vwap_reclaim': '🔄 VWAP-Rec',
            'eod_momentum': '🌇 EOD-Mom',
            'vcp': '📉 VCP',
            'volume_absorption': '🧱 Vol Absorption',
            'vwap_breakout': '📉 VWAP',
            'momentum_breakout': '📈 Momentum',
            'vcp_smallcap': '📉 VCP-SC',
            'generic_01': '🛡️ Low Vol Accum'
        }

        # Clean the strategy name
        clean_name = strategy_name.lower().replace('strategy', '').replace('_strategy', '').strip('_')

        # Return mapped name or formatted original
        return strategy_map.get(clean_name, strategy_name.replace('_', ' ').title())

    async def get_current_price(self, symbol: str) -> float:
        """
        Obtiene precio actual del símbolo usando BatchPriceManager si disponible

        Args:
            symbol: Símbolo a consultar

        Returns:
            Precio actual, 0.0 si falla
        """
        try:
            # PRIORITY 1: Use BatchPriceManager for guaranteed fresh prices
            if hasattr(self.broker, 'batch_price_manager') and self.broker.batch_price_manager:
                bpm = self.broker.batch_price_manager

                # Check if price is fresh (< 5 seconds old)
                if bpm.is_price_fresh(symbol, max_age_seconds=5):
                    price = bpm.get_current_price(symbol)
                    if price > 0:
                        self.logger.debug(f"💰 {symbol}: Using fresh BatchPriceManager price: ${price:.2f}")
                        return price

                # Price is stale or not available - try to get fresh one
                self.logger.debug(f"⚠️ {symbol}: BatchPriceManager price stale, attempting refresh...")

                # Check if symbol is subscribed, if not, subscribe it
                if not bpm.is_subscribed(symbol):
                    self.logger.debug(f"📡 {symbol}: Not subscribed, attempting subscription...")
                    success = await bpm.add_symbol_subscription(symbol)
                    if success:
                        self.logger.debug(f"✅ {symbol}: Successfully subscribed for fresh price")
                        # Wait a moment for price to arrive
                        await asyncio.sleep(0.5)
                        if bpm.is_price_fresh(symbol, max_age_seconds=5):
                            price = bpm.get_current_price(symbol)
                            if price > 0:
                                return price

            # PRIORITY 2: Fallback to traditional broker methods
            if self.broker:
                price = await self.broker.get_current_price(symbol)
                if price and price > 0:
                    self.logger.debug(f"💰 {symbol}: Using broker fallback price: ${price:.2f}")
                    return price

            # LEGACY MODE: Access via TradingEngine
            if self.trading_engine and hasattr(self.trading_engine, 'broker'):
                price = await self.trading_engine.broker.get_current_price(symbol)
                if price and price > 0:
                    return price

            # Fallback legacy paths
            if self.trading_engine and hasattr(self.trading_engine, 'price_service'):
                price = await self.trading_engine.price_service.get_price(symbol)
                if price and price > 0:
                    return price

            if self.trading_engine and hasattr(self.trading_engine, 'broker_adapter'):
                price = await self.trading_engine.broker_adapter.get_current_price(symbol)
                if price and price > 0:
                    return price

            self.logger.warning(f"⚠️ No price source available for {symbol}")
            return 0.0

        except Exception as e:
            self.logger.debug(f"Could not get price for {symbol}: {e}")
            return 0.0

    def _restore_worker_positions_from_db(self):
        """
        Restaura posiciones de workers desde la base de datos al iniciar

        Flujo:
        1. Consulta database manager para trades OPEN
        2. Valida contra broker que la posición realmente existe
        3. Solo restaura si existe en broker (evita posiciones fantasma)
        4. Marca como cerrados los trades que no existen en broker
        """
        try:
            # Query database for open trades
            open_trades = self.db_manager.get_open_trades()

            if not open_trades:
                self.logger.debug("No open trades found in database")
                return

            # Get broker positions from risk manager
            broker_positions = {}
            if hasattr(self.risk_manager, 'broker_positions'):
                broker_positions = self.risk_manager.broker_positions
                self.logger.debug(f"Validating against {len(broker_positions)} broker position(s)")

            restored_count = 0
            skipped_count = 0

            # Group trades by symbol to avoid duplicate processing
            trades_by_symbol = {}
            for trade_data in open_trades:
                symbol = trade_data.get('symbol')
                if not symbol:
                    continue
                if symbol not in trades_by_symbol:
                    trades_by_symbol[symbol] = []
                trades_by_symbol[symbol].append(trade_data)

            # Process each symbol once
            for symbol, symbol_trades in trades_by_symbol.items():
                # Get strategy from first trade (all trades for same symbol should have same strategy)
                strategy = symbol_trades[0].get('strategy')

                # Only restore worker trades (have strategy attribution)
                if not strategy:
                    continue

                # VALIDATION: Check if position exists in broker
                broker_position = broker_positions.get(symbol)

                # Check if we're in paper trading mode
                is_paper_trading = getattr(self.broker, 'paper_trading_mode', False)

                if not broker_position or broker_position.quantity <= 0:
                    # Position doesn't exist in broker - it was closed outside system

                    # In paper trading mode, positions aren't real, so this is expected
                    if is_paper_trading:
                        self.logger.debug(
                            f"📝 {symbol}: Position in DB but not in paper broker (expected in paper mode) - "
                            f"Keeping position from DB"
                        )
                        # In paper trading, trust the database - restore the position
                        # Use most recent trade for this symbol
                        trade_data = symbol_trades[0]

                        # Reconstruct position data from DB
                        position_data = {
                            'symbol': symbol,
                            'strategy': strategy,
                            'entry_price': trade_data.get('entry_price', 0),
                            'quantity': trade_data.get('quantity', 0),
                            'trade_id': trade_data.get('trade_id'),
                            'entry_time': trade_data.get('entry_time'),
                            'opportunity_data': {}  # Lost on restart - not critical
                        }

                        self.worker_positions[symbol] = position_data
                        restored_count += 1

                        self.logger.info(
                            f"🔄 Restored paper position: {symbol} ({strategy}) @ "
                            f"${position_data['entry_price']:.2f} x {position_data['quantity']} shares "
                            f"(paper trading mode - from DB)"
                        )
                        continue

                    # In live trading, this is a phantom position - close it
                    self.logger.warning(
                        f"⚠️ Skipping {symbol}: Found {len(symbol_trades)} trade(s) in DB but NOT in broker "
                        f"(phantom position from previous session)"
                    )

                    # Mark ALL trades for this symbol as closed in database
                    closed_count = 0
                    for trade_data in symbol_trades:
                        try:
                            trade_id = trade_data.get('trade_id')
                            if trade_id:
                                self.db_manager.close_trade(
                                    trade_id=trade_id,
                                    exit_price=trade_data.get('entry_price', 0),  # Use entry as fallback
                                    exit_reason='AUTO_CLOSED_PHANTOM',
                                    pnl=0.0,
                                    commission=0.0
                                )
                                closed_count += 1
                        except Exception as e:
                            self.logger.error(f"Error closing phantom trade {trade_id}: {e}")

                    self.logger.info(f"✅ Marked {closed_count} trade(s) for {symbol} as AUTO_CLOSED in database")
                    skipped_count += 1
                    continue

                # Position exists in broker - safe to restore
                # Use most recent trade for this symbol (first in list)
                trade_data = symbol_trades[0]

                # Reconstruct position data
                position_data = {
                    'symbol': symbol,
                    'strategy': strategy,
                    'entry_price': trade_data.get('entry_price', 0),
                    'quantity': trade_data.get('quantity', 0),
                    'trade_id': trade_data.get('trade_id'),
                    'entry_time': trade_data.get('entry_time'),
                    'opportunity_data': {
                        # Restored exit parameters (from DB columns)
                        'stop_loss_pct': trade_data.get('stop_loss_pct'),
                        'take_profit_pct': trade_data.get('take_profit_pct'),
                        'stop_loss': trade_data.get('stop_loss_price'),
                        'take_profit': trade_data.get('take_profit_price'),
                        'trailing_activation_pct': trade_data.get('trailing_activation_pct'),
                        'trailing_distance_pct': trade_data.get('trailing_distance_pct')
                    }
                }

                self.worker_positions[symbol] = position_data
                restored_count += 1

                trades_info = f" ({len(symbol_trades)} trade record(s) in DB)" if len(symbol_trades) > 1 else ""
                self.logger.info(
                    f"🔄 Restored worker position: {symbol} ({strategy}) @ "
                    f"${position_data['entry_price']:.2f} x {position_data['quantity']} shares "
                    f"(verified in broker: {broker_position.quantity} shares){trades_info}"
                )

                # Register with UnifiedPositionManager to prevent duplicate entries
                # NOTE: This will be done asynchronously by the caller after restoration
                # We store registration data for later async processing
                if not hasattr(self, '_pending_unified_registrations'):
                    self._pending_unified_registrations = []

                position_value = position_data['entry_price'] * position_data['quantity']
                self._pending_unified_registrations.append({
                    'symbol': symbol,
                    'strategy_type': 'day',  # Workers are day trading
                    'position_data': {
                        'entry_price': position_data['entry_price'],
                        'quantity': position_data['quantity'],
                        'position_value': position_value,
                        'strategy': strategy,
                        'restored': True  # Mark as restored position
                    }
                })

            if restored_count > 0:
                self.logger.info(
                    f"✅ Restored {restored_count} worker position(s) from database "
                    f"(pending UnifiedPositionManager registration)"
                )

            if skipped_count > 0:
                self.logger.warning(f"⚠️ Skipped {skipped_count} phantom position(s) (not in broker)")

            # ========================================================================
            # REVERSE CHECK: Detect broker positions NOT in database (untracked positions)
            # This happens when positions are opened manually in IBKR or outside system
            # ========================================================================
            untracked_count = 0
            if broker_positions:
                for symbol, broker_position in broker_positions.items():
                    # Skip if already in database (already restored above)
                    if symbol in trades_by_symbol:
                        continue

                    # Skip if quantity is 0 or negative
                    if broker_position.quantity <= 0:
                        continue

                    # Found untracked position - create trade in DB
                    self.logger.warning(
                        f"⚠️ UNTRACKED POSITION: {symbol} has {broker_position.quantity} shares in broker "
                        f"@ ${broker_position.avg_price:.2f} but NO trade in database"
                    )

                    try:
                        # Create trade entry for this untracked position
                        from datetime import datetime
                        import uuid

                        trade_id = f"MANUAL_{symbol}_{self.clock.now().strftime('%Y%m%d_%H%M%S')}"

                        # Determine strategy based on position characteristics
                        # Default to 'daily_plays' for intraday positions
                        strategy = 'daily_plays'  # Can be enhanced with logic later

                        trade_data = {
                            'trade_id': trade_id,
                            'symbol': symbol,
                            'strategy': strategy,
                            'side': 'BUY',  # Assume long position
                            'quantity': int(broker_position.quantity),
                            'entry_price': float(broker_position.avg_price),
                            'entry_time': self.clock.now(),  # Approximate (we don't know real entry time)
                            'status': 'OPEN',
                            'notes': f'AUTO_REGISTERED: Manual position detected in broker (avg cost ${broker_position.avg_price:.2f})',
                            'actual_entry_price': float(broker_position.avg_price),
                            'entry_filled': True
                        }

                        # Insert into database
                        self.db_manager.save_trade(trade_data)

                        # Add to worker_positions for monitoring
                        position_data = {
                            'symbol': symbol,
                            'strategy': strategy,
                            'entry_price': float(broker_position.avg_price),
                            'quantity': int(broker_position.quantity),
                            'trade_id': trade_id,
                            'entry_time': self.clock.now(),
                            'opportunity_data': {}
                        }

                        self.worker_positions[symbol] = position_data

                        # Register for UnifiedPositionManager
                        if not hasattr(self, '_pending_unified_registrations'):
                            self._pending_unified_registrations = []

                        position_value = float(broker_position.avg_price) * int(broker_position.quantity)
                        self._pending_unified_registrations.append({
                            'symbol': symbol,
                            'strategy_type': 'day',
                            'position_data': {
                                'entry_price': float(broker_position.avg_price),
                                'quantity': int(broker_position.quantity),
                                'position_value': position_value,
                                'strategy': strategy,
                                'restored': True,
                                'manual': True  # Mark as manually created
                            }
                        })

                        self.logger.info(
                            f"✅ AUTO-REGISTERED untracked position: {symbol} ({strategy}) @ "
                            f"${broker_position.avg_price:.2f} x {broker_position.quantity} shares "
                            f"(created trade_id: {trade_id})"
                        )
                        untracked_count += 1

                    except Exception as e:
                        self.logger.error(f"❌ Failed to auto-register {symbol}: {e}")
                        import traceback
                        self.logger.error(traceback.format_exc())

            if untracked_count > 0:
                self.logger.warning(
                    f"⚠️ Auto-registered {untracked_count} untracked position(s) from broker "
                    f"(manually opened outside system)"
                )

        except Exception as e:
            self.logger.error(f"❌ Error restoring worker positions from database: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    async def register_restored_positions_with_unified_manager(self):
        """
        Asynchronously register restored positions with UnifiedPositionManager

        This must be called AFTER _restore_worker_positions_from_db() from an async context
        to complete the restoration process.
        """
        if not hasattr(self, '_pending_unified_registrations'):
            return

        try:
            from core.service_locator import get_unified_position_manager

            unified_manager = await get_unified_position_manager()
            if not unified_manager:
                self.logger.warning("⚠️ UnifiedPositionManager not available for restored position registration")
                return

            registered_count = 0
            for registration in self._pending_unified_registrations:
                try:
                    unified_manager.register_position(
                        symbol=registration['symbol'],
                        strategy_type=registration['strategy_type'],
                        position_data=registration['position_data']
                    )
                    self.logger.info(
                        f"💼 Re-registered {registration['symbol']} with UnifiedPositionManager "
                        f"({registration['position_data']['strategy']}, restored)"
                    )
                    registered_count += 1
                except Exception as e:
                    self.logger.error(
                        f"❌ Failed to register {registration['symbol']} with UnifiedPositionManager: {e}"
                    )

            if registered_count > 0:
                self.logger.info(
                    f"✅ Registered {registered_count} restored position(s) with UnifiedPositionManager"
                )

            # Clear pending registrations
            self._pending_unified_registrations = []

        except Exception as e:
            self.logger.error(f"❌ Error in unified position registration: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _round_to_ibkr_tick_size(self, price: float) -> float:
        """
        Round price to nearest valid IBKR tick size.

        IBKR tick sizes (more comprehensive rules):
        - $0.0001 for prices < $0.10
        - $0.001 for prices $0.10 - $0.99
        - $0.01 for prices $1.00 - $4.99
        - $0.05 for prices $5.00 - $9.99
        - $0.10 for prices ≥ $10.00

        Args:
            price: Raw price to round

        Returns:
            Price rounded to valid tick size
        """
        try:
            if price < 0.10:
                # Sub-penny tick size: $0.0001
                return round(price / 0.0001) * 0.0001
            elif price < 1.0:
                # Penny tick size: $0.001
                return round(price / 0.001) * 0.001
            elif price < 5.0:
                # Nickel tick size: $0.01
                return round(price / 0.01) * 0.01
            elif price < 10.0:
                # Dime tick size: $0.05 - use proper rounding with tolerance for floating point
                ticks = round(price / 0.05)
                rounded_price = ticks * 0.05
                # Ensure it's exactly a multiple by rounding to appropriate decimal places
                return round(rounded_price, 2)
            else:
                # Quarter tick size: $0.10
                return round(price / 0.10) * 0.10
        except Exception as e:
            self.logger.warning(f"Error rounding price {price} to tick size: {e}")
            return price  # Return original price if rounding fails

    def _save_worker_position_to_db(self, symbol: str):
        """
        Persiste posición de worker a la base de datos

        Args:
            symbol: Símbolo de la posición a guardar
        """
        try:
            position = self.worker_positions.get(symbol)
            if not position:
                return

            # Trade data already saved in enter_position() and exit_position()
            # This method is here for consistency but actual persistence happens
            # in those methods via db_manager.save_trade()

        except Exception as e:
            self.logger.debug(f"Error saving worker position {symbol}: {e}")

    async def _wait_for_execution_confirmation(self, order_id: str, symbol: str, expected_quantity: int, timeout: float = 30.0) -> bool:
        """
        Wait for execution confirmation from IBKR before proceeding with position registration.
        This prevents phantom positions when orders are cancelled.

        ENHANCED: Better detection to prevent ECX-style duplicates

        Args:
            order_id: IBKR order ID to monitor
            symbol: Stock symbol
            expected_quantity: Expected quantity to be filled
            timeout: Maximum time to wait in seconds

        Returns:
            bool: True if execution confirmed, False if timeout or cancelled
        """
        import asyncio

        self.logger.info(f"⏳ Waiting for execution confirmation: {symbol} order {order_id} (timeout: {timeout}s)")

        start_time = asyncio.get_event_loop().time()
        check_interval = 0.3  # ⚡ FASTER: Check every 300ms (was 500ms)

        cancelled_detected = False

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                # 🎯 PRIORITY 1: Check order status first (fastest)
                order_status = await self.broker.get_order_status(order_id)
                if order_status:
                    status = order_status.get('status', '').upper()
                    filled_qty = order_status.get('filled_quantity', 0)

                    # Order was cancelled - BUT DON'T ABORT YET
                    # IBKR may cancel then execute (ECX case)
                    if status in ['CANCELLED', 'CANCELLED_BY_USER', 'CANCELLED_BY_SYSTEM']:
                        if not cancelled_detected:
                            cancelled_detected = True
                            self.logger.warning(
                                f"⚠️ Order {order_id} for {symbol} was CANCELLED by IBKR - "
                                f"Waiting 5s to verify if it executed anyway (ECX-style behavior)"
                            )
                            # Wait 5 more seconds to see if position appears
                            await asyncio.sleep(5)
                            continue  # Check position below
                        else:
                            # Already waited 5s after cancellation - check position one last time
                            positions = await self.broker.get_positions()
                            if symbol in positions and positions[symbol].quantity >= expected_quantity:
                                self.logger.warning(
                                    f"🔍 Order {order_id} was CANCELLED but position EXISTS - "
                                    f"IBKR executed despite cancellation (ECX behavior)"
                                )
                                return True
                            else:
                                self.logger.info(
                                    f"✅ Order {order_id} CANCELLED and no position - "
                                    f"Genuine cancellation (not ECX-style)"
                                )
                                return False

                    # Order filled - confirm execution
                    if status == 'FILLED':
                        self.logger.info(f"✅ Order {order_id} for {symbol} filled - execution confirmed")
                        return True

                    # CRITICAL FIX: Check if filled quantity matches expected (even if status != FILLED)
                    # IBKR sometimes reports status as 'SUBMITTED' or 'PRESUBMITTED' even when fully filled
                    if filled_qty >= expected_quantity and filled_qty > 0:
                        self.logger.info(f"✅ Order {order_id} for {symbol} fully filled ({filled_qty}/{expected_quantity}) - execution confirmed (status={status})")
                        return True

                    # Order partially filled - could still be valid
                    if status == 'PARTIALLY_FILLED':
                        if filled_qty >= expected_quantity:
                            self.logger.info(f"✅ Order {order_id} for {symbol} partially filled ({filled_qty}/{expected_quantity}) - execution confirmed")
                            return True

                # 🎯 PRIORITY 2: Check IBKR positions as backup validation (more reliable than order status)
                positions = await self.broker.get_positions()
                if symbol in positions:
                    pos = positions[symbol]
                    if pos.quantity >= expected_quantity and pos.avg_price > 0:
                        self.logger.info(f"✅ Position confirmed in IBKR: {symbol} {pos.quantity} shares @ ${pos.avg_price:.2f}")
                        return True

                await asyncio.sleep(check_interval)

            except Exception as e:
                self.logger.debug(f"Error checking execution status for {order_id}: {e}")
                await asyncio.sleep(check_interval)

        # Timeout reached - final check for position
        try:
            positions = await self.broker.get_positions()
            if symbol in positions and positions[symbol].quantity >= expected_quantity:
                self.logger.warning(
                    f"⚠️ Order {order_id} timeout but position EXISTS - "
                    f"Late execution detected"
                )
                return True
        except:
            pass

        # Timeout reached without execution
        self.logger.error(f"⏰ Execution confirmation timeout for {symbol} order {order_id} after {timeout}s")
        return False

