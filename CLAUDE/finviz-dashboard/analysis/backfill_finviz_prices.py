#!/usr/bin/env python3
"""
backfill_finviz_prices.py — Download daily bars from IBKR for all tickers
that appeared in Finviz snapshots but don't have price data yet.

Stores results in analysis/burst_daily_cache.db (ticker, bar_date, OHLCV).
Skips tickers already present. Safe to re-run — idempotent.

Usage:
    python analysis/backfill_finviz_prices.py
    python analysis/backfill_finviz_prices.py --min-appearances 2  # more tickers
    python analysis/backfill_finviz_prices.py --tickers AAPL TSLA  # specific list
    python analysis/backfill_finviz_prices.py --force               # re-download all
"""

import asyncio
import sqlite3
import argparse
import logging
import sys
import os
from datetime import datetime, timedelta

from ib_insync import IB, Stock, util

util.logToConsole(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

IBKR_HOST = '127.0.0.1'
IBKR_PORT = 7497
IBKR_CLIENT_ID = 5091  # distinto de los demás para no colisionar

FINVIZ_DB   = os.path.expanduser('~/Library/Application Support/finviz-dashboard/finviz_snapshots.db')
PRICE_DB    = os.path.join(os.path.dirname(__file__), 'burst_daily_cache.db')

PACING_DELAY = 0.4   # segundos entre requests (límite IBKR: ~50 req/10s)
DURATION     = '90 D'  # cubre todo el período Finviz + contexto


def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_bars (
            ticker     TEXT NOT NULL,
            bar_date   TEXT NOT NULL,
            open       REAL,
            high       REAL,
            low        REAL,
            close      REAL,
            volume     INTEGER,
            PRIMARY KEY (ticker, bar_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS download_log (
            ticker        TEXT PRIMARY KEY,
            downloaded_at TEXT,
            n_bars        INTEGER,
            status        TEXT,
            error_msg     TEXT
        )
    """)
    conn.commit()


def get_finviz_tickers(min_appearances: int) -> list[str]:
    """Return tickers from Finviz DB that meet minimum appearance threshold."""
    conn = sqlite3.connect(FINVIZ_DB)
    rows = conn.execute("""
        SELECT ticker, COUNT(*) as n, MAX(CAST(price AS REAL)) as max_price
        FROM snapshots
        WHERE price IS NOT NULL AND price != '0' AND price != ''
        GROUP BY ticker
        HAVING n >= ?
        ORDER BY n DESC
    """, (min_appearances,)).fetchall()
    conn.close()
    # Filter price range: 0.5–100$ (avoid ETFs/indices with no data)
    tickers = [r[0] for r in rows if r[2] and 0.5 <= float(r[2]) <= 100]
    logger.info(f"Finviz universe: {len(tickers)} tickers with >={min_appearances} appearances, price $0.5–$100")
    return tickers


def get_already_downloaded(force: bool) -> set[str]:
    if force:
        return set()
    conn = sqlite3.connect(PRICE_DB)
    try:
        rows = conn.execute(
            "SELECT ticker FROM download_log WHERE status = 'ok'"
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()
    finally:
        conn.close()


async def download_ticker(ib: IB, ticker: str, conn: sqlite3.Connection) -> tuple[str, int]:
    """Download daily bars for one ticker. Returns (status, n_bars)."""
    contract = Stock(ticker, 'SMART', 'USD')

    try:
        await asyncio.sleep(PACING_DELAY)
        bars = await ib.reqHistoricalDataAsync(
            contract,
            endDateTime='',           # now
            durationStr=DURATION,
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1,
        )
    except Exception as e:
        return 'error', 0, str(e)

    if not bars:
        return 'no_data', 0, None

    rows = []
    for b in bars:
        ds = str(b.date)[:10].replace(' ', '-')
        rows.append((ticker, ds, float(b.open), float(b.high),
                     float(b.low), float(b.close), int(b.volume)))

    conn.executemany(
        "INSERT OR REPLACE INTO daily_bars (ticker, bar_date, open, high, low, close, volume) "
        "VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return 'ok', len(rows), None


async def main():
    parser = argparse.ArgumentParser(description='Backfill Finviz daily prices from IBKR')
    parser.add_argument('--min-appearances', type=int, default=1,
                        help='Minimum Finviz appearances to include ticker (default: 1)')
    parser.add_argument('--tickers', nargs='+', default=None,
                        help='Explicit ticker list (overrides --min-appearances)')
    parser.add_argument('--force', action='store_true',
                        help='Re-download even if already in DB')
    parser.add_argument('--port', type=int, default=IBKR_PORT,
                        help=f'TWS port (default: {IBKR_PORT})')
    args = parser.parse_args()

    # --- Build ticker list ---
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = get_finviz_tickers(args.min_appearances)

    already_done = get_already_downloaded(args.force)
    tickers_to_download = [t for t in tickers if t not in already_done]
    logger.info(f"Need to download: {len(tickers_to_download)} tickers "
                f"(already done: {len(already_done)}, skipped)")

    if not tickers_to_download:
        logger.info("Nothing to download. Use --force to re-download.")
        return

    # --- Connect to IBKR ---
    ib = IB()
    try:
        await ib.connectAsync(IBKR_HOST, args.port, clientId=IBKR_CLIENT_ID, timeout=15)
        logger.info(f"Connected to TWS on port {args.port}")
    except Exception as e:
        logger.error(f"Cannot connect to TWS: {e}")
        sys.exit(1)

    # --- Init DB ---
    conn = sqlite3.connect(PRICE_DB)
    init_db(conn)

    # --- Download loop ---
    ok_count = 0
    fail_count = 0
    total = len(tickers_to_download)

    for i, ticker in enumerate(tickers_to_download, 1):
        status, n_bars, err = await download_ticker(ib, ticker, conn)

        conn.execute("""
            INSERT OR REPLACE INTO download_log (ticker, downloaded_at, n_bars, status, error_msg)
            VALUES (?, ?, ?, ?, ?)
        """, (ticker, datetime.now().isoformat(), n_bars, status, err))
        conn.commit()

        if status == 'ok':
            ok_count += 1
            logger.info(f"[{i}/{total}] {ticker}: {n_bars} bars")
        elif status == 'no_data':
            fail_count += 1
            logger.warning(f"[{i}/{total}] {ticker}: no data returned (delisted/invalid?)")
        else:
            fail_count += 1
            logger.warning(f"[{i}/{total}] {ticker}: error — {err}")

    conn.close()
    ib.disconnect()

    logger.info(f"\nDone: {ok_count} OK, {fail_count} failed")
    logger.info(f"DB: {PRICE_DB}")


if __name__ == '__main__':
    asyncio.run(main())
