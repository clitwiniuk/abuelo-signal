#!/usr/bin/env python3
"""
Main Synthetic Data Trading System

Sistema de trading principal configurado para usar datos sintéticos.
Versión especializada que fuerza el uso de datos sintéticos independientemente
de la configuración en config.ini.
"""

import asyncio
import logging
import signal
import sys
from typing import List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import threading
import platform
import configparser
import atexit
import os
import time

from core.interfaces import TradingConfig
from core.events import AsyncEventBus, LoggingEventHandler, ErrorEventHandler
from engine.trading_engine import TradingEngine
from strategies import get_strategy_class, MACDVStrategy
from core.risk_manager import RiskManager
from filters.volume_filter import VolumeFilter

# Force TESTING mode for synthetic data
from adapters.mock_ibkr_adapter import MockIBKRAdapter as IBKRAdapter
from adapters.csv_data_provider import CSVDataProvider as DataProvider

print("🎯 MODO SINTÉTICO: Usando MockIBKRAdapter + CSVDataProvider con datos sintéticos")
ADAPTER_MODE = "SYNTHETIC"

# Import main system manager from main.py
from main import TradingSystemManager

class SyntheticTradingSystemManager(TradingSystemManager):
    """
    Trading system manager specialized for synthetic data.
    Forces synthetic data mode regardless of configuration.
    """
    
    async def initialize(self):
        """Initialize all system components with synthetic data forced"""
        try:
            self.logger.info("🎯 Initializing synthetic data trading system...")
            
            try:
                import streamlit
                self.in_streamlit = True
                self.logger.info("Ejecutando en entorno Streamlit")
            except ImportError:
                self.in_streamlit = False
                self.logger.info("Ejecutando en modo standalone")
            
            # Force synthetic data mode
            self.data_provider = DataProvider(use_synthetic_data=True)  # Force synthetic
            self.broker = IBKRAdapter()  # MockIBKRAdapter
            self.logger.info("🎯 INICIALIZADO EN MODO DATOS SINTÉTICOS")
            
            strategy_name = self.config.strategy_name
            strategy_params = self._load_strategy_parameters(strategy_name)
            strategy_class = get_strategy_class(strategy_name)
            if not strategy_class:
                self.logger.error(f"Strategy '{strategy_name}' not found. Defaulting to MACDV.")
                strategy_class = MACDVStrategy
                strategy_name = 'macdv'
            
            self.logger.info(f"Initializing strategy: {strategy_name}")
            self.strategy = strategy_class(strategy_params)
            
            # Initialize risk manager
            self.risk_manager = RiskManager(self.config)
            
            # Initialize filters
            filters = []
            if self.config.enable_filters:
                filters.append(VolumeFilter(self.config))
            
            # Initialize trading engine
            self.trading_engine = TradingEngine(
                config=self.config,
                data_provider=self.data_provider,
                broker=self.broker,
                strategy=self.strategy,
                risk_manager=self.risk_manager,
                filters=filters
            )
            
            # Show synthetic data info
            if hasattr(self.data_provider, 'get_stats'):
                stats = self.data_provider.get_stats()
                self.logger.info(f"📊 Synthetic Data Stats:")
                self.logger.info(f"   Total symbols: {stats.get('total_symbols', 0)}")
                self.logger.info(f"   Total events: {stats.get('total_events', 0)}")
                self.logger.info(f"   Events loaded: {stats.get('events_metadata_loaded', False)}")
            
            self.logger.info("🎯 All components initialized for synthetic data trading")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize synthetic trading system: {e}")
            raise

async def main():
    """Main entry point for synthetic data trading"""
    
    # Check for synthetic data
    if not Path("synthetic_data").exists():
        print("❌ Datos sintéticos no encontrados")
        print("💡 Ejecuta 'python start.py' y selecciona la opción 12 para generar los datos")
        return
    
    if not Path("synthetic_data/events_metadata.csv").exists():
        print("❌ Archivo de metadatos no encontrado")
        print("💡 Ejecuta 'python start.py' y selecciona la opción 12 para generar los datos")
        return
    
    # Show synthetic data summary
    try:
        import pandas as pd
        metadata = pd.read_csv("synthetic_data/events_metadata.csv")
        csv_files = [f for f in os.listdir("synthetic_data") if f.endswith('.csv') and f != 'events_metadata.csv']
        
        print("🎯 SISTEMA DE TRADING CON DATOS SINTÉTICOS")
        print("=" * 60)
        print(f"📊 Eventos disponibles: {len(metadata)}")
        print(f"📁 Símbolos sintéticos: {len(csv_files)}")
        print(f"📈 Ratio volumen promedio: {metadata['ratio_vol'].mean():.1f}x")
        print(f"📅 Período: {metadata['event_timestamp'].min()} a {metadata['event_timestamp'].max()}")
        print("=" * 60)
        
    except Exception as e:
        print(f"⚠️ Error leyendo metadatos: {e}")
    
    # Create configuration with synthetic data forced
    config = TradingConfig(
        max_positions=5,
        max_risk_per_trade=0.02,
        max_daily_loss=-500.0,
        max_daily_trades=20,
        broker_host="127.0.0.1",
        broker_port=7497,
        broker_client_id=1,
        strategy_name="macdv",
        timeframe="1 min",
        log_level="INFO",
        log_file="synthetic_trading_system.log",
        use_synthetic_data=True  # Force synthetic data mode
    )
    
    # Create and run synthetic trading system
    system = SyntheticTradingSystemManager(config, in_streamlit=False)
    
    try:
        await system.run_interactive()
    except Exception as e:
        logging.error(f"Synthetic trading system error: {e}")
    finally:
        await system.stop()

if __name__ == "__main__":
    # Run the synthetic trading system
    asyncio.run(main())