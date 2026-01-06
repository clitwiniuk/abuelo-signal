#!/usr/bin/env python3
"""
DAILY_PLAYS Strategy Worker
Handles intraday momentum trades with pattern-based entry/exit
"""

import asyncio
import logging
import sys
import os
from typing import Dict, List, Optional
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.ibkr_adapter import IBKRAdapter
from core.service_locator import get_config

class DailyPlaysWorker:
    """Worker for DAILY_PLAYS strategy execution"""

    def __init__(self, ibkr_adapter: IBKRAdapter):
        self.logger = logging.getLogger("DailyPlaysWorker")
        self.ibkr = ibkr_adapter
        self.active_positions = {}

        # Load configuration
        self.config = get_config()

        # DAILY_PLAYS specific parameters from config
        self.min_volume_ratio = self.config.getfloat('STRATEGY_DAILY_PLAYS', 'min_volume_ratio', fallback=4.0)
        self.min_news_sentiment = self.config.getfloat('STRATEGY_DAILY_PLAYS', 'min_news_sentiment', fallback=0.6)
        self.max_gap_percent = self.config.getfloat('STRATEGY_DAILY_PLAYS', 'max_gap_percent', fallback=15.0)
        self.min_consolidation_minutes = self.config.getint('STRATEGY_DAILY_PLAYS', 'min_consolidation_minutes', fallback=30)
        self.stop_loss_percent = self.config.getfloat('STRATEGY_DAILY_PLAYS', 'stop_loss_percent', fallback=0.04)
        self.profit_target_percent = self.config.getfloat('STRATEGY_DAILY_PLAYS', 'take_profit_percent', fallback=0.08)

        # Quality threshold (could be added to config)
        self.quality_threshold = 70.0  # Minimum quality score

        self.logger.info(f"✅ DAILY_PLAYS Worker initialized - Volume: {self.min_volume_ratio:.1f}x+, Sentiment: {self.min_news_sentiment:.1f}+")

    async def can_handle(self, opportunity: Dict) -> bool:
        """Check if this worker can handle the opportunity"""
        return opportunity.get('opportunity_type') == 'DAILY_PLAYS'

    async def execute_opportunity(self, opportunity: Dict) -> Dict:
        """Execute DAILY_PLAYS strategy"""
        try:
            symbol = opportunity['symbol']
            current_price = opportunity['current_price']
            quality_score = opportunity.get('quality_score', 0.0)
            volume_ratio = opportunity.get('volume_ratio', 1.0)

            self.logger.info(f"📈 DAILY_PLAYS: Processing {symbol} - Quality: {quality_score:.1f}, Volume: {volume_ratio:.2f}x")

            # Validate quality criteria
            if quality_score < self.quality_threshold:
                return {'status': 'rejected', 'reason': f'Quality {quality_score:.1f} below threshold {self.quality_threshold}'}

            if volume_ratio < self.min_volume_ratio:
                return {'status': 'rejected', 'reason': f'Volume ratio {volume_ratio:.2f} below minimum {self.min_volume_ratio}'}

            # Additional validations based on config
            gap_percentage = opportunity.get('gap_percentage', 0.0)
            if gap_percentage > self.max_gap_percent:
                return {'status': 'rejected', 'reason': f'Gap {gap_percentage:.2f}% above maximum {self.max_gap_percent}%'}

            # News sentiment validation if available
            sentiment_score = opportunity.get('sentiment_score', 0.0)
            if sentiment_score > 0 and sentiment_score < self.min_news_sentiment:
                return {'status': 'rejected', 'reason': f'News sentiment {sentiment_score:.2f} below minimum {self.min_news_sentiment}'}

            # Calculate position size and levels
            position_size = await self._calculate_position_size(symbol, current_price)
            entry_price = current_price * 1.003  # Enter 0.3% above current
            stop_loss = current_price * (1 - self.stop_loss_percent)
            profit_target = current_price * (1 + self.profit_target_percent)

            # Create order
            order_result = await self._place_daily_plays_order(
                symbol=symbol,
                quantity=position_size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                profit_target=profit_target
            )

            if order_result['success']:
                self.active_positions[symbol] = {
                    'strategy': 'DAILY_PLAYS',
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'profit_target': profit_target,
                    'quantity': position_size,
                    'timestamp': datetime.now()
                }

                return {
                    'status': 'executed',
                    'symbol': symbol,
                    'strategy': 'DAILY_PLAYS',
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'profit_target': profit_target,
                    'quantity': position_size
                }
            else:
                return {'status': 'failed', 'reason': order_result['error']}

        except Exception as e:
            self.logger.error(f"❌ DAILY_PLAYS execution error: {e}")
            return {'status': 'error', 'reason': str(e)}

    async def _calculate_position_size(self, symbol: str, price: float) -> int:
        """Calculate position size based on risk management"""
        max_risk_amount = 400  # Max $400 risk per trade
        risk_per_share = price * self.stop_loss_percent

        if risk_per_share > 0:
            position_size = int(max_risk_amount / risk_per_share)
            return max(1, min(position_size, 800))  # Between 1 and 800 shares
        return 100  # Default fallback

    async def _place_daily_plays_order(self, symbol: str, quantity: int, entry_price: float,
                                       stop_loss: float, profit_target: float) -> Dict:
        """Place DAILY_PLAYS order with bracket setup"""
        try:
            self.logger.info(f"📊 DAILY_PLAYS Order: {symbol} x{quantity} @ ${entry_price:.2f}")
            self.logger.info(f"    Stop: ${stop_loss:.2f} | Target: ${profit_target:.2f}")

            # Placeholder for actual order placement
            return {'success': True, 'order_id': f"DP_{symbol}_{datetime.now().strftime('%H%M%S')}"}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def monitor_positions(self) -> List[Dict]:
        """Monitor active DAILY_PLAYS positions"""
        updates = []

        for symbol, position in self.active_positions.items():
            try:
                current_price = await self._get_current_price(symbol)

                if current_price <= position['stop_loss']:
                    await self._close_position(symbol, 'STOP_LOSS')
                    updates.append({
                        'symbol': symbol,
                        'action': 'CLOSED',
                        'reason': 'STOP_LOSS',
                        'price': current_price
                    })
                elif current_price >= position['profit_target']:
                    await self._close_position(symbol, 'PROFIT_TARGET')
                    updates.append({
                        'symbol': symbol,
                        'action': 'CLOSED',
                        'reason': 'PROFIT_TARGET',
                        'price': current_price
                    })

            except Exception as e:
                self.logger.error(f"❌ Error monitoring {symbol}: {e}")

        return updates

    async def _get_current_price(self, symbol: str) -> float:
        """Get current market price"""
        # Placeholder - would use IBKR adapter
        return 10.0

    async def _close_position(self, symbol: str, reason: str):
        """Close position and remove from tracking"""
        if symbol in self.active_positions:
            del self.active_positions[symbol]
            self.logger.info(f"🔄 DAILY_PLAYS: Closed {symbol} - {reason}")