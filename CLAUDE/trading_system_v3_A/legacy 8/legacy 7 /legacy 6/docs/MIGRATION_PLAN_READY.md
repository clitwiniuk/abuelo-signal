# 🚀 Plan de Migración - Listo para Ejecutar

## Fecha: 2025-10-02
## Estado: DOCUMENTADO - Listo para aplicar mañana antes de market open

---

## 📋 Resumen Ejecutivo

Este documento contiene el plan COMPLETO para migrar la lógica crítica de las Strategies a los Workers.

**Tiempo estimado total:** 3-4 horas
**Mejor momento:** Mañana antes de market open (8:00-9:00 AM ET)

---

## 🎯 Prioridades

| # | Worker | Tarea | Prioridad | Tiempo | LOC |
|---|--------|-------|-----------|--------|-----|
| 1 | **Bull Flag** | Pattern detection completo | 🔴 CRÍTICO | 2h | ~400 |
| 2 | **MACDV** | MACD calculation + divergence | 🔴 HIGH | 1h | ~250 |
| 3 | **Gap-Go** | PMH breakout detection | 🔴 HIGH | 1h | ~300 |
| 4 | **Daily Plays** | (Ya está 75% completo) | 🟡 SKIP | - | - |

---

## 1️⃣ Bull Flag - Pattern Detection

### **Estado Actual:**
❌ Worker NO tiene pattern detection real
❌ Solo checks básicos de price/volume
❌ ~30% completeness

### **Qué Falta:**
```python
# Bull Flag pattern tiene 3 fases:
# 1. POLE: Strong upward move (30-60% gain)
# 2. FLAG: Consolidation pullback (downward channel, 5-20% retracement)
# 3. BREAKOUT: Price breaks above flag high with volume
```

### **Métodos a Migrar:**

#### **De `strategies/bull_flag_strategy.py`:**

```python
# FASE 1: Pole Detection
def _detect_flagpole_start(self, symbol, bar):
    """
    Detecta inicio de pole (strong upward move)

    Criterios:
    - Price jump >= 1.5% from prev avg
    - Volume >= 1.3x prev avg
    - Green bar (close > open)
    """

def _is_flagpole_complete(self, symbol, bar):
    """
    Detecta fin de pole formation

    Criterios:
    - Total gain: 30-60%
    - Time: 5-30 minutes
    - Pullback started (0.5% from high)
    """

def _is_flagpole_failed(self, symbol, bar):
    """
    Detecta si pole failed

    Criterios:
    - Tiempo > max_flagpole_minutes
    - Price < start price (lost all gains)
    """

# FASE 2: Flag Detection
def _detect_flag_consolidation(self, symbol, bar):
    """
    Detecta consolidation (flag formation)

    Criterios:
    - Pullback: 5-20% from pole high
    - Downward sloping channel
    - Volume declining (consolidation)
    - Time: 5-20 minutes
    """

def _is_flag_failed(self, symbol, bar):
    """
    Detecta si flag failed

    Criterios:
    - Pullback > 20% (too deep)
    - Time > max_flag_minutes
    - Close < flag start * 0.95 (breakdown)
    """

# FASE 3: Breakout Detection
def _detect_flag_breakout(self, symbol, bar):
    """
    Detecta breakout above flag

    Criterios:
    - Price > flag_high * 1.01 (1% above)
    - Volume >= 1.5x avg flag volume
    - Confirmation: close above breakout level
    """

# VALIDATION
def _validate_complete_pattern(self, symbol, bar):
    """
    Valida pattern completo

    Returns:
    - pattern_data dict con:
      - pole_gain (%)
      - flag_pullback (%)
      - breakout_price
      - volume_confirmation
      - time_in_pattern
    """

def _score_pattern_quality(self, pattern_data):
    """
    Score pattern quality (0-100)

    Factors:
    - Pole strength (gain %, time, volume)
    - Flag quality (pullback depth, slope, time)
    - Breakout strength (volume, price action)
    """
```

### **Implementación en Worker:**

**Archivo:** `strategies/workers/bull_flag_worker_logic.py`

```python
class BullFlagWorkerLogic(BaseWorkerLogic):

    def __init__(self, execution_engine, risk_manager, config):
        super().__init__(...)

        # Pattern detection state tracking
        self.pattern_states = {}  # {symbol: 'SCANNING' | 'POLE' | 'FLAG' | 'BREAKOUT'}
        self.flagpole_data = {}   # {symbol: {start_price, high_price, start_time, ...}}
        self.flag_data = {}       # {symbol: {high_price, low_price, consolidation_bars, ...}}
        self.volume_profile = {}  # {symbol: {flagpole_vol: [], flag_vol: []}}

        # Parameters from config
        self.min_flagpole_pct = 30.0      # Min pole gain
        self.max_flagpole_pct = 60.0      # Max pole gain
        self.min_flag_pullback_pct = 5.0  # Min flag retracement
        self.max_flag_pullback_pct = 20.0 # Max flag retracement
        self.breakout_volume_mult = 1.5   # Breakout volume multiplier

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Entry decision based on COMPLETE pattern detection

        Process:
        1. Check if we have bars history for pattern detection
        2. Detect current pattern phase (POLE, FLAG, BREAKOUT)
        3. Only enter on BREAKOUT confirmation
        """
        symbol = opportunity.get('symbol')

        # Get bars history (need 30+ bars for pattern detection)
        bars = await self._get_bars_history(symbol, duration='30 min', bar_size='1 min')

        if not bars or len(bars) < 10:
            return False  # Not enough data

        # Update pattern state machine
        current_state = self.pattern_states.get(symbol, 'SCANNING')

        if current_state == 'SCANNING':
            # Look for pole start
            if self._detect_flagpole_start(symbol, bars):
                self.pattern_states[symbol] = 'POLE'
                return False  # Not entry yet

        elif current_state == 'POLE':
            # Check if pole complete
            if self._is_flagpole_complete(symbol, bars):
                self.pattern_states[symbol] = 'FLAG'
                return False  # Wait for flag consolidation
            elif self._is_flagpole_failed(symbol, bars):
                self._reset_pattern_state(symbol)
                return False

        elif current_state == 'FLAG':
            # Check for breakout
            if self._detect_flag_breakout(symbol, bars):
                # ENTRY SIGNAL - Pattern complete!
                pattern_data = self._validate_complete_pattern(symbol, bars)

                if pattern_data:
                    quality_score = self._score_pattern_quality(pattern_data)

                    if quality_score >= 70:  # High quality pattern
                        self.logger.info(
                            f"✅ {symbol}: Bull Flag BREAKOUT confirmed! "
                            f"Pole: {pattern_data['pole_gain']:.1f}%, "
                            f"Flag: {pattern_data['flag_pullback']:.1f}%, "
                            f"Quality: {quality_score:.0f}"
                        )
                        self._reset_pattern_state(symbol)  # Ready for next pattern
                        return True

            elif self._is_flag_failed(symbol, bars):
                self._reset_pattern_state(symbol)
                return False

        return False

    # ... implement all pattern detection methods here
```

### **LOC Estimado:** ~400 líneas
### **Archivos a Modificar:**
- `strategies/workers/bull_flag_worker_logic.py` (agregar ~400 líneas)

---

## 2️⃣ MACDV - MACD Calculation + Divergence Detection

### **Estado Actual:**
❌ Worker NO calcula MACD correctamente
❌ Divergence detection es básica
❌ ~40% completeness

### **Qué Falta:**

```python
# MACD Indicator:
# MACD Line = 12-period EMA - 26-period EMA
# Signal Line = 9-period EMA of MACD Line
# Histogram = MACD Line - Signal Line

# Divergence Types:
# 1. Regular Bullish: Price lower low + MACD higher low → BUY
# 2. Regular Bearish: Price higher high + MACD lower high → SELL
# 3. Hidden Bullish: Price higher low + MACD lower low → BUY continuation
# 4. Hidden Bearish: Price lower high + MACD higher high → SELL continuation
```

### **Métodos a Migrar:**

#### **De `strategies/macdv_strategy.py`:**

```python
def _calculate_ema(self, prices, period):
    """Calculate Exponential Moving Average"""
    return pd.Series(prices).ewm(span=period, adjust=False).mean()

def _calculate_macd(self, bars):
    """
    Calculate MACD components

    Returns:
    - macd_line: 12 EMA - 26 EMA
    - signal_line: 9 EMA of MACD
    - histogram: MACD - Signal
    """
    closes = [bar.close for bar in bars]

    ema_12 = self._calculate_ema(closes, 12)
    ema_26 = self._calculate_ema(closes, 26)
    macd_line = ema_12 - ema_26
    signal_line = self._calculate_ema(macd_line, 9)
    histogram = macd_line - signal_line

    return {
        'macd': macd_line.tolist(),
        'signal': signal_line.tolist(),
        'histogram': histogram.tolist()
    }

def _detect_divergence(self, bars, macd_data):
    """
    Detect MACD divergence

    Returns:
    - divergence_type: 'REGULAR_BULLISH' | 'REGULAR_BEARISH' | None
    - strength: 0-100
    """
    # Find price swings (highs/lows)
    price_highs = self._find_price_highs(bars)
    price_lows = self._find_price_lows(bars)

    # Find MACD swings
    macd_highs = self._find_macd_highs(macd_data['macd'])
    macd_lows = self._find_macd_lows(macd_data['macd'])

    # REGULAR BULLISH: Price lower low + MACD higher low
    if len(price_lows) >= 2 and len(macd_lows) >= 2:
        if (price_lows[-1] < price_lows[-2] and
            macd_lows[-1] > macd_lows[-2]):
            return 'REGULAR_BULLISH', self._calculate_divergence_strength(...)

    # REGULAR BEARISH: Price higher high + MACD lower high
    if len(price_highs) >= 2 and len(macd_highs) >= 2:
        if (price_highs[-1] > price_highs[-2] and
            macd_highs[-1] < macd_highs[-2]):
            return 'REGULAR_BEARISH', self._calculate_divergence_strength(...)

    return None, 0

def _find_price_lows(self, bars, lookback=10):
    """Find price swing lows (local minimums)"""
    lows = []
    for i in range(lookback, len(bars) - lookback):
        is_low = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and bars[j].low < bars[i].low:
                is_low = False
                break
        if is_low:
            lows.append((i, bars[i].low))
    return lows

def _find_price_highs(self, bars, lookback=10):
    """Find price swing highs (local maximums)"""
    # Similar to _find_price_lows but for highs

def _calculate_divergence_strength(self, price_swing, macd_swing):
    """
    Calculate divergence strength (0-100)

    Factors:
    - Magnitude of price divergence
    - Magnitude of MACD divergence
    - Distance between swings (time)
    - Volume confirmation
    """
```

### **Implementación en Worker:**

**Archivo:** `strategies/workers/macdv_worker_logic.py`

```python
class MACDVWorkerLogic(BaseWorkerLogic):

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Entry based on MACD divergence
        """
        symbol = opportunity.get('symbol')

        # Get enough bars for MACD (need 26+ for 26-EMA)
        bars = await self._get_bars_history(symbol, duration='2 h', bar_size='5 min')

        if not bars or len(bars) < 35:  # Need 26 + 9 bars minimum
            return False

        # Calculate MACD
        macd_data = self._calculate_macd(bars)

        # Detect divergence
        divergence_type, strength = self._detect_divergence(bars, macd_data)

        if divergence_type == 'REGULAR_BULLISH' and strength >= 60:
            self.logger.info(
                f"✅ {symbol}: MACDV BULLISH divergence detected! Strength: {strength:.0f}"
            )
            return True

        return False
```

### **LOC Estimado:** ~250 líneas
### **Archivos a Modificar:**
- `strategies/workers/macdv_worker_logic.py` (agregar ~250 líneas)

---

## 3️⃣ Gap-Go - PMH Breakout Detection

### **Estado Actual:**
✅ Worker tiene gap/volume checks
✅ Worker tiene VWAP check
❌ NO tiene PMH breakout detection
❌ ~60% completeness

### **Qué Falta:**

```python
# PMH (Premarket High) Strategy:
# 1. Detect PMH (highest price in premarket 4-9:30 AM)
# 2. Wait for consolidation BELOW PMH (15+ min)
# 3. Detect breakout ABOVE PMH with volume spike
# 4. Enter on confirmed breakout
# 5. Exit on stuffed move (rejection back below PMH)
```

### **Métodos a Migrar:**

#### **De `strategies/gap_go_strategy.py`:**

```python
def _calculate_pmh(self, symbol):
    """
    Calculate Premarket High (4:00 - 9:30 AM ET)

    Returns:
    - pmh_price: float
    - pmh_time: datetime
    """
    # Get premarket bars (4-9:30 AM)
    pm_bars = self._get_premarket_bars(symbol)

    if not pm_bars:
        return None, None

    pmh_price = max(bar.high for bar in pm_bars)
    pmh_bar = [bar for bar in pm_bars if bar.high == pmh_price][0]

    return pmh_price, pmh_bar.timestamp

def _detect_pmh_consolidation(self, symbol, current_bar):
    """
    Detect consolidation below PMH

    Criterios:
    - Price trading below PMH for 15+ minutes
    - Price staying within 2% range (tight consolidation)
    - Volume declining (not pumping)
    """
    pmh = self.pmh_data.get(symbol, {}).get('price')
    if not pmh:
        return False

    # Get recent bars since market open
    recent_bars = self._get_bars_since_open(symbol)

    # Check all bars are below PMH
    all_below_pmh = all(bar.high < pmh * 1.01 for bar in recent_bars)

    # Check consolidation time
    consolidation_time = (current_bar.timestamp - recent_bars[0].timestamp).total_seconds() / 60

    # Check tight range
    high_range = max(bar.high for bar in recent_bars)
    low_range = min(bar.low for bar in recent_bars)
    range_pct = (high_range - low_range) / low_range * 100

    if (all_below_pmh and
        consolidation_time >= 15 and
        range_pct < 2.0):  # Tight 2% range
        return True

    return False

def _detect_pmh_breakout(self, symbol, current_bar):
    """
    Detect breakout above PMH

    Criterios:
    - Price breaks above PMH by 0.5%+
    - Volume spike (>= 1.5x avg volume during consolidation)
    - Close above PMH (confirmation)
    """
    pmh = self.pmh_data.get(symbol, {}).get('price')
    if not pmh:
        return False

    breakout_threshold = pmh * 1.005  # 0.5% above PMH

    if current_bar.high >= breakout_threshold:
        # Check volume confirmation
        consolidation_bars = self._get_consolidation_bars(symbol)
        avg_consol_vol = np.mean([bar.volume for bar in consolidation_bars])

        volume_ratio = current_bar.volume / avg_consol_vol if avg_consol_vol > 0 else 1.0

        if volume_ratio >= 1.5 and current_bar.close > pmh:
            return True

    return False

def _detect_stuffed_move(self, symbol, current_bar):
    """
    Detect stuffed move (failed breakout)

    Criterios:
    - Price spiked above PMH but rejected back below
    - Volume explosion on rejection (> 2x breakout volume)
    - Close back below PMH

    Action: IMMEDIATE EXIT
    """
    pmh = self.pmh_data.get(symbol, {}).get('price')
    if not pmh:
        return False

    # Check if we had a spike above PMH
    if current_bar.high > pmh * 1.02 and current_bar.close < pmh:
        # Check volume explosion
        recent_bars = self._get_recent_bars(symbol, count=5)
        avg_vol = np.mean([bar.volume for bar in recent_bars])

        if current_bar.volume > avg_vol * 2.0:
            self.logger.warning(
                f"🚨 {symbol}: STUFFED MOVE detected! "
                f"High: ${current_bar.high:.2f}, Close: ${current_bar.close:.2f}, PMH: ${pmh:.2f}"
            )
            return True

    return False
```

### **Implementación en Worker:**

**Archivo:** `strategies/workers/gap_go_worker_logic.py`

```python
class GapGoWorkerLogic(BaseWorkerLogic):

    def __init__(self, execution_engine, risk_manager, config):
        super().__init__(...)

        # PMH tracking
        self.pmh_data = {}  # {symbol: {price, time, consolidating, breakout_detected}}

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Entry with PMH breakout logic
        """
        symbol = opportunity.get('symbol')

        # Original checks (gap, volume, price, VWAP)
        if not await self._basic_gap_go_checks(opportunity):
            return False

        # PMH ENHANCEMENT: Check for PMH breakout setup
        pmh_price = await self._calculate_pmh(symbol)

        if pmh_price:
            # Check if consolidating below PMH
            if await self._detect_pmh_consolidation(symbol):
                # Check for breakout
                if await self._detect_pmh_breakout(symbol):
                    self.logger.info(
                        f"✅ {symbol}: PMH BREAKOUT confirmed! PMH: ${pmh_price:.2f}"
                    )
                    return True
                else:
                    # Still consolidating, wait for breakout
                    return False

        # Fallback: Use original gap-go logic if no PMH data
        return True  # Original logic already passed

    async def should_exit(self, symbol, position, current_price):
        """
        Exit with stuffed move detection
        """
        # Check for stuffed move FIRST (critical exit)
        if await self._detect_stuffed_move(symbol):
            return True, "STUFFED_MOVE"

        # Original exit logic (stop manager)
        return await super().should_exit(symbol, position, current_price)
```

### **LOC Estimado:** ~300 líneas
### **Archivos a Modificar:**
- `strategies/workers/gap_go_worker_logic.py` (agregar ~300 líneas)

---

## 📋 Checklist de Implementación

### **Antes de Empezar:**
- [ ] Hacer backup de workers actuales
- [ ] Crear branch git: `feature/workers-migration`
- [ ] Verificar que tienes acceso a Strategies completas

### **Bull Flag Migration:**
- [ ] Copiar métodos de pattern detection de Strategy
- [ ] Adaptar a formato Worker (opportunity → bars)
- [ ] Implementar state machine (SCANNING → POLE → FLAG → BREAKOUT)
- [ ] Testear con datos históricos

### **MACDV Migration:**
- [ ] Copiar MACD calculation
- [ ] Copiar divergence detection
- [ ] Copiar swing detection (price highs/lows)
- [ ] Testear cálculos con datos conocidos

### **Gap-Go PMH Migration:**
- [ ] Copiar PMH calculation
- [ ] Copiar consolidation detection
- [ ] Copiar breakout detection
- [ ] Copiar stuffed move detection
- [ ] Testear con premarket data

### **Testing:**
- [ ] Unit tests para cada worker
- [ ] Integration test con scanner mock
- [ ] Backtest con datos históricos
- [ ] Paper trading 1 día

---

## ⏰ Timeline Recomendado

### **Día 1 (Mañana):**
**8:00-9:00 AM:** Migrar Bull Flag (2h)
**9:30 AM:** Market open → Monitorear sistema actual

### **Día 1 (Tarde):**
**2:00-3:00 PM:** Migrar MACDV (1h)
**3:00-4:00 PM:** Migrar Gap-Go PMH (1h)

### **Día 2:**
**8:00-9:30 AM:** Testing completo
**9:30 AM:** Deploy con migraciones

---

## 🎯 Resultado Esperado

**Después de migraciones:**

| Worker | Completeness ANTES | Completeness DESPUÉS |
|--------|-------------------|---------------------|
| Bull Flag | 30% | 95% |
| MACDV | 40% | 90% |
| Gap-Go | 60% | 90% |
| Daily Plays | 75% | 75% (sin cambios) |

---

**Documento creado:** 2025-10-02
**Autor:** Claude
**Estado:** ✅ LISTO para ejecutar mañana
