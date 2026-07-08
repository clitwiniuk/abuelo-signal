# -*- coding: utf-8 -*-
"""
MÓDULO 1: CONTRATO DE DATOS (DATA CONTRACT)

Define el estándar que deben cumplir los datos para considerarse válidos.
Todos los umbrales viven aquí (o en un YAML que sobreescribe estos defaults).

Nota de diseño para small caps:
  - Un gap overnight grande NO es automáticamente un error: el universo típico
    (top gainers) gapea +50..300% de forma legítima. Solo es sospechoso si el
    volumen no acompaña (ver gap_volume_confirm_ratio).
  - En velas de 1 min, un minuto sin trades no genera vela. Cobertura baja es
    un WARNING de liquidez, no un CRITICAL de integridad.
"""

import copy

# ---------------------------------------------------------------------------
# Contrato por defecto. Cada clave está comentada con su intención.
# ---------------------------------------------------------------------------
DEFAULT_CONTRACT = {
    # --- Esquema -----------------------------------------------------------
    # Columnas obligatorias tras la normalización del loader.
    "required_columns": ["ticker", "timestamp", "date",
                         "open", "high", "low", "close", "volume"],
    # Columna de trazabilidad: cuándo se descargó cada fila. Obligatoria.
    "download_ts_column": "downloaded_at",
    # Alias aceptados por el loader (convenciones históricas del proyecto).
    "column_aliases": {
        "symbol": "ticker",
        "dt": "timestamp",
        "datetime": "timestamp",
        "bar_timestamp": "timestamp",
    },
    # Timezone que se asume para timestamps naive (convención legacy = ET).
    "naive_timezone": "America/New_York",
    # Timezone de referencia para sesiones de mercado.
    "market_timezone": "America/New_York",

    # --- Sesión ------------------------------------------------------------
    # Sesión extendida completa: premarket 04:00 -> afterhours 20:00 ET.
    "session_start": "04:00",
    "session_end": "20:00",
    # Sesión regular (RTH) para métricas de cobertura.
    "regular_start": "09:30",
    "regular_end": "16:00",
    # Calendario de mercado (pandas_market_calendars).
    "calendar": "NASDAQ",

    # --- Umbrales de integridad --------------------------------------------
    # Volumen mínimo total del día por ticker para considerarlo operable.
    "min_daily_volume": 10_000,
    # Mínimo de velas 1-min por ticker-día (extendida). 390 = RTH completa.
    "min_bars_day": 150,
    "ideal_bars_day": 390,
    # Máximo de velas 1-min consecutivas sin cambio de precio (halt/dato congelado).
    "max_flat_candles": 30,
    # Tolerancia relativa para close/open fuera de [low, high] (0.01% = 1e-4).
    "ohlc_tolerance_pct": 0.01,
    # Salto de precio intradía en una sola vela que dispara revisión.
    "max_single_bar_jump_pct": 10.0,
    # El salto solo es sospechoso si volumen < ratio * mediana de volumen del día.
    "jump_volume_ratio": 3.0,
    # Gap overnight (cierre previo -> primera vela premarket) que dispara revisión.
    "max_overnight_gap_pct": 50.0,
    # El gap solo es sospechoso si volumen premarket < ratio * mediana diaria.
    "gap_volume_confirm_ratio": 3.0,

    # --- Universo ----------------------------------------------------------
    # Mínimo de tickers con datos en un día para considerar el día válido.
    "min_tickers_per_day": 15,
    # Días sin datos antes del fin del dataset para considerar "desaparición".
    "disappearance_grace_days": 3,
    # Cambio de universo entre snapshots adyacentes del scanner (Jaccard) que
    # dispara WARNING si los parámetros no cambiaron.
    "scanner_max_universe_shift": 0.30,

    # --- Scoring -----------------------------------------------------------
    # Penalización por violación según severidad (score parte de 100).
    "score_weights": {"CRITICAL": 25, "WARNING": 10, "INFO": 2},
    # Score mínimo para que un ticker-día / día se considere APTO.
    "min_score_valid": 70,
}


def load_contract(yaml_path=None):
    """Devuelve el contrato efectivo: defaults + overrides del YAML (si existe).

    El YAML solo necesita las claves que quiera sobreescribir.
    """
    contract = copy.deepcopy(DEFAULT_CONTRACT)
    if yaml_path:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as fh:
            overrides = yaml.safe_load(fh) or {}
        for key, value in overrides.items():
            # Merge superficial por clave; los dicts anidados se reemplazan
            # completos para evitar estados a medias.
            contract[key] = value
    return contract
