# -*- coding: utf-8 -*-
"""
MÓDULO 3: DETECCIÓN DE SESGOS OCULTOS

3.1 Look-ahead bias   : downloaded_at vs fecha del dato + replay temporal.
3.2 Survivorship bias : universo observado vs universo histórico de referencia.
3.3 Scanner-changing  : deriva del universo del scanner entre snapshots.

Todas las funciones devuelven violaciones con el mismo formato del Módulo 2.
"""

import json

import pandas as pd

from .checks import make_violation, check_ticker_disappearance


# ---------------------------------------------------------------------------
# 3.1 LOOK-AHEAD BIAS
# ---------------------------------------------------------------------------
def check_look_ahead(df, contract):
    """Verifica la coherencia temporal de la descarga:
    - downloaded_at ausente/NaT -> CRITICAL (sin trazabilidad no hay auditoría).
    - downloaded_at ANTERIOR al timestamp del dato -> CRITICAL: el dato dice
      haberse descargado antes de existir. O el reloj está mal o alguien
      reconstruyó el dataset a posteriori (look-ahead potencial).
    """
    violations = []
    col = contract["download_ts_column"]

    if col not in df.columns:
        violations.append(make_violation(
            "*", str(df["date"].min()), "look_ahead", "CRITICAL",
            f"Columna '{col}' ausente en todo el dataset: imposible verificar "
            f"disponibilidad temporal de los datos."))
        return violations

    missing = df[df[col].isna()]
    for ticker, grp in missing.groupby("ticker"):
        violations.append(make_violation(
            ticker, grp["date"].min(), "look_ahead", "CRITICAL",
            f"{len(grp)} filas sin '{col}': sin trazabilidad de descarga."))

    # downloaded_at debe ser >= timestamp del dato.
    bad = df[df[col].notna() & (df[col] < df["timestamp"])]
    for (ticker, date), grp in bad.groupby(["ticker", "date"]):
        worst = (grp["timestamp"] - grp[col]).max()
        violations.append(make_violation(
            ticker, date, "look_ahead", "CRITICAL",
            f"{len(grp)} filas con downloaded_at anterior al dato "
            f"(peor caso: {worst}). Posible look-ahead o reloj corrupto."))
    return violations


class PointInTimeView:
    """Vista point-in-time de los datos para el test de replay temporal.

    La estrategia solo puede pedir datos a través de esta vista. Cualquier
    acceso a timestamps posteriores a `as_of` queda registrado como violación
    de look-ahead (no se lanza excepción: queremos el inventario completo).
    """

    def __init__(self, df, as_of):
        self._df = df
        self.as_of = pd.Timestamp(as_of)
        if self.as_of.tzinfo is None:
            self.as_of = self.as_of.tz_localize("UTC")
        self.violations = []  # accesos fuera de la ventana temporal

    def get_bars(self, ticker, start=None, end=None):
        """Devuelve las velas del ticker RECORTADAS a as_of.

        Si el llamante pidió explícitamente datos futuros (end > as_of),
        se registra la petición: la estrategia está escrita con look-ahead.
        """
        if end is not None:
            end_ts = pd.Timestamp(end)
            if end_ts.tzinfo is None:
                end_ts = end_ts.tz_localize("UTC")
            if end_ts > self.as_of:
                self.violations.append(make_violation(
                    ticker, self.as_of.date(), "look_ahead_replay", "CRITICAL",
                    f"La estrategia pidió datos hasta {end_ts} con as_of={self.as_of}: "
                    f"acceso a información futura."))
        sub = self._df[(self._df["ticker"] == ticker)
                       & (self._df["timestamp"] <= self.as_of)]
        if start is not None:
            start_ts = pd.Timestamp(start)
            if start_ts.tzinfo is None:
                start_ts = start_ts.tz_localize("UTC")
            sub = sub[sub["timestamp"] >= start_ts]
        return sub.copy()

    def universe(self):
        """Tickers con datos disponibles hasta as_of."""
        return sorted(self._df.loc[self._df["timestamp"] <= self.as_of, "ticker"].unique())


def run_temporal_replay(df, strategy_fn, contract, sessions=None):
    """Test de replay temporal (3.1): ejecuta `strategy_fn(view, date)` para
    cada sesión D con una vista que solo contiene datos hasta el CIERRE de D-1
    (20:00 ET del día previo, fin de afterhours).

    `strategy_fn` es cualquier callable del usuario que tome (view, date_str).
    Devuelve la lista de violaciones de look-ahead detectadas en los accesos.
    """
    from .checks import get_market_sessions
    if sessions is None:
        sessions = get_market_sessions(df["date"].min(), df["date"].max(), contract)

    violations = []
    tz = contract["market_timezone"]
    for i, date in enumerate(sessions):
        if i == 0:
            continue  # el primer día no tiene D-1 dentro del dataset
        prev = sessions[i - 1]
        # Cierre de la sesión extendida de D-1 en ET, convertido a UTC.
        as_of = (pd.Timestamp(f"{prev} {contract['session_end']}")
                 .tz_localize(tz).tz_convert("UTC"))
        view = PointInTimeView(df, as_of)
        try:
            strategy_fn(view, date)
        except Exception as exc:  # la estrategia no debe romper el audit
            violations.append(make_violation(
                "*", date, "replay_error", "WARNING",
                f"strategy_fn lanzó excepción en el replay de {date}: {exc!r}"))
        violations.extend(view.violations)
    return violations


# ---------------------------------------------------------------------------
# 3.2 SURVIVORSHIP BIAS
# ---------------------------------------------------------------------------
def check_survivorship(df, contract, reference_csv=None, sessions=None):
    """Compara el universo observado contra una referencia histórica.

    `reference_csv` debe tener columnas: ticker, list_date, delist_date
    (delist_date vacío = sigue cotizando). Detecta:
    - Tickers de la referencia que cotizaban en el periodo pero NO aparecen en
      los datos -> survivorship clásico (los muertos no están).
    - Tickers que desaparecen antes de su delisting conocido (delegado en
      check_ticker_disappearance).
    - Tickers huérfanos: aparecen solo tras el inicio del dataset sin
      list_date que lo justifique (inclusión tardía que infla rendimientos).
    """
    from .checks import get_market_sessions
    violations = []
    if sessions is None:
        sessions = get_market_sessions(df["date"].min(), df["date"].max(), contract)
    data_start, data_end = sessions[0], sessions[-1]
    observed = set(df["ticker"].unique())

    delistings = {}
    if reference_csv:
        ref = pd.read_csv(reference_csv, dtype=str).fillna("")
        for _, row in ref.iterrows():
            if row.get("delist_date"):
                delistings[row["ticker"]] = row["delist_date"]

        # Tickers que existían en el periodo y no están en los datos.
        for _, row in ref.iterrows():
            t = row["ticker"]
            listed = row.get("list_date") or "1900-01-01"
            delisted = row.get("delist_date") or "9999-12-31"
            overlaps = listed <= data_end and delisted >= data_start
            if overlaps and t not in observed:
                violations.append(make_violation(
                    t, data_start, "survivorship", "WARNING",
                    f"Ticker en la referencia histórica (listado {listed}, "
                    f"delisting {row.get('delist_date') or 'activo'}) ausente del "
                    f"dataset: posible universo solo-supervivientes."))

        # Huérfanos: primera aparición tardía sin list_date que la explique.
        ref_list_dates = dict(zip(ref["ticker"], ref["list_date"]))
        first_seen = df.groupby("ticker")["date"].min()
        for t, first in first_seen.items():
            if first <= data_start:
                continue
            list_date = ref_list_dates.get(t, "")
            if not list_date or list_date < data_start:
                violations.append(make_violation(
                    t, first, "orphan_ticker", "WARNING",
                    f"Ticker aparece por primera vez el {first} (dataset empieza "
                    f"{data_start}) sin IPO/listing que lo explique: posible "
                    f"inclusión tardía (infla rendimientos del universo)."))

    # Desapariciones sin delisting (usa la referencia si existe).
    violations.extend(check_ticker_disappearance(df, contract, delistings, sessions))
    return violations


# ---------------------------------------------------------------------------
# 3.3 SCANNER CHANGING BIAS
# ---------------------------------------------------------------------------
def load_scanner_log(path):
    """Carga snapshots del scanner desde JSON o JSONL.
    Formato por snapshot: {"fecha": "YYYY-MM-DD", "parametros": {...},
                           "lista_tickers_devueltos": [...]}."""
    snapshots = []
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read().strip()
    if text.startswith("["):
        snapshots = json.loads(text)
    else:
        snapshots = [json.loads(line) for line in text.splitlines() if line.strip()]
    return sorted(snapshots, key=lambda s: s["fecha"])


def check_scanner_universe_shift(snapshots, contract):
    """Compara universos entre snapshots adyacentes del scanner.

    - Cambio de universo (1 - Jaccard) > umbral SIN cambio de parámetros
      -> WARNING (la fuente/scanner derivó silenciosamente).
    - Cambio de parámetros -> INFO de punto de quiebre: el backtest debe
      separarse en regímenes en ese punto.

    Devuelve (violaciones, regímenes) donde regímenes es una lista de
    (fecha_inicio, fecha_fin, parametros) para trocear el backtest.
    """
    violations = []
    regimes = []
    if not snapshots:
        return violations, regimes

    regime_start = snapshots[0]["fecha"]
    for prev, curr in zip(snapshots, snapshots[1:]):
        params_changed = prev.get("parametros") != curr.get("parametros")
        a = set(prev.get("lista_tickers_devueltos", []))
        b = set(curr.get("lista_tickers_devueltos", []))
        union = a | b
        shift = 1 - (len(a & b) / len(union)) if union else 0.0

        if params_changed:
            regimes.append((regime_start, prev["fecha"], prev.get("parametros")))
            regime_start = curr["fecha"]
            violations.append(make_violation(
                "*", curr["fecha"], "scanner_params_changed", "INFO",
                f"Parámetros del scanner cambiaron el {curr['fecha']}: punto de "
                f"quiebre de régimen. Backtest debe evaluarse por separado antes "
                f"y después. Antes: {prev.get('parametros')} | "
                f"Después: {curr.get('parametros')}"))
        elif shift > contract["scanner_max_universe_shift"]:
            violations.append(make_violation(
                "*", curr["fecha"], "scanner_universe_shift", "WARNING",
                f"Universo del scanner cambió {shift*100:.0f}% entre "
                f"{prev['fecha']} y {curr['fecha']} sin cambio de parámetros "
                f"(umbral: {contract['scanner_max_universe_shift']*100:.0f}%). "
                f"Posible fallo de la fuente o deriva silenciosa."))

    regimes.append((regime_start, snapshots[-1]["fecha"],
                    snapshots[-1].get("parametros")))
    return violations, regimes
