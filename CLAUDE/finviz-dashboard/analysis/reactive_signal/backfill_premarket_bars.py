#!/usr/bin/env python3
"""
backfill_premarket_bars.py — Descarga barras 1-min PRE-MARKET (4:00-9:30 ET)
para los ticker-days de bursts Finviz >=15%.

Guarda en burst_premarket_cache.db, tabla 'bars' con misma estructura
que burst_intraday_cache.db pero solo barras 04:00-09:29 ET.

Requiere TWS abierto con API habilitada en puerto 7497.

Uso:
    python backfill_premarket_bars.py              # todos los faltantes
    python backfill_premarket_bars.py --dry-run
    python backfill_premarket_bars.py --date 2026-04-10
    python backfill_premarket_bars.py --ticker BZAI EFOI
"""

import asyncio
import sqlite3
import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from ib_insync import IB, Stock, util
except ImportError:
    print("ERROR: ib_insync no está instalado. Instalar con: pip install ib_insync")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

IBKR_HOST      = '127.0.0.1'
IBKR_PORT      = 7497
IBKR_CLIENT_ID = 5097          # ID dedicado para pre-market (no colisiona)
PACING_DELAY   = 12.0
FINVIZ_DB      = Path.home() / 'Library/Application Support/finviz-dashboard/finviz_snapshots.db'
DB_PREMARKET   = Path(__file__).parent.parent / 'burst_premarket_cache.db'

# Rango pre-market: barras entre 04:00 y 09:29 ET
PREMARKET_START_MSO = -330   # 4:00 ET = -330 min desde 9:30
PREMARKET_END_MSO   = -1     # hasta 09:29 ET


def _ensure_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bars (
            symbol TEXT,
            date   TEXT,
            dt     TEXT,
            open   REAL,
            high   REAL,
            low    REAL,
            close  REAL,
            volume INTEGER,
            PRIMARY KEY (symbol, date, dt)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fetched (
            symbol     TEXT,
            date       TEXT,
            fetched_at TEXT DEFAULT (datetime('now')),
            n_bars     INTEGER DEFAULT 0,
            PRIMARY KEY (symbol, date)
        )
    """)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(fetched)").fetchall()}
    if 'fetched_at' not in cols:
        conn.execute("ALTER TABLE fetched ADD COLUMN fetched_at TEXT DEFAULT (datetime('now'))")
    if 'n_bars' not in cols:
        conn.execute("ALTER TABLE fetched ADD COLUMN n_bars INTEGER DEFAULT 0")
    conn.commit()


def _get_already_fetched(conn: sqlite3.Connection) -> set:
    cur = conn.execute(
        "SELECT symbol, date FROM fetched WHERE n_bars > 0"
        " AND julianday('now') - julianday(fetched_at) < 60"
    )
    return {(r[0], r[1]) for r in cur.fetchall()}


def _mark_fetched(conn: sqlite3.Connection, symbol: str, date: str, n_bars: int = 0):
    conn.execute(
        """INSERT INTO fetched (symbol, date, fetched_at, n_bars)
           VALUES (?, ?, datetime('now'), ?)
           ON CONFLICT(symbol, date) DO UPDATE SET
               fetched_at = datetime('now'), n_bars = excluded.n_bars""",
        (symbol, date, n_bars)
    )
    conn.commit()


def _save_bars(conn: sqlite3.Connection, symbol: str, date: str, bars) -> int:
    """Guarda solo barras pre-market (04:00-09:29 ET) del día solicitado."""
    rows = []
    for b in bars:
        bar_dt = b.date
        if hasattr(bar_dt, 'strftime'):
            date_str = bar_dt.strftime('%Y-%m-%d')
            time_str = bar_dt.strftime('%H:%M')
        else:
            parts    = str(bar_dt).split(' ')
            date_str = parts[0]
            time_str = parts[1][:5] if len(parts) > 1 else '00:00'

        if date_str != date:
            continue

        # Solo barras 04:00-09:29
        h, m = map(int, time_str.split(':'))
        if h < 4 or (h == 9 and m >= 30) or h >= 10:
            continue

        rows.append((symbol, date_str, time_str, b.open, b.high, b.low, b.close, b.volume))

    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO bars (symbol, date, dt, open, high, low, close, volume)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows
        )
        conn.commit()

    return len(rows)


def _get_burst_ticker_days() -> list[tuple[str, str]]:
    """Retorna (ticker, date) de bursts Finviz >=15%."""
    import sqlite3 as _sql
    with _sql.connect(FINVIZ_DB) as conn:
        rows = conn.execute("""
            SELECT DISTINCT ticker, SUBSTR(timestamp,1,10) AS date
            FROM snapshots
            WHERE category = 'Top Gainers'
              AND CAST(REPLACE(REPLACE(change_pct,'%',''),',','') AS REAL) >= 15
            ORDER BY date, ticker
        """).fetchall()
    return [(r[0], r[1]) for r in rows]


async def _download(ticker_days: list[tuple[str, str]], dry_run: bool):
    if dry_run:
        print(f"\n[DRY RUN] Se descargarían {len(ticker_days)} ticker-days pre-market:")
        for ticker, date in ticker_days[:30]:
            print(f"  {ticker}  {date}")
        if len(ticker_days) > 30:
            print(f"  ... y {len(ticker_days) - 30} más")
        return

    ib = IB()
    try:
        await ib.connectAsync(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
        logger.info(f"Conectado a IBKR. Descargando {len(ticker_days)} ticker-days pre-market...")
    except Exception as e:
        logger.error(f"No se pudo conectar a TWS: {e}")
        return

    conn = sqlite3.connect(DB_PREMARKET)
    _ensure_table(conn)
    already = _get_already_fetched(conn)

    ok = skipped = errors = 0

    for i, (ticker, date) in enumerate(ticker_days):
        if (ticker, date) in already:
            skipped += 1
            continue

        # endDateTime = inicio del RTH del día (09:30 ET) para que incluya pre-market
        end_dt = f"{date.replace('-', '')} 09:30:00 US/Eastern"

        try:
            contract = Stock(ticker, 'SMART', 'USD')
            bars = await ib.reqHistoricalDataAsync(
                contract,
                endDateTime=end_dt,
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=False,          # ← pre-market incluido
                formatDate=1,
            )

            if bars:
                n = _save_bars(conn, ticker, date, bars)
                _mark_fetched(conn, ticker, date, n_bars=n)
                ok += 1
                logger.info(f"[{i+1}/{len(ticker_days)}] {ticker} {date}: {n} barras pre-market guardadas")
            else:
                _mark_fetched(conn, ticker, date, n_bars=0)
                logger.warning(f"[{i+1}/{len(ticker_days)}] {ticker} {date}: sin datos pre-market")
                skipped += 1

        except Exception as e:
            logger.error(f"[{i+1}/{len(ticker_days)}] {ticker} {date}: error — {e}")
            errors += 1

        if i < len(ticker_days) - 1:
            time.sleep(PACING_DELAY)

    conn.close()
    ib.disconnect()

    logger.info(f"\n=== Pre-market backfill completado ===")
    logger.info(f"OK: {ok} | Skipped: {skipped} | Errores: {errors}")
    logger.info(f"DB: {DB_PREMARKET}")


def main():
    parser = argparse.ArgumentParser(description='Backfill barras 1-min pre-market para bursts Finviz')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--date',   type=str, help='Solo una fecha (YYYY-MM-DD)')
    parser.add_argument('--ticker', nargs='+', help='Tickers específicos')
    args = parser.parse_args()

    ticker_days = _get_burst_ticker_days()

    with sqlite3.connect(DB_PREMARKET) as conn:
        _ensure_table(conn)
        already = _get_already_fetched(conn)

    ticker_days = [(t, d) for t, d in ticker_days if (t, d) not in already]

    if args.date:
        ticker_days = [(t, d) for t, d in ticker_days if d == args.date]
    if args.ticker:
        upper = [t.upper() for t in args.ticker]
        ticker_days = [(t, d) for t, d in ticker_days if t in upper]

    if not ticker_days:
        print("No hay ticker-days faltantes. Cache al día.")
        return

    print(f"Ticker-days a descargar: {len(ticker_days)}")
    print(f"Tiempo estimado: ~{len(ticker_days) * PACING_DELAY / 60:.0f} min")
    print(f"DB destino: {DB_PREMARKET}")

    util.patchAsyncio()
    asyncio.run(_download(ticker_days, dry_run=args.dry_run))


if __name__ == '__main__':
    main()
