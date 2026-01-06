# workers/gap_go_worker.py
"""
GAP_GO Worker - Specialized worker for gap trading strategies
Focuses on significant gaps with high volume
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import Sistema4Database
from shared.message_bus import WorkerMessageBus
from shared.config_reader import Sistema4Config

class GapGoWorker:
    """
    Specialized worker for GAP_GO opportunities
    Filters and analyzes gap trading setups
    """

    def __init__(self, worker_id: str = "gap_go_worker_1"):
        self.worker_id = worker_id
        self.logger = logging.getLogger(f"{__name__}.{worker_id}")

        # Load configuration
        self.config = Sistema4Config()
        self._load_strategy_params()

        # Initialize components
        self.database = Sistema4Database()
        self.message_bus = WorkerMessageBus(worker_id=worker_id)

        # Control
        self.is_running = False
        self.shutdown_requested = False

        self.logger.info(f"🚀 GAP_GO Worker initialized: {worker_id}")
        self.logger.info(f"   📊 Min Gap: {self.min_gap_percent}% | Max Gap: {self.max_gap_percent}%")
        self.logger.info(f"   📈 Min Volume: {self.min_volume:,} | Max Volume: {self.max_volume:,}")

    def _load_strategy_params(self):
        """Load GAP_GO strategy parameters from config"""
        gap_config = self.config.get_gap_go_config()

        # Gap parameters
        self.min_gap_percent = gap_config['min_gap_percent']
        self.max_gap_percent = gap_config['max_gap_percent']

        # Volume parameters
        self.min_volume = gap_config['min_volume']
        self.max_volume = gap_config['max_volume']

        # Risk parameters
        self.stop_loss_percent = gap_config['stop_loss_percent']
        self.take_profit_percent = gap_config['take_profit_percent']

        # Position sizing
        self.max_position_size = gap_config['max_position_size']
        self.min_price = gap_config['min_price']
        self.max_price = gap_config['max_price']

    async def start(self):
        """Start GAP_GO worker"""
        try:
            # Connect to message bus
            if not await self.message_bus.connect():
                self.logger.error("❌ Failed to connect to Redis")
                return False

            # Subscribe to opportunities
            await self.message_bus.subscribe_to_opportunities(self._process_opportunity)

            self.is_running = True
            self.logger.info("🚀 GAP_GO Worker started - listening for opportunities...")

            # Start listening for messages
            await self.message_bus.start_listening()

        except Exception as e:
            self.logger.error(f"❌ Error starting GAP_GO worker: {e}")
            return False

    async def _process_opportunity(self, opportunity: Dict[str, Any]):
        """Process incoming opportunity"""
        try:
            # Only process GAP_GO opportunities
            if opportunity.get('opportunity_type') != 'GAP_GO':
                return

            symbol = opportunity.get('symbol')
            if not symbol:
                return

            self.logger.info(f"🔍 Processing GAP_GO opportunity: {symbol}")

            # Check if symbol is available
            if not self.database.is_symbol_available(symbol):
                self.logger.info(f"⏭️ {symbol} already taken - skipping")
                return

            # Reserve symbol
            if not self.database.reserve_symbol(symbol, self.worker_id):
                self.logger.info(f"⏭️ Failed to reserve {symbol} - skipping")
                return

            try:
                # Analyze setup
                analysis = await self._analyze_gap_setup(opportunity)
                if not analysis['should_trade']:
                    self.logger.info(f"⛔ {symbol} setup rejected: {analysis['reason']}")
                    return

                # Generate trade request
                trade_request = self._generate_trade_request(symbol, opportunity, analysis)

                # Send to execution engine
                if await self.message_bus.publish_trade_request(trade_request):
                    self.logger.info(f"📡 Trade request sent for {symbol}: {analysis['action']} {analysis['quantity']} shares")
                else:
                    self.logger.error(f"❌ Failed to send trade request for {symbol}")

            finally:
                # Always release reservation
                self.database.release_reservation(symbol, self.worker_id)

        except Exception as e:
            self.logger.error(f"❌ Error processing opportunity: {e}")

    async def _analyze_gap_setup(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze gap setup and determine if should trade"""
        symbol = opportunity['symbol']
        gap_percentage = opportunity.get('gap_percentage', 0.0)
        volume_ratio = opportunity.get('volume_ratio', 0.0)
        current_price = opportunity.get('current_price', 0.0)

        analysis = {
            'should_trade': False,
            'reason': '',
            'action': 'BUY',  # GAP_GO is typically long bias
            'quantity': 0,
            'entry_price': current_price,
            'stop_loss': 0.0,
            'take_profit': 0.0
        }

        # Filter 1: Gap size validation
        gap_abs = abs(gap_percentage)
        if gap_abs < self.min_gap_percent:
            analysis['reason'] = f"Gap too small: {gap_abs:.1f}% < {self.min_gap_percent}%"
            return analysis

        if gap_abs > self.max_gap_percent:
            analysis['reason'] = f"Gap too large: {gap_abs:.1f}% > {self.max_gap_percent}%"
            return analysis

        # Filter 2: Price range
        if current_price < self.min_price or current_price > self.max_price:
            analysis['reason'] = f"Price out of range: ${current_price:.2f} (${self.min_price}-${self.max_price})"
            return analysis

        # Filter 3: Volume validation
        volume = opportunity.get('volume', 0)
        if volume < self.min_volume or volume > self.max_volume:
            analysis['reason'] = f"Volume out of range: {volume:,}"
            return analysis

        # Filter 4: Gap direction and momentum
        if gap_percentage > 0:
            # Positive gap - go long
            analysis['action'] = 'BUY'
            analysis['stop_loss'] = current_price * (1 - self.stop_loss_percent / 100)
            analysis['take_profit'] = current_price * (1 + self.take_profit_percent / 100)
        else:
            # Negative gap - go short
            analysis['action'] = 'SELL'
            analysis['stop_loss'] = current_price * (1 + self.stop_loss_percent / 100)
            analysis['take_profit'] = current_price * (1 - self.take_profit_percent / 100)

        # Calculate position size
        risk_amount = 100  # $100 risk per trade (configurable)
        stop_distance = abs(current_price - analysis['stop_loss'])
        if stop_distance > 0:
            analysis['quantity'] = min(int(risk_amount / stop_distance), self.max_position_size)
        else:
            analysis['quantity'] = 100  # Default size

        if analysis['quantity'] < 10:
            analysis['reason'] = f"Position size too small: {analysis['quantity']} shares"
            return analysis

        # All filters passed
        analysis['should_trade'] = True
        analysis['reason'] = f"Gap setup valid: {gap_percentage:+.1f}% gap, volume {volume:,}"

        self.logger.info(f"✅ {symbol} GAP_GO setup: {analysis['action']} {analysis['quantity']} @ ${current_price:.2f}")
        self.logger.info(f"   🎯 Stop: ${analysis['stop_loss']:.2f} | Target: ${analysis['take_profit']:.2f}")

        return analysis

    def _generate_trade_request(self, symbol: str, opportunity: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trade request for execution engine"""
        return {
            'symbol': symbol,
            'action': analysis['action'],
            'quantity': analysis['quantity'],
            'order_type': 'MARKET',  # GAP_GO typically uses market orders for speed
            'stop_loss_price': analysis['stop_loss'],
            'take_profit_price': analysis['take_profit'],
            'strategy': 'GAP_GO',
            'worker_id': self.worker_id,
            'reason': analysis['reason'],
            'opportunity_data': opportunity
        }

    async def stop(self):
        """Stop GAP_GO worker"""
        try:
            self.is_running = False
            self.shutdown_requested = True

            if self.message_bus:
                await self.message_bus.disconnect()

            self.logger.info("🛑 GAP_GO Worker stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping GAP_GO worker: {e}")

async def main():
    """Main function for standalone worker"""
    import signal
    from utils.log_config import setup_logging

    setup_logging(level="INFO", log_file="logs/gap_go_worker.log")

    worker = GapGoWorker()

    # Setup signal handlers
    def signal_handler(signum, frame):
        worker.logger.info(f"📡 Signal {signum} received - shutting down worker")
        worker.shutdown_requested = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker.start()
    except KeyboardInterrupt:
        worker.logger.info("🛑 Worker interrupted by user")
    finally:
        await worker.stop()

if __name__ == "__main__":
    asyncio.run(main())