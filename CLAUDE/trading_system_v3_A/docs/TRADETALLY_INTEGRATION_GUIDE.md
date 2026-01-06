# TradeTally Integration Guide

Guía completa para la integración entre trading_system_v3 y TradeTally.

## 📋 Descripción

Esta integración permite sincronizar automáticamente los trades de tu base de datos local con TradeTally, un diario de trading en la nube. La sincronización es bidireccional y conserva la integridad de los datos.

## 🚀 Instalación Rápida

### 1. Verificar Estructura
```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3

# Verificar que existen estos archivos:
ls integrations/tradetally_sync.py
ls integrations/tradetally_cli.py
ls config/tradetally_config.py
```

### 2. Instalar Dependencias
```bash
pip install requests
```

### 3. Configurar API Key
```bash
# Método 1: CLI interactivo (recomendado)
python integrations/tradetally_cli.py setup

# Método 2: Variable de entorno
export TRADETALLY_API_KEY="tt_live_tu_api_key_aqui"

# Método 3: Archivo de configuración
echo "tt_live_tu_api_key_aqui" > config/tradetally_api.key
chmod 600 config/tradetally_api.key
```

### 4. Probar Conexión
```bash
python integrations/tradetally_cli.py test
```

## 🔧 Configuración

### Variables de Entorno (Opcionales)
```bash
# API Configuration
export TRADETALLY_API_KEY="tt_live_your_api_key"
export TRADETALLY_BASE_URL="https://app.tradetally.com"

# Sync Configuration
export TRADETALLY_BATCH_SIZE="10"          # Trades por lote
export TRADETALLY_REQUEST_DELAY="1.0"      # Pausa entre requests (segundos)
export TRADETALLY_RETRY_ATTEMPTS="3"       # Intentos de reintento
export TRADETALLY_BROKER_NAME="IBKR"       # Nombre del broker en TradeTally
```

### Archivo de Configuración
El archivo `config/tradetally_config.py` centraliza toda la configuración:

```python
from config.tradetally_config import config

# Verificar configuración
print(config.is_configured())
print(config.get_config_dict())
```

## 🖥️ Uso del CLI

### Comandos Principales

#### Configuración Inicial
```bash
# Configurar API Key de forma interactiva
python integrations/tradetally_cli.py setup

# Ver estado actual
python integrations/tradetally_cli.py status

# Ver configuración completa
python integrations/tradetally_cli.py config
```

#### Pruebas y Conexión
```bash
# Probar conexión con TradeTally
python integrations/tradetally_cli.py test

# Simular sincronización (sin enviar datos)
python integrations/tradetally_cli.py sync --dry-run
```

#### Sincronización
```bash
# Sincronizar todos los trades pendientes
python integrations/tradetally_cli.py sync

# Reintentar trades que fallaron anteriormente
python integrations/tradetally_cli.py retry
```

### Ejemplos de Salida

#### Estado del Sistema
```
📊 Estado de TradeTally Integration
==================================================
🔑 API Key configurada: ✅
🌐 URL base: https://app.tradetally.com
💾 Base de datos: /path/to/trading_data.db

📈 Estado de Sincronización:
   Última sincronización: 2024-08-15T23:30:00
   Trades sincronizados: 45
   Sincronizaciones fallidas: 2

⏳ Trades pendientes: 8
```

#### Resultado de Sincronización
```
📊 REPORTE DE SINCRONIZACIÓN COMPLETADO:
✅ Trades sincronizados: 8
❌ Trades fallidos: 0
📈 Total procesados: 8
```

## 📊 Mapeo de Datos

### De tu Base de Datos → TradeTally

| Campo Local | Campo TradeTally | Transformación |
|-------------|------------------|----------------|
| `symbol` | `symbol` | Directo |
| `side` | `side` | BUY→long, SELL→short |
| `entry_time` | `entryTime` | ISO 8601 format |
| `exit_time` | `exitTime` | ISO 8601 format |
| `entry_price` | `entryPrice` | Directo |
| `exit_price` | `exitPrice` | Directo |
| `quantity` | `quantity` | Directo |
| `commission` | `commission` | Directo |
| `strategy` | `strategy` | Directo |
| `notes` | `notes` | + metadata adicional |
| - | `broker` | "IBKR" (configurable) |

### Campos Calculados Automáticamente
- **PnL**: Se calcula automáticamente en TradeTally
- **Fees**: Se incluyen en commission
- **Duration**: Se agrega a las notas si está disponible

## 🔄 Funcionamiento de la Sincronización

### Estado de Tracking
La integración mantiene un archivo de estado (`tradetally_sync_state.json`) que incluye:
- Timestamp de última sincronización
- Lista de trade_ids ya sincronizados
- Registro de sincronizaciones fallidas

### Proceso de Sincronización
1. **Identificación**: Solo se sincronizan trades con `status = 'CLOSED'`
2. **Filtrado**: Se excluyen trades ya sincronizados
3. **Transformación**: Conversión de formato local a TradeTally
4. **Envío**: Requests en lotes con rate limiting
5. **Tracking**: Actualización del estado de sincronización

### Rate Limiting
- Lotes de 10 trades por defecto
- Pausa de 1 segundo entre requests
- Pausa de 2 segundos entre lotes
- Manejo automático de rate limits (429)

## 🐍 Uso Programático

### Sincronización Básica
```python
from integrations.tradetally_sync import TradeTallyIntegration
from config.tradetally_config import config

# Crear instancia
sync = TradeTallyIntegration(config.api_key, config.base_url, config.db_path)

# Probar conexión
if sync.test_connection():
    # Sincronizar trades
    result = sync.sync_all_trades()
    print(f"Sincronizados: {result['synced']}, Fallidos: {result['failed']}")
```

### Sincronización Personalizada
```python
# Configuración personalizada
result = sync.sync_all_trades(
    batch_size=5,     # Lotes más pequeños
    delay=2.0         # Más pausa entre requests
)

# Solo obtener trades para revisar
trades = sync.get_local_trades(only_new=True)
for trade in trades:
    print(f"{trade.symbol} - {trade.side} - ${trade.pnl}")
```

### Estado y Monitoring
```python
# Estado actual
status = sync.get_sync_status()
print(f"Última sync: {status['last_sync']}")
print(f"Total sincronizados: {status['total_synced']}")

# Reintentar fallos
retry_result = sync.retry_failed_syncs()
```

## 🔒 Seguridad

### Protección de API Key
- El API Key se almacena con permisos 600 (solo propietario)
- No se muestra completo en logs (solo primeros y últimos caracteres)
- Se puede usar variable de entorno para mayor seguridad

### Validaciones
- Verificación de formato de API Key (`tt_live_*`)
- Validación de datos antes del envío
- Manejo seguro de errores de API

## ⚡ Automatización

### Cron Job (Linux/Mac)
```bash
# Agregar a crontab (crontab -e)
# Sincronizar cada hora
0 * * * * cd /path/to/trading_system_v3 && python integrations/tradetally_cli.py sync >> logs/tradetally_sync.log 2>&1
```

### Integración con tu Sistema de Trading
```python
# En tu trading system
from integrations.tradetally_sync import TradeTallyIntegration

class TradingSystem:
    def __init__(self):
        self.tradetally = TradeTallyIntegration(...)
    
    def on_trade_closed(self, trade):
        # Sincronizar automáticamente cuando se cierra un trade
        if self.tradetally.test_connection():
            self.tradetally.sync_all_trades()
```

## 🛠️ Troubleshooting

### Errores Comunes

#### API Key Inválida
```
❌ API Key inválida o expirada
```
**Solución**: Verificar que el API Key sea correcto y tenga permisos de escritura.

#### Rate Limit
```
⚠️ Rate limit alcanzado, pausando...
```
**Solución**: La integración maneja esto automáticamente. Ajustar `request_delay` si es necesario.

#### Error de Conexión
```
❌ Error de red: Connection timeout
```
**Solución**: Verificar conectividad a internet y URL de TradeTally.

#### Datos Faltantes
```
Error 400: Missing required field 'entryPrice'
```
**Solución**: Verificar que los trades tienen todos los campos requeridos.

### Debug y Logs
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Esto mostrará información detallada de todas las operaciones
```

### Archivos de Estado
- `tradetally_sync_state.json`: Estado de sincronización
- `config/tradetally_api.key`: API Key almacenado
- Logs del CLI se pueden redirigir a archivos

## 📈 Casos de Uso

### Sincronización Inicial
```bash
# Primera vez - sincronizar todos los trades históricos
python integrations/tradetally_cli.py sync
```

### Sincronización Diaria
```bash
# Solo trades nuevos desde la última sync
python integrations/tradetally_cli.py sync
```

### Backup y Migración
```bash
# Simular para verificar qué se va a sincronizar
python integrations/tradetally_cli.py sync --dry-run

# Proceder con la sincronización real
python integrations/tradetally_cli.py sync
```

### Monitoreo Continuo
```bash
# Script de monitoreo
while true; do
    python integrations/tradetally_cli.py status
    sleep 3600  # Cada hora
done
```

## 🤝 Soporte

Para problemas con la integración:

1. **Verificar configuración**: `python integrations/tradetally_cli.py config`
2. **Probar conexión**: `python integrations/tradetally_cli.py test`
3. **Revisar logs**: Activar logging debug
4. **Estado de sync**: `python integrations/tradetally_cli.py status`

Para problemas con la API de TradeTally, consultar su documentación oficial.

---

**¡La integración está lista para usar! 🎉**

Ejecuta `python integrations/tradetally_cli.py setup` para comenzar.