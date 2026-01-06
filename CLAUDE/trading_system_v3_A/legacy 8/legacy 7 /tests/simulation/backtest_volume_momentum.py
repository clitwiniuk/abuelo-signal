#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de backtest para la estrategia Volume Momentum optimizada para cuentas pequeñas
"""

import os
import sys
import pandas as pd
import logging
from datetime import datetime, timedelta

# Añadir directorio raíz al path para importaciones
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies import VolumeMomentumStrategy
from engine.backtest_engine import BacktestEngine
from utils.config_manager import ConfigManager
from utils.data_loader import DataLoader
from utils.logger_config import setup_logger

# Configurar logger
setup_logger()
logger = logging.getLogger("backtest_volume_momentum")

def run_backtest():
    """Ejecutar backtest para la estrategia Volume Momentum"""
    
    # Cargar configuración
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    # Configurar parámetros de backtest
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()
    symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]  # Símbolos para backtest
    
    # Crear instancia de la estrategia con parámetros optimizados
    strategy_params = {
        # Volume analysis - Más estrictos para cuentas pequeñas
        'volume_surge_multiplier': 2.5,      # Aumentado de 2.0 a 2.5x para mayor confirmación
        'volume_lookback_hours': 8,          # Reducido de 10 a 8 para mayor relevancia reciente
        'volume_timeframe_minutes': 30,      # Reducido de 60 a 30 min para mayor precisión
        'min_absolute_volume': 750000,       # Aumentado de 500k a 750k para mejor liquidez
        'float_rotation_threshold': 0.15,    # Aumentado de 10% a 15% para mayor confirmación
        
        # Price and market cap filters - Optimizados
        'min_price': 1.5,                    # Reducido de $2 a $1.5 para incluir más oportunidades
        'max_price': 20.0,                   # Reducido de $30 a $20 para enfocarse en small caps
        'max_market_cap': 750000000,         # Reducido de $1B a $750M para enfocarse en small caps
        'max_spread_pct': 0.4,               # Reducido de 0.5% a 0.4% para mejor ejecución
        'min_daily_volume': 1500000,         # Aumentado de 1M a 1.5M para mejor liquidez
        
        # Risk management - Optimizado para cuentas pequeñas
        'atr_period': 14,                    # Mantenido igual
        'stop_loss_atr_mult': 1.7,           # Aumentado de 1.5x a 1.7x para dar más espacio
        'profit_target': 0.20,               # Objetivo único de 20% (reemplaza targets múltiples)
        'min_risk_reward': 2.5,              # Aumentado de 2.0 a 2.5 para mejor calidad de trades
        
        # Trailing stop - Optimizado
        'use_trailing_stop': True,           # Usar trailing stop dinámico
        'trailing_activation_pct': 0.10,     # Activar trailing stop al 10% de beneficio
        'trailing_stop_distance': 0.05,      # 5% de distancia para el trailing stop
        
        # Position sizing - Optimizado para cuentas pequeñas
        'max_position_value': 2000.0,        # Valor máximo de posición
        'min_position_value': 500.0,         # Valor mínimo para evitar operaciones demasiado pequeñas
        'risk_per_trade': 0.01,              # 1% de riesgo por operación
        'min_quantity': 100,                 # Cantidad mínima para evitar odd lots
        'commission_per_share': 0.01,        # Comisión por acción
        'min_commission': 1.0,               # Comisión mínima por operación
    }
    
    strategy = VolumeMomentumStrategy(strategy_params)
    
    # Configurar data loader
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    data_loader = DataLoader(data_path)
    
    # Configurar motor de backtest
    initial_capital = 10000.0  # $10,000 para cuenta pequeña
    backtest_config = {
        "initial_capital": initial_capital,
        "risk_per_trade": 0.01,  # 1% de riesgo por operación
        "commission_per_share": 0.01,  # $0.01 por acción
        "min_commission": 1.0,  # $1.00 mínimo por operación
        "slippage_pct": 0.001,  # 0.1% de slippage
        "simulation_mode": True,  # Modo simulación para ignorar restricciones de horario
        "log_level": "INFO"
    }
    
    engine = BacktestEngine(
        strategy=strategy,
        data_loader=data_loader,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        config=backtest_config
    )
    
    # Ejecutar backtest
    logger.info(f"Iniciando backtest de Volume Momentum con {len(symbols)} símbolos desde {start_date.date()} hasta {end_date.date()}")
    results = engine.run()
    
    # Mostrar resultados
    logger.info("=== RESULTADOS DEL BACKTEST ===")
    logger.info(f"Capital inicial: ${initial_capital:.2f}")
    logger.info(f"Capital final: ${results['final_capital']:.2f}")
    logger.info(f"Retorno total: {results['total_return']:.2f}%")
    logger.info(f"Número de operaciones: {results['total_trades']}")
    logger.info(f"Operaciones ganadoras: {results['winning_trades']} ({results['win_rate']:.2f}%)")
    logger.info(f"Operaciones perdedoras: {results['losing_trades']}")
    logger.info(f"Profit factor: {results['profit_factor']:.2f}")
    logger.info(f"Máximo drawdown: {results['max_drawdown']:.2f}%")
    
    # Guardar resultados detallados en CSV
    trades_df = pd.DataFrame(results['trades'])
    if not trades_df.empty:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"volume_momentum_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        trades_df.to_csv(output_file, index=False)
        logger.info(f"Resultados detallados guardados en: {output_file}")
    else:
        logger.warning("No se ejecutaron operaciones durante el backtest")
    
    return results

if __name__ == "__main__":
    run_backtest()
