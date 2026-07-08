#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repair_split_bug.py — repara el desajuste por split no reflejado en
market_intraday_bars, usando los ratios verificados en vivo contra IBKR por
detect_splits_via_ibkr.py (reports/ibkr_split_detection_*.csv).

Para cada ticker-día confirmado (split_detectado=True):
  1. Backup de las filas de market_intraday_bars afectadas.
  2. UPDATE en market_intraday_bars: precio *= ratio, volumen /= ratio
     (reverse split: menos acciones en circulación tras el split, mismo
     volumen en dólares -> volumen en acciones baja por el mismo factor
     que sube el precio; verificado con RAYA: ratio precio 11.88x,
     ratio volumen daily/intraday 0.071 ≈ 1/14, misma dirección y orden
     de magnitud).
  3. Re-copia market_bars_1min_ge para ese ticker-día desde el
     market_intraday_bars ya corregido, usando el filtro RTH corregido
     (mismo código que repair_timezone_bug.py / backfill_ge_rth_from_intraday.py).

Por defecto dry-run. Requiere --execute explícito para escribir.

Uso (desde trading_system_v3/):
    python3 ../data_audit_system/repair_split_bug.py --detection-csv ../data_audit_system/reports/ibkr_split_detection_20260708_073404.csv
    python3 ../data_audit_system/repair_split_bug.py --detection-csv ../data_audit_system/reports/ibkr_split_detection_20260708_073404.csv --execute
"""

import argparse
import os
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

ET_ZONE = ZoneInfo("America/New_York")
RTH_START = "09:30:00"
RTH_END = "16:00:00"


def _parse_bar_timestamp(raw):
    if raw.endswith("+00:00") or raw.endswith("Z") or "T" in raw:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    naive = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=ET_ZONE).astimezone(timezone.utc)


def recompute_rth_bars(trading_conn, symbol, date):
    raw_rows = trading_conn.execute("""
        SELECT bar_timestamp, open_price, high_price, low_price, close_price, volume
        FROM market_intraday_bars
        WHERE symbol = ? AND substr(bar_timestamp, 1, 10) = ? AND timeframe = '1min'
        ORDER BY bar_timestamp
    """, (symbol, date)).fetchall()
    rows = []
    for bar_ts, o, h, lo, c, v in raw_rows:
        dt_et = _parse_bar_timestamp(bar_ts).astimezone(ET_ZONE)
        hhmmss = dt_et.strftime("%H:%M:%S")
        if RTH_START <= hhmmss < RTH_END:
            rows.append((hhmmss, o, h, lo, c, v))
    rows.sort(key=lambda r: r[0])
    return rows


def load_targets(detection_csv):
    df = pd.read_csv(detection_csv)
    targets = df[df["split_detectado"] == True]  # noqa: E712
    return list(targets[["ticker", "date", "ratio"]].itertuples(index=False, name=None))


def backup_intraday_rows(trading_conn, targets, backup_path):
    frames = []
    for ticker, date, _ in targets:
        df = pd.read_sql(
            "SELECT * FROM market_intraday_bars WHERE symbol=? "
            "AND substr(bar_timestamp,1,10)=? AND timeframe='1min'",
            trading_conn, params=(ticker, date))
        frames.append(df)
    backup = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    backup.to_csv(backup_path, index=False)
    return backup


def run(engine_db, trading_db, detection_csv, dry_run, backup_dir):
    targets = load_targets(detection_csv)
    print(f"Ticker-días a corregir por split: {len(targets)}")
    for t, d, r in targets:
        print(f"  {t:<6} {d}  ratio={r}")

    engine_conn = sqlite3.connect(engine_db)
    trading_conn = sqlite3.connect(trading_db)

    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"pre_split_repair_intraday_backup_{ts}.csv")
    backup = backup_intraday_rows(trading_conn, targets, backup_path)
    print(f"\nBackup de {len(backup)} filas de market_intraday_bars -> {backup_path}")

    summary = []
    for ticker, date, ratio in targets:
        n_intraday = trading_conn.execute(
            "SELECT COUNT(*) FROM market_intraday_bars WHERE symbol=? "
            "AND substr(bar_timestamp,1,10)=? AND timeframe='1min'",
            (ticker, date)).fetchone()[0]
        n_ge_before = engine_conn.execute(
            "SELECT COUNT(*) FROM market_bars_1min_ge WHERE ticker=? AND date=?",
            (ticker, date)).fetchone()[0]

        summary.append({"ticker": ticker, "date": date, "ratio": ratio,
                        "filas_intraday_afectadas": n_intraday,
                        "filas_ge_antes": n_ge_before})

        if dry_run:
            continue

        with trading_conn:
            trading_conn.execute("""
                UPDATE market_intraday_bars
                SET open_price = open_price * ?,
                    high_price = high_price * ?,
                    low_price  = low_price  * ?,
                    close_price = close_price * ?,
                    volume = volume / ?
                WHERE symbol = ? AND substr(bar_timestamp,1,10) = ? AND timeframe = '1min'
            """, (ratio, ratio, ratio, ratio, ratio, ticker, date))

        new_rows = recompute_rth_bars(trading_conn, ticker, date)
        now_iso = datetime.now(timezone.utc).isoformat()
        with engine_conn:
            engine_conn.execute(
                "DELETE FROM market_bars_1min_ge WHERE ticker=? AND date=?", (ticker, date))
            engine_conn.executemany(
                "INSERT OR IGNORE INTO market_bars_1min_ge "
                "(ticker, date, time, open, high, low, close, volume, downloaded_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(ticker, date, r[0], r[1], r[2], r[3], r[4], r[5], now_iso)
                 for r in new_rows])

    df_summary = pd.DataFrame(summary)
    summary_path = os.path.join(backup_dir, f"split_repair_summary_{ts}.csv")
    df_summary.to_csv(summary_path, index=False)

    print(f"\n{'DRY-RUN — nada escrito' if dry_run else 'EJECUTADO — DB modificada'}")
    print(df_summary.to_string(index=False))
    print(f"Resumen -> {summary_path}")
    if dry_run:
        print("\nRe-ejecuta con --execute para aplicar los cambios.")
    return df_summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engine-db", default="trader_engine/db/trader_engine.db")
    ap.add_argument("--trading-db", default="trading_data.db")
    ap.add_argument("--detection-csv", required=True)
    ap.add_argument("--backup-dir", default="../data_audit_system/reports/repair_backups")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    run(args.engine_db, args.trading_db, args.detection_csv,
        dry_run=not args.execute, backup_dir=args.backup_dir)


if __name__ == "__main__":
    main()
