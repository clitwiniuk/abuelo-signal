# adapters/ibkr_adapter.py
"""
IBKR broker adapter implementing the IBroker interface.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd

from ib_insync import IB, Stock, MarketOrder, LimitOrder, util, Trade, OrderStatus as IBOrderStatus, Execution, Fill, Contract
from core.interfaces import (
    IBroker, IDataProvider, MarketData, Position, Order, 
    OrderSide, OrderType, OrderStatus, BrokerConnectionError, DataProviderError
)
from core.batch_price_manager import BatchPriceManager
from core.smart_position_cache import SmartPositionCache
# Hybrid Volume Engine removed - using simple static volume requirements
# ML Volume Engine removed - using simple volume rules
from core.execution_tracker import get_execution_tracker
# Removed rate_limiter and connection_pool imports to fix data retrieval regression

logger = logging.getLogger(__name__)


class IBKRAdapter(IBroker, IDataProvider):
    """
    IBKR adapter that implements both broker and data provider interfaces.
    Uses ib_insync library for IBKR TWS/Gateway connectivity.
    """

    _RECONNECT_INTERVAL = 10  # segundos entre intentos de reconexión
    _MAX_RECONNECT_ATTEMPTS = 5  # máximo de intentos antes de dar alerta

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 4149, config=None):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.config = config
        
        self.ib = IB()
        self._connected = False
        self.logger = logging.getLogger(f"IBKRAdapter({client_id})")
        
        # Cache for contracts and data
        self._contracts_cache = {}
        self._orders_cache = {}
        # Note: _positions_cache removed - now using SmartPositionCache
        
        # FASE 1 OPTIMIZATIONS: Batch managers for API reduction
        self.batch_price_manager = None  # Will be initialized after connection
        self.smart_position_cache = None  # Will be initialized after connection
        
        # EXECUTION TRACKING: Real price tracking for slippage analysis
        self.execution_tracker = get_execution_tracker()
        
        # VOLUME ENGINE REMOVED - using simple static volume requirements
        self._optimizations_enabled = True
        
        # Extended hours configuration
        self._use_extended_hours = self._should_use_extended_hours()
        
        # Rate limiting for IBKR requests
        from collections import deque
        self._request_times = deque(maxlen=100)  # Limit memory usage for small caps spikes
        self._max_requests_per_minute = 30  # Increased for parallel processing
        self._request_delay = 0.2  # Reduced delay for better throughput
        self._last_request_time = None
        # Initialize lock immediately to avoid race conditions
        import asyncio
        try:
            self._rate_limit_lock = asyncio.Lock()
        except RuntimeError:
            # No event loop running yet - will be initialized in connect()
            self._rate_limit_lock = None

        # Concurrency limiting for IBKR requests
        self._concurrency_semaphore = asyncio.Semaphore(3)  # Allow up to 3 concurrent requests
        
        # Setup event handlers
        self._setup_event_handlers()

        # Reconexión automática
        self._reconnect_task = None
        self._reconnect_attempts = 0
        
        if self._use_extended_hours:
            self.logger.info("🌅 Extended hours data enabled - including premarket/afterhours")
        else:
            self.logger.info("🕘 Regular trading hours only - excluding premarket/afterhours")

        # Paper Trading Mode Configuration
        self.paper_trading_mode = self._should_use_paper_trading()
        if self.paper_trading_mode:
            self.logger.warning("📝 PAPER TRADING MODE ENABLED - Orders will NOT be sent to broker")
            # Initialize counter from last used trade_id in database to avoid ID collisions
            self._paper_order_id_counter = self._get_next_paper_order_id()
            self._paper_positions = {}  # Track paper trading positions: {symbol: Position}

    
    def _should_use_extended_hours(self) -> bool:
        """Determine if extended hours should be used based on config"""
        try:
            if self.config:
                trading_hours_mode = getattr(self.config, 'trading_hours_mode', 'REGULAR')
                return trading_hours_mode == 'EXTENDED_HOURS'
            return False
        except Exception as e:
            self.logger.warning(f"Could not determine extended hours setting: {e}")
            return False

    def _should_use_paper_trading(self) -> bool:
        """Determine if paper trading mode is enabled"""
        try:
            if self.config:
                # Check paper_trading_mode from config
                if hasattr(self.config, 'paper_trading_mode'):
                    is_paper = str(self.config.paper_trading_mode).lower() == 'true'
                    if is_paper:
                        self.logger.warning("📝 PAPER TRADING MODE ENABLED - Orders will NOT be sent to broker")
                    else:
                        self.logger.info("💼 LIVE TRADING MODE ENABLED - Orders WILL be sent to broker")
                    return is_paper

            # Default to paper trading for safety if no config found
            self.logger.warning("⚠️ No paper_trading_mode config found - defaulting to PAPER TRADING for safety")
            return True

        except Exception as e:
            self.logger.warning(f"Could not determine paper trading setting: {e}")
            # Default to paper trading for safety
            return True

    def _get_next_paper_order_id(self) -> int:
        """
        Get the next available paper order ID by querying the database for the last used ID.
        This prevents ID collisions when the system restarts.

        Returns:
            int: Next available order ID (last_id + 1, or 1000000 if no trades exist)
        """
        try:
            import sqlite3
            db_path = "trading_data.db"

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # Get the maximum numeric trade_id from the database
                # trade_id can be numeric strings like "1000001" or formatted strings like "MANUAL_..."
                # We only want numeric IDs for continuation
                cursor.execute("""
                    SELECT MAX(CAST(trade_id AS INTEGER))
                    FROM trades
                    WHERE trade_id GLOB '[0-9]*'
                """)

                result = cursor.fetchone()
                max_id = result[0] if result and result[0] is not None else None

                if max_id is not None:
                    next_id = max_id + 1
                    self.logger.info(f"📊 Initializing paper order ID counter from database: {next_id} (last ID was {max_id})")
                    return next_id
                else:
                    self.logger.info("📊 No previous trades found, starting paper order ID counter at 1000000")
                    return 1000000

        except Exception as e:
            self.logger.warning(f"⚠️ Could not read last trade_id from database: {e}")
            self.logger.warning("📊 Defaulting paper order ID counter to 1000000")
            return 1000000

    async def ensure_connection(self):
        """Bucle de supervisión: reconecta si la conexión se pierde."""
        while True:
            try:
                if not self.is_connected():
                    self.logger.warning("🔌 Conexión perdida con IBKR. Intentando reconectar...")
                    self._reconnect_attempts += 1
                    try:
                        await self.connect()
                        self._reconnect_attempts = 0
                        self.logger.info("✅ Reconexión exitosa a IBKR.")
                    except Exception as e:
                        self.logger.error(f"❌ Error al reconectar ({self._reconnect_attempts}): {e}")
                        if self._reconnect_attempts >= self._MAX_RECONNECT_ATTEMPTS:
                            self.logger.critical(f"❌ No se pudo reconectar tras {self._MAX_RECONNECT_ATTEMPTS} intentos. Requiere intervención manual.")
                            self._reconnect_attempts = 0  # Resetea para evitar spam
                else:
                    self._reconnect_attempts = 0
            except Exception as e:
                self.logger.error(f"Error en bucle de reconexión: {e}")
            await asyncio.sleep(self._RECONNECT_INTERVAL)

    def start_auto_reconnect(self, loop=None):
        """Lanza el bucle de reconexión automática en segundo plano."""
        if self._reconnect_task is None:
            loop = loop or asyncio.get_event_loop()
            self._reconnect_task = loop.create_task(self.ensure_connection())

        self._contracts_cache = {}
        self._orders_cache = {}
        # Note: _positions_cache removed - using SmartPositionCache
        
        # Rate limiting for IBKR requests
        from collections import deque
        self._request_times = deque(maxlen=100)  # Limit memory usage for small caps spikes
        self._max_requests_per_minute = 30  # Increased for parallel processing
        self._request_delay = 0.2  # Reduced delay for better throughput
        self._last_request_time = None
        # Initialize lock immediately to avoid race conditions
        import asyncio
        try:
            self._rate_limit_lock = asyncio.Lock()
        except RuntimeError:
            # No event loop running yet - will be initialized in connect()
            self._rate_limit_lock = None

        # Concurrency limiting for IBKR requests
        # Semaphore ensures that only a limited number of requests are in-flight simultaneously
        # Reduced from 5 to 3 to work better with trading engine throttling
        self._concurrency_semaphore = asyncio.Semaphore(3)  # Allow up to 3 concurrent requests
        
        # Setup event handlers
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """Setup IBKR event handlers"""
        self.ib.orderStatusEvent += self._on_order_status
        self.ib.execDetailsEvent += self._on_execution
        self.ib.positionEvent += self._on_position_update
        self.ib.errorEvent += self._on_error
    
    # IBroker interface implementation
    async def connect(self) -> bool:
        """Connect to IBKR TWS/Gateway"""
        try:
            if self._connected:
                self.logger.warning("Already connected to IBKR")
                return True
            
            self.logger.info(f"Connecting to IBKR at {self.host}:{self.port} (client_id: {self.client_id})")
            
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=30
            )
            
            self._connected = True
            self.logger.info("Successfully connected to IBKR")
            
            # Clean up any existing subscriptions before loading data
            await self._cleanup_subscriptions()
            
            # FASE 1 OPTIMIZATIONS: Initialize batch managers
            if self._optimizations_enabled:
                self.batch_price_manager = BatchPriceManager(self)
                self.smart_position_cache = SmartPositionCache(self, cache_ttl_minutes=5)
                self.logger.info("⚡ Phase 1 optimizations initialized:")
                self.logger.info("   📡 Batch Price Manager (99.95% API reduction)")
                self.logger.info("   🧠 Smart Position Cache (80% API reduction)")
                
                # VOLUME ENGINE REMOVED - using simple static volume requirements
                self.logger.info("   🎯 Using simple static volume requirements - NO ML")
            
            # Load initial data
            await self._load_initial_data()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to IBKR: {e}")
            self._connected = False
            raise BrokerConnectionError(f"Failed to connect to IBKR: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to IBKR"""
        return self._connected and self.ib is not None and self.ib.isConnected()
    
    async def disconnect(self) -> None:
        """Disconnect from IBKR"""
        try:
            if not self._connected:
                return
            
            self.logger.info("Disconnecting from IBKR")
            
            # FASE 1 OPTIMIZATIONS: Cleanup batch managers
            if self.batch_price_manager:
                try:
                    await self.batch_price_manager.cleanup()
                    self.batch_price_manager = None
                except Exception as e:
                    self.logger.error(f"Error cleaning up BatchPriceManager: {e}")
            
            # VOLUME ENGINE REMOVED - no cleanup needed
            
            if self.smart_position_cache:
                try:
                    self.smart_position_cache.clear_cache()
                    self.smart_position_cache = None
                except Exception as e:
                    self.logger.error(f"Error cleaning up SmartPositionCache: {e}")
            
            # Clean up any active market data subscriptions
            try:
                # Cancel any active subscriptions
                for contract in self._contracts_cache.values():
                    try:
                        self.ib.cancelMktData(contract)
                    except:
                        pass  # Ignore errors during cleanup
            except:
                pass  # Ignore errors during cleanup
            
            # Disconnect from IBKR
            self.ib.disconnect()
            self._connected = False
            
            # Clean up event loop references
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Give time for cleanup
                    await asyncio.sleep(0.1)
            except:
                pass  # Ignore errors during cleanup
            
            self.logger.info("Successfully disconnected from IBKR")
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from IBKR: {e}")
            self._connected = False
    
    
    async def place_order(self, order: Order) -> str:
        """Place an order with IBKR"""
        try:
            if not self.is_connected():
                raise BrokerConnectionError("Not connected to IBKR")
            
            # Get or create contract
            contract = await self._get_contract(order.symbol)
            if not contract:
                raise ValueError(f"Could not create contract for {order.symbol}")
            
            # Create IBKR order
            ib_order = self._create_ib_order(order)
            
            # PAPER TRADING MODE
            if self.paper_trading_mode:
                return await self._place_paper_order(order, contract, ib_order)
            
            # Place order
            trade = self.ib.placeOrder(contract, ib_order)
            
            # Update our order tracking
            order.order_id = str(trade.order.orderId)
            self._orders_cache[order.order_id] = order
            
            self.logger.info(f"Order placed: {order.side.value} {order.quantity} {order.symbol} (ID: {order.order_id})")
            
            return order.order_id
            
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            raise

    async def _place_paper_order(self, order: Order, contract: Contract, ib_order) -> str:
        """Simulate order placement and execution for paper trading"""
        self._paper_order_id_counter += 1
        paper_id = str(self._paper_order_id_counter)
        
        # Assign ID to IB order
        ib_order.orderId = int(paper_id)
        
        # Update our order object
        order.order_id = paper_id
        order.status = OrderStatus.SUBMITTED
        self._orders_cache[paper_id] = order
        
        self.logger.info(f"📝 PAPER ORDER PLACED: {order.side.value} {order.quantity} {order.symbol} (ID: {paper_id})")
        
        # Simulate execution asynchronously
        asyncio.create_task(self._simulate_execution(order, contract, ib_order))
        
        return paper_id

    async def _simulate_execution(self, order: Order, contract: Contract, ib_order):
        """Simulate order execution flow"""
        try:
            # Wait a brief moment to simulate network latency
            await asyncio.sleep(0.5)
            
            # Determine execution price
            if order.order_type == OrderType.LIMIT and order.price:
                exec_price = order.price
            else:
                # For market orders, get current price
                exec_price = await self.get_current_price(order.symbol)
                if exec_price == 0:
                    exec_price = 100.0 # Fallback if no price available
            
            # Create IBKR objects for event handlers
            # 1. OrderStatus
            ib_status = IBOrderStatus(
                orderId=ib_order.orderId,
                status='Filled',
                filled=order.quantity,
                remaining=0,
                avgFillPrice=exec_price,
                permId=0,
                parentId=0,
                lastFillPrice=exec_price,
                clientId=self.client_id,
                whyHeld=''
            )
            
            # 2. Trade object
            trade = Trade(
                contract=contract,
                order=ib_order,
                orderStatus=ib_status,
                fills=[],
                log=[]
            )
            
            # 3. Execution object
            execution = Execution(
                execId=f"PAPER_EXEC_{ib_order.orderId}",
                time=datetime.now(),
                acctNumber="PAPER_TRADING",
                exchange="PAPER",
                side=ib_order.action,
                shares=order.quantity,
                price=exec_price,
                permId=0,
                clientId=self.client_id,
                orderId=ib_order.orderId,
                liquidation=0,
                cumQty=order.quantity,
                avgPrice=exec_price,
                orderRef="",
                evRule="",
                evMultiplier=0,
                modelCode="",
                lastLiquidity=0
            )
            
            # 4. Fill object
            fill = Fill(
                contract=contract,
                execution=execution,
                commissionReport=None,
                time=datetime.now()
            )
            
            trade.fills.append(fill)
            
            # Trigger event handlers
            self.logger.info(f"📝 Simulating execution for {order.symbol}: {order.quantity} @ {exec_price}")
            
            # 1. Update status to Submitted first
            ib_status_submitted = IBOrderStatus(
                orderId=ib_order.orderId,
                status='Submitted',
                filled=0,
                remaining=order.quantity,
                avgFillPrice=0.0,
                permId=0,
                parentId=0,
                lastFillPrice=0.0,
                clientId=self.client_id,
                whyHeld=''
            )
            trade_submitted = Trade(contract, ib_order, ib_status_submitted, [], [])
            self._on_order_status(trade_submitted)
            
            await asyncio.sleep(0.2)

            # 2. Trigger execution
            self._on_execution(trade, fill)

            # 3. Trigger final status
            self._on_order_status(trade)

            # 4. Update paper positions
            self._update_paper_position(order, exec_price)

        except Exception as e:
            self.logger.error(f"Error in paper trading simulation: {e}")

    def _update_paper_position(self, order: Order, exec_price: float):
        """Update paper trading positions after execution"""
        try:
            symbol = order.symbol
            quantity = order.quantity if order.side == OrderSide.BUY else -order.quantity

            if symbol in self._paper_positions:
                # Update existing position
                current_pos = self._paper_positions[symbol]
                new_quantity = current_pos.quantity + quantity

                if new_quantity == 0:
                    # Position closed
                    del self._paper_positions[symbol]
                    self.logger.info(f"📝 Paper position closed: {symbol}")
                else:
                    # Update position with new average price
                    total_cost = (current_pos.quantity * current_pos.avg_price) + (quantity * exec_price)
                    new_avg_price = total_cost / new_quantity if new_quantity != 0 else exec_price

                    self._paper_positions[symbol] = Position(
                        symbol=symbol,
                        quantity=int(new_quantity),
                        avg_price=new_avg_price,
                        market_price=exec_price,
                        market_value=new_quantity * exec_price,
                        unrealized_pnl=(exec_price - new_avg_price) * new_quantity,
                        realized_pnl=0.0
                    )
                    self.logger.info(f"📝 Paper position updated: {symbol} {new_quantity} @ {new_avg_price:.2f}")
            else:
                # New position
                self._paper_positions[symbol] = Position(
                    symbol=symbol,
                    quantity=int(quantity),
                    avg_price=exec_price,
                    market_price=exec_price,
                    market_value=quantity * exec_price,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0
                )
                self.logger.info(f"📝 Paper position opened: {symbol} {quantity} @ {exec_price:.2f}")

        except Exception as e:
            self.logger.error(f"Error updating paper position: {e}")
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            if not self.is_connected():
                raise BrokerConnectionError("Not connected to IBKR")
            
            # PAPER TRADING MODE
            if self.paper_trading_mode:
                if order_id in self._orders_cache:
                    self._orders_cache[order_id].status = OrderStatus.CANCELLED
                    self.logger.info(f"📝 PAPER ORDER CANCELLED: {order_id}")
                    return True
                return False

            # Find the trade by order ID
            trade = None
            for t in self.ib.trades():
                if str(t.order.orderId) == order_id:
                    trade = t
                    break
            
            if not trade:
                self.logger.warning(f"Order {order_id} not found for cancellation")
                return False
            
            # Cancel the order
            self.ib.cancelOrder(trade.order)
            
            # Update our cache
            if order_id in self._orders_cache:
                self._orders_cache[order_id].status = OrderStatus.CANCELLED
            
            self.logger.info(f"Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def get_positions(self) -> Dict[str, Position]:
        """
        Get current positions - OPTIMIZED PHASE 1

        ANTES: 2 API calls cada vez (positions() + portfolio())
        DESPUÉS: Cache inteligente con 80% reducción
        """
        try:
            # 🎯 PAPER TRADING MODE: Return paper positions
            if self.paper_trading_mode:
                self.logger.debug(f"📝 Returning {len(self._paper_positions)} paper positions")
                return self._paper_positions.copy()

            if not self.is_connected():
                raise BrokerConnectionError("Not connected to IBKR")

            # FASE 1 OPTIMIZATION: Use SmartPositionCache if available
            if self._optimizations_enabled and self.smart_position_cache:
                return await self._get_positions_optimized()

            # FALLBACK: Original method (for backward compatibility)
            self.logger.warning("⚠️ Using fallback position method (optimization disabled)")
            return await self._get_positions_fallback()

        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return {}
    
    async def _get_positions_optimized(self) -> Dict[str, Position]:
        """Optimized positions using SmartPositionCache"""
        try:
            # Get cached positions (minimal API calls due to smart caching)
            raw_positions = await self.smart_position_cache.get_positions()
            raw_portfolio = await self.smart_position_cache.get_portfolio()
            
            positions = {}
            
            # Process positions from cache
            for symbol, pos in raw_positions.items():
                if hasattr(pos, 'contract') and pos.contract.secType == 'STK' and pos.position != 0:
                    portfolio_item = raw_portfolio.get(symbol)
                    
                    # Create position object
                    position = Position(
                        symbol=symbol,
                        quantity=int(pos.position),
                        avg_price=float(pos.avgCost) if pos.avgCost else 0.0,
                        market_price=float(portfolio_item.marketPrice) if portfolio_item else 0.0,
                        market_value=float(portfolio_item.marketValue) if portfolio_item else 0.0,
                        unrealized_pnl=float(portfolio_item.unrealizedPNL) if portfolio_item else 0.0,
                        entry_time=datetime.now()  # IBKR doesn't provide entry time directly
                    )
                    
                    positions[symbol] = position
            
            # Legacy cache removed - using SmartPositionCache
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error in optimized get_positions: {e}")
            # Fallback to original method
            return await self._get_positions_fallback()
    
    async def _get_positions_fallback(self) -> Dict[str, Position]:
        """Fallback positions method (original implementation)"""
        positions = {}
        
        # Get positions from IBKR (API CALLS)
        ib_positions = self.ib.positions()  # API CALL #1
        portfolio_items = {item.contract.symbol: item for item in self.ib.portfolio()}  # API CALL #2
        
        for pos in ib_positions:
            if pos.contract.secType == 'STK' and pos.position != 0:
                symbol = pos.contract.symbol
                portfolio_item = portfolio_items.get(symbol)
                
                # Create position object
                position = Position(
                    symbol=symbol,
                    quantity=int(pos.position),
                    avg_price=float(pos.avgCost) if pos.avgCost else 0.0,
                    market_price=float(portfolio_item.marketPrice) if portfolio_item else 0.0,
                    market_value=float(portfolio_item.marketValue) if portfolio_item else 0.0,
                    unrealized_pnl=float(portfolio_item.unrealizedPNL) if portfolio_item else 0.0,
                    entry_time=datetime.now()  # IBKR doesn't provide entry time directly
                )
                
                positions[symbol] = position
        
        # Legacy cache removed - using SmartPositionCache
        
        return positions
    
    async def get_orders(self) -> List[Order]:
        """Get current orders"""
        try:
            if not self.is_connected():
                raise BrokerConnectionError("Not connected to IBKR")

            orders = []

            for trade in self.ib.trades():
                if trade.orderStatus.status in ['PreSubmitted', 'Submitted', 'PendingSubmit']:
                    order = self._convert_ib_trade_to_order(trade)
                    if order:
                        orders.append(order)

            return orders

        except Exception as e:
            self.logger.error(f"Error getting orders: {e}")
            return []

    async def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order status by order ID

        Args:
            order_id: IBKR order ID (as string)

        Returns:
            Dict with order status info: {
                'status': str,  # 'FILLED', 'CANCELLED', 'SUBMITTED', etc.
                'filled_quantity': int,
                'remaining_quantity': int,
                'avg_fill_price': float
            }
            None if order not found
        """
        try:
            # 🎯 PAPER TRADING MODE: Use orders cache instead of IBKR API
            if self.paper_trading_mode:
                if order_id in self._orders_cache:
                    order = self._orders_cache[order_id]
                    return {
                        'status': order.status.value,
                        'filled_quantity': order.filled_quantity if hasattr(order, 'filled_quantity') else order.quantity,
                        'remaining_quantity': 0 if order.status == OrderStatus.FILLED else order.quantity,
                        'avg_fill_price': order.avg_fill_price if hasattr(order, 'avg_fill_price') else order.price or 0.0
                    }
                else:
                    self.logger.debug(f"📝 Paper order {order_id} not found in cache")
                    return None

            if not self.is_connected():
                self.logger.debug(f"Not connected to IBKR when checking order {order_id}")
                return None

            # Convert order_id to int for comparison
            try:
                order_id_int = int(order_id)
            except ValueError:
                self.logger.warning(f"Invalid order_id format: {order_id}")
                return None

            # Check all trades for this order ID
            for trade in self.ib.trades():
                if trade.order.orderId == order_id_int:
                    status = trade.orderStatus.status

                    # Map IBKR status to our status
                    status_map = {
                        'Filled': 'FILLED',
                        'Cancelled': 'CANCELLED',
                        'ApiCancelled': 'CANCELLED',
                        'Submitted': 'SUBMITTED',
                        'PreSubmitted': 'SUBMITTED',
                        'PendingSubmit': 'PENDING',
                        'PendingCancel': 'PENDING',
                        'Inactive': 'INACTIVE'
                    }

                    mapped_status = status_map.get(status, status.upper())

                    return {
                        'status': mapped_status,
                        'filled_quantity': int(trade.orderStatus.filled),
                        'remaining_quantity': int(trade.orderStatus.remaining),
                        'avg_fill_price': float(trade.orderStatus.avgFillPrice) if trade.orderStatus.avgFillPrice else 0.0
                    }

            # Order not found in active trades
            self.logger.debug(f"Order {order_id} not found in active trades")
            return None

        except Exception as e:
            self.logger.debug(f"Error getting order status for {order_id}: {e}")
            return None

    # IDataProvider interface implementation
    async def get_bars(self, symbol: str, timeframe: str, count: int, end_date: datetime = None) -> List[MarketData]:
        """
        Get historical bars
        
        Args:
            symbol: Ticker symbol
            timeframe: Bar timeframe (e.g. '5 mins', '1 day')
            count: Number of bars (approx)
            end_date: Optional end datetime for historical fetching. If None, fetches from Now.
        """
        import time
        start_time = time.time()
        
        try:
            if not self.is_connected():
                raise DataProviderError("Not connected to IBKR")
            
            # Format endDateTime if provided
            end_date_str = ''
            if end_date:
                # IBKR format: YYYYMMDD HH:mm:ss
                # Ensure we have a valid datetime
                if isinstance(end_date, str):
                    try:
                        end_date = datetime.fromisoformat(end_date)
                    except:
                        pass # Keep as string or handle? Assuming logic passes datetime objects
                
                if isinstance(end_date, datetime):
                     end_date_str = end_date.strftime('%Y%m%d %H:%M:%S')

            # Reduced logging: only log data requests in debug mode
            self.logger.debug(f"🔍 Starting data request for {symbol} ({timeframe}, {count} bars, end={end_date_str or 'Now'})")
            
            # Apply rate limiting before making any requests
            await self._wait_for_rate_limit()
            
            # Get contract
            contract_start = time.time()
            was_in_cache = symbol in self._contracts_cache
            contract = await self._get_contract(symbol)
            contract_time = time.time() - contract_start
            
            if not contract:
                self.logger.warning(f"❌ Could not create contract for {symbol} after {contract_time:.2f}s")
                return []
            
            if was_in_cache:
                self.logger.debug(f"♻️ Contract retrieved from cache for {symbol} in {contract_time:.2f}s")
            else:
                self.logger.info(f"✅ Contract created for {symbol} in {contract_time:.2f}s")
            
            # Convert timeframe to IBKR format
            bar_size = self._convert_timeframe(timeframe)
            duration = self._calculate_duration(count, timeframe)
            
            self.logger.debug(f"📊 Requesting IBKR data for {symbol}: duration={duration}, bar_size={bar_size}")
            
            # Request historical data with detailed timing, limiting concurrency
            async with self._concurrency_semaphore:
                ibkr_start = time.time()
                
                try:
                    # More robust request with retry logic for cancelled requests
                    bars = None
                    retry_count = 0
                    max_retries = 2
                    
                    while bars is None and retry_count <= max_retries:
                        try:
                            bars = await self.ib.reqHistoricalDataAsync(
                                contract=contract,
                                endDateTime=end_date_str, # Use provided date
                                durationStr=duration,
                                barSizeSetting=bar_size,
                                whatToShow='TRADES',
                                useRTH=not self._use_extended_hours,  # False = include extended hours, True = regular hours only
                                timeout=20  # Shorter timeout, with retries
                            )
                            break  # Success, exit retry loop
                            
                        except asyncio.CancelledError:
                            retry_count += 1
                            if retry_count <= max_retries:
                                self.logger.warning(f"🔄 IBKR request for {symbol} was cancelled, retrying ({retry_count}/{max_retries})")
                                await asyncio.sleep(1.0)  # Brief delay before retry
                            else:
                                self.logger.warning(f"🚫 IBKR request for {symbol} was cancelled after {max_retries} retries")
                                return []
                        except Exception as e:
                            if retry_count < max_retries:
                                retry_count += 1
                                self.logger.warning(f"🔄 IBKR request error for {symbol}, retrying ({retry_count}/{max_retries}): {e}")
                                await asyncio.sleep(1.0)
                            else:
                                raise  # Re-raise on final retry
                        
                except Exception as e:
                    self.logger.error(f"❌ IBKR request failed for {symbol}: {e}")
                    return []
            
            ibkr_time = time.time() - ibkr_start
            
            # Log performance info
            if ibkr_time > 30.0:
                self.logger.warning(f"🐌 IBKR slow response for {symbol}: {ibkr_time:.2f}s (>30s)")
            elif ibkr_time > 15.0:
                self.logger.info(f"📈 IBKR responded for {symbol} in {ibkr_time:.2f}s (slower than usual)")
            else:
                self.logger.info(f"📈 IBKR responded for {symbol} in {ibkr_time:.2f}s")
            
            if not bars:
                total_time = time.time() - start_time
                self.logger.warning(f"❌ No bars received for {symbol} after {total_time:.2f}s total")
                return []
            
            # Convert to MarketData objects
            conversion_start = time.time()
            market_data = []
            seen_timestamps = set()

            # Calculate average volume and get previous close
            total_volume = sum(bar.volume for bar in bars if bar.volume)
            avg_volume = total_volume / len(bars) if bars else 0
            prev_close = bars[0].close if bars and len(bars) > 1 else None

            for i, bar in enumerate(bars):
                timestamp = bar.date
                if timestamp in seen_timestamps:
                    self.logger.warning(f"Duplicate timestamp {timestamp} for {symbol}, skipping")
                    continue

                seen_timestamps.add(timestamp)

                # For the first bar, use previous day's close if available
                bar_prev_close = bars[i-1].close if i > 0 else prev_close

                data = MarketData(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume) if bar.volume else 0,
                    prev_close=float(bar_prev_close) if bar_prev_close else None,
                    avg_volume=int(avg_volume)
                )
                market_data.append(data)
            
            conversion_time = time.time() - conversion_start
            total_time = time.time() - start_time
            
            self.logger.info(f"✅ Successfully got {len(market_data)} bars for {symbol} (conversion: {conversion_time:.2f}s, total: {total_time:.2f}s)")
            return market_data
            
        except Exception as e:
            total_time = time.time() - start_time
            self.logger.error(f"❌ Error getting bars for {symbol} after {total_time:.2f}s: {e}")
            return []
    
    async def get_current_price(self, symbol: str) -> float:
        """
        Get current market price - OPTIMIZED PHASE 1
        
        ANTES: 3 API calls (reqMktData + sleep + cancelMktData)
        DESPUÉS: 0 API calls (usa BatchPriceManager cache)
        
        Reducción: 99.95% menos API calls
        """
        try:
            if not self.is_connected():
                raise DataProviderError("Not connected to IBKR")
            
            # FASE 1 OPTIMIZATION: Use BatchPriceManager if available
            if self._optimizations_enabled and self.batch_price_manager:
                price = self.batch_price_manager.get_current_price(symbol)
                
                # If no price available in cache, ensure symbol is subscribed
                if price == 0.0:
                    self.logger.debug(f"📡 No cached price for {symbol}, adding subscription")
                    success = await self.batch_price_manager.add_symbol_subscription(symbol)
                    if success:
                        # Give a moment for initial price data
                        await asyncio.sleep(0.5)
                        price = self.batch_price_manager.get_current_price(symbol)
                
                return price
            
            # FALLBACK: Original method (for backward compatibility or when optimization disabled)
            self.logger.warning(f"⚠️ Using fallback price method for {symbol} (optimization disabled)")
            
            contract = await self._get_contract(symbol)
            if not contract:
                return 0.0
            
            # Request market data
            ticker = self.ib.reqMktData(contract, '', False, False)
            
            # Wait for price data
            await asyncio.sleep(1)  # Give time for data to arrive
            
            if ticker.marketPrice():
                price = float(ticker.marketPrice())
            elif ticker.last:
                price = float(ticker.last)
            elif ticker.close:
                price = float(ticker.close)
            else:
                price = 0.0
            
            # Cancel market data subscription
            self.ib.cancelMktData(contract)
            
            return price
            
        except Exception as e:
            self.logger.error(f"Error getting current price for {symbol}: {e}")
            return 0.0

    async def get_short_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get real-time short data from IBKR (Shortable Shares + ETB/HTB status)
        Generic Ticks:
        - 236: shortableShares
        - 429: shortable (ETB/HTB indicator)
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with keys: 
                'shortable_shares' (int), 
                'shortable' (bool),
                'short_status' (str): 'ETB', 'HTB', or 'NONE',
                'is_etb' (bool)
        """
        try:
            if not self.is_connected():
                raise DataProviderError("Not connected to IBKR")
                
            contract = await self._get_contract(symbol)
            if not contract:
                return {'shortable_shares': 0, 'shortable': False, 'short_status': 'NONE', 'is_etb': False}
                
            # Request market data with generic ticks 236 (Shares) and 429 (Status)
            self.logger.debug(f"🐻 Requesting short data (ETB/HTB) for {symbol}...")
            ticker = self.ib.reqMktData(contract, '236,429', False, False)
            
            # Wait for data to arrive (max 2 seconds)
            for _ in range(20):
                if ticker.shortableShares is not None or ticker.shortable is not None:
                    break
                await asyncio.sleep(0.1)
                
            # Extract data
            shortable_shares = ticker.shortableShares if ticker.shortableShares else 0
            shortable_val = ticker.shortable if ticker.shortable is not None else 0.0
            
            # Map IBKR 'shortable' field (float):
            # > 2.5: Easy to Borrow (ETB)
            # > 1.5: Hard to Borrow (HTB)
            # <= 1.5: Not shortable
            status = 'NONE'
            is_etb = False
            if shortable_val > 2.5:
                status = 'ETB'
                is_etb = True
            elif shortable_val > 1.5:
                status = 'HTB'
            
            self.logger.info(f"🐻 {symbol} Short Data: {shortable_shares} shares, Status: {status} (val={shortable_val})")
            
            # Cancel subscription
            self.ib.cancelMktData(contract)
            
            return {
                'shortable_shares': int(shortable_shares),
                'shortable': shortable_val > 1.5,
                'short_status': status,
                'is_etb': is_etb,
                'raw_shortable': shortable_val
            }
            
        except Exception as e:
            self.logger.error(f"Error getting short data for {symbol}: {e}")
            return {'shortable_shares': 0, 'shortable': False}
    
    # FASE 1 OPTIMIZATION: Batch operations
    async def initialize_batch_subscriptions(self, symbols: List[str]) -> bool:
        """
        Initialize batch price subscriptions for multiple symbols
        Call this at start of trading day with all symbols you'll be monitoring
        
        Returns:
            bool: Success of subscription initialization
        """
        if not self._optimizations_enabled or not self.batch_price_manager:
            self.logger.warning("⚠️ Batch subscriptions not available (optimizations disabled)")
            return False
        
        if not symbols:
            self.logger.warning("⚠️ No symbols provided for batch subscription")
            return False
        
        self.logger.info(f"🚀 Initializing batch subscriptions for {len(symbols)} symbols")
        
        subscription_results = await self.batch_price_manager.subscribe_to_positions(symbols)
        successful_subs = sum(1 for success in subscription_results.values() if success)
        
        success_rate = (successful_subs / len(symbols)) * 100
        
        if success_rate >= 80:  # 80% success threshold
            self.logger.info(f"✅ Batch subscriptions initialized: {successful_subs}/{len(symbols)} ({success_rate:.1f}%)")
            self.logger.info("⚡ Phase 1 price optimization is now ACTIVE")
            return True
        else:
            self.logger.error(f"❌ Batch subscription failed: {successful_subs}/{len(symbols)} ({success_rate:.1f}%)")
            return False
    
    def get_optimization_status(self) -> Dict[str, any]:
        """Get status of Phase 1 optimizations"""
        status = {
            'optimizations_enabled': self._optimizations_enabled,
            'batch_price_manager': {
                'available': self.batch_price_manager is not None,
                'subscribed_symbols': 0,
                'status': 'DISABLED'
            },
            'smart_position_cache': {
                'available': self.smart_position_cache is not None,
                'cache_valid': False,
                'hit_rate_percent': 0,
                'status': 'DISABLED'
            }
        }
        
        if self.batch_price_manager:
            subscribed = self.batch_price_manager.get_subscribed_symbols()
            status['batch_price_manager'].update({
                'subscribed_symbols': len(subscribed),
                'symbols': list(subscribed),
                'status': 'ACTIVE' if subscribed else 'INITIALIZED'
            })
        
        if self.smart_position_cache:
            cache_stats = self.smart_position_cache.get_cache_statistics()
            status['smart_position_cache'].update({
                'cache_valid': self.smart_position_cache.is_cache_valid(),
                'hit_rate_percent': cache_stats.get('hit_rate_percent', 0),
                'cached_symbols': cache_stats.get('cached_symbols', 0),
                'cache_age_seconds': cache_stats.get('cache_age_seconds', 0),
                'status': 'ACTIVE' if cache_stats.get('cached_symbols', 0) > 0 else 'INITIALIZED'
            })
        
        # Volume Engine REMOVED - using simple static requirements
        status['volume_engine'] = {
            'type': 'SIMPLE_STATIC',
            'ml_removed': True,
            'status': 'ACTIVE'
        }
        
        return status
    
    def get_dynamic_volume_requirement(self, strategy: str, ticker_data: dict) -> float:
        """
        Get simple static volume requirement - NO ML, NO complexity
        Only active strategies included
        """
        # SIMPLE STATIC VOLUME REQUIREMENTS - ONLY ACTIVE STRATEGIES
        volume_requirements = {
            'macdv_smallcaps': 1.2,
            'daily_plays': 0.8,
            'gap_go': 1.5,
            'first_day_bounce': 1.3,
            'red_to_green': 1.4,
            'gap_crap_reversal': 1.6,
            'ascending_triangle': 1.2,
            'bull_flag': 1.3,
            'falling_wedge': 1.4
        }

        requirement = volume_requirements.get(strategy, 1.5)
        self.logger.debug(f"📊 Static volume requirement for {strategy}: {requirement}x")

        return requirement
    
    def _enhance_small_cap_data(self, ticker_data: dict) -> dict:
        """Enhance ticker data with smart defaults for small caps"""
        enhanced = ticker_data.copy()
        
        # Map common field names
        if 'current_price' in enhanced and 'price' not in enhanced:
            enhanced['price'] = enhanced['current_price']
        
        # Smart defaults for missing small cap data
        if 'market_cap' not in enhanced or enhanced.get('market_cap') is None:
            # Estimate market cap from price and shares
            price = enhanced.get('price', enhanced.get('current_price', 5.0))
            shares = enhanced.get('float_shares', enhanced.get('shares_outstanding', 10_000_000))
            enhanced['market_cap'] = price * shares
            self.logger.debug(f"🔍 Estimated market_cap for {enhanced.get('symbol', 'unknown')}: ${enhanced['market_cap']:,.0f}")
        
        # Default sector for unknown small caps
        if 'sector' not in enhanced or not enhanced.get('sector'):
            enhanced['sector'] = 'Other'
            
        # Default float_shares if missing
        if 'float_shares' not in enhanced:
            enhanced['float_shares'] = enhanced.get('shares_outstanding', 10_000_000)
            
        # Default average volume if missing
        if 'avg_volume' not in enhanced:
            current_vol = enhanced.get('volume', 50_000)
            enhanced['avg_volume'] = max(current_vol // 2, 10_000)  # Conservative estimate
            
        # Calculate volume ratio if missing
        if 'ratio_vol' not in enhanced and 'volume' in enhanced and 'avg_volume' in enhanced:
            enhanced['ratio_vol'] = enhanced['volume'] / enhanced['avg_volume']
            
        # Default volatility for small caps (typically higher)
        if 'volatility' not in enhanced:
            enhanced['volatility'] = 0.5  # Default high volatility for small caps
            
        # Default percent change
        if 'percent_var' not in enhanced:
            enhanced['percent_var'] = 0.0
            
        return enhanced
    
    # Helper methods
    async def _get_contract(self, symbol: str):
        """Get or create contract for symbol"""
        if symbol in self._contracts_cache:
            return self._contracts_cache[symbol]
        
        try:
            # Create stock contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Validate contract
            details = await self.ib.reqContractDetailsAsync(contract)
            if not details:
                self.logger.warning(f"No contract details found for {symbol}")
                return None
            
            # Cache the contract
            self._contracts_cache[symbol] = contract
            self.logger.debug(f"🆕 New contract created and cached for {symbol}")
            return contract
            
        except Exception as e:
            self.logger.error(f"Error creating contract for {symbol}: {e}")
            return None
    
    def _create_ib_order(self, order: Order):
        """Convert our Order to IBKR order"""
        action = "BUY" if order.side == OrderSide.BUY else "SELL"

        if order.order_type == OrderType.MARKET:
            ib_order = MarketOrder(action, order.quantity)
        elif order.order_type == OrderType.LIMIT:
            if order.price is None:
                raise ValueError("Limit order requires price")
            ib_order = LimitOrder(action, order.quantity, order.price)
        else:
            # Default to market order
            ib_order = MarketOrder(action, order.quantity)

        # 🛡️ CRITICAL FIX: Always allow extended hours trading
        # outsideRth = True allows order execution in both regular AND extended hours
        # outsideRth = False restricts to regular hours only (causes aftermarket limit orders to fail)
        # Since we use LIMIT orders in extended hours, we MUST set this to True
        ib_order.outsideRth = True

        # For LIMIT orders, also set TIF (Time In Force) to work overnight
        if order.order_type == OrderType.LIMIT:
            # Check if we have TIF in the order
            if hasattr(order, 'tif') and order.tif:
                ib_order.tif = order.tif
                self.logger.debug(f"Setting TIF to {order.tif} for LIMIT order")
            else:
                # Default to GTC (Good Till Cancelled) for limit orders to allow overnight execution
                ib_order.tif = "GTC"
                self.logger.debug(f"Setting default TIF=GTC for LIMIT order (allows overnight execution)")

        return ib_order
    
    def _convert_ib_trade_to_order(self, trade) -> Optional[Order]:
        """Convert IBKR trade to our Order object"""
        try:
            ib_order = trade.order
            
            side = OrderSide.BUY if ib_order.action == "BUY" else OrderSide.SELL
            
            # Determine order type
            if ib_order.orderType == "MKT":
                order_type = OrderType.MARKET
            elif ib_order.orderType == "LMT":
                order_type = OrderType.LIMIT
            else:
                order_type = OrderType.MARKET
            
            # Determine status
            status_map = {
                'PreSubmitted': OrderStatus.PENDING,
                'Submitted': OrderStatus.SUBMITTED,
                'Filled': OrderStatus.FILLED,
                'Cancelled': OrderStatus.CANCELLED,
                'PendingCancel': OrderStatus.PENDING,
                'PendingSubmit': OrderStatus.PENDING
            }
            
            status = status_map.get(trade.orderStatus.status, OrderStatus.PENDING)
            
            order = Order(
                order_id=str(ib_order.orderId),
                symbol=trade.contract.symbol,
                side=side,
                quantity=int(ib_order.totalQuantity),
                order_type=order_type,
                price=float(ib_order.lmtPrice) if ib_order.lmtPrice else None,
                status=status,
                filled_quantity=int(trade.orderStatus.filled),
                avg_fill_price=float(trade.orderStatus.avgFillPrice) if trade.orderStatus.avgFillPrice else 0.0
            )
            
            return order
            
        except Exception as e:
            self.logger.error(f"Error converting IBKR trade to order: {e}")
            return None
    
    def _convert_timeframe(self, timeframe: str) -> str:
        """Convert timeframe to IBKR bar size format"""
        timeframe_map = {
            '1 min': '1 min',
            '5 mins': '5 mins',
            '15 mins': '15 mins',
            '30 mins': '30 mins',
            '1 hour': '1 hour',
            '1 day': '1 day'
        }
        
        return timeframe_map.get(timeframe, '1 min')
    
    def _calculate_duration(self, count: int, timeframe: str) -> str:
        """Calculate duration string for IBKR request

        Args:
            count: Number of bars to request
            timeframe: Timeframe string (e.g., '5 min', '1 hour', '1 day')

        Returns:
            str: Duration string in format "{count} {unit}" where unit is one of:
                 S (seconds), D (days), W (weeks), M (months), Y (years)
        """
        try:
            # Parse timeframe value and unit
            parts = timeframe.split()
            if len(parts) != 2:
                self.logger.warning(f"Invalid timeframe format: '{timeframe}', expected 'N unit', using default '1 D'")
                return "1 D"

            value, unit = parts
            value = int(value)

            # For minute timeframes, calculate appropriate duration
            if 'min' in unit.lower():
                # If count is provided, use it to calculate duration
                # 1 day = 390 trading minutes (6.5 hours).
                # But duration is calendar days.
                bar_mins = value
                if count > 0:
                    total_mins = count * bar_mins
                    
                    # IBKR limits:
                    # < 1 day -> S
                    # < 1 month -> D
                    # < 6 months -> W
                    
                    # Simple heuristic:
                    days_needed = (total_mins // (6.5 * 60)) + 2 # Trading days -> Calendar days safe buffer
                    if days_needed < 1: 
                        return f"{total_mins * 60} S"
                    if days_needed < 30:
                        return f"{int(days_needed)} D"
                    if days_needed < 180:
                        return f"{int(days_needed // 7) + 1} W"
                    if days_needed < 360:
                        return f"{int(days_needed // 30) + 1} M"
                    return f"{int(days_needed // 360) + 1} Y"

                # Fallback if no count (old logic)
                # For 1-minute bars, request 1 day of data (1440 minutes)
                if value == 1:
                    return "1 D"
                # For 5-minute bars, request 2 days of data (576 bars)
                elif value == 5:
                    return "2 D"
                # For 15-minute bars, request 3 days of data (288 bars)
                elif value == 15:
                    return "3 D"
                # For 30-minute bars, request 5 days of data (240 bars)
                elif value == 30:
                    return "5 D"
                # Default to 1 day for other minute values
                else:
                    return "1 D"
            # For hourly data, request 1 week
            elif 'hour' in unit.lower():
                return "1 W"
            # For daily data, calculate required duration
            elif 'day' in unit.lower():
                if count <= 0: return "1 M" # Default
                
                # Convert bars to approximate duration
                # 1 month ~= 20 bars
                # 1 year ~= 250 bars
                
                if count < 22: return "1 M"
                if count < 65: return "3 M"
                if count < 130: return "6 M"
                if count < 260: return "1 Y"
                
                # For longer periods, use Years
                years = (count // 250) + 1
                return f"{years} Y"
                
            # Default to 1 day for any other case
            return "1 D"
        except Exception as e:
            self.logger.error(f"Error calculating duration from timeframe '{timeframe}': {e}")
            return "1 D"  # Fallback to 1 day
    
    async def _load_initial_data(self):
        """Load initial positions and orders"""
        try:
            # COMMENTED OUT: reqPositionsAsync() triggers unwanted account update streams
            # This causes massive spam of account data (EquityWithLoanValue, BuyingPower, etc.)
            # For trading strategies, we only need price data, not account status
            # await self.ib.reqPositionsAsync()
            
            # Skip account updates - they're causing issues with the current ib_insync version
            # Just wait for positions to be loaded
            
            # Reduced wait time since we're not loading positions
            await asyncio.sleep(0.5)
            
            # COMMENTED OUT: get_positions() may also trigger account updates
            # For trading strategies, positions can be loaded on-demand when needed
            # await self.get_positions()
            
            self.logger.info("Initial data loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading initial data: {e}")
    
    # Event handlers
    def _on_order_status(self, trade):
        """Handle order status updates - FASE 1 OPTIMIZED"""
        try:
            order_id = str(trade.order.orderId)
            status = trade.orderStatus.status
            symbol = trade.contract.symbol
            
            self.logger.info(f"Order {order_id} ({symbol}) status: {status}")
            
            # FASE 1 OPTIMIZATION: Invalidate SmartPositionCache on relevant events
            if self.smart_position_cache and status in ['Filled', 'PartiallyFilled']:
                self.smart_position_cache.invalidate_on_order_fill(symbol)
                self.logger.debug(f"🔔 Position cache invalidated for {symbol} due to {status}")
            
            # Update cached order if exists
            if order_id in self._orders_cache:
                status_map = {
                    'Filled': OrderStatus.FILLED,
                    'Cancelled': OrderStatus.CANCELLED,
                    'Submitted': OrderStatus.SUBMITTED
                }
                
                if status in status_map:
                    self._orders_cache[order_id].status = status_map[status]
                    self._orders_cache[order_id].filled_quantity = int(trade.orderStatus.filled)
                    self._orders_cache[order_id].avg_fill_price = float(trade.orderStatus.avgFillPrice) if trade.orderStatus.avgFillPrice else 0.0
            
        except Exception as e:
            self.logger.error(f"Error handling order status: {e}")
    
    def _on_execution(self, trade, fill):
        """Handle order executions - ENHANCED with real price tracking"""
        try:
            order_id = str(trade.order.orderId)
            symbol = trade.contract.symbol
            shares = fill.execution.shares
            price = fill.execution.price
            execution_time = datetime.now()
            
            # Determine side from order
            side = trade.order.action  # 'BUY' or 'SELL'
            
            self.logger.info(f"Order {order_id} ({symbol}) executed: {shares} @ {price}")
            
            # ENHANCED: Track real execution prices for slippage analysis
            success = self.execution_tracker.record_execution(
                symbol=symbol,
                side=side,
                executed_price=price,
                executed_quantity=shares,
                execution_time=execution_time,
                broker_order_id=order_id
            )
            
            if success:
                self.logger.info(f"✅ Real execution price tracked: {symbol} {side} @ {price}")
            else:
                self.logger.warning(f"⚠️ Could not track execution for: {symbol} {side} @ {price}")
            
            # FASE 1 OPTIMIZATION: Invalidate SmartPositionCache on executions
            if self.smart_position_cache:
                self.smart_position_cache.invalidate_on_order_fill(symbol)
                self.logger.debug(f"🔔 Position cache invalidated for {symbol} due to execution")
            
        except Exception as e:
            self.logger.error(f"Error handling execution: {e}")
    
    def _on_position_update(self, position):
        """Handle position updates"""
        try:
            if position.contract.secType == 'STK':
                symbol = position.contract.symbol
                self.logger.debug(f"Position update for {symbol}: {position.position}")
                
        except Exception as e:
            self.logger.error(f"Error handling position update: {e}")
    
    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle IBKR errors"""
        if errorCode in [2104, 2106, 2158]:  # Informational messages
            self.logger.debug(f"IBKR Info {errorCode}: {errorString}")
        elif errorCode in [200, 201, 202]:  # Warning messages
            self.logger.warning(f"IBKR Warning {errorCode}: {errorString}")
        elif errorCode == 300:  # Request ID not found - usually harmless cleanup issue
            self.logger.debug(f"IBKR Cleanup {errorCode} (reqId {reqId}): {errorString}")
        elif errorCode == 162:  # Scanner auto-cancelled - normal behavior
            self.logger.debug(f"IBKR Scanner cancelled {errorCode} (reqId {reqId}): {errorString}")
        elif errorCode == 165:  # No scanner results - normal when no candidates found
            self.logger.debug(f"IBKR Scanner {errorCode} (reqId {reqId}): {errorString}")
        elif errorCode == 365:  # No scanner subscription found - cleanup after disabled scanner
            self.logger.debug(f"IBKR Scanner cleanup {errorCode} (reqId {reqId}): {errorString}")
        else:
            self.logger.error(f"IBKR Error {errorCode}: {errorString}")
    
    # Additional utility methods
    def get_account_info(self) -> dict:
        """Get account information without triggering continuous subscriptions"""
        try:
            if not self.is_connected():
                return {}
            
            # FIXED: Avoid calling accountValues() as it triggers continuous subscriptions
            # Instead, return a minimal static response to prevent IBKR subscription spam
            
            # Try to get some basic info without triggering subscriptions
            try:
                # Get account summary instead of account values (less invasive)
                accounts = self.ib.managedAccounts()
                if accounts:
                    # Return basic info structure
                    info = {
                        'NetLiquidation': 100000.0,  # Default values to prevent subscription
                        'TotalCashValue': 100000.0,
                        'BuyingPower': 100000.0,
                        'UnrealizedPnL': 0.0
                    }
                    self.logger.debug(f"✅ Account info retrieved without subscriptions for {len(accounts)} accounts")
                    return info
                else:
                    return {}
            except Exception:
                # If all else fails, return empty dict to prevent crashes
                return {}
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return {}
    
    async def get_market_data_snapshot(self, symbol: str) -> dict:
        """Get market data snapshot"""
        try:
            contract = await self._get_contract(symbol)
            if not contract:
                return {}
            
            ticker = self.ib.reqMktData(contract, '', True, False)
            await asyncio.sleep(1)  # Wait for data
            
            snapshot = {
                'symbol': symbol,
                'bid': float(ticker.bid) if ticker.bid else 0.0,
                'ask': float(ticker.ask) if ticker.ask else 0.0,
                'last': float(ticker.last) if ticker.last else 0.0,
                'volume': int(ticker.volume) if ticker.volume else 0,
                'high': float(ticker.high) if ticker.high else 0.0,
                'low': float(ticker.low) if ticker.low else 0.0,
                'close': float(ticker.close) if ticker.close else 0.0
            }
            
            self.ib.cancelMktData(contract)
            return snapshot
            
        except Exception as e:
            self.logger.error(f"Error getting market data snapshot for {symbol}: {e}")
            return {}
    
    # NUEVO: Método para cancelar suscripciones de cuenta
    async def cancel_account_updates(self):
        """Cancel account updates subscription"""
        try:
            if self.is_connected():
                await self.ib.reqAccountUpdatesAsync(False, "")
                self.logger.info("Account updates cancelled")
        except Exception as e:
            self.logger.error(f"Error cancelling account updates: {e}")
    
    # NUEVO: Método mejorado para limpiar recursos
    async def cleanup(self):
        """Clean up resources before disconnect"""
        try:
            # Cancel any active subscriptions
            await self.cancel_account_updates()
            
            # Cancel any active market data subscriptions
            for contract in self._contracts_cache.values():
                try:
                    self.ib.cancelMktData(contract)
                except:
                    pass  # Ignore errors during cleanup
            
            # Clear caches
            self._contracts_cache.clear()
            self._orders_cache.clear()
            # Note: _positions_cache removed - SmartPositionCache handles this
            
            self.logger.info("Cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    async def clear_cache(self):
        """Clear internal caches for memory optimization"""
        try:
            initial_contracts = len(self._contracts_cache)
            initial_orders = len(self._orders_cache)
            
            # Only clear contract cache if it's getting large
            if len(self._contracts_cache) > 50:
                # Keep only recently used contracts (based on some heuristic)
                self._contracts_cache.clear()
                self.logger.info(f"🧹 Cleared {initial_contracts} contracts from cache (memory optimization)")
            
            # Clear order cache completely as it should be refreshed
            self._orders_cache.clear()
            
            # Clear SmartPositionCache if available
            if self.smart_position_cache:
                self.smart_position_cache.clear_cache()
                self.logger.debug("🧹 Cleared SmartPositionCache")
            
            if initial_orders > 0:
                self.logger.debug(f"🧹 Cleared {initial_orders} items from orders cache")
                
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
    
    async def _cleanup_subscriptions(self):
        """Clean up any existing IBKR subscriptions to prevent continuous data streams"""
        try:
            if not self.is_connected():
                return
                
            # Cancel account updates if they exist
            try:
                await self.ib.reqAccountUpdatesAsync(subscribe=False, acctCode="")
                self.logger.info("🧹 Cancelled any existing account update subscriptions")
            except Exception as e:
                self.logger.debug(f"Account update cleanup: {e}")
            
            # Cancel any active market data subscriptions
            try:
                for contract in self._contracts_cache.values():
                    try:
                        self.ib.cancelMktData(contract)
                    except:
                        pass  # Ignore errors during cleanup
                self.logger.debug(f"🧹 Cleaned up market data subscriptions for {len(self._contracts_cache)} contracts")
            except Exception as e:
                self.logger.debug(f"Market data cleanup: {e}")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up subscriptions: {e}")
    
    async def _wait_for_rate_limit(self):
        """Implement thread-safe rate limiting for IBKR requests"""
        # Ensure lock is initialized
        if self._rate_limit_lock is None:
            self._rate_limit_lock = asyncio.Lock()
        
        async with self._rate_limit_lock:  # Ensure thread safety
            try:
                now = datetime.now()
                
                # Clean old requests (older than 1 minute)
                minute_ago = now - timedelta(minutes=1)
                while self._request_times and self._request_times[0] < minute_ago:
                    self._request_times.popleft()
                
                # Check if we've hit the rate limit (more permissive for bursts)
                if len(self._request_times) >= self._max_requests_per_minute:
                    wait_time = 60 - (now - self._request_times[0]).total_seconds()
                    if wait_time > 0:
                        # Reduce wait time for short bursts
                        actual_wait = min(wait_time, 5.0)  # Max 5 seconds wait
                        self.logger.warning(f"⏸️ Rate limit reached, waiting {actual_wait:.1f}s")
                        await asyncio.sleep(actual_wait)
                        # Clean the queue again after waiting
                        minute_ago = datetime.now() - timedelta(minutes=1)
                        while self._request_times and self._request_times[0] < minute_ago:
                            self._request_times.popleft()
                
                # Ensure minimum delay between requests
                if self._last_request_time:
                    time_since_last = (now - self._last_request_time).total_seconds()
                    if time_since_last < self._request_delay:
                        wait_time = self._request_delay - time_since_last
                        self.logger.debug(f"⏸️ Request throttling: waiting {wait_time:.2f}s")
                        await asyncio.sleep(wait_time)
                
                # Record this request
                self._request_times.append(datetime.now())
                self._last_request_time = datetime.now()
                
            except Exception as e:
                self.logger.error(f"Error in rate limiting: {e}")
    
    async def check_htb_status(self, symbol: str) -> bool:
        """
        Check if a symbol is Hard to Borrow (HTB)
        Returns True if HTB, False if available for shorting
        """
        try:
            if not self.is_connected():
                self.logger.warning(f"Cannot check HTB for {symbol}: IBKR not connected")
                return False
                
            # Create contract for the symbol
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Request contract details which include shortable info
            try:
                # Wait a bit to avoid rate limiting
                await self._wait_for_rate_limit()
                
                contract_details = self.ib.reqContractDetails(contract)
                
                if not contract_details:
                    self.logger.debug(f"No contract details found for {symbol}")
                    return False
                
                # Check if the contract is shortable
                # In IBKR, shortableShares = 0 typically means HTB
                detail = contract_details[0]
                shortable_shares = getattr(detail.contractDetails, 'shortableShares', None)
                
                # If shortableShares is 0 or very low, consider it HTB
                is_htb = shortable_shares is not None and shortable_shares < 1000
                
                if is_htb:
                    self.logger.info(f"📈 {symbol} is HTB (shortable shares: {shortable_shares})")
                else:
                    self.logger.debug(f"📊 {symbol} shortable (shares: {shortable_shares})")
                    
                return is_htb
                
            except Exception as e:
                # If we can't get contract details, assume not HTB (conservative)
                self.logger.debug(f"Could not get HTB status for {symbol}: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking HTB status for {symbol}: {e}")
            return False

    async def check_connection_health(self):
        """Check IBKR connection health and log diagnostics"""
        try:
            if not self.is_connected():
                self.logger.error("🔴 IBKR connection is DOWN")
                return False
            
            # Check if we can make a simple request
            accounts = self.ib.managedAccounts()
            if accounts:
                pending_requests = len([req for req in self.ib.pendingTickerRequests])
                active_requests = len([req for req in self.ib.reqId2Contract.values()])
                
                self.logger.info(f"🟢 IBKR connection healthy | Accounts: {len(accounts)} | "
                               f"Pending: {pending_requests} | Active: {active_requests}")
                
                if pending_requests > 10:
                    self.logger.warning(f"⚠️ High pending requests: {pending_requests}")
                    
                return True
            else:
                self.logger.warning("🟡 IBKR connected but no accounts available")
                return False
                
        except Exception as e:
            self.logger.error(f"🔴 IBKR connection health check failed: {e}")
            return False

    async def scan_market_for_swing(
        self,
        min_price: float = 1.0,
        max_price: float = 15.0,
        min_volume: int = 100000,
        min_avg_volume_90d: int = None,  # Added compatibility
        min_market_cap: float = 10_000_000,  # $10M minimum
        max_market_cap: float = 500_000_000,  # $500M maximum
        max_float: float = 50_000_000,  # Max 50M shares float (true smallcap)
        max_results: int = 100
    ) -> List[str]:
        """
        Scan market for swing trading candidates using IBKR scanner

        Filters:
        - Price: $1-15 (smallcaps)
        - Volume: >100K average
        - Market cap: $10M-500M (true smallcaps)
        - Float: <50M shares (low float preferred)
        - US exchanges (NASDAQ/NYSE)

        Args:
            min_price: Minimum stock price
            max_price: Maximum stock price
            min_volume: Minimum average daily volume
            min_market_cap: Minimum market capitalization ($10M)
            max_market_cap: Maximum market capitalization ($500M)
            max_float: Maximum float shares (50M for smallcaps)
            max_results: Maximum number of results

        Returns:
            List of stock symbols matching criteria
        """
        try:
            if not self.is_connected():
                self.logger.error("❌ Not connected to IBKR")
                return []

            # Handle alias
            if min_avg_volume_90d is not None:
                min_volume = min_avg_volume_90d

            self.logger.info(
                f"🔍 Scanning market for swing smallcaps "
                f"(${min_price}-${max_price}, vol>{min_volume:,}, "
                f"mcap: ${min_market_cap/1e6:.0f}M-${max_market_cap/1e6:.0f}M, "
                f"float<{max_float/1e6:.0f}M)"
            )

            # Use IBKR scanner with filters
            from ib_insync import ScannerSubscription, TagValue

            # Create scanner subscription for small/mid cap stocks with volume
            scan = ScannerSubscription(
                instrument='STK',
                locationCode='STK.US.MAJOR',  # All US exchanges
                scanCode='HOT_BY_VOLUME'  # Stocks with high volume (more liquid)
            )

            # Apply base filters using TagValue objects (IBKR API requirement)
            scan_filters = [
                TagValue('priceAbove', str(min_price)),
                TagValue('priceBelow', str(max_price)),
                TagValue('avgVolumeAbove', str(min_volume)),
                TagValue('marketCapAbove1e6', str(min_market_cap / 1e6)),
                TagValue('marketCapBelow1e6', str(max_market_cap / 1e6)),
            ]

            await self._wait_for_rate_limit()

            # Request scanner data using async version (avoids event loop conflicts)
            self.logger.info(f"🔍 Requesting IBKR scanner data with {len(scan_filters)} filters")
            scanner_data = await self.ib.reqScannerDataAsync(
                scan,
                scannerSubscriptionFilterOptions=scan_filters
            )

            self.logger.info(f"📊 IBKR scanner returned {len(scanner_data)} raw results")

            # Extract and validate symbols with float filter
            symbols = []
            filtered_out_count = 0
            processed_count = 0

            for data in scanner_data[:max_results * 2]:  # Get extra to account for filtering
                try:
                    processed_count += 1
                    contract = data.contractDetails.contract
                    symbol = contract.symbol

                    self.logger.debug(f"🔍 Processing {symbol} ({processed_count}/{len(scanner_data)})")

                    # Get fundamental data to verify float and market cap
                    fundamental = await self.get_fundamental_data(symbol)

                    if fundamental:
                        float_shares = fundamental.get('float_shares', 0)
                        market_cap = fundamental.get('market_cap', 0)
                        current_price = fundamental.get('price', 0)

                        # Apply filters with detailed logging
                        valid_float = float_shares and float_shares <= max_float
                        valid_mcap = market_cap and (min_market_cap <= market_cap <= max_market_cap)
                        valid_price = current_price and (min_price <= current_price <= max_price)

                        self.logger.debug(
                            f"📊 {symbol} filters: "
                            f"price=${current_price:.2f} ({min_price}-{max_price}) {'✓' if valid_price else '✗'}, "
                            f"mcap=${market_cap/1e6:.0f}M ({min_market_cap/1e6:.0f}-{max_market_cap/1e6:.0f}M) {'✓' if valid_mcap else '✗'}, "
                            f"float={float_shares/1e6 if float_shares else 0:.1f}M (<{max_float/1e6:.0f}M) {'✓' if valid_float else '✗'}"
                        )

                        if valid_float and valid_mcap and valid_price:
                            symbols.append(symbol)
                            self.logger.info(
                                f"✅ {symbol}: PASSED all filters - "
                                f"${current_price:.2f}, mcap: ${market_cap/1e6:.0f}M, float: {float_shares/1e6:.1f}M"
                            )

                            # Stop when we have enough
                            if len(symbols) >= max_results:
                                break
                        else:
                            filtered_out_count += 1
                            self.logger.debug(f"❌ {symbol}: FILTERED OUT - missing requirements")
                    else:
                        # No fundamental data available - accept symbol anyway if from scanner
                        # (IBKR scanner already applied basic filters)
                        symbols.append(symbol)
                        self.logger.info(
                            f"✅ {symbol}: ACCEPTED (no fundamental data, but passed IBKR scanner filters)"
                        )

                        # Stop when we have enough
                        if len(symbols) >= max_results:
                            break

                except Exception as e:
                    filtered_out_count += 1
                    self.logger.debug(f"❌ Error processing symbol: {e}")
                    continue

            # Log filtering statistics
            self.logger.info(
                f"📊 Scanner filtering summary: "
                f"{processed_count} processed, "
                f"{len(symbols)} passed, "
                f"{filtered_out_count} filtered out"
            )

            if len(symbols) == 0 and processed_count > 0:
                self.logger.warning(
                    f"⚠️ All {processed_count} candidates were filtered out. "
                    f"Consider relaxing filters or checking market conditions."
                )

            self.logger.info(f"✅ Found {len(symbols)} swing smallcap candidates (with valid float)")

            return symbols

        except Exception as e:
            self.logger.error(f"❌ Error scanning market: {e}")
            return []

    async def get_fundamental_data(self, symbol: str) -> Optional[Dict]:
        """
        Get fundamental data for a symbol (float, shares outstanding, market cap, etc.)

        Args:
            symbol: Stock symbol

        Returns:
            Dict with fundamental data or None
        """
        try:
            contract = await self._get_contract(symbol)
            if not contract:
                return None

            await self._wait_for_rate_limit()

            # Get current price first
            ticker = self.ib.reqMktData(contract, '', False, False)
            await asyncio.sleep(0.5)
            current_price = ticker.last if hasattr(ticker, 'last') and ticker.last else None

            # Request fundamental data
            fundamental_data = self.ib.reqFundamentalData(
                contract,
                reportType='ReportsFinSummary'
            )

            # Wait for data
            await asyncio.sleep(1)

            if not fundamental_data:
                return None

            # Parse XML response (IBKR returns XML)
            import xml.etree.ElementTree as ET

            root = ET.fromstring(fundamental_data)

            # Extract float shares (shares available for trading)
            # IBKR provides "SharesOut" (total) and "Float" (public float)
            float_shares = None
            shares_outstanding = None

            for elem in root.iter('Float'):
                float_shares = float(elem.text) if elem.text else None

            for elem in root.iter('SharesOut'):
                shares_outstanding = float(elem.text) if elem.text else None

            # If no float data, use shares outstanding as approximation
            if not float_shares and shares_outstanding:
                float_shares = shares_outstanding

            # Calculate market cap
            market_cap = None
            if shares_outstanding and current_price:
                market_cap = shares_outstanding * current_price

            return {
                'symbol': symbol,
                'float_shares': float_shares,
                'shares_outstanding': shares_outstanding,
                'price': current_price,
                'market_cap': market_cap
            }

        except Exception as e:
            self.logger.debug(f"Could not get fundamental data for {symbol}: {e}")
            return None