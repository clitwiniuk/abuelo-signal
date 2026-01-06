#!/usr/bin/env python3
"""
Shared Database for Sistema_III - Worker Coordination
Simple SQLite database to avoid trade duplication and coordinate workers
"""

import sqlite3
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
import aiosqlite
import json

@dataclass
class Position:
    """Active position in the system"""
    symbol: str
    worker_id: str
    strategy: str
    side: str  # LONG/SHORT
    quantity: int
    entry_price: float
    entry_time: datetime
    status: str  # ACTIVE/CLOSING/CLOSED
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    # Broker order IDs for tracking
    entry_order_id: Optional[str] = None
    stop_order_id: Optional[str] = None
    target_order_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        data = asdict(self)
        data['entry_time'] = self.entry_time.isoformat()
        data['metadata'] = json.dumps(self.metadata or {})
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """Create from database dictionary"""
        data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        data['metadata'] = json.loads(data.get('metadata', '{}'))
        return cls(**data)

@dataclass
class Reservation:
    """Temporary reservation of a symbol by a worker"""
    symbol: str
    worker_id: str
    strategy: str
    reservation_time: datetime
    expiry_time: datetime
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        data = asdict(self)
        data['reservation_time'] = self.reservation_time.isoformat()
        data['expiry_time'] = self.expiry_time.isoformat()
        data['metadata'] = json.dumps(self.metadata or {})
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Reservation':
        """Create from database dictionary"""
        data['reservation_time'] = datetime.fromisoformat(data['reservation_time'])
        data['expiry_time'] = datetime.fromisoformat(data['expiry_time'])
        data['metadata'] = json.loads(data.get('metadata', '{}'))
        return cls(**data)

@dataclass
class Opportunity:
    """Detected trading opportunity from scanner"""
    symbol: str
    opportunity_type: str  # INTRADAY_MOMENTUM, DAILY_BOUNCE, RED_TO_GREEN
    quality_score: float
    detection_time: datetime
    scanner_metadata: Dict[str, Any]
    status: str  # AVAILABLE/RESERVED/TAKEN/EXPIRED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        data = asdict(self)
        data['detection_time'] = self.detection_time.isoformat()
        data['scanner_metadata'] = json.dumps(self.scanner_metadata)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Opportunity':
        """Create from database dictionary"""
        data['detection_time'] = datetime.fromisoformat(data['detection_time'])
        data['scanner_metadata'] = json.loads(data['scanner_metadata'])
        return cls(**data)

class Sistema3Database:
    """
    Shared SQLite database for Sistema_III coordination
    Thread-safe operations to prevent worker conflicts
    """

    def __init__(self, db_path: str = "shared/positions.db"):
        self.db_path = db_path
        self.logger = logging.getLogger("Database")

    async def initialize(self) -> None:
        """Initialize database tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Enable WAL mode for better concurrent access
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA synchronous=NORMAL")

                # Positions table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS positions (
                        symbol TEXT NOT NULL,
                        worker_id TEXT NOT NULL,
                        strategy TEXT NOT NULL,
                        side TEXT NOT NULL,
                        quantity INTEGER NOT NULL,
                        entry_price REAL NOT NULL,
                        entry_time TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'ACTIVE',
                        stop_loss REAL,
                        take_profit REAL,
                        metadata TEXT DEFAULT '{}',
                        entry_order_id TEXT,
                        stop_order_id TEXT,
                        target_order_id TEXT,
                        PRIMARY KEY (symbol, worker_id)
                    )
                """)

                # Reservations table (temporary locks on symbols)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS reservations (
                        symbol TEXT PRIMARY KEY,
                        worker_id TEXT NOT NULL,
                        strategy TEXT NOT NULL,
                        reservation_time TEXT NOT NULL,
                        expiry_time TEXT NOT NULL,
                        metadata TEXT DEFAULT '{}'
                    )
                """)

                # Opportunities table (from scanner)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS opportunities (
                        symbol TEXT PRIMARY KEY,
                        opportunity_type TEXT NOT NULL,
                        quality_score REAL NOT NULL,
                        detection_time TEXT NOT NULL,
                        scanner_metadata TEXT NOT NULL,
                        status TEXT DEFAULT 'AVAILABLE'
                    )
                """)

                # Create archived opportunities table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS archived_opportunities (
                        symbol TEXT NOT NULL,
                        opportunity_type TEXT NOT NULL,
                        quality_score REAL NOT NULL,
                        detection_time TEXT NOT NULL,
                        scanner_metadata TEXT NOT NULL,
                        status TEXT,
                        archived_time TEXT NOT NULL,
                        PRIMARY KEY (symbol, detection_time)
                    )
                """)

                # Indexes for performance
                await db.execute("CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_reservations_expiry ON reservations(expiry_time)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_opportunities_type ON opportunities(opportunity_type)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status)")

                await db.commit()

            self.logger.info(f"✅ Database initialized: {self.db_path}")

        except Exception as e:
            self.logger.error(f"❌ Database initialization failed: {e}")
            raise

    # === POSITION MANAGEMENT ===

    async def add_position(self, position: Position) -> bool:
        """Add a new position to the database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO positions
                    (symbol, worker_id, strategy, side, quantity, entry_price, entry_time,
                     status, stop_loss, take_profit, metadata, entry_order_id, stop_order_id, target_order_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    position.symbol, position.worker_id, position.strategy, position.side,
                    position.quantity, position.entry_price, position.entry_time.isoformat(),
                    position.status, position.stop_loss, position.take_profit,
                    json.dumps(position.metadata or {}), position.entry_order_id,
                    position.stop_order_id, position.target_order_id
                ))
                await db.commit()

            self.logger.info(f"📊 Position added: {position.symbol} by {position.worker_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to add position {position.symbol}: {e}")
            return False

    async def get_positions(self, worker_id: Optional[str] = None,
                           status: Optional[str] = None) -> List[Position]:
        """Get positions from database with optional filters"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                query = "SELECT * FROM positions WHERE 1=1"
                params = []

                if worker_id:
                    query += " AND worker_id = ?"
                    params.append(worker_id)

                if status:
                    query += " AND status = ?"
                    params.append(status)

                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()

                positions = []
                for row in rows:
                    position_data = dict(row)
                    position_data['entry_time'] = datetime.fromisoformat(position_data['entry_time'])
                    position_data['metadata'] = json.loads(position_data['metadata'])
                    positions.append(Position(**position_data))

                return positions

        except Exception as e:
            self.logger.error(f"❌ Failed to get positions: {e}")
            return []

    async def update_position_status(self, symbol: str, worker_id: str,
                                   new_status: str) -> bool:
        """Update position status"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE positions SET status = ?
                    WHERE symbol = ? AND worker_id = ?
                """, (new_status, symbol, worker_id))
                await db.commit()

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to update position status: {e}")
            return False

    async def remove_position(self, symbol: str, worker_id: str) -> bool:
        """Remove a position from database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    DELETE FROM positions WHERE symbol = ? AND worker_id = ?
                """, (symbol, worker_id))
                await db.commit()

            self.logger.info(f"📊 Position removed: {symbol} by {worker_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to remove position: {e}")
            return False

    # === RESERVATION MANAGEMENT (Temporary Locks) ===

    async def reserve_symbol(self, symbol: str, worker_id: str, strategy: str,
                           duration_minutes: int = 5) -> bool:
        """Reserve a symbol for a worker for a limited time"""
        try:
            now = datetime.now()
            expiry = now + timedelta(minutes=duration_minutes)

            async with aiosqlite.connect(self.db_path) as db:
                # Check if symbol is already reserved or has active position
                async with db.execute("""
                    SELECT COUNT(*) FROM reservations WHERE symbol = ?
                """) as cursor:
                    reservation_exists = (await cursor.fetchone())[0] > 0

                async with db.execute("""
                    SELECT COUNT(*) FROM positions WHERE symbol = ? AND status = 'ACTIVE'
                """) as cursor:
                    position_exists = (await cursor.fetchone())[0] > 0

                if reservation_exists or position_exists:
                    return False

                # Create reservation
                await db.execute("""
                    INSERT INTO reservations
                    (symbol, worker_id, strategy, reservation_time, expiry_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (symbol, worker_id, strategy, now.isoformat(), expiry.isoformat()))

                await db.commit()

            self.logger.info(f"🔒 Symbol reserved: {symbol} by {worker_id} until {expiry.strftime('%H:%M:%S')}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to reserve symbol {symbol}: {e}")
            return False

    async def release_reservation(self, symbol: str, worker_id: str) -> bool:
        """Release a symbol reservation"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    DELETE FROM reservations WHERE symbol = ? AND worker_id = ?
                """, (symbol, worker_id))
                await db.commit()

            self.logger.info(f"🔓 Reservation released: {symbol} by {worker_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to release reservation: {e}")
            return False

    async def cleanup_expired_reservations(self) -> int:
        """Clean up expired reservations"""
        try:
            now = datetime.now()
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM reservations WHERE expiry_time < ?
                """, (now.isoformat(),))
                deleted_count = cursor.rowcount
                await db.commit()

            if deleted_count > 0:
                self.logger.info(f"🧹 Cleaned up {deleted_count} expired reservations")

            return deleted_count

        except Exception as e:
            self.logger.error(f"❌ Failed to cleanup reservations: {e}")
            return 0

    # === OPPORTUNITY MANAGEMENT ===

    async def add_opportunity(self, opportunity: Opportunity) -> bool:
        """Add a detected opportunity from scanner"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO opportunities
                    (symbol, opportunity_type, quality_score, detection_time, scanner_metadata, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    opportunity.symbol, opportunity.opportunity_type, opportunity.quality_score,
                    opportunity.detection_time.isoformat(),
                    json.dumps(opportunity.scanner_metadata), opportunity.status
                ))
                await db.commit()

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to add opportunity {opportunity.symbol}: {e}")
            return False

    async def get_opportunities(self, opportunity_type: Optional[str] = None,
                              status: str = 'AVAILABLE') -> List[Opportunity]:
        """Get available opportunities by type"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                query = "SELECT * FROM opportunities WHERE status = ?"
                params = [status]

                if opportunity_type:
                    query += " AND opportunity_type = ?"
                    params.append(opportunity_type)

                query += " ORDER BY quality_score DESC"

                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()

                opportunities = []
                for row in rows:
                    opp_data = dict(row)
                    opp_data['detection_time'] = datetime.fromisoformat(opp_data['detection_time'])
                    opp_data['scanner_metadata'] = json.loads(opp_data['scanner_metadata'])
                    opportunities.append(Opportunity(**opp_data))

                return opportunities

        except Exception as e:
            self.logger.error(f"❌ Failed to get opportunities: {e}")
            return []

    async def update_opportunity_status(self, symbol: str, new_status: str) -> bool:
        """Update opportunity status"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE opportunities SET status = ? WHERE symbol = ?
                """, (new_status, symbol))
                await db.commit()

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to update opportunity status: {e}")
            return False

    # === COORDINATION HELPERS ===

    async def is_symbol_available(self, symbol: str) -> bool:
        """Check if a symbol is available for trading (not reserved or actively traded)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Check reservations
                async with db.execute("""
                    SELECT COUNT(*) FROM reservations
                    WHERE symbol = ? AND expiry_time > ?
                """, (symbol, datetime.now().isoformat())) as cursor:
                    active_reservations = (await cursor.fetchone())[0]

                # Check active positions
                async with db.execute("""
                    SELECT COUNT(*) FROM positions
                    WHERE symbol = ? AND status = 'ACTIVE'
                """, (symbol,)) as cursor:
                    active_positions = (await cursor.fetchone())[0]

                return active_reservations == 0 and active_positions == 0

        except Exception as e:
            self.logger.error(f"❌ Failed to check symbol availability: {e}")
            return False

    async def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary for risk management"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Active positions count
                async with db.execute("""
                    SELECT COUNT(*) FROM positions WHERE status = 'ACTIVE'
                """) as cursor:
                    active_positions = (await cursor.fetchone())[0]

                # Positions by strategy
                async with db.execute("""
                    SELECT strategy, COUNT(*) FROM positions
                    WHERE status = 'ACTIVE' GROUP BY strategy
                """) as cursor:
                    strategy_counts = dict(await cursor.fetchall())

                # Active reservations
                async with db.execute("""
                    SELECT COUNT(*) FROM reservations WHERE expiry_time > ?
                """, (datetime.now().isoformat(),)) as cursor:
                    active_reservations = (await cursor.fetchone())[0]

                return {
                    'active_positions': active_positions,
                    'strategy_distribution': strategy_counts,
                    'active_reservations': active_reservations,
                    'last_updated': datetime.now().isoformat()
                }

        except Exception as e:
            self.logger.error(f"❌ Failed to get portfolio summary: {e}")
            return {}

    async def cleanup_old_data(self, opportunities_hours: int = 24,
                             reservations_hours: int = 2) -> None:
        """Archive old opportunities and delete expired reservations"""
        try:
            now = datetime.now()
            old_opportunity_cutoff = now - timedelta(hours=opportunities_hours)
            old_reservation_cutoff = now - timedelta(hours=reservations_hours)

            async with aiosqlite.connect(self.db_path) as db:
                # Archive old opportunities instead of deleting
                await db.execute("""
                    INSERT INTO archived_opportunities
                    (symbol, opportunity_type, quality_score, detection_time,
                     scanner_metadata, status, archived_time)
                    SELECT symbol, opportunity_type, quality_score, detection_time,
                           scanner_metadata, status, ?
                    FROM opportunities WHERE detection_time < ?
                """, (now.isoformat(), old_opportunity_cutoff.isoformat()))

                # Now delete the archived opportunities from active table
                await db.execute("""
                    DELETE FROM opportunities WHERE detection_time < ?
                """, (old_opportunity_cutoff.isoformat(),))

                # Clean expired reservations (these are truly temporary)
                await db.execute("""
                    DELETE FROM reservations WHERE expiry_time < ?
                """, (old_reservation_cutoff.isoformat(),))

                await db.commit()

            self.logger.info("🧹 Database cleanup completed (opportunities archived, not deleted)")

        except Exception as e:
            self.logger.error(f"❌ Database cleanup failed: {e}")

    async def cleanup_old_records(self):
        """Alias for cleanup_old_data for compatibility"""
        await self.cleanup_old_data()

    async def get_archived_opportunities(self, days_back: int = 7) -> List[dict]:
        """Get archived opportunities for analysis"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT * FROM archived_opportunities
                    WHERE archived_time > ?
                    ORDER BY archived_time DESC
                """, (cutoff_date.isoformat(),)) as cursor:
                    rows = await cursor.fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            self.logger.error(f"❌ Failed to get archived opportunities: {e}")
            return []

    async def health_check(self) -> bool:
        """Check database health"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Simple query to test connection
                await db.execute("SELECT 1")
                return True
        except Exception as e:
            self.logger.error(f"❌ Database health check failed: {e}")
            return False

    async def get_active_positions(self) -> List[Position]:
        """Get all active positions from database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT symbol, worker_id, strategy, side, quantity, entry_price,
                           entry_time, status, stop_loss, take_profit, metadata,
                           entry_order_id, stop_order_id, target_order_id
                    FROM positions
                    WHERE status = 'ACTIVE'
                """)
                rows = await cursor.fetchall()

                positions = []
                for row in rows:
                    position_data = {
                        'symbol': row[0],
                        'worker_id': row[1],
                        'strategy': row[2],
                        'side': row[3],
                        'quantity': row[4],
                        'entry_price': row[5],
                        'entry_time': datetime.fromisoformat(row[6]),
                        'status': row[7],
                        'stop_loss': row[8],
                        'take_profit': row[9],
                        'metadata': json.loads(row[10] or '{}'),
                        'entry_order_id': row[11],
                        'stop_order_id': row[12],
                        'target_order_id': row[13]
                    }
                    positions.append(Position(**position_data))

                return positions

        except Exception as e:
            self.logger.error(f"❌ Error getting active positions: {e}")
            return []

    async def close(self) -> None:
        """Close database connections (for SQLite with aiosqlite, this is handled automatically)"""
        self.logger.info("🔌 Database connections closed gracefully")
        # For aiosqlite, connections are automatically closed when context managers exit
        # This method exists for compatibility with cleanup procedures

# Global database instance
_db_instance = None

async def get_database(db_path: str = "shared/positions.db") -> Sistema3Database:
    """Get the global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Sistema3Database(db_path)
        await _db_instance.initialize()
    return _db_instance

# Alias for compatibility with main.py and execution_engine.py
Database = Sistema3Database