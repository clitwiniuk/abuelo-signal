# TradeTally Local - Guía Completa de Funcionamiento

## 📋 Índice
- [Descripción General](#descripción-general)
- [Arquitectura del Sistema](#arquitectura-del-sistema)
- [Procesos de Inicio](#procesos-de-inicio)
- [Procesos de Cierre](#procesos-de-cierre)
- [Configuración](#configuración)
- [Sincronización de Trades](#sincronización-de-trades)
- [Gestión de Usuarios](#gestión-de-usuarios)
- [Troubleshooting](#troubleshooting)
- [Comandos Útiles](#comandos-útiles)

## 📖 Descripción General

TradeTally Local es una instancia auto-hospedada del sistema TradeTally que permite:
- **Control total** de tus datos de trading
- **Sincronización automática** con tu sistema de trading
- **Dashboard personalizado** para análisis de trades
- **Sin límites** de API externa
- **Funcionamiento offline**

### Componentes Principales
- **Backend**: API Node.js (puerto 8001)
- **Frontend**: Aplicación React/Vite (puerto 5173)
- **Base de datos**: SQLite local
- **Sincronización**: Integración con trading_data.db

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    TradeTally Local                         │
├─────────────────────────────────────────────────────────────┤
│  Frontend (React/Vite)                                      │
│  http://localhost:5173                                      │
│  ├── Dashboard                                              │
│  ├── Trade Management                                       │
│  └── User Authentication                                    │
├─────────────────────────────────────────────────────────────┤
│  Backend API (Node.js/Express)                             │
│  http://localhost:8001/api                                 │
│  ├── /auth (login, register, config)                       │
│  ├── /trades (CRUD operations)                             │
│  └── /users (user management)                              │
├─────────────────────────────────────────────────────────────┤
│  Base de Datos (SQLite)                                    │
│  tradetally/backend/database.db                            │
│  ├── users                                                 │
│  ├── trades                                                │
│  └── sessions                                              │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│              Trading System v3                             │
│  ├── trading_data.db (fuente de trades)                    │
│  ├── config.ini (configuración TradeTally)                 │
│  └── sync_tradetally_local.py (sincronización)             │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Procesos de Inicio

### Método 1: Scripts de Conveniencia (Recomendado)

#### Inicio Automático
```bash
# Doble-click en Finder o desde terminal:
./Start_TradeTally.command
```

**Lo que hace internamente:**
1. Detecta si Docker está disponible
2. Si no hay Docker, usa modo local (Node.js)
3. Configura variables de entorno:
   - `REGISTRATION_MODE=open`
   - `EMAIL_HOST=` (sin verificación email)
   - `PORT=8001`
4. Inicia backend en puerto 8001
5. Inicia frontend en puerto 5173
6. Muestra PIDs de los procesos

#### Verificación de Estado
```bash
./tradetally/manage_tradetally.sh status
```

### Método 2: Manual

#### Backend
```bash
cd tradetally/backend
export REGISTRATION_MODE=open
export EMAIL_HOST=
export PORT=8001
npm install
npm start
```

#### Frontend
```bash
cd tradetally/frontend
export VITE_API_URL=http://localhost:8001/api
npm install
npm run dev -- --port 5173
```

### Verificación de Funcionamiento

#### 1. Health Check del Backend
```bash
curl http://localhost:8001/api/health
# Respuesta esperada: {"status":"OK","timestamp":"...","services":{"database":"OK"}}
```

#### 2. Configuración de Registro
```bash
curl http://localhost:8001/api/auth/config
# Respuesta esperada: {"registrationMode":"open","emailVerificationEnabled":false,"allowRegistration":true}
```

#### 3. Frontend Accesible
- Navegar a: `http://localhost:5173`
- Debe mostrar la página de login/registro

## 🛑 Procesos de Cierre

### Método 1: Script de Conveniencia
```bash
# Doble-click en Finder o desde terminal:
./Stop_TradeTally.command
```

**Lo que hace:**
1. Ejecuta `./tradetally/manage_tradetally.sh stop`
2. Mata todos los procesos (backend y frontend)
3. Limpia archivos PID
4. Confirma cierre exitoso

### Método 2: Manual
```bash
# Detener servicios
./tradetally/manage_tradetally.sh stop

# O matar procesos específicos
kill $(cat tradetally/backend.pid)
kill $(cat tradetally/frontend.pid)

# Limpiar archivos PID
rm tradetally/*.pid
```

### Verificación de Cierre
```bash
# Verificar que no hay procesos corriendo
lsof -i :8001  # Backend
lsof -i :5173  # Frontend

# Verificar estado
./tradetally/manage_tradetally.sh status
```

## ⚙️ Configuración

### Archivo Principal: `config.ini`
```ini
[TRADETALLY]
api_key = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Token JWT del usuario
base_url = http://localhost:8001/api                    # URL del backend local
```

### Variables de Entorno Importantes
- `REGISTRATION_MODE=open`: Permite registro sin aprobación
- `EMAIL_HOST=`: Desactiva verificación por email
- `PORT=8001`: Puerto del backend
- `VITE_API_URL=http://localhost:8001/api`: URL para el frontend

### Archivos de Configuración
```
tradetally/
├── frontend/.env.local          # Variables del frontend
├── backend/src/config/          # Configuración del backend
└── manage_tradetally.sh         # Script de gestión
```

## 🔄 Sincronización de Trades

### Proceso Automático
- **Horario**: Diario a las 16:30 EST
- **Fuente**: `trading_data.db`
- **Destino**: TradeTally local
- **Estado**: `tradetally_sync_state.json`

### Sincronización Manual
```bash
# Script personalizado (recomendado)
python sync_tradetally_local.py

# Usando el sistema interno
python -c "
import asyncio
from core.service_locator import get_service_locator

async def sync():
    sl = get_service_locator()
    await sl.get_or_create_tradetally_service()
    svc = sl.get_service('tradetally_service')
    result = svc.manual_sync()
    print(result)
    await sl.cleanup()

asyncio.run(sync())
"
```

### Resetear Sincronización
```bash
# Para volver a sincronizar todos los trades
rm tradetally_sync_state.json
python sync_tradetally_local.py
```

### Flujo de Sincronización
1. **Conexión**: Verifica conectividad con API local
2. **Autenticación**: Usa token JWT del config.ini
3. **Extracción**: Lee trades CLOSED de trading_data.db
4. **Filtrado**: Solo trades no sincronizados previamente
5. **Transformación**: Convierte formato local → TradeTally
6. **Envío**: POST a /api/trades en lotes
7. **Estado**: Actualiza tradetally_sync_state.json

## 👥 Gestión de Usuarios

### Crear Usuario
```bash
# Via API
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"tu@email.com","username":"tuuser","password":"tupass","fullName":"Tu Nombre"}'

# Via Frontend
# Navegar a http://localhost:5173/register
```

### Login y Obtener Token
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"tu@email.com","password":"tupass"}'

# Respuesta incluye: {"token":"eyJhbGciOiJIUzI1NiIs..."}
```

### Actualizar Token en Config
```bash
# Copiar token de la respuesta de login a config.ini
[TRADETALLY]
api_key = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 🔧 Troubleshooting

### Problemas Comunes

#### 1. Backend no inicia - Puerto ocupado
```bash
# Verificar qué usa el puerto
lsof -i :8001

# Matar proceso
kill <PID>

# Reiniciar
./Start_TradeTally.command
```

#### 2. Frontend no conecta con Backend
```bash
# Verificar configuración
cat tradetally/frontend/.env.local
# Debe contener: VITE_API_URL=http://localhost:8001/api

# Reiniciar frontend
./tradetally/manage_tradetally.sh stop
./tradetally/manage_tradetally.sh start
```

#### 3. Error de autenticación en sincronización
```bash
# Verificar token válido
curl -H "Authorization: Bearer TU_TOKEN" http://localhost:8001/api/auth/me

# Si expiró, hacer login nuevo y actualizar config.ini
```

#### 4. Trades no aparecen en dashboard
- Verificar que estás logueado con el usuario correcto
- Los trades están asociados al usuario del token en config.ini
- Refrescar navegador o limpiar cache

#### 5. Base de datos corrupta
```bash
# Backup
cp tradetally/backend/database.db tradetally/backend/database.db.backup

# Verificar integridad
sqlite3 tradetally/backend/database.db "PRAGMA integrity_check;"
```

### Logs de Depuración
```bash
# Backend logs
tail -f tradetally/backend/backend.out

# Frontend logs
tail -f tradetally/frontend/frontend.out

# Sistema de trading logs
tail -f trading_system.log
```

## 📝 Comandos Útiles

### Gestión de Servicios
```bash
# Iniciar
./Start_TradeTally.command

# Detener
./Stop_TradeTally.command

# Estado
./tradetally/manage_tradetally.sh status

# Logs en tiempo real
./tradetally/manage_tradetally.sh logs
```

### Sincronización
```bash
# Sincronización manual
python sync_tradetally_local.py

# Resetear estado y resincronizar todo
rm tradetally_sync_state.json && python sync_tradetally_local.py

# Verificar estado de sincronización
cat tradetally_sync_state.json | jq .
```

### Base de Datos
```bash
# Conectar a BD TradeTally
sqlite3 tradetally/backend/database.db

# Ver usuarios
sqlite3 tradetally/backend/database.db "SELECT email, username, role FROM users;"

# Ver trades
sqlite3 tradetally/backend/database.db "SELECT symbol, entry_time, pnl FROM trades LIMIT 5;"

# Conectar a BD Trading System
sqlite3 trading_data.db "SELECT symbol, entry_time, pnl FROM trades WHERE status='CLOSED' LIMIT 5;"
```

### API Testing
```bash
# Health check
curl http://localhost:8001/api/health

# Login
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"tu@email.com","password":"tupass"}'

# Listar trades (requiere token)
curl -H "Authorization: Bearer TU_TOKEN" http://localhost:8001/api/trades

# Crear trade de prueba
curl -X POST -H "Authorization: Bearer TU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"TEST","side":"long","entryTime":"2025-08-30T06:30:00Z","entryPrice":10.50,"quantity":100,"commission":1.00,"strategy":"test","broker":"IBKR"}' \
  http://localhost:8001/api/trades
```

### Monitoreo
```bash
# Procesos activos
ps aux | grep -E "(node|npm)" | grep -v grep

# Puertos en uso
netstat -an | grep -E "(8001|5173)"

# Espacio en disco
du -sh tradetally/backend/database.db
du -sh trading_data.db
```

## 🎯 Flujo de Trabajo Típico

### Inicio del Día
1. `./Start_TradeTally.command`
2. Verificar en `http://localhost:5173`
3. Login con tus credenciales
4. Revisar dashboard de trades

### Durante el Trading
- El sistema sincroniza automáticamente a las 16:30
- Los nuevos trades aparecen en el dashboard
- Análisis en tiempo real disponible

### Sincronización Manual (si necesario)
```bash
python sync_tradetally_local.py
```

### Fin del Día
1. Revisar trades del día en dashboard
2. `./Stop_TradeTally.command` (opcional)
3. Backup de datos (recomendado)

### Backup Semanal
```bash
# Crear backup
cp tradetally/backend/database.db backups/tradetally_$(date +%Y%m%d).db
cp trading_data.db backups/trading_data_$(date +%Y%m%d).db
```

---

## 📞 Soporte

Para problemas específicos:
1. Revisar logs en `tradetally/backend/backend.out`
2. Verificar configuración en `config.ini`
3. Probar comandos de troubleshooting
4. Reiniciar servicios si es necesario

**¡Tu instancia local de TradeTally está lista para usar!** 🚀
