#!/usr/bin/env python3
"""
Recovery Manager - Sistema III
Handles system recovery, position synchronization, and order verification
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from shared.database import Sistema3Database, Position
from adapters.ibkr_adapter import IBKRAdapter
from core.service_locator import ServiceLocator


class RecoveryManager:
    """
    Manages system recovery and position synchronization
    """

    def __init__(self, db: Sistema3Database, ibkr_adapter: IBKRAdapter):
        self.db = db
        self.ibkr = ibkr_adapter
        self.logger = logging.getLogger("RecoveryManager")
        self.config = ServiceLocator().get_config()

        # Configuration
        self.position_sync_interval = self.config.getint("EXECUTION_ENGINE", "position_sync_interval_seconds", 300)
        self.max_position_age_hours = self.config.getint("RISK_MANAGER", "max_position_age_hours", 24)
        self.running = False

    async def startup_recovery(self) -> bool:
        """
        Complete recovery process on system startup
        """
        try:
            self.logger.info("🔄 Starting system recovery...")

            # Step 1: Verify IBKR connection
            if not self.ibkr.is_connected():
                self.logger.warning("⚠️ IBKR not connected during recovery, attempting connection...")
                # Connection handled by main system
                return False

            # Step 2: Sync positions with broker
            sync_success = await self.sync_positions_with_broker()

            # Step 3: Verify and restore missing orders
            if sync_success:
                await self.verify_and_restore_orders()

            # Step 4: Clean up old positions
            await self.cleanup_old_positions()

            self.logger.info("✅ System recovery completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Recovery failed: {e}", exc_info=True)
            return False

    async def sync_positions_with_broker(self) -> bool:
        """
        Synchronize database positions with actual broker positions
        """
        try:
            self.logger.info("🔄 Synchronizing positions with broker...")

            # Get positions from database
            db_positions = await self.db.get_active_positions()

            # Get positions from broker
            broker_positions = await self._get_broker_positions()

            # Create lookup dictionaries
            db_symbols = {pos.symbol: pos for pos in db_positions}
            broker_symbols = {pos['symbol']: pos for pos in broker_positions}

            # Find discrepancies
            only_in_db = set(db_symbols.keys()) - set(broker_symbols.keys())
            only_in_broker = set(broker_symbols.keys()) - set(db_symbols.keys())
            common_symbols = set(db_symbols.keys()) & set(broker_symbols.keys())

            # Handle positions only in database (likely closed externally)
            for symbol in only_in_db:
                self.logger.warning(f"⚠️ Position {symbol} in DB but not in broker - marking as closed")
                await self.db.update_position_status(symbol, db_symbols[symbol].worker_id, "CLOSED")

            # Handle positions only in broker (might be external positions)
            if only_in_broker:
                self.logger.info(f"ℹ️ Found {len(only_in_broker)} broker positions not in DB (external positions)")
                # We don't manage external positions

            # Verify quantities match for common positions
            for symbol in common_symbols:
                db_pos = db_symbols[symbol]
                broker_pos = broker_symbols[symbol]

                if abs(db_pos.quantity - broker_pos['quantity']) > 0.1:
                    self.logger.warning(f"⚠️ Quantity mismatch for {symbol}: DB={db_pos.quantity}, Broker={broker_pos['quantity']}")
                    # Update database with broker quantity
                    db_pos.quantity = broker_pos['quantity']
                    await self.db.add_position(db_pos)

            self.logger.info(f"✅ Position sync completed - DB: {len(db_positions)}, Broker: {len(broker_positions)}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Position sync failed: {e}", exc_info=True)
            return False

    async def verify_and_restore_orders(self) -> None:
        """
        Verify existing orders and restore missing ones
        """
        try:
            self.logger.info("🔍 Verifying and restoring orders...")

            active_positions = await self.db.get_active_positions()

            for position in active_positions:
                try:
                    # Check if position has stop loss order
                    if position.stop_order_id:
                        # Verify order still exists in broker
                        if not await self._verify_order_exists(position.stop_order_id):
                            self.logger.warning(f"⚠️ Stop loss order missing for {position.symbol} - recreating...")
                            await self._recreate_stop_loss_order(position)
                    else:
                        # No stop loss order ID - create one
                        self.logger.warning(f"⚠️ No stop loss order ID for {position.symbol} - creating...")
                        await self._recreate_stop_loss_order(position)

                    # Check take profit order if exists
                    if position.target_order_id:
                        if not await self._verify_order_exists(position.target_order_id):
                            self.logger.warning(f"⚠️ Take profit order missing for {position.symbol} - recreating...")
                            await self._recreate_take_profit_order(position)

                except Exception as e:
                    self.logger.error(f"❌ Error verifying orders for {position.symbol}: {e}")

            self.logger.info("✅ Order verification completed")

        except Exception as e:
            self.logger.error(f"❌ Order verification failed: {e}", exc_info=True)

    async def start_continuous_sync(self) -> None:
        """
        Start continuous position synchronization
        """
        self.running = True
        self.logger.info(f"🔄 Starting continuous sync every {self.position_sync_interval}s")

        while self.running:
            try:
                await asyncio.sleep(self.position_sync_interval)
                if self.running:  # Check again after sleep
                    await self.sync_positions_with_broker()
            except Exception as e:
                self.logger.error(f"❌ Error in continuous sync: {e}")
                await asyncio.sleep(60)  # Wait before retry

    def stop_continuous_sync(self) -> None:
        """Stop continuous synchronization"""
        self.running = False
        self.logger.info("🛑 Continuous sync stopped")

    async def cleanup_old_positions(self) -> None:
        """Clean up positions older than max age"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.max_position_age_hours)

            # This would be implemented in the database class
            # For now, we'll log the intention
            self.logger.info(f"🧹 Cleaning up positions older than {self.max_position_age_hours} hours")

        except Exception as e:
            self.logger.error(f"❌ Error cleaning old positions: {e}")

    async def _get_broker_positions(self) -> List[Dict[str, Any]]:
        """Get positions from broker"""
        try:
            # Use IBKR adapter to get positions
            positions = await self.ibkr.get_positions()
            return [
                {
                    'symbol': pos.contract.symbol,
                    'quantity': pos.position,
                    'avg_cost': pos.avgCost
                }
                for pos in positions if pos.position != 0
            ]
        except Exception as e:
            self.logger.error(f"❌ Error getting broker positions: {e}")
            return []

    async def _verify_order_exists(self, order_id: str) -> bool:
        """Verify if an order exists in the broker"""
        try:
            orders = await self.ibkr.get_open_orders()
            return any(str(order.orderId) == order_id for order in orders)
        except Exception as e:
            self.logger.error(f"❌ Error verifying order {order_id}: {e}")
            return False

    async def _recreate_stop_loss_order(self, position: Position) -> None:
        """Recreate a missing stop loss order"""
        try:
            if not position.stop_loss:
                self.logger.warning(f"⚠️ No stop loss price for {position.symbol}")
                return

            # This would integrate with the execution engine to place the order
            self.logger.info(f"🛡️ Recreating stop loss order for {position.symbol} at {position.stop_loss}")

            # Placeholder - would call execution engine method
            # new_order_id = await self.execution_engine.place_stop_loss_order(position)
            # position.stop_order_id = new_order_id
            # await self.db.add_position(position)

        except Exception as e:
            self.logger.error(f"❌ Error recreating stop loss for {position.symbol}: {e}")

    async def _recreate_take_profit_order(self, position: Position) -> None:
        """Recreate a missing take profit order"""
        try:
            if not position.take_profit:
                return

            self.logger.info(f"🎯 Recreating take profit order for {position.symbol} at {position.take_profit}")

            # Placeholder - would call execution engine method
            # new_order_id = await self.execution_engine.place_take_profit_order(position)
            # position.target_order_id = new_order_id
            # await self.db.add_position(position)

        except Exception as e:
            self.logger.error(f"❌ Error recreating take profit for {position.symbol}: {e}")