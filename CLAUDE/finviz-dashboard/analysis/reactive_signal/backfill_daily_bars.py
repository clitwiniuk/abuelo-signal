#!/usr/bin/env python3
"""
backfill_daily_bars.py — Descarga barras diarias de IBKR para el universo
de tickers del análisis de precursores Finviz.

Para cada ticker burst descarga 120 días de barras diarias (OHLCV) y
las almacena en burst_daily_cache.db en la carpeta de análisis.

Uso:
    # Descarga completa del universo burst (Top Gainers >= 15%)
    python backfill_daily_bars.py

    # Solo un subconjunto de tickers
    python backfill_daily_bars.py --tickers ARTL IMMP PFSA

    # Universo completo Finviz (todas las categorías)
    python backfill_daily_bars.py --all-tickers

    # Ver qué tickers faltan sin descargar
    python backfill_daily_bars.py --dry-run

    # Forzar re-descarga aunque ya estén en caché
    python backfill_daily_bars.py --force

Notas de pacing IBKR:
    - Máx ~50 requests de historical data por 10 minutos
    - Script usa PACING_DELAY=12s entre requests para respetar el límite
    - 177 tickers ≈ 35 minutos de descarga completa
    - clientId=5098 (no colisiona con 5099 del backfill_replay_data.py)
"""

import argparse
import asyncio
import logging
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
ANALYSIS_DIR     = Path(__file__).parent.parent          # .../finviz-dashboard/analysis/
FINVIZ_DB        = Path.home() / 'Library/Application Support/finviz-dashboard/finviz_snapshots.db'
DAILY_CACHE_DB   = ANALYSIS_DIR / 'burst_daily_cache.db'

# ── IBKR ──────────────────────────────────────────────────────────────────────
IBKR_HOST      = '127.0.0.1'
IBKR_PORT      = 7497          # TWS paper trading port
IBKR_CLIENT_ID = 5098          # Exclusivo para este script

# IBKR pacing: 50 req/10min → 1 req cada 12s para margen de seguridad
PACING_DELAY   = 12.0          # segundos entre requests
DURATION_STR   = '120 D'       # ventana de descarga (120 días de barras diarias)
BAR_SIZE       = '1 day'


# ── DB setup ──────────────────────────────────────────────────────────────────

def ensure_tables(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_bars (
            ticker        TEXT NOT NULL,
            bar_date      TEXT NOT NULL,   -- YYYY-MM-DD
            open          REAL,
            high          REAL,
            low           REAL,
            close         REAL,
            volume        INTEGER,
            PRIMARY KEY (ticker, bar_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS download_log (
            ticker        TEXT NOT NULL,
            downloaded_at TEXT NOT NULL,
            n_bars        INTEGER,
            status        TEXT,            -- 'ok' | 'no_data' | 'error'
            error_msg     TEXT,
            PRIMARY KEY (ticker)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_bars_ticker ON daily_bars(ticker)")
    conn.commit()


def get_cached_tickers(conn: sqlite3.Connection) -> set[str]:
    """Tickers ya descargados con status 'ok'."""
    cur = conn.execute("SELECT ticker FROM download_log WHERE status = 'ok'")
    return {row[0] for row in cur.fetchall()}


# ── Ticker lists ──────────────────────────────────────────────────────────────

def get_burst_tickers() -> list[str]:
    """Tickers que aparecieron en Top Gainers >= 15%."""
    with sqlite3.connect(FINVIZ_DB) as conn:
        cur = conn.execute("""
            SELECT DISTINCT ticker
            FROM snapshots
            WHERE category = 'Top Gainers'
              AND CAST(REPLACE(REPLACE(change_pct,'%',''),',','') AS REAL) >= 15
            ORDER BY ticker
        """)
        return [row[0] for row in cur.fetchall()]


def get_all_finviz_tickers() -> list[str]:
    """Todos los tickers que han aparecido en cualquier categoría Finviz."""
    with sqlite3.connect(FINVIZ_DB) as conn:
        cur = conn.execute("SELECT DISTINCT ticker FROM snapshots ORDER BY ticker")
        return [row[0] for row in cur.fetchall()]


# ── IBKR download ─────────────────────────────────────────────────────────────

async def download_daily_bars(
    tickers: list[str],
    force: bool = False,
    dry_run: bool = False,
) -> None:
    """
    Descarga barras diarias para cada ticker y las almacena en DAILY_CACHE_DB.

    Usa endDateTime='' (vacío) para obtener siempre los datos más recientes,
    lo que equivale a pedir hasta hoy.
    """
    from ib_insync import IB, Stock, util

    util.logToConsole(logging.WARNING)  # silenciar logs verbosos de ib_insync

    with sqlite3.connect(DAILY_CACHE_DB) as conn:
        ensure_tables(conn)
        cached = get_cached_tickers(conn) if not force else set()

    pending = [t for t in tickers if t not in cached]

    logger.info(f"Universo: {len(tickers)} tickers")
    logger.info(f"Ya en caché (status=ok): {len(cached)}")
    logger.info(f"Pendientes de descarga: {len(pending)}")

    if dry_run:
        logger.info("--- DRY RUN — no se realiza ninguna descarga ---")
        logger.info(f"Pending tickers: {pending}")
        return

    if not pending:
        logger.info("Nada que descargar. Usa --force para re-descargar.")
        return

    eta_min = len(pending) * PACING_DELAY / 60
    logger.info(f"ETA aproximado: {eta_min:.0f} minutos (pacing {PACING_DELAY}s/ticker)")

    ib = IB()
    try:
        await ib.connectAsync(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
        logger.info(f"Conectado a TWS ({IBKR_HOST}:{IBKR_PORT} clientId={IBKR_CLIENT_ID})")
    except Exception as e:
        logger.error(f"No se pudo conectar a TWS: {e}")
        logger.error("Asegúrate de que TWS está abierto con API habilitada.")
        return

    ok_count  = 0
    err_count = 0

    for i, ticker in enumerate(pending, 1):
        logger.info(f"[{i}/{len(pending)}] {ticker} …")
        contract = Stock(ticker, 'SMART', 'USD')

        try:
            # Calificar contrato para obtener conId correcto
            details = await ib.qualifyContractsAsync(contract)
            if not details:
                logger.warning(f"  {ticker}: no encontrado en IBKR — saltando")
                _log_result(ticker, 0, 'no_data', 'qualify failed')
                continue
            contract = details[0]

            bars = await ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',           # hasta hoy
                durationStr=DURATION_STR,
                barSizeSetting=BAR_SIZE,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1,             # retorna fecha como string YYYYMMDD
            )

            if not bars:
                logger.warning(f"  {ticker}: sin datos devueltos")
                _log_result(ticker, 0, 'no_data', 'empty response')
                continue

            rows = []
            for b in bars:
                # formatDate=1 puede devolver 'YYYYMMDD' o 'YYYY-MM-DD'
                raw_date = str(b.date)[:10]
                bar_date = (
                    f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                    if len(raw_date) == 8 and '-' not in raw_date
                    else raw_date
                )
                rows.append((
                    ticker, bar_date,
                    float(b.open), float(b.high),
                    float(b.low), float(b.close),
                    int(b.volume),
                ))

            with sqlite3.connect(DAILY_CACHE_DB) as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO daily_bars
                        (ticker, bar_date, open, high, low, close, volume)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    rows,
                )
                conn.commit()
                _log_result(ticker, len(rows), 'ok', None, conn)

            logger.info(f"  {ticker}: {len(rows)} barras guardadas "
                        f"({rows[0][1]} → {rows[-1][1]})")
            ok_count += 1

        except Exception as e:
            logger.error(f"  {ticker}: ERROR — {e}")
            _log_result(ticker, 0, 'error', str(e))
            err_count += 1

        # Pacing — esperar antes del siguiente request
        if i < len(pending):
            await asyncio.sleep(PACING_DELAY)

    ib.disconnect()
    logger.info(f"\nDescarga completada: {ok_count} OK, {err_count} errores, "
                f"{len(pending) - ok_count - err_count} sin datos")


def _log_result(
    ticker: str,
    n_bars: int,
    status: str,
    error_msg: str | None,
    conn: sqlite3.Connection | None = None,
):
    """Escribe en download_log. Si no se pasa conn, abre una conexión nueva."""
    row = (ticker, datetime.utcnow().isoformat(), n_bars, status, error_msg)
    if conn is not None:
        conn.execute(
            "INSERT OR REPLACE INTO download_log "
            "(ticker, downloaded_at, n_bars, status, error_msg) VALUES (?,?,?,?,?)",
            row,
        )
        conn.commit()
    else:
        with sqlite3.connect(DAILY_CACHE_DB) as c:
            c.execute(
                "INSERT OR REPLACE INTO download_log "
                "(ticker, downloaded_at, n_bars, status, error_msg) VALUES (?,?,?,?,?)",
                row,
            )
            c.commit()


# ── Stats helper ──────────────────────────────────────────────────────────────

def print_stats():
    """Muestra un resumen del estado de la caché."""
    if not DAILY_CACHE_DB.exists():
        print("burst_daily_cache.db no existe aún. Ejecuta el script primero.")
        return

    with sqlite3.connect(DAILY_CACHE_DB) as conn:
        cur = conn.execute(
            "SELECT status, COUNT(*) FROM download_log GROUP BY status"
        )
        print("\n=== Estado de la caché ===")
        total = 0
        for status, count in cur.fetchall():
            print(f"  {status:12s}: {count}")
            total += count
        print(f"  {'TOTAL':12s}: {total}")

        cur = conn.execute("SELECT COUNT(*), COUNT(DISTINCT ticker) FROM daily_bars")
        n_bars, n_tickers = cur.fetchone()
        print(f"\n  daily_bars: {n_bars:,} barras, {n_tickers} tickers")

        cur = conn.execute(
            "SELECT MIN(bar_date), MAX(bar_date) FROM daily_bars"
        )
        min_d, max_d = cur.fetchone()
        print(f"  Rango: {min_d} → {max_d}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Backfill de barras diarias IBKR para el universo Finviz'
    )
    parser.add_argument(
        '--tickers', nargs='+', default=None,
        help='Lista explícita de tickers. Ej: --tickers ARTL IMMP PFSA'
    )
    parser.add_argument(
        '--all-tickers', action='store_true',
        help='Descargar TODOS los tickers del universo Finviz (784 tickers, ~2.5h)'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Re-descargar aunque ya estén en caché'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Mostrar qué se descargaría sin hacer ninguna request a IBKR'
    )
    parser.add_argument(
        '--stats', action='store_true',
        help='Mostrar estadísticas de la caché y salir'
    )
    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    # Resolver lista de tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
        logger.info(f"Modo: tickers explícitos ({len(tickers)})")
    elif args.all_tickers:
        tickers = get_all_finviz_tickers()
        logger.info(f"Modo: universo completo Finviz ({len(tickers)} tickers)")
    else:
        tickers = get_burst_tickers()
        logger.info(f"Modo: tickers burst Top Gainers >= 15% ({len(tickers)} tickers)")

    if not tickers:
        logger.error("No se encontraron tickers. Verificar finviz_snapshots.db")
        sys.exit(1)

    logger.info(f"DB destino: {DAILY_CACHE_DB}")

    asyncio.run(download_daily_bars(tickers, force=args.force, dry_run=args.dry_run))

    if not args.dry_run:
        print_stats()


if __name__ == '__main__':
    main()
