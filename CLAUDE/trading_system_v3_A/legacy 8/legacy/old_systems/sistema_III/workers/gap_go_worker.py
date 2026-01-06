#!/usr/bin/env python3
"""
GAP_GO Strategy Worker
Handles gap-up momentum trades with specific entry/exit rules
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

class GapGoWorker:
    """Worker for GAP_GO strategy execution"""

    def __init__(self, ibkr_adapter: IBKRAdapter):
        self.logger = logging.getLogger("GapGoWorker")
        self.ibkr = ibkr_adapter
        self.active_positions = {}

        # Load configuration
        self.config = get_config()

        # GAP_GO specific parameters from config
        self.min_gap_percent = self.config.getfloat('STRATEGY_GAP_GO', 'min_gap_percent', fallback=2.0)
        self.max_gap_percent = self.config.getfloat('STRATEGY_GAP_GO', 'max_gap_percent', fallback=8.0)
        self.min_volume_ratio = self.config.getfloat('STRATEGY_GAP_GO', 'min_volume_ratio', fallback=2.0)
        self.max_volume_ratio = self.config.getfloat('STRATEGY_GAP_GO', 'max_volume_ratio', fallback=10.0)
        self.stop_loss_percent = self.config.getfloat('STRATEGY_GAP_GO', 'stop_loss_percent', fallback=0.03)
        self.profit_target_percent = self.config.getfloat('STRATEGY_GAP_GO', 'take_profit_percent', fallback=0.06)
        self.min_price_trend_duration = self.config.getint('STRATEGY_GAP_GO', 'min_price_trend_duration', fallback=5)

        self.logger.info(f"✅ GAP_GO Worker initialized - Gap: {self.min_gap_percent:.1f}%-{self.max_gap_percent:.1f}%, Volume: {self.min_volume_ratio:.1f}x-{self.max_volume_ratio:.1f}x")

    async def can_handle(self, opportunity: Dict) -> bool:
        """Check if this worker can handle the opportunity"""
        return opportunity.get('opportunity_type') == 'GAP_GO'

    async def execute_opportunity(self, opportunity: Dict) -> Dict:
        """Execute GAP_GO strategy"""
        try:
            symbol = opportunity['symbol']
            current_price = opportunity['current_price']
            gap_percent = opportunity['gap_percentage']

            self.logger.info(f"🚀 GAP_GO: Processing {symbol} with {gap_percent:.2f}% gap")

            # Validate gap criteria
            if gap_percent < self.min_gap_percent:
                return {'status': 'rejected', 'reason': f'Gap {gap_percent:.2f}% below minimum {self.min_gap_percent}%'}

            if gap_percent > self.max_gap_percent:
                return {'status': 'rejected', 'reason': f'Gap {gap_percent:.2f}% above maximum {self.max_gap_percent}%'}

            # Validate volume criteria
            volume_ratio = opportunity.get('volume_ratio', 1.0)
            if volume_ratio < self.min_volume_ratio:
                return {'status': 'rejected', 'reason': f'Volume ratio {volume_ratio:.2f}x below minimum {self.min_volume_ratio}x'}

            if volume_ratio > self.max_volume_ratio:
                return {'status': 'rejected', 'reason': f'Volume ratio {volume_ratio:.2f}x above maximum {self.max_volume_ratio}x'}

            # Calculate position size and levels
            position_size = await self._calculate_position_size(symbol, current_price)
            entry_price = current_price * 1.005  # Enter 0.5% above current
            stop_loss = current_price * (1 - self.stop_loss_percent)
            profit_target = current_price * (1 + self.profit_target_percent)

            # Create order
            order_result = await self._place_gap_go_order(
                symbol=symbol,
                quantity=position_size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                profit_target=profit_target
            )

            if order_result['success']:
                self.active_positions[symbol] = {
                    'strategy': 'GAP_GO',
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'profit_target': profit_target,
                    'quantity': position_size,
                    'timestamp': datetime.now()
                }

                return {
                    'status': 'executed',
                    'symbol': symbol,
                    'strategy': 'GAP_GO',
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'profit_target': profit_target,
                    'quantity': position_size
                }
            else:
                return {'status': 'failed', 'reason': order_result['error']}

        except Exception as e:
            self.logger.error(f"❌ GAP_GO execution error: {e}")
            return {'status': 'error', 'reason': str(e)}

    async def _calculate_position_size(self, symbol: str, price: float) -> int:
        """Calculate position size based on risk management"""
        # Simple position sizing - can be enhanced
        max_risk_amount = 500  # Max $500 risk per trade
        risk_per_share = price * self.stop_loss_percent

        if risk_per_share > 0:
            position_size = int(max_risk_amount / risk_per_share)
            return max(1, min(position_size, 1000))  # Between 1 and 1000 shares
        return 100  # Default fallback

    async def _place_gap_go_order(self, symbol: str, quantity: int, entry_price: float,
                                  stop_loss: float, profit_target: float) -> Dict:
        """Place GAP_GO order with bracket setup"""
        try:
            # This would integrate with actual IBKR order placement
            self.logger.info(f"📊 GAP_GO Order: {symbol} x{quantity} @ ${entry_price:.2f}")
            self.logger.info(f"    Stop: ${stop_loss:.2f} | Target: ${profit_target:.2f}")

            # Placeholder for actual order placement
            return {'success': True, 'order_id': f"GAP_{symbol}_{datetime.now().strftime('%H%M%S')}"}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def monitor_positions(self) -> List[Dict]:
        """Monitor active GAP_GO positions"""
        updates = []

        for symbol, position in self.active_positions.items():
            try:
                # Get current price and check exit conditions
                current_price = await self._get_current_price(symbol)

                if current_price <= position['stop_loss']:
                    # Stop loss hit
                    await self._close_position(symbol, 'STOP_LOSS')
                    updates.append({
                        'symbol': symbol,
                        'action': 'CLOSED',
                        'reason': 'STOP_LOSS',
                        'price': current_price
                    })
                elif current_price >= position['profit_target']:
                    # Profit target hit
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
            self.logger.info(f"🔄 GAP_GO: Closed {symbol} - {reason}")