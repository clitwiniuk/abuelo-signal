# 📊 TradeTally Short Squeeze Analytics

## Sistema Analítico Completo para Validar el Edge del Short Squeeze Strategy

Este módulo permite monitorizar y validar estadísticamente si el sistema de Short Squeeze (usando ProactiveScanner) tiene un edge real y cuantificable.

---

## 🎯 **¿Qué Worker Opera esta Estrategia?**

**SOLO el worker `short_squeeze`** utiliza el ProactiveScanner:
- ✅ `short_squeeze_worker_logic.py` - Lee `proactive_candidates` table
- ❌ `daily_plays_worker_logic.py` - NO usa ProactiveScanner
- ❌ Otros workers - NO usan ProactiveScanner

**Flujo**:
1. `ProactiveScanner` detecta patrones (GREEN_DAY_1, FAKE_BREAKDOWN)
2. Almacena en tabla `proactive_candidates` (Day 0-7 tracking)
3. `short_squeeze` worker ejecuta trades cuando triggerea (BREAKOUT_OPEN, VWAP_RECLAIM)
4. TradeTally Analytics analiza performance y valida edge

---

## 📁 **Archivos Creados**

### Backend (Node.js/Express)

1. **Routes** - `/tradetally/backend/src/routes/shortSqueeze.routes.js`
   ```javascript
   GET /api/short-squeeze/overview
   GET /api/short-squeeze/candidates
   GET /api/short-squeeze/performance-by-day
   GET /api/short-squeeze/performance-by-structure
   GET /api/short-squeeze/performance-matrix
   GET /api/short-squeeze/quality-analysis
   GET /api/short-squeeze/expiration-tracking
   GET /api/short-squeeze/edge-validation
   GET /api/short-squeeze/trade-details/:symbol
   GET /api/short-squeeze/candidate-timeline/:symbol
   ```

2. **Controller** - `/tradetally/backend/src/controllers/shortSqueeze.controller.js`
   - Implementa toda la lógica analítica
   - Queries SQL optimizados
   - Validación estadística de edge

3. **Server Registration** - `/tradetally/backend/src/server.js`
   - Línea 42: `const shortSqueezeRoutes = require('./routes/shortSqueeze.routes');`
   - Línea 144: `app.use('/api/short-squeeze', shortSqueezeRoutes);`

### Frontend (Vue.js)

4. **Component** - `/tradetally/frontend/src/components/analytics/ShortSqueezeAnalytics.vue`
   - Dashboard completo con visualizaciones
   - Filtros de fecha
   - Tablas interactivas
   - Validación estadística visual

---

## 🚀 **Cómo Activar el Sistema**

### 1. Restart TradeTally Backend

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/tradetally
./tt-manage.sh restart backend
```

### 2. Verificar API (Opcional)

```bash
# Test overview endpoint
curl -X GET "http://localhost:5001/api/short-squeeze/overview" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Test edge validation
curl -X GET "http://localhost:5001/api/short-squeeze/edge-validation" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Acceder al Dashboard Frontend

**Opción A**: Integrar en menú de Analytics existente

Edita `/tradetally/frontend/src/router/index.js` (o donde se definan las rutas):

```javascript
{
  path: '/analytics/short-squeeze',
  name: 'ShortSqueezeAnalytics',
  component: () => import('@/components/analytics/ShortSqueezeAnalytics.vue'),
  meta: { requiresAuth: true }
}
```

**Opción B**: Crear página standalone

```bash
# Acceder directamente al componente
http://localhost:5173/analytics/short-squeeze
```

---

## 📊 **Métricas y Análisis Disponibles**

### 1. **Overview Dashboard**

**Endpoint**: `GET /api/short-squeeze/overview`

Muestra:
- Total candidates (WATCHING, TRIGGERED, EXPIRED)
- Total trades ejecutados
- Win rate global
- Average return
- Profit factor
- Total P&L
- Recent candidates (últimos 7 días)
- **Edge validation** con significancia estadística

**Edge Validation Incluye**:
- ✅ Sample size
- ✅ Expected value (avg return)
- ✅ T-statistic (significancia estadística)
- ✅ Recommendation (KEEP / MONITOR / REVIEW)

### 2. **Performance by Entry Day**

**Endpoint**: `GET /api/short-squeeze/performance-by-day`

Analiza:
- Win rate por día de entrada (Day 0, Day 1, ..., Day 7)
- Avg profit/loss por día
- Best/worst trade por día
- **Recommendation**: ✅ KEEP, ⚠️ MONITOR, ❌ SKIP

**Ejemplo Output**:
```
entry_day | trades | win_rate | avg_profit | recommendation
----------|--------|----------|------------|---------------
0         | 15     | 66.7%    | 8.5%       | ✅ KEEP
1         | 22     | 63.6%    | 6.2%       | ✅ KEEP
2         | 18     | 61.1%    | 5.1%       | ⚠️ MONITOR
3         | 12     | 50.0%    | 2.3%       | ⚠️ MONITOR
5         | 8      | 37.5%    | -1.2%      | ❌ SKIP
```

**Insight**: Si Day 3+ muestra < 50% win rate, deshabilitar entradas tardías.

### 3. **Performance by Daily Structure** (NEW!)

**Endpoint**: `GET /api/short-squeeze/performance-by-structure`

Analiza performance según la estructura diaria:
- **BREAKOUT**: Stock rompió Day 1 High (>1%)
- **HIGHER_HIGH**: Continuación, haciendo nuevos highs
- **INSIDE_DAY**: Consolidación
- **LOWER_HIGH**: Debilidad

**Ejemplo Output**:
```
structure    | trades | win_rate | avg_profit | insight
-------------|--------|----------|------------|--------------------------------
BREAKOUT     | 12     | 75.0%    | 14.5%      | Stock breaking Day 1 High - strongest
HIGHER_HIGH  | 18     | 66.7%    | 10.2%      | Continuation - solid follow-through
INSIDE_DAY   | 8      | 50.0%    | 5.3%       | Consolidation - needs confirmation
LOWER_HIGH   | 5      | 40.0%    | -2.1%      | Weakness - proceed with caution
```

**Acción**: Si LOWER_HIGH tiene <45% win rate, skip esas entradas.

### 4. **Performance Matrix (Day × Structure)**

**Endpoint**: `GET /api/short-squeeze/performance-matrix`

Matriz combinada: Entry Day × Daily Structure

**Ejemplo Output**:
```
entry_day | structure   | trades | avg_profit | win_rate | recommendation
----------|-------------|--------|------------|----------|---------------
0         | BREAKOUT    | 5      | 18.5%      | 80.0%    | ✅ KEEP
0         | HIGHER_HIGH | 8      | 12.3%      | 62.5%    | ⚠️ MONITOR
1         | BREAKOUT    | 7      | 15.2%      | 71.4%    | ✅ KEEP
2         | INSIDE_DAY  | 6      | 5.2%       | 50.0%    | ⚠️ MONITOR
3         | LOWER_HIGH  | 4      | -1.5%      | 25.0%    | ❌ SKIP
```

**Insight**: Day 0-1 + BREAKOUT = Golden combination (>70% win rate).

### 5. **Squeeze Quality Analysis**

**Endpoint**: `GET /api/short-squeeze/quality-analysis`

Performance por squeeze quality:
- **ULTIMATE**: Zero borrows (NONE status)
- **IDEAL**: Hard-to-borrow (HTB)
- **NORMAL**: Easy-to-borrow (ETB)

**Ejemplo Output**:
```
quality  | trades | win_rate | avg_profit | description
---------|--------|----------|------------|---------------------------
ULTIMATE | 12     | 75.0%    | 14.5%      | Zero borrows - crowded short
IDEAL    | 18     | 66.7%    | 10.2%      | HTB - high demand, low supply
NORMAL   | 8      | 50.0%    | 5.3%       | ETB - standard squeeze
```

**Acción**: Si NORMAL tiene <50% win rate, considerar skip.

### 6. **Expiration Tracking**

**Endpoint**: `GET /api/short-squeeze/expiration-tracking`

Rastrea candidatos que **nunca triggerearon** (EXPIRED):
- Expiration rate global
- Trigger rate global
- Patrones que más expiran

**Ejemplo Output**:
```
pattern_type  | quality | expired_count | symbols
--------------|---------|---------------|------------------
GREEN_DAY_1   | NORMAL  | 12            | ABC, DEF, GHI...
FAKE_BREAKDOWN| NORMAL  | 8             | JKL, MNO, PQR...
GREEN_DAY_1   | IDEAL   | 3             | STU, VWX, YZ
```

**Insight**:
- ✅ ULTIMATE/IDEAL raramente expiran = Alta calidad
- ❌ NORMAL expira frecuentemente = Baja calidad, skip

### 7. **Edge Validation** (Validación Estadística)

**Endpoint**: `GET /api/short-squeeze/edge-validation`

Valida si el edge es **estadísticamente significativo**:

```javascript
{
  sample_size: 50,
  expected_value: 6.5,        // Avg return %
  volatility: 12.3,           // Std deviation
  profit_factor: 2.1,         // Gross profit / Gross loss
  standard_error: 1.74,
  t_statistic: 3.74,          // > 1.96 = significant
  confidence_95_lower: 3.1,   // Lower bound of 95% CI
  confidence_95_upper: 9.9,   // Upper bound
  is_significant: true,       // Statistical significance
  confidence_level: "95%",
  recommendation: "✅ STRONG EDGE DETECTED",
  status: "VALIDATED"
}
```

**Interpretación**:
- **sample_size < 30**: ⚠️ "Need more data"
- **t_statistic > 1.96 AND expected_value > 0 AND profit_factor > 1.5**: ✅ "STRONG EDGE"
- **expected_value > 0 AND profit_factor > 1.0**: ⚠️ "WEAK EDGE"
- **Else**: ❌ "NO EDGE - Review or disable"

---

## 🧪 **Cómo Validar si Hay Edge Real**

### Paso 1: Collect Sample (30-50 trades mínimo)

Ejecuta el sistema normalmente hasta tener al menos **30 trades** de Short Squeeze.

### Paso 2: Check Edge Validation

```bash
GET /api/short-squeeze/edge-validation?startDate=2024-01-01&endDate=2024-12-25
```

**Si devuelve**:
```json
{
  "sample_size": 50,
  "expected_value": 6.5,
  "is_significant": true,
  "profit_factor": 2.1,
  "recommendation": "✅ STRONG EDGE DETECTED",
  "status": "VALIDATED"
}
```

**Entonces**: ✅ **Edge validado**, continuar operando.

### Paso 3: Analyze by Segments

Si el edge global es débil, analiza por segmentos:

**Query 1**: Performance by Day
```sql
-- ¿Qué días funcionan mejor?
SELECT entry_day, win_rate, avg_profit, recommendation
FROM /api/short-squeeze/performance-by-day
```

**Acción**: Si Day 0-2 tienen >65% win rate, deshabilita Day 5-7.

**Query 2**: Performance by Structure
```sql
-- ¿Qué estructuras funcionan mejor?
SELECT structure, win_rate, avg_profit
FROM /api/short-squeeze/performance-by-structure
```

**Acción**: Si BREAKOUT/HIGHER_HIGH tienen >70% win rate, skip LOWER_HIGH.

**Query 3**: Performance Matrix
```sql
-- ¿Qué combinaciones son gold?
SELECT entry_day, structure, win_rate, recommendation
FROM /api/short-squeeze/performance-matrix
WHERE recommendation = '✅ KEEP'
```

**Acción**: Solo operar combinaciones que sean "✅ KEEP".

### Paso 4: Optimize Config Based on Data

Basado en resultados, ajusta `config.ini`:

```ini
[SHORT_SQUEEZE_STRATEGY]
# Si Day 0-2 + BREAKOUT tiene >75% win rate
ultimate_size_multiplier = 1.5

# Si Day 5-7 tiene <40% win rate
max_entry_day = 4  # Skip Day 5-7

# Si LOWER_HIGH tiene <45% win rate
skip_lower_high_structure = true
```

---

## 📈 **Dashboard Visual**

El componente Vue `ShortSqueezeAnalytics.vue` proporciona:

### Sección 1: Overview Cards
- Edge Validation Card (con colores según status)
- Overall Performance Card
- Watchlist Status Card

### Sección 2: Performance Tables
- Performance by Entry Day (tabla completa)
- Performance by Daily Structure (tabla + insights)
- Performance Matrix (Day × Structure)
- Squeeze Quality Analysis
- Expiration Tracking

### Sección 3: Recent Candidates
- Tabla de candidatos recientes (últimos 7 días)
- Status actual (WATCHING, TRIGGERED, EXPIRED)
- Resistance levels actualizados

### Features:
- ✅ Filtros de fecha (custom date range)
- ✅ Color coding (green = good, red = bad, yellow = neutral)
- ✅ Badges para status, structure, quality
- ✅ Recommendations automáticas (KEEP / MONITOR / SKIP)
- ✅ Insights boxes explicando cada métrica

---

## 🔍 **Ejemplo de Uso Real**

### Escenario: Después de 50 trades

1. **Acceder al dashboard**:
   ```
   http://localhost:5173/analytics/short-squeeze
   ```

2. **Revisar Edge Validation**:
   - Sample size: 50 ✅
   - Expected value: 6.5% ✅
   - Profit factor: 2.1 ✅
   - T-statistic: 3.74 (>1.96) ✅
   - **Recommendation: ✅ STRONG EDGE DETECTED**

3. **Analizar por segmentos**:

   **Performance by Day**:
   ```
   Day 0: 75% win rate (15 trades) ✅ KEEP
   Day 1: 68% win rate (22 trades) ✅ KEEP
   Day 2: 62% win rate (18 trades) ⚠️ MONITOR
   Day 5: 35% win rate (8 trades)  ❌ SKIP
   ```

   **Performance by Structure**:
   ```
   BREAKOUT:    75% win rate ✅
   HIGHER_HIGH: 67% win rate ✅
   INSIDE_DAY:  50% win rate ⚠️
   LOWER_HIGH:  40% win rate ❌
   ```

4. **Decisión**:
   - ✅ Continuar operando Day 0-2
   - ❌ Deshabilitar Day 5-7 (poor performance)
   - ✅ Ser agresivo con BREAKOUT/HIGHER_HIGH
   - ❌ Skip LOWER_HIGH structure

5. **Implementar cambios en código**:
   ```python
   # short_squeeze_worker_logic.py
   days_since_detection = candidate_info.get('days_since_detection', 0)
   daily_structure = key_levels.get('daily_structure', 'UNKNOWN')

   # Skip Day 5+
   if days_since_detection > 4:
       self.logger.debug(f"{symbol}: Day {days_since_detection} > 4, skipping (data shows poor performance)")
       return False

   # Skip LOWER_HIGH
   if daily_structure == 'LOWER_HIGH':
       self.logger.debug(f"{symbol}: LOWER_HIGH structure, skipping (data shows <45% win rate)")
       return False
   ```

---

## 📊 **SQL Queries Disponibles (Para Análisis Manual)**

Si prefieres queries SQL directos:

```sql
-- 1. Edge validation manual
SELECT
  COUNT(*) as n,
  AVG(profit_loss_pct) as expected_value,
  STDEV(profit_loss_pct) as volatility,
  SUM(CASE WHEN profit_loss_pct > 0 THEN profit_loss_total ELSE 0 END) as gross_profit,
  ABS(SUM(CASE WHEN profit_loss_pct < 0 THEN profit_loss_total ELSE 0 END)) as gross_loss
FROM trades
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM');

-- 2. Performance by structure
SELECT
  json_extract(pc.key_levels, '$.daily_structure') as structure,
  COUNT(*) as trades,
  AVG(t.profit_loss_pct) as avg_profit,
  100.0 * SUM(CASE WHEN t.profit_loss_pct > 0 THEN 1 ELSE 0 END) / COUNT(*) as win_rate
FROM trades t
JOIN proactive_candidates pc ON t.symbol = pc.symbol
WHERE t.setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
GROUP BY structure
ORDER BY win_rate DESC;

-- 3. Expirations por pattern
SELECT
  pattern_type,
  json_extract(metrics, '$.squeeze_quality') as quality,
  COUNT(*) as expired_count
FROM proactive_candidates
WHERE status = 'EXPIRED'
GROUP BY pattern_type, quality;
```

---

## ✅ **Testing Checklist**

Antes de usar en producción:

1. ✅ Backend routes registradas en `server.js`
2. ✅ Controller implementado con queries SQL
3. ✅ Frontend component creado
4. ✅ Restart backend: `./tt-manage.sh restart backend`
5. ✅ Test API endpoint: `curl http://localhost:5001/api/short-squeeze/overview`
6. ✅ Acceder a frontend: `http://localhost:5173/analytics/short-squeeze`
7. ✅ Ejecutar 30+ trades de Short Squeeze
8. ✅ Validar edge con métricas estadísticas
9. ✅ Optimizar config basado en data real

---

## 🎯 **Conclusión**

Con este sistema analítico puedes:

1. ✅ **Validar estadísticamente** si el Short Squeeze tiene edge real
2. ✅ **Identificar** qué días (0-7) funcionan mejor
3. ✅ **Optimizar** por estructura diaria (BREAKOUT > HIGHER_HIGH > INSIDE_DAY > LOWER_HIGH)
4. ✅ **Detectar** patrones que expiran frecuentemente (bajo edge)
5. ✅ **Tomar decisiones** basadas en data, no suposiciones
6. ✅ **Iterar** mensualmente para refinar la estrategia

**Resultado**: Sistema de trading data-driven que se auto-optimiza basado en performance real.
