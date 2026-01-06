# TradeTally - API-First Architecture

## 🏗️ Arquitectura

La nueva arquitectura utiliza **REST API** en lugar de acceso directo a PostgreSQL, proporcionando:

- ✅ Mejor separación de responsabilidades
- ✅ Más robusto y fácil de mantener
- ✅ Escalable y preparado para múltiples clientes
- ✅ Monitoreo en tiempo real
- ✅ Sin problemas de tipos UUID

## 📊 Flujo de Datos

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   Trading       │         │   TradeTally     │         │   TradeTally    │
│   System        │──HTTP──>│   REST API       │────────>│   PostgreSQL    │
│   (SQLite)      │         │   (Node.js)      │         │   (Metadata)    │
└─────────────────┘         └──────────────────┘         └─────────────────┘
  Source of Truth           Validation & Auth            Only Metadata
```

### Datos Almacenados

**SQLite (trading_data.db)**
- ✅ Todos los datos de trading
- ✅ Ejecuciones, precios, comisiones
- ✅ Estrategias, símbolos, timeframes
- ✅ Análisis de rendimiento
- **Fuente de verdad única**

**PostgreSQL (TradeTally)**
- Metadata solamente:
  - `trade_id` (referencia a SQLite)
  - `user_id` (owner)
  - `is_public` (visibilidad)
  - `notes` (notas de trading)
  - `tags` (categorización)

## 🔌 API Endpoints

### Base URL
```
http://localhost:8001
```

### 1. Sync Status
```http
GET /api/v1/sync-metadata/status
Headers:
  X-API-Key: tt_live_xxxxx

Response:
{
  "success": true,
  "status": {
    "total_metadata": 748,
    "public_count": 0,
    "last_sync": "2025-10-24T14:30:37.843Z"
  }
}
```

### 2. Sync Single Metadata
```http
POST /api/v1/sync-metadata/metadata
Headers:
  X-API-Key: tt_live_xxxxx
  Content-Type: application/json

Body:
{
  "trade_id": "unique_trade_id",
  "is_public": false,
  "notes": "Great entry, poor exit",
  "tags": ["momentum", "breakout"]
}

Response:
{
  "success": true,
  "metadata": { ... }
}
```

### 3. Bulk Sync Metadata
```http
POST /api/v1/sync-metadata/metadata/bulk
Headers:
  X-API-Key: tt_live_xxxxx
  Content-Type: application/json

Body:
{
  "trades": [
    {
      "trade_id": "trade_001",
      "is_public": false,
      "notes": "...",
      "tags": []
    },
    ...
  ]
}

Response:
{
  "success": true,
  "synced": 100,
  "errors": 0,
  "results": [...],
  "errors": []
}
```

### 4. Delete Metadata
```http
DELETE /api/v1/sync-metadata/metadata/:trade_id
Headers:
  X-API-Key: tt_live_xxxxx

Response:
{
  "success": true,
  "deleted": { ... }
}
```

## 🔑 Autenticación

Usa **API Keys** en lugar de JWT para sincronización:

```python
headers = {
    'X-API-Key': 'tt_live_xxxxxxxxxxxxx',
    'Content-Type': 'application/json'
}
```

### Generar API Key

1. Login en TradeTally web
2. Ir a Settings → API Keys
3. Create new API key
4. Guardar en `.env.local`:
   ```
   TRADETALLY_API_KEY=tt_live_xxxxx
   ```

## 🐍 Cliente Python

### Instalación
```bash
# No requiere psycopg2 ni dependencias de PostgreSQL
pip install requests python-dotenv
```

### Uso Básico
```python
from integrations.tradetally.core.tradetally_api_client import TradeTallyAPIClient

# Inicializar cliente
client = TradeTallyAPIClient(
    api_key="tt_live_xxxxx",
    base_url="http://localhost:8001",
    db_path="trading_data.db"
)

# Test connection
if client.test_connection():
    print("✅ Connected!")

# Sync all trades
result = client.sync_all_trades()
print(f"Synced: {result['synced']} / {result['total']}")
```

### CLI
```bash
# Test connection
python integrations/tradetally/cli/tradetally_cli_new.py test

# Check status
python integrations/tradetally/cli/tradetally_cli_new.py status

# Sync all trades
python integrations/tradetally/cli/tradetally_cli_new.py sync

# Sync only today's trades
python integrations/tradetally/cli/tradetally_cli_new.py sync --today

# Show config
python integrations/tradetally/cli/tradetally_cli_new.py config
```

## 🔧 Configuración

### `.env.local`
```bash
# TradeTally API
TRADETALLY_API_KEY=tt_live_xxxxxxxxxxxxx
TRADETALLY_BASE_URL=http://localhost:8001
TRADETALLY_USER_ID=your-uuid-here

# Trading System
TRADING_DB_PATH=trading_data.db
```

## 📈 Ventajas vs Arquitectura Anterior

| Aspecto | Antigua (PostgreSQL Directo) | Nueva (API REST) |
|---------|------------------------------|------------------|
| **Acoplamiento** | Alto | Bajo |
| **Mantenimiento** | Difícil | Fácil |
| **Problemas UUID** | Sí ❌ | No ✅ |
| **Validación** | Manual | Automática |
| **Autenticación** | Por DB | Por API Key |
| **Escalabilidad** | Limitada | Alta |
| **Monitoreo** | Difícil | Fácil |
| **Dependencias** | psycopg2, pg | solo requests |

## 🚀 Migración desde Arquitectura Antigua

### 1. Actualizar .env.local
```bash
# Remover (ya no se usan)
#PG_HOST=localhost
#PG_PORT=5432
#PG_DATABASE=carlos
#PG_USER=carlos
#PG_PASSWORD=

# Mantener/agregar
TRADETALLY_API_KEY=tt_live_xxxxx
TRADETALLY_BASE_URL=http://localhost:8001
```

### 2. Usar nuevo CLI
```bash
# Antiguo (deprecated)
python -m integrations.tradetally.cli.tradetally_cli sync

# Nuevo (recommended)
python integrations/tradetally/cli/tradetally_cli_new.py sync
```

### 3. Actualizar imports en código
```python
# Antiguo
from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration

# Nuevo
from integrations.tradetally.core.tradetally_api_client import TradeTallyAPIClient
```

## 🔍 Debugging

### Ver logs del servidor
```bash
cd tradetally/backend
npm start
# Logs aparecerán en consola
```

### Probar endpoints manualmente
```bash
# Test status
curl -H "X-API-Key: tt_live_xxxxx" \
  http://localhost:8001/api/v1/sync-metadata/status

# Sync single trade
curl -X POST \
  -H "X-API-Key: tt_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{"trade_id":"test_001","is_public":false}' \
  http://localhost:8001/api/v1/sync-metadata/metadata
```

## 📝 Notas Importantes

1. **SQLite es la fuente de verdad** - PostgreSQL solo tiene metadata
2. **API Key requerida** - Sin key, no hay acceso
3. **Backend debe estar corriendo** - `npm start` en backend/
4. **Sin acceso directo a DB** - Todo a través de API
5. **Metadata ligera** - Solo lo esencial en PostgreSQL

## 🎯 Próximos Pasos

1. ✅ Refactorizar a arquitectura API-First
2. ✅ Eliminar dependencias PostgreSQL directas
3. ✅ Crear cliente Python REST
4. ✅ Actualizar CLI
5. 📋 Agregar WebSockets para sync en tiempo real
6. 📋 Implementar cache en cliente
7. 📋 Agregar retry logic con exponential backoff

## 📚 Referencias

- [TradeTally Backend API](../../tradetally/backend/src/routes/v1/sync-metadata.routes.js)
- [Python API Client](../core/tradetally_api_client.py)
- [CLI Tool](../cli/tradetally_cli_new.py)
