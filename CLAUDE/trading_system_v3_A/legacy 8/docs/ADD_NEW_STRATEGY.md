# Guía para Integrar una Nueva Estrategia

## 1. Crear el Archivo de la Estrategia
Crea un nuevo archivo en `strategies/` siguiendo la plantilla:

```python
# strategies/mi_estrategia.py
"""
Descripción corta de la estrategia.
"""

from typing import Dict, Any
from .base import BaseStrategy

class MiEstrategia(BaseStrategy):
    """
    Documentación detallada de la estrategia.
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # Valores por defecto
        default_params = {
            'param1': valor1,
            'param2': valor2,
        }
        super().__init__(parameters or {})
        self.parameters = {**default_params, **self.parameters}
        
    async def generate_signals(self, data: Dict) -> None:
        """Lógica principal de la estrategia."""
        pass
        
    def get_strategy_info(self) -> Dict:
        """Metadatos de la estrategia."""
        return {
            "name": self.name,
            "parameters": self.parameters,
            "version": "1.0"
        }
```

## 2. Registrar la Estrategia
Edita `strategies/__init__.py` para auto-registrar la estrategia:

```python
def _auto_register_strategies():
    # ... código existente ...
    
    try:
        from .mi_estrategia import MiEstrategia
        register_strategy('mi_estrategia', MiEstrategia)
        logger.info("Estrategia 'mi_estrategia' registrada")
    except ImportError as e:
        logger.error(f"Error registrando 'mi_estrategia': {e}")
```

## 3. Configuración en config.ini
Añade una sección para los parámetros de la estrategia:

```ini
[MI_ESTRATEGIA]
param1 = valor1
param2 = valor2
```

## 4. Ejecutar con run_trading_system.py
El archivo principal ya está configurado para cargar dinámicamente las estrategias:

```python
# run_trading_system.py
from strategies import get_strategy_class

# Cargar estrategia configurada
strategy_class = get_strategy_class(config.strategy_name)
if not strategy_class:
    raise ValueError(f"Estrategia no encontrada: {config.strategy_name}")

# Inicializar con parámetros
strategy = strategy_class(parameters=config.strategy_params)
```

## 5. Probar la Estrategia
- **Backtest**: Usa `run_backtest.py`
- **Live**: Inicia con `python run_trading_system.py`

## 6. Verificar en la Interfaz
La estrategia aparecerá automáticamente en el menú desplegable de la interfaz web.

## Notas Importantes
- Sigue el patrón de inyección de dependencias
- Usa logging consistente
- Documenta todos los parámetros
- Maneja adecuadamente los errores
- Incluye tests unitarios
