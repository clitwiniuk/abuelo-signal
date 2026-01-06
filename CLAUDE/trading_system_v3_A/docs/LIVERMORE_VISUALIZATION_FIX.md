# 🎩 LIVERMORE INTRADAY VISUALIZATION FIX

**Fecha:** 30 Diciembre 2025
**Cambio:** Fixed Livermore indicator exposure for WorkerLab visualization

---

## 🎯 PROBLEMA IDENTIFICADO

**Usuario reportó:**
> "No, no se ve nada, solo el precio. No entiendo, con buy & hols lo hicistes muy bien y funciona pero con este otro worker no se ven estos datos de entrada y salida y los parametros que el worker utiliza para hacer la entrada y los TP y SL. Porque?"

### Root Cause Analysis

El worker Livermore Intraday usa un **state machine** con **persistent cache** que no funciona bien en replay mode:

```
LIVERMORE STATE MACHINE:
┌─────────────┐
│ OBSERVATION │ <- Detecta impulse (3%+ move, 1.5x volume)
└──────┬──────┘
       │
       v
┌─────────────┐
│    PAUSE    │ <- Consolida (retrace < 40%, aguanta soporte)
└──────┬──────┘
       │
       v
┌─────────────┐
│  BREAKOUT   │ <- Rompe pause_high con volumen
└─────────────┘
```

**Problema en Replay Mode:**
1. El worker crea un `candidate` cuando detecta un impulso
2. Este candidate se guarda en persistent cache
3. Pero en replay mode, cada barra es procesada secuencialmente UNA SOLA VEZ
4. El worker NO vuelve a ver el mismo símbolo hasta la siguiente barra
5. A diferencia de Buy & Hold que calcula y expone VWAP en CADA barra, Livermore solo exponía indicadores cuando recuperaba un candidate existente

**Flujo Problemático Anterior:**

```python
# should_enter() - OLD FLOW
candidate = self._get_candidate(symbol)
if candidate is None:
    self._evaluate_new_candidate(...)  # Creates candidate, saves to cache
    self._expose_indicators(opportunity, None)  # ❌ OVERWRITES with None!
    return False
```

El problema: `_expose_indicators(opportunity, None)` sobrescribía los indicadores que se acababan de establecer en `_evaluate_new_candidate()`.

---

## ✅ SOLUCIÓN IMPLEMENTADA

### Fix 1: Re-fetch Candidate After Creation

**Cambio en `should_enter()` (lines 146-154):**

```python
# Case 0: New Candidate
candidate = self._get_candidate(symbol)
if candidate is None:
    self._evaluate_new_candidate(symbol, bars, current_price, opportunity)
    # Re-fetch candidate in case it was just created
    candidate = self._get_candidate(symbol)
    # Expose indicators (will be None if no impulse detected, or populated if impulse detected)
    self._expose_indicators(opportunity, candidate)
    return False # Never enter on first sight
```

**Ventaja:** Si `_evaluate_new_candidate()` detectó un impulso y creó un candidate, ahora lo recuperamos inmediatamente y exponemos sus indicadores correctamente.

---

### Fix 2: Remove Duplicate Indicator Code

**Cambio en `_evaluate_new_candidate()` (lines 202-213):**

**ANTES:**
```python
self._set_candidate(symbol, candidate)

# IMPORTANT: Also expose these initial levels immediately for visualization
opportunity['livermore_phase'] = candidate.phase.value
opportunity['livermore_initial_high'] = candidate.initial_high
opportunity['livermore_initial_low'] = candidate.initial_low
opportunity['livermore_pause_high'] = None
opportunity['livermore_pause_low'] = None

self.logger.info(...)
```

**AHORA:**
```python
self._set_candidate(symbol, candidate)  # Save to persistent cache
self.logger.info(f"👀 {symbol}: Added to Livermore Watchlist (Impulse: {impulse_pct:.1f}%)")
```

**Razón:** Los indicadores ahora se exponen en `should_enter()` mediante `_expose_indicators()`, no necesitamos duplicar la lógica.

---

### Fix 3: Use Cache Deletion Methods Consistently

**Cambio en `_update_observation_phase()` (lines 223-227):**

**ANTES:**
```python
del self.watched_candidates[candidate.symbol]
```

**AHORA:**
```python
self._remove_candidate(candidate.symbol)
```

**Razón:** Usar siempre los métodos de cache (`_remove_candidate()`) en lugar de manipular `self.watched_candidates` directamente, para garantizar consistencia con el persistent cache.

---

### Fix 4: Remove Premature Deletion in Breakout

**Cambio en `_check_breakout_entry()` (lines 264-267):**

**ANTES:**
```python
if vol_ratio >= self.breakout_vol_ratio:
    # 3. Update candidate status (so we don't buy twice)
    del self.watched_candidates[candidate.symbol] # Remove from watch, now active
    return True
```

**AHORA:**
```python
if vol_ratio >= self.breakout_vol_ratio:
    # 3. Update candidate status (so we don't buy twice)
    # Note: Will be removed in should_enter() after this returns True
    return True
```

**Razón:** La eliminación del candidate del cache se hace en `should_enter()` (line 180) DESPUÉS de establecer los precios de SL/TP, para evitar race conditions.

---

## 📊 FLUJO CORRECTO AHORA

### Escenario 1: Primera vez viendo ASTI

```
Bar 1 (09:30):
  should_enter() called
  candidate = None (primera vez)
  _evaluate_new_candidate() called
    -> Detecta impulse: 3.5% move, 2.0x volume
    -> Crea LivermoreCandidate(phase=OBSERVATION, initial_high=5.05, initial_low=4.87)
    -> Guarda en cache con _set_candidate()
  candidate = _get_candidate()  # ✅ Re-fetch (ahora existe!)
  _expose_indicators(opportunity, candidate)  # ✅ Expone initial_high, initial_low
  return False
```

**Resultado:** WorkerLab recibe:
```json
{
  "livermore_phase": "OBSERVATION",
  "livermore_initial_high": 5.05,
  "livermore_initial_low": 4.87,
  "livermore_pause_high": null,
  "livermore_pause_low": null
}
```

**Chart muestra:** 2 líneas (initial_high en naranja, initial_low en verde)

---

### Escenario 2: Segunda barra (candidate existe)

```
Bar 2 (09:31):
  should_enter() called
  candidate = _get_candidate()  # ✅ Exists (OBSERVATION phase)
  candidate.last_update = now()
  _set_candidate()  # Update timestamp
  _expose_indicators(opportunity, candidate)  # Expone niveles actuales

  if phase == OBSERVATION:
    _update_observation_phase()
      -> current_price = 5.02 < initial_high (5.05)
      -> Promote to PAUSE phase
      -> pause_high = 5.05, pause_low = 4.95
    _set_candidate()  # Save phase transition
    _expose_indicators()  # ✅ Actualiza con pause levels
  return False
```

**Resultado:** WorkerLab recibe:
```json
{
  "livermore_phase": "PAUSE",
  "livermore_initial_high": 5.05,
  "livermore_initial_low": 4.87,
  "livermore_pause_high": 5.05,
  "livermore_pause_low": 4.95
}
```

**Chart muestra:** 4 líneas (initial_high, initial_low, pause_high azul, pause_low roja)

---

### Escenario 3: Breakout Entry

```
Bar 5 (09:34):
  should_enter() called
  candidate = _get_candidate()  # ✅ Exists (PAUSE phase)
  _expose_indicators(opportunity, candidate)

  if phase == PAUSE:
    entered = _check_breakout_entry()
      -> current_price = 5.12 > pause_high (5.05) ✅
      -> vol_ratio = 1.5 >= 1.2 ✅
      -> return True

    if entered:
      opportunity['stop_loss_price'] = 4.95  # pause_low
      opportunity['take_profit_price'] = 5.89  # 15% above entry
      opportunity['strategy_note'] = "Livermore Breakout"
      _remove_candidate(symbol)  # ✅ Remove from cache
      return True  # ✅ ENTER!
```

**Resultado:** Entrada ejecutada, markers en chart muestran:
- Green arrow UP en 5.12 (entry)
- Red line en 4.95 (SL)
- Green line en 5.89 (TP inicial)

---

## 🎨 VISUALIZACIÓN EN WORKERLAB

### Chart Layers:

1. **Price (Candlesticks)** - Siempre visible
2. **Initial High (Orange Line)** - Top del impulse inicial
3. **Initial Low (Green Line)** - Bottom del impulse inicial
4. **Pause High (Blue Line)** - Nivel de breakout (resistance)
5. **Pause Low (Red Line)** - Stop loss técnico (pivot support)

### Checkbox en WorkerLabView.vue:

```vue
<label class="checkbox-label">
  <input type="checkbox" v-model="showLivermore" />
  Livermore Levels (Impulse/Pause)
</label>
```

### Legend:

```
🟠 Initial High  (Top del impulse)
🟢 Initial Low   (Bottom del impulse)
🔵 Pause High    (Breakout level)
🔴 Pause Low     (Technical stop)
```

---

## 🧪 CÓMO PROBAR

### 1. Ejecutar WorkerLab con ASTI 23/12:

```
http://localhost:5173/worker-lab
```

**Settings:**
- **Date:** 2025-12-23
- **Symbol:** ASTI
- **Worker:** Livermore Intraday
- **Layers:** Check "Livermore Levels"

### 2. Verificar en Chart:

Deberías ver:
- **09:30-09:35:** Orange/Green lines aparecen (initial_high/low)
- **09:36:** Blue/Red lines aparecen cuando entra en PAUSE
- **09:40:** Green arrow UP cuando rompe pause_high
- **Durante trade:** Red line (SL) y Green line (TP)

### 3. Verificar en Logs:

```
[09:30 ET] 👀 ASTI: Added to Livermore Watchlist (Impulse: 3.5%)
[09:36 ET] ⏸️ ASTI: Entering PAUSE phase. Watch for break of 5.05
[09:40 ET] 🎩 ASTI: LIVERMORE ENTRY TRIGGERED! Breakout of 5.05
```

---

## 📝 COMPARACIÓN CON BUY & HOLD

### Buy & Hold (VWAP Strategy):

**Indicators expuestos cada barra:**
- `vwap_value` - Calculado en cada tick
- `price_above_vwap_pct` - Calculado en cada tick
- `quality_score` - Calculado en cada tick
- `stop_loss_price` - Solo cuando pasa filtros
- `take_profit_price` - Solo cuando pasa filtros

**Simplicidad:** Todos los indicadores son **stateless** - se calculan independientemente en cada barra.

---

### Livermore Intraday (State Machine):

**Indicators expuestos:**
- `livermore_phase` - OBSERVATION, PAUSE, etc.
- `livermore_initial_high` - Persiste desde detection
- `livermore_initial_low` - Persiste desde detection
- `livermore_pause_high` - Aparece en PAUSE phase
- `livermore_pause_low` - Aparece en PAUSE phase

**Complejidad:** Los indicadores son **stateful** - dependen del histórico del candidate en el cache.

**Fix aplicado:** Ahora re-fetching candidate inmediatamente después de crearlo para garantizar que los indicadores se expongan correctamente en el primer tick.

---

## ⚡ PERFORMANCE

**Cambio mínimo:**
- Solo añadido 1 llamada adicional a `_get_candidate()` por símbolo nuevo
- Costo: O(1) dict lookup en cache
- Sin impacto en latencia

---

## 🎯 IMPACTO ESPERADO

### Antes del fix:
- ❌ No se veían niveles de Livermore en chart
- ❌ Imposible debuggear por qué no entraba
- ❌ No se veían initial_high/low ni pause levels

### Después del fix:
- ✅ Niveles visibles desde primera detección de impulse
- ✅ Puedes ver exactamente cuándo entra en PAUSE
- ✅ Puedes ver el breakout level (pause_high) antes del entry
- ✅ Debuggability completa del state machine

---

## 📚 ARCHIVOS MODIFICADOS

### [strategies/workers/livermore_intraday_worker_logic.py](strategies/workers/livermore_intraday_worker_logic.py)

**Líneas modificadas:**
- **146-154:** `should_enter()` - Re-fetch candidate after creation
- **202-213:** `_evaluate_new_candidate()` - Removed duplicate indicator exposure
- **223-227:** `_update_observation_phase()` - Use `_remove_candidate()` instead of `del`
- **264-267:** `_check_breakout_entry()` - Remove premature deletion comment

---

## 🔄 ROLLBACK (Si es necesario)

Si prefieres volver a la versión anterior:

```bash
git checkout HEAD~1 -- strategies/workers/livermore_intraday_worker_logic.py
```

---

## ✅ VALIDACIÓN

Para validar que el fix funciona:

1. **Ejecutar test con ASTI 23/12** en WorkerLab
2. **Verificar chart** - Deberías ver 2-4 líneas (initial_high/low, pause_high/low)
3. **Verificar logs** - Buscar "Added to Livermore Watchlist" y "Entering PAUSE phase"
4. **Verificar browser console** - Buscar "[Livermore] First indicator with Livermore data"

---

**Generado:** 30 Diciembre 2025
**Sistema:** trading_system_v3
**Autor:** Claude Sonnet 4.5
**Cambio:** Livermore Intraday visualization fix for WorkerLab
