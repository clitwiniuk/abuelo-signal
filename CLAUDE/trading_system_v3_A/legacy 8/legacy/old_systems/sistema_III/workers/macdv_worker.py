#!/usr/bin/env python3
"""
MACDV Strategy Worker
Handles MACD Divergence trades with technical analysis confirmation
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

class MacdvWorker:
    """Worker for MACDV strategy execution"""

    def __init__(self, ibkr_adapter: IBKRAdapter):
        self.logger = logging.getLogger("MacdvWorker")
        self.ibkr = ibkr_adapter
        self.active_positions = {}

        # Load configuration
        self.config = get_config()

        # MACDV specific parameters from config
        self.min_volume_ratio = self.config.getfloat('STRATEGY_MACDV', 'min_volume_ratio', fallback=1.5)
        self.macd_signal_threshold = self.config.getfloat('STRATEGY_MACDV', 'macd_signal_threshold', fallback=0.02)
        self.volume_confirmation_periods = self.config.getint('STRATEGY_MACDV', 'volume_confirmation_periods', fallback=3)
        self.stop_loss_percent = self.config.getfloat('STRATEGY_MACDV', 'stop_loss_percent', fallback=0.025)
        self.profit_target_percent = self.config.getfloat('STRATEGY_MACDV', 'take_profit_percent', fallback=0.05)

        # Additional MACDV specific parameters (could be added to config)
        self.min_divergence_strength = 0.6  # Minimum divergence strength
        self.confirmation_threshold = 0.7    # Technical confirmation threshold

        self.logger.info(f"✅ MACDV Worker initialized - Volume: {self.min_volume_ratio:.1f}x+, MACD threshold: {self.macd_signal_threshold:.3f}")

    async def can_handle(self, opportunity: Dict) -> bool:
        """Check if this worker can handle the opportunity"""
        return opportunity.get('opportunity_type') == 'MACDV'

    async def execute_opportunity(self, opportunity: Dict) -> Dict:
        """Execute MACDV strategy"""
        try:
            symbol = opportunity['symbol']
            current_price = opportunity['current_price']
            quality_score = opportunity.get('quality_score', 0.0)

            # MACDV specific data
            divergence_strength = opportunity.get('divergence_strength', 0.0)
            macd_signal = opportunity.get('macd_signal', 'NEUTRAL')

            self.logger.info(f"📊 MACDV: Processing {symbol} - Divergence: {divergence_strength:.2f}, Signal: {macd_signal}")

            # Validate MACD divergence criteria
            if divergence_strength < self.min_divergence_strength:
                return {'status': 'rejected', 'reason': f'Divergence strength {divergence_strength:.2f} below minimum {self.min_divergence_strength}'}

            if macd_signal not in ['BULLISH', 'BEARISH']:
                return {'status': 'rejected', 'reason': f'MACD signal {macd_signal} not strong enough'}

            # Volume validation from config
            volume_ratio = opportunity.get('volume_ratio', 1.0)
            if volume_ratio < self.min_volume_ratio:
                return {'status': 'rejected', 'reason': f'Volume ratio {volume_ratio:.2f}x below minimum {self.min_volume_ratio}x'}

            # MACD signal strength validation from config
            macd_strength = abs(opportunity.get('macd_value', 0.0))
            if macd_strength < self.macd_signal_threshold:
                return {'status': 'rejected', 'reason': f'MACD signal strength {macd_strength:.3f} below threshold {self.macd_signal_threshold:.3f}'}

            # Calculate position size and levels
            position_size = await self._calculate_position_size(symbol, current_price)

            # Determine entry based on signal direction
            if macd_signal == 'BULLISH':
                entry_price = current_price * 1.002  # Enter 0.2% above for bullish
                stop_loss = current_price * (1 - self.stop_loss_percent)
                profit_target = current_price * (1 + self.profit_target_percent)
                action = 'BUY'
            else:  # BEARISH
                entry_price = current_price * 0.998  # Enter 0.2% below for bearish
                stop_loss = current_price * (1 + self.stop_loss_percent)
                profit_target = current_price * (1 - self.profit_target_percent)
                action = 'SELL'

            # Create order
            order_result = await self._place_macdv_order(
                symbol=symbol,
                action=action,
                quantity=position_size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                profit_target=profit_target
            )

            if order_result['success']:
                self.active_positions[symbol] = {
                    'strategy': 'MACDV',
                    'action': action,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'profit_target': profit_target,
                    'quantity': position_size,
                    'timestamp': datetime.now()
                }

                return {
                    'status': 'executed',
                    'symbol': symbol,
                    'strategy': 'MACDV',
                    'action': action,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'profit_target': profit_target,
                    'quantity': position_size
                }
            else:
                return {'status': 'failed', 'reason': order_result['error']}

        except Exception as e:
            self.logger.error(f"❌ MACDV execution error: {e}")
            return {'status': 'error', 'reason': str(e)}

    async def _calculate_position_size(self, symbol: str, price: float) -> int:
        """Calculate position size based on risk management"""
        max_risk_amount = 600  # Max $600 risk per trade (higher for technical setups)
        risk_per_share = price * self.stop_loss_percent

        if risk_per_share > 0:
            position_size = int(max_risk_amount / risk_per_share)
            return max(1, min(position_size, 500))  # Between 1 and 500 shares
        return 100  # Default fallback

    async def _place_macdv_order(self, symbol: str, action: str, quantity: int, entry_price: float,
                                 stop_loss: float, profit_target: float) -> Dict:
        """Place MACDV order with bracket setup"""
        try:
            self.logger.info(f"📊 MACDV Order: {action} {symbol} x{quantity} @ ${entry_price:.2f}")
            self.logger.info(f"    Stop: ${stop_loss:.2f} | Target: ${profit_target:.2f}")

            # Placeholder for actual order placement
            return {'success': True, 'order_id': f"MACDV_{symbol}_{datetime.now().strftime('%H%M%S')}"}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def monitor_positions(self) -> List[Dict]:
        """Monitor active MACDV positions"""
        updates = []

        for symbol, position in self.active_positions.items():
            try:
                current_price = await self._get_current_price(symbol)
                action = position['action']

                # Check exit conditions based on position direction
                if action == 'BUY':
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
                else:  # SELL
                    if current_price >= position['stop_loss']:
                        await self._close_position(symbol, 'STOP_LOSS')
                        updates.append({
                            'symbol': symbol,
                            'action': 'CLOSED',
                            'reason': 'STOP_LOSS',
                            'price': current_price
                        })
                    elif current_price <= position['profit_target']:
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
            self.logger.info(f"🔄 MACDV: Closed {symbol} - {reason}")