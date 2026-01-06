# VCP STRICT Worker - Guía de Uso

## Fecha de Creación
23 de Diciembre 2025

## Propósito

Worker VCP con **validación ESTRICTA de pendiente VWAP** para evitar entradas en stocks sin acumulación institucional activa.

## Diferencias vs `vcp_smallcap` Worker

| Característica | vcp_smallcap | vcp_strict |
|---------------|--------------|------------|
| **VWAP Slope Requirement** | >= +0.15% (NO permite plano) | **>= +0.10% (OBLIGATORIO positivo)** |
| **Overrides por Calidad** | ✅ Permite overrides si Q>=70 o Blue Sky | ❌ SIN overrides - VWAP es obligatorio |
| **Overrides por Catalyst** | ✅ Relaxa thresholds para catalysts fuertes | ❌ SIN overrides - slope siempre obligatorio |
| **Objetivo** | Capturar setups tempranos con flexibilidad | Solo entradas con acumulación institucional CONFIRMADA |

## ¿Por Qué Este Worker?

### Problema Identificado

En el análisis de TRIB (23/12/2025 17:01):
- Entry: $1.39 @ 17:01
- VWAP: $1.39 (slope: +0.00% - **PLANO**)
- Resultado: Position cerrada en -11.11% por stop loss

**Análisis posterior mostró**:
- VWAP plano = indecisión institucional
- Entry a las 17:01 NO tenía acumulación activa
- A las 18:15 VWAP slope: **-0.41%** (distribución confirmada)

### Regla de Oro

**VWAP slope refleja el flujo institucional**:
- **Slope > +0.10%** → Acumulación activa (COMPRAR)
- **Slope ≈ 0%** → Indecisión institucional (NO OPERAR)
- **Slope < -0.10%** → Distribución activa (VENDER/CORTO)

## Configuración

### config.ini

```ini
[VCP_STRICT_STRATEGY]
# Activar worker
vcp_strict_strategy_enabled = true

# Parámetros VCP
vcp_strict_min_contractions = 2
vcp_strict_min_quality_score = 60.0
vcp_strict_min_price = 1.0
vcp_strict_max_price = 25.0
vcp_strict_min_volume_ratio = 1.0

# VWAP STRICT - Parámetros Clave
vcp_strict_min_vwap_slope_long = 0.10    # +0.10% mínimo para LARGOS
vcp_strict_max_vwap_slope_short = -0.10  # -0.10% máximo para CORTOS
vcp_strict_vwap_slope_lookback = 10      # Ventana de cálculo (minutos)
vcp_strict_allow_vwap_overrides = false  # NO overrides

# Stops
vcp_strict_stop_loss_pct = 5.0
vcp_strict_take_profit_pct = 15.0
vcp_strict_trailing_activation = 8.0
vcp_strict_trailing_distance = 4.0
vcp_strict_max_position_hours = 6.0
```

### Activación

El worker se activará automáticamente si `vcp_strict_strategy_enabled = true`.

## Criterios de Entrada

### 1. Patrón VCP Válido
- ✅ 2+ contracciones decrecientes
- ✅ Volumen declinando en contracciones
- ✅ Pivot detectado (precio cerca del breakout)

### 2. VWAP Validation STRICT (SIN EXCEPCIONES)

```python
# Cálculo de VWAP slope
vwap_slope_pct = ((current_vwap - previous_vwap_10min) / previous_vwap) * 100

# VALIDACIÓN ESTRICTA
if vwap_slope_pct < +0.10%:
    REJECT  # No hay acumulación activa
```

**Rechazos típicos**:
- VWAP slope = +0.00% → "No accumulation (flat VWAP)"
- VWAP slope = -0.15% → "VWAP declining (selling pressure)"
- VWAP slope = +0.05% → "Below minimum +0.10% threshold"

### 3. Precio vs VWAP
- Precio dentro del 2% del VWAP (fixed, sin overrides)
- RECHAZA si precio > 2% arriba (overextended)
- RECHAZA si precio > 2% abajo (debilidad)

### 4. Otros Filtros Estándar
- Quality Score >= 60.0
- Precio: $1.00 - $25.00
- Volumen >= 1.0x
- ODS filters (Balance Day, etc.)
- Intraday structure (no traps)

## Ejemplo de Uso

### Caso 1: TRIB @ 17:01 (RECHAZADO por vcp_strict)

```
17:01:09 - TRIB: VCP pattern detected (1 contraction, 40% completion)
17:01:09 - TRIB: Pivot detected at 95.9% of high
17:01:09 - TRIB: VWAP slope = +0.00%
17:01:09 - ⚪ TRIB: VWAP STRICT validation FAILED - slope +0.00% < minimum +0.10%
17:01:09 - ⚪ TRIB: Entry REJECTED (no active accumulation)
```

**vcp_smallcap** habría RECHAZADO (slope < +0.15%)
**vcp_strict** también RECHAZA (slope < +0.10%)

### Caso 2: Stock con Acumulación Activa (ACEPTADO)

```
11:30:15 - ABC: VCP pattern detected (3 contractions, 80% completion)
11:30:15 - ABC: Pivot detected at 98.5% of high
11:30:15 - ABC: VWAP slope = +0.25% (active accumulation)
11:30:15 - ✅ ABC: VWAP STRICT validation PASSED - slope +0.25% ✅
11:30:15 - ✅ ABC: VCP STRICT ENTRY APPROVED
```

## Logs Importantes

### Entry Logs
```
✅ [SYMBOL]: VWAP STRICT validation PASSED - Price $X.XX near VWAP $Y.YY, slope +Z.ZZ% ✅ (accumulation active)
⚪ [SYMBOL]: VWAP STRICT validation FAILED - VWAP slope +0.05% < minimum +0.10% (need positive accumulation)
```

### Initialization Logs
```
🎯 VCP STRICT Worker configured: contractions>=2, Q>=60.0, price=$1.0-$25.0, vol>=1.0x |
   ⚡ VWAP STRICT: slope>+0.10% for LONG (lookback=10min) |
   Exits: TP=15%, SL=5%, Trail=8%/4%, Max=6h
```

## Cuándo Usar Este Worker

### ✅ Usar vcp_strict Si:
- Quieres evitar falsos breakouts
- Solo operas con institucionales activos
- Prefieres calidad sobre cantidad de trades
- Buscas mejor win rate (menos entries, más selectivos)

### ❌ NO usar vcp_strict Si:
- Quieres capturar runners volátiles tempranos
- Operas smallcaps pre-halt (momentum explosivo)
- Prefieres volumen de trades sobre precisión
- Quieres flexibilidad con catalysts fuertes

## Operativa en CORTO (SHORT Positions)

### ✅ IMPLEMENTADO - Soporta SHORT desde v1.1

El worker **YA soporta operativa en corto** con detección automática basada en VWAP:

#### Criterios SHORT
1. **VWAP slope <= -0.10%** (distribución institucional activa)
2. **Precio <= VWAP + 2%** (debilidad confirmada)
3. **Patrón INVERSO VCP**: Expansiones CRECIENTES (no contracciones)
4. **Pivot inverso**: Breakdown desde expansión, precio cerca de lows

#### Detección Automática de Dirección

El worker determina automáticamente si operar LONG o SHORT:

```python
direction, vwap_slope_pct, current_vwap = _determine_trade_direction(bars, current_price)

if vwap_slope_pct >= +0.10%:
    direction = 'LONG'  # Acumulación activa
elif vwap_slope_pct <= -0.10%:
    direction = 'SHORT'  # Distribución activa
else:
    direction = 'NONE'  # Indecisión (no operar)
```

### Ejemplo SHORT Entry

```
14:30:15 - XYZ: Trade direction = SHORT (VWAP slope -0.35%, VWAP $15.50)
14:30:15 - XYZ: INVERSE VCP SHORT pattern detected - 3 expansions (ranges: ['2.1%', '3.5%', '4.8%'])
14:30:15 - XYZ: SHORT Pivot at 102.5% of low $15.10, declined 3.2% from high $15.75 (⚠️ increasing volume 1.35)
14:30:15 - XYZ: VWAP STRICT validation PASSED - VWAP slope -0.35% <= -0.10% ✅ (distribution)
14:30:15 - ✅ XYZ: VCP STRICT SHORT ENTRY APPROVED - 3 expansions, 102.5% to breakdown
```

### Diferencias LONG vs SHORT

| Aspecto | LONG | SHORT |
|---------|------|-------|
| **Patrón** | Contracciones decrecientes | Expansiones crecientes |
| **VWAP Slope** | >= +0.10% | <= -0.10% |
| **Precio vs VWAP** | Dentro de 2% arriba VWAP | Dentro de 2% abajo VWAP |
| **Pivot** | Recuperación desde low | Breakdown desde high |
| **Volumen Pivot** | Decreciente (dry volume) | Creciente (distribution) |
| **Stop Level** | Support (low) | Resistance (high) |

### Configuración SHORT

```ini
[VCP_STRICT_STRATEGY]
# Habilitar operativa SHORT
vcp_strict_enable_short = true

# Mínimas expansiones para patrón SHORT
vcp_strict_min_expansions = 2

# VWAP slope máximo para SHORT (negativo)
vcp_strict_max_vwap_slope_short = -0.10
```

## Testing

### Test Manual
```bash
# 1. Activar worker en config.ini
vcp_strict_strategy_enabled = true

# 2. Iniciar sistema
python trader_main.py

# 3. Verificar en logs
grep "VCP STRICT" logs/trader.log

# 4. Buscar entries/rejections
grep "vcp_strict.*ENTRY APPROVED\|VWAP STRICT validation FAILED" logs/trader.log
```

### Test con Datos Históricos

Comparar vcp_smallcap vs vcp_strict en mismos setups:
```bash
# Buscar casos donde vcp_smallcap entró pero vcp_strict habría rechazado
grep "vcp_smallcap.*ENTRY APPROVED" trader.log.1 > vcp_smallcap_entries.txt
grep "vcp_strict.*VWAP.*FAILED" trader.log.1 > vcp_strict_rejections.txt
```

## Notas Técnicas

### Cálculo de VWAP Slope

```python
# VWAP Rolling Window (60min por defecto)
recent_bars = bars[-60:]

# VWAP actual
current_vwap = calculate_vwap_from_bars(recent_bars)

# VWAP de hace 10 minutos
bars_10min_ago = recent_bars[:-10]
previous_vwap = calculate_vwap_from_bars(bars_10min_ago)

# Slope
vwap_slope_pct = ((current_vwap - previous_vwap) / previous_vwap) * 100
```

### Tolerancias Fijas (No Adaptive)

A diferencia de `base_worker_logic.validate_vwap_strength()`, este worker NO usa adaptive thresholds:
- Tolerancia precio/VWAP: **2.0%** (fixed)
- Slope mínimo: **+0.10%** (fixed)
- Sin overrides por calidad, catalyst, o día viernes

## Archivo de Código

`strategies/workers/vcp_strict_worker_logic.py`

## Historial de Cambios

### v1.1 - 23/12/2025
- ✅ **SHORT positions IMPLEMENTADO**
- Detección automática de dirección (LONG/SHORT) basada en VWAP slope
- Patrón inverso VCP para SHORT (expansiones crecientes)
- Pivot inverso detection para SHORT entries
- VWAP slope validation bidireccional (>= +0.10% LONG, <= -0.10% SHORT)
- Config actualizado con parámetros SHORT
- Documentación completa con ejemplos SHORT

### v1.0 - 23/12/2025
- Creación inicial del worker
- VWAP slope validation implementado para LONG
- Config agregado a config.ini
- Registro en worker_based_strategy_engine.py
- Estructura preparada para SHORT positions

## Contacto

Para preguntas o mejoras, contactar al desarrollador principal del sistema.
