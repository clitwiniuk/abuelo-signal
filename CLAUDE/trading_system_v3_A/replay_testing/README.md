# Worker Replay Testing System

Sistema de testing por reproducción (replay) que permite verificar el comportamiento exacto de los workers usando datos reales de market_data.db.

## 🎯 Objetivo

**Problema**: El backtesting tradicional solo muestra el resultado final, pero no verifica si cada decisión del worker es correcta.

**Solución**: Replay mode reproduce día a día, barra a barra, las mismas condiciones que tuvo el sistema en real, permitiendo:
- ✅ Verificar CADA decisión del worker (no solo resultado final)
- ✅ Usar datos REALES de market_data.db
- ✅ Comparar con trades reales ejecutados ese día
- ✅ Detectar bugs en lógica interna
- ✅ Debuggear días problemáticos específicos

## 📁 Estructura

```
replay_testing/
├── core/
│   ├── replay_engine.py       # Motor principal de replay
│   ├── replay_verifier.py     # Verificador de decisiones
│   └── replay_comparator.py   # Comparador replay vs real
├── reports/
│   └── [reportes HTML generados]
├── tests/
│   └── test_replay_*.py       # Tests específicos
├── README.md
└── run_replay.py              # Script principal
```

## 🚀 Uso

### Replay de un día específico
```bash
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --worker generic_01 \
    --symbols MSAI,DFSC
```

### Replay de un rango de fechas
```bash
python replay_testing/run_replay.py \
    --start-date 2025-10-25 \
    --end-date 2025-10-31 \
    --worker generic_01
```

### Replay con verificación estricta
```bash
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --worker generic_01 \
    --strict-mode  # Falla si encuentra discrepancias
```

## 📊 Qué Verifica

### Entry Decisions
- ✅ Pattern completion >= 75%
- ✅ Precio en rango [min_price, max_price]
- ✅ Volumen <= max_volume_ratio
- ✅ Trading hours correctos
- ✅ Cooldown respetado
- ✅ No hay posición abierta del mismo símbolo

### Exit Decisions
- ✅ Stop loss ejecutado al precio correcto
- ✅ Take profit ejecutado al precio correcto
- ✅ Trailing stop funcionando correctamente
- ✅ EOD exit en horario correcto

### Price Accuracy
- ✅ Entry price == IBKR avgCost (no current_price estimado)
- ✅ Exit price == IBKR avgFillPrice (no current_price estimado)
- ✅ Slippage dentro de límites aceptables

### Cooldown System
- ✅ No re-entry en 30 min después de stop loss
- ✅ No re-entry en 15 min después de trailing stop
- ✅ Re-entry permitida después de cooldown

## 📈 Reportes

Cada replay genera un reporte HTML con:

1. **Summary**: Trades totales, decisiones verificadas, discrepancias encontradas
2. **Timeline**: Timeline visual de todas las decisiones del día
3. **Discrepancies**: Lista detallada de discrepancias entre replay y real
4. **Entry Analysis**: Análisis de cada entrada (por qué se tomó la decisión)
5. **Exit Analysis**: Análisis de cada salida (stop loss, TP, etc.)
6. **Price Accuracy**: Comparación de precios replay vs IBKR real

## 🔍 Ejemplo de Uso

### Caso: Investigar por qué MSAI tuvo 3 stop losses seguidos

```bash
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --worker generic_01 \
    --symbols MSAI \
    --verbose
```

**Output esperado:**
```
🔄 Replaying 2025-10-31 for generic_01 worker...
📊 Loaded 538 bars for MSAI

18:04:00 - MSAI Entry Decision
  ✅ Pattern completion: 100% (>= 75%)
  ✅ Price $2.13 in range [$1.00, $10.00]
  ⚠️  Volume 2.0x at limit (max: 2.0x)
  ✅ Trading hours: 18:04 ET (within window)
  ❌ DISCREPANCY: Entry price $2.13 != IBKR real $2.06

18:06:24 - MSAI Exit Decision (STOP_LOSS)
  ✅ Exit price $2.02 matches IBKR
  ✅ Cooldown applied: 30min

18:08:03 - MSAI Entry Attempt
  ❌ BLOCKED: In cooldown (28min remaining)
  ⚠️  DISCREPANCY: Real system allowed entry (cooldown bug?)

📋 Summary:
  Total decisions: 45
  Verified OK: 42
  Discrepancies: 3

🚨 Critical Issues Found:
  1. Entry prices not using IBKR avgCost (fixed now)
  2. Cooldown not enforced in real system (fixed now)

Report saved: replay_testing/reports/2025-10-31_generic_01_MSAI.html
```

## 🛠️ Componentes Principales

### ReplayEngine
Motor que reproduce las condiciones exactas del día:
- Carga datos de market_data.db
- Ejecuta workers barra por barra
- Simula decisions de entry/exit
- NO ejecuta trades reales (solo simula)

### ReplayVerifier
Verifica cada decisión del worker:
- Assertions sobre pattern completion
- Validaciones de precio/volumen/horario
- Checks de cooldown/locks
- Comparación con configuración del worker

### ReplayComparator
Compara replay vs trades reales:
- Carga trades de trading_data.db
- Identifica discrepancias
- Clasifica severidad (crítica, warning, info)
- Genera explicaciones de diferencias

## 💡 Ventajas vs Backtesting

| Feature | Backtesting | Replay Mode |
|---------|-------------|-------------|
| Usa datos reales | ✅ | ✅ |
| Verifica resultado final | ✅ | ✅ |
| Verifica cada decisión | ❌ | ✅ |
| Detecta bugs lógica interna | ❌ | ✅ |
| Compara con trades reales | ❌ | ✅ |
| Permite debuggear paso a paso | ❌ | ✅ |
| Verifica precios exactos | ❌ | ✅ |
| Verifica cooldown/locks | ❌ | ✅ |

## 🎓 Casos de Uso

1. **Debugging**: Investigar por qué un día tuvo comportamiento extraño
2. **Verification**: Verificar que fix de código funciona correctamente
3. **Regression Testing**: Asegurar que cambios no rompieron workers
4. **Performance Analysis**: Analizar decisiones para mejorar workers
5. **Training**: Entender cómo trabajan los workers internamente

---

## 🧪 Regression Testing

### DailyPlays Worker

Sistema de regression testing para validar el worker DailyPlays usando escenarios guardados.

**Ejecutar regression suite:**
```bash
python replay_testing/run_regression.py \
    --scenarios replay_testing/scenarios/dailyplays_scenarios.json
```

**Resultados:** 13/14 (93% pass rate)

Ver: [DailyPlays scenarios](scenarios/dailyplays_scenarios.json)

---

### VCP_Smallcap Worker - ✅ VALIDATED

Sistema completo de regression testing y validación para el worker VCP_Smallcap.

#### Regression Suite (4/4 = 100%)

**Ejecutar tests:**
```bash
python replay_testing/run_regression.py \
    --scenarios replay_testing/scenarios/vcp_smallcap_scenarios.json
```

**Cobertura:**
- ✅ Entry validation (FOXX, ORGO)
- ✅ Rejection validation (volume filter, quality filter)
- ✅ Multi-symbol robustness (2 symbols, 14 days apart)
- ✅ NO over-optimization detected

#### Blind Test (10/10 = 100%)

**Ejecutar blind test:**
```bash
python replay_testing/run_blind_test.py \
    --scenarios replay_testing/scenarios/vcp_smallcap_blind_test.json \
    --output replay_testing/results/vcp_blind_test_results.json
```

**Resultados:**
- ✅ 10/10 symbols tested successfully
- ✅ 2 VCP patterns detected (SGBX, ERNA)
- ✅ 8 correct rejections (no false positives)
- ✅ 20% VCP discovery rate (realistic)
- ✅ 100% execution success (0 errors)

#### Validation Summary

**Status:** ✅ APPROVED FOR PRODUCTION

**Key Metrics:**
- Regression Pass Rate: 100% (4/4)
- Blind Test Success: 100% (10/10)
- Symbol Diversity: 6 symbols tested
- Temporal Coverage: Oct-Nov 2025
- Error Rate: 0%

**Ver documentación completa:** [VCP_VALIDATION_SUMMARY.md](VCP_VALIDATION_SUMMARY.md)

**Archivos:**
- Regression scenarios: [vcp_smallcap_scenarios.json](scenarios/vcp_smallcap_scenarios.json)
- Blind test scenarios: [vcp_smallcap_blind_test.json](scenarios/vcp_smallcap_blind_test.json)
- Blind test results: [vcp_blind_test_results.json](results/vcp_blind_test_results.json)
- Automation script: [run_blind_test.py](run_blind_test.py)

---

## 📝 Notas Importantes

- **No ejecuta trades reales**: Solo simula decisiones
- **Usa módulos reales**: Importa workers reales del sistema
- **Read-only**: No modifica market_data.db ni trading_data.db
- **Requiere datos**: Necesita que market_data.db tenga datos del día
- **Compara con real**: Necesita que trading_data.db tenga trades del día
