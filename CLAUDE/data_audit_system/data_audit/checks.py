# -*- coding: utf-8 -*-
"""
MÓDULO 2: CHECKS DE INTEGRIDAD (DATA QUALITY CHECKS)

Cada check es una función independiente y testeable que recibe el DataFrame
normalizado (ver pipeline.load_data_folder) y el contrato, y devuelve una
lista de violaciones con el formato:

    {"ticker": str, "date": str, "check_type": str,
     "severity": "CRITICAL"|"WARNING"|"INFO", "detail": str}

El DataFrame normalizado garantiza columnas:
    ticker (str), timestamp (datetime64 UTC), date (str YYYY-MM-DD, sesión ET),
    open/high/low/close (float), volume (float), downloaded_at (datetime64 UTC o NaT)
"""

import numpy as np
import pandas as pd


def make_violation(ticker, date, check_type, severity, detail):
    """Constructor único de violaciones: garantiza el formato exacto."""
    return {
        "ticker": str(ticker),
        "date": str(date),
        "check_type": check_type,
        "severity": severity,
        "detail": detail,
    }


def get_market_sessions(start_date, end_date, contract):
    """Sesiones reales del calendario NYSE/NASDAQ entre dos fechas (lista de str)."""
    import pandas_market_calendars as mcal
    cal = mcal.get_calendar(contract["calendar"])
    schedule = cal.schedule(start_date=start_date, end_date=end_date)
    return [d.strftime("%Y-%m-%d") for d in schedule.index]


# ---------------------------------------------------------------------------
# CHECK 1: Días de mercado faltantes por ticker
# ---------------------------------------------------------------------------
def check_missing_market_days(df, contract, sessions=None):
    """Compara los días con datos de cada ticker contra el calendario real.

    Solo se evalúa el rango [primer día, último día] de cada ticker: que un
    ticker no exista antes de su IPO o después de su delisting no es un hueco.
    Severidad WARNING: en small caps un día entero sin velas puede ser un halt
    de jornada completa, pero lo normal es que sea descarga incompleta.
    """
    violations = []
    if sessions is None:
        sessions = get_market_sessions(df["date"].min(), df["date"].max(), contract)
    sessions_idx = pd.Index(sessions)

    for ticker, grp in df.groupby("ticker"):
        have = set(grp["date"].unique())
        first, last = min(have), max(have)
        expected = sessions_idx[(sessions_idx >= first) & (sessions_idx <= last)]
        missing = [d for d in expected if d not in have]
        for d in missing:
            violations.append(make_violation(
                ticker, d, "missing_data", "WARNING",
                f"Día de mercado sin ninguna vela (rango del ticker: {first}..{last}). "
                f"Posible descarga incompleta o halt de jornada completa."))
    return violations


# ---------------------------------------------------------------------------
# CHECK 2: Velas faltantes dentro del día
# ---------------------------------------------------------------------------
def check_missing_intraday_bars(df, contract):
    """Cuenta velas por ticker-día y compara contra el mínimo del contrato.

    En 1-min de small caps, minutos sin trades no generan vela: cobertura baja
    es un WARNING de liquidez (el dato puede ser correcto pero el ticker no es
    operable con fiabilidad), no un error de integridad.
    """
    violations = []
    counts = df.groupby(["ticker", "date"]).size()
    for (ticker, date), n in counts.items():
        if n < contract["min_bars_day"]:
            severity = "WARNING" if n >= contract["min_bars_day"] // 3 else "CRITICAL"
            violations.append(make_violation(
                ticker, date, "missing_bars", severity,
                f"Solo {n} velas 1-min en el día (mínimo contrato: "
                f"{contract['min_bars_day']}, ideal RTH: {contract['ideal_bars_day']}). "
                f"Cobertura insuficiente para validar hipótesis intradía."))
    return violations


# ---------------------------------------------------------------------------
# CHECK 3: Volumen 0 / negativo / NaN + volumen diario mínimo
# ---------------------------------------------------------------------------
def check_volume_anomalies(df, contract):
    """Volumen NaN o negativo = CRITICAL (dato corrupto).
    Volumen 0 en muchas velas = INFO agregado (normal en ilíquidos, pero si la
    fuente rellena minutos vacíos con vol=0 hay que saberlo).
    Volumen total diario < mínimo = WARNING (ticker no operable ese día)."""
    violations = []

    bad = df[df["volume"].isna() | (df["volume"] < 0)]
    for (ticker, date), grp in bad.groupby(["ticker", "date"]):
        violations.append(make_violation(
            ticker, date, "volume_invalid", "CRITICAL",
            f"{len(grp)} velas con volumen NaN o negativo."))

    zeros = df[df["volume"] == 0]
    for (ticker, date), grp in zeros.groupby(["ticker", "date"]):
        violations.append(make_violation(
            ticker, date, "volume_zero", "INFO",
            f"{len(grp)} velas con volumen = 0 (posible relleno sintético de la fuente)."))

    daily_vol = df.groupby(["ticker", "date"])["volume"].sum()
    for (ticker, date), total in daily_vol.items():
        if total < contract["min_daily_volume"]:
            violations.append(make_violation(
                ticker, date, "volume_below_min", "WARNING",
                f"Volumen total del día = {total:,.0f} < mínimo del contrato "
                f"({contract['min_daily_volume']:,}). Ticker ilíquido, no apto para backtest."))
    return violations


# ---------------------------------------------------------------------------
# CHECK 4: OHLC inválido
# ---------------------------------------------------------------------------
def check_ohlc_integrity(df, contract):
    """high < low, o close/open fuera de [low, high] más allá de la tolerancia."""
    violations = []
    tol = contract["ohlc_tolerance_pct"] / 100.0

    hl = df[df["high"] < df["low"]]
    for (ticker, date), grp in hl.groupby(["ticker", "date"]):
        worst = (grp["low"] - grp["high"]).max()
        violations.append(make_violation(
            ticker, date, "ohlc_invalid", "CRITICAL",
            f"{len(grp)} velas con high < low (peor caso: low-high = {worst:.4f})."))

    # close u open fuera de rango con tolerancia relativa sobre el propio precio.
    lo_band = df["low"] * (1 - tol)
    hi_band = df["high"] * (1 + tol)
    out = df[(df["close"] < lo_band) | (df["close"] > hi_band)
             | (df["open"] < lo_band) | (df["open"] > hi_band)]
    # Excluir las que ya cayeron en high<low para no duplicar.
    out = out[out["high"] >= out["low"]]
    for (ticker, date), grp in out.groupby(["ticker", "date"]):
        violations.append(make_violation(
            ticker, date, "ohlc_out_of_range", "CRITICAL",
            f"{len(grp)} velas con open/close fuera de [low, high] "
            f"(tolerancia {contract['ohlc_tolerance_pct']}%)."))
    return violations


# ---------------------------------------------------------------------------
# CHECK 5: Precio 0 o NaN
# ---------------------------------------------------------------------------
def check_price_anomalies(df, contract):
    """Cualquier campo de precio <= 0 o NaN invalida la vela."""
    violations = []
    price_cols = ["open", "high", "low", "close"]
    bad = df[df[price_cols].isna().any(axis=1) | (df[price_cols] <= 0).any(axis=1)]
    for (ticker, date), grp in bad.groupby(["ticker", "date"]):
        violations.append(make_violation(
            ticker, date, "price_invalid", "CRITICAL",
            f"{len(grp)} velas con precio 0, negativo o NaN."))
    return violations


# ---------------------------------------------------------------------------
# CHECK 6: Saltos de precio sin volumen acorde (split no ajustado / corrupto)
# ---------------------------------------------------------------------------
def check_price_jumps(df, contract):
    """Dos casos:
    a) Salto intradía > max_single_bar_jump_pct entre velas consecutivas del
       mismo día con volumen < jump_volume_ratio * mediana del día -> WARNING.
       (Un pump real con volumen NO se marca: es exactamente el setup buscado.)
    b) Gap overnight > max_overnight_gap_pct sin volumen que lo confirme ->
       CRITICAL (patrón típico de split/reverse-split no ajustado).
    """
    violations = []
    jump_th = contract["max_single_bar_jump_pct"] / 100.0
    gap_th = contract["max_overnight_gap_pct"] / 100.0

    df = df.sort_values(["ticker", "timestamp"])
    for ticker, grp in df.groupby("ticker"):
        med_vol = grp.groupby("date")["volume"].transform("median").replace(0, np.nan)
        prev_close = grp["close"].shift(1)
        same_day = grp["date"] == grp["date"].shift(1)

        # a) Saltos intradía sospechosos
        ret = (grp["close"] / prev_close - 1).abs()
        suspicious = same_day & (ret > jump_th) & (
            grp["volume"] < contract["jump_volume_ratio"] * med_vol)
        for (date,), sub in grp[suspicious].groupby(["date"]):
            worst = ret[sub.index].max()
            violations.append(make_violation(
                ticker, date, "price_jump_no_volume", "WARNING",
                f"{len(sub)} saltos intradía > {contract['max_single_bar_jump_pct']}% "
                f"sin volumen acorde (peor: {worst*100:.1f}%). "
                f"Posible dato corrupto o split intradía."))

        # b) Gaps overnight sospechosos (primera vela del día vs último close previo)
        firsts = grp.groupby("date").first()
        prev_last_close = grp.groupby("date")["close"].last().shift(1)
        gap = (firsts["open"] / prev_last_close - 1).abs()
        day_vol = grp.groupby("date")["volume"].sum()
        median_day_vol = day_vol.rolling(20, min_periods=3).median()
        for date in gap.index:
            if pd.isna(gap[date]) or gap[date] <= gap_th:
                continue
            confirm = median_day_vol.get(date)
            if pd.notna(confirm) and day_vol[date] >= \
                    contract["gap_volume_confirm_ratio"] * confirm:
                continue  # gap real confirmado por volumen: setup legítimo
            violations.append(make_violation(
                ticker, date, "overnight_gap_suspect", "CRITICAL",
                f"Gap overnight de {gap[date]*100:.1f}% "
                f"(> {contract['max_overnight_gap_pct']}%) sin volumen que lo confirme "
                f"(vol día = {day_vol[date]:,.0f}). Posible split no ajustado."))
    return violations


# ---------------------------------------------------------------------------
# CHECK 6b: Velas congeladas (precio sin cambio demasiado tiempo)
# ---------------------------------------------------------------------------
def check_frozen_candles(df, contract):
    """Rachas de más de max_flat_candles velas consecutivas con OHLC idéntico.
    Con volumen > 0 es dato congelado (CRITICAL); con volumen = 0 suele ser
    relleno sintético o halt (WARNING, cruzar con calendario de halts)."""
    violations = []
    max_flat = contract["max_flat_candles"]
    df = df.sort_values(["ticker", "timestamp"])
    for (ticker, date), grp in df.groupby(["ticker", "date"]):
        same = ((grp["open"] == grp["open"].shift(1))
                & (grp["high"] == grp["high"].shift(1))
                & (grp["low"] == grp["low"].shift(1))
                & (grp["close"] == grp["close"].shift(1)))
        # Longitud de cada racha de velas idénticas consecutivas.
        run_id = (~same).cumsum()
        run_lengths = same.groupby(run_id).sum() + 1
        for rid, length in run_lengths.items():
            if length <= max_flat:
                continue
            run_rows = grp[run_id == rid]
            with_vol = (run_rows["volume"] > 0).any()
            severity = "CRITICAL" if with_vol else "WARNING"
            kind = "dato congelado (hay volumen pero el precio no se mueve)" \
                if with_vol else "posible halt o relleno sintético (volumen 0)"
            violations.append(make_violation(
                ticker, date, "frozen_candles", severity,
                f"Racha de {int(length)} velas 1-min sin cambio de precio "
                f"(máximo contrato: {max_flat}): {kind}."))
    return violations


# ---------------------------------------------------------------------------
# CHECK 7: Timestamps duplicados
# ---------------------------------------------------------------------------
def check_duplicate_timestamps(df, contract):
    """Más de una vela para el mismo (ticker, minuto)."""
    violations = []
    dup = df[df.duplicated(subset=["ticker", "timestamp"], keep=False)]
    for (ticker, date), grp in dup.groupby(["ticker", "date"]):
        n_dup_minutes = grp["timestamp"].nunique()
        violations.append(make_violation(
            ticker, date, "duplicate_timestamp", "CRITICAL",
            f"{n_dup_minutes} minutos con velas duplicadas ({len(grp)} filas). "
            f"Riesgo de doble conteo de volumen/señales."))
    return violations


# ---------------------------------------------------------------------------
# CHECK 8: Desapariciones sin delisting conocido
# ---------------------------------------------------------------------------
def check_ticker_disappearance(df, contract, delistings=None, sessions=None):
    """Tickers cuyo último día con datos es anterior al fin del dataset sin
    delisting conocido que lo explique: posible error de descarga o cambio de
    símbolo. `delistings` es un dict {ticker: fecha_delisting 'YYYY-MM-DD'}."""
    violations = []
    delistings = delistings or {}
    if sessions is None:
        sessions = get_market_sessions(df["date"].min(), df["date"].max(), contract)
    grace = contract["disappearance_grace_days"]
    cutoff = sessions[-(grace + 1)] if len(sessions) > grace else sessions[0]

    last_seen = df.groupby("ticker")["date"].max()
    for ticker, last in last_seen.items():
        if last >= cutoff:
            continue  # sigue presente al final del dataset (con margen)
        delist = delistings.get(ticker)
        if delist and delist <= sessions[-1]:
            if last < delist:
                # Desaparece ANTES de su delisting: faltan datos reales.
                n_missing = len([s for s in sessions if last < s < delist])
                if n_missing > 0:
                    violations.append(make_violation(
                        ticker, last, "missing_pre_delisting", "WARNING",
                        f"Último dato {last} pero delisting conocido {delist}: "
                        f"faltan ~{n_missing} sesiones previas al delisting."))
            continue  # delisting explica la desaparición
        violations.append(make_violation(
            ticker, last, "survivorship", "WARNING",
            f"Ticker desaparece tras {last} sin delisting conocido "
            f"(dataset llega hasta {sessions[-1]}). Posible error de descarga "
            f"o cambio de símbolo."))
    return violations


# ---------------------------------------------------------------------------
# CHECK 9: Universo mínimo por día
# ---------------------------------------------------------------------------
def check_universe_size(df, contract):
    """Días con menos tickers que el mínimo del contrato: el día no es
    representativo del universo y no debe usarse para validar hipótesis."""
    violations = []
    per_day = df.groupby("date")["ticker"].nunique()
    for date, n in per_day.items():
        if n < contract["min_tickers_per_day"]:
            violations.append(make_violation(
                "*", date, "universe_too_small", "WARNING",
                f"Solo {n} tickers con datos "
                f"(mínimo contrato: {contract['min_tickers_per_day']}). "
                f"Día no representativo del universo."))
    return violations


# Registro de todos los checks de integridad para el pipeline.
ALL_INTEGRITY_CHECKS = [
    check_missing_market_days,
    check_missing_intraday_bars,
    check_volume_anomalies,
    check_ohlc_integrity,
    check_price_anomalies,
    check_price_jumps,
    check_frozen_candles,
    check_duplicate_timestamps,
    check_universe_size,
]
