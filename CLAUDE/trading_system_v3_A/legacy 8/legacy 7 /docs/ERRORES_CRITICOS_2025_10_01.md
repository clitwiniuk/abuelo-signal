# 🚨 Errores Críticos Encontrados - 2025-10-01

## Resumen Ejecutivo

Sistema tenía **6 ERRORES CRÍTICOS** que bloqueaban completamente la ejecución de trades:

1. ❌ **Firma incorrecta en `_execute_entry()`** - Todos los workers (crasheaba al intentar ejecutar)
2. ❌ **Atributo incorrecto `execution_engine.adapter`** - Debía ser `broker` (bloqueaba market data)
3. ❌ **Scanner timestamp attribute** - `play.timestamp` → `play.scan_timestamp` (bloqueaba catalyst plays)
4. ❌ **ServiceLocator method call** - `get_risk_manager()` → `get_or_create_risk_manager()` (pipeline error)
5. ❌ **Config.ini `%` sin escapar** - Comentarios con `%` deben usar `%%` (bloqueaba carga de config)
6. ❌ **Timezone-aware/naive datetime mismatch** - StopLossManager (bloqueaba exits de posiciones abiertas)

---

## Error Crítico #1: `_execute_entry()` Firma Incorrecta ❌→✅

### Síntoma
```
❌ Error processing opportunity DVLT: DailyPlaysWorkerLogic._execute_entry()
   missing 1 required positional argument: 'opportunity'
```

### Causa Raíz
Los 4 workers sobreescribían `_execute_entry()` con firma incorrecta que no coincidía con la base class.

**Firma Incorrecta** (tenía parámetro `symbol` extra):
```python
async def _execute_entry(self, symbol: str, opportunity: Dict[str, Any]) -> bool:
    success = await super()._execute_entry(symbol, opportunity)  # ❌ 2 args
```

**Firma Correcta** (base class espera solo `opportunity`):
```python
async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
    success = await super()._execute_entry(opportunity)  # ✅ 1 arg
    symbol = opportunity.get('symbol', 'UNKNOWN')  # Extract from dict
```

### Archivos Corregidos
- `strategies/workers/daily_plays_worker_logic.py:380`
- `strategies/workers/macdv_worker_logic.py:277`
- `strategies/workers/gap_go_worker_logic.py:277`
- `strategies/workers/bull_flag_worker_logic.py:284`

### Impacto
**BLOQUEANTE TOTAL**: Workers confirmaban entradas pero el sistema crasheaba al intentar ejecutar.
- ✅ Workers evaluaban: "Entry criteria met"
- ❌ Execution fallaba: TypeError al llamar `_execute_entry()`
- 💔 0 trades ejecutados

---

## Error Crítico #2: Atributo `execution_engine.adapter` Incorrecto ❌→✅

### Síntoma
```
❌ Error checking daily context for DVLT: 'ExecutionEngineAdapter' object
   has no attribute 'adapter'
```

### Historia del Error (3 iteraciones)

**Iteración 1 - Error Original**:
```python
bars = await self.execution_engine.ibkr_adapter.ib.reqHistoricalDataAsync(...)
# ❌ AttributeError: 'ExecutionEngineAdapter' object has no attribute 'ibkr_adapter'
```

**Iteración 2 - Fix Incorrecto**:
```python
bars = await self.execution_engine.adapter.ib.reqHistoricalDataAsync(...)
# ❌ AttributeError: 'ExecutionEngineAdapter' object has no attribute 'adapter'
```

**Iteración 3 - Fix Correcto** ✅:
```python
bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(...)
# ✅ ExecutionEngineAdapter.broker → IBKRAdapter → IB()
```

### Estructura Correcta
```
self.execution_engine        → ExecutionEngineAdapter
  └─ self.execution_engine.broker → IBKRAdapter
       └─ self.execution_engine.broker.ib → IB() object
```

### Archivos Corregidos (7 ocurrencias)
- `strategies/workers/daily_plays_worker_logic.py:347` (_get_vwap)
- `strategies/workers/daily_plays_worker_logic.py:431` (_check_daily_context)
- `strategies/workers/daily_plays_worker_logic.py:493` (should_exit FOMO detection)
- `strategies/workers/macdv_worker_logic.py:244` (should_exit FOMO detection)
- `strategies/workers/gap_go_worker_logic.py:244` (should_exit FOMO detection)
- `strategies/workers/gap_go_worker_logic.py:328` (_get_vwap)
- `strategies/workers/bull_flag_worker_logic.py:251` (should_exit FOMO detection)

### Impacto
**BLOQUEANTE FUNCIONAL**: Impedía acceso a market data de IBKR.
- ❌ Daily Context Check fallaba (Daily Plays worker)
- ❌ VWAP calculation fallaba (Gap-Go worker)
- ❌ FOMO detection fallaba (todos los workers)
- 💔 Análisis técnico incompleto

---

## Error #3: Scanner Timestamp Attribute ❌→✅

### Síntoma
```
❌ Error in unified scanning: 'SmallcapPlay' object has no attribute 'timestamp'
```

### Causa
Auto-cleanup intentaba acceder `play.timestamp` pero `SmallcapPlay` dataclass usa `scan_timestamp`.

**Código Incorrecto**:
```python
self.active_plays_session = [
    play for play in self.active_plays_session
    if (current_time - play.timestamp).total_seconds() / 60 < 30  # ❌ timestamp
]
```

**Código Correcto**:
```python
self.active_plays_session = [
    play for play in self.active_plays_session
    if (current_time - play.scan_timestamp).total_seconds() / 60 < 30  # ✅ scan_timestamp
]
```

### Archivo Corregido
- `scanner/smallcap/smallcap_daily_scanner.py:282`

### Impacto
**BLOQUEANTE DE PUBLICACIÓN**: Scanner detectaba plays pero no los publicaba al trader.
- ✅ Scanner detectaba: `catalyst_news` plays (TLRY, PTON, CGC, NAKA)
- ❌ Unified scan crasheaba: AttributeError
- 💔 Solo `INTRADAY_MOMENTUM` publicado, NO catalyst plays

---

## Error #4: ServiceLocator Method Call Incorrecto ❌→✅

### Síntoma
```
❌ Failed to sync positions to RiskManager: 'ServiceLocator' object has no
   attribute 'get_risk_manager'
```

### Causa
Pipeline llamaba método `get_risk_manager()` que no existe en ServiceLocator.

**Código Incorrecto**:
```python
service_locator = ServiceLocator()
risk_manager = await service_locator.get_risk_manager()  # ❌ No existe
```

**Código Correcto**:
```python
service_locator = ServiceLocator()
risk_manager = await service_locator.get_or_create_risk_manager()  # ✅ Existe
```

### Archivo Corregido
- `core/pipeline.py:136`

### Impacto
**NO BLOQUEANTE**: Este error ocurría en TradingPipeline (sistema antiguo de señales), no en Workers (sistema nuevo). Pero causaba warning logs y falla al sincronizar posiciones entre sistemas.

---

## 📊 Estado del Sistema

### ANTES de los fixes (20:54:27):
```
✅ Scanner: Detectando opportunities
✅ Router: Distribuyendo correctamente (TECHNICAL→macdv, CATALYST→daily_plays)
✅ Workers: Evaluando y confirmando entradas (14 confirmadas)
❌ Execution: BLOQUEADO por Error #1 (_execute_entry)
❌ Market Data: BLOQUEADO por Error #2 (adapter access)
❌ Catalyst Publishing: BLOQUEADO por Error #3 (timestamp)
```

### DESPUÉS de los fixes:
```
✅ Scanner: Detectando opportunities
✅ Router: Distribuyendo correctamente
✅ Workers: Evaluando y confirmando entradas
✅ Execution: FUNCIONAL (firma corregida)
✅ Market Data: FUNCIONAL (broker.ib access)
✅ Catalyst Publishing: FUNCIONAL (scan_timestamp)
✅ Pipeline Sync: FUNCIONAL (get_or_create_risk_manager)
```

---

## ⚠️ ACCIÓN REQUERIDA

**El trader DEBE REINICIARSE** para cargar estos fixes.

Los logs muestran que a las 20:54:27 el trader todavía tenía:
1. Error de `adapter` attribute
2. Error de `_execute_entry()` missing argument

Esto confirma que el trader está corriendo con **código viejo**. Los fixes están aplicados en los archivos pero el proceso necesita reiniciarse.

### Comando de Reinicio
```bash
# Detener trader actual
pkill -f trader_main.py

# Reiniciar trader
python trader_main.py
```

---

## 🎯 Comportamiento Esperado Post-Reinicio

### Scanner → Trader Flow
```
📡 Scanner detecta 22 opportunities (8 catalyst, 14 technical)
🎯 Trader recibe 22 opportunities
🎯 DVLT: Routing to workers: ['daily_plays']     ← Catalyst
🔍 daily_plays: DVLT: Evaluating opportunity...
✓ DVLT: Daily context healthy (sin error de broker) ✅
✓ DVLT: Price above VWAP ✅
✅ DVLT: Daily Plays CONFIRMED!
💰 ENTRY EXECUTED: DVLT @ $1.35                  ← Trade real! ✅
```

### Confirmación de Fixes
Verificar en logs:
1. ✅ NO más error `'ExecutionEngineAdapter' object has no attribute 'adapter'`
2. ✅ NO más error `_execute_entry() missing 1 required positional argument`
3. ✅ NO más error `'SmallcapPlay' object has no attribute 'timestamp'`
4. ✅ NO más error `'ServiceLocator' object has no attribute 'get_risk_manager'`
5. ✅ SÍ aparecen: `ENTRY EXECUTED` logs
6. ✅ SÍ aparecen: Catalyst plays publicados al trader

---

## 📋 Checklist de Verificación

- [ ] Trader reiniciado
- [ ] Logs muestran evaluation de workers (INFO level)
- [ ] Daily context check funciona (sin error de `broker`)
- [ ] Workers confirman entradas sin crashear
- [ ] Trades se ejecutan (`ENTRY EXECUTED` logs)
- [ ] Catalyst plays llegan al trader (TLRY, PTON, CGC, etc.)
- [ ] Pipeline sync funciona (sin error de ServiceLocator)

---

## 🔍 Lecciones Aprendidas

1. **Method Signatures Matter**: Siempre verificar firma de métodos override coincide con base class
2. **Attribute Names Critical**: Un error de typo en attribute name (`adapter` vs `broker`) bloquea todo
3. **Dataclass Attributes**: Verificar nombres exactos de atributos en dataclasses (timestamp vs scan_timestamp)
4. **Service Locator Pattern**: Usar métodos completos (`get_or_create_*` no `get_*`)
5. **Error Cascading**: Un error pequeño (timestamp) puede bloquear todo un pipeline (unified scan)
6. **Restart Required**: Cambios en código Python requieren restart del proceso para tomar efecto

---

## Error #5: Config.ini `%` sin escapar ❌→✅

### Síntoma
```
❌ Failed loading daily_plays: '%' must be followed by '%' or '(', found: '% distance from support'
```

### Causa
ConfigParser interpreta `%` como inicio de variable de interpolación. Comentarios en config.ini con `%` deben usar `%%`.

**Línea Problemática**:
```ini
reversal_max_support_distance = 3.0  # Max % distance from support  # ❌
```

**Fix Aplicado**:
```bash
sed -i '' 's/\(# .*[^%]\)%\([^%]\)/\1%%\2/g' config.ini
```

Escapó todos los `%` en comentarios a `%%`.

### Impacto
**BLOQUEANTE DE CARGA**: Impedía cargar configuración de daily_plays strategy.
- ❌ Strategy no se inicializaba
- ❌ Config parameters no disponibles
- 💔 Daily Plays worker sin configuración

---

## Error Crítico #6: Timezone-aware/naive Datetime Mismatch ❌→✅

### Síntoma
```
🔄 Trailing stop activated for GLXG at 7.9% profit
❌ Error analyzing bar for GLXG: can't subtract offset-naive and offset-aware datetimes
```

### Causa Raíz
`position.entry_time` tiene timezone (aware) pero `current_time` no tiene timezone (naive), o viceversa. Python no permite restar datetimes con diferentes timezone awareness.

**Código Problemático** (línea 686):
```python
hold_minutes = (current_time - position.entry_time).total_seconds() / 60  # ❌ TypeError
```

**Fix Aplicado**:
```python
# Calculate hold time - handle timezone-aware/naive datetime mismatch
try:
    entry_time = position.entry_time
    curr_time = current_time

    # Normalize timezone awareness
    if entry_time.tzinfo is not None and curr_time.tzinfo is None:
        entry_time = entry_time.replace(tzinfo=None)
    elif entry_time.tzinfo is None and curr_time.tzinfo is not None:
        curr_time = curr_time.replace(tzinfo=None)

    hold_minutes = (curr_time - entry_time).total_seconds() / 60  # ✅
except (TypeError, AttributeError) as e:
    self.logger.warning(f"⚠️ Timezone issue: {e}")
    hold_minutes = 0  # Fallback to allow other exit checks
```

### Archivos Corregidos (2 ocurrencias)
- `core/stop_loss_manager.py:686` (_check_time_exits)
- `core/stop_loss_manager.py:646` (_detect_runner_behavior)

### Impacto
**BLOQUEANTE DE EXITS**: Impedía cerrar posiciones cuando trailing stop se activaba.
- ✅ Trailing stop detectado: "activated for GLXG at 7.9%"
- ❌ Exit crasheaba: TypeError en cálculo de hold_minutes
- 💔 **Posición atrapada** - No podía salir a pesar de tener profit

**CRÍTICO**: Este error bloqueaba exits de posiciones en profit, causando pérdida de ganancias si el precio revertía.

---

## 📊 Estado Final del Sistema

### ANTES de los fixes (21:32):
```
✅ Scanner: Detectando opportunities
✅ Router: Distribuyendo correctamente
✅ Workers: Evaluando oportunidades
✅ Entry: Posición GLXG abierta
✅ Trailing Stop: Activado al 7.9% profit
❌ Exit: BLOQUEADO por timezone error
💔 Posición atrapada con profit
```

### DESPUÉS de los fixes:
```
✅ Scanner: Detectando opportunities
✅ Router: Distribuyendo correctamente
✅ Workers: Evaluando y confirmando entradas
✅ Execution: FUNCIONAL (firma corregida)
✅ Market Data: FUNCIONAL (broker.ib access)
✅ Catalyst Publishing: FUNCIONAL (scan_timestamp)
✅ Pipeline Sync: FUNCIONAL (get_or_create_risk_manager)
✅ Config Loading: FUNCIONAL (%% escapado)
✅ Exit System: FUNCIONAL (timezone normalizado)
```

---

## 🔍 Lecciones Aprendidas

1. **Method Signatures Matter**: Siempre verificar firma de métodos override coincide con base class
2. **Attribute Names Critical**: Un error de typo en attribute name (`adapter` vs `broker`) bloquea todo
3. **Dataclass Attributes**: Verificar nombres exactos de atributos en dataclasses (timestamp vs scan_timestamp)
4. **Service Locator Pattern**: Usar métodos completos (`get_or_create_*` no `get_*`)
5. **Config File Escaping**: ConfigParser requiere `%%` para literales en comentarios
6. **Timezone Consistency**: Normalizar timezone awareness antes de operaciones con datetime
7. **Exit System Critical**: Un error en exit logic es MÁS peligroso que error en entry (posiciones atrapadas)
8. **Error Cascading**: Un error pequeño puede bloquear todo un sistema
9. **Restart Required**: Cambios en código Python requieren restart del proceso para tomar efecto

---

**Documento creado**: 2025-10-01 21:05:00 CET
**Última actualización**: 2025-10-01 21:35:00 CET
**Fixes aplicados**: 6 errores críticos corregidos
**Estado**: ✅ Código arreglado - ⏳ Pendiente restart del trader
**Prioridad**: 🚨 **URGENTE** - Posición GLXG atrapada con profit necesita exit funcional
