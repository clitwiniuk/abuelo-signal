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

# Auto-detect adapter based on active profile
print("🔍 Detectando perfil activo...")
try:
    config = configparser.ConfigParser()
    config.read('config.ini')
    active_profile = config.get('TRADING', 'active_profile')
    
    if active_profile == 'TESTING':
        # Modo simulación - usar MockIBKRAdapter
        from adapters.mock_ibkr_adapter import MockIBKRAdapter as IBKRAdapter
        from adapters.csv_data_provider import CSVDataProvider as DataProvider
        print("🎮 MODO SIMULACIÓN: Usando MockIBKRAdapter + CSVDataProvider")
        ADAPTER_MODE = "MOCK"
    else:  # PRODUCTION
        # Modo demo/real - usar IBKRAdapter real
        try:
            from adapters.ibkr_adapter import IBKRAdapter
            print("📈 MODO PRODUCTION: Usando IBKRAdapter real")
            ADAPTER_MODE = "REAL"
            DataProvider = IBKRAdapter  # En production, IBKR provee tanto broker como data
        except ImportError as e:
            print("❌ Error: ib_insync no instalado para modo PRODUCTION")
            print("💡 Solución: pip install ib_insync")
            print("🔄 FALLBACK: Cambiando automáticamente a modo TESTING")
            # Fallback automático a modo TESTING
            from adapters.mock_ibkr_adapter import MockIBKRAdapter as IBKRAdapter
            from adapters.csv_data_provider import CSVDataProvider as DataProvider
            print("🎮 FALLBACK ACTIVADO: Usando MockIBKRAdapter + CSVDataProvider")
            ADAPTER_MODE = "MOCK"
            
except Exception as e:
    print(f"❌ Error leyendo configuración: {e}")
    print("🔄 Usando modo TESTING por defecto")
    from adapters.mock_ibkr_adapter import MockIBKRAdapter as IBKRAdapter
    from adapters.csv_data_provider import CSVDataProvider as DataProvider
    ADAPTER_MODE = "MOCK"


class TradingSystemManager:
    """
    Main system manager that orchestrates all components.
    Compatible with both standalone and Streamlit execution.
    """

    def __init__(self, config: TradingConfig, in_streamlit: bool = False):
        self.config = config
        self.logger = logging.getLogger("TradingSystem")
        self.in_streamlit = in_streamlit

        self.event_bus = AsyncEventBus()
        self.data_provider: Optional[DataProvider] = None
        self.broker: Optional[IBKRAdapter] = None
        self.strategy: Optional[MACDVStrategy] = None
        self.risk_manager: Optional[RiskManager] = None
        self.trading_engine: Optional[TradingEngine] = None

        self.is_running = False
        self.shutdown_requested = False
        self.manual_tickers = []
        self.operation_mode = None
        
        # Enhanced cleanup system
        self.start_time = datetime.now()
        self.max_runtime_hours = 12  # Max 12 hours runtime
        self.cleanup_registered = False

        self._setup_logging()

        if not self.in_streamlit:
            self._setup_signal_handlers()
            self._setup_enhanced_cleanup()

    def _setup_logging(self):
        """Setup logging configuration (always write to file)."""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config.log_level))
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        log_path = Path(self.config.log_file).expanduser()
        if not log_path.parent.exists():
            log_path.parent.mkdir(parents=True, exist_ok=True)
        if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '') == str(log_path) for h in root_logger.handlers):
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        self.logger = logging.getLogger("TradingSystem")

        log_handler = LoggingEventHandler(logging.INFO)
        error_handler = ErrorEventHandler()
        self.event_bus.subscribe("*", log_handler)
        self.event_bus.subscribe("error_occurred", error_handler)

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown - ONLY for standalone mode"""
        try:
            def signal_handler(signum, frame):
                signal_name = "SIGINT" if signum == signal.SIGINT else f"Signal {signum}"
                
                if self.shutdown_requested:
                    self.logger.warning(f"⚠️ Segunda señal {signal_name} recibida. Forzando salida inmediata...")
                    sys.exit(1)
                
                self.logger.info(f"👋 Señal {signal_name} recibida (Ctrl+C). Iniciando cierre ordenado...")
                self.shutdown_requested = True
                self.is_running = False
                
                # Set shutdown flags immediately
                if hasattr(self, 'trading_engine') and self.trading_engine:
                    self.trading_engine.is_running = False
                    if hasattr(self.trading_engine, 'shutdown_requested'):
                        self.trading_engine.shutdown_requested = True
                
                # Try to signal the event loop
                try:
                    loop = asyncio.get_running_loop()
                    loop.call_soon_threadsafe(self._request_shutdown)
                    self.logger.info("🔄 Señal enviada al event loop")
                except RuntimeError:
                    self.logger.info("📴 No hay event loop activo, saliendo directamente...")
                    sys.exit(0)
            
            if platform.system() != 'Windows' and threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)
            elif platform.system() == 'Windows' and threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)
                
        except Exception as e:
            self.logger.warning(f"No se pudieron configurar signal handlers: {e}")

    def _request_shutdown(self):
        """Request system shutdown - IMMEDIATE FORCE"""
        self.logger.info("📴 IMMEDIATE FORCE SHUTDOWN - killing all operations")
        
        self.shutdown_requested = True
        self.is_running = False
        
        try:
            if self.trading_engine:
                self.trading_engine.is_running = False
                self.logger.info("📴 Trading engine stopped")
                
                if hasattr(self.trading_engine, 'monitored_symbols'):
                    self.trading_engine.monitored_symbols.clear()
                if hasattr(self.trading_engine, 'failed_symbols'):
                    self.trading_engine.failed_symbols.clear()
                    
                if hasattr(self.trading_engine, 'data_provider') and hasattr(self.trading_engine.data_provider, '_shutdown'):
                    self.trading_engine.data_provider._shutdown = True
                    self.logger.info("📴 IBKR adapter shutdown flag set")
                        
        except Exception as e:
            self.logger.warning(f"Error during force shutdown: {e}")
            
        self.logger.info("📴 IMMEDIATE FORCE SHUTDOWN completed")
        
        def force_exit():
            time.sleep(2)
            if self.is_running:
                self.logger.error("📴 SYSTEM STILL RUNNING AFTER 2s - FORCE EXIT")
                sys.exit(1)
                
        threading.Thread(target=force_exit, daemon=True).start()

    async def initialize(self):
        """Initialize all system components"""
        try:
            self.logger.info("Initializing trading system...")
            
            try:
                import streamlit
                self.in_streamlit = True
                self.logger.info("Ejecutando en entorno Streamlit")
            except ImportError:
                self.in_streamlit = False
                self.logger.info("Ejecutando en modo standalone")
            
            # Initialize adapters based on mode
            if ADAPTER_MODE == "MOCK":
                # Simulación: usar adaptadores separados
                # Check for synthetic data mode
                use_synthetic = getattr(self.config, 'use_synthetic_data', False)
                self.data_provider = DataProvider(use_synthetic_data=use_synthetic)  # CSVDataProvider
                self.broker = IBKRAdapter()  # MockIBKRAdapter
                
                if use_synthetic:
                    self.logger.info("🎯 Inicializado en modo SIMULACIÓN con DATOS SINTÉTICOS")
                else:
                    self.logger.info("🎮 Inicializado en modo SIMULACIÓN")
            else:
                # Production: usar IBKRAdapter real (mismo para data y broker)
                self.data_provider = IBKRAdapter(
                    host=self.config.broker_host,
                    port=self.config.broker_port,
                    client_id=self.config.broker_client_id,
                    config=self.config
                )
                self.broker = self.data_provider
                self.logger.info("📈 Inicializado en modo PRODUCTION")
            
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
            
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize system: {e}")
            raise
    
    async def start(self, symbols: List[str] = None):
        """Start the trading system"""
        if self.is_running:
            self.logger.warning("System is already running")
            return
        
        try:
            # Initialize if not already done
            if not self.trading_engine:
                await self.initialize()
            
            self.is_running = True
            self.logger.info(f"Starting trading system with symbols: {symbols}")
            
            # Start the trading engine
            await self.trading_engine.start(symbols)
            
        except Exception as e:
            self.logger.error(f"Error starting trading system: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """Stop the trading system gracefully"""
        if not self.is_running:
            self.logger.info("🔄 Sistema ya detenido")
            return
        
        self.logger.info("🛑 Deteniendo sistema de trading...")
        self.is_running = False
        self.shutdown_requested = True
        
        try:
            # Stop trading engine first
            if self.trading_engine:
                self.logger.info("📉 Deteniendo motor de trading...")
                await asyncio.wait_for(self.trading_engine.stop(), timeout=5.0)
                self.logger.info("✅ Motor de trading detenido")
            
            # Disconnect adapters
            if ADAPTER_MODE == "MOCK":
                if self.data_provider:
                    self.logger.info("📊 Desconectando data provider...")
                    try:
                        await asyncio.wait_for(self.data_provider.disconnect(), timeout=2.0)
                    except:
                        pass
                        
                if self.broker:
                    self.logger.info("💼 Desconectando broker...")
                    try:
                        await asyncio.wait_for(self.broker.disconnect(), timeout=2.0)
                    except:
                        pass
            else:
                # For real IBKR, disconnect once since it's the same instance
                if self.data_provider:
                    self.logger.info("📊 Desconectando IBKR...")
                    try:
                        await asyncio.wait_for(self.data_provider.disconnect(), timeout=3.0)
                    except:
                        pass
            
            self.logger.info("✅ Sistema detenido correctamente")
            
        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout deteniendo componentes, forzando cierre...")
        except Exception as e:
            self.logger.error(f"❌ Error deteniendo sistema: {e}")
        finally:
            self.is_running = False
            self.shutdown_requested = True
    
    async def add_symbol(self, symbol: str, skip_validation: bool = False):
        """Add a symbol to monitor"""
        if self.trading_engine and self.is_running:
            result = await self.trading_engine.add_symbol(symbol, skip_validation)
            return result
        else:
            self.logger.debug(f"Cannot add symbol {symbol}: system not running")
            return False
    
    async def remove_symbol(self, symbol: str):
        """Remove a symbol from monitoring"""
        if self.trading_engine and self.is_running:
            await self.trading_engine.remove_symbol(symbol)
        else:
            self.logger.debug(f"Cannot remove symbol {symbol}: system not running")
    
    def get_status(self) -> dict:
        """Get system status"""
        status = {
            'is_running': self.is_running,
            'start_time': None,
            'positions': {},
            'active_orders': {},
            'monitored_symbols': set(),
            'daily_stats': {},
            'risk_metrics': {}
        }
        
        if self.trading_engine:
            # Get current positions
            positions = self.trading_engine.get_positions()
            status.update({
                'positions': positions,
                'active_orders': self.trading_engine.get_active_orders(),
                'monitored_symbols': self.trading_engine.get_monitored_symbols(),
                'daily_stats': self.trading_engine.get_daily_stats()
            })
            
            # CRITICAL: Update risk manager with current positions for max_positions validation
            if self.risk_manager and positions:
                self.risk_manager.update_broker_positions(positions)
        
        if self.risk_manager:
            status['risk_metrics'] = self.risk_manager.get_risk_metrics()
        
        return status
    
    def _load_strategy_parameters(self, strategy_name: str) -> dict:
        """Load strategy parameters from config based on strategy name"""
        # Common parameters for all strategies (from RISK section)
        common_params = {
            'max_position_value': getattr(self.config, 'max_position_value', 100.0),
            'max_portfolio_exposure': getattr(self.config, 'max_portfolio_exposure', 100.0)
        }
        
        # Strategy-specific parameters
        if strategy_name.lower() == 'macdv':
            return {
                **common_params,
                'macd_fast': getattr(self.config, 'macd_fast', 12),
                'macd_slow': getattr(self.config, 'macd_slow', 26),
                'macd_signal': getattr(self.config, 'macd_signal', 9),
                'volume_threshold': getattr(self.config, 'volume_threshold', 1.5),
                'stop_loss_pct': getattr(self.config, 'stop_loss_pct', 0.03),
                'take_profit_pct': getattr(self.config, 'take_profit_pct', 0.06),
            }
        elif strategy_name.lower() == 'volume_breakout':
            return {
                **common_params,
                'volume_threshold': getattr(self.config, 'volume_threshold', 2.0),
                'breakout_periods': getattr(self.config, 'breakout_periods', 20),
                'stop_loss_pct': getattr(self.config, 'stop_loss_pct', 0.03),
                'take_profit_pct': getattr(self.config, 'take_profit_pct', 0.06),
                'trailing_stop_activation_pct': getattr(self.config, 'trailing_stop_activation_pct', 0.02),
                'trailing_stop_distance_pct': getattr(self.config, 'trailing_stop_distance_pct', 0.01),
            }
        elif strategy_name.lower() == 'gap_go':
            return {
                **common_params,
                'min_gap_percent': getattr(self.config, 'min_gap_percent', 5.0),
                'max_gap_percent': getattr(self.config, 'max_gap_percent', 20.0),
                'volume_multiplier': getattr(self.config, 'volume_multiplier', 2.5),
                'stop_loss_pct': getattr(self.config, 'stop_loss_pct', 0.07),
                'profit_target': getattr(self.config, 'profit_target', 0.25),
                'trailing_stop_activation': getattr(self.config, 'trailing_stop_activation', 0.1),
                'trailing_stop_distance': getattr(self.config, 'trailing_stop_distance', 0.05),
            }
        elif strategy_name.lower() == 'multi_strategy':
            # Load parameters for all strategies used by MultiStrategyEngine
            from configparser import ConfigParser
            import os
            
            config_file = os.path.join(os.path.dirname(__file__), 'config.ini')
            config_parser = ConfigParser()
            if os.path.exists(config_file):
                config_parser.read(config_file)
            
            # Load individual strategy parameters
            multi_params = {
                **common_params,
                'enabled_strategies': ['macdv_smallcaps', 'gap_go', 'orb', 'volume_breakout', 'pmh_breakout'],
                'max_daily_trades': getattr(self.config, 'max_daily_trades', 20),
                'max_concurrent_positions': getattr(self.config, 'max_concurrent_positions', 5),
                'risk_per_trade': getattr(self.config, 'risk_per_trade', 0.015),
            }
            
            # Load MACDV parameters
            if config_parser.has_section('MACDV_STRATEGY'):
                multi_params['macdv'] = {k: self._convert_config_value(v) for k, v in config_parser.items('MACDV_STRATEGY')}
            
            # Load Gap Go parameters  
            if config_parser.has_section('GAP_GO_STRATEGY'):
                multi_params['gap_go'] = {k: self._convert_config_value(v) for k, v in config_parser.items('GAP_GO_STRATEGY')}
            
            # Load ORB parameters
            if config_parser.has_section('ORB_STRATEGY'):
                multi_params['orb'] = {k: self._convert_config_value(v) for k, v in config_parser.items('ORB_STRATEGY')}
            
            # Load Volume Breakout parameters
            if config_parser.has_section('VOLUME_BREAKOUT_STRATEGY'):
                multi_params['volume_breakout'] = {k: self._convert_config_value(v) for k, v in config_parser.items('VOLUME_BREAKOUT_STRATEGY')}
            
            # Load PMH Breakout parameters
            if config_parser.has_section('PMH_BREAKOUT_STRATEGY'):
                multi_params['pmh_breakout'] = {k: self._convert_config_value(v) for k, v in config_parser.items('PMH_BREAKOUT_STRATEGY')}
            
            return multi_params
        elif strategy_name.lower() == 'ml_multi_strategy':
            # Load parameters for ML Multi-Strategy Engine
            from configparser import ConfigParser
            import os
            
            config_file = os.path.join(os.path.dirname(__file__), 'config.ini')
            config_parser = ConfigParser()
            if os.path.exists(config_file):
                config_parser.read(config_file)
            
            # ML-specific parameters
            ml_params = {
                **common_params,
                'max_strategies_per_ticker': 2,
                'min_bars_required': 20,
                'model_save_frequency': 50,
                'exploration_rate': 0.1,
                'strategy_timeout': 1.0
            }
            
            # Load ML section if exists
            if config_parser.has_section('ML_MULTI_STRATEGY'):
                for key, value in config_parser['ML_MULTI_STRATEGY'].items():
                    ml_params[key] = self._convert_config_value(value)
            
            return ml_params
        else:
            self.logger.info(f"Using default parameters for strategy: {strategy_name}")
            return common_params
    
    def _convert_config_value(self, value):
        """Convert config string values to appropriate types"""
        if isinstance(value, str):
            # Boolean values
            if value.lower() in ('true', 'false'):
                return value.lower() == 'true'
            # Try to convert to float/int
            try:
                if '.' in value:
                    return float(value)
                else:
                    return int(value)
            except ValueError:
                return value  # Keep as string
        return value
    
    async def run_interactive(self):
        """Run system in interactive mode - ONLY for standalone execution"""
        if self.in_streamlit:
            self.logger.error("Interactive mode not available in Streamlit")
            return
            
        print("\n" + "="*60)
        print("🤖 IMPROVED TRADING SYSTEM")
        print("="*60)
        print("Commands:")
        print("  add <SYMBOL>     - Add symbol to monitor")
        print("  remove <SYMBOL>  - Remove symbol from monitoring")
        print("  status           - Show system status")
        print("  positions        - Show current positions")
        print("  stop/quit/exit   - Stop the system")
        print("  Ctrl+C           - Quick exit (press twice for force)")
        
        # Show available symbols in TESTING mode
        if ADAPTER_MODE == "MOCK":
            try:
                from adapters.csv_data_provider import CSVDataProvider
                temp_provider = CSVDataProvider()
                available_symbols = temp_provider.get_available_symbols()
                print(f"📊 Símbolos disponibles en CSV: {', '.join(available_symbols[:10])}{'...' if len(available_symbols) > 10 else ''}")
            except:
                pass
        print("="*60)
        
        # Load default symbols from config.ini
        try:
            config = configparser.ConfigParser()
            config.read('config.ini')
            symbols_str = config.get('TRADING', 'default_symbols', fallback='XXII,SOFI,SNDL')
            default_symbols = [s.strip() for s in symbols_str.split(',')]
            
            print(f"📈 Símbolos configurados: {', '.join(default_symbols)}")
            print(f"💡 Puedes agregar más con: add <SYMBOL>")
        except Exception as e:
            self.logger.warning(f"Error leyendo símbolos del config: {e}")
            default_symbols = ['XXII', 'SOFI', 'SNDL']  # Fallback con símbolos que tenemos datos
            
        await self.start(default_symbols)
        
        try:
            while self.is_running and not self.shutdown_requested:
                try:
                    # Check for user input (non-blocking with shorter timeout)
                    cmd = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, input, "\n> "),
                        timeout=0.5  # Shorter timeout for more responsive Ctrl+C
                    )
                    
                    if cmd.strip().lower() in ['quit', 'exit', 'stop']:
                        self.logger.info("👋 Comando de salida recibido")
                        break
                        
                    await self._process_command(cmd.strip())
                    
                except asyncio.TimeoutError:
                    # No input, continue monitoring
                    # Check shutdown flag more frequently
                    if self.shutdown_requested:
                        break
                    continue
                except EOFError:
                    # User pressed Ctrl+D
                    self.logger.info("👋 EOF detectado (Ctrl+D)")
                    break
                except KeyboardInterrupt:
                    # Handle Ctrl+C in the inner loop too
                    self.logger.info("👋 Interrupción de teclado detectada (Ctrl+C)")
                    break
                    
        except KeyboardInterrupt:
            self.logger.info("👋 Salida por interrupción de teclado (Ctrl+C)")
        except Exception as e:
            self.logger.error(f"❌ Error inesperado en el bucle principal: {e}")
        finally:
            self.logger.info("🛑 Iniciando proceso de cierre...")
            await self.stop()
    
    async def update_config(self, new_config: TradingConfig):
        """
        Actualiza la configuración en tiempo real.
        Esto actualiza tanto el motor de trading como el gestor de riesgo.
        """
        try:
            # Actualizar la configuración local
            self.config = new_config
            
            # Actualizar el motor de trading si existe
            if self.trading_engine:
                self.trading_engine.config = new_config
                self.logger.info("Configuración actualizada en el motor de trading")
            
            # Actualizar el gestor de riesgo si existe
            if self.risk_manager:
                self.risk_manager.config = new_config
                self.logger.info("Configuración actualizada en el gestor de riesgo")
                
            return True
        except Exception as e:
            self.logger.error(f"Error actualizando configuración: {e}")
            return False
            
    async def _process_command(self, command: str):
        """Process interactive commands"""
        if not command:
            return
        
        parts = command.lower().split()
        cmd = parts[0]
        
        if cmd == 'add' and len(parts) > 1:
            symbol = parts[1].upper()
            await self.add_symbol(symbol)
            print(f"✅ Added {symbol} to monitoring")
            
        elif cmd == 'remove' and len(parts) > 1:
            symbol = parts[1].upper()
            await self.remove_symbol(symbol)
            print(f"❌ Removed {symbol} from monitoring")
            
        elif cmd == 'status':
            status = self.get_status()
            print(f"\n📊 System Status:")
            print(f"   Running: {status['is_running']}")
            print(f"   Monitored Symbols: {len(status['monitored_symbols'])}")
            print(f"   Active Positions: {len(status['positions'])}")
            print(f"   Pending Orders: {len(status['active_orders'])}")
            
        elif cmd == 'positions':
            positions = self.get_status()['positions']
            if positions:
                print(f"\n💼 Current Positions:")
                for symbol, pos in positions.items():
                    pnl_color = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
                    print(f"   {symbol}: {pos.quantity} @ ${pos.avg_price:.2f} "
                          f"(Current: ${pos.market_price:.2f}) "
                          f"{pnl_color} ${pos.unrealized_pnl:.2f}")
            else:
                print("\n💼 No open positions")
                
        elif cmd == 'stop':
            print("🛑 Stopping system...")
            self.shutdown_requested = True
            
        else:
            print("❓ Unknown command. Type 'stop' to exit.")

    def _setup_enhanced_cleanup(self):
        """Setup enhanced cleanup system with timeout and better signal handling"""
        if self.cleanup_registered:
            return
            
        self.cleanup_registered = True
        self.logger.info("🛡️ Setting up enhanced cleanup system...")
        
        # 1. Register atexit handler
        atexit.register(self._emergency_cleanup)
        
        # 2. Start timeout watchdog thread
        timeout_thread = threading.Thread(target=self._timeout_watchdog, daemon=True)
        timeout_thread.start()
        
        # 3. Start market hours monitor
        hours_thread = threading.Thread(target=self._market_hours_monitor, daemon=True)  
        hours_thread.start()
        
        self.logger.info(f"✅ Enhanced cleanup active (max runtime: {self.max_runtime_hours}h)")
    
    def _timeout_watchdog(self):
        """Auto-shutdown after maximum runtime"""
        while not self.shutdown_requested:
            time.sleep(300)  # Check every 5 minutes
            
            runtime = datetime.now() - self.start_time
            if runtime > timedelta(hours=self.max_runtime_hours):
                self.logger.warning(f"⏰ TIMEOUT: Process running for {runtime}")
                self.logger.warning(f"   Auto-shutdown after {self.max_runtime_hours} hours")
                self._emergency_cleanup()
                os._exit(1)  # Force exit
    
    def _market_hours_monitor(self):
        """Monitor market hours and warn if running outside trading hours"""
        while not self.shutdown_requested:
            time.sleep(1800)  # Check every 30 minutes
            
            now = datetime.now()
            # Simple check: warn if running outside 6 AM - 8 PM
            if now.hour < 6 or now.hour > 20:
                self.logger.warning(f"🕐 Running outside typical market hours ({now.hour}:00)")
                self.logger.warning("   Consider stopping the system to save resources")
    
    def _emergency_cleanup(self):
        """Emergency cleanup - called by atexit or timeout"""
        if self.shutdown_requested:
            return
            
        self.logger.info("🚨 EMERGENCY CLEANUP ACTIVATED")
        self.shutdown_requested = True
        self.is_running = False
        
        try:
            if hasattr(self, 'trading_engine') and self.trading_engine:
                self.logger.info("🛑 Emergency stop of trading engine...")
                # Try async stop in sync context
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.trading_engine.stop())
                    loop.close()
                except Exception as e:
                    self.logger.error(f"Failed to stop trading engine cleanly: {e}")
                    
            self.logger.info("✅ Emergency cleanup completed")
        except Exception as e:
            self.logger.error(f"❌ Emergency cleanup failed: {e}")


class VolumeFilter:
    """Simple volume filter implementation - Placeholder"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger("VolumeFilter")
    
    async def should_trade(self, symbol: str, bars: List) -> tuple[bool, str]:
        """Check if symbol should be traded based on volume"""
        if not bars or len(bars) < 20:
            return False, "Insufficient data"
        
        current_volume = bars[-1].volume
        avg_volume = sum(bar.volume for bar in bars[-20:-1]) / 19
        
        if current_volume < avg_volume * 1.5:
            return False, f"Low volume: {current_volume} vs avg {avg_volume:.0f}"
        
        return True, f"Volume OK: {current_volume} ({current_volume/avg_volume:.1f}x avg)"


async def main():
    """Main entry point - ONLY for standalone execution"""
    # Load configuration from config.ini
    import configparser
    config_parser = configparser.ConfigParser()
    config_parser.read('config.ini')
    
    # Get strategy name from config
    strategy_name = config_parser.get('TRADING', 'strategy', fallback='macdv')
    print(f"🎯 Loading strategy from config: {strategy_name}")
    
    # Create configuration
    config = TradingConfig(
        max_positions=5,
        max_risk_per_trade=0.02,
        max_daily_loss=-500.0,
        max_daily_trades=20,
        broker_host="127.0.0.1",
        broker_port=7497,
        broker_client_id=1,
        strategy_name=strategy_name,  # Use strategy from config.ini
        timeframe="1 min",
        log_level="INFO",
        log_file="trading_system.log",
        use_synthetic_data=True  # Enable synthetic data mode
    )
    
    # Create and run system
    system = TradingSystemManager(config, in_streamlit=False)
    
    try:
        await system.run_interactive()
    except Exception as e:
        logging.error(f"System error: {e}")
    finally:
        await system.stop()


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())