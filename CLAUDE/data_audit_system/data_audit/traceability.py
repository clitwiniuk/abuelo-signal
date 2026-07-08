# -*- coding: utf-8 -*-
"""
MÓDULO 5: TRAZABILIDAD TOTAL

- create_download_metadata : JSON por descarga (fuente, sha256, rango, scanner).
- load_metadata_history    : reconstruye qué datos existían en cualquier momento.
- audit_trade              : verifica que una operación simulada solo usó datos
                             disponibles y válidos en el momento de la decisión.
"""

import hashlib
import json
import os

import pandas as pd

HISTORY_FILE = "metadata_history.jsonl"


def sha256_file(path, chunk_size=1 << 20):
    """Hash SHA256 de un fichero (streaming, apto para ficheros grandes)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def create_download_metadata(data_file, source, output_folder,
                             scanner_params=None, df=None):
    """Genera y persiste los metadatos de una descarga.

    Se escribe un JSON individual (auditable) y se añade una línea al
    historial JSONL (append-only) para reconstrucción temporal.
    """
    os.makedirs(output_folder, exist_ok=True)
    if df is None:
        df = (pd.read_parquet(data_file) if data_file.endswith(".parquet")
              else pd.read_csv(data_file))
    date_col = "date" if "date" in df.columns else None
    ticker_col = next((c for c in ("ticker", "symbol") if c in df.columns), None)

    meta = {
        "fuente": source,
        "fichero": os.path.abspath(data_file),
        "sha256": sha256_file(data_file),
        "timestamp_descarga": pd.Timestamp.utcnow().isoformat(),
        "rango_fechas": [str(df[date_col].min()), str(df[date_col].max())] if date_col else None,
        "n_filas": int(len(df)),
        "n_tickers": int(df[ticker_col].nunique()) if ticker_col else None,
        "parametros_scanner": scanner_params,
    }
    stem = os.path.splitext(os.path.basename(data_file))[0]
    meta_path = os.path.join(output_folder,
                             f"meta_{stem}_{pd.Timestamp.utcnow():%Y%m%d_%H%M%S}.json")
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)
    with open(os.path.join(output_folder, HISTORY_FILE), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(meta, ensure_ascii=False) + "\n")
    return meta_path, meta


def load_metadata_history(output_folder):
    """Lee el historial completo de descargas (lista de dicts, orden temporal)."""
    path = os.path.join(output_folder, HISTORY_FILE)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def data_available_at(history, as_of):
    """Metadatos de descargas ya realizadas en el instante `as_of`:
    reconstrucción de 'qué sabíamos entonces'."""
    as_of = pd.Timestamp(as_of)
    if as_of.tzinfo is None:
        as_of = as_of.tz_localize("UTC")
    return [m for m in history
            if pd.Timestamp(m["timestamp_descarga"]) <= as_of]


def audit_trade(trade, df, violations, history=None, contract=None):
    """Audita una operación simulada. `trade` debe contener:
        ticker, decision_time (ISO, momento en que la estrategia decidió),
        y opcionalmente entry_time.

    Verifica tres condiciones y devuelve un dict con veredicto y detalle:
    1. Existían velas del ticker con timestamp <= decision_time (había datos).
    2. Ninguna vela usada tiene downloaded_at > decision_time (los datos ya
       estaban descargados: sin look-ahead de infraestructura).
    3. El (ticker, día) de la decisión no tiene violaciones CRITICAL.
    """
    from .contract import DEFAULT_CONTRACT
    contract = contract or DEFAULT_CONTRACT
    ticker = trade["ticker"]
    decision = pd.Timestamp(trade["decision_time"])
    if decision.tzinfo is None:
        decision = decision.tz_localize("UTC")

    issues = []

    bars = df[(df["ticker"] == ticker) & (df["timestamp"] <= decision)]
    if bars.empty:
        issues.append("Sin ninguna vela del ticker anterior a decision_time: "
                      "la decisión no pudo basarse en estos datos.")
    else:
        col = contract["download_ts_column"]
        if col in bars.columns:
            late = bars[bars[col].isna() | (bars[col] > decision)]
            if len(late):
                issues.append(
                    f"{len(late)} velas usadas se descargaron DESPUÉS de la "
                    f"decisión (o sin downloaded_at): look-ahead de infraestructura.")
        else:
            issues.append(f"Columna '{col}' ausente: disponibilidad no verificable.")

    day = decision.tz_convert(contract["market_timezone"]).strftime("%Y-%m-%d")
    crit = [v for v in violations
            if v["severity"] == "CRITICAL"
            and v["ticker"] in (ticker, "*") and v["date"] == day]
    if crit:
        issues.append(f"{len(crit)} violaciones CRITICAL en ({ticker}, {day}): "
                      + "; ".join(v["check_type"] for v in crit[:5]))

    if history is not None:
        available = data_available_at(history, decision)
        if not available:
            issues.append("Ninguna descarga registrada en el historial es "
                          "anterior a decision_time.")

    return {
        "trade": {k: str(v) for k, v in trade.items()},
        "veredicto": "APTO" if not issues else "NO APTO",
        "problemas": issues,
        "n_velas_disponibles": int(len(bars)),
    }
