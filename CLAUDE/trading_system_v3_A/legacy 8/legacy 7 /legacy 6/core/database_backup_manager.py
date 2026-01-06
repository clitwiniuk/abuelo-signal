"""
Database Backup Manager
Automatic backups after market close integrated with trading system scheduler
"""

import os
import sqlite3
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class DatabaseBackupManager:
    """
    Manages automatic database backups integrated with market calendar

    Features:
    - Automatic backup after market close (coordinated with EOD scheduler)
    - Integrity check before backup
    - Keeps last 30 days of backups
    - Creates daily snapshot + timestamped backups
    - Validates backup after creation
    """

    def __init__(self, db_path: str = "trading_data.db", backup_dir: str = "backups/database"):
        """
        Initialize backup manager

        Args:
            db_path: Path to database file
            backup_dir: Directory to store backups
        """
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.logger = logging.getLogger("DatabaseBackup")

        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Track last backup
        self.last_backup_date = None

        self.logger.info(f"💾 Database Backup Manager initialized")
        self.logger.info(f"   Database: {self.db_path}")
        self.logger.info(f"   Backup dir: {self.backup_dir}")

    def should_backup_today(self) -> bool:
        """Check if backup is needed today"""
        today = datetime.now().date()

        # Check if already backed up today
        if self.last_backup_date == today:
            self.logger.debug("✅ Already backed up today")
            return False

        return True

    def check_database_integrity(self) -> tuple[bool, str]:
        """
        Check database integrity

        Returns:
            (is_ok, message)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()[0]
            conn.close()

            if result == "ok":
                return True, "Database integrity OK"
            else:
                return False, f"Integrity check failed: {result}"

        except Exception as e:
            return False, f"Integrity check error: {e}"

    def create_backup(self, force: bool = False) -> Optional[str]:
        """
        Create database backup

        Args:
            force: Force backup even if already backed up today

        Returns:
            Path to backup file or None if failed
        """
        # Check if backup needed
        if not force and not self.should_backup_today():
            return None

        timestamp = datetime.now()
        date_str = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%H%M%S")

        self.logger.info("=" * 60)
        self.logger.info(f"💾 Starting database backup - {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        # Check if database exists
        if not os.path.exists(self.db_path):
            self.logger.error(f"❌ Database not found: {self.db_path}")
            return None

        # Get database size
        db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
        self.logger.info(f"📊 Database size: {db_size_mb:.2f} MB")

        # Check integrity
        self.logger.info("🔍 Checking database integrity...")
        is_ok, message = self.check_database_integrity()
        self.logger.info(f"   {message}")

        # Create backup filename
        if not is_ok:
            backup_filename = f"trading_data_{date_str}_{time_str}_CORRUPTED.db"
            self.logger.warning("⚠️  Creating backup of corrupted database")
        else:
            backup_filename = f"trading_data_{date_str}_{time_str}.db"

        backup_path = self.backup_dir / backup_filename

        # Create backup using SQLite backup API (safe for active databases)
        try:
            self.logger.info(f"💾 Creating backup: {backup_filename}")

            source_conn = sqlite3.connect(self.db_path)
            backup_conn = sqlite3.connect(str(backup_path))

            # Use SQLite backup API
            source_conn.backup(backup_conn)

            source_conn.close()
            backup_conn.close()

            backup_size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            self.logger.info(f"✅ Backup created: {backup_size_mb:.2f} MB")

            # Validate backup
            self.logger.info("🔍 Validating backup...")
            backup_is_ok, backup_msg = self._validate_backup(str(backup_path))

            if backup_is_ok:
                self.logger.info(f"✅ {backup_msg}")
            else:
                self.logger.warning(f"⚠️  {backup_msg}")

            # Create/update "latest" symlink
            latest_link = self.backup_dir / "trading_data_latest.db"
            if latest_link.exists() or latest_link.is_symlink():
                latest_link.unlink()
            latest_link.symlink_to(backup_filename)

            # Create daily backup (overwrite if exists for same day)
            daily_backup = self.backup_dir / f"trading_data_daily_{date_str}.db"
            shutil.copy2(backup_path, daily_backup)
            self.logger.info(f"📅 Daily backup: {daily_backup.name}")

            # Update last backup date
            self.last_backup_date = datetime.now().date()

            # Cleanup old backups
            self._cleanup_old_backups()

            self.logger.info("✅ Backup process completed successfully")
            self.logger.info("=" * 60)

            return str(backup_path)

        except Exception as e:
            self.logger.error(f"❌ Backup failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def _validate_backup(self, backup_path: str) -> tuple[bool, str]:
        """
        Validate backup file

        Returns:
            (is_valid, message)
        """
        try:
            conn = sqlite3.connect(backup_path)
            cursor = conn.cursor()

            # Check integrity
            cursor.execute("PRAGMA integrity_check;")
            integrity = cursor.fetchone()[0]

            if integrity != "ok":
                conn.close()
                return False, f"Backup integrity check failed: {integrity}"

            # Count trades
            cursor.execute("SELECT COUNT(*) FROM trades;")
            trade_count = cursor.fetchone()[0]

            conn.close()

            return True, f"Backup validated - {trade_count} trades"

        except Exception as e:
            return False, f"Backup validation error: {e}"

    def _cleanup_old_backups(self):
        """Clean up old backup files (keep last 30 days)"""
        try:
            self.logger.info("🧹 Cleaning up old backups...")

            cutoff_date = datetime.now() - timedelta(days=30)
            deleted_count = 0

            # Delete timestamped backups older than 30 days
            for backup_file in self.backup_dir.glob("trading_data_*_*.db"):
                # Skip daily backups and "latest" symlink
                if "daily" in backup_file.name or backup_file.is_symlink():
                    continue

                file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_mtime < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1

            # Keep only last 7 daily backups
            daily_backups = sorted(
                self.backup_dir.glob("trading_data_daily_*.db"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            for old_daily in daily_backups[7:]:
                old_daily.unlink()
                deleted_count += 1

            if deleted_count > 0:
                self.logger.info(f"🗑️  Deleted {deleted_count} old backup(s)")

            # Show statistics
            remaining_backups = len(list(self.backup_dir.glob("trading_data_*.db")))
            total_size_mb = sum(
                f.stat().st_size for f in self.backup_dir.glob("trading_data_*.db")
                if not f.is_symlink()
            ) / (1024 * 1024)

            self.logger.info(f"📦 Total backups: {remaining_backups}")
            self.logger.info(f"💾 Backup directory size: {total_size_mb:.2f} MB")

        except Exception as e:
            self.logger.error(f"❌ Cleanup error: {e}")

    def restore_from_backup(self, backup_path: str) -> bool:
        """
        Restore database from backup

        Args:
            backup_path: Path to backup file

        Returns:
            True if successful
        """
        try:
            self.logger.info(f"🔄 Restoring from backup: {backup_path}")

            # Validate backup first
            is_valid, msg = self._validate_backup(backup_path)
            if not is_valid:
                self.logger.error(f"❌ Cannot restore - {msg}")
                return False

            self.logger.info(f"✅ {msg}")

            # Create backup of current database before restore
            if os.path.exists(self.db_path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                pre_restore_backup = f"{self.db_path}.pre_restore_{timestamp}"
                shutil.copy2(self.db_path, pre_restore_backup)
                self.logger.info(f"💾 Current database backed up to: {pre_restore_backup}")

            # Restore
            shutil.copy2(backup_path, self.db_path)
            self.logger.info(f"✅ Database restored successfully")

            return True

        except Exception as e:
            self.logger.error(f"❌ Restore failed: {e}")
            return False

    def list_available_backups(self) -> list[dict]:
        """
        List all available backups

        Returns:
            List of backup info dicts
        """
        backups = []

        for backup_file in sorted(
            self.backup_dir.glob("trading_data_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            if backup_file.is_symlink():
                continue

            stat = backup_file.stat()
            size_mb = stat.st_size / (1024 * 1024)
            mtime = datetime.fromtimestamp(stat.st_mtime)

            backups.append({
                "filename": backup_file.name,
                "path": str(backup_file),
                "size_mb": size_mb,
                "created": mtime,
                "is_corrupted": "CORRUPTED" in backup_file.name
            })

        return backups
