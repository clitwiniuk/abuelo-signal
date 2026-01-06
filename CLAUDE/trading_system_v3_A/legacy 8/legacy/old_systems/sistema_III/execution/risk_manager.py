#!/usr/bin/env python3
"""
Risk Management System
Manages position sizing, exposure limits, and trading risk across all strategies
"""

import asyncio
import logging
import sys
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.service_locator import get_config

class RiskManager:
    """
    Centralized risk management for all trading strategies
    """

    def __init__(self):
        self.logger = logging.getLogger("RiskManager")

        # Load configuration
        self.config = get_config()

        # Risk parameters from config
        self.max_portfolio_risk = self.config.getfloat('RISK_MANAGER', 'max_portfolio_risk', fallback=0.10)
        self.max_single_position_risk = self.config.getfloat('RISK_MANAGER', 'max_risk_per_trade', fallback=0.02)
        self.max_daily_trades = self.config.getint('RISK_MANAGER', 'max_daily_trades', fallback=20)
        self.max_positions = self.config.getint('RISK_MANAGER', 'max_positions', fallback=5)
        self.max_daily_loss = self.config.getfloat('RISK_MANAGER', 'max_daily_loss', fallback=-1000.0)

        # Portfolio tracking from config
        self.total_portfolio_value = self.config.getfloat('RISK_MANAGER', 'portfolio_capital', fallback=50000.0)
        self.max_position_size = self.config.getint('RISK_MANAGER', 'max_position_size', fallback=500)
        self.min_position_size = self.config.getint('RISK_MANAGER', 'min_position_size', fallback=100)

        # Position sizing method
        self.position_sizing_method = self.config.get('RISK_MANAGER', 'position_sizing_method', fallback='FIXED')

        # Market hours from config
        self.market_open = self.config.get('MARKET_SESSIONS', 'market_open', fallback='09:30')
        self.market_close = self.config.get('MARKET_SESSIONS', 'market_close', fallback='16:00')

        # Strategy-specific parameters
        self.strategy_params = self._load_strategy_risk_params()

        # Runtime tracking
        self.current_positions = {}             # Active positions
        self.daily_trade_count = 0
        self.daily_reset_time = None

        # Risk metrics tracking
        self.risk_metrics = {
            'total_risk_amount': 0.0,
            'sector_exposure': {},
            'strategy_exposure': {},
            'daily_pnl': 0.0,
            'max_drawdown': 0.0
        }

        self.logger.info(f"🛡️ Risk Manager initialized - Portfolio: ${self.total_portfolio_value:.0f}, Max Risk: {self.max_portfolio_risk*100:.1f}%")

    def _load_strategy_risk_params(self) -> Dict:
        """Load strategy-specific risk parameters from config"""
        return {
            'GAP_GO': {
                'stop_loss_percent': self.config.getfloat('STRATEGY_GAP_GO', 'stop_loss_percent', fallback=0.03),
                'take_profit_percent': self.config.getfloat('STRATEGY_GAP_GO', 'take_profit_percent', fallback=0.06)
            },
            'DAILY_PLAYS': {
                'stop_loss_percent': self.config.getfloat('STRATEGY_DAILY_PLAYS', 'stop_loss_percent', fallback=0.04),
                'take_profit_percent': self.config.getfloat('STRATEGY_DAILY_PLAYS', 'take_profit_percent', fallback=0.08)
            },
            'MACDV': {
                'stop_loss_percent': self.config.getfloat('STRATEGY_MACDV', 'stop_loss_percent', fallback=0.025),
                'take_profit_percent': self.config.getfloat('STRATEGY_MACDV', 'take_profit_percent', fallback=0.05)
            },
            'BULL_FLAG': {
                'stop_loss_percent': self.config.getfloat('STRATEGY_BULL_FLAG', 'stop_loss_percent', fallback=0.03),
                'take_profit_percent': self.config.getfloat('STRATEGY_BULL_FLAG', 'take_profit_percent', fallback=0.06)
            }
        }

    async def approve_trade(self, opportunity: Dict) -> Dict:
        """
        Approve or reject a trade based on risk parameters
        """
        try:
            symbol = opportunity['symbol']
            strategy = opportunity['opportunity_type']
            current_price = opportunity.get('current_price', 0.0)

            # Reset daily counters if needed
            await self._reset_daily_counters_if_needed()

            # Risk checks
            checks = []

            # 1. Daily trade limit
            if self.daily_trade_count >= self.max_daily_trades:
                return {'approved': False, 'reason': f'Daily trade limit reached ({self.max_daily_trades})'}

            # 2. Max positions limit
            if len(self.current_positions) >= self.max_positions:
                return {'approved': False, 'reason': f'Max positions reached ({self.max_positions})'}

            # 3. Daily loss limit
            if self.risk_metrics['daily_pnl'] <= self.max_daily_loss:
                return {'approved': False, 'reason': f'Daily loss limit reached (${self.max_daily_loss:.0f})'}

            # 4. Portfolio risk limit
            position_risk_amount = self._calculate_position_risk(opportunity)
            total_risk_after = self.risk_metrics['total_risk_amount'] + position_risk_amount
            max_risk_allowed = self.total_portfolio_value * self.max_portfolio_risk

            if total_risk_after > max_risk_allowed:
                return {'approved': False, 'reason': f'Portfolio risk limit exceeded: ${total_risk_after:.0f} > ${max_risk_allowed:.0f}'}

            # 5. Single position risk limit
            max_single_risk = self.total_portfolio_value * self.max_single_position_risk
            if position_risk_amount > max_single_risk:
                return {'approved': False, 'reason': f'Single position risk too high: ${position_risk_amount:.0f} > ${max_single_risk:.0f}'}

            # 6. Market hours check
            if not await self._is_market_hours():
                return {'approved': False, 'reason': 'Market is closed'}

            # 7. Volatility check
            if await self._is_high_volatility_period():
                return {'approved': False, 'reason': 'High volatility period - reducing risk'}

            # All checks passed
            recommended_size = await self._calculate_recommended_position_size(opportunity)

            # Increment trade counter
            self.daily_trade_count += 1

            self.logger.info(f"✅ Trade approved: {symbol} ({strategy}) - Size: {recommended_size}, Risk: ${position_risk_amount:.0f}")

            return {
                'approved': True,
                'recommended_position_size': recommended_size,
                'risk_amount': position_risk_amount,
                'remaining_daily_trades': self.max_daily_trades - self.daily_trade_count,
                'portfolio_risk_utilization': (total_risk_after / max_risk_allowed) * 100
            }

        except Exception as e:
            self.logger.error(f"❌ Error in trade approval: {e}")
            return {'approved': False, 'reason': f'Risk check error: {str(e)}'}

    def _calculate_position_risk(self, opportunity: Dict) -> float:
        """Calculate risk amount for a position based on config parameters"""
        try:
            current_price = opportunity.get('current_price', 0.0)
            strategy = opportunity.get('opportunity_type', '')

            # Get strategy-specific stop loss from config
            strategy_config = self.strategy_params.get(strategy, {})
            stop_loss_percent = strategy_config.get('stop_loss_percent', 0.02)

            # Position sizing based on config method
            if self.position_sizing_method == 'FIXED':
                # Fixed dollar amount risk per trade
                max_risk_per_position = self.total_portfolio_value * self.max_single_position_risk
                shares = int(max_risk_per_position / (current_price * stop_loss_percent)) if current_price > 0 and stop_loss_percent > 0 else self.min_position_size
            else:
                # Percentage of portfolio method
                shares = self.max_position_size

            # Apply position size limits from config
            shares = max(self.min_position_size, min(shares, self.max_position_size))

            risk_amount = shares * current_price * stop_loss_percent
            return risk_amount

        except Exception as e:
            self.logger.error(f"❌ Error calculating position risk: {e}")
            return self.total_portfolio_value * self.max_single_position_risk  # Conservative fallback

    async def _calculate_recommended_position_size(self, opportunity: Dict) -> int:
        """Calculate recommended position size based on config and risk parameters"""
        try:
            current_price = opportunity.get('current_price', 0.0)
            strategy = opportunity.get('opportunity_type', '')
            quality_score = opportunity.get('quality_score', 50.0)

            # Base risk amount from config
            base_risk = self.total_portfolio_value * self.max_single_position_risk

            # Quality-based adjustment (if quality score is available)
            if quality_score > 0:
                quality_multiplier = min(quality_score / 75.0, 1.5)  # Max 1.5x for high quality
                adjusted_risk = base_risk * quality_multiplier
            else:
                adjusted_risk = base_risk

            # Strategy-specific stop loss from config
            strategy_config = self.strategy_params.get(strategy, {})
            stop_loss_percent = strategy_config.get('stop_loss_percent', 0.02)

            # Calculate shares
            if current_price > 0 and stop_loss_percent > 0:
                shares = int(adjusted_risk / (current_price * stop_loss_percent))
                # Apply config limits
                return max(self.min_position_size, min(shares, self.max_position_size))

            return self.min_position_size  # Fallback to minimum

        except Exception as e:
            self.logger.error(f"❌ Error calculating position size: {e}")
            return self.min_position_size

    async def update_position(self, symbol: str, position_data: Dict):
        """Update position tracking"""
        try:
            self.current_positions[symbol] = {
                'symbol': symbol,
                'strategy': position_data['strategy'],
                'entry_price': position_data['entry_price'],
                'quantity': position_data['quantity'],
                'risk_amount': position_data.get('risk_amount', 0.0),
                'timestamp': datetime.now()
            }

            # Update risk metrics
            await self._update_risk_metrics()

            self.logger.info(f"📊 Position updated: {symbol}")

        except Exception as e:
            self.logger.error(f"❌ Error updating position: {e}")

    async def close_position(self, symbol: str, close_price: float, reason: str):
        """Record position closure"""
        try:
            if symbol in self.current_positions:
                position = self.current_positions.pop(symbol)

                # Calculate P&L
                entry_price = position['entry_price']
                quantity = position['quantity']
                pnl = (close_price - entry_price) * quantity

                # Update daily P&L
                self.risk_metrics['daily_pnl'] += pnl

                # Update risk metrics
                await self._update_risk_metrics()

                self.logger.info(f"💰 Position closed: {symbol} - P&L: ${pnl:.2f} ({reason})")

                # Check if daily loss limit is approaching
                if self.risk_metrics['daily_pnl'] < self.max_daily_loss * 0.8:  # 80% of limit
                    self.logger.warning(f"⚠️ Daily loss approaching limit: ${self.risk_metrics['daily_pnl']:.2f}")

        except Exception as e:
            self.logger.error(f"❌ Error closing position: {e}")

    async def _update_risk_metrics(self):
        """Update current risk metrics"""
        try:
            # Calculate total risk amount
            total_risk = sum(pos.get('risk_amount', 0.0) for pos in self.current_positions.values())
            self.risk_metrics['total_risk_amount'] = total_risk

            # Strategy exposure
            strategy_exposure = {}
            for pos in self.current_positions.values():
                strategy = pos['strategy']
                risk = pos.get('risk_amount', 0.0)
                strategy_exposure[strategy] = strategy_exposure.get(strategy, 0.0) + risk

            self.risk_metrics['strategy_exposure'] = strategy_exposure

        except Exception as e:
            self.logger.error(f"❌ Error updating risk metrics: {e}")

    async def get_risk_utilization(self) -> Dict:
        """Get current risk utilization metrics"""
        try:
            max_risk = self.total_portfolio_value * self.max_portfolio_risk
            current_risk = self.risk_metrics['total_risk_amount']

            return {
                'portfolio_risk_used': current_risk,
                'portfolio_risk_available': max_risk - current_risk,
                'portfolio_risk_percentage': (current_risk / max_risk) * 100 if max_risk > 0 else 0,
                'active_positions': len(self.current_positions),
                'max_positions': self.max_positions,
                'daily_trades_used': self.daily_trade_count,
                'daily_trades_remaining': self.max_daily_trades - self.daily_trade_count,
                'daily_pnl': self.risk_metrics['daily_pnl'],
                'daily_loss_limit': self.max_daily_loss,
                'strategy_exposure': self.risk_metrics['strategy_exposure'],
                'position_sizing_method': self.position_sizing_method
            }

        except Exception as e:
            self.logger.error(f"❌ Error getting risk utilization: {e}")
            return {}

    async def _reset_daily_counters_if_needed(self):
        """Reset daily counters at start of new trading day"""
        now = datetime.now()

        if self.daily_reset_time is None or now.date() > self.daily_reset_time.date():
            self.daily_trade_count = 0
            self.risk_metrics['daily_pnl'] = 0.0
            self.daily_reset_time = now
            self.logger.info("🔄 Daily risk counters reset")

    async def _is_market_hours(self) -> bool:
        """Check if market is open based on config"""
        now = datetime.now()

        # Weekend check
        if now.weekday() >= 5:  # Weekend
            return False

        # Parse market hours from config
        try:
            open_time = datetime.strptime(self.market_open, '%H:%M').time()
            close_time = datetime.strptime(self.market_close, '%H:%M').time()

            current_time = now.time()
            return open_time <= current_time <= close_time

        except Exception as e:
            self.logger.error(f"❌ Error checking market hours: {e}")
            # Fallback to hardcoded hours
            return 9.5 <= now.hour + now.minute/60.0 <= 16.0

    async def _is_high_volatility_period(self) -> bool:
        """Check if current period has high volatility (reduce risk)"""
        # Could be enhanced to read volatility thresholds from config
        now = datetime.now()

        # First 30 minutes after open
        if now.hour == 9 and now.minute < 60:
            return True

        # Last 30 minutes before close
        if now.hour == 15 and now.minute >= 30:
            return True

        return False

    async def emergency_reduce_risk(self):
        """Emergency risk reduction - close riskiest positions"""
        try:
            self.logger.warning("🚨 Emergency risk reduction triggered")

            # Sort positions by risk amount (highest first)
            positions_by_risk = sorted(
                self.current_positions.items(),
                key=lambda x: x[1].get('risk_amount', 0.0),
                reverse=True
            )

            # Close top 50% of riskiest positions
            positions_to_close = positions_by_risk[:len(positions_by_risk)//2]

            for symbol, position in positions_to_close:
                self.logger.warning(f"🚨 Emergency closing: {symbol}")
                # This would trigger actual position closure
                await self.close_position(symbol, position['entry_price'], 'EMERGENCY_RISK_REDUCTION')

        except Exception as e:
            self.logger.error(f"❌ Error in emergency risk reduction: {e}")

    def get_risk_config_summary(self) -> Dict:
        """Get current risk configuration for monitoring/debugging"""
        return {
            'max_portfolio_risk': self.max_portfolio_risk,
            'max_single_position_risk': self.max_single_position_risk,
            'max_daily_trades': self.max_daily_trades,
            'max_positions': self.max_positions,
            'max_daily_loss': self.max_daily_loss,
            'portfolio_capital': self.total_portfolio_value,
            'position_sizing_method': self.position_sizing_method,
            'max_position_size': self.max_position_size,
            'min_position_size': self.min_position_size,
            'strategy_params': self.strategy_params
        }