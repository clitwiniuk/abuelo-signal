# shared/database.py
"""
Sistema_4 Database - SQLite for coordination between workers
Implements coordination logic to prevent duplicate trades
"""

import sqlite3
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """Represents an active position"""
    symbol: str
    owner: str  # worker_id that owns this position
    side: str   # LONG/SHORT
    quantity: int
    entry_price: float
    status: str  # ACTIVE/CLOSED
    created_at: datetime

@dataclass
class Opportunity:
    """Scanner opportunity"""
    symbol: str
    opportunity_type: str  # GAP_GO, DAILY_PLAYS, MACDV, BULL_FLAG
    quality_score: float
    data: str  # JSON string with opportunity data
    created_at: datetime

class Sistema4Database:
    """
    SQLite database for Sistema_4 coordination
    Prevents duplicate trades between workers
    """

    def __init__(self, db_path: str = "shared/sistema4.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(f"{__name__}.Sistema4Database")
        self._init_database()

    def _init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Positions table - tracks active positions by worker
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        owner TEXT NOT NULL,
                        side TEXT NOT NULL,
                        quantity INTEGER NOT NULL,
                        entry_price REAL NOT NULL,
                        status TEXT NOT NULL DEFAULT 'ACTIVE',
                        created_at TEXT NOT NULL,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Reservations table - temporary locks on symbols
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS reservations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL UNIQUE,
                        owner TEXT NOT NULL,
                        reserved_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    )
                """)

                # Opportunities table - scanner results
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS opportunities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        opportunity_type TEXT NOT NULL,
                        quality_score REAL NOT NULL,
                        data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        processed BOOLEAN DEFAULT FALSE
                    )
                """)

                # Trades table - detailed tracking for TradeTally integration
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        quantity INTEGER NOT NULL,
                        planned_entry_price REAL,
                        planned_exit_price REAL,
                        actual_entry_price REAL,
                        actual_exit_price REAL,
                        entry_time TIMESTAMP,
                        exit_time TIMESTAMP,
                        actual_entry_time TIMESTAMP,
                        actual_exit_time TIMESTAMP,
                        entry_slippage REAL,
                        exit_slippage REAL,
                        entry_slippage_pct REAL,
                        exit_slippage_pct REAL,
                        total_slippage_impact REAL,
                        planned_pnl REAL,
                        actual_pnl REAL,
                        entry_filled BOOLEAN DEFAULT 0,
                        exit_filled BOOLEAN DEFAULT 0,
                        broker_order_id_entry TEXT,
                        broker_order_id_exit TEXT,
                        strategy TEXT,
                        worker_id TEXT,
                        status TEXT DEFAULT 'OPEN',
                        created_at TEXT NOT NULL,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reservations_symbol ON reservations(symbol)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_opportunities_type ON opportunities(opportunity_type)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time)")

                conn.commit()
                self.logger.info("✅ Database initialized successfully with trades tracking")

        except Exception as e:
            self.logger.error(f"❌ Database initialization failed: {e}")
            raise

    def is_symbol_available(self, symbol: str) -> bool:
        """
        Check if symbol is available for trading
        Returns False if symbol has active position or reservation
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check for active positions
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM positions WHERE symbol = ? AND status = 'ACTIVE'",
                    (symbol,)
                )
                if cursor.fetchone()[0] > 0:
                    return False

                # Check for valid reservations
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM reservations WHERE symbol = ? AND expires_at > ?",
                    (symbol, datetime.now().isoformat())
                )
                if cursor.fetchone()[0] > 0:
                    return False

                return True

        except Exception as e:
            self.logger.error(f"Error checking symbol availability for {symbol}: {e}")
            return False

    def reserve_symbol(self, symbol: str, owner: str, duration_minutes: int = 5) -> bool:
        """
        Reserve symbol for worker for specified duration
        Returns True if reservation successful
        """
        try:
            if not self.is_symbol_available(symbol):
                return False

            expires_at = datetime.now() + timedelta(minutes=duration_minutes)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO reservations (symbol, owner, reserved_at, expires_at) VALUES (?, ?, ?, ?)",
                    (symbol, owner, datetime.now().isoformat(), expires_at.isoformat())
                )
                conn.commit()

            self.logger.info(f"🔒 Symbol {symbol} reserved by {owner} for {duration_minutes} minutes")
            return True

        except Exception as e:
            self.logger.error(f"Error reserving symbol {symbol}: {e}")
            return False

    def release_reservation(self, symbol: str, owner: str) -> bool:
        """Release reservation on symbol"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM reservations WHERE symbol = ? AND owner = ?",
                    (symbol, owner)
                )
                conn.commit()

                if cursor.rowcount > 0:
                    self.logger.info(f"🔓 Reservation released for {symbol} by {owner}")
                    return True
                return False

        except Exception as e:
            self.logger.error(f"Error releasing reservation for {symbol}: {e}")
            return False

    def add_position(self, symbol: str, owner: str, side: str, quantity: int, entry_price: float) -> bool:
        """Add new active position"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO positions (symbol, owner, side, quantity, entry_price, status, created_at) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?)",
                    (symbol, owner, side, quantity, entry_price, datetime.now().isoformat())
                )
                conn.commit()

            self.logger.info(f"📊 Position added: {symbol} {side} {quantity} @ ${entry_price:.2f} by {owner}")
            return True

        except Exception as e:
            self.logger.error(f"Error adding position: {e}")
            return False

    def close_position(self, symbol: str, owner: str) -> bool:
        """Mark position as closed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "UPDATE positions SET status = 'CLOSED', updated_at = ? WHERE symbol = ? AND owner = ? AND status = 'ACTIVE'",
                    (datetime.now().isoformat(), symbol, owner)
                )
                conn.commit()

                if cursor.rowcount > 0:
                    self.logger.info(f"🔚 Position closed: {symbol} by {owner}")
                    return True
                return False

        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return False

    def get_active_positions(self) -> List[Position]:
        """Get all active positions"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT symbol, owner, side, quantity, entry_price, status, created_at FROM positions WHERE status = 'ACTIVE'"
                )

                positions = []
                for row in cursor.fetchall():
                    positions.append(Position(
                        symbol=row[0],
                        owner=row[1],
                        side=row[2],
                        quantity=row[3],
                        entry_price=row[4],
                        status=row[5],
                        created_at=datetime.fromisoformat(row[6])
                    ))

                return positions

        except Exception as e:
            self.logger.error(f"Error getting active positions: {e}")
            return []

    def add_opportunity(self, symbol: str, opportunity_type: str, quality_score: float, data: Dict[str, Any]) -> bool:
        """Add scanner opportunity"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO opportunities (symbol, opportunity_type, quality_score, data, created_at) VALUES (?, ?, ?, ?, ?)",
                    (symbol, opportunity_type, quality_score, json.dumps(data), datetime.now().isoformat())
                )
                conn.commit()

            return True

        except Exception as e:
            self.logger.error(f"Error adding opportunity: {e}")
            return False

    def get_opportunities_by_type(self, opportunity_type: str, limit: int = 50) -> List[Opportunity]:
        """Get unprocessed opportunities by type"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT symbol, opportunity_type, quality_score, data, created_at FROM opportunities WHERE opportunity_type = ? AND processed = FALSE ORDER BY quality_score DESC LIMIT ?",
                    (opportunity_type, limit)
                )

                opportunities = []
                for row in cursor.fetchall():
                    opportunities.append(Opportunity(
                        symbol=row[0],
                        opportunity_type=row[1],
                        quality_score=row[2],
                        data=row[3],
                        created_at=datetime.fromisoformat(row[4])
                    ))

                return opportunities

        except Exception as e:
            self.logger.error(f"Error getting opportunities: {e}")
            return []

    def mark_opportunity_processed(self, symbol: str, opportunity_type: str) -> bool:
        """Mark opportunity as processed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE opportunities SET processed = TRUE WHERE symbol = ? AND opportunity_type = ?",
                    (symbol, opportunity_type)
                )
                conn.commit()
                return True

        except Exception as e:
            self.logger.error(f"Error marking opportunity processed: {e}")
            return False

    def cleanup_old_data(self, hours: int = 24):
        """Clean up old reservations and opportunities"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            with sqlite3.connect(self.db_path) as conn:
                # Clean expired reservations
                cursor = conn.execute("DELETE FROM reservations WHERE expires_at < ?", (datetime.now().isoformat(),))
                expired_reservations = cursor.rowcount

                # Clean old opportunities
                cursor = conn.execute("DELETE FROM opportunities WHERE created_at < ?", (cutoff_time.isoformat(),))
                old_opportunities = cursor.rowcount

                conn.commit()

            self.logger.info(f"🧹 Cleanup: {expired_reservations} expired reservations, {old_opportunities} old opportunities")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def record_trade_entry(self, symbol: str, side: str, quantity: int,
                          planned_entry_price: float, actual_entry_price: float,
                          entry_time: datetime, actual_entry_time: datetime,
                          broker_order_id: str, strategy: str, worker_id: str) -> Optional[int]:
        """Record trade entry with detailed tracking"""
        try:
            entry_slippage = actual_entry_price - planned_entry_price
            entry_slippage_pct = (entry_slippage / planned_entry_price) * 100 if planned_entry_price > 0 else 0

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO trades (
                        symbol, side, quantity, planned_entry_price, actual_entry_price,
                        entry_time, actual_entry_time, entry_slippage, entry_slippage_pct,
                        entry_filled, broker_order_id_entry, strategy, worker_id, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 'OPEN', ?)
                """, (
                    symbol, side, quantity, planned_entry_price, actual_entry_price,
                    entry_time.isoformat(), actual_entry_time.isoformat(),
                    entry_slippage, entry_slippage_pct, broker_order_id,
                    strategy, worker_id, datetime.now().isoformat()
                ))
                conn.commit()
                trade_id = cursor.lastrowid

            self.logger.info(f"📊 Trade entry recorded: {symbol} {side} @ ${actual_entry_price:.2f} (ID: {trade_id})")
            return trade_id

        except Exception as e:
            self.logger.error(f"Error recording trade entry: {e}")
            return None

    def record_trade_exit(self, trade_id: int, planned_exit_price: float,
                         actual_exit_price: float, exit_time: datetime,
                         actual_exit_time: datetime, broker_order_id: str) -> bool:
        """Record trade exit and calculate final P&L"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get trade details for P&L calculation
                cursor = conn.execute("""
                    SELECT side, quantity, actual_entry_price, planned_entry_price
                    FROM trades WHERE id = ?
                """, (trade_id,))
                trade_data = cursor.fetchone()

                if not trade_data:
                    self.logger.error(f"Trade {trade_id} not found")
                    return False

                side, quantity, actual_entry_price, planned_entry_price = trade_data

                # Calculate slippage and P&L
                exit_slippage = actual_exit_price - planned_exit_price
                exit_slippage_pct = (exit_slippage / planned_exit_price) * 100 if planned_exit_price > 0 else 0
                total_slippage_impact = abs(actual_entry_price - planned_entry_price) + abs(actual_exit_price - planned_exit_price)

                # Calculate P&L (positive for profit, negative for loss)
                if side == 'BUY':
                    planned_pnl = (planned_exit_price - planned_entry_price) * quantity
                    actual_pnl = (actual_exit_price - actual_entry_price) * quantity
                else:  # SHORT
                    planned_pnl = (planned_entry_price - planned_exit_price) * quantity
                    actual_pnl = (actual_entry_price - actual_exit_price) * quantity

                # Update trade record
                conn.execute("""
                    UPDATE trades SET
                        planned_exit_price = ?, actual_exit_price = ?,
                        exit_time = ?, actual_exit_time = ?,
                        exit_slippage = ?, exit_slippage_pct = ?,
                        total_slippage_impact = ?, planned_pnl = ?, actual_pnl = ?,
                        exit_filled = 1, broker_order_id_exit = ?,
                        status = 'CLOSED', updated_at = ?
                    WHERE id = ?
                """, (
                    planned_exit_price, actual_exit_price,
                    exit_time.isoformat(), actual_exit_time.isoformat(),
                    exit_slippage, exit_slippage_pct, total_slippage_impact,
                    planned_pnl, actual_pnl, broker_order_id,
                    datetime.now().isoformat(), trade_id
                ))
                conn.commit()

            self.logger.info(f"📊 Trade exit recorded: ID {trade_id} @ ${actual_exit_price:.2f}, P&L: ${actual_pnl:.2f}")
            return True

        except Exception as e:
            self.logger.error(f"Error recording trade exit: {e}")
            return False

    def get_trade_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get trade statistics for specified period"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            with sqlite3.connect(self.db_path) as conn:
                stats = {}

                # Total trades
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM trades
                    WHERE created_at >= ? AND status = 'CLOSED'
                """, (cutoff_date.isoformat(),))
                stats['total_trades'] = cursor.fetchone()[0]

                # Win/Loss ratio
                cursor = conn.execute("""
                    SELECT
                        COUNT(CASE WHEN actual_pnl > 0 THEN 1 END) as wins,
                        COUNT(CASE WHEN actual_pnl < 0 THEN 1 END) as losses
                    FROM trades
                    WHERE created_at >= ? AND status = 'CLOSED' AND actual_pnl IS NOT NULL
                """, (cutoff_date.isoformat(),))
                win_loss = cursor.fetchone()
                stats['wins'] = win_loss[0] or 0
                stats['losses'] = win_loss[1] or 0
                stats['win_rate'] = stats['wins'] / max(stats['total_trades'], 1) * 100

                # P&L stats
                cursor = conn.execute("""
                    SELECT
                        SUM(actual_pnl) as total_pnl,
                        AVG(actual_pnl) as avg_pnl,
                        MAX(actual_pnl) as best_trade,
                        MIN(actual_pnl) as worst_trade
                    FROM trades
                    WHERE created_at >= ? AND status = 'CLOSED' AND actual_pnl IS NOT NULL
                """, (cutoff_date.isoformat(),))
                pnl_data = cursor.fetchone()
                stats['total_pnl'] = pnl_data[0] or 0.0
                stats['avg_pnl'] = pnl_data[1] or 0.0
                stats['best_trade'] = pnl_data[2] or 0.0
                stats['worst_trade'] = pnl_data[3] or 0.0

                # Slippage stats
                cursor = conn.execute("""
                    SELECT
                        AVG(ABS(entry_slippage_pct)) as avg_entry_slippage,
                        AVG(ABS(exit_slippage_pct)) as avg_exit_slippage,
                        AVG(total_slippage_impact) as avg_total_slippage
                    FROM trades
                    WHERE created_at >= ? AND status = 'CLOSED'
                """, (cutoff_date.isoformat(),))
                slippage_data = cursor.fetchone()
                stats['avg_entry_slippage_pct'] = slippage_data[0] or 0.0
                stats['avg_exit_slippage_pct'] = slippage_data[1] or 0.0
                stats['avg_total_slippage'] = slippage_data[2] or 0.0

                # Strategy breakdown
                cursor = conn.execute("""
                    SELECT strategy, COUNT(*), SUM(actual_pnl)
                    FROM trades
                    WHERE created_at >= ? AND status = 'CLOSED'
                    GROUP BY strategy
                """, (cutoff_date.isoformat(),))
                strategy_stats = {}
                for row in cursor.fetchall():
                    strategy_stats[row[0]] = {
                        'trades': row[1],
                        'pnl': row[2] or 0.0
                    }
                stats['by_strategy'] = strategy_stats

                return stats

        except Exception as e:
            self.logger.error(f"Error getting trade stats: {e}")
            return {}

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get all open trades"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT id, symbol, side, quantity, actual_entry_price,
                           strategy, worker_id, created_at
                    FROM trades
                    WHERE status = 'OPEN'
                    ORDER BY created_at DESC
                """)

                trades = []
                for row in cursor.fetchall():
                    trades.append({
                        'trade_id': row[0],
                        'symbol': row[1],
                        'side': row[2],
                        'quantity': row[3],
                        'entry_price': row[4],
                        'strategy': row[5],
                        'worker_id': row[6],
                        'created_at': datetime.fromisoformat(row[7])
                    })

                return trades

        except Exception as e:
            self.logger.error(f"Error getting open trades: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                stats = {}

                # Active positions
                cursor = conn.execute("SELECT COUNT(*) FROM positions WHERE status = 'ACTIVE'")
                stats['active_positions'] = cursor.fetchone()[0]

                # Active reservations
                cursor = conn.execute("SELECT COUNT(*) FROM reservations WHERE expires_at > ?", (datetime.now().isoformat(),))
                stats['active_reservations'] = cursor.fetchone()[0]

                # Unprocessed opportunities
                cursor = conn.execute("SELECT COUNT(*) FROM opportunities WHERE processed = FALSE")
                stats['unprocessed_opportunities'] = cursor.fetchone()[0]

                # Trade stats
                cursor = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'OPEN'")
                stats['open_trades'] = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'")
                stats['completed_trades'] = cursor.fetchone()[0]

                return stats

        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {}