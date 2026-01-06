# execution/execution_engine.py
"""
Execution Engine - Centralized trade execution and coordination
Receives trade requests from workers and executes them through IBKR
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import Sistema4Database
from shared.message_bus import MessageBus
from shared.config_reader import Sistema4Config
from execution.risk_manager import RiskManager
from adapters.ibkr_adapter_clean import IBKRAdapterClean as IBKRAdapter
from notifications import telegram_client

class ExecutionEngine:
    """
    Centralized execution engine for Sistema_4
    Validates, executes, and manages all trades
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ExecutionEngine")

        # Load configuration
        self.config = Sistema4Config()
        self._load_execution_params()

        # Initialize components
        self.database = Sistema4Database()
        self.message_bus = MessageBus()
        self.risk_manager = RiskManager()
        self.ibkr_adapter = None

        # Trade tracking
        self.pending_orders = {}  # order_id -> trade_request
        self.active_positions = {}  # symbol -> position_info

        # Control
        self.is_running = False
        self.shutdown_requested = False

        self.logger.info("⚙️ Execution Engine initialized")

    def _load_execution_params(self):
        """Load execution parameters from config"""
        # Load from config.ini
        execution_config = self.config.get_execution_engine_config()
        ibkr_config = self.config.get_ibkr_config()

        self.execution_client_id = ibkr_config['client_id_execution']
        self.order_timeout_seconds = execution_config['order_timeout_seconds']
        self.max_concurrent_orders = execution_config['max_concurrent_orders']
        self.enable_bracket_orders = execution_config['enable_bracket_orders']

    async def start(self):
        """Start execution engine"""
        try:
            # Initialize IBKR connection
            ibkr_config = self.config.get_ibkr_config()
            self.ibkr_adapter = IBKRAdapter(
                host=ibkr_config['host'],
                port=ibkr_config['port'],
                client_id=self.execution_client_id
            )

            if not await self.ibkr_adapter.connect():
                self.logger.error("❌ Failed to connect to IBKR")
                return False

            self.logger.info(f"✅ IBKR connected (client_id: {self.execution_client_id})")

            # Connect to message bus
            if not await self.message_bus.connect():
                self.logger.error("❌ Failed to connect to Redis")
                return False

            # Subscribe to trade requests
            await self.message_bus._subscribe_to_channel("trade_requests", self._process_trade_request)

            self.is_running = True
            self.logger.info("🚀 Execution Engine started - listening for trade requests...")

            # Return True to indicate successful start, the listener will be started separately
            return True

        except Exception as e:
            self.logger.error(f"❌ Error starting execution engine: {e}")
            return False

    async def start_listening(self):
        """Start the message listener loop"""
        try:
            if not self.is_running:
                self.logger.error("❌ Execution engine not started")
                return False

            # Start message listener (this will run forever)
            await self.message_bus.start_listening()

        except Exception as e:
            self.logger.error(f"❌ Error in message listener: {e}")
            return False

    async def _process_trade_request(self, trade_request: Dict[str, Any]):
        """Process incoming trade request from workers"""
        try:
            symbol = trade_request.get('symbol')
            worker_id = trade_request.get('worker_id')
            strategy = trade_request.get('strategy', 'UNKNOWN')

            self.logger.info(f"📥 Trade request received: {symbol} from {worker_id} ({strategy})")

            # Validate trade request
            validation_result = await self._validate_trade_request(trade_request)
            if not validation_result['valid']:
                self.logger.warning(f"⛔ Trade request rejected: {validation_result['reason']}")
                await self._send_trade_response(trade_request, 'REJECTED', validation_result['reason'])
                return

            # Execute trade
            execution_result = await self._execute_trade(trade_request)

            # Send response back to worker
            await self._send_trade_response(trade_request, execution_result['status'], execution_result['message'])

        except Exception as e:
            self.logger.error(f"❌ Error processing trade request: {e}")
            await self._send_trade_response(trade_request, 'ERROR', str(e))

    async def _validate_trade_request(self, trade_request: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trade request using risk manager"""
        try:
            symbol = trade_request.get('symbol')
            action = trade_request.get('action')
            quantity = trade_request.get('quantity', 0)
            worker_id = trade_request.get('worker_id')

            # Basic validation
            if not all([symbol, action, quantity > 0, worker_id]):
                return {'valid': False, 'reason': 'Missing required fields'}

            # Check if symbol is still available
            if not self.database.is_symbol_available(symbol):
                return {'valid': False, 'reason': f'Symbol {symbol} no longer available'}

            # Risk validation
            risk_check = await self.risk_manager.validate_trade(trade_request)
            if not risk_check['approved']:
                return {'valid': False, 'reason': risk_check['reason']}

            # Check concurrent orders limit
            if len(self.pending_orders) >= self.max_concurrent_orders:
                return {'valid': False, 'reason': f'Max concurrent orders limit reached: {self.max_concurrent_orders}'}

            return {'valid': True, 'reason': 'Trade request validated'}

        except Exception as e:
            return {'valid': False, 'reason': f'Validation error: {e}'}

    async def _execute_trade(self, trade_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute validated trade request"""
        try:
            symbol = trade_request['symbol']
            action = trade_request['action']
            quantity = trade_request['quantity']
            order_type = trade_request.get('order_type', 'MARKET')
            worker_id = trade_request['worker_id']

            self.logger.info(f"🔄 Executing trade: {action} {quantity} {symbol} ({order_type})")

            # Use bracket orders if enabled and stop/target prices provided
            if (self.enable_bracket_orders and
                trade_request.get('stop_loss_price') and
                trade_request.get('take_profit_price')):

                result = await self._execute_bracket_order(trade_request)
            else:
                result = await self._execute_simple_order(trade_request)

            if result['success']:
                # Add position to database (existing coordination tracking)
                entry_price = result.get('fill_price', trade_request.get('limit_price', 0.0))
                self.database.add_position(
                    symbol=symbol,
                    owner=worker_id,
                    side=action,
                    quantity=quantity,
                    entry_price=entry_price
                )

                # Record detailed trade entry for TradeTally integration
                planned_entry = trade_request.get('limit_price', entry_price)
                strategy = trade_request.get('strategy', 'UNKNOWN')
                entry_time = datetime.now()

                trade_id = self.database.record_trade_entry(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    planned_entry_price=planned_entry,
                    actual_entry_price=entry_price,
                    entry_time=entry_time,
                    actual_entry_time=entry_time,  # Same for now, could be different for limit orders
                    broker_order_id=result.get('order_id', ''),
                    strategy=strategy,
                    worker_id=worker_id
                )

                self.logger.info(f"✅ Trade executed: {symbol} @ ${entry_price:.2f} (Trade ID: {trade_id})")

                # Send Telegram notification
                try:
                    telegram_client.notify_trade_executed(
                        symbol=symbol,
                        action=action,
                        quantity=quantity,
                        price=entry_price,
                        worker_id=worker_id
                    )
                except Exception as e:
                    self.logger.debug(f"Telegram notification error: {e}")

                return {'status': 'FILLED', 'message': f"Order filled @ ${entry_price:.2f}"}
            else:
                self.logger.error(f"❌ Trade execution failed: {result['error']}")
                return {'status': 'FAILED', 'message': result['error']}

        except Exception as e:
            self.logger.error(f"❌ Trade execution error: {e}")
            return {'status': 'ERROR', 'message': str(e)}

    async def _execute_bracket_order(self, trade_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute bracket order with stop loss and take profit"""
        try:
            symbol = trade_request['symbol']
            action = trade_request['action']
            quantity = trade_request['quantity']
            limit_price = trade_request.get('limit_price')
            stop_loss_price = trade_request['stop_loss_price']
            take_profit_price = trade_request['take_profit_price']

            # Place bracket order
            order_result = await self.ibkr_adapter.place_bracket_order(
                symbol=symbol,
                action=action,
                quantity=quantity,
                limit_price=limit_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price
            )

            if order_result and 'parent_order_id' in order_result:
                self.logger.info(f"🎯 Bracket order placed: {symbol} (Parent: {order_result['parent_order_id']})")
                return {
                    'success': True,
                    'order_id': order_result['parent_order_id'],
                    'fill_price': limit_price or 0.0  # Will be updated when filled
                }
            else:
                return {'success': False, 'error': 'Failed to place bracket order'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _execute_simple_order(self, trade_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute simple order without bracket"""
        try:
            symbol = trade_request['symbol']
            action = trade_request['action']
            quantity = trade_request['quantity']
            order_type = trade_request.get('order_type', 'MARKET')
            limit_price = trade_request.get('limit_price')

            # Place order
            order_result = await self.ibkr_adapter.place_order(
                symbol=symbol,
                action=action,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price
            )

            if order_result and 'order_id' in order_result:
                self.logger.info(f"📝 Order placed: {symbol} (ID: {order_result['order_id']})")
                return {
                    'success': True,
                    'order_id': order_result['order_id'],
                    'fill_price': limit_price or 0.0
                }
            else:
                return {'success': False, 'error': 'Failed to place order'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _send_trade_response(self, trade_request: Dict[str, Any], status: str, message: str):
        """Send trade response back to requesting worker"""
        try:
            worker_id = trade_request.get('worker_id')
            response = {
                'symbol': trade_request.get('symbol'),
                'worker_id': worker_id,
                'status': status,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'original_request': trade_request
            }

            # Publish to worker-specific channel
            channel = f"trade_responses_{worker_id}"
            message_json = json.dumps(response)
            await self.message_bus.redis_client.publish(channel, message_json)

            self.logger.debug(f"📤 Response sent to {worker_id}: {status}")

        except Exception as e:
            self.logger.error(f"❌ Error sending trade response: {e}")

    async def record_trade_exit(self, symbol: str, worker_id: str, planned_exit_price: float,
                               actual_exit_price: float, broker_order_id: str) -> bool:
        """Record trade exit when position is closed"""
        try:
            # Find the open trade for this symbol/worker
            open_trades = self.database.get_open_trades()
            trade_to_close = None

            for trade in open_trades:
                if trade['symbol'] == symbol and trade['worker_id'] == worker_id:
                    trade_to_close = trade
                    break

            if not trade_to_close:
                self.logger.warning(f"No open trade found for {symbol} by {worker_id}")
                return False

            # Record the exit
            exit_time = datetime.now()
            success = self.database.record_trade_exit(
                trade_id=trade_to_close['trade_id'],
                planned_exit_price=planned_exit_price,
                actual_exit_price=actual_exit_price,
                exit_time=exit_time,
                actual_exit_time=exit_time,
                broker_order_id=broker_order_id
            )

            if success:
                self.logger.info(f"📊 Trade exit recorded: {symbol} @ ${actual_exit_price:.2f}")

            return success

        except Exception as e:
            self.logger.error(f"Error recording trade exit: {e}")
            return False

    async def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution engine statistics"""
        try:
            active_positions = self.database.get_active_positions()
            trade_stats = self.database.get_trade_stats(days=7)  # Last 7 days

            stats = {
                'active_positions': len(active_positions),
                'pending_orders': len(self.pending_orders),
                'risk_metrics': await self.risk_manager.get_current_metrics(),
                'ibkr_connected': self.ibkr_adapter.is_connected() if self.ibkr_adapter else False,
                'trade_performance': {
                    'total_trades_7d': trade_stats.get('total_trades', 0),
                    'win_rate_7d': trade_stats.get('win_rate', 0.0),
                    'total_pnl_7d': trade_stats.get('total_pnl', 0.0),
                    'avg_trade_pnl': trade_stats.get('avg_pnl', 0.0),
                    'best_trade': trade_stats.get('best_trade', 0.0),
                    'worst_trade': trade_stats.get('worst_trade', 0.0),
                    'avg_slippage': trade_stats.get('avg_total_slippage', 0.0)
                }
            }

            return stats

        except Exception as e:
            self.logger.error(f"Error getting execution stats: {e}")
            return {}

    async def stop(self):
        """Stop execution engine"""
        try:
            self.is_running = False
            self.shutdown_requested = True

            # Close any pending orders
            if self.pending_orders:
                self.logger.info(f"🔄 Cancelling {len(self.pending_orders)} pending orders...")
                # Would implement order cancellation here

            # Disconnect IBKR
            if self.ibkr_adapter:
                await self.ibkr_adapter.disconnect()
                self.logger.info("✅ IBKR disconnected")

            # Disconnect message bus
            if self.message_bus:
                await self.message_bus.disconnect()

            self.logger.info("🛑 Execution Engine stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping execution engine: {e}")

async def main():
    """Main function for standalone execution engine"""
    import signal
    from utils.log_config import setup_logging

    setup_logging(level="INFO", log_file="logs/execution_engine.log")

    engine = ExecutionEngine()

    # Setup signal handlers
    def signal_handler(signum, frame):
        engine.logger.info(f"📡 Signal {signum} received - shutting down execution engine")
        engine.shutdown_requested = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await engine.start()
    except KeyboardInterrupt:
        engine.logger.info("🛑 Execution engine interrupted by user")
    finally:
        await engine.stop()

if __name__ == "__main__":
    asyncio.run(main())