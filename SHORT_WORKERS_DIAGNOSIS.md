# Diagnóstico Workers Short: gap_fade y short_parabolic

**Fecha**: 2024-12-26
**Investigación**: ¿Por qué `gap_fade` y `short_parabolic` no tienen operaciones?

---

## Resumen Ejecutivo

Ambos workers están configurados correctamente en el sistema, pero **NO están generando trades** por razones diferentes:

1. **`gap_fade`**: FALTABA en `worker_capabilities_config.py` (SOLUCIONADO ✅)
2. **`short_parabolic`**: El scanner NO enriquece con `parabolic_data` (BLOQUEADO ⚠️)

---

## 1. Gap Fade Worker

### Estado Actual
- ✅ Importado en `strategies/workers/__init__.py`
- ✅ Registrado en `worker_based_strategy_engine.py`
- ❌ **FALTABA** en `worker_capabilities_config.py`

### Problema Identificado
Mismo patrón que `livermore_intraday`: el worker estaba inicializado en el engine, pero cuando el sistema opera en modo `arbiter_enabled=True`, los workers se filtran contra el diccionario `WORKER_CAPABILITIES`. Si un worker no está en ese diccionario, **NO SE EVALÚA**.

### Solución Aplicada ✅
Agregado `gap_fade` a `WORKER_CAPABILITIES` en [worker_capabilities_config.py:290-301](CLAUDE/trading_system_v3/core/worker_capabilities_config.py#L290-L301):

```python
'gap_fade': WorkerCapabilities(
    name='gap_fade',
    priority=4,  # High priority (Gap fades are reliable mean-reversion setups)
    compatible_contexts=[
        MarketContext.MOMENTUM,   # Primary: fading momentum gaps without catalyst
        MarketContext.RANGE       # Secondary: gaps that fail and return to range
    ],
    horizon=TradingHorizon.INTRADAY,  # Strictly intraday (entry 10-11am, exit by 15:45)
    historical_winrate=0.65,  # 65% estimated (62-68% expected per worker docs)
    avg_hold_time=4.0,  # 4 hours average (10am entry to 15:45 exit)
    min_confidence=70.0  # High confidence required (gap >= 5%, VWAP resistance, volume decline)
),
```

### Criterios de Entrada (gap_fade)
El worker es **MUY SELECTIVO** y requiere **TODAS** estas condiciones:

1. **Gap >= 5%** en la apertura (vs cierre previo)
2. **Ventana de entrada: 10:00 - 11:00 AM** SOLAMENTE
3. **Sin catalizador fuerte** (catalyst_strength < 7 o catalyst_type == 'TECHNICAL')
4. **Gap failure**: Primera hora cierra < 75% del rango del gap
5. **Volumen declinando**: Volumen actual < 50% del promedio de primeros 5 min
6. **Precio rechazado en VWAP** (actuando como resistencia)
7. **Quality Score >= 6.0**
8. **Float >= 50M shares** (evita hard-to-borrow)
9. **ADV >= 1M** (liquidez)
10. **Short Interest < 20%** (evita short squeeze)
11. **Risk/Reward >= 1.5:1**

### Por Qué No Ha Generado Trades
Es un worker de **SHORT** con ventana de entrada ESTRECHA (1 hora: 10-11am) y filtros muy restrictivos:
- Gaps >= 5% sin catalizador son **raros**
- Requiere confirmación de gap failure + volumen decline + VWAP resistance
- Solo puede entrar en horario regular (no premarket/afterhours)
- Necesita ETB (Easy To Borrow) confirmado

**Conclusión**: El worker ahora puede evaluar oportunidades. La baja actividad es **por diseño** (alta selectividad).

---

## 2. Short Parabolic Worker

### Estado Actual
- ✅ Importado en `strategies/workers/__init__.py`
- ✅ Registrado en `worker_based_strategy_engine.py`
- ✅ Registrado en `worker_capabilities_config.py` (prioridad 5 - HIGHEST)
- ❌ **BLOQUEADO**: Scanner no enriquece con `parabolic_data`

### Problema Identificado
El worker requiere que el scanner enriquezca las oportunidades con datos de parabolic pattern. En [short_parabolic_worker_logic.py:186-233](CLAUDE/trading_system_v3/strategies/workers/short_parabolic_worker_logic.py#L186-L233), el worker busca:

```python
parabolic_data = opportunity.get('parabolic_data')

if not parabolic_data:
    self.logger.debug(f"⏭️ {symbol}: No parabolic data")
    return False
```

**Búsqueda en scanner**:
```bash
$ grep -r "parabolic_data" CLAUDE/trading_system_v3/scanner/
# NO MATCHES

$ grep -r "ParabolicExtensionDetector" CLAUDE/trading_system_v3/scanner/
# NO MATCHES
```

**Resultado**: El scanner **NO está enriqueciendo** las oportunidades con `parabolic_data`, por lo tanto el worker **NUNCA** pasa el filtro inicial.

### Criterios de Entrada (short_parabolic)
Requiere **TODAS** estas condiciones:

1. **`parabolic_data` debe existir** con:
   - `stage == 'LATE'` OR `exhaustion_score >= 0.70`
   - `short_entry_opportunity == True` (confirmación de reversal)
2. **Precio entre $2 - $50** (smallcaps típicamente)
3. **Confirmación de reversal** (red candle close OR rejection wick)
4. **Risk/Reward >= 2.0:1** (HOD stop vs VWAP target)
5. **Volumen >= 500k** (liquidez para shorting)
6. **ETB confirmado** (Easy To Borrow - shares disponibles)
7. **Market hours**: Solo horario regular (9:30-16:00 ET)

### Solución Requerida ⚠️

Hay **dos opciones**:

#### Opción A: Enriquecer en Scanner (RECOMENDADO)
Agregar detección parabólica en el scanner (similar a ODS):

```python
# En ibkr_native_scanner.py, después de enriquecer ODS
from core.parabolic_extension_detector import ParabolicExtensionDetector

parabolic_detector = ParabolicExtensionDetector(config)
parabolic_result = parabolic_detector.detect_parabolic_extension(symbol, bars_1min)

if parabolic_result:
    result.parabolic_data = {
        'stage': parabolic_result.stage,
        'exhaustion_score': parabolic_result.exhaustion_score,
        'short_entry_opportunity': parabolic_result.short_entry_opportunity,
        'acceleration': parabolic_result.acceleration
    }
```

**Ventajas**:
- Detecta parabólicos en tiempo real
- Worker puede evaluar inmediatamente
- Consistente con arquitectura actual (scanner enriquece, worker decide)

#### Opción B: Fallback en Worker (ACTUAL)
El worker YA tiene un fallback que calcula `parabolic_data` on-the-fly si no existe (líneas 190-229), PERO:
- Solo funciona si `bars_history` está disponible
- Agrega latencia en cada evaluación
- No es la arquitectura ideal

### Por Qué No Ha Generado Trades
El scanner no está detectando/enriqueciendo patrones parabólicos, por lo tanto el worker **NUNCA** llega a evaluar. El fallback on-the-fly puede funcionar pero:
- Requiere `bars_history` completo
- Agrega overhead de cálculo
- Puede tener timing issues (parabólico ya colapsó cuando se detecta)

**Conclusión**: El worker está **BLOQUEADO** hasta que se implemente detección parabólica en el scanner.

---

## 3. Características de SHORT Trading

Ambos workers son **SHORT-only** y tienen restricciones adicionales:

### Market Hours (CRÍTICO)
```python
from core.market_hours import can_enter_short, should_force_exit_short

can_short, short_reason = can_enter_short()
if not can_short:
    self.logger.warning(f"🚫 {symbol}: SHORT entry BLOCKED - {short_reason}")
    return False
```

**Restricciones**:
- ❌ NO premarket
- ❌ NO afterhours
- ❌ NO overnight positions
- ✅ SOLO horario regular: 9:30 AM - 4:00 PM ET

### Borrowability Check (CRÍTICO)
Ambos workers verifican ETB antes de entrar:

```python
short_data = await self.execution_engine.broker.get_short_data(symbol)

is_etb = short_data.get('is_etb', False)
shares_available = short_data.get('shortable_shares', 0)

if not is_etb or shares_available < 10000:
    self.logger.warning(f"⏳ {symbol}: WAITING for ETB/Shares to enter short")
    return False
```

**Motivo**: Evitar short squeeze / borrow fees altos en HTB (Hard To Borrow) stocks.

---

## 4. Recomendaciones

### Inmediato ✅
- [x] Agregar `gap_fade` a `worker_capabilities_config.py` (HECHO)

### Corto Plazo
1. **Implementar detección parabólica en scanner** (Opción A recomendada)
   - Agregar `ParabolicExtensionDetector` en `ibkr_native_scanner.py`
   - Enriquecer resultados con `parabolic_data`
   - Similar a como se enriquece con ODS actualmente

2. **Monitorear logs de `gap_fade`**
   - Verificar que evalúa oportunidades (debería ver logs "Gap Fade evaluation for...")
   - Los trades serán raros por la alta selectividad (esperado)

### Largo Plazo
1. **Considerar si SHORT trading es prioritario**
   - Ambos workers tienen barreras significativas (ETB, horarios, selectividad)
   - Si SHORT no es core strategy, podría ser mejor deshabilitar

2. **Backtesting de SHORT strategies**
   - Validar si gap_fade y short_parabolic tienen edge en mercado actual
   - Considerar costos de borrow (no modelados en backtest típico)

---

## 5. Testing

### Verificar gap_fade está activo
```bash
# Buscar en logs de trader después del próximo market open
grep -i "gap fade evaluation" CLAUDE/trading_system_v3_A/logs/trader.log

# Debería ver evaluaciones entre 10:00-11:00 AM si hay gaps >= 5%
```

### Verificar short_parabolic está bloqueado
```bash
# Buscar rechazos por falta de parabolic_data
grep -i "No parabolic data" CLAUDE/trading_system_v3_A/logs/trader.log

# Debería ver MUCHOS rechazos (confirma que worker está intentando evaluar)
```

---

## Conclusión

| Worker | Estado | Acción Requerida |
|--------|--------|------------------|
| `gap_fade` | ✅ **SOLUCIONADO** | Ninguna - Ahora puede evaluar (trades serán raros por diseño) |
| `short_parabolic` | ⚠️ **BLOQUEADO** | Implementar detección parabólica en scanner |

Ambos workers están **funcionando correctamente** a nivel de código. La falta de actividad se debe a:
1. `gap_fade`: Configuración faltante (CORREGIDO) + Alta selectividad por diseño
2. `short_parabolic`: Scanner no enriquece con datos parabólicos (REQUIERE IMPLEMENTACIÓN)
