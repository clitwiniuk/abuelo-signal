# Metodología de Mejora de Workers mediante Replay Testing

## 📋 Índice

1. [Objetivo](#objetivo)
2. [Cuándo Usar Esta Metodología](#cuándo-usar-esta-metodología)
3. [Procedimiento Completo](#procedimiento-completo)
4. [Ejemplos Prácticos](#ejemplos-prácticos)
5. [Checklist de Validación](#checklist-de-validación)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 Objetivo

Esta metodología permite **validar y mejorar workers** utilizando datos históricos reales de `trading_data.db` y `market_data.db`. A diferencia del backtesting tradicional que solo muestra resultados finales, el replay testing permite:

- ✅ **Verificar cada decisión** del worker barra por barra
- ✅ **Detectar bugs** en la lógica interna
- ✅ **Comparar** decisiones simuladas vs trades reales ejecutados
- ✅ **Identificar mejoras** basadas en comportamiento real
- ✅ **Validar fixes** antes de producción

---

## 🔍 Cuándo Usar Esta Metodología

### Casos de Uso Principales

1. **Desarrollo de nuevo worker**: Validar que funciona correctamente antes de producción
2. **Debugging de worker existente**: Investigar por qué un worker tuvo comportamiento extraño
3. **Optimización de parámetros**: Probar diferentes configuraciones con datos reales
4. **Validación de fixes**: Verificar que un cambio de código resuelve el problema
5. **Regression testing**: Asegurar que cambios no rompieron workers existentes
6. **Análisis de performance**: Entender por qué un worker tiene ciertos resultados

### Señales de que Necesitas Replay Testing

- ❌ Worker tiene muchos stop losses consecutivos
- ❌ Worker entra/sale en momentos inesperados
- ❌ Discrepancias entre lo esperado y lo ejecutado
- ❌ Cooldowns no se respetan correctamente
- ❌ Precios de entrada/salida no coinciden con IBKR
- ❌ Pattern completion parece incorrecto

---

## 📝 Procedimiento Completo

### Fase 1: Preparación

#### 1.1 Identificar el Período a Analizar

```bash
# Ver fechas disponibles en trading_data.db
sqlite3 trading_data.db "
SELECT 
    DATE(entry_time) as fecha,
    worker_name,
    COUNT(*) as num_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as perdidas,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as ganancias
FROM trades
WHERE worker_name = 'TU_WORKER'
GROUP BY DATE(entry_time), worker_name
ORDER BY fecha DESC
LIMIT 30;
"
```

**Criterios de selección:**
- Días con comportamiento anómalo (muchas pérdidas, entradas extrañas)
- Días recientes con datos completos
- Días con variedad de símbolos
- Rango de 5-10 días para análisis completo

#### 1.2 Verificar Disponibilidad de Datos

```bash
# Verificar market_data.db tiene datos del período
sqlite3 backtesting_system/market_data.db "
SELECT 
    DATE(timestamp) as fecha,
    COUNT(DISTINCT symbol) as simbolos,
    COUNT(*) as barras
FROM bars
WHERE DATE(timestamp) BETWEEN '2025-10-25' AND '2025-10-31'
GROUP BY DATE(timestamp)
ORDER BY fecha;
"

# Verificar trading_data.db tiene trades del período
sqlite3 trading_data.db "
SELECT 
    DATE(entry_time) as fecha,
    worker_name,
    COUNT(*) as trades,
    GROUP_CONCAT(DISTINCT symbol) as simbolos
FROM trades
WHERE DATE(entry_time) BETWEEN '2025-10-25' AND '2025-10-31'
  AND worker_name = 'TU_WORKER'
GROUP BY DATE(entry_time), worker_name
ORDER BY fecha;
"
```

#### 1.3 Identificar Símbolos Problemáticos (Opcional)

```bash
# Símbolos con más stop losses
sqlite3 trading_data.db "
SELECT 
    symbol,
    COUNT(*) as trades,
    SUM(CASE WHEN exit_reason LIKE '%STOP%' THEN 1 ELSE 0 END) as stop_losses,
    AVG(pnl) as avg_pnl
FROM trades
WHERE worker_name = 'TU_WORKER'
  AND DATE(entry_time) BETWEEN '2025-10-25' AND '2025-10-31'
GROUP BY symbol
HAVING stop_losses > 2
ORDER BY stop_losses DESC;
"
```

---

### Fase 2: Ejecución del Replay

#### 2.1 Replay Inicial (Día Específico)

```bash
# Replay de un día específico con verbose para ver detalles
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers TU_WORKER \
    --verbose
```

**Qué observar:**
- Número total de decisiones vs trades reales
- Discrepancias encontradas
- Pattern completion de entradas
- Razones de rechazo de oportunidades

#### 2.2 Replay de Símbolo Específico (Deep Dive)

```bash
# Investigar símbolo problemático en detalle
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers TU_WORKER \
    --symbols MSAI \
    --verbose
```

**Qué observar:**
- Timeline completo de decisiones
- Precios exactos de entrada/salida
- Cooldowns aplicados
- Comparación con trade real de IBKR

#### 2.3 Replay de Rango de Fechas (Análisis Completo)

```bash
# Replay de toda la semana
python replay_testing/run_replay.py \
    --start-date 2025-10-25 \
    --end-date 2025-10-31 \
    --workers TU_WORKER
```

**Qué observar:**
- Patrones consistentes de discrepancias
- Días con más problemas
- Tendencias en decisiones

---

### Fase 3: Análisis de Resultados

#### 3.1 Revisar Output del Replay

El output mostrará:

```
📊 REPLAY SESSION SUMMARY
Date: 2025-10-31
Worker: TU_WORKER
Events: 15 (one per ticker)
Bars processed: 6,543
Decisions made: 189
Entries approved: 12
Entries rejected: 45
Exits executed: 11
Simulated trades: 12

Verification:
  Total discrepancies: 3

⚠️  Discrepancies found:
  - PRICE_MISMATCH: MSAI entry $2.13 != IBKR real $2.06
  - COOLDOWN_BUG: MSAI entry allowed despite cooldown
  - PATTERN_ERROR: DFSC pattern completion 65% but entered
```

#### 3.2 Clasificar Discrepancias

| Tipo | Severidad | Acción Requerida |
|------|-----------|------------------|
| `PRICE_MISMATCH` | 🔴 CRÍTICA | Verificar uso de avgCost de IBKR |
| `COOLDOWN_BUG` | 🔴 CRÍTICA | Revisar lógica de cooldown |
| `PATTERN_ERROR` | 🟡 ALTA | Revisar cálculo de pattern completion |
| `MISSING_TRADE` | 🟡 ALTA | Investigar por qué no se ejecutó |
| `EXTRA_TRADE` | 🟡 ALTA | Investigar por qué se ejecutó de más |
| `TIMING_DIFF` | 🟢 MEDIA | Verificar horarios de trading |
| `VOLUME_DIFF` | 🟢 BAJA | Revisar filtros de volumen |

#### 3.3 Documentar Hallazgos

Crear un documento de análisis:

```markdown
# Análisis Replay - [WORKER_NAME] - [FECHA]

## Resumen Ejecutivo
- Período analizado: [fechas]
- Total decisiones: [número]
- Discrepancias encontradas: [número]
- Severidad: [crítica/alta/media/baja]

## Discrepancias Críticas

### 1. PRICE_MISMATCH en MSAI
- **Fecha**: 2025-10-31 18:04:00
- **Esperado**: $2.06 (IBKR avgCost)
- **Obtenido**: $2.13 (current_price estimado)
- **Causa**: Worker usa current_price en vez de avgCost
- **Fix**: Usar opportunity.entry_price de IBKR

### 2. COOLDOWN_BUG en MSAI
- **Fecha**: 2025-10-31 18:08:03
- **Problema**: Entrada permitida 2min después de stop loss
- **Esperado**: Cooldown de 30min
- **Causa**: Cooldown no se verifica en production
- **Fix**: Agregar check de cooldown en should_enter()

## Mejoras Identificadas
1. [Mejora 1]
2. [Mejora 2]

## Próximos Pasos
- [ ] Implementar fix para PRICE_MISMATCH
- [ ] Implementar fix para COOLDOWN_BUG
- [ ] Re-ejecutar replay para validar fixes
```

---

### Fase 4: Implementación de Mejoras

#### 4.1 Crear Branch para Mejoras

```bash
git checkout -b fix/worker-TU_WORKER-replay-improvements
```

#### 4.2 Implementar Fixes

Ejemplo de fix común:

```python
# strategies/workers/tu_worker_logic.py

def should_enter(self, opportunity):
    """Decide si entrar en una oportunidad"""
    
    # FIX 1: Usar avgCost de IBKR en vez de current_price
    # ANTES:
    # entry_price = opportunity.current_price
    # DESPUÉS:
    entry_price = opportunity.entry_price  # avgCost de IBKR
    
    # FIX 2: Verificar cooldown antes de entrar
    if self._is_in_cooldown(opportunity.symbol):
        self.logger.info(f"❌ {opportunity.symbol} en cooldown, rechazando entrada")
        return False
    
    # FIX 3: Verificar pattern completion >= 75%
    completion = self.calculate_pattern_completion(opportunity)
    if completion < 0.75:
        self.logger.info(f"❌ {opportunity.symbol} pattern {completion:.0%} < 75%")
        return False
    
    return True
```

#### 4.3 Actualizar Tests

```python
# tests/test_tu_worker.py

def test_cooldown_respected():
    """Verificar que cooldown se respeta después de stop loss"""
    worker = TuWorkerLogic()
    
    # Simular stop loss
    worker._add_cooldown('MSAI', cooldown_minutes=30)
    
    # Intentar entrada inmediata
    opportunity = create_test_opportunity('MSAI')
    assert worker.should_enter(opportunity) == False
    
def test_uses_ibkr_avgcost():
    """Verificar que usa avgCost de IBKR"""
    worker = TuWorkerLogic()
    opportunity = create_test_opportunity('MSAI')
    opportunity.entry_price = 2.06  # avgCost
    opportunity.current_price = 2.13  # precio actual
    
    # Worker debe usar entry_price (avgCost)
    assert worker.get_entry_price(opportunity) == 2.06
```

---

### Fase 5: Validación de Mejoras

#### 5.1 Re-ejecutar Replay con Código Mejorado

```bash
# Replay del mismo período con código mejorado
python replay_testing/run_replay.py \
    --start-date 2025-10-25 \
    --end-date 2025-10-31 \
    --workers TU_WORKER \
    --verbose
```

**Verificar:**
- ✅ Discrepancias críticas resueltas
- ✅ Número de discrepancias reducido
- ✅ Decisiones más consistentes con trades reales

#### 5.2 Comparar Antes vs Después

```bash
# Guardar resultados ANTES del fix
git checkout main
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers TU_WORKER > before_fix.txt

# Guardar resultados DESPUÉS del fix
git checkout fix/worker-TU_WORKER-replay-improvements
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers TU_WORKER > after_fix.txt

# Comparar
diff before_fix.txt after_fix.txt
```

#### 5.3 Ejecutar Tests Automatizados

```bash
# Tests unitarios
pytest tests/test_tu_worker.py -v

# Tests de integración
pytest tests/integration/test_tu_worker_integration.py -v

# Regression testing (si existe)
python replay_testing/run_regression.py \
    --scenarios replay_testing/scenarios/tu_worker_scenarios.json
```

---

### Fase 6: Documentación y Deployment

#### 6.1 Documentar Cambios

```markdown
# CHANGELOG - TU_WORKER

## [v1.2.0] - 2025-11-27

### Fixed
- 🔴 **CRÍTICO**: Ahora usa avgCost de IBKR en vez de current_price estimado
- 🔴 **CRÍTICO**: Cooldown de 30min se respeta correctamente después de stop loss
- 🟡 Pattern completion ahora requiere >= 75% para entrar

### Validation
- Replay testing: 0 discrepancias críticas (antes: 3)
- Tests: 15/15 passing
- Período validado: 2025-10-25 a 2025-10-31

### Performance Impact
- Entradas: -15% (más selectivo)
- Win rate: +8% (mejor calidad)
- Avg PnL: +12% (menos stop losses)
```

#### 6.2 Crear Pull Request

```bash
git add .
git commit -m "fix(tu_worker): Resolve critical replay discrepancies

- Use IBKR avgCost instead of current_price
- Enforce 30min cooldown after stop loss
- Require pattern completion >= 75%

Validated via replay testing on 2025-10-25 to 2025-10-31
Discrepancies: 3 → 0 (critical)
Tests: 15/15 passing"

git push origin fix/worker-TU_WORKER-replay-improvements
```

#### 6.3 Deployment Checklist

- [ ] Replay testing muestra 0 discrepancias críticas
- [ ] Tests automatizados passing (100%)
- [ ] Documentación actualizada
- [ ] CHANGELOG actualizado
- [ ] Code review aprobado
- [ ] Merge a main
- [ ] Deploy a producción
- [ ] Monitorear primeros días en producción

---

## 📚 Ejemplos Prácticos

### Ejemplo 1: Worker con Muchos Stop Losses

**Problema**: Worker `generic_01` tuvo 8 stop losses en MSAI el 2025-10-31

```bash
# 1. Replay del día problemático
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers generic_01 \
    --symbols MSAI \
    --verbose
```

**Hallazgos:**
- Pattern completion era 100% pero precio ya había subido 15%
- Entradas tardías (después del breakout inicial)
- Stop loss muy ajustado (2%) para volatilidad del símbolo

**Mejoras implementadas:**
1. Requerir entrada en primeros 5min del breakout
2. Ajustar stop loss dinámicamente según ATR
3. Rechazar si precio ya subió >10% desde apertura

**Validación:**
```bash
# Re-ejecutar replay con mejoras
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers generic_01 \
    --symbols MSAI \
    --verbose
```

**Resultado:** 8 stop losses → 2 stop losses (75% mejora)

---

### Ejemplo 2: Validar Nuevo Worker

**Objetivo**: Validar worker `vcp_smallcap` antes de producción

```bash
# 1. Crear escenarios de regression testing
# Editar: replay_testing/scenarios/vcp_smallcap_scenarios.json

# 2. Ejecutar regression suite
python replay_testing/run_regression.py \
    --scenarios replay_testing/scenarios/vcp_smallcap_scenarios.json

# 3. Ejecutar blind test (símbolos no vistos)
python replay_testing/run_blind_test.py \
    --scenarios replay_testing/scenarios/vcp_smallcap_blind_test.json \
    --output replay_testing/results/vcp_blind_test_results.json

# 4. Replay de múltiples días
python replay_testing/run_replay.py \
    --start-date 2025-10-01 \
    --end-date 2025-10-31 \
    --workers vcp_smallcap
```

**Criterios de aprobación:**
- ✅ Regression suite: 100% passing
- ✅ Blind test: >80% success rate
- ✅ Replay testing: <5 discrepancias críticas
- ✅ False positive rate: <20%

---

### Ejemplo 3: Optimizar Parámetros

**Objetivo**: Encontrar mejor configuración de take profit para `daily_plays`

```bash
# 1. Replay con configuración actual
python replay_testing/run_replay.py \
    --start-date 2025-10-01 \
    --end-date 2025-10-31 \
    --workers daily_plays > results_tp_current.txt

# 2. Modificar config.ini (TP: 5% → 7%)
# [daily_plays]
# take_profit_pct = 7.0

# 3. Replay con nueva configuración
python replay_testing/run_replay.py \
    --start-date 2025-10-01 \
    --end-date 2025-10-31 \
    --workers daily_plays > results_tp_7pct.txt

# 4. Comparar resultados
python scripts/compare_replay_results.py \
    results_tp_current.txt \
    results_tp_7pct.txt
```

**Análisis:**
- TP 5%: 45 trades, 60% win rate, avg PnL $120
- TP 7%: 38 trades, 55% win rate, avg PnL $180
- **Decisión**: Usar TP 7% (mejor avg PnL)

---

## ✅ Checklist de Validación

### Pre-Deployment Checklist

- [ ] **Datos verificados**
  - [ ] market_data.db tiene datos del período
  - [ ] trading_data.db tiene trades del período
  - [ ] Período cubre al menos 5-10 días de trading

- [ ] **Replay ejecutado**
  - [ ] Replay de día específico completado
  - [ ] Replay de símbolos problemáticos completado
  - [ ] Replay de rango de fechas completado

- [ ] **Análisis completado**
  - [ ] Discrepancias documentadas
  - [ ] Causas identificadas
  - [ ] Mejoras propuestas

- [ ] **Mejoras implementadas**
  - [ ] Código modificado
  - [ ] Tests actualizados
  - [ ] Documentación actualizada

- [ ] **Validación completada**
  - [ ] Re-ejecutar replay muestra mejoras
  - [ ] Discrepancias críticas resueltas
  - [ ] Tests automatizados passing
  - [ ] Regression testing passing (si aplica)

- [ ] **Deployment**
  - [ ] CHANGELOG actualizado
  - [ ] Pull request creado
  - [ ] Code review aprobado
  - [ ] Merge a main
  - [ ] Deploy a producción

---

## 🔧 Troubleshooting

### Problema: "No market data found for date"

**Causa**: market_data.db no tiene datos de esa fecha

**Solución:**
```bash
# Verificar fechas disponibles
sqlite3 backtesting_system/market_data.db "
SELECT DISTINCT DATE(timestamp) as fecha
FROM bars
ORDER BY fecha DESC
LIMIT 20;
"

# Usar fecha que tenga datos
```

---

### Problema: "Worker failed to load"

**Causa**: Worker no existe o tiene error de sintaxis

**Solución:**
```bash
# Verificar que worker existe
ls strategies/workers/ | grep tu_worker

# Verificar sintaxis
python -m py_compile strategies/workers/tu_worker_logic.py

# Ver workers disponibles
cat replay_testing/WORKERS_DISPONIBLES.md
```

---

### Problema: "Too many discrepancies"

**Causa**: Worker tiene bugs o configuración incorrecta

**Solución:**
1. Ejecutar con `--verbose` para ver detalles
2. Analizar tipo de discrepancias
3. Empezar con 1 símbolo específico
4. Debuggear paso a paso

```bash
# Replay de 1 símbolo con verbose
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers TU_WORKER \
    --symbols MSAI \
    --verbose
```

---

### Problema: Replay muy lento

**Causa**: Demasiados símbolos o días

**Solución:**
```bash
# Reducir scope
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers TU_WORKER \
    --symbols MSAI,DFSC  # Solo 2 símbolos
```

---

### Problema: Resultados inconsistentes

**Causa**: Datos faltantes o corruptos

**Solución:**
```bash
# Verificar integridad de datos
python replay_testing/analyze_market_data.py \
    --date 2025-10-31

# Verificar gaps en datos
sqlite3 backtesting_system/market_data.db "
SELECT 
    symbol,
    COUNT(*) as bars,
    MIN(timestamp) as first_bar,
    MAX(timestamp) as last_bar
FROM bars
WHERE DATE(timestamp) = '2025-10-31'
GROUP BY symbol
HAVING bars < 100;  -- Símbolos con pocos datos
"
```

---

## 📞 Recursos Adicionales

- **Documentación completa**: [README.md](README.md)
- **Quick start**: [QUICK_START.md](QUICK_START.md)
- **Workers disponibles**: [WORKERS_DISPONIBLES.md](WORKERS_DISPONIBLES.md)
- **Sistema de eventos**: [EVENT_SYSTEM.md](EVENT_SYSTEM.md)
- **Ejemplos de validación**: [VCP_VALIDATION_SUMMARY.md](VCP_VALIDATION_SUMMARY.md)

---

## 🎓 Mejores Prácticas

1. **Empezar pequeño**: 1 día, 1 worker, 1-2 símbolos
2. **Documentar todo**: Hallazgos, mejoras, resultados
3. **Validar siempre**: Re-ejecutar replay después de cambios
4. **Usar regression testing**: Para workers críticos
5. **Monitorear producción**: Primeros días después de deploy
6. **Iterar**: Replay → Analizar → Mejorar → Validar → Repeat

---

**Última actualización**: 2025-11-28  
**Versión**: 1.1.0

---

## 🧪 Regression Testing con Escenarios Personalizados

### Objetivo

El **regression testing** permite validar workers de forma sistemática usando escenarios específicos. A diferencia del replay ad-hoc, los escenarios son:
- **Reproducibles**: Mismos datos, mismos resultados
- **Documentados**: Cada escenario tiene propósito claro
- **Automatizables**: Se pueden ejecutar en CI/CD
- **Comparables**: Validar antes/después de cambios

### Paso 1: Identificar Candidatos para Escenarios

#### Opción A: Desde Señales del Scanner

```bash
# Buscar señales detectadas por el scanner
sqlite3 trading_data.db "
SELECT 
    symbol, 
    date(timestamp) as date, 
    quality_score, 
    forward_return_60m,
    entered,
    rejection_reason
FROM signal_events 
WHERE worker_name = 'orb_breakout' 
  AND quality_score > 70
ORDER BY timestamp DESC 
LIMIT 20;
"
```

**Ventajas**: Escenarios reales que el scanner detectó  
**Desventajas**: Puede que no hayan generado trades

#### Opción B: Desde Alto Volumen

```bash
# Buscar símbolos con alto volumen (candidatos potenciales)
sqlite3 market_data.db "
SELECT 
    symbol, 
    date(bar_timestamp) as date,
    SUM(volume) as total_vol 
FROM intraday_bars 
WHERE date(bar_timestamp) = '2025-11-14' 
GROUP BY symbol, date
ORDER BY total_vol DESC 
LIMIT 10;
"
```

**Ventajas**: Datos de mercado garantizados  
**Desventajas**: No garantiza que el patrón exista

#### Opción C: Desde Trades Reales

```bash
# Buscar trades históricos del worker
sqlite3 trading_data.db "
SELECT 
    symbol, 
    date(entry_time) as date,
    entry_price,
    exit_price,
    pnl
FROM trades 
WHERE worker_name = 'orb_breakout'
ORDER BY entry_time DESC
LIMIT 10;
"
```

**Ventajas**: Escenarios con trades confirmados  
**Desventajas**: Si el worker tenía bugs, los trades pueden ser malos

### Paso 2: Validar Disponibilidad de Datos

**ANTES de crear un escenario, verificar:**

```bash
# 1. Datos de mercado existen
sqlite3 market_data.db "
SELECT COUNT(*) as bars 
FROM intraday_bars 
WHERE symbol = 'BITF' 
  AND date(bar_timestamp) = '2025-11-14';
"
# Debe retornar > 100 barras

# 2. Rango de tiempo correcto
sqlite3 market_data.db "
SELECT 
    MIN(bar_timestamp) as first_bar,
    MAX(bar_timestamp) as last_bar
FROM intraday_bars 
WHERE symbol = 'BITF' 
  AND date(bar_timestamp) = '2025-11-14';
"
# Para ORB: debe cubrir 13:30-14:00 UTC (9:30-10:00 AM ET)

# 3. Volumen suficiente
sqlite3 market_data.db "
SELECT 
    AVG(volume) as avg_vol, 
    MAX(volume) as max_vol
FROM intraday_bars 
WHERE symbol = 'BITF' 
  AND date(bar_timestamp) = '2025-11-14';
"
```

### Paso 3: Crear Archivo de Escenarios

**Ubicación**: `replay_testing/scenarios/[worker_name]_scenarios.json`

**Estructura**:

```json
[
    {
        "id": "BITF_2025-11-14_SCANNER_DETECTED",
        "symbol": "BITF",
        "worker_name": "orb_breakout",
        "date": "2025-11-14",
        "description": "Scanner detected ORB setup - Quality 93.5",
        "expected_action": "ENTRY",
        "mock_scanner_data": {
            "quality_score": 93.5,
            "catalyst_strength": 9,
            "catalyst_type": "NEWS",
            "gap_percentage": 7.0,
            "vwap": 2.51
        }
    },
    {
        "id": "CYPH_2025-11-14_NO_BREAKOUT",
        "symbol": "CYPH",
        "worker_name": "orb_breakout",
        "date": "2025-11-14",
        "description": "High volume but no valid breakout",
        "expected_action": "NO_ENTRY",
        "mock_scanner_data": {
            "quality_score": 90.0,
            "catalyst_strength": 9,
            "catalyst_type": "NEWS",
            "gap_percentage": 8.0,
            "vwap": 3.5
        }
    }
]
```

**Campos Obligatorios**:
- `id`: Identificador único (formato: `SYMBOL_DATE_DESCRIPTION`)
- `symbol`: Símbolo a testear
- `worker_name`: Nombre del worker (debe coincidir con engine)
- `date`: Fecha en formato `YYYY-MM-DD`
- `expected_action`: `ENTRY`, `NO_ENTRY`, `EXIT_BREAKEVEN`, etc.
- `mock_scanner_data`: Datos que el scanner proporcionaría

**Campos Opcionales**:
- `description`: Descripción del escenario
- `notes`: Información adicional

### Paso 4: Ejecutar Regression Suite

```bash
# Ejecutar todos los escenarios
python replay_testing/run_regression.py \
    --scenarios replay_testing/scenarios/orb_breakout_scenarios.json \
    --market-db market_data.db
```

**Output Esperado**:

```
🚀 Starting Regression Suite: 5 scenarios
============================================================

▶️ Running Scenario: BITF_2025-11-14_SCANNER_DETECTED
   Symbol: BITF
   Date: 2025-11-14
   Expected: ENTRY
   🔄 Running Replay...
   📊 Results: 0 entries approved
   ❌ FAIL: No entry occurred

▶️ Running Scenario: CYPH_2025-11-14_NO_BREAKOUT
   Symbol: CYPH
   Date: 2025-11-14
   Expected: NO_ENTRY
   🔄 Running Replay...
   📊 Results: 0 entries approved
   ✅ PASS: No entry occurred as expected

============================================================
🏁 Regression Complete
✅ Passed: 1
❌ Failed: 1
```

### Paso 5: Analizar Resultados

```bash
# Ver logs detallados del worker
tail -n 100 logs/worker_orb_breakout.log

# Buscar razones de rechazo específicas
grep -E "(BITF|LAES).*(ORB defined|Breakout|quality|R:R)" logs/worker_orb_breakout.log
```

**Ejemplo de Análisis**:

```
2025-11-28 06:20:34 - Worker.orb_breakout - INFO - ✅ LAES: ORB defined - High: $4.54, Low: $4.40, Range: 3.17%
2025-11-28 06:20:34 - Worker.orb_breakout - INFO - ⏸ LAES: Breakout not confirmed - Price $4.52 vs ORB high $4.54
2025-11-28 06:20:34 - Worker.orb_breakout - INFO - ⏸ LAES: Poor R:R - 0.97 < 1.5
```

**Interpretación**:
- ✅ Worker calculó ORB correctamente
- ✅ Detectó que precio no rompió el high
- ✅ Validó R:R antes de entrada
- ✅ **Comportamiento correcto** - Protegió capital

### Paso 6: Documentar Hallazgos

```markdown
# Regression Test Results - orb_breakout

## Escenarios Probados: 5

| Symbol | Expected | Result | Razón |
|--------|----------|--------|-------|
| BITF | ENTRY | NO_ENTRY | No breakout confirmado |
| LAES | ENTRY | NO_ENTRY | R:R 0.97 < 1.5 |
| CYPH | NO_ENTRY | NO_ENTRY | ✅ PASS |

## Validación

✅ Timezone handling correcto  
✅ Cálculo ORB preciso  
✅ Breakout validation funcional  
✅ Risk management activo  

## Conclusión

Worker funciona correctamente. 0 entradas es comportamiento esperado cuando no hay breakouts válidos.
```

---

## 🎯 Tipos de Escenarios a Incluir

### 1. Escenarios Positivos (Expected: ENTRY)
- Símbolos detectados por scanner con quality score alto
- Días con breakouts conocidos
- Configuraciones ideales del patrón

### 2. Escenarios Negativos (Expected: NO_ENTRY)
- Alto volumen pero sin breakout
- Breakout fallido (precio retrocede)
- R:R desfavorable
- Fuera de ventana de trading

### 3. Escenarios de Exit
- `EXIT_BREAKEVEN`: Activación de breakeven
- `EXIT_TAKE_PROFIT`: Alcance de TP
- `EXIT_STOP_LOSS`: Activación de SL
- `EXIT_TRAILING_STOP`: Trailing stop

### 4. Escenarios Edge Case
- Gaps extremos (>20%)
- Volatilidad muy alta
- Volumen muy bajo
- Horarios límite (cerca del cierre)
- Datos faltantes o corruptos

---

## 🛠️ Mejores Prácticas para Escenarios

### 1. Diversidad
- Incluir diferentes condiciones de mercado
- Mezclar escenarios positivos y negativos
- Cubrir diferentes rangos de precios y volúmenes

### 2. Realismo
- Usar datos reales del scanner cuando sea posible
- Basar `mock_scanner_data` en valores históricos
- No inventar escenarios imposibles

### 3. Documentación
- IDs descriptivos: `SYMBOL_DATE_SCENARIO_TYPE`
- Descripciones claras del propósito
- Notas sobre por qué el escenario es importante

### 4. Mantenibilidad
- Un archivo por worker
- Máximo 10-15 escenarios por archivo
- Actualizar cuando el worker cambie

### 5. Validación
- Verificar datos disponibles ANTES de crear
- Probar escenario individualmente primero
- Documentar expected_action claramente

---

## 📊 Interpretación de Resultados

### Escenario FAIL pero Worker Correcto

**Situación**: Esperabas `ENTRY` pero obtienes `NO_ENTRY`

**Posibles Causas Legítimas**:
1. Patrón no se completó realmente
2. R:R era desfavorable
3. Filtros de calidad rechazaron correctamente
4. Timing incorrecto (fuera de ventana)

**Acción**: Revisar logs para confirmar que el rechazo fue correcto. Si sí, actualizar `expected_action` a `NO_ENTRY`.

### Escenario PASS pero Comportamiento Sospechoso

**Situación**: Test pasa pero los logs muestran algo extraño

**Posibles Problemas**:
1. Worker entró por razones incorrectas
2. Cálculos internos erróneos que se compensaron
3. Datos de mercado corruptos

**Acción**: Investigar logs en detalle, validar cálculos intermedios.

### Todos los Escenarios FAIL

**Situación**: Ningún escenario pasa

**Posibles Causas**:
1. Worker tiene bug crítico
2. Datos de mercado no disponibles
3. `mock_scanner_data` incorrecto
4. Worker no registrado en engine

**Acción**: Ejecutar un escenario con `--verbose` y revisar logs completos.

---

## 🔄 Workflow Completo: Nuevo Worker

### 1. Desarrollo Inicial
```bash
# Crear worker
vim strategies/workers/nuevo_worker_logic.py

# Registrar en engine
vim strategies/worker_based_strategy_engine.py
```

### 2. Crear Escenarios de Validación
```bash
# Identificar candidatos
sqlite3 trading_data.db "SELECT ..."

# Crear archivo de escenarios
vim replay_testing/scenarios/nuevo_worker_scenarios.json
```

### 3. Ejecutar Regression
```bash
python replay_testing/run_regression.py \
    --scenarios replay_testing/scenarios/nuevo_worker_scenarios.json \
    --market-db market_data.db
```

### 4. Iterar Hasta Validación
```bash
# Fix bugs
vim strategies/workers/nuevo_worker_logic.py

# Re-test
python replay_testing/run_regression.py ...

# Repeat hasta 100% pass rate
```

### 5. Deployment
```bash
# Activar en config
vim config.ini  # enabled = true

# Reiniciar sistema
# Monitorear primeros días
```

---

## 📝 Checklist: Crear Escenarios de Calidad

- [ ] **Datos Verificados**
  - [ ] `market_data.db` tiene datos del símbolo/fecha
  - [ ] Rango de tiempo cubre ventana del worker
  - [ ] Volumen suficiente en los datos

- [ ] **Escenario Documentado**
  - [ ] ID descriptivo y único
  - [ ] Descripción clara del propósito
  - [ ] `expected_action` correcto

- [ ] **Mock Data Realista**
  - [ ] `quality_score` basado en datos reales
  - [ ] `catalyst_type` apropiado
  - [ ] Valores de gap/volumen coherentes

- [ ] **Validación Individual**
  - [ ] Escenario probado individualmente
  - [ ] Logs revisados
  - [ ] Comportamiento esperado confirmado

- [ ] **Documentación**
  - [ ] Razón de inclusión documentada
  - [ ] Resultados esperados claros
  - [ ] Notas sobre edge cases
