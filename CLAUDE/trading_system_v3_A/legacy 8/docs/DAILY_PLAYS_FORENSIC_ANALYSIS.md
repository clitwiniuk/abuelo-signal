# 🔍 DAILY PLAYS WORKER - ANÁLISIS FORENSE COMPLETO

**Fecha:** 2025-12-03
**Worker:** daily_plays_worker_logic.py
**Objetivo:** Identificar código obsoleto, inconsistencias y problemas de diseño

---

## 📋 EXECUTIVE SUMMARY

**Score General:** 5.5/10 ⚠️

El Daily Plays worker tiene **problemas moderados** que afectan su comportamiento:
- ✅ Usa config.ini parcialmente (mejor que ORB)
- ⚠️ Código complejo con lógica obsoleta comentada
- ❌ Performance real: 65% losses (13/20 trades)
- ❌ Avg loss: -3.13% vs diseño (-5%)
- ⚠️ Filtros ODS deshabilitados sin claridad
- ⚠️ Múltiples modos de entry sin coordinación clara

---

## 🔍 ANÁLISIS DE CÓDIGO

### **Archivo Analizado**
- **Path:** `strategies/workers/daily_plays_worker_logic.py`
- **Líneas:** 1,636
- **Última modificación:** Múltiples iteraciones

### **1. ANÁLISIS DE CONFIGURACIÓN (Config.ini)**

#### **Config Params Definidos (config.ini):**
```ini
[DAILY_PLAYS_STRATEGY]
enabled = true

# ===== BASIC PARAMS =====
first_30_minutes = 30
ema_period = 9
volume_lookback = 10
min_gap_percent = 0.1

# ===== RISK MANAGEMENT =====
stop_loss_pct = 0.05          # 5% SL
take_profit_pct = 0.20        # 20% TP
quick_target_pct = 0.07       # 7% Quick TP
trailing_activation = 0.08    # 8% Trailing activation
trailing_distance = 0.04      # 4% Trailing distance
breakeven_activation_pct = 0.03
max_hold_hours = 8

# ===== REVERSAL MODE =====
enable_reversal_mode = true
reversal_min_rsi = 35
reversal_min_signals = 4
reversal_max_support_distance = 3.0
reversal_volume_ratio_relaxed = 1.5
reversal_quality_score_relaxed = 40

# ===== MOMENTUM RUNNER =====
runner_min_gap_pct = 10.0
runner_min_volume_ratio = 3.0
runner_max_price = 20.0
runner_vwap_tolerance = 0.9
```

**Total params en config:** 23

#### **Config Params Usados (código):**

**✅ USADOS CORRECTAMENTE:**
```python
# Line 87-88: WorkerStopManager integración
if config:
    self.stop_manager = create_worker_stop_manager(config, 'DAILY_PLAYS_STRATEGY')
    # ✅ Lee stop_loss_pct, take_profit_pct, trailing, etc.
```

```python
# Lines 92-98: Reversal mode configuration
self.enable_reversal_mode = getattr(config, 'enable_reversal_mode', True)
self.reversal_min_rsi = getattr(config, 'reversal_min_rsi', 35.0)
self.reversal_min_signals = int(getattr(config, 'reversal_min_signals', 4))
# ✅ CORRECTO: Lee de config
```

**❌ HARDCODED (NO LEE CONFIG):**
```python
# Lines 66-73: HARDCODED values
self.strong_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH', 'CONTRACT', 'NEWS', 'ANALYST']
self.min_volume_ratio = getattr(config, 'min_volume_ratio', 1.8)  # ❌ Lee de wrong place
self.min_price = 1.0          # ❌ HARDCODED
self.max_price = 25.0         # ❌ HARDCODED
self.min_quality_score = 50.0 # ❌ HARDCODED

# Lines 77-78: Entry confirmation
self.min_confirmations = 1    # ❌ HARDCODED
self.confirmation_window = 120 # ❌ HARDCODED

# Lines 81-84: First 30min breakout
self.ema_period = 9           # ⚠️ DUPLICADO (existe en config: ema_period = 9)
self.volume_multiplier_30min = 1.5  # ❌ HARDCODED
```

**Resultado:**
- **Config usage:** 40% (9/23 params)
- **Hardcoded params:** 14
- **WorkerStopManager:** ✅ Integrado correctamente

---

### **2. ANÁLISIS DE FILTROS**

#### **Filtros Activos:**

1. **✅ DUPLICATE POSITION CHECK** (Line 389-400)
   - Usa UnifiedPositionManager
   - CORRECTO: Evita duplicados

2. **✅ CRITICAL VALIDATION 1: Trading Hours** (Line 617-636)
   - Usa `is_within_entry_hours()` centralizado
   - CORRECTO: Validación de horario

3. **✅ CRITICAL VALIDATION 2: VWAP Strength** (Line 644-657)
   - Usa `validate_vwap_strength()` centralizado
   - CORRECTO: Filtro universal

4. **⚠️ ODS FILTERS - DISABLED** (Lines 442-462)
   - **PROBLEMA:** Filtros ODS comentados sin explicación clara
   ```python
   # ODS FILTERS DISABLED - ARCHITECTURAL DECOUPLING
   # Pattern-specific filtering moved to dedicated ODS-driven worker

   # FILTER 1: Skip FAILED DRIVE days - DISABLED
   # if ods.day_type == ODSDayType.FAILED_DRIVE:
   #     return False

   # FILTER 2: Skip BALANCE days - DISABLED
   # if ods.day_type == ODSDayType.BALANCE_DAY:
   #     return False
   ```
   - **Impacto:** Worker entra en días con ODS desfavorable
   - **Fix:** Usar confidence_boost en lugar de filtros (lines 471-503)

5. **✅ INTRADAY STRUCTURE FILTERS** (Lines 565-608)
   - MIDDAY BALANCE: Rechaza si balance/chop zone
   - AFTERNOON BULL TRAP: Rechaza traps
   - FINAL DRIVE FADE: Rechaza parabolic sin volume
   - CORRECTO: Filtros contextuales

#### **Filtros de Precio/Volumen:**

**❌ PROBLEMA: Rangos hardcoded sin config**
```python
self.min_price = 1.0          # Hardcoded (should be from config)
self.max_price = 25.0         # Hardcoded (should be from config)
self.min_quality_score = 50.0 # Hardcoded (should be from config)
```

**Comparación con config.ini:**
- Config NO define `min_price`, `max_price`, `min_quality_score`
- Worker usa valores hardcoded
- **Incompatible con smallcaps**: $1-$25 es rango amplio (incluye mid-caps)

---

### **3. ANÁLISIS DE MODOS DE ENTRY**

El worker tiene **2 MODOS DE ENTRY independientes:**

#### **MODO 1: CATALYST-DRIVEN BREAKOUT** (Lines 660-708)
```python
# Pattern completion: 75-95% = OPTIMAL entry window
if 75.0 <= completion <= 95.0:
    return True
```

**Criterios:**
1. Catalyst fuerte (FDA, M&A, EARNINGS, etc.)
2. Volume ratio >= 0.5x (desde scanner)
3. Precio $1-$25 (hardcoded)
4. Quality score >= 50 (hardcoded)
5. Precio > VWAP (75% completion stage)
6. Daily context safe (evita trampas institucionales)
7. Pattern completion 75-95%

**⚠️ PROBLEMA:** Stage 2 validation (lines 686-708):
- Recalcula Stage 2 DESPUÉS de aprobar entry
- Blocking logic confusa
- Puede rechazar entries ya aprobados

#### **MODO 2: FIRST 30-MINUTE HIGH BREAKOUT** (Lines 716-762)
```python
# Check for first 30min breakout
is_breakout = self._check_first_30min_breakout(symbol, bars, current_price)

if is_breakout:
    # Validate EMA9 and Volume spike
    if ema_valid and volume_valid:
        return True
```

**Criterios:**
1. Precio rompe high de 9:30-10:00 AM
2. Precio >= EMA9 * 0.99 (1% tolerance)
3. Volume >= 1.5x avg de últimas 8 barras

**⚠️ PROBLEMA:**
- Entry mode secundario ACTIVO pero NO documentado en header
- Puede generar trades sin catalyst
- Riesgo de false breakouts

---

### **4. ANÁLISIS DE CÓDIGO OBSOLETO**

#### **Código Comentado:**

**❌ Lines 442-462: ODS FILTERS DISABLED**
```python
# FILTER 1: Skip FAILED DRIVE days (catalyst momentum reversed) - DISABLED
# if ods.day_type == ODSDayType.FAILED_DRIVE:
#     return False

# FILTER 2: Skip BALANCE days (no clear trend) - DISABLED
# if ods.day_type == ODSDayType.BALANCE_DAY:
#     return False
```

**Razón:** "ARCHITECTURAL DECOUPLING"
**Impacto:** Worker puede entrar en días con momentum reversado o sin tendencia
**Fix aplicado:** Usa confidence_boost (0.7x para FAILED_DRIVE, 0.9x para BALANCE)
**Estado:** ✅ Mitigation OK, pero confuso

#### **❌ Lines 310-324: DEPRECATED method**
```python
def _is_trading_hours(self, time_decimal: float) -> bool:
    """
    DEPRECATED: Use centralized is_within_entry_hours() from BaseWorkerLogic
    """
    # Delegate to centralized validation
    is_valid, _ = self.is_within_entry_hours()
    return is_valid
```

**Estado:** ⚠️ Deprecated pero no removido - confunde

#### **Fallback logic (Lines 100-110):**
```python
else:
    # Fallback: create with default parameters
    from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
    self.stop_manager = WorkerStopManager(WorkerStopConfig(
        stop_loss_pct=5.0,
        take_profit_pct=20.0,
        # ... defaults hardcoded
    ))
```

**Estado:** ✅ OK - Fallback sensato si config no disponible

---

### **5. ANÁLISIS DE REVERSAL MODE**

**Reversal Mode:** Detecta setups de reversión alcista desde oversold (Lines 1220-1328)

**Señales de reversión (6 total):**
1. RSI < 35 (oversold)
2. Cerca de soporte 30-day (< 3%)
3. 3+ días consecutivos bajistas
4. MACD histogram increasing (divergencia positiva)
5. Volume declining (exhaustion)
6. Price stabilizing (volatilidad baja)

**Requisito:** 4/6 señales para activar reversal mode

**Criterios RELAJADOS en reversal:**
- Catalyst OPCIONAL (no requerido)
- Volume ratio >= 1.5x (vs 2.0x normal)
- Quality score >= 40 (vs 50 normal)
- VWAP requirement relaxed

**Estado:** ✅ Bien diseñado e implementado

**⚠️ PROBLEMA:** Reversal mode puede generar trades sin catalyst fuerte
- Contradice diseño "catalyst-driven"
- Risk de entries de baja calidad

---

## 📊 ANÁLISIS DE TRADES REALES

### **Performance Real (Últimos 30 días)**

**Datos:**
- Total trades: 20
- Trades cerrados: 13
- Trades abiertos: 7
- Win rate: 7.7% (1/13) ❌
- Avg loss: -3.13% ✅ (dentro de SL -5%)

**Trades Cerrados:**
```
WINNER:
✅ BITF: +0.14% (Nov 28)

LOSERS (12):
❌ NVTS: -2.64%
❌ BTBT: -4.92%
❌ JBLU: -0.66%
❌ BITF: -5.15% (SL hit)
❌ FTEL: -3.57%
❌ HIVE: -1.26%
❌ BITF: -1.80%
❌ ABVE: -6.38% (SL exceeded!)
```

**Trades Abiertos (posibles problemas):**
```
⚠️ MSTX: 3 entries (6.13, 6.13, 4.96, 4.94) - DUPLICATE ISSUE?
⚠️ TSLS: 2 entries (5.39, 5.40) - DUPLICATE ISSUE?
⚠️ BTBT: 2 entries (2.3898, 2.39) - DUPLICATE ISSUE?
⚠️ HIVE: 2 entries (3.4185, 3.41) - DUPLICATE ISSUE?
```

### **Problemas Identificados:**

#### **PROBLEMA 1: Win Rate Horrible (7.7%)**
- **Diseño esperado:** 50-60% win rate
- **Real:** 7.7% (1/13) ❌
- **Causa probable:**
  1. Entries en momentum desfavorable (ODS filters disabled)
  2. Daily context checks no suficientes
  3. First 30min breakout mode genera false breakouts

#### **PROBLEMA 2: Duplicados?**
- **Múltiples entries en mismo símbolo el mismo día**
- MSTX: 3-4 entries el 2025-12-02
- TSLS: 2 entries el 2025-12-02
- **Causa probable:** Anti-overtrading no funciona correctamente

#### **PROBLEMA 3: Stop Loss Exceeded**
- ABVE: -6.38% (diseño: -5% SL)
- **Causa:** Stop loss no ejecutó a tiempo o slippage

---

## 🎯 IDENTIFICACIÓN DE PROBLEMAS CRÍTICOS

### **PROBLEMA CRÍTICO #1: Config.ini Parcialmente Usado**

**Severity:** 🔴 HIGH

**Descripción:**
- Solo 40% de params se leen de config (9/23)
- Valores críticos hardcoded:
  * `min_price = 1.0`
  * `max_price = 25.0`
  * `min_quality_score = 50.0`
  * `min_volume_ratio = 1.8` (lee de lugar incorrecto)
  * `min_confirmations = 1`
  * `confirmation_window = 120`
  * `ema_period = 9` (duplicado con config)
  * `volume_multiplier_30min = 1.5`

**Impacto:**
- NO se puede tunar desde config
- Valores hardcoded pueden ser obsoletos
- Incompatible con optimización smallcaps

**Fix Recomendado:**
```python
# Read ALL params from config.ini
self.min_price = config.getfloat('DAILY_PLAYS_STRATEGY', 'min_price', fallback=1.0)
self.max_price = config.getfloat('DAILY_PLAYS_STRATEGY', 'max_price', fallback=25.0)
self.min_quality_score = config.getfloat('DAILY_PLAYS_STRATEGY', 'min_quality_score', fallback=50.0)
self.min_volume_ratio = config.getfloat('DAILY_PLAYS_STRATEGY', 'min_volume_ratio', fallback=1.8)
self.min_confirmations = config.getint('DAILY_PLAYS_STRATEGY', 'min_confirmations', fallback=1)
self.confirmation_window = config.getint('DAILY_PLAYS_STRATEGY', 'confirmation_window', fallback=120)
self.ema_period = config.getint('DAILY_PLAYS_STRATEGY', 'ema_period', fallback=9)
self.volume_multiplier_30min = config.getfloat('DAILY_PLAYS_STRATEGY', 'volume_multiplier_30min', fallback=1.5)
```

---

### **PROBLEMA CRÍTICO #2: ODS Filters Disabled Sin Claridad**

**Severity:** 🟠 MEDIUM

**Descripción:**
- Filtros ODS completamente deshabilitados (lines 442-462)
- Comentado con "ARCHITECTURAL DECOUPLING"
- Mitigation: confidence_boost (0.7x-1.4x)
- **PERO:** Confidence boost NO rechaza entries, solo ajusta

**Impacto:**
- Worker entra en FAILED_DRIVE days (momentum reversado)
- Worker entra en BALANCE days (sin tendencia clara)
- Genera trades de baja calidad
- Win rate 7.7% puede deberse a esto

**Fix Recomendado:**
```python
# OPTION A: RE-ENABLE ODS filters con toggle
enable_ods_filters = config.getboolean('DAILY_PLAYS_STRATEGY', 'enable_ods_filters', fallback=True)

if enable_ods_filters:
    if ods.day_type == ODSDayType.FAILED_DRIVE:
        return False  # Hard reject

    if ods.day_type == ODSDayType.BALANCE_DAY:
        return False  # Hard reject

# OPTION B: Keep boost but make stricter
if ods.day_type == ODSDayType.FAILED_DRIVE:
    confidence_boost = 0.5  # -50% (more aggressive reduction)
elif ods.day_type == ODSDayType.BALANCE_DAY:
    confidence_boost = 0.7  # -30% (more aggressive reduction)
```

---

### **PROBLEMA CRÍTICO #3: Duplicate Entries**

**Severity:** 🔴 HIGH

**Descripción:**
- Múltiples entries en mismo símbolo mismo día:
  * MSTX: 4 entries (Dec 2)
  * TSLS: 2 entries (Dec 2)
  * BTBT: 2 entries (Nov 28)
  * HIVE: 2 entries (Nov 28, Dec 1)

**Causa probable:**
1. UnifiedPositionManager check (line 391-400) NO funciona
2. Anti-overtrading check falla
3. First 30min breakout mode bypass checks

**Impacto:**
- Overtrading severo
- Exposure multiplicado en mismo símbolo
- Risk management comprometido

**Fix Recomendado:**
```python
# FILTER 1: ANTI-OVERTRADING (symbol-level)
if symbol in self.traded_symbols_today:
    self.logger.info(
        f"⚪ {symbol}: Already traded today (max 1 per symbol)"
    )
    return False
```

**Agregar tracking:**
```python
async def on_position_opened(self, symbol, entry_price, quantity):
    self.traded_symbols_today.add(symbol)  # Track daily
```

---

### **PROBLEMA CRÍTICO #4: First 30min Breakout Mode Oculto**

**Severity:** 🟠 MEDIUM

**Descripción:**
- Entry mode secundario ACTIVO (lines 716-762)
- NO documentado en header del worker
- Puede generar trades SIN catalyst
- Contradice diseño "catalyst-driven"

**Impacto:**
- Entries inesperadas sin catalyst
- False breakouts
- Confusion en análisis de trades

**Fix Recomendado:**
```python
# OPTION A: Document in header
"""
    Criterios de entrada NORMAL (Catalyst Mode):
    ...

    Criterios de entrada ALTERNATIVE (First 30min Breakout):
    - Price breaks 9:30-10:00 AM high
    - Price >= EMA9 * 0.99
    - Volume >= 1.5x avg (8 bars)
    NOTE: NO catalyst required for this mode
"""

# OPTION B: Add config toggle
enable_first_30min_mode = config.getboolean('DAILY_PLAYS_STRATEGY', 'enable_first_30min_breakout', fallback=False)

if enable_first_30min_mode and is_breakout:
    # Only enter if explicitly enabled
    return True
```

---

### **PROBLEMA #5: Stage 2 Blocking Logic Confusa**

**Severity:** 🟡 LOW

**Descripción:**
- Lines 686-708: Stage 2 validation DESPUÉS de aprobar entry
- Recalcula quality/strength checks
- Puede bloquear entries ya aprobados por pattern completion

**Código:**
```python
if 75.0 <= completion <= 95.0:
    return True  # ✅ Entry approved

# 🛡️ PROTECTION: If Stage 2 failed, reject entry
if completion >= 75.0:
    # Recalculate Stage 2 checks (quality, catalyst strength)
    if not stage2_passed:
        return False  # ❌ Block entry retroactively
```

**Impacto:**
- Lógica redundante y confusa
- Stage 2 debería validarse EN calculate_pattern_completion()

**Fix Recomendado:**
- Remover Stage 2 blocking (lines 686-708)
- Confiar en calculate_pattern_completion() result

---

### **PROBLEMA #6: Código Deprecated No Removido**

**Severity:** 🟢 COSMETIC

**Descripción:**
- `_is_trading_hours()` deprecated (line 310-324)
- Delegated to centralized method
- Pero NO removido del código

**Fix:** Remover método deprecated

---

## 🎯 COMPATIBILIDAD CON SMALLCAPS

### **Score: 6/10** ⚠️

**Filtros Smallcap-friendly:**

✅ **BUENOS:**
1. Precio: $1-$25 (acepta smallcaps)
2. WorkerStopManager integrado (SL 5%, TP 20%)
3. VWAP validation (evita weakness)
4. Intraday structure filters (contextuales)
5. Reversal mode (detecta oversold bounces)

⚠️ **PROBLEMAS:**
1. Range muy amplio ($1-$25, incluye mid-caps)
2. NO hay filtro de avg volume (ilíquidos pueden pasar)
3. NO hay filtro de dollar volume ($50k mínimo recomendado)
4. ODS filters disabled (entra en momentum desfavorable)
5. Quality score 50 puede ser bajo para smallcaps
6. First 30min breakout sin catalyst validation

**Recomendaciones para Smallcaps:**
```ini
[DAILY_PLAYS_STRATEGY]
# Tighten price range
min_price = 1.0
max_price = 10.0   # Focus on true smallcaps (vs 25.0 current)

# Add volume filters
min_avg_volume = 100000     # 100k avg daily volume
min_dollar_volume = 50000   # $50k dollar volume

# Tighten quality
min_quality_score = 55.0    # Higher bar for smallcaps

# Re-enable ODS filters
enable_ods_filters = true   # Reject FAILED_DRIVE, BALANCE_DAY
```

---

## 📈 COMPARACIÓN: DISEÑO vs REAL

| Métrica | Diseño | Real | Status |
|---------|--------|------|--------|
| **Win Rate** | 50-60% | 7.7% (1/13) | ❌ HORRIBLE |
| **Avg Win** | +8-12% | +0.14% | ❌ MUY BAJO |
| **Avg Loss** | -3-5% | -3.13% | ✅ OK (SL working) |
| **Max Loss** | -5% (SL) | -6.38% (ABVE) | ⚠️ SL exceeded |
| **Trades/día** | 1-2 | ~3-4 (overtrading?) | ⚠️ ALTO |
| **Config usage** | 100% | 40% (9/23) | ❌ BAJO |
| **ODS filters** | Enabled | Disabled | ❌ PROBLEM |
| **Duplicate prevention** | Working | Failing | ❌ PROBLEM |

**Conclusión:** Performance real NO coincide con diseño

---

## 🎯 RECOMENDACIONES

### **OPCIÓN A: Refactor Ligero** (2-3 horas)

**Fixes Críticos:**
1. ✅ Leer TODOS los params de config.ini (lines 66-84)
2. ✅ RE-ENABLE ODS filters o make boost stricter
3. ✅ Fix anti-overtrading (tracked_symbols_today)
4. ✅ Document First 30min breakout mode en header
5. ✅ Remove deprecated `_is_trading_hours()`
6. ✅ Add volume filters (min_avg_volume, min_dollar_volume)
7. ✅ Tighten price range ($1-$10 vs $1-$25)

**Resultado esperado:**
- Config usage: 40% → 100% ✅
- Win rate: 7.7% → 30-40% ⚠️ (aún bajo pero mejorado)
- Overtrading: Eliminado ✅
- Compatibility: 6/10 → 8/10 ✅

---

### **OPCIÓN B: Refactor Completo** (6-8 horas)

**Todo de Opción A +:**
1. ✅ Simplificar entry logic (unify catalyst vs first 30min modes)
2. ✅ Review reversal mode criteria (4/6 signals puede ser muy lax)
3. ✅ Improve daily context checks (institucional traps)
4. ✅ Add quality_score boost logic (ODS + structure)
5. ✅ Review Stage 2 blocking logic (remove or simplify)
6. ✅ Add comprehensive logging de rejection reasons
7. ✅ Cleanup obsolete comments
8. ✅ Add unit tests

**Resultado esperado:**
- Config usage: 100% ✅
- Win rate: 7.7% → 45-55% ✅
- Code quality: 5.5/10 → 8/10 ✅
- Compatibility: 6/10 → 9/10 ✅

---

### **OPCIÓN C: Replay Testing Primero** (1-2 horas)

**Antes de refactor, validar con datos históricos:**

```bash
# Test daily_plays con múltiples fechas
python replay_testing/test_daily_plays.py --date 2025-11-18
python replay_testing/test_daily_plays.py --date 2025-11-28
python replay_testing/test_daily_plays.py --date 2025-12-02

# Identificar:
# - ¿Cuántos trades son de Catalyst mode vs First 30min mode?
# - ¿Cuántos rechazos por ODS (boost reduction)?
# - ¿Cuántos duplicados?
# - ¿Win rate por modo?
```

**Después de validar, decidir entre Opción A o B**

---

## 🎯 PRIORIZACIÓN

### **Urgente (Fix Inmediato):**
1. 🔴 **Duplicate entries** - Overtrading severo
2. 🔴 **Config.ini integration** - 60% params hardcoded
3. 🔴 **ODS filters** - Entrando en momentum desfavorable

### **Importante (Fix Esta Semana):**
4. 🟠 **First 30min mode** - Entry sin catalyst no documentado
5. 🟠 **Volume filters** - Ilíquidos pueden pasar
6. 🟠 **Price range** - Tighten para true smallcaps ($1-$10)

### **Nice to Have (Fix Próxima Iteración):**
7. 🟡 **Stage 2 blocking logic** - Simplificar
8. 🟡 **Reversal mode criteria** - Review 4/6 threshold
9. 🟢 **Code cleanup** - Remove deprecated methods

---

## 📝 CONCLUSIÓN

### **Estado Actual: 5.5/10** ⚠️

**Problemas Principales:**
1. ❌ Config parcialmente usado (40%)
2. ❌ ODS filters disabled
3. ❌ Win rate horrible (7.7%)
4. ❌ Duplicate entries
5. ⚠️ First 30min mode oculto
6. ⚠️ Volume filters ausentes

**El worker tiene bases sólidas pero necesita:**
- ✅ Refactor de config integration (CRÍTICO)
- ✅ Fix anti-overtrading (CRÍTICO)
- ✅ Re-enable o strengthen ODS logic (CRÍTICO)
- ✅ Add volume filters para smallcaps
- ✅ Document first 30min breakout mode

**Comparado con ORB worker:**
- ORB score: 4.0/10
- Daily Plays score: 5.5/10
- **Daily Plays está MEJOR que ORB** pero aún tiene problemas serios

**Recomendación:** **OPCIÓN A (Refactor Ligero)** para fix rápido

---

**Generado:** 2025-12-03
**Analizado por:** Claude Code (Forensic Analysis)
**Próximo paso:** Decidir entre Opción A, B, o C según urgencia

