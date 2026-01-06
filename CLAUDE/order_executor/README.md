# Order Executor API

API REST para la ejecución de órdenes de trading con Interactive Brokers, diseñada para ser utilizada por estrategias de trading independientes.

## Características

- **Desacoplado**: Las estrategias no necesitan conocer los detalles de implementación de IBKR
- **Seguro**: Validación de órdenes y gestión de riesgos integrada
- **Simple**: API REST fácil de usar
- **Asíncrono**: Basado en asyncio para alto rendimiento
- **Multi-estrategia**: Soporte para múltiples estrategias concurrentes

## Instalación

1. Instalar dependencias:

```bash
pip install fastapi uvicorn aiohttp pydantic python-dotenv
```

2. Configurar variables de entorno (opcional):

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

## Uso

### Iniciar el servidor de la API

```bash
python -m order_executor.api.main
```

La API estará disponible en `http://localhost:8000`

### Endpoints

#### 1. Enviar señal de trading

```http
POST /signal
```

**Ejemplo de solicitud:**

```json
{
  "strategy_id": "mi_estrategia_1",
  "ticker": "AAPL",
  "signal": "BUY",
  "quantity": 10,
  "price": 150.50,
  "metadata": {
    "nota": "Señal de compra por cruce de medias"
  }
}
```

**Señales soportadas:**
- `BUY`: Abre una posición larga
- `SELL`: Abre una posición corta
- `CLOSE`: Cierra la posición actual

#### 2. Obtener posiciones abiertas

```http
GET /positions?strategy_id=mi_estrategia_1&ticker=AAPL
```

#### 3. Verificar estado del servicio

```http
GET /health
```

### Ejemplo de estrategia

Ver [examples/strategy_example.py](examples/strategy_example.py) para un ejemplo completo de cómo implementar una estrategia que utiliza esta API.

## Configuración

La configuración se maneja a través de variables de entorno o un archivo `.env`:

```ini
# .env
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
```

## Requisitos

- Python 3.8+
- TWS o IB Gateway ejecutándose
- Cuenta de Interactive Brokers configurada

## Desarrollo

1. Instalar dependencias de desarrollo:

```bash
pip install -r requirements-dev.txt
```

2. Ejecutar tests:

```bash
pytest
```

## Seguridad

- La API no tiene autenticación por defecto. Se recomienda:
  - Usar un proxy inverso con autenticación
  - Restringir el acceso por IP
  - Usar HTTPS

## Licencia

MIT
