# execution/risk_manager.py
"""
Risk Manager - Centralized risk management for Sistema_4
Validates trades against risk limits and portfolio constraints
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import Sistema4Database
from shared.config_reader import Sistema4Config

class RiskManager:
    """
    Centralized risk management for Sistema_4
    Enforces portfolio limits and trading constraints
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.RiskManager")

        # Load configuration
        self.config = Sistema4Config()
        self._load_risk_parameters()

        # Initialize components
        self.database = Sistema4Database()

        # Risk tracking
        self.daily_trade_count = 0
        self.daily_loss_amount = 0.0
        self.last_reset_date = datetime.now().date()

        self.logger.info("🛡️ Risk Manager initialized")
        self.logger.info(f"   💰 Portfolio: ${self.total_portfolio_value:,}")
        self.logger.info(f"   📊 Max risk per trade: {self.max_risk_per_trade_percent}%")
        self.logger.info(f"   🔄 Max daily trades: {self.max_daily_trades}")

    def _load_risk_parameters(self):
        """Load risk management parameters from config"""
        # Portfolio limits - using fallback values since config structure differs
        self.total_portfolio_value = 10000.0
        self.max_portfolio_risk_percent = 2.0
        self.max_position_size_percent = 5.0

        # Per-trade limits
        self.max_risk_per_trade_percent = 1.0
        self.max_trade_value = 1000.0

        # Daily limits
        self.max_daily_trades = 10
        self.max_daily_loss_percent = 3.0

        # Symbol limits
        self.max_symbols_per_strategy = 3
        self.max_total_symbols = 8

        # Price limits
        self.min_stock_price = 0.50
        self.max_stock_price = 50.0

    async def validate_trade(self, trade_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate trade request against all risk limits
        Returns approval status and reason
        """
        try:
            self._reset_daily_counters_if_needed()

            symbol = trade_request.get('symbol')
            action = trade_request.get('action')
            quantity = trade_request.get('quantity', 0)
            price = trade_request.get('limit_price') or trade_request.get('entry_price', 0.0)
            strategy = trade_request.get('strategy', 'UNKNOWN')
            stop_loss_price = trade_request.get('stop_loss_price', 0.0)

            # Calculate trade metrics
            trade_value = quantity * price
            risk_amount = abs((price - stop_loss_price) * quantity) if stop_loss_price else trade_value * 0.02

            # Validation checks
            checks = [
                self._check_daily_trade_limit(),
                self._check_daily_loss_limit(),
                self._check_trade_value_limit(trade_value),
                self._check_risk_per_trade_limit(risk_amount),
                self._check_position_size_limit(trade_value),
                self._check_price_limits(price),
                self._check_symbol_limits(strategy),
                self._check_portfolio_exposure()
            ]

            # Find first failed check
            for check in checks:
                if not check['approved']:
                    self.logger.warning(f"⛔ Risk check failed: {check['reason']}")
                    return check

            # All checks passed
            self.daily_trade_count += 1
            self.logger.info(f"✅ Trade approved: {symbol} risk ${risk_amount:.2f} ({self.daily_trade_count}/{self.max_daily_trades} today)")

            return {
                'approved': True,
                'reason': 'Trade approved by risk manager',
                'risk_amount': risk_amount,
                'trade_value': trade_value
            }

        except Exception as e:
            self.logger.error(f"❌ Risk validation error: {e}")
            return {'approved': False, 'reason': f'Risk validation error: {e}'}

    def _reset_daily_counters_if_needed(self):
        """Reset daily counters if new day"""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_trade_count = 0
            self.daily_loss_amount = 0.0
            self.last_reset_date = current_date
            self.logger.info("🔄 Daily risk counters reset")

    def _check_daily_trade_limit(self) -> Dict[str, Any]:
        """Check daily trade count limit"""
        if self.daily_trade_count >= self.max_daily_trades:
            return {
                'approved': False,
                'reason': f'Daily trade limit reached: {self.daily_trade_count}/{self.max_daily_trades}'
            }
        return {'approved': True, 'reason': 'Daily trade limit OK'}

    def _check_daily_loss_limit(self) -> Dict[str, Any]:
        """Check daily loss limit"""
        max_daily_loss = self.total_portfolio_value * (self.max_daily_loss_percent / 100)
        if self.daily_loss_amount >= max_daily_loss:
            return {
                'approved': False,
                'reason': f'Daily loss limit reached: ${self.daily_loss_amount:.2f}/${max_daily_loss:.2f}'
            }
        return {'approved': True, 'reason': 'Daily loss limit OK'}

    def _check_trade_value_limit(self, trade_value: float) -> Dict[str, Any]:
        """Check individual trade value limit"""
        if trade_value > self.max_trade_value:
            return {
                'approved': False,
                'reason': f'Trade value too large: ${trade_value:.2f} > ${self.max_trade_value:.2f}'
            }
        return {'approved': True, 'reason': 'Trade value limit OK'}

    def _check_risk_per_trade_limit(self, risk_amount: float) -> Dict[str, Any]:
        """Check risk per trade limit"""
        max_risk_amount = self.total_portfolio_value * (self.max_risk_per_trade_percent / 100)
        if risk_amount > max_risk_amount:
            return {
                'approved': False,
                'reason': f'Risk per trade too high: ${risk_amount:.2f} > ${max_risk_amount:.2f}'
            }
        return {'approved': True, 'reason': 'Risk per trade limit OK'}

    def _check_position_size_limit(self, trade_value: float) -> Dict[str, Any]:
        """Check position size as percentage of portfolio"""
        max_position_value = self.total_portfolio_value * (self.max_position_size_percent / 100)
        if trade_value > max_position_value:
            return {
                'approved': False,
                'reason': f'Position size too large: ${trade_value:.2f} > ${max_position_value:.2f} ({self.max_position_size_percent}%)'
            }
        return {'approved': True, 'reason': 'Position size limit OK'}

    def _check_price_limits(self, price: float) -> Dict[str, Any]:
        """Check stock price limits"""
        if price < self.min_stock_price:
            return {
                'approved': False,
                'reason': f'Stock price too low: ${price:.2f} < ${self.min_stock_price:.2f}'
            }
        if price > self.max_stock_price:
            return {
                'approved': False,
                'reason': f'Stock price too high: ${price:.2f} > ${self.max_stock_price:.2f}'
            }
        return {'approved': True, 'reason': 'Price limits OK'}

    def _check_symbol_limits(self, strategy: str) -> Dict[str, Any]:
        """Check symbol concentration limits"""
        try:
            active_positions = self.database.get_active_positions()

            # Count positions by strategy
            strategy_count = sum(1 for pos in active_positions if strategy in pos.owner)
            if strategy_count >= self.max_symbols_per_strategy:
                return {
                    'approved': False,
                    'reason': f'Max symbols for {strategy}: {strategy_count}/{self.max_symbols_per_strategy}'
                }

            # Check total symbols
            if len(active_positions) >= self.max_total_symbols:
                return {
                    'approved': False,
                    'reason': f'Max total symbols reached: {len(active_positions)}/{self.max_total_symbols}'
                }

            return {'approved': True, 'reason': 'Symbol limits OK'}

        except Exception as e:
            return {'approved': False, 'reason': f'Symbol limit check error: {e}'}

    def _check_portfolio_exposure(self) -> Dict[str, Any]:
        """Check overall portfolio exposure"""
        try:
            active_positions = self.database.get_active_positions()

            # Calculate total exposure
            total_exposure = sum(pos.quantity * pos.entry_price for pos in active_positions)
            exposure_percent = (total_exposure / self.total_portfolio_value) * 100

            max_exposure_percent = 80.0  # Don't use more than 80% of portfolio
            if exposure_percent > max_exposure_percent:
                return {
                    'approved': False,
                    'reason': f'Portfolio exposure too high: {exposure_percent:.1f}% > {max_exposure_percent}%'
                }

            return {'approved': True, 'reason': 'Portfolio exposure OK'}

        except Exception as e:
            return {'approved': False, 'reason': f'Portfolio exposure check error: {e}'}

    async def get_current_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics"""
        try:
            self._reset_daily_counters_if_needed()
            active_positions = self.database.get_active_positions()

            # Calculate portfolio metrics
            total_exposure = sum(pos.quantity * pos.entry_price for pos in active_positions)
            exposure_percent = (total_exposure / self.total_portfolio_value) * 100

            # Calculate daily limits remaining
            daily_trades_remaining = self.max_daily_trades - self.daily_trade_count
            max_daily_loss = self.total_portfolio_value * (self.max_daily_loss_percent / 100)
            daily_loss_remaining = max_daily_loss - self.daily_loss_amount

            metrics = {
                'portfolio_value': self.total_portfolio_value,
                'total_exposure': total_exposure,
                'exposure_percent': exposure_percent,
                'active_positions': len(active_positions),
                'daily_trades_used': self.daily_trade_count,
                'daily_trades_remaining': daily_trades_remaining,
                'daily_loss_amount': self.daily_loss_amount,
                'daily_loss_remaining': daily_loss_remaining,
                'max_position_value': self.total_portfolio_value * (self.max_position_size_percent / 100),
                'max_risk_per_trade': self.total_portfolio_value * (self.max_risk_per_trade_percent / 100)
            }

            return metrics

        except Exception as e:
            self.logger.error(f"Error calculating risk metrics: {e}")
            return {}

    def record_trade_loss(self, loss_amount: float):
        """Record a trade loss for daily tracking"""
        if loss_amount > 0:
            self.daily_loss_amount += loss_amount
            self.logger.info(f"💸 Trade loss recorded: ${loss_amount:.2f} (total today: ${self.daily_loss_amount:.2f})")

    def get_risk_summary(self) -> str:
        """Get formatted risk summary"""
        try:
            import asyncio
            metrics = asyncio.run(self.get_current_metrics())

            summary = f"""
🛡️ RISK MANAGER SUMMARY
Portfolio: ${metrics['portfolio_value']:,.2f}
Exposure: ${metrics['total_exposure']:,.2f} ({metrics['exposure_percent']:.1f}%)
Active Positions: {metrics['active_positions']}/{self.max_total_symbols}
Daily Trades: {metrics['daily_trades_used']}/{self.max_daily_trades}
Daily Loss: ${metrics['daily_loss_amount']:.2f}/${metrics['daily_loss_remaining']:.2f}
"""
            return summary.strip()

        except Exception as e:
            return f"Error generating risk summary: {e}"