# workers/bull_flag_worker.py
"""
BULL_FLAG Worker - Specialized worker for bull flag pattern strategies
Focuses on flag patterns and volume breakouts
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
from shared.enhancement_service import EnhancementService
from adapters.ibkr_adapter_clean import IBKRAdapterClean as IBKRAdapter

class BullFlagWorker:
    """
    Specialized worker for BULL_FLAG opportunities
    Identifies and trades bull flag breakout patterns
    """

    def __init__(self, worker_id: str = "bull_flag_worker_1"):
        self.worker_id = worker_id
        self.logger = logging.getLogger(f"{__name__}.{worker_id}")

        # Load configuration
        self.config = Sistema4Config()
        self._load_strategy_params()

        # Initialize components
        self.database = Sistema4Database()
        self.message_bus = WorkerMessageBus(worker_id=worker_id)

        # Initialize IBKR adapter for enhancement service
        ibkr_config = self.config.get_ibkr_config()
        self.ibkr_adapter = IBKRAdapter(
            host=ibkr_config['host'],
            port=ibkr_config['port'],
            client_id=ibkr_config['client_id_bull_flag_worker']  # Dedicated client ID
        )

        # Enhancement service for detailed analysis
        self.enhancement_service = EnhancementService(self.ibkr_adapter)

        # Control
        self.is_running = False
        self.shutdown_requested = False

        self.logger.info(f"🏁 BULL_FLAG Worker initialized: {worker_id}")
        self.logger.info(f"   📏 Pole Height: {self.min_pole_height}%-{self.max_pole_height}%")
        self.logger.info(f"   📐 Flag Range: {self.max_flag_range}% | Duration: {self.min_flag_duration}-{self.max_flag_duration}min")

    def _load_strategy_params(self):
        """Load BULL_FLAG strategy parameters from config"""
        bull_flag_config = self.config.get_bull_flag_config()

        # Flag pattern parameters
        self.min_pole_height = bull_flag_config['min_pole_height_percent']
        self.max_pole_height = bull_flag_config['max_pole_height_percent']
        self.max_flag_range = bull_flag_config['max_flag_range_percent']

        # Timing parameters
        self.min_flag_duration = bull_flag_config['min_flag_duration_minutes']
        self.max_flag_duration = bull_flag_config['max_flag_duration_minutes']

        # Volume parameters
        self.min_volume = bull_flag_config['min_volume']
        self.volume_breakout_multiplier = bull_flag_config['volume_breakout_multiplier']

        # Risk management
        self.stop_loss_percent = bull_flag_config['stop_loss_percent']
        self.take_profit_percent = bull_flag_config['take_profit_percent']

        # Position sizing
        self.max_position_size = bull_flag_config['max_position_size']
        self.min_price = bull_flag_config['min_price']
        self.max_price = bull_flag_config['max_price']

    async def start(self):
        """Start BULL_FLAG worker"""
        try:
            # Connect to IBKR
            if not await self.ibkr_adapter.connect():
                self.logger.error("❌ Failed to connect to IBKR")
                return False

            # Connect enhancement service
            if not await self.enhancement_service.connect():
                self.logger.error("❌ Failed to connect enhancement service")
                return False

            # Connect to message bus
            if not await self.message_bus.connect():
                self.logger.error("❌ Failed to connect to Redis")
                return False

            # Subscribe to opportunities
            await self.message_bus.subscribe_to_opportunities(self._process_opportunity)

            self.is_running = True
            self.logger.info("🚀 BULL_FLAG Worker started - listening for opportunities...")

            # Start listening for messages
            await self.message_bus.start_listening()

        except Exception as e:
            self.logger.error(f"❌ Error starting BULL_FLAG worker: {e}")
            return False

    async def _process_opportunity(self, opportunity: Dict[str, Any]):
        """Process incoming opportunity"""
        try:
            # Only process BULL_FLAG opportunities
            if opportunity.get('opportunity_type') != 'BULL_FLAG':
                return

            symbol = opportunity.get('symbol')
            if not symbol:
                return

            self.logger.info(f"🔍 Processing BULL_FLAG opportunity: {symbol}")

            # Check if symbol is available
            if not self.database.is_symbol_available(symbol):
                self.logger.info(f"⏭️ {symbol} already taken - skipping")
                return

            # Reserve symbol
            if not self.database.reserve_symbol(symbol, self.worker_id):
                self.logger.info(f"⏭️ Failed to reserve {symbol} - skipping")
                return

            try:
                # First, enhance the opportunity with detailed data
                enhanced_opportunity = await self._enhance_opportunity(opportunity)
                if not enhanced_opportunity:
                    self.logger.info(f"⛔ {symbol} enhancement failed - skipping")
                    return

                # Analyze setup using enhanced data
                analysis = await self._analyze_flag_setup(enhanced_opportunity)
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

    async def _enhance_opportunity(self, opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enhance opportunity with detailed market data using enhancement service"""
        try:
            symbol = opportunity.get('symbol')
            if not symbol:
                return None

            # Create contract for IBKR
            from ib_insync import Stock
            contract = Stock(symbol, 'SMART', 'USD')

            # Get enhanced data
            enhanced_data = await self.enhancement_service.enhance_symbol(symbol, contract)

            # Merge enhanced data with original opportunity
            enhanced_opportunity = {**opportunity}
            enhanced_opportunity.update({
                'current_price': enhanced_data.get('current_price', 0.0),
                'previous_close': enhanced_data.get('previous_close', 0.0),
                'gap_percentage': enhanced_data.get('gap_percentage', 0.0),
                'volume': enhanced_data.get('current_volume', 0),
                'market_cap': enhanced_data.get('market_cap', 500_000_000),
                'enhanced': True
            })

            self.logger.debug(f"✅ Enhanced {symbol}: price=${enhanced_data.get('current_price', 0.0):.2f}, gap={enhanced_data.get('gap_percentage', 0.0):.1%}")

            return enhanced_opportunity

        except Exception as e:
            self.logger.error(f"❌ Error enhancing opportunity for {symbol}: {e}")
            return None

    async def _analyze_flag_setup(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze bull flag setup and determine if should trade"""
        symbol = opportunity['symbol']
        current_price = opportunity.get('current_price', 0.0)
        volume = opportunity.get('volume', 0)
        volume_ratio = opportunity.get('volume_ratio', 1.0)

        # Pattern analysis (would be calculated from real price data)
        pattern_analysis = self._analyze_flag_pattern(opportunity)

        analysis = {
            'should_trade': False,
            'reason': '',
            'action': 'BUY',  # Bull flags are long setups
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

        # Filter 3: Pattern validation
        if not pattern_analysis['valid_pattern']:
            analysis['reason'] = pattern_analysis['reason']
            return analysis

        # Filter 4: Volume breakout confirmation
        if volume_ratio < self.volume_breakout_multiplier:
            analysis['reason'] = f"Volume breakout insufficient: {volume_ratio:.1f}x < {self.volume_breakout_multiplier}x"
            return analysis

        # Calculate entry points based on flag pattern
        flag_high = pattern_analysis['flag_high']
        flag_low = pattern_analysis['flag_low']

        analysis['action'] = 'BUY'
        analysis['entry_price'] = flag_high * 1.01  # Enter slightly above flag high
        analysis['stop_loss'] = flag_low * 0.99     # Stop below flag low
        analysis['take_profit'] = analysis['entry_price'] * (1 + self.take_profit_percent / 100)

        # Position sizing based on pattern strength
        pattern_strength = pattern_analysis['strength']
        base_risk = 70  # $70 base risk
        adjusted_risk = base_risk * (1 + pattern_strength)

        stop_distance = abs(analysis['entry_price'] - analysis['stop_loss'])
        if stop_distance > 0:
            analysis['quantity'] = min(int(adjusted_risk / stop_distance), self.max_position_size)
        else:
            analysis['quantity'] = 100

        if analysis['quantity'] < 10:
            analysis['reason'] = f"Position size too small: {analysis['quantity']} shares"
            return analysis

        # All filters passed
        analysis['should_trade'] = True
        analysis['reason'] = f"Bull flag breakout: pole {pattern_analysis['pole_height']:.1f}%, vol {volume_ratio:.1f}x"

        self.logger.info(f"✅ {symbol} BULL_FLAG setup: {analysis['action']} {analysis['quantity']} @ ${analysis['entry_price']:.2f}")
        self.logger.info(f"   🏁 Pattern: Pole {pattern_analysis['pole_height']:.1f}%, Flag {pattern_analysis['flag_range']:.1f}%")
        self.logger.info(f"   🎯 Stop: ${analysis['stop_loss']:.2f} | Target: ${analysis['take_profit']:.2f}")

        return analysis

    def _analyze_flag_pattern(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze flag pattern characteristics"""
        # Simplified pattern analysis based on available data
        gap_percentage = opportunity.get('gap_percentage', 0.0)
        current_price = opportunity.get('current_price', 0.0)
        quality_score = opportunity.get('quality_score', 50.0)

        pattern = {
            'valid_pattern': False,
            'reason': '',
            'pole_height': 0.0,
            'flag_range': 0.0,
            'flag_high': current_price,
            'flag_low': current_price,
            'strength': 0.0
        }

        # Estimate pole height from gap (simplified)
        pole_height = abs(gap_percentage)

        # Pole height validation
        if pole_height < self.min_pole_height:
            pattern['reason'] = f"Pole too short: {pole_height:.1f}% < {self.min_pole_height}%"
            return pattern

        if pole_height > self.max_pole_height:
            pattern['reason'] = f"Pole too tall: {pole_height:.1f}% > {self.max_pole_height}%"
            return pattern

        # Estimate flag characteristics
        flag_range = min(pole_height * 0.2, self.max_flag_range)  # Flag should be ~20% of pole

        if flag_range > self.max_flag_range:
            pattern['reason'] = f"Flag range too wide: {flag_range:.1f}% > {self.max_flag_range}%"
            return pattern

        # Calculate pattern levels
        if gap_percentage > 0:  # Positive gap (bullish)
            pattern['flag_high'] = current_price
            pattern['flag_low'] = current_price * (1 - flag_range / 100)
        else:
            pattern['reason'] = "Negative gap not suitable for bull flag"
            return pattern

        # Pattern strength based on quality and proportions
        strength_score = quality_score / 100.0
        proportion_score = min(pole_height / 10.0, 1.0)  # Normalize to 0-1
        pattern['strength'] = (strength_score + proportion_score) / 2.0

        # Valid pattern
        pattern['valid_pattern'] = True
        pattern['pole_height'] = pole_height
        pattern['flag_range'] = flag_range
        pattern['reason'] = f"Valid bull flag: pole {pole_height:.1f}%, flag {flag_range:.1f}%"

        return pattern

    def _generate_trade_request(self, symbol: str, opportunity: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trade request for execution engine"""
        return {
            'symbol': symbol,
            'action': analysis['action'],
            'quantity': analysis['quantity'],
            'order_type': 'STOP_LIMIT',  # Bull flags often use stop-limit for breakouts
            'limit_price': analysis['entry_price'],
            'stop_price': analysis['entry_price'] * 0.995,  # Trigger slightly below entry
            'stop_loss_price': analysis['stop_loss'],
            'take_profit_price': analysis['take_profit'],
            'strategy': 'BULL_FLAG',
            'worker_id': self.worker_id,
            'reason': analysis['reason'],
            'opportunity_data': opportunity
        }

    async def stop(self):
        """Stop BULL_FLAG worker"""
        try:
            self.is_running = False
            self.shutdown_requested = True

            if self.message_bus:
                await self.message_bus.disconnect()

            if self.enhancement_service:
                await self.enhancement_service.disconnect()

            if self.ibkr_adapter:
                await self.ibkr_adapter.disconnect()

            self.logger.info("🛑 BULL_FLAG Worker stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping BULL_FLAG worker: {e}")

async def main():
    """Main function for standalone worker"""
    import signal
    from utils.log_config import setup_logging

    setup_logging(level="INFO", log_file="logs/bull_flag_worker.log")

    worker = BullFlagWorker()

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