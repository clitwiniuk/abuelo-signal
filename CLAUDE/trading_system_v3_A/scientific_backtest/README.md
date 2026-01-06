# Scientific Backtesting System

Sistema de backtesting científico para validar workers con datos reales almacenados.

## 🎯 Objetivo

Determinar qué workers son **realmente** rentables usando:
- Datos OHLC reales almacenados en la base de datos
- Validación de consistencia en múltiples períodos
- Replay del sistema para simular decisiones exactas

## 📁 Archivos

### `backtest_worker_scientific.py`
Backtest individual de un worker específico.

**Uso:**
```bash
python backtest_worker_scientific.py --worker vcp_smallcap
python backtest_worker_scientific.py --worker vcp_smallcap --start-date 2024-01-01 --end-date 2025-12-17
```

**Output:**
- Resultados por período (2 meses cada uno por defecto)
- Análisis de consistencia (% de períodos que pasan validación)
- Recomendación: MANTENER Y ESCALAR / MONITOREAR / DESHABILITAR

### `backtest_all_workers.py`
Backtest masivo de todos los workers activos.

**Uso:**
```bash
python backtest_all_workers.py
python backtest_all_workers.py --workers vcp_smallcap daily_plays vwap_breakout
```

**Output:**
- Tabla comparativa de todos los workers
- Ranking por performance
- Reporte HTML interactivo (`backtest_comparison.html`)
- Reporte JSON completo (`backtest_comparison.json`)

### `validate_replay_fidelity.py`
Valida que el replay replica exactamente la ejecución real.

**Uso:**
```bash
python validate_replay_fidelity.py --worker vcp_smallcap --days 7
```

**Output:**
- Match rate (% de decisiones coincidentes)
- Discrepancias en precios, timing, P&L
- Veredicto: CONFIABLE (>95%) / REVISAR (80-95%) / NO CONFIABLE (<80%)

## 🚀 Workflow Recomendado

### 1. Validar Fidelidad del Replay
```bash
# Comparar últimos 7 días de replay vs ejecución real
python validate_replay_fidelity.py --worker vcp_smallcap --days 7
```

**Requisito:** Match rate >95% para confiar en los backtests.

### 2. Backtest de Todos los Workers
```bash
# Ejecutar backtest masivo
python backtest_all_workers.py
```

### 3. Revisar Resultados
```bash
# Abrir reporte HTML
open backtest_comparison.html
```

### 4. Tomar Decisiones
Basado en las recomendaciones:
- **✅ MANTENER Y ESCALAR**: Aumentar position size 2x
- **⚠️ MONITOREAR**: Mantener size actual, revisar en 100 trades más
- **❌ DESHABILITAR**: Editar config.ini y deshabilitar worker

## 📊 Criterios de Validación

### Por Período
Un período PASA si cumple:
- Mínimo 10 trades
- Win Rate ≥ 45%
- Profit Factor ≥ 1.3
- Max Drawdown < 25%

### Recomendación Final

**MANTENER Y ESCALAR:**
- Consistency Score ≥ 75% (pasa en 3+ de 4 períodos)
- Win Rate promedio ≥ 45%
- Profit Factor promedio ≥ 1.3

**MONITOREAR:**
- Consistency Score 50-75%
- Win Rate 40-45%
- Profit Factor 1.1-1.3

**DESHABILITAR:**
- Consistency Score < 50%
- Win Rate < 40%
- Profit Factor < 1.1

## ⚠️ Consideraciones Importantes

1. **NO ejecutar backtest el mismo día que modificaste el worker**
   - Los datos históricos no reflejan la configuración actual
   - Esperar al menos 1 día de operativa estable

2. **Validar fidelidad del replay PRIMERO**
   - Si match rate < 95%, los backtests no son confiables
   - Arreglar discrepancias antes de confiar en resultados

3. **Usar múltiples períodos**
   - Un worker puede tener suerte en 1 período
   - Consistencia en 3+ períodos es mejor predictor de futuro

4. **Sample size importa**
   - Mínimo 10 trades por período
   - Preferir 50+ trades para alta confianza estadística

## 📖 Documentación Completa

Ver [INSTRUCCIONES_BACKTEST.md](../INSTRUCCIONES_BACKTEST.md) para guía detallada.
