#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inspect_ticker_day.py — inspección visual de un ticker-día concreto marcado
por audit_timezone_blast_radius.py, para verificar a simple vista si el bug
de timezone lo afectó de verdad.

De solo lectura. Muestra tres bloques uno debajo del otro, todos convertidos
a ET real (zoneinfo, DST-aware) para poder compararlos:

  1. Lo que quedó en market_bars_1min_ge bajo la etiqueta de "RTH" (columna
     'time', asumida ET por contrato de la tabla).
  2. El premarket real de market_intraday_bars (04:00-09:30 ET).
  3. El RTH real de market_intraday_bars (09:30-16:00 ET).

Si el bloque 1 es prácticamente idéntico al bloque 2 (mismos OHLCV en el
mismo orden), el ticker-día está corrompido: lo que se guardó como "apertura
de mercado" es en realidad el premarket. Si el bloque 1 se parece al bloque 3,
está limpio.

Uso (desde trading_system_v3/):
    python3 ../data_audit_system/inspect_ticker_day.py CDT 2026-06-18
    python3 ../data_audit_system/inspect_ticker_day.py CDT 2026-06-18 --max-rows 20
"""

import argparse
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

ET_ZONE = ZoneInfo("America/New_York")


def _parse_intraday_timestamp(raw):
    if raw is None:
        return pd.NaT
    if "T" in raw or raw.endswith("+00:00") or raw.endswith("Z"):
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    naive = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=ET_ZONE).astimezone(timezone.utc)


def load_ge(engine_conn, ticker, date):
    df = pd.read_sql(
        "SELECT ticker, date, time, open, high, low, close, volume, downloaded_at "
        "FROM market_bars_1min_ge WHERE ticker=? AND date=? ORDER BY time",
        engine_conn, params=(ticker, date))
    if df.empty:
        return df
    naive_et = pd.to_datetime(df["date"] + " " + df["time"])
    df["et_ts"] = naive_et.dt.tz_localize(ET_ZONE, ambiguous="NaT", nonexistent="NaT")
    return df


def load_intraday(trading_conn, ticker, date):
    df = pd.read_sql(
        "SELECT symbol, bar_timestamp, open_price AS open, high_price AS high, "
        "low_price AS low, close_price AS close, volume "
        "FROM market_intraday_bars "
        "WHERE symbol=? AND substr(bar_timestamp,1,10)=? AND timeframe IN ('1min','1m')",
        trading_conn, params=(ticker, date))
    if df.empty:
        return df
    df["utc_ts"] = df["bar_timestamp"].map(_parse_intraday_timestamp)
    df["et_ts"] = df["utc_ts"].dt.tz_convert(ET_ZONE)
    return df.sort_values("et_ts")


def load_daily(trading_conn, ticker, date):
    return pd.read_sql(
        "SELECT symbol, trading_date, open, high, low, close, volume "
        "FROM market_daily_bars WHERE symbol=? AND trading_date=?",
        trading_conn, params=(ticker, date))


def fmt(df, cols):
    if df.empty:
        return "  (sin filas)"
    return df[cols].to_string(index=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ticker")
    ap.add_argument("date", help="YYYY-MM-DD")
    ap.add_argument("--engine-db", default="trader_engine/db/trader_engine.db")
    ap.add_argument("--trading-db", default="trading_data.db")
    ap.add_argument("--max-rows", type=int, default=15,
                    help="Filas a mostrar por bloque (cabeza y cola)")
    args = ap.parse_args()

    engine_conn = sqlite3.connect(args.engine_db)
    trading_conn = sqlite3.connect(args.trading_db)

    ge = load_ge(engine_conn, args.ticker, args.date)
    im = load_intraday(trading_conn, args.ticker, args.date)
    daily = load_daily(trading_conn, args.ticker, args.date)

    im_pm = im[(im["et_ts"].dt.strftime("%H:%M:%S") >= "04:00:00")
              & (im["et_ts"].dt.strftime("%H:%M:%S") < "09:30:00")] if not im.empty else im
    im_rth = im[(im["et_ts"].dt.strftime("%H:%M:%S") >= "09:30:00")
               & (im["et_ts"].dt.strftime("%H:%M:%S") < "16:00:00")] if not im.empty else im

    n = args.max_rows
    print("=" * 78)
    print(f"{args.ticker} {args.date}")
    print("=" * 78)

    print(f"\n[1] market_bars_1min_ge — etiquetado como RTH ({len(ge)} velas)")
    print(fmt(ge.head(n)[["time", "open", "high", "low", "close", "volume", "downloaded_at"]],
              ["time", "open", "high", "low", "close", "volume", "downloaded_at"]))
    if len(ge) > n:
        print(f"  ... ({len(ge) - n} más)")

    print(f"\n[2] market_intraday_bars — PREMARKET real 04:00-09:30 ET ({len(im_pm)} velas)")
    if not im_pm.empty:
        show = im_pm.copy()
        show["hora_et"] = show["et_ts"].dt.strftime("%H:%M:%S")
        print(fmt(show.head(n)[["hora_et", "open", "high", "low", "close", "volume"]],
                  ["hora_et", "open", "high", "low", "close", "volume"]))
        if len(im_pm) > n:
            print(f"  ... ({len(im_pm) - n} más)")
    else:
        print("  (sin filas)")

    print(f"\n[3] market_intraday_bars — RTH real 09:30-16:00 ET ({len(im_rth)} velas)")
    if not im_rth.empty:
        show = im_rth.copy()
        show["hora_et"] = show["et_ts"].dt.strftime("%H:%M:%S")
        print(fmt(show.head(n)[["hora_et", "open", "high", "low", "close", "volume"]],
                  ["hora_et", "open", "high", "low", "close", "volume"]))
        if len(im_rth) > n:
            print(f"  ... ({len(im_rth) - n} más)")
    else:
        print("  (sin filas — no hay RTH real disponible en market_intraday_bars para este día)")

    print(f"\n[4] market_daily_bars — referencia diaria")
    print(fmt(daily, ["open", "high", "low", "close", "volume"]) if not daily.empty
          else "  (sin fila)")

    # Veredicto automático: para cada vela de [1], ¿su OHLC aparece EN
    # CUALQUIER PUNTO de [2] (premarket)? Búsqueda por contenido, no por
    # posición — el fragmento copiado no tiene por qué empezar en el primer
    # minuto de premarket. Complementado con la señal de volumen: RTH real de
    # un smallcap operable casi nunca tiene la apertura a volumen 0.
    print("\n" + "-" * 78)
    if not ge.empty and not im_pm.empty:
        pm_set = set(map(tuple, im_pm[["open", "high", "low", "close"]].round(6).values))
        ge_ohlc = ge[["open", "high", "low", "close"]].round(6)
        match_mask = ge_ohlc.apply(tuple, axis=1).isin(pm_set)
        n_match = int(match_mask.sum())
        print(f"Velas de [1] cuyo OHLC aparece en algún punto de [2] (premarket): "
              f"{n_match}/{len(ge)} ({100*n_match/len(ge):.0f}%)")

        vol_open = ge.head(5)["volume"]
        vol_dead = int((vol_open == 0).sum())
        print(f"Volumen en los primeros 5 minutos etiquetados '09:30 RTH': "
              f"{list(vol_open)} ({vol_dead}/5 en cero)")

        if n_match / len(ge) > 0.5:
            print("VEREDICTO: CONTAMINADO — la mayoría de velas etiquetadas RTH "
                  "son en realidad premarket copiado.")
        elif vol_dead >= 4 and not im_rth.empty and im_rth.head(5)["volume"].sum() > 0:
            print("VEREDICTO: SOSPECHOSO — apertura con volumen ~0 mientras el RTH "
                  "real de referencia [3] sí tiene volumen: el bloque [1] no parece "
                  "ser la apertura real, aunque el match exacto de OHLC no la localizó "
                  "(la fuente premarket puede estar incompleta en market_intraday_bars).")
        elif n_match == 0:
            print("VEREDICTO: probablemente limpio — sin coincidencias con premarket "
                  "y volumen de apertura coherente.")
        else:
            print("VEREDICTO: mixto — revisar manualmente los bloques [1]-[4] arriba.")
    else:
        print("Sin datos suficientes para veredicto automático — revisar manualmente"
              " los bloques [1]-[4] arriba.")


if __name__ == "__main__":
    main()
