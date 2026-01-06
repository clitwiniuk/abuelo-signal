
import sqlite3
import json
import logging
from datetime import datetime, date
from typing import Dict, Optional, Any, List

class ScannerSignalRecorder:
    """
    Component responsible for persisting scanner signals to the database
    and retrieving them for replay simulations.
    """

    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.logger = logging.getLogger("ScannerSignalRecorder")

    def record_signal(self, opportunity: Any) -> bool:
        """
        Record a scanner opportunity to the database.
        
        Args:
            opportunity: SmallcapPlay object (or similar duck-typed object)
            
        Returns:
            bool: Success status
        """
        try:
            # Extract basic fields
            symbol = opportunity.symbol
            scan_time = opportunity.scan_timestamp
            quality_score = opportunity.quality_score
            opportunity_type = str(opportunity.opportunity_type.value) if hasattr(opportunity.opportunity_type, 'value') else str(opportunity.opportunity_type)
            
            # Extract catalyst info safely
            catalyst_type = 'NONE'
            catalyst_strength = 0
            if hasattr(opportunity, 'catalyst') and opportunity.catalyst:
                catalyst_type = opportunity.catalyst.catalyst_type
                catalyst_strength = opportunity.catalyst.strength
                
            # Serialize full object
            # Note: opportunity.to_dict() is standard in this system
            if hasattr(opportunity, 'to_dict'):
                full_json = json.dumps(opportunity.to_dict(), default=str)
            else:
                full_json = json.dumps(opportunity.__dict__, default=str)
                
            signal_date = scan_time.date().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scanner_signals (
                        symbol, signal_date, scan_time, opportunity_type,
                        quality_score, catalyst_type, catalyst_strength, full_signal_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol, signal_date, scan_time, opportunity_type,
                    quality_score, catalyst_type, catalyst_strength, full_json
                ))
                conn.commit()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error recording scanner signal for {getattr(opportunity, 'symbol', 'UNKNOWN')}: {e}")
            return False

    def get_signal_for_replay(self, symbol: str, signal_date: date) -> Optional[Dict[str, Any]]:
        """
        Retrieve a persisted signal for replay.
        Returns the most relevant signal for the day (e.g., highest score or earliest).
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get the highest quality signal for the day
                cursor.execute("""
                    SELECT full_signal_json 
                    FROM scanner_signals 
                    WHERE symbol = ? AND signal_date = ?
                    ORDER BY quality_score DESC, scan_time ASC
                    LIMIT 1
                """, (symbol, signal_date.isoformat()))
                
                row = cursor.fetchone()
                
                if row:
                    return json.loads(row['full_signal_json'])
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving replay signal for {symbol}: {e}")
            return None

    def count_signals(self) -> int:
        """Count total signals in DB"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM scanner_signals")
                count = cursor.fetchone()[0]
                return count
        except Exception as e:
            self.logger.error(f"Error counting signals: {e}")
            return 0

    def get_date_range(self) -> tuple:
        """Get min/max dates with signals"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MIN(signal_date), MAX(signal_date)
                    FROM scanner_signals
                """)
                row = cursor.fetchone()
                return (row[0], row[1]) if row[0] else (None, None)
        except Exception as e:
            self.logger.error(f"Error getting date range: {e}")
            return (None, None)

    def get_signals_for_date(self, signal_date: date) -> Dict[str, Dict[str, Any]]:
        """Get all signals for a specific date"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT symbol, full_signal_json
                    FROM scanner_signals
                    WHERE signal_date = ?
                    ORDER BY symbol
                """, (signal_date.isoformat(),))

                signals = {}
                for row in cursor:
                    symbol = row['symbol']
                    signals[symbol] = json.loads(row['full_signal_json'])

                return signals
        except Exception as e:
            self.logger.error(f"Error getting signals for {signal_date}: {e}")
            return {}
