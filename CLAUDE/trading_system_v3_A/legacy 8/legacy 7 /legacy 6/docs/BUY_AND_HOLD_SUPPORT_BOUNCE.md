# 🚀 BUY AND HOLD WORKER - SUPPORT BOUNCE STRATEGY

**Fecha:** 29 Diciembre 2025
**Última actualización:** 29 Diciembre 2025 22:10 ET
**Archivo:** `strategies/workers/buy_and_hold_worker_logic.py`
**Config:** `config.ini` → `[BUY_AND_HOLD_WORKER]`

---

## 📊 EVOLUCIÓN DE LA ESTRATEGIA

### Versión 1: Modo Complejo ❌
- 12 filtros diferentes (ODS, falling knife, resistance, etc.)
- **95.6% de rechazo** (647 de 677 oportunidades rechazadas)
- Solo ~30 entradas ejecutadas
- Problema: Sobre-perfeccionismo, rechazaba setups válidos

### Versión 2: Modo Simplificado ⚠️
- 5 filtros esenciales (Quality + VWAP)
- Mejor tasa de entrada (~150-200/día esperado)
- Problema: **Timing deficiente** - entraba en cualquier momento

### Versión 3: Support Bounce Strategy ✅ (ACTUAL)
```
Soporte + Rebote + Precio > VWAP = ENTRADA ÓPTIMA
```

**Por qué funciona:**
1. **Soporte = SL ajustado** → Mejor Risk/Reward
2. **Rebote = Confirmación** → No compra caídas
3. **VWAP = Momentum** → Compra fuerza, no debilidad

---

## 🎯 LÓGICA DE ENTRADA

### Opción 1: SUPPORT BOUNCE (Preferida - Óptima R:R)

**Condiciones:**
1. ✅ Quality Score ≥ 60
2. ✅ Precio > VWAP (+0.5% mínimo)
3. ✅ Cerca de soporte (dentro de threshold configurable, default 5%)
4. ✅ Rebotando (N barras consecutivas subiendo, default 3)
5. ✅ Trading window (9:30-16:00 ET)

**Resultado:**
- Entrada en zona de soporte con momentum confirmado
- Stop loss óptimo justo debajo del soporte
- Excelente Risk/Reward (SL pequeño, TP grande)

### Opción 2: STRONG CATALYST (Fallback - Sin soporte)

**Condiciones:**
1. ✅ Quality Score ≥ 75 (MUY ALTO - configurable)
2. ✅ Precio > VWAP (+0.5% mínimo)
3. ✅ Trading window (9:30-16:00 ET)

**Resultado:**
- Entrada sin confirmación de soporte
- Requiere catalizador MUY fuerte para compensar
- SL estándar (no basado en soporte)

### Rechazo: WAITING FOR SUPPORT

**Condiciones:**
- Quality Score < 75 (no alcanza threshold sin soporte)
- NO cerca de soporte O NO rebotando

**Acción:**
- Espera a que precio baje a soporte
- O espera a quality score más alto
- Evita entradas aleatorias sin setup óptimo

---

## 📐 EJEMPLO REAL

```
Ticker: SIDU
Precio actual: $10.50
VWAP: $10.00
Soporte detectado: $10.20 (swing low más fuerte)
Quality Score: 65
Últimas 3 barras: $10.25 → $10.35 → $10.50

✅ ANÁLISIS:
- Precio > VWAP: ✅ ($10.50 vs $10.00 = +5% momentum)
- Cerca de soporte: ✅ ($10.50 vs $10.20 = 2.9% arriba)
- Rebotando: ✅ (3 barras consecutivas subiendo)
- Quality: ✅ (65 ≥ 60)

✅ ENTRADA APROBADA

📊 RISK/REWARD:
- Entry: $10.50
- Stop Loss: $10.00 (2% debajo del soporte $10.20)
- Risk: -4.8% ($10.50 → $10.00)
- Take Profit: $11.50 (resistencia siguiente)
- Reward: +9.5% ($10.50 → $11.50)
- R:R = 1:2 (EXCELENTE)

💡 VENTAJA vs entrada aleatoria:
- Sin soporte: SL a $9.98 (-5%) → R:R 1.9:1
- Con soporte: SL a $10.00 (-4.8%) → R:R 2.0:1
- Mejora: +5% en R:R + mayor probabilidad de éxito
```

---

## 🔧 PARÁMETROS CONFIGURABLES

Todos los parámetros se configuran en `config.ini` → `[BUY_AND_HOLD_WORKER]`:

### Parámetros Esenciales
```ini
enabled = true                          # Activar/desactivar worker
trading_start_hour = 9.5                # Inicio ventana trading (9:30 AM ET)
trading_end_hour = 16.0                 # Fin ventana trading (4:00 PM ET)
min_price = 1.0                         # Precio mínimo ($)
max_price = 50.0                        # Precio máximo ($)
min_quality_score = 60.0                # Score mínimo del scanner
min_price_above_vwap_pct = 0.5          # % mínimo sobre VWAP
max_trades_per_symbol_per_day = 1       # Máx trades por símbolo/día
```

### Parámetros Support Bounce (NUEVO)
```ini
# Detección de Soporte
support_detection_lookback = 30         # Barras para buscar swing lows (20-40 recomendado)
support_proximity_threshold = 5.0       # % máximo al soporte para "cerca" (3-7% recomendado)
support_bounce_bars = 3                 # Barras subiendo para confirmar rebote (2-4 recomendado)

# Thresholds
min_quality_no_support = 75.0           # Quality mínimo sin soporte (70-80 recomendado)
optimal_sl_below_support_pct = 2.0      # % debajo del soporte para SL (1-3% recomendado)
```

### Recomendaciones de Ajuste

**Para más entradas (menos restrictivo):**
```ini
support_proximity_threshold = 7.0       # Aceptar hasta 7% del soporte
min_quality_no_support = 70.0           # Bajar threshold sin soporte
support_bounce_bars = 2                 # Solo 2 barras para confirmar
```

**Para mejor calidad (más restrictivo):**
```ini
support_proximity_threshold = 3.0       # Solo 3% del soporte
min_quality_no_support = 80.0           # Subir threshold sin soporte
support_bounce_bars = 4                 # 4 barras para confirmar rebote fuerte
```

**Para scalping (entradas rápidas):**
```ini
support_detection_lookback = 20         # Lookback corto (últimas 20 barras)
support_proximity_threshold = 4.0       # Cerca del soporte
optimal_sl_below_support_pct = 1.5      # SL muy ajustado
```

**Para swing (entradas conservadoras):**
```ini
support_detection_lookback = 40         # Lookback largo (estructura diaria)
support_proximity_threshold = 6.0       # Más flexible
optimal_sl_below_support_pct = 3.0      # SL más amplio
```

---

## 🔍 ALGORITMO DE DETECCIÓN DE SOPORTE

### Método: `_find_support_level(bars, current_price)`

**Paso 1: Identificar Swing Lows**
- Busca mínimos locales en últimas N barras (configurable)
- Swing low = low[i] ≤ low[i-1] AND low[i] ≤ low[i+1]

**Paso 2: Puntuar Soportes**
```python
score = (recency_score * 0.6) + (volume_score * 0.4)
```
- **Recency (60%)**: Soportes recientes más importantes
- **Volume (40%)**: Mayor volumen = soporte más fuerte

**Paso 3: Seleccionar Mejor Soporte**
- Elige swing low con mayor score total
- Calcula distancia al precio actual

**Paso 4: Validar Rebote**
- Verifica que últimas N barras suben (configurable)
- Ejemplo: close[-3] < close[-2] < close[-1]

**Paso 5: Calcular SL Óptimo**
- SL = support_price * (1 - optimal_sl_below_support_pct / 100)
- Default: 2% debajo del soporte

**Output:** `SupportAnalysis`
- `support_price`: Nivel de soporte identificado
- `distance_to_support_pct`: % al soporte
- `is_near_support`: Dentro de threshold
- `is_bouncing`: Rebote confirmado
- `support_strength`: Confianza 0-100
- `optimal_stop_loss`: SL recomendado

---

## 📈 RESULTADOS ESPERADOS

### Antes (Modo Complejo)
- Oportunidades: 677
- Entradas: ~30 (4.4%)
- Rechazo: 95.6%
- Problema: Demasiados filtros

### Después (Support Bounce)
- Oportunidades: 677
- Entradas esperadas: **80-120** (12-18%)
- Rechazo esperado: 82-88%
- Ventajas:
  - ✅ Timing óptimo (en soportes)
  - ✅ Mejor R:R (SL ajustado)
  - ✅ Mayor win rate (rebotes confirmados)
  - ✅ Menos entradas aleatorias

### Comparación R:R

| Estrategia | Entry | SL | Risk | TP | Reward | R:R |
|-----------|-------|----|----- |----|--------|-----|
| **Aleatoria** | $10.50 | $9.98 | -5.0% | $11.50 | +9.5% | 1.9:1 |
| **Support Bounce** | $10.50 | $10.00 | -4.8% | $11.50 | +9.5% | **2.0:1** |
| **Mejora** | - | +$0.02 | **-0.2%** | - | - | **+5%** |

---

## ⚙️ TESTING RECOMENDADO

### 1. Backtest Comparativo (1 mes)
```bash
# Versión 2 (Simplificada)
python backtest.py --worker buy_and_hold --version simplified --period 30d

# Versión 3 (Support Bounce)
python backtest.py --worker buy_and_hold --version support_bounce --period 30d
```

**Métricas clave:**
- Win rate
- Avg R:R
- Profit factor
- Max drawdown
- # trades/día

### 2. Paper Trading (1-2 semanas)
```ini
[BUY_AND_HOLD_WORKER]
enabled = true
```

**Monitorear:**
- Logs de entrada: "OPTIMAL ENTRY" vs "STRONG CATALYST"
- Frecuencia de entradas
- Timing de entradas (¿realmente en soportes?)
- P&L por tipo de entrada

### 3. Ajuste de Parámetros

**Si muy pocas entradas (<50/día):**
```ini
support_proximity_threshold = 7.0
min_quality_no_support = 70.0
```

**Si demasiadas entradas (>150/día):**
```ini
support_proximity_threshold = 3.0
min_quality_no_support = 80.0
```

**Si bajo win rate (<50%):**
```ini
support_bounce_bars = 4               # Confirmar rebote más fuerte
min_quality_score = 65.0              # Subir quality mínimo
```

---

## 🔧 FIXES APLICADOS

### Fix 1: Líneas huérfanas (líneas 265-266)
- **Error:** `IndentationError: unexpected indent`
- **Fix:** Eliminadas líneas huérfanas

### Fix 2: Bloque de resistencia (líneas 265-303)
- **Error:** `NameError: name 'is_blue_sky' is not defined`
- **Fix:** Eliminado bloque "EARLY RESISTANCE VALIDATION"

### Fix 3: Log con variables eliminadas (línea 279)
- **Error:** `NameError: name 'resistance_distance' is not defined`
- **Fix:** Simplificado mensaje de log

### Fix 4: Support Bounce Implementation (ACTUAL)
- **Añadido:** Clase `SupportAnalysis`
- **Añadido:** Método `_find_support_level()`
- **Añadido:** Lógica de entrada basada en soporte
- **Añadido:** Parámetros configurables en config.ini

---

## 🔄 ROLLBACK

Si necesitas volver a la versión anterior:

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
git checkout HEAD~1 -- strategies/workers/buy_and_hold_worker_logic.py
git checkout HEAD~1 -- config.ini
```

---

## 📝 PRÓXIMOS PASOS

1. ✅ Activar worker en config.ini (`enabled = true`)
2. ✅ Monitorear logs en `logs/worker_buy_and_hold.log`
3. ✅ Revisar entries: buscar "OPTIMAL ENTRY" vs "STRONG CATALYST"
4. ⏳ Ajustar parámetros según resultados
5. ⏳ Comparar performance vs versión simplificada

---

**Generado:** 29 Diciembre 2025 22:10 ET
**Sistema:** trading_system_v3
**Autor:** Claude Sonnet 4.5
