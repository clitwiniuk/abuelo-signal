"""
Módulo de ejecución de órdenes para sistemas de trading con gestión de riesgo integrada
"""

from .order_executor import (
    OrderExecutor,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position
)

from .risk_manager import (
    RiskManager,
    RiskParameters
)

from .config_loader import (
    load_config,
    get_config,
    reload_config,
    Config
)

# Cargar configuración al importar el módulo
config = get_config()

__all__ = [
    'OrderExecutor',
    'OrderRequest',
    'OrderResponse',
    'OrderStatus',
    'Position',
    'RiskManager',
    'RiskParameters',
    'load_config',
    'get_config',
    'reload_config',
    'Config',
    'config'
]
