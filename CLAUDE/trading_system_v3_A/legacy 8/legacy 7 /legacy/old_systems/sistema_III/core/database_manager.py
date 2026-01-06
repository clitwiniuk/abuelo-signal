# core/database_manager.py
"""
Database Manager for Trading System
Handles SQLite database operations for trades, performance, and analytics
"""

import sqlite3
import logging
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any

class DatabaseManager:
    """Manages SQLite database for trading system analytics"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = Path(db_path)
        self.logger = logging.getLogger("DatabaseManager")
        self._init_database()
    
    def _init_database(self):
        """Initialize database and create tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                self._create_tables(conn)
            self.logger.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise
    
    def migrate_strategy_names(self, placeholder: str = "multi_strategy") -> int:
        """Update trades using placeholder strategy to real strategy based on recent trade per symbol.

        Returns number of trades updated.
        """
        updated = 0
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get symbols that still have placeholder strategy
                rows = conn.execute("SELECT DISTINCT symbol FROM trades WHERE strategy = ?", (placeholder,)).fetchall()
                symbols = [r[0] for r in rows]
                for symbol in symbols:
                    # Find most recent non-placeholder strategy for the symbol
                    row = conn.execute(
                        "SELECT strategy FROM trades WHERE symbol = ? AND strategy != ? ORDER BY entry_time DESC LIMIT 1",
                        (symbol, placeholder),
                    ).fetchone()
                    if row:
                        real_strategy = row[0]
                        conn.execute(
                            "UPDATE trades SET strategy = ? WHERE symbol = ? AND strategy = ?",
                            (real_strategy, symbol, placeholder),
                        )
                        updated += conn.total_changes  # type: ignore[attr-defined]
                conn.commit()
            if updated:
                self.logger.info(f"Migrated {updated} trades from '{placeholder}' strategy to real strategies")
            else:
                self.logger.info("No trades needed strategy migration")
            return updated
        except Exception as e:
            self.logger.error(f"Error migrating strategy names: {e}")
            return 0

    def _create_tables(self, conn: sqlite3.Connection):
        """Create all necessary tables"""
        
        # Trades table - Core trade data
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                side TEXT NOT NULL, -- 'BUY' or 'SELL'
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                entry_time TIMESTAMP NOT NULL,
                exit_time TIMESTAMP,
                duration_minutes INTEGER,
                pnl REAL,
                commission REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN', -- 'OPEN', 'CLOSED', 'CANCELLED'
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Daily stats table - Daily performance summary
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                gross_profit REAL DEFAULT 0,
                gross_loss REAL DEFAULT 0,
                max_win REAL DEFAULT 0,
                max_loss REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                avg_win REAL DEFAULT 0,
                avg_loss REAL DEFAULT 0,
                profit_factor REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Trading journal table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trading_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                market_notes TEXT,
                strategy_notes TEXT,
                lessons_learned TEXT,
                mood_rating INTEGER CHECK(mood_rating >= 1 AND mood_rating <= 5),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Manual symbols table - Persistent symbol management
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manual_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                notes TEXT
            )
        """)
        
        # Position risk management table - Persistent risk configuration
        conn.execute("""
            CREATE TABLE IF NOT EXISTS position_risk_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                stop_loss_price REAL,
                take_profit_price REAL,
                trailing_stop_activation_price REAL,
                trailing_stop_distance_pct REAL DEFAULT 0.05,
                max_hold_time_minutes INTEGER DEFAULT 240,
                strategy_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                UNIQUE(symbol, entry_price, quantity)
            )
        """)
        
        # Create indexes for better performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date(entry_time))")
        
        self.logger.info("Database tables created successfully")
    
    def get_latest_strategy(self, symbol: str) -> Optional[str]:
        """Return strategy of most recent trade for symbol (any status)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT strategy FROM trades WHERE symbol = ? ORDER BY entry_time DESC LIMIT 1",
                    (symbol,)
                ).fetchone()
                return row[0] if row else None
        except Exception as e:
            self.logger.error(f"Error fetching latest strategy for {symbol}: {e}")
            return None

    def load_open_trades(self) -> List[Dict[str, Any]]:
        """Load all trades with status 'OPEN'. Returns list of dicts."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM trades WHERE status = 'OPEN'").fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            self.logger.error(f"Error loading open trades: {e}")
            return []
    
    def load_latest_open_trades_by_symbol(self) -> List[Dict[str, Any]]:
        """Load most recent open trade per symbol. Returns list of dicts."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                # Get most recent open trade per symbol
                rows = conn.execute("""
                    SELECT * FROM trades 
                    WHERE status = 'OPEN' 
                    AND (symbol, entry_time) IN (
                        SELECT symbol, MAX(entry_time) 
                        FROM trades 
                        WHERE status = 'OPEN' 
                        GROUP BY symbol
                    )
                    ORDER BY entry_time DESC
                """).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            self.logger.error(f"Error loading latest open trades by symbol: {e}")
            return []

    def save_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Save a trade to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if trade already exists
                existing = conn.execute(
                    "SELECT id FROM trades WHERE trade_id = ?", 
                    (trade_data['trade_id'],)
                ).fetchone()
                
                if existing:
                    # Update existing trade (including order flow fields)
                    conn.execute("""
                        UPDATE trades SET
                            symbol = ?, strategy = ?, side = ?, quantity = ?,
                            entry_price = ?, exit_price = ?, entry_time = ?, exit_time = ?,
                            duration_minutes = ?, pnl = ?, commission = ?, status = ?,
                            notes = ?, confidence = ?, order_flow_boost = ?, order_flow_signals = ?,
                            entry_bid = ?, entry_ask = ?, entry_bid_size = ?, entry_ask_size = ?,
                            entry_spread_pct = ?, bid_pressure = ?, institutional_activity = ?,
                            aggressive_buying = ?, pressure_building = ?, volume_at_ask_ratio = ?,
                            volume_at_bid_ratio = ?, spread_compression_ratio = ?, volume_multiplier = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE trade_id = ?
                    """, (
                        trade_data['symbol'], trade_data['strategy'], trade_data['side'],
                        trade_data['quantity'], trade_data['entry_price'],
                        trade_data.get('exit_price'), trade_data['entry_time'],
                        trade_data.get('exit_time'), trade_data.get('duration_minutes'),
                        trade_data.get('pnl'), trade_data.get('commission', 0),
                        trade_data.get('status', 'OPEN'), trade_data.get('notes'),
                        trade_data.get('confidence'),
                        # Order flow fields
                        trade_data.get('order_flow_boost', 0),
                        trade_data.get('order_flow_signals'),
                        trade_data.get('entry_bid'),
                        trade_data.get('entry_ask'),
                        trade_data.get('entry_bid_size'),
                        trade_data.get('entry_ask_size'),
                        trade_data.get('entry_spread_pct'),
                        trade_data.get('bid_pressure'),
                        trade_data.get('institutional_activity', False),
                        trade_data.get('aggressive_buying', False),
                        trade_data.get('pressure_building', False),
                        trade_data.get('volume_at_ask_ratio'),
                        trade_data.get('volume_at_bid_ratio'),
                        trade_data.get('spread_compression_ratio'),
                        trade_data.get('volume_multiplier'),
                        trade_data['trade_id']
                    ))
                else:
                    # Insert new trade (including order flow fields)
                    conn.execute("""
                        INSERT INTO trades (
                            trade_id, symbol, strategy, side, quantity, entry_price,
                            exit_price, entry_time, exit_time, duration_minutes,
                            pnl, commission, status, notes, confidence,
                            order_flow_boost, order_flow_signals, entry_bid, entry_ask,
                            entry_bid_size, entry_ask_size, entry_spread_pct, bid_pressure,
                            institutional_activity, aggressive_buying, pressure_building,
                            volume_at_ask_ratio, volume_at_bid_ratio, spread_compression_ratio,
                            volume_multiplier
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade_data['trade_id'], trade_data['symbol'], trade_data['strategy'],
                        trade_data['side'], trade_data['quantity'], trade_data['entry_price'],
                        trade_data.get('exit_price'), trade_data['entry_time'],
                        trade_data.get('exit_time'), trade_data.get('duration_minutes'),
                        trade_data.get('pnl'), trade_data.get('commission', 0),
                        trade_data.get('status', 'OPEN'), trade_data.get('notes'),
                        trade_data.get('confidence'),
                        # Order flow fields
                        trade_data.get('order_flow_boost', 0),
                        trade_data.get('order_flow_signals'),
                        trade_data.get('entry_bid'),
                        trade_data.get('entry_ask'),
                        trade_data.get('entry_bid_size'),
                        trade_data.get('entry_ask_size'),
                        trade_data.get('entry_spread_pct'),
                        trade_data.get('bid_pressure'),
                        trade_data.get('institutional_activity', False),
                        trade_data.get('aggressive_buying', False),
                        trade_data.get('pressure_building', False),
                        trade_data.get('volume_at_ask_ratio'),
                        trade_data.get('volume_at_bid_ratio'),
                        trade_data.get('spread_compression_ratio'),
                        trade_data.get('volume_multiplier')
                    ))
                
                conn.commit()
                self.logger.info(f"Trade saved: {trade_data['trade_id']}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error saving trade: {e}")
            return False
    
    def get_trades(self, symbol: str = None, strategy: str = None, 
                  start_date: date = None, end_date: date = None,
                  limit: int = 100) -> pd.DataFrame:
        """Get trades with optional filters"""
        try:
            query = "SELECT * FROM trades WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if strategy:
                query += " AND strategy = ?"
                params.append(strategy)
            
            if start_date:
                query += " AND date(entry_time) >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND date(entry_time) <= ?"
                params.append(end_date.isoformat())
            
            query += " ORDER BY entry_time DESC LIMIT ?"
            params.append(limit)
            
            with sqlite3.connect(self.db_path) as conn:
                return pd.read_sql_query(query, conn, params=params)
                
        except Exception as e:
            self.logger.error(f"Error getting trades: {e}")
            return pd.DataFrame()
    
    def calculate_daily_stats(self, target_date: date = None) -> Dict[str, Any]:
        """Calculate daily statistics"""
        if not target_date:
            target_date = date.today()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get trades for the day
                trades_df = pd.read_sql_query("""
                    SELECT * FROM trades 
                    WHERE date(entry_time) = ? AND status = 'CLOSED'
                """, conn, params=[target_date.isoformat()])
                
                if trades_df.empty:
                    return self._empty_daily_stats()
                
                # Calculate stats
                total_trades = len(trades_df)
                winning_trades = len(trades_df[trades_df['pnl'] > 0])
                losing_trades = len(trades_df[trades_df['pnl'] < 0])
                
                total_pnl = trades_df['pnl'].sum()
                gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
                gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
                
                max_win = trades_df['pnl'].max() if not trades_df.empty else 0
                max_loss = trades_df['pnl'].min() if not trades_df.empty else 0
                
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                avg_win = gross_profit / winning_trades if winning_trades > 0 else 0
                avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
                
                stats = {
                    'date': target_date,
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'total_pnl': round(total_pnl, 2),
                    'gross_profit': round(gross_profit, 2),
                    'gross_loss': round(gross_loss, 2),
                    'max_win': round(max_win, 2),
                    'max_loss': round(max_loss, 2),
                    'win_rate': round(win_rate, 2),
                    'avg_win': round(avg_win, 2),
                    'avg_loss': round(avg_loss, 2),
                    'profit_factor': round(profit_factor, 2)
                }
                
                # Save to daily_stats table
                self._save_daily_stats(stats)
                return stats
                
        except Exception as e:
            self.logger.error(f"Error calculating daily stats: {e}")
            return self._empty_daily_stats()
    
    def _empty_daily_stats(self) -> Dict[str, Any]:
        """Return empty daily stats structure"""
        return {
            'date': date.today(),
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'gross_profit': 0.0,
            'gross_loss': 0.0,
            'max_win': 0.0,
            'max_loss': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0
        }
    
    def _save_daily_stats(self, stats: Dict[str, Any]):
        """Save daily stats to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO daily_stats (
                        date, total_trades, winning_trades, losing_trades,
                        total_pnl, gross_profit, gross_loss, max_win, max_loss,
                        win_rate, avg_win, avg_loss, profit_factor
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stats['date'], stats['total_trades'], stats['winning_trades'],
                    stats['losing_trades'], stats['total_pnl'], stats['gross_profit'],
                    stats['gross_loss'], stats['max_win'], stats['max_loss'],
                    stats['win_rate'], stats['avg_win'], stats['avg_loss'],
                    stats['profit_factor']
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error saving daily stats: {e}")
    
    def get_strategy_performance(self, days: int = 30) -> pd.DataFrame:
        """Get performance by strategy"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # First, let's see what we have in the database for debugging
                debug_df = pd.read_sql_query("""
                    SELECT 
                        strategy,
                        status,
                        COUNT(*) as count
                    FROM trades
                    WHERE date(entry_time) >= date('now', '-{} days')
                    GROUP BY strategy, status
                    ORDER BY strategy, status
                """.format(days), conn)
                
                if not debug_df.empty:
                    self.logger.info(f"Strategy performance debug - Available data: {debug_df.to_dict('records')}")
                
                # Try with all trades that have PnL (indicating they were closed)
                return pd.read_sql_query("""
                    SELECT 
                        strategy,
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                        ROUND(AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 2) as win_rate,
                        ROUND(SUM(pnl), 2) as total_pnl,
                        ROUND(AVG(pnl), 2) as avg_pnl,
                        ROUND(MAX(pnl), 2) as best_trade,
                        ROUND(MIN(pnl), 2) as worst_trade
                    FROM trades
                    WHERE date(entry_time) >= date('now', '-{} days')
                        AND pnl IS NOT NULL
                    GROUP BY strategy
                    ORDER BY total_pnl DESC
                """.format(days), conn)
                
        except Exception as e:
            self.logger.error(f"Error getting strategy performance: {e}")
            return pd.DataFrame()
    
    def get_today_stats(self) -> Dict[str, Any]:
        """Get today's trading statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get today's trades
                today_df = pd.read_sql_query("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN pnl <= 0 AND pnl IS NOT NULL THEN 1 ELSE 0 END) as losing_trades,
                        COALESCE(SUM(pnl), 0) as total_pnl,
                        COALESCE(AVG(pnl), 0) as avg_pnl,
                        COALESCE(MAX(pnl), 0) as best_trade,
                        COALESCE(MIN(pnl), 0) as worst_trade,
                        COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_positions
                    FROM trades 
                    WHERE date(entry_time) = date('now')
                """, conn)
                
                if today_df.empty:
                    # Return default stats if no data
                    return {
                        'total_trades': 0,
                        'winning_trades': 0,
                        'losing_trades': 0,
                        'win_rate': 0.0,
                        'total_pnl': 0.0,
                        'avg_pnl': 0.0,
                        'best_trade': 0.0,
                        'worst_trade': 0.0,
                        'open_positions': 0
                    }
                
                # Extract data from DataFrame
                stats = today_df.iloc[0].to_dict()
                
                # Calculate win rate - handle None values
                winning_trades = stats.get('winning_trades') or 0
                losing_trades = stats.get('losing_trades') or 0
                total_closed = winning_trades + losing_trades
                stats['win_rate'] = (winning_trades / total_closed * 100) if total_closed > 0 else 0.0
                
                # Ensure all required keys exist with proper defaults
                stats.setdefault('total_trades', 0)
                stats.setdefault('winning_trades', 0)
                stats.setdefault('losing_trades', 0)
                stats.setdefault('total_pnl', 0.0)
                stats.setdefault('avg_pnl', 0.0)
                stats.setdefault('best_trade', 0.0)
                stats.setdefault('worst_trade', 0.0)
                stats.setdefault('open_positions', 0)
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting today's stats: {e}")
            # Return default stats on error
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0,
                'open_positions': 0
            }
    
    def save_journal_entry(self, date_entry: date, market_notes: str = None, 
                          strategy_notes: str = None, lessons_learned: str = None,
                          mood_rating: int = None) -> bool:
        """Save trading journal entry"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO trading_journal (
                        date, market_notes, strategy_notes, lessons_learned, mood_rating
                    ) VALUES (?, ?, ?, ?, ?)
                """, (date_entry, market_notes, strategy_notes, lessons_learned, mood_rating))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error saving journal entry: {e}")
            return False
    
    def get_journal_entries(self, days: int = 30) -> pd.DataFrame:
        """Get trading journal entries"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                return pd.read_sql_query("""
                    SELECT * FROM trading_journal
                    WHERE date >= date('now', '-{} days')
                    ORDER BY date DESC
                """.format(days), conn)
        except Exception as e:
            self.logger.error(f"Error getting journal entries: {e}")
            return pd.DataFrame()
    
    # =============== MANUAL SYMBOLS MANAGEMENT ===============
    
    def add_manual_symbol(self, symbol: str, notes: str = None) -> bool:
        """Add a symbol to manual symbols list"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO manual_symbols (symbol, notes, is_active)
                    VALUES (?, ?, 1)
                """, (symbol.upper(), notes))
                conn.commit()
                self.logger.info(f"Added manual symbol: {symbol}")
                return True
        except Exception as e:
            self.logger.error(f"Error adding manual symbol {symbol}: {e}")
            return False
    
    def remove_manual_symbol(self, symbol: str) -> bool:
        """Remove a symbol from manual symbols list"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM manual_symbols WHERE symbol = ?", (symbol.upper(),))
                conn.commit()
                self.logger.info(f"Removed manual symbol: {symbol}")
                return True
        except Exception as e:
            self.logger.error(f"Error removing manual symbol {symbol}: {e}")
            return False
    
    def get_manual_symbols(self, active_only: bool = True) -> List[str]:
        """Get list of manual symbols"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if active_only:
                    cursor = conn.execute("SELECT symbol FROM manual_symbols WHERE is_active = 1 ORDER BY symbol")
                else:
                    cursor = conn.execute("SELECT symbol FROM manual_symbols ORDER BY symbol")
                
                symbols = [row[0] for row in cursor.fetchall()]
                self.logger.debug(f"Retrieved {len(symbols)} manual symbols")
                return symbols
        except Exception as e:
            self.logger.error(f"Error getting manual symbols: {e}")
            return []
    
    def set_manual_symbols(self, symbols: List[str]) -> bool:
        """Set the complete list of manual symbols (replaces existing)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Clear existing symbols
                conn.execute("DELETE FROM manual_symbols")
                
                # Add new symbols
                for symbol in symbols:
                    conn.execute("""
                        INSERT INTO manual_symbols (symbol, is_active)
                        VALUES (?, 1)
                    """, (symbol.upper(),))
                
                conn.commit()
                self.logger.info(f"Set manual symbols to: {symbols}")
                return True
        except Exception as e:
            self.logger.error(f"Error setting manual symbols: {e}")
            return False
    
    def get_recent_trades(self, symbol: str = None, days: int = 7, limit: int = 100) -> pd.DataFrame:
        """Get recent trades for a specific symbol or all symbols"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if symbol:
                    query = """
                        SELECT * FROM trades 
                        WHERE symbol = ? AND entry_time >= datetime('now', '-{} days')
                        ORDER BY entry_time DESC
                        LIMIT ?
                    """.format(days)
                    return pd.read_sql_query(query, conn, params=(symbol.upper(), limit))
                else:
                    query = """
                        SELECT * FROM trades 
                        WHERE entry_time >= datetime('now', '-{} days')
                        ORDER BY entry_time DESC
                        LIMIT ?
                    """.format(days)
                    return pd.read_sql_query(query, conn, params=(limit,))
        except Exception as e:
            self.logger.error(f"Error getting recent trades: {e}")
            return pd.DataFrame()
    
    # =============== POSITION RISK MANAGEMENT ===============
    
    def save_position_risk_config(self, symbol: str, entry_price: float, quantity: int, 
                                 stop_loss_price: float = None, take_profit_price: float = None,
                                 trailing_stop_activation_price: float = None, 
                                 trailing_stop_distance_pct: float = 0.05,
                                 max_hold_time_minutes: int = 240,
                                 strategy_used: str = None) -> bool:
        """Save risk management configuration for a position"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO position_risk_config (
                        symbol, entry_price, quantity, stop_loss_price, take_profit_price,
                        trailing_stop_activation_price, trailing_stop_distance_pct, 
                        max_hold_time_minutes, strategy_used, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (symbol.upper(), entry_price, quantity, stop_loss_price, take_profit_price,
                      trailing_stop_activation_price, trailing_stop_distance_pct,
                      max_hold_time_minutes, strategy_used))
                conn.commit()
                self.logger.info(f"Saved risk config for {symbol}: SL={stop_loss_price}, TP={take_profit_price}")
                return True
        except Exception as e:
            self.logger.error(f"Error saving position risk config for {symbol}: {e}")
            return False
    
    def get_position_risk_config(self, symbol: str = None) -> pd.DataFrame:
        """Get risk management configuration for positions"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if symbol:
                    query = """
                        SELECT * FROM position_risk_config 
                        WHERE symbol = ? AND is_active = 1
                        ORDER BY created_at DESC
                    """
                    return pd.read_sql_query(query, conn, params=(symbol.upper(),))
                else:
                    query = """
                        SELECT * FROM position_risk_config 
                        WHERE is_active = 1
                        ORDER BY created_at DESC
                    """
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            self.logger.error(f"Error getting position risk config: {e}")
            return pd.DataFrame()
    
    def deactivate_position_risk_config(self, symbol: str, entry_price: float = None) -> bool:
        """Deactivate risk config when position is closed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if entry_price:
                    conn.execute("""
                        UPDATE position_risk_config 
                        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                        WHERE symbol = ? AND entry_price = ?
                    """, (symbol.upper(), entry_price))
                else:
                    conn.execute("""
                        UPDATE position_risk_config 
                        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                        WHERE symbol = ?
                    """, (symbol.upper(),))
                conn.commit()
                self.logger.info(f"Deactivated risk config for {symbol}")
                return True
        except Exception as e:
            self.logger.error(f"Error deactivating position risk config for {symbol}: {e}")
            return False
    
    def restore_risk_management_for_existing_positions(self, positions_dict: Dict[str, Any]) -> int:
        """
        Restore default risk management for existing positions that don't have config
        Called when system restarts and finds existing broker positions
        """
        restored_count = 0
        
        try:
            for symbol, position_data in positions_dict.items():
                # Extract position data (handle both dict and object formats)
                if isinstance(position_data, dict):
                    entry_price = position_data.get('avg_price', 0)
                    quantity = position_data.get('quantity', 0)
                else:
                    entry_price = getattr(position_data, 'averageCost', 0)
                    quantity = getattr(position_data, 'position', 0)
                
                if entry_price <= 0 or quantity <= 0:
                    continue
                
                # Check if already has risk config
                existing_config = self.get_position_risk_config(symbol)
                if not existing_config.empty:
                    self.logger.info(f"Risk config already exists for {symbol}")
                    continue
                
                # Create default risk management config
                stop_loss_price = entry_price * 0.95  # 5% stop loss
                take_profit_price = entry_price * 1.10  # 10% take profit
                trailing_activation = entry_price * 1.05  # Activate trailing at 5% profit
                
                success = self.save_position_risk_config(
                    symbol=symbol,
                    entry_price=entry_price,
                    quantity=abs(int(quantity)),
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price,
                    trailing_stop_activation_price=trailing_activation,
                    trailing_stop_distance_pct=0.03,  # 3% trailing distance
                    max_hold_time_minutes=480,  # 8 hours max hold
                    strategy_used="restored_on_restart"
                )
                
                if success:
                    restored_count += 1
                    self.logger.info(f"✅ Restored risk management for {symbol}: "
                                   f"Entry=${entry_price:.4f}, SL=${stop_loss_price:.4f}, TP=${take_profit_price:.4f}")
                
        except Exception as e:
            self.logger.error(f"Error restoring risk management for existing positions: {e}")
        
        self.logger.info(f"🔧 Restored risk management for {restored_count} positions")
        return restored_count


# Singleton instance for global access
_database_manager = None

def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance"""
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
    return _database_manager