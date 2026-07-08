#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
detect_splits_via_ibkr.py — detecta y cuantifica splits no documentados
comparando el precio ACTUAL (fresco) que devuelve IBKR para un día
histórico contra lo que ya tenemos guardado en market_intraday_bars.

Descubrimiento clave (verificado con RAYA 2026-04-10): IBKR aplica el
ajuste por split de forma retroactiva sobre 'TRADES' en cuanto ha pasado
tiempo suficiente desde el split — no hace falta pedir 'ADJUSTED_LAST'
(que además no admite endDateTime histórico, error 321 'End date not
supported with adjusted last'). Comparando contra 'ADJUSTED_LAST' el
ratio siempre daba 1.0 (ambos ya vienen ajustados). En cambio comparar el
'TRADES' fresco contra lo guardado en market_intraday_bars sí revela el
desajuste: para RAYA, IBKR fresco daba 9.505 (= lo que ya tenía
market_daily_bars) mientras market_intraday_bars tenía 0.8001 (11.9x
menor, congelado desde antes del split y nunca refrescado).

Conclusión operativa: market_daily_bars es la referencia fiable (coincide
con IBKR fresco); market_intraday_bars es la fuente contaminada. El ratio
detectado aquí es exactamente el factor de corrección a aplicar sobre
market_intraday_bars (y, por herencia, sobre market_bars_1min_ge).

Evita yfinance (prohibido en este proyecto, ver CLAUDE.md) — todo viene
de IBKR/TWS, igual que el resto del pipeline de datos.

De solo lectura respecto a tu DB: solo escribe si pasas --write-to-db, y
únicamente en split_events (nunca toca market_daily_bars/market_intraday_bars).

Uso (con TWS/Gateway corriendo en 127.0.0.1:7497):
    python3 detect_splits_via_ibkr.py --tickers NCRA,PAVS,POM --dates 2026-05-26,2026-06-09,2026-05-11
    python3 detect_splits_via_ibkr.py --from-csv reports/split_mismatch_scan_2026-07-08.csv
"""

import argparse
import asyncio
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from ib_insync import IB, Contract, util

IB_HOST = "127.0.0.1"
IB_PORT = 7497
CLIENT_ID = 5097
SLEEP_SEC = 11.0
RATIO_THRESHOLD = 1.5  # por debajo de esto, se considera "sin split detectable"


def build_contract(ticker: str) -> Contract:
    c = Contract()
    c.symbol, c.secType, c.exchange, c.currency = ticker, "STK", "SMART", "USD"
    return c


async def fetch_fresh_close(ib: IB, ticker: str, date: str):
    """Precio de cierre fresco de IBKR (TRADES) para `date`. Sin acotar
    endDateTime al día exacto: se pide desde hoy hacia atrás lo suficiente
    y se localiza la barra de esa sesión, así IBKR aplica su ajuste
    retroactivo normal sobre el histórico completo."""
    target_date = datetime.strptime(date, "%Y-%m-%d").date()
    days_back = (datetime.now().date() - target_date).days + 5
    duration = f"{max(days_back, 5)} D"
    try:
        bars = await ib.reqHistoricalDataAsync(
            build_contract(ticker),
            endDateTime="", durationStr=duration,
            barSizeSetting="1 day", whatToShow="TRADES",
            useRTH=True, formatDate=1,
        )
    except Exception as e:
        print(f"  [{ticker} {date}] error IBKR: {e}")
        return None
    if not bars:
        return None
    same_day = [b for b in bars if str(b.date)[:10] == date]
    if same_day:
        return same_day[0].close
    before = [b for b in bars if str(b.date)[:10] <= date]
    return before[-1].close if before else None


def stored_close(trading_conn, ticker, date):
    """Último close guardado en market_intraday_bars para ese ticker-día."""
    row = trading_conn.execute(
        "SELECT close_price FROM market_intraday_bars "
        "WHERE symbol=? AND substr(bar_timestamp,1,10)=? AND timeframe='1min' "
        "ORDER BY bar_timestamp DESC LIMIT 1",
        (ticker, date)).fetchone()
    return row[0] if row else None


def daily_close(trading_conn, ticker, date):
    row = trading_conn.execute(
        "SELECT close FROM market_daily_bars WHERE symbol=? AND trading_date=?",
        (ticker, date)).fetchone()
    return row[0] if row else None


async def detect(ib: IB, trading_conn, ticker: str, date: str):
    fresh = await fetch_fresh_close(ib, ticker, date)
    await asyncio.sleep(SLEEP_SEC)
    stored = stored_close(trading_conn, ticker, date)
    daily = daily_close(trading_conn, ticker, date)

    if fresh is None or stored is None or stored <= 0:
        return {"ticker": ticker, "date": date, "ibkr_fresh_close": fresh,
                "market_intraday_stored_close": stored, "market_daily_close": daily,
                "ratio": None, "split_detectado": None,
                "daily_matches_fresh_ibkr": None}

    ratio = fresh / stored
    detected = ratio > RATIO_THRESHOLD or ratio < (1 / RATIO_THRESHOLD)
    daily_match = (daily is not None and abs(daily - fresh) / fresh < 0.05)
    return {"ticker": ticker, "date": date, "ibkr_fresh_close": round(fresh, 4),
            "market_intraday_stored_close": round(stored, 4),
            "market_daily_close": round(daily, 4) if daily is not None else None,
            "ratio": round(ratio, 3), "split_detectado": detected,
            "daily_matches_fresh_ibkr": daily_match}


async def run(pairs, write_to_db, engine_db, trading_db):
    ib = IB()
    trading_conn = sqlite3.connect(trading_db)
    await ib.connectAsync(IB_HOST, IB_PORT, clientId=CLIENT_ID)
    print(f"Conectado a IBKR ({len(pairs)} pares a consultar, "
          f"~{len(pairs) * SLEEP_SEC / 60:.1f} min estimados)")

    results = []
    for i, (ticker, date) in enumerate(pairs):
        print(f"[{i+1}/{len(pairs)}] {ticker} {date}...")
        r = await detect(ib, trading_conn, ticker, date)
        results.append(r)
        tag = "SPLIT DETECTADO" if r["split_detectado"] else (
            "sin split" if r["split_detectado"] is False else "SIN DATOS")
        print(f"  ibkr_fresh={r['ibkr_fresh_close']} "
              f"stored_intraday={r['market_intraday_stored_close']} "
              f"daily={r['market_daily_close']} ratio={r['ratio']} -> {tag}")

    ib.disconnect()
    trading_conn.close()

    df = pd.DataFrame(results)
    out_path = Path(__file__).parent / "reports" / \
        f"ibkr_split_detection_{datetime.now():%Y%m%d_%H%M%S}.csv"
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"\nResultado -> {out_path}")
    print(df.to_string(index=False))

    detected = df[df["split_detectado"] == True]  # noqa: E712
    print(f"\n{len(detected)}/{len(df)} pares con split confirmado por IBKR "
          f"(ratio fuera de [{1/RATIO_THRESHOLD:.2f}, {RATIO_THRESHOLD:.2f}])")
    n_daily_ok = df["daily_matches_fresh_ibkr"].sum()
    print(f"market_daily_bars coincide con IBKR fresco en {n_daily_ok}/{len(df)} casos "
          f"(confirma que market_daily_bars es la referencia fiable)")

    if write_to_db and len(detected):
        conn = sqlite3.connect(trading_db)  # split_events vive en trading_data.db
        conn.execute("""
            CREATE TABLE IF NOT EXISTS split_events (
                symbol TEXT, effective_date TEXT, ratio REAL, display_ratio TEXT,
                PRIMARY KEY (symbol, effective_date)
            )
        """)
        for _, row in detected.iterrows():
            display = f"1:{round(row['ratio'])}" if row["ratio"] >= 1 else \
                f"{round(1/row['ratio'])}:1"
            conn.execute(
                "INSERT OR REPLACE INTO split_events "
                "(symbol, effective_date, ratio, display_ratio) VALUES (?,?,?,?)",
                (row["ticker"], "UNKNOWN_EXACT_DATE_detected_" + row["date"],
                 row["ratio"], display))
        conn.commit()
        conn.close()
        print(f"Escritos {len(detected)} registros en split_events "
              f"(effective_date desconocida exacta, marcada como aproximada)")

    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickers", help="Lista separada por comas")
    ap.add_argument("--dates", help="Lista separada por comas, alineada con --tickers")
    ap.add_argument("--from-csv", help="CSV con columnas ticker,date (p.ej. split_mismatch_scan)")
    ap.add_argument("--engine-db", default="trader_engine/db/trader_engine.db")
    ap.add_argument("--trading-db", default="trading_data.db")
    ap.add_argument("--write-to-db", action="store_true",
                    help="Escribe los splits detectados en split_events (por defecto solo CSV)")
    args = ap.parse_args()

    if args.from_csv:
        df = pd.read_csv(args.from_csv)
        pairs = list(df[["ticker", "date"]].itertuples(index=False, name=None))
    elif args.tickers and args.dates:
        tickers = args.tickers.split(",")
        dates = args.dates.split(",")
        if len(tickers) != len(dates):
            sys.exit("--tickers y --dates deben tener la misma longitud")
        pairs = list(zip(tickers, dates))
    else:
        sys.exit("Pasa --from-csv o --tickers/--dates")

    util.startLoop()
    asyncio.run(run(pairs, args.write_to_db, args.engine_db, args.trading_db))


if __name__ == "__main__":
    main()
