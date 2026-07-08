# -*- coding: utf-8 -*-
"""
MÓDULO 4: INFORME DE SALUD DE DATOS (DATA HEALTH REPORT)

- flag_invalid_rows : marca fila a fila is_valid según reglas del contrato.
- compute_scores    : score 0-100 por ticker-día y por día.
- build_summary     : agregados (% días válidos, % tickers válidos, ...).
- export_violations_csv / save_clean_data / generate_html_report / print_summary.

El HTML no depende de matplotlib: el diagrama temporal de calidad se dibuja
con barras CSS inline, así el informe es un único fichero autocontenido.
"""

import html
import os

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Marcado fila a fila (is_valid)
# ---------------------------------------------------------------------------
def flag_invalid_rows(df, contract):
    """Devuelve una Series booleana is_valid aplicando las reglas del contrato
    que son decidibles a nivel de fila (las violaciones agregadas —universo,
    survivorship— afectan al score del día, no a la validez de la fila)."""
    tol = contract["ohlc_tolerance_pct"] / 100.0
    price_cols = ["open", "high", "low", "close"]

    valid = pd.Series(True, index=df.index)
    # Precios corruptos.
    valid &= ~df[price_cols].isna().any(axis=1)
    valid &= (df[price_cols] > 0).all(axis=1)
    # Volumen corrupto (NaN/negativo; vol=0 se tolera como fila, es INFO).
    valid &= df["volume"].notna() & (df["volume"] >= 0)
    # OHLC coherente.
    valid &= df["high"] >= df["low"]
    valid &= (df["close"] >= df["low"] * (1 - tol)) & (df["close"] <= df["high"] * (1 + tol))
    valid &= (df["open"] >= df["low"] * (1 - tol)) & (df["open"] <= df["high"] * (1 + tol))
    # Duplicados: se conserva la primera aparición, el resto se invalida.
    valid &= ~df.duplicated(subset=["ticker", "timestamp"], keep="first")
    # Fuera de sesión extendida (04:00-20:00 ET): datos no contratados.
    et = df["timestamp"].dt.tz_convert(contract["market_timezone"])
    hhmm = et.dt.strftime("%H:%M")
    valid &= (hhmm >= contract["session_start"]) & (hhmm < contract["session_end"])
    # Sin trazabilidad de descarga o descarga anterior al dato.
    col = contract["download_ts_column"]
    if col in df.columns:
        valid &= df[col].notna() & (df[col] >= df["timestamp"])
    else:
        valid &= False  # sin downloaded_at el contrato no se cumple
    return valid


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def compute_scores(df, violations, contract):
    """Score 0-100 por (ticker, date) y por date.

    Cada violación resta su peso por severidad. Las violaciones de universo
    (ticker='*') penalizan el score del día completo.
    Devuelve (scores_ticker_dia: DataFrame, scores_dia: DataFrame).
    """
    weights = contract["score_weights"]
    vdf = pd.DataFrame(violations) if violations else \
        pd.DataFrame(columns=["ticker", "date", "check_type", "severity", "detail"])

    # Base: todos los pares (ticker, date) presentes en los datos.
    pairs = df[["ticker", "date"]].drop_duplicates()
    penalties = {}
    for _, v in vdf[vdf["ticker"] != "*"].iterrows():
        key = (v["ticker"], v["date"])
        penalties[key] = penalties.get(key, 0) + weights.get(v["severity"], 0)

    rows = []
    for _, p in pairs.iterrows():
        pen = penalties.get((p["ticker"], p["date"]), 0)
        rows.append({"ticker": p["ticker"], "date": p["date"],
                     "score": max(0, 100 - pen)})
    scores_td = pd.DataFrame(rows)

    # Score del día: media de sus tickers menos penalizaciones globales ('*').
    day_pen = {}
    for _, v in vdf[vdf["ticker"] == "*"].iterrows():
        day_pen[v["date"]] = day_pen.get(v["date"], 0) + weights.get(v["severity"], 0)
    scores_day = (scores_td.groupby("date")["score"].mean().round(1)
                  .reset_index(name="score"))
    scores_day["score"] = scores_day.apply(
        lambda r: max(0, r["score"] - day_pen.get(r["date"], 0)), axis=1)
    scores_day["is_valid_day"] = scores_day["score"] >= contract["min_score_valid"]
    scores_td["is_valid"] = scores_td["score"] >= contract["min_score_valid"]
    return scores_td, scores_day


def build_summary(df, valid_mask, violations, scores_td, scores_day, contract):
    """Agregados del informe: % días/tickers válidos, % datos descartados,
    tickers NO APTOS con su razón principal."""
    vdf = pd.DataFrame(violations) if violations else \
        pd.DataFrame(columns=["ticker", "date", "check_type", "severity", "detail"])

    # Tickers NO APTOS: score medio bajo el umbral, con la razón dominante.
    ticker_scores = scores_td.groupby("ticker")["score"].mean()
    unfit = []
    for ticker, score in ticker_scores[ticker_scores < contract["min_score_valid"]].items():
        tv = vdf[vdf["ticker"] == ticker]
        if len(tv):
            # Razón principal = check con más peso acumulado.
            w = contract["score_weights"]
            reason = (tv.assign(w=tv["severity"].map(w))
                        .groupby("check_type")["w"].sum().idxmax())
        else:
            reason = "score_bajo"
        unfit.append({"ticker": ticker, "score_medio": round(score, 1),
                      "razon_principal": reason})

    sev_counts = vdf["severity"].value_counts().to_dict() if len(vdf) else {}
    return {
        "n_filas": int(len(df)),
        "n_tickers": int(df["ticker"].nunique()),
        "n_dias": int(df["date"].nunique()),
        "pct_dias_validos": round(100 * scores_day["is_valid_day"].mean(), 1) if len(scores_day) else 0.0,
        "pct_tickers_validos": round(100 * (ticker_scores >= contract["min_score_valid"]).mean(), 1) if len(ticker_scores) else 0.0,
        "pct_datos_descartados": round(100 * (1 - valid_mask.mean()), 2) if len(valid_mask) else 0.0,
        "n_violaciones": int(len(vdf)),
        "violaciones_por_severidad": sev_counts,
        "tickers_no_aptos": sorted(unfit, key=lambda u: u["score_medio"]),
    }


# ---------------------------------------------------------------------------
# Exportación
# ---------------------------------------------------------------------------
def export_violations_csv(violations, path):
    """CSV con todas las violaciones en el formato exacto del Módulo 2."""
    cols = ["ticker", "date", "check_type", "severity", "detail"]
    pd.DataFrame(violations, columns=cols).sort_values(
        ["severity", "ticker", "date"]).to_csv(path, index=False)
    return path


def save_clean_data(df, valid_mask, output_folder, fmt="parquet"):
    """Guarda una copia SOLO con filas válidas. Los originales no se tocan:
    este fichero es derivado y regenerable. También guarda el dataset completo
    anotado con is_valid para inspección."""
    os.makedirs(output_folder, exist_ok=True)
    annotated = df.copy()
    annotated["is_valid"] = valid_mask.values
    clean = annotated[annotated["is_valid"]].drop(columns=["is_valid"])
    if fmt == "parquet":
        clean_path = os.path.join(output_folder, "clean_data.parquet")
        clean.to_parquet(clean_path, index=False)
        annotated.to_parquet(os.path.join(output_folder, "annotated_data.parquet"),
                             index=False)
    else:
        clean_path = os.path.join(output_folder, "clean_data.csv")
        clean.to_csv(clean_path, index=False)
        annotated.to_csv(os.path.join(output_folder, "annotated_data.csv"), index=False)
    return clean_path


# ---------------------------------------------------------------------------
# Informe HTML (autocontenido, sin dependencias externas)
# ---------------------------------------------------------------------------
def _score_color(score):
    if score >= 85:
        return "#2e9e5b"   # verde
    if score >= 70:
        return "#d9a520"   # ámbar
    return "#c94f4f"       # rojo


def generate_html_report(summary, scores_day, scores_td, violations, contract,
                         path, regimes=None):
    """Informe HTML con: resumen, timeline de calidad (barras CSS), tickers
    no aptos y las 200 violaciones más severas."""
    vdf = pd.DataFrame(violations) if violations else \
        pd.DataFrame(columns=["ticker", "date", "check_type", "severity", "detail"])
    sev_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    if len(vdf):
        vdf = vdf.sort_values("severity", key=lambda s: s.map(sev_order)).head(200)

    bars = []
    for _, r in scores_day.sort_values("date").iterrows():
        bars.append(
            f'<div class="bar" title="{r["date"]}: {r["score"]:.0f}" '
            f'style="height:{max(4, r["score"])}px;background:{_score_color(r["score"])}">'
            f'</div>')

    unfit_rows = "".join(
        f'<tr><td>{html.escape(u["ticker"])}</td><td>{u["score_medio"]}</td>'
        f'<td>{html.escape(u["razon_principal"])}</td></tr>'
        for u in summary["tickers_no_aptos"])

    viol_rows = "".join(
        f'<tr class="{v["severity"].lower()}"><td>{html.escape(str(v["ticker"]))}</td>'
        f'<td>{v["date"]}</td><td>{html.escape(v["check_type"])}</td>'
        f'<td>{v["severity"]}</td><td>{html.escape(str(v["detail"]))}</td></tr>'
        for _, v in vdf.iterrows())

    regime_html = ""
    if regimes:
        items = "".join(f"<li>{r[0]} → {r[1]} — parámetros: "
                        f"<code>{html.escape(str(r[2]))}</code></li>" for r in regimes)
        regime_html = f"<h2>Regímenes del scanner</h2><ul>{items}</ul>"

    sev = summary["violaciones_por_severidad"]
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Data Health Report</title>
<style>
 body{{font-family:-apple-system,Segoe UI,sans-serif;margin:2rem;color:#222;max-width:1100px}}
 h1{{font-size:1.4rem}} h2{{font-size:1.1rem;margin-top:2rem}}
 .cards{{display:flex;gap:1rem;flex-wrap:wrap}}
 .card{{border:1px solid #ddd;border-radius:8px;padding:.8rem 1.2rem;min-width:140px}}
 .card .v{{font-size:1.5rem;font-weight:600}} .card .l{{font-size:.75rem;color:#666}}
 .timeline{{display:flex;align-items:flex-end;gap:2px;height:110px;border-bottom:1px solid #ccc;overflow-x:auto;padding-bottom:1px}}
 .bar{{width:14px;min-width:8px;border-radius:2px 2px 0 0}}
 table{{border-collapse:collapse;width:100%;font-size:.82rem;margin-top:.5rem}}
 th,td{{border:1px solid #e3e3e3;padding:4px 8px;text-align:left}}
 th{{background:#f5f5f5}}
 tr.critical td{{background:#fdecec}} tr.warning td{{background:#fdf6e3}}
</style></head><body>
<h1>Data Health Report</h1>
<p>Generado: {pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC")} ·
Contrato: score mínimo {contract["min_score_valid"]}, universo mínimo
{contract["min_tickers_per_day"]} tickers/día</p>
<div class="cards">
 <div class="card"><div class="v">{summary["n_filas"]:,}</div><div class="l">filas</div></div>
 <div class="card"><div class="v">{summary["n_tickers"]}</div><div class="l">tickers</div></div>
 <div class="card"><div class="v">{summary["n_dias"]}</div><div class="l">días</div></div>
 <div class="card"><div class="v">{summary["pct_dias_validos"]}%</div><div class="l">días válidos</div></div>
 <div class="card"><div class="v">{summary["pct_tickers_validos"]}%</div><div class="l">tickers válidos</div></div>
 <div class="card"><div class="v">{summary["pct_datos_descartados"]}%</div><div class="l">filas descartadas</div></div>
 <div class="card"><div class="v">{sev.get("CRITICAL", 0)}</div><div class="l">CRITICAL</div></div>
 <div class="card"><div class="v">{sev.get("WARNING", 0)}</div><div class="l">WARNING</div></div>
</div>
<h2>Calidad por día (0-100)</h2>
<div class="timeline">{"".join(bars)}</div>
<p style="font-size:.75rem;color:#666">Pasa el cursor por las barras para ver fecha y score.
Verde ≥85 · ámbar 70-85 · rojo &lt;70 (día NO APTO).</p>
{regime_html}
<h2>Tickers NO APTOS ({len(summary["tickers_no_aptos"])})</h2>
<table><tr><th>Ticker</th><th>Score medio</th><th>Razón principal</th></tr>{unfit_rows}</table>
<h2>Violaciones (top 200 por severidad; CSV completo aparte)</h2>
<table><tr><th>Ticker</th><th>Fecha</th><th>Check</th><th>Severidad</th><th>Detalle</th></tr>
{viol_rows}</table>
</body></html>"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return path


def print_summary(summary, scores_day, contract):
    """Resumen legible en consola."""
    print("=" * 64)
    print("DATA HEALTH REPORT — resumen")
    print("=" * 64)
    print(f"Filas: {summary['n_filas']:,} | Tickers: {summary['n_tickers']} "
          f"| Días: {summary['n_dias']}")
    print(f"Días válidos:      {summary['pct_dias_validos']}%")
    print(f"Tickers válidos:   {summary['pct_tickers_validos']}%")
    print(f"Filas descartadas: {summary['pct_datos_descartados']}%")
    print(f"Violaciones: {summary['n_violaciones']} "
          f"{summary['violaciones_por_severidad']}")
    worst = scores_day.nsmallest(5, "score") if len(scores_day) else scores_day
    if len(worst):
        print("Peores días:")
        for _, r in worst.iterrows():
            flag = "OK " if r["is_valid_day"] else "NO APTO"
            print(f"  {r['date']}  score={r['score']:5.1f}  [{flag}]")
    if summary["tickers_no_aptos"]:
        print(f"Tickers NO APTOS ({len(summary['tickers_no_aptos'])}):")
        for u in summary["tickers_no_aptos"][:10]:
            print(f"  {u['ticker']:<8} score={u['score_medio']:5.1f} "
                  f"razón={u['razon_principal']}")
    print("=" * 64)
