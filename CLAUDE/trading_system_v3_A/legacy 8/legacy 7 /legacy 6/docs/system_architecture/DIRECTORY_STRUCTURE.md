# Trading System V3 - Directory Structure

## Core System Files
- `main.py` - Main entry point (standalone execution)
- `streamlit_app_v2.py` - Streamlit web interface
- `config.ini` - Configuration file
- `requirements.txt` - Dependencies

## Core Modules
- `core/` - Core system components
  - `interfaces.py` - Data structures and interfaces
  - `events.py` - Event system
  - `risk_manager.py` - Risk management
  - `stop_loss_manager.py` - Centralized stop loss
  - `database_manager.py` - Data persistence
  - `trading_execution_stage.py` - Trade execution pipeline

- `engine/` - Trading engine
  - `trading_engine.py` - Main trading engine

- `strategies/` - Trading strategies
  - `base.py` - Base strategy interface
  - `ml_strategy_selector.py` - ML strategy selection
  - `multi_strategy_engine_ml.py` - **ML Multi-Strategy Engine** 🤖
  - `multi_strategy_engine.py` - Traditional multi-strategy
  - Individual strategies: `macdv_strategy.py`, `gap_go_strategy.py`, etc.

## Data & ML
- `data/` - Data storage
  - `csv/` - Historical CSV data
  - `ml_models/` - ML model files
  - `synthetic_data/` - Synthetic test data
  - `trading_data.db` - Trading history database

## Testing & Development
- `tests/` - Organized test suite
- `scripts/` - Development utilities
  - `debug/` - Debug scripts
  - `runners/` - System runners
  - `tools/` - Development tools

## Adapters & Integrations
- `adapters/` - Broker/data adapters
  - `ibkr_adapter.py` - Interactive Brokers
  - `mock_ibkr_adapter.py` - Mock trading
  - `csv_data_provider.py` - CSV data

## Supporting Modules
- `filters/` - Trade filters
- `notifications/` - Alert system
- `utils/` - Utilities
- `scanner/` - Stock scanner
- `backtesting/` - Backtesting framework

## Documentation
- `docs/` - Technical documentation
- `documentation/` - Additional guides and markdown files

## Archive
- `archive/` - Unused/temporary files
  - `unused_tests/` - Old test files
  - `temp_files/` - Temporary utilities
- `archived/` - Legacy components

## Logs
- `logs/` - System logs
  - `trading_system.log` - Main system log

## Current Status
✅ **ML Multi-Strategy Engine Active**
✅ **Directory Structure Organized** 
✅ **Test Files Archived**
✅ **Duplicates Removed**

## Key Active Components
1. **ML Engine**: `strategies/multi_strategy_engine_ml.py`
2. **Strategy Selector**: `strategies/ml_strategy_selector.py`
3. **Config**: `config.ini` (strategy = ml_multi_strategy)
4. **Main Interface**: `streamlit_app_v2.py`