"""
data_loader.py — Carga y parsea las tres fuentes de datos del estudio reactive_signal.

Fuentes:
  - snapshots      : Finviz Top Gainers capturados cada 5-15 min (prod DB)
  - intraday_bars  : OHLCV 1-min de burst tickers (burst_intraday_cache.db)
  - hype_metrics   : Señales de momentum computadas por el dashboard (prod DB, Apr 14+)
"""

import sqlite3
import pandas as pd
from pathlib import Path

# --- Paths por defecto ---
DB_PROD_DEFAULT  = Path.home() / 'Library/Application Support/finviz-dashboard/finviz_snapshots.db'
DB_BURST_DEFAULT = Path(__file__).parents[2] / 'burst_intraday_cache.db'

TZ = 'America/New_York'


def load_snapshots(
    db_path: Path = DB_PROD_DEFAULT,
    category: str = 'Top Gainers',
    min_change_pct: float = 0.0,
) -> pd.DataFrame:
    """
    Carga snapshots de Finviz para una categoría dada.

    Returns
    -------
    DataFrame con columnas:
        timestamp (str), ticker, price (float), change_pct (float),
        ts (Timestamp tz=America/New_York), date (str YYYY-MM-DD),
        time_et (str HH:MM), hour, minute, minutes_since_open
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql(
            """
            SELECT
                timestamp,
                ticker,
                CAST(REPLACE(price, ',', '') AS REAL)                          AS price,
                CAST(REPLACE(REPLACE(change_pct, '%', ''), ',', '') AS REAL)   AS change_pct,
                volume
            FROM snapshots
            WHERE category = ?
              AND change_pct NOT LIKE '0%'
              AND change_pct != ''
              AND change_pct IS NOT NULL
            """,
            conn,
            params=(category,),
        )

    df['ts']     = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert(TZ)
    df['date']   = df['ts'].dt.strftime('%Y-%m-%d')
    df['time_et'] = df['ts'].dt.strftime('%H:%M')
    df['hour']   = df['ts'].dt.hour
    df['minute'] = df['ts'].dt.minute
    df['minutes_since_open'] = (df['hour'] - 9) * 60 + df['minute'] - 30

    if min_change_pct > 0:
        df = df[df['change_pct'] >= min_change_pct].copy()

    return df.reset_index(drop=True)


def load_intraday_bars(db_path: Path = DB_BURST_DEFAULT) -> pd.DataFrame:
    """
    Carga barras 1-min del burst_intraday_cache.

    Returns
    -------
    DataFrame con columnas:
        ticker, date (str), dt (str HH:MM), open, high, low, close, volume,
        bar_ts (Timestamp tz=America/New_York)
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql(
            "SELECT symbol AS ticker, date, dt, open, high, low, close, volume FROM bars",
            conn,
        )

    df['bar_ts'] = (
        pd.to_datetime(df['date'] + 'T' + df['dt'])
        .dt.tz_localize(TZ, ambiguous='NaT', nonexistent='NaT')
    )
    df['date'] = df['date'].astype(str)

    return df.reset_index(drop=True)


def load_hype_metrics(
    db_path: Path = DB_PROD_DEFAULT,
    signals: tuple = ('confirmed', 'accelerating', 'spike', 'trending', 'topping', 'new'),
) -> pd.DataFrame:
    """
    Carga hype_metrics filtrado por señales relevantes.

    Returns
    -------
    DataFrame con columnas:
        timestamp (str), ticker, rel_volume, delta_5m, delta_15m,
        hype_cum, close_price, signal,
        ts (Timestamp tz=America/New_York), date (str)
    """
    placeholders = ','.join('?' * len(signals))
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql(
            f"""
            SELECT timestamp, ticker, rel_volume, delta_5m, delta_15m,
                   hype_cum, close_price, signal
            FROM hype_metrics
            WHERE signal IN ({placeholders})
            """,
            conn,
            params=list(signals),
        )

    # Timestamps have mixed tz formats (naive ET or with UTC offset) — parse to UTC then convert
    df['ts']   = pd.to_datetime(df['timestamp'], format='mixed', utc=True).dt.tz_convert(TZ)
    df['date'] = df['ts'].dt.strftime('%Y-%m-%d')
    df['minutes_since_open'] = (df['ts'].dt.hour - 9) * 60 + df['ts'].dt.minute - 30

    return df.reset_index(drop=True)


def load_market_bars(db_path: Path = DB_PROD_DEFAULT) -> pd.DataFrame:
    """
    Carga barras 1-min de market_bars (prod DB — tickers rastreados por el dashboard).

    Returns
    -------
    DataFrame con columnas:
        ticker, date (str), bar_time (str), open, high, low, close, volume, vwap,
        bar_ts (Timestamp tz=America/New_York)
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql(
            "SELECT ticker, bar_time, open, high, low, close, volume, vwap FROM market_bars",
            conn,
        )

    df['bar_ts'] = (
        pd.to_datetime(df['bar_time'])
        .dt.tz_localize(TZ, ambiguous='NaT', nonexistent='NaT')
    )
    df['date'] = df['bar_ts'].dt.strftime('%Y-%m-%d')

    return df.reset_index(drop=True)
