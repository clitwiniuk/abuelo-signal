# core/trading_execution_stage.py
"""
Trading Execution Stage - Pipeline Pattern
Minimal IBKR calls for order execution only
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, time
import time as time_module
import uuid
import atexit
from zoneinfo import ZoneInfo

from core.pipeline import PipelineStage
from core.interfaces import Signal, IBroker, Order, OrderSide, OrderType, SignalType
from core.extended_hours_manager import ExtendedHoursManager, MarketSession
from core.database_manager import get_database_manager
from core.commission_calculator import IBKRCommissionCalculator
# Telegram notifications
from notifications import telegram_client


from core.interfaces import Order, OrderSide, OrderType, OrderStatus

class TradingExecutionStage(PipelineStage):
    """
    Stage 3: Trading Execution
    - Minimal IBKR calls (orders only)
    - Batch order processing
    - Position management
    - Risk validation before execution
    """
    
    def __init__(self, broker: IBroker, risk_manager=None, config=None, event_bus=None):
        super().__init__("TradingExecution")
        self.broker = broker
        self.risk_manager = risk_manager
        self.config = config
        self.event_bus = event_bus  # CRITICAL FIX: Add event bus for ML feedback
        
        # Database manager for trade persistence (singleton)
        self.db_manager = get_database_manager()
        
        # Extended hours manager
        self.extended_hours_manager = ExtendedHoursManager()
        
        # Initialize execution stats immediately
        self.execution_stats = {
            'orders_attempted': 0,
            'orders_successful': 0,
            'orders_failed': 0,
            'total_execution_time': 0.0,
            'extended_hours_orders': 0,
            'limit_orders': 0,
            'market_orders': 0
        }
        
        # Position tracking (simplified)
        self.positions = {}
        self.pending_orders = {}
        
        # Trade tracking for database persistence
        self.active_trades = {}  # Maps symbols to active trade records
        
        # Execution settings (MOVED HERE FROM AFTER _format_strategy_name method)
        self.max_concurrent_orders = 3  # Max simultaneous order placement
        self.order_timeout = 10.0  # Max time per order
        
        # Notifications
        self._telegram_enabled = telegram_client.is_enabled()
        self._send_telegram = telegram_client.send_message if self._telegram_enabled else lambda *args, **kwargs: None
        if self._telegram_enabled:
            self.logger.info("📨 Telegram notifications ENABLED")
            # Send startup notification (async to avoid blocking initialization)
            try:
                import threading
                def send_startup_notification():
                    try:
                        self._send_telegram("🚀 Trading system iniciado y en funcionamiento ✅")
                    except Exception as e:
                        self.logger.warning(f"Failed to send startup Telegram notification: {e}")
                
                # Send notification in background thread to avoid blocking
                threading.Thread(target=send_startup_notification, daemon=True).start()
                
                # Register shutdown hook (only if not already registered)
                if not hasattr(TradingExecutionStage, '_telegram_shutdown_registered'):
                    atexit.register(lambda: self._send_telegram("🛑 Trading system detenido"))
                    TradingExecutionStage._telegram_shutdown_registered = True
            except Exception as e:
                self.logger.error(f"Error setting up Telegram notifications: {e}")
        else:
            self.logger.info("📨 Telegram notifications DISABLED")
        
        # Log initialization completion
        self.logger.info(f"💼 TradingExecutionStage initialized: max_concurrent={self.max_concurrent_orders}")
        self.logger.info(f"🕐 Extended hours support: ENABLED")
        self.logger.info(f"💾 Database integration: ENABLED")
    
    def _format_strategy_name(self, strategy_name: str) -> str:
        """Format strategy name for display in Telegram messages"""
        strategy_map = {
            'macdv_smallcaps': 'MACDV-SC',
            'gap_go': 'Gap&Go',
            'volume_breakout': 'VolBreak',
            'explosive_volume': 'ExpVol',
            'daily_plays': 'DailyPlays',
            'optimized_gap_go': 'OptGap',
            'catalyst_momentum': 'CatMom',
            'orb': 'ORB',
            'pmh_breakout': 'PMH',
            'vwap_smallcaps': 'VWAP-SC',
            'vwap_reclaim': 'VWAP-Rec',
            'eod_momentum': 'EOD-Mom',
            'vcp': 'VCP',
            'realistic_strategy_engine': 'Realistic'
        }
        
        # Clean the strategy name
        clean_name = strategy_name.lower().replace('strategy', '').replace('_strategy', '')
        
        # Return mapped name or formatted original
        return strategy_map.get(clean_name, strategy_name.replace('_', ' ').title())
    
    def _calculate_trade_confidence(self, signal: Signal, strategy_name: str) -> float:
        """
        ROBUST calculation of trade confidence - ALWAYS returns a valid confidence

        Args:
            signal: Señal de trading
            strategy_name: Nombre de la estrategia

        Returns:
            float: Confidence entre 0-100 (NUNCA None o NaN)
        """
        try:
            base_confidence = 70.0  # Safe default

            # 1. Try signal.confidence first (primary source)
            if hasattr(signal, 'confidence') and signal.confidence is not None and signal.confidence != 1.0:
                if signal.confidence <= 1.0:
                    base_confidence = signal.confidence * 100
                else:
                    base_confidence = signal.confidence
                self.logger.debug(f"Used signal.confidence: {base_confidence:.1f}% for {signal.symbol}")

            # 2. Fallback to signal.strength
            elif hasattr(signal, 'strength') and signal.strength is not None:
                signal_confidence = signal.strength * 100
                base_confidence = signal_confidence
                self.logger.debug(f"Used signal.strength: {base_confidence:.1f}% for {signal.symbol}")

            # 3. Ensure base_confidence is valid
            if base_confidence is None or base_confidence != base_confidence:  # Check for NaN
                base_confidence = 70.0
            
            # 3. Ajustes por estrategia (basado en estrategias actuales)
            strategy_multipliers = {
                # Estrategias más confiables
                'gap_go': 1.1,
                'macdv_smallcaps': 1.05,
                'daily_plays': 1.05,
                'gap_crap_reversal': 1.0,

                # Estrategias estándar
                'first_day_bounce': 1.0,
                'red_to_green': 0.95,

                # Estrategias más experimentales
                'orb': 0.9,  # ORB menos confiable por ahora

                # Legacy names (backwards compatibility)
                'GapGoStrategy': 1.1,
                'VolumeBreakoutStrategy': 1.05,
                'VWAPReclaimStrategy': 1.0,
                'ExplosiveVolumeStrategy': 0.95,
                'ImprovedSimpleExplosionStrategy': 0.9
            }
            
            multiplier = strategy_multipliers.get(strategy_name, 1.0)
            adjusted_confidence = base_confidence * multiplier
            
            # 4. Ajustes por tipo de señal
            signal_type_adjustments = {
                'ENTRY_LONG': 0,
                'ENTRY_SHORT': -5,  # Shorts generalmente más riesgosos
                'EXIT_LONG': 0,
                'EXIT_SHORT': 0
            }
            
            signal_adjustment = signal_type_adjustments.get(signal.signal_type.value, 0)
            final_confidence = adjusted_confidence + signal_adjustment
            
            # 5. Limitar entre 0-100
            final_confidence = max(0.0, min(100.0, final_confidence))
            
            self.logger.debug(f"Confidence calculated: {final_confidence:.1f}% "
                            f"(base: {base_confidence:.1f}, strategy: {strategy_name}, "
                            f"signal_type: {signal.signal_type.value})")
            
            # 6. Final validation and formatting
            if final_confidence is None or final_confidence != final_confidence:  # Check for NaN again
                final_confidence = 70.0

            return round(final_confidence, 1)

        except Exception as e:
            self.logger.error(f"Error calculating confidence for {signal.symbol}: {e}")
            return 70.0  # ALWAYS return a valid confidence
    
    async def _process(self, signals: List[Signal]) -> Dict[str, Any]:
        """
        Execute trading signals with minimal IBKR interaction
        
        Args:
            signals: List of validated trading signals
            
        Returns:
            Dict with execution results and metrics
        """
        if not signals:
            self.logger.info("📭 No signals to execute")
            return {'orders': [], 'metrics': self.execution_stats}
        
        self.logger.info(f"💼 Executing {len(signals)} trading signals")
        
        # CRITICAL FIX: Update positions BEFORE processing signals to ensure we have current position data for exits
        await self._update_positions()
        
        # DEBUG: Log current positions for exit signal processing
        if self.positions:
            position_symbols = list(self.positions.keys())
            self.logger.info(f"📊 Current positions available for exit: {position_symbols}")
        else:
            self.logger.warning("⚠️ No positions found in execution stage - exit signals may fail")
        
        # Group signals by type for efficient processing
        signal_groups = self._group_signals(signals)
        
        # Ensure execution_stats exists (defensive programming)
        if not hasattr(self, 'execution_stats') or self.execution_stats is None:
            self.logger.warning("⚠️ execution_stats not found, initializing...")
            self.execution_stats = {
                'orders_attempted': 0,
                'orders_successful': 0,
                'orders_failed': 0,
                'total_execution_time': 0.0,
                'extended_hours_orders': 0,
                'limit_orders': 0,
                'market_orders': 0
            }
        
        execution_results = {
            'orders': [],
            'metrics': self.execution_stats.copy(),
            'signal_groups': signal_groups
        }
        
        # Process each signal group
        for signal_type, grouped_signals in signal_groups.items():
            if not grouped_signals:
                continue
                
            self.logger.info(f"🔄 Processing {len(grouped_signals)} {signal_type} signals")
            
            try:
                group_results = await self._execute_signal_group(grouped_signals)
                execution_results['orders'].extend(group_results)
                
            except Exception as e:
                self.logger.error(f"❌ Failed to execute {signal_type} signals: {e}")
        
        # Update positions after execution
        await self._update_positions()
        # DEBUG: STOP ORDERS DESACTIVADOS - Comentado para debugging
        # await self.ensure_position_stops()
        
        # Create detailed summary message
        if execution_results['orders']:
            symbols_traded = [result['signal'].symbol for result in execution_results['orders'] if result]
            summary_msg = f"✅ Executed {len(execution_results['orders'])} orders: {', '.join(symbols_traded)}"
        else:
            summary_msg = f"✅ Execution completed: {len(execution_results['orders'])} orders processed"
        
        self.logger.info(summary_msg)
        # Don't send summary to Telegram - individual order messages are more useful
        
        return execution_results
    
    def _group_signals(self, signals: List[Signal]) -> Dict[str, List[Signal]]:
        """Group signals by type for batch processing"""
        groups = {
            'entry': [],
            'exit': [],
            'stop': []
        }
        
        for signal in signals:
            signal_type_str = str(signal.signal_type).lower()
            
            if 'exit' in signal_type_str:
                groups['exit'].append(signal)
            elif 'stop' in signal_type_str:
                groups['stop'].append(signal)
            else:
                groups['entry'].append(signal)
        
        return groups
    
    async def _execute_signal_group(self, signals: List[Signal]) -> List[Dict[str, Any]]:
        """Execute a group of similar signals"""
        if not signals:
            return []
        
        # Create execution tasks with concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent_orders)
        tasks = []
        
        for signal in signals:
            task = asyncio.create_task(
                self._execute_signal_with_semaphore(semaphore, signal)
            )
            tasks.append(task)
        
        # Wait for all executions with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0  # 30 seconds max for group execution
            )
            
            # Process results
            execution_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Signal execution failed: {result}")
                    self.execution_stats['orders_failed'] += 1
                elif result:
                    execution_results.append(result)
                    self.execution_stats['orders_successful'] += 1
                
                self.execution_stats['orders_attempted'] += 1
            
            return execution_results
            
        except asyncio.TimeoutError:
            self.logger.error("⏰ Signal group execution timed out")
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            return []
    
    async def _execute_signal_with_semaphore(self, semaphore: asyncio.Semaphore, signal: Signal) -> Optional[Dict[str, Any]]:
        """Execute single signal with concurrency control"""
        async with semaphore:
            return await self._execute_signal(signal)
    
    async def _execute_signal(self, signal: Signal) -> Optional[Dict[str, Any]]:
        """Execute a single trading signal"""
        start_time = time_module.time()
        
        try:
            self.logger.debug(f"💼 Executing {signal.signal_type} signal for {signal.symbol}")
            
            # CRITICAL FIX: Check for pending orders to prevent duplicates (ISPC halt bug)
            if signal.symbol in self.pending_orders:
                pending_info = self.pending_orders[signal.symbol]
                self.logger.warning(f"🚫 Order already pending for {signal.symbol}: {pending_info['order_type']} (ID: {pending_info.get('order_id', 'N/A')})")
                self.logger.warning(f"   Pending since: {pending_info.get('timestamp', 'Unknown')} - Skipping duplicate")
                return None
            
            # Convert signal to order
            order = await self._signal_to_order(signal)
            if not order:
                self.logger.warning(f"⚠️ Could not convert signal to order: {signal.symbol}")
                return None
            
            # Apply final risk checks
            if self.risk_manager and not await self._final_risk_check(signal, order):
                self.logger.warning(f"🚫 Signal rejected by final risk check: {signal.symbol}")
                return None
            
            # Execute order with timeout
            try:
                # CRITICAL FIX: Register pending order BEFORE sending to prevent duplicates
                self.pending_orders[signal.symbol] = {
                    'order_type': f"{order.side.value}_{signal.signal_type.value}",
                    'quantity': order.quantity,
                    'timestamp': datetime.now().isoformat(),
                    'order_id': None  # Will be filled after successful placement
                }
                
                order_id = await asyncio.wait_for(
                    self.broker.place_order(order),  # Pass the Order object directly
                    timeout=self.order_timeout
                )
                
                # Update pending order with actual order ID
                if signal.symbol in self.pending_orders:
                    self.pending_orders[signal.symbol]['order_id'] = order_id
                
                execution_time = time_module.time() - start_time
                
                # Create detailed execution message with enhanced strategy info
                strategy_name = getattr(signal, 'strategy_name', 'Unknown')
                order_side = order.side.value
                order_type_str = order.order_type.value if hasattr(order.order_type, 'value') else str(order.order_type)
                
                # Get confidence safely with fallback - use ML Engine confidence if available
                if hasattr(signal, 'confidence') and signal.confidence is not None:
                    confidence = signal.confidence if signal.confidence > 1.0 else signal.confidence
                else:
                    confidence = getattr(signal, 'strength', 1.0)
                
                # Enhanced strategy display
                strategy_display = self._format_strategy_name(strategy_name)
                
                # Get additional signal context from metadata
                metadata = getattr(signal, 'metadata', {})
                signal_context = getattr(signal, 'context', {})
                
                # Extract key information from metadata and context
                reason = metadata.get('reason', signal_context.get('reason', ''))
                setup_type = metadata.get('setup_type', signal_context.get('setup_type', ''))
                gap_percent = metadata.get('gap_percent', '')
                volume_ratio = metadata.get('volume_ratio', '')
                pattern = metadata.get('pattern', '')
                
                # Build enhanced message
                base_msg = f"{'📈' if order_side == 'BUY' else '📉'} {signal.symbol} {order_side} {order.quantity}@${order.price:.2f}"
                
                # Add strategy and confidence
                strategy_info = f"[{strategy_display}] conf:{confidence:.1%}"
                
                # Add context details if available
                context_details = []
                
                if setup_type:
                    context_details.append(setup_type)
                
                if gap_percent:
                    context_details.append(f"Gap:{gap_percent:.1f}%")
                    
                if volume_ratio:
                    context_details.append(f"Vol:{volume_ratio:.1f}x")
                    
                if pattern:
                    context_details.append(pattern)
                    
                if reason and reason != setup_type:
                    context_details.append(reason)
                
                # Combine context details
                if context_details:
                    strategy_info += f" ({', '.join(context_details)})"
                
                execution_msg = f"{base_msg} {strategy_info}"
                
                self.logger.info(f"✅ Order executed: {signal.symbol} {signal.signal_type} -> {order_id}")
                self._send_telegram(execution_msg)
                
                # Save trade to database
                await self._save_trade_to_database(signal, order, order_id, execution_time)
                
                # Process ALL delayed orders if this was from a delayed entry
                if hasattr(self, 'mayordomo'):
                    delayed_orders = self.mayordomo.process_all_delayed_orders(signal.symbol)
                    
                    # Create delayed stop order
                    if delayed_orders['stop_order']:
                        self.logger.info(f"🛡️  Creating delayed stop order for {signal.symbol}")
                        await self._create_delayed_stop_order(delayed_orders['stop_order'])
                    
                    # Initialize delayed trailing stop
                    if delayed_orders['trailing_stop']:
                        self.logger.info(f"📈 Initializing delayed trailing stop for {signal.symbol}")
                        await self._initialize_delayed_trailing_stop(signal.symbol, delayed_orders['trailing_stop'])
                    
                    # Set delayed take profit target
                    if delayed_orders['take_profit']:
                        self.logger.info(f"🎯 Setting delayed take profit for {signal.symbol}")
                        await self._set_delayed_take_profit(signal.symbol, delayed_orders['take_profit'])
                    
                    # Register with ML exit engine
                    if delayed_orders['ml_exit']:
                        self.logger.info(f"🧠 Registering delayed ML exit for {signal.symbol}")
                        await self._register_delayed_ml_exit(signal.symbol, delayed_orders['ml_exit'])
                
                # CRITICAL FIX: Remove from pending orders after successful execution
                if signal.symbol in self.pending_orders:
                    del self.pending_orders[signal.symbol]
                    self.logger.debug(f"🧹 Cleared pending order for {signal.symbol}")
                
                return {
                    'signal': signal,
                    'order': order,
                    'order_id': order_id,
                    'execution_time': execution_time,
                    'status': 'executed'
                }
                
            except asyncio.TimeoutError:
                execution_time = time_module.time() - start_time
                self.logger.error(f"⏰ Order execution timeout for {signal.symbol} after {execution_time:.2f}s")
                # CRITICAL FIX: Remove from pending orders on timeout
                if signal.symbol in self.pending_orders:
                    del self.pending_orders[signal.symbol]
                    self.logger.debug(f"🧹 Cleared pending order for {signal.symbol} (timeout)")
                return None
            
        except Exception as e:
            execution_time = time_module.time() - start_time
            self.logger.error(f"❌ Order execution failed for {signal.symbol}: {e}")
            # CRITICAL FIX: Remove from pending orders on error
            if signal.symbol in self.pending_orders:
                del self.pending_orders[signal.symbol]
                self.logger.debug(f"🧹 Cleared pending order for {signal.symbol} (error)")
            return None
    
    async def _signal_to_order(self, signal: Signal) -> Optional[Order]:
        """Convert signal to order with extended hours support"""
        try:
            # Get current market session
            current_session = self.extended_hours_manager.get_market_session()
            
            # Determine order side
            if signal.signal_type in [SignalType.LONG]:
                side = OrderSide.BUY
            elif signal.signal_type in [SignalType.SHORT, SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                side = OrderSide.SELL
            else:
                self.logger.warning(f"Unknown signal type: {signal.signal_type}")
                return None
            
            # Determine quantity
            if signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                # Exit position - get quantity from position tracking
                position = self.positions.get(signal.symbol)
                if not position:
                    # Position might have been closed externally - check and clean up
                    self.logger.info(f"🔄 Position {signal.symbol} not found for exit - checking for external closure")
                    
                    # Clean up any stale tracking
                    if signal.symbol in self.active_trades:
                        self.logger.info(f"🧹 Cleaning up stale active trade for {signal.symbol}")
                        self.active_trades.pop(signal.symbol, None)
                    
                    self.logger.debug(f"Available positions: {list(self.positions.keys())}")
                    return None
                quantity = abs(position.get('quantity', 0))
                self.logger.info(f"📤 Exit order for {signal.symbol}: quantity={quantity} from position={position}")
            else:
                # New position - calculate size
                quantity = self._calculate_position_size(signal)
            
            if quantity <= 0:
                self.logger.warning(f"Invalid quantity for {signal.symbol}: {quantity}")
                return None
            
            # Determine order type based on market session
            order_type = self.extended_hours_manager.get_order_type(current_session)
            
            # Get market data for limit price calculation
            market_data = getattr(signal, 'market_data', None)
            if not market_data:
                # Fallback: create minimal market data from signal
                from core.interfaces import MarketData
                from datetime import datetime
                market_data = MarketData(
                    symbol=signal.symbol,
                    timestamp=datetime.now(),
                    open=signal.price, high=signal.price, low=signal.price, close=signal.price,
                    volume=0, last_price=signal.price
                )
            
            # Calculate limit price if needed
            limit_price = None
            if order_type == OrderType.LIMIT:
                limit_price, reasoning = self.extended_hours_manager.calculate_limit_price(
                    market_data, side, current_session
                )
                self.logger.info(f"🎯 {signal.symbol} {current_session.value}: {reasoning} → ${limit_price:.4f}")
                self.execution_stats['limit_orders'] += 1
                
                if current_session in [MarketSession.PREMARKET, MarketSession.AFTERHOURS]:
                    self.execution_stats['extended_hours_orders'] += 1
            else:
                self.execution_stats['market_orders'] += 1
            
            # Validate order for extended hours
            is_valid, validation_msg = self.extended_hours_manager.validate_extended_hours_order(
                market_data, order_type, limit_price, current_session
            )
            
            if not is_valid:
                self.logger.error(f"❌ Order validation failed for {signal.symbol}: {validation_msg}")
                return None
            
            self.logger.debug(f"✅ Order validation passed for {signal.symbol}: {validation_msg}")
            
            # Create order
            order = Order(
                order_id="",
                symbol=signal.symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=limit_price if order_type == OrderType.LIMIT else signal.price
            )
            
            # Log order details
            order_details = f"{side.value} {quantity} {signal.symbol} @ "
            if order_type == OrderType.LIMIT:
                order_details += f"LIMIT ${limit_price:.4f}"
            else:
                order_details += f"MARKET"
            order_details += f" ({current_session.value})"
            
            self.logger.info(f"📋 Created order: {order_details}")
            
            return order
            
        except Exception as e:
            self.logger.error(f"Error converting signal to order for {signal.symbol}: {e}")
            return None
    
    def _calculate_position_size(self, signal: Signal) -> int:
        """Calculate position size based on max_position_value from config and optional confidence-based sizing"""
        try:
            # Get max position value from config (default 200.0 per config.ini)
            max_position_value = getattr(self.config, 'max_position_value', 200.0)
            min_quantity = getattr(self.config, 'min_quantity', 10)

            # Check if confidence-based sizing is enabled
            enable_confidence_sizing = getattr(self.config, 'enable_confidence_sizing', False)

            if enable_confidence_sizing:
                # Calculate confidence for this signal
                confidence = self._calculate_trade_confidence(signal, getattr(signal, 'strategy', 'Unknown'))

                # Get confidence sizing parameters
                min_multiplier = getattr(self.config, 'confidence_sizing_min_multiplier', 0.5)
                max_multiplier = getattr(self.config, 'confidence_sizing_max_multiplier', 1.5)
                threshold_low = getattr(self.config, 'confidence_sizing_threshold_low', 60.0)
                threshold_high = getattr(self.config, 'confidence_sizing_threshold_high', 85.0)

                # Calculate confidence multiplier
                if confidence <= threshold_low:
                    # Low confidence: reduce size
                    multiplier = min_multiplier
                    self.logger.info(f"📉 Low confidence ({confidence:.1f}%) - reducing position size by {(1-multiplier)*100:.0f}%")
                elif confidence >= threshold_high:
                    # High confidence: increase size
                    multiplier = max_multiplier
                    self.logger.info(f"📈 High confidence ({confidence:.1f}%) - increasing position size by {(multiplier-1)*100:.0f}%")
                else:
                    # Normal confidence: linear interpolation between 1.0 and multipliers
                    if confidence < 75.0:  # Between low threshold and 75%
                        range_size = 75.0 - threshold_low
                        position_in_range = confidence - threshold_low
                        multiplier = min_multiplier + (1.0 - min_multiplier) * (position_in_range / range_size)
                    else:  # Between 75% and high threshold
                        range_size = threshold_high - 75.0
                        position_in_range = confidence - 75.0
                        multiplier = 1.0 + (max_multiplier - 1.0) * (position_in_range / range_size)

                    self.logger.info(f"📊 Medium confidence ({confidence:.1f}%) - position size multiplier: {multiplier:.2f}")

                # Apply confidence multiplier to max position value
                adjusted_max_value = max_position_value * multiplier
                position_size = int(adjusted_max_value / signal.price)

                self.logger.info(f"🎯 Confidence-based sizing: ${max_position_value:.0f} → ${adjusted_max_value:.0f} (confidence: {confidence:.1f}%)")
            else:
                # Standard sizing without confidence adjustment
                position_size = int(max_position_value / signal.price)

            # Respect min_quantity from config, no arbitrary max limit
            return max(min_quantity, position_size)

        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 10  # Default fallback
    
    async def _final_risk_check(self, signal: Signal, order: Order) -> bool:
        """Final risk validation before execution"""
        try:
            if self.risk_manager:
                # CRITICAL FIX: Check if this is an exit signal to allow exit orders to bypass position limits
                is_exit_order = signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]
                
                # Use the new method that understands exit context
                if hasattr(self.risk_manager, 'validate_order_with_signal_context'):
                    return await self.risk_manager.validate_order_with_signal_context(order, is_exit_order=is_exit_order)
                else:
                    # Fallback to original method
                    return await self.risk_manager.validate_order(order)
            return True
        except Exception as e:
            self.logger.error(f"Risk check error: {e}")
            return False  # Reject on error
    
    async def _update_positions(self):
        """Update position tracking with minimal IBKR calls"""
        try:
            # Always update positions to catch external changes (like manual closes)
            positions = await asyncio.wait_for(
                self.broker.get_positions(),
                timeout=5.0  # Quick timeout
            )
            
            # Update internal position tracking
            self.positions = {}
            for symbol, position in positions.items():
                # Try to get strategy from active_trades if available
                strategy_name = None
                if symbol in self.active_trades:
                    strategy_name = self.active_trades[symbol].get('strategy')
                if not strategy_name and hasattr(self, 'db_manager'):
                    strategy_name = self.db_manager.get_latest_strategy(symbol)
                self.positions[symbol] = {
                    'quantity': position.quantity,
                    'avg_price': position.avg_price,
                    'market_value': position.market_value,
                    'strategy': strategy_name or 'Multi-Strategy'
                }
            
            # Log position updates (only if there are changes)
            position_count = len(self.positions)
            if position_count > 0:
                self.logger.debug(f"📊 Updated positions: {position_count} active")
            
            # Clean up active trades for positions that no longer exist
            # SAFEGUARD: Only consider positions closed if they've been active for at least 60 seconds
            # This prevents premature closure due to broker data delays
            closed_symbols = set(self.active_trades.keys()) - set(positions.keys())
            for symbol in closed_symbols:
                if symbol in self.active_trades:
                    active_trade = self.active_trades[symbol]
                    entry_time = active_trade['entry_time']

                    # Handle different entry_time formats
                    if isinstance(entry_time, (tuple, list)) and len(entry_time) >= 6:
                        entry_time = datetime(*entry_time[:6])
                    elif isinstance(entry_time, str):
                        entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))

                    # Calculate time since trade creation
                    time_since_entry = (datetime.now() - entry_time).total_seconds()

                    # Only close if trade has been active for at least 60 seconds
                    if time_since_entry >= 60:
                        self.logger.info(f"🚪 Position closed externally: {symbol} (active for {time_since_entry:.0f}s)")
                        # Handle external close - update database with exit data and close reason
                        await self._handle_external_close(symbol, active_trade)
                        del self.active_trades[symbol]
                    else:
                        self.logger.debug(f"⏳ Position {symbol} not in broker data, but only {time_since_entry:.0f}s old - waiting for broker sync")
                
        except asyncio.TimeoutError:
            self.logger.warning("⏰ Position update timeout")
        except Exception as e:
            self.logger.error(f"❌ Position update failed: {e}")
    
    async def _handle_external_close(self, symbol: str, active_trade: Dict[str, Any]):
        """Handle externally closed position - update database with exit data"""
        try:
            self.logger.info(f"🔄 Processing external close for {symbol}")
            
            # Get current market price for exit price estimation
            try:
                market_data = await self.broker.get_market_data(symbol)
                current_price = market_data.price if market_data else active_trade['entry_price']
            except:
                current_price = active_trade['entry_price']  # Fallback to entry price
            
            # Calculate exit time and duration
            entry_time_raw = active_trade['entry_time']
            exit_time = datetime.now()

            # Handle entry_time format conversion (fixes volume_breakout tuple issue)
            if isinstance(entry_time_raw, (tuple, list)) and len(entry_time_raw) >= 6:
                entry_time = datetime(*entry_time_raw[:6])
            elif isinstance(entry_time_raw, str):
                entry_time = datetime.fromisoformat(entry_time_raw.replace('Z', '+00:00'))
            else:
                entry_time = entry_time_raw  # Assume it's already a datetime

            duration_minutes = int((exit_time - entry_time).total_seconds() / 60)
            
            # Get trade parameters
            entry_price = active_trade['entry_price']
            quantity = active_trade['quantity']
            side = active_trade['side']
            
            # Calculate PnL
            if side == 'BUY':
                pnl = (current_price - entry_price) * quantity
            else:
                pnl = (entry_price - current_price) * quantity
            
            # Estimate commission for round trip (buy + sell)
            commission_calc = IBKRCommissionCalculator()
            commission, commission_breakdown = commission_calc.calculate_round_trip_commission(
                quantity, entry_price, current_price
            )

            net_pnl = pnl - commission
            
            # Determine close reason based on price movement and time
            close_reason = self._determine_close_reason(
                entry_price, current_price, side, entry_time, exit_time, duration_minutes
            )
            
            # Create updated trade data
            trade_data = {
                'trade_id': active_trade['trade_id'],
                'symbol': symbol,
                'strategy': active_trade['strategy'],
                'side': side,
                'quantity': quantity,
                'entry_price': entry_price,
                'exit_price': current_price,
                'entry_time': entry_time,
                'exit_time': exit_time,
                'duration_minutes': duration_minutes,
                'pnl': round(net_pnl, 2),
                'commission': round(commission, 2),
                'status': 'CLOSED',
                'confidence': active_trade.get('confidence'),  # CRITICAL: Preserve confidence from entry
                'notes': f"{active_trade.get('notes', '')} | External close: {close_reason}".strip(' |')
            }
            
            # Save to database
            success = self.db_manager.save_trade(trade_data)
            if success:
                self.logger.info(f"💾 External close saved: {symbol} - {close_reason} - Net PnL: ${net_pnl:.2f}")
                
                # Emit position closed event for ML feedback
                if self.event_bus:
                    try:
                        from core.interfaces import Position
                        position = Position(
                            symbol=symbol,
                            quantity=quantity,
                            avg_price=entry_price,
                            market_value=current_price * quantity,
                            realized_pnl=net_pnl
                        )
                        
                        from core.events import create_position_event, EventTypes
                        event = create_position_event(position, EventTypes.POSITION_CLOSED)
                        await self.event_bus.publish(event)
                        
                        self.logger.info(f"📡 ML Feedback: External close event emitted for {symbol}")
                        
                    except Exception as e:
                        self.logger.error(f"❌ Failed to emit external close event: {e}")
            else:
                self.logger.error(f"❌ Failed to save external close for {symbol}")
                
        except Exception as e:
            self.logger.error(f"❌ Error handling external close for {symbol}: {e}")
    
    def _determine_close_reason(self, entry_price: float, exit_price: float, side: str, 
                              entry_time: datetime, exit_time: datetime, duration_minutes: int) -> str:
        """Determine the reason for position close based on price movement and timing"""
        try:
            # Calculate price change percentage
            if side == 'BUY':
                price_change_pct = (exit_price - entry_price) / entry_price
            else:
                price_change_pct = (entry_price - exit_price) / entry_price
            
            # Check if it's end of day close (after 15:50 EST)
            exit_time_et = exit_time.astimezone(ZoneInfo('US/Eastern'))
            if exit_time_et.time() >= time(15, 50):
                return f"End of day close at 15:50+ ET (PnL: {price_change_pct:+.1%})"
            
            # Check for stop loss (significant loss)
            if price_change_pct <= -0.05:  # 5% or more loss
                return f"Stop loss triggered ({price_change_pct:+.1%})"
            
            # Check for take profit (significant gain)
            if price_change_pct >= 0.08:  # 8% or more gain
                return f"Take profit target hit ({price_change_pct:+.1%})"
            
            # Check for trailing stop (moderate gain but closed)
            if 0.03 <= price_change_pct < 0.08:
                return f"Trailing stop activated ({price_change_pct:+.1%})"
            
            # Check for quick exit (very short duration)
            if duration_minutes <= 15:
                return f"Quick exit after {duration_minutes}min ({price_change_pct:+.1%})"
            
            # Check for extended hold (long duration)
            if duration_minutes >= 300:  # 5+ hours
                return f"Extended hold closure after {duration_minutes//60}h {duration_minutes%60}min ({price_change_pct:+.1%})"
            
            # Default case
            return f"Position closed ({price_change_pct:+.1%} after {duration_minutes}min)"
            
        except Exception as e:
            self.logger.error(f"Error determining close reason: {e}")
            return "External close - reason unknown"
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics with extended hours info"""
        # Ensure execution_stats exists (defensive programming)
        if not hasattr(self, 'execution_stats') or self.execution_stats is None:
            self.logger.warning("⚠️ execution_stats not found in get_execution_stats, initializing...")
            self.execution_stats = {
                'orders_attempted': 0,
                'orders_successful': 0,
                'orders_failed': 0,
                'total_execution_time': 0.0,
                'extended_hours_orders': 0,
                'limit_orders': 0,
                'market_orders': 0
            }
        
        stats = self.execution_stats.copy()
        if stats['orders_attempted'] > 0:
            stats['success_rate'] = stats['orders_successful'] / stats['orders_attempted']
            stats['limit_order_percentage'] = (stats['limit_orders'] / stats['orders_attempted']) * 100
            stats['extended_hours_percentage'] = (stats['extended_hours_orders'] / stats['orders_attempted']) * 100
        else:
            stats['success_rate'] = 0.0
            stats['limit_order_percentage'] = 0.0
            stats['extended_hours_percentage'] = 0.0
        stats['active_positions'] = len(self.positions)
        session_info = self.extended_hours_manager.get_session_info()
        stats['current_session'] = session_info['current_session']
        stats['us_time'] = session_info['us_time']
        stats['requires_limit_orders'] = session_info['requires_limit_orders']
        return stats

    # === STOP ORDER MANAGEMENT ===
    async def ensure_position_stops(self, stop_loss_pct: float = 0.05) -> None:
        """Ensure every open position has a protective stop order at the broker."""
        try:
            if not self.broker or not self.broker.is_connected():
                self.logger.warning("Broker not connected – cannot verify stop orders")
                return
            
            # Get current positions directly from broker
            broker_positions = await self.broker.get_positions()
            if not broker_positions:
                self.logger.debug("No positions found at broker - no stops needed")
                return
                
            open_orders = await self.broker.get_orders()
            self.logger.info(f"🔍 Checking stops for {len(broker_positions)} positions")
            
            for symbol, pos in broker_positions.items():
                qty = pos.get('quantity', 0) if isinstance(pos, dict) else getattr(pos, 'quantity', 0)
                if qty == 0:
                    continue
                if self._has_active_stop(symbol, open_orders):
                    continue  # already protected
                
                # Check if this symbol has delayed entries - if so, delay stop order creation
                if hasattr(self, 'mayordomo') and self.mayordomo.should_delay_stop_order(symbol):
                    self.logger.info(f"🛡️  Delaying stop order for {symbol} - entry is delayed")
                    
                    # Register the stop order to be created later
                    stop_order_info = {
                        'symbol': symbol,
                        'quantity': abs(qty),
                        'position_side': 'LONG' if qty > 0 else 'SHORT',
                        'avg_price': pos['avg_price'] if isinstance(pos, dict) else pos.avg_price,
                        'stop_loss_pct': stop_loss_pct
                    }
                    self.mayordomo.register_delayed_stop_order(symbol, stop_order_info)
                    continue
                
                if qty > 0:
                    avg_price = pos['avg_price'] if isinstance(pos, dict) else pos.avg_price
                    stop_price = round(avg_price * (1 - stop_loss_pct), 2)
                    side = OrderSide.SELL
                else:
                    avg_price = pos['avg_price'] if isinstance(pos, dict) else pos.avg_price
                    stop_price = round(avg_price * (1 + stop_loss_pct), 2)
                    side = OrderSide.BUY
                await self._send_stop_order(symbol, abs(qty), stop_price, side)
        except Exception as e:
            self.logger.error(f"Error ensuring stop orders: {e}")

    def _has_active_stop(self, symbol: str, open_orders: list[Order]) -> bool:
        """Return True if an active stop order for symbol exists."""
        for o in open_orders:
            if o.symbol == symbol and o.order_type == OrderType.STOP and o.status not in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}:
                return True
        return False

    async def _send_stop_order(self, symbol: str, quantity: int, stop_price: float, side: OrderSide) -> None:
        """Submit a stop order via broker adapter."""
        try:
            # Create Order object for stop order
            stop_order = Order(
                order_id="",  # Will be assigned by broker
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=OrderType.STOP,
                price=None,
                stop_price=stop_price,
                timestamp=datetime.now()
            )
            
            order_id = await self.broker.place_order(stop_order)
            
            # Get strategy name from the original position if available
            strategy_name = "Unknown"
            try:
                # Try to get strategy from database for this symbol
                db_manager = get_database_manager()
                open_trades = db_manager.get_open_trades()
                for trade in open_trades:
                    if trade.get('symbol') == symbol and trade.get('status') == 'OPEN':
                        strategy_name = self._format_strategy_name(trade.get('strategy', 'Unknown'))
                        break
            except Exception as e:
                self.logger.debug(f"Could not retrieve strategy for stop order: {e}")
            
            msg = f"🛡️ Stop order placed for {symbol} @ {stop_price} (qty {quantity}) [{strategy_name}]"
            self.logger.info(msg)
            self._send_telegram(msg)
        except Exception as e:
            self.logger.error(f"Failed to place stop order for {symbol}: {e}")
    
    async def _create_delayed_stop_order(self, stop_info: Dict) -> None:
        """Create a stop order from delayed stop order info"""
        try:
            symbol = stop_info['symbol']
            quantity = stop_info['quantity']
            avg_price = stop_info['avg_price']
            stop_loss_pct = stop_info['stop_loss_pct']
            position_side = stop_info['position_side']
            
            if position_side == 'LONG':
                stop_price = round(avg_price * (1 - stop_loss_pct), 2)
                side = OrderSide.SELL
            else:
                stop_price = round(avg_price * (1 + stop_loss_pct), 2)
                side = OrderSide.BUY
            
            self.logger.info(f"🛡️  Creating delayed stop order: {symbol} @ {stop_price} for {position_side} position")
            await self._send_stop_order(symbol, quantity, stop_price, side)
            
        except Exception as e:
            self.logger.error(f"Failed to create delayed stop order: {e}")
    
    async def _initialize_delayed_trailing_stop(self, symbol: str, trailing_info: Dict) -> None:
        """Initialize a trailing stop from delayed trailing stop info"""
        try:
            # Here we would initialize the trailing stop mechanism
            # This could involve registering with the stop loss manager
            if hasattr(self, 'stop_loss_manager'):
                self.stop_loss_manager.register_delayed_trailing_stop(symbol, trailing_info)
            
            self.logger.info(f"📈 Initialized delayed trailing stop for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize delayed trailing stop for {symbol}: {e}")
    
    async def _set_delayed_take_profit(self, symbol: str, profit_info: Dict) -> None:
        """Set a take profit target from delayed profit info"""
        try:
            take_profit_price = profit_info.get('target_price')
            take_profit_pct = profit_info.get('target_pct', 0.08)  # Default 8%
            
            # Get current position to calculate target
            if hasattr(self, 'broker') and self.broker:
                positions = await self.broker.get_positions()
                if symbol in positions:
                    pos = positions[symbol]
                    entry_price = pos.get('avg_price') if isinstance(pos, dict) else pos.avg_price
                    
                    if not take_profit_price:
                        take_profit_price = entry_price * (1 + take_profit_pct)
                    
                    # Create take profit order
                    quantity = abs(pos.get('quantity', 0) if isinstance(pos, dict) else pos.quantity)
                    
                    profit_order = Order(
                        order_id="",
                        symbol=symbol,
                        side=OrderSide.SELL,  # Assuming long positions
                        quantity=quantity,
                        order_type=OrderType.LIMIT,
                        price=take_profit_price,
                        timestamp=datetime.now()
                    )
                    
                    await self.broker.place_order(profit_order)
                    self.logger.info(f"🎯 Take profit order placed for {symbol} @ ${take_profit_price:.2f}")
            
        except Exception as e:
            self.logger.error(f"Failed to set delayed take profit for {symbol}: {e}")
    
    async def _register_delayed_ml_exit(self, symbol: str, ml_exit_info: Dict) -> None:
        """Register position with ML exit engine from delayed ML exit info"""
        try:
            # Here we would register the position with the ML exit engine
            if hasattr(self, 'ml_exit_engine'):
                self.ml_exit_engine.register_delayed_position(symbol, ml_exit_info)
            
            self.logger.info(f"🧠 Registered {symbol} with delayed ML exit engine")
            
        except Exception as e:
            self.logger.error(f"Failed to register delayed ML exit for {symbol}: {e}")
    
    async def _save_trade_to_database(self, signal: Signal, order: Order, order_id: str, execution_time: float):
        """Save trade execution to database"""
        try:
            # Determine strategy name from signal metadata, signal attributes, or config
            strategy_name = None
            
            # Try to get from signal metadata first (Multi-Strategy puts it there)
            if hasattr(signal, 'metadata') and signal.metadata:
                strategy_name = signal.metadata.get('strategy_name')
            
            # Fallback to signal attributes
            if not strategy_name:
                strategy_name = getattr(signal, 'strategy_name', None) or getattr(signal, 'strategy', None)
            
            # CRITICAL FIX: For exit signals, try to get strategy from existing active trade
            is_exit = signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]
            if is_exit and (not strategy_name or strategy_name == "ML_MultiStrategy_Engine"):
                # Try to get from active trades
                if signal.symbol in self.active_trades:
                    original_strategy = self.active_trades[signal.symbol].get('strategy')
                    if original_strategy and original_strategy != "ML_MultiStrategy_Engine":
                        strategy_name = original_strategy
                        self.logger.info(f"📊 Using original strategy for exit: {signal.symbol} -> {strategy_name}")
                
                # Try to get from database as fallback
                if not strategy_name or strategy_name == "ML_MultiStrategy_Engine":
                    try:
                        db_strategy = self.db_manager.get_latest_strategy(signal.symbol) if hasattr(self, 'db_manager') else None
                        if db_strategy and db_strategy != "ML_MultiStrategy_Engine":
                            strategy_name = db_strategy
                            self.logger.info(f"📊 Using database strategy for exit: {signal.symbol} -> {strategy_name}")
                    except Exception as e:
                        self.logger.debug(f"Could not get strategy from database: {e}")
            
            # Final fallback
            if not strategy_name:
                strategy_name = getattr(self.config, 'strategy', 'Multi-Strategy')
            
            # Generate unique trade ID
            trade_id = f"{signal.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Determine if this is an entry or exit trade
            is_exit = signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]
            
            if is_exit:
                # This is an exit trade - update existing trade record
                await self._handle_exit_trade(signal, order, order_id, trade_id, strategy_name)
            else:
                # This is an entry trade - create new trade record
                await self._handle_entry_trade(signal, order, order_id, trade_id, strategy_name)
            
            self.logger.info(f"💾 Trade saved to database: {trade_id} ({signal.symbol})")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to save trade to database: {e}")
    
    async def _handle_entry_trade(self, signal: Signal, order: Order, order_id: str, trade_id: str, strategy_name: str):
        """Handle entry trade - create new trade record"""
        try:
            # Calculate entry commission
            entry_commission, commission_breakdown = IBKRCommissionCalculator.calculate_commission(
                quantity=order.quantity,
                price=order.price,
                side=order.side.value,
                plan='tiered'  # Default to tiered, could be configurable
            )
            
            # ALWAYS use the robust confidence calculation to ensure consistency
            # This eliminates the race condition and ensures every trade has valid confidence
            confidence = self._calculate_trade_confidence(signal, strategy_name)

            # Log confidence source for debugging
            if hasattr(signal, 'confidence') and signal.confidence is not None and signal.confidence != 1.0:
                signal_conf = signal.confidence * 100 if signal.confidence <= 1.0 else signal.confidence
                self.logger.debug(f"Signal had confidence {signal_conf:.1f}%, calculated: {confidence:.1f}% for {signal.symbol}")
            else:
                self.logger.debug(f"Calculated confidence: {confidence:.1f}% for {signal.symbol} (no signal confidence)")

            # Extract order flow data from signal metadata
            order_flow_data = self._extract_order_flow_data(signal)

            trade_data = {
                'trade_id': trade_id,
                'symbol': signal.symbol,
                'strategy': strategy_name,
                'side': order.side.value,
                'quantity': order.quantity,
                'entry_price': order.price,
                'entry_time': datetime.now(),
                'commission': entry_commission,  # Store entry commission
                'status': 'OPEN',
                'confidence': confidence,  # Add confidence to trade data
                'notes': f"Entry signal: {signal.signal_type.value}, Confidence: {confidence}%, Order ID: {order_id}, Commission: ${entry_commission:.2f}",
                # Add order flow fields
                **order_flow_data
            }
            
            # Save to database
            success = self.db_manager.save_trade(trade_data)
            if success:
                # Track active trade for potential exit
                self.active_trades[signal.symbol] = {
                    'trade_id': trade_id,
                    'entry_time': trade_data['entry_time'],
                    'entry_price': order.price,
                    'quantity': order.quantity,
                    'side': order.side.value,
                    'strategy': strategy_name,
                    'entry_commission': entry_commission,
                    'confidence': confidence,  # CRITICAL: Store confidence for exit updates
                    'notes': trade_data.get('notes', '')  # Store notes for exit updates
                }
                self.logger.info(f"📊 New trade opened: {trade_id} - {signal.symbol} {order.side.value} {order.quantity}@${order.price} (Commission: ${entry_commission:.2f})")
            
        except Exception as e:
            self.logger.error(f"❌ Error handling entry trade: {e}")
    
    async def _handle_exit_trade(self, signal: Signal, order: Order, order_id: str, trade_id: str, strategy_name: str):
        """Handle exit trade - update existing trade record"""
        try:
            # Look for active trade for this symbol
            if signal.symbol in self.active_trades:
                active_trade = self.active_trades[signal.symbol]
                
                # Calculate trade metrics
                entry_time = active_trade['entry_time']
                exit_time = datetime.now()
                duration_minutes = int((exit_time - entry_time).total_seconds() / 60)
                
                # Calculate exit commission and total commission
                exit_commission, exit_breakdown = IBKRCommissionCalculator.calculate_commission(
                    quantity=active_trade['quantity'],
                    price=order.price,
                    side='SELL' if active_trade['side'] == 'BUY' else 'BUY',  # Opposite of entry
                    plan='tiered'
                )
                
                # Total commission = entry + exit
                entry_commission = active_trade.get('entry_commission', 0.0)
                total_commission = entry_commission + exit_commission
                
                # Calculate PnL (simplified - assumes long positions for now)
                entry_price = active_trade['entry_price']
                exit_price = order.price
                quantity = active_trade['quantity']
                
                if active_trade['side'] == 'BUY':  # Long position
                    gross_pnl = (exit_price - entry_price) * quantity
                else:  # Short position
                    gross_pnl = (entry_price - exit_price) * quantity
                
                # Net PnL after commissions
                net_pnl = gross_pnl - total_commission
                
                # Update trade record
                trade_data = {
                    'trade_id': active_trade['trade_id'],
                    'symbol': signal.symbol,
                    'strategy': active_trade['strategy'],
                    'side': active_trade['side'],
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'duration_minutes': duration_minutes,
                    'pnl': round(net_pnl, 2),  # Net PnL after commissions
                    'commission': round(total_commission, 2),  # Total round-trip commission
                    'status': 'CLOSED',
                    'confidence': active_trade.get('confidence'),  # CRITICAL: Preserve confidence from entry
                    'notes': f"Exit signal: {signal.signal_type.value}, Order ID: {order_id}, Entry Commission: ${entry_commission:.2f}, Exit Commission: ${exit_commission:.2f}, Total Commission: ${total_commission:.2f}"
                }
                
                # Save updated trade to database
                success = self.db_manager.save_trade(trade_data)
                if success:
                    # CRITICAL FIX: Emit position_closed event for ML feedback
                    if self.event_bus:
                        try:
                            # Create position object with PnL for ML feedback
                            from core.interfaces import Position
                            position = Position(
                                symbol=signal.symbol,
                                quantity=quantity,
                                avg_price=entry_price,
                                market_value=exit_price * quantity,
                                realized_pnl=net_pnl  # Critical for ML learning (net after commissions)
                            )
                            
                            # Import event creation function
                            from core.events import create_position_event, EventTypes
                            event = create_position_event(position, EventTypes.POSITION_CLOSED)
                            await self.event_bus.publish(event)
                            
                            self.logger.info(f"📡 ML Feedback: position_closed event emitted for {signal.symbol} (Net PnL: ${net_pnl:.2f})")
                            
                        except Exception as e:
                            self.logger.error(f"❌ Failed to emit position_closed event: {e}")
                    
                    # Remove from active trades
                    del self.active_trades[signal.symbol]
                    self.logger.info(f"💰 Trade closed: {active_trade['trade_id']} - Net PnL: ${net_pnl:.2f} (Commission: ${total_commission:.2f})")
                
            else:
                # No active trade found - try to get existing trade from database and update it
                self.logger.warning(f"⚠️ Exit signal for {signal.symbol} but no active trade found - searching database for existing OPEN trade")
                
                # Try to find existing OPEN trade in database
                existing_trade = None
                try:
                    # Query database for OPEN trade with this symbol
                    import sqlite3
                    conn = sqlite3.connect(self.db_manager.db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT * FROM trades 
                        WHERE symbol = ? AND status = 'OPEN'
                        ORDER BY entry_time DESC 
                        LIMIT 1
                    """, (signal.symbol,))
                    
                    row = cursor.fetchone()
                    if row:
                        existing_trade = dict(row)
                        self.logger.info(f"✅ Found existing OPEN trade for {signal.symbol}: {existing_trade['trade_id']}")
                    
                    conn.close()
                    
                except Exception as e:
                    self.logger.error(f"❌ Error querying database for existing trade: {e}")
                
                if existing_trade:
                    # Update existing trade with exit data
                    entry_time = datetime.fromisoformat(existing_trade['entry_time'].replace('Z', '+00:00')) if isinstance(existing_trade['entry_time'], str) else existing_trade['entry_time']
                    exit_time = datetime.now()
                    duration_minutes = int((exit_time - entry_time).total_seconds() / 60)
                    
                    # Calculate exit commission
                    exit_commission, _ = IBKRCommissionCalculator.calculate_commission(
                        quantity=existing_trade['quantity'],
                        price=order.price,
                        side='SELL' if existing_trade['side'] == 'BUY' else 'BUY',
                        plan='tiered'
                    )
                    
                    # Total commission = entry + exit
                    entry_commission = existing_trade.get('commission', 0.35)  # Default IBKR commission
                    total_commission = entry_commission + exit_commission
                    
                    # Calculate PnL
                    entry_price = existing_trade['entry_price']
                    exit_price = order.price
                    quantity = existing_trade['quantity']
                    
                    if existing_trade['side'] == 'BUY':  # Long position
                        gross_pnl = (exit_price - entry_price) * quantity
                    else:  # Short position
                        gross_pnl = (entry_price - exit_price) * quantity
                    
                    net_pnl = gross_pnl - total_commission
                    
                    # Update trade record
                    trade_data = {
                        'trade_id': existing_trade['trade_id'],
                        'symbol': signal.symbol,
                        'strategy': existing_trade['strategy'],
                        'side': existing_trade['side'],
                        'quantity': quantity,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'entry_time': entry_time,
                        'exit_time': exit_time,
                        'duration_minutes': duration_minutes,
                        'pnl': round(net_pnl, 2),
                        'commission': round(total_commission, 2),
                        'status': 'CLOSED',
                        'confidence': existing_trade.get('confidence'),  # CRITICAL: Preserve confidence from entry
                        'notes': f"{existing_trade.get('notes', '')} | Exit signal: {signal.signal_type.value}, Order ID: {order_id}, Exit Commission: ${exit_commission:.2f}",
                        'updated_at': exit_time.isoformat()
                    }
                    
                    # Save updated trade to database
                    success = self.db_manager.save_trade(trade_data)
                    if success:
                        self.logger.info(f"💰 Database trade updated: {existing_trade['trade_id']} - Entry: ${entry_price:.2f}, Exit: ${exit_price:.2f}, Net PnL: ${net_pnl:.2f}")
                        
                        # CRITICAL: Emit position_closed event for ML feedback
                        if self.event_bus:
                            try:
                                from core.interfaces import Position
                                position = Position(
                                    symbol=signal.symbol,
                                    quantity=quantity,
                                    avg_price=entry_price,
                                    market_value=exit_price * quantity,
                                    realized_pnl=net_pnl
                                )
                                
                                from core.events import create_position_event, EventTypes
                                event = create_position_event(position, EventTypes.POSITION_CLOSED)
                                await self.event_bus.publish(event)
                                
                                self.logger.info(f"📡 ML Feedback: position_closed event emitted for {signal.symbol} (Net PnL: ${net_pnl:.2f})")
                                
                            except Exception as e:
                                self.logger.error(f"❌ Failed to emit position_closed event: {e}")
                    else:
                        self.logger.error(f"❌ Failed to update trade record in database for {signal.symbol}")
                        
                    return
                
                # If no existing trade found, log and skip
                self.logger.warning(f"⚠️ No existing OPEN trade found in database for {signal.symbol} - cannot update trade record")
                self.logger.info(f"🚫 Trade record NOT updated for {signal.symbol} - no matching OPEN trade in database")
                
        except Exception as e:
            self.logger.error(f"❌ Error handling exit trade: {e}")

    def _extract_order_flow_data(self, signal: Signal) -> Dict[str, Any]:
        """
        Extract order flow data from signal metadata for database storage

        Returns:
            Dictionary with order flow fields for database
        """
        order_flow_data = {}

        try:
            if not hasattr(signal, 'metadata') or not signal.metadata:
                return {}

            metadata = signal.metadata

            # Extract order flow boost and signals
            order_flow_data['order_flow_boost'] = metadata.get('order_flow_boost', 0)

            # Convert order flow signals list to JSON string
            order_flow_signals = metadata.get('order_flow_signals', [])
            if order_flow_signals:
                import json
                order_flow_data['order_flow_signals'] = json.dumps(order_flow_signals)
            else:
                order_flow_data['order_flow_signals'] = None

            # Extract bid/ask data (these would come from the current bar used in strategy)
            # Note: These may not be in signal metadata directly, but could be added by strategy
            order_flow_data['entry_bid'] = metadata.get('entry_bid')
            order_flow_data['entry_ask'] = metadata.get('entry_ask')
            order_flow_data['entry_bid_size'] = metadata.get('entry_bid_size')
            order_flow_data['entry_ask_size'] = metadata.get('entry_ask_size')
            order_flow_data['entry_spread_pct'] = metadata.get('entry_spread_pct')

            # Extract order flow analysis results
            order_flow_data['bid_pressure'] = metadata.get('bid_pressure')
            order_flow_data['institutional_activity'] = metadata.get('institutional_activity', False)
            order_flow_data['aggressive_buying'] = metadata.get('aggressive_buying', False)
            order_flow_data['pressure_building'] = metadata.get('pressure_building', False)

            # Extract volume at price data
            order_flow_data['volume_at_ask_ratio'] = metadata.get('volume_at_ask_ratio')
            order_flow_data['volume_at_bid_ratio'] = metadata.get('volume_at_bid_ratio')

            # Extract additional predictive indicators
            order_flow_data['spread_compression_ratio'] = metadata.get('spread_compression_ratio')
            order_flow_data['volume_multiplier'] = metadata.get('volume_multiplier')

            # Log if order flow data was found
            if order_flow_data.get('order_flow_boost', 0) > 0:
                signals_text = order_flow_signals if order_flow_signals else "None"
                self.logger.info(f"📊 Order flow data extracted for {signal.symbol}: boost={order_flow_data['order_flow_boost']}, signals={signals_text}")

            return order_flow_data

        except Exception as e:
            self.logger.error(f"❌ Error extracting order flow data: {e}")
            return {}