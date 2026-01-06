

from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple, Union,List,Optional
from enum import Enum
from datetime import datetime, timedelta
from Utils import *
import pandas as pd


#######################################################################################################################################################

def extract_price_series(df: pd.DataFrame, source: str) -> pd.Series:
    """
    Extrae la serie de precios correspondiente del DataFrame según el parámetro `source`.

    Parámetros:
        df: pd.DataFrame  → DataFrame con columnas de precios como open, high, low, close.
        source: str       → Puede ser "open", "high", "low", "close", o "hlcc".

    Retorna:
        pd.Series         → Serie de precios correspondiente.
    """
    source = source.lower()

    if source in {"open", "high", "low", "close", "volume" }:
        if source not in df.columns:
            raise ValueError(f"La columna '{source}' no está en el DataFrame.")
        return df[source]

    elif source == "hlcc":
        required = {"high", "low", "close"}
        if not required.issubset(df.columns):
            raise ValueError("Columnas requeridas para hlcc: 'high', 'low', 'close'.")
        return (df["high"] + df["low"] + 2 * df["close"]) / 4

    else:
        raise ValueError(f"Fuente de datos desconocida: {source}")


