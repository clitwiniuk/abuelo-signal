# adapters/thread_safe_ibkr_adapter.py
"""
Thread-safe IBKR adapter that handles cross-thread communication.
Solves the event loop issue by running IBKR operations in a dedicated thread.
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty

from ib_insync import IB, Contract, Stock
from core.interfaces import (
    IDataProvider, IBroker, Position, Order, MarketData, 
    OrderSide, OrderType, OrderStatus, BrokerConnectionError, DataProviderError
)
from utils.rate_limiter import rate_limit


class ThreadSafeIBKRAdapter(IDataProvider, IBroker):
    """
    Thread-safe IBKR adapter that runs IB operations in a dedicated thread.
    This solves the event loop conflict between Streamlit and Trading Engine.
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.logger = logging.getLogger(f"ThreadSafeIBKRAdapter({client_id})")
        self.logger.info("🚀 THREAD-SAFE IBKR ADAPTER INITIALIZED - This should fix event loop errors!")
        
        # Thread management
        self._ibkr_thread = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="IBKR")
        self._ib = None
        self._connected = False
        self._shutdown = False
        self._reconnecting = False
        self._reconnection_lock = threading.Lock()
        
        # Communication queues
        self._request_queue = Queue()
        self._response_dict = {}
        self._request_counter = 0
        self._request_lock = threading.Lock()
        
        # Cache for better performance
        self._contracts_cache = {}
        self._positions_cache = {}
        self._orders_cache = {}
        
        # Start the dedicated IBKR thread
        self._start_ibkr_thread()
    
    def _start_ibkr_thread(self):
        """Start the dedicated IBKR thread"""
        self._ibkr_thread = threading.Thread(target=self._ibkr_worker, daemon=True)
        self._ibkr_thread.start()
        self.logger.info("Started dedicated IBKR thread")
    
    def _ibkr_worker(self):
        """Worker thread that handles all IBKR operations"""
        self.logger.info("IBKR worker thread started")
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Create IB instance in this thread
        self._ib = IB()
        self._ib.errorEvent += self._on_ib_error
        self._ib.disconnectedEvent += self._on_ib_disconnected
        
        try:
            while not self._shutdown:
                try:
                    # Process requests from the queue with very short timeout for responsiveness
                    request = self._request_queue.get(timeout=0.5)  # Reduced from 1.0 to 0.5
                    if request is None:  # Shutdown signal
                        self.logger.info("📴 Shutdown signal received in IBKR worker")
                        break
                    
                    # Check shutdown again before executing
                    if self._shutdown:
                        self.logger.info("📴 Shutdown detected, skipping request execution")
                        break
                    
                    # Execute the request
                    self._execute_request(request)
                    
                except Empty:
                    # Check shutdown flag more frequently
                    if self._shutdown:
                        self.logger.info("📴 Shutdown detected during empty queue")
                        break
                    continue
                except Exception as e:
                    if not self._shutdown:  # Only log if not shutting down
                        self.logger.error(f"Error in IBKR worker: {e}")
                    
        finally:
            # Aggressive cleanup
            self.logger.info("📴 IBKR worker cleanup starting...")
            try:
                if self._ib and self._ib.isConnected():
                    # Force disconnect with minimal timeout
                    self._ib.disconnect()
                    self.logger.info("📴 IBKR disconnected")
            except Exception as e:
                self.logger.warning(f"Error during IBKR disconnect: {e}")
            
            try:
                loop.close()
                self.logger.info("📴 Event loop closed")
            except:
                pass
                
            self.logger.info("📴 IBKR worker thread stopped")
    
    def _execute_request(self, request: Dict[str, Any]):
        """Execute a request in the IBKR thread"""
        request_id = request['id']
        method = request['method']
        args = request.get('args', [])
        kwargs = request.get('kwargs', {})
        
        self.logger.debug(f"Executing request {request_id}: {method}")
        
        try:
            # Get the method from the IB instance
            if method == 'connect':
                result = self._thread_connect(*args, **kwargs)
            elif method == 'disconnect':
                result = self._thread_disconnect()
            elif method == 'is_connected':
                result = self._thread_is_connected()
            elif method == 'get_bars':
                result = self._thread_get_bars(*args, **kwargs)
            elif method == 'get_current_price':
                result = self._thread_get_current_price(*args, **kwargs)
            elif method == 'get_positions':
                result = self._thread_get_positions()
            elif method == 'place_order':
                result = self._thread_place_order(*args, **kwargs)
            elif method == 'cancel_order':
                result = self._thread_cancel_order(*args, **kwargs)
            else:
                raise ValueError(f"Unknown method: {method}")
            
            # Store the result
            self._response_dict[request_id] = {'success': True, 'result': result}
            self.logger.debug(f"Request {request_id} completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error executing {method}: {e}")
            self._response_dict[request_id] = {'success': False, 'error': str(e)}
    
    def _make_request(self, method: str, *args, **kwargs) -> Any:
        """Make a thread-safe request to the IBKR thread"""
        if self._shutdown:
            raise RuntimeError("Adapter is shutting down")
        
        # Generate unique request ID
        with self._request_lock:
            self._request_counter += 1
            request_id = self._request_counter
        
        # Create request
        request = {
            'id': request_id,
            'method': method,
            'args': args,
            'kwargs': kwargs
        }
        
        # Send request with timeout
        try:
            self._request_queue.put(request, timeout=1.0)  # Add timeout to put
        except:
            if self._shutdown:
                raise RuntimeError("Adapter is shutting down")
            raise
        
        # Wait for response with more frequent shutdown checks
        timeout = 12.0  # Reduced timeout for faster error detection
        start_time = time.time()
        
        while request_id not in self._response_dict:
            # Check shutdown more frequently
            if self._shutdown:
                raise RuntimeError("Adapter is shutting down")
                
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Request {method} timed out")
            time.sleep(0.01)  # Small sleep to avoid busy waiting
        
        # Get response
        response = self._response_dict.pop(request_id)
        
        if response['success']:
            return response['result']
        else:
            raise Exception(response['error'])
    
    # Thread-safe methods that delegate to IBKR thread
    
    def _thread_connect(self) -> bool:
        """Connect to IBKR in the dedicated thread"""
        try:
            if self._ib.isConnected():
                return True
            
            self.logger.info("🔧 THREAD-SAFE ADAPTER: Connecting to IBKR in dedicated thread")
            # Use synchronous connect in the dedicated thread
            self._ib.connect(self.host, self.port, self.client_id, timeout=60)
            self._connected = True
            self.logger.info("✅ THREAD-SAFE ADAPTER: Successfully connected to IBKR")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect: {e}")
            self._connected = False
            return False
    
    def _on_ib_error(self, reqId, errorCode, errorString, contract=None):
        """Event handler for IBKR errors."""
        # Códigos de error que indican una desconexión o un problema grave de conexión
        # 502: Couldn't connect to TWS
        # 504: Not connected
        # 1100: Connectivity between IB and TWS is lost
        # 1102: Connectivity between IB and TWS is restored - data lost
        # 1300: Socket port has been reset
        # 2104: Market data farm connection is OK
        # 2106: A historical data farm is connected
        # 2158: Sec-def data farm connection is OK
        connection_lost_codes = {502, 504, 1100, 1102, 1300}

        if errorCode in connection_lost_codes:
            self.logger.error(f"💥 CRITICAL IBKR ERROR (Code: {errorCode}): {errorString}. Connection lost.")
            if self._connected:
                self._connected = False
                self._trigger_reconnection()
        elif errorCode in {2104, 2106, 2158}: # Connection restored codes
            self.logger.info(f"✅ IBKR connection restored (Code: {errorCode}): {errorString}")
            # Si estábamos reconectando, la conexión se ha restaurado
            if self._reconnecting:
                self._connected = True
        else:
            # Manejar Error 300 específicamente (EId not found)
            if errorCode == 300:
                self.logger.debug(f"IBKR tickerId cleanup (Code: {errorCode}, Req: {reqId}): {errorString}")
            # Ignorar warnings comunes, loguear errores inesperados
            elif errorCode < 300 or errorCode >= 400: # IBKR suele usar 200-300 para warnings
                 self.logger.warning(f"IBKR Info/Error (Req: {reqId}, Code: {errorCode}): {errorString}")

    def _on_ib_disconnected(self):
        """Event handler for IBKR disconnection."""
        # Solo actuar si no estamos ya en un proceso de desconexión/reconexión controlado
        if self._connected:
            self.logger.warning("🔌 IBKR client disconnected unexpectedly!")
            self._connected = False
            self._trigger_reconnection()

    def _trigger_reconnection(self):
        """Triggers the reconnection process in a new thread if not already running."""
        with self._reconnection_lock:
            if self._reconnecting or self._shutdown:
                return
            self._reconnecting = True
        
        self.logger.info("🔄 Starting reconnection process in background...")
        reconnect_thread = threading.Thread(target=self._reconnect, daemon=True)
        reconnect_thread.start()

    def _reconnect(self):
        """Handles the reconnection logic with exponential backoff."""
        max_delay = 60
        delay = 1
        while not self._shutdown and not self._connected:
            try:
                self.logger.info(f"Attempting to reconnect in {delay} seconds...")
                time.sleep(delay)
                
                # La conexión debe ocurrir en el hilo del worker
                self.connect() # Esto pondrá la solicitud en la cola

                # Esperar un tiempo razonable para que se establezca la conexión
                time.sleep(15) 

                if self.is_connected():
                    self.logger.info("✅ Reconnection successful!")
                    break
                else:
                    self.logger.warning("Reconnect attempt failed.")
                    delay = min(delay * 2, max_delay)

            except Exception as e:
                self.logger.error(f"Error during reconnection attempt: {e}")
                delay = min(delay * 2, max_delay)
        
        with self._reconnection_lock:
            self._reconnecting = False
            if not self._connected and not self._shutdown:
                 self.logger.error("🛑 Reconnection process failed after multiple attempts.")
            elif self._connected:
                 self.logger.info("Reconnection process finished.")

    def _thread_disconnect(self) -> None:
        """Disconnect from IBKR in the dedicated thread"""
        try:
            if self._ib and self._ib.isConnected():
                self._ib.disconnect()
            self._connected = False
        except Exception as e:
            self.logger.error(f"Error disconnecting: {e}")
    
    def _thread_is_connected(self) -> bool:
        """Check connection status in the dedicated thread"""
        return self._connected and self._ib and self._ib.isConnected()
    
    def _thread_get_bars(self, symbol: str, timeframe: str, count: int) -> List[MarketData]:
        """Get historical bars in the dedicated thread"""
        try:
            if not self._thread_is_connected():
                raise DataProviderError("Not connected to IBKR")
            
            # Only log if debugging needed
            # self.logger.debug(f"🔧 THREAD-SAFE ADAPTER: Getting bars for {symbol} ({timeframe}, {count} bars) in dedicated thread")
            
            # Get or create contract
            contract = self._get_contract(symbol)
            if not contract:
                return []
            
            # Convert timeframe
            bar_size = self._convert_timeframe(timeframe)
            duration = self._calculate_duration(count, timeframe)
            
            # Only log IBKR requests if debugging needed
            # self.logger.debug(f"📊 IBKR request: {symbol} duration={duration}, bar_size={bar_size}")
            
            # Add error callback to catch Error 366 immediately
            def error_callback(reqId, errorCode, errorString, contract):
                if errorCode == 366 or "no se encontraron datos" in errorString.lower():
                    raise ValueError(f"NO_HISTORICAL_DATA:{symbol}")
            
            # Request data (synchronous in this thread) with faster timeout
            bars = self._ib.reqHistoricalData(
                contract=contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,
                timeout=12  # Balanced timeout - fast enough but allows IBKR processing time
            )
            
            if not bars:
                self.logger.warning(f"📊 No bars received for {symbol} - symbol may not exist or have no data")
                return []
            
            # Convert to MarketData objects
            market_data = []
            for bar in bars:
                data = MarketData(
                    symbol=symbol,
                    timestamp=bar.date,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume) if bar.volume else 0
                )
                market_data.append(data)
            
            # Only log conversion details if debugging needed
            # self.logger.debug(f"🔧 Converted {len(market_data)} bars for {symbol}, latest: {market_data[-1].timestamp}")
            return market_data
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for specific IBKR errors - prioritize Error 366 detection
            if ("366" in error_msg or "no historical data" in error_msg.lower() or 
                "no se encontraron datos" in error_msg.lower() or 
                "No security definition" in error_msg or
                "security not found" in error_msg.lower()):
                self.logger.warning(f"Symbol {symbol} has no historical data (Error 366) - immediate removal")
                # Raise a specific exception that the trading engine can catch immediately
                raise ValueError(f"NO_HISTORICAL_DATA:{symbol}")
            elif "timeout" in error_msg.lower():
                self.logger.warning(f"Timeout getting bars for {symbol}")
                raise TimeoutError(f"Timeout getting bars for {symbol}")
            else:
                self.logger.error(f"Error getting bars for {symbol}: {e}")
                raise
    
    def _thread_get_current_price(self, symbol: str) -> float:
        """Get current price in the dedicated thread"""
        try:
            if not self._thread_is_connected():
                raise DataProviderError("Not connected to IBKR")
            
            contract = self._get_contract(symbol)
            if not contract:
                return 0.0
            
            # Request market data
            ticker = self._ib.reqMktData(contract, '', False, False)
            self._ib.sleep(2)  # Wait for data
            
            if ticker.last and ticker.last > 0:
                return float(ticker.last)
            elif ticker.close and ticker.close > 0:
                return float(ticker.close)
            else:
                return 0.0
                
        except Exception as e:
            self.logger.error(f"Error getting price for {symbol}: {e}")
            return 0.0
    
    def _thread_get_positions(self) -> Dict[str, Position]:
        """Get positions in the dedicated thread"""
        try:
            if not self._thread_is_connected():
                return {}
            
            positions = {}
            for pos in self._ib.positions():
                if pos.position != 0:  # Only active positions
                    symbol = pos.contract.symbol
                    position = Position(
                        symbol=symbol,
                        quantity=int(pos.position),
                        avg_price=float(pos.avgCost) if pos.avgCost else 0.0,
                        market_price=0.0,  # Will be updated separately
                        unrealized_pnl=0.0,  # Will be calculated
                        realized_pnl=0.0
                    )
                    positions[symbol] = position
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return {}
    
    def _thread_place_order(self, symbol: str, side: OrderSide, quantity: int, 
                           order_type: OrderType, price: float = None) -> str:
        """Place order in the dedicated thread"""
        # Implementation for placing orders
        # This would need to be implemented based on your specific needs
        return ""
    
    def _thread_cancel_order(self, order_id: str) -> bool:
        """Cancel order in the dedicated thread"""
        # Implementation for canceling orders
        return False
    
    def _get_contract(self, symbol: str) -> Optional[Contract]:
        """Get contract for symbol"""
        if symbol in self._contracts_cache:
            return self._contracts_cache[symbol]
        
        contract = Stock(symbol, 'SMART', 'USD')
        self._contracts_cache[symbol] = contract
        return contract
    
    def _convert_timeframe(self, timeframe: str) -> str:
        """Convert timeframe to IBKR format"""
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
        """Calculate duration string for IBKR"""
        if 'min' in timeframe:
            # Extract the number of minutes from timeframe (e.g., "1 min" -> 1, "5 mins" -> 5)
            minutes = int(timeframe.split()[0])
            total_seconds = count * minutes * 60
            return f"{total_seconds} S"
        elif 'hour' in timeframe:
            return f"{count} H"
        elif 'day' in timeframe:
            return f"{count} D"
        else:
            return f"{count} S"
    
    # Public interface methods that delegate to the IBKR thread
    
    async def connect(self) -> bool:
        """Connect to IBKR"""
        return await asyncio.get_event_loop().run_in_executor(
            self._executor, self._make_request, 'connect'
        )
    
    async def disconnect(self) -> None:
        """Disconnect from IBKR with IMMEDIATE forced shutdown"""
        self.logger.info("📴 IMMEDIATE FORCE DISCONNECT - no waiting...")
        
        # Signal shutdown FIRST
        self._shutdown = True
        self._connected = False
        
        try:
            # Cancel all pending requests immediately
            self._response_dict.clear()
            
            # Clear request queue
            while not self._request_queue.empty():
                try:
                    self._request_queue.get_nowait()
                except:
                    break
            
            # Send immediate shutdown signal
            try:
                self._request_queue.put(None, timeout=0.1)  # Very short timeout
            except:
                pass
                
            # Force shutdown the executor IMMEDIATELY
            if self._executor:
                self._executor.shutdown(wait=False)  # Don't wait at all
                self.logger.info("📴 Executor shutdown (no wait)")
                
            self.logger.info("📴 IBKR adapter disconnected (IMMEDIATE FORCE)")
            
        except Exception as e:
            self.logger.warning(f"Error during force disconnect: {e}")
        
        # Ensure flags are set regardless of errors
        self._connected = False
        self._shutdown = True
    
    def is_connected(self) -> bool:
        """Check if connected to IBKR"""
        try:
            return self._make_request('is_connected')
        except:
            return False
    
    @rate_limit(calls_per_second=3, burst_limit=5, key="ibkr_bars")
    async def get_bars(self, symbol: str, timeframe: str, count: int) -> List[MarketData]:
        """Get historical bars"""
        return await asyncio.get_event_loop().run_in_executor(
            self._executor, self._make_request, 'get_bars', symbol, timeframe, count
        )
    
    @rate_limit(calls_per_second=8, burst_limit=15, key="ibkr_prices")
    async def get_current_price(self, symbol: str) -> float:
        """Get current market price"""
        return await asyncio.get_event_loop().run_in_executor(
            self._executor, self._make_request, 'get_current_price', symbol
        )
    
    async def get_positions(self) -> Dict[str, Position]:
        """Get current positions"""
        return await asyncio.get_event_loop().run_in_executor(
            self._executor, self._make_request, 'get_positions'
        )
    
    async def place_order(self, symbol: str, side: OrderSide, quantity: int,
                         order_type: OrderType, price: float = None) -> str:
        """Place an order"""
        return await asyncio.get_event_loop().run_in_executor(
            self._executor, self._make_request, 'place_order', 
            symbol, side, quantity, order_type, price
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        return await asyncio.get_event_loop().run_in_executor(
            self._executor, self._make_request, 'cancel_order', order_id
        )
    
    async def get_orders(self) -> List[Order]:
        """Get active orders"""
        return []  # Placeholder
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        return {}  # Placeholder
    
    def __del__(self):
        """Cleanup when adapter is destroyed"""
        self._shutdown = True
        if self._request_queue:
            self._request_queue.put(None)  # Signal shutdown
        if self._executor:
            self._executor.shutdown(wait=False)