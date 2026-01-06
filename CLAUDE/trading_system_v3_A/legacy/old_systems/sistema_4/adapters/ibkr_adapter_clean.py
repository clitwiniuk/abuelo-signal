"""
Clean IBKR Adapter for Sistema_4
Simplified version without external system dependencies
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import threading

try:
    from ib_insync import IB, Stock, MarketOrder, LimitOrder, StopOrder
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False

class IBKRAdapterClean:
    """
    Clean IBKR adapter for Sistema_4 - no external dependencies
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id

        self.logger = logging.getLogger(f"{__name__}.{client_id}")
        self.ib = None
        self.is_connected = False

        # Thread safety
        self._lock = threading.Lock()

    async def connect(self) -> bool:
        """Connect to IBKR"""
        try:
            if not IB_INSYNC_AVAILABLE:
                self.logger.error("❌ ib_insync not available - using mock mode")
                self.is_connected = True  # Mock connection
                return True

            self.ib = IB()

            # Connect with error handling
            try:
                await self.ib.connectAsync(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    timeout=10
                )
                self.is_connected = True
                self.logger.info(f"✅ IBKR connected (client_id: {self.client_id})")
                return True

            except Exception as e:
                if "already in use" in str(e).lower():
                    self.logger.error(f"❌ Client ID {self.client_id} already in use")
                else:
                    self.logger.error(f"❌ IBKR connection failed: {e}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error connecting to IBKR: {e}")
            return False

    async def disconnect(self):
        """Disconnect from IBKR"""
        try:
            if self.ib and self.is_connected:
                self.ib.disconnect()
                self.logger.info("✅ IBKR disconnected")

            self.is_connected = False
            self.ib = None

        except Exception as e:
            self.logger.error(f"❌ Error disconnecting: {e}")

    async def run_scanner(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run IBKR scanner with simplified parameters"""
        try:
            if not self.is_connected:
                self.logger.error("❌ Not connected to IBKR")
                return []

            if not IB_INSYNC_AVAILABLE:
                # Return mock data for testing
                return self._get_mock_scanner_data()

            # Use ib_insync scanner
            from ib_insync import ScannerSubscription

            scanner_sub = ScannerSubscription(
                instrument=params.get('instrument', 'STK'),
                locationCode=params.get('location_code', 'STK.US.MAJOR'),
                scanCode=params.get('scan_code', 'TOP_VOLUME_RATE'),
                numberOfRows=params.get('number_of_rows', 50),
                abovePrice=params.get('above_price'),
                belowPrice=params.get('below_price'),
                aboveVolume=params.get('above_volume'),
                marketCapAbove=params.get('market_cap_above'),
                marketCapBelow=params.get('market_cap_below'),
                stockTypeFilter=params.get('stock_type', 'ALL')
            )

            # Run scanner
            scan_data = await self.ib.reqScannerDataAsync(scanner_sub)

            results = []
            for data in scan_data:
                try:
                    # Get current market data for the contract
                    ticker = await self.ib.reqMktDataAsync(data.contractDetails.contract)
                    await asyncio.sleep(0.1)  # Rate limiting

                    # Extract relevant data
                    result = {
                        'symbol': data.contractDetails.contract.symbol,
                        'price': float(ticker.marketPrice()) if ticker.marketPrice() else 0.0,
                        'volume': int(ticker.volume) if ticker.volume else 0,
                        'volume_ratio': float(data.rank) if hasattr(data, 'rank') else 1.0,
                        'percent_change': 0.0  # Would need historical data to calculate
                    }

                    if result['symbol'] and result['price'] > 0:
                        results.append(result)

                    # Cancel market data to avoid accumulating subscriptions
                    self.ib.cancelMktData(data.contractDetails.contract)

                except Exception as e:
                    self.logger.debug(f"Error processing scan result: {e}")
                    continue

            self.logger.info(f"📊 Scanner found {len(results)} results")
            return results

        except Exception as e:
            self.logger.error(f"❌ Scanner error: {e}")
            return self._get_mock_scanner_data()

    def _get_mock_scanner_data(self) -> List[Dict[str, Any]]:
        """Return mock scanner data for testing"""
        import random

        mock_symbols = ['AAPL', 'TSLA', 'MSFT', 'AMZN', 'GOOGL', 'META', 'NVDA', 'AMD']

        results = []
        for i, symbol in enumerate(mock_symbols[:5]):  # Limit to 5 for testing
            results.append({
                'symbol': symbol,
                'price': round(random.uniform(10.0, 200.0), 2),
                'volume': random.randint(1000000, 10000000),
                'volume_ratio': round(random.uniform(1.5, 5.0), 1),
                'percent_change': round(random.uniform(-10.0, 15.0), 2)
            })

        return results

    async def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        try:
            if not self.is_connected:
                return 0.0

            if not IB_INSYNC_AVAILABLE:
                import random
                return round(random.uniform(10.0, 100.0), 2)

            contract = Stock(symbol, 'SMART', 'USD')
            ticker = await self.ib.reqMktDataAsync(contract, timeout=5)

            price = ticker.marketPrice() if ticker.marketPrice() else 0.0

            # Cancel market data subscription
            self.ib.cancelMktData(contract)

            return float(price)

        except Exception as e:
            self.logger.error(f"❌ Error getting price for {symbol}: {e}")
            return 0.0

    async def place_order(self, symbol: str, action: str, quantity: int,
                         order_type: str = "MKT", limit_price: float = 0.0) -> Optional[str]:
        """Place order (simplified)"""
        try:
            if not self.is_connected:
                self.logger.error("❌ Not connected to IBKR")
                return None

            if not IB_INSYNC_AVAILABLE:
                # Mock order placement
                order_id = f"MOCK_{symbol}_{datetime.now().strftime('%H%M%S')}"
                self.logger.info(f"📝 Mock order placed: {action} {quantity} {symbol} ({order_type})")
                return order_id

            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')

            # Create order based on type
            if order_type == "MKT":
                order = MarketOrder(action, quantity)
            elif order_type == "LMT" and limit_price > 0:
                order = LimitOrder(action, quantity, limit_price)
            else:
                self.logger.error(f"❌ Unsupported order type: {order_type}")
                return None

            # Place order
            trade = self.ib.placeOrder(contract, order)

            self.logger.info(f"📝 Order placed: {action} {quantity} {symbol} - Order ID: {trade.order.orderId}")
            return str(trade.order.orderId)

        except Exception as e:
            self.logger.error(f"❌ Error placing order: {e}")
            return None

    def is_market_open(self) -> bool:
        """Check if market is open (simplified)"""
        try:
            from datetime import datetime, time
            import pytz

            # US Eastern Time
            et_tz = pytz.timezone('US/Eastern')
            now_et = datetime.now(et_tz)

            # Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
            market_open = time(9, 30)
            market_close = time(16, 0)

            # Check if weekday and within market hours
            is_weekday = now_et.weekday() < 5  # Monday = 0, Friday = 4
            is_market_hours = market_open <= now_et.time() <= market_close

            return is_weekday and is_market_hours

        except Exception as e:
            self.logger.error(f"Error checking market hours: {e}")
            return True  # Default to open for testing

    async def get_historical_data(self, symbol: str, duration: str = "1 D", bar_size: str = "1 min") -> List[Dict]:
        """Get historical data (simplified)"""
        try:
            if not self.is_connected:
                return []

            if not IB_INSYNC_AVAILABLE:
                # Return mock historical data
                return [
                    {"datetime": datetime.now(), "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 10000}
                ]

            from ib_insync import Stock
            contract = Stock(symbol, 'SMART', 'USD')

            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True
            )

            historical_data = []
            for bar in bars:
                historical_data.append({
                    "datetime": bar.date,
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": int(bar.volume)
                })

            return historical_data

        except Exception as e:
            self.logger.error(f"❌ Error getting historical data for {symbol}: {e}")
            return []

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive market data"""
        try:
            if not self.is_connected:
                return {}

            if not IB_INSYNC_AVAILABLE:
                import random
                return {
                    "current_price": round(random.uniform(10.0, 100.0), 2),
                    "previous_close": round(random.uniform(10.0, 100.0), 2),
                    "volume": random.randint(100000, 1000000),
                    "market_cap": random.randint(100000000, 10000000000)
                }

            # Get current price
            price = await self.get_current_price(symbol)

            # Get historical data for previous close
            historical = await self.get_historical_data(symbol, "2 D", "1 day")
            previous_close = historical[-2]["close"] if len(historical) >= 2 else price

            # Get current volume (simplified)
            from ib_insync import Stock
            contract = Stock(symbol, 'SMART', 'USD')
            ticker = await self.ib.reqMktDataAsync(contract, timeout=5)

            volume = int(ticker.volume) if ticker.volume else 0

            # Cancel subscription
            self.ib.cancelMktData(contract)

            return {
                "current_price": price,
                "previous_close": previous_close,
                "volume": volume,
                "market_cap": 500000000  # Default market cap
            }

        except Exception as e:
            self.logger.error(f"❌ Error getting market data for {symbol}: {e}")
            return {}