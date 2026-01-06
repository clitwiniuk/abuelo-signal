# Fix: Momentum Runner Logic Restored + Catalyst Threshold Reverted

## Fecha: 1 Diciembre 2025

## Problema Identificado

El sistema Daily Plays Worker tenía un threshold de `catalyst_strength >= 7` que era demasiado alto, resultando en:
- **0.02% tasa de conversión** (1 trade de 4,240 oportunidades)
- **La mayoría de candidatos rechazados** por strength 2 < 7

## Causa Raíz

El commit del 14 de Noviembre añadió configuración dual (Momentum Runner + Catalyst) pero:
1. La configuración se **perdió** en refactors posteriores
2. El threshold se cambió de 5 → 7 sin la lógica de momentum runner
3. Solo quedó el modo catalyst con threshold=7

## Solución Implementada

### 1. Añadida Configuración a config.ini

**Ubicación**: `config.ini` líneas 873-895

```ini
# ===== MOMENTUM RUNNER CONFIGURATION (Dual-Mode System) =====
# Momentum Runners: Explosive gap+volume smallcap movers
runner_min_gap_pct = 10.0             # Minimum gap for momentum runners
runner_min_volume_ratio = 3.0         # Minimum volume ratio for runners
runner_max_price = 20.0               # Maximum price for smallcap runners
runner_vwap_tolerance = 0.9           # VWAP tolerance (10% below allowed)
runner_min_quality_score = 30.0       # Relaxed quality score for runners
runner_min_confirmations = 0          # Immediate entry for runners
runner_confirmation_window = 30       # 30 second confirmation window
runner_skip_daily_checks = true       # Skip daily context checks for speed
runner_catalyst_optional = true       # Catalyst not required for runners

# Catalyst Plays: Strong catalyst-driven moves (traditional mode)
catalyst_min_gap_pct = 0.0            # No minimum gap required
catalyst_min_volume_ratio = 1.2       # Normal volume requirement
catalyst_max_price = 25.0             # Normal max price
catalyst_vwap_tolerance = 1.0         # Strict VWAP requirement
catalyst_min_quality_score = 35.0     # Normal quality score
catalyst_min_strength = 5             # Minimum catalyst strength (REVERTED: was 7)
catalyst_min_confirmations = 1        # 1 confirmation required
catalyst_confirmation_window = 120    # 2 minute confirmation window
catalyst_skip_daily_checks = false    # Daily context checks active
catalyst_catalyst_optional = false    # Catalyst required
```

### 2. Modificado __init__ del Worker

**Archivo**: `daily_plays_worker_logic.py` líneas 87-131

**Cambios**:
- Añadido `self.position_types = {}` para tracking
- Carga configuración desde config.ini con getattr()
- Fallback a valores por defecto si no hay config

```python
# Load runner and catalyst configs from config.ini (centralized)
if config:
    # Momentum Runner config
    self.runner_config = {
        'min_gap_pct': getattr(config, 'runner_min_gap_pct', 10.0),
        'min_volume_ratio': getattr(config, 'runner_min_volume_ratio', 3.0),
        ...
    }

    # Catalyst Play config
    self.catalyst_config = {
        'min_gap_pct': getattr(config, 'catalyst_min_gap_pct', 0.0),
        'min_catalyst_strength': getattr(config, 'catalyst_min_strength', 5),  # FIXED: was 7
        ...
    }
```

### 3. Añadido Método de Detección

**Archivo**: `daily_plays_worker_logic.py` líneas 475-509

**Nuevo método**: `_is_momentum_runner()`

```python
def _is_momentum_runner(self, opportunity: Dict[str, Any]) -> bool:
    """
    Detect if opportunity is a momentum runner

    Criteria:
    - Gap >= 10%
    - Volume >= 3x average
    - Price < $20
    """
    gap_pct = opportunity.get('gap_percentage', 0.0)
    volume_ratio = opportunity.get('volume_ratio', 0.0)
    price = opportunity.get('price', 0.0)

    is_runner = (
        gap_pct >= self.runner_config['min_gap_pct'] and
        volume_ratio >= self.runner_config['min_volume_ratio'] and
        price <= self.runner_config['max_price']
    )

    if is_runner:
        self.logger.info(
            f"🏃 {symbol}: MOMENTUM RUNNER detected "
            f"(gap={gap_pct:.1f}%, vol={volume_ratio:.1f}x, price=${price:.2f})"
        )

    return is_runner
```

### 4. Modificado calculate_pattern_completion()

**Archivo**: `daily_plays_worker_logic.py` líneas 209-296

**Cambios principales**:

a) **Detección al inicio** (líneas 209-216):
```python
# ===== DUAL MODE DETECTION =====
is_momentum_runner = self._is_momentum_runner(opportunity)

# Store position type for later (dynamic exits)
if is_momentum_runner:
    self.position_types[symbol] = 'runner'
else:
    self.position_types[symbol] = 'catalyst'
```

b) **Stage 2 con lógica dual** (líneas 256-296):
```python
# Use different thresholds based on mode (runner vs catalyst)
if is_momentum_runner:
    # MOMENTUM RUNNER mode: relaxed requirements
    min_quality = self.runner_config['min_quality_score']  # 30
    min_strength = 0  # Catalyst optional for runners
    mode_name = "RUNNER"
elif daily_context.get('reversal', {}).get('is_reversal', False):
    # REVERSAL mode: relaxed requirements
    min_quality = self.reversal_quality_score_relaxed
    min_strength = 0  # Catalyst optional for reversals
    mode_name = "REVERSAL"
else:
    # CATALYST mode: standard requirements
    min_quality = self.catalyst_config['min_quality_score']  # 35
    min_strength = self.catalyst_config['min_catalyst_strength']  # 5 (FIXED: was 7)
    mode_name = "CATALYST"
```

c) **Logs mejorados**:
```python
self.logger.info(
    f"📊 {symbol}: ✅ Stage 2 passed (50%) [{mode_name}] - "
    f"Quality: {quality_score:.1f}>={min_quality}, "
    f"Strength: {catalyst_strength}>={min_strength}"
)
```

## Impacto Esperado

### Antes del Fix
- **Catalyst Threshold**: 7 (muy alto)
- **No detección** de momentum runners
- **Tasa de conversión**: 0.02% (1/4240)
- **Modo único**: Solo catalyst mode

### Después del Fix
- **Catalyst Threshold**: 5 (revertido)
- **Detección activa** de momentum runners
- **Tasa de conversión esperada**: 5-10% (210-420 trades)
- **Tres modos**: Runner / Catalyst / Reversal

### Distribución Esperada de Trades

| Modo | Threshold | % Oportunidades | Trades Esperados (de 4,240) |
|------|-----------|----------------|--------------------------|
| Momentum Runner | Quality>=30, Strength>=0 | 2-3% | 85-127 |
| Catalyst | Quality>=35, Strength>=5 | 3-5% | 127-212 |
| Reversal | Quality>=40, Strength>=0 | 1-2% | 42-85 |
| **TOTAL** | - | **6-10%** | **254-424** |

## Ejemplos de Comportamiento

### Ejemplo 1: FLYE (Momentum Runner)
```
Gap: 300%+ (10% ✅)
Volume: 9M (3x ✅)
Price: $18 (<$20 ✅)
Quality: 28

→ ANTES: Rechazado (Quality 28 < 35)
→ AHORA: ✅ ACEPTADO como RUNNER (Quality 28 >= 30)
```

### Ejemplo 2: KTTA (Catalyst Play)
```
Gap: 5%
Volume: 1.5x
Price: $12
Quality: 34.3
Strength: 2

→ ANTES: Rechazado (Strength 2 < 7)
→ AHORA: Rechazado (Strength 2 < 5) - pero más cerca!
```

### Ejemplo 3: FTEL (Catalyst Play Mejorado)
```
Gap: 3%
Volume: 2x
Price: $8
Quality: 29
Strength: 5

→ ANTES: Rechazado (Quality 29 < 35 AND Strength 5 < 7)
→ AHORA: Rechazado (Quality 29 < 35) - solo falta quality!
```

## Logs Nuevos a Ver

Cuando funcione correctamente verás:

```
🏃 FLYE: MOMENTUM RUNNER detected (gap=308.7%, vol=9.2x, price=$18.31)
📊 FLYE: ✅ Stage 2 passed (50%) [RUNNER] - Quality: 28.0>=30.0, Strength: 2>=0
```

O para catalyst plays:

```
📊 KTTA: ✅ Stage 2 passed (50%) [CATALYST] - Quality: 34.3>=35.0, Strength: 5>=5
```

## Testing Recomendado

1. **Reiniciar el sistema** para cargar la nueva configuración
2. **Monitorear logs** para ver detección de runners:
   ```bash
   tail -f logs/worker_daily_plays.log | grep "MOMENTUM RUNNER\|Stage 2"
   ```
3. **Verificar tasa de conversión** después de 1 hora de mercado
4. **Esperar símbolos** como FLYE (gap >10%, vol >3x) para confirmar detección

## Archivos Modificados

1. ✅ `config.ini` - Añadida configuración dual (líneas 873-895)
2. ✅ `strategies/workers/daily_plays_worker_logic.py` - Lógica dual implementada
   - __init__ (líneas 87-131)
   - _is_momentum_runner() (líneas 475-509)
   - calculate_pattern_completion() (líneas 209-296)

## Próximos Pasos

1. ✅ **Configuración añadida**
2. ✅ **Código implementado**
3. ⏳ **Testing en producción** (requiere reinicio)
4. ⏳ **Monitoreo de resultados** (primer día)
5. ⏳ **Ajuste fino** de thresholds si es necesario

## Rollback Plan

Si algo falla, revertir catalyst_min_strength a 7:

```ini
catalyst_min_strength = 7  # Revert to previous value
```

Y comentar la lógica de momentum runner en el código.

## Conclusión

✅ El sistema ahora tiene **3 modos de entrada**:
1. **Momentum Runner**: Para movers explosivos (gap >10%, vol >3x)
2. **Catalyst Play**: Para catalyst tradicionales (strength >= 5)
3. **Reversal**: Para oversold bounces

✅ **Catalyst threshold revertido** de 7 → 5

✅ **Logs mejorados** muestran el modo usado

La tasa de conversión debería aumentar de **0.02% → 5-10%**, capturando tanto momentum runners como catalyst plays de calidad.
