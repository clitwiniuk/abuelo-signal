#!/usr/bin/env python3
"""
Enrich Recovered Trades
=======================

Updates recovered trades with additional information from trader.log:
- Strategy (daily_plays, vcp_smallcap, etc.)
- Trade session (DAY, SWING)
- Market context (CATALYST, BREAKOUT, etc.)
- Confidence level
- Trade type (scalp, swing, day)

Usage:
    python tools/enrich_recovered_trades.py --date 2025-11-21
"""

import re
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path


def extract_trade_metadata(log_lines, trade_id):
    """Extract all available metadata for a trade from log lines."""
    metadata = {
        'strategy': None,
        'trade_session': None,
        'market_context': None,
        'confidence': None,
        'trade_type': None
    }

    # Find the trade ID in logs
    for i, line in enumerate(log_lines):
        if f"Trade ID: {trade_id}" in line:
            # Extract strategy from ExecutionEngineAdapter line
            worker_match = re.search(
                r'(daily_plays|vcp_smallcap|momentum_surge|gap_and_go|ods_universal|ods_swing_universal|orb_breakout):',
                line
            )
            if worker_match:
                metadata['strategy'] = worker_match.group(1)

            # Look ahead for more context
            for j in range(i, min(i + 10, len(log_lines))):
                context_line = log_lines[j]

                # Extract trade type: [scalp, 1.0h]
                type_match = re.search(r'\[(scalp|swing|day),\s*([0-9.]+)h\]', context_line)
                if type_match:
                    metadata['trade_type'] = type_match.group(1)

                # Extract session: "Registered DAY position"
                session_match = re.search(r'Registered (DAY|SWING) position:', context_line)
                if session_match:
                    metadata['trade_session'] = session_match.group(1)

                # Extract market context: "Context(FOXX): CATALYST (conf=90%"
                context_match = re.search(r'Context\([A-Z]+\):\s+(\w+)\s+\(conf=(\d+)%', context_line)
                if context_match:
                    metadata['market_context'] = context_match.group(1)
                    metadata['confidence'] = int(context_match.group(2)) / 100.0

            break

    return metadata


def enrich_trades(db_path, log_path, target_date):
    """Enrich recovered trades with metadata from log."""
    print(f"\n📖 Reading log file: {log_path}")
    print(f"🎯 Target date: {target_date}\n")

    with open(log_path, 'r') as f:
        log_lines = f.readlines()

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all trades from target date
    date_str = target_date.strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT trade_id, symbol, strategy, trade_session, market_context, confidence
        FROM trades
        WHERE date(entry_time) = ?
    """, (date_str,))

    trades = cursor.fetchall()
    print(f"📊 Found {len(trades)} trades from {date_str}\n")

    updated = 0
    for trade_id, symbol, current_strategy, current_session, current_context, current_confidence in trades:
        # Extract metadata from log
        metadata = extract_trade_metadata(log_lines, trade_id)

        # Build update query
        updates = []
        values = []

        if metadata['strategy'] and metadata['strategy'] != current_strategy:
            updates.append('strategy = ?')
            values.append(metadata['strategy'])

        if metadata['trade_session'] and metadata['trade_session'] != current_session:
            updates.append('trade_session = ?')
            values.append(metadata['trade_session'])

        if metadata['market_context'] and metadata['market_context'] != current_context:
            updates.append('market_context = ?')
            values.append(metadata['market_context'])

        if metadata['confidence'] is not None and metadata['confidence'] != current_confidence:
            updates.append('confidence = ?')
            values.append(metadata['confidence'])

        if updates:
            # Append audit note
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            audit_note = f"\n[{timestamp}] Enriched with log data: {', '.join(k for k in metadata.keys() if metadata[k])}"
            updates.append('notes = COALESCE(notes, "") || ?')
            values.append(audit_note)

            # Update timestamp
            updates.append('updated_at = CURRENT_TIMESTAMP')

            # Execute update
            values.append(trade_id)
            query = f"UPDATE trades SET {', '.join(updates)} WHERE trade_id = ?"

            cursor.execute(query, values)

            # Show what was updated
            updated_fields = [k for k in metadata.keys() if metadata[k]]
            print(f"✅ Updated {symbol} (ID: {trade_id}): {', '.join(updated_fields)}")
            print(f"   Strategy: {metadata['strategy']}, Session: {metadata['trade_session']}, "
                  f"Context: {metadata['market_context']}, Confidence: {metadata['confidence']}")
            updated += 1
        else:
            print(f"⏭️  Skipped {symbol} (ID: {trade_id}) - no new data")

    conn.commit()
    conn.close()

    print(f"\n📊 Summary:")
    print(f"   ✅ Updated: {updated}")
    print(f"   ⏭️  Skipped: {len(trades) - updated}")
    print(f"   📝 Total: {len(trades)}")

    return updated


def main():
    parser = argparse.ArgumentParser(description='Enrich recovered trades with log metadata')
    parser.add_argument('--date', type=str, required=True,
                       help='Date to enrich trades for (YYYY-MM-DD)')
    parser.add_argument('--log', type=str,
                       default='logs/trader.log',
                       help='Path to trader.log file')
    parser.add_argument('--db', type=str,
                       default='trading_data.db',
                       help='Path to trading_data.db')

    args = parser.parse_args()

    # Parse date
    try:
        target_date = datetime.strptime(args.date, '%Y-%m-%d')
    except ValueError:
        print(f"❌ Invalid date format: {args.date}. Use YYYY-MM-DD")
        return 1

    # Check if log file exists
    log_path = Path(args.log)
    if not log_path.exists():
        print(f"❌ Log file not found: {log_path}")
        return 1

    # Check if database exists
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return 1

    print("=" * 60)
    print("📦 Trade Enrichment Tool")
    print("=" * 60)

    # Enrich trades
    updated = enrich_trades(db_path, log_path, target_date)

    print(f"\n✅ Enrichment complete! {updated} trades updated.")
    print(f"💡 Note: Exit prices and P&L must be added manually in TradeTally")

    return 0


if __name__ == '__main__':
    exit(main())
