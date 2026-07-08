# -*- coding: utf-8 -*-
"""
MÓDULO 6: PIPELINE PRINCIPAL

run_data_audit(data_folder, output_folder, ...) orquesta todo:
  carga (CSV/Parquet) -> normalización -> checks (M2) -> sesgos (M3)
  -> scoring e informe (M4) -> trazabilidad e historial (M5).

Diseñado para ejecutarse tras cada descarga nueva: cada ejecución añade una
entrada a audit_history.jsonl, de modo que se conserva el historial de
validaciones y se puede ver si la calidad de la fuente se degrada.
"""

import glob
import json
import os

import pandas as pd

from .contract import load_contract
from . import checks as C
from . import biases as B
from . import report as R
from . import traceability as T

AUDIT_HISTORY_FILE = "audit_history.jsonl"


# ---------------------------------------------------------------------------
# Carga y normalización
# ---------------------------------------------------------------------------
def _parse_timestamps(series, naive_tz):
    """Parsea timestamps mezclados (naive=ET legacy, aware=UTC) a UTC.
    Convención del proyecto: un timestamp sin timezone se asume hora de
    mercado (America/New_York); uno con timezone se respeta."""
    parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    if parsed.dtype == object:
        # Mezcla de aware y naive: localizar los naive uno a uno.
        parsed = parsed.map(
            lambda t: t if (pd.isna(t) or t.tzinfo is not None)
            else t.tz_localize(naive_tz))
        parsed = pd.to_datetime(parsed, utc=True)
    elif parsed.dt.tz is None:
        parsed = parsed.dt.tz_localize(naive_tz)
    return parsed.dt.tz_convert("UTC")


def normalize_dataframe(df, contract, source_file=None):
    """Normaliza un DataFrame crudo al esquema interno del auditor:
    ticker, timestamp (UTC), date (sesión ET), open/high/low/close/volume,
    downloaded_at (UTC o NaT). No modifica el fichero original."""
    df = df.rename(columns={k: v for k, v in contract["column_aliases"].items()
                            if k in df.columns})
    if source_file is not None:
        df["source_file"] = os.path.basename(source_file)

    # 'date' del CSV puede ser la fecha de sesión o venir ausente; el timestamp
    # manda. Si solo hay 'date' sin hora, se asume dato diario y se rechaza.
    if "timestamp" not in df.columns:
        raise ValueError(
            f"{source_file}: sin columna de timestamp intradía "
            f"(aceptadas: timestamp/dt/datetime/bar_timestamp). "
            f"Este auditor es para velas 1-min.")

    df["ticker"] = df["ticker"].astype(str)
    df["timestamp"] = _parse_timestamps(df["timestamp"], contract["naive_timezone"])
    # Fecha de sesión derivada SIEMPRE del timestamp en hora de mercado.
    df["date"] = (df["timestamp"].dt.tz_convert(contract["market_timezone"])
                  .dt.strftime("%Y-%m-%d"))
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    dcol = contract["download_ts_column"]
    if dcol in df.columns:
        df[dcol] = _parse_timestamps(df[dcol], "UTC")
    return df


def load_data_folder(data_folder, contract):
    """Carga todos los CSV/Parquet de la carpeta y devuelve un único DataFrame
    normalizado. Las filas cuyo timestamp no parsea se apartan (se reportan
    como violación en el pipeline)."""
    files = sorted(glob.glob(os.path.join(data_folder, "*.csv"))
                   + glob.glob(os.path.join(data_folder, "*.parquet")))
    if not files:
        raise FileNotFoundError(f"Sin CSV/Parquet en {data_folder}")
    frames = []
    for path in files:
        raw = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
        missing = [c for c in ("open", "high", "low", "close", "volume")
                   if c not in raw.columns
                   and c not in contract["column_aliases"].values()]
        if missing:
            raise ValueError(f"{path}: faltan columnas obligatorias {missing}")
        frames.append(normalize_dataframe(raw, contract, source_file=path))
    df = pd.concat(frames, ignore_index=True)
    unparseable = df["timestamp"].isna()
    return df[~unparseable].reset_index(drop=True), int(unparseable.sum()), files


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
def run_data_audit(data_folder, output_folder, contract_path=None,
                   scanner_log=None, reference_tickers_csv=None,
                   strategy_fn=None, source_name="unknown",
                   output_format="parquet", verbose=True):
    """Ejecuta la auditoría completa.

    Parámetros:
        data_folder          carpeta con CSV/Parquet de velas 1-min.
        output_folder        carpeta de salida (informes, datos limpios, historial).
        contract_path        YAML opcional que sobreescribe el contrato por defecto.
        scanner_log          JSON/JSONL con snapshots del scanner (Módulo 3.3).
        reference_tickers_csv CSV con universo histórico: ticker,list_date,delist_date.
        strategy_fn          callable(view, date) para el replay temporal (3.1).
        source_name          nombre de la fuente para los metadatos (M5).
        output_format        'parquet' o 'csv' para los datos limpios.

    Devuelve un dict con: summary, violations, scores_day, scores_ticker_day,
    clean_data_path, report_path, regimes.
    """
    contract = load_contract(contract_path)
    os.makedirs(output_folder, exist_ok=True)

    # --- Carga ---------------------------------------------------------
    df, n_unparseable, files = load_data_folder(data_folder, contract)
    violations = []
    if n_unparseable:
        violations.append(C.make_violation(
            "*", str(df["date"].min()) if len(df) else "?", "timestamp_unparseable",
            "CRITICAL", f"{n_unparseable} filas con timestamp no parseable, apartadas."))
    if df.empty:
        raise ValueError("Ningún dato utilizable tras la normalización.")

    sessions = C.get_market_sessions(df["date"].min(), df["date"].max(), contract)

    # --- M5: metadatos de la descarga -----------------------------------
    scanner_params = None
    snapshots = None
    if scanner_log:
        snapshots = B.load_scanner_log(scanner_log)
        scanner_params = snapshots[-1].get("parametros") if snapshots else None
    for path in files:
        T.create_download_metadata(path, source_name, output_folder,
                                   scanner_params=scanner_params)

    # --- M2: checks de integridad ----------------------------------------
    for check in C.ALL_INTEGRITY_CHECKS:
        if check in (C.check_missing_market_days,):
            violations.extend(check(df, contract, sessions=sessions))
        elif check is C.check_ticker_disappearance:
            continue  # se ejecuta dentro de check_survivorship (M3.2)
        else:
            violations.extend(check(df, contract))

    # --- M3: sesgos -------------------------------------------------------
    violations.extend(B.check_look_ahead(df, contract))
    violations.extend(B.check_survivorship(df, contract,
                                           reference_csv=reference_tickers_csv,
                                           sessions=sessions))
    regimes = None
    if snapshots:
        scanner_viols, regimes = B.check_scanner_universe_shift(snapshots, contract)
        violations.extend(scanner_viols)
    if strategy_fn is not None:
        violations.extend(B.run_temporal_replay(df, strategy_fn, contract,
                                                sessions=sessions))

    # --- M4: marcado, scoring, informes -----------------------------------
    valid_mask = R.flag_invalid_rows(df, contract)
    scores_td, scores_day = R.compute_scores(df, violations, contract)
    summary = R.build_summary(df, valid_mask, violations, scores_td,
                              scores_day, contract)

    viol_csv = os.path.join(output_folder, "violations.csv")
    R.export_violations_csv(violations, viol_csv)
    clean_path = R.save_clean_data(df, valid_mask, output_folder, fmt=output_format)
    report_path = os.path.join(output_folder, "data_health_report.html")
    R.generate_html_report(summary, scores_day, scores_td, violations,
                           contract, report_path, regimes=regimes)
    scores_day.to_csv(os.path.join(output_folder, "scores_by_day.csv"), index=False)
    scores_td.to_csv(os.path.join(output_folder, "scores_by_ticker_day.csv"),
                     index=False)

    # --- Historial de validaciones (una línea por ejecución) ---------------
    history_entry = {
        "run_at": pd.Timestamp.utcnow().isoformat(),
        "data_folder": os.path.abspath(data_folder),
        "n_filas": summary["n_filas"],
        "n_tickers": summary["n_tickers"],
        "pct_dias_validos": summary["pct_dias_validos"],
        "pct_tickers_validos": summary["pct_tickers_validos"],
        "pct_datos_descartados": summary["pct_datos_descartados"],
        "violaciones_por_severidad": summary["violaciones_por_severidad"],
    }
    with open(os.path.join(output_folder, AUDIT_HISTORY_FILE), "a",
              encoding="utf-8") as fh:
        fh.write(json.dumps(history_entry, ensure_ascii=False) + "\n")

    if verbose:
        R.print_summary(summary, scores_day, contract)
        print(f"Informe HTML : {report_path}")
        print(f"Violaciones  : {viol_csv}")
        print(f"Datos limpios: {clean_path}")

    return {
        "summary": summary,
        "violations": violations,
        "scores_day": scores_day,
        "scores_ticker_day": scores_td,
        "clean_data_path": clean_path,
        "report_path": report_path,
        "regimes": regimes,
        "df": df,
        "valid_mask": valid_mask,
    }
