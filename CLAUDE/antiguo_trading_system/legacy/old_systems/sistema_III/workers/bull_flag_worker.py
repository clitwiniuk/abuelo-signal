#!/usr/bin/env python3
"""
BULL_FLAG Strategy Worker
Handles bull flag pattern trades with breakout confirmation
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

class BullFlagWorker:
    """Worker for BULL_FLAG strategy execution"""

    def __init__(self, ibkr_adapter: IBKRAdapter):
        self.logger = logging.getLogger("BullFlagWorker")
        self.ibkr = ibkr_adapter
        self.active_positions = {}

        # Load configuration
        self.config = get_config()

        # BULL_FLAG specific parameters from config
        self.min_flag_duration_minutes = self.config.getint('STRATEGY_BULL_FLAG', 'min_flag_duration_minutes', fallback=15)
        self.max_flag_duration_minutes = self.config.getint('STRATEGY_BULL_FLAG', 'max_flag_duration_minutes', fallback=120)
        self.min_pole_height_percent = self.config.getfloat('STRATEGY_BULL_FLAG', 'min_pole_height_percent', fallback=3.0)
        self.max_consolidation_range_percent = self.config.getfloat('STRATEGY_BULL_FLAG', 'max_consolidation_range_percent', fallback=2.0)
        self.breakout_volume_threshold = self.config.getfloat('STRATEGY_BULL_FLAG', 'volume_breakout_multiplier', fallback=1.8)
        self.stop_loss_percent = self.config.getfloat('STRATEGY_BULL_FLAG', 'stop_loss_percent', fallback=0.03)
        self.profit_target_percent = self.config.getfloat('STRATEGY_BULL_FLAG', 'take_profit_percent', fallback=0.06)

        # Additional parameters (could be added to config)
        self.min_flag_quality = 0.75        # Minimum flag pattern quality

        self.logger.info(f"✅ BULL_FLAG Worker initialized - Pole: {self.min_pole_height_percent:.1f}%+, Consolidation: <{self.max_consolidation_range_percent:.1f}%")

    async def can_handle(self, opportunity: Dict) -> bool:
        """Check if this worker can handle the opportunity"""
        return opportunity.get('opportunity_type') == 'BULL_FLAG'

    async def execute_opportunity(self, opportunity: Dict) -> Dict:
        """Execute BULL_FLAG strategy"""
        try:
            symbol = opportunity['symbol']
            current_price = opportunity['current_price']
            quality_score = opportunity.get('quality_score', 0.0)

            # Bull flag specific data
            flag_quality = opportunity.get('flag_quality', 0.0)
            breakout_level = opportunity.get('breakout_level', current_price * 1.02)
            flag_volume = opportunity.get('flag_volume_ratio', 1.0)
            pole_height_percent = opportunity.get('pole_height_percent', 0.0)
            consolidation_range_percent = opportunity.get('consolidation_range_percent', 0.0)
            flag_duration_minutes = opportunity.get('flag_duration_minutes', 0)

            self.logger.info(f"🚩 BULL_FLAG: Processing {symbol} - Flag Quality: {flag_quality:.2f}, Pole: {pole_height_percent:.1f}%, Consolidation: {consolidation_range_percent:.1f}%")

            # Validate bull flag criteria from config
            if flag_quality < self.min_flag_quality:
                return {'status': 'rejected', 'reason': f'Flag quality {flag_quality:.2f} below minimum {self.min_flag_quality}'}

            if pole_height_percent < self.min_pole_height_percent:
                return {'status': 'rejected', 'reason': f'Pole height {pole_height_percent:.1f}% below minimum {self.min_pole_height_percent:.1f}%'}

            if consolidation_range_percent > self.max_consolidation_range_percent:
                return {'status': 'rejected', 'reason': f'Consolidation range {consolidation_range_percent:.1f}% above maximum {self.max_consolidation_range_percent:.1f}%'}

            if flag_duration_minutes < self.min_flag_duration_minutes:
                return {'status': 'rejected', 'reason': f'Flag duration {flag_duration_minutes}min below minimum {self.min_flag_duration_minutes}min'}

            if flag_duration_minutes > self.max_flag_duration_minutes:
                return {'status': 'rejected', 'reason': f'Flag duration {flag_duration_minutes}min above maximum {self.max_flag_duration_minutes}min'}

            # Calculate position size and levels
            position_size = await self._calculate_position_size(symbol, current_price)

            # Entry slightly above breakout level to confirm breakout
            entry_price = breakout_level * 1.005  # Enter 0.5% above breakout
            stop_loss = breakout_level * (1 - self.stop_loss_percent)  # Stop below breakout
            profit_target = breakout_level * (1 + self.profit_target_percent)

            # Wait for breakout confirmation before placing order
            breakout_confirmed = await self._wait_for_breakout(symbol, breakout_level)

            if not breakout_confirmed:
                return {'status': 'rejected', 'reason': 'Breakout not confirmed within timeout'}

            # Create order after breakout confirmation
            order_result = await self._place_bull_flag_order(
                symbol=symbol,
                quantity=position_size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                profit_target=profit_target
            )

            if order_result['success']:
                self.active_positions[symbol] = {
                    'strategy': 'BULL_FLAG',
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'profit_target': profit_target,
                    'quantity': position_size,
                    'breakout_level': breakout_level,
                    'timestamp': datetime.now()
                }

                return {
                    'status': 'executed',
                    'symbol': symbol,
                    'strategy': 'BULL_FLAG',
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'profit_target': profit_target,
                    'quantity': position_size,
                    'breakout_level': breakout_level
                }
            else:
                return {'status': 'failed', 'reason': order_result['error']}

        except Exception as e:
            self.logger.error(f"❌ BULL_FLAG execution error: {e}")
            return {'status': 'error', 'reason': str(e)}

    async def _wait_for_breakout(self, symbol: str, breakout_level: float, timeout_minutes: int = 30) -> bool:
        """Wait for price to break above the flag pattern with volume confirmation"""
        try:
            self.logger.info(f"⏳ Waiting for {symbol} breakout above ${breakout_level:.2f}")

            start_time = datetime.now()
            timeout_seconds = timeout_minutes * 60

            while (datetime.now() - start_time).total_seconds() < timeout_seconds:
                current_price = await self._get_current_price(symbol)
                current_volume = await self._get_current_volume_ratio(symbol)

                if current_price > breakout_level and current_volume > self.breakout_volume_threshold:
                    self.logger.info(f"✅ {symbol} breakout confirmed: ${current_price:.2f} with {current_volume:.2f}x volume")
                    return True

                await asyncio.sleep(30)  # Check every 30 seconds

            self.logger.info(f"⏰ {symbol} breakout timeout after {timeout_minutes} minutes")
            return False

        except Exception as e:
            self.logger.error(f"❌ Error waiting for breakout: {e}")
            return False

    async def _calculate_position_size(self, symbol: str, price: float) -> int:
        """Calculate position size based on risk management"""
        max_risk_amount = 750  # Max $750 risk per trade (higher for pattern trades)
        risk_per_share = price * self.stop_loss_percent

        if risk_per_share > 0:
            position_size = int(max_risk_amount / risk_per_share)
            return max(1, min(position_size, 400))  # Between 1 and 400 shares
        return 100  # Default fallback

    async def _place_bull_flag_order(self, symbol: str, quantity: int, entry_price: float,
                                     stop_loss: float, profit_target: float) -> Dict:
        """Place BULL_FLAG order with bracket setup"""
        try:
            self.logger.info(f"📊 BULL_FLAG Order: {symbol} x{quantity} @ ${entry_price:.2f}")
            self.logger.info(f"    Stop: ${stop_loss:.2f} | Target: ${profit_target:.2f}")

            # Placeholder for actual order placement
            return {'success': True, 'order_id': f"BF_{symbol}_{datetime.now().strftime('%H%M%S')}"}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def monitor_positions(self) -> List[Dict]:
        """Monitor active BULL_FLAG positions"""
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
                else:
                    # Trail stop loss for profitable positions
                    if current_price > position['entry_price'] * 1.05:  # 5% profit
                        new_stop = current_price * 0.98  # Trail at 2% below current
                        if new_stop > position['stop_loss']:
                            position['stop_loss'] = new_stop
                            self.logger.info(f"📈 {symbol} trailing stop updated to ${new_stop:.2f}")

            except Exception as e:
                self.logger.error(f"❌ Error monitoring {symbol}: {e}")

        return updates

    async def _get_current_price(self, symbol: str) -> float:
        """Get current market price"""
        # Placeholder - would use IBKR adapter
        return 10.0

    async def _get_current_volume_ratio(self, symbol: str) -> float:
        """Get current volume ratio vs average"""
        # Placeholder - would use IBKR adapter
        return 1.5

    async def _close_position(self, symbol: str, reason: str):
        """Close position and remove from tracking"""
        if symbol in self.active_positions:
            del self.active_positions[symbol]
            self.logger.info(f"🔄 BULL_FLAG: Closed {symbol} - {reason}")