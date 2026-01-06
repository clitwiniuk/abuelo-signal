# MIDCAP PIPELINE - EVALUACIÓN COMPLETA
## Trading System v3 - Análisis Técnico y Arquitectural
**Fecha**: 2025-12-19
**Evaluador**: Claude Code
**Scope**: Pipeline completo de trading para Mid-Caps ($2B-$50B)

---

## RESUMEN EJECUTIVO

### Estado General: ⚠️ FUNCIONAL CON OBSERVACIONES CRÍTICAS

**Hallazgos Principales:**
1. 🔴 **CRÍTICO**: Worker usa **barras de 1 MINUTO** (intraday) para estrategia SWING (multi-día)
2. ⚠️ **IMPORTANTE**: Hereda lógica de smallcaps sin ajustes específicos para mid-caps
3. ⚠️ **IMPORTANTE**: Configuración SWING pero análisis técnico pensado para intraday
4. ✅ **POSITIVO**: Arquitectura sólida y bien separada de smallcaps
5. ✅ **POSITIVO**: Configuración completa y parámetros bien calibrados

---

## 1. ARQUITECTURA DEL PIPELINE

### 1.1 Flujo Completo

```
[IBKR Native Scanner]
    ↓ (mid_cap_movers)
    ↓ Market Cap: $2B - $50B
    ↓ Price: $10 - $200
    ↓ Volume: 500k+ shares
    ↓
[WorkerBasedStrategyEngine]
    ↓ (Universal Routing)
    ↓ Envía a TODOS los workers
    ↓
[DailyPlaysMidCapWorkerLogic] ← 🔍 AQUÍ ESTÁ EL PROBLEMA
    ↓ (Hereda de DailyPlaysWorkerLogic)
    ↓ Uses 1-minute bars (INTRADAY DATA)
    ↓ Analiza: VWAP, momentum, volume spikes
    ↓ Context: Daily bars solo para validación
    ↓ Forces: trading_horizon='SWING'
    ↓
[WorkerStopManager]
    ↓ Max hold: 120 hours (5 días)
    ↓ No fuerza EOD exit
    ↓
[ExecutionEngine]
    ↓
[Position Held Overnight/Multi-day]
```

**✅ Arquitectura**: Correcta y bien separada
**🔴 Problema**: Worker pensado para INTRADAY pero configurado para SWING

---

## 2. ANÁLISIS DEL WORKER - PROBLEMA CRÍTICO

### 2.1 Worker Implementation

**Archivo**: `strategies/workers/daily_plays_midcap_worker_logic.py`

```python
class DailyPlaysMidCapWorkerLogic(DailyPlaysWorkerLogic):
    """
    Daily Plays Worker for MID CAPS ($2B - $50B)
    Uses the same logic as Daily Plays (breakouts, reversals) but tuned for
    institutional-grade stocks (higher liquidity, steadier moves).
    """
```

**Líneas 17-46**: El worker solo hace 3 cosas:
1. Cambia config_section a `DAILY_PLAYS_MIDCAP_STRATEGY`
2. Cambia worker_name a `"daily_plays_midcap"`
3. **Fuerza SWING mode** (`EOD_safe=True`, `trading_horizon='SWING'`)

**🔴 PROBLEMA CRÍTICO**:
- Hereda **TODO** de `DailyPlaysWorkerLogic`
- `DailyPlaysWorkerLogic` está diseñado para **INTRADAY**
- Usa barras de **1 MINUTO** para análisis técnico
- Analiza VWAP intraday, momentum de corto plazo, volume spikes

### 2.2 Uso de Barras en DailyPlaysWorkerLogic

**Archivo**: `strategies/workers/daily_plays_worker_logic.py`

#### Barras de 1 Minuto (PRIMARY DATA)
```python
# Línea 1117-1122: Fetching 1-minute bars
bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
    contract,
    endDateTime='',
    durationStr='300 S',  # 5 minutes = 300 seconds
    barSizeSetting='1 min',  # ← 1-MINUTE INTRADAY
    whatToShow='TRADES',
)
```

**Uso de barras 1-min**:
- Línea 350: `bars = self.get_bars_from_opportunity(opportunity)`
- Línea 351: `vwap_valid = self.validate_vwap_strength(bars, ...)` ← VWAP INTRADAY
- Línea 522: `len(bars)` para validación
- Línea 812: VWAP validation otra vez
- Línea 1645: First 30min breakout logic
- Línea 1814: Volume spike detection (lookback 8 bars = 8 minutos)
- Línea 1930: `_check_volume_spike(bars, lookback=8)` ← 8 MINUTOS

#### Barras Diarias (SECONDARY DATA - Solo Validación)
```python
# Línea 1263-1268: Fetching daily bars
daily_bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
    contract,
    endDateTime='',
    durationStr='1 M',  # 1 month (approximately 30 days)
    barSizeSetting='1 day',  # ← DAILY BARS
    whatToShow='TRADES',
)
```

**Uso de barras diarias**:
- Solo en `_check_daily_context()` method
- Para validación de contexto:
  - RSI daily < 70 (no overbought)
  - MACD no extremo
  - Distancia a resistencia > 2%
  - Max 5 días consecutivos alcistas
- **NO SE USA** para decisiones de entrada/salida principales

### 2.3 Lógica Heredada - No Apropiada para SWING

**Modos de Entrada Heredados**:

#### MODE 1: CATALYST MODE
```
1. Precio > VWAP INTRADAY ← ⚠️ Métrica intraday
2. Volume ratio >= 1.8x ← ⚠️ Comparado con día actual
3. Volume spike detection (8 bars = 8 minutos) ← ⚠️ Lookback muy corto
4. First 30min high breakout ← ⚠️ Lógica intraday pura
```

#### MODE 2: REVERSAL MODE
```
1. RSI < 35 (oversold) ← ✅ OK (usa daily bars)
2. Cerca de soporte 30-day ← ✅ OK
3. MACD histogram increasing ← ⚠️ ¿Daily o intraday?
4. Volume declining (exhaustion) ← ⚠️ Lookback intraday
5. Price stabilizing ← ⚠️ Volatilidad intraday
```

#### MODE 3: FIRST 30MIN BREAKOUT
```
- Timeframe: 10:00-10:30 AM ET ← 🔴 100% INTRADAY
- Price > first 30min high (9:30-10:00 AM) ← 🔴 INTRADAY
- Volume multiplier >= 1.5x ← ⚠️ Métrica intraday
```

**🔴 CONCLUSIÓN**: La lógica está pensada para trades INTRADAY (cerrar antes de EOD), pero midcap lo configura para SWING (mantener multi-día).

---

## 3. CONFIGURACIÓN vs REALIDAD

### 3.1 Configuración Declarada

**Archivo**: `config.ini` - `[DAILY_PLAYS_MIDCAP_STRATEGY]`

| Parámetro | Valor | Interpretación |
|-----------|-------|----------------|
| `max_position_hours` | 120.0 | 5 días (SWING) |
| `stop_loss_pct` | 7.0% | Stops más amplios (SWING) |
| `take_profit_pct` | 25.0% | Targets más grandes (SWING) |
| `trailing_activation` | 10.0% | Trailing más amplio (SWING) |
| `strategy_start_time` | 10:00 | ⚠️ Horario intraday |
| `strategy_end_time` | 15:45 | ⚠️ Horario intraday |

**Worker Capabilities** (`worker_capabilities_config.py`):
```python
'daily_plays_midcap': WorkerCapabilities(
    horizon=TradingHorizon.SWING,  # ← Declarado SWING
    avg_hold_time=72.0,             # ← 3 días promedio
)
```

### 3.2 Realidad de la Implementación

| Aspecto | Configurado | Implementado |
|---------|-------------|--------------|
| **Timeframe de análisis** | SWING (multi-día) | INTRADAY (1-min bars) |
| **Datos principales** | Daily bars | 1-minute bars |
| **VWAP** | Daily VWAP | Intraday VWAP |
| **Volume spikes** | Daily comparison | 8-minute lookback |
| **Momentum** | Daily momentum | Intraday momentum |
| **Entry timing** | Any time | 10:00-15:45 ET |
| **Holding period** | 120 hours (5 días) | ✅ Correcto |
| **EOD exit** | Disabled (SWING) | ✅ Correcto |

**🔴 DESALINEACIÓN CRÍTICA**:
- Worker analiza datos INTRADAY (1-min)
- Pero mantiene posiciones MULTI-DÍA (SWING)
- Decisiones de entrada basadas en momentum de minutos
- Holding period de días

---

## 4. CONSECUENCIAS DEL PROBLEMA

### 4.1 Impacto en Performance

**Riesgos Identificados**:

1. **False Signals** 🔴
   - VWAP intraday > precio al abrir el día siguiente
   - Señal de entrada basada en momentum de 5-10 minutos
   - Posición mantenida 3-5 días
   - **Resultado**: Entry signal obsoleto en horas

2. **Volume Spike Misalignment** ⚠️
   - Detecta spike de volumen en ventana de 8 minutos
   - Posición held multi-día
   - **Resultado**: Spike puede desaparecer en 30 minutos, pero trade sigue abierto

3. **First 30min Breakout** 🔴
   - Lógica: Price > high de 9:30-10:00 AM
   - Hold: 3-5 días
   - **Resultado**: Breakout intraday irrelevante para swing

4. **VWAP Intraday** ⚠️
   - Entry: Price > VWAP intraday
   - Day 2: VWAP recalcula desde 0
   - **Resultado**: Condición de entrada no válida al siguiente día

### 4.2 Escenario de Ejemplo

**Día 1 - Entrada**:
```
10:30 AM - Spike de volumen detectado (8-min window)
10:35 AM - Price > VWAP intraday ($50.20 > $50.00)
10:36 AM - ENTRY ejecutado → Position OPENED
```

**Día 2-5 - Holding**:
```
Día 2: VWAP resetea a $49.80 (open)
       - Price ahora < VWAP
       - Condición de entrada ya no válida

Día 3: Volume normal (no spike)
       - Señal de volumen desapareció hace 48 horas

Día 4: Position todavía abierta
       - Decisión basada en datos de hace 72 horas

Día 5: Stop loss o take profit
       - Trade decidido por 1-min data de hace 5 días
```

### 4.3 Comparación con Worker Apropiado

**Lo que DEBERÍA hacer un worker SWING**:

| Aspecto | Worker SWING Correcto | DailyPlaysMidCap Actual |
|---------|----------------------|------------------------|
| **Timeframe primario** | Daily bars | 1-minute bars 🔴 |
| **VWAP** | Daily VWAP | Intraday VWAP 🔴 |
| **Volume** | Daily volume comparison | 8-minute window 🔴 |
| **Momentum** | Multi-day trend | Intraday momentum 🔴 |
| **Entry trigger** | Daily close > resistance | Price > VWAP intraday 🔴 |
| **Pattern detection** | Daily chart patterns | First 30min breakout 🔴 |
| **Lookback** | 20-50 days | 8-300 seconds 🔴 |

---

## 5. ASPECTOS POSITIVOS

### 5.1 Configuración ✅

**Muy bien calibrada para mid-caps**:
- Market cap range: $2B - $50B ✅
- Price range: $10 - $200 ✅
- Quality score: 65+ (vs 55 smallcap) ✅
- Volume filters: 500k shares, $2M dollar volume ✅
- Stop loss: 7% (vs 5% smallcap) ✅
- Take profit: 25% (vs 20% smallcap) ✅
- Max hold: 120 hours (5 días) ✅

### 5.2 Arquitectura ✅

**Separación limpia**:
- Worker independiente de smallcaps ✅
- Config section propia ✅
- Scanner dedicado ✅
- Capabilities registry ✅
- Test suite completo ✅

### 5.3 Risk Management ✅

**WorkerStopManager bien configurado**:
- Stops más amplios para swings ✅
- Trailing stops apropiados ✅
- EOD exit disabled ✅
- Swing transition enabled ✅
- Tiered sizing enabled ✅

---

## 6. RECOMENDACIONES

### 6.1 CRÍTICO - Crear Worker SWING Apropiado

**Opción A: Nuevo Worker para Mid-Caps** (RECOMENDADO)

Crear `DailyPlaysMidCapSwingWorkerLogic` que:

1. **Use Daily Bars como PRIMARY DATA**
```python
# Fetch daily bars (50 días)
daily_bars = await broker.reqHistoricalDataAsync(
    contract,
    durationStr='3 M',  # 3 months
    barSizeSetting='1 day',  # DAILY
)

# Análisis basado en daily bars
daily_close = daily_bars[-1].close
daily_volume = daily_bars[-1].volume
daily_vwap = calculate_vwap_daily(daily_bars)  # Daily VWAP
```

2. **Lógica de Entrada para SWING**
```python
# Entry criteria basado en DAILY data
def should_enter_swing(self, opportunity):
    # 1. Daily close > Daily VWAP
    if current_price <= daily_vwap:
        return False

    # 2. Daily volume > 20-day average
    if daily_volume < avg_volume_20d * 1.5:
        return False

    # 3. Multi-day momentum (3-5 days)
    if not self.check_multi_day_trend(daily_bars, days=3):
        return False

    # 4. Daily pattern detection
    if not self.detect_daily_breakout_pattern(daily_bars):
        return False

    return True
```

3. **Patterns Apropiados para SWING**
```python
# Daily chart patterns
- Bull Flag (5-10 day consolidation)
- Cup & Handle (15-30 day pattern)
- Daily resistance breakout
- Daily support bounce
- 20/50 EMA crossover (daily)
- Daily MACD crossover
```

**Opción B: Modificar DailyPlaysWorkerLogic** (NO RECOMENDADO)

Agregar modo SWING al worker existente:
```python
class DailyPlaysWorkerLogic:
    def __init__(self, ..., timeframe='INTRADAY'):
        self.timeframe = timeframe

    async def should_enter(self, opportunity):
        if self.timeframe == 'INTRADAY':
            return await self._check_intraday_entry(opportunity)
        else:
            return await self._check_swing_entry(opportunity)
```

**⚠️ Problemas**:
- Código más complejo
- Mezclamos lógicas diferentes
- Más difícil de mantener

### 6.2 IMPORTANTE - Ajustar Config Section

Si decides usar datos daily, actualiza config:

```ini
[DAILY_PLAYS_MIDCAP_STRATEGY]
# Timeframe settings
primary_timeframe = daily  # ← NUEVO
use_daily_vwap = true      # ← NUEVO
daily_lookback_days = 50   # ← NUEVO

# Entry criteria (DAILY-based)
min_daily_volume_ratio = 1.5  # vs 20-day avg
min_consecutive_up_days = 2   # Momentum de días
max_consecutive_up_days = 5   # No exhaustion

# Pattern detection
enable_daily_patterns = true  # Bull flags, C&H, etc.
min_consolidation_days = 5    # Para patterns
max_consolidation_days = 20

# Keep existing (ya correctos)
max_position_hours = 120.0
stop_loss_pct = 7.0
...
```

### 6.3 MEJORABLE - Daily Context Validation

**Actualmente**: Daily bars solo para validación
**Recomendación**: Usar daily bars como PRIMARY data

```python
# ANTES (actual)
bars_1min = get_bars(...)  # PRIMARY
daily_bars = get_daily_bars(...)  # VALIDATION ONLY

# DESPUÉS (recomendado para SWING)
daily_bars = get_daily_bars(...)  # PRIMARY
bars_1min = get_bars(...)  # For precise entry timing only
```

### 6.4 OPCIONAL - Hybrid Approach

**Posible solución intermedia**:

1. **Daily bars para DECISIÓN** (entry/exit logic)
2. **1-min bars para TIMING** (execution timing)

```python
async def should_enter_swing(self, opportunity):
    # PASO 1: Daily analysis (DECISION)
    daily_bars = await fetch_daily_bars(...)

    if not self._check_daily_setup(daily_bars):
        return False  # No daily setup

    # PASO 2: Intraday timing (EXECUTION)
    bars_1min = opportunity.get('bars')

    if not self._check_intraday_timing(bars_1min):
        return False  # Wrong timing

    return True
```

**Ejemplo**:
- Daily analysis: "Stock tiene bull flag de 7 días" ✅
- Intraday timing: "Espera a que price > VWAP intraday para entry preciso" ✅
- **Resultado**: Decisión basada en daily, timing basado en intraday

---

## 7. COMPARACIÓN CON OTROS WORKERS

### 7.1 Holy Grail Worker (Swing Apropiado)

**Archivo**: `strategies/workers/holy_grail_worker_logic.py`

```python
# Holy Grail usa DAILY bars correctamente
class HolyGrailWorkerLogic:
    def _get_adx_period(self):
        return self.adx_period  # 14 días (daily)

    def _get_ema_period(self):
        return self.ema_period  # 20 días (daily)
```

**✅ Hace SWING correctamente**:
- ADX de 14 períodos = 14 DÍAS
- EMA de 20 períodos = 20 DÍAS
- Trend detection multi-día
- Max hold: 240 minutos = 4 horas (pero permite EOD safe)

### 7.2 VCP SmallCap Worker (Similar Issue)

**Similar problema** a DailyPlaysMidCap:
- Configurado para swing (`max_position_hours = 12.0`)
- Pero analiza intraday data
- VCP pattern detection on intraday bars

---

## 8. PLAN DE ACCIÓN RECOMENDADO

### Fase 1: INMEDIATO (1-2 días)

1. **Crear nuevo worker**: `SwingMidCapWorkerLogic`
   - Hereda de `BaseWorkerLogic` (no de DailyPlaysWorkerLogic)
   - Usa daily bars como primary data
   - Implementa lógica SWING apropiada

2. **Config nueva**: `[SWING_MIDCAP_STRATEGY]`
   - Parámetros daily-based
   - Lookbacks en días (no minutos)
   - Patterns multi-día

3. **Registro**: Agregar a `worker_capabilities_config.py`
   ```python
   'swing_midcap': WorkerCapabilities(
       horizon=TradingHorizon.SWING,
       compatible_contexts=[MarketContext.CATALYST, MarketContext.TREND],
       avg_hold_time=72.0,
       min_confidence=70.0
   )
   ```

### Fase 2: TESTING (3-5 días)

1. **Backtesting** con datos históricos
2. **Paper trading** paralelo
3. **Comparación** vs DailyPlaysMidCap actual

### Fase 3: DEPLOYMENT (1 semana)

1. **Deprecar** `DailyPlaysMidCapWorkerLogic` gradualmente
2. **Migrar** a `SwingMidCapWorkerLogic`
3. **Monitorear** performance

### Fase 4: CLEANUP (después de confirmar)

1. **Remover** código deprecated
2. **Documentar** decisiones de diseño
3. **Actualizar** tests

---

## 9. CÓDIGO DE EJEMPLO

### 9.1 Nuevo Worker Recomendado

```python
# strategies/workers/swing_midcap_worker_logic.py

from typing import Dict, Any
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager

class SwingMidCapWorkerLogic(BaseWorkerLogic):
    """
    Swing Trading Worker for MID CAPS ($2B - $50B)
    Uses DAILY bars for analysis and decision-making.
    Holds positions 3-10 days.
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="swing_midcap",
            execution_engine=execution_engine,
            risk_manager=risk_manager,
            config=config
        )

        self.config_section = 'SWING_MIDCAP_STRATEGY'
        self.min_daily_bars = 50  # Need 50 days of history

        # Daily-based parameters
        self.min_daily_volume_ratio = self._get_config_float('min_daily_volume_ratio', 1.5)
        self.min_consecutive_up_days = self._get_config_int('min_consecutive_up_days', 2)
        self.daily_vwap_lookback = self._get_config_int('daily_vwap_lookback', 20)

        self.logger.info(f"🦅 Swing Mid-Cap Worker initialized (Daily timeframe)")

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Entry logic based on DAILY bars analysis
        """
        symbol = opportunity.get('symbol')
        current_price = opportunity.get('current_price', 0)

        # STEP 1: Get DAILY bars (primary data)
        daily_bars = await self._fetch_daily_bars(symbol, days=self.min_daily_bars)

        if not daily_bars or len(daily_bars) < self.min_daily_bars:
            self.logger.warning(f"⚪ {symbol}: Insufficient daily bars ({len(daily_bars)} < {self.min_daily_bars})")
            return False

        # STEP 2: Daily volume analysis
        daily_volume_valid = self._check_daily_volume(daily_bars)
        if not daily_volume_valid:
            self.logger.info(f"⚪ {symbol}: Daily volume too low")
            return False

        # STEP 3: Daily VWAP
        daily_vwap = self._calculate_daily_vwap(daily_bars, lookback=self.daily_vwap_lookback)
        if current_price <= daily_vwap:
            self.logger.info(f"⚪ {symbol}: Price ${current_price:.2f} <= Daily VWAP ${daily_vwap:.2f}")
            return False

        # STEP 4: Multi-day momentum
        momentum_valid = self._check_multi_day_momentum(daily_bars, min_days=self.min_consecutive_up_days)
        if not momentum_valid:
            self.logger.info(f"⚪ {symbol}: No multi-day momentum")
            return False

        # STEP 5: Daily pattern detection
        pattern_detected = self._detect_daily_pattern(daily_bars, current_price)
        if not pattern_detected:
            self.logger.info(f"⚪ {symbol}: No daily pattern detected")
            return False

        # STEP 6: (Optional) Intraday timing for precise entry
        bars_1min = opportunity.get('bars', [])
        if bars_1min:
            intraday_timing_ok = self._check_intraday_timing(bars_1min, current_price)
            if not intraday_timing_ok:
                self.logger.info(f"⚪ {symbol}: Poor intraday timing (wait for better entry)")
                return False

        # ENTRY APPROVED - Force SWING mode
        opportunity['EOD_safe'] = True
        opportunity['trading_horizon'] = 'SWING'

        self.logger.info(f"✅ {symbol}: SWING entry approved (Daily analysis)")
        return True

    async def _fetch_daily_bars(self, symbol: str, days: int = 50):
        """Fetch daily bars from broker"""
        from ib_insync import Stock

        contract = Stock(symbol, 'SMART', 'USD')

        daily_bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
            contract,
            endDateTime='',
            durationStr=f'{days} D',  # Days
            barSizeSetting='1 day',   # DAILY
            whatToShow='TRADES',
            useRTH=True
        )

        return daily_bars

    def _check_daily_volume(self, daily_bars: list) -> bool:
        """Check if current daily volume > avg"""
        if not daily_bars or len(daily_bars) < 20:
            return False

        current_volume = daily_bars[-1].volume
        avg_volume_20d = sum(bar.volume for bar in daily_bars[-20:]) / 20

        volume_ratio = current_volume / avg_volume_20d if avg_volume_20d > 0 else 0

        return volume_ratio >= self.min_daily_volume_ratio

    def _calculate_daily_vwap(self, daily_bars: list, lookback: int = 20) -> float:
        """Calculate VWAP based on DAILY bars"""
        if not daily_bars or len(daily_bars) < lookback:
            return 0.0

        recent_bars = daily_bars[-lookback:]

        total_volume = sum(bar.volume for bar in recent_bars)
        if total_volume == 0:
            return 0.0

        vwap_sum = sum(
            (bar.high + bar.low + bar.close) / 3 * bar.volume
            for bar in recent_bars
        )

        return vwap_sum / total_volume

    def _check_multi_day_momentum(self, daily_bars: list, min_days: int = 2) -> bool:
        """Check for consecutive up days"""
        if not daily_bars or len(daily_bars) < min_days + 1:
            return False

        consecutive_up = 0
        for i in range(len(daily_bars) - min_days, len(daily_bars)):
            if daily_bars[i].close > daily_bars[i - 1].close:
                consecutive_up += 1

        return consecutive_up >= min_days

    def _detect_daily_pattern(self, daily_bars: list, current_price: float) -> bool:
        """Detect daily chart patterns (bull flags, breakouts, etc.)"""
        if not daily_bars or len(daily_bars) < 10:
            return False

        # Example: Simple breakout detection
        # Check if price breaking above 10-day high
        ten_day_high = max(bar.high for bar in daily_bars[-10:])

        if current_price > ten_day_high * 1.01:  # 1% above
            return True  # Breakout detected

        # TODO: Add more pattern detection
        # - Bull flags
        # - Cup & Handle
        # - Consolidation breakouts

        return False

    def _check_intraday_timing(self, bars_1min: list, current_price: float) -> bool:
        """
        Optional: Use intraday bars for TIMING only (not decision)
        Wait for intraday VWAP confirmation for better entry
        """
        if not bars_1min or len(bars_1min) < 10:
            return True  # Allow entry if no intraday data

        # Calculate intraday VWAP
        intraday_vwap = self._calculate_vwap(bars_1min)

        # Entry timing: wait for price > intraday VWAP
        return current_price > intraday_vwap
```

### 9.2 Config para Nuevo Worker

```ini
[SWING_MIDCAP_STRATEGY]
enabled = true

# Market filters (same as before)
min_price = 10.0
max_price = 200.0
min_market_cap = 2000
max_market_cap = 50000

# Quality filters
min_quality_score = 70.0
min_avg_volume = 500000
min_dollar_volume = 2000000

# DAILY-based analysis
primary_timeframe = daily
min_daily_bars = 50
daily_vwap_lookback = 20

# Daily volume
min_daily_volume_ratio = 1.5

# Multi-day momentum
min_consecutive_up_days = 2
max_consecutive_up_days = 7

# Pattern detection
enable_daily_patterns = true
min_consolidation_days = 5
max_consolidation_days = 20

# Risk management (SWING-appropriate)
stop_loss_pct = 7.0
take_profit_pct = 25.0
trailing_activation = 10.0
trailing_distance = 4.0
max_position_hours = 120.0

# Timing (optional intraday optimization)
use_intraday_timing = true
strategy_start_time = 10:00
strategy_end_time = 15:45

# Position sizing
enable_tiered_sizing = true
earnings_risk_multiplier = 1.5
standard_risk_multiplier = 0.5
```

---

## 10. CONCLUSIONES

### ✅ Lo Que Funciona Bien

1. **Arquitectura**: Separación limpia, modular, extensible
2. **Configuración**: Parámetros bien calibrados para mid-caps
3. **Risk Management**: Stops, targets, y position sizing apropiados
4. **Scanner**: Filtros correctos para identificar mid-caps

### 🔴 Lo Que Necesita Corrección

1. **CRÍTICO**: Worker usa timeframe INTRADAY para estrategia SWING
2. **CRÍTICO**: Decisiones basadas en 1-minute bars pero holding multi-día
3. **IMPORTANTE**: Lógica heredada no apropiada para swing trading

### ⚠️ Recomendación Final

**NO uses `DailyPlaysMidCapWorkerLogic` en producción** hasta que se corrija el problema del timeframe.

**Opciones**:
1. **MEJOR**: Crear nuevo worker `SwingMidCapWorkerLogic` con daily bars
2. **ALTERNATIVA**: Modificar para usar daily bars como primary data
3. **TEMPORAL**: Si usas actual worker, reduce `max_position_hours` a 8 (intraday only)

El código está bien estructurado y la configuración es sólida, pero el **timeframe mismatch** es un problema fundamental que afectará la performance.

---

**Fin del Reporte**
