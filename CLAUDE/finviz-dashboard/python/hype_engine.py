"""
=============================================================
  Momentum Engine  (replaces volume-based hype engine)

  Metrics computed per ticker-day from Finviz snapshots:

    velocity     — slope of change_pct over time (%/min)
                   positive = momentum accelerating
                   negative = momentum dying
    persistence  — N snapshots seen in Top Gainers today
    mom_score    — composite: chg_initial × sign(vel) × log(1+persistence)
                   comparable across price ranges (all % based)

  Signal classification:
    "confirmed"     — vel>0, persistence>=8, chg 20-40%  → proven edge
    "accelerating"  — vel>0, chg 20-40%, persistence<8   → watch
    "topping"       — velocity turning negative            → avoid/exit
    "new"           — first/second appearance, no vel yet  → wait

  DB column mapping (backward-compat with frontend):
    hype_cum        ← mom_score
    rel_volume      ← persistence (N snapshots)
    delta_5m        ← velocity (%/min)
    delta_15m       ← chg_initial (% at first appearance)
    delta_1h        ← chg_now (% at latest snapshot)
    volume_1m       ← dollar_volume at entry (price × vol)
    price_change_1m ← price change last snapshot → previous
=============================================================
"""
import logging
import math
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd
import pytz

log = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")

# Signal thresholds (from empirical analysis on 14 days data)
CHG_LO, CHG_HI   = 20.0, 40.0   # proven edge bucket
VEL_ACC           = 0.0           # velocity > 0 = accelerating
PERSIST_CONFIRMED = 8             # ≥8 snapshots ≈ ≥2h in list → 100% WR


# ------------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------------

def compute_hype(db_path: str, day: str | None = None):
    """Compute and persist momentum metrics for today's tickers."""
    now_et = datetime.now(ET)
    if day is None:
        day = now_et.strftime("%Y-%m-%d")
    timestamp = now_et.strftime("%Y-%m-%dT%H:%M:%S%z")

    conn = sqlite3.connect(db_path)
    try:
        tickers = _get_finviz_tickers(conn, day)
        computed = 0
        for ticker in tickers:
            if _compute_momentum(conn, ticker, day, timestamp):
                computed += 1
        conn.commit()
        if computed:
            log.info(f"Momentum computed: {computed} tickers for {day}")
    finally:
        conn.close()


# ------------------------------------------------------------------
# CORE COMPUTATION
# ------------------------------------------------------------------

def _compute_momentum(conn, ticker: str, day: str, timestamp: str) -> bool:
    df = pd.read_sql(
        "SELECT timestamp, price, change_pct, volume FROM snapshots "
        "WHERE ticker=? AND timestamp LIKE ? AND category='Top Gainers' ORDER BY timestamp",
        conn, params=(ticker, f"{day}%")
    )
    if df.empty or len(df) < 1:
        return False

    df["price_f"]  = df["price"].apply(_parse_price)
    df["chg_f"]    = df["change_pct"].apply(_parse_chg)
    df["ts"]       = pd.to_datetime(df["timestamp"], utc=True)
    df["vol_num"]  = df["volume"].apply(_parse_volume)

    df = df[df["chg_f"].notna() & (df["chg_f"] > 0)].reset_index(drop=True)
    if df.empty:
        return False

    first = df.iloc[0]
    last  = df.iloc[-1]

    chg_initial   = float(first["chg_f"])
    chg_now       = float(last["chg_f"])
    price_entry   = float(first["price_f"]) if pd.notna(first["price_f"]) else 0.0
    price_now     = float(last["price_f"])  if pd.notna(last["price_f"])  else 0.0
    persistence   = len(df)
    dollar_vol    = price_entry * float(first["vol_num"]) if pd.notna(first["vol_num"]) else 0.0

    price_change  = price_now - float(df.iloc[-2]["price_f"]) if len(df) >= 2 and pd.notna(df.iloc[-2]["price_f"]) else 0.0

    # Velocity: linear regression of chg_f over elapsed minutes
    velocity = _compute_velocity(df)

    # Momentum score: directional, normalized, persistence-weighted
    mom_score = chg_initial * math.copysign(1, velocity) * math.log1p(persistence) if velocity != 0 else 0.0

    signal = _classify_signal(chg_initial, velocity, persistence)

    finviz_cat = _last_finviz_cat(conn, ticker, day)

    conn.execute(
        """INSERT OR REPLACE INTO hype_metrics
               (timestamp, ticker,
                volume_1m, rel_volume, hype_cum,
                delta_5m, delta_15m, delta_1h,
                close_price, price_change_1m,
                signal, finviz_category, source)
           VALUES (?,?, ?,?,?, ?,?,?, ?,?, ?,?,?)""",
        (
            timestamp, ticker,
            int(dollar_vol),        # volume_1m  ← dollar_volume at entry
            float(persistence),     # rel_volume ← persistence (N snapshots)
            float(mom_score),       # hype_cum   ← mom_score
            float(velocity),        # delta_5m   ← velocity (%/min)
            float(chg_initial),     # delta_15m  ← chg_initial
            float(chg_now),         # delta_1h   ← chg_now
            float(price_now),       # close_price
            float(price_change),    # price_change_1m
            signal,
            finviz_cat,
            "finviz",
        ),
    )
    return True


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def _compute_velocity(df: pd.DataFrame) -> float:
    """Slope of change_pct vs elapsed minutes (%/min). Returns 0 if insufficient data."""
    if len(df) < 2:
        return 0.0
    t0 = df["ts"].iloc[0]
    elapsed = [(t - t0).total_seconds() / 60.0 for t in df["ts"]]
    chg = df["chg_f"].values
    mask = ~np.isnan(chg)
    if mask.sum() < 2:
        return 0.0
    try:
        slope = float(np.polyfit(np.array(elapsed)[mask], chg[mask], 1)[0])
        return slope
    except Exception:
        return 0.0


def _classify_signal(chg_initial: float, velocity: float, persistence: int) -> str | None:
    in_bucket = CHG_LO <= chg_initial < CHG_HI
    if velocity < -0.01:
        return "topping"
    if persistence < 2:
        return "new"
    if in_bucket and velocity > VEL_ACC and persistence >= PERSIST_CONFIRMED:
        return "confirmed"   # 100% WR historically
    if in_bucket and velocity > VEL_ACC:
        return "accelerating"
    return None


def _get_finviz_tickers(conn, day: str) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM snapshots WHERE timestamp LIKE ? AND category='Top Gainers'",
        (f"{day}%",)
    ).fetchall()
    return {r[0] for r in rows}


def _last_finviz_cat(conn, ticker: str, day: str) -> str | None:
    row = conn.execute(
        "SELECT category FROM snapshots WHERE ticker=? AND timestamp LIKE ? ORDER BY id DESC LIMIT 1",
        (ticker, f"{day}%")
    ).fetchone()
    return row[0] if row else None


def _parse_volume(v) -> float:
    if not v:
        return 0.0
    s = str(v).upper().replace(",", "")
    try:
        if s.endswith("B"): return float(s[:-1]) * 1_000_000_000
        if s.endswith("M"): return float(s[:-1]) * 1_000_000
        if s.endswith("K"): return float(s[:-1]) * 1_000
        return float(s)
    except Exception:
        return 0.0


def _parse_price(v) -> float:
    try:
        return float(str(v).replace("$", "").replace(",", ""))
    except Exception:
        return 0.0


def _parse_chg(v) -> float | None:
    try:
        return float(str(v).replace("%", "").strip())
    except Exception:
        return None
