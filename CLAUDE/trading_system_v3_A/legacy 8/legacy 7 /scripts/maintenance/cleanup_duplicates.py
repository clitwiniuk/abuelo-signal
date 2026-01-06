#!/usr/bin/env python3
"""
Cleanup Duplicates in Trade OHLC Snapshots
==========================================

Identifica y elimina registros duplicados de snapshots para el mismo Símbolo y Fecha.
Criterio de conservación:
1. Mayor cantidad de datos (length de intraday_bars) - Preferimos la data completa.
2. Si tienen la misma cantidad, fecha de actualización más reciente.

Elimina los registros redundantes de:
- trade_ohlc_snapshots
- trade_intraday_bars
"""

import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DuplicateCleanup")

DB_PATH = Path("trading_data.db")

def cleanup_duplicates():
    if not DB_PATH.exists():
        logger.error(f"❌ Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        logger.info("🔍 Scanning for duplicates...")

        # 1. Identificar grupos de duplicados (Symbol + TradingDate)
        # Obtenemos TODOS los snapshots para procesarlos en python (más flexible que SQL complejo)
        cursor.execute("SELECT id, trade_id, symbol, trading_date, intraday_bars, updated_at, created_at FROM trade_ohlc_snapshots")
        rows = cursor.fetchall()

        # Agrupar por (symbol, date)
        groups: Dict[Tuple[str, str], List[sqlite3.Row]] = {}
        for row in rows:
            key = (row['symbol'], row['trading_date'])
            if key not in groups:
                groups[key] = []
            groups[key].append(row)

        duplicates_found = 0
        records_to_delete = []
        trades_to_delete = []

        logger.info(f"📊 Found {len(groups)} unique Symbol/Date pairs.")

        for (symbol, date), group in groups.items():
            if len(group) > 1:
                duplicates_found += 1
                
                # Logic to find the "Best" record to KEEP
                # Calculate score for each: (data_length, update_timestamp)
                scored_records = []
                for rec in group:
                    data_len = len(rec['intraday_bars']) if rec['intraday_bars'] else 0
                    # Fallback to created_at if updated_at is null
                    ts = rec['updated_at'] or rec['created_at'] or "2000-01-01"
                    scored_records.append((data_len, ts, rec))

                # Sort descending: Max Length first, then Newest Date
                scored_records.sort(key=lambda x: (x[0], x[1]), reverse=True)

                winner = scored_records[0][2]
                losers = scored_records[1:]

                #logger.info(f"⚔️  Conflict for {symbol} on {date} ({len(group)} records):")
                #logger.info(f"   🏆 Keeping ID {winner['trade_id']} (Len: {len(winner['intraday_bars'] or '')})")
                
                for _, _, loser in losers:
                    #logger.info(f"   🗑️ Deleting ID {loser['trade_id']} (Len: {len(loser['intraday_bars'] or '')})")
                    records_to_delete.append(loser['id'])
                    trades_to_delete.append(loser['trade_id'])

        logger.info(f"⚠️  Found {duplicates_found} groups with duplicates.")
        logger.info(f"🗑️  Identified {len(records_to_delete)} redundant snapshots to delete.")

        if not records_to_delete:
            logger.info("✅ No cleanup needed.")
            return

        # Execute Deletion
        # 1. Remove from trade_ohlc_snapshots
        chunk_size = 500
        total_deleted_snapshots = 0
        
        for i in range(0, len(records_to_delete), chunk_size):
            chunk = records_to_delete[i:i + chunk_size]
            placeholders = ','.join(['?'] * len(chunk))
            cursor.execute(f"DELETE FROM trade_ohlc_snapshots WHERE id IN ({placeholders})", chunk)
            total_deleted_snapshots += cursor.rowcount
            conn.commit()

        # 2. Remove associated intraday bars (clean up child table)
        total_deleted_bars = 0
        for i in range(0, len(trades_to_delete), chunk_size):
            chunk = trades_to_delete[i:i + chunk_size]
            placeholders = ','.join(['?'] * len(chunk))
            cursor.execute(f"DELETE FROM trade_intraday_bars WHERE trade_id IN ({placeholders})", chunk)
            total_deleted_bars += cursor.rowcount
            conn.commit()

        logger.info("="*50)
        logger.info("✅ CLEANUP COMPLETE")
        logger.info(f"🗑️  Deleted {total_deleted_snapshots} duplicated snapshots.")
        logger.info(f"🗑️  Freed {total_deleted_bars} rows from intraday bars table.")
        logger.info("="*50)

    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    cleanup_duplicates()
