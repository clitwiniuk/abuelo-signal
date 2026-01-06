# Sistema de Eventos en Replay Testing

## 🎯 Concepto: ¿Qué es un Evento?

Un **evento** es la combinación de:
- **1 ticker** (símbolo)
- **1 día** (fecha)
- **1 worker** (estrategia)

**Cada evento es COMPLETAMENTE INDEPENDIENTE y aislado.**

## 📊 Ejemplos

### Caso 1: Mismo ticker, diferentes días
```
Evento 1: MSAI @ 2025-10-31 con generic_01
  - 538 barras
  - 3 entradas, 3 stop losses
  - Problema: re-entradas inmediatas

Evento 2: MSAI @ 2025-11-01 con generic_01
  - 612 barras
  - 1 entrada, 1 take profit
  - Sin problemas

✅ Son EVENTOS DIFERENTES - se analizan por separado
```

### Caso 2: Diferentes tickers, mismo día
```
Evento 1: MSAI @ 2025-10-31 con generic_01
  - 538 barras
  - Múltiples stop losses

Evento 2: DFSC @ 2025-10-31 con generic_01
  - 425 barras
  - 1 entrada, 1 EOD exit exitoso

✅ Son EVENTOS DIFERENTES - se analizan por separado
```

### Caso 3: Mismo ticker y día, diferentes workers
```
Evento 1: MSAI @ 2025-10-31 con generic_01
  - Worker generic_01 entró y perdió

Evento 2: MSAI @ 2025-10-31 con daily_plays
  - Worker daily_plays NO entró (rechazado por VWAP)

✅ Son EVENTOS DIFERENTES - cada worker tiene su propia lógica
```

## 🔧 Implementación Técnica

### Estructura de ReplayEvent

```python
@dataclass
class ReplayEvent:
    """
    Evento único e independiente
    """
    symbol: str              # MSAI
    date: str                # 2025-10-31
    worker_name: str         # generic_01

    # Event ID único: "MSAI_2025-10-31_generic_01"
    def get_event_id(self) -> str:
        return f"{self.symbol}_{self.date}_{self.worker_name}"

    # Datos específicos de ESTE evento
    total_bars: int
    decisions: List[ReplayDecision]
    simulated_trades: List[Dict]
    real_trades: List[Dict]
    discrepancies: List[Dict]
```

### Estado Aislado por Evento

**CRÍTICO**: Cada evento tiene su propio estado simulado, aislado de otros eventos.

```python
# Al procesar cada evento:
for symbol, bars in bars_by_symbol.items():
    # Crear evento independiente
    event = ReplayEvent(symbol=symbol, date=date, worker=worker)

    # RESET estado - aislamiento total
    self.active_positions = {}      # Fresh state
    self.locked_symbols = {}        # Fresh state
    self.cooldown_symbols = {}      # Fresh state

    # Procesar SOLO este evento
    for bar in bars:
        decision = process_bar(worker, bar, event)
        event.decisions.append(decision)

    # Comparar SOLO este evento con sus trades reales
    event.real_trades = load_real_trades(symbol, date)
    event.discrepancies = compare(event.simulated, event.real)
```

## 📈 Output con Sistema de Eventos

```bash
python replay_testing/run_replay.py --date 2025-10-31 --worker generic_01
```

```
================================================================================
🔄 REPLAY SESSION: 2025-10-31 - Worker: generic_01
================================================================================

📊 Loaded data for 15 symbols

📈 Replaying EVENT: MSAI @ 2025-10-31 (538 bars)
   Event complete: 12 decisions, 3 simulated trades, 3 real trades, 2 discrepancies

📈 Replaying EVENT: DFSC @ 2025-10-31 (425 bars)
   Event complete: 8 decisions, 1 simulated trades, 1 real trades, 0 discrepancies

📈 Replaying EVENT: ASST @ 2025-10-31 (312 bars)
   Event complete: 5 decisions, 0 simulated trades, 0 real trades, 0 discrepancies

...

================================================================================
✅ REPLAY COMPLETED in 3.2s
================================================================================
   Events: 15 (one per ticker)
   Bars processed: 6,543
   Decisions made: 89
   Entries approved: 12
   Simulated trades: 12

📈 Events Summary:
  MSAI: 12 decisions, 3 simulated trades, 3 real trades ⚠️ (2 issues)
  DFSC: 8 decisions, 1 simulated trades, 1 real trades ✅
  ASST: 5 decisions, 0 simulated trades, 0 real trades ✅
  ...
```

## 🔍 Análisis Granular por Evento

### Analizar un evento específico problemático

```bash
# Solo MSAI del 31 de octubre
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --worker generic_01 \
    --symbols MSAI
```

**Output:**
```
📈 Replaying EVENT: MSAI @ 2025-10-31 (538 bars)

  18:04:00 - Entry decision: APPROVED (pattern: 100%)
    ✅ Pattern completion: 100% >= 75%
    ✅ Price $2.13 in range
    ⚠️ Volume 2.0x at limit
    ❌ DISCREPANCY: Entry price $2.13 != IBKR $2.06

  18:06:24 - Exit decision: STOP_LOSS_5.0%
    ✅ Exit price $2.02 matches IBKR
    ✅ Cooldown applied: 30min

  18:08:03 - Entry attempt: BLOCKED
    ✅ Cooldown check: In cooldown (28min remaining)
    ❌ DISCREPANCY: Real system allowed entry (cooldown bug)

  18:13:37 - Exit decision: STOP_LOSS_5.0%
    ✅ Exit price $2.02 matches IBKR

Event complete:
  Decisions: 12
  Simulated trades: 3
  Real trades: 3
  Discrepancies: 2

🚨 Critical Issues for MSAI @ 2025-10-31:
  1. Entry price not using IBKR avgCost (FIXED)
  2. Cooldown not enforced (FIXED)
```

## 💡 Beneficios del Sistema de Eventos

### 1. Aislamiento Total
- Cada ticker no afecta a otros
- Estado fresco por evento
- No hay contaminación entre días

### 2. Análisis Granular
- Puedes analizar UN ticker problemático
- No necesitas procesar todo el día
- Debugging más rápido

### 3. Comparación Precisa
- Comparas MSAI 31/10 replay vs MSAI 31/10 real
- No mezclas trades de diferentes eventos
- Discrepancias claras y específicas

### 4. Escalabilidad
- Puedes procesar 100 eventos en paralelo (futuro)
- Cada evento es independiente
- Fácil agregar más fechas/símbolos

## 🎓 Casos de Uso

### Caso 1: Investigar día problemático completo
```bash
# Todos los eventos del día
python replay_testing/run_replay.py --date 2025-10-31 --worker generic_01

# Output muestra resumen por evento:
# MSAI: ⚠️ 2 issues
# DFSC: ✅ OK
# ASST: ✅ OK
```

### Caso 2: Deep dive en evento específico
```bash
# Solo el evento problemático
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --worker generic_01 \
    --symbols MSAI \
    --verbose

# Output detallado de CADA decisión del evento MSAI
```

### Caso 3: Comparar mismo ticker en diferentes días
```bash
# MSAI en semana completa
python replay_testing/run_replay.py \
    --start-date 2025-10-25 \
    --end-date 2025-10-31 \
    --worker generic_01 \
    --symbols MSAI

# Output:
# Evento: MSAI @ 2025-10-25: ✅ OK
# Evento: MSAI @ 2025-10-26: ✅ OK
# Evento: MSAI @ 2025-10-31: ⚠️ 2 issues  ← Problemas solo este día
```

### Caso 4: Regression testing por evento
```bash
# Antes del fix
git checkout before-fix
python replay_testing/run_replay.py --date 2025-10-31 --worker generic_01 --symbols MSAI
# MSAI: ⚠️ 2 issues

# Después del fix
git checkout after-fix
python replay_testing/run_replay.py --date 2025-10-31 --worker generic_01 --symbols MSAI
# MSAI: ✅ OK  ← ¡Fix funcionó!
```

## 📊 Estructura de Datos

### ReplaySession (día completo)
```python
session = ReplaySession(
    date="2025-10-31",
    worker_name="generic_01",
    events={
        "MSAI": ReplayEvent(...),   # Evento independiente
        "DFSC": ReplayEvent(...),   # Evento independiente
        "ASST": ReplayEvent(...),   # Evento independiente
        ...
    }
)

# Acceder a evento específico
msai_event = session.get_event("MSAI")
print(msai_event.discrepancies)  # Solo problemas de MSAI
```

### ReplayEvent (ticker + día)
```python
event = ReplayEvent(
    symbol="MSAI",
    date="2025-10-31",
    worker_name="generic_01",

    decisions=[...],          # Todas las decisiones de MSAI ese día
    simulated_trades=[...],   # Trades simulados de MSAI ese día
    real_trades=[...],        # Trades reales de MSAI ese día
    discrepancies=[...]       # Problemas específicos de MSAI ese día
)

# Unique ID
event.get_event_id()  # "MSAI_2025-10-31_generic_01"
```

## 🔒 Garantías del Sistema

1. ✅ **Aislamiento**: Cada evento es independiente
2. ✅ **Reproducibilidad**: Mismo evento = mismo resultado
3. ✅ **Precisión**: Comparación exacta replay vs real
4. ✅ **Escalabilidad**: Fácil procesar múltiples eventos
5. ✅ **Debugging**: Análisis granular por evento

## 🚀 Próximos Pasos

Con este sistema de eventos, podemos:
1. ✅ Analizar eventos independientes
2. 🔜 Implementar verificador de decisiones por evento
3. 🔜 Generar reportes HTML por evento
4. 🔜 Comparar eventos entre sí
5. 🔜 Detectar patrones en eventos problemáticos
