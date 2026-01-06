# core/risk_manager.py
"""
Risk management system for trading engine.
"""

import logging
import math
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

from .interfaces import IRiskManager, Signal, Order, Position, TradingConfig, SignalType


class RiskManager(IRiskManager):
    """Comprehensive risk management system with detailed logging"""
    """
    Comprehensive risk management system.
    
    Validates signals and orders against multiple risk criteria:
    - Position sizing limits
    - Portfolio exposure limits
    - Daily loss limits
    - Correlation limits
    - Volatility limits
    """
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger("RiskManager")
        
        # Track daily statistics
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.daily_reset_time = datetime.now().date()
        
        # Track trades per symbol for per-symbol limits
        self.symbol_daily_trades: Dict[str, int] = {}
        
        # Track rejected signals/orders for analysis
        self.rejected_signals = []
        self.rejected_orders = []
        
        # Position tracking
        self.positions: Dict[str, Position] = {}
        self.last_position_update = datetime.min
        
        # Track broker positions for max_positions validation
        self.broker_positions: Dict[str, any] = {}
        
        # Simulation mode (ignora restricciones de horario y antigüedad de señales)
        self.simulation_mode = getattr(config, 'simulation_mode', False)
        
        # Debug mode (hace que todas las comprobaciones de riesgo sean extremadamente permisivas)
        self.debug_mode = getattr(config, 'debug_mode', False)  # Desactivado por defecto para aplicar restricciones
        
        # Log initial state
        self.logger.info(
            "RiskManager initialized | simulation_mode=%s | debug_mode=%s | max_daily_trades=%s | max_daily_loss=%s | max_position_value=%s",
            self.simulation_mode,
            self.debug_mode,
            self.config.max_daily_trades,
            self.config.max_daily_loss,
            getattr(self.config, 'max_position_value', 'Not set')
        )
    
    async def validate_signal(self, signal: Signal) -> bool:
        """Validate if signal meets risk criteria"""
        try:
            self._reset_daily_stats_if_needed()
            
            # DEBUG: Log signal validation entry
            self.logger.info(f"🔍 SIGNAL VALIDATION: {signal.symbol} {signal.signal_type.value} | Current positions: {list(self.broker_positions.keys())}")
            
            # CRITICAL FIX: Don't check position limits for EXIT signals 
            # Exit signals should ALWAYS be allowed to close positions
            check_position_limit = signal.signal_type not in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]
            
            validations = [
                self._check_daily_trade_limit(),
                self._check_daily_loss_limit(),
                self._check_signal_quality(signal),
                self._check_symbol_exposure_limit(signal.symbol),
                self._check_symbol_trade_limit(signal.symbol),
                self._check_max_positions_limit(signal.symbol) if check_position_limit else True,  # Skip for exits
                await self._check_market_conditions()
            ]
            
            # Detailed log per-check
            validation_results = {
                'daily_trade_limit': validations[0],
                'daily_loss_limit': validations[1], 
                'signal_quality': validations[2],
                'symbol_exposure': validations[3],
                'symbol_trade_limit': validations[4],
                'max_positions_limit': validations[5],  # CRITICAL: Add max positions check
                'market_conditions': validations[6]
            }
            
            is_valid = all(validations)
            # Log validation results
            self._log_validation_results("SIGNAL", validation_results, is_valid, extra=f"{signal.symbol}-{signal.signal_type.value}")
            
            if not is_valid:
                failed_checks = [k for k, v in validation_results.items() if not v]
                self.logger.warning(
                    f"Signal rejected for {signal.symbol}: {signal.signal_type.value} "
                    f"Failed checks: {failed_checks}"
                )
                
                self.rejected_signals.append({
                    'signal': signal,
                    'timestamp': datetime.now(),
                    'failed_checks': failed_checks
                })
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Error validating signal: {e}")
            return False
    
    def _get_current_position_value(self, symbol: str) -> float:
        """Get current position value for a symbol
        
        Args:
            symbol: The symbol to get position value for
            
        Returns:
            float: Current position value in account currency, or 0 if no position
        """
        if symbol in self.positions:
            position = self.positions[symbol]
            return abs(position.quantity * position.market_price)
        return 0.0
    
    def _get_total_portfolio_value(self) -> float:
        """Get total portfolio value in account currency
        
        Returns:
            float: Total portfolio value
        """
        # This is a placeholder - in a real implementation, this would come from the broker/account
        # For now, we'll sum up all position values
        total = 0.0
        for position in self.positions.values():
            total += abs(position.quantity * position.market_price)
        return total
    
    def _check_position_value_limit(self, symbol: str, order_quantity: float, price: float) -> bool:
        """Check if order would exceed max_position_value
        
        Args:
            symbol: Symbol being traded
            order_quantity: Quantity in the order (positive for buy, negative for sell)
            price: Price of the instrument
            
        Returns:
            bool: True if within limits, False if would exceed max_position_value
        """
        if not hasattr(self.config, 'max_position_value'):
            return True  # No limit set
            
        # Handle None price (market orders)
        if price is None:
            self.logger.warning(f"Price is None for {symbol}, skipping position value limit check")
            return True  # Skip check if price is not available
            
        current_value = self._get_current_position_value(symbol)
        order_value = abs(order_quantity * price)
        
        # Para órdenes de compra, verificar si la posición existente + nueva orden excedería el límite
        if order_quantity > 0:
            resulting_position_value = current_value + order_value
            if resulting_position_value > self.config.max_position_value:
                self.logger.warning(
                    "Order would exceed max_position_value: %.2f + %.2f = %.2f > %.2f (limit) for %s",
                    current_value, order_value, resulting_position_value, self.config.max_position_value, symbol
                )
                return False
            
            # Log información detallada sobre la posición acumulada para facilitar depuración
            self.logger.info(
                "Position value check passed: %.2f + %.2f = %.2f <= %.2f (limit) for %s",
                current_value, order_value, resulting_position_value, self.config.max_position_value, symbol
            )
            
        return True
    
    def update_positions(self, positions: Dict[str, Position]):
        """Update internal position tracking
        
        Args:
            positions: Dictionary of symbol -> Position
        """
        self.positions = positions
        self.last_position_update = datetime.now()
    
    async def validate_order(self, order: Order) -> bool:
        """Validate if order meets risk criteria"""
        return await self.validate_order_with_signal_context(order, is_exit_order=False)
    
    async def validate_order_with_signal_context(self, order: Order, is_exit_order: bool = False) -> bool:
        """Validate if order meets risk criteria with knowledge of whether it's an exit order"""
        try:
            # Log whether this is an exit order for debugging
            self.logger.info(f"🔍 Validating order for {order.symbol}: {order.side.value} {order.quantity} | is_exit_order={is_exit_order}")
            
            # Get current price for validation
            current_price = order.price  # Use order price as fallback
            
            # Additional validations for position limits
            # CRITICAL FIX: Skip max_positions_limit check for exit orders
            check_position_limit = not is_exit_order
            
            validations = [
                self._check_order_size(order),
                self._check_order_value(order),
                self._check_position_concentration(order),
                self._check_portfolio_risk(order) if not is_exit_order else True,  # Skip portfolio risk for exits
                self._check_order_timing(order),
                self._check_position_value_limit(order.symbol, order.quantity, current_price) if not is_exit_order else True,  # Skip for exit orders
                self._check_max_positions_limit(order.symbol) if check_position_limit else True  # Skip for exit orders
            ]
            
            # Detailed log per-check
            validation_results = {
                'order_size': validations[0],
                'order_value': validations[1],
                'position_concentration': validations[2],
                'portfolio_risk': validations[3],
                'order_timing': validations[4],
                'position_value_limit': validations[5],
                'max_positions_limit': validations[6]  # CRITICAL: Add max positions check for orders too
            }
            
            is_valid = all(validations)
            # Log validation results
            self._log_validation_results("ORDER", validation_results, is_valid, extra=f"{order.symbol}-{order.side.value}")
            
            if not is_valid:
                failed_checks = [k for k, v in validation_results.items() if not v]
                self.logger.warning(
                    f"Order rejected for {order.symbol}: {order.side.value} {order.quantity} "
                    f"Failed checks: {failed_checks}"
                )
                
                self.rejected_orders.append({
                    'order': order,
                    'timestamp': datetime.now(),
                    'failed_checks': failed_checks
                })
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Error validating order: {e}")
            return False
    
    async def check_portfolio_risk(self, positions: Dict[str, Position]) -> bool:
        """Check overall portfolio risk metrics"""
        try:
            validations = [
                self._check_portfolio_concentration(positions),
                self._check_portfolio_correlation(positions),
                self._check_portfolio_exposure(positions),
                self._check_portfolio_volatility(positions)
            ]
            
            return all(validations)
            
        except Exception as e:
            self.logger.error(f"Error checking portfolio risk: {e}")
            return False
            
    def _check_portfolio_risk(self, order: Order) -> bool:
        """Check if order would create excessive portfolio risk
        
        This method is called during order validation and checks if adding
        the order would create excessive portfolio risk.
        
        Args:
            order: Order to validate
            
        Returns:
            bool: True if portfolio risk is acceptable, False otherwise
        """
        # En modo debug, siempre permitir órdenes sin importar el riesgo del portfolio
        if self.debug_mode:
            self.logger.info(f"Portfolio risk check bypassed for {order.symbol} (debug mode)")
            return True
            
        try:
            # Create a copy of current positions
            positions_copy = self.positions.copy()
            
            # Simulate adding the new order to positions
            symbol = order.symbol
            price = order.price or 0
            
            # If we already have a position for this symbol, update it
            if symbol in positions_copy:
                position = positions_copy[symbol]
                new_quantity = position.quantity + order.quantity
                
                # If new quantity would be zero, remove the position
                if new_quantity == 0:
                    del positions_copy[symbol]
                else:
                    # Update the position with new quantity
                    position.quantity = new_quantity
                    position.market_value = new_quantity * price
            # Otherwise create a new position
            elif order.quantity != 0:
                from core.interfaces import Position
                positions_copy[symbol] = Position(
                    symbol=symbol,
                    quantity=order.quantity,
                    avg_price=price,
                    market_price=price,
                    market_value=order.quantity * price,
                    unrealized_pnl=0.0,
                    entry_time=datetime.now()
                )
            
            # Check portfolio concentration
            if not self._check_portfolio_concentration(positions_copy):
                self.logger.warning(f"Order would create excessive portfolio concentration for {symbol}")
                return False
                
            # Check portfolio exposure
            if not self._check_portfolio_exposure(positions_copy):
                self.logger.warning(f"Order would create excessive portfolio exposure for {symbol}")
                return False
                
            # Check portfolio volatility
            if not self._check_portfolio_volatility(positions_copy):
                self.logger.warning(f"Order would create excessive portfolio volatility for {symbol}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking portfolio risk for order: {e}")
            return False
    
    def _reset_daily_stats_if_needed(self):
        """Reset daily statistics if new day
        Also reset per-symbol trade counters and active daily plays"""
        current_date = datetime.now().date()
        if current_date > self.daily_reset_time:
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.daily_reset_time = current_date
            self.symbol_daily_trades.clear()
            
            # CRITICAL FIX: Clear active daily plays from previous day
            if hasattr(self, 'active_daily_plays'):
                previous_plays = list(self.active_daily_plays.keys())
                self.active_daily_plays.clear()
                if previous_plays:
                    self.logger.info(f"🔄 Cleared {len(previous_plays)} active daily plays from previous day: {', '.join(previous_plays)}")
            
            self.logger.info("Daily risk statistics reset - ready for new trading day")
    
    def _check_daily_trade_limit(self) -> bool:
        """Check if daily trade limit is exceeded"""
        return self.daily_trades < self.config.max_daily_trades
    
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit is exceeded"""
        return self.daily_pnl > self.config.max_daily_loss
    
    def _check_signal_quality(self, signal: Signal) -> bool:
        """Check signal quality metrics"""
        # Minimum signal strength
        min_strength = getattr(self.config, 'min_signal_strength', 0.3)
        if signal.strength < min_strength:
            return False
        
        # Check for reasonable price
        if signal.price <= 0:
            return False
        
        try:
            # Check signal age (signals shouldn't be too old)
            now = datetime.now(signal.timestamp.tzinfo) if signal.timestamp.tzinfo else datetime.now()
            signal_age = now - signal.timestamp
            max_age = timedelta(minutes=10)  # 10 minutes max (increased due to processing delays)
            
            # En modo simulación, ignoramos la antigüedad de la señal
            if signal_age > max_age and not self.simulation_mode:
                self.logger.warning(f"Signal too old: {signal_age} > {max_age}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking signal age: {e}")
            return False
    
    def _check_symbol_exposure_limit(self, symbol: str) -> bool:
        """Check if we already have too much exposure to this symbol"""
        # This would check existing positions for the symbol
        # For now, simple check - could be enhanced with actual position data
        max_symbol_exposure = getattr(self.config, 'max_symbol_exposure', 0.1)  # 10% max per symbol
        
        # Would need access to current positions to implement fully
        return True
    
    async def _check_market_conditions(self) -> bool:
        """Check if market conditions are suitable for trading"""
        try:
            # Si estamos en modo simulación, siempre permitimos operar
            if self.simulation_mode:
                return True
                
            # Get current time in market timezone (US/Eastern)
            from zoneinfo import ZoneInfo
            import pytz
            
            # Get current time in US/Eastern timezone
            ny_tz = ZoneInfo('US/Eastern')
            now = datetime.now(ny_tz)
            
            # Skip weekend checks
            if now.weekday() >= 5:  # 5=Saturday, 6=Sunday
                self.logger.info(f"Market closed: Weekend ({now.strftime('%A')})")
                return False
                
            # Get market hours from config or use defaults (9:30 AM - 4:00 PM ET)
            market_open = getattr(self.config, 'market_open_time', '09:30')
            market_close = getattr(self.config, 'market_close_time', '16:00')
            
            # Parse market hours
            open_hour, open_minute = map(int, market_open.split(':'))
            close_hour, close_minute = map(int, market_close.split(':'))
            
            # Create time objects with timezone
            market_open_time = now.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
            market_close_time = now.replace(hour=close_hour, minute=close_minute, second=0, microsecond=0)
            
            # Check if current time is within market hours
            if not (market_open_time <= now <= market_close_time):
                self.logger.info(f"Market closed: Current time {now.strftime('%H:%M:%S %Z')} "
                              f"is outside market hours {market_open}-{market_close} ET")
                return False
            
            # Additional market condition checks can be added here
            # (e.g., market volatility, news events, etc.)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking market conditions: {e}")
            # In case of error, be conservative and don't allow trading
            return False
    
    def _check_symbol_trade_limit(self, symbol: str) -> bool:
        """Ensure we don't exceed max trades per symbol per day"""
        max_trades_symbol = getattr(self.config, 'max_trades_per_symbol', 5)
        return self.symbol_daily_trades.get(symbol, 0) < max_trades_symbol

    def _record_symbol_trade(self, symbol: str, count: int = 1):
        """Increment trade count for symbol after order execution (call externally)"""
        self.symbol_daily_trades[symbol] = self.symbol_daily_trades.get(symbol, 0) + count
    
    def update_broker_positions(self, positions: Dict[str, any]) -> None:
        """
        Update broker positions for risk management validation
        
        CRITICAL: This method should be called regularly to ensure
        max_positions validation uses current broker positions.
        
        Args:
            positions: Dict of symbol -> position_data from broker
        """
        try:
            self.broker_positions = positions or {}
            self.last_position_update = datetime.now()
            
            position_count = len(self.broker_positions)
            self.logger.debug(f"📊 Updated broker positions: {position_count} positions - {list(self.broker_positions.keys())}")
            
        except Exception as e:
            self.logger.error(f"Error updating broker positions: {e}")
            self.broker_positions = {}
    
    async def sync_broker_positions(self) -> None:
        """
        Helper method to fetch positions from broker and update internal state.
        This solves the issue where update_broker_positions() was called without arguments.
        """
        try:
            if hasattr(self, 'broker_adapter') and self.broker_adapter:
                if hasattr(self.broker_adapter, 'get_positions'):
                    positions = await self.broker_adapter.get_positions()
                    self.update_broker_positions(positions)
                    self.logger.debug(f"🔄 Synced {len(positions)} positions from broker")
                else:
                    self.logger.debug("📊 Broker adapter doesn't support get_positions")
            else:
                self.logger.debug("📊 No broker adapter available for position sync")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not sync positions from broker: {e}")
            # Fallback to empty positions to avoid stale data
            self.update_broker_positions({})
    
    def _check_max_positions_limit(self, symbol: str) -> bool:
        """
        ENHANCED: Check position limits with granular control
        
        Implements two-tier position control:
        1. max_positions: Maximum number of different tickers
        2. max_positions_per_symbol: Maximum positions per individual ticker
        
        Args:
            symbol: Symbol for which we want to open a position
            
        Returns:
            bool: True if we can open a new position, False if limits exceeded
        """
        try:
            # Get limits from config with safe defaults
            max_different_tickers = getattr(self.config, 'max_positions', 1)
            max_per_symbol = getattr(self.config, 'max_positions_per_symbol', 1)
            
            # Count current positions
            current_different_tickers = len(self.broker_positions)
            has_existing_position = symbol in self.broker_positions
            
            # CHECK 1: Per-symbol limit (if symbol already has a position)
            if has_existing_position:
                current_symbol_positions = 1  # Currently we track one position per symbol
                
                # CRITICAL FIX: With max_positions_per_symbol=1, reject new BUY orders if position exists
                if current_symbol_positions >= max_per_symbol:
                    self.logger.warning(
                        f"🚫 SYMBOL POSITION LIMIT EXCEEDED: Cannot open additional {symbol} position. "
                        f"Current {symbol} positions: {current_symbol_positions}/{max_per_symbol}. "
                        f"Only EXIT orders allowed for existing positions."
                    )
                    return False
                else:
                    # This branch should never execute with max_per_symbol=1 since 1 >= 1 is always True
                    self.logger.info(f"✅ {symbol} per-symbol limit check passed: {current_symbol_positions + 1}/{max_per_symbol}")
                    return True
            
            # CHECK 2: Different tickers limit (for new ticker)
            if current_different_tickers >= max_different_tickers:
                self.logger.warning(
                    f"🚫 MAX TICKERS EXCEEDED: Cannot open {symbol} position (new ticker). "
                    f"Current different tickers: {current_different_tickers}/{max_different_tickers}. "
                    f"Open tickers: {list(self.broker_positions.keys())}"
                )
                return False
            
            # We can open the new ticker position
            self.logger.info(
                f"✅ Position limits check passed for {symbol} (new ticker): "
                f"Tickers: {current_different_tickers + 1}/{max_different_tickers}, "
                f"Per-symbol: 1/{max_per_symbol}"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking position limits for {symbol}: {e}")
            # Err on the side of caution - reject if we can't validate
            return False

    def _check_order_size(self, order: Order) -> bool:
        """Check if order size is within limits"""
        min_order_size = getattr(self.config, 'min_order_size', 1)
        max_order_size = getattr(self.config, 'max_order_size', 10000)
        
        return min_order_size <= order.quantity <= max_order_size
    
    def _check_order_value(self, order: Order) -> bool:
        """Check if order value is within limits
        
        Args:
            order: Order to validate
            
        Returns:
            bool: True if order value is within limits, False otherwise
        """
        if not hasattr(self.config, 'max_order_value'):
            return True  # No order value limit set
            
        order_value = abs(order.quantity * (order.price or 0))
        
        if order_value > self.config.max_order_value:
            self.logger.warning(
                "Order value exceeds limit: %.2f > %.2f",
                order_value, self.config.max_order_value
            )
            return False
            
        return True  # Market orders - we'll check position value after execution
        
    def _check_position_concentration(self, order: Order) -> bool:
        """Check if order would make position too concentrated
        
        Args:
            order: Order to validate
            
        Returns:
            bool: True if position concentration is within limits, False otherwise
        """
        if not hasattr(self.config, 'max_position_concentration'):
            return True  # No concentration limit set
            
        symbol = order.symbol
        current_value = self._get_current_position_value(symbol)
        order_value = abs(order.quantity * (order.price or 0))
        
        # For buy orders, calculate new position value
        if order.quantity > 0:
            new_position_value = current_value + order_value
        # For sell orders, calculate remaining position value
        else:
            new_position_value = max(0, current_value - order_value)
        
        # Get total portfolio value
        total_value = self._get_total_portfolio_value()
        
        # If portfolio is empty, check if this would be the first position
        if total_value <= 0:
            # For empty portfolio, check if position value exceeds max_position_value
            max_position_value = getattr(self.config, 'max_position_value', 1000.0)
            if new_position_value > max_position_value:
                self.logger.warning(
                    f"Position value {new_position_value:.2f} would exceed max_position_value {max_position_value:.2f} for {symbol}"
                )
                return False
            # For empty portfolio, concentration check is not applicable
            return True
            
        # Calculate new concentration
        concentration = (new_position_value / total_value) * 100
        
        if concentration > self.config.max_position_concentration:
            self.logger.warning(
                "Portfolio concentration %.1f%% exceeds max %.1f%% for %s",
                concentration, self.config.max_position_concentration, symbol
            )
            return False
            
        # Check against max position value
        max_position_value = getattr(self.config, 'max_position_value', 1000.0)
        if new_position_value > max_position_value:
            self.logger.warning(
                f"Position value {new_position_value:.2f} would exceed max_position_value {max_position_value:.2f} for {order.symbol}"
            )
            return False
            
        return True
    
    def _check_order_timing(self, order: Order) -> bool:
        """Check if order timing is appropriate"""
        # Check if too many orders in short period
        order_age = datetime.now() - order.timestamp
        max_order_age = timedelta(minutes=1)
        
        return order_age <= max_order_age
    
    def _check_portfolio_concentration(self, positions: Dict[str, Position]) -> bool:
        """Check portfolio concentration risk and max position value"""
        if not positions:
            self.logger.debug("No positions to check for concentration")
            return True
        
        # Log all positions for debugging
        self.logger.debug("Current positions for concentration check:")
        for symbol, pos in positions.items():
            self.logger.debug(f"  - {symbol}: {pos.quantity} @ {getattr(pos, 'market_price', 'N/A')} = {getattr(pos, 'market_value', 'N/A')}")
        
        total_value = sum(abs(pos.market_value) if hasattr(pos, 'market_value') else 0 for pos in positions.values())
        self.logger.debug(f"Total portfolio value for concentration check: {total_value:.2f}")
        
        if total_value == 0:
            self.logger.debug("Total portfolio value is zero, skipping concentration check")
            return True
        
        max_concentration = getattr(self.config, 'max_portfolio_concentration', 0.8)
        max_position_value = getattr(self.config, 'max_position_value', 1000.0)
        
        self.logger.debug(f"Max concentration: {max_concentration:.1%}, Max position value: {max_position_value:.2f}")
        
        # If we only have one position, concentration check is different
        if len(positions) == 1:
            position = list(positions.values())[0]
            position_value = abs(position.market_value) if hasattr(position, 'market_value') else 0
            
            # For single position, only check max position value, not concentration
            if position_value > max_position_value:
                self.logger.warning(
                    f"Position value {position_value:.2f} exceeds "
                    f"max_position_value {max_position_value:.2f} for {position.symbol}"
                )
                return False
            
            self.logger.debug(f"Single position check passed: {position.symbol} value={position_value:.2f} <= {max_position_value:.2f}")
            return True
        
        # For multiple positions, check concentration
        for position in positions.values():
            if not hasattr(position, 'market_value') or position.market_value is None:
                self.logger.warning(f"Position {getattr(position, 'symbol', 'unknown')} has no market_value")
                continue
                
            position_value = abs(position.market_value)
            
            # Check position value against max_position_value
            if position_value > max_position_value:
                self.logger.warning(
                    f"Position value {position_value:.2f} exceeds "
                    f"max_position_value {max_position_value:.2f} for {position.symbol}"
                )
                return False
                
            # Check concentration
            concentration = position_value / total_value
            self.logger.debug(f"  - {position.symbol}: value={position_value:.2f}, concentration={concentration:.1%}")
            
            if concentration > max_concentration:
                self.logger.warning(
                    f"Portfolio concentration {concentration:.1%} exceeds "
                    f"max {max_concentration:.1%} for {position.symbol}"
                )
                return False
        
        self.logger.debug("Portfolio concentration check passed")
        return True
    
    def _check_portfolio_correlation(self, positions: Dict[str, Position]) -> bool:
        """Check portfolio correlation risk"""
        # This would require historical correlation data
        # For now, simple sector/industry concentration check could be implemented
        return True
    
    def _get_current_position_value(self, symbol: str) -> float:
        """Get current position value for a symbol"""
        # This should be implemented to get the current position value from your position manager
        # For now, return 0 - you'll need to implement this based on your position tracking
        return 0.0
        
        
    def _check_portfolio_exposure(self, positions: Dict[str, Position]) -> bool:
        """Check total portfolio exposure and max position values"""
        total_long_exposure = sum(pos.market_value for pos in positions.values() if pos.quantity > 0)
        total_short_exposure = sum(abs(pos.market_value) for pos in positions.values() if pos.quantity < 0)
        
        max_exposure = getattr(self.config, 'max_portfolio_exposure', 1200.0)  # From config
        max_position_value = getattr(self.config, 'max_position_value', 1000.0)
        
        # Check max exposure
        if total_long_exposure > max_exposure:
            self.logger.warning(f"Long exposure ${total_long_exposure:,.2f} exceeds max ${max_exposure:,.2f}")
            return False
            
        if total_short_exposure > max_exposure:
            self.logger.warning(f"Short exposure ${total_short_exposure:,.2f} exceeds max ${max_exposure:,.2f}")
            return False
        
        # Check individual position values
        for symbol, position in positions.items():
            pos_value = abs(position.market_value)
            if pos_value > max_position_value:
                self.logger.warning(
                    f"Position value ${pos_value:,.2f} for {symbol} exceeds "
                    f"max_position_value ${max_position_value:,.2f}"
                )
                return False
        
        # Only log periodically to reduce noise
        if not hasattr(self, '_exposure_log_counter'):
            self._exposure_log_counter = 0
        self._exposure_log_counter += 1
        if self._exposure_log_counter % 20 == 0:  # Log every 20 checks (~1 minute)
            self.logger.debug("Portfolio exposure check passed")
        return True
    
    def _check_portfolio_volatility(self, positions: Dict[str, Position]) -> bool:
        """Check portfolio volatility risk based on individual position volatilities
        and estimated correlations between positions.
        
        Args:
            positions: Dictionary of current positions keyed by symbol
            
        Returns:
            bool: True if portfolio volatility is within acceptable limits, False otherwise
        """
        # En modo debug, siempre permitir operaciones sin importar la volatilidad
        if self.debug_mode:
            self.logger.info("Portfolio volatility check bypassed (debug mode)")
            return True
            
        if not positions:
            # Only log periodically to reduce noise
            if not hasattr(self, '_volatility_log_counter'):
                self._volatility_log_counter = 0
            self._volatility_log_counter += 1
            if self._volatility_log_counter % 20 == 0:  # Log every 20 checks (~1 minute)
                self.logger.debug("Portfolio volatility check passed (no positions)")
            return True
            
        try:
            # 1. Calculate weighted volatility contribution of each position
            total_position_value = sum(pos.market_value for pos in positions.values())
            if total_position_value <= 0:
                self.logger.info("Portfolio volatility check passed (no market value)")
                return True
                
            # Get position volatilities (using ATR as proxy if available)
            position_weights = {}
            position_volatilities = {}
            
            for symbol, position in positions.items():
                # Calculate position weight
                weight = position.market_value / total_position_value
                position_weights[symbol] = weight
                
                # Use ATR as volatility proxy if available, otherwise use a default
                # based on asset class or a fixed percentage
                atr = getattr(position, 'metadata', {}).get('atr', None)
                price = position.avg_price
                
                if atr is not None and price > 0:
                    # Normalize ATR as percentage of price
                    volatility = atr / price
                else:
                    # Default volatility estimate based on asset class
                    if symbol.endswith('BTC') or symbol.endswith('ETH'):
                        volatility = 0.05  # 5% daily volatility for crypto
                    elif len(symbol) > 5:  # Crude check for forex pairs
                        volatility = 0.01  # 1% daily volatility for forex
                    else:
                        # Check if it's likely a smallcap based on price or other metadata
                        price = position.market_price
                        is_smallcap = price < 20.0 or 'smallcap' in getattr(position, 'metadata', {}).get('tags', [])
                        
                        if is_smallcap:
                            volatility = 0.06  # 6% daily volatility for smallcaps
                        else:
                            volatility = 0.02  # 2% daily volatility for regular stocks
                        
                position_volatilities[symbol] = volatility
            
            # 2. Estimate portfolio volatility using a simplified approach
            # Assuming average correlation of 0.5 between positions
            avg_correlation = 0.5
            
            # Calculate weighted sum of individual volatilities
            weighted_vol_sum = sum(weight * vol for symbol, (weight, vol) in 
                              [(s, (position_weights[s], position_volatilities[s])) for s in positions])
            
            # Calculate weighted sum of volatility cross-terms
            cross_term_sum = 0
            symbols = list(positions.keys())
            
            for i in range(len(symbols)):
                for j in range(i+1, len(symbols)):
                    sym_i, sym_j = symbols[i], symbols[j]
                    weight_i, weight_j = position_weights[sym_i], position_weights[sym_j]
                    vol_i, vol_j = position_volatilities[sym_i], position_volatilities[sym_j]
                    
                    # Use average correlation as estimate
                    cross_term_sum += 2 * weight_i * weight_j * vol_i * vol_j * avg_correlation
            
            # Portfolio variance formula: sum of weighted individual variances + sum of weighted covariances
            portfolio_variance = sum((position_weights[s] * position_volatilities[s])**2 for s in positions) + cross_term_sum
            portfolio_volatility = math.sqrt(portfolio_variance)
            
            # 3. Check against maximum allowable portfolio volatility
            max_portfolio_volatility = getattr(self.config, 'max_portfolio_volatility', 0.5)  # Default 50%
            is_within_limits = portfolio_volatility <= max_portfolio_volatility
            
            if is_within_limits:
                self.logger.info(f"Portfolio volatility check passed: {portfolio_volatility:.2%} (max: {max_portfolio_volatility:.2%})")
            else:
                self.logger.warning(f"Portfolio volatility check FAILED: {portfolio_volatility:.2%} exceeds maximum {max_portfolio_volatility:.2%}")
                
            return is_within_limits
            
        except Exception as e:
            self.logger.error(f"Error in portfolio volatility calculation: {e}")
            # Default to conservative approach - fail the check if we can't calculate it
            return False
    
    def update_daily_stats(self, pnl_change: float = 0.0, trade_count: int = 0):
        """Update daily statistics"""
        self.daily_pnl += pnl_change
        self.daily_trades += trade_count
    
    def get_risk_metrics(self) -> dict:
        """Get current risk metrics"""
        return {
            'daily_trades': self.daily_trades,
            'daily_pnl': self.daily_pnl,
            'daily_trade_limit': self.config.max_daily_trades,
            'daily_loss_limit': self.config.max_daily_loss,
            'rejected_signals_today': len([s for s in self.rejected_signals 
                                         if s['timestamp'].date() == datetime.now().date()]),
            'rejected_orders_today': len([o for o in self.rejected_orders 
                                        if o['timestamp'].date() == datetime.now().date()])
        }
    
    def _log_validation_results(self, context: str, results: dict, is_valid: bool, extra: str = ""):
        """Internal helper to log per-check validation results"""
        status = "PASS" if is_valid else "FAIL"
        # Convert boolean results to strings for readability
        parsed = {k: ("OK" if v else "FAIL") for k, v in results.items()}
        self.logger.info("Validation %s | %s | %s | %s", status, context, extra, parsed)

    def get_rejection_analysis(self) -> dict:
        """Get analysis of rejected signals and orders"""
        # Analyze common rejection reasons
        signal_rejections = {}
        order_rejections = {}
        
        for rejected in self.rejected_signals:
            for check in rejected['failed_checks']:
                signal_rejections[check] = signal_rejections.get(check, 0) + 1
        
        for rejected in self.rejected_orders:
            for check in rejected['failed_checks']:
                order_rejections[check] = order_rejections.get(check, 0) + 1
        
        return {
            'signal_rejection_reasons': signal_rejections,
            'order_rejection_reasons': order_rejections,
            'total_signal_rejections': len(self.rejected_signals),
            'total_order_rejections': len(self.rejected_orders)
        }
    
    # ========================================
    # SMALLCAP-SPECIFIC RISK MANAGEMENT
    # ========================================
    
    def calculate_smallcap_position_size(self, 
                                       symbol: str,
                                       current_price: float,
                                       gap_percentage: float = 0.0,
                                       volume_ratio: float = 1.0,
                                       catalyst_type: str = 'OTHER',
                                       catalyst_strength: int = 5) -> Dict[str, any]:
        """
        Calculate optimal position size for smallcap daily plays
        
        Args:
            symbol: Stock symbol
            current_price: Current stock price
            gap_percentage: Gap % from previous close (0.10 = 10%)
            volume_ratio: Volume vs average (2.0 = 2x average)
            catalyst_type: FDA/EARNINGS/CONTRACT/M&A/OTHER/TECHNICAL
            catalyst_strength: 1-10 scale
            
        Returns:
            Dict with position sizing recommendation
        """
        try:
            # Input validation
            if current_price <= 0 or not isinstance(gap_percentage, (int, float)) or not isinstance(volume_ratio, (int, float)):
                raise ValueError("Invalid input parameters")
            
            # Smallcap position sizing rules
            base_position_percent = 0.08  # 8% base position
            max_smallcap_percent = 0.15   # 15% max per smallcap
            min_smallcap_percent = 0.02   # 2% minimum
            
            # Gap-based adjustments
            gap_abs = abs(gap_percentage)
            if gap_abs < 0.08:
                gap_multiplier = 0.8      # Small gaps: reduce size
            elif gap_abs < 0.15:
                gap_multiplier = 1.0      # Normal gaps: normal size
            elif gap_abs < 0.30:
                gap_multiplier = 1.2      # Large gaps: increase size
            else:
                gap_multiplier = 0.6      # Huge gaps: reduce (risky)
            
            # Volume-based adjustments
            if volume_ratio < 2.0:
                volume_multiplier = 0.7   # Low volume: small position
            elif volume_ratio < 5.0:
                volume_multiplier = 1.0   # Normal volume
            elif volume_ratio < 10.0:
                volume_multiplier = 1.3   # High volume: larger position
            else:
                volume_multiplier = 1.1   # Extreme volume: slightly larger
            
            # Catalyst-based adjustments
            catalyst_multipliers = {
                'FDA': 1.4,        # FDA news: higher confidence
                'EARNINGS': 0.9,   # Earnings: more volatile
                'CONTRACT': 1.2,   # Contracts: good momentum
                'M&A': 1.5,        # M&A: very strong
                'OTHER': 0.8,      # Other news: conservative
                'TECHNICAL': 0.6,  # Pure technical: smallest
            }
            catalyst_multiplier = catalyst_multipliers.get(catalyst_type, 0.8)
            
            # Adjust for catalyst strength (1-10 scale)
            strength_adjustment = (catalyst_strength - 5) * 0.05  # ±25% based on strength
            catalyst_multiplier = max(0.3, catalyst_multiplier + strength_adjustment)
            
            # Calculate final position size
            final_percent = base_position_percent * gap_multiplier * volume_multiplier * catalyst_multiplier
            
            # Apply limits
            final_percent = max(min_smallcap_percent, min(final_percent, max_smallcap_percent))
            
            # Get portfolio value
            portfolio_value = getattr(self.config, 'portfolio_value', 100000)
            recommended_value = portfolio_value * final_percent
            
            # Determine risk level
            risk_score = 0
            if gap_abs > 0.30: risk_score += 3
            elif gap_abs > 0.15: risk_score += 1
            if volume_ratio < 2: risk_score += 2
            elif volume_ratio > 10: risk_score += 1
            if catalyst_type == 'TECHNICAL': risk_score += 2
            elif catalyst_type in ['FDA', 'M&A']: risk_score -= 1
            
            risk_level = 'HIGH' if risk_score >= 4 else 'MODERATE' if risk_score >= 2 else 'LOW'
            
            result = {
                'symbol': symbol,
                'recommended_percent': final_percent,
                'recommended_value': recommended_value,
                'recommended_shares': int(recommended_value / current_price) if current_price > 0 else 0,
                'gap_multiplier': gap_multiplier,
                'volume_multiplier': volume_multiplier,
                'catalyst_multiplier': catalyst_multiplier,
                'risk_level': risk_level,
                'reasoning': f"Base {base_position_percent:.1%} × Gap({gap_multiplier:.1f}) × Vol({volume_multiplier:.1f}) × {catalyst_type}({catalyst_multiplier:.1f}) = {final_percent:.1%}"
            }
            
            self.logger.info(f"Smallcap sizing for {symbol}: {final_percent:.1%} (${recommended_value:,.0f}) - {risk_level} risk")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating smallcap position size for {symbol}: {e}")
            return {
                'symbol': symbol,
                'recommended_percent': 0.05,
                'recommended_value': 5000,
                'recommended_shares': int(5000 / current_price) if current_price > 0 else 0,
                'gap_multiplier': 1.0,
                'volume_multiplier': 1.0,
                'catalyst_multiplier': 1.0,
                'risk_level': 'MODERATE',
                'reasoning': "Conservative fallback due to calculation error"
            }
    
    def calculate_smallcap_stop_loss(self,
                                   symbol: str,
                                   gap_percentage: float = 0.0,
                                   volume_ratio: float = 1.0,
                                   catalyst_type: str = 'OTHER',
                                   catalyst_strength: int = 5) -> Dict[str, any]:
        """
        Calculate adaptive stop loss for smallcap daily plays
        
        Args:
            symbol: Stock symbol
            gap_percentage: Gap % from previous close
            volume_ratio: Volume vs average
            catalyst_type: Type of catalyst
            catalyst_strength: 1-10 scale
            
        Returns:
            Dict with stop loss recommendations
        """
        try:
            # Base stop loss by catalyst type
            catalyst_stop_bases = {
                'FDA': 0.12,       # 12% stop for FDA (wider for volatility)
                'EARNINGS': 0.08,  # 8% stop for earnings
                'CONTRACT': 0.10,  # 10% stop for contracts
                'M&A': 0.15,       # 15% stop for M&A (wider)
                'OTHER': 0.08,     # 8% stop for other
                'TECHNICAL': 0.06, # 6% stop for technical only
            }
            base_stop = catalyst_stop_bases.get(catalyst_type, 0.08)
            
            # Adjust for gap size (bigger gaps need wider stops)
            gap_abs = abs(gap_percentage)
            if gap_abs < 0.10:
                gap_adjustment = -0.01    # Tighter stops for small gaps
            elif gap_abs < 0.20:
                gap_adjustment = 0.0      # Normal gaps
            elif gap_abs < 0.35:
                gap_adjustment = 0.02     # Wider stops for large gaps
            else:
                gap_adjustment = 0.04     # Much wider for huge gaps
            
            # Adjust for volume (higher volume = can use tighter stops)
            if volume_ratio > 10:
                volume_adjustment = -0.01   # High volume = tighter stops
            elif volume_ratio < 2:
                volume_adjustment = 0.02    # Low volume = wider stops
            else:
                volume_adjustment = 0.0     # Normal volume
            
            # Adjust for catalyst strength
            strength_adjustment = (catalyst_strength - 5) * 0.005  # ±2.5% max
            
            # Calculate final stop loss
            final_stop = base_stop + gap_adjustment + volume_adjustment + strength_adjustment
            final_stop = max(0.04, min(final_stop, 0.20))  # 4% min, 20% max
            
            # Trailing stop parameters
            trailing_trigger = max(final_stop * 2, 0.10)  # Start trailing at 2x stop or 10%
            trailing_distance = final_stop * 0.6          # Trail at 60% of initial stop
            
            # Time-based tightening for momentum plays
            time_decay_factor = 1.0 if catalyst_type in ['TECHNICAL', 'OTHER'] else 0.5
            
            result = {
                'symbol': symbol,
                'initial_stop_percent': final_stop,
                'trailing_trigger_percent': trailing_trigger,
                'trailing_distance_percent': trailing_distance,
                'time_decay_factor': time_decay_factor,
                'catalyst_type': catalyst_type,
                'base_stop': base_stop,
                'gap_adjustment': gap_adjustment,
                'volume_adjustment': volume_adjustment,
                'strength_adjustment': strength_adjustment,
                'reasoning': f"{catalyst_type} base {base_stop:.1%} + Gap({gap_adjustment:+.1%}) + Vol({volume_adjustment:+.1%}) + Strength({strength_adjustment:+.1%}) = {final_stop:.1%}"
            }
            
            self.logger.info(f"Smallcap stop loss for {symbol}: {final_stop:.1%} ({catalyst_type})")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating smallcap stop loss for {symbol}: {e}")
            return {
                'symbol': symbol,
                'initial_stop_percent': 0.08,
                'trailing_trigger_percent': 0.12,
                'trailing_distance_percent': 0.05,
                'time_decay_factor': 1.0,
                'catalyst_type': catalyst_type,
                'reasoning': "Conservative 8% stop loss fallback"
            }
    
    def check_smallcap_momentum_decay(self, symbol: str, current_volume_ratio: float) -> tuple[bool, str]:
        """
        Detect momentum decay for smallcap positions
        
        Args:
            symbol: Stock symbol
            current_volume_ratio: Current volume vs daily average
            
        Returns:
            (should_exit, reason)
        """
        try:
            current_time = datetime.now()
            
            # Time-based momentum decay (afternoon fade)
            if current_time.hour >= 13:  # After 1 PM
                if current_volume_ratio < 0.5:  # Volume dropped below 50%
                    return True, "Afternoon volume fade - momentum lost"
            
            # Critical volume threshold
            if current_volume_ratio < 0.3:  # Volume < 30% of average
                return True, "Volume dropped below 30% - exit recommended"
            
            # End of day approach (after 3 PM)
            if current_time.hour >= 15:
                if current_volume_ratio < 0.7:  # Volume declining in final hour
                    return True, "End-of-day volume decline - consider exit"
            
            return False, "Momentum intact"
            
        except Exception as e:
            self.logger.error(f"Error detecting momentum decay for {symbol}: {e}")
            return False, f"Error in momentum analysis: {e}"
    
    def check_smallcap_exposure_limits(self, 
                                     symbol: str,
                                     position_value: float,
                                     catalyst_type: str = 'OTHER') -> tuple[bool, str]:
        """
        Check smallcap-specific exposure limits
        
        Args:
            symbol: Stock symbol
            position_value: Dollar value of proposed position
            catalyst_type: Type of catalyst
            
        Returns:
            (allowed, reason)
        """
        try:
            # Get portfolio value
            portfolio_value = getattr(self.config, 'portfolio_value', 100000)
            
            # Calculate current smallcap exposure
            # This is simplified - in production you'd track actual smallcap positions
            current_smallcap_exposure = 0.0  # Would be calculated from actual positions
            
            # Exposure limits
            max_total_smallcap_exposure = 0.40    # 40% max in smallcaps
            max_gap_exposure = 0.25               # 25% max in gap plays
            max_catalyst_positions = 3            # Max 3 per catalyst type
            
            # Check total smallcap exposure
            new_total_exposure = (current_smallcap_exposure + position_value) / portfolio_value
            if new_total_exposure > max_total_smallcap_exposure:
                return False, f"Exceeds max smallcap exposure: {new_total_exposure:.1%} > {max_total_smallcap_exposure:.1%}"
            
            # Check catalyst concentration (simplified)
            # In production, you'd track actual catalyst positions
            catalyst_positions = 0  # Would be counted from actual positions
            if catalyst_positions >= max_catalyst_positions:
                return False, f"Max {catalyst_type} positions reached: {catalyst_positions}"
            
            return True, "Smallcap exposure limits passed"
            
        except Exception as e:
            self.logger.error(f"Error checking smallcap exposure: {e}")
            return False, f"Error in exposure check: {e}"
    
    def format_smallcap_analysis(self, symbol: str, analysis_data: Dict) -> str:
        """
        Format smallcap analysis for display
        
        Args:
            symbol: Stock symbol
            analysis_data: Dict containing position sizing and stop loss data
            
        Returns:
            Formatted string for display
        """
        try:
            sizing = analysis_data.get('position_sizing', {})
            stop_loss = analysis_data.get('stop_loss', {})
            
            output = f"🎯 SMALLCAP ANALYSIS - {symbol}\n\n"
            
            # Position Sizing
            if sizing:
                output += f"📊 POSITION SIZING:\n"
                output += f"   Recommended: {sizing.get('recommended_percent', 0):.1%} (${sizing.get('recommended_value', 0):,.0f})\n"
                output += f"   Shares: {sizing.get('recommended_shares', 0):,}\n"
                output += f"   Risk Level: {sizing.get('risk_level', 'UNKNOWN')}\n"
                output += f"   Reasoning: {sizing.get('reasoning', 'N/A')}\n\n"
            
            # Stop Loss
            if stop_loss:
                output += f"🛡️ STOP LOSS:\n"
                output += f"   Initial Stop: {stop_loss.get('initial_stop_percent', 0):.1%}\n"
                output += f"   Trailing Trigger: {stop_loss.get('trailing_trigger_percent', 0):.1%}\n"
                output += f"   Trailing Distance: {stop_loss.get('trailing_distance_percent', 0):.1%}\n"
                output += f"   Catalyst: {stop_loss.get('catalyst_type', 'UNKNOWN')}\n"
                output += f"   Reasoning: {stop_loss.get('reasoning', 'N/A')}\n\n"
            
            return output
            
        except Exception as e:
            return f"Error formatting smallcap analysis: {e}"


# ========================================
# SMALLCAP MAYORDOMO - DAILY PLAYS ORCHESTRATOR
# ========================================

class SmallcapMayordomo(RiskManager):
    """
    Smallcap Daily Plays Mayordomo - Extends RiskManager
    Orchestrates daily plays lifecycle from pre-market to close
    
    Core Functions:
    1. Daily plays lifecycle management (momentum tracking)
    2. Timing optimization (entry/exit windows)
    3. Position rotation between daily plays
    4. Market context awareness for smallcaps
    5. FOMO detection for optimal exits
    """
    
    def __init__(self, config: TradingConfig):
        super().__init__(config)
        self.logger = logging.getLogger("SmallcapMayordomo")
        
        # Initialize FOMO Detection System
        try:
            from core.fomo_detector import FOMODetector
            fomo_config = {
                'fomo_threshold': getattr(config, 'fomo_threshold', 0.75),
                'critical_threshold': getattr(config, 'critical_threshold', 0.90),
                'volume_explosion_multiplier': getattr(config, 'volume_explosion_multiplier', 8.0),
                'consecutive_green_bars': getattr(config, 'consecutive_green_bars', 5),
                'rsi_overbought_level': getattr(config, 'rsi_overbought_level', 85)
            }
            self.fomo_detector = FOMODetector(fomo_config)
            self.fomo_enabled = True
            self.logger.info("🎪 FOMO Detection enabled for SmallcapMayordomo")
        except ImportError:
            self.fomo_detector = None
            self.fomo_enabled = False
            self.logger.warning("⚠️ FOMO Detection module not available")
        except Exception as e:
            self.fomo_detector = None
            self.fomo_enabled = False
            self.logger.error(f"❌ Error initializing FOMO Detection: {e}")
        
        # Daily plays tracking
        self.active_daily_plays: Dict[str, Dict] = {}
        self.play_queue: List[Dict] = []  # Queue of potential plays
        self.momentum_tracker: Dict[str, List] = {}  # Volume/price momentum history
        
        # Timing optimization
        self.market_session_analysis = {
            'premarket_strength': 0.5,
            'opening_volatility': 0.5, 
            'midday_fade_risk': 0.5,
            'closing_pressure': 0.5
        }
        
        # Position rotation management
        self.rotation_candidates: Dict[str, float] = {}  # symbol -> opportunity_score
        self.daily_rotation_count = 0
        self.max_daily_rotations = 3
        
        # Market context for smallcaps
        self.smallcap_market_regime = {
            'risk_sentiment': 'NEUTRAL',  # RISK_ON, RISK_OFF, NEUTRAL
            'catalyst_effectiveness': 0.7,  # How well catalysts are working
            'volume_environment': 'NORMAL',  # HIGH, NORMAL, LOW
            'volatility_regime': 'MODERATE'  # HIGH, MODERATE, LOW
        }
        
        self.logger.info("🏛️ SmallcapMayordomo initialized - Daily plays orchestrator ready")
    
    def register_daily_play(self, symbol: str, catalyst_type: str, 
                          catalyst_strength: int, gap_percentage: float,
                          volume_ratio: float, entry_price: float) -> bool:
        """
        Register a new daily play for tracking
        
        Args:
            symbol: Stock symbol
            catalyst_type: FDA/EARNINGS/CONTRACT/M&A/OTHER/TECHNICAL
            catalyst_strength: 1-10 scale
            gap_percentage: Gap from previous close
            volume_ratio: Volume vs average
            entry_price: Entry price
            
        Returns:
            bool: True if registered successfully
        """
        try:
            play_info = {
                'symbol': symbol,
                'catalyst_type': catalyst_type,
                'catalyst_strength': catalyst_strength,
                'gap_percentage': gap_percentage,
                'volume_ratio': volume_ratio,
                'entry_price': entry_price,
                'entry_time': datetime.now(),
                'phase': 'ENTRY',  # ENTRY, MOMENTUM, FADE, EXIT
                'momentum_score': self._calculate_initial_momentum(gap_percentage, volume_ratio),
                'peak_price': entry_price,
                'volume_decay_alerts': 0,
                'time_decay_factor': 1.0
            }
            
            self.active_daily_plays[symbol] = play_info
            
            # Initialize momentum tracking
            self.momentum_tracker[symbol] = [{
                'timestamp': datetime.now(),
                'price': entry_price,
                'volume_ratio': volume_ratio,
                'momentum_score': play_info['momentum_score']
            }]
            
            self.logger.info(f"🎯 Daily play registered: {symbol} [{catalyst_type}] "
                           f"Gap: {gap_percentage:.1%}, Vol: {volume_ratio:.1f}x, "
                           f"Momentum: {play_info['momentum_score']:.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering daily play {symbol}: {e}")
            return False
    
    def update_daily_play_momentum(self, symbol: str, current_price: float, 
                                 current_volume_ratio: float) -> Dict[str, Any]:
        """
        Update momentum tracking for active daily play
        
        Returns:
            Dict with momentum analysis and recommendations
        """
        if symbol not in self.active_daily_plays:
            return {'action': 'NONE', 'reason': 'Not an active daily play'}
        
        try:
            play = self.active_daily_plays[symbol]
            current_time = datetime.now()
            
            # Update peak price tracking
            if current_price > play['peak_price']:
                play['peak_price'] = current_price
            
            # Calculate current momentum
            momentum_score = self._calculate_current_momentum(
                play, current_price, current_volume_ratio, current_time
            )
            
            # Add to momentum history
            self.momentum_tracker[symbol].append({
                'timestamp': current_time,
                'price': current_price,
                'volume_ratio': current_volume_ratio,
                'momentum_score': momentum_score
            })
            
            # Keep only last 20 data points
            if len(self.momentum_tracker[symbol]) > 20:
                self.momentum_tracker[symbol] = self.momentum_tracker[symbol][-20:]
            
            # Analyze momentum trend
            momentum_analysis = self._analyze_momentum_trend(symbol)
            
            # Update play phase
            new_phase = self._determine_play_phase(play, momentum_analysis, current_time)
            if new_phase != play['phase']:
                self.logger.info(f"🔄 {symbol} phase change: {play['phase']} -> {new_phase}")
                play['phase'] = new_phase
            
            # Generate recommendations
            recommendation = self._generate_momentum_recommendation(
                symbol, play, momentum_analysis, current_price
            )
            
            return recommendation
            
        except Exception as e:
            self.logger.error(f"Error updating momentum for {symbol}: {e}")
            return {'action': 'HOLD', 'reason': f'Error in momentum update: {e}'}
    
    def evaluate_position_rotation(self, new_opportunity: Dict) -> Dict[str, Any]:
        """
        Evaluate if we should open new position - SIMPLIFIED for smallcaps
        No rotation logic - smallcaps are event-driven, hold until completion
        
        Args:
            new_opportunity: Dict with symbol, catalyst_type, strength, etc.
            
        Returns:
            Dict with decision and reasoning
        """
        try:
            symbol = new_opportunity.get('symbol', '')
            
            # CRITICAL FIX: Force position sync before evaluation to ensure latest state
            if hasattr(self, 'broker') and self.broker and hasattr(self.broker, 'get_positions'):
                try:
                    import asyncio
                    # Try to update positions synchronously for immediate check
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Create task for position update (will complete in next cycle)
                        loop.create_task(self.sync_broker_positions())
                        self.logger.debug(f"📊 Position sync scheduled for {symbol} evaluation")
                    else:
                        # Update positions synchronously
                        loop.run_until_complete(self.sync_broker_positions())
                        self.logger.debug(f"📊 Position sync completed for {symbol} evaluation")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not sync positions before {symbol} evaluation: {e}")
            
            # CRITICAL: Prevent MARTINGALA - check if we already have position
            # AUTO-SYNC: Simple broker verification (no async needed for smallcaps)
            has_internal_position = symbol in self.active_daily_plays
            
            # ENHANCED: Also check broker positions directly
            has_broker_position = symbol in self.broker_positions if hasattr(self, 'broker_positions') else False
            
            # Quick broker sync check if broker available
            if has_internal_position and hasattr(self, 'broker') and self.broker:
                try:
                    has_broker_position = self._check_broker_position_sync(symbol)
                    if not has_broker_position:
                        self.logger.warning(f"🔄 AUTO-SYNC: Internal position for {symbol} exists but no broker position - cleaning internal state")
                        self.remove_active_play(symbol, "Auto-sync: no broker position")
                        has_internal_position = False
                except Exception as e:
                    self.logger.debug(f"🔍 Broker sync check failed for {symbol}: {e} - continuing with internal state")
            
            # CRITICAL: Check for existing position using BOTH internal tracking AND broker positions
            has_existing_position = has_internal_position or has_broker_position
            
            if has_existing_position:
                # Log which source detected the position
                position_source = []
                if has_internal_position:
                    position_source.append("internal")
                if has_broker_position:
                    position_source.append("broker")
                self.logger.info(f"🔍 Existing position detected for {symbol} via: {', '.join(position_source)}")
                
            if has_existing_position:
                # Check if pyramid trading is enabled
                allow_pyramiding = getattr(self.config, 'allow_pyramiding', False)
                
                if allow_pyramiding:
                    # Evaluate pyramid opportunity
                    pyramid_decision = self._evaluate_pyramid_opportunity(symbol, new_opportunity)
                    
                    if pyramid_decision['allow_pyramid']:
                        self.logger.info(f"🔺 PYRAMID opportunity for {symbol}: {pyramid_decision['reason']}")
                        return {
                            'action': 'PYRAMID_POSITION', 
                            'symbol': symbol,
                            'reason': f"Pyramid: {pyramid_decision['reason']}",
                            'position_size': pyramid_decision['pyramid_size']
                        }
                    else:
                        self.logger.info(f"🚫 PYRAMID rejected for {symbol}: {pyramid_decision['reason']}")
                        return {
                            'action': 'REJECT',
                            'reason': f'Pyramid criteria not met: {pyramid_decision["reason"]}'
                        }
                else:
                    # Anti-martingala protection (default behavior)
                    self.logger.warning(f"🚫 ANTI-MARTINGALA: Already have position in {symbol} - rejecting duplicate entry")
                    return {
                        'action': 'REJECT',
                        'reason': f'ANTI-MARTINGALA: Already have active position in {symbol}. No duplicates allowed.'
                    }
            
            # Calculate opportunity score for new play
            new_score = self._calculate_opportunity_score(new_opportunity)
            
            # Check if opportunity meets minimum quality threshold
            min_quality_threshold = 0.45
            
            if new_score < min_quality_threshold:
                return {
                    'action': 'REJECT',
                    'reason': f'Opportunity score {new_score:.2f} below minimum threshold {min_quality_threshold:.2f}'
                }
            
            # Check how many positions we currently have - USE BROKER POSITIONS, NOT INTERNAL TRACKER
            # This fixes the bug where closed positions were still counted internally
            current_positions = len([pos for pos in self.broker_positions.values() 
                                   if isinstance(pos, dict) and abs(pos.get('position', 0)) > 0])
            max_positions = getattr(self.config, 'max_positions', 3)
            
            # If we have available slots, take good opportunities
            if current_positions < max_positions:
                if new_score >= 0.50:  # Reasonable threshold for available slots
                    return {
                        'action': 'OPEN_POSITION',
                        'symbol': new_opportunity['symbol'],
                        'reason': f'Good opportunity {new_score:.2f} - open position (slot {current_positions + 1}/{max_positions})',
                        'confidence': new_score,
                        'position_size': self._calculate_position_size_from_score(new_score)
                    }
                else:
                    return {
                        'action': 'REJECT',
                        'reason': f'Opportunity score {new_score:.2f} not strong enough (need ≥0.50 for available slot)'
                    }
            
            # Portfolio is full - only accept exceptional opportunities
            exceptional_threshold = 0.80  # Very high bar when portfolio is full
            
            if new_score >= exceptional_threshold:
                return {
                    'action': 'OPEN_POSITION',
                    'symbol': new_opportunity['symbol'],
                    'reason': f'Exceptional opportunity {new_score:.2f} - overriding full portfolio',
                    'confidence': new_score,
                    'position_size': self._calculate_position_size_from_score(new_score)
                }
            else:
                return {
                    'action': 'REJECT',
                    'reason': f'Portfolio full ({current_positions}/{max_positions}) - need exceptional score (≥{exceptional_threshold:.2f}), got {new_score:.2f}'
                }
            
        except Exception as e:
            self.logger.error(f"Error evaluating position: {e}")
            return {'action': 'REJECT', 'reason': f'Error in position analysis: {e}'}
    
    def get_optimal_entry_timing(self, symbol: str, catalyst_type: str) -> Dict[str, Any]:
        """
        Determine optimal entry timing for smallcap daily play
        
        Returns:
            Dict with timing recommendation
        """
        try:
            current_time = datetime.now()
            market_session = self._get_market_session_phase()
            
            # Base timing recommendations by catalyst type
            timing_matrix = {
                'FDA': {
                    'premarket': 0.9,     # High - news usually breaks pre-market
                    'open': 0.8,          # Good - momentum carries over
                    'morning': 0.6,       # Moderate - can still catch moves
                    'midday': 0.3,        # Low - momentum usually fades
                    'afternoon': 0.2      # Very low - avoid late entries
                },
                'EARNINGS': {
                    'premarket': 0.8,     # Good - earnings before market
                    'open': 0.9,          # Excellent - immediate reaction
                    'morning': 0.7,       # Good - digestion period
                    'midday': 0.4,        # Moderate - depends on reaction
                    'afternoon': 0.3      # Low - momentum usually done
                },
                'CONTRACT': {
                    'premarket': 0.6,     # Moderate - news timing varies
                    'open': 0.8,          # Good - market can react
                    'morning': 0.8,       # Good - sustained momentum
                    'midday': 0.6,        # Moderate - still viable
                    'afternoon': 0.4      # Low but possible
                },
                'M&A': {
                    'premarket': 0.9,     # Excellent - usually announced pre-market
                    'open': 0.9,          # Excellent - strong momentum
                    'morning': 0.7,       # Good - still processing
                    'midday': 0.5,        # Moderate - depends on details
                    'afternoon': 0.3      # Low - momentum fades
                },
                'OTHER': {
                    'premarket': 0.5,     # Moderate - depends on news
                    'open': 0.6,          # Moderate
                    'morning': 0.6,       # Moderate
                    'midday': 0.4,        # Lower
                    'afternoon': 0.3      # Low
                },
                'TECHNICAL': {
                    'premarket': 0.3,     # Low - need market volume
                    'open': 0.7,          # Good - breakouts happen
                    'morning': 0.8,       # Excellent - best volume
                    'midday': 0.6,        # Moderate - decent volume
                    'afternoon': 0.4      # Lower - volume fades
                }
            }
            
            base_score = timing_matrix.get(catalyst_type, timing_matrix['OTHER']).get(market_session, 0.5)
            
            # Adjust for market conditions
            adjusted_score = self._adjust_timing_for_market_conditions(base_score, market_session)
            
            # Generate recommendation (adjusted to be less restrictive)
            if adjusted_score >= 0.8:
                recommendation = 'IMMEDIATE'
            elif adjusted_score >= 0.6:
                recommendation = 'FAVORABLE'
            elif adjusted_score >= 0.3:  # Lowered from 0.4 to 0.3
                recommendation = 'CAUTION'
            else:
                recommendation = 'AVOID'
            
            return {
                'symbol': symbol,
                'recommendation': recommendation,
                'timing_score': adjusted_score,
                'market_session': market_session,
                'catalyst_type': catalyst_type,
                'reasoning': self._get_timing_reasoning(recommendation, market_session, catalyst_type)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating entry timing for {symbol}: {e}")
            return {
                'recommendation': 'CAUTION',
                'timing_score': 0.5,
                'reasoning': f'Error in timing analysis: {e}'
            }
    
    def assess_smallcap_market_regime(self) -> Dict[str, Any]:
        """
        Assess current smallcap market regime and conditions
        
        Returns:
            Dict with market regime analysis
        """
        try:
            current_time = datetime.now()
            
            # Analyze risk sentiment (simplified - would use VIX, sector performance, etc.)
            risk_sentiment = self._assess_risk_sentiment()
            
            # Analyze catalyst effectiveness 
            catalyst_effectiveness = self._assess_catalyst_effectiveness()
            
            # Analyze volume environment
            volume_environment = self._assess_volume_environment()
            
            # Update internal regime tracking
            self.smallcap_market_regime.update({
                'risk_sentiment': risk_sentiment,
                'catalyst_effectiveness': catalyst_effectiveness,
                'volume_environment': volume_environment,
                'last_update': current_time
            })
            
            # Generate position sizing adjustment recommendations
            sizing_adjustment = self._calculate_regime_sizing_adjustment()
            
            return {
                'regime': self.smallcap_market_regime,
                'sizing_adjustment': sizing_adjustment,
                'recommendations': self._generate_regime_recommendations()
            }
            
        except Exception as e:
            self.logger.error(f"Error assessing market regime: {e}")
            return {
                'regime': self.smallcap_market_regime,
                'sizing_adjustment': 1.0,
                'recommendations': ['Error in regime analysis - use conservative approach']
            }
    
    # Private helper methods
    def _calculate_initial_momentum(self, gap_percentage: float, volume_ratio: float) -> float:
        """Calculate initial momentum score"""
        gap_score = min(abs(gap_percentage) * 2, 1.0)  # Cap at 50% gap
        volume_score = min(volume_ratio / 5.0, 1.0)    # Cap at 5x volume
        return (gap_score + volume_score) / 2
    
    def _calculate_current_momentum(self, play: Dict, current_price: float, 
                                  volume_ratio: float, current_time: datetime) -> float:
        """Calculate current momentum score"""
        try:
            # Price momentum (relative to entry and peak)
            price_vs_entry = (current_price - play['entry_price']) / play['entry_price']
            price_vs_peak = (current_price - play['peak_price']) / play['peak_price']
            
            # Time decay factor
            minutes_since_entry = (current_time - play['entry_time']).total_seconds() / 60
            time_decay = max(0.3, 1.0 - (minutes_since_entry / 360))  # Decay over 6 hours
            
            # Volume decay
            volume_decay = min(volume_ratio / max(play['volume_ratio'], 1.0), 1.0)
            
            # Combined momentum
            momentum = (
                max(0, price_vs_entry) * 0.4 +       # 40% price performance vs entry
                max(0, price_vs_peak + 1) * 0.3 +    # 30% price vs peak (drawdown)
                volume_decay * 0.2 +                 # 20% volume maintenance
                time_decay * 0.1                     # 10% time decay
            )
            
            return max(0, min(1, momentum))
            
        except Exception as e:
            self.logger.error(f"Error calculating momentum: {e}")
            return 0.5
    
    def _analyze_momentum_trend(self, symbol: str) -> Dict[str, Any]:
        """Analyze momentum trend from recent history"""
        if symbol not in self.momentum_tracker or len(self.momentum_tracker[symbol]) < 3:
            return {'trend': 'INSUFFICIENT_DATA', 'strength': 0.5}
        
        recent_data = self.momentum_tracker[symbol][-5:]  # Last 5 data points
        
        # Calculate trend
        momentum_values = [d['momentum_score'] for d in recent_data]
        volume_values = [d['volume_ratio'] for d in recent_data]
        
        # Simple trend analysis
        momentum_trend = 'STABLE'
        if len(momentum_values) >= 3:
            if momentum_values[-1] > momentum_values[-2] > momentum_values[-3]:
                momentum_trend = 'STRENGTHENING'
            elif momentum_values[-1] < momentum_values[-2] < momentum_values[-3]:
                momentum_trend = 'WEAKENING'
        
        avg_momentum = sum(momentum_values) / len(momentum_values)
        avg_volume = sum(volume_values) / len(volume_values)
        
        return {
            'trend': momentum_trend,
            'strength': avg_momentum,
            'volume_trend': avg_volume,
            'data_points': len(recent_data)
        }
    
    def _determine_play_phase(self, play: Dict, momentum_analysis: Dict, current_time: datetime) -> str:
        """Determine current phase of daily play"""
        minutes_since_entry = (current_time - play['entry_time']).total_seconds() / 60
        momentum_strength = momentum_analysis['strength']
        momentum_trend = momentum_analysis['trend']
        
        # Phase determination logic
        if minutes_since_entry < 30 and momentum_strength > 0.7:
            return 'ENTRY'
        elif momentum_trend == 'STRENGTHENING' and momentum_strength > 0.6:
            return 'MOMENTUM'
        elif momentum_trend == 'WEAKENING' or momentum_strength < 0.4:
            return 'FADE'
        elif minutes_since_entry > 300:  # After 5 hours
            return 'EXIT'
        else:
            return 'MOMENTUM'
    
    def _generate_momentum_recommendation(self, symbol: str, play: Dict, 
                                        momentum_analysis: Dict, current_price: float) -> Dict[str, Any]:
        """Generate action recommendation based on momentum analysis with FOMO detection"""
        phase = play['phase']
        trend = momentum_analysis['trend']
        strength = momentum_analysis['strength']
        
        # PRIORITY 1: Check FOMO exit signal first (overrides other logic)
        if self.fomo_enabled and self.fomo_detector:
            try:
                # Get bars history for FOMO analysis
                bars_history = self.momentum_tracker.get(symbol, [])
                if len(bars_history) >= 10:  # Need sufficient data
                    # Create a mock position object if we don't have one
                    position = type('MockPosition', (), {
                        'symbol': symbol,
                        'entry_time': play.get('entry_time'),
                        'quantity': 100,  # Mock quantity
                        'avg_price': play.get('entry_price', current_price)
                    })()
                    
                    # Create current bar from latest data
                    if bars_history:
                        latest_data = bars_history[-1]
                        current_bar = type('MockBar', (), {
                            'timestamp': latest_data.get('timestamp'),
                            'close': current_price,
                            'volume': latest_data.get('volume_ratio', 1.0) * 1000000,  # Mock volume
                            'high': current_price * 1.02,  # Mock high
                            'low': current_price * 0.98,   # Mock low
                            'open': current_price * 0.99   # Mock open
                        })()
                        
                        fomo_analysis = self.fomo_detector.detect_fomo_exit(
                            symbol, current_bar, position, []
                        )
                        
                        if fomo_analysis.get('should_exit', False):
                            fomo_signal = fomo_analysis.get('fomo_signal')
                            return {
                                'action': 'EXIT',
                                'reason': f'FOMO TOP DETECTED - Score: {fomo_signal.fomo_score:.2f}',
                                'urgency': fomo_signal.exit_urgency,
                                'confidence': fomo_signal.confidence,
                                'exit_type': 'FOMO_EXIT',
                                'fomo_reasons': fomo_signal.fomo_reasons
                            }
            except Exception as e:
                self.logger.error(f"Error in FOMO analysis for {symbol}: {e}")
        
        # PRIORITY 2: Standard momentum-based decisions (if no FOMO exit)
        if phase == 'FADE' and trend == 'WEAKENING':
            return {
                'action': 'EXIT',
                'reason': f'Momentum fade detected - strength: {strength:.2f}',
                'urgency': 'HIGH',
                'confidence': 0.8,
                'exit_type': 'MOMENTUM_FADE'
            }
        elif phase == 'MOMENTUM' and trend == 'STRENGTHENING':
            return {
                'action': 'HOLD',
                'reason': f'Strong momentum continuing - strength: {strength:.2f}',
                'urgency': 'LOW',
                'confidence': 0.9
            }
        elif strength < 0.3:
            return {
                'action': 'EXIT',
                'reason': f'Very weak momentum - strength: {strength:.2f}',
                'urgency': 'HIGH',
                'confidence': 0.7,
                'exit_type': 'WEAK_MOMENTUM'
            }
        else:
            return {
                'action': 'HOLD',
                'reason': f'Monitoring momentum - phase: {phase}, strength: {strength:.2f}',
                'urgency': 'LOW',
                'confidence': 0.6
            }
    
    def _calculate_opportunity_score(self, opportunity: Dict) -> float:
        """Calculate opportunity score for rotation decisions"""
        try:
            catalyst_scores = {
                'FDA': 0.9, 'M&A': 0.85, 'CONTRACT': 0.7,
                'EARNINGS': 0.6, 'OTHER': 0.4, 'TECHNICAL': 0.3
            }
            
            catalyst_score = catalyst_scores.get(opportunity.get('catalyst_type', 'OTHER'), 0.4)
            strength_score = opportunity.get('catalyst_strength', 5) / 10.0
            gap_score = min(abs(opportunity.get('gap_percentage', 0)) * 2, 1.0)
            volume_score = min(opportunity.get('volume_ratio', 1) / 5.0, 1.0)
            
            # Weighted combination
            opportunity_score = (
                catalyst_score * 0.4 +
                strength_score * 0.3 +
                gap_score * 0.2 +
                volume_score * 0.1
            )
            
            return min(1.0, opportunity_score)
            
        except Exception as e:
            self.logger.error(f"Error calculating opportunity score: {e}")
            return 0.5
    
    def _find_weakest_position(self) -> Optional[Dict]:
        """Find weakest current position for potential rotation"""
        if not self.active_daily_plays:
            return None
        
        weakest = None
        lowest_score = float('inf')
        
        for symbol, play in self.active_daily_plays.items():
            # Calculate current strength of position
            current_strength = self._calculate_position_strength(play)
            
            if current_strength < lowest_score:
                lowest_score = current_strength
                weakest = {
                    'symbol': symbol,
                    'opportunity_score': current_strength,
                    'play_info': play
                }
        
        return weakest
    
    def _calculate_position_strength(self, play: Dict) -> float:
        """Calculate current strength of position"""
        try:
            current_time = datetime.now()
            minutes_since_entry = (current_time - play['entry_time']).total_seconds() / 60
            
            # Time decay penalty
            time_penalty = min(minutes_since_entry / 360, 0.5)  # Up to 50% penalty over 6 hours
            
            # Phase penalty
            phase_scores = {'ENTRY': 1.0, 'MOMENTUM': 0.8, 'FADE': 0.3, 'EXIT': 0.1}
            phase_score = phase_scores.get(play['phase'], 0.5)
            
            # Momentum score
            momentum_score = play.get('momentum_score', 0.5)
            
            strength = (phase_score * 0.5 + momentum_score * 0.3 + (1 - time_penalty) * 0.2)
            
            return max(0, min(1, strength))
            
        except Exception as e:
            self.logger.error(f"Error calculating position strength: {e}")
            return 0.5
    
    def _calculate_position_size_from_score(self, opportunity_score: float) -> float:
        """
        Calculate position size based on opportunity score
        
        Args:
            opportunity_score: Score from 0.0 to 1.0
            
        Returns:
            Position size as fraction of portfolio (0.0 to 1.0)
        """
        try:
            # Base position size
            base_size = 0.05  # 5% base position
            max_size = 0.15   # 15% max position for smallcaps
            
            # Scale position size with opportunity score
            # Score 0.6 = 5% position, Score 1.0 = 15% position
            if opportunity_score >= 0.6:
                size_multiplier = (opportunity_score - 0.6) / 0.4  # 0.0 to 1.0 range
                position_size = base_size + (max_size - base_size) * size_multiplier
            else:
                # Below threshold, very small position
                position_size = base_size * 0.5
            
            return max(0.02, min(position_size, max_size))  # 2% min, 15% max
            
        except Exception as e:
            self.logger.error(f"Error calculating position size from score: {e}")
            return 0.05  # Default 5%
    
    def _get_market_session_phase(self) -> str:
        """Get current market session phase based on EST timezone"""
        from datetime import timezone, timedelta

        # Convert to EST (UTC-5) or EDT (UTC-4) depending on daylight saving
        est_timezone = timezone(timedelta(hours=-5))  # EST
        current_time_est = datetime.now(est_timezone)
        hour = current_time_est.hour
        minute = current_time_est.minute

        if hour < 9 or (hour == 9 and minute < 30):
            return 'premarket'
        elif hour == 9 and minute >= 30:
            return 'open'
        elif hour < 12:
            return 'morning'
        elif hour < 15:
            return 'midday'
        else:
            return 'afternoon'
    
    def _adjust_timing_for_market_conditions(self, base_score: float, session: str) -> float:
        """Adjust timing score based on current market conditions"""
        regime = self.smallcap_market_regime
        
        adjustments = 0
        
        # Risk sentiment adjustment
        if regime['risk_sentiment'] == 'RISK_ON':
            adjustments += 0.1
        elif regime['risk_sentiment'] == 'RISK_OFF':
            adjustments -= 0.2
        
        # Volume environment adjustment
        if regime['volume_environment'] == 'HIGH':
            adjustments += 0.1
        elif regime['volume_environment'] == 'LOW':
            adjustments -= 0.1
        
        return max(0, min(1, base_score + adjustments))
    
    def _get_timing_reasoning(self, recommendation: str, session: str, catalyst_type: str) -> str:
        """Generate reasoning for timing recommendation"""
        reasoning_map = {
            'IMMEDIATE': f'Excellent timing for {catalyst_type} during {session} session',
            'FAVORABLE': f'Good timing for {catalyst_type}, favorable {session} conditions',
            'CAUTION': f'Moderate timing for {catalyst_type}, {session} session has limitations',
            'AVOID': f'Poor timing for {catalyst_type} during {session}, avoid entry'
        }
        
        return reasoning_map.get(recommendation, 'Standard timing assessment')
    
    def _assess_risk_sentiment(self) -> str:
        """Assess current risk sentiment (simplified)"""
        # In production, this would analyze VIX, sector performance, etc.
        # For now, return based on time-based heuristics
        from datetime import timezone, timedelta
        est_timezone = timezone(timedelta(hours=-5))
        current_hour = datetime.now(est_timezone).hour

        if 9 <= current_hour <= 11:
            return 'RISK_ON'    # Morning optimism
        elif 14 <= current_hour <= 16:
            return 'NEUTRAL'    # Afternoon consolidation
        else:
            return 'RISK_OFF'   # Pre-market caution
    
    def _assess_catalyst_effectiveness(self) -> float:
        """Assess how well catalysts are working in current market"""
        # Simplified - would track actual catalyst success rates
        return 0.7  # Default 70% effectiveness
    
    def _assess_volume_environment(self) -> str:
        """Assess current volume environment"""
        # Simplified - would analyze actual market volume
        from datetime import timezone, timedelta
        est_timezone = timezone(timedelta(hours=-5))
        current_hour = datetime.now(est_timezone).hour

        if 9 <= current_hour <= 12:
            return 'HIGH'       # Morning volume
        elif 13 <= current_hour <= 15:
            return 'NORMAL'     # Afternoon normal
        else:
            return 'LOW'        # Extended hours
    
    def _calculate_regime_sizing_adjustment(self) -> float:
        """Calculate position sizing adjustment based on regime"""
        regime = self.smallcap_market_regime
        adjustment = 1.0
        
        # Risk sentiment adjustment
        if regime['risk_sentiment'] == 'RISK_ON':
            adjustment *= 1.2
        elif regime['risk_sentiment'] == 'RISK_OFF':
            adjustment *= 0.7
        
        # Catalyst effectiveness adjustment
        effectiveness = regime['catalyst_effectiveness']
        adjustment *= (0.8 + effectiveness * 0.4)  # 0.8 to 1.2 range
        
        return max(0.5, min(1.5, adjustment))
    
    def _generate_regime_recommendations(self) -> List[str]:
        """Generate recommendations based on current regime"""
        regime = self.smallcap_market_regime
        recommendations = []
        
        if regime['risk_sentiment'] == 'RISK_OFF':
            recommendations.append('Reduce position sizes due to risk-off environment')
            recommendations.append('Focus on highest-conviction catalysts only')
        
        if regime['volume_environment'] == 'LOW':
            recommendations.append('Avoid technical-only plays due to low volume')
            recommendations.append('Prefer catalyst-driven plays with strong fundamentals')
        
        if regime['catalyst_effectiveness'] < 0.5:
            recommendations.append('Be more selective with catalyst plays - effectiveness is low')
        
        if not recommendations:
            recommendations.append('Normal market conditions - standard strategy execution')
        
        return recommendations


# ========================================
# FACTORY FUNCTIONS
# ========================================

def create_smallcap_mayordomo(config: TradingConfig = None, broker=None) -> SmallcapMayordomo:
    """
    Factory function to create SmallcapMayordomo instance
    
    Args:
        config: TradingConfig object (optional, will create default if None)
        broker: Shared broker adapter for position synchronization (optional)
        
    Returns:
        SmallcapMayordomo instance ready to orchestrate daily plays
    """
    try:
        # Create default config if none provided
        if config is None:
            config = TradingConfig()
            config.max_daily_trades = 10
            config.max_daily_loss = -500.0
            config.max_positions = 1
            config.portfolio_capital = 10000.0
        
        # Create and return mayordomo instance
        mayordomo = SmallcapMayordomo(config)
        
        # CRITICAL FIX: Use shared broker for position synchronization
        if broker:
            mayordomo.broker = broker
            logging.getLogger(__name__).info("🔗 SmallcapMayordomo: Using shared broker adapter for position sync")
            # Immediately sync positions from shared broker
            try:
                import asyncio
                if hasattr(broker, 'get_positions'):
                    # Try to update positions if broker is available
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Schedule position update for next cycle
                        loop.create_task(mayordomo.sync_broker_positions())
                    else:
                        # Update positions synchronously if no loop is running
                        loop.run_until_complete(mayordomo.sync_broker_positions())
                    logging.getLogger(__name__).info("✅ SmallcapMayordomo: Initial position sync completed")
            except Exception as e:
                logging.getLogger(__name__).warning(f"⚠️ SmallcapMayordomo: Could not sync positions immediately: {e}")
        
        logging.getLogger(__name__).info("🏛️ SmallcapMayordomo factory: Created new instance")
        logging.getLogger(__name__).info(f"   Portfolio capital: ${config.portfolio_capital:,.0f}")
        logging.getLogger(__name__).info(f"   Max daily trades: {config.max_daily_trades}")
        logging.getLogger(__name__).info(f"   Max positions: {config.max_positions}")
        logging.getLogger(__name__).info(f"   Shared broker: {'YES' if broker else 'NO'}")
        
        return mayordomo
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Error creating SmallcapMayordomo: {e}")
        raise


def get_mayordomo_status(mayordomo: SmallcapMayordomo) -> Dict[str, Any]:
    """
    Get comprehensive status of SmallcapMayordomo
    
    Args:
        mayordomo: SmallcapMayordomo instance
        
    Returns:
        Dict with status information
    """
    try:
        status = {
            'active_daily_plays': len(mayordomo.active_daily_plays),
            'play_queue_size': len(mayordomo.play_queue),
            'daily_rotation_count': mayordomo.daily_rotation_count,
            'max_daily_rotations': mayordomo.max_daily_rotations,
            'market_regime': mayordomo.smallcap_market_regime,
            'tracked_symbols': list(mayordomo.active_daily_plays.keys()),
            'momentum_tracker_size': len(mayordomo.momentum_tracker),
        }
        
        # Add detailed play information
        status['play_details'] = {}
        for symbol, play in mayordomo.active_daily_plays.items():
            status['play_details'][symbol] = {
                'catalyst_type': play['catalyst_type'],
                'phase': play['phase'],
                'momentum_score': play['momentum_score'],
                'entry_time': play['entry_time'].isoformat(),
                'minutes_since_entry': (datetime.now() - play['entry_time']).total_seconds() / 60
            }
        
        return status
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Error getting mayordomo status: {e}")
        return {'error': str(e)}


def format_mayordomo_summary(mayordomo: SmallcapMayordomo) -> str:
    """
    Format SmallcapMayordomo status for display
    
    Args:
        mayordomo: SmallcapMayordomo instance
        
    Returns:
        Formatted string for display
    """
    try:
        status = get_mayordomo_status(mayordomo)
        
        output = f"🏛️ SMALLCAP MAYORDOMO STATUS:\n\n"
        
        # Overview
        output += f"📊 OVERVIEW:\n"
        output += f"   Active Daily Plays: {status['active_daily_plays']}\n"
        output += f"   Play Queue: {status['play_queue_size']}\n"
        output += f"   Daily Rotations: {status['daily_rotation_count']}/{status['max_daily_rotations']}\n\n"
        
        # Market Regime
        regime = status['market_regime']
        output += f"🌍 MARKET REGIME:\n"
        output += f"   Risk Sentiment: {regime['risk_sentiment']}\n"
        output += f"   Volume Environment: {regime['volume_environment']}\n"
        output += f"   Catalyst Effectiveness: {regime['catalyst_effectiveness']:.1%}\n\n"
        
        # Active Plays
        if status['play_details']:
            output += f"🎯 ACTIVE DAILY PLAYS:\n"
            for symbol, details in status['play_details'].items():
                minutes = int(details['minutes_since_entry'])
                output += f"   {symbol}: {details['catalyst_type']} | Phase: {details['phase']} | "
                output += f"Momentum: {details['momentum_score']:.2f} | {minutes}min ago\n"
        else:
            output += f"🎯 ACTIVE DAILY PLAYS: None\n"
        
        output += f"\n🏛️ Mayordomo ready to orchestrate smallcap daily plays"
        
        return output
        
    except Exception as e:
        return f"Error formatting mayordomo summary: {e}"

    def _evaluate_pyramid_opportunity(self, symbol: str, new_opportunity: Dict) -> Dict[str, Any]:
        """
        Evaluate if we should add to an existing position (pyramid)
        Only allows adding to WINNING positions - never losing ones (anti-martingala)
        
        Args:
            symbol: Symbol to evaluate for pyramid
            new_opportunity: New opportunity data
            
        Returns:
            Dict with pyramid decision and reasoning
        """
        try:
            # Get pyramid configuration
            max_levels = getattr(self.config, 'max_pyramid_levels', 1)
            profit_threshold = getattr(self.config, 'pyramid_profit_threshold', 0.05)
            size_fraction = getattr(self.config, 'pyramid_size_fraction', 0.5)
            cooldown_minutes = getattr(self.config, 'pyramid_cooldown_minutes', 30)
            
            # Get existing position info
            existing_play = self.active_daily_plays.get(symbol, {})
            
            if not existing_play:
                return {
                    'allow_pyramid': False,
                    'reason': 'No existing position found'
                }
            
            # Check pyramid level limits
            current_pyramid_level = existing_play.get('pyramid_level', 1)
            if current_pyramid_level >= max_levels:
                return {
                    'allow_pyramid': False,
                    'reason': f'Max pyramid level {max_levels} already reached'
                }
            
            # Check cooldown period
            entry_time = existing_play.get('entry_time', datetime.now())
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time)
            
            time_since_entry = (datetime.now() - entry_time).total_seconds() / 60
            
            if time_since_entry < cooldown_minutes:
                return {
                    'allow_pyramid': False,
                    'reason': f'Cooldown period: {cooldown_minutes - time_since_entry:.0f}min remaining'
                }
            
            # CRITICAL: Check if position is profitable (anti-martingala)
            entry_price = existing_play.get('entry_price', 0)
            current_price = new_opportunity.get('current_price', 0)
            
            if entry_price <= 0 or current_price <= 0:
                return {
                    'allow_pyramid': False,
                    'reason': 'Invalid price data for profit calculation'
                }
            
            profit_pct = (current_price - entry_price) / entry_price
            
            if profit_pct < profit_threshold:
                return {
                    'allow_pyramid': False,
                    'reason': f'Position must be +{profit_threshold:.1%} profitable. Current: {profit_pct:+.1%}'
                }
            
            # Calculate pyramid position size
            original_size = self._calculate_position_size_from_score(0.6)  # Base size
            pyramid_size = original_size * size_fraction
            
            return {
                'allow_pyramid': True,
                'reason': f'Position +{profit_pct:.1%} profitable, adding {size_fraction:.0%} pyramid',
                'pyramid_size': pyramid_size,
                'profit_pct': profit_pct,
                'pyramid_level': current_pyramid_level + 1
            }
            
        except Exception as e:
            self.logger.error(f"Error evaluating pyramid opportunity for {symbol}: {e}")
            return {
                'allow_pyramid': False,
                'reason': f'Error in pyramid evaluation: {e}'
            }
    
    def clear_active_plays(self, force: bool = False):
        """
        Clear active daily plays - useful for fixing stuck positions
        
        Args:
            force: If True, clear regardless of time. If False, only clear if new day
        """
        if force:
            if hasattr(self, 'active_daily_plays') and self.active_daily_plays:
                previous_plays = list(self.active_daily_plays.keys())
                self.active_daily_plays.clear()
                self.logger.warning(f"🔄 FORCE CLEARED {len(previous_plays)} active daily plays: {', '.join(previous_plays)}")
            else:
                self.logger.info("🔄 No active daily plays to clear")
        else:
            self._reset_daily_stats_if_needed()
    
    def remove_active_play(self, symbol: str, reason: str = "Trade closed"):
        """
        Remove a specific symbol from active daily plays
        
        Args:
            symbol: Symbol to remove
            reason: Reason for removal
        """
        if hasattr(self, 'active_daily_plays') and symbol in self.active_daily_plays:
            del self.active_daily_plays[symbol]
            self.logger.info(f"🔄 Removed {symbol} from active daily plays: {reason}")
        else:
            self.logger.debug(f"🔄 Symbol {symbol} not in active daily plays (already removed or never existed)")
    
    def _check_broker_position_sync(self, symbol: str) -> bool:
        """
        SIMPLE SOLUTION: Quick sync check if position exists in broker
        Designed for smallcaps - simple and fast, no async complexity
        
        Args:
            symbol: Symbol to verify
            
        Returns:
            bool: True if position exists in broker, False otherwise
        """
        try:
            broker = getattr(self, 'broker', None)
            if not broker:
                return True  # Safe mode
            
            # Quick check - get current positions (sync access only)
            if hasattr(broker, 'positions') and broker.positions:
                # Simple dict-based position check
                if isinstance(broker.positions, dict):
                    return symbol in broker.positions
                else:
                    # List-based positions
                    for pos in broker.positions:
                        try:
                            pos_symbol = getattr(pos, 'symbol', '')
                            if pos_symbol == symbol:
                                return True
                        except:
                            continue
                    return False
            else:
                # No positions found = no position exists
                return False
                
        except Exception as e:
            self.logger.debug(f"🔍 Quick broker check failed for {symbol}: {e}")
            return True  # Safe mode on error