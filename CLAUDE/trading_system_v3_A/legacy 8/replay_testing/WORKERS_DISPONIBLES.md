# Workers Disponibles en Replay Testing

## 📋 Lista Completa de Workers

El sistema de Replay Testing soporta los siguientes workers:

### 1. `generic_01` ✅
- **Archivo**: `strategies/workers/generic_01_worker_logic.py`
- **Clase**: `Generic01Worker`
- **Descripción**: Worker genérico con estrategia de early entry (75-100% pattern completion)
- **Uso**: `--workers generic_01`

### 2. `daily_plays` ✅
- **Archivo**: `strategies/workers/daily_plays_worker_logic.py`
- **Clase**: `DailyPlaysWorker`
- **Descripción**: Worker para daily plays con dos modos (catalyst y standard)
- **Uso**: `--workers daily_plays`

### 3. `macdv` ✅
- **Archivo**: `strategies/workers/macdv_worker_logic.py`
- **Clase**: `MACDVWorker`
- **Descripción**: Worker basado en MACD divergence
- **Uso**: `--workers macdv`

### 4. `vcp_smallcap` ✅
- **Archivo**: `strategies/workers/vcp_smallcap_worker_logic.py`
- **Clase**: `VCPSmallcapWorker`
- **Descripción**: Worker para Volatility Contraction Pattern en smallcaps
- **Uso**: `--workers vcp_smallcap`

### 5. `volume_absorption` ✅
- **Archivo**: `strategies/workers/volume_absorption_worker_logic.py`
- **Clase**: `VolumeAbsorptionWorker`
- **Descripción**: Worker basado en absorción de volumen
- **Uso**: `--workers volume_absorption`

### 6. `vwap` ✅
- **Archivo**: `strategies/workers/vwap_worker_logic.py`
- **Clase**: `VWAPWorker`
- **Descripción**: Worker basado en VWAP breakout
- **Uso**: `--workers vwap`

### 7. `momentum_breakout` ✅ **NUEVO**
- **Archivo**: `strategies/workers/momentum_breakout_worker_logic.py`
- **Clase**: `MomentumBreakoutWorker`
- **Descripción**: Worker para momentum breakouts (estilo Mark Minervini / IBD)
- **Uso**: `--workers momentum_breakout`

## 🚀 Ejemplos de Uso

### Replay con un solo worker
```bash
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers generic_01 \
    --verbose
```

### Replay con múltiples workers
```bash
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers generic_01,daily_plays,macdv \
    --verbose
```

### Replay con todos los workers
```bash
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers generic_01,daily_plays,macdv,vcp_smallcap,volume_absorption,vwap,momentum_breakout \
    --verbose
```

### Replay de worker específico en símbolo específico
```bash
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers macdv \
    --symbols MSAI \
    --verbose
```

## 📊 Comparación de Workers vs Estrategias

### ⚠️ IMPORTANTE: Diferencia entre Workers y Estrategias

El sistema tiene **dos tipos** de componentes que NO deben confundirse:

### Workers (Replay Testing) ✅
- Ubicación: `strategies/workers/*_worker_logic.py`
- Uso: Sistema de trading en vivo + Replay Testing
- Base: `BaseWorkerLogic`
- Métodos: `should_enter()`, `calculate_pattern_completion()`, etc.
- **Estos son los que usa el replay testing**

### Estrategias (Sistema Antiguo) ⚠️
- Ubicación: `strategies/*_strategy.py`
- Uso: Sistema antiguo de backtesting
- Base: `BaseStrategy`
- **NO se usan en replay testing**
- **El warning sobre "MACDV Smallcaps strategy" es inofensivo**

## 🔧 Añadir Nuevos Workers al Replay

Si creas un nuevo worker, debes agregarlo al ReplayEngine:

1. Crea el archivo: `strategies/workers/nuevo_worker_logic.py`
2. Edita: `replay_testing/core/replay_engine.py`
3. Agrega en el método `_load_worker()`:

```python
elif worker_name == 'nuevo_worker':
    from strategies.workers.nuevo_worker_logic import NuevoWorker
    worker = NuevoWorker()
```

## ✅ Verificación

Para verificar que todos los workers están disponibles:

```bash
# Ver lista de workers en el código
grep "elif worker_name ==" replay_testing/core/replay_engine.py

# Ejecutar test básico
python replay_testing/test_replay_basic.py
```

## 📝 Notas

- ✅ Todos los workers están implementados y probados
- ✅ El warning sobre "MACDV Smallcaps strategy" fue suprimido (cambió a DEBUG)
- ✅ El replay testing SOLO usa workers, NO estrategias
- ✅ Los workers pueden evaluarse múltiples a la vez en el mismo evento
- ✅ Solo 1 worker puede tener posición activa por evento a la vez
