#!/usr/bin/env python3
"""
Database Cleanup Script
Removes old duplicate copies of trading_data.db while keeping the main database and official backups
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Main database (DO NOT DELETE)
MAIN_DB = PROJECT_ROOT / "trading_data.db"

# Official backup directory (DO NOT DELETE)
BACKUP_DIR = PROJECT_ROOT / "backups" / "database"

# Directories with old duplicate copies to clean
CLEANUP_TARGETS = [
    PROJECT_ROOT / "data" / "backup" / "trading_data.db",  # 197 MB old copy
    PROJECT_ROOT / "tests" / "trading_data.db",  # 1.4 MB test copy
    PROJECT_ROOT / "tests" / "comprehensive" / "trading_data.db",  # 56 KB
    PROJECT_ROOT / "production" / "trading_data.db",  # 56 KB
    PROJECT_ROOT / "tradetally" / "backend" / "trading_data.db",  # 168 KB
    PROJECT_ROOT / "tradetally" / "trading_data.db",  # 4 KB
    PROJECT_ROOT / "scientific_backtest" / "trading_data.db",  # 0 bytes
    PROJECT_ROOT / "data" / "trading_data.db",  # 0 bytes
]

def get_file_size_mb(path: Path) -> float:
    """Get file size in MB"""
    if path.exists() and path.is_file():
        return path.stat().st_size / (1024 * 1024)
    return 0.0

def main():
    print("=" * 70)
    print("🧹 Database Cleanup Script")
    print("=" * 70)
    print()
    
    # Verify main database exists
    if not MAIN_DB.exists():
        print(f"❌ Main database not found: {MAIN_DB}")
        return
    
    main_size = get_file_size_mb(MAIN_DB)
    print(f"✅ Main database: {MAIN_DB.name} ({main_size:.2f} MB)")
    print()
    
    # Check backup directory
    if BACKUP_DIR.exists():
        backup_files = list(BACKUP_DIR.glob("trading_data_*.db"))
        backup_size = sum(get_file_size_mb(f) for f in backup_files if not f.is_symlink())
        print(f"✅ Official backups: {len(backup_files)} files ({backup_size:.2f} MB)")
        print(f"   Location: {BACKUP_DIR}")
    else:
        print(f"⚠️  Backup directory not found: {BACKUP_DIR}")
    
    print()
    print("=" * 70)
    print("🔍 Scanning for duplicate copies...")
    print("=" * 70)
    print()
    
    total_to_delete = 0.0
    files_to_delete = []
    
    for target in CLEANUP_TARGETS:
        if target.exists() and target.is_file():
            size = get_file_size_mb(target)
            total_to_delete += size
            files_to_delete.append((target, size))
            print(f"📁 {target.relative_to(PROJECT_ROOT)}")
            print(f"   Size: {size:.2f} MB")
            print()
    
    if not files_to_delete:
        print("✅ No duplicate copies found - database is clean!")
        return
    
    print("=" * 70)
    print(f"📊 Summary:")
    print(f"   Files to delete: {len(files_to_delete)}")
    print(f"   Space to recover: {total_to_delete:.2f} MB")
    print("=" * 70)
    print()
    
    # Ask for confirmation
    response = input("⚠️  Delete these duplicate copies? (yes/no): ").strip().lower()
    
    if response != "yes":
        print("❌ Cleanup cancelled")
        return
    
    print()
    print("🗑️  Deleting duplicate copies...")
    print()
    
    deleted_count = 0
    deleted_size = 0.0
    
    for file_path, size in files_to_delete:
        try:
            file_path.unlink()
            deleted_count += 1
            deleted_size += size
            print(f"✅ Deleted: {file_path.relative_to(PROJECT_ROOT)} ({size:.2f} MB)")
        except Exception as e:
            print(f"❌ Failed to delete {file_path.name}: {e}")
    
    print()
    print("=" * 70)
    print(f"✅ Cleanup completed!")
    print(f"   Files deleted: {deleted_count}/{len(files_to_delete)}")
    print(f"   Space recovered: {deleted_size:.2f} MB")
    print("=" * 70)
    print()
    print("💡 Note: The main database and official backups were preserved:")
    print(f"   Main: {MAIN_DB}")
    print(f"   Backups: {BACKUP_DIR}")

if __name__ == "__main__":
    main()
