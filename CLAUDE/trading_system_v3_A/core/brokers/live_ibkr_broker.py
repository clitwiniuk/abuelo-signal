import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from core.interfaces.broker_adapter import AbstractBroker, BrokerOrder, BrokerPosition

class LiveIBKRBroker(AbstractBroker):
    """
    Live IBKR Broker Adapter using ib_insync.
    Wraps existing IBKRAdapter to conform to AbstractBroker while exposing IBKR-specific features.

    This adapter:
    - Implements AbstractBroker interface for strategy engine compatibility
    - Exposes IBKRAdapter attributes (batch_price_manager, smart_position_cache) for worker access
    - Prevents subscription leaks by proper subscribe/unsubscribe management
    """

    def __init__(self, ib_client: Any, account_id: str, ibkr_adapter: Any = None, logger: Optional[logging.Logger] = None):
        """
        Args:
            ib_client: Configured and connected IB instance (ib_insync)
            account_id: Account ID (e.g. U1234567)
            ibkr_adapter: Full IBKRAdapter instance (optional, for accessing batch_price_manager, etc.)
            logger: Logger instance
        """
        self.ib = ib_client
        self.account_id = account_id
        self._ibkr_adapter = ibkr_adapter
        self.logger = logger or logging.getLogger("LiveIBKRBroker")

        # Expose IBKRAdapter attributes if available (for worker compatibility)
        if ibkr_adapter:
            self.batch_price_manager = getattr(ibkr_adapter, 'batch_price_manager', None)
            self.smart_position_cache = getattr(ibkr_adapter, 'smart_position_cache', None)
        else:
            self.batch_price_manager = None
            self.smart_position_cache = None

        # Cache for account summary to prevent subscription leaks
        self._account_summary_cache = {}
        self._account_summary_last_update = None
        self._account_summary_cache_duration = timedelta(seconds=5)  # Cache for 5 seconds
        
    async def get_account_summary(self) -> Dict[str, Any]:
        """Fetch real account values with caching to prevent subscription leaks"""
        try:
            # Check if cache is still valid
            now = datetime.now()
            if (self._account_summary_last_update and
                now - self._account_summary_last_update < self._account_summary_cache_duration):
                self.logger.debug("Returning cached account summary")
                return self._account_summary_cache

            # We want 'NetLiquidation', 'TotalCashValue' (or 'Cash')
            # IBKR returns a list of AccountValue objects
            tags = ['NetLiquidation', 'TotalCashValue', 'BuyingPower']

            # CRITICAL FIX: Use reqAccountUpdatesAsync instead of accountSummaryAsync
            # accountSummaryAsync creates persistent subscriptions that leak
            # reqAccountUpdatesAsync is a one-time request
            self.logger.debug(f"Requesting account summary for {self.account_id}")

            # Subscribe to account updates
            await self.ib.reqAccountUpdatesAsync(subscribe=True, acctCode=self.account_id)

            # Wait briefly for data to populate
            await asyncio.sleep(0.5)

            # Get account values
            account_values = self.ib.accountValues(account=self.account_id)

            # Unsubscribe immediately to prevent leak
            await self.ib.reqAccountUpdatesAsync(subscribe=False, acctCode=self.account_id)

            result = {}
            for item in account_values:
                if item.tag in tags:
                     try:
                         result[item.tag] = float(item.value)
                     except ValueError:
                         result[item.tag] = item.value

            # Alias Cash
            if 'TotalCashValue' in result:
                result['Cash'] = result['TotalCashValue']

            # Update cache
            self._account_summary_cache = result
            self._account_summary_last_update = now
            self.logger.debug(f"Account summary cached: {result}")

            return result
        except Exception as e:
            self.logger.error(f"Error fetching account summary: {e}")
            # Return cached data if available, otherwise empty dict
            return self._account_summary_cache if self._account_summary_cache else {}

    async def get_all_positions(self) -> List[BrokerPosition]:
        try:
            # Current positions from IB
            # ib.positions() is synchronous getter of cached positions, usually updated via subscription
            # Ensure we have fresh data?
            # self.ib.reqPositions() # Triggers async update. 
            # In live system, we usually subscribe at startup.
            
            ib_positions = self.ib.positions(self.account_id)
            result = []
            
            for p in ib_positions:
                contract = p.contract
                symbol = contract.symbol
                
                # In Backtrader style, we want standardized View
                # Market price might need to be fetched if not in Position object (IB Position obj has avgCost, but not current price directly, usually separate ticker)
                
                # Try to get market Price from active tickers if available
                ticker = self.ib.ticker(contract)
                market_price = ticker.marketPrice() if ticker else 0.0
                
                # Calculate metrics
                mkt_val = p.position * market_price
                unrealized = mkt_val - (p.position * p.avgCost)
                
                bp = BrokerPosition(
                    symbol=symbol,
                    quantity=p.position,
                    avg_cost=p.avgCost,
                    market_price=market_price,
                    market_value=mkt_val,
                    unrealized_pnl=unrealized,
                    realized_pnl=0.0, # IB doesn't give realized per position easily here
                    account=p.account
                )
                result.append(bp)
                
            return result
        except Exception as e:
            self.logger.error(f"Error fetching positions: {e}")
            return []

    async def get_position(self, symbol: str) -> Optional[BrokerPosition]:
        all_pos = await self.get_all_positions()
        for p in all_pos:
            if p.symbol == symbol:
                return p
        return None
    
    async def place_order(self, order: BrokerOrder) -> Any:
        try:
            from ib_insync import Stock, MarketOrder, LimitOrder, StopOrder
            
            # Simple Contract Mapping (Stocks only for now, 'SMART', 'USD')
            contract = Stock(order.symbol, 'SMART', 'USD')
            
            ib_order = None
            if order.order_type == 'MKT':
                ib_order = MarketOrder(order.action, abs(order.quantity))
            elif order.order_type == 'LMT' and order.limit_price:
                ib_order = LimitOrder(order.action, abs(order.quantity), order.limit_price)
            elif order.order_type == 'STP' and order.stop_price:
                ib_order = StopOrder(order.action, abs(order.quantity), order.stop_price)
            else:
                self.logger.error(f"Unsupported order type: {order.order_type}")
                return None
                
            if order.algo_strategy:
                ib_order.orderRef = order.algo_strategy
                
            trade = self.ib.placeOrder(contract, ib_order)
            self.logger.info(f"Placed IBKR {order.action} {order.quantity} {order.symbol} [Ref: {ib_order.orderRef}]")
            
            # Wait for fill? Backtrader default is fire and forget, but returning Trade object allows tracking
            return trade
            
        except Exception as e:
            self.logger.error(f"Error placing IBKR order: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        # Need to implement mapping from generic ID to IBKR order object
        # V3 implementation usually holds references or cancels by permId
        self.logger.warning("Cancel order not fully implemented in LiveBroker adapter yet")
        return False
    
    async def get_pending_orders(self) -> List[Any]:
        return self.ib.openOrders()

    async def get_last_price(self, symbol: str) -> float:
        try:
            from ib_insync import Stock
            contract = Stock(symbol, 'SMART', 'USD')
            # Request market data
            ticker = self.ib.reqMktData(contract, '', False, False)
            # Wait a bit? Or assume data is flowing.
            # In live, we might want to wait up to X ms
            count = 0
            while count < 5 and (not ticker.last and not ticker.close):
                await asyncio.sleep(0.1)
                count += 1
                
            price = ticker.marketPrice()
            return price
        except Exception as e:
             self.logger.error(f"Error getting price for {symbol}: {e}")
             return 0.0
             
    async def get_history(self, symbol: str, duration: str, bar_size: str) -> List[Any]:
        try:
            from ib_insync import Stock, util
            contract = Stock(symbol, 'SMART', 'USD')
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True
            )
            return bars
        except Exception as e:
            self.logger.error(f"Error getting history for {symbol}: {e}")
            return []

    async def cleanup(self):
        """Clean up subscriptions to prevent leaks"""
        try:
            # Cancel account updates if subscribed
            try:
                await self.ib.reqAccountUpdatesAsync(subscribe=False, acctCode=self.account_id)
                self.logger.info("🧹 Cancelled account update subscriptions")
            except Exception as e:
                self.logger.debug(f"Account cleanup: {e}")

            # Clear cache
            self._account_summary_cache = {}
            self._account_summary_last_update = None

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
