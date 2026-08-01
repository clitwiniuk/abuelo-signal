import re
from pathlib import Path
import pandas as pd
import numpy as np


def parse_volume_to_number(vol_series: pd.Series) -> pd.Series:
    """Parse volumes like '162.91K', '3.2M', '1.1B', '0' into numeric floats."""
    vol_str = vol_series.astype(str).str.strip()
    mult = vol_str.str.extract(r'([KMB])$', expand=False)
    num = pd.to_numeric(vol_str.str.replace(r'[KMB]$', '', regex=True), errors='coerce')
    vol = num.copy()
    vol[mult == 'K'] = num[mult == 'K'] * 1e3
    vol[mult == 'M'] = num[mult == 'M'] * 1e6
    vol[mult == 'B'] = num[mult == 'B'] * 1e9
    return vol


def load_intraday_file(file_path: str | Path) -> pd.DataFrame:
    """Load a similar Finviz intraday snapshot file.

    Supports CSV (comma) and TSV (tab). Auto-detects delimiter.
    Expects columns: timestamp, category, ticker, price, change_pct, volume

    Returns a cleaned dataframe with:
    - timestamp parsed to UTC
    - price numeric
    - change_pct as float (e.g. 0.0123 for +1.23%)
    - volume numeric
    """
    fp = Path(file_path)
    if not fp.exists():
        raise FileNotFoundError(str(fp))

    # Auto-detect delimiter quickly
    sample = fp.read_text(encoding='utf-8', errors='replace')[:5000]
    sep = '	' if '	' in sample and sample.count('	') >= sample.count(',') else ','

    df = pd.read_csv(fp, sep=sep)

    # Normalize column names just in case
    df.columns = [str(c).strip() for c in df.columns]

    # Basic cleaning
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
    df['ticker'] = df['ticker'].astype(str).str.strip()
    df['category'] = df['category'].astype(str).str.strip()

    df['price'] = pd.to_numeric(df['price'], errors='coerce')

    ch = df['change_pct'].astype(str).str.strip().str.replace('%', '', regex=False)
    ch = ch.replace('nan', np.nan)
    df['change_pct'] = pd.to_numeric(ch, errors='coerce') / 100.0

    df['volume'] = parse_volume_to_number(df['volume'])

    # Drop fully-broken rows
    df = df.dropna(subset=['timestamp', 'category', 'ticker']).copy()

    return df


def compute_transitions(df: pd.DataFrame) -> pd.DataFrame:
    """Compute consecutive category transitions per ticker over time."""
    d = df.sort_values(['ticker', 'timestamp', 'category']).copy()
    d['prev_category'] = d.groupby('ticker')['category'].shift(1)
    d['prev_timestamp'] = d.groupby('ticker')['timestamp'].shift(1)

    tr = d[(d['prev_category'].notna()) & (d['timestamp'] > d['prev_timestamp']) & (d['category'] != d['prev_category'])].copy()
    tr['from_category'] = tr['prev_category']
    tr['to_category'] = tr['category']
    tr['from_to'] = tr['from_category'] + ' -> ' + tr['to_category']
    tr['delta_seconds'] = (tr['timestamp'] - tr['prev_timestamp']).dt.total_seconds()
    return tr[['timestamp', 'ticker', 'from_category', 'to_category', 'from_to', 'delta_seconds', 'price', 'change_pct', 'volume']]


def top_volume_spikes(df: pd.DataFrame, q: float = 0.95, min_volume: float = 1.0) -> pd.DataFrame:
    """Return rows where volume is above ticker-specific quantile threshold."""
    d = df.copy()
    d = d[d['volume'].fillna(0) >= min_volume].copy()
    if len(d) == 0:
        return d
    thr = d.groupby('ticker')['volume'].quantile(q)
    d = d.join(thr.rename('thr'), on='ticker')
    d = d[d['volume'] >= d['thr']].copy()
    return d.sort_values('volume', ascending=False)
