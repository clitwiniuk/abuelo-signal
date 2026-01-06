# run_trading_system.py
"""
Script simplificado para ejecutar el sistema de trading.
Este script carga la configuración y ejecuta el sistema.
"""

import asyncio
import logging
import sys
import os
import configparser
from pathlib import Path

# Añadir el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Imports del sistema
from core.interfaces import TradingConfig
from strategies.macdv_strategy import MACDVStrategy
from strategies.gap_go_strategy import GapGoStrategy
from strategies.vwap_strategy import VWAPSmallcapsStrategy  # ← NUEVO IMPORT
from strategies.multi_strategy_engine import MultiStrategyEngine
from strategies import register_strategy


def get_config_value_with_global_fallback(config, section, key, fallback_value, data_type='float'):
    """
    Helper function to get configuration values with GLOBAL section as fallback
    
    Priority order:
    1. Section-specific value
    2. GLOBAL section value
    3. Provided fallback value
    """
    try:
        # Try to get global value first as fallback
        global_fallback = fallback_value
        if config.has_section('GLOBAL') and config.has_option('GLOBAL', key):
            if data_type == 'float':
                global_fallback = config.getfloat('GLOBAL', key)
            elif data_type == 'int':
                global_fallback = config.getint('GLOBAL', key)
            elif data_type == 'bool':
                global_fallback = config.getboolean('GLOBAL', key)
            else:
                global_fallback = config.get('GLOBAL', key)
        
        # Try to get section-specific value, falling back to global or default
        if data_type == 'float':
            return config.getfloat(section, key, fallback=global_fallback)
        elif data_type == 'int':
            return config.getint(section, key, fallback=global_fallback)
        elif data_type == 'bool':
            return config.getboolean(section, key, fallback=global_fallback)
        else:
            return config.get(section, key, fallback=global_fallback)
            
    except Exception:
        return fallback_value


def setup_logging():
    """Configurar logging básico"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('trading_system.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Configurar niveles de logging específicos para estrategias
    from utils.log_config import configure_strategy_logging
    
    # Reducir verbosidad de MACDV a WARNING para mensajes regulares
    strategy_log_levels = {
        'MACDV': 'WARNING'  # Solo mostrará WARNING, ERROR y CRITICAL
    }
    
    configure_strategy_logging(strategy_log_levels)


def load_config_from_ini() -> TradingConfig:
    """Cargar configuración desde config.ini (compatibilidad con tu sistema actual)"""
    import configparser
    
    config = configparser.ConfigParser()
    config_file = current_dir / 'config.ini'
    
    if config_file.exists():
        config.read(config_file)
        print(f"✅ Configuración cargada desde: {config_file}")
    else:
        print(f"⚠️ No se encontró config.ini en {config_file}, usando valores por defecto")
    
    # Extraer valores con fallbacks
    return TradingConfig(
        max_positions=config.getint('TRADING', 'max_positions', fallback=5),
        max_risk_per_trade=config.getfloat('TRADING', 'max_risk_per_trade', fallback=0.02),
        max_daily_loss=config.getfloat('TRADING', 'max_daily_loss', fallback=-500.0),
        max_daily_trades=config.getint('TRADING', 'max_daily_trades', fallback=20),
        enable_filters=config.getboolean('TRADING', 'use_volume_filter', fallback=True),
        portfolio_capital=config.getfloat('TRADING', 'portfolio_capital', fallback=2000.0),
        
        # IBKR config
        broker_host=config.get('IBKR', 'host', fallback='127.0.0.1'),
        broker_port=config.getint('IBKR', 'port', fallback=7497),
        broker_client_id=config.getint('IBKR', 'client_id', fallback=1),
        
        # Strategy config
        strategy_name=config.get('TRADING', 'strategy', fallback='macdv'),
        timeframe=config.get('TRADING', 'timeframe', fallback='1 min'),
        
        # Logging
        log_level=config.get('LOGGING', 'level', fallback='INFO'),
        log_file=config.get('LOGGING', 'file', fallback='trading_system.log')
    )


def get_strategy_parameters(config: configparser.ConfigParser, strategy_name: str) -> dict:
    """
    Cargar parámetros específicos de estrategia desde config.ini
    Aplica perfiles TESTING o PRODUCTION según configuración
    """
    params = {}
    
    # Determinar perfil activo
    active_profile = config.get('TRADING', 'active_profile', fallback='PRODUCTION')
    profile_section = f"{active_profile}_PROFILE"
    
    print(f"🎯 Usando perfil: {active_profile}")
    if config.has_section(profile_section):
        print(f"✅ Perfil {active_profile} encontrado, aplicando parámetros personalizados")
    else:
        print(f"⚠️ Perfil {active_profile} no encontrado, usando valores por defecto")
    
    if strategy_name == 'macdv':
        section = 'MACDV_STRATEGY'
        if config.has_section(section):
            params = {
                # MACD parameters optimized for smallcaps
                'macd_fast': config.getint(section, 'macd_fast', fallback=5),
                'macd_slow': config.getint(section, 'macd_slow', fallback=13),
                'macd_signal': config.getint(section, 'macd_signal', fallback=3),
                # Volume parameters (con override del perfil)
                'volume_threshold': config.getfloat(profile_section, 'macdv_volume_threshold', 
                                                   fallback=config.getfloat(section, 'volume_threshold', fallback=1.5)),
                'volume_period': config.getint(section, 'volume_period', fallback=10),
                'volume_spike_threshold': config.getfloat(profile_section, 'macdv_volume_spike_threshold',
                                                        fallback=config.getfloat(section, 'volume_spike_threshold', fallback=2.0)),
                # Price filters (inherit from GLOBAL)
                'min_price': get_config_value_with_global_fallback(config, section, 'min_price', 1.0),
                'max_price': get_config_value_with_global_fallback(config, section, 'max_price', 25.0),
                # RSI parameters
                'rsi_period': config.getint(section, 'rsi_period', fallback=7),
                'rsi_overbought': config.getint(section, 'rsi_overbought', fallback=75),
                # Risk management
                'stop_loss_pct': config.getfloat(section, 'stop_loss_pct', fallback=0.08),
                'take_profit_pct': config.getfloat(section, 'take_profit_pct', fallback=0.15),
                'trailing_stop_activation': config.getfloat(section, 'trailing_stop_activation', fallback=0.08),
                'trailing_stop_distance': config.getfloat(section, 'trailing_stop_distance', fallback=0.04),
                # Position sizing
                'max_position_value': config.getfloat(section, 'max_position_value', fallback=300.0),
                'min_position_value': config.getfloat(section, 'min_position_value', fallback=50.0),
                'max_quantity': config.getint(section, 'max_quantity', fallback=200),
                'min_quantity': config.getint(section, 'min_quantity', fallback=10),
                'risk_per_trade': config.getfloat(section, 'risk_per_trade', fallback=0.015),
                # Timing
                'max_hold_hours': config.getint(section, 'max_hold_hours', fallback=8),
                'min_conditions': config.getint(profile_section, 'macdv_min_conditions',
                                               fallback=config.getint(section, 'min_conditions', fallback=3))
            }
    
    elif strategy_name == 'gap_go':
        section = 'GAP_GO_STRATEGY'
        if config.has_section(section):
            params = {
                # Gap parameters (con override del perfil)
                'min_gap_percent': config.getfloat(profile_section, 'gap_go_min_gap_percent',
                                                  fallback=config.getfloat(section, 'min_gap_percent', fallback=3.0)),
                'max_gap_percent': config.getfloat(section, 'max_gap_percent', fallback=25.0),
                'gap_timeout_minutes': config.getint(section, 'gap_timeout_minutes', fallback=30),
                
                # Volume parameters (con override del perfil)
                'volume_multiplier': config.getfloat(profile_section, 'gap_go_volume_multiplier',
                                                   fallback=config.getfloat(section, 'volume_multiplier', fallback=2.0)),
                'volume_period': config.getint(section, 'volume_period', fallback=20),
                'min_volume': config.getint(profile_section, 'gap_go_min_volume',
                                          fallback=config.getint(section, 'min_volume', fallback=100000)),
                'premarket_volume_min': config.getint(profile_section, 'gap_go_premarket_volume_min',
                                                     fallback=config.getint(section, 'premarket_volume_min', fallback=10000)),
                
                # Price filters (inherit from GLOBAL)
                'max_price': get_config_value_with_global_fallback(config, section, 'max_price', 20.0),
                'min_price': get_config_value_with_global_fallback(config, section, 'min_price', 1.0),
                
                # Price action
                'breakout_buffer': config.getfloat(section, 'breakout_buffer', fallback=0.002),
                'first_candle_minutes': config.getint(section, 'first_candle_minutes', fallback=5),
                
                # Risk management
                'stop_loss_pct': config.getfloat(section, 'stop_loss_pct', fallback=0.05),
                'profit_target_1': config.getfloat(section, 'profit_target_1', fallback=0.10),
                'profit_target_2': config.getfloat(section, 'profit_target_2', fallback=0.20),
                'risk_reward_ratio': config.getfloat(section, 'risk_reward_ratio', fallback=2.0),
                
                # Time management
                'market_open_hour': config.getfloat(section, 'market_open_hour', fallback=9.5),
                'market_close_hour': config.getfloat(section, 'market_close_hour', fallback=16.0),
                'no_entry_after_hour': config.getfloat(section, 'no_entry_after_hour', fallback=11.0),
                'end_day_exit_hour': config.getfloat(section, 'end_day_exit_hour', fallback=15.5),
                
                # Position sizing
                'max_position_value': config.getfloat(section, 'max_position_value', fallback=300.0),
                'min_quantity': config.getint(section, 'min_quantity', fallback=10),
                'max_risk_per_trade': config.getfloat(section, 'max_risk_per_trade', fallback=0.02),
                
                # Gap direction
                'allow_gap_up': config.getboolean(section, 'allow_gap_up', fallback=True),
                'allow_gap_down': config.getboolean(section, 'allow_gap_down', fallback=True),
                
                # History
                'min_history_days': config.getint(section, 'min_history_days', fallback=20),
                'max_history_bars': config.getint(section, 'max_history_bars', fallback=500)
            }
    
    elif strategy_name == 'optimized_gap_go':
        section = 'OPTIMIZED_GAP_GO_STRATEGY'
        if config.has_section(section):
            params = {
                # Scanner Integration
                'trust_scanner_gap': config.getboolean(section, 'trust_scanner_gap', fallback=True),
                'trust_scanner_volume': config.getboolean(section, 'trust_scanner_volume', fallback=True),
                'scanner_gap_timeout': config.getint(section, 'scanner_gap_timeout', fallback=15),
                
                # Entry conditions
                'breakout_buffer': config.getfloat(section, 'breakout_buffer', fallback=0.001),
                'momentum_bars': config.getint(section, 'momentum_bars', fallback=2),
                'gap_fill_buffer': config.getfloat(section, 'gap_fill_buffer', fallback=0.03),
                
                # Risk Management
                'stop_loss_pct': config.getfloat(section, 'stop_loss_pct', fallback=0.05),
                'profit_target': config.getfloat(section, 'profit_target', fallback=0.12),
                'trailing_activation': config.getfloat(section, 'trailing_activation', fallback=0.06),
                'trailing_distance': config.getfloat(section, 'trailing_distance', fallback=0.03),
                
                # Position Sizing
                'max_position_value': config.getfloat(section, 'max_position_value', fallback=300.0),
                'min_position_value': config.getfloat(section, 'min_position_value', fallback=50.0),
                'max_risk_per_trade': config.getfloat(section, 'max_risk_per_trade', fallback=0.015),
                'min_quantity': config.getint(section, 'min_quantity', fallback=10),
                
                # Timing
                'market_open_hour': config.getfloat(section, 'market_open_hour', fallback=9.5),
                'no_entry_after': config.getfloat(section, 'no_entry_after', fallback=11.0),
                'max_hold_time': config.getint(section, 'max_hold_time', fallback=90),
                
                # Filters (inherit from GLOBAL)
                'min_price': get_config_value_with_global_fallback(config, section, 'min_price', 1.50),
                'max_price': get_config_value_with_global_fallback(config, section, 'max_price', 20.0),
                'min_daily_volume': config.getint(section, 'min_daily_volume', fallback=150000),
                
                # Commission
                'commission_per_share': config.getfloat(section, 'commission_per_share', fallback=0.005),
                'min_commission': config.getfloat(section, 'min_commission', fallback=1.0),
                'max_history_bars': config.getint(section, 'max_history_bars', fallback=200)
            }
    
    elif strategy_name == 'vwap_smallcaps':
        section = 'VWAP_SMALLCAPS'
        if config.has_section(section):
            params = {
                # Parámetros Técnicos
                'vwap_period': config.getint(section, 'vwap_period', fallback=20),
                'momentum_period': config.getint(section, 'momentum_period', fallback=5),
                
                # Filtros Smallcaps (inherit from GLOBAL)
                'min_price': get_config_value_with_global_fallback(config, section, 'min_price', 1.0),
                'max_price': get_config_value_with_global_fallback(config, section, 'max_price', 20.0),
                'volatility_threshold': config.getfloat(section, 'volatility_threshold', fallback=0.03),
                'volume_threshold': config.getfloat(section, 'volume_threshold', fallback=1.5),
                'min_volume_ratio': config.getfloat(section, 'min_volume_ratio', fallback=0.5),
                
                # Gestión de Riesgo
                'risk_management_mode': config.get(section, 'risk_management_mode', fallback='dynamic'),
                'initial_stop_loss': config.getfloat(section, 'initial_stop_loss', fallback=0.05),
                'trailing_stop_distance': config.getfloat(section, 'trailing_stop_distance', fallback=0.08),
                'partial_take_profit': config.getfloat(section, 'partial_take_profit', fallback=0.12),
                'max_hold_days': config.getint(section, 'max_hold_days', fallback=30),
                
                # Señales
                'vwap_entry_threshold': config.getfloat(section, 'vwap_entry_threshold', fallback=0.99),
                'momentum_entry_threshold': config.getfloat(section, 'momentum_entry_threshold', fallback=0.01),
                'vwap_exit_threshold': config.getfloat(section, 'vwap_exit_threshold', fallback=1.01),
                'momentum_exit_threshold': config.getfloat(section, 'momentum_exit_threshold', fallback=-0.015),
                
                # Parámetros Generales
                'confidence_base': config.getfloat(section, 'confidence_base', fallback=0.3),
                'confidence_multiplier': config.getfloat(section, 'confidence_multiplier', fallback=10.0),
                'max_confidence': config.getfloat(section, 'max_confidence', fallback=0.9),
                
                # Trading
                'max_position_value': config.getfloat(section, 'max_position_value', fallback=300.0),
                'min_position_value': config.getfloat(section, 'min_position_value', fallback=80.0),
                'max_risk_per_trade': config.getfloat(section, 'max_risk_per_trade', fallback=0.02),
                'min_quantity': config.getint(section, 'min_quantity', fallback=5),
                'position_size': config.getfloat(section, 'position_size', fallback=0.02),
                'max_positions': config.getint(section, 'max_positions', fallback=5),
                
                # Timing Controls
                'market_open_hour': config.getfloat(section, 'market_open_hour', fallback=9.5),
                'no_entry_after': config.getfloat(section, 'no_entry_after', fallback=13.0),
                'max_hold_time': config.getint(section, 'max_hold_time', fallback=90),
                'cooldown_period': config.getint(section, 'cooldown_period', fallback=60),
                
                # Trading Limits
                'max_daily_trades': config.getint(section, 'max_daily_trades', fallback=5),
                'max_concurrent_positions': config.getint(section, 'max_concurrent_positions', fallback=3),
                'daily_loss_limit': config.getfloat(section, 'daily_loss_limit', fallback=150.0),
                
                # Commission & Costs
                'commission_per_share': config.getfloat(section, 'commission_per_share', fallback=0.005),
                'min_commission': config.getfloat(section, 'min_commission', fallback=1.0),
                'slippage_bps': config.getint(section, 'slippage_bps', fallback=5),
            }
    
    elif strategy_name == 'orb':
        section = 'ORB_STRATEGY'
        if config.has_section(section):
            params = {
                # Opening Range Breakout parameters
                'opening_range_minutes': config.getint(section, 'opening_range_minutes', fallback=20),
                'range_min_size': config.getfloat(section, 'range_min_size', fallback=0.03),
                'range_max_size': config.getfloat(section, 'range_max_size', fallback=0.12),
                'volume_spike_threshold': config.getfloat(section, 'volume_spike_threshold', fallback=3.5),
                'volume_confirmation_threshold': config.getfloat(section, 'volume_confirmation_threshold', fallback=2.5),
                'volume_period': config.getint(section, 'volume_period', fallback=20),
                # Price filters (inherit from GLOBAL)
                'min_price': get_config_value_with_global_fallback(config, section, 'min_price', 2.00),
                'max_price': get_config_value_with_global_fallback(config, section, 'max_price', 12.0),
                'min_dollar_volume': config.getint(section, 'min_dollar_volume', fallback=200000),
                'breakout_min_size': config.getfloat(section, 'breakout_min_size', fallback=0.01),
                'consolidation_bars': config.getint(section, 'consolidation_bars', fallback=3),
                'stop_loss_pct': config.getfloat(section, 'stop_loss_pct', fallback=0.06),
                'profit_target': config.getfloat(section, 'profit_target', fallback=0.18),
                'trailing_stop_activation': config.getfloat(section, 'trailing_stop_activation', fallback=0.10),
                'trailing_stop_distance': config.getfloat(section, 'trailing_stop_distance', fallback=0.05),
                'max_position_value': config.getfloat(section, 'max_position_value', fallback=300.0),
                'min_position_value': config.getfloat(section, 'min_position_value', fallback=80.0),
                'risk_per_trade': config.getfloat(section, 'risk_per_trade', fallback=0.008),
                'min_quantity': config.getint(section, 'min_quantity', fallback=10),
                'commission_per_share': config.getfloat(section, 'commission_per_share', fallback=0.01),
                'min_commission': config.getfloat(section, 'min_commission', fallback=1.0),
                'max_gap_size': config.getfloat(section, 'max_gap_size', fallback=0.15),
                'min_conditions': config.getint(section, 'min_conditions', fallback=6),
                'trading_start_time': config.get(section, 'trading_start_time', fallback='09:30:00'),
                'trading_end_time': config.get(section, 'trading_end_time', fallback='13:00:00'),
                'max_hold_hours': config.getfloat(section, 'max_hold_hours', fallback=3.5),
                'signal_cooldown_bars': config.getint(section, 'signal_cooldown_bars', fallback=10),
                'max_signals_per_symbol': config.getint(section, 'max_signals_per_symbol', fallback=1),
                'min_avg_volume': config.getint(section, 'min_avg_volume', fallback=500000),
                'max_volatility': config.getfloat(section, 'max_volatility', fallback=0.25),
                'min_market_cap': config.getint(section, 'min_market_cap', fallback=50000000),
                'max_history_bars': config.getint(section, 'max_history_bars', fallback=100),
            }
    
    elif strategy_name == 'volume_breakout':
        section = 'VOLUME_BREAKOUT_STRATEGY'
        if config.has_section(section):
            params = {
                # Breakout detection
                'lookback_periods': config.getint(section, 'lookback_periods', fallback=20),
                'breakout_buffer': config.getfloat(section, 'breakout_buffer', fallback=0.008),
                'min_breakout_move': config.getfloat(section, 'min_breakout_move', fallback=0.012),
                'max_breakout_move': config.getfloat(section, 'max_breakout_move', fallback=0.08),
                # Volume analysis
                'volume_multiplier': config.getfloat(section, 'volume_multiplier', fallback=2.0),
                'volume_lookback': config.getint(section, 'volume_lookback', fallback=30),
                'min_volume_threshold': config.getint(section, 'min_volume_threshold', fallback=8000),
                'volume_spike_multiplier': config.getfloat(section, 'volume_spike_multiplier', fallback=3.0),
                # Momentum & RSI
                'momentum_periods': config.getint(section, 'momentum_periods', fallback=10),
                'momentum_threshold': config.getfloat(section, 'momentum_threshold', fallback=0.005),
                'rsi_overbought': config.getint(section, 'rsi_overbought', fallback=75),
                'rsi_oversold': config.getint(section, 'rsi_oversold', fallback=25),
                'rsi_periods': config.getint(section, 'rsi_periods', fallback=14),
                # Risk management
                'stop_loss_pct': config.getfloat(section, 'stop_loss_pct', fallback=0.025),
                'take_profit_pct': config.getfloat(section, 'take_profit_pct', fallback=0.08),
                'trailing_stop_pct': config.getfloat(section, 'trailing_stop_pct', fallback=0.015),
                'trailing_activation': config.getfloat(section, 'trailing_activation', fallback=0.018),
                'aggressive_trailing_pct': config.getfloat(section, 'aggressive_trailing_pct', fallback=0.012),
                'aggressive_trailing_threshold': config.getfloat(section, 'aggressive_trailing_threshold', fallback=0.05),
                # Dynamic take profit
                'dynamic_take_profit': config.getboolean(section, 'dynamic_take_profit', fallback=True),
                'tp_step_size': config.getfloat(section, 'tp_step_size', fallback=0.025),
                'tp_move_ratio': config.getfloat(section, 'tp_move_ratio', fallback=0.6),
                'max_take_profit': config.getfloat(section, 'max_take_profit', fallback=0.25),
                # Partial profits
                'partial_profit_enabled': config.getboolean(section, 'partial_profit_enabled', fallback=True),
                'partial_profit_threshold': config.getfloat(section, 'partial_profit_threshold', fallback=0.06),
                'partial_profit_size': config.getfloat(section, 'partial_profit_size', fallback=0.5),
                # Position management
                'max_hold_time': config.getint(section, 'max_hold_time', fallback=150),
                'max_daily_trades': config.getint(section, 'max_daily_trades', fallback=8),
                'max_concurrent_positions': config.getint(section, 'max_concurrent_positions', fallback=4),
                'cooldown_minutes': config.getint(section, 'cooldown_minutes', fallback=45),
                'daily_loss_limit': config.getfloat(section, 'daily_loss_limit', fallback=100.0),
                # Position sizing
                'base_position_value': config.getfloat(section, 'base_position_value', fallback=150.0),
                'min_position_value': config.getfloat(section, 'min_position_value', fallback=50.0),
                'max_position_value': config.getfloat(section, 'max_position_value', fallback=300.0),
                'volatility_adjustment': config.getboolean(section, 'volatility_adjustment', fallback=True),
                # Price filters (inherit from GLOBAL)
                'min_price': get_config_value_with_global_fallback(config, section, 'min_price', 1.2),
                'max_price': get_config_value_with_global_fallback(config, section, 'max_price', 85.0),
                'min_spread_pct': config.getfloat(section, 'min_spread_pct', fallback=0.001),
                'max_spread_pct': config.getfloat(section, 'max_spread_pct', fallback=0.035),
                # Trading hours
                'market_open_hour': config.getfloat(section, 'market_open_hour', fallback=9.5),
                'market_close_hour': config.getfloat(section, 'market_close_hour', fallback=15.5),
                'avoid_first_minutes': config.getint(section, 'avoid_first_minutes', fallback=15),
                'avoid_last_minutes': config.getint(section, 'avoid_last_minutes', fallback=30),
                # Quality filters
                'min_daily_volume': config.getint(section, 'min_daily_volume', fallback=75000),
                'min_price_change': config.getfloat(section, 'min_price_change', fallback=0.008),
            }
    
    elif strategy_name == 'multi_strategy':
        # Load parameters for all enabled strategies
        multi_section = 'MULTI_STRATEGY'
        params = {
            'enabled_strategies': config.get(profile_section, 'multi_strategy_enabled_strategies',
                                           fallback=config.get(multi_section, 'enabled_strategies', fallback='macdv_smallcaps,gap_go,orb,volume_breakout')).split(','),
            'default_confidence_threshold': config.getfloat(profile_section, 'multi_strategy_default_confidence_threshold',
                                                          fallback=config.getfloat(multi_section, 'default_confidence_threshold', fallback=0.6)),
            'max_concurrent_strategies': config.getint(multi_section, 'max_concurrent_strategies', fallback=4),
            'strategy_selection_mode': config.get(multi_section, 'strategy_selection_mode', fallback='confidence_based'),
            'learning_enabled': config.getboolean(multi_section, 'learning_enabled', fallback=True),
            'symbol_memory_enabled': config.getboolean(multi_section, 'symbol_memory_enabled', fallback=True),
            'performance_tracking': config.getboolean(multi_section, 'performance_tracking', fallback=True),
        }
        
        # Load parameters for each enabled strategy
        enabled_strategies = params['enabled_strategies']
        for strategy in enabled_strategies:
            strategy_key = strategy.strip()
            if strategy_key == 'macdv_smallcaps':
                params['macdv'] = get_strategy_parameters(config, 'macdv')
            elif strategy_key == 'gap_go':
                params['gap_go'] = get_strategy_parameters(config, 'gap_go') 
            elif strategy_key == 'orb':
                params['orb'] = get_strategy_parameters(config, 'orb')
            elif strategy_key == 'volume_breakout':
                params['volume_breakout'] = get_strategy_parameters(config, 'volume_breakout')
            elif strategy_key == 'vwap_smallcaps':
                params['vwap_smallcaps'] = get_strategy_parameters(config, 'vwap_smallcaps')
    
    return params


async def main():
    """Función principal"""
    print("\n🚀 INICIANDO SISTEMA DE TRADING MEJORADO")
    print("=" * 50)
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger("Main")
    
    try:
        # Cargar configuración completa PRIMERO para parámetros de estrategia
        config_parser = configparser.ConfigParser()
        config_file = current_dir / 'config.ini'
        if config_file.exists():
            config_parser.read(config_file)
        
        # Registrar estrategias disponibles con sus parámetros
        register_strategy('macdv', lambda params=None: MACDVStrategy(params or get_strategy_parameters(config_parser, 'macdv')))
        register_strategy('gap_go', lambda params=None: GapGoStrategy(params or get_strategy_parameters(config_parser, 'gap_go')))
        register_strategy('vwap_smallcaps', lambda params=None: VWAPSmallcapsStrategy(params or get_strategy_parameters(config_parser, 'vwap_smallcaps')))
        register_strategy('multi_strategy', lambda params=None: MultiStrategyEngine(params or get_strategy_parameters(config_parser, 'multi_strategy')))
        
        logger.info("Estrategias registradas: macdv, gap_go, vwap_smallcaps, multi_strategy")
        
        # Cargar configuración
        trading_config = load_config_from_ini()
        
        logger.info(f"Configuración cargada: {trading_config.strategy_name} strategy")
        
        # Mostrar información del perfil activo
        active_profile = config_parser.get('TRADING', 'active_profile', fallback='PRODUCTION')
        print(f"\n🎯 PERFIL ACTIVO: {active_profile}")
        if active_profile == 'TESTING':
            print("   📝 Modo PRUEBAS - Umbrales permisivos para generar señales")
            print("   ⚠️  Ideal para verificar funcionamiento de estrategias")
        else:
            print("   💼 Modo PRODUCCIÓN - Umbrales estrictos para operativa real") 
            print("   ✅ Filtros rigurosos para evitar falsas señales")
        print(f"   💡 Para cambiar perfil, edita 'active_profile' en config.ini")
        
        # Mostrar estrategias disponibles
        print(f"\n📊 ESTRATEGIAS DISPONIBLES:")
        print("- macdv: MACD con confirmación de volumen")
        print("- gap_go: Gap & Go para small caps intraday")
        print("- multi_strategy: Motor multi-estrategia")
        print(f"\n🚀 Estrategia seleccionada: {trading_config.strategy_name}")
        
        # Cargar parámetros de la estrategia desde config.ini
        strategy_params = get_strategy_parameters(config_parser, trading_config.strategy_name)
        if strategy_params:
            print(f"\n⚙️ PARÁMETROS DE {trading_config.strategy_name.upper()}:")
            for key, value in strategy_params.items():
                print(f"   {key}: {value}")
        else:
            print(f"\n⚠️ No se encontraron parámetros para {trading_config.strategy_name} en config.ini")
            print("   Se usarán valores por defecto.")
        
        # Importar y crear el sistema
        from main import TradingSystemManager
        system = TradingSystemManager(trading_config)
        
        # Menú de opciones
        print("\n📋 OPCIONES DE EJECUCIÓN:")
        print("1. Modo interactivo (recomendado para testing)")
        print("2. Modo automático con símbolos predefinidos")
        print("3. Modo manual - ingresar símbolos")
        
        choice = input("\nSeleccione una opción (1-3): ").strip()
        
        if choice == "1":
            # Modo interactivo
            logger.info("Iniciando en modo interactivo")
            await system.run_interactive()
            
        elif choice == "2":
            # Modo automático - DESHABILITADO para evitar símbolos inválidos
            print("❌ Modo automático con símbolos predeterminados DESHABILITADO")
            print("💡 Usa el modo manual (opción 3) para especificar símbolos válidos")
            print("🔍 Los símbolos deben tener datos históricos disponibles en IBKR")
            print()
            # Volver al menú principal
            pass
            
            # Mantener ejecutándose hasta Ctrl+C
            try:
                while not system.shutdown_requested:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Recibido Ctrl+C, deteniendo sistema...")
            
        elif choice == "3":
            # Modo manual
            print("⚠️  IMPORTANTE: Usa solo símbolos con datos históricos válidos en IBKR")
            print("💡 Ejemplo de símbolos típicamente válidos: AAPL, MSFT, GOOGL, TSLA, NVDA")
            if trading_config.strategy_name == 'gap_go':
                print("📊 Para Gap & Go: Verifica que los small caps tengan datos históricos")
            
            symbols_input = input("Ingrese símbolos separados por comas (ej: AAPL,MSFT): ").strip()
            if symbols_input:
                symbols = [s.strip().upper() for s in symbols_input.split(',')]
                logger.info(f"Iniciando con símbolos manuales: {symbols}")
                await system.start(symbols)
                
                # Mantener ejecutándose
                try:
                    while not system.shutdown_requested:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    logger.info("Recibido Ctrl+C, deteniendo sistema...")
            else:
                print("❌ No se ingresaron símbolos")
                return
        else:
            print("❌ Opción no válida")
            return
            
    except Exception as e:
        logger.error(f"Error en sistema principal: {e}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        return 1
    
    finally:
        if 'system' in locals():
            await system.stop()
        print("\n👋 Sistema detenido. ¡Hasta luego!")
    
    return 0


def check_dependencies():
    """Verificar que las dependencias estén instaladas"""
    required_packages = ['ib_insync', 'pandas', 'numpy']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Faltan dependencias: {', '.join(missing_packages)}")
        print("📦 Instala con: pip install " + ' '.join(missing_packages))
        return False
    
    return True


if __name__ == "__main__":
    # Verificar dependencias
    if not check_dependencies():
        sys.exit(1)
    
    # Verificar conexión a IBKR
    print("\n🔌 VERIFICACIÓN DE CONEXIÓN:")
    print("1. ¿Está TWS o IB Gateway ejecutándose?")
    print("2. ¿Está habilitada la API en TWS/Gateway?")
    print("3. ¿El puerto 7497 está disponible?")
    
    proceed = input("\n¿Continuar? (y/n): ").strip().lower()
    if proceed not in ['y', 'yes', 'sí', 's']:
        print("❌ Ejecución cancelada")
        sys.exit(0)
    
    # Verificar estrategia seleccionada
    print(f"\n🎯 Para usar Gap & Go, asegúrate de que en config.ini tengas:")
    print("   [TRADING]")
    print("   strategy = gap_go")
    print("\n   O para MACDV:")
    print("   strategy = macdv")
    
    # Ejecutar sistema
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n🛑 Detenido por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        sys.exit(1)