# 📊 Multi-Day Monitoring Improvements

## Problema Identificado

El sistema detectaba patrones "Green Day 1" correctamente en **Day 0**, pero **no actualizaba los niveles clave** en los días siguientes (Day 1-7). Esto causaba:

❌ **PROBLEMA 1**: Resistencias obsoletas
- Day 0: Detecta `day1_high = $3.25`
- Day 2: Stock hace nuevo high de `$3.50`
- Sistema: **Todavía usa $3.25** (obsoleto)

❌ **PROBLEMA 2**: Worker ciego a breakouts diarios
- Si el stock rompe Day 1 High en Day 2, el worker no lo detecta
- Busca breakout del nivel **obsoleto** en lugar del nivel **actual**

❌ **PROBLEMA 3**: Stop loss incorrecto
- Worker pone stop 1% debajo de Day 1 High ($3.25)
- Pero el breakout real fue de $3.50
- Stop demasiado bajo = Mayor riesgo

## Solución Implementada

### 1. Monitor Diario de Candidatos

**Archivo**: `scanner/smallcap/proactive_scanner.py`

Nuevo método `_monitor_existing_candidates()` que:

✅ **Fetchea daily bars** para cada candidato activo (Day 0-7)
✅ **Analiza estructura diaria** (BREAKOUT, HIGHER_HIGH, INSIDE_DAY, LOWER_HIGH)
✅ **Actualiza resistencia** cuando se hacen nuevos highs
✅ **Almacena niveles por día** (day2_high, day3_high, etc.)
✅ **Guarda estructura** para que el worker adapte su lógica

```python
async def _monitor_existing_candidates(self):
    """
    Monitor existing candidates (Day 1 - Day 7) for:
    1. Update resistance levels when new daily highs are made
    2. Detect daily structure (BREAKOUT, HIGHER_HIGH, INSIDE_DAY, LOWER_HIGH)
    3. Update key_levels with day-specific highs
    """
    # Fetch 10 days of daily bars
    bars = await self.ibkr_adapter.get_bars(symbol, '1d', 10)

    # Analyze yesterday's structure
    daily_structure = self._analyze_daily_structure(
        yesterday_bar, current_resistance, day1_high
    )

    # Update resistance if broke previous high
    if yesterday_high > current_resistance:
        key_levels['resistance'] = yesterday_high
        key_levels[f'day{days_since}_high'] = yesterday_high
```

### 2. Análisis de Estructura Diaria

**Método**: `_analyze_daily_structure()`

Clasifica cada vela diaria:

- **BREAKOUT**: Rompió Day 1 High por primera vez (>1%)
- **HIGHER_HIGH**: Continuación, haciendo nuevos highs
- **INSIDE_DAY**: Consolidación (no hizo nuevo high)
- **LOWER_HIGH**: Debilidad (no pudo romper resistencia)

```python
def _analyze_daily_structure(yesterday_bar, previous_high, day1_high):
    yesterday_high = float(yesterday_bar.high)

    # Check if broke previous resistance
    if yesterday_high > previous_high * 1.005:  # >0.5% above
        if previous_high == day1_high and yesterday_high > day1_high * 1.01:
            return "BREAKOUT"  # First break of Day 1 High
        else:
            return "HIGHER_HIGH"  # Continuation

    elif yesterday_high <= previous_high:
        return "INSIDE_DAY"  # Consolidation

    else:
        return "LOWER_HIGH"  # Weakness
```

### 3. Worker Usa Resistencia Actual

**Archivo**: `strategies/workers/short_squeeze_worker_logic.py`

**ANTES** (❌):
```python
day1_high = trading_rec.get('day1_high')  # Siempre $3.25
if current_price > day1_high:
    # Breakout detection
```

**DESPUÉS** (✅):
```python
key_levels = json.loads(candidate_info.get('key_levels'))
current_resistance = key_levels.get('resistance')  # $3.50 en Day 2
daily_structure = key_levels.get('daily_structure')  # "BREAKOUT"

if current_price > current_resistance:
    # Uses UPDATED resistance!
```

### 4. Volumen Adaptativo por Estructura

El worker ahora ajusta los thresholds de volumen según la estructura diaria:

```python
# Base threshold by days_since_detection
if days_since <= 2:
    base_threshold = 1.5
elif days_since <= 5:
    base_threshold = 2.0
else:
    base_threshold = 3.0

# Adjust based on daily structure
if daily_structure in ['BREAKOUT', 'HIGHER_HIGH']:
    min_vol_threshold = base_threshold - 0.5  # Relax (ya muestra fortaleza)
elif daily_structure == 'LOWER_HIGH':
    min_vol_threshold = base_threshold + 0.5  # Increase (necesita más confirmación)
else:
    min_vol_threshold = base_threshold  # Standard
```

**Ejemplo**:
- Day 2 + BREAKOUT: 1.5x - 0.5 = **1.0x** (muy agresivo)
- Day 2 + LOWER_HIGH: 1.5x + 0.5 = **2.0x** (más conservador)

### 5. Stop Loss Correcto

**ANTES** (❌):
```python
day1_high = trading_rec.get('day1_high')  # $3.25
fixed_stop = day1_high * 0.99  # $3.22
```

**DESPUÉS** (✅):
```python
key_levels = json.loads(candidate_info.get('key_levels'))
resistance_broken = key_levels.get('resistance')  # $3.50 (actual level broken)
fixed_stop = resistance_broken * 0.99  # $3.46 (7.7% better protection!)
```

## Ejemplo Real: AZI

### Escenario Anterior (❌)

```
Day 0: AZI detectado, day1_high = $3.25
Day 1: AZI hace inside day, high = $3.20
Day 2: AZI breakout a $3.50 ← Sistema NO LO VE
Day 3: Worker busca breakout de... $3.25 (obsoleto!)
```

### Escenario Nuevo (✅)

```
Day 0: AZI detectado
  key_levels = {
    "day1_high": 3.25,
    "resistance": 3.25,
    "daily_structure": "N/A"
  }

Day 1: Monitor detecta inside day
  key_levels = {
    "day1_high": 3.25,
    "resistance": 3.25,
    "day1_high": 3.20,
    "daily_structure": "INSIDE_DAY"
  }

Day 2: Monitor detecta BREAKOUT!
  key_levels = {
    "day1_high": 3.25,
    "resistance": 3.50,  ← ACTUALIZADO!
    "day2_high": 3.50,
    "daily_structure": "BREAKOUT"
  }

Day 3: Worker busca breakout de $3.50 (correcto!)
  - Volume threshold: 1.5x - 0.5 = 1.0x (relajado por BREAKOUT)
  - Stop loss: $3.46 (1% below $3.50)
```

## Base de Datos

### Tabla: `proactive_candidates`

Campos actualizados diariamente:

```sql
key_levels = {
    "day1_high": 3.25,      -- Nunca cambia (referencia original)
    "day1_low": 2.08,
    "resistance": 3.50,     -- ✅ SE ACTUALIZA con nuevos highs
    "day2_high": 3.30,      -- ✅ NUEVO: High del Day 2
    "day3_high": 3.50,      -- ✅ NUEVO: High del Day 3
    "daily_structure": "BREAKOUT"  -- ✅ NUEVO: Estructura actual
}
```

### Query para Análisis

```sql
-- Ver evolución de niveles por candidato
SELECT
    symbol,
    days_since_detection,
    json_extract(key_levels, '$.day1_high') as day1_high,
    json_extract(key_levels, '$.resistance') as current_resistance,
    json_extract(key_levels, '$.daily_structure') as structure
FROM proactive_candidates
WHERE status IN ('WATCHING', 'TRIGGERED')
ORDER BY days_since_detection;
```

## Testing

### Test Completo: `test_multiday_monitoring.py`

✅ **TEST 1**: Daily structure analysis
- BREAKOUT detection (>1% above Day 1)
- HIGHER_HIGH detection (continuation)
- INSIDE_DAY detection (consolidation)
- LOWER_HIGH detection (weakness)

✅ **TEST 2**: Database level updates
- Resistance updates correctly
- day2_high, day3_high stored
- Structure saved to DB

✅ **TEST 3**: Worker uses current resistance
- Not stale Day 1 High
- Uses updated levels

✅ **TEST 4**: Adaptive volume thresholds
- BREAKOUT: -0.5x (relaxed)
- HIGHER_HIGH: -0.5x (relaxed)
- INSIDE_DAY: standard
- LOWER_HIGH: +0.5x (stricter)

✅ **TEST 5**: Stop loss placement
- Uses resistance that was broken
- Not Day 1 High
- 7.7% tighter protection

**Run test**:
```bash
python test_multiday_monitoring.py
```

## Beneficios

### 1. Detección Precisa
✅ Worker detecta breakouts en **cualquier día** (0-7), no solo Day 0
✅ Usa niveles **actuales**, no obsoletos
✅ Entiende si el stock está en **continuación** o **debilidad**

### 2. Risk Management Mejorado
✅ Stop loss basado en nivel **realmente roto**
✅ No demasiado bajo (mejor protección)
✅ Apropiado para cada fase del squeeze

### 3. Volumen Adaptativo
✅ **Agresivo** cuando estructura es fuerte (BREAKOUT, HIGHER_HIGH)
✅ **Conservador** cuando estructura es débil (LOWER_HIGH)
✅ **Estándar** en consolidación (INSIDE_DAY)

### 4. Analytics Mejorados
✅ Puede analizar win rate por **estructura diaria**
✅ Optimizar parámetros según **días** + **estructura**
✅ Identificar qué estructuras producen mejores resultados

## Próximos Pasos

1. ✅ Ejecutar sistema por 30-50 trades
2. ✅ Analizar performance por estructura diaria
3. ✅ Optimizar thresholds basado en data real
4. ✅ Comparar BREAKOUT vs HIGHER_HIGH vs INSIDE_DAY win rates

## Queries de Análisis

```sql
-- Win rate by daily structure
SELECT
    json_extract(pc.key_levels, '$.daily_structure') as structure,
    COUNT(*) as trades,
    AVG(profit_pct) as avg_profit,
    100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*) as win_rate
FROM trades t
JOIN proactive_candidates pc ON t.symbol = pc.symbol
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
GROUP BY structure
ORDER BY win_rate DESC;

-- Performance by days + structure
SELECT
    entry_day,
    json_extract(pc.key_levels, '$.daily_structure') as structure,
    COUNT(*) as trades,
    AVG(profit_pct) as avg_profit,
    100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*) as win_rate
FROM trades t
JOIN proactive_candidates pc ON t.symbol = pc.symbol
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
GROUP BY entry_day, structure
ORDER BY entry_day, win_rate DESC;
```

## Archivos Modificados

1. ✅ `scanner/smallcap/proactive_scanner.py`
   - `_monitor_existing_candidates()` - Fetch & update daily levels
   - `_update_candidate_levels()` - Update resistance & structure
   - `_analyze_daily_structure()` - Classify daily candles

2. ✅ `strategies/workers/short_squeeze_worker_logic.py`
   - Uses `current_resistance` instead of stale `day1_high`
   - Adapts volume thresholds by `daily_structure`
   - Stop loss uses resistance that was broken

3. ✅ `test_multiday_monitoring.py` (NEW)
   - Comprehensive test suite for all improvements

4. ✅ `ANALYTICS_GUIDE_SHORT_SQUEEZE.md`
   - Updated with structure-based analytics queries

## Conclusión

El sistema ahora tiene **visibilidad completa** del lifecycle de cada candidato:

- ✅ Day 0: Detecta patrón (GREEN_DAY_1, FAKE_BREAKDOWN)
- ✅ Day 1-7: **Monitorea evolución diaria** (NEW!)
- ✅ Worker: Usa **niveles actuales** (NEW!)
- ✅ Analytics: Puede optimizar por **estructura** (NEW!)

**Resultado**: Sistema robusto que adapta su estrategia basado en el comportamiento real del stock, no suposiciones obsoletas.
