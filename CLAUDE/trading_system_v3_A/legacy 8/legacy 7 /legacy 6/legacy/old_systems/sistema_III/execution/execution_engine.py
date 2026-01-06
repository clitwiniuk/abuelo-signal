#!/usr/bin/env python3
"""
Centralized Execution Engine
Routes opportunities to appropriate strategy workers and manages execution
"""

import asyncio
import logging
import sys
import os
from typing import Dict, List, Optional
from datetime import datetime
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.ibkr_adapter import IBKRAdapter
from workers.gap_go_worker import GapGoWorker
from workers.daily_plays_worker import DailyPlaysWorker
from workers.macdv_worker import MacdvWorker
from workers.bull_flag_worker import BullFlagWorker
from execution.risk_manager import RiskManager
from shared.database import Database
from shared.message_bus import MessageBus
from notifications.telegram_client import get_telegram_client

class ExecutionEngine:
    """
    Centralized execution engine that routes opportunities to strategy workers
    """

    def __init__(self, ibkr_adapter: IBKRAdapter):
        self.logger = logging.getLogger("ExecutionEngine")
        self.ibkr = ibkr_adapter

        # Strategy workers
        self.workers = {}
        self._initialize_workers()

        # Risk management
        self.risk_manager = RiskManager()

        # Coordination components
        self.database = Database()
        self.message_bus = MessageBus()

        # Notifications
        self.telegram_client = get_telegram_client()

        # Execution tracking
        self.active_executions = {}
        self.execution_history = []

    def _initialize_workers(self):
        """Initialize all strategy workers"""
        self.workers = {
            'GAP_GO': GapGoWorker(self.ibkr),
            'DAILY_PLAYS': DailyPlaysWorker(self.ibkr),
            'MACDV': MacdvWorker(self.ibkr),
            'BULL_FLAG': BullFlagWorker(self.ibkr)
        }
        self.logger.info(f"✅ Initialized {len(self.workers)} strategy workers")

    async def execute_opportunity(self, opportunity: Dict) -> Dict:
        """
        Execute an opportunity by routing to the appropriate worker
        """
        try:
            opportunity_id = f"{opportunity['symbol']}_{datetime.now().strftime('%H%M%S')}"
            strategy = opportunity.get('opportunity_type', 'UNKNOWN')
            symbol = opportunity.get('symbol', 'UNKNOWN')

            self.logger.info(f"🎯 Executing opportunity: {symbol} ({strategy})")

            # Risk check first
            risk_approved = await self.risk_manager.approve_trade(opportunity)
            if not risk_approved['approved']:
                return {
                    'opportunity_id': opportunity_id,
                    'status': 'rejected',
                    'reason': f"Risk check failed: {risk_approved['reason']}",
                    'timestamp': datetime.now().isoformat()
                }

            # Find appropriate worker
            worker = self.workers.get(strategy)
            if not worker:
                return {
                    'opportunity_id': opportunity_id,
                    'status': 'error',
                    'reason': f"No worker available for strategy: {strategy}",
                    'timestamp': datetime.now().isoformat()
                }

            # Verify worker can handle this opportunity
            can_handle = await worker.can_handle(opportunity)
            if not can_handle:
                return {
                    'opportunity_id': opportunity_id,
                    'status': 'rejected',
                    'reason': f"Worker {strategy} cannot handle this opportunity",
                    'timestamp': datetime.now().isoformat()
                }

            # Track execution start
            self.active_executions[opportunity_id] = {
                'symbol': symbol,
                'strategy': strategy,
                'start_time': datetime.now(),
                'status': 'executing'
            }

            # Execute via worker
            execution_result = await worker.execute_opportunity(opportunity)

            # Update execution tracking
            execution_result['opportunity_id'] = opportunity_id
            execution_result['timestamp'] = datetime.now().isoformat()

            if execution_result['status'] == 'executed':
                self.active_executions[opportunity_id]['status'] = 'active'
                self.active_executions[opportunity_id]['execution_details'] = execution_result
            else:
                self.active_executions[opportunity_id]['status'] = 'failed'
                # Move to history if not active
                self.execution_history.append(self.active_executions.pop(opportunity_id))

            # Log to database
            await self.database.log_execution(opportunity_id, opportunity, execution_result)

            # Publish execution result
            await self.message_bus.publish_execution_result(execution_result)

            # Send Telegram notification
            try:
                await self.telegram_client.notify_execution(execution_result)
            except Exception as e:
                self.logger.error(f"❌ Error sending Telegram execution notification: {e}")

            self.logger.info(f"✅ Execution completed: {symbol} - {execution_result['status']}")
            return execution_result

        except Exception as e:
            self.logger.error(f"❌ Execution engine error: {e}")
            return {
                'opportunity_id': opportunity_id if 'opportunity_id' in locals() else 'unknown',
                'status': 'error',
                'reason': str(e),
                'timestamp': datetime.now().isoformat()
            }

    async def monitor_active_positions(self) -> List[Dict]:
        """
        Monitor all active positions across all workers
        """
        all_updates = []

        try:
            # Get updates from each worker
            for strategy, worker in self.workers.items():
                try:
                    worker_updates = await worker.monitor_positions()
                    for update in worker_updates:
                        update['strategy'] = strategy
                        all_updates.append(update)

                        # Update execution tracking
                        symbol = update['symbol']
                        for exec_id, execution in self.active_executions.items():
                            if execution['symbol'] == symbol and execution['strategy'] == strategy:
                                if update['action'] == 'CLOSED':
                                    execution['status'] = 'completed'
                                    execution['close_reason'] = update['reason']
                                    execution['close_price'] = update['price']
                                    execution['end_time'] = datetime.now()

                                    # Send Telegram position close notification
                                    try:
                                        close_data = {
                                            'symbol': symbol,
                                            'reason': update['reason'],
                                            'price': update['price'],
                                            'pnl': update.get('pnl', 0.0)
                                        }
                                        await self.telegram_client.notify_position_close(close_data)
                                    except Exception as e:
                                        self.logger.error(f"❌ Error sending Telegram close notification: {e}")

                                    # Move to history
                                    self.execution_history.append(self.active_executions.pop(exec_id))

                except Exception as e:
                    self.logger.error(f"❌ Error monitoring {strategy} positions: {e}")

            if all_updates:
                self.logger.info(f"📊 Position updates: {len(all_updates)} across all strategies")

                # Log updates to database
                for update in all_updates:
                    await self.database.log_position_update(update)

                # Publish updates
                await self.message_bus.publish_position_updates(all_updates)

        except Exception as e:
            self.logger.error(f"❌ Error monitoring positions: {e}")

        return all_updates

    async def get_portfolio_status(self) -> Dict:
        """Get current portfolio status across all strategies"""
        try:
            status = {
                'active_positions': len(self.active_executions),
                'strategies': {},
                'total_capital_used': 0.0,
                'risk_utilization': await self.risk_manager.get_risk_utilization(),
                'timestamp': datetime.now().isoformat()
            }

            # Count positions by strategy
            for execution in self.active_executions.values():
                strategy = execution['strategy']
                if strategy not in status['strategies']:
                    status['strategies'][strategy] = {
                        'active_positions': 0,
                        'symbols': []
                    }
                status['strategies'][strategy]['active_positions'] += 1
                status['strategies'][strategy]['symbols'].append(execution['symbol'])

            return status

        except Exception as e:
            self.logger.error(f"❌ Error getting portfolio status: {e}")
            return {'error': str(e)}

    async def emergency_close_all(self, reason: str = "EMERGENCY"):
        """Emergency close all active positions"""
        try:
            self.logger.warning(f"🚨 EMERGENCY CLOSE ALL - Reason: {reason}")

            closed_positions = []
            for strategy, worker in self.workers.items():
                try:
                    # Force close all positions for this worker
                    for symbol in worker.active_positions.keys():
                        await worker._close_position(symbol, f"EMERGENCY_{reason}")
                        closed_positions.append({
                            'symbol': symbol,
                            'strategy': strategy,
                            'reason': f"EMERGENCY_{reason}"
                        })
                except Exception as e:
                    self.logger.error(f"❌ Error closing {strategy} positions: {e}")

            # Clear execution tracking
            for exec_id in list(self.active_executions.keys()):
                execution = self.active_executions.pop(exec_id)
                execution['status'] = 'emergency_closed'
                execution['close_reason'] = f"EMERGENCY_{reason}"
                execution['end_time'] = datetime.now()
                self.execution_history.append(execution)

            self.logger.warning(f"🚨 Emergency closed {len(closed_positions)} positions")
            return closed_positions

        except Exception as e:
            self.logger.error(f"❌ Error in emergency close: {e}")
            return []

    async def cleanup(self):
        """Cleanup resources"""
        try:
            await self.database.close()
            await self.message_bus.disconnect()
            self.logger.info("✅ Execution engine cleanup completed")
        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")