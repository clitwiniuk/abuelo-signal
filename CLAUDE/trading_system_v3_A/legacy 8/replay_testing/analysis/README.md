# Worker Analysis Tools

Herramientas para analizar root causes de comportamiento agresivo en workers **SIN modificar parámetros**.

## 🎯 Objetivo

Identificar **POR QUÉ** los workers son tan agresivos, NO optimizar parámetros.

## 🔧 Herramientas

### 1. Root Cause Analyzer

Analiza decisiones paso a paso para identificar problemas.

#### Uso: Analizar Trade Específico

```bash
python replay_testing/analysis/root_cause_analyzer.py analyze-trade \
    --symbol LUNG \
    --date 2025-10-28 \
    --worker daily_plays \
    --market-db market_data.db
```

**Output Ejemplo**:
```
🔍 ROOT CAUSE ANALYSIS - LUNG @ 2025-10-28
════════════════════════════════════════════════════════════════════════════════

Worker: daily_plays
Date: 2025-10-28
Symbol: LUNG

📊 Real Trades Found: 1
   1. 2025-10-28 15:32:50 @ $2.17

🔄 Running Replay Analysis...

📈 Simulated Trades: 0

🎯 DISCREPANCY ANALYSIS
════════════════════════════════════════════════════════════════════════════════
❌ MISSING SIMULATED: Real system entered but replay did not

🔬 Analyzing why replay rejected...

📊 Decision Summary:
   Total decisions: 78
   Rejected: 78
   Approved: 0

🚫 Rejection Reasons:
   15:32:45 - Worker strategy rejected entry
   15:32:46 - Worker strategy rejected entry
   ...
```

#### Uso: Analizar Worker Completo

```bash
python replay_testing/analysis/root_cause_analyzer.py analyze-worker \
    --worker daily_plays \
    --start-date 2025-10-28 \
    --end-date 2025-10-29 \
    --market-db market_data.db
```

**Output Ejemplo**:
```
🎯 WORKER AGGRESSIVENESS ANALYSIS - daily_plays
════════════════════════════════════════════════════════════════════════════════

Period: 2025-10-28 to 2025-10-29

📅 Analyzing 2025-10-28...
📅 Analyzing 2025-10-29...

📊 ANALYSIS RESULTS
════════════════════════════════════════════════════════════════════════════════
Total Decisions: 2533
Entries Approved: 727
Entries Rejected: 1806
Selectivity Ratio: 28.7%

⚠️ WARNING: Selectivity ratio TOO HIGH (>10%)
   Expected: <5% (1 in 20 decisions)
   Actual: 28.7% (1 in 3 decisions)

🚫 TOP REJECTION REASONS:
   1. Worker strategy rejected entry: 1206 (66.8%)
   2. Pattern incomplete (65.2% < 75%): 423 (23.4%)
   3. Volume too high (2.5x >= 2.0x): 177 (9.8%)
   ...
```

## 📊 Interpretación de Resultados

### Selectivity Ratio

```
Ratio    | Estado              | Acción
---------|--------------------|---------------------------------
<5%      | ✅ ÓPTIMO          | Worker bien calibrado
5-10%    | ⚠️ MODERADO        | Revisar filtros
10-20%   | ❌ AGRESIVO        | Ajustar criterios urgente
>20%     | ❌ MUY AGRESIVO    | Rediseñar filtros
```

### Status Types

- **MATCH**: Replay y real coinciden (✅ BUENO)
- **MISSING_SIMULATED**: Real entró pero replay no (❌ Worker demasiado conservador en replay)
- **FALSE_POSITIVES**: Replay entró pero real no (❌ Worker demasiado agresivo)
- **PARTIAL_MATCH**: Ambos tienen trades pero diferentes cantidades (⚠️ Revisar)

## 🎯 Workflow de Análisis

### Paso 1: Identificar Worker Problemático

Ejecutar comprehensive analysis para todos los workers:

```bash
python replay_testing/comprehensive_worker_analysis.py \
    --start-date 2025-10-07 \
    --end-date 2025-10-20 \
    --market-db market_data.db
```

### Paso 2: Analizar Worker Específico

```bash
python replay_testing/analysis/root_cause_analyzer.py analyze-worker \
    --worker daily_plays \
    --start-date 2025-10-07 \
    --end-date 2025-10-20 \
    --market-db market_data.db
```

### Paso 3: Investigar Trades Específicos

Para cada discrepancia encontrada:

```bash
python replay_testing/analysis/root_cause_analyzer.py analyze-trade \
    --symbol LUNG \
    --date 2025-10-28 \
    --worker daily_plays \
    --market-db market_data.db
```

### Paso 4: Documentar Findings

Documentar en `WORKER_OPTIMIZATION_PLAN.md`:
- Problema identificado
- Root cause
- Propuesta de fix (logic-based)
- Validación requerida

### Paso 5: Implementar Fix

**IMPORTANTE**: NO modificar parámetros basándote solo en estos análisis.
- Usar walk-forward validation
- Validar en out-of-sample data
- Documentar cambios

## ⚠️ REGLAS IMPORTANTES

### ✅ Permitido

- Analizar decisiones
- Identificar filtros que fallan
- Documentar problemas
- Proponer fixes basados en lógica de trading

### ❌ NO Permitido

- Optimizar parámetros directamente
- Hacer curve fitting a datos históricos
- Modificar thresholds sin validación
- Implementar cambios sin walk-forward testing

## 📝 Próximas Herramientas

1. **Decision Breakdown** - Descompone cada decisión en checks individuales
2. **Filter Effectiveness** - Evalúa efectividad de cada filtro
3. **Pattern Quality Audit** - Audita quality scores vs realidad
4. **Walk-Forward Validator** - Valida cambios sin overfitting

## 📚 Referencias

Ver `WORKER_OPTIMIZATION_PLAN.md` para:
- Estrategia completa de optimización
- Walk-forward analysis framework
- Anti-overfitting guidelines
- Timeline y success criteria
