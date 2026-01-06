# Ejemplo de Migración: Clock Abstraction

Este documento muestra cómo migrar componentes existentes para usar `TimeProvider`, usando casos reales del sistema.

---

## Caso 1: AsyncEventBus - Event Timestamps

### ANTES (No-determinístico)

```python
# core/events.py línea 107-117
def create_bar_event(bar_data: 'MarketData') -> Event:
    """Create a bar received event"""
    return Event(
        event_id="",
        event_type=EventTypes.BAR_RECEIVED,
        timestamp=datetime.now(),  # ❌ PROBLEMA: Tiempo del sistema
        data={
            "symbol": bar_data.symbol,
            "bar": bar_data
        }
    )
```

**Problema:**
- En **live**: `datetime.now()` = tiempo actual del sistema ✅
- En **replay**: `datetime.now()` = tiempo del sistema (no del histórico) ❌
- Evento marcado con timestamp incorrecto

### DESPUÉS (Determinístico)

```python
# core/events.py (migrado)
from core.time_provider import TimeProvider, get_clock

def create_bar_event(bar_data: 'MarketData',
                     clock: TimeProvider = None) -> Event:
    """
    Create a bar received event

    Args:
        bar_data: Market data
        clock: Time provider (None = usa global clock)
    """
    if clock is None:
        clock = get_clock()  # Global clock (live = system, replay = simulated)

    return Event(
        event_id="",
        event_type=EventTypes.BAR_RECEIVED,
        timestamp=clock.now(),  # ✅ SOLUCIÓN: Inyectado
        data={
            "symbol": bar_data.symbol,
            "bar": bar_data
        }
    )
```

**Beneficio:**
- En **live**: `clock = SystemTimeProvider()` → comportamiento igual que antes
- En **replay**: `clock = SimulatedTimeProvider()` → usa timestamp histórico
- **Backward compatible**: Si no pasas clock, usa global (default = system)

---

## Caso 2: ExecutionEngineAdapter - Entry Timestamps

### ANTES (No-determinístico)

```python
# core/execution_engine_adapter.py línea 163-169
entry_request = {
    'strategy': strategy,
    'opportunity_data': opportunity_data,
    'pattern_completion': pattern_completion,
    'timestamp': datetime.now()  # ❌ PROBLEMA
}
self._pending_entries[symbol].append(entry_request)

await asyncio.sleep(0.05)  # ❌ PROBLEMA: Race condition
```

**Problemas:**
1. `datetime.now()` en replay = tiempo del sistema
2. `asyncio.sleep(0.05)` no es determinístico (scheduler-dependent)

### DESPUÉS (Determinístico)

```python
# core/execution_engine_adapter.py (migrado)
from core.time_provider import TimeProvider, SystemTimeProvider

class ExecutionEngineAdapter:
    def __init__(self, broker, risk_manager, config,
                 clock: TimeProvider = None):
        """
        Args:
            broker: IBKRAdapter instance
            risk_manager: RiskManager instance
            config: Configuration dict
            clock: Time provider (None = SystemTimeProvider for live)
        """
        self.broker = broker
        self.risk_manager = risk_manager
        self.config = config
        self.clock = clock or SystemTimeProvider()  # ✅ Inyectado

        # ... resto de init

    async def enter_position(self, symbol, strategy,
                            opportunity_data, pattern_completion):
        """Enter position with deterministic timestamps"""

        # Registrar entrada con timestamp determinístico
        entry_request = {
            'strategy': strategy,
            'opportunity_data': opportunity_data,
            'pattern_completion': pattern_completion,
            'timestamp': self.clock.now()  # ✅ SOLUCIÓN
        }

        if symbol not in self._pending_entries:
            self._pending_entries[symbol] = []

        self._pending_entries[symbol].append(entry_request)

        # ✅ SOLUCIÓN: Eliminado asyncio.sleep()
        # Competencia se resuelve sincrónicamente

        # Decidir ganador inmediatamente (determinístico)
        pending = self._pending_entries[symbol]
        if len(pending) > 1:
            # Ordenar por pattern_completion (mayor a menor)
            # En empate: alfabético por strategy (determinístico)
            best_entry = max(pending,
                           key=lambda x: (x['pattern_completion'],
                                        -ord(x['strategy'][0])))

            if best_entry['strategy'] != strategy:
                # Perdimos
                self._pending_entries[symbol] = [
                    e for e in pending if e['strategy'] != strategy
                ]
                return None

        # Ganamos o somos únicos
        self._pending_entries[symbol] = []

        # ... resto de ejecución
```

**Beneficio:**
- ✅ Timestamps determinísticos (live y replay)
- ✅ Sin race conditions (no sleep)
- ✅ Competencia reproducible (mismo ganador)

---

## Caso 3: ExtendedHoursManager - Market Session Detection

### ANTES (No-determinístico)

```python
# core/extended_hours_manager.py
class ExtendedHoursManager:
    def get_market_session(self) -> MarketSession:
        """Get current market session"""
        now = datetime.now()  # ❌ PROBLEMA
        et_time = self._to_eastern(now)

        # Check day of week
        if et_time.weekday() >= 5:
            return MarketSession.CLOSED

        # Check time of day
        hour = et_time.hour
        if hour < 9 or (hour == 9 and et_time.minute < 30):
            return MarketSession.PRE_MARKET
        elif hour < 16:
            return MarketSession.REGULAR
        # ...
```

**Problema:**
- En **replay de jueves histórico** ejecutado un **domingo**:
  - `datetime.now()` = domingo 14:00
  - `get_market_session()` = CLOSED ❌
  - Rechaza entries que deberían ser válidas

### DESPUÉS (Determinístico)

```python
# core/extended_hours_manager.py (migrado)
from core.time_provider import TimeProvider, SystemTimeProvider

class ExtendedHoursManager:
    def __init__(self, clock: TimeProvider = None):
        """
        Args:
            clock: Time provider (None = SystemTimeProvider)
        """
        self.clock = clock or SystemTimeProvider()

    def get_market_session(self, timestamp: datetime = None) -> MarketSession:
        """
        Get market session for given time

        Args:
            timestamp: Specific time (None = use clock.now())

        Returns:
            MarketSession: Current session
        """
        if timestamp is None:
            timestamp = self.clock.now()  # ✅ SOLUCIÓN

        et_time = self._to_eastern(timestamp)

        # Check day of week
        if et_time.weekday() >= 5:
            return MarketSession.CLOSED

        # Check time of day
        hour = et_time.hour
        minute = et_time.minute

        if hour < 4:
            return MarketSession.CLOSED
        elif hour < 9 or (hour == 9 and minute < 30):
            return MarketSession.PRE_MARKET
        elif hour < 16:
            return MarketSession.REGULAR
        elif hour < 20:
            return MarketSession.AFTER_MARKET
        else:
            return MarketSession.CLOSED
```

**Beneficio:**
- En **live**: `clock.now()` = tiempo actual → correcto
- En **replay**: `clock.now()` = 2025-10-24 14:00 (jueves) → REGULAR session ✅
- Extended hours entries reproducibles

---

## Caso 4: ReplayEngine - Simulated Time Injection

### ANTES (Problema)

```python
# replay_testing/core/replay_engine.py línea 385-425
def replay_day(self, date: str, worker_names: List[str]):
    """Replay a single day"""

    # Load bars
    bars_by_symbol = self._load_market_data(date, None)

    for symbol, bars in bars_by_symbol.items():
        for bar in bars:
            # Process bar
            opportunity = self._bar_to_opportunity(bar, None, None)

            # Workers evalúan
            decision = await worker.should_enter(opportunity)

            # PROBLEMA: worker usa datetime.now() internamente
            # → Timestamp incorrecto
```

### DESPUÉS (Solución)

```python
# replay_testing/core/replay_engine.py (migrado)
from core.time_provider import SimulatedTimeProvider, set_clock

class ReplayEngine:
    def __init__(self, market_data_db, trading_data_db):
        self.market_data_db = market_data_db
        self.trading_data_db = trading_data_db

        # ✅ SOLUCIÓN: Crear clock simulado
        self.clock = SimulatedTimeProvider()

    def replay_day(self, date: str, worker_names: List[str]):
        """Replay a single day with simulated time"""

        # ✅ SOLUCIÓN: Establecer clock global para replay
        set_clock(self.clock)

        try:
            # Load bars
            bars_by_symbol = self._load_market_data(date, None)

            for symbol, bars in bars_by_symbol.items():
                for bar in bars:
                    # ✅ SOLUCIÓN: Avanzar tiempo simulado
                    self.clock.set_time(bar.timestamp)

                    # Ahora TODO el código ve el tiempo correcto
                    # - Events: timestamp = clock.now() = bar.timestamp ✅
                    # - Market hours: clock.now() = bar.timestamp ✅
                    # - Entry timestamps: clock.now() = bar.timestamp ✅

                    opportunity = self._bar_to_opportunity(bar, None, None)

                    # Workers evalúan con tiempo correcto
                    decision = await worker.should_enter(opportunity)

        finally:
            # ✅ SOLUCIÓN: Restaurar clock real al terminar
            from core.time_provider import reset_clock
            reset_clock()
```

**Beneficio:**
- Todo el sistema ve el **tiempo histórico correcto**
- Market hours detection funciona
- Event timestamps son precisos
- **Sin cambios en workers** (usan clock global automáticamente)

---

## Caso 5: DatabaseManager - Trade Creation Timestamps

### ANTES (No-determinístico)

```python
# core/database_manager.py
def create_trade(self, symbol, strategy, side, entry_price, quantity):
    """Create new trade"""

    trade = Trade(
        symbol=symbol,
        strategy=strategy,
        side=side,
        entry_price=entry_price,
        quantity=quantity,
        entry_time=datetime.now(),  # ❌ PROBLEMA
        status='OPEN'
    )

    self.session.add(trade)
    self.session.commit()
    return trade
```

### DESPUÉS (Determinístico)

```python
# core/database_manager.py (migrado)
from core.time_provider import get_clock

class DatabaseManager:
    def __init__(self, clock=None):
        self.clock = clock or get_clock()  # Global clock

    def create_trade(self, symbol, strategy, side, entry_price,
                    quantity, entry_time=None):
        """
        Create new trade

        Args:
            entry_time: Override entry time (None = use clock.now())
        """

        if entry_time is None:
            entry_time = self.clock.now()  # ✅ SOLUCIÓN

        trade = Trade(
            symbol=symbol,
            strategy=strategy,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=entry_time,  # ✅ Determinístico
            status='OPEN'
        )

        self.session.add(trade)
        self.session.commit()
        return trade
```

**Beneficio:**
- Trades en DB tienen timestamps correctos
- Replay puede comparar entry_time exactos
- Análisis histórico más preciso

---

## Plan de Migración Gradual

### Fase 1: Core Components (Critical Path)
**Archivos:**
1. ✅ `core/time_provider.py` (nuevo)
2. `core/events.py` - Event creation
3. `core/execution_engine_adapter.py` - Entry/exit timestamps
4. `core/extended_hours_manager.py` - Market session detection

**Testing:**
- Unit tests para TimeProvider
- Integration test: replay 1 día con SimulatedTimeProvider
- Comparar: timestamps de eventos live vs replay

### Fase 2: Database & Persistence
**Archivos:**
1. `core/database_manager.py` - Trade timestamps
2. `core/execution_tracker.py` - Fill timestamps
3. `core/trade_ohlc_recorder.py` - OHLC snapshots

**Testing:**
- Verificar trades tienen entry_time correcto
- Comparar DB records: live vs replay

### Fase 3: Workers (Optional)
**Archivos:**
1. `strategies/workers/base_worker_logic.py`
2. Workers específicos que usan datetime.now()

**Nota:** Workers pueden usar clock global automáticamente sin cambios

### Fase 4: Replay Engine
**Archivos:**
1. `replay_testing/core/replay_engine.py`
2. `replay_testing/backtester.py`

**Testing:**
- Ejecutar replay completo
- Verificar reproducibilidad: 70% → 90%+

---

## Verificación de Migración

### Test 1: Event Timestamps

```python
# test_time_provider.py
def test_event_timestamps_live():
    """Verify events use system time in live"""
    from core.time_provider import SystemTimeProvider
    from core.events import create_bar_event

    clock = SystemTimeProvider()
    before = clock.now()

    event = create_bar_event(mock_bar, clock=clock)

    after = clock.now()

    assert before <= event.timestamp <= after
    print("✅ Live events use system time")

def test_event_timestamps_replay():
    """Verify events use simulated time in replay"""
    from core.time_provider import SimulatedTimeProvider
    from core.events import create_bar_event
    from datetime import datetime

    clock = SimulatedTimeProvider()
    historical_time = datetime(2025, 10, 24, 14, 30)
    clock.set_time(historical_time)

    event = create_bar_event(mock_bar, clock=clock)

    assert event.timestamp == historical_time
    print("✅ Replay events use historical time")
```

### Test 2: Market Hours Detection

```python
def test_market_hours_replay():
    """Verify market hours detection works in replay"""
    from core.time_provider import SimulatedTimeProvider
    from core.extended_hours_manager import ExtendedHoursManager, MarketSession
    from datetime import datetime

    clock = SimulatedTimeProvider()
    manager = ExtendedHoursManager(clock=clock)

    # Thursday 10:00 AM ET (market open)
    clock.set_time(datetime(2025, 10, 24, 10, 0))
    assert manager.get_market_session() == MarketSession.REGULAR

    # Thursday 9:00 AM ET (pre-market)
    clock.set_time(datetime(2025, 10, 24, 9, 0))
    assert manager.get_market_session() == MarketSession.PRE_MARKET

    # Thursday 5:00 PM ET (after-hours)
    clock.set_time(datetime(2025, 10, 24, 17, 0))
    assert manager.get_market_session() == MarketSession.AFTER_MARKET

    print("✅ Market hours detection works in replay")
```

### Test 3: End-to-End Replay

```python
def test_replay_reproducibility():
    """Verify replay produces same decisions as live"""
    from replay_testing.core.replay_engine import ReplayEngine
    from core.time_provider import SimulatedTimeProvider, set_clock

    engine = ReplayEngine('market_data.db', 'trading_data.db')

    # Run replay with simulated time
    session = engine.replay_day('2025-10-24', ['daily_plays', 'macdv'])

    # Compare with real trades
    real_trades = engine._load_real_trades_for_event('2025-10-24', None, 'CMBM')
    simulated_trades = [t for t in session.simulated_trades if t['symbol'] == 'CMBM']

    # Verify timestamps match (within 1 minute)
    for real, sim in zip(real_trades, simulated_trades):
        real_time = pd.to_datetime(real['entry_time'])
        sim_time = pd.to_datetime(sim['entry_time'])

        diff = abs((real_time - sim_time).total_seconds())
        assert diff < 60, f"Entry time diff: {diff}s (should be <60s)"

    print(f"✅ Replay reproducibility: {len(simulated_trades)}/{len(real_trades)} trades matched")
```

---

## Checklist de Migración

### Pre-Migración
- [ ] Backup de código actual
- [ ] Tests de regresión baseline (replay actual)
- [ ] Identificar todos los `datetime.now()` con grep

### Migración
- [ ] Crear `core/time_provider.py`
- [ ] Unit tests para TimeProvider
- [ ] Migrar `core/events.py`
- [ ] Migrar `core/execution_engine_adapter.py`
- [ ] Migrar `core/extended_hours_manager.py`
- [ ] Migrar `replay_testing/core/replay_engine.py`

### Post-Migración
- [ ] Integration tests (live mode)
- [ ] Integration tests (replay mode)
- [ ] Ejecutar replay de 10 días históricos
- [ ] Comparar reproducibilidad: antes vs después
- [ ] Documentar mejoras en métricas

### Rollout
- [ ] Deploy en test environment
- [ ] Monitor live trading (1 semana)
- [ ] Validar no hay regresiones
- [ ] Deploy a producción

---

## Resultado Esperado

### Baseline (Sin Clock Abstraction)
```
Replay 2025-10-24:
  - Entries simulated: 8
  - Entries real: 10
  - Match rate: 60%
  - Avg time diff: 8 minutes
  - Market hours errors: 2
```

### Post-Migración (Con Clock Abstraction)
```
Replay 2025-10-24:
  - Entries simulated: 10
  - Entries real: 10
  - Match rate: 95%
  - Avg time diff: 0 seconds
  - Market hours errors: 0
```

**Mejora:** +35% en reproducibilidad
