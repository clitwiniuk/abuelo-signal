#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Punto de entrada del sistema de auditoría de datos.

Uso normal (tras cada descarga nueva):
    python3 run_audit.py <carpeta_datos> <carpeta_salida> \
        [--contract contract.yaml] [--scanner-log scanner.jsonl] \
        [--reference tickers_historicos.csv] [--source IBKR] [--format csv]

Demo autocontenida (genera datos sintéticos con errores sembrados y audita):
    python3 run_audit.py --demo
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_audit import run_data_audit, audit_trade  # noqa: E402


# ===========================================================================
# DEMO: dataset sintético de small caps con errores sembrados a propósito
# ===========================================================================
def build_demo_data(base_folder):
    """Genera ~18 tickers x 10 sesiones de velas 1-min con errores conocidos:
    velas OHLC inválidas, volumen negativo, duplicados, dato congelado,
    gap sospechoso sin volumen, ticker que desaparece sin delisting,
    ticker huérfano, look-ahead en downloaded_at y un scanner que deriva.
    Sirve para verificar que cada check dispara donde debe."""
    import numpy as np
    import pandas as pd
    import pandas_market_calendars as mcal

    rng = np.random.default_rng(42)
    data_dir = os.path.join(base_folder, "data")
    os.makedirs(data_dir, exist_ok=True)

    cal = mcal.get_calendar("NASDAQ")
    sessions = [d.strftime("%Y-%m-%d")
                for d in cal.schedule("2026-06-15", "2026-06-26").index]

    tickers = [f"TCK{i:02d}" for i in range(16)] + ["GONE", "ORPH"]
    rows = []
    for ticker in tickers:
        price = rng.uniform(1.5, 12.0)
        for si, date in enumerate(sessions):
            if ticker == "GONE" and si >= 5:
                continue   # desaparece a mitad de dataset sin delisting
            if ticker == "ORPH" and si < 6:
                continue   # huérfano: aparece tarde sin IPO que lo explique
            # Sesión extendida 04:00-20:00 ET; los ilíquidos solo tienen
            # velas en una fracción de los minutos (realista en small caps).
            minutes = pd.date_range(f"{date} 04:00", f"{date} 19:59",
                                    freq="1min", tz="America/New_York")
            keep = rng.random(len(minutes)) < rng.uniform(0.25, 0.85)
            minutes = minutes[keep]
            drift = rng.normal(0, 0.002, len(minutes)).cumsum()
            close = price * np.exp(drift)
            open_ = np.roll(close, 1); open_[0] = price
            high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.004, len(minutes)))
            low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.004, len(minutes)))
            vol = rng.integers(100, 8000, len(minutes)).astype(float)
            downloaded = (minutes.tz_convert("UTC") + pd.Timedelta(hours=6))
            rows.append(pd.DataFrame({
                "symbol": ticker,                      # alias a propósito
                "dt": minutes.tz_convert("UTC"),       # alias a propósito
                "open": open_, "high": high, "low": low, "close": close,
                "volume": vol, "downloaded_at": downloaded,
            }))
            price = close[-1]

    df = pd.concat(rows, ignore_index=True)

    # --- Errores sembrados -------------------------------------------------
    day0, day2, day4 = sessions[0], sessions[2], sessions[4]
    def sample_idx(ticker, date, n):
        pool = df[(df["symbol"] == ticker)
                  & (df["dt"].dt.tz_convert("America/New_York")
                       .dt.strftime("%Y-%m-%d") == date)].index
        return rng.choice(pool, size=min(n, len(pool)), replace=False)

    df.loc[sample_idx("TCK01", day0, 5), "high"] = 0.01        # high < low
    df.loc[sample_idx("TCK02", day0, 4), "volume"] = -500      # volumen negativo
    df.loc[sample_idx("TCK03", day2, 3), "close"] = float("nan")  # precio NaN
    dup = df[df["symbol"] == "TCK04"].head(30)                 # duplicados
    df = pd.concat([df, dup], ignore_index=True)
    frozen = sample_idx("TCK05", day2, 0)                      # dato congelado:
    mask = (df["symbol"] == "TCK05") & (df["dt"].dt.tz_convert(
        "America/New_York").dt.strftime("%Y-%m-%d") == day2)
    idx = df[mask].sort_values("dt").index[:60]
    df.loc[idx, ["open", "high", "low", "close"]] = 5.55
    df.loc[idx, "volume"] = 1000
    mask6 = (df["symbol"] == "TCK06") & (df["dt"].dt.tz_convert(  # gap x3 sin volumen
        "America/New_York").dt.strftime("%Y-%m-%d") >= day4)
    df.loc[mask6, ["open", "high", "low", "close"]] *= 3.2
    la = sample_idx("TCK07", day2, 25)                         # look-ahead
    df.loc[la, "downloaded_at"] = df.loc[la, "dt"] - pd.Timedelta(days=2)

    df.to_csv(os.path.join(data_dir, "bars_demo.csv"), index=False)

    # --- Referencia histórica de universo (para survivorship) --------------
    ref_rows = [{"ticker": t, "list_date": "2024-01-02", "delist_date": ""}
                for t in tickers if t not in ("GONE", "ORPH")]
    ref_rows.append({"ticker": "GONE", "list_date": "2024-01-02", "delist_date": ""})
    ref_rows.append({"ticker": "ORPH", "list_date": "2024-01-02", "delist_date": ""})
    ref_rows.append({"ticker": "DEAD", "list_date": "2024-01-02",
                     "delist_date": sessions[-1]})  # existía y no está: survivorship
    ref_path = os.path.join(base_folder, "reference_tickers.csv")
    import pandas as pd2
    pd2.DataFrame(ref_rows).to_csv(ref_path, index=False)

    # --- Log del scanner: deriva de universo + cambio de parámetros --------
    snapshots = []
    universe = tickers[:15]
    for si, date in enumerate(sessions):
        params = {"min_gap_pct": 15, "max_price": 20}
        if si >= 7:
            params = {"min_gap_pct": 10, "max_price": 20}   # cambio de régimen
        if si == 4:
            universe = tickers[8:] + ["ZZZZ", "YYYY", "XXXX"]  # deriva >30%
        snapshots.append({"fecha": date, "parametros": params,
                          "lista_tickers_devueltos": list(universe)})
    scanner_path = os.path.join(base_folder, "scanner_log.jsonl")
    with open(scanner_path, "w", encoding="utf-8") as fh:
        for s in snapshots:
            fh.write(json.dumps(s) + "\n")

    return data_dir, ref_path, scanner_path, sessions


def demo_strategy(view, date):
    """Estrategia de ejemplo para el replay temporal: correcta en el universo
    (solo usa view) pero con UN acceso look-ahead deliberado para demostrar
    que el test lo captura."""
    for ticker in view.universe()[:3]:
        view.get_bars(ticker)                       # acceso legítimo (<= as_of)
    # Error deliberado: pedir datos hasta el cierre del propio día D.
    view.get_bars("TCK00", end=f"{date} 23:59")


def run_demo():
    """Demo end-to-end: genera datos, audita, y audita dos trades de ejemplo."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_run")
    os.makedirs(base, exist_ok=True)
    data_dir, ref_path, scanner_path, sessions = build_demo_data(base)
    out_dir = os.path.join(base, "audit_output")

    results = run_data_audit(
        data_folder=data_dir,
        output_folder=out_dir,
        scanner_log=scanner_path,
        reference_tickers_csv=ref_path,
        strategy_fn=demo_strategy,
        source_name="DEMO_SYNTHETIC",
    )

    # --- audit_trade: un trade limpio y otro con look-ahead -----------------
    # El trade "limpio" decide AHORA (datos ya descargados y en el historial):
    # veredicto APTO. El trade "malo" decide en el pasado, antes de que los
    # datos existieran en disco: audit_trade lo caza como look-ahead de
    # infraestructura, además del look-ahead sembrado en downloaded_at.
    import pandas as pd
    from data_audit.traceability import load_metadata_history
    history = load_metadata_history(out_dir)
    good = {"ticker": "TCK10",
            "decision_time": pd.Timestamp.utcnow().isoformat()}
    bad = {"ticker": "TCK07", "decision_time": f"{sessions[2]} 10:00:00+00:00"}
    print("\naudit_trade — trade limpio:")
    print(json.dumps(audit_trade(good, results["df"], results["violations"],
                                 history=history), indent=2, ensure_ascii=False))
    print("\naudit_trade — trade sobre ticker con look-ahead sembrado:")
    print(json.dumps(audit_trade(bad, results["df"], results["violations"],
                                 history=history), indent=2, ensure_ascii=False))


# ===========================================================================
# CLI
# ===========================================================================
def main():
    p = argparse.ArgumentParser(description="Auditoría de datos intradía 1-min")
    p.add_argument("data_folder", nargs="?", help="Carpeta con CSV/Parquet")
    p.add_argument("output_folder", nargs="?", help="Carpeta de salida")
    p.add_argument("--contract", help="YAML con overrides del contrato")
    p.add_argument("--scanner-log", help="JSON/JSONL de snapshots del scanner")
    p.add_argument("--reference", help="CSV universo histórico (ticker,list_date,delist_date)")
    p.add_argument("--source", default="unknown", help="Nombre de la fuente de datos")
    p.add_argument("--format", default="parquet", choices=["parquet", "csv"])
    p.add_argument("--demo", action="store_true", help="Ejecutar demo sintética")
    args = p.parse_args()

    if args.demo:
        run_demo()
        return
    if not args.data_folder or not args.output_folder:
        p.error("data_folder y output_folder son obligatorios (o usa --demo)")

    run_data_audit(args.data_folder, args.output_folder,
                   contract_path=args.contract,
                   scanner_log=args.scanner_log,
                   reference_tickers_csv=args.reference,
                   source_name=args.source,
                   output_format=args.format)


if __name__ == "__main__":
    main()
