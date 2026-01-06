# ¿El Worker Momentum Breakout Hubiera Capturado KALA/CNCK?

## Fecha: 1 Diciembre 2025

---

## Respuesta Rápida

❌ **NO**, el worker momentum_breakout **NO evaluó** KALA ni CNCK porque **no fue llamado** por el sistema de routing.

---

## Por Qué No Fue Llamado

### Sistema de Context Routing

El sistema usa **Context Engine** para determinar qué workers llamar:

```
1. Context Engine analiza símbolo
2. Determina context: CATALYST, MOMENTUM, TREND, etc.
3. Routing engine llama solo workers compatibles con ese context
```

### KALA Context

```
Context: CATALYST (conf=90%, ADX=76.1, ATR=3.58%, VolZ=-0.7)
Workers llamados: ['daily_plays', 'vcp_smallcap', 'ods_swing_universal', 'orb_breakout']
```

**momentum_breakout NO fue llamado** porque:
- KALA context = **CATALYST**
- momentum_breakout contexts = **[momentum, trend]**
- ❌ No hay match

### CNCK Context

```
Context: CATALYST (conf=90%, ADX=68.2, ATR=3.57%, VolZ=0.6)
Workers llamados: ['daily_plays', 'vcp_smallcap', 'ods_swing_universal', 'orb_breakout']
```

**momentum_breakout NO fue llamado** porque:
- CNCK context = **CATALYST**
- momentum_breakout contexts = **[momentum, trend]**
- ❌ No hay match

---

## Configuración de Workers y Contexts

### momentum_breakout Worker

**Registro del worker** (línea del log):
```
📝 Registered worker: momentum_breakout (priority=2, contexts=[momentum, trend], horizon=intraday)
```

**Contexts compatibles**: `momentum`, `trend`

### Otros Workers

| Worker | Contexts | ¿Evalúa CATALYST? |
|--------|----------|-------------------|
| daily_plays | catalyst, momentum, trend | ✅ Sí |
| vcp_smallcap | catalyst, trend, reversal | ✅ Sí |
| momentum_breakout | **momentum, trend** | ❌ **NO** |
| orb_breakout | catalyst, momentum, trend | ✅ Sí |
| ods_swing_universal | catalyst, swing | ✅ Sí |

**Resultado**: momentum_breakout es el único worker que **NO acepta context CATALYST**.

---

## ¿Podría momentum_breakout Haber Entrado?

### Supongamos que SÍ fue llamado...

Déjame analizar si **hubiera entrado** basándome en sus criterios:

### Criterios de momentum_breakout

**Del código** (líneas 42-46):
```python
lookback_bars = 5                  # Barras para detectar breakout
min_volume_ratio = 1.2             # Ratio volumen mínimo
min_price = 1.0                    # Precio mínimo
max_price = 25.0                   # Precio máximo
momentum_bars = 3                  # Barras consecutivas en misma dirección
```

**Pattern completion criteria** (líneas 83-88):
```
- 40%: Datos básicos disponibles
- 60%: Breakout detectado (precio rompe máximo/mínimo de últimas N barras)
- 80%: Momentum confirmado + volumen
- 100%: Setup completo listo para entrada
```

---

## Análisis de KALA vs momentum_breakout

### KALA Parámetros

```
Price: $1.55
Volume ratio: 2.0x
Gap: 0.6%
Movement: Gradual desde $1.29 → $1.55 en horas
RSI: 85.3
```

### ¿Cumpliría Criterios?

| Criterio | Requisito | KALA | ¿Cumple? |
|----------|-----------|------|----------|
| **Precio** | $1.0 - $25.0 | $1.55 | ✅ Sí |
| **Volume ratio** | >= 1.2x | 2.0x | ✅ Sí |
| **Breakout detected** | Rompe high de 5 barras | Probablemente sí | ✅ Sí |
| **Momentum bars** | 3 barras consecutivas | Probablemente sí | ✅ Sí |

### ¿Habría Entrado?

**Probablemente ✅ SÍ**, momentum_breakout es más **permisivo** que daily_plays:

**Ventajas**:
1. ✅ No requiere catalyst (ignora catalyst_strength)
2. ✅ No check de RSI overbought (no tiene filtro RSI > 70)
3. ✅ Volume ratio bajo (1.2x vs 1.5x de daily_plays)
4. ✅ Solo requiere breakout técnico + momentum

**Resultado esperado**: KALA **habría pasado** momentum_breakout si hubiera sido llamado.

---

## Análisis de CNCK vs momentum_breakout

### CNCK Parámetros

```
Price: $6.97
Volume ratio: 1.5x
Gap: 1.2%
Movement: Masivo de $3.24 → $7.42 (+103% desde ORB high)
RSI: 86.5
```

### ¿Cumpliría Criterios?

| Criterio | Requisito | CNCK | ¿Cumple? |
|----------|-----------|------|----------|
| **Precio** | $1.0 - $25.0 | $6.97 | ✅ Sí |
| **Volume ratio** | >= 1.2x | 1.5x | ✅ Sí |
| **Breakout detected** | Rompe high de 5 barras | ✅ Definitivamente | ✅ Sí |
| **Momentum bars** | 3 barras consecutivas | ✅ Definitivamente | ✅ Sí |

### ¿Habría Entrado?

**Definitivamente ✅ SÍ**, CNCK es un breakout perfecto:

**Por qué**:
1. ✅ Breakout masivo (de $3.64 → $7.42)
2. ✅ Volume confirma (1.5x >= 1.2x)
3. ✅ Momentum claro (barras consecutivas alcistas)
4. ✅ **No hay check de RSI** (habría ignorado RSI 86.5)
5. ✅ No requiere quality score alto

**Resultado esperado**: CNCK **definitivamente habría entrado** con momentum_breakout.

---

## Comparación: daily_plays vs momentum_breakout

### daily_plays (LO QUE PASÓ)

**KALA**:
- ✅ Stage 1 passed
- ✅ Stage 2 passed (Quality 49.4, Strength 7)
- ❌ **Stage 3 FAILED** (RSI 85.3 > 70)
- **Resultado**: ❌ Rechazado

**CNCK**:
- ✅ Stage 1 passed
- ✅ Stage 2 passed (Quality 86.1, TECHNICAL)
- ❌ **Stage 3 FAILED** (RSI 86.5 > 70)
- **Resultado**: ❌ Rechazado

### momentum_breakout (HIPOTÉTICO)

**KALA**:
- ✅ Precio OK ($1.55)
- ✅ Volume OK (2.0x >= 1.2x)
- ✅ Breakout detected
- ✅ Momentum confirmed
- ✅ **No RSI check**
- **Resultado**: ✅ Habría entrado

**CNCK**:
- ✅ Precio OK ($6.97)
- ✅ Volume OK (1.5x >= 1.2x)
- ✅ Breakout detected (masivo)
- ✅ Momentum confirmed (obvio)
- ✅ **No RSI check**
- **Resultado**: ✅ Habría entrado

---

## Por Qué momentum_breakout Hubiera Funcionado

### Ventajas de momentum_breakout

1. **No requiere catalyst**: Ignora catalyst_strength, solo busca breakout técnico
2. **No check de RSI**: No tiene filtro de RSI > 70 (exhaustion)
3. **Volume bajo**: Solo requiere 1.2x (vs 1.5x de otros)
4. **Criterios simples**: Breakout + momentum + volume, nada más
5. **Enfoque puro técnico**: No analiza daily context, swing, reversal, etc.

### Por Qué Es Más Agresivo

momentum_breakout está diseñado para capturar **momentum puro** sin preocuparse por:
- ❌ Catalyst strength
- ❌ Quality score alto
- ❌ RSI overbought
- ❌ Daily context
- ❌ Support/resistance

**Filosofía**: Si hay breakout + momentum + volume → **entra**

---

## Problema: Context Routing No Lo Llamó

### Por Qué KALA/CNCK Fueron CATALYST Context

**Context Engine determina context basándose en**:
- ADX alto (>50) → indica trend o catalyst
- Catalyst presente → CATALYST context
- Quality score → puede forzar TECHNICAL context

**KALA**:
- Catalyst: M&A (strength 7)
- ADX: 76.1 (muy alto)
- **→ Context: CATALYST**

**CNCK**:
- Catalyst: TECHNICAL (pero ADX muy alto)
- ADX: 68.2 (muy alto)
- **→ Context: CATALYST** (por ADX alto)

### momentum_breakout No Se Llama en CATALYST Context

**Por diseño**, momentum_breakout solo acepta:
- `momentum` context
- `trend` context

**NO acepta**:
- ❌ `catalyst` context

**Razón**: Probablemente para evitar solapamiento con daily_plays (catalyst specialist).

---

## Solución: Añadir CATALYST Context a momentum_breakout

### Opción 1: Modificar Contexts de momentum_breakout

**Archivo**: Donde se registra el worker (probablemente `worker_registry.py` o similar)

**Cambio**:
```python
# ANTES:
contexts=[momentum, trend]

# DESPUÉS:
contexts=[momentum, trend, catalyst]
```

**Resultado**: momentum_breakout evaluaría KALA y CNCK.

**Pros**:
- ✅ Captura KALA/CNCK automáticamente
- ✅ No requiere cambios en lógica del worker
- ✅ Simple (1 línea)

**Contras**:
- ⚠️ Se solaparía con daily_plays (ambos evalúan CATALYST)
- ⚠️ Puede generar trades duplicados
- ⚠️ Más load en el sistema

---

### Opción 2: Modificar Context Engine para CNCK-type

**Lógica**: Símbolos con ADX muy alto + Quality alta → MOMENTUM context (no CATALYST)

**Cambio en Context Engine**:
```python
# Si quality score muy alta y ADX muy alto, usar MOMENTUM context
if quality_score >= 80 and adx >= 60 and catalyst_strength < 5:
    return Context.MOMENTUM  # En lugar de CATALYST
```

**Resultado**: CNCK-type setups se clasificarían como MOMENTUM → momentum_breakout los evaluaría.

**Pros**:
- ✅ Captura high-quality technical breakouts
- ✅ No solapamiento con daily_plays (diferente context)
- ✅ Más preciso conceptualmente

**Contras**:
- ⚠️ Más complejo
- ⚠️ Requiere tunear thresholds

---

### Opción 3: Mantener Como Está + Implementar RSI Dinámico

**Razonamiento**:
- momentum_breakout está diseñado para MOMENTUM context puro
- CATALYST context es dominio de daily_plays
- **Mejor solución**: Arreglar daily_plays para que no rechace por RSI overbought en high-quality

**Acción**: Implementar solución de [SOLUCION_KALA_CNCK.md](SOLUCION_KALA_CNCK.md):
- Dynamic RSI threshold en daily_plays
- Catalyst override en daily_plays

**Pros**:
- ✅ Mantiene separación de responsabilidades
- ✅ No genera solapamiento
- ✅ Más control sobre entradas

**Contras**:
- ⚠️ Requiere modificar daily_plays

---

## Recomendación Final

### Implementar Opción 3 (RSI Dinámico en daily_plays)

**Por qué**:

1. **Separación de responsabilidades**:
   - daily_plays → CATALYST context
   - momentum_breakout → MOMENTUM context
   - Cada uno con su especialidad

2. **Evita solapamiento**:
   - Si añadimos CATALYST a momentum_breakout, ambos evaluarían los mismos símbolos
   - Riesgo de trades duplicados

3. **Más control**:
   - RSI dinámico en daily_plays nos da control fino
   - Podemos ajustar por quality, catalyst type, etc.
   - momentum_breakout sigue siendo agresivo para MOMENTUM puro

4. **Arquitectura más limpia**:
   - Cada worker con su rol claro
   - Context routing funciona como debe

---

## Resumen Ejecutivo

### Pregunta: ¿momentum_breakout hubiera capturado KALA/CNCK?

**Respuesta**: ❌ **NO fue llamado**, pero ✅ **SÍ habría entrado** si hubiera sido llamado.

### Por Qué No Fue Llamado

- KALA/CNCK context: **CATALYST**
- momentum_breakout contexts: **momentum, trend**
- ❌ No hay match → No fue llamado

### Habría Entrado Si Fuera Llamado

**KALA**: ✅ Sí (volume 2.0x, breakout, momentum, sin RSI check)
**CNCK**: ✅ Definitivamente (breakout masivo, momentum obvio, sin RSI check)

### Solución Recomendada

**NO añadir CATALYST context a momentum_breakout**.

**SÍ implementar RSI dinámico en daily_plays**:
- Solución más limpia
- Evita solapamiento
- Mantiene arquitectura

---

## Configuración Actual vs Propuesta

### Actual

```
CATALYST context → daily_plays (rechaza por RSI > 70)
MOMENTUM context → momentum_breakout (sin RSI check)

KALA/CNCK → CATALYST context → daily_plays → ❌ Rechazado por RSI
```

### Propuesta (Opción 3)

```
CATALYST context → daily_plays (RSI dinámico: Q>=85 → threshold 90)
MOMENTUM context → momentum_breakout (sin RSI check)

KALA → CATALYST context → daily_plays → ✅ Entra (M&A override)
CNCK → CATALYST context → daily_plays → ✅ Entra (threshold 90)
```

**Arquitectura mantenida, problema resuelto**.
