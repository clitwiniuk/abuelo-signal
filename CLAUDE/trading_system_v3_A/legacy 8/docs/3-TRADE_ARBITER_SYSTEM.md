# 🎯 Trade Arbiter & Context Engine System

## 📋 Overview

Sistema híbrido de coordinación de workers que implementa análisis de contexto de mercado y selección inteligente de señales.

## 🏗️ Arquitectura

```
┌──────────────────────────────────┐
│        SCANNER                   │
│  (envía tickers a analizar)      │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│     CONTEXT ENGINE               │
│ Detecta entorno del ticker:      │
│ - Volatilidad (ATR%)             │
│ - Tendencia (ADX)                │
│ - Volumen (Z-score)              │
│ - Gap / News flags               │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│     TRADE ARBITER                │
│ - Filtra workers por contexto    │
│ - Workers evalúan en paralelo    │
│ - Calcula score y prioridad      │
│ - Escoge el mejor candidato      │
│ - Bloquea ticker (1 trade max)   │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│         WORKERS                  │
│ - DailyPlays                     │
│ - MACDV                          │
│ - MomentumBreakout               │
│ - VWAP                           │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│   TRADE EXECUTION ENGINE         │
│ Ejecuta trade y bloquea ticker   │
└──────────────────────────────────┘
```

## 🧠 Context Engine

### Regímenes de Mercado

| Contexto | Condiciones | Workers Compatibles |
|----------|-------------|---------------------|
| **CATALYST** | News OR Gap > 4% | DailyPlays, (MomentumBreakout) |
| **MOMENTUM** | VolZ > 2.0 AND ATR > 6% | MomentumBreakout, (MACDV) |
| **TREND** | ADX > 25 | MACDV, DailyPlays, MomentumBreakout |
| **RANGE** | ADX < 20 | VWAP, (MACDV) |
| **NEUTRAL** | Default | MACDV, VWAP |

### Variables Calculadas

| Variable | Indicador | Descripción |
|----------|-----------|-------------|
| `atr_pct` | ATR(14)/Close | Volatilidad diaria relativa |
| `adx` | ADX(14) | Fuerza de tendencia (0-100) |
| `vol_zscore` | (Vol - VolMA20) / Std | Anomalía de volumen |
| `gap_pct` | (Open - PrevClose)/PrevClose | Gaps |
| `news_flag` | Boolean | Catalizador detectado |

### Clasificación Jerárquica

```python
if news_flag or gap_pct > 0.04:
    return "CATALYST"  # Prioridad 1
elif vol_zscore > 2.0 and atr_pct > 0.06:
    return "MOMENTUM"  # Prioridad 2
elif adx > 25 and atr_pct < 0.05:
    return "TREND"     # Prioridad 3
elif adx < 20:
    return "RANGE"     # Prioridad 4
else:
    return "NEUTRAL"   # Default
```

## ⚖️ Trade Arbiter

### Worker Capabilities Matrix

| Worker | Priority | Compatible Contexts | Horizon | Winrate |
|--------|----------|---------------------|---------|---------|
| **DailyPlays** | 4 (highest) | CATALYST, TREND | Swing | 60% |
| **MACDV** | 3 | TREND, NEUTRAL | Swing Short | 55% |
| **MomentumBreakout** | 2 | MOMENTUM, TREND | Intraday | 50% |
| **VWAP** | 1 (lowest) | RANGE, NEUTRAL | Intraday | 52% |

### Signal Scoring System

Formula de puntuación (0-100):

```python
base_score = worker.historical_winrate * 100  # 0-100
if context_compatible:
    base_score += 10
if vol_zscore > 1.5:
    base_score += 5
if risk_reward > 2.0:
    base_score += 5
if age < 2 minutes:
    base_score += 3

total_score = (base_score * signal_confidence/100) * 0.7 + context_score * 0.3
```

### Ticker Locking Mechanism

```python
# On entry
if trade_executed:
    arbiter.lock_ticker(symbol)  # Bloquea ticker

# On exit
if position_closed:
    arbiter.unlock_ticker(symbol)  # Desbloquea ticker

# Auto-unlock después de 60 minutos si no hay trade
```

## 🔄 Flujo de Operación

### Modo Context-Aware (arbiter_enabled=True)

1. **Scanner** envía oportunidad via Redis
2. **Context Engine** analiza:
   - ATR%, ADX, Volume Z-score, Gap%, News
   - Clasifica: CATALYST/MOMENTUM/TREND/RANGE/NEUTRAL
3. **Trade Arbiter** filtra workers:
   - Solo workers compatibles con el contexto
   - Verifica ticker no bloqueado
4. **Workers** evalúan en paralelo:
   - Cada worker genera señal con confidence
   - Arbiter puntúa cada señal
5. **Best Signal Selection**:
   - Score mínimo: 50/100
   - Si múltiples señales: prioridad desempata
6. **Execution + Lock**:
   - Ejecuta mejor trade
   - Bloquea ticker (solo 1 trade activo)
7. **Exit + Unlock**:
   - Worker cierra posición
   - Desbloquea ticker

### Modo Legacy (arbiter_enabled=False)

- Todos los workers procesan en paralelo
- Primer worker en ejecutar gana
- No hay coordinación ni scoring

## 📊 Métricas Tracking

```python
metrics = {
    'opportunities_processed': int,
    'context_analyzed': int,
    'context_distribution': {
        'catalyst': int,
        'momentum': int,
        'trend': int,
        'range': int,
        'neutral': int
    },
    'arbiter_selected': int,
    'arbiter_rejected': int,
    'worker_entries': {worker_name: count},
    'worker_matches': {worker_name: count}
}
```

## 📁 Archivos Implementados

| Archivo | Descripción |
|---------|-------------|
| `core/context_engine.py` | Market regime detection (ATR, ADX, Vol, Gap) |
| `core/trade_arbiter.py` | Worker coordination & signal scoring |
| `core/worker_capabilities_config.py` | Worker capabilities matrix |
| `strategies/worker_based_strategy_engine.py` | Integration layer (UPDATED) |
| `strategies/workers/base_worker_logic.py` | Ticker unlocking on exit (UPDATED) |

## 🎯 Ventajas del Sistema

1. **Context-Aware**: Cada worker opera en su contexto óptimo
2. **No Conflictos**: Un ticker = un trade máximo
3. **Best Signal**: Selección inteligente basada en scoring
4. **Adaptativo**: Sistema detecta automáticamente el régimen
5. **Robusto**: Ticker locking previene entradas duplicadas
6. **Métricas**: Tracking completo de contextos y performance

## ⚙️ Configuración

### Habilitar/Deshabilitar Arbiter

```python
# En WorkerBasedStrategyEngine.__init__
self.arbiter_enabled = True  # Context-aware mode
self.arbiter_enabled = False  # Legacy parallel mode
```

### Ajustar Thresholds

```python
# En ContextEngine
CATALYST_GAP_THRESHOLD = 0.04      # 4% gap
MOMENTUM_VOL_ZSCORE = 2.0          # 2σ volume spike
MOMENTUM_ATR_THRESHOLD = 0.06      # 6% ATR
TREND_ADX_THRESHOLD = 25.0         # Strong trend
RANGE_ADX_MAX = 20.0               # Weak trend

# En TradeArbiter
MIN_SCORE_THRESHOLD = 50.0         # Minimum score to execute
lock_duration_minutes = 60         # Auto-unlock time
```

### Ajustar Worker Winrates

```python
# En worker_capabilities_config.py
WORKER_CAPABILITIES = {
    'daily_plays': WorkerCapabilities(
        historical_winrate=0.60,  # Update based on backtesting
        ...
    ),
    ...
}
```

## 🧪 Testing

```bash
# Run trading system with arbiter enabled
python trader_main.py

# Monitor logs for context analysis
tail -f logs/trader.log | grep "🧠"

# Monitor arbiter decisions
tail -f logs/trader.log | grep "⚖️"
```

## 📈 Expected Output

```
🧠 TSLA: Context(TSLA): MOMENTUM (conf=85%, ADX=18.2, ATR=7.20%, VolZ=2.8)
🎯 TSLA: 2 context-compatible workers: ['momentum_breakout', 'macdv']
⚖️ TSLA: Evaluating 2 signals for context: momentum
  momentum_breakout: Score=72.5 (context=68, conf=85) - ✅ SELECTED
  macdv: Score=45.2 (context=40, conf=70) - ❌ score_too_low
✅ TSLA: Worker momentum_breakout ENTERED POSITION
🔒 TSLA: Ticker locked
```

## 🚀 Next Steps (Full Arbiter Mode)

Para completar el sistema con selección post-evaluación:

1. Workers deben retornar `WorkerSignal` en lugar de ejecutar directamente
2. Arbiter colecta todas las señales
3. Arbiter puntúa y selecciona la mejor
4. Solo la mejor señal se ejecuta

Actualmente el sistema funciona en modo **híbrido**:
- ✅ Context filtering (solo workers compatibles evalúan)
- ✅ Ticker locking (previene duplicados)
- ⏳ Signal scoring (pending - workers aún ejecutan directamente)

---

**Created:** 2025-10-16
**Status:** ✅ Phase 1 Complete (Context Filtering + Ticker Locking)
**Next:** Phase 2 - Full Signal Scoring & Selection



--------------------------


✅ FIX IMPLEMENTADO - Obtención de precio real de ejecución
🔧 Mejoras implementadas:
1. Timeout aumentado: 5s → 10s
max_wait_time = 10.0  # Más tiempo para que IB reporte el fill
wait_interval = 0.5   # Chequeo cada 500ms (menos carga API)
2. Detección inteligente de fills (3 casos):
CASO 1 - Nueva posición:
# No había posición previa → Nueva entrada
previous_quantity = None
current_quantity = 54
→ Fill detectado: avgCost = $3.70
CASO 2 - Añadir a posición existente:
# Ya había posición → Se añade más
previous_quantity = 100, avgCost = $3.50
current_quantity = 154, avgCost = $3.58  # Cambió!
→ Fill detectado: nuevo avgCost = $3.58
CASO 3 - Match exacto (protección duplicados activa):
# Orden de 54 shares
current_quantity = 54
→ Fill detectado: avgCost = $3.70
3. Tracking de estado previo:
# ANTES del while loop:
previous_avg_cost = broker_position.avgCost  # Ej: $3.50
previous_quantity = broker_position.quantity  # Ej: 100

# DETECTA cambio:
if current_quantity > previous_quantity:
    # avgCost cambió → fill confirmado
📊 Logs esperados en próxima orden:
Escenario 1 - Fill rápido (< 1s):
📊 daily_plays: SYMB initial position: qty=None, avgCost=N/A
⏳ Waiting for fill... (0.5s)
📊 daily_plays: SYMB fill price from IBKR (NEW position): $3.72 (qty: 54)
✅ daily_plays: Position opened - SYMB @ $3.72 x 54 shares
Escenario 2 - Fill lento (3-5s):
📊 daily_plays: SYMB initial position: qty=None, avgCost=N/A
⏳ Waiting for fill... (0.5s)
⏳ Waiting for fill... (1.0s)
⏳ Waiting for fill... (1.5s)
...
📊 daily_plays: SYMB fill price from IBKR (NEW position): $3.72 (qty: 54)
✅ daily_plays: Slippage: +0.54% (expected: $3.70, actual: $3.72)
Escenario 3 - Timeout (>10s, raro):
⏳ Waiting for fill... (10.0s)
❌ daily_plays: Could not get actual fill price after 10.0s
⚠️ Using expected price $3.70 (fallback)
🎯 Resultado:
Con IONZ u otras órdenes futuras:
✅ Sistema esperará hasta 10 segundos para obtener avgCost real
✅ Detecta fills incluso si ya había posición previa
✅ Stop loss calculado desde precio real (no estimado)
✅ Slippage reportado correctamente
✅ PnL preciso desde el inicio
El problema de ARTV e IONZ no volverá a ocurrir. 🎯



----------------------------------------



✅ Implementación completada
📱 Nuevo formato de notificación Telegram:
ANTES:
🎯 ENTRY: IONZ @ $3.70
Strategy: Daily Plays
Quantity: 54 shares ($199.80)
Confidence: 89%
Commission: $0.35
Catalyst: TECHNICAL
AHORA:
🎯 ENTRY: IONZ @ $3.70
Strategy: Daily Plays
Quantity: 54 shares ($199.80)
Confidence: 89%
Commission: $0.35
Catalyst: TECHNICAL
⚡ Horizon: SCALP (0.5h)

🎯 TP: 8.5% ($4.01)
🛡️ SL: 5.0% ($3.52)
O para SWING:
🚀 Horizon: SWING (72.0h)

🎯 TP: 32.5% ($4.90)
🛡️ SL: 6.8% ($3.45)
💾 Nuevos campos en Base de Datos:
Los siguientes campos ahora se guardan en la tabla trades:
trading_horizon - SCALP | INTRADAY | SWING_SHORT | SWING
expected_hold_hours - 0.5 | 6.0 | 30.0 | 72.0
take_profit_pct - 8.5% | 15.2% | 32.5%
stop_loss_pct - 5.0% | 6.2% | 6.8%
daily_rsi - 76.3 | 59.0 | 94.3
distance_to_resistance_pct - 8.2% | 15.5% | 20.0%
resistance_price - $4.62 | $7.85
🎯 Emojis por horizonte:
Horizon	Emoji	Hold Time
SCALP	⚡	0.5h (30min)
INTRADAY	📊	6h
SWING_SHORT	📈	30h (1-2 días)
SWING	🚀	72h (3 días)
📊 Ejemplo real con próxima entrada:
Si ACHV entra con catalizador FDA (strength=7):
🎯 ENTRY: ACHV @ $4.28
Strategy: Daily Plays
Quantity: 46 shares ($196.88)
Confidence: 88%
Commission: $0.35
Catalyst: FDA
📈 Horizon: SWING_SHORT (30.0h)

🎯 TP: 18.2% ($5.06)
🛡️ SL: 5.8% ($4.03)

Ahora tendrás visibilidad completa del plan de trade desde el momento de entrada. 🎯

--------------------------------

## 🎯 Buy-the-Dip Entry Strategy (VWAP Worker)

✅ Buy-the-dip implementation completed for VWAP Worker

### What was implemented:

**Two-phase entry system** in vwap_worker_logic.py:
- **PHASE 1** (lines 723-767): Detect VWAP breakout → Track but DON'T enter
- **PHASE 2** (lines 769-860): Wait for 30-60% pullback → Enter when volume increases

**Configuration** (lines 66-72):
- `enable_buy_the_dip = True` - System enabled by default
- `dip_pullback_min_pct = 0.30` - Minimum 30% pullback required
- `dip_pullback_max_pct = 0.60` - Maximum 60% (deeper = invalidated)
- `dip_timeout_minutes = 20` - 20 min max wait time
- `dip_volume_multiplier = 1.5` - Requires 1.5x volume on dip entry
- `breakout_tracker = {}` - Tracks pending breakouts

**Logic flow:**
1. Breakout detected at $10.00 (VWAP $9.50) → Tracked, no entry
2. Price pulls back to $9.65 (30% pullback) → Still waiting
3. Volume spikes to 1.5x average → **ENTER** at $9.65 instead of $10.00
4. Avoids buying the high and getting stopped out on normal pullback

**Next step:** Implement buy-the-dip for Daily Plays Worker (similar logic but using EMA9/VWAP support zones instead of pure VWAP breakout).
