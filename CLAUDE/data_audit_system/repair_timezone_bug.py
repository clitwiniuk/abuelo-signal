#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repair_timezone_bug.py — repara en market_bars_1min_ge los ticker-días
confirmados como contaminados por el bug de timezone (ver
audit_timezone_blast_radius.py + inspect_ticker_day.py).

Estrategia (por ticker-día, dentro de una transacción):
  1. Backup de las filas actuales a CSV (rollback manual si algo sale mal).
  2. DELETE de esas filas en market_bars_1min_ge.
  3. Re-copia desde market_intraday_bars usando el filtro RTH corregido
     (timezone real vía zoneinfo — mismo código que backfill_ge_rth_from_intraday.py).

Por defecto corre en --dry-run (no escribe nada). Requiere --execute explícito
para tocar la base de datos.

Uso (desde trading_system_v3/):
    python3 ../data_audit_system/repair_timezone_bug.py --verdicts ../data_audit_system/reports/verdicts_alta66_2026-07-08.csv --dry-run
    python3 ../data_audit_system/repair_timezone_bug.py --verdicts ../data_audit_system/reports/verdicts_alta66_2026-07-08.csv --execute
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

ET_ZONE = ZoneInfo("America/New_York")
RTH_START = "09:30:00"
RTH_END = "16:00:00"
TARGET_VERDICTS = ("CONTAMINADO", "SOSPECHOSO")


def _parse_bar_timestamp(raw):
    if raw.endswith("+00:00") or raw.endswith("Z") or "T" in raw:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    naive = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=ET_ZONE).astimezone(timezone.utc)


def recompute_rth_bars(trading_conn, symbol, date):
    """Misma lógica que copy_bars() ya corregido en backfill_ge_rth_from_intraday.py."""
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


def load_targets(verdicts_csv):
    df = pd.read_csv(verdicts_csv)
    targets = df[df["veredicto"].isin(TARGET_VERDICTS)]
    return list(targets[["ticker", "date", "veredicto"]].itertuples(index=False, name=None))


def backup_current_rows(engine_conn, targets, backup_path):
    frames = []
    for ticker, date, _ in targets:
        df = pd.read_sql(
            "SELECT * FROM market_bars_1min_ge WHERE ticker=? AND date=?",
            engine_conn, params=(ticker, date))
        frames.append(df)
    backup = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    backup.to_csv(backup_path, index=False)
    return backup


def run(engine_db, trading_db, verdicts_csv, dry_run, backup_dir):
    targets = load_targets(verdicts_csv)
    print(f"Ticker-días objetivo (CONTAMINADO + SOSPECHOSO): {len(targets)}")
    for t, d, v in targets:
        print(f"  {t:<8} {d}  [{v}]")

    engine_conn = sqlite3.connect(engine_db)
    trading_conn = sqlite3.connect(trading_db)

    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(
        backup_dir, f"pre_repair_backup_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.csv")
    backup = backup_current_rows(engine_conn, targets, backup_path)
    print(f"\nBackup de {len(backup)} filas actuales -> {backup_path}")

    total_before = 0
    total_after = 0
    summary = []
    for ticker, date, verdict in targets:
        n_before = engine_conn.execute(
            "SELECT COUNT(*) FROM market_bars_1min_ge WHERE ticker=? AND date=?",
            (ticker, date)).fetchone()[0]
        new_rows = recompute_rth_bars(trading_conn, ticker, date)
        total_before += n_before
        total_after += len(new_rows)
        summary.append({"ticker": ticker, "date": date, "veredicto": verdict,
                        "filas_antes": n_before, "filas_recalculadas": len(new_rows)})

        if dry_run:
            continue

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
    summary_path = os.path.join(
        backup_dir, f"repair_summary_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.csv")
    df_summary.to_csv(summary_path, index=False)

    print(f"\n{'DRY-RUN — nada escrito' if dry_run else 'EJECUTADO — DB modificada'}")
    print(f"Filas totales antes      : {total_before}")
    print(f"Filas totales recalculadas: {total_after}")
    print(f"Resumen -> {summary_path}")
    if dry_run:
        print("\nRe-ejecuta con --execute para aplicar los cambios.")
    return df_summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engine-db", default="trader_engine/db/trader_engine.db")
    ap.add_argument("--trading-db", default="trading_data.db")
    ap.add_argument("--verdicts", required=True,
                    help="CSV de inspect_ticker_day batch (columnas ticker,date,veredicto)")
    ap.add_argument("--backup-dir", default="../data_audit_system/reports/repair_backups")
    ap.add_argument("--execute", action="store_true",
                    help="Aplica los cambios. Sin este flag, solo simula (dry-run).")
    args = ap.parse_args()

    if not args.execute:
        run(args.engine_db, args.trading_db, args.verdicts, dry_run=True,
            backup_dir=args.backup_dir)
        return

    run(args.engine_db, args.trading_db, args.verdicts, dry_run=False,
        backup_dir=args.backup_dir)


if __name__ == "__main__":
    main()
