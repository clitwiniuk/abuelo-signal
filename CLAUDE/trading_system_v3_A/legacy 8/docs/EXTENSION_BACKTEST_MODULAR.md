# Extensión del Backtest Científico para Análisis Modular

**Fecha**: 2025-12-18
**Objetivo**: Agregar análisis modular al backtest científico existente sin crear sistema nuevo

---

## 🎯 Concepto: Instrumentar el Replay Existente

En lugar de crear nuevo sistema de backtest, **instrumentamos** el replay engine existente para capturar métricas modulares.

### Arquitectura Actual:
```
ScientificBacktester
    ↓
ReplayEngine (reproduce condiciones reales)
    ↓
Worker.should_enter() / should_exit()
    ↓
Trades ejecutados
    ↓
Análisis de P&L, Win Rate, etc.
```

### Nueva Arquitectura (EXTENDIDA):
```
ScientificBacktester
    ↓
ReplayEngine (reproduce condiciones reales)
    ↓ [HOOK 1: Log Scanner Opportunities]
    ↓
TradeArbiter (asigna a worker)
    ↓ [HOOK 2: Log Arbiter Decisions]
    ↓
Worker.should_enter()
    ↓ [HOOK 3: Log Entry Decisions + Rejection Reasons]
    ↓
Worker.should_exit()
    ↓ [HOOK 4: Log MFE/MAE + Exit Reasons]
    ↓
Trades ejecutados
    ↓
Análisis Modular + Análisis Completo
```

---

## 📦 Módulos a Agregar (4 extensiones)

### MÓDULO 1: Scanner Performance Analysis
**Qué hace**: Analiza effectiveness del scanner

**Dónde instrumentar**: ReplayEngine cuando genera opportunities

**Cambios mínimos**:
```python
# En replay_engine.py - Método process_opportunity()

class ReplayEngine:
    def __init__(self):
        self.scanner_analytics = []  # NEW: Track scanner performance

    async def process_opportunity(self, opportunity, timestamp):
        # EXISTING: Generate opportunity
        symbol = opportunity['symbol']
        quality_score = opportunity.get('quality_score', 0)

        # NEW: Log scanner opportunity para análisis posterior
        self.scanner_analytics.append({
            'symbol': symbol,
            'timestamp': timestamp,
            'quality_score': quality_score,
            'catalyst_type': opportunity.get('catalyst_type'),
            # Calcular max move en próximas 1h, 2h, 4h (async task)
        })

        # EXISTING: Continue con worker assignment...
```

**Output al final del backtest**:
```python
def analyze_scanner_performance(self):
    """
    Analiza scanner_analytics acumulados durante replay

    Métricas:
    - Avg max move by quality_score bucket
    - Lead time (scanner detect → max move time)
    - Catalyst effectiveness
    """
    df = pd.DataFrame(self.scanner_analytics)

    # Group by quality_score buckets
    df['score_bucket'] = pd.cut(df['quality_score'], bins=[0, 50, 70, 100])

    results = df.groupby('score_bucket').agg({
        'max_move_1h': 'mean',
        'max_move_2h': 'mean',
        'max_move_4h': 'mean'
    })

    return results
```

---

### MÓDULO 2: Arbiter Decision Analysis
**Qué hace**: Analiza si arbiter elige el mejor worker

**Dónde instrumentar**: TradeArbiter cuando selecciona worker

**Cambios mínimos**:
```python
# En trade_arbiter.py - Método select_best_signal()

class TradeArbiter:
    def __init__(self):
        self.arbiter_analytics = []  # NEW: Track arbiter decisions

    def select_best_signal(self, signals: List[WorkerSignal]) -> Optional[WorkerSignal]:
        # EXISTING: Score all signals
        scored_signals = self._score_signals(signals)

        # EXISTING: Select best
        best_signal = max(scored_signals, key=lambda x: x.total_score)

        # NEW: Log ALL signals para análisis "what if"
        self.arbiter_analytics.append({
            'timestamp': datetime.now(),
            'symbol': signals[0].symbol,
            'all_signals': [
                {
                    'worker': s.worker_name,
                    'confidence': s.confidence,
                    'score': scored.total_score
                }
                for s, scored in zip(signals, scored_signals)
            ],
            'selected_worker': best_signal.worker_name,
            # Simular: ¿Qué habría pasado con cada worker? (async task)
        })

        # EXISTING: Return best
        return best_signal
```

**Output al final del backtest**:
```python
def analyze_arbiter_decisions(self):
    """
    Compara: Worker elegido vs mejor worker retroactivo

    Métricas:
    - % veces que eligió el mejor worker
    - Context matching accuracy
    - Rejection accuracy
    """
    df = pd.DataFrame(self.arbiter_analytics)

    # Para cada decisión, comparar selected_worker con best_worker_retroactive
    accuracy = (df['selected_worker'] == df['best_worker_retroactive']).mean()

    return {
        'selection_accuracy': accuracy,
        'context_match_rate': ...,
        'rejection_accuracy': ...
    }
```

---

### MÓDULO 3: Worker Entry Analysis
**Qué hace**: Analiza timing y filtros de entry logic

**Dónde instrumentar**: Worker.should_enter()

**Cambios mínimos**:
```python
# En base_worker_logic.py - Método should_enter()

class BaseWorkerLogic:
    def __init__(self):
        self.entry_analytics = []  # NEW: Track entry decisions

    async def should_enter(self, opportunity):
        # EXISTING: Validate opportunity
        symbol = opportunity['symbol']

        # EXISTING: Apply filters
        filters_passed = []
        filters_failed = []

        # Price filter
        if self.min_price <= price <= self.max_price:
            filters_passed.append('price_range')
        else:
            filters_failed.append('price_range')

        # Volume filter
        if volume >= self.min_volume:
            filters_passed.append('volume')
        else:
            filters_failed.append('volume')

        # ... más filtros ...

        # EXISTING: Final decision
        should_enter = len(filters_failed) == 0

        # NEW: Log entry decision para análisis
        self.entry_analytics.append({
            'timestamp': datetime.now(),
            'symbol': symbol,
            'accepted': should_enter,
            'filters_passed': filters_passed,
            'filters_failed': filters_failed,
            'rejection_reason': filters_failed[0] if filters_failed else None,
            # Calcular: ¿Qué habría pasado si entraba? (async task)
        })

        # EXISTING: Return decision
        return should_enter
```

**Output al final del backtest**:
```python
def analyze_entry_decisions(self):
    """
    Analiza entry acceptance rate y filter effectiveness

    Métricas:
    - Entry acceptance rate
    - Filter effectiveness (% de rechazos correctos)
    - Missed opportunities (rechazó pero movió)
    """
    df = pd.DataFrame(self.entry_analytics)

    # Filter effectiveness
    filter_stats = {}
    for filter_name in self.all_filters:
        rejections = df[df['filters_failed'].apply(lambda x: filter_name in x)]
        correct_rejections = rejections[rejections['would_have_lost']].shape[0]
        incorrect_rejections = rejections[rejections['would_have_won']].shape[0]

        filter_stats[filter_name] = {
            'total_rejections': len(rejections),
            'correct_rejections': correct_rejections,
            'incorrect_rejections': incorrect_rejections,
            'effectiveness': correct_rejections / len(rejections) if len(rejections) > 0 else 0
        }

    return filter_stats
```

---

### MÓDULO 4: Worker Exit Analysis
**Qué hace**: Analiza timing de exits y MFE/MAE

**Dónde instrumentar**: Worker.should_exit() + Position tracking

**Cambios mínimos**:
```python
# En base_worker_logic.py - Position tracking

class BaseWorkerLogic:
    def __init__(self):
        self.exit_analytics = []  # NEW: Track exit decisions
        self.active_positions_mfe_mae = {}  # NEW: Track MFE/MAE

    async def on_position_opened(self, position):
        """EXISTING: Called when position opens"""
        symbol = position['symbol']
        entry_price = position['entry_price']

        # NEW: Initialize MFE/MAE tracking
        self.active_positions_mfe_mae[symbol] = {
            'entry_price': entry_price,
            'max_favorable': 0.0,   # MFE
            'max_adverse': 0.0,     # MAE
            'entry_time': datetime.now()
        }

    async def on_bar_update(self, symbol, bar):
        """EXISTING: Called on each new bar"""
        # NEW: Update MFE/MAE
        if symbol in self.active_positions_mfe_mae:
            pos = self.active_positions_mfe_mae[symbol]
            entry_price = pos['entry_price']

            # MFE: Max profit seen
            current_profit_pct = ((bar.high - entry_price) / entry_price) * 100
            pos['max_favorable'] = max(pos['max_favorable'], current_profit_pct)

            # MAE: Max drawdown seen
            current_loss_pct = ((entry_price - bar.low) / entry_price) * 100
            pos['max_adverse'] = max(pos['max_adverse'], current_loss_pct)

    async def should_exit(self, position, current_bar):
        # EXISTING: Exit logic
        symbol = position['symbol']
        entry_price = position['entry_price']
        current_price = current_bar.close

        exit_reason = None
        should_exit = False

        # Stop loss
        if current_price <= entry_price * (1 - self.stop_loss_pct):
            exit_reason = 'stop_loss'
            should_exit = True

        # Take profit
        elif current_price >= entry_price * (1 + self.take_profit_pct):
            exit_reason = 'take_profit'
            should_exit = True

        # ... más exit conditions ...

        # NEW: Log exit decision
        if should_exit:
            mfe_mae = self.active_positions_mfe_mae.get(symbol, {})

            self.exit_analytics.append({
                'symbol': symbol,
                'entry_price': entry_price,
                'exit_price': current_price,
                'exit_reason': exit_reason,
                'pnl_pct': ((current_price - entry_price) / entry_price) * 100,
                'mfe': mfe_mae.get('max_favorable', 0),
                'mae': mfe_mae.get('max_adverse', 0),
                'hold_time_minutes': (datetime.now() - mfe_mae.get('entry_time')).total_seconds() / 60
            })

            # Clean up
            del self.active_positions_mfe_mae[symbol]

        return should_exit
```

**Output al final del backtest**:
```python
def analyze_exit_decisions(self):
    """
    Analiza exit timing y parameter optimization

    Métricas:
    - Avg P&L by exit_reason
    - MFE analysis (dinero dejado en mesa)
    - MAE analysis (stop placement quality)
    - Exit parameter optimization
    """
    df = pd.DataFrame(self.exit_analytics)

    # By exit reason
    exit_stats = df.groupby('exit_reason').agg({
        'pnl_pct': 'mean',
        'mfe': 'mean',
        'mae': 'mean'
    })

    # MFE analysis
    avg_mfe = df['mfe'].mean()
    avg_pnl = df['pnl_pct'].mean()
    money_left_on_table = avg_mfe - avg_pnl

    # Parameter optimization
    # Simular: ¿Qué TP/SL darían mejor P&L?
    optimal_tp = ...
    optimal_sl = ...

    return {
        'exit_reason_stats': exit_stats,
        'avg_mfe': avg_mfe,
        'money_left_on_table': money_left_on_table,
        'optimal_tp': optimal_tp,
        'optimal_sl': optimal_sl
    }
```

---

## 🚀 Plan de Implementación (Incremental)

### Fase 1: Módulo 4 - Exit Analysis (MÁS FÁCIL)
**Archivos a modificar**:
1. `strategies/workers/base_worker_logic.py`
   - Agregar `exit_analytics = []`
   - Agregar `active_positions_mfe_mae = {}`
   - Modificar `on_position_opened()` para inicializar MFE/MAE
   - Modificar `on_bar_update()` para actualizar MFE/MAE
   - Modificar `should_exit()` para loggear decisión

2. `scientific_backtest/backtest_worker_scientific.py`
   - Agregar método `analyze_exit_performance(worker)`
   - Generar reporte de exits al final

**Tiempo estimado**: 2-3 horas
**Impacto**: Alto (optimización de exits mejora P&L inmediatamente)

---

### Fase 2: Módulo 3 - Entry Analysis
**Archivos a modificar**:
1. `strategies/workers/base_worker_logic.py`
   - Agregar `entry_analytics = []`
   - Modificar `should_enter()` para loggear filtros passed/failed

2. `scientific_backtest/backtest_worker_scientific.py`
   - Agregar método `analyze_entry_performance(worker)`
   - Calcular filter effectiveness

**Tiempo estimado**: 3-4 horas
**Impacto**: Medio (identificar filtros que ayudan/perjudican)

---

### Fase 3: Módulo 1 - Scanner Analysis
**Archivos a modificar**:
1. `replay_testing/core/replay_engine.py`
   - Agregar `scanner_analytics = []`
   - Modificar `process_opportunity()` para loggear

2. `scientific_backtest/backtest_worker_scientific.py`
   - Agregar método `analyze_scanner_performance()`
   - Calcular quality_score effectiveness

**Tiempo estimado**: 4-5 horas
**Impacto**: Medio (validar si scanner detecta buenos tickers)

---

### Fase 4: Módulo 2 - Arbiter Analysis
**Archivos a modificar**:
1. `core/trade_arbiter.py`
   - Agregar `arbiter_analytics = []`
   - Modificar `select_best_signal()` para loggear

2. `scientific_backtest/backtest_worker_scientific.py`
   - Agregar método `analyze_arbiter_decisions()`
   - Simular "what if" con otros workers

**Tiempo estimado**: 5-6 horas
**Impacto**: Bajo al principio (solo tienes 2 workers activos)

---

## 📊 Ejemplo de Output Integrado

Cuando ejecutes:
```bash
python backtest_worker_scientific.py --worker vcp_smallcap
```

**Output ACTUAL** (sistema existente):
```
VCP_SMALLCAP BACKTEST
=====================
Total P&L: $173.95
Win Rate: 64.7%
Profit Factor: 2.15
VERDICT: ✅ MANTENER Y ESCALAR
```

**Output NUEVO** (con análisis modular):
```
VCP_SMALLCAP BACKTEST - ANÁLISIS COMPLETO
==========================================

📊 OVERALL PERFORMANCE
Total P&L: $173.95
Win Rate: 64.7%
Profit Factor: 2.15

🔍 MODULE 1: SCANNER ANALYSIS
Quality Score Effectiveness:
  0-50:   Avg move = +3.2%  (Scanner noise)
  50-70:  Avg move = +8.1%  (Decent)
  70-100: Avg move = +15.4% (GOOD!)
Scanner Lead Time: 23 min avg
Verdict: ✅ Scanner is effective

🔍 MODULE 2: ARBITER ANALYSIS
(SKIP - Solo 1 worker activo)

🔍 MODULE 3: ENTRY ANALYSIS
Entry Acceptance Rate: 23.9% (34/142 opportunities)
Filter Effectiveness:
  ✅ quality_score:        84.4% helpful
  ✅ resistance_proximity: 83.3% helpful
  ❌ price_range:          37.5% harmful (too strict)
Missed Opportunities: 28.7% (rejected but moved +10%)
Verdict: ⚠️ Relax price_range filter

🔍 MODULE 4: EXIT ANALYSIS
Exit Reason Breakdown:
  Take Profit: 12 trades → +$142.50 avg
  Stop Loss:   8 trades  → -$48.30 avg
  Trailing:    9 trades  → +$67.80 avg (cut 6 winners early)

MFE Analysis:
  Avg MFE: +18.2%  (Current TP = 15%)
  Money left on table: +3.2% per trade  ⚠️

MAE Analysis:
  Avg MAE: -3.1%  (Current SL = 5%)
  Stop placement: ✅ GOOD

Verdict: ⚠️ Optimize exits
Recommendations:
  1. Increase TP: 15% → 18%
  2. Widen trailing_distance: 4% → 5%
  3. Keep SL at 5%

🎯 FINAL VERDICT: ✅ MANTENER Y ESCALAR
ACTION ITEMS:
  1. Relax price_range filter (Entry Module)
  2. Increase TP to 18% (Exit Module)
  3. Widen trailing to 5% (Exit Module)
```

---

## ✅ Ventajas de Este Enfoque

1. **No crea sistema nuevo**: Extiende replay engine existente
2. **Incremental**: Implementas 1 módulo a la vez
3. **Backwards compatible**: Sistema actual sigue funcionando
4. **Reutiliza infraestructura**: DB, OHLC data, replay logic
5. **Debugging fácil**: Análisis modular identifica problema exacto

---

## 💡 Recomendación Inmediata

**EMPEZAR CON MÓDULO 4** (Exit Analysis):

1. Agregar tracking de MFE/MAE (5 líneas de código)
2. Loggear exit_reason en cada exit (3 líneas)
3. Calcular análisis al final del backtest (20 líneas)

**Beneficio**: Optimización de exits mejora P&L un 20-30% típicamente.

**Tiempo**: 2-3 horas de desarrollo.

**Resultado**: Sabrás EXACTAMENTE si tus TPs/SLs/trailing son óptimos.

---

¿Quieres que empiece implementando el Módulo 4 (Exit Analysis) como prueba de concepto?
