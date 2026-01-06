# Trading System v3 - Organizado

A modular and extensible trading system with support for multiple strategies, backtesting, and live trading.

## Features

- **Multiple Strategy Support**: Easily switch between different trading strategies
- **Backtesting Framework**: Comprehensive backtesting with detailed analytics
- **Parameter Optimization**: Find optimal parameters for your strategies
- **Session-Specific Testing**: Test strategies in different market sessions
- **Dynamic Strategy Selection**: Choose strategies at runtime

## Available Strategies

1. **MACD-V**
   - Combines MACD with volume analysis
   - Optimized for 1-minute and 5-minute timeframes

2. **Gap & Go**
   - Identifies and trades gap patterns
   - Includes volume and price action confirmation

3. **Optimized Gap & Go**
   - Enhanced version with improved entry/exit logic
   - Advanced risk management features

## Getting Started

### Prerequisites

- Python 3.8+
- Required packages (see `requirements.txt`)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd trading_system_v2
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Quick Start

**🎯 Menú Principal (Recomendado):**
```bash
python start.py
```

**🎮 Test Rápido del Mock:**
```bash
python simulation/simple_mock_test.py
```

**📊 Descargar Datos:**
```bash
python scripts/tools/download_menu.py
```

### Running Backtests

1. Start the backtest system:
   ```bash
   python scripts/runners/run_backtest.py
   ```

2. Select a strategy when prompted
3. Choose from the available backtest options

### Strategy Development

To add a new strategy:

1. Create a new strategy class in `strategies/`
2. Add parameter getters in `backtests/backtest_config.py`
3. Register the strategy in `run_backtest.py`

See [docs/strategy_selection.md](docs/strategy_selection.md) for detailed instructions.

## Documentation

📚 **[Ver toda la documentación en /docs](docs/README_DOCS.md)**

### Documentos Principales:
- **[Cómo Ejecutar con Mock](docs/COMO_EJECUTAR_MOCK.md)**: Guía para usar el sistema sin IBKR real
- **[Guía de Simulación](docs/SIMULATION_GUIDE.md)**: Sistema completo de simulación
- **[Estructura Organizada](docs/ESTRUCTURA_ORGANIZADA.md)**: Nueva organización del proyecto
- **[Agregar Estrategias](docs/ADD_NEW_STRATEGY.md)**: Desarrollo de nuevas estrategias
- **[Selección de Estrategias](docs/strategy_selection.md)**: Configuración de estrategias

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
