# Sistema de Protección contra Slippage Excesivo

## 📋 Problema Identificado

**Trade AIIO - 8 Oct 2025 15:33**
- Precio esperado de entrada: **$1.53**
- Precio real de entrada: **$1.45** (slippage de **-5.23%**)
- Salió inmediatamente por stop loss en 3 segundos
- Pérdida neta: **-$9.87**

**Causa raíz**: Bid-ask spread amplio en smallcap ilíquido cerca del cierre de mercado.

---

## 🛡️ Solución Implementada: Protección Multicapa

### **CAPA 1: Filtro de Bid-Ask Spread** (Prevención)
**Ubicación**: `execution_engine_adapter.py` líneas 164-186

**Objetivo**: Rechazar símbolos ilíquidos ANTES de entrar.

**Lógica**:
```python
spread_pct = ((ask - bid) / bid) * 100
if spread_pct > 3.0%:
    RECHAZAR entrada
```

**Resultado**:
- ✅ Evita entrar en símbolos con spread > 3%
- ✅ Protege contra slippage extremo por iliquidez
- ✅ Log detallado: bid, ask, spread %

**Ejemplo de log**:
```
🚫 gap_go: REJECTED AIIO - Bid-Ask spread too wide: 5.23%
   (bid=$1.45, ask=$1.53). Max allowed: 3.0%
```

---

### **CAPA 2: Detección de Slippage Post-Ejecución** (Respuesta Inmediata)
**Ubicación**: `execution_engine_adapter.py` líneas 277-332

**Objetivo**: Cerrar posición INMEDIATAMENTE si slippage > 2% tras la ejecución.

**Lógica**:
```python
actual_fill_price = trade.fill_price
slippage_pct = ((actual_fill_price - expected_price) / expected_price) * 100

if abs(slippage_pct) > 2.0%:
    # Cerrar posición inmediatamente
    emergency_exit(symbol)
```

**Resultado**:
- ✅ Cierra posición en milisegundos si slippage excesivo
- ✅ Limita pérdida máxima por slippage a ~2%
- ✅ Alerta por Telegram con detalles
- ✅ No rastrea la posición (return None)

**Ejemplo de log**:
```
🚨 gap_go: EXCESSIVE SLIPPAGE on AIIO!
   Expected: $1.53, Actual: $1.45 (slippage: -5.23%). Max allowed: ±2.0%
⚠️ gap_go: Closing AIIO immediately due to excessive slippage
✅ gap_go: Emergency exit successful for AIIO @ $1.45 (slippage protection)
```

**Mensaje Telegram**:
```
🚨 SLIPPAGE PROTECTION TRIGGERED
Symbol: AIIO
Expected: $1.53
Actual: $1.45
Slippage: -5.23%
Position closed immediately
```

---

### **CAPA 3: Stop Loss Ajustado a Precio Real** (Precisión)
**Ubicación**: `execution_engine_adapter.py` líneas 334-345, 384

**Objetivo**: Calcular stop loss desde precio de fill REAL, no esperado.

**Lógica**:
```python
# Actualizar current_price al fill real
current_price = actual_fill_price

# Guardar en DB y tracking
trade_data['entry_price'] = current_price  # Fill real
position_data['entry_price'] = current_price  # Fill real

# Stop loss se calcula desde este precio
stop_loss_trigger = entry_price * (1 - stop_loss_pct)
```

**Resultado**:
- ✅ Stop loss siempre relativo al precio REAL de entrada
- ✅ Evita que slippage pequeño dispare stop loss inmediato
- ✅ Log de slippage aceptable (< 2%)

**Ejemplo de log**:
```
💱 gap_go: BIAF fill slippage: +0.62%
   (expected $3.22, actual $3.24)
✅ gap_go: Position opened - BIAF @ $3.24 x 50 shares
   🛡️ Protection: Spread checked ✓, Slippage monitored ✓, Stop loss @ actual fill ✓
```

---

## 📊 Configuración de Umbrales

| Protección | Umbral | Ajustable en | Recomendación |
|------------|--------|--------------|---------------|
| **Spread máximo** | 3.0% | Línea 172 | 2-4% según mercado |
| **Slippage máximo** | 2.0% | Línea 282 | 1.5-2.5% según volatilidad |
| **Stop loss base** | 5.0% | config.ini | Configurado por estrategia |

---

## 🔍 Monitoreo y Logs

### **Logs de Protección Activa**:

1. **Spread Check Pass**:
   ```
   ✅ gap_go: BIAF spread check passed: 1.23% (bid=$3.20, ask=$3.24)
   ```

2. **Slippage Aceptable**:
   ```
   💱 gap_go: BIAF fill slippage: +0.62% (expected $3.22, actual $3.24)
   ```

3. **Entrada Exitosa con Protecciones**:
   ```
   ✅ gap_go: Position opened - BIAF @ $3.24 x 50 shares
      🛡️ Protection: Spread checked ✓, Slippage monitored ✓, Stop loss @ actual fill ✓
      📊 Trade ID: gap_go_BIAF_1728...
   ```

### **Logs de Protección Disparada**:

1. **Rechazo por Spread**:
   ```
   🚫 gap_go: REJECTED AIIO - Bid-Ask spread too wide: 5.23%
      (bid=$1.45, ask=$1.53). Max allowed: 3.0%
   ```

2. **Cierre por Slippage Excesivo**:
   ```
   🚨 gap_go: EXCESSIVE SLIPPAGE on AIIO! Expected: $1.53, Actual: $1.45 (slippage: -5.23%)
   ⚠️ gap_go: Closing AIIO immediately due to excessive slippage
   ✅ gap_go: Emergency exit successful for AIIO @ $1.45 (slippage protection)
   ```

---

## 🧪 Casos de Prueba

### **Caso 1: Entrada Normal (Spread y Slippage OK)**
- Spread: 1.2% < 3% ✅
- Slippage: +0.5% < 2% ✅
- Resultado: Posición abierta con precio real

### **Caso 2: Rechazo por Spread Alto**
- Spread: 5.2% > 3% ❌
- Resultado: Entrada rechazada, sin orden

### **Caso 3: Cierre Inmediato por Slippage**
- Spread: 2.1% < 3% ✅ (pasa filtro)
- Slippage: -5.2% > 2% ❌
- Resultado: Orden ejecutada pero cerrada inmediatamente

### **Caso 4: Slippage Pequeño Aceptado**
- Spread: 1.8% < 3% ✅
- Slippage: +1.2% < 2% ✅
- Resultado: Posición abierta, stop loss ajustado a fill real

---

## 📈 Impacto Esperado

### **Antes (sin protecciones)**:
- Trade AIIO: Pérdida -$9.87 por slippage + stop loss
- Trade similar: Posible pérdida -5% a -8%

### **Después (con protecciones)**:

**Si Capa 1 rechaza** (spread > 3%):
- ✅ **Sin pérdida**: Entrada bloqueada

**Si Capa 2 cierra** (slippage > 2%):
- ✅ **Pérdida limitada**: ~$2-4 (comisiones + pequeño slippage)

**Si ambas capas pasan** (spread OK, slippage < 2%):
- ✅ **Trade normal**: Stop loss correcto desde precio real

---

## 🔄 Flujo de Protección

```
1. Signal detectado (ej: AIIO @ $1.53)
   ↓
2. 🛡️ CAPA 1: Check bid-ask spread
   ├─ Spread > 3% → RECHAZAR (sin orden)
   └─ Spread ≤ 3% → CONTINUAR
   ↓
3. Ejecutar orden de mercado
   ↓
4. 🛡️ CAPA 2: Check slippage real
   ├─ Slippage > 2% → CERRAR INMEDIATAMENTE
   └─ Slippage ≤ 2% → CONTINUAR
   ↓
5. 🛡️ CAPA 3: Actualizar entry_price a fill real
   ↓
6. Tracking con stop loss desde precio real
   ↓
7. Worker stop manager calcula exits desde entry_price real
```

---

## 🛠️ Mantenimiento

### **Revisar periódicamente**:

1. **Tasa de rechazo por spread** (Capa 1)
   - Si > 30%: Considerar aumentar umbral a 3.5-4%
   - Si < 5%: Umbral apropiado

2. **Frecuencia de cierres por slippage** (Capa 2)
   - Si > 10%: Revisar liquidez de símbolos o aumentar umbral
   - Si = 0%: Considerar reducir umbral a 1.5%

3. **Slippage promedio aceptado** (Capa 3)
   - Objetivo: < 1% promedio
   - Monitorear en logs `💱 fill slippage`

### **Ajuste de umbrales por condiciones de mercado**:

| Condición | Spread Max | Slippage Max |
|-----------|------------|--------------|
| **Premarket** | 4.0% | 3.0% |
| **Market Open (9:30-10:00)** | 3.5% | 2.5% |
| **Regular Hours** | 3.0% | 2.0% |
| **Market Close (15:30-16:00)** | 2.5% | 1.5% |
| **Afterhours** | 4.0% | 3.0% |

---

## 📝 Cambios Realizados

### **Archivo**: `core/execution_engine_adapter.py`

1. **Líneas 164-186**: Añadido filtro de bid-ask spread (Capa 1)
2. **Líneas 279-283**: **FIX CRÍTICO**: Obtener `avg_fill_price` del broker (IBKR)
3. **Líneas 285-296**: Validación y logging de fill price real
4. **Líneas 298-332**: Añadida detección y cierre por slippage excesivo (Capa 2)
5. **Líneas 353-366**: Cálculo de slippage y actualización de current_price (Capa 3)
6. **Líneas 372-385**: Guardar slippage data en DB (entry_price, expected_entry_price, entry_slippage_pct)
7. **Línea 410**: entry_price en position_data usa precio real de fill
8. **Línea 414**: Añadido entry_time a position_data
9. **Líneas 420-426**: Log de resumen de protecciones

### **🔧 Fix Crítico - Precio Real vs Esperado**

**Problema detectado** (Trade BAOS - 9 Oct 2025):
```
Sistema reportaba:  Entry $4.81 → Exit $5.11 → PnL +6.30%
Broker ejecutó:     Entry $4.86 → Exit $5.11 → PnL +5.14%
Diferencia:         $0.05 (+1.04% slippage no detectado)
```

**Causa raíz**:
- Código intentaba `trade.fill_price` (no existe en IBKR)
- IBKR devuelve precio real en `trade.avg_fill_price`
- Sistema usaba precio esperado para stop loss, trailing stop, PnL

**Solución**:
- Priorizar `trade.avg_fill_price` al obtener fill price (línea 280)
- Guardar precio esperado y real por separado en DB
- Calcular y registrar slippage percentage
- Actualizar todos los cálculos para usar precio real de fill

---

## ✅ Estado: COMPLETO

- ✅ **Capa 1**: Filtro de spread implementado
- ✅ **Capa 2**: Detección y cierre por slippage implementado
- ✅ **Capa 3**: Stop loss ajustado a precio real implementado
- ✅ **Logging**: Completo y detallado
- ✅ **Telegram**: Alertas configuradas
- ✅ **Documentación**: Este archivo

---

## 🎯 Próximos Pasos (Opcional)

1. **Backtesting**: Analizar trades pasados con estas protecciones
2. **Ajuste dinámico**: Variar umbrales según sesión de mercado
3. **Métricas**: Dashboard de slippage/spread por símbolo
4. **Machine Learning**: Predecir slippage probable antes de entrada

---

**Última actualización**: 2025-10-09
**Versión**: 1.0
**Autor**: Sistema de Trading v3
