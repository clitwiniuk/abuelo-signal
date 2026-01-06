# Checklist de Integración - Breakout Strategy

## ✅ COMPLETADO

- ✅ Scanner creado: [scanner/swing/breakout_scanner.py](scanner/swing/breakout_scanner.py)
- ✅ Worker creado: [strategies/swing_workers/breakout_worker.py](strategies/swing_workers/breakout_worker.py)
- ✅ Exit Manager creado: [strategies/swing_workers/breakout_exit_manager.py](strategies/swing_workers/breakout_exit_manager.py)
- ✅ Configuración añadida: [config.ini](config.ini) sección `[BREAKOUT_STRATEGY]`
- ✅ Guía de uso creada: [BREAKOUT_STRATEGY_GUIDE.md](BREAKOUT_STRATEGY_GUIDE.md)

---

## ⚠️ PENDIENTE DE INTEGRACIÓN

### 1. Integrar Scanner en `scanner_main.py`

**Archivo**: `scanner_main.py`

**Cambios necesarios**:

```python
# Añadir import al inicio del archivo
from scanner.swing.breakout_scanner import BreakoutScanner

# En la clase IndependentScanner.__init__()
def __init__(self, ...):
    # ... código existente ...

    # Añadir Breakout Scanner
    self.breakout_scanner = BreakoutScanner(
        ibkr_adapter=self.ibkr_adapter,
        logger=self.logger
    )
    self.logger.info("📈 Breakout Scanner initialized")

# En el método _scan_for_opportunities() - sección EOD
async def _scan_for_opportunities(self):
    # ... código existente ...

    # Añadir escaneo EOD (después de las 16:00 ET)
    current_time = datetime.now(pytz.timezone('US/Eastern'))

    # EOD Breakout Scan (16:05 ET)
    if current_time.hour >= 16 and current_time.minute >= 5:
        try:
            self.logger.info("🔍 Running EOD Breakout Scan...")
            breakout_opportunities = await self.breakout_scanner.scan_eod_breakouts()

            if breakout_opportunities:
                self.logger.info(f"🎯 Found {len(breakout_opportunities)} breakout setups")
                all_opportunities.extend(breakout_opportunities)
        except Exception as e:
            self.logger.error(f"Error in breakout scan: {e}")
```

**Ubicación exacta**: Busca la sección donde se hace el escaneo EOD (alrededor de las 16:00 ET) y añade el breakout scanner ahí.

---

### 2. Registrar Worker en `trader_main.py` o `worker_based_strategy_engine.py`

**Opción A - En trader_main.py** (si se gestiona desde ahí):

```python
# Añadir import
from strategies.swing_workers.breakout_worker import BreakoutWorker

# En la sección donde se crean los swing workers
breakout_enabled = self.config.getboolean('BREAKOUT_STRATEGY', 'enabled', fallback=True)
if breakout_enabled:
    self.breakout_worker = BreakoutWorker(
        execution_engine=self.execution_engine,
        risk_manager=self.risk_manager,
        config=self.config
    )
    self.logger.info("✅ Breakout worker created")
```

**Opción B - En worker_based_strategy_engine.py** (más probable):

```python
# Añadir import al inicio
from strategies.swing_workers.breakout_worker import BreakoutWorker

# En el método initialize() o donde se registran los workers
def initialize(self):
    # ... código existente ...

    # Crear Breakout Worker
    breakout_enabled = getattr(self.config, 'BREAKOUT_STRATEGY', {}).get('enabled', True)
    if breakout_enabled:
        self.workers['breakout'] = BreakoutWorker(
            execution_engine=self.execution_engine,
            risk_manager=self.risk_manager,
            config=self.config
        )
        self.logger.info("✅ Breakout worker created")
```

---

### 3. Configurar Worker Capabilities (Opcional pero Recomendado)

**Archivo**: `core/worker_capabilities_config.py`

**Añadir**:

```python
'breakout': WorkerCapabilities(
    name='breakout',
    priority=5,  # Alta prioridad (estrategia probada)
    compatible_contexts=[
        MarketContext.TREND,      # Mejor en mercados trending
        MarketContext.MOMENTUM,   # Breakouts de momentum
    ],
    horizon=TradingHorizon.SWING,  # Multi-día/semana
    historical_winrate=0.65,  # 65% winrate estimado
    avg_hold_time=600.0,  # ~25 días promedio
    min_confidence=60.0  # Confianza mínima
),
```

---

## 📋 VERIFICACIÓN POST-INTEGRACIÓN

Una vez integrados los componentes, verifica:

### 1. Scanner
```bash
# Revisar que el scanner se inicializa correctamente
tail -f logs/scanner.log | grep -i "breakout"

# Debería aparecer:
# "📈 Breakout Scanner initialized"
# "🔍 Running EOD Breakout Scan..."
```

### 2. Worker
```bash
# Revisar que el worker se crea correctamente
tail -f logs/trader.log | grep -i "breakout"

# Debería aparecer:
# "✅ Breakout worker created"
# "📈🔥 Breakout Worker (Qullamaggie) initialized"
```

### 3. Configuración
```bash
# Verificar que la config se lee correctamente
grep -A 5 "BREAKOUT_STRATEGY" config.ini

# Debería mostrar:
# [BREAKOUT_STRATEGY]
# enabled = true
# ...
```

---

## 🚀 ACTIVACIÓN PASO A PASO

### Paso 1: Backup
```bash
# Hacer backup del sistema antes de modificar
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
git add .
git commit -m "feat: Add Qullamaggie Breakout Strategy (pre-integration)"
```

### Paso 2: Integrar Scanner
1. Abre `scanner_main.py`
2. Añade el import del BreakoutScanner
3. Inicializa el scanner en `__init__()`
4. Añade el escaneo EOD en `_scan_for_opportunities()`

### Paso 3: Integrar Worker
1. Abre `worker_based_strategy_engine.py` (o `trader_main.py`)
2. Añade el import del BreakoutWorker
3. Registra el worker en el método `initialize()`

### Paso 4: Test
```bash
# Reiniciar el scanner (si está corriendo)
pkill -f scanner_main.py
python scanner_main.py &

# Reiniciar el trader (si está corriendo)
pkill -f trader_main.py
python trader_main.py &

# Monitorear logs
tail -f logs/scanner.log logs/trader.log
```

### Paso 5: Validar
- ✅ Scanner aparece en logs: "Breakout Scanner initialized"
- ✅ Worker aparece en logs: "Breakout worker created"
- ✅ No hay errores de import o configuración
- ✅ El sistema sigue funcionando con los workers existentes

---

## 🔧 TROUBLESHOOTING

### Error: "Module not found: breakout_scanner"
**Solución**: Verifica que el archivo existe en `scanner/swing/breakout_scanner.py` y que el import es correcto.

### Error: "Config section not found: BREAKOUT_STRATEGY"
**Solución**: Verifica que `config.ini` tiene la sección `[BREAKOUT_STRATEGY]` con `enabled = true`.

### El scanner no encuentra setups
**Opción 1**: Los thresholds son muy estrictos (baja `min_quality_score` a 50)
**Opción 2**: No hay top performers en el mercado actual (normal en mercados laterales)
**Opción 3**: Yahoo Finance API tiene problemas (revisa logs para errores)

### El worker no entra en trades
**Opción 1**: `max_distance_to_breakout_pct` muy bajo (sube a 5%)
**Opción 2**: Market regime bloqueando entradas (revisa adaptive thresholds)
**Opción 3**: No hay capital disponible para swing (ajusta `swing_capital_percentage`)

---

## 📊 MONITOREO

### Logs Clave

**Scanner**:
```bash
# Ver escaneos EOD
tail -f logs/scanner.log | grep "EOD Breakout Scan"

# Ver setups encontrados
tail -f logs/scanner.log | grep "BREAKOUT SETUP"
```

**Worker**:
```bash
# Ver entradas
tail -f logs/trader.log | grep "Breakout Entry"

# Ver salidas parciales
tail -f logs/trader.log | grep "Partial Profit"

# Ver trailing stops
tail -f logs/trader.log | grep "MA"
```

---

## 📈 PRÓXIMOS PASOS

Una vez integrado y funcionando:

1. **Backtest**: Ejecutar backtest histórico para validar parámetros
2. **Paper Trading**: Mínimo 1 mes en paper antes de live
3. **Optimización**: Ajustar thresholds según resultados
4. **Escalado**: Incrementar `risk_per_trade` gradualmente

---

## 📞 AYUDA

Si necesitas ayuda con la integración:
1. Revisa [BREAKOUT_STRATEGY_GUIDE.md](BREAKOUT_STRATEGY_GUIDE.md)
2. Compara con la implementación de `ShortSqueezeWorker` (estructura similar)
3. Revisa los logs en detalle para identificar el problema específico

---

**Fecha**: 2025-12-20
**Status**: ⚠️ Pendiente de Integración
**Prioridad**: Alta (estrategia clave para mercados de medias/grandes caps)
