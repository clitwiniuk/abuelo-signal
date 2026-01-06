# Volume Absorption Breakout Worker - Reglas Cuantificadas

## EDGE FUNDAMENTAL
Detecta acumulación institucional ANTES del breakout mediante análisis de absorción de volumen en zonas clave.

**NO requiere noticias como catalizador obligatorio** - El edge está en la microestructura del mercado.

---

## MODOS DE OPERACIÓN

### MODO 1: Scanner-Assisted (RECOMENDADO - Mayor Win Rate)
```
Input: Tickers del scanner con quality_score > 70
Ventaja: Catalizador + Absorción = Mayor probabilidad
Oportunidades: 1-3 por día
Win Rate estimado: 50-55%
```

### MODO 2: Standalone (OPCIONAL - Más Oportunidades)
```
Input: Top 200 smallcaps por volumen del día
Ventaja: Detecta acumulación "oscura" antes de noticias
Oportunidades: 3-6 por día
Win Rate estimado: 42-48%
```

**Configuración sugerida**:
- 70% capital en Modo 1 (scanner-assisted)
- 30% capital en Modo 2 (standalone exploratorio)

---

## REGLAS DE ENTRADA (TODAS deben cumplirse)

### 1. FILTRO INICIAL (Pre-selección)
```
✓ Precio > $2.00 y < $20.00
✓ Volumen promedio diario > 200,000 acciones
✓ Spread bid/ask < 3% del precio
✓ Gap del día < 15% (evitar extremos)
```

### 2. ZONA DE ACUMULACIÓN (Detectar absorción)
```
✓ Precio en rango de 2% durante últimas 10 velas (1min)
✓ Volumen últimas 10 velas > 1.8x promedio volumen últimas 30 velas
✓ Precio dentro de ±0.5% del VWAP
✓ Al menos 2 "absorption events" en últimas 15 velas:

  ABSORPTION EVENT =
    - Vela con volumen > 2x promedio
    - Cuerpo vela < 40% del rango (mucha indecisión)
    - Precio cierra en top 30% del rango (compradores ganando)
```

### 3. BREAKOUT TRIGGER
```
✓ Precio > máximo últimas 15 velas + 0.15%
✓ Volumen vela breakout > 3x promedio últimas 10 velas
✓ VWAP slope positivo (VWAP ahora > VWAP 5 velas atrás)
✓ Precio > VWAP en momento de breakout
```

### 4. TIME & SALES CONFIRMATION (últimos 2 minutos)
```
✓ Número de trades > 20 (actividad real)
✓ Bloques grandes (>500 acciones) en ask: mínimo 2
✓ Último precio = ask (compradores agresivos)
✓ NO hay bloques >2000 acciones en bid (no distribución)
```

### 5. TIMING
```
✓ Hora: 10:00 AM - 3:30 PM ET
✓ NO primeros 30min después de noticias
✓ NO últimos 30min del día
```

---

## REGLAS DE SALIDA

### STOP LOSS (el que ocurra primero)
```
• Fixed: -2.5% desde entrada
• Dinámico: Mínimo de últimas 5 velas - 0.3%
• Breakdown: Precio < VWAP - 0.8%
```

### TAKE PROFIT (objetivo realista para smallcaps)
```
• TP MÍNIMO: +10% (base para INTRADAY horizon)
• Quality multiplier:
  - Setup A+ (quality 85-100): TP = 10% × 3.0 = 30%
  - Setup A (quality 75-84): TP = 10% × 2.0 = 20%
  - Setup B+ (quality 65-74): TP = 10% × 1.5 = 15%
  - Setup B (quality < 65): TP = 10% × 1.0 = 10%
• Cap máximo: 80% de distancia a resistencia
```

### TRAILING STOP
```
• Activa cuando PnL > +6.0% (INTRADAY activation)
• Distancia: 3.0% desde peak (INTRADAY distance)
• Captura runners que excedan TP inicial
```

### TIME STOP
```
• Máximo 4 horas en posición (INTRADAY horizon)
• Permite capturar movimientos institucionales completos
```

---

## GESTIÓN DE RIESGO

### CAPITAL
```
• Riesgo por trade: 1.5% del capital
• Máximo 2 posiciones simultáneas este worker
• Máximo 25% capital total en este worker
```

### EXCLUSIONES
```
✗ NO operar si ya hay 2 pérdidas consecutivas hoy
✗ NO operar si drawdown diario > -4%
✗ NO operar símbolos con noticias en últimas 2 horas
```

---

## PARÁMETROS TÉCNICOS (para código)

```python
# Filtros iniciales
MIN_PRICE = 2.0
MAX_PRICE = 20.0
MIN_AVG_VOLUME = 200000
MAX_SPREAD_PCT = 0.03
MAX_GAP_PCT = 0.15

# Zona de acumulación
CONSOLIDATION_RANGE_PCT = 0.02  # 2% range
CONSOLIDATION_LOOKBACK = 10     # velas
VOLUME_RATIO_CONSOLIDATION = 1.8
VWAP_TOLERANCE = 0.005          # 0.5%
MIN_ABSORPTION_EVENTS = 2

# Absorption event detection
ABSORPTION_VOLUME_MULT = 2.0
ABSORPTION_BODY_PCT = 0.40      # cuerpo < 40% rango
ABSORPTION_CLOSE_TOP_PCT = 0.30 # cierre en top 30%

# Breakout
BREAKOUT_BUFFER = 0.0015        # 0.15%
BREAKOUT_VOLUME_MULT = 3.0
VWAP_SLOPE_MIN = 0.0001         # VWAP creciente

# Time & Sales
TS_LOOKBACK_MINUTES = 2
TS_MIN_TRADES = 20
TS_MIN_LARGE_BLOCKS = 2
TS_LARGE_BLOCK_SIZE = 500
TS_DISTRIBUTION_BLOCK_SIZE = 2000

# Timing
TRADING_START_HOUR = 10.0       # 10:00 AM ET
TRADING_END_HOUR = 15.5         # 3:30 PM ET
NEWS_BLACKOUT_HOURS = 0.5       # 30 min

# Exits
STOP_LOSS_FIXED_PCT = 0.025     # 2.5%
STOP_LOSS_BUFFER = 0.003        # 0.3%
VWAP_BREAKDOWN_PCT = 0.008      # 0.8%

TP1_PCT = 0.012                 # 1.2%
TP1_SIZE = 0.40                 # 40%
TP2_PCT = 0.020                 # 2.0%
TP2_SIZE = 0.30                 # 30%
TP3_PCT = 0.035                 # 3.5%
TP3_SIZE = 0.30                 # 30%

TRAILING_ACTIVATION = 0.015     # 1.5%
TRAILING_DISTANCE = 0.006       # 0.6%

MAX_HOLD_MINUTES = 90
TIME_STOP_THRESHOLD_MINUTES = 45
TIME_STOP_MIN_PNL = 0.005       # 0.5%

# Risk
RISK_PER_TRADE = 0.015          # 1.5%
MAX_POSITIONS = 2
MAX_CAPITAL_PCT = 0.25          # 25%
MAX_CONSECUTIVE_LOSSES = 2
MAX_DAILY_DRAWDOWN = 0.04       # 4%
```

---

## CHECKLIST DE ENTRADA (para debugging)

```
PRE-SELECCIÓN:
[ ] Precio $2-$20
[ ] Volume >200k avg
[ ] Spread <3%
[ ] Gap <15%

ACUMULACIÓN:
[ ] Rango 2% últimas 10 velas
[ ] Volumen 1.8x+ últimas 10 vs 30
[ ] Precio ±0.5% VWAP
[ ] ≥2 absorption events

BREAKOUT:
[ ] Precio > máx 15 velas +0.15%
[ ] Volumen 3x+ promedio
[ ] VWAP slope positivo
[ ] Precio > VWAP

TIME & SALES:
[ ] >20 trades en 2min
[ ] ≥2 bloques grandes en ask
[ ] Último precio = ask
[ ] Sin bloques >2000 en bid

TIMING:
[ ] 10:00-15:30 ET
[ ] Sin noticias recientes
[ ] No es EOD
```

---

## VENTAJAS vs ESTRATEGIAS ORIGINALES

1. **vs Momentum Breakout**:
   - ✅ Espera acumulación ANTES del breakout (mejor precio)
   - ✅ No depende de order book completo (IBKR limitación)

2. **vs Reversión por Agotamiento**:
   - ✅ Va con el momentum, no contra él (mejor win rate)
   - ✅ Usa absorción como confirmación (no solo RSI extremo)

3. **Edge adicional**:
   - Detecta "smart money" acumulando en zona
   - Entra en inicio de momentum, no al final
   - R:R mínimo 1:1.4, objetivo 1:2.8

---

## BACKTEST ESPERADO (estimado)

```
Win Rate: 45-52%
Avg Win: +2.2%
Avg Loss: -1.8%
Profit Factor: 1.5-2.0
Max Drawdown: -8%
Trades/día: 1-3
```
