#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test de backtest para la estrategia Volume Momentum.
Este script ejecuta un backtest simple para verificar que la estrategia
Volume Momentum está correctamente integrada en el sistema.
"""

import os
import sys
import pandas as pd
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("VolumeMomentumTest")

# Añadir el directorio actual al path para poder importar módulos
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Importar componentes del sistema
from core.interfaces import TradingConfig
from backtesting.backtest_engine import BacktestEngine
from strategies import get_strategy_class
from backtesting.data_loader import BacktestDataLoader

def run_volume_momentum_backtest():
    """
    Ejecuta un backtest simple para la estrategia Volume Momentum
    """
    logger.info("Iniciando backtest de Volume Momentum Strategy")
    
    # Configurar el backtest
    config = TradingConfig(
        strategy_name="volume_momentum",  # Usar la estrategia Volume Momentum
        timeframe="5 min",
        max_positions=3,
        max_risk_per_trade=0.02,
        enable_filters=True
    )
    
    # Establecer atributos adicionales necesarios para el backtest
    config.simulation_mode = True  # Importante para ignorar restricciones de horario
    config.initial_capital = 10000.0  # Capital inicial para el backtest
    
    # Añadir atributos adicionales para la estrategia Volume Momentum
    # Estos valores vienen de la sección [VOLUME_MOMENTUM_STRATEGY] en config.ini
    config.volume_surge_multiplier = 2.0
    config.volume_lookback_hours = 10
    config.volume_timeframe_minutes = 60
    config.min_absolute_volume = 500000
    config.float_rotation_threshold = 0.1
    config.min_price = 2.0
    config.max_price = 30.0
    config.vwap_period = 20
    config.vwap_deviation_threshold = 0.005
    config.require_vwap_direction = True
    config.use_macd_confirmation = True
    config.use_adx_filter = True
    config.adx_threshold = 25
    config.atr_period = 14
    config.stop_loss_atr_mult = 1.5
    config.profit_target_1_atr = 2.0
    config.profit_target_2_atr = 3.5
    
    # Crear el motor de backtest
    engine = BacktestEngine(config)
    
    # Definir fechas para el backtest (usar datos recientes)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)  # 5 días de backtest
    
    # Símbolos para el backtest
    symbols = ["AAPL", "MSFT", "TSLA", "NVDA", "AMD"]
    
    # Cargar datos para cada símbolo
    data_path = os.path.join(current_dir, "data")
    data_loader = BacktestDataLoader(primary_timeframe=config.timeframe, debug=True)
    
    for symbol in symbols:
        try:
            # Buscar archivos CSV para el símbolo
            file_patterns = [f"{symbol}_5m.csv", f"{symbol}.csv", f"{symbol}_1m.csv"]
            found_file = None
            
            for pattern in file_patterns:
                file_path = os.path.join(data_path, pattern)
                if os.path.exists(file_path):
                    found_file = file_path
                    break
            
            if found_file:
                # Cargar los datos con el BacktestDataLoader
                df = data_loader.load_csv_data(symbol, found_file, start_date, end_date)
                
                if not df.empty:
                    # Asegurar que tenemos las columnas necesarias
                    required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    if all(col in df.columns for col in required_cols):
                        # Convertir al timeframe correcto si es necesario
                        if config.timeframe != "1min" and config.timeframe in data_loader.supported_conversions.get("1min", []):
                            df = data_loader.resample_timeframe(df, config.timeframe)
                        
                        engine.add_data(symbol, df)
                        logger.info(f"Datos cargados para {symbol}: {len(df)} barras")
                    else:
                        logger.warning(f"Faltan columnas requeridas en los datos de {symbol}")
                else:
                    logger.warning(f"No se encontraron datos para {symbol} en el rango de fechas especificado")
            else:
                logger.warning(f"No se encontró archivo de datos para {symbol} en {data_path}")
        except Exception as e:
            logger.error(f"Error cargando datos para {symbol}: {e}")
    
    # Ejecutar el backtest
    try:
        logger.info("Ejecutando backtest...")
        results = engine.run()
        
        # Mostrar resultados
        logger.info("Resultados del backtest:")
        logger.info(f"Total de operaciones: {results.get('total_trades', 0)}")
        logger.info(f"Operaciones ganadoras: {results.get('winning_trades', 0)}")
        logger.info(f"Operaciones perdedoras: {results.get('losing_trades', 0)}")
        logger.info(f"Porcentaje de acierto: {results.get('win_rate', 0):.2f}%")
        logger.info(f"Profit factor: {results.get('profit_factor', 0):.2f}")
        logger.info(f"Retorno total: {results.get('total_return', 0):.2f}%")
        logger.info(f"Drawdown máximo: {results.get('max_drawdown', 0):.2f}%")
        
        # Mostrar operaciones
        trades = results.get('trades', [])
        if trades:
            logger.info("\nDetalle de operaciones:")
            for i, trade in enumerate(trades):
                logger.info(f"Operación {i+1}: {trade['symbol']} - {trade['side']} - "
                           f"Entrada: {trade['entry_price']:.2f} - Salida: {trade['exit_price']:.2f} - "
                           f"P&L: {trade['pnl']:.2f}$ ({trade['pnl_pct']:.2f}%)")
        
        return results
    except Exception as e:
        logger.error(f"Error en el backtest: {e}")
        return None

if __name__ == "__main__":
    run_volume_momentum_backtest()
