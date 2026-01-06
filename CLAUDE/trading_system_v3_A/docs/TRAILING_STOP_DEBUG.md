# 🔍 TRAILING STOP DEBUG GUIDE

**Problema reportado:** ASTI el 23/12 - Segunda operación no sale correctamente cuando debería

**Síntomas:**
- Entrada a las 14:52
- Precio sube de ~$4.98 a ~$7.21 (+44.8%)
- Precio baja a ~$4.90 (-1.6% del entry)
- Sale a las 16:31 (casi 2 horas después del pico)
- **Comportamiento esperado:** Debería salir con trailing stop cuando el precio cae desde el pico

---

## ✅ DEBUG LOGGING AÑADIDO

He añadido logs de debug detallados en [worker_stop_manager.py](strategies/workers/worker_stop_manager.py):

### 1. **Actualización de Peak PnL** (Línea 192)
```python
print(f"[DEBUG] {symbol}: NEW PEAK PnL {pnl_pct:.2f}% (previous: {highest_pnl:.2f}%)")
```
Esto muestra CADA VEZ que el PnL alcanza un nuevo máximo.

### 2. **Check de Exit** (Línea 180)
```python
print(f"[DEBUG] check_exit called: symbol={symbol}, price=${current_price:.2f}, entry=${entry_price:.2f}, _current_time={self._current_time}")
```
Muestra cada llamada a `check_exit` con el timestamp.

### 3. **Trailing Stop Check** (Línea 248)
```python
print(f"[DEBUG] Trailing check: highest={highest_pnl_float:.2f}%, current={pnl_pct:.2f}%, trigger={trailing_trigger:.2f}%")
```
Muestra la lógica del trailing stop cuando está activo.

### 4. **Take Profit Check** (Línea 327)
```python
print(f"[DEBUG] Take Profit check: pnl={pnl_pct:.2f}%, target={tp_pct:.2f}%")
```

---

## 🧪 CÓMO DEBUGGEAR EN WORKERLAB

### Paso 1: Abrir WorkerLab
```
http://localhost:5173/worker-lab
```

### Paso 2: Configurar el test
- **Date:** 2025-12-23
- **Symbol:** ASTI
- **Worker:** Buy & Hold
- **Layers:** Activa VWAP, Quality Score, SL & TP

### Paso 3: Abrir Developer Console (F12)
Antes de ejecutar, abre la consola del navegador para ver los logs de JavaScript.

### Paso 4: Ejecutar "Run Simulation"

### Paso 5: Revisar logs en la columna derecha
Busca estos patrones:

#### ✅ **Logs de entrada correctos:**
```
✅✅✅ ASTI: VWAP MOMENTUM ENTRY ✅✅✅
   💰 Price: $4.98
   📈 VWAP: $4.85 (+2.6%)
   ...
```

#### 🔍 **Logs de Peak PnL (deberías ver varios):**
```
[DEBUG] ASTI: NEW PEAK PnL 5.23% (previous: 0.00%)
[DEBUG] ASTI: NEW PEAK PnL 12.45% (previous: 5.23%)
[DEBUG] ASTI: NEW PEAK PnL 25.10% (previous: 12.45%)
[DEBUG] ASTI: NEW PEAK PnL 44.78% (previous: 25.10%)  <-- Este es el pico ($7.21)
```

#### 🔍 **Logs de Trailing Stop (cuando el precio cae):**
```
[DEBUG] Trailing check: highest=44.78%, current=42.50%, trigger=41.78%
[DEBUG] Trailing check: highest=44.78%, current=38.20%, trigger=41.78%
[DEBUG] Trailing check: highest=44.78%, current=35.10%, trigger=41.78%  <-- Debería salir aquí
```

**Configuración del trailing stop:**
- Activación: **8%** (se activa cuando PnL > 8%)
- Distancia: **3%** (sale si cae 3% desde el pico)

**Ejemplo:**
- Pico: 44.78%
- Trigger: 44.78% - 3% = **41.78%**
- Si PnL cae a 41.78% o menos → **EXIT con TRAILING_STOP**

---

## 🔍 POSIBLES CAUSAS DEL PROBLEMA

### 1. **Timestamp no se está inyectando correctamente**
Si `_current_time` no se actualiza, el check_exit podría estar usando tiempos incorrectos.

**Verificar:**
```
[DEBUG] check_exit called: ... _current_time=2025-12-23 14:52:00-05:00
[DEBUG] check_exit called: ... _current_time=2025-12-23 14:53:00-05:00
```
Los timestamps deberían **avanzar** con cada barra.

### 2. **highest_pnl no se está actualizando**
Si no ves logs de "NEW PEAK PnL", significa que el diccionario `highest_pnl` no se está actualizando.

**Verificar:**
Deberías ver múltiples líneas de "NEW PEAK PnL" a medida que el precio sube.

### 3. **Trailing stop no se está evaluando**
Si no ves logs de "Trailing check", el trailing stop no se está ejecutando.

**Verificar:**
- ¿El trailing activation (8%) se alcanzó? (Pico de 44.78% > 8% ✅)
- ¿El código está llegando a la línea 248?

### 4. **El exit se llama pero no se aplica**
Posiblemente `should_exit` retorna `True` pero `run_worker_test.py` no lo procesa correctamente.

**Verificar en [run_worker_test.py](tools/run_worker_test.py:407-415):**
```python
if should_exit:
    decision = "EXIT"
    del worker.active_positions[symbol]
    if hasattr(worker, 'stop_manager'):
        worker.stop_manager.unregister_position(symbol)
```

---

## 📊 EJEMPLO DE OUTPUT ESPERADO

Para ASTI subiendo de $4.98 a $7.21 y bajando a $4.90:

```
[10:08] ✅✅✅ ASTI: VWAP MOMENTUM ENTRY ✅✅✅ Price: $4.98
[10:09] [DEBUG] check_exit called: price=$5.05, entry=$4.98, _current_time=2025-12-23 10:09:00-05:00
[10:09] [DEBUG] ASTI: NEW PEAK PnL 1.41% (previous: 0.00%)
[10:10] [DEBUG] ASTI: NEW PEAK PnL 3.21% (previous: 1.41%)
...
[14:25] [DEBUG] ASTI: NEW PEAK PnL 44.78% (previous: 42.12%)  <-- Pico en $7.21
[14:26] [DEBUG] Trailing check: highest=44.78%, current=43.57%, trigger=41.78%
[14:27] [DEBUG] Trailing check: highest=44.78%, current=42.17%, trigger=41.78%
[14:28] [DEBUG] Trailing check: highest=44.78%, current=40.96%, trigger=41.78%  <-- PnL < trigger
[14:28] 📤 ASTI: Exit triggered: TRAILING_STOP (Peak: +44.78%, Current: +40.96%)
[14:28] EXIT at $7.02 (PnL: +40.96%)
```

---

## 🐛 SI EL PROBLEMA PERSISTE

### Opción 1: Envíame los logs completos
Copia todos los logs de la columna derecha de WorkerLab y pégalos aquí.

### Opción 2: Captura de pantalla
Haz screenshot del gráfico mostrando:
- Las velas de precio
- La línea VWAP (cyan)
- Las líneas SL/TP (red/green dashed)
- Los marcadores de Entry/Exit

### Opción 3: Verificar configuración
Revisa [config.ini](config.ini) sección `[BUY_AND_HOLD_WORKER]`:
```ini
[BUY_AND_HOLD_WORKER]
enabled = true
trailing_activation = 8.0
trailing_distance = 3.0
max_position_hours = 24.0
```

---

## 📝 ANÁLISIS PRELIMINAR

Basándome en tu descripción:
- Entry: $4.98 a las 14:52
- Pico: $7.21 (PnL +44.78%)
- Exit: $4.90 (PnL -1.61%) a las 16:31

**Esto NO es normal.** El trailing stop debería haber salido alrededor de $6.98-$7.00 (PnL ~41.78%).

**Posibles hipótesis:**
1. ❌ Trailing stop no se activó porque `highest_pnl` no se guardó
2. ❌ Los halts interfirieron con la actualización de `highest_pnl`
3. ❌ El timestamp `_current_time` no se inyectó correctamente
4. ❌ El check_exit no se llamó en cada barra durante el replay

**Ejecuta el test y envíame los logs para confirmar cuál es la causa.**

---

**Generado:** 30 Diciembre 2025
**Sistema:** trading_system_v3
**Autor:** Claude Sonnet 4.5
