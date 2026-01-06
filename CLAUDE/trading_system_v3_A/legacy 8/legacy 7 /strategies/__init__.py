# strategies/__init__.py

import os
import importlib
import inspect
from pathlib import Path

# Intentar importar la clase base. Asumimos que está en 'base.py' o 'base_strategy.py'
# Esto hace el sistema más robusto a cambios de nombre de archivo.
try:
    from .base import BaseStrategy
except ImportError as e:
    print(f"DEBUG: Error importing .base: {e}")
    try:
        from .base_strategy import BaseStrategy
    except ImportError:
        raise ImportError(f"Could not import BaseStrategy. Original error: {e}")

# --- Carga Dinámica de Estrategias ---

# Registro para mantener todas las clases de estrategia descubiertas, usando su nombre como clave.
STRATEGY_REGISTRY = {}

# Ruta al directorio actual (strategies)
current_dir = Path(__file__).parent

# Iterar sobre todos los archivos Python en el directorio
for file in current_dir.glob('*.py'):
    # Omitir el propio __init__.py y archivos que no son de estrategia (ej. backups, archivos de sistema)
    if file.name == '__init__.py' or file.name.startswith(('.', '_')) or '.bak' in file.name or '.backup' in file.name:
        continue

    # Obtener el nombre del módulo a partir del nombre del archivo (ej. 'macdv_strategy')
    module_name = file.stem
    
    try:
        # Importar el módulo de forma dinámica
        module = importlib.import_module(f'.{module_name}', package=__name__)

        # Iterar sobre todos los miembros del módulo
        for name, obj in inspect.getmembers(module):
            # Comprobar si el miembro es una clase, es una subclase de BaseStrategy,
            # y no es la propia BaseStrategy.
            if inspect.isclass(obj) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                # Añadir la estrategia al registro
                if name not in STRATEGY_REGISTRY:
                    STRATEGY_REGISTRY[name] = obj
                    # Hacer la clase directamente importable (ej. from strategies import MACDVStrategy)
                    globals()[name] = obj

    except (ImportError, SyntaxError) as e:
        print(f"ADVERTENCIA: No se pudo importar la estrategia desde {file.name}: {e}")

# Función de ayuda para obtener una estrategia por su nombre
def get_strategy(name: str) -> type[BaseStrategy]:
    strategy = STRATEGY_REGISTRY.get(name)
    if not strategy:
        raise ValueError(f"La estrategia '{name}' no está registrada o no se encontró. Estrategias disponibles: {list(STRATEGY_REGISTRY.keys())}")
    return strategy

# Exponer públicamente el registro y la función de ayuda para que otras partes de la aplicación puedan usarlos.
__all__ = list(STRATEGY_REGISTRY.keys()) + ['get_strategy', 'BaseStrategy', 'STRATEGY_REGISTRY']

# print(f"🔎 Estrategias cargadas dinámicamente: {list(STRATEGY_REGISTRY.keys())}")

"""
Trading strategies module with strategy registry.
"""

import logging

logger = logging.getLogger(__name__)

# Registry for strategies
_strategy_registry = {}

def register_strategy(name: str, strategy_class):
    """
    Register a strategy class in the global registry.
    
    Args:
        name: Strategy name (e.g., 'macdv', 'vcp')
        strategy_class: Strategy class that implements IStrategy
    """
    _strategy_registry[name.lower()] = strategy_class
    logger.debug(f"Strategy registered: {name} -> {strategy_class.__name__}")

def get_strategy_class(name: str):
    """
    Get a strategy class by name from the registry.
    
    Args:
        name: Strategy name
        
    Returns:
        Strategy class or None if not found
    """
    return _strategy_registry.get(name.lower())

def list_strategies():
    """
    List all registered strategy names.
    
    Returns:
        List of strategy names
    """
    return list(_strategy_registry.keys())

def get_strategy_info():
    """
    Get information about all registered strategies.
    
    Returns:
        Dictionary with strategy info
    """
    info = {}
    for name, strategy_class in _strategy_registry.items():
        info[name] = {
            'class_name': strategy_class.__name__,
            'module': strategy_class.__module__,
            'doc': strategy_class.__doc__
        }
    return info

# Auto-register available strategies
def _auto_register_strategies():
    """Auto-register only ACTIVE strategies from config"""

    # ✅ ACTIVE STRATEGIES (from MULTI_STRATEGY.enabled_strategies)

    # Gap & Go
    try:
        from .gap_go_strategy import GapGoStrategy
        register_strategy('gap_go', GapGoStrategy)
        logger.info("✅ Auto-registered GAP_GO strategy")
    except ImportError as e:
        logger.warning(f"Could not auto-register GAP_GO strategy: {e}")

    # Daily Plays
    try:
        from .daily_plays_strategy import DailyPlaysStrategy
        register_strategy('daily_plays', DailyPlaysStrategy)
        logger.info("✅ Auto-registered Daily Plays strategy")
    except ImportError as e:
        logger.warning(f"Could not auto-register Daily Plays strategy: {e}")

    # First Day Bounce
    try:
        from .first_day_bounce_strategy import FirstDayBounceStrategy
        register_strategy('first_day_bounce', FirstDayBounceStrategy)
        logger.info("✅ Auto-registered First Day Bounce Strategy")
    except ImportError as e:
        logger.warning(f"Could not auto-register First Day Bounce Strategy: {e}")


    # Gap Crap Reversal
    try:
        from .gap_crap_reversal_strategy import GapCrapReversalStrategy
        register_strategy('gap_crap_reversal', GapCrapReversalStrategy)
        logger.info("✅ Auto-registered Gap Crap Reversal strategy")
    except ImportError as e:
        logger.warning(f"Could not auto-register Gap Crap Reversal strategy: {e}")


    # Bull Flag
    try:
        from .bull_flag_strategy import BullFlagStrategy
        register_strategy('bull_flag', BullFlagStrategy)
        logger.info("✅ Auto-registered Bull Flag strategy")
    except ImportError as e:
        logger.warning(f"Could not auto-register Bull Flag strategy: {e}")

    # Falling Wedge
    try:
        from .falling_wedge_strategy import FallingWedgeStrategy
        register_strategy('falling_wedge', FallingWedgeStrategy)
        logger.info("✅ Auto-registered Falling Wedge strategy")
    except ImportError as e:
        logger.warning(f"Could not auto-register Falling Wedge strategy: {e}")

# Auto-register when module is imported
_auto_register_strategies()


# Register DynamicStrategyEngine (NO ML + Dynamic switching)
try:
    from .dynamic_strategy_engine import DynamicStrategyEngine
    register_strategy('dynamic_strategy_engine', DynamicStrategyEngine)
    logger.info("✅ DynamicStrategyEngine registered (NO ML + Dynamic switching)")
except ImportError as e:
    logger.warning(f"⚠️ Could not register DynamicStrategyEngine: {e}")

# Register RealisticStrategyEngine (Industry-proven approach)
try:
    from .realistic_strategy_engine import RealisticStrategyEngine
    register_strategy('realistic_strategy_engine', RealisticStrategyEngine)
    logger.info("✅ RealisticStrategyEngine registered (Industry-proven, 3 core strategies)")
except ImportError as e:
    logger.warning(f"⚠️ Could not register RealisticStrategyEngine: {e}")

# Export main components
__all__ = [
    'register_strategy',
    'get_strategy_class',
    'list_strategies',
    'get_strategy_info'
]