# 🔍 Worker Routing Analysis - Por Qué Solo MACDV Se Ejecuta

## Fecha: 2025-10-02
## Estado: ANÁLISIS COMPLETO

---

## 🎯 TL;DR - Respuesta Corta

**El routing SÍ funciona correctamente. Todos los 4 workers están activos.**

**Problema:** El scanner está enviando principalmente **opportunities TECHNICAL con gaps pequeños**, que SOLO matchean con MACDV según las reglas de routing.

---

## 📊 Datos del Log (1 Oct 22:00-22:14)

### **Worker Activity (líneas de log):**
```
Daily Plays:  87,963 líneas  🔥 MUY ACTIVO (pero rechazando)
MACDV:         2,289 líneas  ✅ EJECUTANDO
Gap-Go:          410 líneas  ⚪ POCAS OPORTUNIDADES
Bull Flag:       237 líneas  ⚪ POCAS OPORTUNIDADES
```

### **Routing Distribution:**
```
MACDV:        18 opportunities routed (90%)
Daily Plays:   2 opportunities routed (10%)
Gap-Go:        0 opportunities routed
Bull Flag:     0 opportunities routed
```

---

## 🔍 ¿Por Qué Solo MACDV?

### **Opportunities Enviadas por Scanner:**

**Símbolos detectados:**
- AIHS, BYND, GLXG, JBLU, HCTI, AKAN, BTBT, CLOV, PLUG, RZLV, TSLQ, RR, IONZ, TSLS, DPRO (MACDV)
- DVLT, FBIO (Daily Plays)

**Características comunes:**
```
Gap:          1-5% (pequeño)
Volume Ratio: 1.5-3.0x
Catalyst:     TECHNICAL (mayoría)
Quality:      50-70
Price:        $1-$10
```

### **Matching Rules:**

#### **MACDV Match Criteria:**
```python
catalyst_type == 'TECHNICAL' and     # ✅ MAYORÍA son TECHNICAL
gap <= 5.0 and                        # ✅ Gaps pequeños
volume_ratio >= 1.5 and               # ✅ Volume moderado
1.0 <= current_price <= 25.0 and     # ✅ Rango amplio
quality_score >= 50.0                 # ✅ Quality razonable
```
**Resultado:** 90% de opportunities matchean MACDV

---

#### **Gap-Go Match Criteria:**
```python
gap >= 8.0 and                        # ❌ REQUIERE gap >= 8%
volume_ratio >= 2.0 and               # ✅ OK
current_price <= 15.0 and             # ✅ OK
quality_score >= 50.0 and             # ✅ OK
not has_strong_catalyst               # ✅ OK
```
**Problema:** Scanner NO detecta gaps >= 8% → 0 matches

---

#### **Daily Plays Match Criteria:**
```python
catalyst_type in ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH', 'CONTRACT'] and  # ✅ OK
catalyst_strength >= 6 and            # ⚠️ DVLT/FBIO tienen strength bajo
volume_ratio >= 0.5 and               # ✅ OK
1.0 <= current_price <= 50.0 and     # ✅ OK
quality_score >= 35.0                 # ⚠️ FBIO=36.9 (borderline)
```
**Problema:**
- DVLT rechazado: RSI overbought (81.1 > 70)
- FBIO rechazado: Quality score bajo (36.9, pero pasó routing)

---

#### **Bull Flag Match Criteria:**
```python
3.0 <= gap <= 8.0 and                 # ❌ Gaps son < 3% o > 8%
volume_ratio >= 2.0 and               # ✅ OK
catalyst_type not in ['FDA', 'M&A', 'EARNINGS'] and  # ✅ OK
1.0 <= current_price <= 15.0 and     # ✅ OK
quality_score >= 50.0                 # ✅ OK
```
**Problema:** Scanner NO detecta gaps en rango [3.0-8.0] → 0 matches

---

## 📈 Análisis de Opportunities

### **Ejemplo 1: AKAN (MACDV)**
```
Gap:          2.3%     ✅ <= 5.0 (MACDV pass)
                       ❌ < 8.0 (Gap-Go fail)
                       ❌ not in [3.0, 8.0] (Bull Flag fail)

Volume:       2.1x     ✅ >= 1.5 (MACDV pass)
Catalyst:     TECHNICAL ✅ (MACDV pass)
                       ❌ not strong (Daily Plays fail)
Price:        $3.60
Quality:      58.0

RESULT: Routed to MACDV ✅
```

### **Ejemplo 2: DVLT (Daily Plays)**
```
Gap:          0.2%     ❌ < 5.0 pero no técnico
Volume:       2.0x
Catalyst:     CONTRACT (strength=6)  ✅ Strong catalyst
Price:        $1.35
Quality:      51.2

RESULT: Routed to Daily Plays ✅
        BUT REJECTED: RSI overbought (81.1)
```

### **Ejemplo 3: AIHS (Si fuera gap >= 8%)**
```
Gap:          12.5%    ✅ >= 8.0 (Gap-Go pass)
                       ❌ > 5.0 (MACDV fail)
                       ❌ > 8.0 (Bull Flag fail)

Volume:       3.2x
Catalyst:     TECHNICAL (no strong)
Price:        $1.25
Quality:      65.0

RESULT: Would route to Gap-Go ✅
        (pero scanner NO detecta este tipo)
```

---

## 🚨 Problemas Identificados

### **1. Scanner Bias hacia TECHNICAL smallcaps**
El scanner detecta principalmente:
- Gaps pequeños (1-5%)
- Catalyst TECHNICAL
- Volume moderado (1.5-3x)

**Resultado:** 90% matchea solo MACDV

---

### **2. Gap-Go NO Recibe Oportunidades**
**Requiere:**
- Gap >= 8%
- Volume >= 2x
- Sin catalyst fuerte

**Problema:** Scanner NO detecta gaps >= 8% consistentemente
**Posible causa:**
- Gap threshold en scanner muy bajo
- Timeframe de detección (gaps se disipan rápido)
- Premarket data no disponible

---

### **3. Bull Flag NO Recibe Oportunidades**
**Requiere:**
- Gap en rango [3.0, 8.0]%
- Volume >= 2x

**Problema:** Scanner NO detecta gaps en este rango específico
**Posible causa:**
- Gaps detectados son < 3% (MACDV) o > 8% (raros)
- El sweet spot [3-8%] es poco común

---

### **4. Daily Plays Recibe Pero Rechaza**
**Recibió:** DVLT, FBIO (catalysts CONTRACT, FDA)

**Rechazó:**
- DVLT: RSI overbought (81.1 > 70)
- FBIO: Quality score bajo (36.9 < 50)

**Problema:** Worker criteria MÁS restrictivos que routing criteria
- Routing: quality >= 35
- Worker: quality >= 50 (inconsistencia)

---

## ✅ Soluciones Recomendadas

### **Solución 1: Ajustar Routing Criteria (RECOMENDADO)**

**Problema:** Routing criteria están demasiado segregados

**Fix:** Hacer routing más flexible

```python
# ANTES: Gap-Go
if (gap >= 8.0 and ...):  # MUY RESTRICTIVO

# DESPUÉS: Gap-Go
if (gap >= 5.0 and          # RELAJADO (captura más)
    volume_ratio >= 2.0 and
    not has_strong_catalyst):
    workers.append('gap_go')
```

**Ventaja:** Gap-Go recibiría más opportunities

---

### **Solución 2: Align Worker y Routing Criteria**

**Problema:** Routing dice quality >= 35 pero Worker rechaza < 50

**Fix:** Daily Plays Worker

```python
# daily_plays_worker_logic.py

# ANTES:
if quality_score < 50.0:
    return False

# DESPUÉS:
if quality_score < 35.0:  # Match routing criteria
    return False
```

**Ventaja:** Consistency entre routing y validation

---

### **Solución 3: Agregar Fallback Routing**

**Problema:** Opportunities que no matchean nadie se pierden

**Fix:** WorkerBasedStrategyEngine

```python
def _match_workers(self, opportunity):
    workers = []

    # ... existing matching logic ...

    # FALLBACK: Si no matchea nadie, enviar a MACDV (generalist)
    if not workers:
        self.logger.warning(
            f"⚠️ {symbol}: No specific match, routing to MACDV (fallback)"
        )
        workers.append('macdv')

    return workers
```

**Ventaja:** No perdemos ninguna opportunity

---

### **Solución 4: Scanner Configuration**

**Problema:** Scanner no detecta gaps >= 8%

**Fix:** Verificar scanner config

```python
# scanner/smallcap/smallcap_daily_scanner.py

# Verificar:
# 1. Gap calculation method
# 2. Gap threshold en config
# 3. Premarket data availability
```

**Ventaja:** Más variedad de opportunities

---

## 📋 Testing Recomendado

### **Test 1: Simular Opportunities Variadas**
```python
# Ya hecho en test_worker_routing.py
# Resultado: Routing funciona correctamente ✅
```

### **Test 2: Verificar Scanner Output**
```bash
# Check scanner log para gaps detectados
grep "gap_percentage" logs/scanner.log | awk '{print $NF}' | sort -n | uniq -c
```

### **Test 3: Monitor Worker Activity Durante 1 Día**
```bash
# Track qué workers ejecutan
tail -f logs/trader.log | grep "Routing to workers"
```

---

## 🎯 Conclusión

### **Estado Actual:**
✅ Routing funciona correctamente
✅ Todos los 4 workers están activos
⚠️ Scanner bias hacia TECHNICAL gaps pequeños
⚠️ Gap-Go y Bull Flag no reciben opportunities
⚠️ Daily Plays recibe pero rechaza (criteria inconsistency)

### **Recomendación Inmediata:**
1. **Relajar Gap-Go criteria**: gap >= 5.0 (en lugar de >= 8.0)
2. **Alinear Daily Plays criteria**: quality >= 35 (match routing)
3. **Agregar fallback routing**: MACDV como generalist

### **Recomendación Long-term:**
1. **Investigar scanner**: ¿Por qué no detecta gaps grandes?
2. **Migrar lógica completa** de Strategies (PMH, pattern detection)
3. **Testear 1 semana** con criterios ajustados

---

**Documento creado:** 2025-10-02
**Autor:** Claude
**Estado:** ✅ ANÁLISIS COMPLETO - Listo para aplicar fixes
