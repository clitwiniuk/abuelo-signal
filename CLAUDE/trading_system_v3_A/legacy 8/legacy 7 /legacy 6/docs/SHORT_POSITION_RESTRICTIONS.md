# Restricciones de Posiciones SHORT - Evitar Overnight Risk

## Overview

Implementación de controles estrictos para operaciones en corto (SHORT positions) que **eliminan completamente** el riesgo de posiciones overnight, premarket y afterhours.

## Problema Resuelto

### Riesgos de Posiciones SHORT Overnight

1. **Gap Risk Extremo**: Stock puede gap up 50-200% con noticias positivas (FDA approval, buyout, etc.)
2. **Short Squeeze Overnight**: Institucionales pueden cubrir masivamente fuera de horas
3. **Liquidez Limitada**: Imposible salir rápidamente en premarket/afterhours
4. **Borrowing Costs**: Shares pueden volverse HTB (Hard To Borrow) overnight
5. **Margin Calls**: Gap adverso puede generar margin call antes de poder actuar

### Solución Implementada

**REGLA ABSOLUTA**: SHORT positions **SOLO** durante regular market hours (9:30 AM - 4:00 PM ET)

- ❌ NO premarket entries
- ❌ NO afterhours entries
- ❌ NO overnight holds
- ✅ Force close 15:45 ET (15 min antes del cierre)

---

## Arquitectura

### 1. Módulo Central: market_hours.py

Ubicación: [core/market_hours.py](../core/market_hours.py)

```python
from core.market_hours import (
    get_market_hours,
    can_enter_short,
    should_force_exit_short,
    is_regular_hours
)
```

#### Horarios Definidos

```python
# Premarket: 4:00 AM - 9:30 AM ET
# Regular Hours: 9:30 AM - 4:00 PM ET
# After Hours: 4:00 PM - 8:00 PM ET

# SHORT Restrictions:
SHORT_ENTRY_EARLIEST = 9:35 AM ET   # 5 min después de apertura
SHORT_ENTRY_LATEST = 3:00 PM ET     # 1 hora antes del cierre
SHORT_EXIT_DEADLINE = 3:45 PM ET    # FORCE CLOSE 15 min antes del cierre
```

### 2. Workers con SHORT Integrado

#### Gap Fade Worker

[strategies/workers/gap_fade_worker_logic.py](../strategies/workers/gap_fade_worker_logic.py)

```python
def evaluate_opportunity(self, opportunity: Dict) -> bool:
    """
    Evalúa GAP FADE SHORT entry
    """
    # PHASE 0: MARKET HOURS CHECK (CRITICAL)
    can_short, short_reason = can_enter_short()
    if not can_short:
        self.logger.warning(f"🚫 {symbol}: SHORT entry BLOCKED - {short_reason}")
        return False

    # ... resto de filtros
```

#### Short Parabolic Worker

[strategies/workers/short_parabolic_worker_logic.py](../strategies/workers/short_parabolic_worker_logic.py)

```python
async def should_enter(self, opportunity: Dict) -> bool:
    """
    Parabolic Reversal SHORT entry
    """
    # STEP 0A: MARKET HOURS CHECK (CRITICAL)
    can_short, short_reason = can_enter_short()
    if not can_short:
        self.logger.warning(f"🚫 {symbol}: SHORT entry BLOCKED - {short_reason}")
        return False

    # ... resto de filtros
```

### 3. Base Worker Logic - Cierre Automático

[strategies/workers/base_worker_logic.py:1876-1928](../strategies/workers/base_worker_logic.py#L1876-L1928)

```python
async def _monitor_positions(self):
    """
    Monitorea posiciones activas
    CRITICAL: SHORT positions force-close at 15:45 ET
    """
    for symbol, data in list(self.active_positions.items()):
        position_data = data['position'].copy()

        # CRITICAL: Check if SHORT position needs force exit
        is_short = position_data.get('side') == 'SELL'
        if is_short:
            force_exit, force_reason = should_force_exit_short()
            if force_exit:
                self.logger.warning(
                    f"⚠️ {symbol}: FORCE CLOSING SHORT - {force_reason}"
                )
                await self._execute_exit(symbol, f"FORCED EXIT: {force_reason}", current_price)
                continue  # Skip normal exit logic

        # ... normal exit logic
```

---

## Flujo de Ejecución

### Entrada SHORT (Entry)

```
Oportunidad detectada: TSLA gap fade
    ↓
Gap Fade Worker: evaluate_opportunity()
    ↓
can_enter_short() → Verifica:
    ├─ Session == 'REGULAR'? (9:30-16:00)
    ├─ Time >= 9:35 AM ET?
    └─ Time <= 3:00 PM ET?
    ↓
✅ ALLOWED → Continuar con filtros técnicos
❌ BLOCKED → Reject (log warning)
```

### Monitorización SHORT (Ongoing)

```
Cada 1 segundo: _monitor_positions()
    ↓
Para cada posición SHORT:
    ↓
should_force_exit_short() → Verifica:
    ├─ Time >= 3:45 PM ET? → FORCE EXIT
    ├─ Session != 'REGULAR'? → FORCE EXIT
    └─ OK → Continue normal monitoring
    ↓
Si FORCE EXIT:
    ├─ Log: "⚠️ FORCE CLOSING SHORT - {reason}"
    ├─ Execute exit immediately
    └─ Skip normal exit logic
    ↓
Si OK:
    └─ Evaluar exits normales (TP/SL/Time Stop)
```

### Timeline Completo (Ejemplo de Día)

```
9:30 AM ET - Market Open
    └─ SHORT entries BLOQUEADAS (volatilidad inicial)

9:35 AM ET - Ventana SHORT abre
    └─ ✅ Entrada permitida: Gap Fade Worker puede abrir SHORT

12:00 PM ET - Mid Day
    └─ ✅ Monitorización normal: TP/SL activos

3:00 PM ET - Última entrada SHORT
    └─ ❌ Nuevas entradas SHORT BLOQUEADAS

3:45 PM ET - SHORT EXIT DEADLINE
    └─ 🚨 FORCE CLOSE todas las posiciones SHORT
    └─ Razón: "SHORT exit deadline reached (15:45 ET) - FORCE CLOSE"

4:00 PM ET - Market Close
    └─ ✅ Todas las SHORT positions ya cerradas (desde 15:45)

4:01 PM ET - After Hours
    └─ ❌ SHORT entries permanentemente BLOQUEADAS
    └─ Session: AFTERHOURS → can_enter_short() = False
```

---

## API Reference

### market_hours.py

#### `can_enter_short() -> Tuple[bool, str]`

Verifica si entrada SHORT está permitida **ahora**.

```python
can_short, reason = can_enter_short()

# Returns:
# (True, "SHORT entry allowed") si OK
# (False, "SHORT entries only during regular hours (current: PREMARKET)") si bloqueado
# (False, "SHORT entries start at 09:35 ET (current: 09:31 ET)") si muy temprano
# (False, "SHORT entries end at 15:00 ET (current: 15:05 ET)") si muy tarde
```

#### `should_force_exit_short() -> Tuple[bool, str]`

Verifica si SHORT debe cerrarse **forzosamente**.

```python
force_exit, reason = should_force_exit_short()

# Returns:
# (True, "SHORT exit deadline reached (15:45 ET) - FORCE CLOSE") si deadline
# (True, "Market session changed to AFTERHOURS - FORCE CLOSE SHORT") si fuera de horas
# (False, "No forced exit required") si OK
```

#### `get_market_session() -> str`

Retorna sesión actual del mercado.

```python
session = get_market_session()

# Returns: 'PREMARKET', 'REGULAR', 'AFTERHOURS', 'CLOSED'
```

#### `is_regular_hours() -> bool`

Quick check si mercado está en horario regular.

```python
if is_regular_hours():
    # OK para SHORT entries (con time window check)
```

#### `MarketHours.get_market_status_summary() -> dict`

Obtiene resumen completo del estado del mercado.

```python
market_hours = get_market_hours()
status = market_hours.get_market_status_summary()

# Returns:
{
    'current_time_et': '2025-12-26 14:30:00 EST',
    'session': 'REGULAR',
    'is_regular_hours': True,
    'is_extended_hours': False,
    'can_enter_short': True,
    'short_entry_reason': 'SHORT entry allowed',
    'can_enter_long': True,
    'long_entry_reason': 'LONG entry allowed',
    'should_force_exit_short': False,
    'force_exit_reason': 'No forced exit required',
    'minutes_to_short_deadline': 75  # minutos hasta 15:45
}
```

---

## Configuración

### Ajustar Horarios (si necesario)

Editar [core/market_hours.py](../core/market_hours.py):

```python
class MarketHours:
    # Cambiar horarios de entrada SHORT
    SHORT_ENTRY_EARLIEST = datetime_time(9, 35)   # Default: 9:35 AM
    SHORT_ENTRY_LATEST = datetime_time(15, 0)     # Default: 3:00 PM
    SHORT_EXIT_DEADLINE = datetime_time(15, 45)   # Default: 3:45 PM
```

**Valores Recomendados**:

| Perfil | ENTRY_EARLIEST | ENTRY_LATEST | EXIT_DEADLINE | Justificación |
|--------|----------------|--------------|---------------|---------------|
| **Conservador** | 9:45 AM | 2:30 PM | 3:30 PM | Evita volatilidad apertura/cierre |
| **Balanceado** (ACTUAL) | 9:35 AM | 3:00 PM | 3:45 PM | 5 min cushion apertura, 15 min cierre |
| **Agresivo** | 9:31 AM | 3:30 PM | 3:55 PM | Máxima ventana (⚠️ Mayor riesgo) |

**NO RECOMENDADO**: Nunca usar `EXIT_DEADLINE > 3:55 PM` (demasiado cerca del cierre)

---

## Testing

### Script de Prueba

Ubicación: [core/market_hours.py](../core/market_hours.py) (al final del archivo)

```bash
# Ejecutar tests
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
python core/market_hours.py
```

Output esperado:
```
============================================================
MARKET STATUS SUMMARY
============================================================
Current Time (ET): 2025-12-26 14:30:00 EST
Session: REGULAR
Regular Hours: True

ENTRY PERMISSIONS:
  SHORT: ✅ ALLOWED
    → SHORT entry allowed
  LONG: ✅ ALLOWED
    → LONG entry allowed

EXIT REQUIREMENTS:
  Force Exit SHORT: ✅ NO
    → No forced exit required
  Minutes to SHORT deadline: 75 min
============================================================

============================================================
TEST SCENARIOS
============================================================

Premarket (08:00 ET):
  Can enter SHORT: ❌ - SHORT entries only during regular hours (current: PREMARKET)
  Force exit: ✅ - No forced exit required

Market Open (09:30 ET):
  Can enter SHORT: ❌ - SHORT entries start at 09:35 ET (current: 09:30 ET)
  Force exit: ✅ - No forced exit required

Early Morning (09:35 ET):
  Can enter SHORT: ✅ - SHORT entry allowed
  Force exit: ✅ - No forced exit required

Mid Day (12:00 ET):
  Can enter SHORT: ✅ - SHORT entry allowed
  Force exit: ✅ - No forced exit required

Late Afternoon (14:55 ET):
  Can enter SHORT: ✅ - SHORT entry allowed
  Force exit: ✅ - No forced exit required

Near Deadline (15:40 ET):
  Can enter SHORT: ❌ - SHORT entries end at 15:00 ET (current: 15:40 ET)
  Force exit: ✅ - No forced exit required

Past Deadline (15:50 ET):
  Can enter SHORT: ❌ - SHORT entries end at 15:00 ET (current: 15:50 ET)
  Force exit: ⚠️ - SHORT exit deadline reached (15:45 ET) - FORCE CLOSE

Market Close (16:00 ET):
  Can enter SHORT: ❌ - SHORT entries only during regular hours (current: AFTERHOURS)
  Force exit: ⚠️ - Market session changed to AFTERHOURS - FORCE CLOSE SHORT

After Hours (17:00 ET):
  Can enter SHORT: ❌ - SHORT entries only during regular hours (current: AFTERHOURS)
  Force exit: ⚠️ - Market session changed to AFTERHOURS - FORCE CLOSE SHORT
```

---

## Logs Típicos

### Entrada Bloqueada (Premarket)

```
WARNING - 🚫 TSLA: SHORT entry BLOCKED - SHORT entries only during regular hours (current: PREMARKET)
```

### Entrada Bloqueada (Demasiado Tarde)

```
WARNING - 🚫 NVDA: SHORT entry BLOCKED - SHORT entries end at 15:00 ET (current: 15:10 ET)
```

### Cierre Forzado (Deadline)

```
WARNING - ⚠️ AAPL: FORCE CLOSING SHORT - SHORT exit deadline reached (15:45 ET) - FORCE CLOSE
INFO - 🔴 AAPL: SHORT EXIT executed - FORCED EXIT: SHORT exit deadline reached (15:45 ET) - FORCE CLOSE
```

### Cierre Forzado (After Hours)

```
WARNING - ⚠️ META: FORCE CLOSING SHORT - Market session changed to AFTERHOURS - FORCE CLOSE SHORT
INFO - 🔴 META: SHORT EXIT executed - FORCED EXIT: Market session changed to AFTERHOURS - FORCE CLOSE SHORT
```

---

## Preguntas Frecuentes

### ¿Qué pasa si hay una posición SHORT a las 15:45 con ganancia del 8%?

**Respuesta**: Se cierra automáticamente, independientemente del P&L. La protección contra overnight risk es **absoluta**.

### ¿Puedo extender el deadline a 15:55 para capturar más movimiento?

**Respuesta**: **NO RECOMENDADO**. Quedan solo 5 minutos hasta el cierre, liquidez baja, riesgo de slippage alto. El deadline 15:45 da 15 minutos de margen para ejecutar salidas ordenadas.

### ¿Los LONG positions tienen las mismas restricciones?

**Respuesta**: No. LONG positions pueden:
- Entrar en premarket (opcional, configurable)
- Entrar en afterhours (opcional, configurable)
- Mantenerse overnight (swing transitions a las 15:30 ET)

Solo SHORT positions tienen restricciones estrictas por el gap risk asimétrico.

### ¿Qué pasa si IBKR rechaza la orden de cierre a las 15:45?

**Respuesta**: El sistema intentará cerrar cada segundo hasta éxito. Si falla:
1. Log error crítico
2. Enviar alerta Telegram (si configurado)
3. Intentar exit manual via TWS

**PREVENCIÓN**: Usar limit orders con buffer (ask + 0.5%) en vez de market orders para garantizar fills.

### ¿Cómo pruebo el sistema sin esperar a las 15:45?

**Respuesta**: Usar [Replay Mode](REPLAY_SYSTEM.md) con fechas específicas:

```python
# En replay_runner.py
test_time = datetime(2025, 1, 15, 15, 44, 0)  # 15:44 ET
replay_engine.advance_to_time(test_time)

# Avanzar 1 min → 15:45 → Trigger force exit
replay_engine.advance_minutes(1)
```

---

## Métricas de Éxito

### Indicadores de Salud del Sistema

```sql
-- Verificar que NO hay shorts overnight (query en trading_data.db)
SELECT
    symbol,
    entry_time,
    exit_time,
    side,
    DATE(entry_time) as entry_date,
    DATE(exit_time) as exit_date
FROM trades
WHERE
    side = 'SELL'  -- SHORT positions
    AND status = 'CLOSED'
    AND DATE(entry_time) != DATE(exit_time)  -- Overnight hold
ORDER BY entry_time DESC
LIMIT 10;

-- Expected result: 0 rows (no overnight shorts)
```

### Logs a Monitorizar

```bash
# Buscar force exits (deben existir cerca de las 15:45 diariamente)
grep "FORCE CLOSING SHORT" logs/worker_*.log | tail -20

# Verificar que no hay entradas bloqueadas fuera de horas
grep "SHORT entry BLOCKED" logs/worker_*.log | grep -E "PREMARKET|AFTERHOURS" | tail -10
```

---

## Próximos Pasos (Opcional)

### Posibles Mejoras Futuras

1. **Alertas Telegram**: Notificar cuando se fuerza cierre de SHORT
2. **Dashboard**: Visualizar tiempo restante hasta deadline en UI
3. **Dynamic Deadline**: Ajustar deadline basado en volatilidad (15:30 si VIX > 30)
4. **Smart Exit**: En vez de force close a precio de mercado, usar limit order inteligente
5. **Pre-Close Warning**: Log warning a las 15:30 si hay SHORTs activos

---

## Conclusión

La implementación de restricciones horarias para posiciones SHORT elimina completamente el riesgo de overnight/extended hours holds, protegiendo la cuenta de eventos catastróficos (gap ups, short squeezes) que pueden ocurrir fuera del horario regular.

**Regla de Oro**: SHORT positions son **intraday only**, sin excepciones.

**Estado**: ✅ IMPLEMENTADO Y ACTIVO

**Mantenimiento**: Revisar logs diariamente para confirmar force exits cerca de las 15:45 ET
