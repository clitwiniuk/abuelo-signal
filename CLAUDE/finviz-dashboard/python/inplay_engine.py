"""
=============================================================
  Inplay Engine — per-ticker quality ranking using 1-min bars

  Computes VWAP-based inplay metrics for Top Gainers tickers
  to distinguish ordered pullbacks (A+/A) from reversals (C/D).

  Key features (from inplay_feature_study.py research, 98 ticker-dates):
    score_pre        — VWAP pullback score: neg = below VWAP = ordered pullback
                       best single feature (44% precision OOS, 1.9x lift)
    rejection        — (HOD - current_close) / (HOD - LOD); 0=at HOD, 1=at LOD
    pct_above_vwap   — (close - vwap) / vwap; >0 = above VWAP
    detection_vs_close — extension from prev_close; >150% = likely D

  Best combo OOS: score_pre < -3 AND rejection < 0.3 → 50% precision, 2.2x lift

  Grade mapping: A+(4) / A(3) / B(2) / C(1) / D(0)
=============================================================
"""
import logging
import sqlite3
from datetime import datetime

import pandas as pd
import pytz

log = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")

# Score thresholds (from research study)
SCORE_PRE_THRESH   = -3      # below = ordered pullback (positive signal)
REJECTION_THRESH   = 0.35    # below = close to HOD (positive signal)
PCT_ABOVE_THRESH   = 0.0     # above = price above VWAP (positive signal)
DVSC_THRESH        = 1.5     # below = not massively overextended (positive signal)
DVSC_OVERRIDE      = 2.0     # override to D if overextended AND no pullback


# ------------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------------

def compute_inplay_scores(db_path: str, day: str | None = None) -> list[dict]:
    """Compute inplay quality scores for today's Top Gainers tickers.

    Uses market_bars (1-min OHLCV from IBKR) and snapshots tables.

    Args:
        db_path: Path to finviz_snapshots.db
        day: Date string "YYYY-MM-DD". Defaults to today ET.

    Returns:
        List of dicts sorted by inplay_score desc, then score_pre asc.
        Each dict contains: ticker, score_pre, rejection, pct_above_vwap,
        detection_vs_close, chg_pct_now, prev_close_est, current_price,
        current_vwap, hod, lod, n_bars, inplay_score, inplay_grade.
    """
    now_et = datetime.now(ET)
    if day is None:
        day = now_et.strftime("%Y-%m-%d")

    conn = sqlite3.connect(db_path)
    try:
        tickers = _get_top_gainers_tickers(conn, day)
        if not tickers:
            return []

        results = []
        for ticker in tickers:
            result = _compute_ticker(conn, ticker, day)
            results.append(result)

        # Sort: inplay_score desc, then score_pre asc (more negative = better)
        results.sort(key=lambda x: (-x["inplay_score"], x["score_pre"] if x["score_pre"] is not None else 0))
        return results
    finally:
        conn.close()


# ------------------------------------------------------------------
# PER-TICKER COMPUTATION
# ------------------------------------------------------------------

def _compute_ticker(conn, ticker: str, day: str) -> dict:
    """Compute inplay metrics for a single ticker."""
    base = {
        "ticker":             ticker,
        "score_pre":          None,
        "rejection":          None,
        "pct_above_vwap":     None,
        "detection_vs_close": None,
        "chg_pct_now":        None,
        "prev_close_est":     None,
        "current_price":      None,
        "current_vwap":       None,
        "hod":                None,
        "lod":                None,
        "n_bars":             0,
        "inplay_score":       0,
        "inplay_grade":       "?",
    }

    # --- 1-min bars for this ticker today (09:30 onward) ---
    bars_df = _get_market_bars(conn, ticker, day)
    base["n_bars"] = len(bars_df)

    # --- Finviz snapshot data ---
    snap_chg, snap_price = _get_latest_snapshot(conn, ticker, day)
    base["chg_pct_now"] = snap_chg

    # Prev close + detection price from earliest valid finviz scan before 10:00
    prev_close, detection_price = _estimate_prev_close(conn, ticker, day)
    base["prev_close_est"] = prev_close

    if bars_df.empty:
        # No bars yet — return partial with grade "?"
        if detection_price and prev_close and prev_close > 0:
            base["current_price"] = detection_price
            base["detection_vs_close"] = round((detection_price - prev_close) / prev_close, 4)
        return base

    # Ensure VWAP column: use stored if available, else compute from bars
    bars_df = _ensure_vwap(bars_df)

    # All features use the detection window (09:30-10:00) for consistency with research study.
    # In real-time at 10:00 this is the same as bars_df; for historical runs it avoids look-ahead.
    score_window = bars_df[bars_df["bar_time"].str[11:16] <= "10:00"]
    if len(score_window) == 0:
        score_window = bars_df  # fallback: market is still early, use all available bars

    current_bar   = score_window.iloc[-1]
    current_close = float(current_bar["close"])
    current_vwap  = float(current_bar["cum_vwap"])
    hod = float(score_window["high"].max())
    lod = float(score_window["low"].min())

    base["current_price"] = current_close
    base["current_vwap"]  = round(current_vwap, 4)
    base["hod"]           = round(hod, 4)
    base["lod"]           = round(lod, 4)

    # --- score_pre: count bars below/above VWAP in detection window ---
    # +1 if close < vwap (pullback = ordered), -1 if above
    below_mask = score_window["close"] < score_window["cum_vwap"]
    score_pre = int(below_mask.sum()) - int((~below_mask).sum())
    base["score_pre"] = score_pre

    # --- rejection: (HOD - close@10:00) / (HOD - LOD) in detection window ---
    hod_lod_range = hod - lod
    if hod_lod_range > 0:
        rejection = (hod - current_close) / hod_lod_range
    else:
        rejection = 0.0
    base["rejection"] = round(rejection, 4)

    # --- pct_above_vwap: (close@10:00 - vwap@10:00) / vwap ---
    if current_vwap > 0:
        pct_above_vwap = (current_close - current_vwap) / current_vwap
    else:
        pct_above_vwap = 0.0
    base["pct_above_vwap"] = round(pct_above_vwap, 4)

    # --- detection_vs_close: extension from prev_close at FIRST detection (before 10:00) ---
    # Use detection_price (first finviz scan price), NOT current bar close —
    # this measures how extended the ticker was when first spotted, not EOD
    if detection_price and prev_close and prev_close > 0:
        detection_vs_close = (detection_price - prev_close) / prev_close
        base["detection_vs_close"] = round(detection_vs_close, 4)
    else:
        detection_vs_close = None

    # --- inplay_score (0-4) ---
    score = 0
    if score_pre < SCORE_PRE_THRESH:
        score += 1
    if rejection < REJECTION_THRESH:
        score += 1
    if pct_above_vwap > PCT_ABOVE_THRESH:
        score += 1
    if detection_vs_close is not None and detection_vs_close < DVSC_THRESH:
        score += 1

    # Override to D: massively overextended AND no pullback behavior
    if (detection_vs_close is not None and
            detection_vs_close > DVSC_OVERRIDE and
            score_pre >= 0):
        score = 0

    base["inplay_score"] = score
    base["inplay_grade"] = _grade(score)

    return base


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def _grade(score: int) -> str:
    return {4: "A+", 3: "A", 2: "B", 1: "C", 0: "D"}.get(score, "D")


def _get_top_gainers_tickers(conn, day: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM snapshots "
        "WHERE substr(timestamp,1,10)=? AND category='Top Gainers' ORDER BY ticker",
        (day,)
    ).fetchall()
    return [r[0] for r in rows]


def _get_market_bars(conn, ticker: str, day: str) -> pd.DataFrame:
    """Load 1-min bars for ticker on day, from 09:30 onward.
    bar_time format: '2026-05-13T09:30:00' — use substr filter."""
    df = pd.read_sql(
        "SELECT bar_time, open, high, low, close, volume, vwap "
        "FROM market_bars "
        "WHERE ticker=? AND bar_time LIKE ? "
        "  AND substr(bar_time,12,5) >= '09:30' "
        "ORDER BY bar_time",
        conn,
        params=(ticker, f"{day}%"),
    )
    return df


def _ensure_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Add cum_vwap column: use stored vwap if present and non-null, else compute."""
    df = df.copy()

    # If vwap column exists and is mostly populated, use it
    if "vwap" in df.columns and df["vwap"].notna().sum() > len(df) * 0.5:
        df["cum_vwap"] = df["vwap"]
        # Fill any remaining nulls with rolling computation
        needs_fill = df["cum_vwap"].isna()
        if needs_fill.any():
            cum_tpv = ((df["high"] + df["low"] + df["close"]) / 3 * df["volume"].fillna(0)).cumsum()
            cum_vol = df["volume"].fillna(0).cumsum()
            fallback = (cum_tpv / cum_vol.replace(0, float("nan"))).fillna(method="ffill")
            df.loc[needs_fill, "cum_vwap"] = fallback[needs_fill]
    else:
        # Compute cumulative VWAP from scratch
        typical = (df["high"] + df["low"] + df["close"]) / 3
        cum_tpv = (typical * df["volume"].fillna(0)).cumsum()
        cum_vol = df["volume"].fillna(0).cumsum()
        df["cum_vwap"] = (cum_tpv / cum_vol.replace(0, float("nan"))).fillna(method="ffill")

    return df


def _get_latest_snapshot(conn, ticker: str, day: str) -> tuple[float | None, float | None]:
    """Return (chg_pct_float, price_float) from latest finviz snapshot today."""
    row = conn.execute(
        "SELECT change_pct, price FROM snapshots "
        "WHERE ticker=? AND timestamp LIKE ? ORDER BY id DESC LIMIT 1",
        (ticker, f"{day}%")
    ).fetchone()
    if not row:
        return None, None
    chg = _parse_chg(row[0])
    price = _parse_price(row[1])
    return chg, price


def _estimate_prev_close(conn, ticker: str, day: str) -> tuple[float | None, float | None]:
    """Estimate (prev_close, detection_price) from earliest valid finviz scan before 10:00.

    Formula: prev_close = detection_price / (1 + chg_pct/100)
    Uses first scan with chg > 0 before 10:00 ET as the anchor.
    Returns (prev_close, detection_price) or (None, None).
    """
    rows = conn.execute(
        "SELECT price, change_pct FROM snapshots "
        "WHERE ticker=? AND substr(timestamp,1,10)=? "
        "  AND substr(timestamp,12,5) <= '10:00' "
        "ORDER BY id ASC LIMIT 10",
        (ticker, day)
    ).fetchall()

    if not rows:
        rows = conn.execute(
            "SELECT price, change_pct FROM snapshots "
            "WHERE ticker=? AND substr(timestamp,1,10)=? "
            "ORDER BY id ASC LIMIT 10",
            (ticker, day)
        ).fetchall()

    for row in rows:
        price = _parse_price(row[0])
        chg = _parse_chg(row[1])
        if price and chg and chg > 0:
            prev_close = round(price / (1 + chg / 100), 4)
            return prev_close, price  # (prev_close, detection_price)

    return None, None


def _parse_price(v) -> float | None:
    try:
        val = float(str(v).replace("$", "").replace(",", ""))
        return val if val > 0 else None
    except Exception:
        return None


def _parse_chg(v) -> float | None:
    try:
        return float(str(v).replace("%", "").replace("+", "").strip())
    except Exception:
        return None
