# Prompt: Worker Small Cap Simple (100% Reproducible)

## Objetivo

Crear un worker minimalista que sea **100% reproducible en replay** para poder validar su performance histórica y futura.

---

## Filosofía de Diseño

**KISS: Keep It Simple, Stupid**

1. Entry simple basado en datos **ya disponibles** en el sistema
2. Exit mecánico sin interpretación
3. Zero subjetividad
4. Zero lookback complejo
5. Zero indicadores custom

---

## Datos Disponibles Garantizados en Replay

El sistema ya tiene persistidos:

```python
# De scanner_signals (DB)
quality_score: float  # 0-100
catalyst_type: str  # 'EARNINGS', 'FDA', etc.
catalyst_strength: float  # 0-100

# De bar data (OHLCV)
open, high, low, close: float
volume: int
timestamp: datetime

# De market data (calculables)
vwap: float  # Volume-weighted average price
```

**Eso es TODO lo que necesitas.**

---

## Worker Minimalista: "VWAP Runner"

### Entry (3 condiciones, todas del sistema)

```python
def should_enter(opportunity) -> (bool, float, str):
    """
    Entry ultra simple - solo 3 checks
    """

    # 1. Scanner quality (YA EN DB)
    if opportunity['quality_score'] < 65:
        return False, 0, "Low quality"

    # 2. Precio sobre VWAP (calculable de OHLCV)
    if opportunity['close'] <= opportunity['vwap']:
        return False, 0, "Below VWAP"

    # 3. Barra verde (OHLCV)
    if opportunity['close'] <= opportunity['open']:
        return False, 0, "Red bar"

    # Pattern completion = quality_score directamente
    # (El scanner ya hizo el trabajo duro)
    pattern_completion = opportunity['quality_score']

    return True, pattern_completion, "VWAP + Quality + Green"
```

**Eso es TODO.**

No más filtros. No más complejidad.

---

### Stop Loss (Mecánico)

```python
def calculate_stop(entry_price, vwap) -> float:
    """
    Stop simple: 2% bajo entry o VWAP, lo que sea más bajo
    """
    stop_pct = entry_price * 0.98  # 2% bajo entry
    stop_vwap = vwap * 0.99  # 1% bajo VWAP

    # El más bajo (más conservador)
    return max(stop_pct, stop_vwap)
```

**No higher lows. No pivots. No complejidad.**

---

### Exit (2 opciones, ambas mecánicas)

```python
def should_exit(position, current_bar) -> (bool, str):
    """
    Exit simple - 2 reglas
    """
    current_price = current_bar['close']

    # 1. Hard stop
    if current_price <= position['stop_price']:
        return True, "Stop hit"

    # 2. Cruza VWAP hacia abajo
    if current_price < current_bar['vwap']:
        return True, "VWAP break"

    return False, "Hold"
```

**No trailing complejo. No momentum death. No parciales.**

Solo stop duro + invalidación VWAP.

---

## Template Completo (Production Ready)

```python
"""
Small Cap VWAP Runner - Minimalista

Entry: Quality + VWAP + Green bar
Stop: 2% o VWAP-1%
Exit: Stop hit o VWAP break

100% reproducible en replay
"""

from strategies.workers.base_worker_logic import BaseWorkerLogic
from typing import Dict, Any, Optional


class SmallcapVwapRunnerWorker(BaseWorkerLogic):
    """Worker minimalista para small caps"""

    def __init__(self, execution_engine, **kwargs):
        super().__init__(execution_engine, **kwargs)

        self.worker_name = "smallcap_vwap_runner"

        # Solo 3 parámetros
        self.min_quality = 65  # Scanner quality mínima
        self.stop_pct = 0.02  # 2% stop
        self.vwap_buffer = 0.01  # 1% buffer VWAP


    async def should_enter(self, opportunity: Dict[str, Any]) -> tuple[bool, float, str]:
        """Entry: 3 checks simples"""

        # 1. Quality (de scanner_signals DB)
        quality = opportunity.get('quality_score', 0)
        if quality < self.min_quality:
            return False, 0, f"Quality {quality} < {self.min_quality}"

        # 2. VWAP (calculable de OHLCV)
        current_price = opportunity['current_price']
        vwap = opportunity.get('vwap', 0)

        if vwap == 0:
            return False, 0, "No VWAP data"

        if current_price <= vwap:
            return False, 0, f"Below VWAP ({current_price} <= {vwap})"

        # 3. Green bar (OHLCV)
        bar = opportunity.get('bar', {})
        if bar.get('close', 0) <= bar.get('open', 0):
            return False, 0, "Red bar"

        # Pattern completion = quality directamente
        pattern_completion = quality

        return True, pattern_completion, f"Q={quality:.0f}, Price={current_price:.2f}, VWAP={vwap:.2f}"


    async def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        opportunity: Dict[str, Any]
    ) -> int:
        """
        Position size usando RiskManager del sistema
        """
        vwap = opportunity.get('vwap', entry_price)
        stop_price = self._calculate_stop(entry_price, vwap)

        # RiskManager ya implementado en el sistema
        # Solo calculamos el stop, él hace el resto
        risk_per_share = entry_price - stop_price

        if risk_per_share <= 0:
            return 0

        # 1% de la cuenta por trade (hardcoded simple)
        account_size = 100_000  # TODO: get from broker
        risk_amount = account_size * 0.01

        shares = int(risk_amount / risk_per_share)

        return max(100, shares)  # Mínimo 100 shares


    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_bar: Dict[str, Any]
    ) -> tuple[bool, str]:
        """Exit: 2 reglas mecánicas"""

        current_price = current_bar['close']
        stop_price = position.get('stop_price', 0)

        # 1. Hard stop
        if current_price <= stop_price:
            return True, f"Stop hit: {current_price:.2f} <= {stop_price:.2f}"

        # 2. VWAP break
        vwap = current_bar.get('vwap', 0)
        if vwap > 0 and current_price < vwap:
            return True, f"VWAP break: {current_price:.2f} < {vwap:.2f}"

        return False, f"Hold (price={current_price:.2f}, vwap={vwap:.2f})"


    def _calculate_stop(self, entry_price: float, vwap: float) -> float:
        """Stop: 2% bajo entry o 1% bajo VWAP"""
        stop_pct = entry_price * (1 - self.stop_pct)
        stop_vwap = vwap * (1 - self.vwap_buffer)

        # Más conservador (el más bajo)
        return round(max(stop_pct, stop_vwap), 2)


    async def update_position(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_bar: Dict[str, Any]
    ):
        """
        Actualizar posición cada barra

        Para este worker simple: NO hacer nada
        (No trailing, no parciales, solo esperar exit conditions)
        """
        pass
```

---

## Parámetros Iniciales

```python
MIN_QUALITY = 65  # Scanner quality
STOP_PCT = 0.02  # 2% stop
VWAP_BUFFER = 0.01  # 1% VWAP buffer
RISK_PER_TRADE = 0.01  # 1% account risk
```

**Eso es TODO.**

---

## Por Qué Es 100% Reproducible

1. **quality_score** → Ya en DB (scanner_signals)
2. **VWAP** → Calculable de OHLCV (determinístico)
3. **Green bar** → OHLCV (determinístico)
4. **Stop price** → Función pura de entry + VWAP
5. **Exit** → Función pura de price + VWAP

**Zero lookback dinámico. Zero indicadores custom. Zero interpretación.**

---

## Testing

```python
# Backtest en replay
python -m replay_testing.run_replay \
    --date 2026-01-05 \
    --workers smallcap_vwap_runner

# Expected:
# - 100% match entre live y replay (mismos entries)
# - 100% match en exits (mismas condiciones)
# - Resultados idénticos en múltiples runs
```

---

## Evolución Futura (Solo después de validar esto)

**Si este worker simple funciona**, entonces:

1. Añadir trailing VWAP (opcional)
2. Añadir parciales (opcional)
3. Añadir filtros de volumen (opcional)

**Si NO funciona**, entonces:

- El problema NO es la complejidad que falta
- El problema es el edge no existe
- No añadir más complejidad

---

## Output del Prompt

**Genera el archivo completo:**

`strategies/workers/smallcap_vwap_runner_worker_logic.py`

Con:
- ✅ 3 condiciones de entry (quality, VWAP, green)
- ✅ Stop mecánico (2% o VWAP-1%)
- ✅ Exit simple (stop o VWAP break)
- ✅ Zero complejidad adicional
- ✅ 100% reproducible en replay
- ✅ Integrado con sistema actual (BaseWorkerLogic, ExecutionEngineAdapter)

---

**¿Proceder con esta versión simple?**

Es literalmente:
- 3 líneas de entry
- 2 líneas de stop
- 2 líneas de exit

Total: ~100 líneas de código.

**Simple. Testable. Reproducible.**
