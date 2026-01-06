"""
Configuración del Sistema de Backtesting Híbrido

Configuración centralizada para el sistema de backtesting que combina
backtrader con datos reales de trading_data.db
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime, timedelta


@dataclass
class BacktestConfig:
    """Configuración principal del backtesting"""

    # Capital inicial
    initial_capital: float = 100_000.0

    # Comisiones y costos
    commission_per_share: float = 0.005  # $0.005 por acción
    slippage_pct: float = 0.05  # 0.05% slippage

    # Rango de fechas
    start_date: str = "2025-08-26"
    end_date: str = "2025-10-17"

    # Universos de prueba
    small_cap_universe: List[str] = None

    # Parámetros de riesgo
    max_position_size_pct: float = 0.05  # 5% del capital por posición
    max_daily_trades: int = 10
    max_open_positions: int = 5

    # Parámetros de estrategia
    min_confidence_threshold: float = 50.0
    max_risk_per_trade_pct: float = 2.0

    def __post_init__(self):
        if self.small_cap_universe is None:
            # Todos los símbolos disponibles con datos (186 símbolos)
            # Usaremos los primeros 50 para el backtest masivo
            import sqlite3
            import os
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                market_db_path = os.path.join(base_dir, 'market_data.db')
                if os.path.exists(market_db_path):
                    conn = sqlite3.connect(market_db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT symbol FROM intraday_bars GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 50")
                    symbols = [row[0] for row in cursor.fetchall()]
                    conn.close()
                    self.small_cap_universe = symbols
                else:
                    # Fallback a símbolos conocidos
                    self.small_cap_universe = [
                        'RR', 'IONZ', 'BITF', 'HIVE', 'LAES', 'RZLV', 'NUAI', 'SLNH',
                        'ONDS', 'OPEN', 'BTBT', 'MGIH', 'TSLQ', 'WLDS', 'ASST', 'NFE',
                        'CWD', 'TLRY', 'TSLS', 'NVTS', 'ABAT', 'ACHV', 'AIIO', 'AMDL'
                    ]
            except Exception:
                # Fallback si hay error
                self.small_cap_universe = [
                    'RR', 'IONZ', 'BITF', 'HIVE', 'LAES', 'RZLV', 'NUAI', 'SLNH',
                    'ONDS', 'OPEN', 'BTBT', 'MGIH', 'TSLQ', 'WLDS', 'ASST', 'NFE'
                ]


@dataclass
class StrategyConfig:
    """Configuración específica por estrategia"""

    name: str
    enabled: bool = True
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = self._get_default_params()

    def _get_default_params(self) -> Dict[str, Any]:
        """Parámetros por defecto según estrategia"""
        defaults = {
            'daily_plays': {
                'buy_threshold': 6.50,
                'sell_threshold': 7.00,
                'max_position_size': 0.05
            },
            'macdv': {
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9,
                'confirmation_threshold': 0.7
            },
            'momentum_breakout': {
                'lookback_period': 20,
                'breakout_threshold': 2.0,
                'volume_multiplier': 1.5
            },
            'vwap_breakout': {
                'enable_buy_the_dip': True,
                'dip_pullback_min_pct': 0.30,
                'dip_pullback_max_pct': 0.60,
                'dip_timeout_minutes': 20,
                'dip_volume_multiplier': 1.5
            }
        }
        return defaults.get(self.name, {})


# Configuración global
BACKTEST_CONFIG = BacktestConfig()

STRATEGY_CONFIGS = [
    # Estrategias complejas (ya probadas)
    StrategyConfig('daily_plays', parameters={
        'volume_ratio_min': 1.0,
        'vwap_validation': False,
        'rsi_filter': False,
        'gap_analysis': False,
        'momentum_check': False,
        'rsi_overbought': 80,
        'rsi_oversold': 20,
        'min_confidence': 10,
        'max_position_size': 0.10
    }),
    StrategyConfig('macdv', parameters={
        'fast_period': 8,
        'slow_period': 21,
        'signal_period': 5,
        'confirmation_threshold': 0.3
    }),
    StrategyConfig('momentum_breakout', parameters={
        'lookback_period': 10,
        'breakout_threshold': 1.0,
        'volume_multiplier': 1.0
    }),
    StrategyConfig('vwap_breakout', parameters={
        'enable_buy_the_dip': True,
        'dip_pullback_min_pct': 0.1,
        'dip_pullback_max_pct': 0.8,
        'dip_timeout_minutes': 30,
        'dip_volume_multiplier': 1.0
    }),

    # Estrategias simples intraday
    StrategyConfig('rsi_oversold', parameters={
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'max_position_size': 0.10,
        'min_volume': 10000,
        'max_holding_bars': 50
    }),
    StrategyConfig('ma_crossover', parameters={
        'fast_period': 9,
        'slow_period': 21,
        'max_position_size': 0.10,
        'min_volume': 10000,
        'max_holding_bars': 100
    }),
    StrategyConfig('volume_price', parameters={
        'volume_multiplier': 1.5,
        'price_change_pct': 0.5,
        'max_position_size': 0.10,
        'max_holding_bars': 50,
        'volume_period': 20
    }),
]

# Configuración de logging
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': 'INFO',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'CLAUDE/trading_system_v3/backtesting_system/logs/backtest.log',
            'formatter': 'standard',
            'level': 'DEBUG',
        },
    },
    'loggers': {
        'backtesting': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}