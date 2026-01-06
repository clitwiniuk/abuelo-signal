# Análisis End-to-End: Livermore Intraday Worker

## Overview

Análisis completo del flujo del worker Livermore desde la detección de oportunidades hasta la venta de acciones, siguiendo los principios de Jesse Livermore.

**Filosofía Core**:
> "The big money is made by the sitting, not the trading."
> "Buy the breakout of the consolidation (Pivot Point), not the initial move."

---

## Tabla de Contenidos

1. [Fuente de Oportunidades](#1-fuente-de-oportunidades)
2. [Routing al Worker](#2-routing-al-worker)
3. [Lógica de Entrada (State Machine)](#3-lógica-de-entrada-state-machine)
4. [Gestión de Posiciones](#4-gestión-de-posiciones)
5. [Lógica de Salida](#5-lógica-de-salida)
6. [Flujo Completo Visualizado](#6-flujo-completo-visualizado)
7. [Archivos Clave](#7-archivos-clave)

---

## 1. Fuente de Oportunidades

### 1.1 Proactive Scanner (Day 0)

Ubicación: [scanner/smallcap/proactive_scanner.py](../scanner/smallcap/proactive_scanner.py)

El **Proactive Scanner** detecta "Green Day 1" patterns:

```python
# Criterios de detección (líneas 363-424)
def _is_green_day_1(df: pd.DataFrame) -> bool:
    """
    1. Vela verde: Close > Open
    2. Relative Volume > 3x promedio 10 días
    3. Volumen absoluto > 4M shares (liquidez institucional)
    4. Ganancia 20-150%
    5. Retención > 45% (close cerca del high)
    6. No fue green ayer (evita Day 2+)
    """
```

**Validación adicional**:
- **Catalizador**: FinBERT analiza noticias (FDA, M&A, Earnings)
- **Borrow Status**: Requiere ETB (Easy To Borrow) en Day 0
- **Quality Score**: Mínimo 50 pts con catalizador, 65 sin catalizador

**Almacenamiento**: Base de datos `proactive_candidates`

```sql
INSERT INTO proactive_candidates (
    symbol,
    detection_date,
    pattern_type,        -- 'GREEN_DAY_1'
    status,              -- 'WATCHING'
    metrics,             -- JSON: {rel_vol, quality_score, catalyst_type, ...}
    key_levels           -- JSON: {day1_high, day1_low, resistance, ...}
)
```

### 1.2 Monitorización Day 1-7

Ubicación: [proactive_scanner.py:593-683](../scanner/smallcap/proactive_scanner.py#L593-L683)

Cada día (premarket/postmarket), el scanner:

1. **Fetches daily bars** (últimos 10 días)
2. **Analiza estructura diaria**:
   - `BREAKOUT`: Primera rotura de day1_high >1%
   - `HIGHER_HIGH`: Nuevo high >0.5% sobre anterior
   - `INSIDE_DAY`: Consolidación (high ≤ anterior)
   - `LOWER_HIGH`: Intento débil
3. **Actualiza niveles clave**: `resistance`, `day2_high`, `day3_high`...
4. **Verifica borrow status**: Detecta cambios ETB→HTB

**Ejemplo de candidato activo**:
```json
{
  "symbol": "TQQQ",
  "detection_date": "2025-12-26",
  "status": "WATCHING",
  "metrics": {
    "rel_vol": 4.2,
    "quality_score": 68.5,
    "catalyst_type": "FDA",
    "squeeze_quality": "NORMAL"
  },
  "key_levels": {
    "day1_high": 3.95,
    "day1_low": 3.10,
    "resistance": 4.15,
    "day2_high": 4.15,
    "daily_structure": "HIGHER_HIGH"
  }
}
```

### 1.3 Smallcap Daily Scanner (Intraday)

Ubicación: [scanner/smallcap/smallcap_daily_scanner.py:2748-2782](../scanner/smallcap/smallcap_daily_scanner.py#L2748-L2782)

Durante market hours, el **SmallcapDailyScanner**:

1. **Carga candidatos activos** de BD:
```python
def _load_proactive_watchlist() -> Dict[str, Dict]:
    """
    SELECT symbol, metrics, key_levels
    FROM proactive_candidates
    WHERE status IN ('WATCHING', 'TRIGGERED')
    AND detection_date >= date('now', '-7 days')
    """
```

2. **Obtiene datos intraday** via IBKR:
   - Precio actual
   - Volumen
   - Relative volume
   - VWAP

3. **Valida condiciones** (líneas 1687-1707):
   - Quality score >= threshold
   - Short squeeze metrics (si aplica)

4. **Crea SmallcapPlay** con routing:
```python
targets = ['livermore_intraday']  # Si es proactive
opp_type = OpportunityType.LIVERMORE_INTRADAY

SmallcapPlay(
    symbol=symbol,
    opportunity_type=OpportunityType.LIVERMORE_INTRADAY,
    strategy_targets=['livermore_intraday'],
    # ... contexto, métricas, niveles clave
)
```

---

## 2. Routing al Worker

### 2.1 Worker-Based Strategy Engine

Ubicación: [strategies/worker_based_strategy_engine.py:488-544](../strategies/worker_based_strategy_engine.py#L488-L544)

```python
async def process_opportunity(opportunity: Dict):
    """
    1. Verifica extended hours (si permitido)
    2. Analiza market context (si arbiter habilitado)
    3. Determina workers relevantes
    4. Envía a workers en paralelo
    """
```

### 2.2 Routing Logic

**Opción A: Targeted Routing** (Preferido para Livermore)

```python
# Si opportunity tiene strategy_targets=['livermore_intraday']
target_strategy = opportunity.get('strategy')
if target_strategy == 'livermore_intraday':
    return ['livermore_intraday']  # Solo a Livermore
```

**Opción B: Universal Routing** (Fallback)

```python
# Todos los workers reciben la oportunidad
workers = ['daily_plays', 'vwap_breakout', 'livermore_intraday', ...]
# Cada worker decide si el patrón aplica
```

### 2.3 Worker Initialization

Ubicación: [worker_based_strategy_engine.py:232-242](../strategies/worker_based_strategy_engine.py#L232-L242)

```python
livermore_enabled = getattr(config, 'livermore_intraday_strategy_enabled', True)

if livermore_enabled:
    self.workers['livermore_intraday'] = LivermoreIntradayWorkerLogic(
        execution_engine=execution_engine,
        risk_manager=risk_manager,
        config=config
    )
```

---

## 3. Lógica de Entrada (State Machine)

### 3.1 Filosofía de Entrada

Ubicación: [livermore_intraday_worker_logic.py:9-18](../strategies/workers/livermore_intraday_worker_logic.py#L9-L18)

```
PIPELINE:
1. OBSERVATION (Evento): Detecta movimiento inusual (Rango/Volumen)
2. PAUSE (Pivote): Espera consolidación saludable (Volumen bajando, precio aguantando)
3. ENTRY (Continuación): Compra el breakout de la pausa con volumen
```

### 3.2 Estados (LivermorePhase)

```python
class LivermorePhase(Enum):
    OBSERVATION = "OBSERVATION"  # Detected initial move (Green Day 1)
    PAUSE = "PAUSE"              # Consolidating/Flagging (Day 2-7)
    READY = "READY"              # Ready for breakout entry
    ACTIVE = "ACTIVE"            # Position open
```

### 3.3 Candidatos Internos (In-Memory State)

```python
@dataclass
class LivermoreCandidate:
    symbol: str
    phase: LivermorePhase
    detection_time: datetime
    initial_high: float        # High of initial impulse (Day 1 high)
    initial_low: float         # Low of initial impulse (Day 1 low)
    pause_high: float = 0.0    # High of consolidation (breakout level)
    pause_low: float = 0.0     # Low of consolidation (STOP LOSS level)
    vol_at_detection: float = 0.0
    last_update: datetime = None
```

### 3.4 State Machine Flow

Ubicación: [livermore_intraday_worker_logic.py:99-150](../strategies/workers/livermore_intraday_worker_logic.py#L99-L150)

```python
async def should_enter(opportunity: Dict) -> bool:
    """
    Entry decision tree
    """
    symbol = opportunity['symbol']
    bars = get_bars_from_opportunity(opportunity)

    # --- CASE 0: NEW CANDIDATE ---
    if symbol not in self.watched_candidates:
        self._evaluate_new_candidate(symbol, bars, ...)
        return False  # Never enter on first sight

    # --- CASE 1: EXISTING CANDIDATE ---
    candidate = self.watched_candidates[symbol]

    if candidate.phase == LivermorePhase.OBSERVATION:
        self._update_observation_phase(candidate, bars, current_price)
        return False  # Still watching

    if candidate.phase == LivermorePhase.PAUSE:
        # CHECK FOR BREAKOUT ENTRY
        if self._check_breakout_entry(candidate, bars, current_price, opportunity):
            # SET STOP LOSS
            opportunity['stop_loss_price'] = candidate.pause_low
            opportunity['strategy_note'] = "Livermore Breakout"

            # REMOVE FROM WATCHLIST (now active)
            del self.watched_candidates[symbol]

            return True  # 🎩 ENTER!
        else:
            # Validate pause integrity
            self._validate_pause_integrity(candidate, current_price)
            return False

    return False
```

### 3.5 Step-by-Step Entry Logic

#### Step 1: Evaluate New Candidate (OBSERVATION)

Ubicación: [livermore_intraday_worker_logic.py:152-172](../strategies/workers/livermore_intraday_worker_logic.py#L152-L172)

```python
def _evaluate_new_candidate(symbol, bars, opportunity):
    """
    Detectar impulso inicial (Reaction)
    """
    recent_bars = bars[-10:]  # Last 10 bars
    low = min(b.low for b in recent_bars)
    high = max(b.high for b in recent_bars)

    impulse_pct = ((high - low) / low) * 100
    vol_ratio = opportunity.get('volume_ratio', 1.0)

    # CRITERIA:
    # - impulse_pct >= 3.0%  (min_impulse_range)
    # - vol_ratio >= 1.5x    (min_impulse_vol)

    if impulse_pct >= 3.0 and vol_ratio >= 1.5:
        # Add to watchlist
        self.watched_candidates[symbol] = LivermoreCandidate(
            symbol=symbol,
            phase=LivermorePhase.OBSERVATION,
            detection_time=datetime.now(),
            initial_high=high,
            initial_low=low,
            vol_at_detection=vol_ratio
        )
        logger.info(f"👀 {symbol}: Added to Livermore Watchlist (Impulse: {impulse_pct:.1f}%)")
```

**Ejemplo**:
- TQQQ detectado en Proactive Scanner (Day 0)
- Scanner intraday envía oportunidad: `price=$3.85, vol_ratio=4.2x`
- Worker calcula: `impulse_pct = 25.3%` (desde $3.10 a $3.95)
- ✅ Añadido a watchlist en fase `OBSERVATION`

#### Step 2: Update Observation Phase (PAUSE Detection)

Ubicación: [livermore_intraday_worker_logic.py:174-202](../strategies/workers/livermore_intraday_worker_logic.py#L174-L202)

```python
def _update_observation_phase(candidate, bars, current_price):
    """
    Detectar inicio de pausa (consolidación)
    """
    # Livermore quiere ver STRENGTH (no más del 40% de retroceso)
    retrace_limit = initial_high - (initial_high - initial_low) * 0.40

    if current_price < retrace_limit:
        # ❌ Dropped too much - discard
        del self.watched_candidates[symbol]
        return

    if current_price >= candidate.initial_high:
        # 📈 Still expanding - update high
        candidate.initial_high = max(candidate.initial_high, current_price)
        return

    if current_price < candidate.initial_high:
        # ⏸️ Trading below high → PAUSE phase
        candidate.phase = LivermorePhase.PAUSE
        candidate.pause_high = candidate.initial_high  # Level to break
        candidate.pause_low = min(b.low for b in bars[-3:])  # Stop loss level

        logger.info(f"⏸️ {symbol}: Entering PAUSE phase. Watch for break of {pause_high}")
```

**Ejemplo**:
- Day 1: TQQQ cierra en $3.95 (initial_high)
- Day 2: TQQQ abre $3.88, tradea entre $3.80-$3.92 (no rompe high)
- Worker detecta: `current_price ($3.88) < initial_high ($3.95)`
- ✅ Promoción a fase `PAUSE`, pause_high=$3.95, pause_low=$3.80

#### Step 3: Check Breakout Entry (READY → ACTIVE)

Ubicación: [livermore_intraday_worker_logic.py:214-228](../strategies/workers/livermore_intraday_worker_logic.py#L214-L228)

```python
def _check_breakout_entry(candidate, bars, current_price, opportunity):
    """
    Entry trigger: Breakout de la pausa con volumen
    """
    # 1. Price breaks pause_high
    if current_price > candidate.pause_high:
        # 2. Volume confirmation
        vol_ratio = opportunity.get('volume_ratio', 1.0)

        if vol_ratio >= 1.2:  # breakout_vol_ratio
            # 3. Remove from watchlist (now entering)
            del self.watched_candidates[symbol]

            return True  # 🎩 ENTER!

    return False
```

**Ejemplo**:
- Day 3 @ 10:45 AM: TQQQ rompe $3.95 con volumen 2.1x promedio
- Worker detecta: `current_price ($3.97) > pause_high ($3.95)` AND `vol_ratio (2.1) >= 1.2`
- ✅ **ENTRY TRIGGERED**

#### Step 4: Execute Entry

Ubicación: [base_worker_logic.py:368-448](../strategies/workers/base_worker_logic.py#L368-L448)

```python
async def process_opportunity(opportunity: Dict) -> bool:
    """
    1. Verifica si ya tenemos posición
    2. Verifica failed entries (max 2 attempts)
    3. Llama a should_enter() del worker
    4. Si True, ejecuta via execution_engine
    """

    symbol = opportunity['symbol']

    # Check if already have position
    if symbol in self.active_positions:
        return False

    # Check failed entries
    if symbol in self.failed_entries:
        if self.failed_entries[symbol]['attempts'] >= 2:
            return False  # Blacklisted

    # EVALUATE ENTRY
    should_enter = await self.should_enter(opportunity)

    if should_enter:
        # EXECUTE via ExecutionEngine
        position = await self.execution_engine.enter_position(
            symbol=symbol,
            side='BUY',
            quantity=calculate_quantity(...),
            stop_loss=opportunity.get('stop_loss_price'),  # pause_low
            metadata={
                'worker': 'livermore_intraday',
                'strategy': 'Livermore Breakout',
                'entry_reason': 'Pause breakout with volume'
            }
        )

        if position:
            # Add to active positions
            self.active_positions[symbol] = {
                'position': position,
                'entry_time': datetime.now(),
                'opportunity_data': opportunity
            }

            return True
```

**Ejecución real**:
1. **Cálculo de cantidad**: Risk manager calcula shares basado en:
   - Account size
   - Risk per trade (típicamente 1-2% del capital)
   - Distance to stop: `(entry_price - stop_loss) / entry_price`

2. **Orden IBKR**:
   ```python
   # Via IBKRAdapter
   order = MarketOrder('BUY', quantity)
   trade = ib.placeOrder(contract, order)
   ```

3. **Almacenamiento**:
   ```sql
   INSERT INTO trades (
       symbol, strategy, side, quantity,
       entry_price, stop_loss_price,
       entry_time, status
   ) VALUES (
       'TQQQ', 'livermore_intraday', 'BUY', 250,
       3.97, 3.80,
       '2025-12-26 10:45:00', 'OPEN'
   )
   ```

---

## 4. Gestión de Posiciones

### 4.1 Monitoring Loop

Ubicación: [base_worker_logic.py:211-244](../strategies/workers/base_worker_logic.py#L211-L244)

```python
async def run():
    """
    Worker monitoring loop (runs every 1 second)
    """
    while self.is_running:
        try:
            await self._monitor_positions()
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")

        await asyncio.sleep(1)  # Check every second
```

### 4.2 Position Monitoring

Ubicación: [base_worker_logic.py:1876-1928](../strategies/workers/base_worker_logic.py#L1876-L1928)

```python
async def _monitor_positions():
    """
    Para cada posición activa:
    1. Obtiene precio actual
    2. Verifica forced exits (SHORT positions @ 15:45)
    3. Evalúa should_exit() del worker
    4. Ejecuta salida si necesario
    """
    for symbol, data in self.active_positions.items():
        # Get current price
        current_price = await self._get_current_price(symbol)

        position_data = data['position']

        # Evaluate exit
        should_exit, reason = await self.should_exit(
            symbol=symbol,
            position=position_data,
            current_price=current_price
        )

        if should_exit:
            await self._execute_exit(symbol, reason, current_price)
        else:
            # Log status (every minute)
            self._log_position_status(symbol, data, current_price)
```

### 4.3 Price Updates

```python
async def _get_current_price(symbol: str) -> float:
    """
    Priority order:
    1. BatchPriceManager (if available) - Garantiza precios frescos
    2. IBKR live price
    3. Cached price (last known)
    """
```

---

## 5. Lógica de Salida

### 5.1 Exit Strategy (Livermore Style)

Ubicación: [livermore_intraday_worker_logic.py:230-236](../strategies/workers/livermore_intraday_worker_logic.py#L230-L236)

```python
async def should_exit(symbol: str, position: Dict, current_price: float) -> Tuple[bool, str]:
    """
    Livermore exit: Technical stop + Trailing
    """
    return self.stop_manager.check_exit(symbol, current_price, position['entry_price'])
```

### 5.2 Stop Manager Configuration

Ubicación: [livermore_intraday_worker_logic.py:84-95](../strategies/workers/livermore_intraday_worker_logic.py#L84-L95)

```python
stop_config = WorkerStopConfig(
    stop_loss_pct=5.0,        # Hard stop fallback (Technical is primary)
    take_profit_pct=100.0,    # "Open ended" - let trailing handle
    trailing_activation=3.0,  # Activate trail after 3% gain
    trailing_distance=2.0,    # 2% trailing (tight but fair)
    max_position_hours=6.0    # Intraday max (6 hours)
)
```

### 5.3 Exit Scenarios

#### A. Stop Loss (Technical)

```
Entry: $3.97 (pause breakout)
Stop Loss: $3.80 (pause_low - set at entry)

Si price <= $3.80:
    → EXIT con razón: "Stop Loss Hit - Technical (Pause Low)"
    → P&L: -4.3%
```

#### B. Take Profit (Trailing)

```
Entry: $3.97
Current: $4.15 (+4.5%)

Si gain >= 3.0% (trailing_activation):
    → Activar trailing stop
    → Trail distance: 2.0%
    → Trailing stop price: $4.15 * 0.98 = $4.07

Si price drops a $4.06:
    → EXIT con razón: "Trailing Stop Hit"
    → P&L: +2.3%
```

#### C. Time Stop

```
Entry: 10:45 AM
Current: 4:30 PM (5h 45min)

Si position_hours >= 6.0:
    → EXIT con razón: "Time Stop - Max Position Hours"
    → P&L: Depends on price
```

#### D. Open-Ended (Livermore Style)

```
Entry: $3.97
Day 1 Close: $4.20 (+5.8%)

Si gain < 100% AND hours < 6:
    → NO EXIT
    → Mantener posición con trailing stop activo
    → "Let profits run" (Livermore philosophy)
```

### 5.4 Exit Execution

Ubicación: [base_worker_logic.py:2023-2073](../strategies/workers/base_worker_logic.py#L2023-L2073)

```python
async def _execute_exit(symbol: str, reason: str, current_price: float):
    """
    1. Log exit decision
    2. Call execution_engine.exit_position()
    3. Remove from active_positions
    4. Log final P&L
    """

    logger.info(f"🔴 {symbol}: EXIT triggered - {reason}")

    # Execute via ExecutionEngine
    exit_result = await self.execution_engine.exit_position(
        symbol=symbol,
        reason=reason,
        current_price=current_price
    )

    if exit_result['success']:
        # Remove from active positions
        del self.active_positions[symbol]

        # Log P&L
        pnl = exit_result.get('pnl', 0)
        pnl_pct = exit_result.get('pnl_pct', 0)

        logger.info(
            f"✅ {symbol}: EXIT completed - "
            f"P&L: ${pnl:.2f} ({pnl_pct:+.2f}%) - "
            f"{reason}"
        )
```

**IBKR Order Execution**:
```python
# Via ExecutionEngine → IBKRAdapter
order = MarketOrder('SELL', quantity)
trade = ib.placeOrder(contract, order)

# Wait for fill
while not trade.isDone():
    await asyncio.sleep(0.1)

# Update database
UPDATE trades
SET exit_price = ?, exit_time = ?, pnl = ?, status = 'CLOSED'
WHERE symbol = ? AND status = 'OPEN'
```

---

## 6. Flujo Completo Visualizado

### Timeline Ejemplo: TQQQ Trade

```
DAY 0 (2025-12-26) - DETECTION
==================
09:00 AM - Proactive Scanner detecta Green Day 1
           • TQQQ: +25.3%, 4.2M shares, FDA catalyst
           • Guarda en BD: status='WATCHING', day1_high=$3.95

09:30 AM - Market opens
10:00 AM - SmallcapDailyScanner carga proactive watchlist
           • TQQQ encontrado en BD
           • Envía oportunidad a Livermore Worker

10:01 AM - Livermore Worker: should_enter()
           [CASE 0: NEW CANDIDATE]
           • Calcula impulse: 25.3% (✅ >= 3%)
           • Vol ratio: 4.2x (✅ >= 1.5x)
           • Añade a watched_candidates
           • Phase: OBSERVATION
           • Return False (no entra aún)

11:00 AM - Livermore Worker: should_enter()
           [CASE 1: OBSERVATION → PAUSE]
           • Price $3.88 < initial_high $3.95
           • No retroceso excesivo (✅)
           • Promociona a PAUSE phase
           • pause_high = $3.95
           • pause_low = $3.80
           • Return False (esperando breakout)

DAY 1 (2025-12-27) - CONSOLIDATION
==================
09:30 AM - Market opens, TQQQ en $3.85
10:00 AM - SmallcapDailyScanner envía update
           • Price $3.90, vol 1.8x

10:15 AM - Livermore Worker: should_enter()
           [CASE 1: PAUSE - No breakout]
           • Price $3.90 < pause_high $3.95
           • Valida integridad: ✅ (no bajó mucho)
           • Return False (esperando)

02:00 PM - Price $3.92, consolidando cerca de pause_high

DAY 2 (2025-12-28) - BREAKOUT & ENTRY
==================
10:30 AM - Price action: Rompe $3.95
10:45 AM - SmallcapDailyScanner envía:
           • Symbol: TQQQ
           • Price: $3.97
           • Vol ratio: 2.1x

10:45:15 - Livermore Worker: should_enter()
           [CASE 1: PAUSE → ENTRY CHECK]
           • _check_breakout_entry():
             - current_price ($3.97) > pause_high ($3.95) ✅
             - vol_ratio (2.1x) >= 1.2x ✅
             - DELETE from watched_candidates
             - RETURN TRUE ✅

           • Sets: opportunity['stop_loss_price'] = $3.80

10:45:20 - BaseWorkerLogic.process_opportunity():
           • should_enter() returned TRUE
           • Calculates quantity:
             - Account: $100,000
             - Risk: 1% = $1,000
             - Stop distance: ($3.97 - $3.80) / $3.97 = 4.3%
             - Quantity: $1,000 / ($3.97 * 0.043) = 585 shares

10:45:25 - ExecutionEngine.enter_position()
           • IBKRAdapter places order:
             - Contract: TQQQ (Stock, SMART)
             - Order: Market BUY 585 shares
           • Fill: $3.97 avg (slippage +$0.00)

10:45:30 - Position added to active_positions:
           {
             'symbol': 'TQQQ',
             'side': 'BUY',
             'quantity': 585,
             'entry_price': 3.97,
             'stop_loss': 3.80,
             'entry_time': '2025-12-28 10:45:30'
           }

           Logger: "🎩 TQQQ: LIVERMORE ENTRY TRIGGERED! Breakout of $3.95"

10:46 - 12:00 - Monitoring (every 1 second)
                • _monitor_positions() checks:
                  - Current price
                  - Stop loss ($3.80)
                  - Trailing activation (3% = $4.09)

12:30 PM - Price: $4.15 (+4.5%)
           • Trailing activated (gain >= 3%)
           • Trailing stop: $4.15 * 0.98 = $4.07

01:00 PM - Price: $4.22 (+6.3%)
           • Trailing stop updated: $4.22 * 0.98 = $4.14

01:45 PM - Price drops to $4.10
           • Still above trailing stop ($4.14)
           • No exit

02:15 PM - Price: $4.08 (below trailing $4.14)

02:15:05 - Livermore Worker: should_exit()
           • StopManager.check_exit():
             - current_price ($4.08) < trailing_stop ($4.14)
             - RETURN (True, "Trailing Stop Hit")

02:15:10 - BaseWorkerLogic._execute_exit():
           • Logs: "🔴 TQQQ: EXIT triggered - Trailing Stop Hit"
           • Calls ExecutionEngine.exit_position()

02:15:15 - ExecutionEngine.exit_position():
           • IBKRAdapter places order:
             - Contract: TQQQ
             - Order: Market SELL 585 shares
           • Fill: $4.08 avg

02:15:20 - Database updated:
           UPDATE trades SET
             exit_price = 4.08,
             exit_time = '2025-12-28 14:15:20',
             pnl = (4.08 - 3.97) * 585 = $64.35,
             pnl_pct = 2.77%,
             status = 'CLOSED'

02:15:25 - Position removed from active_positions
           Logger: "✅ TQQQ: EXIT completed - P&L: $64.35 (+2.77%) - Trailing Stop Hit"

RESUMEN TRADE:
==============
Entry: $3.97 @ 10:45:30 (Day 2)
Exit: $4.08 @ 14:15:20 (Day 2)
Duration: 3h 30min
Shares: 585
P&L: +$64.35 (+2.77%)
Strategy: Livermore Breakout
Exit Reason: Trailing Stop Hit
```

---

## 7. Archivos Clave

### Componentes del Sistema

| Componente | Archivo | Responsabilidad |
|------------|---------|-----------------|
| **Detección Day 0** | [proactive_scanner.py](../scanner/smallcap/proactive_scanner.py) | Detecta Green Day 1, valida catalizador, guarda en BD |
| **Monitorización Day 1-7** | [proactive_scanner.py:593-683](../scanner/smallcap/proactive_scanner.py#L593-L683) | Actualiza niveles, estructura diaria |
| **Scanner Intraday** | [smallcap_daily_scanner.py](../scanner/smallcap/smallcap_daily_scanner.py) | Carga watchlist, envía oportunidades |
| **Strategy Engine** | [worker_based_strategy_engine.py](../strategies/worker_based_strategy_engine.py) | Routing, coordinación workers |
| **Livermore Worker** | [livermore_intraday_worker_logic.py](../strategies/workers/livermore_intraday_worker_logic.py) | State machine, lógica entrada |
| **Base Worker** | [base_worker_logic.py](../strategies/workers/base_worker_logic.py) | Monitoring, ejecución |
| **Execution Engine** | [core/trading_execution_stage.py](../core/trading_execution_stage.py) | Órdenes IBKR, risk management |
| **Database** | [core/database_manager.py](../core/database_manager.py) | Almacenamiento trades, candidatos |

### Configuración

**config.ini**:
```ini
[LIVERMORE_INTRADAY_STRATEGY]
# Enable/Disable
livermore_intraday_strategy_enabled = True

# Entry criteria
min_impulse_range = 3.0         # Min 3% move
min_impulse_vol = 1.5           # Min 1.5x relative volume
min_pause_candles = 3           # Min consolidation
max_pause_drawdown = 0.40       # Max 40% retrace
breakout_vol_ratio = 1.2        # Volume on breakout

# Risk Management
stop_loss_pct = 5.0             # Hard stop fallback
take_profit_pct = 100.0         # Open-ended
trailing_activation = 3.0       # After 3% gain
trailing_distance = 2.0         # 2% trail
max_position_hours = 6.0        # Max hold time
```

---

## Conclusión

El **Livermore Intraday Worker** implementa un sistema completo de 3 fases:

1. **OBSERVATION**: Detecta impulsos iniciales (Green Day 1) via Proactive Scanner
2. **PAUSE**: Espera consolidación saludable, establece niveles técnicos
3. **ENTRY**: Compra breakout con volumen, stop loss técnico estricto

**Filosofía**: "Buy the breakout, not the initial move" + "Let profits run"

**Protección**: Stop loss técnico (pause low) + Trailing stop (2%) + Time stop (6h)

**Estado**: ✅ COMPLETAMENTE INTEGRADO Y OPERATIVO