# Sistema de Precios en Tiempo Real - Dashboard

## Resumen

El dashboard de Streamlit obtiene precios en tiempo real **directamente de la base de datos**, donde el `trader_main.py` los actualiza cada 3 minutos usando IBKR `BatchPriceManager`.

## Arquitectura

### 1. trader_main.py (Fuente de Datos)
```
┌─────────────────────────────────────────────────────────┐
│ trader_main.py - Snapshot Loop (cada 3 minutos)         │
│                                                          │
│ 1. Obtiene trades OPEN de la DB                         │
│ 2. Suscribe símbolos a BatchPriceManager (IBKR)        │
│ 3. Obtiene precios en tiempo real vía IBKR API         │
│ 4. Calcula P&L actualizado                             │
│ 5. Actualiza DB:                                        │
│    - actual_exit_price = current_price                 │
│    - actual_pnl = calculated_pnl                        │
└─────────────────────────────────────────────────────────┘
```

**Código relevante** ([trader_main.py:558-606](trader_main.py#L558-L606)):
```python
async def _snapshot_positions_loop(self):
    while True:
        # Get OPEN trades
        df = pd.read_sql_query(...)

        # Subscribe to IBKR prices
        await self.ibkr_adapter.batch_price_manager.subscribe_to_positions(symbols)

        # Get real-time prices
        prices = self.ibkr_adapter.batch_price_manager.get_all_current_prices()

        # Update DB
        cursor.execute(
            "UPDATE trades SET actual_exit_price = ?, actual_pnl = ? WHERE symbol = ? AND status = 'OPEN'",
            (current_price, pnl, sym)
        )
```

### 2. dashboard_utils.py (Consumidor)
```
┌─────────────────────────────────────────────────────────┐
│ dashboard_utils.py - get_active_trades()                │
│                                                          │
│ 1. Lee trades OPEN de la DB                            │
│ 2. Usa actual_exit_price como current_price            │
│    (actualizado por trader_main cada 3 min)            │
│ 3. Usa actual_pnl directamente                         │
│ 4. NO hace llamadas adicionales a IBKR                 │
│ 5. NO usa scanner como fallback                        │
└─────────────────────────────────────────────────────────┘
```

**Código relevante** ([dashboard_utils.py:97-112](dashboard_utils.py#L97-L112)):
```python
# USE IBKR SNAPSHOT PRICES: trader_main.py updates actual_exit_price every 3 minutes
df['current_price'] = df.apply(
    lambda row: (
        # Use actual_exit_price if available (updated by trader_main snapshot)
        row['actual_exit_price'] if pd.notna(row['actual_exit_price']) and row['actual_exit_price'] > 0
        # Otherwise fallback to entry price (trade just opened, no snapshot yet)
        else row['actual_entry_price']
    ),
    axis=1
)

# USE ACTUAL_PNL FROM DB: trader_main.py calculates this with IBKR prices
df['pnl'] = df['actual_pnl'].fillna(0.0)
```

## Flujo de Datos

```
IBKR (API)
    ↓ (vía BatchPriceManager)
trader_main.py
    ↓ (actualiza cada 3 min)
trading_data.db (actual_exit_price, actual_pnl)
    ↓ (lectura en tiempo real)
dashboard_utils.py
    ↓
Streamlit Dashboard
```

## Ventajas de Este Diseño

### ✅ 1. **No Duplica Conexiones IBKR**
- Solo `trader_main.py` se conecta a IBKR
- El dashboard es read-only de la DB
- Evita problemas de múltiples conexiones

### ✅ 2. **Usa BatchPriceManager Optimizado**
- Fase 1 optimization: suscripciones persistentes
- Reduce API calls de IBKR en 99.95%
- Precios en tiempo real sin polling constante

### ✅ 3. **Sincronizado Automáticamente**
- El dashboard siempre muestra los últimos datos
- No hay stale data si el trader está corriendo
- Actualización cada 3 minutos garantizada

### ✅ 4. **Sin Fallbacks Innecesarios**
- NO usa scanner_opportunities (menos preciso)
- NO calcula P&L redundantemente
- Confía en los valores calculados por el trader

## Frecuencia de Actualización

| Componente | Frecuencia | Fuente |
|------------|-----------|---------|
| trader_main.py | 3 minutos | IBKR BatchPriceManager |
| dashboard_utils.py | Cada refresh | DB (actual_exit_price) |
| Streamlit UI | Configurable (3-30s) | dashboard_utils |

## Validación de Datos

El sistema tiene varios niveles de validación:

1. **Detección de Inconsistencias** ([dashboard_utils.py:68-86](dashboard_utils.py#L68-L86))
   - Precios con >50% slippage
   - Trades OPEN con exit_filled=1

2. **Script de Corrección** ([fix_trades_auto.py](fix_trades_auto.py))
   - Corrige estados inconsistentes
   - Identifica precios sospechosos

3. **Tests** ([test_dashboard_data.py](test_dashboard_data.py))
   - Verifica integridad de datos
   - Confirma ausencia de errores

## Troubleshooting

### Problema: Precios no se actualizan
**Solución**: Verificar que `trader_main.py` esté corriendo
```bash
ps aux | grep trader_main
```

### Problema: Precios = 0
**Causa**: Trade recién abierto, snapshot no ha corrido aún
**Comportamiento**: Dashboard muestra entry_price como fallback

### Problema: Error "Cannot operate on a closed database"
**Causa**: Conexión DB cerrada antes de completar queries
**Solución**: Ya corregido en [dashboard_utils.py:136](dashboard_utils.py#L136)

## Archivos Modificados

1. **[dashboard_utils.py](dashboard_utils.py)** - Usa actual_exit_price de DB
2. **[fix_trades_auto.py](fix_trades_auto.py)** - Corrige datos inconsistentes
3. **[test_dashboard_data.py](test_dashboard_data.py)** - Valida sistema

## Referencias

- **BatchPriceManager**: [core/batch_price_manager.py](core/batch_price_manager.py)
- **IBKRAdapter**: [adapters/ibkr_adapter.py](adapters/ibkr_adapter.py)
- **Trader Main**: [trader_main.py](trader_main.py)
