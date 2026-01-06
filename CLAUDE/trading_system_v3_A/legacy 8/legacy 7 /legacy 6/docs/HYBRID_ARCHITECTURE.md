# Arquitectura Híbrida TradeTally

## Resumen

TradeTally ahora utiliza una **arquitectura híbrida** que elimina la duplicación de datos entre SQLite y PostgreSQL.

### Antes (Arquitectura Duplicada)
```
trading_data.db (SQLite)          tradetally (PostgreSQL)
├─ trades (20+ campos)      →     ├─ trades (20+ campos) [DUPLICADO]
├─ ohlc_data                      ├─ users
└─ executions                     ├─ comments
                                  └─ attachments
```
**Problema**: Todos los campos del trade se sincronizaban de SQLite a PostgreSQL, duplicando información.

### Ahora (Arquitectura Híbrida)
```
trading_data.db (SQLite)          tradetally (PostgreSQL)
├─ trades (FUENTE DE VERDAD)      ├─ trade_metadata (SOLO 3-4 campos)
├─ ohlc_data                      │  ├─ trade_id (FK a SQLite)
└─ executions                     │  ├─ user_id
                                  │  ├─ is_public
                                  │  ├─ notes
                                  │  └─ tags
                                  ├─ users
                                  ├─ trade_comments
                                  └─ attachments
```
**Solución**: PostgreSQL solo guarda metadata específica de TradeTally. Los datos del trade permanecen en SQLite.

## Ventajas

1. ✅ **Sin duplicación**: Cada dato se almacena una vez
2. ✅ **Sincronización simple**: Solo 3-4 campos en vez de 20+
3. ✅ **Separación clara**: SQLite = datos de trading, PostgreSQL = datos sociales
4. ✅ **Menos errores**: No hay desincronización entre bases de datos
5. ✅ **Performance**: Menos datos a sincronizar

## Componentes

### 1. Base de Datos

#### SQLite (trading_data.db)
**Propósito**: Fuente de verdad para todos los datos de trading

**Tablas principales**:
- `trades`: Todos los trades con precios, PnL, estrategia, etc.
- `ohlc_data`: Datos de velas para gráficos
- `executions`: Ejecuciones individuales de cada trade

#### PostgreSQL (tradetally)
**Propósito**: Datos específicos de TradeTally (social, usuarios, metadata)

**Tablas principales**:
- `trade_metadata`: **NUEVA** - Solo metadata (trade_id, user_id, is_public, notes, tags)
- `users`: Usuarios de TradeTally
- `trade_comments`: Comentarios en trades públicos
- `attachments`: Archivos adjuntos

### 2. Backend Service

#### hybridTradeService.js
Servicio que **merge** datos de ambas bases de datos:

```javascript
const trade = await hybridTradeService.getTradeById(tradeId, userId);

// Devuelve:
{
  // De SQLite:
  trade_id: "AAPL_2024_001",
  symbol: "AAPL",
  entry_price: 150.25,
  exit_price: 152.50,
  pnl: 225.00,
  ... // todos los campos del trade

  // De PostgreSQL:
  metadata: {
    is_public: true,
    notes: "Entrada perfecta en soporte",
    tags: ["scalp", "momentum"]
  }
}
```

**Métodos principales**:
- `getUserTrades(userId, filters)`: Lista de trades del usuario
- `getPublicTrades(filters, limit, offset)`: Trades públicos para feed
- `getTradeById(tradeId, userId)`: Trade individual con metadata
- `saveTradeMetadata(tradeId, userId, metadata)`: Guardar metadata
- `getUserTradeStats(userId)`: Estadísticas calculadas desde SQLite

### 3. API Endpoints

Los endpoints principales ahora usan `hybridTradeController`:

```javascript
// GET /api/trades - Lista de trades del usuario
router.get('/', authenticate, hybridTradeController.getUserTrades);

// GET /api/trades/public - Trades públicos
router.get('/public', optionalAuth, hybridTradeController.getPublicTrades);

// GET /api/trades/:id - Trade específico
router.get('/:id', optionalAuth, hybridTradeController.getTrade);

// PUT /api/trades/:id - Actualizar metadata
router.put('/:id', authenticate, hybridTradeController.updateTrade);
```

### 4. Sincronización

#### tradetally_sync_hybrid.py
Script simplificado que sincroniza **SOLO metadata**:

```bash
# Dry run (ver qué se sincronizaría)
python tradetally_sync_hybrid.py --dry-run

# Sincronizar
python tradetally_sync_hybrid.py --user-id "UUID-DEL-USUARIO"
```

**Variables de entorno necesarias**:
```bash
SQLITE_DB_PATH=/path/to/trading_data.db
TRADETALLY_USER_ID=uuid-del-usuario
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=tradetally
PG_USER=postgres
PG_PASSWORD=tu-password
```

**Qué hace**:
1. Lee `trade_id` de trades cerrados en SQLite
2. Verifica cuáles ya están en `trade_metadata`
3. Inserta los nuevos en PostgreSQL (solo trade_id + user_id)

## Migración

### Paso 1: Crear tabla trade_metadata
```bash
cd tradetally/backend
psql -d tradetally -f migrations/058_create_trade_metadata.sql
```

### Paso 2: Sincronizar trades existentes
```bash
cd integrations/tradetally/core
python tradetally_sync_hybrid.py --user-id "TU-UUID"
```

### Paso 3: Reiniciar backend
```bash
cd tradetally/backend
npm start
```

## Flujo de Datos

### Lectura de Trades
```
1. Usuario hace GET /api/trades
2. hybridTradeController.getUserTrades()
3. hybridTradeService:
   a. Query a PostgreSQL: SELECT trade_id FROM trade_metadata WHERE user_id = ?
   b. Query a SQLite: SELECT * FROM trades WHERE trade_id IN (...)
   c. Merge: Combina datos de SQLite + metadata de PostgreSQL
4. Devuelve array de trades completos
```

### Actualización de Metadata
```
1. Usuario hace PUT /api/trades/:id con { notes, tags, is_public }
2. hybridTradeController.updateTrade()
3. hybridTradeService.saveTradeMetadata():
   - UPSERT en trade_metadata (PostgreSQL)
4. Frontend actualiza vista
```

### Nuevo Trade (desde sistema de trading)
```
1. Sistema de trading guarda en SQLite (trading_data.db)
2. Telegram notificación opcional
3. Usuario ejecuta sync: python tradetally_sync_hybrid.py
4. Se crea registro en trade_metadata
5. Trade ahora visible en TradeTally
```

## Consideraciones

### ¿Qué pasa si borro metadata?
- `DELETE` en trade_metadata NO borra el trade de SQLite
- Solo oculta el trade de TradeTally
- Para volverlo a ver, ejecuta sync nuevamente

### ¿Cómo hacer un trade público?
```javascript
PUT /api/trades/:tradeId
{
  "is_public": true,
  "notes": "Gran entrada en breakout",
  "tags": ["breakout", "high-confidence"]
}
```

### ¿Puedo editar el trade?
- **NO** desde TradeTally (solo metadata)
- Para editar datos del trade (precio, cantidad, etc.), edita en SQLite
- La próxima lectura reflejará los cambios

### Performance
- ✅ Lectura rápida: JOIN entre PostgreSQL (metadata) y SQLite (datos)
- ✅ Escritura rápida: Solo metadata se actualiza
- ✅ Sync eficiente: Solo nuevos trades, no todos

## Archivos Modificados

### Backend
- ✅ `migrations/058_create_trade_metadata.sql` - Nueva tabla
- ✅ `migrations/059_migrate_existing_trades.sql` - Helper functions
- ✅ `services/hybridTradeService.js` - **NUEVO** servicio híbrido
- ✅ `controllers/hybridTrade.controller.js` - **NUEVO** controlador
- ✅ `routes/trade.routes.js` - Actualizado para usar hybrid controller

### Integración
- ✅ `integrations/tradetally/core/tradetally_sync_hybrid.py` - **NUEVO** sync simplificado

### Frontend
- ℹ️ Sin cambios necesarios (API compatible)

## Testing

### 1. Test Conexiones
```bash
python tradetally_sync_hybrid.py --dry-run
```

### 2. Test Backend
```bash
curl -H "Authorization: Bearer TOKEN" http://localhost:3000/api/trades
```

### 3. Test Frontend
```
1. Login en TradeTally
2. Ver lista de trades
3. Abrir detalle de un trade
4. Editar notes/tags
5. Marcar como público
6. Ver en feed público
```

## Rollback

Si necesitas volver a la arquitectura anterior:

```bash
# 1. Restaurar tabla trades completa
psql -d tradetally -f migrations/backup/old_trades_table.sql

# 2. Restaurar rutas originales
git checkout routes/trade.routes.js

# 3. Reiniciar backend
npm start
```

## Próximos Pasos

- [ ] Migrar `attachments` a usar trade_id en vez de UUID
- [ ] Agregar índices adicionales si hay problemas de performance
- [ ] Considerar cache para queries frecuentes
- [ ] Dashboard de estadísticas de sync

## Soporte

Si encuentras problemas:
1. Verifica logs del backend: `pm2 logs backend`
2. Verifica conexiones: `python tradetally_sync_hybrid.py --dry-run`
3. Revisa PostgreSQL: `psql -d tradetally -c "SELECT COUNT(*) FROM trade_metadata"`
4. Revisa SQLite: `sqlite3 trading_data.db "SELECT COUNT(*) FROM trades WHERE status='CLOSED'"`
