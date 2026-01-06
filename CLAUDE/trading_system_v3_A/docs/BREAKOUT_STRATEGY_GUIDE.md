# Breakout Strategy Guide (Qullamaggie-style)

## 📋 Resumen

Esta es una implementación completa de la estrategia de breakouts de consolidación tipo Qullamaggie, diseñada para integrarse perfectamente con tu sistema de trading existente.

### Características Principales

✅ **Scanner EOD**: Escanea el mercado completo buscando top performers con setups de consolidación
✅ **Worker Swing**: Gestiona posiciones multi-día/semana con lógica de salida avanzada
✅ **Salidas Parciales**: Vende 1/3-1/2 de la posición después de 3-5 días
✅ **Trailing MA**: Trailing stop basado en MA de 10 o 20 días
✅ **Gestión de Riesgo**: Stop loss en LOD (lows of day) con máximo basado en ATR

---

## 🎯 Estrategia de Trading (Qullamaggie)

### Patrón de Setup

Los mejores ganadores históricos suelen moverse en "escalones":
1. **Gran movimiento** (30-100%+) en 1-3 meses
2. **Consolidación ordenada** con mínimos más altos (2 semanas - 2 meses)
3. **Breakout** con expansión de rango y volumen

### Selección de Universo

El scanner busca el **top 1-2% de performers** en estos timeframes:
- **1 mes**: +15% o más
- **3 meses**: +30% o más
- **6 meses**: +50% o más

### Entrada

- **Timing**: Opening range highs (1min, 5min, o 60min breakout)
- **Alternativa**: Breakout en gráfico diario
- **Confirmación**: Volumen > 1.5x promedio

### Stop Loss

- **Método primario**: Lows of day (LOD)
- **Límite**: Máximo 1x ATR o 7% (lo que sea menor)
- **Lógica**: Evitar que el R/R se descontrole

### Gestión de Posición

#### Salida Parcial (Días 3-5)
- Vender **40%** de la posición
- Requisito: Mínimo +5% de ganancia
- Después: **Mover stop a breakeven**

#### Trailing Stop (Resto de posición)
- **10-day MA**: Para acciones volátiles (ATR > 5%)
- **20-day MA**: Para acciones menos volátiles
- **Exit**: Primer **cierre** por debajo de la MA (no intraday)

#### Objetivo
- En mercados alcistas: **10-20x+ el riesgo inicial**
- Hold time típico: 10-30 días (puede extenderse mucho más)

---

## 🏗️ Arquitectura de Implementación

### Componentes Creados

```
trading_system_v3/
├── scanner/
│   └── swing/
│       └── breakout_scanner.py          ← Scanner EOD para breakouts
│
├── strategies/
│   └── swing_workers/
│       ├── breakout_worker.py           ← Worker de trading
│       └── breakout_exit_manager.py     ← Gestor de salidas (parciales + MA)
│
└── config.ini                            ← Configuración [BREAKOUT_STRATEGY]
```

### Flujo de Ejecución

```
16:05 ET (EOD) → BreakoutScanner escanea mercado
                 ↓
                 Filtra por performance (1M, 3M, 6M)
                 ↓
                 Analiza consolidación + MA relationship
                 ↓
                 Publica oportunidades vía Redis
                 ↓
trader_main.py → Recibe oportunidades
                 ↓
                 BreakoutWorker.evaluate_opportunity()
                 ↓
                 Si OK → execute_entry()
                 ↓
                 Monitor posición diariamente (EOD)
                 ↓
                 BreakoutExitManager.check_all_exits()
                 ↓
                 Exit: Partial → Breakeven → MA Trailing
```

---

## 🔧 Integración con el Sistema

### 1. Integrar el Scanner (scanner_main.py)

Añade el scanner de breakouts al scanner principal:

```python
# En scanner_main.py

from scanner.swing.breakout_scanner import BreakoutScanner

class IndependentScanner:
    def __init__(self, ...):
        # ... código existente ...

        # Añadir Breakout Scanner
        self.breakout_scanner = BreakoutScanner(
            ibkr_adapter=self.ibkr_adapter,
            logger=self.logger
        )

    async def _scan_for_opportunities(self):
        # ... código existente ...

        # EOD Scan (después de 16:00 ET)
        if self._should_run_eod_scan():
            try:
                # Breakout Scan
                breakout_opportunities = await self.breakout_scanner.scan_eod_breakouts()

                if breakout_opportunities:
                    self.logger.info(f"🎯 Found {len(breakout_opportunities)} breakout setups")
                    all_opportunities.extend(breakout_opportunities)

            except Exception as e:
                self.logger.error(f"Error in breakout scan: {e}")
```

### 2. Registrar el Worker (trader_main.py o worker_based_strategy_engine.py)

Registra el BreakoutWorker en el motor de workers:

```python
# En worker_based_strategy_engine.py

from strategies.swing_workers.breakout_worker import BreakoutWorker

class WorkerBasedStrategyEngine:
    def initialize(self):
        # ... código existente ...

        # Crear Breakout Worker
        breakout_enabled = getattr(self.config, 'breakout_strategy_enabled', True)
        if breakout_enabled:
            self.workers['breakout'] = BreakoutWorker(
                execution_engine=self.execution_engine,
                risk_manager=self.risk_manager,
                config=self.config
            )
            self.logger.info("✅ Breakout worker created")
```

### 3. Configurar Worker Capabilities

Añade capacidades del worker en `core/worker_capabilities_config.py`:

```python
'breakout': WorkerCapabilities(
    name='breakout',
    priority=5,  # Alta prioridad (estrategia probada históricamente)
    compatible_contexts=[
        MarketContext.TREND,      # Mejor en mercados trending
        MarketContext.MOMENTUM,   # Breakouts de momentum
    ],
    horizon=TradingHorizon.SWING,  # Multi-día/semana
    historical_winrate=0.65,  # 65% winrate estimado (Qullamaggie track record)
    avg_hold_time=600.0,  # ~25 días promedio (puede ser mucho más)
    min_confidence=60.0  # Confianza mínima requerida
),
```

---

## ⚙️ Configuración

La configuración se encuentra en `config.ini` bajo `[BREAKOUT_STRATEGY]`.

### Parámetros Clave

#### Universo y Filtros
```ini
min_1m_gain_pct = 15.0          # Top 5% en 1 mes
min_3m_gain_pct = 30.0          # Top 2% en 3 meses
min_6m_gain_pct = 50.0          # Top 1% en 6 meses
min_price = 5.0                 # Evita penny stocks
max_price = 100.0
min_avg_volume = 500000         # Liquidez mínima
```

#### Entrada
```ini
min_quality_score = 60.0        # Score mínimo del setup
min_volume_ratio = 1.5          # Volumen mínimo en breakout
max_distance_to_breakout_pct = 3.0  # Cercanía al breakout
```

#### Gestión de Riesgo
```ini
risk_per_trade = 100.0          # Riesgo fijo por trade
max_stop_pct = 7.0              # Stop máximo absoluto
```

#### Salidas
```ini
# Partial Profit
partial_profit_days_min = 3     # Día 3-5 para partial
partial_profit_days_max = 5
partial_profit_size = 0.40      # 40% de la posición
min_profit_for_partial = 5.0    # Min +5% ganancia

# Trailing
trailing_ma_period_fast = 10    # 10-day MA (volátiles)
trailing_ma_period_slow = 20    # 20-day MA (lentos)
```

---

## 🚀 Modo de Uso

### Activación

1. **Habilita la estrategia** en `config.ini`:
   ```ini
   [BREAKOUT_STRATEGY]
   enabled = true
   ```

2. **Ajusta el riesgo** según tu cuenta:
   ```ini
   risk_per_trade = 100.0          # $100 por trade
   max_position_value = 5000.0     # Máximo $5000 por posición
   ```

3. **Configura el capital swing** en `[SWING_TRADING]`:
   ```ini
   [SWING_TRADING]
   enabled = true
   swing_capital_percentage = 0.40  # 40% capital para swing
   day_capital_percentage = 0.60    # 60% para day trading
   ```

### Ejecución

#### Scanner (EOD)
```bash
# El scanner se ejecuta automáticamente después de las 16:00 ET
python scanner_main.py
```

#### Trader (Multi-day monitoring)
```bash
# El trader monitorea posiciones diariamente
python trader_main.py
```

### Monitoreo

- **Scanner**: Revisa logs en `logs/scanner.log`
- **Worker**: Revisa logs en `logs/breakout.log`
- **Trades**: Revisa TradeTally dashboard

---

## 📊 Métricas de Calidad del Setup

El scanner calcula un **Quality Score (0-100)** basado en:

| Factor | Puntos | Descripción |
|--------|--------|-------------|
| **Big Move** | 0-20 | Tamaño del movimiento previo (100%+ = 20 pts) |
| **Consolidación** | 0-20 | Duración y estructura (3-8 semanas ideal = 20 pts) |
| **Higher Lows** | 0-10 | Consolidación ordenada (+10 pts bonus) |
| **MA Relationship** | 0-15 | Surfing 10-day MA = 15 pts, 20-day = 10 pts |
| **Proximidad BO** | 0-15 | Distancia al breakout (<1% = 15 pts) |

**Score mínimo para entrada**: 60

---

## 🎓 Ejemplos de Setups Ideales

### Setup A+ (Score: 90+)
- Gran movimiento: +120% en 45 días
- Consolidación: 4 semanas, mínimos más altos
- Precio surfing 10-day MA
- A 0.5% del breakout
- Volumen: 2.5x promedio

### Setup B (Score: 70)
- Movimiento: +50% en 60 días
- Consolidación: 6 semanas, algo errática
- Precio cerca de 20-day MA
- A 2% del breakout
- Volumen: 1.6x promedio

---

## ⚠️ Consideraciones Importantes

### Contexto de Mercado
- ✅ **Mercado alcista**: Los breakouts pueden ir 10-20x+ el riesgo
- ⚠️ **Mercado lateral**: Breakouts tienden a fallar más
- ❌ **Mercado bajista**: Evitar esta estrategia

### Paciencia
- Esta estrategia requiere **paciencia** para dejar correr ganadores
- No te asustes con pullbacks normales al MA
- El objetivo es capturar el **gran movimiento** (no scalping)

### Gestión de Riesgo
- **Nunca** muevas el stop en contra (más lejos)
- Respeta el stop inicial (LOD o max %)
- Después de partial → Stop a breakeven (protección)

### Partial Profit
- Ayuda a **asegurar ganancias** tempranas
- Reduce **estrés psicológico**
- Permite dejar correr el resto sin presión

---

## 🔍 Troubleshooting

### El scanner no encuentra setups
- Verifica que `enabled = true` en config
- Revisa los thresholds (puede que estén muy estrictos)
- Comprueba logs: `tail -f logs/scanner.log`

### El worker no entra en trades
- Verifica `min_quality_score` (60 por defecto)
- Chequea `max_distance_to_breakout_pct` (3% por defecto)
- Revisa market regime (puede estar bloqueando entradas)

### Salidas muy tempranas
- Ajusta `trailing_ma_period_fast` a 20 si usas 10
- Incrementa `max_distance_from_ma_pct` en el scanner
- Revisa volatilidad (stocks muy volátiles activan MA más rápido)

### Salidas muy tardías
- Reduce `trailing_ma_period_slow` de 20 a 10
- Habilita partial profit más agresivo (días 2-4 en vez de 3-5)

---

## 📈 Optimización y Backtest

### Próximos Pasos

1. **Backtest Histórico**:
   - Usar `scientific_backtest` framework
   - Testear en diferentes regímenes de mercado
   - Optimizar thresholds de performance

2. **Paper Trading**:
   - Ejecutar en paper por 1-2 meses
   - Validar lógica de salidas parciales
   - Afinar quality score thresholds

3. **Live Trading**:
   - Empezar con riesgo bajo ($50 por trade)
   - Monitorear primeros 10-20 trades
   - Escalar gradualmente

---

## 📚 Referencias

- **Qullamaggie**: [Real Breakout Patterns](https://www.youtube.com/watch?v=y6AwxhPRQt8)
- **Mark Minervini**: *Trade Like a Stock Market Wizard* (VCP patterns)
- **William O'Neil**: *How to Make Money in Stocks* (CANSLIM)

---

## 🤝 Contribuciones y Mejoras

### Posibles Mejoras Futuras

1. **Multi-timeframe Analysis**: Añadir confirmación en weekly chart
2. **Sector Rotation**: Filtrar por sectores en rotación
3. **Relative Strength**: Comparar con SPY performance
4. **News Integration**: Boost score si hay catalizador
5. **Fundamentals**: Filtrar por institucional ownership, earnings growth

---

## 📝 Changelog

### v1.0 (Initial Release)
- ✅ Breakout Scanner con filtros de top performers
- ✅ Breakout Worker con entrada en OR highs
- ✅ Breakout Exit Manager (parciales + MA trailing)
- ✅ Configuración completa en config.ini
- ✅ Integración con sistema swing existente

---

**¡Buena suerte con tu trading! 🚀📈**
