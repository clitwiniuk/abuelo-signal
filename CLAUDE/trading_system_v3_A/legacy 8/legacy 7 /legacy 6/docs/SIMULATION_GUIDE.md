# Trading System Simulation Guide

## Overview

Este sistema de simulación está diseñado para desarrollo y testing sin necesidad de conexión a IBKR real. Incluye:

- **MockIBKRAdapter**: Simula completamente la funcionalidad de IBKR
- **CSVDataProvider**: Carga datos históricos desde archivos CSV
- **SimulationManager**: Coordina backtesting y testing
- **Configuración optimizada**: Para desarrollo sin restricciones

## ¿Por qué usar el sistema de simulación?

### ✅ Ventajas
- **Sin dependencias externas**: No necesitas TWS/Gateway corriendo
- **Testing rápido**: Prueba cambios sin esperar market data real
- **Datos consistentes**: Mismos datos en cada test para comparación
- **Sin costos**: No ejecutas trades reales durante desarrollo
- **Debugging fácil**: Control total sobre datos y timing

### 🎯 Casos de uso
- Desarrollo de nuevas estrategias
- Testing de modificaciones al código
- Backtesting histórico
- Debugging de errores
- Validación de risk management

## Quick Start

### 1. Configuración básica

```python
from config.simulation_config import setup_simulation_environment

# Setup completo del entorno de simulación
sim_env = setup_simulation_environment()

broker = sim_env['broker']
data_provider = sim_env['data_provider']
config = sim_env['config']
simulation_manager = sim_env['simulation_manager']
```

### 2. Inicializar el entorno

```python
# Inicializar con datos de ejemplo
await simulation_manager.initialize(create_sample_data=True)

# Verificar que está todo conectado
print(f"Broker connected: {broker.is_connected()}")
print(f"Data provider connected: {data_provider.is_connected()}")
print(f"Available symbols: {data_provider.get_available_symbols()}")
```

### 3. Usar como IBKR normal

```python
# El MockIBKRAdapter implementa las mismas interfaces que ThreadSafeIBKRAdapter
# Puedes usar el código existente sin cambios!

# Obtener datos históricos
bars = await data_provider.get_bars("AAPL", "1 min", 100)

# Obtener precio actual
price = await broker.get_current_price("AAPL")

# Colocar orden
order_id = await broker.place_order(
    symbol="AAPL",
    side=OrderSide.BUY,
    quantity=100,
    order_type=OrderType.MARKET
)

# Obtener posiciones
positions = await broker.get_positions()
```

## Estructura del Sistema

### MockIBKRAdapter
Simula completamente IBKR con:
- Ejecución realista de órdenes con slippage
- Gestión de posiciones
- Simulación de account balance
- Generación de datos sintéticos
- Carga de datos CSV

### CSVDataProvider
Maneja datos históricos:
- Carga automática de archivos CSV
- Formato estándar (timestamp, OHLCV)
- Cache para performance
- Generación de datos de ejemplo

### SimulationManager
Coordina todo el entorno:
- Backtesting completo
- Testing de estrategias individuales
- Métricas de performance
- Control de velocidad de simulación

## Configuración de Datos

### Formato CSV requerido
```csv
timestamp,open,high,low,close,volume
2024-01-01 09:30:00,150.00,151.50,149.50,151.00,10000
2024-01-01 09:31:00,151.00,152.00,150.50,151.75,8500
```

### Estructura de directorios
```
data/csv/
├── PLTR_1_min.csv
├── TSLA_1_min.csv
├── NVDA_1_min.csv
└── MVIS_1_min.csv
```

### 🎯 Descargar datos REALES con Polygon.io

**¡NUEVO!** Ya no necesitas datos sintéticos. Descarga datos reales de cualquier ticker:

```python
from adapters.polygon_downloader import download_single_symbol, download_any_symbols

# Configura tu API key (gratis en polygon.io)
import os
os.environ['POLYGON_API_KEY'] = 'tu_api_key_aqui'

# Descarga cualquier ticker que te interese
await download_single_symbol('PLTR', days=10)
await download_single_symbol('MVIS', days=10)
await download_single_symbol('NVDA', days=10)

# O descarga tu lista personalizada
my_tickers = ['PLTR', 'TSLA', 'NVDA', 'AMD', 'MVIS', 'BB', 'SOFI']
results = await download_any_symbols(my_tickers, days=10)
```

### Crear datos sintéticos (alternativa)
```python
# Si no tienes API key, el sistema puede generar datos sintéticos
csv_provider = CSVDataProvider("data/csv")
csv_provider.create_sample_data(
    symbols=['PLTR', 'TSLA', 'NVDA'],
    days=30
)
```

## Configuración Avanzada

### SimulationConfig personalizada
```python
from config.simulation_config import SimulationConfig

config = SimulationConfig()

# Ajustar risk management
config.max_position_value = 5000.0
config.max_portfolio_exposure = 20000.0
config.debug_mode = True  # Desactiva casi todas las restricciones

# Ajustar simulación
config.simulation_speed = 10.0  # 10x velocidad real
config.portfolio_capital = 50000.0  # Empezar con $50k
```

### MockIBKRAdapter personalizado
```python
mock_broker = MockIBKRAdapter(
    data_path="custom/data/path",
    simulation_mode=True
)

# Ajustar parámetros de simulación
mock_broker._price_volatility = 0.05  # 5% volatilidad
mock_broker._slippage = 0.002  # 0.2% slippage
mock_broker._order_fill_delay = 0.5  # 500ms delay
```

## Backtesting

### Test básico de estrategia
```python
# Test en un símbolo específico
result = await simulation_manager.test_strategy_on_symbol(
    symbol="AAPL",
    timeframe="1 min",
    bars_count=500
)

print(f"Trades executed: {result['trades_executed']}")
print(f"Final P&L: {result['final_stats']['total_pnl']}")
```

### Backtesting completo
```python
from datetime import datetime, timedelta

# Backtest de múltiples símbolos
results = await simulation_manager.run_backtest(
    symbols=['AAPL', 'MSFT', 'TSLA'],
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    strategy_config={'strategy': 'macdv', 'timeframe': '1 min'}
)

print(f"Total return: {results['performance']['total_return_pct']:.2f}%")
print(f"Max drawdown: {results['performance']['max_drawdown_pct']:.2f}%")
print(f"Sharpe ratio: {results['performance']['sharpe_ratio']:.2f}")
```

## Integración con Sistema Existente

### Modificar MultiStrategyEngine para simulación
```python
# En lugar de:
# self.broker = ThreadSafeIBKRAdapter(host, port, client_id)

# Usar:
if config.simulation_mode:
    sim_env = setup_simulation_environment()
    self.broker = sim_env['broker']
    self.data_provider = sim_env['data_provider']
    await sim_env['simulation_manager'].initialize()
else:
    self.broker = ThreadSafeIBKRAdapter(host, port, client_id)
```

### Switch automático en base a configuración
```python
class TradingEngine:
    def __init__(self, config):
        if getattr(config, 'simulation_mode', False):
            self._setup_simulation(config)
        else:
            self._setup_live_trading(config)
    
    def _setup_simulation(self, config):
        sim_env = setup_simulation_environment()
        self.broker = sim_env['broker']
        self.data_provider = sim_env['data_provider']
        self.simulation_manager = sim_env['simulation_manager']
    
    def _setup_live_trading(self, config):
        self.broker = ThreadSafeIBKRAdapter(
            host=config.broker_host,
            port=config.broker_port,
            client_id=config.broker_client_id
        )
```

## Debugging y Development

### Logging detallado
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Los adapters mock tienen logging muy detallado
# Verás cada trade, cada price update, etc.
```

### Testing de escenarios específicos
```python
# Crear escenario de test específico
scenario_config = simulation_manager.create_test_scenario(
    scenario_name="high_volatility_test",
    symbols=['TSLA', 'GME'],
    config_override={
        'max_position_value': 1000.0,
        'debug_mode': True
    }
)
```

### Performance metrics en tiempo real
```python
# Durante la simulación
stats = mock_broker.get_performance_stats()
print(f"Current P&L: {stats['total_pnl']:.2f}")
print(f"Trades: {stats['trades_executed']}")
print(f"Win rate: {stats.get('win_rate', 0):.1%}")
```

## Troubleshooting

### Error: "No CSV data available"
```python
# Crear datos de ejemplo
csv_provider.create_sample_data(symbols=['AAPL'], days=30)

# O cargar tus propios datos
import pandas as pd
df = pd.read_csv("mi_datos.csv")
csv_provider.add_data_from_dataframe("AAPL", "1 min", df)
```

### Error: "Simulation manager not initialized"
```python
# Siempre inicializar antes de usar
await simulation_manager.initialize(create_sample_data=True)
```

### Performance lenta
```python
# Usar datos en cache
csv_provider._scan_available_data()

# Reducir velocidad de simulación
simulation_manager._simulation_speed = 0.5  # Más lento pero más estable
```

## Best Practices

### 1. Testing incremental
- Empezar con un símbolo
- Probar con datos sintéticos
- Validar métricas básicas
- Expandir a múltiples símbolos

### 2. Datos consistentes
- Usar mismos datasets para comparación
- Guardar configuraciones de test
- Documentar escenarios específicos

### 3. Métricas relevantes
- No solo P&L total
- Revisar drawdown, Sharpe ratio
- Verificar número de trades
- Validar risk management

### 4. Debugging sistemático
- Logs detallados en desarrollo
- Testing de edge cases
- Validación de lógica step-by-step

## Polygon.io Data Downloader

### 🚀 Configuración rápida

1. **Obtén API key gratis**: Ve a [polygon.io](https://polygon.io) y regístrate
2. **Configura la key**:
   ```bash
   export POLYGON_API_KEY="tu_api_key_aqui"
   ```

### 📥 Ejemplos de uso

#### Descarga tickers específicos que te interesan
```python
from adapters.polygon_downloader import download_single_symbol, download_any_symbols

# Descarga tu ticker favorito
success = await download_single_symbol('PLTR', days=10)

# Descarga tu lista personalizada
my_watchlist = ['PLTR', 'TSLA', 'NVDA', 'AMD', 'MVIS', 'BB', 'SOFI', 'COIN']
results = await download_any_symbols(my_watchlist, days=10)
```

#### Usa sugerencias predefinidas (opcional)
```python
from adapters.polygon_downloader import download_smallcap_suggestions, download_growth_suggestions

# Smallcaps sugeridos
smallcap_results = await download_smallcap_suggestions(days=10)

# Growth stocks sugeridos
growth_results = await download_growth_suggestions(days=10)
```

#### Actualizar datos existentes
```python
from adapters.polygon_downloader import update_existing_data

# Actualizar tus tickers específicos
results = await update_existing_data(['PLTR', 'TSLA', 'NVDA'])

# Actualizar todos los datos existentes
results = await update_existing_data()
```

#### Información de los datos
```python
from adapters.polygon_downloader import PolygonDownloader

async with PolygonDownloader.from_env() as downloader:
    # Ver qué datos tienes
    available_symbols = downloader.get_available_data()
    print(f"Símbolos disponibles: {available_symbols}")
    
    # Información detallada de un símbolo
    info = downloader.get_data_info('PLTR')
    print(f"PLTR: {info['bars_count']} bars, desde {info['start_date']} hasta {info['end_date']}")
```

## Ejemplo Completo con Datos Reales

```python
async def main():
    # 1. Descarga datos reales de tus tickers favoritos
    my_tickers = ['PLTR', 'TSLA', 'NVDA', 'AMD', 'MVIS']
    print("📥 Descargando datos reales...")
    results = await download_any_symbols(my_tickers, days=10)
    
    # 2. Setup entorno de simulación
    sim_env = setup_simulation_environment()
    
    # 3. Inicializar (sin datos sintéticos, usamos los reales)
    await sim_env['simulation_manager'].initialize(create_sample_data=False)
    
    # 4. Test con datos reales
    result = await sim_env['simulation_manager'].test_strategy_on_symbol("PLTR")
    print(f"Test result with REAL data: {result}")
    
    # 5. Backtest completo con datos reales
    backtest_results = await sim_env['simulation_manager'].run_backtest(
        symbols=['PLTR', 'TSLA', 'NVDA'],
        start_date=datetime.now() - timedelta(days=7),
        end_date=datetime.now(),
        strategy_config={}
    )
    
    print(f"Backtest performance with REAL data: {backtest_results['performance']}")
    
    # Cleanup
    await sim_env['simulation_manager'].cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

## Conclusión

Este sistema de simulación te permite:
- ✅ Desarrollar sin conexión a IBKR
- ✅ Testing rápido y consistente  
- ✅ Backtesting completo
- ✅ Debugging efectivo
- ✅ Zero risk durante desarrollo

**¡Úsalo para todo el desarrollo y testing antes de conectar al broker real!**