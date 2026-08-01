#!/usr/bin/env python3
"""
watchlist_builder.py — Genera la watchlist diaria de candidatos pre-burst.

Pipeline:
  1. IBKR scanner → NASDAQ stocks $1-$15, market cap <500M, vol mínimo
  2. yahooquery  → filtrar float <50M (cache local)
  3. Barras diarias IBKR → filtros técnicos:
       - NOT en nuevo máximo (dist_20d_high < -10%)
       - Compresión de rango (range_5d_pct < 20%)
       - Vol ratio T-1 entre 0.5x-3x (ni muerto ni ya disparado)
  4. Guarda en watchlist.db con score y motivo

Uso:
    python watchlist_builder.py              # construir watchlist hoy
    python watchlist_builder.py --dry-run    # mostrar candidatos sin guardar
    python watchlist_builder.py --show       # mostrar watchlist actual

Insight clave (burst_narrative_reconstruction.ipynb):
    Los bursts ocurren desde tickers BEATEN-DOWN, NO desde New Highs.
    lift(New_High_previo) = 0.07x — ausencia de NH es señal positiva.
"""

import asyncio
import sqlite3
import argparse
import logging
import json
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'trading_system_v3'))

try:
    from ib_insync import IB, ScannerSubscription, Stock, util
except ImportError:
    print("ERROR: ib_insync no instalado")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
IBKR_HOST      = '127.0.0.1'
IBKR_PORT      = 7497
IBKR_CLIENT_ID = 5096

# Filtros universo
PRICE_MIN      = 1.0
PRICE_MAX      = 15.0
FLOAT_MAX      = 50_000_000    # 50M shares float

# Filtros técnicos T-1 (aplicados si hay datos — no bloquean si no hay)
DIST_20D_HIGH_MAX  = -5.0    # excluir los que están en máximos
DIST_20D_HIGH_MIN  = -80.0   # excluir los completamente muertos
RANGE_5D_MAX       = 25.0    # compresión presente
VOL_RATIO_MIN      = 0.3
VOL_RATIO_MAX      = 8.0

DB_WATCHLIST  = Path(__file__).parent / 'watchlist.db'
FLOAT_CACHE   = Path(__file__).parent / 'edgar_cache' / 'float_cache.json'
# Barras diarias del universo general (separado del burst cache)
UNIVERSE_DAILY_DB = Path(__file__).parent / 'universe_daily_cache.db'


def _ensure_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            ticker          TEXT,
            date            TEXT,
            price           REAL,
            float_M         REAL,
            market_cap_M    REAL,
            exchange        TEXT,
            dist_20d_high   REAL,
            range_5d_pct    REAL,
            vol_ratio_1d    REAL,
            avg_vol_20d     REAL,
            score           INTEGER DEFAULT 0,
            flags           TEXT,
            added_at        TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sec_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT,
            date        TEXT,
            form_type   TEXT,
            title       TEXT,
            filed_at    TEXT,
            url         TEXT,
            alerted_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def _load_float_cache() -> dict:
    if FLOAT_CACHE.exists():
        return json.loads(FLOAT_CACHE.read_text())
    return {}


def _save_float_cache(cache: dict):
    FLOAT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    FLOAT_CACHE.write_text(json.dumps(cache))


def _fetch_floats_yahooquery(tickers: list, cache: dict) -> dict:
    missing = [t for t in tickers if t not in cache]
    if not missing:
        return cache
    try:
        from yahooquery import Ticker
        logger.info(f"Fetching float para {len(missing)} tickers via yahooquery...")
        batch_size = 25
        for i in range(0, len(missing), batch_size):
            batch = missing[i:i+batch_size]
            try:
                t = Ticker(batch)
                ks = t.key_stats
                for sym in batch:
                    s = ks.get(sym, {})
                    cache[sym] = int(s.get('floatShares', 0) or 0) if isinstance(s, dict) else 0
            except Exception:
                for sym in batch:
                    cache[sym] = 0
            time.sleep(0.5)
        _save_float_cache(cache)
        n_ok = sum(1 for v in cache.values() if v > 0)
        logger.info(f"Floats OK: {n_ok}/{len(cache)}")
    except ImportError:
        logger.warning("yahooquery no disponible — float filter desactivado")
        for t in missing:
            cache[t] = 0
    return cache


def _get_technical_filters_yq(tickers: list) -> dict:
    """
    Descarga barras diarias via yahooquery para calcular:
    dist_20d_high, range_5d_pct, vol_ratio_1d
    Usa universe_daily_cache.db para no repetir descargas.
    """
    import pandas as pd

    # Cargar cache existente
    cached = {}
    if UNIVERSE_DAILY_DB.exists():
        with sqlite3.connect(UNIVERSE_DAILY_DB) as conn:
            try:
                placeholders = ','.join('?' * len(tickers))
                rows = pd.read_sql(
                    f"SELECT ticker, bar_date, high, low, close, volume FROM daily_bars "
                    f"WHERE ticker IN ({placeholders}) ORDER BY ticker, bar_date",
                    conn, params=tickers
                )
                if not rows.empty:
                    cached_tickers = set(rows['ticker'].unique())
                    logger.info(f"Daily cache: {len(cached_tickers)} tickers ya cacheados")
            except Exception:
                rows = pd.DataFrame()
    else:
        rows = pd.DataFrame()

    # Tickers que faltan en cache
    cached_tickers = set(rows['ticker'].unique()) if not rows.empty else set()
    missing = [t for t in tickers if t not in cached_tickers]

    if missing:
        logger.info(f"Descargando barras diarias via yahooquery para {len(missing)} tickers...")
        try:
            from yahooquery import Ticker
            batch_size = 50
            new_rows = []
            for i in range(0, len(missing), batch_size):
                batch = missing[i:i+batch_size]
                try:
                    t = Ticker(batch)
                    hist = t.history(period='3mo', interval='1d')
                    if isinstance(hist, pd.DataFrame) and not hist.empty:
                        hist = hist.reset_index()
                        # yahooquery columnas: symbol, date, open, high, low, close, volume
                        if 'symbol' in hist.columns and 'date' in hist.columns:
                            hist = hist.rename(columns={'symbol':'ticker','date':'bar_date'})
                            hist['bar_date'] = hist['bar_date'].astype(str).str[:10]
                            new_rows.append(hist[['ticker','bar_date','high','low','close','volume']])
                except Exception as e:
                    logger.warning(f"yahooquery batch {i}: {e}")
                time.sleep(0.3)

            if new_rows:
                new_df = pd.concat(new_rows, ignore_index=True)
                # Guardar en cache
                UNIVERSE_DAILY_DB.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(UNIVERSE_DAILY_DB) as conn:
                    conn.execute("""CREATE TABLE IF NOT EXISTS daily_bars (
                        ticker TEXT, bar_date TEXT, high REAL, low REAL,
                        close REAL, volume INTEGER, PRIMARY KEY(ticker, bar_date))""")
                    new_df.to_sql('_tmp_bars', conn, if_exists='replace', index=False)
                    conn.execute("""INSERT OR IGNORE INTO daily_bars
                        SELECT ticker, bar_date, high, low, close, volume FROM _tmp_bars""")
                    conn.execute("DROP TABLE IF EXISTS _tmp_bars")
                rows = pd.concat([rows, new_df], ignore_index=True) if not rows.empty else new_df
                logger.info(f"Barras descargadas para {new_df['ticker'].nunique()} tickers")
        except ImportError:
            logger.warning("yahooquery no disponible — filtros técnicos desactivados")
            return {}

    if rows.empty:
        return {}

    rows = rows.sort_values(['ticker','bar_date']).reset_index(drop=True)
    rows['volume']      = pd.to_numeric(rows['volume'], errors='coerce').fillna(0)
    rows['avg_vol_20d'] = rows.groupby('ticker')['volume'].transform(
        lambda x: x.shift(1).rolling(20, min_periods=5).mean())
    rows['vol_ratio']   = rows['volume'] / rows['avg_vol_20d'].replace(0, float('nan'))
    rows['high_5d']     = rows.groupby('ticker')['high'].transform(
        lambda x: x.shift(1).rolling(5).max())
    rows['low_5d']      = rows.groupby('ticker')['low'].transform(
        lambda x: x.shift(1).rolling(5).min())
    rows['range_5d']    = (rows['high_5d'] - rows['low_5d']) / rows['close'] * 100
    rows['high_20d']    = rows.groupby('ticker')['high'].transform(
        lambda x: x.shift(1).rolling(20).max())
    rows['dist_20d']    = (rows['close'] - rows['high_20d']) / rows['high_20d'] * 100

    latest = rows.groupby('ticker').last()
    result = {}
    for ticker, row in latest.iterrows():
        result[ticker] = {
            'dist_20d_high': row['dist_20d'] if not pd.isna(row['dist_20d']) else None,
            'range_5d_pct':  row['range_5d'] if not pd.isna(row['range_5d']) else None,
            'vol_ratio_1d':  row['vol_ratio'] if not pd.isna(row['vol_ratio']) else None,
            'avg_vol_20d':   row['avg_vol_20d'] if not pd.isna(row['avg_vol_20d']) else None,
        }
    return result


def _score_candidate(tech: dict, float_M: float) -> tuple[int, list]:
    """
    Score 0-10 basado en calidad del setup.
    Más score = mejor candidato pre-burst.
    """
    score = 0
    flags = []

    dist = tech.get('dist_20d_high')
    rng  = tech.get('range_5d_pct')
    vr   = tech.get('vol_ratio_1d')

    # Distancia de máximos: beaten-down pero no muerto
    if dist is not None:
        if -40 <= dist <= -10:
            score += 3
            flags.append(f"beaten_down({dist:.0f}%)")
        elif -70 <= dist < -40:
            score += 1
            flags.append(f"deep_down({dist:.0f}%)")

    # Compresión: energía acumulada
    if rng is not None:
        if rng < 10:
            score += 3
            flags.append(f"tight_compression({rng:.0f}%)")
        elif rng < 15:
            score += 2
            flags.append(f"compression({rng:.0f}%)")
        elif rng < 20:
            score += 1

    # Vol ratio: algo de interés pero no ya disparado
    if vr is not None:
        if 1.5 <= vr <= 3.0:
            score += 2
            flags.append(f"vol_interest({vr:.1f}x)")
        elif 1.0 <= vr < 1.5:
            score += 1

    # Float pequeño: más fácil de mover
    if float_M > 0:
        if float_M < 10:
            score += 2
            flags.append(f"micro_float({float_M:.0f}M)")
        elif float_M < 25:
            score += 1
            flags.append(f"small_float({float_M:.0f}M)")

    return score, flags


async def _build_watchlist(dry_run: bool = False):
    ib = IB()
    try:
        await ib.connectAsync(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
        logger.info("Conectado a IBKR")
    except Exception as e:
        logger.error(f"No se pudo conectar a TWS: {e}")
        return []

    # ── Step 1: IBKR scanner ─────────────────────────────────────────────────
    # Scan codes orientados a smallcaps activos en $1-$15:
    # - TOP_PERC_GAIN: mayores % subida del día → momentum activo
    # - TOP_VOLUME_RATE: volumen inusual vs media → acumulación
    # - HOT_BY_VOLUME: volumen alto relativo → interés institucional
    # No usamos marketCapBelow porque IBKR lo ignora con algunos scan codes.
    # El filtro de float (<50M) vía yahooquery es más preciso.
    scan_configs = [
        dict(scan_code='TOP_PERC_GAIN',   location='STK.NASDAQ', above_price=PRICE_MIN, below_price=PRICE_MAX),
        dict(scan_code='TOP_VOLUME_RATE', location='STK.NASDAQ', above_price=PRICE_MIN, below_price=PRICE_MAX),
        dict(scan_code='TOP_PERC_GAIN',   location='STK.AMEX',   above_price=PRICE_MIN, below_price=PRICE_MAX),
        dict(scan_code='TOP_VOLUME_RATE', location='STK.AMEX',   above_price=PRICE_MIN, below_price=PRICE_MAX),
    ]

    raw_tickers = set()
    for cfg in scan_configs:
        try:
            sub = ScannerSubscription(
                instrument='STK',
                locationCode=cfg['location'],
                scanCode=cfg['scan_code'],
                abovePrice=cfg.get('above_price'),
                belowPrice=cfg.get('below_price'),
                stockTypeFilter='CORP',
            )
            results = await asyncio.wait_for(ib.reqScannerDataAsync(sub), timeout=30)
            tickers = [r.contractDetails.contract.symbol for r in results]
            raw_tickers.update(tickers)
            logger.info(f"  {cfg['scan_code']} {cfg['location']}: {len(tickers)} tickers")
        except Exception as e:
            logger.warning(f"  {cfg['scan_code']} {cfg['location']} falló: {e}")

    ib.disconnect()
    logger.info(f"Total IBKR scanner: {len(raw_tickers)} tickers únicos")

    if not raw_tickers:
        logger.error("Sin tickers del scanner IBKR")
        return []

    tickers_list = sorted(raw_tickers)

    # ── Step 2: Float filter (yahooquery) ────────────────────────────────────
    float_cache = _load_float_cache()
    float_cache = _fetch_floats_yahooquery(tickers_list, float_cache)

    passed_float = [t for t in tickers_list
                    if float_cache.get(t, 0) == 0 or float_cache.get(t, 1) <= FLOAT_MAX]
    logger.info(f"Pasaron filtro float <{FLOAT_MAX/1e6:.0f}M: {len(passed_float)}/{len(tickers_list)}")

    # ── Step 3: Filtros técnicos ─────────────────────────────────────────────
    tech = _get_technical_filters_yq(passed_float)

    candidates = []
    for ticker in passed_float:
        t_data = tech.get(ticker, {})
        dist   = t_data.get('dist_20d_high')
        rng    = t_data.get('range_5d_pct')
        vr     = t_data.get('vol_ratio_1d')

        # Filtros técnicos duros
        if dist is not None:
            if dist > DIST_20D_HIGH_MAX:   # en máximos o por encima → excluir
                continue
            if dist < DIST_20D_HIGH_MIN:   # completamente muerto → excluir
                continue
        if rng is not None and rng > RANGE_5D_MAX:
            continue
        if vr is not None and (vr < VOL_RATIO_MIN or vr > VOL_RATIO_MAX):
            continue

        float_M = float_cache.get(ticker, 0) / 1e6
        score, flags = _score_candidate(t_data, float_M)

        candidates.append({
            'ticker':       ticker,
            'float_M':      round(float_M, 1),
            'dist_20d_high':round(dist, 1)  if dist is not None else None,
            'range_5d_pct': round(rng, 1)   if rng  is not None else None,
            'vol_ratio_1d': round(vr, 2)    if vr   is not None else None,
            'avg_vol_20d':  round(t_data.get('avg_vol_20d', 0)),
            'score':        score,
            'flags':        ','.join(flags),
        })

    candidates.sort(key=lambda x: x['score'], reverse=True)
    logger.info(f"Candidatos finales: {len(candidates)}")

    # ── Step 4: Guardar ──────────────────────────────────────────────────────
    today = date.today().isoformat()

    if dry_run:
        print(f"\n[DRY RUN] {len(candidates)} candidatos — {today}")
        print(f"{'Ticker':<8} {'Score':>5} {'Float':>8} {'Dist20d':>8} {'Range5d':>8} {'VolRatio':>9}  Flags")
        print("─" * 75)
        for c in candidates[:40]:
            d20 = f"{c['dist_20d_high']:+.0f}%" if c['dist_20d_high'] else "N/A"
            r5  = f"{c['range_5d_pct']:.0f}%"   if c['range_5d_pct']  else "N/A"
            vr  = f"{c['vol_ratio_1d']:.1f}x"   if c['vol_ratio_1d']  else "N/A"
            fl  = f"{c['float_M']:.0f}M"         if c['float_M'] > 0  else "?"
            print(f"{c['ticker']:<8} {c['score']:>5} {fl:>8} {d20:>8} {r5:>8} {vr:>9}  {c['flags']}")
        return candidates

    with sqlite3.connect(DB_WATCHLIST) as conn:
        _ensure_db(conn)
        for c in candidates:
            conn.execute("""
                INSERT INTO watchlist (ticker, date, float_M, dist_20d_high, range_5d_pct,
                                       vol_ratio_1d, avg_vol_20d, score, flags)
                VALUES (:ticker, :date, :float_M, :dist_20d_high, :range_5d_pct,
                        :vol_ratio_1d, :avg_vol_20d, :score, :flags)
                ON CONFLICT(ticker, date) DO UPDATE SET
                    score = excluded.score,
                    flags = excluded.flags,
                    added_at = datetime('now')
            """, {**c, 'date': today})
        conn.commit()

    logger.info(f"Guardados {len(candidates)} candidatos en {DB_WATCHLIST}")
    return candidates


def _show_watchlist(days: int = 1):
    if not DB_WATCHLIST.exists():
        print("watchlist.db no existe — ejecutar primero sin --show")
        return
    with sqlite3.connect(DB_WATCHLIST) as conn:
        rows = conn.execute("""
            SELECT ticker, date, score, float_M, dist_20d_high, range_5d_pct, vol_ratio_1d, flags
            FROM watchlist
            WHERE date >= date('now', ?)
            ORDER BY date DESC, score DESC
        """, (f'-{days} days',)).fetchall()

    if not rows:
        print("Sin candidatos en los últimos días")
        return

    print(f"\n{'─'*85}")
    print(f"WATCHLIST — {len(rows)} candidatos")
    print(f"{'─'*85}")
    print(f"{'Ticker':<8} {'Fecha':<12} {'Score':>5} {'Float':>8} {'Dist20d':>8} {'Range5d':>8} {'VolR':>6}  Flags")
    print(f"{'─'*85}")
    for r in rows:
        ticker, d, score, fl, d20, r5, vr, flags = r
        d20s = f"{d20:+.0f}%" if d20 else "N/A"
        r5s  = f"{r5:.0f}%"  if r5  else "N/A"
        vrs  = f"{vr:.1f}x"  if vr  else "N/A"
        fls  = f"{fl:.0f}M"  if fl  else "?"
        print(f"{ticker:<8} {d:<12} {score:>5} {fls:>8} {d20s:>8} {r5s:>8} {vrs:>6}  {flags or ''}")


def main():
    parser = argparse.ArgumentParser(description='Watchlist diaria de candidatos pre-burst')
    parser.add_argument('--dry-run', action='store_true', help='Mostrar sin guardar')
    parser.add_argument('--show',    action='store_true', help='Mostrar watchlist actual')
    parser.add_argument('--days',    type=int, default=3,  help='Días a mostrar con --show')
    args = parser.parse_args()

    if args.show:
        _show_watchlist(args.days)
        return

    util.patchAsyncio()
    asyncio.run(_build_watchlist(dry_run=args.dry_run))


if __name__ == '__main__':
    main()
