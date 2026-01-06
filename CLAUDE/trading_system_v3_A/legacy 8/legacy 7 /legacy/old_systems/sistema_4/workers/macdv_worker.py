# workers/macdv_worker.py
"""
MACDV Worker - Specialized worker for MACD + Volume strategies
Focuses on technical momentum with volume confirmation
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

class MacdvWorker:
    """
    Specialized worker for MACDV opportunities
    Combines MACD momentum signals with volume confirmation
    """

    def __init__(self, worker_id: str = "macdv_worker_1"):
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

        self.logger.info(f"📊 MACDV Worker initialized: {worker_id}")
        self.logger.info(f"   📈 Volume Ratio: {self.min_volume_ratio}x | MACD Threshold: {self.macd_threshold}")
        self.logger.info(f"   🔄 Confirmation: {self.confirmation_periods} periods")

    def _load_strategy_params(self):
        """Load MACDV strategy parameters from config"""
        macdv_config = self.config.get_macdv_config()

        # Volume requirements
        self.min_volume = macdv_config['min_volume']
        self.min_volume_ratio = macdv_config['min_volume_ratio']

        # MACD parameters
        self.macd_threshold = macdv_config['macd_threshold']
        self.confirmation_periods = macdv_config['confirmation_periods']

        # Technical filters
        self.min_momentum_score = macdv_config['min_momentum_score']
        self.max_rsi = macdv_config['max_rsi']

        # Risk management
        self.stop_loss_percent = macdv_config['stop_loss_percent']
        self.take_profit_percent = macdv_config['take_profit_percent']

        # Position sizing
        self.max_position_size = macdv_config['max_position_size']
        self.min_price = macdv_config['min_price']
        self.max_price = macdv_config['max_price']

    async def start(self):
        """Start MACDV worker"""
        try:
            # Connect to message bus
            if not await self.message_bus.connect():
                self.logger.error("❌ Failed to connect to Redis")
                return False

            # Subscribe to opportunities
            await self.message_bus.subscribe_to_opportunities(self._process_opportunity)

            self.is_running = True
            self.logger.info("🚀 MACDV Worker started - listening for opportunities...")

            # Start listening for messages
            await self.message_bus.start_listening()

        except Exception as e:
            self.logger.error(f"❌ Error starting MACDV worker: {e}")
            return False

    async def _process_opportunity(self, opportunity: Dict[str, Any]):
        """Process incoming opportunity"""
        try:
            # Only process MACDV opportunities
            if opportunity.get('opportunity_type') != 'MACDV':
                return

            symbol = opportunity.get('symbol')
            if not symbol:
                return

            self.logger.info(f"🔍 Processing MACDV opportunity: {symbol}")

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
                analysis = await self._analyze_macdv_setup(opportunity)
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

    async def _analyze_macdv_setup(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze MACDV setup and determine if should trade"""
        symbol = opportunity['symbol']
        current_price = opportunity.get('current_price', 0.0)
        volume = opportunity.get('volume', 0)
        volume_ratio = opportunity.get('volume_ratio', 0.0)

        # Technical indicators (would be calculated from real market data)
        # For now, we'll simulate based on available data
        momentum_score = self._calculate_momentum_score(opportunity)
        macd_signal = self._evaluate_macd_signal(opportunity)

        analysis = {
            'should_trade': False,
            'reason': '',
            'action': 'BUY',
            'quantity': 0,
            'entry_price': current_price,
            'stop_loss': 0.0,
            'take_profit': 0.0
        }

        # Filter 1: Price range
        if current_price < self.min_price or current_price > self.max_price:
            analysis['reason'] = f"Price out of range: ${current_price:.2f} (${self.min_price}-${self.max_price})"
            return analysis

        # Filter 2: Volume validation
        if volume < self.min_volume:
            analysis['reason'] = f"Volume too low: {volume:,} < {self.min_volume:,}"
            return analysis

        if volume_ratio < self.min_volume_ratio:
            analysis['reason'] = f"Volume ratio too low: {volume_ratio:.1f}x < {self.min_volume_ratio}x"
            return analysis

        # Filter 3: Momentum validation
        if momentum_score < self.min_momentum_score:
            analysis['reason'] = f"Momentum score too low: {momentum_score:.2f} < {self.min_momentum_score}"
            return analysis

        # Filter 4: MACD signal validation
        if not macd_signal['valid']:
            analysis['reason'] = f"MACD signal invalid: {macd_signal['reason']}"
            return analysis

        # Determine direction based on MACD
        if macd_signal['direction'] == 'bullish':
            analysis['action'] = 'BUY'
            analysis['stop_loss'] = current_price * (1 - self.stop_loss_percent / 100)
            analysis['take_profit'] = current_price * (1 + self.take_profit_percent / 100)
        else:
            analysis['action'] = 'SELL'
            analysis['stop_loss'] = current_price * (1 + self.stop_loss_percent / 100)
            analysis['take_profit'] = current_price * (1 - self.take_profit_percent / 100)

        # Position sizing based on volume and momentum
        base_risk = 90  # $90 base risk
        momentum_multiplier = min(momentum_score * 1.5, 2.0)  # Cap at 2x
        adjusted_risk = base_risk * momentum_multiplier

        stop_distance = abs(current_price - analysis['stop_loss'])
        if stop_distance > 0:
            analysis['quantity'] = min(int(adjusted_risk / stop_distance), self.max_position_size)
        else:
            analysis['quantity'] = 100

        if analysis['quantity'] < 10:
            analysis['reason'] = f"Position size too small: {analysis['quantity']} shares"
            return analysis

        # All filters passed
        analysis['should_trade'] = True
        analysis['reason'] = f"MACDV setup: {macd_signal['direction']} momentum {momentum_score:.2f}, volume {volume_ratio:.1f}x"

        self.logger.info(f"✅ {symbol} MACDV setup: {analysis['action']} {analysis['quantity']} @ ${current_price:.2f}")
        self.logger.info(f"   📊 Momentum: {momentum_score:.2f} | MACD: {macd_signal['direction']}")
        self.logger.info(f"   🎯 Stop: ${analysis['stop_loss']:.2f} | Target: ${analysis['take_profit']:.2f}")

        return analysis

    def _calculate_momentum_score(self, opportunity: Dict[str, Any]) -> float:
        """Calculate momentum score based on available data"""
        # Simplified momentum calculation
        gap_percentage = opportunity.get('gap_percentage', 0.0)
        volume_ratio = opportunity.get('volume_ratio', 1.0)
        quality_score = opportunity.get('quality_score', 50.0)

        # Normalize and combine factors
        gap_factor = min(abs(gap_percentage) / 10.0, 1.0)  # Normalize gap to 0-1
        volume_factor = min(volume_ratio / 5.0, 1.0)       # Normalize volume ratio to 0-1
        quality_factor = quality_score / 100.0             # Normalize quality to 0-1

        # Weighted momentum score
        momentum = (gap_factor * 0.3 + volume_factor * 0.4 + quality_factor * 0.3)
        return momentum

    def _evaluate_macd_signal(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate MACD signal based on available data"""
        # Simplified MACD evaluation
        gap_percentage = opportunity.get('gap_percentage', 0.0)
        volume_ratio = opportunity.get('volume_ratio', 1.0)

        signal = {
            'valid': False,
            'direction': 'neutral',
            'reason': ''
        }

        # Simple heuristics for MACD signal
        if gap_percentage > 1.0 and volume_ratio > self.min_volume_ratio:
            signal['valid'] = True
            signal['direction'] = 'bullish'
            signal['reason'] = f"Positive gap {gap_percentage:.1f}% with volume {volume_ratio:.1f}x"
        elif gap_percentage < -1.0 and volume_ratio > self.min_volume_ratio:
            signal['valid'] = True
            signal['direction'] = 'bearish'
            signal['reason'] = f"Negative gap {gap_percentage:.1f}% with volume {volume_ratio:.1f}x"
        else:
            signal['reason'] = f"Insufficient momentum: gap {gap_percentage:.1f}%, volume {volume_ratio:.1f}x"

        return signal

    def _generate_trade_request(self, symbol: str, opportunity: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trade request for execution engine"""
        return {
            'symbol': symbol,
            'action': analysis['action'],
            'quantity': analysis['quantity'],
            'order_type': 'LIMIT',  # MACDV uses limit orders for better fills
            'limit_price': analysis['entry_price'],
            'stop_loss_price': analysis['stop_loss'],
            'take_profit_price': analysis['take_profit'],
            'strategy': 'MACDV',
            'worker_id': self.worker_id,
            'reason': analysis['reason'],
            'opportunity_data': opportunity
        }

    async def stop(self):
        """Stop MACDV worker"""
        try:
            self.is_running = False
            self.shutdown_requested = True

            if self.message_bus:
                await self.message_bus.disconnect()

            self.logger.info("🛑 MACDV Worker stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping MACDV worker: {e}")

async def main():
    """Main function for standalone worker"""
    import signal
    from utils.log_config import setup_logging

    setup_logging(level="INFO", log_file="logs/macdv_worker.log")

    worker = MacdvWorker()

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