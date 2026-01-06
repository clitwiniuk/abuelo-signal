"""
TradeTally Integration Package - API-First Architecture
========================================================

Integración con TradeTally usando REST API (sin acceso directo a PostgreSQL).

Módulos principales:
- core: Cliente REST API
- cli: Interfaz de línea de comandos
- config: Configuración y API keys
- legacy: Archivos deprecados (no usar)
- docs: Documentación

Uso básico:
    from integrations.tradetally.core.tradetally_api_client import TradeTallyAPIClient
    from integrations.tradetally.config.tradetally_config import TradeTallyConfig

    client = TradeTallyAPIClient(api_key, base_url, db_path)
    client.sync_all_trades()
"""

# Re-export main classes for convenient imports
from .core.tradetally_api_client import TradeTallyAPIClient
from .config.tradetally_config import TradeTallyConfig

__version__ = "2.0.0"  # Major version bump for API-First architecture
__author__ = "Trading System v3"

__all__ = [
    'TradeTallyAPIClient',
    'TradeTallyConfig'
]