#!/usr/bin/env python3
"""
Database Backup Restoration Tool
Interactive script to restore database from backup
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.database_backup_manager import DatabaseBackupManager
from datetime import datetime


def list_backups(manager):
    """List all available backups"""
    backups = manager.list_available_backups()

    if not backups:
        print("❌ No backups found")
        return None

    print("\n" + "=" * 80)
    print("📦 Available Database Backups")
    print("=" * 80)

    for idx, backup in enumerate(backups, 1):
        created = backup['created'].strftime("%Y-%m-%d %H:%M:%S")
        size = f"{backup['size_mb']:.2f} MB"
        corrupted = " ⚠️  CORRUPTED" if backup['is_corrupted'] else ""

        print(f"\n{idx}. {backup['filename']}")
        print(f"   Created: {created}")
        print(f"   Size: {size}{corrupted}")

    print("\n" + "=" * 80)

    return backups


def main():
    print("🔄 Database Backup Restoration Tool")
    print("=" * 80)

    # Initialize backup manager
    manager = DatabaseBackupManager(db_path="trading_data.db")

    # List available backups
    backups = list_backups(manager)

    if not backups:
        return

    # Ask user to select backup
    while True:
        try:
            selection = input("\n📋 Select backup number to restore (or 'q' to quit): ")

            if selection.lower() == 'q':
                print("👋 Cancelled")
                return

            idx = int(selection) - 1

            if 0 <= idx < len(backups):
                selected_backup = backups[idx]
                break
            else:
                print("❌ Invalid selection. Please try again.")

        except ValueError:
            print("❌ Invalid input. Please enter a number.")

    # Show selected backup
    print("\n" + "=" * 80)
    print(f"📦 Selected Backup: {selected_backup['filename']}")
    print(f"   Created: {selected_backup['created'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Size: {selected_backup['size_mb']:.2f} MB")

    if selected_backup['is_corrupted']:
        print("   ⚠️  WARNING: This backup was created from a corrupted database!")

    # Confirm restoration
    print("\n⚠️  WARNING: This will overwrite the current database!")
    print("   A backup of the current database will be created before restoration.")
    confirm = input("\n   Type 'YES' to confirm restoration: ")

    if confirm != "YES":
        print("👋 Restoration cancelled")
        return

    # Restore backup
    print("\n🔄 Restoring database...")

    success = manager.restore_from_backup(selected_backup['path'])

    if success:
        print("\n✅ Database restored successfully!")
        print(f"   Restored from: {selected_backup['filename']}")
        print(f"\n💡 Restart your trading system to use the restored database.")
    else:
        print("\n❌ Database restoration failed!")
        print("   Check the logs for details.")

    print("\n" + "=" * 80)


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
