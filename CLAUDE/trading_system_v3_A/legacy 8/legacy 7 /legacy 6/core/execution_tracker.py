"""
Execution Tracker - Tracks real execution prices and calculates slippage
Updates the enhanced trades database with actual broker execution data
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List
from threading import Lock
import os
import time

logger = logging.getLogger(__name__)

class ExecutionTracker:
    """Tracks real execution prices and updates database with actual broker data"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self._lock = Lock()
        self.logger = logging.getLogger("ExecutionTracker")
        
        # Ensure database exists and has enhanced schema
        self._ensure_enhanced_schema()
    
    def _ensure_enhanced_schema(self):
        """Ensure the database has the enhanced schema with execution tracking"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if enhanced columns exist
                cursor.execute("PRAGMA table_info(trades)")
                columns = [row[1] for row in cursor.fetchall()]
                
                enhanced_columns = [
                    'actual_entry_price', 'actual_exit_price', 'actual_entry_time', 'actual_exit_time',
                    'entry_slippage', 'exit_slippage', 'entry_slippage_pct', 'exit_slippage_pct',
                    'total_slippage_impact', 'planned_pnl', 'actual_pnl',
                    'entry_filled', 'exit_filled', 'broker_order_id_entry', 'broker_order_id_exit'
                ]
                
                missing_columns = [col for col in enhanced_columns if col not in columns]
                
                if missing_columns:
                    self.logger.info("Adding enhanced execution tracking columns to database...")
                    
                    # Add missing columns
                    alterations = [
                        "ALTER TABLE trades ADD COLUMN actual_entry_price REAL",
                        "ALTER TABLE trades ADD COLUMN actual_exit_price REAL", 
                        "ALTER TABLE trades ADD COLUMN actual_entry_time TIMESTAMP",
                        "ALTER TABLE trades ADD COLUMN actual_exit_time TIMESTAMP",
                        "ALTER TABLE trades ADD COLUMN entry_slippage REAL",
                        "ALTER TABLE trades ADD COLUMN exit_slippage REAL",
                        "ALTER TABLE trades ADD COLUMN entry_slippage_pct REAL",
                        "ALTER TABLE trades ADD COLUMN exit_slippage_pct REAL",
                        "ALTER TABLE trades ADD COLUMN total_slippage_impact REAL",
                        "ALTER TABLE trades ADD COLUMN planned_pnl REAL",
                        "ALTER TABLE trades ADD COLUMN actual_pnl REAL",
                        "ALTER TABLE trades ADD COLUMN entry_filled BOOLEAN DEFAULT 0",
                        "ALTER TABLE trades ADD COLUMN exit_filled BOOLEAN DEFAULT 0",
                        "ALTER TABLE trades ADD COLUMN broker_order_id_entry TEXT",
                        "ALTER TABLE trades ADD COLUMN broker_order_id_exit TEXT"
                    ]
                    
                    for alter_sql in alterations:
                        try:
                            cursor.execute(alter_sql)
                        except sqlite3.OperationalError as e:
                            if "duplicate column name" not in str(e).lower():
                                raise
                    
                    conn.commit()
                    self.logger.info("Enhanced schema applied successfully")
                
        except Exception as e:
            self.logger.error(f"Error ensuring enhanced schema: {e}")
    
    def record_execution(self, 
                        symbol: str,
                        side: str,  # 'BUY' or 'SELL' 
                        executed_price: float,
                        executed_quantity: int,
                        execution_time: datetime,
                        broker_order_id: str,
                        trade_id: Optional[str] = None) -> bool:
        """
        Record a real execution from the broker
        
        Args:
            symbol: Stock symbol
            side: 'BUY' or 'SELL'
            executed_price: Actual execution price from broker
            executed_quantity: Actual quantity executed
            execution_time: When the execution occurred
            broker_order_id: Broker's internal order ID
            trade_id: Optional trade ID if known
            
        Returns:
            bool: Success status
        """
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Handle consolidated exits differently
                    if side in ['SELL', 'SLD'] and not trade_id:
                        # For exit orders, we need to handle consolidated positions
                        return self._handle_consolidated_exit(cursor, symbol, executed_quantity, executed_price, execution_time, broker_order_id)
                    
                    # Find the matching trade
                    if trade_id:
                        # Use provided trade_id
                        cursor.execute(
                            "SELECT * FROM trades WHERE trade_id = ? AND symbol = ?",
                            (trade_id, symbol)
                        )
                    else:
                        # 🔑 ENHANCED: Try to find by broker_order_id first (most reliable)
                        # This handles the case where ExecutionTracker is called before trade is fully committed
                        # 🔧 FIX: Search for both PENDING and OPEN status (trades are saved as PENDING first)
                        # 🔄 RETRY LOGIC: Handle race conditions with DB commits
                        trade = None
                        max_retries = 3
                        retry_delay = 0.1  # 100ms initial delay

                        for attempt in range(max_retries):
                            cursor.execute("""
                                SELECT * FROM trades
                                WHERE symbol = ? AND broker_order_id_entry = ? AND status IN ('PENDING', 'OPEN')
                                ORDER BY entry_time DESC
                                LIMIT 1
                            """, (symbol, str(broker_order_id)))

                            trade = cursor.fetchone()

                            if trade:
                                break

                            if attempt < max_retries - 1:
                                # Trade not found yet, might be DB commit delay
                                self.logger.debug(f"🔄 Trade not found for {symbol} (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff

                        if not trade:
                            # Fallback: Find most recent pending or open trade for this symbol
                            self.logger.debug(f"⚠️ Broker order ID match failed for {symbol}, trying fallback by symbol...")
                            cursor.execute("""
                                SELECT * FROM trades
                                WHERE symbol = ? AND status IN ('PENDING', 'OPEN')
                                ORDER BY entry_time DESC
                                LIMIT 1
                            """, (symbol,))
                            trade = cursor.fetchone()

                    # If trade_id was provided, we need to fetch it here
                    if trade_id and not trade:
                        trade = cursor.fetchone()

                    if not trade:
                        self.logger.warning(f"No matching trade found for execution: {symbol} {side} @ {executed_price}")
                        return False
                    
                    # Get column names for easier access
                    columns = [description[0] for description in cursor.description]
                    trade_dict = dict(zip(columns, trade))
                    
                    # Determine if this is entry or exit execution
                    is_entry = self._is_entry_execution(trade_dict, side)
                    
                    if is_entry:
                        self._update_entry_execution(cursor, trade_dict, executed_price, execution_time, broker_order_id)
                    else:
                        self._update_exit_execution(cursor, trade_dict, executed_price, execution_time, broker_order_id)
                    
                    conn.commit()
                    
                    operation_type = "Entry" if is_entry else "Exit"
                    self.logger.info(f"✅ {operation_type} execution recorded: {symbol} @ {executed_price}")
                    
                    return True
                    
            except Exception as e:
                self.logger.error(f"Error recording execution: {e}")
                return False
    
    def _is_entry_execution(self, trade_dict: Dict, side: str) -> bool:
        """Determine if this execution is for entry or exit"""
        # If entry not filled yet and sides match, it's entry
        if not trade_dict.get('entry_filled', False):
            trade_side = trade_dict['side'].upper()
            if (trade_side == 'BUY' and side == 'BUY') or (trade_side == 'SELL' and side == 'SELL'):
                return True
        
        # Otherwise it's exit
        return False
    
    def _update_entry_execution(self, cursor, trade_dict: Dict, price: float, execution_time: datetime, order_id: str):
        """Update trade with entry execution data"""
        trade_id = trade_dict['trade_id']
        planned_entry = trade_dict['entry_price']
        symbol = trade_dict['symbol']

        # VALIDATION: Check if entry was already filled
        if trade_dict.get('entry_filled'):
            existing_price = trade_dict.get('actual_entry_price')
            self.logger.warning(
                f"⚠️ DUPLICATE ENTRY: {symbol} ({trade_id}) already filled @ ${existing_price:.2f}. "
                f"Ignoring new execution @ ${price:.2f}"
            )
            return

        # VALIDATION: Detect extreme slippage (potential data error)
        entry_slippage = price - planned_entry
        entry_slippage_pct = (entry_slippage / planned_entry) * 100 if planned_entry != 0 else 0

        if abs(entry_slippage_pct) > 50:  # More than 50% slippage is suspicious
            self.logger.error(
                f"🚨 EXTREME SLIPPAGE DETECTED: {symbol} ({trade_id})\n"
                f"   Planned: ${planned_entry:.2f}\n"
                f"   Executed: ${price:.2f}\n"
                f"   Slippage: {entry_slippage_pct:+.2f}%\n"
                f"   This may indicate a data integrity issue!"
            )
            # Still update, but flag it clearly

        # VALIDATION: Check execution time is reasonable (not in the past)
        trade_entry_time = trade_dict.get('entry_time')
        if trade_entry_time and isinstance(trade_entry_time, str):
            from datetime import datetime as dt
            trade_entry_dt = dt.fromisoformat(trade_entry_time)
            if execution_time < trade_entry_dt - timedelta(hours=24):
                self.logger.error(
                    f"🚨 TIME ANOMALY: {symbol} ({trade_id})\n"
                    f"   Trade logged: {trade_entry_time}\n"
                    f"   Execution time: {execution_time}\n"
                    f"   Execution is >24h BEFORE trade creation!"
                )

        # Update database with actual execution price
        cursor.execute("""
            UPDATE trades SET
                actual_entry_price = ?,
                actual_entry_time = ?,
                entry_slippage = ?,
                entry_slippage_pct = ?,
                entry_filled = 1,
                broker_order_id_entry = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE trade_id = ? AND entry_filled = 0
        """, (price, execution_time, entry_slippage, entry_slippage_pct, order_id, trade_id))

        if cursor.rowcount == 0:
            self.logger.warning(f"⚠️ No rows updated for {trade_id} - trade may already be filled")
        else:
            self.logger.info(f"✅ Entry execution updated: {trade_id} @ ${price:.2f} - Slippage: ${entry_slippage:.4f} ({entry_slippage_pct:+.2f}%)")
    
    def _update_exit_execution(self, cursor, trade_dict: Dict, price: float, execution_time: datetime, order_id: str):
        """Update trade with exit execution data and calculate final P&L"""
        trade_id = trade_dict['trade_id']
        planned_exit = trade_dict['exit_price']
        planned_entry = trade_dict['entry_price']
        actual_entry = trade_dict.get('actual_entry_price') or planned_entry
        quantity = trade_dict['quantity']
        commission = trade_dict.get('commission', 0)
        side = trade_dict['side'].upper()
        
        # Calculate exit slippage
        exit_slippage = 0
        exit_slippage_pct = 0
        if planned_exit:
            exit_slippage = price - planned_exit
            exit_slippage_pct = (exit_slippage / planned_exit) * 100 if planned_exit != 0 else 0
        
        # Calculate P&L with actual prices
        if side == 'BUY':  # Long position
            actual_pnl = (price - actual_entry) * quantity - commission
            planned_pnl = (planned_exit - planned_entry) * quantity - commission if planned_exit else None
        else:  # Short position  
            actual_pnl = (actual_entry - price) * quantity - commission
            planned_pnl = (planned_entry - planned_exit) * quantity - commission if planned_exit else None
        
        # Calculate total slippage impact
        entry_slippage = trade_dict.get('entry_slippage', 0) or 0
        if side == 'BUY':
            total_slippage_impact = (exit_slippage - entry_slippage) * quantity
        else:
            total_slippage_impact = (entry_slippage - exit_slippage) * quantity
        
        # Update database
        cursor.execute("""
            UPDATE trades SET 
                actual_exit_price = ?,
                actual_exit_time = ?,
                exit_slippage = ?,
                exit_slippage_pct = ?,
                actual_pnl = ?,
                planned_pnl = ?,
                total_slippage_impact = ?,
                exit_filled = 1,
                broker_order_id_exit = ?,
                status = 'CLOSED',
                pnl = ?,
                exit_time = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE trade_id = ?
        """, (price, execution_time, exit_slippage, exit_slippage_pct, 
              actual_pnl, planned_pnl, total_slippage_impact, order_id,
              actual_pnl, execution_time, trade_id))
        
        self.logger.info(f"Exit execution completed: {trade_id}")
        planned_pnl_str = f"${planned_pnl:.2f}" if planned_pnl else "$0.00"
        self.logger.info(f"  Actual P&L: ${actual_pnl:.2f} | Planned P&L: {planned_pnl_str}")
        self.logger.info(f"  Exit Slippage: ${exit_slippage:.4f} ({exit_slippage_pct:.2f}%)")
        self.logger.info(f"  Total Slippage Impact: ${total_slippage_impact:.2f}")
    
    def _handle_consolidated_exit(self, cursor, symbol: str, total_quantity: int, 
                                 exit_price: float, execution_time: datetime, 
                                 broker_order_id: str) -> bool:
        """
        Handle consolidated exit orders that close multiple open trades
        Uses FIFO (First In, First Out) to close trades
        """
        try:
            # Get all open trades for this symbol, ordered by entry time (FIFO)
            cursor.execute("""
                SELECT * FROM trades 
                WHERE symbol = ? AND status = 'OPEN'
                ORDER BY entry_time ASC
            """, (symbol,))
            
            open_trades = cursor.fetchall()
            
            if not open_trades:
                self.logger.warning(f"No open trades found for consolidated exit: {symbol}")
                return False
            
            # Get column names for easier access
            columns = [description[0] for description in cursor.description]
            
            remaining_quantity = total_quantity
            closed_trades = []
            total_cost_basis = 0
            weighted_entry_time = None
            
            self.logger.info(f"🔄 Processing consolidated exit: {symbol} SELL {total_quantity}@${exit_price}")
            
            for trade_row in open_trades:
                if remaining_quantity <= 0:
                    break
                    
                trade_dict = dict(zip(columns, trade_row))
                trade_quantity = trade_dict['quantity']
                
                # Determine how much of this trade to close
                close_quantity = min(remaining_quantity, trade_quantity)
                
                # Calculate proportional exit for this trade
                proportion = close_quantity / trade_quantity
                
                # If closing partial position, we need to split the trade
                if close_quantity < trade_quantity:
                    # Split the trade: close part, keep part open
                    self._split_and_close_trade(cursor, trade_dict, close_quantity, 
                                               exit_price, execution_time, broker_order_id, proportion)
                else:
                    # Close the entire trade
                    self._close_entire_trade(cursor, trade_dict, exit_price, 
                                           execution_time, broker_order_id)
                
                # Track for logging
                closed_trades.append({
                    'trade_id': trade_dict['trade_id'],
                    'quantity': close_quantity,
                    'entry_price': trade_dict.get('actual_entry_price') or trade_dict['entry_price']
                })
                
                # Update cost basis for consolidated P&L calculation
                entry_price = trade_dict.get('actual_entry_price') or trade_dict['entry_price']
                total_cost_basis += entry_price * close_quantity
                
                remaining_quantity -= close_quantity
            
            # Log summary
            total_closed_quantity = total_quantity - remaining_quantity
            avg_entry_price = total_cost_basis / total_closed_quantity if total_closed_quantity > 0 else 0
            gross_pnl = (exit_price - avg_entry_price) * total_closed_quantity
            
            self.logger.info(f"✅ Consolidated exit completed:")
            self.logger.info(f"  Symbol: {symbol}")
            self.logger.info(f"  Total quantity closed: {total_closed_quantity}")
            self.logger.info(f"  Trades affected: {len(closed_trades)}")
            self.logger.info(f"  Weighted avg entry: ${avg_entry_price:.3f}")
            self.logger.info(f"  Exit price: ${exit_price:.3f}")
            self.logger.info(f"  Gross P&L: ${gross_pnl:.2f}")
            
            if remaining_quantity > 0:
                self.logger.warning(f"⚠️ Could not close {remaining_quantity} shares - insufficient open positions")
            
            return True
            
        except Exception as e:
            import traceback
            self.logger.error(f"Error in consolidated exit handling: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _split_and_close_trade(self, cursor, trade_dict: Dict, close_quantity: int,
                              exit_price: float, execution_time: datetime, 
                              broker_order_id: str, proportion: float):
        """Split a trade: close part of it, keep remainder open"""
        original_trade_id = trade_dict['trade_id']
        original_quantity = trade_dict['quantity']
        remaining_quantity = original_quantity - close_quantity
        
        # Create new trade for the remaining open position
        new_trade_id = f"{original_trade_id}_split_{close_quantity}"
        
        cursor.execute("""
            INSERT INTO trades (
                trade_id, symbol, strategy, side, quantity, entry_price, 
                entry_time, commission, status, notes, created_at, updated_at,
                actual_entry_price, actual_entry_time, entry_slippage, 
                entry_slippage_pct, entry_filled, broker_order_id_entry,
                confidence, market_context, trade_session, market_context_score, signal_strength
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
        """, (
            new_trade_id, trade_dict['symbol'], trade_dict['strategy'], 
            trade_dict['side'], remaining_quantity, trade_dict['entry_price'],
            trade_dict['entry_time'], (trade_dict.get('commission', 0) or 0) * (remaining_quantity/original_quantity),
            f"Split from {original_trade_id} - remaining {remaining_quantity} shares",
            trade_dict['created_at'], execution_time,
            trade_dict.get('actual_entry_price'), trade_dict.get('actual_entry_time'),
            (trade_dict.get('entry_slippage', 0) or 0) * proportion,
            trade_dict.get('entry_slippage_pct'), trade_dict.get('broker_order_id_entry'),
            trade_dict.get('confidence'), trade_dict.get('market_context'), 
            trade_dict.get('trade_session'), trade_dict.get('market_context_score'),
            trade_dict.get('signal_strength')
        ))
        
        # Update original trade to reflect the closed portion
        cursor.execute("""
            UPDATE trades SET quantity = ? WHERE trade_id = ?
        """, (close_quantity, original_trade_id))
        
        # Now close the original trade with the partial quantity
        trade_dict['quantity'] = close_quantity
        self._close_entire_trade(cursor, trade_dict, exit_price, execution_time, broker_order_id)
        
        self.logger.info(f"Trade split: {original_trade_id} -> closed {close_quantity}, new open position: {new_trade_id} ({remaining_quantity} shares)")
    
    def _close_entire_trade(self, cursor, trade_dict: Dict, exit_price: float, 
                           execution_time: datetime, broker_order_id: str):
        """Close an entire trade"""
        self._update_exit_execution(cursor, trade_dict, exit_price, execution_time, broker_order_id)
    
    def get_execution_price(self, symbol: str, side: str) -> Optional[float]:
        """
        Get the most recent execution price for a symbol and side

        ⚠️  WARNING: This method is unreliable and should only be used as fallback.
        IBKR positions are the primary source of truth for execution prices.

        Args:
            symbol: Stock symbol
            side: 'BUY' or 'SELL'

        Returns:
            float: Execution price if found, None otherwise
        """
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()

                    if side in ['BUY', 'BOT']:
                        # Get most recent entry execution
                        cursor.execute("""
                            SELECT actual_entry_price
                            FROM trades
                            WHERE symbol = ? AND entry_filled = 1 AND actual_entry_price IS NOT NULL
                            ORDER BY actual_entry_time DESC
                            LIMIT 1
                        """, (symbol,))
                    else:
                        # Get most recent exit execution
                        cursor.execute("""
                            SELECT actual_exit_price
                            FROM trades
                            WHERE symbol = ? AND exit_filled = 1 AND actual_exit_price IS NOT NULL
                            ORDER BY actual_exit_time DESC
                            LIMIT 1
                        """, (symbol,))

                    result = cursor.fetchone()

                    if result and result[0]:
                        price = float(result[0])
                        self.logger.debug(f"ExecutionTracker: {symbol} {side} price = ${price:.2f}")
                        return price

                    self.logger.debug(f"ExecutionTracker: No {side} execution found for {symbol}")
                    return None

            except Exception as e:
                self.logger.error(f"Error getting execution price for {symbol}: {e}")
                return None

    def _get_recent_valid_executions(self, symbol: str, side: str, minutes: int = 5) -> List[Dict]:
        """
        Get recent valid executions for a symbol within the last N minutes.
        Used as fallback when ExecutionTracker data appears corrupted.

        Args:
            symbol: Stock symbol
            side: 'BUY' or 'SELL'
            minutes: Time window in minutes

        Returns:
            List of execution records with price and timestamp
        """
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()

                    if side in ['BUY', 'BOT']:
                        cursor.execute("""
                            SELECT actual_entry_price as price, actual_entry_time as timestamp
                            FROM trades
                            WHERE symbol = ? AND entry_filled = 1 AND actual_entry_price IS NOT NULL
                            AND actual_entry_time >= datetime('now', '-{} minutes')
                            ORDER BY actual_entry_time DESC
                            LIMIT 5
                        """.format(minutes), (symbol,))
                    else:
                        cursor.execute("""
                            SELECT actual_exit_price as price, actual_exit_time as timestamp
                            FROM trades
                            WHERE symbol = ? AND exit_filled = 1 AND actual_exit_price IS NOT NULL
                            AND actual_exit_time >= datetime('now', '-{} minutes')
                            ORDER BY actual_exit_time DESC
                            LIMIT 5
                        """.format(minutes), (symbol,))

                    results = cursor.fetchall()
                    executions = []

                    for row in results:
                        if row[0] and row[1]:
                            executions.append({
                                'price': float(row[0]),
                                'timestamp': row[1]
                            })

                    return executions

            except Exception as e:
                self.logger.error(f"Error getting recent executions for {symbol}: {e}")
                return []

    def get_slippage_stats(self, days: int = 30) -> Dict:
        """Get slippage statistics for the last N days"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT
                        COUNT(*) as total_trades,
                        AVG(entry_slippage) as avg_entry_slippage,
                        AVG(exit_slippage) as avg_exit_slippage,
                        AVG(entry_slippage_pct) as avg_entry_slippage_pct,
                        AVG(exit_slippage_pct) as avg_exit_slippage_pct,
                        AVG(total_slippage_impact) as avg_slippage_impact,
                        SUM(total_slippage_impact) as total_slippage_cost
                    FROM trades
                    WHERE exit_filled = 1
                    AND actual_exit_time >= datetime('now', '-{} days')
                """.format(days))

                result = cursor.fetchone()

                if result and result[0] > 0:
                    return {
                        'total_trades': result[0],
                        'avg_entry_slippage': round(result[1] or 0, 4),
                        'avg_exit_slippage': round(result[2] or 0, 4),
                        'avg_entry_slippage_pct': round(result[3] or 0, 2),
                        'avg_exit_slippage_pct': round(result[4] or 0, 2),
                        'avg_slippage_impact': round(result[5] or 0, 2),
                        'total_slippage_cost': round(result[6] or 0, 2),
                        'period_days': days
                    }
                else:
                    return {'message': f'No completed trades found in the last {days} days'}

        except Exception as e:
            self.logger.error(f"Error getting slippage stats: {e}")
            return {'error': str(e)}

# Global instance
_execution_tracker = None

def get_execution_tracker(db_path: str = "trading_data.db") -> ExecutionTracker:
    """Get global execution tracker instance"""
    global _execution_tracker
    if _execution_tracker is None:
        _execution_tracker = ExecutionTracker(db_path)
    return _execution_tracker