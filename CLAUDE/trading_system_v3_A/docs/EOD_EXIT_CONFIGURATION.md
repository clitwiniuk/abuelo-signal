# End-of-Day Exit Configuration (Centralizado)

## ✅ Configuración Unificada

Toda la configuración de horarios de cierre está centralizada en **un único lugar**: `config.ini`

### 📍 Ubicación Central

**Archivo:** `config.ini`
**Sección:** `[GLOBAL]`
**Línea 87:**

```ini
end_of_day_exit_time = 15:58
```

---

## 🕐 Horarios Configurados

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `end_of_day_exit_time` | **15:58 ET** | Hora de cierre forzado de posiciones day trading |
| Hora España | **21:58** | (ET + 6 horas) |
| `no_entry_after` | **15:50 ET** | No nuevas entradas después de esta hora |

---

## 🔄 Lectura Automática

El sistema lee automáticamente esta configuración en:

**Archivo:** `strategies/workers/worker_stop_manager.py`
**Función:** `create_worker_stop_manager()`
**Líneas 312-316:**

```python
# Read end_of_day_exit_time from config (centralized)
eod_time_str = config_obj.get('GLOBAL', 'end_of_day_exit_time', fallback='15:58')
# Convert HH:MM to decimal hours (15:58 -> 15.97)
hours, minutes = map(int, eod_time_str.split(':'))
end_of_day_hour = hours + (minutes / 60.0)
```

---

## ✅ Workers que Usan EOD Exit

Todos los workers de **day trading** usan esta configuración centralizada:

1. ✅ **GAP_GO_STRATEGY** - Gap & Go pattern
2. ✅ **MACDV_STRATEGY** - MACDV confirmation pattern
3. ✅ **BULL_FLAG_STRATEGY** - Bull flag pattern
4. ✅ **DAILY_PLAYS_STRATEGY** - Daily consolidation plays

**Verificado:** Test `tests/test_eod_configuration.py` confirma que todos leen de config.ini

---

## ❌ Swing Trading NO Usa EOD Exit

**Importante:** El sistema de swing trading **NO cierra posiciones al final del día**.

- ✅ Swing positions se mantienen durante días/semanas
- ✅ Solo se cierran por: stop loss, target profit, trailing stop, o tiempo máximo
- ✅ NO hay `END_OF_DAY` exit en `ConsolidationBreakoutWorker`

---

## 🔧 Cómo Modificar el Horario

Para cambiar la hora de cierre de day trading:

1. Editar **solo** `config.ini` línea 87:
   ```ini
   end_of_day_exit_time = 15:55  # Ejemplo: cerrar 3 min antes
   ```

2. Reiniciar el sistema

3. Verificar con test:
   ```bash
   PYTHONPATH=. python tests/test_eod_configuration.py
   ```

**⚠️ NO modificar valores hardcodeados en el código** - ahora todo se lee de config.ini

---

## 📊 Prioridad de Exits

Order de evaluación en `WorkerStopManager.check_exit()`:

1. **FOMO Exhaustion** (prioridad 0) - Detección de agotamiento
2. **Trailing Stop** (prioridad 1) - Protege ganancias
3. **Take Profit** - Target alcanzado
4. **Stop Loss** - Protege capital
5. **Time Limit** - Posición muy antigua
6. **END_OF_DAY** (prioridad 5) - Cierre forzado horario ← **ESTO**

---

## 🧪 Test de Verificación

**Archivo:** `tests/test_eod_configuration.py`

```bash
PYTHONPATH=. python tests/test_eod_configuration.py
```

**Output esperado:**
```
✅ GAP_GO_STRATEGY           -> EOD: 15.9667
✅ MACDV_STRATEGY            -> EOD: 15.9667
✅ BULL_FLAG_STRATEGY        -> EOD: 15.9667
✅ DAILY_PLAYS_STRATEGY      -> EOD: 15.9667

🎉 SUCCESS - All workers use centralized EOD time from config.ini
```

---

## 📝 Resumen

- ✅ **Centralizado:** Todo en `config.ini` línea 87
- ✅ **Único valor:** 15:58 ET (21:58 España)
- ✅ **4 workers day trading** usan esta configuración
- ✅ **Swing trading** NO se ve afectado
- ✅ **Fácil modificación:** Solo editar config.ini
- ✅ **Verificado:** Test automático confirma centralización
