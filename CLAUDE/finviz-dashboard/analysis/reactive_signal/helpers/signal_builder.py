"""
signal_builder.py — Construye eventos de señal a partir de los snapshots de Finviz.

Un evento de señal es una fila (ticker, día, timestamp) que cumple las condiciones
configuradas (change_pct >= threshold, etc.).  El notebook puede filtrar o agregar
condiciones adicionales sobre el DataFrame resultante.
"""

import pandas as pd

SESSION_BINS = [
    (float('-inf'), 0,   'pre-market'),
    (0,             30,  '9:30-10:00'),
    (30,            90,  '10:00-11:00'),
    (90,            210, '11:00-13:00'),
    (210,           330, '13:00-15:00'),
    (330,           float('inf'), '15:00-16:00'),
]


def _session_label(mso: float) -> str:
    for lo, hi, label in SESSION_BINS:
        if lo <= mso < hi:
            return label
    return 'post-market'


def build_signal_events(
    snaps: pd.DataFrame,
    min_change_pct: float = 15.0,
    one_per_ticker_day: bool = False,
) -> pd.DataFrame:
    """
    Dado el DataFrame de snapshots (de data_loader.load_snapshots),
    construye un DataFrame de eventos de señal con features calculados.

    Parámetros
    ----------
    snaps : DataFrame retornado por load_snapshots (sin filtro de min_change_pct)
    min_change_pct : umbral mínimo de change_pct para considerar el ticker
    one_per_ticker_day : si True, retiene solo el PRIMER evento por (ticker, date).
        Usar para análisis donde la independencia entre observaciones es necesaria
        (tests estadísticos, segmentaciones con n pequeño).
        Si False (default), retiene todos los snapshots — útil para estudiar la
        trayectoria intradiaria y el comportamiento por appearance_n.

    Returns
    -------
    DataFrame con columnas adicionales:
        appearance_n      : n-ésima aparición del ticker ese día (1 = primera)
        session           : bucket de sesión ('9:30-10:00', '10:00-11:00', ...)
        prev_change_pct   : change_pct del snapshot anterior del mismo ticker-día
        chg_delta         : cambio entre snapshots consecutivos
        momentum_dir      : 'first_appearance' | 'accelerating' | 'decelerating' | 'flat'

    Nota sobre independencia
    ------------------------
    Con one_per_ticker_day=False, múltiples snapshots del mismo ticker-día están
    correlacionados: el return a T+30m del snapshot #3 de HUBC no es independiente
    del return del snapshot #4.  Esto infla los grados de libertad y puede hacer
    que resultados sin edge parezcan significativos.
    Recomendación: usar one_per_ticker_day=True para la validación estadística
    y one_per_ticker_day=False para exploración de patrones intradiarios.
    """
    df = snaps[snaps['change_pct'] >= min_change_pct].copy()
    df = df.sort_values(['ticker', 'date', 'ts']).reset_index(drop=True)

    # Orden de aparición dentro del día
    df['appearance_n'] = df.groupby(['ticker', 'date']).cumcount() + 1

    # Sesión
    df['session'] = df['minutes_since_open'].apply(_session_label)

    # Delta de change_pct entre snapshots consecutivos
    df['prev_change_pct'] = df.groupby(['ticker', 'date'])['change_pct'].shift(1)
    df['chg_delta'] = df['change_pct'] - df['prev_change_pct']

    def _momentum_dir(row):
        if pd.isna(row['chg_delta']):
            return 'first_appearance'
        if row['chg_delta'] > 0.5:
            return 'accelerating'
        if row['chg_delta'] < -0.5:
            return 'decelerating'
        return 'flat'

    df['momentum_dir'] = df.apply(_momentum_dir, axis=1)

    if one_per_ticker_day:
        df = df[df['appearance_n'] == 1].copy()

    return df.reset_index(drop=True)
