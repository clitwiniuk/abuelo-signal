# Scanner Improvements Needed

**Fecha:** 2025-11-09
**Contexto:** Tras implementar ORB Worker + Worker Coordination con pattern alignment

---

## 🎯 Problema Actual

El scanner actual **NO está aprovechando el nuevo sistema de coordinación** porque:

1. ❌ No calcula ODS data (Opening Drive Signal)
2. ❌ No calcula Intraday Structure data
3. ❌ No envía pattern alignment metadata
4. ❌ No calcula ATR (necesario para adaptive risk sizing)
5. ❌ Quality score no considera patterns
6. ❌ Falta metadata específica para ORB Worker

**Resultado:** Trade Arbiter no puede aplicar pattern alignment bonus (+10 pts) ni adaptive risk sizing correctamente.

---

## 📊 Análisis de Impacto

### Sin mejoras (estado actual):
```python
# Scanner envía opportunity básico
opportunity = {
    'symbol': 'AAPL',
    'quality_score': 75.0,  # Score básico sin patterns
    'current_price': 150.0,
    'bars_history': [...],   # Solo bars generales
    # ❌ NO ODS data
    # ❌ NO Intraday Structure
    # ❌ NO ATR
}

# Trade Arbiter score:
total_score = 65.0  # Sin pattern bonus
adaptive_risk = 1.2%  # Risk fijo base
```

### Con mejoras (propuesto):
```python
# Scanner envía opportunity ENRIQUECIDO
opportunity = {
    'symbol': 'AAPL',
    'quality_score': 85.0,  # Score mejorado con patterns
    'current_price': 150.0,
    'bars_history': [...],
    'atr_percent': 5.2,     # ✅ ATR calculado

    # ✅ ODS data
    'ods_data': {
        'day_type': 'TREND_DRIVE_BULLISH',
        'classification': 'STRONG_BULLISH',
        'strength': 8.5,
        'upside_move_pct': 5.0
    },

    # ✅ Intraday Structure
    'intraday_structure': {
        'current_phase': 'CONTINUATION',
        'continuation_type': 'PULLBACK_TO_VWAP',
        'liquidity_sweep_detected': True,
        'sweep_direction': 'BULLISH_RECLAIM'
    },

    # ✅ ORB specific data
    'orb_data': {
        'orb_high': 151.0,
        'orb_low': 149.5,
        'orb_range_pct': 1.0,
        'orb_bars': [...],  # Bars 9:30-10:00
        'current_vs_orb': 'ABOVE_HIGH'
    }
}

# Trade Arbiter score:
total_score = 91.0  # ✅ +10 pattern bonus + quality bonus
adaptive_risk = 1.7%  # ✅ Adaptive risk (quality + patterns)
```

**Mejora:** +26 pts en score, +0.5% en risk allocation = mejor capital utilization

---

## 🔧 Mejoras Propuestas

### 1️⃣ **Integrar ODS Classifier**

**Archivo:** `scanner_main.py` → `_scan_for_opportunities()`

**Código a añadir:**
```python
from core.ods_classifier import ODSClassifier

# En _scan_for_opportunities(), después de obtener bars:
ods_classifier = ODSClassifier()

for play in intraday_plays:
    # Calcular ODS para cada opportunity
    if play.bars_1min and len(play.bars_1min) >= 12:
        ods_data = ods_classifier.classify_opening_drive(
            symbol=play.symbol,
            bars_1min=play.bars_1min[:12]  # First 12 minutes
        )

        # Añadir a opportunity
        opportunity['ods_data'] = {
            'day_type': ods_data.day_type.value,
            'classification': ods_data.classification,
            'strength': ods_data.strength,
            'direction': ods_data.direction,
            'upside_move_pct': ods_data.upside_move_pct,
            'downside_move_pct': ods_data.downside_move_pct,
            'range_pct': ods_data.range_pct
        }
```

**Beneficio:** Trade Arbiter puede aplicar +5 bonus por 1 pattern, +10 por 2+

---

### 2️⃣ **Integrar Intraday Structure Classifier**

**Archivo:** `scanner_main.py` → `_scan_for_opportunities()`

**Código a añadir:**
```python
from core.intraday_structure_classifier import IntradayStructureClassifier

# En _scan_for_opportunities()
structure_classifier = IntradayStructureClassifier()

for play in intraday_plays:
    # Calcular Intraday Structure
    if play.bars_1min:
        structure_data = structure_classifier.classify_structure(
            symbol=play.symbol,
            bars_1min=play.bars_1min,
            current_price=play.context.current_price
        )

        # Añadir a opportunity
        opportunity['intraday_structure'] = {
            'current_phase': structure_data.current_phase.value,
            'continuation_type': structure_data.continuation_type,
            'liquidity_sweep_detected': structure_data.liquidity_sweep_detected,
            'sweep_direction': structure_data.sweep_direction,
            'midday_structure': structure_data.midday_structure
        }
```

**Beneficio:** Completa pattern alignment (ODS + Structure = 2 patterns = +10 bonus)

---

### 3️⃣ **Añadir Cálculo de ATR**

**Archivo:** `scanner_main.py` → `_scan_for_opportunities()`

**Código a añadir:**
```python
def calculate_atr(bars, period=14):
    """Calculate ATR from bars"""
    if len(bars) < period:
        return 0.0

    true_ranges = []
    for i in range(1, len(bars)):
        high_low = bars[i].high - bars[i].low
        high_close = abs(bars[i].high - bars[i-1].close)
        low_close = abs(bars[i].low - bars[i-1].close)
        true_range = max(high_low, high_close, low_close)
        true_ranges.append(true_range)

    atr = sum(true_ranges[-period:]) / period
    atr_pct = (atr / bars[-1].close) * 100 if bars[-1].close > 0 else 0.0
    return atr_pct

# En opportunity creation:
opportunity['atr_percent'] = calculate_atr(play.bars_1min)
```

**Beneficio:** Adaptive risk sizing puede reducir risk en alta volatilidad (-0.2% si ATR > 8%)

---

### 4️⃣ **Mejorar Quality Score con Patterns**

**Archivo:** `scanner_main.py` → `_scan_for_opportunities()`

**Código a añadir:**
```python
def calculate_enhanced_quality_score(play, ods_data, structure_data, atr_pct):
    """
    Enhanced quality score considering patterns
    Base: 0-100
    Adjustments:
    - ODS STRONG_BULLISH: +10
    - Intraday continuation: +5
    - Liquidity sweep: +5
    - Low volatility (ATR < 5%): +5
    """
    base_score = play.quality_score  # Original scanner score

    # ODS bonus
    if ods_data and ods_data.get('classification') == 'STRONG_BULLISH':
        base_score += 10
    elif ods_data and ods_data.get('classification') == 'MODERATE_BULLISH':
        base_score += 5

    # Intraday structure bonus
    if structure_data:
        if structure_data.get('continuation_type') in ['PULLBACK_TO_VWAP', 'HIGHER_LOW']:
            base_score += 5
        if structure_data.get('liquidity_sweep_detected'):
            base_score += 5

    # Volatility bonus (low vol = more predictable)
    if atr_pct > 0 and atr_pct < 5.0:
        base_score += 5

    # Cap at 100
    return min(base_score, 100.0)

# En opportunity creation:
opportunity['quality_score'] = calculate_enhanced_quality_score(
    play, ods_data, structure_data, atr_pct
)
```

**Beneficio:** Better quality scores → better signal selection → higher win rate

---

### 5️⃣ **Añadir Metadata para ORB Worker**

**Archivo:** `scanner_main.py` → `_scan_for_opportunities()`

**Código a añadir:**
```python
def extract_orb_data(bars_1min):
    """
    Extract ORB-specific data from bars
    ORB = 9:30-10:00 AM range
    """
    from datetime import time

    orb_start = time(9, 30)
    orb_end = time(10, 0)

    orb_bars = []
    for bar in bars_1min:
        bar_time = bar.timestamp.time()
        if orb_start <= bar_time < orb_end:
            orb_bars.append(bar)

    if len(orb_bars) < 20:  # Need at least 20/30 bars
        return None

    orb_high = max(b.high for b in orb_bars)
    orb_low = min(b.low for b in orb_bars)
    orb_range_pct = (orb_high - orb_low) / orb_low if orb_low > 0 else 0.0

    # Determine current price vs ORB
    current_price = bars_1min[-1].close
    if current_price > orb_high:
        position = 'ABOVE_HIGH'
    elif current_price < orb_low:
        position = 'BELOW_LOW'
    else:
        position = 'INSIDE_RANGE'

    return {
        'orb_high': orb_high,
        'orb_low': orb_low,
        'orb_range_pct': orb_range_pct * 100,
        'orb_bars': orb_bars,
        'current_vs_orb': position,
        'orb_avg_volume': sum(b.volume for b in orb_bars) / len(orb_bars)
    }

# En opportunity creation (only during ORB window 9:30-10:30):
now = datetime.now().time()
if time(9, 30) <= now <= time(10, 30):
    orb_data = extract_orb_data(play.bars_1min)
    if orb_data:
        opportunity['orb_data'] = orb_data
```

**Beneficio:** ORB Worker puede evaluar oportunidades sin re-fetching data

---

## 📈 Impacto Esperado de las Mejoras

### Métricas de Scoring
| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| Avg Score (sin patterns) | 65.0 | 65.0 | - |
| Avg Score (1 pattern) | 65.0 | 70.0 | +5 pts |
| Avg Score (2+ patterns) | 65.0 | 75.0 | +10 pts |
| Quality Score (STRONG setup) | 75.0 | 90.0 | +15 pts |

### Métricas de Risk Sizing
| Scenario | Antes | Después | Mejora |
|----------|-------|---------|--------|
| Base case | 1.2% | 1.2% | - |
| High quality (>80) | 1.2% | 1.5% | +25% size |
| 2+ patterns | 1.2% | 1.4% | +17% size |
| High quality + patterns | 1.2% | 1.7% | +42% size |
| High volatility (ATR>8%) | 1.2% | 1.0% | -17% size (protection) |

### Mejora en Edge
```
Escenario: High quality setup con 2+ patterns

Antes:
- Score: 65 → No pasa MIN_THRESHOLD (50) pero sin bonus
- Risk: 1.2% fijo
- Expected edge: +8%

Después:
- Score: 91 → +10 pattern bonus + quality bonus
- Risk: 1.7% adaptativo (+42% size)
- Expected edge: +12%

Resultado: +50% más capital en mejores setups = +50% más P&L en buenos trades
```

---

## 🎯 Priorización de Mejoras

### ALTA PRIORIDAD (hacer primero):
1. **Integrar ODS Classifier** → Pattern alignment (mayor impacto en scoring)
2. **Integrar Intraday Structure** → Completa pattern alignment (+10 bonus)
3. **Añadir ATR calculation** → Adaptive risk sizing funcional

### MEDIA PRIORIDAD (después):
4. **Mejorar Quality Score** → Mejor signal selection
5. **Añadir ORB metadata** → ORB Worker más eficiente

---

## 📝 Estimación de Tiempo

| Mejora | Tiempo | Complejidad |
|--------|--------|-------------|
| ODS Classifier | 1-2h | Media (ya existe, solo integrar) |
| Intraday Structure | 1-2h | Media (ya existe, solo integrar) |
| ATR Calculation | 30min | Baja (función simple) |
| Quality Score | 1h | Baja (lógica simple) |
| ORB Metadata | 1h | Baja (extracción de datos) |
| **TOTAL** | **4-6h** | - |

---

## ✅ Checklist de Implementación

### Pre-work:
- [ ] Revisar `core/ods_classifier.py` para entender API
- [ ] Revisar `core/intraday_structure_classifier.py` para entender API
- [ ] Verificar que ambos classifiers funcionan con bars_1min

### Implementation:
- [ ] Añadir imports de ODS y Intraday Structure classifiers
- [ ] Crear función `calculate_atr(bars, period=14)`
- [ ] Crear función `extract_orb_data(bars_1min)`
- [ ] Crear función `calculate_enhanced_quality_score()`
- [ ] Modificar `_scan_for_opportunities()` para integrar todo
- [ ] Añadir nuevos campos a opportunity dict

### Testing:
- [ ] Test con datos reales de IBKR
- [ ] Verificar que ODS data se calcula correctamente
- [ ] Verificar que Intraday Structure se calcula correctamente
- [ ] Verificar que ATR es razonable (3-10% range)
- [ ] Verificar que quality_score mejora con patterns
- [ ] Verificar que ORB data se extrae correctamente

### Integration Testing:
- [ ] Scanner → Trade Arbiter → Verificar pattern bonus se aplica
- [ ] Scanner → Workers → Verificar adaptive risk se calcula
- [ ] Scanner → ORB Worker → Verificar ORB data se usa

---

## 🚀 Próximos Pasos

**Opción 1: Implementar todas las mejoras ahora** (4-6h)
- Ventaja: Scanner completo y optimizado
- Desventaja: Tiempo de implementación largo

**Opción 2: Implementar solo alta prioridad** (2-3h)
- ODS + Intraday Structure + ATR
- Ventaja: 80% del beneficio en 50% del tiempo
- Desventaja: Deja quality score y ORB metadata para después

**Opción 3: Implementar incremental**
- Día 1: ODS Classifier (1-2h)
- Día 2: Intraday Structure (1-2h)
- Día 3: ATR + Quality Score (1-2h)
- Ventaja: Testing incremental, menos riesgo
- Desventaja: Takes longer overall

**Recomendación:** Opción 2 (alta prioridad) → Test → Opción 3 (resto incremental)
