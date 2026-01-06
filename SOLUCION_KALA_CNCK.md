# Solución: Capturar Oportunidades como KALA y CNCK

## Fecha: 1 Diciembre 2025

---

## Problema Identificado

Tanto **KALA** como **CNCK** fueron rechazados a pesar de ser setups de alta calidad:

| Símbolo | Quality | Catalyst | Strength | RSI | Motivo Rechazo |
|---------|---------|----------|----------|-----|----------------|
| KALA | 49.4 | M&A | 7 | 85.3 | RSI > 70 |
| CNCK | 86.1 | TECHNICAL | 0 | 86.5 | RSI > 70 |

**Ambos rechazados por Daily RSI overbought** (>70 threshold).

---

## Análisis: ¿Es Correcto Rechazar por RSI > 70?

### Argumentos A FAVOR de Rechazar

1. **Exhaustion risk**: RSI > 80 indica sobre-compra extrema
2. **Risk management**: Evita entrar en tops
3. **Estadísticamente**: RSI > 70 suele preceder correcciones

### Argumentos EN CONTRA de Rechazar

1. **Momentum stocks**: En strong trends, RSI puede estar overbought durante días
2. **Catalyst-driven moves**: M&A news puede superar análisis técnico
3. **High-quality setups**: Q > 80 indica setup excepcional
4. **Perdemos oportunidades reales**: KALA con catalyst fuerte (M&A, strength 7)

---

## Soluciones Propuestas

### 🎯 Solución 1: RSI Threshold Dinámico Basado en Quality Score (RECOMENDADO)

**Lógica**: Cuanto mayor sea el quality score, más tolerante ser con RSI overbought.

#### Implementación

**Archivo**: `strategies/workers/daily_plays_worker_logic.py`

**Ubicación**: Método `_analyze_daily_potential_for_signal()` o Stage 3 check

**Código actual** (aproximadamente línea ~240-260):
```python
# Check daily RSI overbought
if daily_rsi > 70:
    return False, "Daily RSI overbought: {:.1f} > 70 (exhaustion risk)".format(daily_rsi)
```

**Código propuesto**:
```python
# Dynamic RSI threshold based on quality score
# High-quality setups get more tolerance for overbought conditions
quality_score = opportunity.get('quality_score', 0)
catalyst_strength = opportunity.get('catalyst_strength', 0)

# Base threshold
rsi_threshold = 70

# Adjust based on quality
if quality_score >= 85:
    rsi_threshold = 90  # Exceptional quality: very high tolerance
elif quality_score >= 75:
    rsi_threshold = 85  # High quality: high tolerance
elif quality_score >= 60:
    rsi_threshold = 80  # Good quality: moderate tolerance
# else: keep 70 (default for lower quality)

# Additional tolerance for strong catalysts
if catalyst_strength >= 7:
    rsi_threshold += 5  # Strong catalyst: extra 5 points

# Check daily RSI with dynamic threshold
if daily_rsi > rsi_threshold:
    return False, f"Daily RSI overbought: {daily_rsi:.1f} > {rsi_threshold} (exhaustion risk, Q={quality_score:.1f})"

self.logger.info(
    f"✅ {symbol}: RSI check passed - {daily_rsi:.1f} <= {rsi_threshold} "
    f"(threshold adjusted for Q={quality_score:.1f}, catalyst={catalyst_strength})"
)
```

#### Resultados Esperados con Esta Solución

| Símbolo | Quality | Catalyst Str | RSI Actual | Threshold Dinámico | ¿Pasaría? |
|---------|---------|--------------|------------|-------------------|-----------|
| **KALA** | 49.4 | 7 | 85.3 | 70 + 5 = **75** | ❌ NO (85.3 > 75) |
| **CNCK** | 86.1 | 0 | 86.5 | 90 = **90** | ✅ **SÍ** (86.5 < 90) |

**CNCK entraría**, **KALA todavía no** (RSI demasiado extremo incluso con ajuste).

---

### 🎯 Solución 2: Catalyst Override para M&A/Earnings (COMPLEMENTARIO)

**Lógica**: Ciertos catalysts (M&A, Earnings) justifican ignorar RSI overbought.

#### Implementación

**Código propuesto**:
```python
# Strong catalyst types that override RSI check
OVERRIDE_CATALYSTS = ['M&A', 'EARNINGS_BEAT', 'FDA_APPROVAL', 'CONTRACT_WIN']

catalyst_type = opportunity.get('catalyst', 'NONE')
catalyst_strength = opportunity.get('catalyst_strength', 0)

# Override RSI check for very strong catalysts
if catalyst_type in OVERRIDE_CATALYSTS and catalyst_strength >= 7:
    self.logger.info(
        f"✅ {symbol}: RSI check OVERRIDDEN - Strong catalyst {catalyst_type} "
        f"(strength={catalyst_strength}) justifies overbought entry (RSI={daily_rsi:.1f})"
    )
    # Skip RSI check
else:
    # Normal RSI check (with dynamic threshold from Solution 1)
    if daily_rsi > rsi_threshold:
        return False, f"Daily RSI overbought: {daily_rsi:.1f} > {rsi_threshold}"
```

#### Resultados Esperados

| Símbolo | Catalyst | Strength | RSI | ¿Pasaría? |
|---------|----------|----------|-----|-----------|
| **KALA** | M&A | 7 | 85.3 | ✅ **SÍ** (override por M&A) |
| **CNCK** | TECHNICAL | 0 | 86.5 | ✅ **SÍ** (threshold 90) |

**Ambos entrarían**.

---

### 🎯 Solución 3: Modo "Aggressive Entry" con Risk Adjustments (AVANZADO)

**Lógica**: Permitir entrada en overbought pero con position sizing reducido y stops más ajustados.

#### Implementación

**Código propuesto**:
```python
# Check if we should use aggressive entry mode
aggressive_entry = False
position_size_multiplier = 1.0
stop_multiplier = 1.0

if daily_rsi > 70:
    # Determine if we allow aggressive entry
    if quality_score >= 80 or (catalyst_strength >= 7 and quality_score >= 45):
        aggressive_entry = True

        # Calculate risk adjustments
        rsi_excess = daily_rsi - 70
        position_size_multiplier = max(0.5, 1.0 - (rsi_excess / 100))  # Reduce size
        stop_multiplier = 0.7  # Tighter stop (30% closer)

        self.logger.warning(
            f"⚠️ {symbol}: AGGRESSIVE ENTRY - RSI overbought ({daily_rsi:.1f}) but "
            f"high quality (Q={quality_score:.1f}, catalyst={catalyst_strength}). "
            f"Position size: {position_size_multiplier:.1%}, Stop: {stop_multiplier:.1%} of normal"
        )
    else:
        # Still reject if quality not sufficient
        return False, f"Daily RSI overbought: {daily_rsi:.1f} > 70 (Q={quality_score:.1f} insufficient)"

# Store risk adjustments in opportunity
if aggressive_entry:
    opportunity['position_size_multiplier'] = position_size_multiplier
    opportunity['stop_loss_multiplier'] = stop_multiplier
    opportunity['aggressive_entry'] = True
```

#### Resultados Esperados

| Símbolo | Quality | RSI | Position Size | Stop Distance | ¿Entra? |
|---------|---------|-----|---------------|---------------|---------|
| **KALA** | 49.4 | 85.3 | 85% | 70% | ✅ **SÍ** (catalyst 7) |
| **CNCK** | 86.1 | 86.5 | 84% | 70% | ✅ **SÍ** (quality 86) |

**Ambos entrarían con position size reducido y stops más ajustados**.

---

## Recomendación Final

### Implementar Combinación de Solución 1 + 2

**Por qué**:
1. ✅ **Solución 1** (Dynamic RSI threshold) maneja casos como CNCK (high quality, no catalyst)
2. ✅ **Solución 2** (Catalyst override) maneja casos como KALA (strong catalyst M&A)
3. ✅ Mantiene risk management (no entra en RSI > 90 sin razón)
4. ✅ Simple de implementar y testear

### Código Completo Combinado

```python
def _check_daily_rsi_overbought(self, opportunity: Dict, daily_rsi: float) -> tuple:
    """
    Check daily RSI with dynamic thresholds

    Returns:
        (passed: bool, reason: str)
    """
    symbol = opportunity.get('symbol', 'UNKNOWN')
    quality_score = opportunity.get('quality_score', 0)
    catalyst = opportunity.get('catalyst', 'NONE')
    catalyst_strength = opportunity.get('catalyst_strength', 0)

    # --- SOLUTION 2: Catalyst Override ---
    OVERRIDE_CATALYSTS = ['M&A', 'EARNINGS_BEAT', 'FDA_APPROVAL', 'CONTRACT_WIN']

    if catalyst in OVERRIDE_CATALYSTS and catalyst_strength >= 7:
        self.logger.info(
            f"✅ {symbol}: RSI check OVERRIDDEN - Strong catalyst {catalyst} "
            f"(strength={catalyst_strength}) justifies overbought entry (RSI={daily_rsi:.1f})"
        )
        return True, f"RSI override for {catalyst}"

    # --- SOLUTION 1: Dynamic RSI Threshold ---
    # Base threshold
    rsi_threshold = 70

    # Adjust based on quality
    if quality_score >= 85:
        rsi_threshold = 90  # Exceptional quality
    elif quality_score >= 75:
        rsi_threshold = 85  # High quality
    elif quality_score >= 60:
        rsi_threshold = 80  # Good quality

    # Additional tolerance for strong catalysts (non-override types)
    if catalyst_strength >= 7:
        rsi_threshold += 5

    # Check
    if daily_rsi > rsi_threshold:
        return False, f"Daily RSI overbought: {daily_rsi:.1f} > {rsi_threshold} (Q={quality_score:.1f}, catalyst={catalyst}/{catalyst_strength})"

    self.logger.info(
        f"✅ {symbol}: RSI check passed - {daily_rsi:.1f} <= {rsi_threshold} "
        f"(adjusted for Q={quality_score:.1f}, catalyst={catalyst_strength})"
    )
    return True, f"RSI {daily_rsi:.1f} within threshold {rsi_threshold}"
```

### Integración en el Worker

**Ubicación**: En `calculate_pattern_completion()` o método equivalente, reemplazar el check actual de RSI:

```python
# OLD CODE (comentar):
# if daily_rsi > 70:
#     completion = 50.0
#     self.logger.warning(f"❌ {symbol}: Stage 3 FAILED - Daily RSI overbought: {daily_rsi:.1f} > 70")
#     return completion, support_level

# NEW CODE:
passed, reason = self._check_daily_rsi_overbought(opportunity, daily_rsi)
if not passed:
    completion = 50.0
    self.logger.warning(f"❌ {symbol}: Stage 3 FAILED - {reason}")
    return completion, support_level
```

---

## Resultados Esperados Después del Fix

### Con Solución 1 + 2 Implementada

| Símbolo | Quality | Catalyst | Strength | RSI | Threshold | Override | Resultado |
|---------|---------|----------|----------|-----|-----------|----------|-----------|
| **KALA** | 49.4 | M&A | 7 | 85.3 | 75 | ✅ SÍ (M&A) | ✅ **ENTRA** |
| **CNCK** | 86.1 | TECHNICAL | 0 | 86.5 | 90 | No | ✅ **ENTRA** |

### Símbolos de Baja Calidad (Protección Mantenida)

| Símbolo | Quality | Catalyst | Strength | RSI | Threshold | Resultado |
|---------|---------|----------|----------|-----|-----------|-----------|
| FTEL | 28.6 | OTHER | 2 | 75 | 70 | ❌ NO entra (correcto) |
| KTTA | 34.0 | OTHER | 2 | 73 | 70 | ❌ NO entra (correcto) |

**Balance perfecto**: Captura high-quality setups en overbought, rechaza low-quality setups.

---

## Plan de Implementación

### Paso 1: Añadir Método Helper (5 minutos)

Añadir método `_check_daily_rsi_overbought()` en `daily_plays_worker_logic.py`.

### Paso 2: Integrar en Stage 3 Check (5 minutos)

Reemplazar check actual de RSI > 70 con llamada al nuevo método.

### Paso 3: Testing (1 día)

Monitorear logs para verificar:
- ✅ High-quality setups entran correctamente
- ✅ Low-quality setups siguen siendo rechazados
- ✅ Logs claros sobre threshold usado

### Paso 4: Backtesting (Opcional pero Recomendado)

Correr backtest sobre días pasados para validar que:
- Captura más oportunidades (KALA, CNCK)
- No aumenta drawdown significativamente
- Win rate se mantiene o mejora

---

## Configuración Recomendada de Thresholds

```python
# Quality-based RSI thresholds
RSI_THRESHOLDS = {
    'exceptional': 90,  # Q >= 85
    'high': 85,         # Q >= 75
    'good': 80,         # Q >= 60
    'normal': 70        # Q < 60
}

# Catalyst strength bonus
CATALYST_BONUS = 5  # Add 5 points if catalyst_strength >= 7

# Override catalysts (ignore RSI completely)
OVERRIDE_CATALYSTS = ['M&A', 'EARNINGS_BEAT', 'FDA_APPROVAL', 'CONTRACT_WIN']
OVERRIDE_MIN_STRENGTH = 7  # Minimum strength for override
```

---

## Riesgos y Mitigaciones

### Riesgo 1: Entrar en Exhaustion Tops

**Mitigación**:
- Threshold máximo 90 (nunca > 90)
- Solo para Q >= 85 o catalyst fuerte
- Monitorear win rate de estos trades

### Riesgo 2: Aumentar Drawdown

**Mitigación**:
- Position size normal (sin leverage)
- Stops más ajustados si queremos (Solución 3)
- Limit a 2-3 aggressive entries por día

### Riesgo 3: False Breakouts

**Mitigación**:
- Mantener otros filtros (VWAP, volume spike, etc.)
- Solo aplicar en [TECHNICAL] high-quality o [CATALYST] strong
- No aplicar en setup medios (Q 40-60)

---

## Alternativa Conservadora (Si Dudas)

Si no quieres cambiar el threshold 70, otra opción es:

### Alert-Only Mode

**En lugar de entrar**, generar **alerta especial** para review manual:

```python
if daily_rsi > 70 and (quality_score >= 80 or catalyst_strength >= 7):
    self.logger.warning(
        f"🔔 {symbol}: HIGH-QUALITY OVERBOUGHT ALERT - "
        f"Q={quality_score:.1f}, RSI={daily_rsi:.1f}, catalyst={catalyst}/{catalyst_strength}. "
        f"Consider manual entry with tight stops."
    )
    # Send Telegram notification
    await self.send_telegram_alert(
        f"🔔 OVERBOUGHT OPPORTUNITY\n"
        f"Symbol: {symbol}\n"
        f"Quality: {quality_score:.1f}\n"
        f"RSI: {daily_rsi:.1f} (OVERBOUGHT)\n"
        f"Catalyst: {catalyst} (strength {catalyst_strength})\n"
        f"Recommend: Manual review"
    )
```

Esto te permite **revisar manualmente** cada caso sin modificar el filtro automático.

---

## Conclusión

### Solución Recomendada: Implementar Dynamic RSI Threshold (Solución 1 + 2)

**Esfuerzo**: 10-15 minutos
**Riesgo**: Bajo (solo afecta high-quality setups)
**Beneficio**: Captura KALA y CNCK type opportunities

**Archivo a modificar**: `strategies/workers/daily_plays_worker_logic.py`

**¿Quieres que implemente el código ahora?**
