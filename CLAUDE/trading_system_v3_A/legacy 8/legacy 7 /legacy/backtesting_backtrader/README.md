# Backtesting con Backtrader

Este directorio está dedicado al backtesting de estrategias de trading utilizando la biblioteca Backtrader. El sistema está diseñado específicamente para daytrading, donde cada día representa un evento independiente.

## Propósito

- **Backtesting de estrategias**: Probar y validar estrategias de trading usando datos históricos.
- **Base de datos**: Utiliza `market_data.db` que contiene datos de tickers y sus precios históricos.
- **Daytrading**: Cada día es tratado como un evento independiente, sin carry-over de posiciones entre días.
- **Backtrader**: Framework de backtesting profesional para Python.

## Estructura del Directorio

```
backtesting_backtrader/
├── strategies/          # Estrategias de trading implementadas con Backtrader
├── data/               # Módulos para cargar datos desde market_data.db
├── config/             # Configuraciones de backtesting
├── core/               # Motor de backtesting y utilidades principales
├── reports/            # Resultados y reportes de backtesting
├── scripts/            # Scripts para ejecutar backtests
└── README.md           # Este archivo
```

## Base de Datos

El sistema utiliza `market_data.db` que contiene:
- Datos intraday (1 minuto) de tickers
- Información histórica de precios
- Datos descargados específicamente para días con oportunidades de trading

## Próximos Pasos

1. Implementar estrategias en el directorio `strategies/`
2. Crear data feeds para cargar datos desde `market_data.db`
3. Configurar parámetros de backtesting
4. Ejecutar backtests y analizar resultados

## Notas

- Todas las estrategias están diseñadas para daytrading
- No hay posiciones overnight
- Cada día se analiza independientemente