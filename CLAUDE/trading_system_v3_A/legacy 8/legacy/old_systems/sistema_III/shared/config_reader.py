#!/usr/bin/env python3
"""
Centralized Configuration Reader for Sistema_III
Simple, clean config management without ML complexity
"""

import os
import configparser
from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

@dataclass
class IBKRConfig:
    """IBKR connection configuration"""
    host: str
    port: int
    client_id_scanner: int
    client_id_execution: int
    client_id_gap_worker: int
    client_id_daily_worker: int
    client_id_macdv_worker: int
    client_id_bull_flag_worker: int

@dataclass
class MarketSessionsConfig:
    """Market timing configuration"""
    market_open: str
    market_close: str
    premarket_start: str
    aftermarket_end: str
    entry_start: str
    entry_end: str
    exit_before_close: str

@dataclass
class ScannerConfig:
    """Scanner parameters"""
    scan_interval_seconds: int
    max_candidates_per_cycle: int
    min_price: float
    max_price: float
    min_volume: int
    min_market_cap_millions: int
    max_market_cap_millions: int
    enable_intraday_momentum: bool
    enable_daily_bounce: bool
    enable_red_to_green: bool
    enable_bull_flag: bool

@dataclass
class RiskManagerConfig:
    """Risk management parameters"""
    max_portfolio_risk: float
    max_positions: int
    max_position_size: int
    min_position_size: int
    max_daily_trades: int
    max_daily_loss: float
    portfolio_capital: float
    max_risk_per_trade: float
    position_sizing_method: str

@dataclass
class ExecutionEngineConfig:
    """Execution engine parameters"""
    order_timeout_seconds: int
    max_slippage_percent: float
    use_market_orders: bool
    enable_bracket_orders: bool

@dataclass
class WorkersConfig:
    """Workers configuration"""
    gap_go_workers: int
    daily_plays_workers: int
    macdv_workers: int
    bull_flag_workers: int
    gap_go_opportunity_types: List[str]
    daily_plays_opportunity_types: List[str]
    macdv_opportunity_types: List[str]
    bull_flag_opportunity_types: List[str]

@dataclass
class StrategyConfig:
    """Individual strategy parameters"""
    name: str
    parameters: Dict[str, float]

@dataclass
class DatabaseConfig:
    """Database configuration"""
    positions_table: str
    reservations_table: str
    opportunities_table: str
    cleanup_old_opportunities_hours: int
    cleanup_old_reservations_hours: int

@dataclass
class CommunicationConfig:
    """Redis communication configuration"""
    redis_host: str
    redis_port: int
    redis_db: int
    redis_password: str
    scanner_channel: str
    execution_channel: str
    workers_status_channel: str
    message_timeout_seconds: int
    heartbeat_interval_seconds: int

@dataclass
class MonitoringConfig:
    """Monitoring and logging configuration"""
    enable_performance_monitoring: bool
    save_trade_history: bool
    enable_position_monitoring: bool
    monitoring_interval_seconds: int
    scanner_health_check_seconds: int
    worker_health_check_seconds: int
    execution_health_check_seconds: int

class Sistema3Config:
    """
    Centralized configuration for Sistema_III
    Loads from config.ini and provides typed access to all parameters
    """

    def __init__(self, config_path: str = "config.ini"):
        self.config_path = config_path
        self.config = configparser.ConfigParser()

        # Load configuration
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        self.config.read(config_path)

        # Initialize all configurations
        self.ibkr = self._load_ibkr_config()
        self.market_sessions = self._load_market_sessions_config()
        self.scanner = self._load_scanner_config()
        self.risk_manager = self._load_risk_manager_config()
        self.execution_engine = self._load_execution_engine_config()
        self.workers = self._load_workers_config()
        self.strategies = self._load_strategies_config()
        self.database = self._load_database_config()
        self.communication = self._load_communication_config()
        self.monitoring = self._load_monitoring_config()

        # System level config
        self.timezone = self.config.get('SYSTEM', 'timezone', fallback='America/New_York')
        self.log_level = self.config.get('SYSTEM', 'log_level', fallback='INFO')
        self.log_directory = self.config.get('SYSTEM', 'log_directory', fallback='logs/')
        self.database_path = self.config.get('SYSTEM', 'database_path', fallback='shared/positions.db')

        logging.info(f"✅ Sistema_III configuration loaded from {config_path}")

    def _load_ibkr_config(self) -> IBKRConfig:
        """Load IBKR configuration"""
        section = 'IBKR'
        return IBKRConfig(
            host=self.config.get(section, 'host', fallback='127.0.0.1'),
            port=self.config.getint(section, 'port', fallback=7497),
            client_id_scanner=self.config.getint(section, 'client_id_scanner', fallback=6120),
            client_id_execution=self.config.getint(section, 'client_id_execution', fallback=6121),
            client_id_gap_worker=self.config.getint(section, 'client_id_gap_worker', fallback=6122),
            client_id_daily_worker=self.config.getint(section, 'client_id_daily_worker', fallback=6123),
            client_id_macdv_worker=self.config.getint(section, 'client_id_macdv_worker', fallback=6124),
            client_id_bull_flag_worker=self.config.getint(section, 'client_id_bull_flag_worker', fallback=6125)
        )

    def _load_market_sessions_config(self) -> MarketSessionsConfig:
        """Load market sessions configuration"""
        section = 'MARKET_SESSIONS'
        return MarketSessionsConfig(
            market_open=self.config.get(section, 'market_open', fallback='09:30'),
            market_close=self.config.get(section, 'market_close', fallback='16:00'),
            premarket_start=self.config.get(section, 'premarket_start', fallback='04:00'),
            aftermarket_end=self.config.get(section, 'aftermarket_end', fallback='20:00'),
            entry_start=self.config.get(section, 'entry_start', fallback='09:30'),
            entry_end=self.config.get(section, 'entry_end', fallback='15:30'),
            exit_before_close=self.config.get(section, 'exit_before_close', fallback='15:57')
        )

    def _load_scanner_config(self) -> ScannerConfig:
        """Load scanner configuration"""
        section = 'SCANNER'
        return ScannerConfig(
            scan_interval_seconds=self.config.getint(section, 'scan_interval_seconds', fallback=30),
            max_candidates_per_cycle=self.config.getint(section, 'max_candidates_per_cycle', fallback=20),
            min_price=self.config.getfloat(section, 'min_price', fallback=1.0),
            max_price=self.config.getfloat(section, 'max_price', fallback=15.0),
            min_volume=self.config.getint(section, 'min_volume', fallback=100000),
            min_market_cap_millions=self.config.getint(section, 'min_market_cap_millions', fallback=50),
            max_market_cap_millions=self.config.getint(section, 'max_market_cap_millions', fallback=2000),
            enable_intraday_momentum=self.config.getboolean(section, 'enable_intraday_momentum', fallback=True),
            enable_daily_bounce=self.config.getboolean(section, 'enable_daily_bounce', fallback=True),
            enable_red_to_green=self.config.getboolean(section, 'enable_red_to_green', fallback=True),
            enable_bull_flag=self.config.getboolean(section, 'enable_bull_flag', fallback=True)
        )

    def _load_risk_manager_config(self) -> RiskManagerConfig:
        """Load risk manager configuration"""
        section = 'RISK_MANAGER'
        return RiskManagerConfig(
            max_portfolio_risk=self.config.getfloat(section, 'max_portfolio_risk', fallback=0.02),
            max_positions=self.config.getint(section, 'max_positions', fallback=5),
            max_position_size=self.config.getint(section, 'max_position_size', fallback=500),
            min_position_size=self.config.getint(section, 'min_position_size', fallback=100),
            max_daily_trades=self.config.getint(section, 'max_daily_trades', fallback=20),
            max_daily_loss=self.config.getfloat(section, 'max_daily_loss', fallback=-1000.0),
            portfolio_capital=self.config.getfloat(section, 'portfolio_capital', fallback=30000),
            max_risk_per_trade=self.config.getfloat(section, 'max_risk_per_trade', fallback=0.015),
            position_sizing_method=self.config.get(section, 'position_sizing_method', fallback='FIXED')
        )

    def _load_execution_engine_config(self) -> ExecutionEngineConfig:
        """Load execution engine configuration"""
        section = 'EXECUTION_ENGINE'
        return ExecutionEngineConfig(
            order_timeout_seconds=self.config.getint(section, 'order_timeout_seconds', fallback=30),
            max_slippage_percent=self.config.getfloat(section, 'max_slippage_percent', fallback=0.5),
            use_market_orders=self.config.getboolean(section, 'use_market_orders', fallback=True),
            enable_bracket_orders=self.config.getboolean(section, 'enable_bracket_orders', fallback=False)
        )

    def _load_workers_config(self) -> WorkersConfig:
        """Load workers configuration"""
        section = 'WORKERS'

        def parse_list(value: str) -> List[str]:
            return [item.strip() for item in value.split(',') if item.strip()]

        return WorkersConfig(
            gap_go_workers=self.config.getint(section, 'gap_go_workers', fallback=1),
            daily_plays_workers=self.config.getint(section, 'daily_plays_workers', fallback=1),
            macdv_workers=self.config.getint(section, 'macdv_workers', fallback=1),
            bull_flag_workers=self.config.getint(section, 'bull_flag_workers', fallback=1),
            gap_go_opportunity_types=parse_list(self.config.get(section, 'gap_go_opportunity_types', fallback='INTRADAY_MOMENTUM')),
            daily_plays_opportunity_types=parse_list(self.config.get(section, 'daily_plays_opportunity_types', fallback='DAILY_BOUNCE')),
            macdv_opportunity_types=parse_list(self.config.get(section, 'macdv_opportunity_types', fallback='INTRADAY_MOMENTUM,DAILY_BOUNCE')),
            bull_flag_opportunity_types=parse_list(self.config.get(section, 'bull_flag_opportunity_types', fallback='RED_TO_GREEN,INTRADAY_MOMENTUM'))
        )

    def _load_strategies_config(self) -> Dict[str, StrategyConfig]:
        """Load all strategy configurations"""
        strategies = {}

        for section_name in self.config.sections():
            if section_name.startswith('STRATEGY_'):
                strategy_name = section_name.replace('STRATEGY_', '').lower()
                parameters = {}

                for key, value in self.config.items(section_name):
                    try:
                        # Try to convert to float
                        parameters[key] = float(value)
                    except ValueError:
                        # Keep as string if conversion fails
                        parameters[key] = value

                strategies[strategy_name] = StrategyConfig(
                    name=strategy_name,
                    parameters=parameters
                )

        return strategies

    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration"""
        section = 'DATABASE'
        return DatabaseConfig(
            positions_table=self.config.get(section, 'positions_table', fallback='positions'),
            reservations_table=self.config.get(section, 'reservations_table', fallback='reservations'),
            opportunities_table=self.config.get(section, 'opportunities_table', fallback='opportunities'),
            cleanup_old_opportunities_hours=self.config.getint(section, 'cleanup_old_opportunities_hours', fallback=24),
            cleanup_old_reservations_hours=self.config.getint(section, 'cleanup_old_reservations_hours', fallback=2)
        )

    def _load_communication_config(self) -> CommunicationConfig:
        """Load communication configuration"""
        section = 'COMMUNICATION'
        return CommunicationConfig(
            redis_host=self.config.get(section, 'redis_host', fallback='localhost'),
            redis_port=self.config.getint(section, 'redis_port', fallback=6379),
            redis_db=self.config.getint(section, 'redis_db', fallback=0),
            redis_password=self.config.get(section, 'redis_password', fallback=''),
            scanner_channel=self.config.get(section, 'scanner_channel', fallback='scanner_opportunities'),
            execution_channel=self.config.get(section, 'execution_channel', fallback='execution_commands'),
            workers_status_channel=self.config.get(section, 'workers_status_channel', fallback='workers_status'),
            message_timeout_seconds=self.config.getint(section, 'message_timeout_seconds', fallback=10),
            heartbeat_interval_seconds=self.config.getint(section, 'heartbeat_interval_seconds', fallback=30)
        )

    def _load_monitoring_config(self) -> MonitoringConfig:
        """Load monitoring configuration"""
        section = 'MONITORING'
        return MonitoringConfig(
            enable_performance_monitoring=self.config.getboolean(section, 'enable_performance_monitoring', fallback=True),
            save_trade_history=self.config.getboolean(section, 'save_trade_history', fallback=True),
            enable_position_monitoring=self.config.getboolean(section, 'enable_position_monitoring', fallback=True),
            monitoring_interval_seconds=self.config.getint(section, 'monitoring_interval_seconds', fallback=60),
            scanner_health_check_seconds=self.config.getint(section, 'scanner_health_check_seconds', fallback=120),
            worker_health_check_seconds=self.config.getint(section, 'worker_health_check_seconds', fallback=90),
            execution_health_check_seconds=self.config.getint(section, 'execution_health_check_seconds', fallback=60)
        )

    def get_strategy_config(self, strategy_name: str) -> Optional[StrategyConfig]:
        """Get configuration for a specific strategy"""
        return self.strategies.get(strategy_name.lower())

    def get_client_id_for_worker(self, worker_type: str) -> int:
        """Get the appropriate client_id for a worker type"""
        worker_client_ids = {
            'gap_go': self.ibkr.client_id_gap_worker,
            'daily_plays': self.ibkr.client_id_daily_worker,
            'macdv': self.ibkr.client_id_macdv_worker,
            'bull_flag': self.ibkr.client_id_bull_flag_worker,
            'scanner': self.ibkr.client_id_scanner,
            'execution': self.ibkr.client_id_execution
        }

        return worker_client_ids.get(worker_type, self.ibkr.client_id_execution)

    def validate_config(self) -> bool:
        """Validate configuration sanity"""
        try:
            # Check required sections exist
            required_sections = ['IBKR', 'RISK_MANAGER', 'SCANNER', 'EXECUTION_ENGINE']
            for section in required_sections:
                if not self.config.has_section(section):
                    logging.error(f"Missing required configuration section: {section}")
                    return False

            # Check client_id uniqueness
            client_ids = [
                self.ibkr.client_id_scanner,
                self.ibkr.client_id_execution,
                self.ibkr.client_id_gap_worker,
                self.ibkr.client_id_daily_worker,
                self.ibkr.client_id_macdv_worker,
                self.ibkr.client_id_bull_flag_worker
            ]

            if len(client_ids) != len(set(client_ids)):
                logging.error("IBKR client_id values must be unique")
                return False

            # Check risk parameters make sense
            if self.risk_manager.max_risk_per_trade > self.risk_manager.max_portfolio_risk:
                logging.warning("max_risk_per_trade > max_portfolio_risk - may limit opportunities")

            logging.info("✅ Configuration validation passed")
            return True

        except Exception as e:
            logging.error(f"Configuration validation failed: {e}")
            return False


# Global config instance
_config_instance = None

def get_config(config_path: str = "config.ini") -> Sistema3Config:
    """Get the global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Sistema3Config(config_path)
    return _config_instance

def reload_config(config_path: str = "config.ini") -> Sistema3Config:
    """Reload configuration from file"""
    global _config_instance
    _config_instance = Sistema3Config(config_path)
    return _config_instance