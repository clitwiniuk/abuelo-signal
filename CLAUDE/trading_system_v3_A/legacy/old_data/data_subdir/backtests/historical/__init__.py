# backtesting/__init__.py
"""
Backtesting module - simplified for MACDV strategy
"""

try:
    from .macdv_backtest_engine import MacdvBacktestEngine
    __all__ = ['MacdvBacktestEngine']
except ImportError:
    __all__ = []

__version__ = "1.0.0"