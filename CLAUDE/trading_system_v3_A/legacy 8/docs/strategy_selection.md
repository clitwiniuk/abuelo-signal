# Dynamic Strategy Selection in Backtest System

## Overview
We've enhanced the backtest system to support dynamic strategy selection, allowing users to choose between different trading strategies when running backtests. This document outlines the changes made and how to use the new functionality.

## Changes Made

### 1. Strategy Registration System
- Added a `STRATEGIES` dictionary in `run_backtest.py` that maps strategy IDs to their respective classes and parameter getters
- Each strategy entry includes:
  - Display name
  - Strategy class
  - Parameter getter function

### 2. Updated Backtest Functions
Modified the following functions to accept `strategy_class` and `params_getter` parameters:
- `run_simple_backtest()`
- `run_quick_test()`
- `run_session_specific_backtest()`
- `run_parameter_optimization()`
- `run_comparison_backtest()`

### 3. New Functions
- `select_strategy()`: Displays available strategies and handles user selection
- Updated `main()` to integrate strategy selection with the menu system

### 4. Parameter Management
- Added parameter getter methods in `StrategyConfigurations` for each strategy
- Ensured backward compatibility with existing parameter structures

## How to Add a New Strategy

1. **Define the Strategy Class**
   - Create a new strategy class that inherits from `BaseStrategy`
   - Implement the required methods (e.g., `generate_signals`, `calculate_position_size`)

2. **Add Parameter Getters**
   - Add parameter getter methods in `StrategyConfigurations` class
   - Example: `get_my_strategy_params()`

3. **Register the Strategy**
   - Add an entry to the `STRATEGIES` dictionary in `run_backtest.py`
   ```python
   STRATEGIES = {
       '1': ('MACD-V Multi-Timeframe', MACDVStrategy, StrategyConfigurations.get_macdv_1min_optimized),
       '2': ('Gap & Go', GapGoStrategy, StrategyConfigurations.get_gap_go_params),
       '3': ('Optimized Gap & Go', OptimizedGapGoStrategy, StrategyConfigurations.get_optimized_gap_go_params),
       '4': ('My New Strategy', MyNewStrategy, StrategyConfigurations.get_my_strategy_params)
   }
   ```

## Usage

1. **Selecting a Strategy**
   - When starting the backtest system, you'll be prompted to select a strategy
   - Enter the number corresponding to your desired strategy

2. **Running Backtests**
   - All backtest functions will now use the selected strategy
   - Parameters specific to the selected strategy will be automatically loaded

3. **Switching Strategies**
   - During operation, you can press 'c' at any prompt to change the current strategy

## Example Workflow

```bash
# Start the backtest system
$ python run_backtest.py

# Select a strategy
📊 ESTRATEGIAS DISPONIBLES
==============================
1. MACD-V
2. Gap & Go
3. Optimized Gap & Go

👉 Selecciona la estrategia (1-3): 3

# Run a quick test with the selected strategy
🎯 INICIANDO SISTEMA DE BACKTESTING
========================================
🔍 Estrategia actual: OptimizedGapGoStrategy
...
```

## Notes
- The system maintains backward compatibility with existing code
- All strategies must implement the same base interface
- Parameter structures should be consistent within each strategy family
- Session-specific parameters are automatically merged with base parameters
