# 📊 Pre-Market Data Strategy

**Objetivo**: Usar datos de pre-market para contexto, pero **SOLO operar en horario regular**.

---

## 🎯 Estrategia Implementada

### Datos de Pre-Market: ✅ SÍ
### Trading Pre-Market: ❌ NO

El sistema **acumula barras de 8:00-9:30 AM** para análisis, pero **solo ejecuta trades de 9:30-16:00**.

---

## 🔧 Configuración Actual

### Scanner (`smallcap_daily_scanner.py`)
```python
useRTH=False  # Obtiene datos de pre-market + regular hours
```

**Resultado**:
- ✅ Barras de 1 minuto desde 8:00 AM
- ✅ Datos de gap, volume, price action pre-market
- ✅ Contexto completo para decisiones

### Workers (config.ini)
```ini
[ORB_STRATEGY]
enable_extended_hours = false  # NO tradear en pre-market
premarket_enabled = false

[DAILY_PLAYS_STRATEGY]
enable_extended_hours = false  # NO tradear en pre-market
premarket_enabled = false
```

**Resultado**:
- ✅ Workers solo operan 9:30-16:00
- ✅ No se ejecutan trades fuera de horario regular
- ✅ Datos de pre-market solo para análisis

### ContextEngine (`context_engine.py`)
```python
# Early Bird: min 10 bars (10 minutos de pre-market)
# Normal: min 30 bars (30 minutos de regular hours)
min_bars_required = 10 if is_early_bird else 30
```

**Resultado**:
- ✅ Early Bird symbols evaluados con 10 barras
- ✅ Símbolos detectados a las 9:20 AM tienen contexto suficiente
- ✅ No necesita esperar 30 minutos después de apertura

---

## 📈 Flujo de Datos

### Pre-Market (8:00-9:30 AM):

```
8:00 AM → IBKR scanner detecta CETX (gap 189%, vol 2x)
       → Scanner obtiene barras: useRTH=False
       → Acumula barras: 8:00, 8:01, 8:02... 9:29

8:45 AM → CETX tiene 45 barras acumuladas
       → Early Bird califica: gap >=5%, price OK, volume OK
       → Agrega a cola: "Enviar a las 9:30 AM"

9:20 AM → CETX tiene 80 barras acumuladas
       → Early Bird mantiene en cola
```

### Market Open (9:30 AM):

```
9:30:00 AM → Early Bird envía CETX al trader
           → Flag 'early_bird': True
           → Incluye 90 barras (8:00-9:30 AM)

9:30:01 AM → Trader recibe CETX
           → ContextEngine: "Early Bird, 90 barras (min 10 OK)"
           → Crea contexto: ATR, ADX, Volume, Trend
           → Routing a ORB worker
```

### ORB Worker Evaluation (9:30-10:00 AM):

```
9:30-9:35 AM → ORB worker forma opening range
             → Tiene contexto pre-market: volatilidad, trend
             → Decisión informada con 90 barras de historia

9:35 AM → Breakout detectado
       → ENTRY: $9.20 (horario regular)
       → ✅ Trade ejecutado SOLO en horario regular
```

---

## 🆚 Comparación: Antes vs Después

| Aspecto | Antes | Después |
|---------|-------|---------|
| **Barras disponibles a 9:30 AM** | 0-5 barras | 90 barras (pre-market) |
| **Contexto disponible** | ❌ Insuficiente | ✅ Completo |
| **ContextEngine acepta** | ❌ Rechaza (0/30) | ✅ Acepta (90/10) |
| **Trading pre-market** | ❌ No | ❌ No |
| **Trading regular hours** | ✅ Sí | ✅ Sí |
| **Decisiones informadas** | ❌ No (sin datos) | ✅ Sí (con pre-market) |

---

## 🔍 Verificación

### Logs Correctos (Sistema Funcionando):

**Scanner** (8:00-9:30 AM):
```
8:45 AM → 🐦 EARLY BIRD qualified: CETX (gap=189.9%, price=$8.90, pm_vol=50,000)
9:30 AM → 🔔 Market OPEN - Sending 1 Early Bird opportunities
9:30 AM → 📤 Early Bird: CETX qualified (gap=189.9%, Q=85.9)
```

**Trader** (9:30 AM):
```
9:30 AM → 📡 Received 1 opportunities from scanner
9:30 AM → 🎯 ORB Priority: Processing CETX (Early Bird)
9:30 AM → 🏹 Routing CETX directly to ORB worker
```

**ContextEngine** (9:30 AM):
```
9:30 AM → 🐦 CETX: Early Bird with 90 bars (min 10) - creating context
9:30 AM → 📊 CETX: ATR=0.0456, ADX=35.2, VolZ=2.5, Gap=189.9%
9:30 AM → ✅ CETX: Context created - MOMENTUM_RUNNER (confidence: 0.85)
```

**ORB Worker** (9:30-10:00 AM):
```
9:30 AM → [ORB] Evaluating CETX with pre-market context
9:35 AM → [ORB] ✅ ENTRY SIGNAL: CETX at $9.20 (breakout confirmed)
```

### Logs Incorrectos (Problema):

```
❌ 9:30 AM → ⚠️ CETX: Insufficient bars for context (0/30)
❌ 9:30 AM → 🚫 CETX: Extended hours trading DISABLED - Current session: PREMARKET
❌ 9:30 AM → ContextEngine: neutral context (insufficient data)
```

---

## ⚙️ Configuración Recomendada

### Para Máxima Efectividad:

1. **Scanner**:
   ```python
   useRTH=False  # Ya configurado ✅
   ```

2. **Workers** (config.ini):
   ```ini
   enable_extended_hours = false  # Ya configurado ✅
   premarket_enabled = false      # Ya configurado ✅
   ```

3. **ContextEngine**:
   ```python
   min_bars_required = 10 if is_early_bird else 30  # Ya implementado ✅
   ```

---

## 🚨 Troubleshooting

### Problema: "Insufficient bars (0/30)"

**Causa**: Símbolo NO es Early Bird, llegó después de 9:30 AM sin datos

**Solución**: Normal, el sistema espera 30 minutos para acumular barras

---

### Problema: "Insufficient bars (5/10)" para Early Bird

**Causa**:
1. IBKR no proporcionó datos de pre-market
2. Símbolo detectado muy cerca de 9:30 AM (ej: 9:25 AM)

**Solución**:
- Verificar conexión IBKR a 8:00 AM
- Verificar `useRTH=False` en scanner
- Aceptable si solo hay 5-9 minutos de pre-market

---

### Problema: "Extended hours trading DISABLED - PREMARKET"

**Causa**: Worker intentando operar en pre-market

**Solución**: ✅ Correcto - esto es esperado y correcto

**Explicación**: El worker rechaza trades en pre-market, pero ACEPTA en regular hours con contexto de pre-market.

---

## 📊 Beneficios de Esta Estrategia

1. ✅ **Contexto Completo**: 90 barras vs 0 barras
2. ✅ **Decisiones Informadas**: ATR, ADX, Trend desde pre-market
3. ✅ **Sin Riesgo Pre-Market**: Solo opera en horario líquido
4. ✅ **Cumple Regulaciones**: No trading fuera de horas regulares
5. ✅ **Mejor Win Rate**: Más datos = mejores decisiones

---

## 🎯 Próximos Pasos

1. ✅ **Implementado**: ContextEngine acepta 10 barras para Early Bird
2. ⏳ **Monitorear**: Primera sesión con esta configuración
3. ⏳ **Validar**: Verificar que workers reciben contexto completo
4. ⏳ **Optimizar**: Ajustar min_bars si es necesario (8-15 barras)

---

**✅ Sistema configurado correctamente - Pre-market data SÍ, Pre-market trading NO**
