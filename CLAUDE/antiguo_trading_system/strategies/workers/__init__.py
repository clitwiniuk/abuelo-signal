"""
Worker Logic Components
Workers lógicos para procesamiento paralelo de estrategias
"""

from .base_worker_logic import BaseWorkerLogic
from .macdv_worker_logic import MacdvWorkerLogic
from .daily_plays_worker_logic import DailyPlaysWorkerLogic
from .vwap_worker_logic import VWAPWorkerLogic
from .momentum_breakout_worker_logic import MomentumBreakoutWorkerLogic
from .vcp_smallcap_worker_logic import VCPSmallcapWorkerLogic
from .volume_absorption_worker_logic import VolumeAbsorptionWorkerLogic
from .generic_01_worker_logic import Generic01WorkerLogic
from .smallcaps_long_worker_logic import SmallCapsLongWorkerLogic
from .outlier_penny_extreme_worker_logic import OutlierPennyExtremeWorkerLogic
from .trend_filters import TrendFilters, create_trend_filters_from_config

__all__ = [
    'BaseWorkerLogic',
    'MacdvWorkerLogic',
    'DailyPlaysWorkerLogic',
    'VWAPWorkerLogic',
    'MomentumBreakoutWorkerLogic',
    'VCPSmallcapWorkerLogic',
    'VolumeAbsorptionWorkerLogic',
    'Generic01WorkerLogic',
    'SmallCapsLongWorkerLogic',
    'OutlierPennyExtremeWorkerLogic',
    'TrendFilters',
    'create_trend_filters_from_config'
]