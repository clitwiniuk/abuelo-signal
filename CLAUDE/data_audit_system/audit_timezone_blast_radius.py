#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_timezone_blast_radius.py — auditoría de solo lectura del bug de timezone
en market_bars_1min_ge (ver CLAUDE.md / commit de fix en backfill_ge_rth_from_intraday.py).

El script antiguo copiaba barras de market_intraday_bars a market_bars_1min_ge
comparando el bar_timestamp UTC crudo contra el reloj ET (09:30-16:00) sin
convertir zona horaria. En temporada DST (ET = UTC-4), eso significa que
"09:30-16:00" tal cual aparece en el string UTC corresponde en realidad a
05:30-12:00 ET (premarket + primera hora de RTH), no a la sesión regular.

Este script NO modifica nada. Solo lee market_bars_1min_ge (trader_engine.db),
market_intraday_bars y market_daily_bars (trading_data.db) y genera un
informe de qué ticker-días están probablemente contaminados, usando 3
heurísticas independientes que se pueden combinar.

Uso (desde la raíz de trading_system_v3):
    python3 ../data_audit_system/audit_timezone_blast_radius.py
    python3 ../data_audit_system/audit_timezone_blast_radius.py --engine-db trader_engine/db/trader_engine.db --trading-db trading_data.db
"""

import argparse
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

ET_ZONE = ZoneInfo("America/New_York")

# Ventanas fijas en UTC pedidas por el análisis (aproximación deliberada:
# coinciden exactamente con RTH real solo en temporada DST — ver README).
BELIEVED_RTH_UTC = ("13:30:00", "20:00:00")     # lo que el script creía RTH
REAL_PREMARKET_UTC = ("08:00:00", "13:30:00")   # premarket real en market_intraday_bars
FIRST_HOUR_RTH_UTC = ("13:30:00", "14:30:00")   # primera hora de RTH real

RANGE_MISMATCH_RATIO = 0.30   # rango intradía < 30% del rango diario -> sospechoso (falta RTH)
RANGE_EXCESSIVE_RATIO = 2.00  # rango intradía > 200% del rango diario -> sospechoso (dato corrupto)
VOLUME_DEAD_THRESHOLD = 0.50  # >50% de barras con volumen 0/NULL en la 1a hora -> sospechoso

# Umbral de barras coincidentes para que H1 se considere alta confianza por sí
# sola. Con 1 sola vela, un match de OHLC puede ser coincidencia de precio en
# un ticker ilíquido (frecuente en smallcaps con velas planas); con muchas
# velas de la misma sesión coincidiendo, la coincidencia deja de ser plausible.
PREMATCH_HIGH_CONFIDENCE_BARS = 10


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
def load_ge_bars(engine_conn):
    """market_bars_1min_ge -> DataFrame con columna utc_ts calculada
    convirtiendo (date, time) — contrato de la columna: hora ET — a UTC real
    vía zoneinfo (DST-aware, no offset fijo)."""
    df = pd.read_sql(
        "SELECT ticker, date, time, open, high, low, close, volume, downloaded_at "
        "FROM market_bars_1min_ge", engine_conn)
    if df.empty:
        return df
    naive_et = pd.to_datetime(df["date"] + " " + df["time"])
    df["utc_ts"] = (naive_et.dt.tz_localize(ET_ZONE, ambiguous="NaT", nonexistent="NaT")
                    .dt.tz_convert("UTC"))
    df = df.dropna(subset=["utc_ts"])
    return df


def _parse_intraday_timestamp(raw):
    """Replica la doble convención de bar_timestamp en market_intraday_bars:
    naive 'YYYY-MM-DD HH:MM:SS' = ET legacy; con 'T'/'+00:00' = UTC explícito."""
    if raw is None:
        return pd.NaT
    if "T" in raw or raw.endswith("+00:00") or raw.endswith("Z"):
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    naive = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=ET_ZONE).astimezone(timezone.utc)


def load_intraday_bars_for_pairs(trading_conn, pairs):
    """Carga SOLO las barras de market_intraday_bars para los (symbol, date)
    presentes en market_bars_1min_ge. La tabla tiene 11M+ filas: nunca se
    carga entera, se filtra por par vía tabla temporal + JOIN."""
    trading_conn.execute("DROP TABLE IF EXISTS temp.target_pairs")
    trading_conn.execute("CREATE TEMP TABLE target_pairs (symbol TEXT, date TEXT)")
    trading_conn.executemany("INSERT INTO temp.target_pairs VALUES (?, ?)", pairs)

    df = pd.read_sql("""
        SELECT mib.symbol, mib.bar_timestamp,
               mib.open_price AS open, mib.high_price AS high,
               mib.low_price AS low, mib.close_price AS close, mib.volume
        FROM market_intraday_bars mib
        JOIN temp.target_pairs tp
          ON tp.symbol = mib.symbol
         AND tp.date   = substr(mib.bar_timestamp, 1, 10)
        WHERE mib.timeframe IN ('1min', '1m')
    """, trading_conn)
    if df.empty:
        return df
    df["utc_ts"] = df["bar_timestamp"].map(_parse_intraday_timestamp)
    df["date"] = df["utc_ts"].dt.tz_convert(ET_ZONE).dt.strftime("%Y-%m-%d")
    return df.dropna(subset=["utc_ts"])


def load_daily_bars_for_pairs(trading_conn, pairs):
    trading_conn.execute("DROP TABLE IF EXISTS temp.target_pairs_d")
    trading_conn.execute("CREATE TEMP TABLE target_pairs_d (symbol TEXT, date TEXT)")
    trading_conn.executemany("INSERT INTO temp.target_pairs_d VALUES (?, ?)", pairs)
    df = pd.read_sql("""
        SELECT mdb.symbol, mdb.trading_date AS date, mdb.high, mdb.low
        FROM market_daily_bars mdb
        JOIN temp.target_pairs_d tp
          ON tp.symbol = mdb.symbol AND tp.date = mdb.trading_date
    """, trading_conn)
    return df


# ---------------------------------------------------------------------------
# Heurística 1: coincidencia exacta con premarket
# ---------------------------------------------------------------------------
def heuristic_1_exact_prematch(ge_df, intraday_df):
    """Por ticker-día: barras de ge_df en la ventana 'RTH creída' cuyo OHLC
    coincide EXACTO con una barra de intraday_df en la ventana premarket real.
    Devuelve dict (ticker, date) -> n_barras_sospechosas."""
    result = {}
    if ge_df.empty or intraday_df.empty:
        return result

    rth_start, rth_end = BELIEVED_RTH_UTC
    pm_start, pm_end = REAL_PREMARKET_UTC

    ge_win = ge_df[ge_df["utc_ts"].dt.strftime("%H:%M:%S").between(rth_start, rth_end)]
    im_win = intraday_df[intraday_df["utc_ts"].dt.strftime("%H:%M:%S").between(pm_start, pm_end)]

    for (ticker, date), ge_grp in ge_win.groupby(["ticker", "date"]):
        im_grp = im_win[(im_win["symbol"] == ticker) & (im_win["date"] == date)]
        if im_grp.empty:
            continue
        # Coincidencia exacta de OHLC (tolerancia de punto flotante mínima).
        merged = ge_grp.merge(
            im_grp, on=["open", "high", "low", "close"], suffixes=("_ge", "_im"))
        n = len(merged.drop_duplicates(subset=["open", "high", "low", "close",
                                                "utc_ts_ge"]))
        if n > 0:
            result[(ticker, date)] = n
    return result


# ---------------------------------------------------------------------------
# Heurística 2: rango diario incompatible
# ---------------------------------------------------------------------------
def heuristic_2_range_mismatch(ge_df, daily_df):
    """Por ticker-día: rango (max(high)-min(low)) de las barras 'RTH creída'
    en ge_df frente al rango real de market_daily_bars. Devuelve dict
    (ticker, date) -> (tag, range_ge, range_daily, pct)."""
    result = {}
    if ge_df.empty:
        return result

    rth_start, rth_end = BELIEVED_RTH_UTC
    ge_win = ge_df[ge_df["utc_ts"].dt.strftime("%H:%M:%S").between(rth_start, rth_end)]
    daily_idx = daily_df.set_index(["symbol", "date"])[["high", "low"]] \
        if not daily_df.empty else pd.DataFrame()

    for (ticker, date), grp in ge_win.groupby(["ticker", "date"]):
        range_ge = float(grp["high"].max() - grp["low"].min())
        if daily_idx.empty or (ticker, date) not in daily_idx.index:
            continue  # sin referencia diaria, no comparable
        drow = daily_idx.loc[(ticker, date)]
        range_daily = float(drow["high"] - drow["low"])
        if range_daily <= 0:
            continue
        pct = range_ge / range_daily
        if pct < RANGE_MISMATCH_RATIO:
            result[(ticker, date)] = ("SUSPECT_RANGE_MISMATCH", range_ge, range_daily, pct)
        elif pct > RANGE_EXCESSIVE_RATIO:
            result[(ticker, date)] = ("SUSPECT_RANGE_EXCESSIVE", range_ge, range_daily, pct)
    return result


# ---------------------------------------------------------------------------
# Heurística 3: volumen muerto en la primera hora
# ---------------------------------------------------------------------------
def heuristic_3_dead_volume(ge_df):
    """Por ticker-día: % de barras con volumen 0/NULL entre 13:30-14:30 UTC.
    Devuelve dict (ticker, date) -> (pct_dead, n_barras)."""
    result = {}
    if ge_df.empty:
        return result
    fh_start, fh_end = FIRST_HOUR_RTH_UTC
    win = ge_df[ge_df["utc_ts"].dt.strftime("%H:%M:%S").between(fh_start, fh_end)]
    for (ticker, date), grp in win.groupby(["ticker", "date"]):
        n = len(grp)
        if n == 0:
            continue
        dead = int((grp["volume"].isna() | (grp["volume"] == 0)).sum())
        pct = dead / n
        if pct > VOLUME_DEAD_THRESHOLD:
            result[(ticker, date)] = (pct, n)
    return result


# ---------------------------------------------------------------------------
# Orquestación + informe
# ---------------------------------------------------------------------------
def run_audit(engine_db, trading_db):
    engine_conn = sqlite3.connect(engine_db)
    trading_conn = sqlite3.connect(trading_db)

    ge_df = load_ge_bars(engine_conn)
    pairs = sorted(set(zip(ge_df["ticker"], ge_df["date"])))
    n_pairs = len(pairs)
    print(f"Ticker-días en market_bars_1min_ge: {n_pairs}")

    intraday_df = load_intraday_bars_for_pairs(trading_conn, pairs)
    daily_df = load_daily_bars_for_pairs(trading_conn, pairs)
    print(f"Barras cargadas de market_intraday_bars (filtradas por par): {len(intraday_df):,}")
    print(f"Referencias diarias cargadas de market_daily_bars: {len(daily_df):,}")

    h1 = heuristic_1_exact_prematch(ge_df, intraday_df)
    h2 = heuristic_2_range_mismatch(ge_df, daily_df)
    h3 = heuristic_3_dead_volume(ge_df)

    all_pairs = set(h1) | set(h2) | set(h3)
    rows = []
    for ticker, date in sorted(all_pairs):
        reasons = []
        n_prematch = h1.get((ticker, date), 0)
        if (ticker, date) in h1:
            reasons.append("SUSPECT_PREMATCH_EXACT")

        range_tag, range_ge, range_daily, range_pct = (None, None, None, None)
        if (ticker, date) in h2:
            range_tag, range_ge, range_daily, range_pct = h2[(ticker, date)]
            reasons.append(range_tag)

        vol_pct, n_firsthour = (None, None)
        if (ticker, date) in h3:
            vol_pct, n_firsthour = h3[(ticker, date)]
            reasons.append("SUSPECT_VOLUME_DEAD")

        # Confianza combinada: >=2 heurísticas siempre es alta confianza;
        # con solo H1, un match de 1 vela puede ser coincidencia de precio
        # (frecuente en smallcaps con velas planas) — exigir varias barras.
        if len(reasons) >= 2:
            confianza = "ALTA"
        elif reasons == ["SUSPECT_PREMATCH_EXACT"] and n_prematch >= PREMATCH_HIGH_CONFIDENCE_BARS:
            confianza = "ALTA"
        elif reasons:
            confianza = "MEDIA" if reasons != ["SUSPECT_PREMATCH_EXACT"] else "BAJA"
        else:
            confianza = None

        rows.append({
            "ticker": ticker, "date": date,
            "reasons": ";".join(reasons),
            "confianza": confianza,
            "n_heuristicas": len(reasons),
            "n_barras_prematch_exacto": n_prematch,
            "rango_ge_rth_creido": round(range_ge, 4) if range_ge is not None else None,
            "rango_diario_real": round(range_daily, 4) if range_daily is not None else None,
            "pct_rango_vs_diario": round(range_pct * 100, 1) if range_pct is not None else None,
            "pct_volumen_muerto_1a_hora": round(vol_pct * 100, 1) if vol_pct is not None else None,
            "n_barras_1a_hora_analizadas": n_firsthour,
        })

    report = pd.DataFrame(rows).sort_values(
        ["confianza", "n_heuristicas", "ticker", "date"],
        ascending=[True, False, True, True],
        key=lambda s: s.map({"ALTA": 0, "MEDIA": 1, "BAJA": 2}) if s.name == "confianza" else s)

    print("\n" + "=" * 70)
    print("AUDITORÍA BLAST RADIUS — bug de timezone en market_bars_1min_ge")
    print("=" * 70)
    print(f"Ticker-días totales analizados       : {n_pairs}")
    print(f"Sospechosos SUSPECT_PREMATCH_EXACT   : {len(h1)}")
    print(f"Sospechosos SUSPECT_RANGE_MISMATCH   : {sum(1 for v in h2.values() if v[0] == 'SUSPECT_RANGE_MISMATCH')}")
    print(f"Sospechosos SUSPECT_RANGE_EXCESSIVE  : {sum(1 for v in h2.values() if v[0] == 'SUSPECT_RANGE_EXCESSIVE')}")
    print(f"Sospechosos SUSPECT_VOLUME_DEAD      : {len(h3)}")
    print(f"Total ticker-días sospechosos (unión): {len(report)} "
          f"({100 * len(report) / n_pairs:.1f}% del total)")
    print(f"Marcados por >=2 heurísticas a la vez : {(report['n_heuristicas'] >= 2).sum()}")
    print("\nPor nivel de confianza (ALTA = >=2 heurísticas, o H1 con "
          f">={PREMATCH_HIGH_CONFIDENCE_BARS} barras coincidentes; "
          "BAJA = solo H1 con pocas barras, revisar con cautela):")
    print(report["confianza"].value_counts().reindex(["ALTA", "MEDIA", "BAJA"]).fillna(0).astype(int))

    if len(report):
        print("\nTop 15 (ordenado por confianza):")
        cols = ["ticker", "date", "confianza", "reasons", "n_barras_prematch_exacto",
                "pct_rango_vs_diario", "pct_volumen_muerto_1a_hora"]
        print(report[cols].head(15).to_string(index=False))

    out_path = "blast_radius_report.csv"
    report.to_csv(out_path, index=False)
    print(f"\nInforme completo exportado a: {out_path}")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engine-db", default="trader_engine/db/trader_engine.db",
                    help="Ruta a trader_engine.db (contiene market_bars_1min_ge)")
    ap.add_argument("--trading-db", default="trading_data.db",
                    help="Ruta a trading_data.db (contiene market_intraday_bars y market_daily_bars)")
    args = ap.parse_args()
    run_audit(args.engine_db, args.trading_db)


if __name__ == "__main__":
    main()
