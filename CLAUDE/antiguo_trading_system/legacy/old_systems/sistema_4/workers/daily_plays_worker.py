# workers/daily_plays_worker.py
"""
DAILY_PLAYS Worker - Specialized worker for daily play strategies
Focuses on bounce setups and daily momentum
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

class DailyPlaysWorker:
    """
    Specialized worker for DAILY_PLAYS opportunities
    Focuses on daily bounce and momentum setups
    """

    def __init__(self, worker_id: str = "daily_plays_worker_1"):
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

        self.logger.info(f"🎯 DAILY_PLAYS Worker initialized: {worker_id}")
        self.logger.info(f"   📊 Min Volume: {self.min_volume:,} | Quality Score: {self.min_quality_score}")
        self.logger.info(f"   💡 Min Catalyst: {self.min_catalyst_strength} | Max Gap: {self.max_gap_percent}%")

    def _load_strategy_params(self):
        """Load DAILY_PLAYS strategy parameters from config"""
        daily_config = self.config.get_daily_plays_config()

        # Volume and quality
        self.min_volume = daily_config['min_volume']
        self.min_quality_score = daily_config['min_quality_score']

        # Catalyst analysis
        self.min_catalyst_strength = daily_config['min_catalyst_strength']
        self.preferred_catalysts = daily_config['preferred_catalysts']

        # Gap limits (daily plays prefer smaller gaps)
        self.max_gap_percent = daily_config['max_gap_percent']

        # Risk management
        self.stop_loss_percent = daily_config['stop_loss_percent']
        self.take_profit_percent = daily_config['take_profit_percent']

        # Position sizing
        self.max_position_size = daily_config['max_position_size']
        self.min_price = daily_config['min_price']
        self.max_price = daily_config['max_price']

        # Consolidation requirements
        self.consolidation_min_time = daily_config['consolidation_min_time_minutes']

    async def start(self):
        """Start DAILY_PLAYS worker"""
        try:
            # Connect to message bus
            if not await self.message_bus.connect():
                self.logger.error("❌ Failed to connect to Redis")
                return False

            # Subscribe to opportunities
            await self.message_bus.subscribe_to_opportunities(self._process_opportunity)

            self.is_running = True
            self.logger.info("🚀 DAILY_PLAYS Worker started - listening for opportunities...")

            # Start listening for messages
            await self.message_bus.start_listening()

        except Exception as e:
            self.logger.error(f"❌ Error starting DAILY_PLAYS worker: {e}")
            return False

    async def _process_opportunity(self, opportunity: Dict[str, Any]):
        """Process incoming opportunity"""
        try:
            # Only process DAILY_PLAYS opportunities
            if opportunity.get('opportunity_type') != 'DAILY_PLAYS':
                return

            symbol = opportunity.get('symbol')
            if not symbol:
                return

            self.logger.info(f"🔍 Processing DAILY_PLAYS opportunity: {symbol}")

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
                analysis = await self._analyze_daily_setup(opportunity)
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

    async def _analyze_daily_setup(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze daily play setup and determine if should trade"""
        symbol = opportunity['symbol']
        quality_score = opportunity.get('quality_score', 0.0)
        current_price = opportunity.get('current_price', 0.0)
        gap_percentage = opportunity.get('gap_percentage', 0.0)
        volume = opportunity.get('volume', 0)
        catalyst_type = opportunity.get('catalyst_type', 'TECHNICAL')
        catalyst_strength = opportunity.get('catalyst_strength', 0.0)

        analysis = {
            'should_trade': False,
            'reason': '',
            'action': 'BUY',  # Daily plays typically long bias
            'quantity': 0,
            'entry_price': current_price,
            'stop_loss': 0.0,
            'take_profit': 0.0
        }

        # Filter 1: Quality score
        if quality_score < self.min_quality_score:
            analysis['reason'] = f"Quality score too low: {quality_score:.1f} < {self.min_quality_score}"
            return analysis

        # Filter 2: Price range
        if current_price < self.min_price or current_price > self.max_price:
            analysis['reason'] = f"Price out of range: ${current_price:.2f} (${self.min_price}-${self.max_price})"
            return analysis

        # Filter 3: Volume validation
        if volume < self.min_volume:
            analysis['reason'] = f"Volume too low: {volume:,} < {self.min_volume:,}"
            return analysis

        # Filter 4: Gap validation (daily plays prefer smaller gaps)
        gap_abs = abs(gap_percentage)
        if gap_abs > self.max_gap_percent:
            analysis['reason'] = f"Gap too large for daily play: {gap_abs:.1f}% > {self.max_gap_percent}%"
            return analysis

        # Filter 5: Catalyst validation
        if catalyst_strength < self.min_catalyst_strength:
            analysis['reason'] = f"Catalyst too weak: {catalyst_strength:.1f} < {self.min_catalyst_strength}"
            return analysis

        # Bonus for preferred catalysts
        catalyst_bonus = 1.0
        if catalyst_type in self.preferred_catalysts:
            catalyst_bonus = 1.2
            self.logger.info(f"   💎 Preferred catalyst detected: {catalyst_type}")

        # Calculate entry, stops, and targets
        analysis['action'] = 'BUY'  # Daily plays are typically long
        analysis['stop_loss'] = current_price * (1 - self.stop_loss_percent / 100)
        analysis['take_profit'] = current_price * (1 + self.take_profit_percent / 100)

        # Position sizing with catalyst bonus
        base_risk = 80  # $80 base risk per trade
        adjusted_risk = base_risk * catalyst_bonus
        stop_distance = abs(current_price - analysis['stop_loss'])

        if stop_distance > 0:
            analysis['quantity'] = min(int(adjusted_risk / stop_distance), self.max_position_size)
        else:
            analysis['quantity'] = 100  # Default size

        if analysis['quantity'] < 10:
            analysis['reason'] = f"Position size too small: {analysis['quantity']} shares"
            return analysis

        # All filters passed
        analysis['should_trade'] = True
        analysis['reason'] = f"Daily play setup: Q{quality_score:.0f}, {catalyst_type} catalyst {catalyst_strength:.1f}"

        self.logger.info(f"✅ {symbol} DAILY_PLAYS setup: {analysis['action']} {analysis['quantity']} @ ${current_price:.2f}")
        self.logger.info(f"   🎯 Stop: ${analysis['stop_loss']:.2f} | Target: ${analysis['take_profit']:.2f}")
        self.logger.info(f"   💡 Catalyst: {catalyst_type} (strength: {catalyst_strength:.1f})")

        return analysis

    def _generate_trade_request(self, symbol: str, opportunity: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trade request for execution engine"""
        return {
            'symbol': symbol,
            'action': analysis['action'],
            'quantity': analysis['quantity'],
            'order_type': 'LIMIT',  # Daily plays can use limit orders
            'limit_price': analysis['entry_price'],
            'stop_loss_price': analysis['stop_loss'],
            'take_profit_price': analysis['take_profit'],
            'strategy': 'DAILY_PLAYS',
            'worker_id': self.worker_id,
            'reason': analysis['reason'],
            'opportunity_data': opportunity
        }

    async def stop(self):
        """Stop DAILY_PLAYS worker"""
        try:
            self.is_running = False
            self.shutdown_requested = True

            if self.message_bus:
                await self.message_bus.disconnect()

            self.logger.info("🛑 DAILY_PLAYS Worker stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping DAILY_PLAYS worker: {e}")

async def main():
    """Main function for standalone worker"""
    import signal
    from utils.log_config import setup_logging

    setup_logging(level="INFO", log_file="logs/daily_plays_worker.log")

    worker = DailyPlaysWorker()

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