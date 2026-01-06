# shared/config_reader.py
"""
Config Reader for Sistema_4
Reads all parameters from config.ini using configparser
"""

import configparser
import os
from typing import Dict, Any, List

class Sistema4Config:
    """
    Configuration reader for Sistema_4
    Provides access to all config.ini sections
    """

    def __init__(self, config_file: str = "config.ini"):
        self.config = configparser.ConfigParser()

        # Load config file
        if os.path.exists(config_file):
            self.config.read(config_file)
        else:
            raise FileNotFoundError(f"Config file not found: {config_file}")

    def get_risk_manager_config(self) -> Dict[str, Any]:
        """Get risk manager configuration"""
        section = 'RISK_MANAGER'
        return {
            'total_portfolio_value': self.config.getfloat(section, 'total_portfolio_value', fallback=10000.0),
            'max_portfolio_risk_percent': self.config.getfloat(section, 'max_portfolio_risk_percent', fallback=2.0),
            'max_position_size_percent': self.config.getfloat(section, 'max_position_size_percent', fallback=5.0),
            'max_risk_per_trade_percent': self.config.getfloat(section, 'max_risk_per_trade_percent', fallback=1.0),
            'max_trade_value': self.config.getfloat(section, 'max_trade_value', fallback=1000.0),
            'max_daily_trades': self.config.getint(section, 'max_daily_trades', fallback=10),
            'max_daily_loss_percent': self.config.getfloat(section, 'max_daily_loss_percent', fallback=3.0),
            'max_symbols_per_strategy': self.config.getint(section, 'max_symbols_per_strategy', fallback=3),
            'max_total_symbols': self.config.getint(section, 'max_total_symbols', fallback=8),
            'min_stock_price': self.config.getfloat(section, 'min_stock_price', fallback=0.50),
            'max_stock_price': self.config.getfloat(section, 'max_stock_price', fallback=50.0)
        }

    def get_execution_engine_config(self) -> Dict[str, Any]:
        """Get execution engine configuration"""
        section = 'EXECUTION_ENGINE'
        return {
            'order_timeout_seconds': self.config.getint(section, 'order_timeout_seconds', fallback=30),
            'max_concurrent_orders': self.config.getint(section, 'max_concurrent_orders', fallback=5),
            'enable_bracket_orders': self.config.getboolean(section, 'enable_bracket_orders', fallback=True)
        }

    def get_gap_go_config(self) -> Dict[str, Any]:
        """Get GAP_GO strategy configuration"""
        section = 'STRATEGY_GAP_GO'
        return {
            'min_gap_percent': self.config.getfloat(section, 'min_gap_percent', fallback=2.0),
            'max_gap_percent': self.config.getfloat(section, 'max_gap_percent', fallback=15.0),
            'min_volume': self.config.getint(section, 'min_volume', fallback=500000),
            'max_volume': self.config.getint(section, 'max_volume', fallback=10000000),
            'stop_loss_percent': self.config.getfloat(section, 'stop_loss_percent', fallback=3.0),
            'take_profit_percent': self.config.getfloat(section, 'take_profit_percent', fallback=8.0),
            'max_position_size': self.config.getint(section, 'max_position_size', fallback=1000),
            'min_price': self.config.getfloat(section, 'min_price', fallback=1.0),
            'max_price': self.config.getfloat(section, 'max_price', fallback=15.0)
        }

    def get_daily_plays_config(self) -> Dict[str, Any]:
        """Get DAILY_PLAYS strategy configuration"""
        section = 'STRATEGY_DAILY_PLAYS'
        preferred_catalysts = self.config.get(section, 'preferred_catalysts', fallback='FDA,M&A,EARNINGS,CONTRACT')

        return {
            'min_volume': self.config.getint(section, 'min_volume', fallback=300000),
            'min_quality_score': self.config.getfloat(section, 'min_quality_score', fallback=60.0),
            'min_catalyst_strength': self.config.getfloat(section, 'min_catalyst_strength', fallback=5.0),
            'preferred_catalysts': [cat.strip() for cat in preferred_catalysts.split(',')],
            'max_gap_percent': self.config.getfloat(section, 'max_gap_percent', fallback=8.0),
            'stop_loss_percent': self.config.getfloat(section, 'stop_loss_percent', fallback=4.0),
            'take_profit_percent': self.config.getfloat(section, 'take_profit_percent', fallback=12.0),
            'max_position_size': self.config.getint(section, 'max_position_size', fallback=800),
            'min_price': self.config.getfloat(section, 'min_price', fallback=0.5),
            'max_price': self.config.getfloat(section, 'max_price', fallback=12.0),
            'consolidation_min_time_minutes': self.config.getint(section, 'consolidation_min_time_minutes', fallback=15)
        }

    def get_macdv_config(self) -> Dict[str, Any]:
        """Get MACDV strategy configuration"""
        section = 'STRATEGY_MACDV'
        return {
            'min_volume': self.config.getint(section, 'min_volume', fallback=400000),
            'min_volume_ratio': self.config.getfloat(section, 'min_volume_ratio', fallback=2.0),
            'macd_threshold': self.config.getfloat(section, 'macd_threshold', fallback=0.02),
            'confirmation_periods': self.config.getint(section, 'confirmation_periods', fallback=3),
            'min_momentum_score': self.config.getfloat(section, 'min_momentum_score', fallback=0.6),
            'max_rsi': self.config.getfloat(section, 'max_rsi', fallback=70.0),
            'stop_loss_percent': self.config.getfloat(section, 'stop_loss_percent', fallback=3.5),
            'take_profit_percent': self.config.getfloat(section, 'take_profit_percent', fallback=10.0),
            'max_position_size': self.config.getint(section, 'max_position_size', fallback=600),
            'min_price': self.config.getfloat(section, 'min_price', fallback=1.0),
            'max_price': self.config.getfloat(section, 'max_price', fallback=20.0)
        }

    def get_bull_flag_config(self) -> Dict[str, Any]:
        """Get BULL_FLAG strategy configuration"""
        section = 'STRATEGY_BULL_FLAG'
        return {
            'min_pole_height_percent': self.config.getfloat(section, 'min_pole_height_percent', fallback=3.0),
            'max_pole_height_percent': self.config.getfloat(section, 'max_pole_height_percent', fallback=25.0),
            'max_flag_range_percent': self.config.getfloat(section, 'max_flag_range_percent', fallback=3.0),
            'min_flag_duration_minutes': self.config.getint(section, 'min_flag_duration_minutes', fallback=10),
            'max_flag_duration_minutes': self.config.getint(section, 'max_flag_duration_minutes', fallback=60),
            'min_volume': self.config.getint(section, 'min_volume', fallback=200000),
            'volume_breakout_multiplier': self.config.getfloat(section, 'volume_breakout_multiplier', fallback=1.5),
            'stop_loss_percent': self.config.getfloat(section, 'stop_loss_percent', fallback=2.5),
            'take_profit_percent': self.config.getfloat(section, 'take_profit_percent', fallback=8.0),
            'max_position_size': self.config.getint(section, 'max_position_size', fallback=500),
            'min_price': self.config.getfloat(section, 'min_price', fallback=2.0),
            'max_price': self.config.getfloat(section, 'max_price', fallback=25.0)
        }

    def get_ibkr_config(self) -> Dict[str, Any]:
        """Get IBKR configuration"""
        section = 'IBKR'
        return {
            'host': self.config.get(section, 'host', fallback='127.0.0.1'),
            'port': self.config.getint(section, 'port', fallback=7497),
            'client_id': self.config.getint(section, 'client_id', fallback=6000),
            'client_id_scanner': self.config.getint(section, 'client_id_scanner', fallback=6010),
            'client_id_execution': self.config.getint(section, 'client_id_execution', fallback=6020),
            'client_id_gap_go_worker': self.config.getint(section, 'client_id_gap_go_worker', fallback=6030),
            'client_id_daily_plays_worker': self.config.getint(section, 'client_id_daily_plays_worker', fallback=6040),
            'client_id_macdv_worker': self.config.getint(section, 'client_id_macdv_worker', fallback=6050),
            'client_id_bull_flag_worker': self.config.getint(section, 'client_id_bull_flag_worker', fallback=6060)
        }