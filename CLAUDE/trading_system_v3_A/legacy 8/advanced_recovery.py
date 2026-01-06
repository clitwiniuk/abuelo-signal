#!/usr/bin/env python3
"""
Advanced SQLite Recovery - Extract full records from binary data
"""
import struct
import sqlite3
import re
from datetime import datetime

def extract_records_from_raw(db_file):
    """Extract complete trade records from raw database pages"""
    print(f"🔬 Advanced recovery from: {db_file}")

    with open(db_file, 'rb') as f:
        # Read page size from header
        f.seek(16)
        page_size = struct.unpack('>H', f.read(2))[0]
        print(f"📄 Page size: {page_size}")

        f.seek(0, 2)
        file_size = f.tell()
        num_pages = file_size // page_size
        print(f"📊 Total pages: {num_pages:,}")

        # Pattern to match complete trade records
        # Looking for sequences that contain trade_id pattern + symbol + dates
        trade_pattern = re.compile(
            rb'([A-Z]{2,5}_\d{8}_\d{6}_[a-f0-9]{8,})'  # trade_id
            rb'.{0,100}'  # gap
            rb'([A-Z]{2,5})'  # symbol
            rb'.{0,200}'  # gap
            rb'(20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'  # timestamp
        )

        all_matches = []
        recovered_trades = {}

        print("\n🔎 Scanning for trade records...")

        for page_num in range(num_pages):
            f.seek(page_num * page_size)
            page_data = f.read(page_size)

            # Find all trade patterns in this page
            matches = trade_pattern.findall(page_data)
            all_matches.extend(matches)

            if page_num % 10000 == 0 and page_num > 0:
                print(f"  Scanned {page_num:,} / {num_pages:,} pages... Found {len(all_matches)} patterns")

    print(f"\n✅ Found {len(all_matches)} potential trade records")

    # Parse matches into structured data
    for match in all_matches:
        try:
            trade_id = match[0].decode('utf-8', errors='ignore')
            symbol = match[1].decode('utf-8', errors='ignore')
            timestamp = match[2].decode('utf-8', errors='ignore')

            if trade_id not in recovered_trades:
                recovered_trades[trade_id] = {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'entry_time': timestamp
                }
        except:
            continue

    print(f"📦 Parsed {len(recovered_trades)} unique trades")
    return list(recovered_trades.values())

def save_to_database(trades, output_db):
    """Save recovered trades to new database"""
    print(f"\n💾 Saving to: {output_db}")

    conn = sqlite3.connect(output_db)
    cursor = conn.cursor()

    # Create minimal trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE,
            symbol TEXT,
            entry_time TIMESTAMP,
            recovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    inserted = 0
    for trade in trades:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO trades (trade_id, symbol, entry_time)
                VALUES (?, ?, ?)
            """, (trade['trade_id'], trade['symbol'], trade['entry_time']))
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            continue

    conn.commit()

    print(f"✅ Inserted {inserted} trades")

    # Statistics
    cursor.execute("SELECT COUNT(*) FROM trades")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT symbol) FROM trades")
    symbols = cursor.fetchone()[0]

    cursor.execute("SELECT symbol, COUNT(*) as cnt FROM trades GROUP BY symbol ORDER BY cnt DESC LIMIT 10")
    top_symbols = cursor.fetchall()

    print(f"\n📊 Recovery Statistics:")
    print(f"  Total trades: {total}")
    print(f"  Unique symbols: {symbols}")
    print(f"\n🏆 Top symbols:")
    for sym, cnt in top_symbols:
        print(f"    {sym}: {cnt} trades")

    conn.close()

if __name__ == "__main__":
    db_file = "trading_data.db.corrupted_backup"
    output_db = "trading_data_ADVANCED_RECOVERY.db"

    trades = extract_records_from_raw(db_file)
    save_to_database(trades, output_db)

    print(f"\n✅ Done! Recovery database: {output_db}")
