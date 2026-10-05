"""Small SQLite write boundary shared by the Finviz worker threads."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar


T = TypeVar("T")

# All writers in this process use the same lock. SQLite still remains the
# authority for cross-process contention; the retry loop below covers that
# case.
DB_WRITE_LOCK = threading.RLock()
DEFAULT_TIMEOUT_SECONDS = 1.0
DEFAULT_BUSY_TIMEOUT_MS = 1_000
DEFAULT_RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8, 1.6)


def execute_write(
    db_path: str | Path,
    operation: Callable[[sqlite3.Connection], T],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS,
) -> T:
    """Run one replayable transaction with process and SQLite contention handling.

    ``operation`` must contain only the transaction's writes and be safe to
    execute again. Retrying the complete operation is important because a
    failed commit can leave the connection unusable for the original attempt.
    """

    for attempt in range(len(retry_delays) + 1):
        try:
            with DB_WRITE_LOCK:
                conn = sqlite3.connect(str(db_path), timeout=timeout_seconds)
                conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
                try:
                    result = operation(conn)
                    conn.commit()
                    return result
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    conn.close()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == len(retry_delays):
                raise
            time.sleep(retry_delays[attempt])

    raise AssertionError("unreachable")
