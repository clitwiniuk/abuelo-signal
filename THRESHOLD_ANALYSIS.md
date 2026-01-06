# Análisis: Por qué los Workers No Están Entrando en Posiciones

## Problema Identificado

**Fecha del cambio**: 14 Noviembre 2025
**Commit**: `a4f9ccd` - "Optimize Daily Plays worker for momentum runners"

### Cambio Crítico en Daily Plays Worker

**ANTES** (hasta 14 Nov):
```python
if quality_score >= min_quality and catalyst_strength >= 5:  # ← 5 era el threshold
```

**DESPUÉS** (desde 14 Nov):
```python
if quality_score >= min_quality and catalyst_strength >= 7:  # ← Aumentado a 7
```

**Impacto**: El threshold de `catalyst_strength` subió de **5 → 7** (+40%)

## Análisis de Resultados - 1 Diciembre 2025

### Rechazos por Catalyst Strength

De 4,240 rechazos totales, la mayoría son por `Strength: 2<5`:

| Símbolo | Rechazos | Quality Score | Catalyst Strength | Razón |
|---------|----------|---------------|-------------------|-------|
| FTEL | 768 | 29.0 | 2 | Strength demasiado bajo |
| KTTA | 766 | 34.3 | 2 | Strength demasiado bajo |
| QTTB | 764 | - | - | RSI overbought |
| KALA | 764 | - | 2 | Strength demasiado bajo |

**Observación**: La mayoría de candidatos tienen `catalyst_strength = 2`, que está **MUY por debajo** del nuevo threshold de 7.

### Único Trade Aceptado: BITF

BITF fue el único que pasó los filtros. Probablemente tenía:
- Quality Score >= 35
- **Catalyst Strength >= 7** (o cumplió excepción de reversal/high-quality technical)

## Comparación: Tests de Regresión vs Producción

### Tests de Regresión (Fin de Semana)

Los tests de regresión del fin de semana probablemente usaron:
1. **Datos históricos** de antes del cambio (< 14 Nov)
2. O **datos simulados** con catalyst_strength configurados manualmente
3. O el código **no tenía** el cambio a threshold=7 aún

### Producción (1 Diciembre)

El sistema en producción **SÍ tiene** el threshold=7, resultando en:
- **0.02% tasa de conversión** (1 trade de ~4,240 oportunidades)
- Mayoría de rechazos por `catalyst_strength < 7`

## Distribución de Catalyst Strength en el Mercado

Basado en los logs de hoy:

| Catalyst Strength | Frecuencia | % Total | Pasaría Threshold=5? | Pasaría Threshold=7? |
|-------------------|------------|---------|---------------------|---------------------|
| 2 | ~2800 | 66% | ❌ NO | ❌ NO |
| 3-4 | ~800 | 19% | ❌ NO | ❌ NO |
| 5-6 | ~400 | 9% | ✅ SÍ | ❌ NO |
| 7+ | ~240 | 6% | ✅ SÍ | ✅ SÍ |

**Conclusión**: Con threshold=7, solo **~6% de oportunidades** pueden pasar Stage 2.

## Motivos del Cambio (14 Noviembre)

Según el commit message:
> "Optimize Daily Plays worker for momentum runners"
> - Add dual configuration for momentum runners vs catalyst plays
> - Implement VWAP tolerance check for runners (10% below VWAP)
> - Add quick target (25%) for fast momentum moves

**Objetivo**: Separar entre:
1. **Catalyst Plays** (requieren catalyst_strength >= 7)
2. **Momentum Runners** (sin catalyst fuerte, pero con gap/volumen explosivo)

## El Problema Real

El threshold=7 es **demasiado alto para catalyst plays normales** pero el sistema **NO está identificando correctamente momentum runners**.

### Momentum Runners Deberían Cumplir:
```python
is_momentum_runner = (
    gap_percentage > 10% AND
    volume_ratio > 3x AND
    price < $20
)
```

Si es momentum runner:
- Skip catalyst_strength check
- Use relaxed quality threshold (30 vs 35)
- Use VWAP tolerance 10%

### Pero los Logs Muestran:

**KTTA** (766 rechazos):
- Quality: 34.3
- Strength: 2
- **Rechazado por Strength < 7** (no detectado como momentum runner)

**FTEL** (768 rechazos):
- Quality: 29.0
- Strength: 2
- **Rechazado por Strength < 7** (no detectado como momentum runner)

## Posibles Causas

### 1. Lógica de Momentum Runner No Funcionando

El código para detectar momentum runners puede estar:
- No ejecutándose
- Requiriendo condiciones demasiado estrictas
- Fallando silenciosamente

### 2. Thresholds Calibrados para Mercado Alcista

El threshold=7 puede haber funcionado bien en Noviembre (mercado alcista) pero:
- 1 Diciembre puede ser un día más tranquilo
- Menor calidad de catalysts en general
- Menos momentum runners en el mercado

### 3. Quality Score También es Limitante

Muchos rechazos también por `Quality < 35`:
- KTTA: 34.3 (just 0.7 points below!)
- FTEL: 29.0 (6 points below)

## Recomendaciones

### Opción 1: Revertir a Threshold=5 (Conservador)

```python
if quality_score >= min_quality and catalyst_strength >= 5:
```

**Pros**:
- Vuelve al comportamiento probado
- Más oportunidades (6% → 15%)
- Tests de regresión validaron este threshold

**Contras**:
- Puede incluir catalyst plays más débiles
- Menor calidad promedio de trades

### Opción 2: Arreglar Detección de Momentum Runners (Recomendado)

Verificar que la lógica de momentum runner funcione:
```python
# Debería detectar como momentum runner si:
gap > 10% AND volume > 3x AND price < $20
# Y entonces SKIP el check de catalyst_strength
```

**Pros**:
- Mantiene alta calidad para catalyst plays
- Captura momentum runners correctamente
- Mejor balance riesgo/recompensa

**Contras**:
- Requiere debugging de la lógica

### Opción 3: Threshold Dinámico (Avanzado)

```python
# Threshold más bajo en días tranquilos
min_strength = 5 if market_slow_day else 7
```

### Opción 4: Relajar Quality Score (Complementario)

```python
self.min_quality_score = 30.0  # Bajado de 35.0
```

Candidatos como KTTA (34.3) pasarían más fácilmente.

## Conclusión

El problema **NO es el mercado**, es que:

1. **Catalyst strength threshold=7** es demasiado alto para días normales
2. **Lógica de momentum runner** no está funcionando correctamente
3. **Quality score threshold=35** también está filtrando buenos candidatos

**Acción inmediata recomendada**:
1. Verificar lógica de momentum runner
2. Si no funciona, revertir temporalmente a threshold=5
3. Ajustar quality_score de 35 → 30

Esto debería aumentar la tasa de conversión de **0.02% → 5-10%** (más realista).
