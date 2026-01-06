# Quick Start: TP/SL Optimization System

**Date:** 2025-11-09
**Status:** ✅ Ready to Use

---

## 🚀 Start Collecting Data NOW

### Step 1: Start Your Trading System (Como siempre)

```bash
cd CLAUDE/trading_system_v3
python simple_main.py
```

Esto inicia tu sistema de trading normal con scanner y trader.

### Step 2: Start the Forward Return Tracker (En paralelo)

**Abre un NUEVO terminal** y ejecuta:

```bash
cd CLAUDE/trading_system_v3
python run_forward_tracker.py
```

Este tracker automáticamente:
- Monitoriza todas las señales generadas por tus workers
- Captura precios a 5m, 15m, 60m, 240m después de cada señal
- Calcula MFE/MAE (Max Favorable/Adverse Excursion)
- Guarda resultados en `trading_data.db`

### Step 3: Déjalo Correr 2-4 Semanas

Ambos procesos deben correr continuamente para recopilar datos de optimización.

**Monitoriza logs:**
```bash
# Sistema principal (trader + scanner)
tail -f logs/trader.log

# Forward tracker
tail -f forward_tracker.log
```

---

## 📊 Después de 2-4 Semanas: Analizar Datos

### Verificar Estado de Recopilación de Datos

```bash
# ¿Cuántas señales se han rastreado?
sqlite3 trading_data.db "SELECT COUNT(*) FROM signal_events WHERE forward_tracked_at IS NOT NULL;"

# Ver muestra de señales rastreadas
sqlite3 trading_data.db "SELECT symbol, worker_name, forward_return_60m * 100 as return_pct, mfe_percent, mae_percent FROM signal_events WHERE forward_tracked_at IS NOT NULL ORDER BY timestamp DESC LIMIT 10;"
```

### Ejecutar TP/SL Optimizer

**Analizar todos los workers:**
```bash
python analysis/tp_sl_optimizer.py --period 30
```

**Analizar worker específico:**
```bash
python analysis/tp_sl_optimizer.py --worker daily_plays --confidence high
```

**Output Ejemplo:**
```
================================================================================
TP/SL OPTIMIZATION REPORT: daily_plays (high)
================================================================================

Sample Size: 87
Overall Win Rate: 62.1%

Forward Return Percentiles (60min):
  P60: +8.2%
  P70: +11.5%
  P75: +13.8%
  P80: +16.2%

OPTIMAL TP/SL:
  TP: 13.8%
  SL: 3.4%
  R:R: 4.06:1
  Expected Win Rate: 68.5%
  Expected Expectancy: +6.24% per trade
```

---

## 🔧 Aplicar Valores Optimizados

Basándote en las recomendaciones del optimizer, actualiza tu `config.ini`:

**Antes (ejemplo):**
```ini
[DAILY_PLAYS_STRATEGY]
stop_loss_pct = 0.05  # 5%
take_profit_pct = 0.20  # 20%
```

**Después (basado en análisis):**
```ini
[DAILY_PLAYS_STRATEGY]
stop_loss_pct = 0.034  # 3.4% (optimizado de datos reales)
take_profit_pct = 0.138  # 13.8% (optimizado de datos reales)
```

---

## 📁 Referencia de Archivos

| Componente | Archivo | Propósito |
|-----------|------|---------|
| **Event Logger** | [core/trade_event_logger.py](core/trade_event_logger.py) | Loggea todas las señales (ya integrado) |
| **Forward Tracker** | [core/forward_return_tracker.py](core/forward_return_tracker.py) | Captura forward returns |
| **Production Runner** | [run_forward_tracker.py](run_forward_tracker.py) | Ejecuta esto en paralelo con simple_main.py |
| **Optimizer** | [analysis/tp_sl_optimizer.py](analysis/tp_sl_optimizer.py) | Analiza datos y recomienda TP/SL |
| **Database Schema** | [database/schema_extensions.sql](database/schema_extensions.sql) | Ya aplicado a trading_data.db |
| **Guía Completa** | [docs/FORWARD_RETURN_TRACKER_GUIDE.md](docs/FORWARD_RETURN_TRACKER_GUIDE.md) | Documentación completa |
| **System Overview** | [docs/TP_SL_OPTIMIZATION_SYSTEM.md](docs/TP_SL_OPTIMIZATION_SYSTEM.md) | Arquitectura e implementación |

---

## ⚠️ Notas Importantes

1. **Ambos procesos deben correr simultáneamente**
   - Sistema principal (`simple_main.py`) genera señales
   - Forward tracker captura precios futuros

2. **Requisitos mínimos de datos**
   - Al menos 20 señales por worker/confidence bucket
   - Recomendado: 50-100 señales para estadísticas fiables
   - Marco temporal: 2-4 semanas

3. **No detener/iniciar frecuentemente**
   - Ejecución continua = mejores datos
   - Brechas en tracking = análisis incompleto

4. **Revisar logs regularmente**
   ```bash
   # ¿Se están generando señales?
   grep "Signal event logged" logs/trader.log | tail

   # ¿Se están rastreando forward returns?
   grep "Forward tracking completed" forward_tracker.log | tail
   ```

---

## 🐛 Troubleshooting Rápido

### ¿No hay señales en base de datos?

```sql
SELECT COUNT(*) FROM signal_events;
```

Si es 0 o muy pocas:
- Verifica que `simple_main.py` esté corriendo
- Verifica que workers estén habilitados en config.ini
- Verifica que scanner encuentre oportunidades

### ¿No se está haciendo forward tracking?

```sql
SELECT COUNT(*) FROM signal_events WHERE forward_tracked_at IS NOT NULL;
```

Si es 0:
- Verifica que forward tracker esté corriendo: `ps aux | grep forward_tracker`
- Revisa logs del tracker: `tail -f forward_tracker.log`
- Las señales deben tener > 5 minutos de antigüedad para ser rastreadas

### ¿El tracker crashea?

```bash
# Ejecutar con debug logging
python run_forward_tracker.py --log-level DEBUG

# Revisar errores
grep ERROR forward_tracker.log
```

---

## 🎯 Criterios de Éxito

Después de 2-4 semanas, deberías tener:

✅ **100+ señales** en tabla `signal_events`
✅ **80%+ con forward tracking** (algunas pueden fallar por disponibilidad de datos)
✅ **Múltiples workers** con datos suficientes (20+ señales cada uno)
✅ **Recomendaciones TP/SL** del optimizer con expectancy positiva

---

## 🔄 Workflow Completo

```
DÍA 1:
Terminal 1: python simple_main.py
Terminal 2: python run_forward_tracker.py
         ↓
SEMANAS 2-4:
Dejar corriendo ambos procesos
Monitorizar logs/trader.log y forward_tracker.log
         ↓
SEMANA 4+:
python analysis/tp_sl_optimizer.py --period 30
Revisar recomendaciones
Actualizar config.ini
         ↓
REPETIR:
Cada 2-4 semanas re-analizar y ajustar
```

---

## 📞 ¿Necesitas Ayuda?

- **Documentación completa:** [docs/FORWARD_RETURN_TRACKER_GUIDE.md](docs/FORWARD_RETURN_TRACKER_GUIDE.md)
- **System overview:** [docs/TP_SL_OPTIMIZATION_SYSTEM.md](docs/TP_SL_OPTIMIZATION_SYSTEM.md)
- **Test del tracker:** `python scripts/testing/test_forward_return_tracker.py`

---

**Recuerda:** El objetivo es reemplazar valores TP/SL "supuestos" con valores basados en datos del rendimiento REAL de TU sistema. ¡Empieza a recopilar datos hoy!
