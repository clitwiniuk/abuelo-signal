#!/usr/bin/env python3
"""
Professional Backtesting System
===============================

Sistema profesional de backtesting para workers de trading.
Organizado de manera estructurada y modular.
"""

__version__ = "1.0.0"
__author__ = "Trading System Team"

# Importar clases principales
from .core.backtest_runner import BacktestRunner
from .core.pattern_generator import PatternGenerator
from .core.worker_tester import WorkerTester
from .core.metrics_calculator import MetricsCalculator
from .core.visualization_utils import VisualizationUtils
from .core.intraday_backtester import IntradayBacktester

__all__ = [
    'BacktestRunner',
    'PatternGenerator', 
    'WorkerTester',
    'MetricsCalculator',
    'VisualizationUtils',
    'IntradayBacktester'
]