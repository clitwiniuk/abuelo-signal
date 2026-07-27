"""
forward_returns.py — Calcula forward returns desde eventos de señal usando barras 1-min.

Uso típico:
    idx = BarsIndex(bars_df)
    results = compute_forward_returns(signal_events_df, idx, horizons=[15, 30, 60, 120])
"""

import pandas as pd
import numpy as np
from typing import Optional


class BarsIndex:
    """
    Índice pre-construido de barras 1-min por (ticker, date) para búsqueda O(log n).
    Construirlo una vez y reutilizarlo para todos los eventos.
    """

    def __init__(self, bars: pd.DataFrame):
        """
        Parameters
        ----------
        bars : DataFrame de load_intraday_bars — debe tener columnas
               ticker, date, bar_ts, open, high, low, close, volume
        """
        self._idx: dict[tuple, pd.DataFrame] = {}
        for (ticker, date), grp in bars.groupby(['ticker', 'date']):
            self._idx[(ticker, str(date))] = grp.sort_values('bar_ts').reset_index(drop=True)

    def get(self, ticker: str, date: str) -> Optional[pd.DataFrame]:
        return self._idx.get((ticker, str(date)))

    @property
    def available_keys(self) -> set:
        return set(self._idx.keys())


def _forward_return_single(
    ticker: str,
    date: str,
    signal_ts: pd.Timestamp,
    horizon_min: int,
    bars_index: BarsIndex,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Retorna (return, mfe, mae) para un evento dado.

    - Entrada : open del primer bar DESPUÉS de signal_ts
    - Salida  : close del bar más cercano a entry_ts + horizon_min
    - MFE/MAE : calculados sobre la ventana [entry_ts, exit_ts]
    """
    day_bars = bars_index.get(ticker, date)
    if day_bars is None:
        return None, None, None

    # Bar de entrada: primero estrictamente después del timestamp de señal
    entry_candidates = day_bars[day_bars['bar_ts'] > signal_ts]
    if len(entry_candidates) == 0:
        return None, None, None

    entry_bar   = entry_candidates.iloc[0]
    entry_price = entry_bar['open']
    entry_ts    = entry_bar['bar_ts']

    if entry_price <= 0:
        return None, None, None

    # Bar de salida
    exit_target = entry_ts + pd.Timedelta(minutes=horizon_min)
    exit_candidates = day_bars[day_bars['bar_ts'] >= exit_target]
    exit_bar = exit_candidates.iloc[0] if len(exit_candidates) > 0 else day_bars.iloc[-1]
    exit_price = exit_bar['close']

    ret = (exit_price - entry_price) / entry_price

    # MFE / MAE sobre la ventana
    window = day_bars[
        (day_bars['bar_ts'] >= entry_ts) & (day_bars['bar_ts'] <= exit_bar['bar_ts'])
    ]
    if len(window) == 0:
        return ret, None, None

    mfe = (window['high'].max()  - entry_price) / entry_price
    mae = (window['low'].min()   - entry_price) / entry_price

    return ret, mfe, mae


def compute_forward_returns(
    events: pd.DataFrame,
    bars_index: BarsIndex,
    horizons: list[int] = (15, 30, 60, 120),
) -> pd.DataFrame:
    """
    Calcula forward returns para todos los eventos de señal.

    Parameters
    ----------
    events      : DataFrame de build_signal_events — debe tener ticker, date, ts (signal_ts)
    bars_index  : BarsIndex construido con load_intraday_bars
    horizons    : lista de horizontes en minutos

    Returns
    -------
    DataFrame con las columnas originales de `events` más:
        ret_{h}m, mfe_{h}m, mae_{h}m  para cada horizonte h
        entry_price, entry_ts
    """
    records = []
    for _, row in events.iterrows():
        rec = row.to_dict()

        # Guardar el ts de señal con nombre explícito para no pisar columnas
        signal_ts = row['ts']

        # Entrada (calculada una vez, igual para todos los horizontes)
        day_bars = bars_index.get(row['ticker'], row['date'])
        if day_bars is not None:
            entry_candidates = day_bars[day_bars['bar_ts'] > signal_ts]
            if len(entry_candidates) > 0:
                rec['entry_price'] = entry_candidates.iloc[0]['open']
                rec['entry_ts']    = entry_candidates.iloc[0]['bar_ts']
            else:
                rec['entry_price'] = None
                rec['entry_ts']    = None
        else:
            rec['entry_price'] = None
            rec['entry_ts']    = None

        for h in horizons:
            ret, mfe, mae = _forward_return_single(
                row['ticker'], row['date'], signal_ts, h, bars_index
            )
            rec[f'ret_{h}m']  = ret
            rec[f'mfe_{h}m']  = mfe
            rec[f'mae_{h}m']  = mae

        records.append(rec)

    return pd.DataFrame(records)


def edge_summary(
    df: pd.DataFrame,
    horizons: list[int] = (15, 30, 60, 120),
    col_prefix: str = 'ret',
) -> pd.DataFrame:
    """
    Tabla resumen de WR, PF, avg_win, avg_loss, n para cada horizonte.

    Parameters
    ----------
    col_prefix : prefijo de las columnas de retorno.
        'ret'     → busca ret_15m, ret_30m, ...  (retornos brutos)
        'ret_net' → busca ret_net_15m, ...        (retornos netos de slippage)
    """
    rows = []
    for h in horizons:
        col = f'{col_prefix}_{h}m'
        if col not in df.columns:
            continue
        s = df[col].dropna()
        # Asegurar que es una Series 1D (evita problema de columnas duplicadas)
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        if len(s) == 0:
            continue
        wins   = s[s > 0]
        losses = s[s < 0]
        pf     = wins.sum() / abs(losses.sum()) if len(losses) > 0 else np.inf
        rows.append({
            'horizonte'  : f'T+{h}m',
            'n'          : len(s),
            'wr'         : (s > 0).mean(),
            'profit_factor': pf,
            'avg_ret_pct': s.mean() * 100,
            'avg_win_pct': wins.mean()  * 100 if len(wins) > 0 else 0,
            'avg_loss_pct': losses.mean() * 100 if len(losses) > 0 else 0,
            'median_ret_pct': s.median() * 100,
        })
    return pd.DataFrame(rows)
