# -*- coding: utf-8 -*-
"""Sistema de auditoría y validación de datos financieros intradía (1-min).

Responde a la pregunta: ¿es este dataset apto para validar o refutar una
hipótesis de trading? Ver README.md para uso.
"""

from .contract import DEFAULT_CONTRACT, load_contract
from .pipeline import run_data_audit, load_data_folder, normalize_dataframe
from .traceability import audit_trade, create_download_metadata, load_metadata_history
from .biases import PointInTimeView, run_temporal_replay

__all__ = [
    "DEFAULT_CONTRACT", "load_contract",
    "run_data_audit", "load_data_folder", "normalize_dataframe",
    "audit_trade", "create_download_metadata", "load_metadata_history",
    "PointInTimeView", "run_temporal_replay",
]
