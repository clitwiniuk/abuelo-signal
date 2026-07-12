"""Classify a UTC timestamp into a US equity market session (PM/RTH/AH/Closed).

Uses standard broker session boundaries in US Eastern time (DST-aware via
zoneinfo, no manual UTC-offset math needed):
    04:00–09:30  Pre-market   (PM)
    09:30–16:00  Regular      (RTH)
    16:00–20:00  After-hours  (AH)
    everything else, incl. weekends  Closed
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")

_PM_START = time(4, 0)
_RTH_START = time(9, 30)
_AH_START = time(16, 0)
_AH_END = time(20, 0)

SESSIONS = ("PM", "RTH", "AH", "Closed")


def market_session(dt: datetime | None) -> str:
    """Classify a timestamp (assumed UTC if naive) into PM/RTH/AH/Closed."""
    if dt is None:
        return "Closed"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    local = dt.astimezone(_ET)

    if local.weekday() >= 5:  # Saturday/Sunday
        return "Closed"

    t = local.time()
    if _PM_START <= t < _RTH_START:
        return "PM"
    if _RTH_START <= t < _AH_START:
        return "RTH"
    if _AH_START <= t < _AH_END:
        return "AH"
    return "Closed"
