#!/usr/bin/env python3
"""
Database Duplicate Cleanup Tool
Removes duplicate entries from various tables while preserving the most recent/important data
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class DuplicateCleanup:
    """Clean up duplicate entries in database"""

    def __init__(self, db_path: str = "trading_data.db", dry_run: bool = True):
        """
        Initialize cleanup tool

        Args:
            db_path: Path to database
            dry_run: If True, only report what would be deleted (don't actually delete)
        """
        self.db_path = db_path
        self.dry_run = dry_run
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        self.stats = {
            'scanner_opportunities': 0,
            'trade_ohlc_snapshots': 0,
            'market_intraday_bars': 0,
            'trade_intraday_bars': 0,
            'trades': 0
        }

    def cleanup_scanner_opportunities(self):
        """
        Clean up scanner_opportunities duplicates

        Strategy: Keep only the LATEST entry per symbol per day
        Rationale: Multiple scans of same symbol same day are redundant
        """
        print("\n" + "=" * 80)
        print("🔍 Cleaning scanner_opportunities duplicates...")
        print("=" * 80)

        # Find duplicates
        self.cursor.execute("""
            SELECT symbol, DATE(timestamp) as date, COUNT(*) as count
            FROM scanner_opportunities
            GROUP BY symbol, DATE(timestamp)
            HAVING count > 1
            ORDER BY count DESC
        """)

        duplicates = self.cursor.fetchall()

        if not duplicates:
            print("✅ No duplicates found in scanner_opportunities")
            return

        print(f"\n📊 Found {len(duplicates)} symbols with duplicate entries")
        print(f"   Top duplicates:")

        for symbol, date, count in duplicates[:10]:
            print(f"   - {symbol} on {date}: {count} entries")

        # Calculate total duplicates to remove
        total_duplicates = sum(count - 1 for _, _, count in duplicates)
        print(f"\n🗑️  Total entries to remove: {total_duplicates:,}")

        if self.dry_run:
            print("   ⚠️  DRY RUN - No data will be deleted")
            self.stats['scanner_opportunities'] = total_duplicates
            return

        # Delete duplicates, keeping only the latest per symbol per day
        self.cursor.execute("""
            DELETE FROM scanner_opportunities
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM scanner_opportunities
                GROUP BY symbol, DATE(timestamp)
            )
        """)

        deleted = self.cursor.rowcount
        self.stats['scanner_opportunities'] = deleted
        print(f"✅ Deleted {deleted:,} duplicate scanner opportunities")

    def cleanup_trade_splits(self):
        """
        Clean up trade splits (trades with _split_ in trade_id)

        Strategy: Keep splits only if they're active, otherwise remove
        """
        print("\n" + "=" * 80)
        print("🔍 Cleaning trade splits...")
        print("=" * 80)

        # Find split trades
        self.cursor.execute("""
            SELECT COUNT(*)
            FROM trades
            WHERE trade_id LIKE '%_split_%'
        """)

        split_count = self.cursor.fetchone()[0]

        if split_count == 0:
            print("✅ No split trades found")
            return

        print(f"📊 Found {split_count} split trades")

        # Find closed split trades
        self.cursor.execute("""
            SELECT COUNT(*)
            FROM trades
            WHERE trade_id LIKE '%_split_%' AND status = 'CLOSED'
        """)

        closed_splits = self.cursor.fetchone()[0]

        print(f"   - {closed_splits} closed split trades (safe to review)")
        print(f"   - {split_count - closed_splits} open split trades (keeping)")

        if self.dry_run:
            print("   ⚠️  DRY RUN - No data will be deleted")
            print("   💡 Note: Split trades are usually intentional, review manually")
            return

        print("   ℹ️  Split trades are usually intentional - skipping automatic deletion")
        print("   💡 Review manually if needed")

    def cleanup_old_intraday_bars(self, days_to_keep: int = 90):
        """
        Clean up old intraday bars (older than N days)

        Strategy: Keep last 90 days, delete older
        """
        print("\n" + "=" * 80)
        print(f"🔍 Cleaning old intraday bars (keeping last {days_to_keep} days)...")
        print("=" * 80)

        tables = ['trade_intraday_bars', 'market_intraday_bars']

        for table in tables:
            # Check if table exists
            self.cursor.execute(f"""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='{table}'
            """)

            if not self.cursor.fetchone():
                print(f"⚠️  Table {table} not found - skipping")
                continue

            # Count old entries
            # Different tables use different column names for timestamp
            timestamp_col = 'bar_timestamp' if 'intraday_bars' in table else 'timestamp'

            self.cursor.execute(f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE {timestamp_col} < datetime('now', '-{days_to_keep} days')
            """)

            old_count = self.cursor.fetchone()[0]

            if old_count == 0:
                print(f"✅ No old entries in {table}")
                continue

            print(f"📊 {table}: {old_count:,} entries older than {days_to_keep} days")

            if self.dry_run:
                print(f"   ⚠️  DRY RUN - No data will be deleted")
                self.stats[table] = old_count
                continue

            # Delete old entries
            timestamp_col = 'bar_timestamp' if 'intraday_bars' in table else 'timestamp'

            self.cursor.execute(f"""
                DELETE FROM {table}
                WHERE {timestamp_col} < datetime('now', '-{days_to_keep} days')
            """)

            deleted = self.cursor.rowcount
            self.stats[table] = deleted
            print(f"✅ Deleted {deleted:,} old entries from {table}")

    def cleanup_orphaned_snapshots(self):
        """
        Clean up trade_ohlc_snapshots for trades that no longer exist
        """
        print("\n" + "=" * 80)
        print("🔍 Cleaning orphaned trade snapshots...")
        print("=" * 80)

        # Check if table exists
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='trade_ohlc_snapshots'
        """)

        if not self.cursor.fetchone():
            print("⚠️  Table trade_ohlc_snapshots not found - skipping")
            return

        # Find orphaned snapshots
        self.cursor.execute("""
            SELECT COUNT(*)
            FROM trade_ohlc_snapshots
            WHERE trade_id NOT IN (SELECT trade_id FROM trades)
        """)

        orphaned_count = self.cursor.fetchone()[0]

        if orphaned_count == 0:
            print("✅ No orphaned snapshots found")
            return

        print(f"📊 Found {orphaned_count:,} orphaned snapshots")

        if self.dry_run:
            print("   ⚠️  DRY RUN - No data will be deleted")
            self.stats['trade_ohlc_snapshots'] = orphaned_count
            return

        # Delete orphaned snapshots
        self.cursor.execute("""
            DELETE FROM trade_ohlc_snapshots
            WHERE trade_id NOT IN (SELECT trade_id FROM trades)
        """)

        deleted = self.cursor.rowcount
        self.stats['trade_ohlc_snapshots'] = deleted
        print(f"✅ Deleted {deleted:,} orphaned snapshots")

    def analyze_database(self):
        """Analyze database and show statistics"""
        print("\n" + "=" * 80)
        print("📊 Database Analysis")
        print("=" * 80)

        tables = [
            'trades',
            'scanner_opportunities',
            'trade_ohlc_snapshots',
            'trade_intraday_bars',
            'market_intraday_bars'
        ]

        for table in tables:
            # Check if table exists
            self.cursor.execute(f"""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='{table}'
            """)

            if not self.cursor.fetchone():
                continue

            # Get count
            self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = self.cursor.fetchone()[0]

            # Get size
            self.cursor.execute(f"""
                SELECT page_count * page_size as size
                FROM pragma_page_count(), pragma_page_size()
            """)

            print(f"\n📋 {table}")
            print(f"   Rows: {count:,}")

            # Table-specific analysis
            if table == 'scanner_opportunities':
                self.cursor.execute("""
                    SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT DATE(timestamp))
                    FROM scanner_opportunities
                """)
                unique_symbols, unique_days = self.cursor.fetchone()
                print(f"   Unique symbols: {unique_symbols}")
                print(f"   Unique days: {unique_days}")

            elif table == 'trades':
                self.cursor.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE status='OPEN') as open_trades,
                        COUNT(*) FILTER (WHERE status='CLOSED') as closed_trades,
                        COUNT(*) FILTER (WHERE trade_id LIKE '%_split_%') as split_trades
                    FROM trades
                """)
                open_t, closed_t, split_t = self.cursor.fetchone()
                print(f"   Open: {open_t}, Closed: {closed_t}, Splits: {split_t}")

    def run_cleanup(self):
        """Run all cleanup operations"""
        print("🧹 Database Duplicate Cleanup Tool")
        print("=" * 80)

        if self.dry_run:
            print("⚠️  DRY RUN MODE - No data will be deleted")
            print("   Run with --execute to actually delete duplicates")
        else:
            print("🔴 EXECUTE MODE - Data will be deleted!")

        # Analyze first
        self.analyze_database()

        # Run cleanups
        self.cleanup_scanner_opportunities()
        self.cleanup_trade_splits()
        self.cleanup_old_intraday_bars(days_to_keep=90)
        self.cleanup_orphaned_snapshots()

        # Summary
        print("\n" + "=" * 80)
        print("📊 Cleanup Summary")
        print("=" * 80)

        total_removed = sum(self.stats.values())

        for table, count in self.stats.items():
            if count > 0:
                print(f"   {table}: {count:,} entries")

        print(f"\n   Total entries removed: {total_removed:,}")

        if not self.dry_run and total_removed > 0:
            # Commit changes
            self.conn.commit()
            print("\n✅ Changes committed to database")

            # Vacuum to reclaim space
            print("\n🗜️  Running VACUUM to reclaim space...")
            self.conn.execute("VACUUM")
            print("✅ Database optimized")

        print("\n" + "=" * 80)

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Clean up duplicate data in trading database")
    parser.add_argument('--execute', action='store_true', help='Actually delete duplicates (default is dry-run)')
    parser.add_argument('--db', default='trading_data.db', help='Database path')
    parser.add_argument('--keep-days', type=int, default=90, help='Days of intraday bars to keep (default: 90)')

    args = parser.parse_args()

    dry_run = not args.execute

    print(f"\n📁 Database: {args.db}")

    if dry_run:
        print("⚠️  Running in DRY RUN mode (no changes will be made)")
        print("   Use --execute to actually delete duplicates\n")
    else:
        print("🔴 Running in EXECUTE mode (data WILL be deleted)")
        confirm = input("\n   Type 'YES' to confirm: ")
        if confirm != 'YES':
            print("👋 Cancelled")
            return

    cleanup = DuplicateCleanup(db_path=args.db, dry_run=dry_run)

    try:
        cleanup.run_cleanup()
    finally:
        cleanup.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
