# Instrucciones de Uso - Sistema de Backtesting Científico

## 🎯 Objetivo

Este sistema te permite:
1. Ejecutar backtests con el replay system
2. Validar consistencia de workers en múltiples períodos
3. Obtener recomendación clara: mantener/revisar/eliminar cada worker
4. Comparar todos los workers side-by-side

---

## 📋 Archivos Creados

```
backtest_worker_scientific.py  → Backtest individual de 1 worker
backtest_all_workers.py         → Backtest masivo de todos los workers
validate_replay_fidelity.py     → Validación de fidelidad del replay
```

---

## 🚀 Uso Rápido (Mañana cuando no toques nada)

### Opción 1: Backtest de UN worker específico

```bash
# Analizar solo vcp_smallcap
python backtest_worker_scientific.py --worker vcp_smallcap

# Con fechas específicas
python backtest_worker_scientific.py \
    --worker vcp_smallcap \
    --start-date 2024-01-01 \
    --end-date 2025-12-17 \
    --period-months 2

# Guardar resultados en JSON
python backtest_worker_scientific.py \
    --worker vcp_smallcap \
    --output backtest_vcp.json
```

**Output esperado:**
```
================================================================================
BACKTEST CIENTÍFICO - VCP_SMALLCAP
================================================================================

📊 RESULTADOS POR PERÍODO

Período 1: 2024-01-01 to 2024-03-01
   Trades:         12
   P&L:            $89.50
   Win Rate:       66.7%
   Profit Factor:  2.30
   Verdict:        ✅ PASS

Período 2: 2024-03-01 to 2024-05-01
   Trades:         15
   P&L:            $112.00
   Win Rate:       60.0%
   Profit Factor:  2.00
   Verdict:        ✅ PASS

...

================================================================================
🎯 ANÁLISIS DE CONSISTENCIA
================================================================================

Períodos testeados:     3
Total trades:           34
Total P&L:              $173.95
Consistency Score:      100.0%
Avg Win Rate:           64.7%
Avg Profit Factor:      2.15

RECOMENDACIÓN FINAL:    ✅ MANTENER Y ESCALAR
Razón:                  Consistentemente rentable en múltiples períodos
Ajuste de size:         2.0x
```

---

### Opción 2: Backtest de TODOS los workers (RECOMENDADO)

```bash
# Auto-detecta top 10 workers y los analiza
python backtest_all_workers.py

# Especificar workers manualmente
python backtest_all_workers.py \
    --workers vcp_smallcap daily_plays vwap_breakout volume_absorption macdv

# Con rango de fechas
python backtest_all_workers.py \
    --start-date 2024-01-01 \
    --end-date 2025-12-17 \
    --period-months 2
```

**Output esperado:**
```
================================================================================
BACKTESTING MULTI-WORKER - ANÁLISIS COMPARATIVO
================================================================================

Workers a analizar: vcp_smallcap, daily_plays, volume_absorption, macdv, ...

[Ejecuta cada worker individual...]

================================================================================
📊 COMPARATIVE ANALYSIS - ALL WORKERS
================================================================================

RANKING BY PERFORMANCE:
Worker              Action                     Total P&L  Total Trades  Consistency %  Avg WR %  Avg PF  Size Adj  Periods
vcp_smallcap        ✅ MANTENER Y ESCALAR          173.95            34          100.0      64.7    2.15       2.0x        3
daily_plays         ⚠️ MANTENER PERO MONITOREAR    117.51           282           67.0      30.1    1.05       1.0x        3
volume_absorption   ❌ DESHABILITAR               -297.42           132            0.0      31.8    0.89       0.0x        3
macdv               ❌ DESHABILITAR               -271.06           160            0.0      42.5    0.95       0.0x        3

🎯 NEXT ACTIONS:
✅ ESCALAR (1 workers):
   python scripts/update_worker_size.py --worker vcp_smallcap --multiplier 2

❌ DESHABILITAR (2 workers):
   # Editar config.ini: set volume_absorption.enabled = false
   # Editar config.ini: set macdv.enabled = false
```

**Genera también:**
- `backtest_comparison.json` - Datos completos
- `backtest_comparison.html` - Reporte visual bonito

---

## 📊 Interpretación de Resultados

### Métricas Clave

| Métrica | Bueno | Aceptable | Malo |
|---------|-------|-----------|------|
| **Consistency Score** | >75% | 50-75% | <50% |
| **Win Rate** | >50% | 40-50% | <40% |
| **Profit Factor** | >1.5 | 1.2-1.5 | <1.2 |
| **R/R Ratio** | >2:1 | 1.5:1-2:1 | <1.5:1 |
| **Sharpe Ratio** | >1.5 | 1.0-1.5 | <1.0 |

### Verdicts por Período

- **✅ PASS**: Worker cumple criterios mínimos este período
- **⚠️ MARGINAL**: Resultados mixtos, necesita más datos
- **❌ FAIL**: Worker NO cumple criterios mínimos
- **⚠️ INSUF DATA**: Menos de 10 trades, no estadísticamente significativo

### Recomendaciones Finales

#### ✅ MANTENER Y ESCALAR
```
Criterios:
- Consistency ≥75% (pasa en 3+ de 4 períodos)
- Win Rate promedio ≥45%
- Profit Factor promedio ≥1.3

Acción: Aumentar position size 2x
```

#### ⚠️ MANTENER PERO MONITOREAR
```
Criterios:
- Consistency 50-75%
- Win Rate 40-45%
- Profit Factor 1.1-1.3

Acción: Mantener size, monitorear 100 trades más
```

#### ❌ DESHABILITAR
```
Criterios:
- Consistency <50%
- Win Rate <40%
- Profit Factor <1.1

Acción: Deshabilitar inmediatamente
```

---

## 🔧 Validación de Fidelidad (IMPORTANTE)

**Antes de confiar 100% en los backtests**, validar fidelidad del replay:

```bash
# Validar replay para un worker
python validate_replay_fidelity.py --worker vcp_smallcap --days 14

# Validar múltiples workers
for worker in vcp_smallcap daily_plays vwap_breakout; do
    python validate_replay_fidelity.py --worker $worker --days 14
done
```

**Si match rate >95%**: Replay es confiable → Confía en backtests ✅

**Si match rate 80-95%**: Revisar discrepancias → Ajustar si es necesario ⚠️

**Si match rate <80%**: Replay NO confiable → Arreglar primero ❌

---

## 📝 Workflow Recomendado

### DÍA 1 (Hoy - Desarrollo)
```bash
# Ya hecho:
✅ backtest_worker_scientific.py creado
✅ backtest_all_workers.py creado
✅ validate_replay_fidelity.py creado
✅ Sistema listo para usar
```

### DÍA 2 (Mañana - NO tocar configuraciones)
```bash
# 1. Dejar el sistema correr sin modificaciones
# 2. Al final del día, ejecutar validación
python validate_replay_fidelity.py --worker vcp_smallcap --days 1

# 3. Si match >95%, proceder con backtests
python backtest_all_workers.py

# 4. Revisar backtest_comparison.html
# 5. Tomar decisiones basadas en recomendaciones
```

### DÍA 3 (Simplificación)
```bash
# Basado en resultados del backtest:

# Deshabilitar workers perdedores
vim config.ini
# [VOLUME_ABSORPTION_STRATEGY]
# enabled = false  # ← Cambiar a false

# [MACDV_STRATEGY]
# enabled = false  # ← Cambiar a false

# Aumentar size de winners
# [VCP_SMALLCAP_STRATEGY]
# position_size = 200  # ← Duplicar (era 100)

# Restart sistema
pkill -f trader_main.py
python trader_main.py &
```

### DÍA 4-30 (NO TOCAR)
```
- Dejar correr SIN modificaciones
- Recolectar 100+ trades por worker
- Monitorear pero NO modificar
- Solo al final del mes, revisar resultados
```

---

## 🚨 Errores Comunes a Evitar

### ❌ Error #1: Ejecutar backtest el mismo día que modificaste
```
Problema: Configuración del backtest ≠ configuración histórica
Solución: Espera 1 día de operativa estable
```

### ❌ Error #2: Modificar parámetros porque un período falló
```
Problema: Overfitting a un período específico
Solución: Solo confiar si 75%+ de períodos pasan
```

### ❌ Error #3: No validar fidelidad del replay
```
Problema: Basas decisiones en datos incorrectos
Solución: SIEMPRE validar replay primero (match >95%)
```

### ❌ Error #4: Sample size insuficiente
```
Problema: Worker con 5 trades parece bueno (100% WR)
Solución: Mínimo 10 trades por período para validar
```

---

## 💡 Tips Pro

### Tip #1: Análisis Incremental
```bash
# No necesitas analizar todo el historial de golpe
# Empieza con últimos 6 meses

python backtest_worker_scientific.py \
    --worker vcp_smallcap \
    --start-date 2024-06-01 \
    --end-date 2025-12-17

# Si pasa, expande a 12 meses, 24 meses, etc.
```

### Tip #2: Focus en Consistency > Win Rate
```
Worker A: 70% WR en 1 período, 30% en otro → INCONSISTENTE
Worker B: 50% WR en todos los períodos → CONSISTENTE

Prefiere Worker B → Más predecible
```

### Tip #3: Usa HTML Report para decisiones
```bash
# El HTML es más fácil de analizar visualmente
python backtest_all_workers.py

# Abre en browser
open backtest_comparison.html

# Comparte con otros (si trabajas en equipo)
```

---

## 🎯 Resultado Esperado Final

Después de este proceso tendrás:

1. **Lista clara** de workers a mantener (2-5 workers)
2. **Lista clara** de workers a eliminar (10+ workers)
3. **Confianza estadística** en tus decisiones (>95%)
4. **Sistema simplificado** fácil de monitorear
5. **Plan de ejecución** sin modificaciones por 30 días

---

## 📞 Troubleshooting

### Problema: "No data found for worker"
```bash
# Verificar que hay datos OHLC
sqlite3 trading_data.db "SELECT COUNT(*) FROM broker_ohlc;"

# Si 0, el replay no puede funcionar
# Solución: Ejecutar sistema en vivo primero para recolectar OHLC
```

### Problema: "Error loading worker config"
```bash
# El worker puede tener nombre diferente en el código
# Solución: Verificar nombre exacto
ls strategies/workers/*_worker_logic.py

# Usar nombre exacto sin "_worker_logic"
python backtest_worker_scientific.py --worker vcp_smallcap
```

### Problema: Backtest muy lento
```bash
# Reducir período
python backtest_worker_scientific.py \
    --worker vcp_smallcap \
    --period-months 1  # En vez de 2

# O limitar rango de fechas
python backtest_worker_scientific.py \
    --worker vcp_smallcap \
    --start-date 2025-01-01  # Solo últimos meses
```

---

## ✅ Checklist Final

Antes de ejecutar backtests masivos:

- [ ] Sistema corrió al menos 1 día SIN modificaciones
- [ ] Hay datos OHLC en la DB (verificar con SQL)
- [ ] Validaste fidelidad del replay (match >95%)
- [ ] Tienes lista de workers a analizar
- [ ] Tienes espacio en disco para reportes

¡Listo para ejecutar!
