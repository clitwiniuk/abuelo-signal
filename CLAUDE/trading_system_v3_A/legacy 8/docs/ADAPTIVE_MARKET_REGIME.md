# Sistema de Adaptación Automática de Mercado

## 🎯 Objetivo

Sistema que detecta automáticamente el régimen de mercado actual (bull, bear, volátil, pánico) y ajusta los parámetros de entrada de los workers en tiempo real, sin intervención manual.

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────┐
│   MarketRegimeDetector (Singleton)              │
│   - Analiza SPY cada 15 minutos                 │
│   - Detecta régimen: BULL/BEAR/CHOPPY/PANIC    │
│   - Calcula métricas: trend, vol, liquidity     │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│   AdaptiveThresholdManager (Singleton)          │
│   - Traduce régimen → parámetros concretos     │
│   - Proporciona thresholds adaptativos         │
│   - Cache invalidación automática              │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│   BaseWorkerLogic (Todos los workers)          │
│   - Consulta thresholds adaptativos            │
│   - Fallback a Friday-only si sistema falla   │
│   - Sin modificar lógica core del worker      │
└─────────────────────────────────────────────────┘
```

## 📊 Regímenes Detectados

### 1. **BULL_HIGH_LIQUIDITY** 🐂💧
- **Condiciones:** SPY > +0.5%, Liquidez > 70
- **Ajustes:**
  - VWAP tolerance: 2.5% (relajado)
  - Min quality: 45 (relajado)
  - Pattern completion: 20% (entrada temprana)
  - Daily trades: 1.3x (más agresivo)
- **Filosofía:** Capturar momentum fuerte

### 2. **BULL_LOW_LIQUIDITY** 🐂
- **Condiciones:** SPY > +0.3%, Liquidez < 60
- **Ajustes:**
  - VWAP tolerance: 3.0% (muy permisivo)
  - Min quality: 40 (viernes-style)
  - Volume ratio: 0.7x (bajo volumen OK)
- **Filosofía:** Adaptación a viernes tarde / días lentos

### 3. **BEAR_HIGH_VOL** 🐻⚡
- **Condiciones:** SPY < -1.0%, Volatilidad > 2.0%
- **Ajustes:**
  - VWAP tolerance: 1.0% (muy estricto)
  - Min quality: 70 (solo perfectos)
  - Pattern completion: 40% (más desarrollado)
  - Daily trades: 0.5x (muy conservador)
- **Filosofía:** Supervivencia, solo setups perfectos

### 4. **BEAR_LOW_VOL** 🐻
- **Condiciones:** SPY < -0.5%, Volatilidad < 1.5%
- **Ajustes:**
  - VWAP tolerance: 1.5% (conservador)
  - Min quality: 60
  - Daily trades: 0.7x
- **Filosofía:** Consolidación post-caída, cauteloso

### 5. **CHOPPY** 🌊
- **Condiciones:** |SPY| < 0.3%, Volatilidad < 1.5%
- **Ajustes:**
  - VWAP tolerance: 1.8% (selectivo)
  - Min quality: 55
  - Daily trades: 0.8x
- **Filosofía:** Lateral, solo setups claros

### 6. **PANIC** 🚨
- **Condiciones:** SPY < -2.0%, Volatilidad > 3.0%
- **Ajustes:**
  - **ENTRADAS DESACTIVADAS** ❌
  - Position size: 0.0x
- **Filosofía:** Protección capital, sin trading

## 🔧 Uso en Workers

### Automático (Recomendado)

Los workers heredan de `BaseWorkerLogic` y obtienen thresholds adaptativos automáticamente:

```python
# En validate_vwap_strength() - BaseWorkerLogic
try:
    from core.adaptive_threshold_manager import get_adaptive_threshold_manager
    threshold_mgr = get_adaptive_threshold_manager()
    vwap_tolerance_pct = threshold_mgr.get_vwap_price_tolerance()
except Exception:
    # Fallback: Friday-only manual adjustment
    vwap_tolerance_pct = 2.0
    if weekday == 4:  # Friday
        vwap_tolerance_pct = 3.5
```

### Manual (Workers Específicos)

Si un worker necesita thresholds custom:

```python
from core.adaptive_threshold_manager import get_adaptive_threshold_manager

threshold_mgr = get_adaptive_threshold_manager()
thresholds = threshold_mgr.get_thresholds()

# Acceso individual
vwap_tol = threshold_mgr.get_vwap_price_tolerance()
min_quality = threshold_mgr.get_min_quality_score()
pos_size_mult = threshold_mgr.get_position_size_multiplier()

# Check si permitir entradas
if not threshold_mgr.should_allow_entries():
    return False  # Panic mode, skip entry
```

## 📱 Monitoreo con Telegram

### Comando: `/regime`

Muestra régimen actual y thresholds adaptados:

```
🌍 MARKET REGIME REPORT
========================================

🐂💧 BULL HIGH LIQUIDITY
Confidence: 85%

📊 Market Metrics:
• SPY Trend: +0.75%
• Volatility: 1.2%
• Volume Ratio: 1.4x
• Liquidity Score: 78/100
• Sentiment: +75/100

✅ Entries: ENABLED

🎚️ Adaptive Thresholds:
• VWAP Tolerance: 2.5%
• VWAP Trend: -0.15%
• Min Quality: 45
• Min Pattern: 20%
• Position Size: 1.2x
• Daily Trades: 1.3x

⚖️ Risk Mode: 🟢 Aggressive (favorable conditions)

🕒 Updated: 14:35:22 ET
```

## 🚀 Inicialización

El sistema se inicializa automáticamente en `trader_main.py`:

```python
# ADAPTIVE MARKET REGIME SYSTEM
from core.market_regime_detector import get_market_regime_detector

regime_detector = get_market_regime_detector()
regime_detector.set_ibkr_adapter(ibkr_adapter)
await regime_detector.start()  # Updates every 15 minutes

# Initial detection
await regime_detector.update_market_regime()
```

## 📈 Métricas Calculadas

### 1. SPY Trend
- % cambio desde apertura
- Rango: -5% a +5% típicamente

### 2. Volatility (ATR-based)
- ATR 14-period normalizado
- Rango: 0.5% (calma) a 4%+ (pánico)

### 3. Volume Ratio
- Volumen reciente (15min) vs promedio (45min)
- Rango: 0.5x (bajo) a 3.0x (alto)

### 4. Liquidity Score (0-100)
- 60 pts: Volume ratio * 30
- 40 pts: Spread tightness

### 5. Sentiment Score (-100 a +100)
- Base: SPY trend * 10
- Penalización: -20 si volatility > 2%

## 🔄 Actualización Automática

- **Frecuencia:** Cada 15 minutos
- **Datos:** SPY 1-min bars (última hora)
- **Cache:** Invalidación automática al cambiar régimen
- **Fallback:** Si falla, mantiene último régimen conocido

## 🛡️ Sistema de Fallback

Si el sistema adaptativo falla (ej: SPY data no disponible):

1. **Intenta usar cache** del último régimen válido
2. Si no hay cache, usa **Friday-only adaptation**:
   - Lunes-Jueves: Thresholds estrictos
   - Viernes: Thresholds relajados
3. Logs warning pero continúa operando

## ⚙️ Configuración Avanzada

### Ajustar Frecuencia de Actualización

En `market_regime_detector.py`:

```python
self.update_interval_seconds = 900  # Default: 15 min
# Cambiar a 5 min para mercados muy volátiles:
self.update_interval_seconds = 300
```

### Ajustar Baseline Thresholds

En `adaptive_threshold_manager.py`:

```python
self.baseline_thresholds = WorkerThresholds(
    vwap_price_tolerance_pct=2.0,  # Ajustar default
    vwap_trend_tolerance_pct=0.0,
    min_quality_score=50.0,
    ...
)
```

### Custom Regime Adjustments

Modificar `_calculate_adaptive_thresholds()` para ajustar comportamiento por régimen.

## 📊 Ejemplos de Escenarios

### Escenario 1: Lunes Bajista con Alta Volatilidad

```
Input:
- SPY: -1.5%
- Volatility: 2.8%
- Volume: 1.8x

Detección: BEAR_HIGH_VOL (confidence: 80%)

Thresholds:
- VWAP tolerance: 1.0% (muy estricto)
- Min quality: 70 (solo perfectos)
- Position size: 0.5x (muy conservador)

Resultado: Solo 1-2 entradas perfectas vs 5-8 en día normal
```

### Escenario 2: Viernes Tarde, Alcista Débil

```
Input:
- SPY: +0.4%
- Volatility: 1.1%
- Volume: 0.8x (bajo)
- Liquidity: 55

Detección: BULL_LOW_LIQUIDITY (confidence: 75%)

Thresholds:
- VWAP tolerance: 3.0% (muy permisivo)
- Min quality: 40 (relajado)
- Volume ratio: 0.7x (bajo OK)

Resultado: Captura setups en mercado lento, 3-4 entradas
```

### Escenario 3: Martes Rally Fuerte

```
Input:
- SPY: +1.2%
- Volatility: 1.0%
- Volume: 2.5x
- Liquidity: 85

Detección: BULL_HIGH_LIQUIDITY (confidence: 90%)

Thresholds:
- VWAP tolerance: 2.5% (relajado)
- Min quality: 45 (permisivo)
- Position size: 1.2x (agresivo)
- Daily trades: 1.3x

Resultado: Máxima captura de momentum, 8-10 entradas
```

## 🧪 Testing

### Test Manual

```python
from core.market_regime_detector import get_market_regime_detector
from core.adaptive_threshold_manager import get_adaptive_threshold_manager

# Force update
detector = get_market_regime_detector()
await detector.update_market_regime()

# Check regime
conditions = detector.get_current_regime()
print(f"Regime: {conditions.regime.value}")
print(f"SPY: {conditions.spy_trend:+.2f}%")

# Check thresholds
threshold_mgr = get_adaptive_threshold_manager()
summary = threshold_mgr.get_regime_summary()
print(summary)
```

## 📝 Logs a Revisar

```bash
# Inicialización
grep "Market regime detection started" logs/trader.log

# Actualizaciones
grep "Analyzing market regime\|Market Regime:" logs/trader.log

# Thresholds adaptados
grep "Thresholds adapted for" logs/trader.log

# Verificar si workers usan adaptive
grep "ADAPTIVE\|adaptive_threshold" logs/worker_*.log
```

## 🎓 Filosofía del Sistema

1. **Supervivencia primero:** En mercados peligrosos (PANIC, BEAR_HIGH_VOL), priorizar protección de capital

2. **Oportunismo inteligente:** En mercados favorables (BULL_HIGH_LIQUIDITY), maximizar captura de momentum

3. **Adaptación continua:** No esperar al lunes para ajustar, detectar cambios intraday

4. **Degradación elegante:** Si falla, usar Friday-only fallback, nunca dejar sistema sin umbrales

5. **Transparencia:** Logs claros, comando Telegram para visibilidad en tiempo real

## 🚨 Troubleshooting

### Problema: Sistema no detecta régimen

**Síntomas:**
```
⚠️ No market conditions - using baseline thresholds
```

**Solución:**
1. Verificar que IBKR adapter está conectado
2. Verificar que SPY data está disponible
3. Revisar logs: `grep "Could not fetch SPY bars" logs/trader.log`

### Problema: Thresholds no se aplican

**Síntomas:**
Workers usan valores hardcoded, no adaptativos

**Solución:**
1. Verificar que `trader_main.py` inicializa regime detector
2. Verificar import en `base_worker_logic.py`:
   ```python
   from core.adaptive_threshold_manager import get_adaptive_threshold_manager
   ```
3. Revisar logs de workers para ver si usan fallback

### Problema: Demasiadas entradas en PANIC mode

**Síntomas:**
System trading agresivamente cuando debería estar detenido

**Solución:**
1. Verificar que `should_allow_entries()` se llama en workers
2. Verificar detección de PANIC:
   ```bash
   grep "PANIC MODE" logs/trader.log
   ```
3. Ajustar threshold de PANIC en `market_regime_detector.py` si es necesario

## 📚 Referencias

- [market_regime_detector.py](../core/market_regime_detector.py) - Detector de régimen
- [adaptive_threshold_manager.py](../core/adaptive_threshold_manager.py) - Manager de thresholds
- [base_worker_logic.py](../strategies/workers/base_worker_logic.py) - Integración en workers
- [trader_main.py](../trader_main.py) - Inicialización del sistema
