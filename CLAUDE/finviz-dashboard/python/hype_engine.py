"""
=============================================================
  Hype Engine
  Computes intraday hype/momentum metrics per ticker.

  Two data sources (auto-detected, best available):
    1. market_bars  — 1-min OHLCV from IBKR (precise)
    2. snapshots    — 5-min cumulative volume from Finviz (fallback)
=============================================================
"""
import sqlite3
import logging
from datetime import datetime

import pandas as pd
import pytz

log = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")

SPIKE_THRESHOLD   = 2.5   # rel_volume > X  → "spike"
TRENDING_DELTA    = 3.0   # delta_5m   > X  → "trending"
EARLY_MOM_DELTA   = 1.5   # delta_5m   > X  → "early_momentum"


# ------------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------------

def compute_hype(db_path: str, day: str | None = None):
    """Compute and persist hype metrics for today's tickers."""
    now_et = datetime.now(ET)
    if day is None:
        day = now_et.strftime("%Y-%m-%d")
    timestamp = now_et.strftime("%Y-%m-%dT%H:%M:%S%z")

    conn = sqlite3.connect(db_path)
    try:
        ibkr_tickers = _get_ibkr_tickers(conn, day)
        finviz_tickers = _get_finviz_tickers(conn, day)

        computed = 0
        for ticker in ibkr_tickers:
            if _compute_from_bars(conn, ticker, day, timestamp):
                computed += 1

        for ticker in finviz_tickers - ibkr_tickers:
            if _compute_from_snapshots(conn, ticker, day, timestamp):
                computed += 1

        conn.commit()
        if computed:
            log.info(f"Hype computed: {computed} tickers ({len(ibkr_tickers)} IBKR, "
                     f"{len(finviz_tickers - ibkr_tickers)} Finviz fallback)")
    finally:
        conn.close()


# ------------------------------------------------------------------
# IBKR BARS PATH (1-min precision)
# ------------------------------------------------------------------

def _get_ibkr_tickers(conn, day: str) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM market_bars WHERE bar_time LIKE ?",
        (f"{day}%",)
    ).fetchall()
    return {r[0] for r in rows}


def _compute_from_bars(conn, ticker: str, day: str, timestamp: str) -> bool:
    df = pd.read_sql(
        "SELECT bar_time, open, high, low, close, volume FROM market_bars "
        "WHERE ticker=? AND bar_time LIKE ? ORDER BY bar_time",
        conn, params=(ticker, f"{day}%")
    )
    if df.empty or len(df) < 2:
        return False

    avg_vol = df["volume"].replace(0, pd.NA).mean()
    if not avg_vol or avg_vol == 0:
        return False

    df["rel_vol"] = df["volume"] / avg_vol
    df["hype_cum"] = df["rel_vol"].cumsum()

    finviz_cat = _last_finviz_cat(conn, ticker, day)

    # Guardar UNA FILA POR BAR — así el gráfico tiene resolución de 1 minuto
    for pos in range(1, len(df)):
        row  = df.iloc[pos]
        prev = df.iloc[pos - 1]
        sub  = df.iloc[:pos + 1]

        rel_vol   = float(row["rel_vol"])
        hype_cum  = float(row["hype_cum"])
        close     = float(row["close"])
        price_chg = close - float(prev["close"])

        delta_5m  = _delta(sub, 5)
        delta_15m = _delta(sub, 15)
        delta_1h  = _delta(sub, 60)
        signal    = _signal(rel_vol, delta_5m)

        bar_ts = str(row["bar_time"])

        conn.execute(
            """INSERT OR REPLACE INTO hype_metrics
                   (timestamp, ticker, volume_1m, rel_volume, hype_cum,
                    delta_5m, delta_15m, delta_1h, close_price, price_change_1m,
                    signal, finviz_category, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (bar_ts, ticker, int(row["volume"]), rel_vol, hype_cum,
             delta_5m, delta_15m, delta_1h, close, price_chg,
             signal, finviz_cat, "ibkr"),
        )
    return True


# ------------------------------------------------------------------
# FINVIZ FALLBACK PATH (5-min snapshots)
# ------------------------------------------------------------------

def _get_finviz_tickers(conn, day: str) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM snapshots WHERE timestamp LIKE ?",
        (f"{day}%",)
    ).fetchall()
    return {r[0] for r in rows}


def _compute_from_snapshots(conn, ticker: str, day: str, timestamp: str) -> bool:
    df = pd.read_sql(
        "SELECT timestamp, price, change_pct, volume FROM snapshots "
        "WHERE ticker=? AND timestamp LIKE ? ORDER BY timestamp",
        conn, params=(ticker, f"{day}%")
    )
    if df.empty or len(df) < 2:
        return False

    df["vol_num"] = df["volume"].apply(_parse_volume)
    # Incremental volume per snapshot window (difference of cumulative totals)
    df["vol_delta"] = df["vol_num"].diff().fillna(df["vol_num"])
    df["vol_delta"] = df["vol_delta"].clip(lower=0)

    avg_delta = df["vol_delta"].replace(0, pd.NA).mean()
    if not avg_delta or avg_delta == 0:
        return False

    df["rel_vol"] = df["vol_delta"] / avg_delta
    df["hype_cum"] = df["rel_vol"].cumsum()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    hype_cum  = float(last["hype_cum"])
    rel_vol   = float(last["rel_vol"])
    price_chg = _parse_price(last["price"]) - _parse_price(prev["price"])
    close     = _parse_price(last["price"])

    # Each snapshot = ~5 min → delta_5m = last bar, delta_15m = last 3, delta_1h = last 12
    delta_5m  = _delta(df, 1)
    delta_15m = _delta(df, 3)
    delta_1h  = _delta(df, 12)
    signal    = _signal(rel_vol, delta_5m)

    finviz_cat = _last_finviz_cat(conn, ticker, day)

    conn.execute(
        """INSERT INTO hype_metrics
               (timestamp, ticker, volume_1m, rel_volume, hype_cum,
                delta_5m, delta_15m, delta_1h, close_price, price_change_1m,
                signal, finviz_category, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (timestamp, ticker, int(last["vol_num"]), rel_vol, hype_cum,
         delta_5m, delta_15m, delta_1h, close, price_chg,
         signal, finviz_cat, "finviz"),
    )
    return True


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def _delta(df: pd.DataFrame, n: int) -> float | None:
    if len(df) <= n:
        return None
    return float(df.iloc[-1]["hype_cum"] - df.iloc[-(n + 1)]["hype_cum"])


def _signal(rel_vol: float, delta_5m: float | None) -> str | None:
    if rel_vol >= SPIKE_THRESHOLD:
        return "spike"
    if delta_5m is not None and delta_5m >= TRENDING_DELTA:
        return "trending"
    if delta_5m is not None and delta_5m >= EARLY_MOM_DELTA:
        return "early_momentum"
    return None


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
        if s.endswith("B"):
            return float(s[:-1]) * 1_000_000_000
        if s.endswith("M"):
            return float(s[:-1]) * 1_000_000
        if s.endswith("K"):
            return float(s[:-1]) * 1_000
        return float(s)
    except Exception:
        return 0.0


def _parse_price(v) -> float:
    try:
        return float(str(v).replace("$", "").replace(",", ""))
    except Exception:
        return 0.0
