# Análisis de Workers - 1 Diciembre 2025

## Resumen Ejecutivo

**Trades Ejecutados Hoy**: 2
- ❌ **ABVE**: SELL 50 shares @ $2.79 (cierre de posición perdedora: -$12.01)
- ✅ **BITF**: BUY 59 shares @ $3.35 (nueva entrada)

**Oportunidades Rechazadas**: 4,240 rechazos totales

## Workers Activos

| Worker | Rechazos | Status |
|--------|----------|--------|
| orb_breakout | 964 | ✅ Funcionando |
| vcp_smallcap | 963 | ✅ Funcionando |
| ods_swing_universal | 963 | ✅ Funcionando |
| daily_plays | 936 | ⚠️ Errores detectados |
| momentum_breakout | ? | ⚠️ No actualizado desde 15:06 |

## Problemas Identificados

### 1. Daily Plays Worker - Error Crítico

```
ERROR - ❌ Error getting price for BITF: 'NoneType' object has no attribute 'is_price_fresh'
WARNING - ⚠️ BITF: Invalid price 0.0
```

**Impacto**: El worker no puede obtener precios válidos para algunos símbolos.

### 2. Momentum Breakout Worker

**Última actualización**: 2025-12-01 15:06 (9:06 AM ET)
**Status**: ⚠️ Posiblemente detenido o no recibió oportunidades

### 3. Filtros Demasiado Restrictivos

#### Símbolos Más Rechazados:
- **FTEL**: 768 rechazos
- **KTTA**: 766 rechazos
- **QTTB**: 764 rechazos
- **KALA**: 764 rechazos

#### Motivos Principales de Rechazo:

**Stage 2 Failures (Quality < 35 OR Strength < 5)**:
- Quality scores típicos: 21-34 (justo por debajo del umbral de 35)
- Strength scores: 2 (muy por debajo del umbral de 5)

**Stage 3 Failures (Daily Context)**:
- Daily RSI overbought (>70) - señal de exhaustion

**VWAP Rejections**:
- Precio más de 2.5-3.5% por debajo de VWAP
- VWAP en declive (presión vendedora)

## Análisis Detallado por Símbolo

### QTTB (764 rechazos)
```
❌ Stage 3 FAILED - Daily RSI overbought: 78.6 > 70 (exhaustion risk)
❌ VWAP validation failed - Price $4.27 more than 3.5% below VWAP $4.49
❌ VWAP declining (-0.27% in last 10min) - selling pressure
```

**Problema**: Símbolo en territorio de sobre-compra con precio cayendo por debajo de VWAP.

### KALA (764 rechazos)
```
❌ REJECTED by VWAP filter - Price $1.60 more than 2.5% below VWAP $1.76
```

**Problema**: Precio consistentemente por debajo de VWAP (mínimo requerido: $1.71).

### KTTA (766 rechazos)
```
❌ Stage 2 FAILED (25%) - Quality: 34.3<35.0 OR Strength: 2<5
```

**Problema**: Quality score de 34.3 (muy cerca del umbral 35) pero Strength de solo 2.

### FTEL (768 rechazos)
```
❌ Stage 2 FAILED (25%) - Quality: 29.0<35.0 OR Strength: 2<5
```

**Problema**: Quality score de 29 y Strength de 2.

### NWL (128 rechazos)
```
❌ Stage 2 FAILED (25%) - Quality: 21.5<35.0 OR Strength: 2<5
```

**Problema**: Quality y Strength muy bajos.

### BITF (48 rechazos, 1 ACEPTADO ✅)

**Único símbolo que pasó los filtros**:
- Comprado a las 14:53 ET @ $3.35
- 59 shares = $197.07 de capital usado
- Worker: Daily Plays
- Status actual: -$4.30 unrealized PNL

## Conclusiones

### Problemas Sistémicos

1. **Filtros Demasiado Estrictos**:
   - Quality threshold: 35 (muchos candidatos en 28-34)
   - Strength threshold: 5 (candidatos típicos en 2)
   - VWAP: 2.5-3.5% tolerance muy ajustado para volátiles

2. **Error de Pricing en Daily Plays**:
   - `'NoneType' object has no attribute 'is_price_fresh'`
   - Necesita debugging del sistema de precios

3. **Momentum Breakout Worker**:
   - No se actualizó desde 9:06 AM ET
   - Posiblemente no está recibiendo oportunidades o está detenido

### Impacto en Trading

**Solo 1 trade nuevo de ~8 símbolos detectados = 12.5% conversion rate**

Esto es extremadamente bajo para un día de mercado activo.

### Oportunidades Perdidas

Basado en el análisis de FLYE (no detectado):
- +308% move desde $4.48 → $18.31
- 9M volumen
- No detectado por IBKR scanner (posiblemente filtros internos)

## Recomendaciones

1. **Ajustar Quality Threshold**: Reducir de 35 → 30
2. **Ajustar Strength Threshold**: Reducir de 5 → 3
3. **VWAP Tolerance**: Aumentar a 5% para intraday momentum
4. **Debuggear Daily Plays**: Arreglar error de pricing
5. **Verificar Momentum Breakout**: Por qué no se actualiza
6. **Añadir Scanner Alternativo**: Para capturar movers extremos como FLYE

## Símbolos del Día (Para Referencia)

Scanner detectó estos símbolos recurrentemente:
- QTTB, KALA, FTEL, KTTA, NFE, IRBT, NWL, BITF, WBUY, CNEY

De estos, **solo BITF** cumplió todos los criterios.
