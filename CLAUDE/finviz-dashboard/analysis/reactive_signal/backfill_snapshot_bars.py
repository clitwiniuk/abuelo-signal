#!/usr/bin/env python3
"""
backfill_snapshot_bars.py — Descarga barras 1-min de IBKR para todos los tickers
que aparecen en Finviz Top Gainers snapshots pero que no tienen barras en
burst_intraday_cache.db.

Guarda en burst_intraday_cache.db (misma tabla 'bars' que usa el análisis).

Requiere TWS abierto con API habilitada en puerto 7497.

Uso:
    python backfill_snapshot_bars.py              # todos los faltantes
    python backfill_snapshot_bars.py --dry-run    # solo muestra qué descargaría
    python backfill_snapshot_bars.py --date 2026-04-10   # solo un día
    python backfill_snapshot_bars.py --ticker BZAI EFOI  # tickers específicos
"""

import asyncio
import sqlite3
import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from helpers import load_snapshots, build_signal_events

try:
    from ib_insync import IB, Stock, util
except ImportError:
    print("ERROR: ib_insync no está instalado. Instalar con: pip install ib_insync")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# --- Config ---
IBKR_HOST      = '127.0.0.1'
IBKR_PORT      = 7497
IBKR_CLIENT_ID = 5098          # ID dedicado, no colisiona con engines (5099) ni live (1)
PACING_DELAY   = 12.0          # segundos entre requests (IBKR: max ~6 req/min con pacing safe)
DB_BURST       = Path(__file__).parent.parent / 'burst_intraday_cache.db'


RETENTION_DAYS = 60   # Re-intentar tickers cuyo fetch tiene >60 días o que devolvieron 0 barras


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
            symbol      TEXT,
            date        TEXT,
            fetched_at  TEXT DEFAULT (datetime('now')),
            n_bars      INTEGER DEFAULT 0,
            PRIMARY KEY (symbol, date)
        )
    """)
    # Migrar tabla vieja (sin fetched_at / n_bars) si existe
    cols = {r[1] for r in conn.execute("PRAGMA table_info(fetched)").fetchall()}
    if 'fetched_at' not in cols:
        conn.execute("ALTER TABLE fetched ADD COLUMN fetched_at TEXT DEFAULT (datetime('now'))")
    if 'n_bars' not in cols:
        conn.execute("ALTER TABLE fetched ADD COLUMN n_bars INTEGER DEFAULT 0")
    conn.commit()


def _get_already_fetched(conn: sqlite3.Connection) -> set:
    """
    Retorna set de (symbol, date) que ya tienen barras descargadas con éxito
    (n_bars > 0) Y cuyo fetch tiene menos de RETENTION_DAYS días.
    Los que tienen n_bars=0 o son muy viejos se re-intentan.
    """
    cur = conn.execute(
        """
        SELECT symbol, date FROM fetched
        WHERE n_bars > 0
          AND julianday('now') - julianday(fetched_at) < ?
        """,
        (RETENTION_DAYS,)
    )
    return {(r[0], r[1]) for r in cur.fetchall()}


def _mark_fetched(conn: sqlite3.Connection, symbol: str, date: str, n_bars: int = 0):
    conn.execute(
        """
        INSERT INTO fetched (symbol, date, fetched_at, n_bars)
        VALUES (?, ?, datetime('now'), ?)
        ON CONFLICT(symbol, date) DO UPDATE SET
            fetched_at = datetime('now'),
            n_bars     = excluded.n_bars
        """,
        (symbol, date, n_bars)
    )
    conn.commit()


def _save_bars(conn: sqlite3.Connection, symbol: str, date: str, bars):
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

        # Solo guardar barras del día solicitado
        if date_str != date:
            continue

        rows.append((symbol, date_str, time_str, b.open, b.high, b.low, b.close, b.volume))

    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO bars (symbol, date, dt, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows
        )
        conn.commit()

    return len(rows)


def _get_missing_ticker_days() -> list[tuple[str, str]]:
    """Retorna lista de (ticker, date) que están en snapshots pero no en burst cache."""
    import pandas as pd

    snaps  = load_snapshots(min_change_pct=0.0)
    events = build_signal_events(snaps, min_change_pct=15.0)
    need   = set(zip(events['ticker'], events['date'].astype(str)))

    with sqlite3.connect(DB_BURST) as conn:
        _ensure_table(conn)
        already = _get_already_fetched(conn)

    missing = sorted(need - already)
    return missing


async def _download(ticker_days: list[tuple[str, str]], dry_run: bool):
    if dry_run:
        print(f"\n[DRY RUN] Se descargarían {len(ticker_days)} ticker-days:")
        for ticker, date in ticker_days[:30]:
            print(f"  {ticker}  {date}")
        if len(ticker_days) > 30:
            print(f"  ... y {len(ticker_days) - 30} más")
        return

    ib = IB()
    try:
        await ib.connectAsync(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
        logger.info(f"Conectado a IBKR. Descargando {len(ticker_days)} ticker-days...")
    except Exception as e:
        logger.error(f"No se pudo conectar a TWS: {e}")
        logger.error("Asegúrate de que TWS está abierto con API habilitada en puerto 7497")
        return

    conn = sqlite3.connect(DB_BURST)
    _ensure_table(conn)
    already = _get_already_fetched(conn)

    ok = 0
    skipped = 0
    errors = 0

    for i, (ticker, date) in enumerate(ticker_days):
        if (ticker, date) in already:
            skipped += 1
            continue

        # Formato IBKR para fechas históricas: YYYYMMDD HH:MM:SS US/Eastern
        end_dt = f"{date.replace('-', '')} 23:59:59 US/Eastern"

        try:
            contract = Stock(ticker, 'SMART', 'USD')
            bars = await ib.reqHistoricalDataAsync(
                contract,
                endDateTime=end_dt,
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1,
            )

            if bars:
                n = _save_bars(conn, ticker, date, bars)
                _mark_fetched(conn, ticker, date, n_bars=n)
                ok += 1
                logger.info(f"[{i+1}/{len(ticker_days)}] {ticker} {date}: {n} barras guardadas")
            else:
                _mark_fetched(conn, ticker, date, n_bars=0)
                logger.warning(f"[{i+1}/{len(ticker_days)}] {ticker} {date}: sin datos (ticker inactivo o fecha fuera de rango)")
                skipped += 1

        except Exception as e:
            logger.error(f"[{i+1}/{len(ticker_days)}] {ticker} {date}: error — {e}")
            errors += 1

        # Pacing para evitar throttle de IBKR
        if i < len(ticker_days) - 1:
            time.sleep(PACING_DELAY)

    conn.close()
    ib.disconnect()

    logger.info(f"\n=== Backfill completado ===")
    logger.info(f"OK: {ok} | Skipped: {skipped} | Errores: {errors}")
    logger.info(f"DB: {DB_BURST}")


def main():
    parser = argparse.ArgumentParser(description='Backfill barras 1-min para análisis reactivo')
    parser.add_argument('--dry-run',  action='store_true', help='Solo mostrar qué se descargaría')
    parser.add_argument('--date',     type=str, help='Filtrar solo una fecha (YYYY-MM-DD)')
    parser.add_argument('--ticker',   nargs='+', help='Tickers específicos a descargar')
    args = parser.parse_args()

    missing = _get_missing_ticker_days()

    if args.date:
        missing = [(t, d) for t, d in missing if d == args.date]
    if args.ticker:
        tickers_upper = [t.upper() for t in args.ticker]
        missing = [(t, d) for t, d in missing if t in tickers_upper]

    if not missing:
        print("No hay ticker-days faltantes. Cache al día.")
        return

    print(f"Ticker-days a descargar: {len(missing)}")
    print(f"Tiempo estimado: ~{len(missing) * PACING_DELAY / 60:.0f} min con pacing de {PACING_DELAY}s")

    util.patchAsyncio()
    asyncio.run(_download(missing, dry_run=args.dry_run))


if __name__ == '__main__':
    main()
