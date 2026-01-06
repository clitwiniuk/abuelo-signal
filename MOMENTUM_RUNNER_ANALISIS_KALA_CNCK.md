# ¿El Momentum Runner Hubiera Capturado KALA y CNCK?

## Fecha: 1 Diciembre 2025

---

## Criterios del Momentum Runner

**Del fix implementado** ([MOMENTUM_RUNNER_FIX.md](MOMENTUM_RUNNER_FIX.md)):

```python
is_momentum_runner = (
    gap_percentage >= 10.0 AND      # Gap >= 10%
    volume_ratio >= 3.0 AND          # Volume >= 3x
    price <= 20.0                    # Price < $20
)
```

**Si es momentum runner**:
- ✅ Skip catalyst_strength check (no requiere catalyst)
- ✅ Min quality score: 30 (relajado vs 35 normal)
- ✅ No confirmations required (entrada inmediata)
- ✅ Skip daily checks (para velocidad)

---

## Análisis de KALA

### Parámetros Reales de KALA

**Primera detección (16:43)**:
```
Gap: 0.3%
Volume: 2.0x
Price: $1.29
Quality: 49.4
Catalyst: M&A
Catalyst Strength: 7
```

**Segunda detección (17:40)**:
```
Gap: 0.6%
Volume: 2.0x
Price: $1.55
Quality: 49.4
Catalyst: M&A
Catalyst Strength: 7
RSI: 85.3
```

### ¿Cumple Criterios de Momentum Runner?

| Criterio | Requisito | KALA | ¿Cumple? |
|----------|-----------|------|----------|
| Gap | >= 10% | 0.3-0.6% | ❌ **NO** |
| Volume | >= 3x | 2.0x | ❌ **NO** |
| Price | <= $20 | $1.29-$1.55 | ✅ Sí |

**Resultado**: ❌ **NO**, KALA NO hubiera sido detectado como momentum runner.

**Razón**: Gap de solo 0.6% (necesita 10%+) y volumen 2.0x (necesita 3x+).

---

## Análisis de CNCK

### Parámetros Reales de CNCK

**Detección (20:40)**:
```
Gap: 1.2%
Volume: 1.5x
Price: $6.97
Quality: 86.1
Catalyst: TECHNICAL
Catalyst Strength: 0
RSI: 86.5
```

### ¿Cumple Criterios de Momentum Runner?

| Criterio | Requisito | CNCK | ¿Cumple? |
|----------|-----------|------|----------|
| Gap | >= 10% | 1.2% | ❌ **NO** |
| Volume | >= 3x | 1.5x | ❌ **NO** |
| Price | <= $20 | $6.97 | ✅ Sí |

**Resultado**: ❌ **NO**, CNCK NO hubiera sido detectado como momentum runner.

**Razón**: Gap de solo 1.2% (necesita 10%+) y volumen 1.5x (necesita 3x+).

---

## Conclusión: Momentum Runner NO los Hubiera Capturado

### KALA
- ❌ Gap: 0.6% vs 10% requerido (falta 9.4%)
- ❌ Volume: 2.0x vs 3.0x requerido (falta 1.0x)
- **NO es momentum runner**

### CNCK
- ❌ Gap: 1.2% vs 10% requerido (falta 8.8%)
- ❌ Volume: 1.5x vs 3.0x requerido (falta 1.5x)
- **NO es momentum runner**

---

## Tipo de Setups que Son

### KALA es un **CATALYST PLAY**
- **Catalyst**: M&A (muy fuerte)
- **Catalyst Strength**: 7 (alto)
- **Gap**: Bajo (0.6%)
- **Volume**: Moderado (2.0x)
- **Movimiento**: Catalyst-driven, no momentum explosivo

**Clasificación**: CATALYST mode (strength >= 5 ✅)

### CNCK es un **TECHNICAL BREAKOUT**
- **Catalyst**: TECHNICAL (no catalyst específico)
- **Quality**: 86.1 (excepcional técnico)
- **Gap**: Bajo (1.2%)
- **Volume**: Bajo (1.5x)
- **Movimiento**: Breakout técnico gradual (de $3.24 → $7.42 en 4.5 horas)

**Clasificación**: TECHNICAL mode (quality >= 75 ✅)

---

## ¿Qué Tipo de Setups SÍ Captura el Momentum Runner?

### Ejemplo: FLYE (No Detectado, pero sería Momentum Runner)

**FLYE - 1 Diciembre**:
```
Gap: ~300%+ (de $4.48 apertura)
Volume: ~9M (estimado 5-10x volumen promedio)
Price: $4.48 → $18.31
Movement: De $4.48 → $18.31 (+308%) en pocas horas
```

### ¿Cumpliría Criterios?

| Criterio | Requisito | FLYE | ¿Cumple? |
|----------|-----------|------|----------|
| Gap | >= 10% | ~300% | ✅ **SÍ** |
| Volume | >= 3x | ~5-10x | ✅ **SÍ** |
| Price | <= $20 | $4.48-$18 | ✅ **Sí** |

**Resultado**: ✅ **SÍ**, FLYE sería momentum runner.

**Modo usado**: RUNNER (quality >= 30, no catalyst required)

---

## Comparación: 3 Tipos de Setups

| Tipo | Ejemplo | Gap | Volume | Catalyst | Quality | Modo |
|------|---------|-----|--------|----------|---------|------|
| **Momentum Runner** | FLYE | 300%+ | 5-10x | Opcional | 28+ | RUNNER |
| **Catalyst Play** | KALA | 0.6% | 2.0x | M&A (7) | 49.4 | CATALYST |
| **Technical Breakout** | CNCK | 1.2% | 1.5x | None | 86.1 | TECHNICAL |

---

## Por Qué el Momentum Runner NO Ayuda con KALA/CNCK

### Momentum Runner Está Diseñado Para

**Movers explosivos tipo FLYE**:
- Gap masivo (>10%) desde premarket
- Volumen explosivo (>3x) confirmando momentum
- Movimiento vertical rápido
- No requiere catalyst (el momentum es el catalyst)

**Características**:
- Detección temprana en apertura (gap + volume)
- Entrada rápida (0 confirmations)
- Target rápido (25% quick target)
- Alto riesgo/alto reward

### KALA y CNCK Son Diferentes

**KALA** (Catalyst Play):
- Gap bajo (0.6%)
- Volume moderado (2.0x)
- **Necesita catalyst fuerte** (M&A) para justificar entrada
- Movimiento gradual catalyst-driven

**CNCK** (Technical Breakout):
- Gap bajo (1.2%)
- Volume bajo (1.5x)
- **Necesita quality excepcional** (86.1) para justificar entrada
- Movimiento gradual técnico (4.5 horas de $3 → $7)

---

## Solución Real para KALA/CNCK

### No es Momentum Runner, es RSI Threshold

El problema con KALA y CNCK no es que no sean momentum runners, es que:

**Ambos fueron rechazados por RSI > 70**:
- KALA: RSI 85.3 > 70 ❌
- CNCK: RSI 86.5 > 70 ❌

**La solución correcta es**:
1. ✅ **Dynamic RSI threshold** (Q >= 85 → threshold 90)
2. ✅ **Catalyst override** (M&A strength 7 → ignore RSI)

**NO cambiar momentum runner criteria**, porque:
- Momentum runner está bien calibrado para FLYE-type movers
- Relajar a gap 1% + vol 1.5x capturaría demasiados falsos positivos
- KALA/CNCK no son momentum runners por naturaleza

---

## ¿Deberíamos Relajar Momentum Runner Criteria?

### Opción: Relajar a Gap >= 5%, Volume >= 2x

**Pros**:
- ✅ Capturaría KALA (gap 0.6% → No, sigue sin cumplir)
- ✅ Capturaría CNCK (gap 1.2% → No, sigue sin cumplir)

**Contras**:
- ❌ KALA/CNCK **TODAVÍA no cumplirían** (gaps demasiado bajos)
- ❌ Capturaría muchos falsos positivos
- ❌ Diluiría el concepto de "momentum runner"

**Resultado**: ❌ **NO tiene sentido** relajar momentum runner para KALA/CNCK.

---

## Configuración Óptima de Momentum Runner

### Mantener Criteria Actual (Correcto)

```python
# Momentum Runner criteria (NO cambiar)
runner_min_gap_pct = 10.0       # Correcto para movers explosivos
runner_min_volume_ratio = 3.0   # Correcto para confirmar momentum
runner_max_price = 20.0         # Correcto para smallcaps
```

**Por qué**:
- Gap 10% + Vol 3x identifica **movers excepcionales** como FLYE
- Estos movers justifican entrada rápida sin catalyst
- Reducir thresholds capturaría ruido, no señal

### Añadir Otros Modos (Complementario)

En lugar de relajar momentum runner, tener **3 modos independientes**:

1. **RUNNER Mode** (Gap >= 10%, Vol >= 3x)
   - Para: FLYE, movers explosivos
   - Quality: >= 30 (relajado)
   - RSI: Skip check (momentum supera técnico)

2. **CATALYST Mode** (Catalyst strength >= 5)
   - Para: KALA, M&A, Earnings
   - Quality: >= 35 (normal)
   - RSI: Override si catalyst >= 7 + M&A/FDA/Earnings

3. **TECHNICAL Mode** (Quality >= 75, no catalyst)
   - Para: CNCK, breakouts técnicos
   - Quality: >= 75 (alto)
   - RSI: Threshold dinámico (Q >= 85 → 90)

---

## Resumen Final

### Pregunta: ¿El Momentum Runner hubiera capturado KALA/CNCK?

**Respuesta**: ❌ **NO**

**Razón**:
- KALA: Gap 0.6% vs 10% requerido, Vol 2.0x vs 3.0x requerido
- CNCK: Gap 1.2% vs 10% requerido, Vol 1.5x vs 3.0x requerido

### KALA y CNCK NO son Momentum Runners

Son **setups diferentes** que requieren **solución diferente**:

| Setup Type | Ejemplo | Solución Correcta |
|------------|---------|-------------------|
| Momentum Runner | FLYE | ✅ Ya implementado (gap 10%, vol 3x) |
| Catalyst Play | KALA | ✅ Catalyst override (M&A → ignore RSI) |
| Technical Breakout | CNCK | ✅ Dynamic RSI threshold (Q 86 → threshold 90) |

### Acción Recomendada

1. ✅ **Mantener momentum runner criteria** (10%, 3x) para FLYE-type
2. ✅ **Implementar dynamic RSI threshold** para CNCK-type (SOLUCIÓN_KALA_CNCK.md)
3. ✅ **Implementar catalyst override** para KALA-type (SOLUCIÓN_KALA_CNCK.md)

**NO relajar momentum runner criteria**, porque no es el problema.

El problema es **RSI threshold fijo en 70**, no la falta de momentum runner detection.
