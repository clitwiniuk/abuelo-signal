"""
Configuración para backtesting con Backtrader
"""

# Configuración general
BACKTEST_CONFIG = {
    'initial_cash': 10000,  # Capital inicial
    'commission': 0.001,   # Comisión por trade (0.1%)
    'position_size': 10000, # Tamaño de posición en dólares
    'max_positions': 1,    # Máximo posiciones simultáneas
}

# Configuración de datos
DATA_CONFIG = {
    'db_path': '../market_data.db',
    'market_open': '09:30',
    'market_close': '22:00',  # Hora española (16:00 USA + 6 horas) - CORREGIDO
    'timeframe': '1min',  # Timeframe de las barras
}

# Configuración de estrategias
STRATEGY_CONFIGS = {
    'BreakoutStrategy': {
        'consolidation_bars': 12,  # 3 horas en 15min
        'volume_multiplier': 1.5,
    },
    'GapUpStrategy': {
        'min_gap': 0.02,    # 2% gap mínimo
        'max_gap': 0.08,    # 8% gap máximo
        'volume_multiplier': 2.0,
    },
    'VWAPBounceStrategy': {
        'vwap_deviation_min': -0.03,  # -3% bajo VWAP
        'vwap_deviation_max': -0.01,  # -1% bajo VWAP
        'rsi_oversold': 40,
    },
    'OptunaOptimizedStrategy': {
        # Parámetros por defecto (se sobreescriben si se carga JSON)
        'rsi_period': 14,
        'rsi_threshold': 70,
        'sma_period': 20,
        'adx_period': 14,
        'adx_threshold': 25,
        'tp_pct': 5.0,
        'sl_pct': -2.0,
        'trailing_stop': True,
        'trailing_pct': 1.0,
        'max_holding_period': 30,
        'position_size_pct': 95,
        # Path al archivo de optimización (relativo al directorio de backtesting)
        'params_file': '../backtesting_system/rule_extractor-main/optuna_optimization_summary.json',
    },
}

# Configuración de análisis
ANALYSIS_CONFIG = {
    'sharpe_ratio': True,
    'max_drawdown': True,
    'total_return': True,
    'win_rate': True,
    'profit_factor': True,
    'avg_trade': True,
}

# Símbolos disponibles para testing
TEST_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',
    'NVDA', 'META', 'NFLX', 'AMD', 'INTC'
]

# Períodos de testing (días disponibles en la base de datos)
TEST_PERIODS = [
    ('2025-10-15', '2025-10-15'),  # Datos disponibles para ABAT
    ('2025-10-16', '2025-10-16'),
]