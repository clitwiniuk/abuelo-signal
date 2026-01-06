# 📊 Short Squeeze Analytics Guide

## Guía Completa de Análisis Post-Trading

Este documento explica cómo usar el nuevo sistema de multi-day tracking para optimizar la estrategia de Short Squeeze mediante análisis de datos.

---

## 🎯 **Nuevas Capacidades de Análisis**

### **1. Win Rate por Día de Entrada**

#### Pregunta: ¿Qué día produce mejores resultados?

```sql
-- Análisis de performance por día de entrada
SELECT
    entry_day,
    COUNT(*) as total_trades,
    SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(profit_pct), 2) as avg_profit,
    ROUND(AVG(CASE WHEN profit_pct > 0 THEN profit_pct END), 2) as avg_win,
    ROUND(AVG(CASE WHEN profit_pct < 0 THEN profit_pct END), 2) as avg_loss,
    ROUND(100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
FROM trades
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
AND entry_day IS NOT NULL
GROUP BY entry_day
ORDER BY entry_day;
```

**Ejemplo de Output:**
```
entry_day | total_trades | wins | avg_profit | avg_win | avg_loss | win_rate
----------|--------------|------|------------|---------|----------|----------
0         | 15           | 10   | 8.5%       | 15.2%   | -5.1%    | 66.7%
1         | 22           | 14   | 6.2%       | 12.8%   | -4.9%    | 63.6%
2         | 18           | 11   | 5.1%       | 11.5%   | -5.3%    | 61.1%
3         | 12           | 6    | 2.3%       | 9.8%    | -6.2%    | 50.0%
5         | 8            | 3    | -1.2%      | 8.5%    | -7.1%    | 37.5%
7         | 3            | 1    | -3.5%      | 6.2%    | -8.4%    | 33.3%
```

**Insights:**
- ✅ Day 0-2 producen mejor win rate (>60%)
- ⚠️ Day 3-5 muestran degradación
- ❌ Day 6-7 tienen poor performance

**Acción:** Ajustar config para ser más agresivo en Days 0-2, más selectivo después.

---

### **2. Setup Type Performance**

#### Pregunta: ¿Breakout Open vs VWAP Reclaim?

```sql
-- Comparar efectividad de setups
SELECT
    setup_type,
    entry_day,
    COUNT(*) as trades,
    ROUND(AVG(profit_pct), 2) as avg_profit,
    ROUND(100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
FROM trades
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
GROUP BY setup_type, entry_day
ORDER BY setup_type, entry_day;
```

**Ejemplo de Output:**
```
setup_type    | entry_day | trades | avg_profit | win_rate
--------------|-----------|--------|------------|----------
BREAKOUT_OPEN | 0         | 8      | 12.3%      | 75.0%
BREAKOUT_OPEN | 1         | 10     | 9.5%       | 70.0%
BREAKOUT_OPEN | 2         | 6      | 7.2%       | 66.7%
VWAP_RECLAIM  | 1         | 12     | 4.8%       | 58.3%
VWAP_RECLAIM  | 2         | 10     | 3.5%       | 50.0%
VWAP_RECLAIM  | 3         | 8      | 1.2%       | 37.5%
```

**Insights:**
- ✅ Breakout Open (Days 0-2) es MÁS efectivo
- ⚠️ VWAP Reclaim degrada con días
- ❌ VWAP Reclaim Day 3+ tiene bajo rendimiento

---

### **3. Squeeze Quality Analysis**

#### Pregunta: ¿ULTIMATE vs IDEAL vs NORMAL?

```sql
-- Performance por squeeze quality
SELECT
    squeeze_quality,
    entry_day,
    COUNT(*) as trades,
    ROUND(AVG(profit_pct), 2) as avg_profit,
    ROUND(100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
FROM trades t
JOIN proactive_candidates pc ON t.symbol = pc.symbol
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
GROUP BY squeeze_quality, entry_day
ORDER BY squeeze_quality, entry_day;
```

**Ejemplo de Output:**
```
squeeze_quality | entry_day | trades | avg_profit | win_rate
----------------|-----------|--------|------------|----------
ULTIMATE        | 0         | 5      | 18.5%      | 80.0%
ULTIMATE        | 1         | 7      | 14.2%      | 71.4%
IDEAL           | 0         | 8      | 11.3%      | 62.5%
IDEAL           | 1         | 10     | 8.5%       | 60.0%
NORMAL          | 0         | 4      | 5.2%       | 50.0%
NORMAL          | 1         | 5      | 3.1%       | 40.0%
```

**Insights:**
- ✅ ULTIMATE quality tiene mejor performance consistente
- ✅ IDEAL sigue siendo profitable
- ⚠️ NORMAL es marginal

**Acción:**
- Aumentar size en ULTIMATE (de 1.0x a 1.5x?)
- Mantener IDEAL (0.66x)
- Considerar skip NORMAL si entry_day > 2

---

### **4. Expiration Analysis (Lost Opportunities)**

#### Pregunta: ¿Qué patrones nunca triggerearon?

```sql
-- Candidatos que expiraron sin triggerear
SELECT
    pattern_type,
    squeeze_quality,
    COUNT(*) as expired_count,
    GROUP_CONCAT(symbol, ', ') as symbols
FROM proactive_candidates
WHERE status = 'EXPIRED'
GROUP BY pattern_type, squeeze_quality
ORDER BY expired_count DESC;
```

**Ejemplo de Output:**
```
pattern_type  | squeeze_quality | expired_count | symbols
--------------|-----------------|---------------|------------------
GREEN_DAY_1   | NORMAL          | 12            | ABC, DEF, GHI...
FAKE_BREAKDOWN| NORMAL          | 8             | JKL, MNO, PQR...
GREEN_DAY_1   | IDEAL           | 3             | STU, VWX, YZ
FAKE_BREAKDOWN| ULTIMATE        | 1             | RARE
```

**Insights:**
- ❌ NORMAL quality expira frecuentemente (bajo edge)
- ✅ ULTIMATE rara vez expira (alta probabilidad)
- 📊 GREEN_DAY_1 tiene más expiraciones que FAKE_BREAKDOWN

**Acción:**
- Considerar skip NORMAL quality después de optimización
- GREEN_DAY_1 puede necesitar mejores filtros

---

### **5. Volume Threshold Optimization**

#### Pregunta: ¿Los thresholds adaptativos funcionan?

```sql
-- Performance con diferentes niveles de volumen
SELECT
    CASE
        WHEN entry_day <= 2 THEN '1.5x (Aggressive)'
        WHEN entry_day <= 5 THEN '2.0x (Moderate)'
        ELSE '3.0x (Conservative)'
    END as threshold_group,
    entry_day,
    COUNT(*) as trades,
    ROUND(AVG(profit_pct), 2) as avg_profit,
    ROUND(100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
FROM trades
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
GROUP BY threshold_group, entry_day
ORDER BY entry_day;
```

---

### **6. Holding Period Analysis**

#### Pregunta: ¿Cuánto duran los squeezes exitosos?

```sql
-- Distribución de holding period por día de entrada
SELECT
    entry_day,
    AVG(holding_hours) as avg_hold_hours,
    MIN(holding_hours) as min_hold,
    MAX(holding_hours) as max_hold,
    ROUND(AVG(CASE WHEN profit_pct > 0 THEN holding_hours END), 1) as avg_win_hold,
    ROUND(AVG(CASE WHEN profit_pct < 0 THEN holding_hours END), 1) as avg_loss_hold
FROM trades
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
GROUP BY entry_day;
```

**Insights:**
- Winners tienden a resolver rápido (< 24h)
- Losers se quedan estancados (> 48h)

---

## 🔧 **Configuración Optimizada Basada en Data**

### Después de 30+ trades, puedes ajustar:

```ini
[SHORT_SQUEEZE_STRATEGY]
# OPTIMIZADO POR ANALYTICS

# Day 0-2 Settings (si win_rate > 65%)
aggressive_breakout_open = true
aggressive_volume_threshold = 1.3  # Incluso más relajado si data lo soporta

# Day 3-5 Settings (si win_rate 50-60%)
moderate_vwap_only = true
moderate_volume_threshold = 2.5  # Más estricto

# Day 6-7 Settings (si win_rate < 40%)
conservative_disable = true  # Skip completamente si no profitable

# Quality Filters (basado en expiration analysis)
skip_normal_after_day = 2  # Si NORMAL tiene alta expiración
ultimate_size_multiplier = 1.5  # Si ULTIMATE tiene >75% win rate
```

---

## 📈 **Ejemplo de Análisis Completo**

### Escenario: Después de 50 trades

```sql
-- Full Performance Report
WITH trade_stats AS (
    SELECT
        entry_day,
        setup_type,
        squeeze_quality,
        COUNT(*) as trades,
        AVG(profit_pct) as avg_profit,
        100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*) as win_rate
    FROM trades t
    JOIN proactive_candidates pc ON t.symbol = pc.symbol
    WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
    GROUP BY entry_day, setup_type, squeeze_quality
)
SELECT
    entry_day,
    setup_type,
    squeeze_quality,
    trades,
    ROUND(avg_profit, 2) || '%' as avg_profit,
    ROUND(win_rate, 1) || '%' as win_rate,
    CASE
        WHEN win_rate >= 65 THEN '✅ KEEP'
        WHEN win_rate >= 50 THEN '⚠️ MONITOR'
        ELSE '❌ SKIP'
    END as recommendation
FROM trade_stats
ORDER BY entry_day, win_rate DESC;
```

---

## 🎯 **Decisiones que Puedes Tomar**

### Basado en Win Rate:
- **> 65%**: Aumentar sizing, relajar filtros
- **50-65%**: Mantener actual
- **< 50%**: Añadir filtros, reducir sizing
- **< 35%**: Deshabilitar ese segmento

### Basado en Avg Profit:
- **> 10%**: Considerar aumentar TP target
- **5-10%**: TP actual (40%) está bien
- **< 5%**: TP puede ser muy agresivo, trail más temprano

### Basado en Expiraciones:
- **Alta expiración NORMAL**: Skip NORMAL quality
- **Alta expiración GREEN_DAY_1**: Mejorar detección
- **Alta expiración Day 6-7**: Deshabilitar entradas tardías

---

## 📊 **Dashboard SQL Queries**

### Query 1: Performance Summary
```sql
SELECT
    'Total Trades' as metric,
    COUNT(*) as value
FROM trades WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
UNION ALL
SELECT 'Win Rate', ROUND(100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*), 1)
FROM trades WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
UNION ALL
SELECT 'Avg Profit', ROUND(AVG(profit_pct), 2)
FROM trades WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
UNION ALL
SELECT 'Best Day', entry_day
FROM (SELECT entry_day, AVG(profit_pct) as p FROM trades WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM') GROUP BY entry_day ORDER BY p DESC LIMIT 1);
```

### Query 2: Red Flags
```sql
-- Identify losing patterns
SELECT
    entry_day,
    setup_type,
    squeeze_quality,
    COUNT(*) as trades,
    ROUND(AVG(profit_pct), 2) as avg_profit,
    ROUND(100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
FROM trades t
JOIN proactive_candidates pc ON t.symbol = pc.symbol
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
AND profit_pct < 0
GROUP BY entry_day, setup_type, squeeze_quality
HAVING COUNT(*) >= 3  -- At least 3 trades
ORDER BY avg_profit ASC;
```

### Query 3: Performance by Daily Structure (NEW!)
```sql
-- Win rate by daily structure at entry
SELECT
    json_extract(pc.key_levels, '$.daily_structure') as daily_structure,
    COUNT(*) as trades,
    ROUND(AVG(profit_pct), 2) as avg_profit,
    ROUND(AVG(CASE WHEN profit_pct > 0 THEN profit_pct END), 2) as avg_win,
    ROUND(AVG(CASE WHEN profit_pct < 0 THEN profit_pct END), 2) as avg_loss,
    ROUND(100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
FROM trades t
JOIN proactive_candidates pc ON t.symbol = pc.symbol
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
GROUP BY daily_structure
ORDER BY win_rate DESC;
```

**Expected Output:**
```
daily_structure | trades | avg_profit | avg_win | avg_loss | win_rate
----------------|--------|------------|---------|----------|----------
BREAKOUT        | 12     | 14.5%      | 18.2%   | -4.8%    | 75.0%
HIGHER_HIGH     | 18     | 10.2%      | 14.5%   | -5.2%    | 66.7%
INSIDE_DAY      | 8      | 5.3%       | 11.2%   | -6.1%    | 50.0%
LOWER_HIGH      | 5      | -2.1%      | 8.5%    | -7.5%    | 40.0%
```

**Insights:**
- ✅ BREAKOUT entries have highest win rate (stock already breaking out on daily)
- ✅ HIGHER_HIGH shows strong continuation
- ⚠️ INSIDE_DAY is 50/50 (wait for confirmation)
- ❌ LOWER_HIGH has poor performance (weakness signal)

**Action:** Adjust volume thresholds or skip LOWER_HIGH entries after data confirms pattern.

### Query 4: Entry Day + Structure Combination
```sql
-- Performance matrix: Days x Structure
SELECT
    entry_day,
    json_extract(pc.key_levels, '$.daily_structure') as structure,
    COUNT(*) as trades,
    ROUND(AVG(profit_pct), 2) as avg_profit,
    ROUND(100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate,
    CASE
        WHEN 100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*) >= 65 THEN '✅ KEEP'
        WHEN 100.0 * SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) / COUNT(*) >= 50 THEN '⚠️ MONITOR'
        ELSE '❌ SKIP'
    END as recommendation
FROM trades t
JOIN proactive_candidates pc ON t.symbol = pc.symbol
WHERE setup_type IN ('BREAKOUT_OPEN', 'VWAP_RECLAIM')
GROUP BY entry_day, structure
HAVING COUNT(*) >= 3  -- At least 3 trades for statistical significance
ORDER BY entry_day, win_rate DESC;
```

**Expected Output:**
```
entry_day | structure   | trades | avg_profit | win_rate | recommendation
----------|-------------|--------|------------|----------|---------------
0         | BREAKOUT    | 5      | 18.5%      | 80.0%    | ✅ KEEP
0         | HIGHER_HIGH | 8      | 12.3%      | 62.5%    | ⚠️ MONITOR
1         | BREAKOUT    | 7      | 15.2%      | 71.4%    | ✅ KEEP
1         | HIGHER_HIGH | 10     | 9.5%       | 60.0%    | ⚠️ MONITOR
2         | INSIDE_DAY  | 6      | 5.2%       | 50.0%    | ⚠️ MONITOR
3         | LOWER_HIGH  | 4      | -1.5%      | 25.0%    | ❌ SKIP
```

**Insights:**
- ✅ Day 0-1 + BREAKOUT = Best performance (>70% win rate)
- ✅ HIGHER_HIGH on early days is solid
- ⚠️ INSIDE_DAY needs more data
- ❌ LOWER_HIGH on Day 3+ should be skipped

---

## ✅ **Conclusión**

Con el nuevo sistema de multi-day tracking + daily monitoring tienes:

1. ✅ **Visibilidad completa** del lifecycle de cada candidato (Day 0-7)
2. ✅ **Data granular** para optimización basada en evidencia
3. ✅ **Tracking de expiración** para identificar patrones que no funcionan
4. ✅ **Adaptive strategy** que ajusta por días Y estructura diaria
5. ✅ **Entry day tracking** en cada trade para post-analysis
6. ✅ **Daily structure analysis** (BREAKOUT, HIGHER_HIGH, INSIDE_DAY, LOWER_HIGH) - NEW!
7. ✅ **Niveles actualizados** (resistance se actualiza cuando hay nuevos highs) - NEW!
8. ✅ **Stop loss correcto** (usa resistencia rota, no Day 1 High obsoleto) - NEW!

**Resultado:** Puedes iterar la estrategia mensualmente usando tus propios datos históricos, y el sistema adapta su agresividad según la estructura diaria real del stock.

---

## 🚀 **Próximos Pasos**

1. Ejecutar sistema por 30-50 trades
2. Correr queries de análisis
3. Identificar patterns ganadores/perdedores
4. Ajustar config.ini basado en data
5. Repetir ciclo mensualmente
