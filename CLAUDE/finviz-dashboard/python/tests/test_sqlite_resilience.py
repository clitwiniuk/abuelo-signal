import sqlite3
import sys
import threading
import time
from pathlib import Path


PYTHON_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_DIR))

from scheduler_guard import run_scheduler_cycle
from sqlite_writer import execute_write, insert_snapshot_rows


def _create_events_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE events (value INTEGER NOT NULL)")


def test_concurrent_writers_commit_every_row(tmp_path):
    db_path = tmp_path / "events.db"
    _create_events_db(db_path)

    def insert(value):
        execute_write(
            db_path,
            lambda conn: conn.execute("INSERT INTO events(value) VALUES (?)", (value,)),
        )

    threads = [
        threading.Thread(target=lambda offset=offset: [insert(offset + i) for i in range(20)])
        for offset in (0, 20, 40, 60)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 80


def test_write_retries_after_an_external_lock_is_released(tmp_path):
    db_path = tmp_path / "events.db"
    _create_events_db(db_path)
    holder = sqlite3.connect(db_path, check_same_thread=False)
    holder.execute("BEGIN IMMEDIATE")

    def release_lock():
        time.sleep(0.05)
        holder.rollback()
        holder.close()

    releaser = threading.Thread(target=release_lock)
    releaser.start()
    execute_write(
        db_path,
        lambda conn: conn.execute("INSERT INTO events(value) VALUES (1)"),
        timeout_seconds=0.01,
        retry_delays=(0.01, 0.02, 0.04, 0.08),
    )
    releaser.join()

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1


def test_snapshot_write_is_idempotent_for_the_same_snapshot(tmp_path):
    db_path = tmp_path / "snapshots.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE snapshots (
                timestamp TEXT, category TEXT, ticker TEXT,
                price TEXT, change_pct TEXT, volume TEXT
            )"""
        )

    rows = [{
        "category": "Top Gainers",
        "ticker": "TEST",
        "price": "1.00",
        "change_pct": "20%",
        "volume": "100K",
    }]
    write_snapshot = lambda: execute_write(
        db_path,
        lambda conn: insert_snapshot_rows(conn, rows, "2026-10-05T09:45:00-0400"),
    )

    write_snapshot()
    write_snapshot()

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 1


def test_scheduler_cycle_logs_failure_without_dying():
    def fail_once():
        raise RuntimeError("transient snapshot failure")

    errors = []
    messages = []

    class Logger:
        def exception(self, message):
            errors.append(message)

    error = run_scheduler_cycle(fail_once, Logger(), messages.append)

    assert isinstance(error, RuntimeError)
    assert errors == ["Scheduler cycle failed; continuing"]
    assert messages == ["Scheduler error: transient snapshot failure"]
