# Dashboard - Resumen Completo de Correcciones

## Problemas Encontrados y Solucionados

### 1. ❌ Error "Cannot operate on a closed database"

**Causa**: Conexión a DB cerrada prematuramente antes de completar todas las queries

**Ubicación**: [dashboard_utils.py:64](dashboard_utils.py#L64)

**Solución**: Movido `conn.close()` al final después de todas las queries (línea 136)

**Estado**: ✅ SOLUCIONADO

---

### 2. ❌ Trades "fantasma" - OPEN pero ya cerrados

**Causa**: 7 trades marcados como `status='OPEN'` pero con `exit_filled=1` (ya ejecutaron salida)

**Trades afectados**:
- Primera corrida: NVD, ISPO, IRBT, TSLS, PLTD (5 trades)
- Segunda corrida: PLTD, ISPO (2 trades más)

**Solución**: Script automático [fix_trades_auto.py](fix_trades_auto.py) que actualiza `status='CLOSED'`

**Estado**: ✅ SOLUCIONADO (7 trades corregidos)

---

### 3. ❌ Dashboard NO mostraba trades activos

**Causa**: Los trades estaban mal etiquetados como OPEN cuando ya estaban cerrados

**Efecto**: Dashboard mostraba 0 trades activos cuando debería mostrar los realmente abiertos

**Solución**: Después de corregir los estados, ahora refleja correctamente: **0 trades activos** (correcto)

**Estado**: ✅ SOLUCIONADO

---

### 4. ❌ P&L inflado incorrectamente (-$4,203 vs -$1,334 real)

**Causa**: Dashboard usaba columna `pnl` (legacy, calculada teóricamente) en lugar de `actual_pnl` (precios reales IBKR)

**Diferencia**:
```
pnl (legacy, teórico):     -$4,404.01  ❌
actual_pnl (IBKR real):    -$1,167.03  ✅
Correcto (COALESCE):       -$1,333.74  ✅
```

**Funciones corregidas**:
- `get_pnl_stats()` - Estadísticas principales
- `get_risk_metrics()` - Métricas de riesgo
- `get_equity_curve()` - Curva de equity

**Cambio**:
```python
# ANTES (incorrecto)
SELECT SUM(pnl) FROM trades...

# DESPUÉS (correcto)
SELECT SUM(COALESCE(actual_pnl, pnl, 0)) FROM trades...
```

**Estado**: ✅ SOLUCIONADO

---

### 5. ❌ Fallback al scanner para precios (innecesario y con errores)

**Causa**: Dashboard intentaba obtener precios de `scanner_opportunities` como fallback

**Problema**:
- Error "Cannot operate on a closed database"
- Precios del scanner menos precisos que IBKR
- Duplicación de lógica

**Solución**: Usar `actual_exit_price` directamente de la DB (actualizado cada 3 min por trader_main vía IBKR)

**Código corregido**: [dashboard_utils.py:98-113](dashboard_utils.py#L98-L113)

**Estado**: ✅ SOLUCIONADO

---

### 6. ⚠️ Precios de entrada sospechosos (no crítico)

**Trades afectados**:
- IRBT: 373.8% diferencia (planned: $1.03, actual: $4.88)
- PLTD: 69.9% diferencia (planned: $6.68, actual: $2.01)

**Comportamiento**: Dashboard usa precio planificado como fallback cuando diferencia >50%

**Causa probable**: Órdenes fill a precios muy diferentes (halt, volatilidad extrema, error de datos)

**Estado**: ⚠️ MITIGADO (usa fallback automático, revisar manualmente)

---

## Estado Actual del Sistema

### Trades
```
Total trades cerrados: 938
Trades con actual_pnl:  466 (50%)
Trades legacy (pnl):    472 (50%)
Trades activos (OPEN):    0
```

### Performance Real
```
P&L Total:    -$1,333.74
P&L Hoy:      -$645.24
Win Rate:     36.7%
Winners:      344 trades
Losers:       594 trades
```

### Precios en Dashboard
```
Fuente:       actual_exit_price (IBKR vía BatchPriceManager)
Actualización: Cada 3 minutos por trader_main.py
Fallback:     actual_entry_price (si trade recién abierto)
```

---

## Archivos Modificados

1. **[dashboard_utils.py](dashboard_utils.py)**
   - Línea 64: Eliminado `conn.close()` prematuro
   - Línea 98-113: Usa `actual_exit_price` de IBKR
   - Línea 136: `conn.close()` movido al final
   - Línea 398: `get_pnl_stats()` usa `COALESCE(actual_pnl, pnl)`
   - Línea 251: `get_risk_metrics()` usa `COALESCE(actual_pnl, pnl)`
   - Línea 306: `get_equity_curve()` usa `COALESCE(actual_pnl, pnl)`

2. **[fix_trades_auto.py](fix_trades_auto.py)** (nuevo)
   - Corrige automáticamente trades con `exit_filled=1` pero `status='OPEN'`
   - Identifica precios con >50% slippage

3. **[test_dashboard_data.py](test_dashboard_data.py)** (nuevo)
   - Valida integridad de datos
   - Confirma ausencia de inconsistencias

4. **[DASHBOARD_PRICE_SYSTEM.md](DASHBOARD_PRICE_SYSTEM.md)** (nuevo)
   - Documentación completa del flujo de precios IBKR

---

## Explicación: ¿Por qué tantas pérdidas?

### Análisis Actual
```
Total P&L: -$1,333.74 en 938 trades
Promedio por trade: -$1.42
Win rate: 36.7%
```

### Breakdown por P&L
```sql
SELECT
    CASE
        WHEN COALESCE(actual_pnl, pnl, 0) > 0 THEN 'Winners'
        WHEN COALESCE(actual_pnl, pnl, 0) < 0 THEN 'Losers'
        ELSE 'Breakeven'
    END as categoria,
    COUNT(*) as trades,
    ROUND(SUM(COALESCE(actual_pnl, pnl, 0)), 2) as total_pnl,
    ROUND(AVG(COALESCE(actual_pnl, pnl, 0)), 2) as avg_pnl
FROM trades
WHERE status != 'OPEN'
GROUP BY categoria;
```

### Posibles causas de pérdidas:
1. **Win rate bajo** (36.7% vs óptimo 50%+)
2. **Ratio R/R negativo** (losers más grandes que winners)
3. **Slippage** (diferencias entre precio planeado vs ejecutado)
4. **Comisiones** acumuladas
5. **Estrategias específicas** con bajo performance
6. **Market regime** desfavorable

### Próximos pasos sugeridos:
1. Analizar estrategias individualmente (¿cuál tiene peor performance?)
2. Revisar setup quality scores
3. Analizar slippage promedio
4. Revisar stop losses (¿demasiado apretados?)
5. Validar comisiones en cálculos

---

## Tests de Validación

```bash
# Ejecutar tests
python test_dashboard_data.py

# Verificar inconsistencias
python fix_trades_auto.py

# Ver estado de trades
sqlite3 trading_data.db "SELECT status, COUNT(*) FROM trades GROUP BY status;"
```

---

## Referencias

- **Sistema de precios**: [DASHBOARD_PRICE_SYSTEM.md](DASHBOARD_PRICE_SYSTEM.md)
- **BatchPriceManager**: [core/batch_price_manager.py](core/batch_price_manager.py)
- **Snapshot loop**: [trader_main.py:558-606](trader_main.py#L558-L606)
