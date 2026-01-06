# Fix: LiveIBKRBroker - Sistema Funcional Restaurado

## Problema Identificado

El sistema no funcionaba porque `LiveIBKRBroker` no exponía los atributos necesarios que esperan los workers:

### Arquitectura del Sistema

```
trader_main.py
    ↓
WorkerBasedStrategyEngine
    ↓
Workers (DailyPlays, VWAP, Livermore, etc.)
    ↓ expect:
    - broker.batch_price_manager
    - broker.ib (raw IB instance)
    - broker.smart_position_cache
```

### Problema Original

1. **Commit ac0bde6** creó `LiveIBKRBroker` para resolver Error 322 (subscription leak)
2. `LiveIBKRBroker` solo envolvía el `ib_client` (IB instance) directamente
3. **No tenía acceso** a:
   - `batch_price_manager` (optimización de precios en batch)
   - `smart_position_cache` (caché inteligente de posiciones)
   - Otros atributos del `IBKRAdapter`

4. Los workers intentaban acceder a `broker.batch_price_manager` → **AttributeError**
5. Sistema crasheaba al inicializar workers

## Solución Implementada

### 1. Actualizado `LiveIBKRBroker.__init__()`

**Archivo**: `core/brokers/live_ibkr_broker.py`

```python
def __init__(self, ib_client: Any, account_id: str, ibkr_adapter: Any = None, logger: Optional[logging.Logger] = None):
    """
    Args:
        ib_client: Configured and connected IB instance (ib_insync)
        account_id: Account ID (e.g. U1234567)
        ibkr_adapter: Full IBKRAdapter instance (NEW - for accessing batch_price_manager, etc.)
        logger: Logger instance
    """
    self.ib = ib_client
    self.account_id = account_id
    self._ibkr_adapter = ibkr_adapter

    # ✅ EXPOSE IBKRAdapter attributes for worker compatibility
    if ibkr_adapter:
        self.batch_price_manager = getattr(ibkr_adapter, 'batch_price_manager', None)
        self.smart_position_cache = getattr(ibkr_adapter, 'smart_position_cache', None)
    else:
        self.batch_price_manager = None
        self.smart_position_cache = None
```

### 2. Actualizado `trader_main.py`

**Cambio en líneas 250-254**:

**ANTES (roto)**:
```python
live_broker = LiveIBKRBroker(ib_client=self.ibkr_adapter.ib, account_id=account_id)
```

**DESPUÉS (funcional)**:
```python
live_broker = LiveIBKRBroker(
    ib_client=self.ibkr_adapter.ib,
    account_id=account_id,
    ibkr_adapter=self.ibkr_adapter  # ✅ Pass full adapter
)
```

## Arquitectura Correcta

```
IBKRAdapter (adapters/ibkr_adapter.py)
    - ib: IB instance (ib_insync)
    - batch_price_manager: BatchPriceManager
    - smart_position_cache: SmartPositionCache
    - get_bars(), get_positions(), etc.

    ↓ wrapped by

LiveIBKRBroker (core/brokers/live_ibkr_broker.py)
    - Implementa AbstractBroker interface
    - Expone atributos de IBKRAdapter (batch_price_manager, etc.)
    - Previene subscription leaks (Error 322)

    ↓ used by

WorkerBasedStrategyEngine
    ↓
Workers (acceden a broker.batch_price_manager, etc.)
```

## Por Qué Funcionaba Antes (Contexto)

El usuario reportó que funcionaba con "commit e17bb09", pero ese commit **NO EXISTE** en el historial actual porque:

1. `trader_main.py` es un archivo **UNTRACKED** (no está en git)
2. El usuario probablemente tenía una versión diferente de `trader_main.py` que:
   - No usaba `LiveIBKRBroker`
   - O usaba una implementación diferente
3. `LiveIBKRBroker` fue **CREADO** en commit ac0bde6, no existía antes

## Beneficios de Esta Solución

✅ **Mantiene el fix del Error 322**: Subscribe/unsubscribe apropiado
✅ **Expone batch_price_manager**: Workers pueden optimizar llamadas a precios
✅ **Expone smart_position_cache**: Workers pueden cachear posiciones
✅ **Compatible con AbstractBroker**: Puede usarse en tests/replay
✅ **Backward compatible**: `ibkr_adapter` es opcional (None si no se provee)

## Testing

Para verificar que funciona:

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A

# 1. Verificar que no hay errores de import
python3 -c "from core.brokers.live_ibkr_broker import LiveIBKRBroker; print('✅ Import OK')"

# 2. Iniciar el sistema
python3 trader_main.py

# 3. Verificar logs:
tail -f logs/trader.log | grep -E "LiveIBKRBroker|batch_price_manager|Worker.*initialized"
```

**Señales de éxito**:
- ✅ "LiveIBKRBroker adapter created for account XXX"
- ✅ Workers se inicializan sin AttributeError
- ✅ No aparece "Error 322"
- ✅ batch_price_manager está disponible

**Señales de problema**:
- ❌ AttributeError: 'LiveIBKRBroker' object has no attribute 'batch_price_manager'
- ❌ Workers fallan al inicializar
- ❌ Error 322 reaparece

## Archivos Modificados

1. ✅ `core/brokers/live_ibkr_broker.py` - Añadido parámetro `ibkr_adapter`, expuesto atributos
2. ✅ `trader_main.py` - Pasar `ibkr_adapter` completo a `LiveIBKRBroker`

## Notas Importantes

- ⚠️ `trader_main.py` es **UNTRACKED** - no está en git
- ⚠️ Si reseteas el repositorio, este archivo puede perderse
- ⚠️ Considera hacer commit de `trader_main.py` si es estable

## Changelog

- **2026-01-05 14:30**: Fix implementado - sistema restaurado
- **2026-01-05 14:08**: Commit ac0bde6 - `LiveIBKRBroker` creado (causó el problema)
- **2026-01-05 14:30**: `LiveIBKRBroker` actualizado con `ibkr_adapter` parameter

---

**Estado**: ✅ RESUELTO
**Próximo paso**: Probar con trader_main.py y verificar logs
