#!/usr/bin/env python3
"""
Service Locator Pattern - UNIFIED TRADING SYSTEM
Soluciona el problema de múltiples instancias duplicadas usando Singleton + Dependency Injection
"""

import logging
import threading
import asyncio
import configparser
import os
from typing import Dict, Any, Optional, TypeVar, Type, Union
from dataclasses import dataclass
from datetime import datetime

T = TypeVar('T')

@dataclass
class UnifiedConfig:
    """Configuración unificada para todo el sistema"""
    # IBKR Configuration
    client_id: int = 1
    host: str = "127.0.0.1"
    port: int = 7497

    # Risk Management
    max_positions: int = 15
    max_positions_per_symbol: int = 1
    max_daily_loss: float = -500.0
    max_daily_trades: int = 20
    max_position_value: float = 200.0

    # Trading Strategy - ZERO ML DEPENDENCIES
    strategy_name: str = "realistic_strategy_engine"
    long_only: bool = True

    # Scanning
    enable_scanner: bool = True
    scan_interval: int = 30

    # System Mode
    production_mode: bool = True
    enable_smallcap_mode: bool = True

    # DISABLED - Hybrid Learning System (ML removed)
    enable_hybrid_learning: bool = False
    hybrid_max_strategies: int = 3  # Legacy - not used
    hybrid_learning_rate: float = 0.1  # Legacy - not used

    # TradeTally Integration
    enable_tradetally_sync: bool = True
    tradetally_sync_time: str = "16:30"  # After market close EST
    tradetally_api_key: str = ""
    tradetally_base_url: str = "https://app.tradetally.com"

    # ConfigParser compatibility methods
    def __post_init__(self):
        """Initialize internal config parser for compatibility"""
        self._parser = None

    def _load_parser(self):
        """Load the config parser if not already loaded"""
        if self._parser is None:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")
            if os.path.exists(config_path):
                self._parser = configparser.ConfigParser()
                self._parser.read(config_path)
            else:
                self._parser = configparser.ConfigParser()

    def get(self, section: str, option: str, fallback: str = None) -> str:
        """ConfigParser compatible get method"""
        self._load_parser()
        try:
            return self._parser.get(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

    def getint(self, section: str, option: str, fallback: int = None) -> int:
        """ConfigParser compatible getint method"""
        self._load_parser()
        try:
            return self._parser.getint(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback

    def getfloat(self, section: str, option: str, fallback: float = None) -> float:
        """ConfigParser compatible getfloat method"""
        self._load_parser()
        try:
            return self._parser.getfloat(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback

    def getboolean(self, section: str, option: str, fallback: bool = None) -> bool:
        """ConfigParser compatible getboolean method"""
        self._load_parser()
        try:
            return self._parser.getboolean(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback

class ServiceLocator:
    """
    Patrón Singleton + Service Locator
    
    SOLUCIONA:
    - ✅ Múltiples IBKRAdapters -> Una sola instancia compartida
    - ✅ Múltiples RiskManagers -> Un solo estado de posiciones
    - ✅ Múltiples TelegramClients -> Notificaciones unificadas
    - ✅ Configuraciones conflictivas -> Una sola fuente de verdad
    - ✅ Sistemas duplicados -> Un sistema unificado
    """
    
    _instance: Optional['ServiceLocator'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self._services: Dict[str, Any] = {}
        self._config: Optional[UnifiedConfig] = None
        self._logger = logging.getLogger("ServiceLocator")
        self._initialized = True
        
        self._logger.info("🏗️ ServiceLocator initialized - UNIFIED TRADING SYSTEM")
        self._logger.info("📋 Patrón: Singleton + Dependency Injection")
    
    def load_config(self, config_file: str = "config.ini") -> UnifiedConfig:
        """Cargar configuración unificada desde config.ini"""
        if self._config is not None:
            return self._config
            
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), config_file)
            
            if not os.path.exists(config_path):
                self._logger.warning(f"⚠️ Config file not found: {config_path} - using defaults")
                self._config = UnifiedConfig()
                return self._config
            
            parser = configparser.ConfigParser()
            parser.read(config_path)
            
            # Load unified configuration
            self._config = UnifiedConfig(
                # IBKR - CRITICAL: Use single client_id to avoid conflicts
                client_id=parser.getint('IBKR', 'client_id', fallback=1),
                host=parser.get('IBKR', 'host', fallback="127.0.0.1"),
                port=parser.getint('IBKR', 'port', fallback=7497),
                
                # Risk Management
                max_positions=parser.getint('TRADING', 'max_positions', fallback=15),
                max_positions_per_symbol=parser.getint('TRADING', 'max_positions_per_symbol', fallback=1),
                max_daily_loss=parser.getfloat('TRADING', 'max_daily_loss', fallback=-500.0),
                max_daily_trades=parser.getint('TRADING', 'max_daily_trades', fallback=20),
                max_position_value=parser.getfloat('TRADING', 'max_position_value', fallback=200.0),
                
                # Strategy
                strategy_name=parser.get('TRADING', 'strategy', fallback="realistic_strategy_engine"),
                long_only=parser.getboolean('GLOBAL', 'long_only', fallback=True),
                
                # Production mode detection
                production_mode=parser.get('TRADING', 'active_profile', fallback="MOCK") == "PRODUCTION",
                enable_smallcap_mode=parser.getboolean('TRADING', 'enable_smallcap_mode', fallback=True),
                scan_interval=parser.getint('TRADING', 'scan_interval_seconds', fallback=30),
                
                # Hybrid Learning System
                enable_hybrid_learning=parser.getboolean('TRADING', 'enable_hybrid_learning', fallback=True),
                hybrid_max_strategies=parser.getint('TRADING', 'hybrid_max_strategies', fallback=1),
                hybrid_learning_rate=parser.getfloat('TRADING', 'hybrid_learning_rate', fallback=0.1),
                
                # TradeTally Integration
                enable_tradetally_sync=parser.getboolean('TRADING', 'enable_tradetally_sync', fallback=True),
                tradetally_sync_time=parser.get('TRADING', 'tradetally_sync_time', fallback='16:30'),  # After market close
                tradetally_api_key=parser.get('TRADETALLY', 'api_key', fallback=''),
                tradetally_base_url=parser.get('TRADETALLY', 'base_url', fallback='https://app.tradetally.com/api/v2')
            )
            
            self._logger.info(f"✅ Unified config loaded from {config_file}")
            self._logger.info(f"   Mode: {'PRODUCTION' if self._config.production_mode else 'MOCK'}")
            self._logger.info(f"   Client ID: {self._config.client_id}")
            self._logger.info(f"   Strategy: {self._config.strategy_name}")
            self._logger.info(f"   Smallcap Mode: {self._config.enable_smallcap_mode}")
            
            return self._config
            
        except Exception as e:
            self._logger.error(f"❌ Error loading config: {e}")
            self._config = UnifiedConfig()
            return self._config
    
    def get_config(self) -> UnifiedConfig:
        """Get unified configuration"""
        if self._config is None:
            return self.load_config()
        return self._config
    
    def register_service(self, service_name: str, instance: Any) -> None:
        """Register a service instance"""
        with self._lock:
            if service_name in self._services:
                self._logger.warning(f"⚠️ Service '{service_name}' already registered - replacing")
            
            self._services[service_name] = instance
            self._logger.info(f"✅ Service registered: {service_name} -> {type(instance).__name__}")
    
    def get_service(self, service_name: str, service_type: Type[T] = None) -> Optional[T]:
        """Get a service instance"""
        service = self._services.get(service_name)
        
        if service is None:
            return None
        
        if service_type and not isinstance(service, service_type):
            self._logger.warning(f"❌ Service '{service_name}' type mismatch")
            return None
            
        return service
    
    async def get_or_create_ibkr_adapter(self):
        """Get or create THE SINGLE IBKRAdapter instance - SOLVES DUPLICATION"""
        adapter = self.get_service('ibkr_adapter')
        
        if adapter is None:
            config = self.get_config()
            self._logger.info(f"🔌 Creating SINGLE IBKRAdapter instance (client_id={config.client_id})")
            
            # Import here to avoid circular imports
            if config.production_mode:
                from adapters.ibkr_adapter import IBKRAdapter
                adapter = IBKRAdapter(client_id=config.client_id)
            else:
                from adapters.mock_ibkr_adapter import MockIBKRAdapter
                adapter = MockIBKRAdapter(client_id=config.client_id)
            
            # Connect if not connected
            if hasattr(adapter, 'is_connected') and not adapter.is_connected():
                self._logger.info("🔗 Connecting to IBKR...")
                await adapter.connect()
                self._logger.info("✅ IBKR connected")
            
            self.register_service('ibkr_adapter', adapter)
            self._logger.info("✅ IBKRAdapter created and registered - NO MORE DUPLICATES")
        
        return adapter
    
    async def get_or_create_risk_manager(self):
        """Get or create THE SINGLE RiskManager instance - SOLVES STATE SYNC"""
        risk_manager = self.get_service('risk_manager')
        
        if risk_manager is None:
            config = self.get_config()
            self._logger.info("🛡️ Creating SINGLE RiskManager instance")
            
            # Import here to avoid circular imports
            from core.risk_manager import RiskManager
            from core.interfaces import TradingConfig
            
            # Create unified config
            trading_config = TradingConfig()
            trading_config.max_positions = config.max_positions
            trading_config.max_daily_loss = config.max_daily_loss
            trading_config.max_daily_trades = config.max_daily_trades
            trading_config.max_positions_per_symbol = config.max_positions_per_symbol
            trading_config.max_position_value = config.max_position_value
            
            risk_manager = RiskManager(trading_config)
            
            # CRITICAL: Connect to shared IBKRAdapter
            ibkr_adapter = await self.get_or_create_ibkr_adapter()
            if ibkr_adapter:
                risk_manager.broker = ibkr_adapter
                # Force position sync - get positions from broker
                try:
                    broker_positions = await ibkr_adapter.get_positions() if hasattr(ibkr_adapter, 'get_positions') else {}
                    risk_manager.update_broker_positions(broker_positions)
                    self._logger.info("🔗 RiskManager connected to shared IBKRAdapter")
                except Exception as e:
                    self._logger.warning(f"⚠️ Could not sync initial positions: {e}")
            
            self.register_service('risk_manager', risk_manager)
            self._logger.info("✅ RiskManager created - UNIFIED STATE")
        
        return risk_manager
    
    async def get_or_create_smart_game_plan_manager(self):
        """Get or create THE SINGLE Smart Game Plan Manager instance"""
        game_plan_manager = self.get_service('smart_game_plan_manager')
        
        if game_plan_manager is None:
            config = self.get_config()
            self._logger.info("🧠 Creating SINGLE Smart Game Plan Manager instance")
            
            # Import here to avoid circular imports
            from core.smart_game_plan_manager import SmartGamePlanManager
            
            # Create Smart Game Plan Manager with config
            game_plan_manager = SmartGamePlanManager(
                config=config,
                data_provider=None,  # Could add data provider later
                logger=self._logger
            )
            
            # Start dynamic updates
            await game_plan_manager.start_dynamic_updates()
            
            # Register the service
            self.register_service('smart_game_plan_manager', game_plan_manager)
            self._logger.info("✅ Smart Game Plan Manager created and registered - Context-aware planning active")
        
        return game_plan_manager
    
    async def get_or_create_mayordomo(self):
        """Get or create THE SINGLE SmallcapMayordomo instance - SOLVES POSITION CONFLICTS"""
        mayordomo = self.get_service('mayordomo')
        
        if mayordomo is None:
            config = self.get_config()
            self._logger.info("🏛️ Creating SINGLE SmallcapMayordomo instance")
            
            # Import here to avoid circular imports
            from core.risk_manager import create_smallcap_mayordomo
            from core.interfaces import TradingConfig
            
            # Create unified config
            trading_config = TradingConfig()
            trading_config.max_positions = config.max_positions
            trading_config.max_daily_loss = config.max_daily_loss
            trading_config.max_daily_trades = config.max_daily_trades
            trading_config.max_positions_per_symbol = config.max_positions_per_symbol
            
            # CRITICAL: Get shared IBKRAdapter
            ibkr_adapter = await self.get_or_create_ibkr_adapter()
            
            # Create mayordomo with shared broker
            mayordomo = create_smallcap_mayordomo(trading_config, broker=ibkr_adapter)
            
            self.register_service('mayordomo', mayordomo)
            self._logger.info("✅ SmallcapMayordomo created - SHARED STATE")
        
        return mayordomo
    
    def get_or_create_telegram_client(self):
        """Get or create THE SINGLE TelegramClient instance - SOLVES LOG CONFLICTS"""
        telegram = self.get_service('telegram_client')
        
        if telegram is None:
            self._logger.info("📱 Creating SINGLE TelegramClient instance")
            
            # Import here to avoid circular imports  
            from notifications import telegram_client
            
            # Register the module itself as the service
            self.register_service('telegram_client', telegram_client)
            self._logger.info("✅ TelegramClient registered - UNIFIED NOTIFICATIONS")
        
        return telegram
    
    async def get_or_create_trading_engine(self):
        """Get or create THE SINGLE TradingEngine instance - SOLVES DOUBLE EXECUTION"""
        engine = self.get_service('trading_engine')
        
        if engine is None:
            config = self.get_config()
            self._logger.info("⚡ Creating SINGLE TradingEngine instance")
            
            # Import here to avoid circular imports
            from engine.trading_engine import TradingEngine
            from core.interfaces import TradingConfig
            
            # Create unified config
            trading_config = TradingConfig()
            trading_config.max_positions = config.max_positions
            trading_config.max_daily_loss = config.max_daily_loss
            trading_config.max_daily_trades = config.max_daily_trades
            trading_config.max_positions_per_symbol = config.max_positions_per_symbol
            
            # Get shared services
            self._logger.info("🔗 Getting shared IBKR adapter for TradingEngine...")
            ibkr_adapter = await self.get_or_create_ibkr_adapter()
            if ibkr_adapter is None:
                self._logger.error("❌ IBKR adapter is None!")
                return None
                
            self._logger.info("🛡️ Getting shared risk manager for TradingEngine...")
            risk_manager = await self.get_or_create_risk_manager()
            if risk_manager is None:
                self._logger.error("❌ Risk manager is None!")
                return None
            
            # Create unified engine with configured strategy
            self._logger.info("🎯 Loading strategy...")
            from strategies import get_strategy_class
            strategy_name = config.strategy_name
            strategy_class = get_strategy_class(strategy_name)
            
            if strategy_class is None:
                self._logger.warning(f"⚠️ Strategy '{strategy_name}' not found, using SimpleStrategyEngine")
                from strategies.simple_strategy_engine import SimpleStrategyEngine
                strategy = SimpleStrategyEngine()
            else:
                self._logger.info(f"🎯 Using configured strategy: {strategy_name}")
                strategy = strategy_class()
            
            if strategy is None:
                self._logger.error("❌ Strategy is None!")
                return None
            
            # Inject Smart Game Plan Manager if strategy supports it
            if hasattr(strategy, 'set_smart_game_plan_manager'):
                self._logger.info("🧠 Injecting Smart Game Plan Manager into strategy...")
                smart_game_plan_manager = await self.get_or_create_smart_game_plan_manager()
                if smart_game_plan_manager:
                    strategy.set_smart_game_plan_manager(smart_game_plan_manager)
                else:
                    self._logger.warning("⚠️ Failed to create Smart Game Plan Manager")
                
            self._logger.info("⚡ Creating TradingEngine instance...")
            engine = TradingEngine(
                config=trading_config,
                data_provider=ibkr_adapter,
                broker=ibkr_adapter,
                strategy=strategy,
                risk_manager=risk_manager
            )
            
            if engine is None:
                self._logger.error("❌ TradingEngine constructor returned None!")
                return None
            
            self.register_service('trading_engine', engine)
            self._logger.info("✅ TradingEngine created - NO MORE DOUBLE EXECUTION")
        
        return engine
    
    async def get_or_create_hybrid_learning_system(self):
        """Get or create THE SINGLE Hybrid Learning System instance"""
        hybrid_system = self.get_service('hybrid_learning_system')
        
        if hybrid_system is None:
            config = self.get_config()
            
            if not config.enable_hybrid_learning:
                self._logger.info("🧠 Hybrid Learning System disabled in config")
                return None
                
            self._logger.info("🧠 Creating SINGLE Hybrid Learning System instance")
            
            try:
                # Import here to avoid circular imports
                from analysis.hybrid_learning_system import create_hybrid_learning_system
                
                # Create hybrid system with config
                hybrid_config = {
                    "max_strategies": config.hybrid_max_strategies,
                    "learning_rate": config.hybrid_learning_rate,
                    "available_strategies": ["gap_go"]  # Solo Gap&Go por ahora
                }
                
                hybrid_system = await create_hybrid_learning_system(hybrid_config)
                
                self.register_service('hybrid_learning_system', hybrid_system)
                self._logger.info("✅ Hybrid Learning System created - PROFESSIONAL TRADER AI ACTIVE")
                
            except Exception as e:
                self._logger.error(f"❌ Error creating Hybrid Learning System: {e}")
                return None
        
        return hybrid_system
    
    async def get_or_create_tradetally_service(self):
        """Get or create TradeTally integration service"""
        tradetally_service = self.get_service('tradetally_service')
        
        if tradetally_service is None:
            config = self.get_config()
            
            if not config.enable_tradetally_sync:
                self._logger.info("📊 TradeTally sync disabled in config")
                return None
                
            self._logger.info("📊 Creating TradeTally integration service")
            
            try:
                # Import here to avoid circular imports
                from integrations.tradetally.core.tradetally_scheduled_sync import TradeTallyScheduledSync
                import os
                
                # Get project root for database path
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_path = os.path.join(project_root, "trading_data.db")
                
                # Create TradeTally service with market close scheduling
                tradetally_service = TradeTallyScheduledSync(
                    api_key=config.tradetally_api_key,
                    base_url=config.tradetally_base_url,
                    db_path=db_path,
                    sync_time=config.tradetally_sync_time
                )
                
                # Start the scheduler
                tradetally_service.start_scheduler()
                
                self.register_service('tradetally_service', tradetally_service)
                self._logger.info("✅ TradeTally service created - End-of-day sync scheduled")
                
            except Exception as e:
                self._logger.error(f"❌ Error creating TradeTally service: {e}")
                import traceback
                self._logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                return None
        
        return tradetally_service
    
    async def cleanup(self):
        """Cleanup all services"""
        self._logger.info("🧹 Cleaning up unified system...")
        
        # Stop Hybrid Learning System
        hybrid_system = self.get_service('hybrid_learning_system')
        if hybrid_system:
            try:
                # Save learned models before cleanup
                if hasattr(hybrid_system, 'ml_selector') and hybrid_system.ml_selector:
                    hybrid_system.ml_selector.save_model("data/ml_models/hybrid_strategy_selector.json")
                self._logger.info("✅ Hybrid Learning System saved and stopped")
            except Exception as e:
                self._logger.warning(f"⚠️ Error stopping Hybrid Learning System: {e}")
        
        # Stop TradeTally Service
        tradetally_service = self.get_service('tradetally_service')
        if tradetally_service:
            try:
                tradetally_service.stop_scheduler()
                self._logger.info("✅ TradeTally service stopped")
            except Exception as e:
                self._logger.warning(f"⚠️ Error stopping TradeTally service: {e}")
        
        # Stop Trading Engine
        engine = self.get_service('trading_engine')
        if engine and hasattr(engine, 'stop'):
            try:
                await engine.stop()
                self._logger.info("✅ TradingEngine stopped")
            except Exception as e:
                self._logger.warning(f"⚠️ Error stopping TradingEngine: {e}")
        
        # Disconnect IBKRAdapter
        ibkr = self.get_service('ibkr_adapter')
        if ibkr and hasattr(ibkr, 'disconnect'):
            try:
                await ibkr.disconnect()
                self._logger.info("✅ IBKRAdapter disconnected")
            except Exception as e:
                self._logger.warning(f"⚠️ Error disconnecting IBKRAdapter: {e}")
        
        # Clear all services
        self._services.clear()
        self._logger.info("✅ All services cleaned up")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        config = self.get_config()
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'system_mode': 'PRODUCTION' if config.production_mode else 'MOCK',
            'services_count': len(self._services),
            'registered_services': list(self._services.keys()),
            'config': {
                'client_id': config.client_id,
                'strategy': config.strategy_name,
                'max_positions': config.max_positions,
                'max_positions_per_symbol': config.max_positions_per_symbol,
                'smallcap_mode': config.enable_smallcap_mode,
                'hybrid_learning_enabled': config.enable_hybrid_learning,
                'hybrid_max_strategies': config.hybrid_max_strategies
            }
        }
        
        # Add service-specific statuses
        ibkr = self.get_service('ibkr_adapter')
        if ibkr:
            status['ibkr_connected'] = getattr(ibkr, 'is_connected', lambda: False)()
            
        risk_manager = self.get_service('risk_manager')
        if risk_manager:
            status['positions_count'] = len(getattr(risk_manager, 'broker_positions', {}))
        
        hybrid_system = self.get_service('hybrid_learning_system')
        if hybrid_system:
            try:
                hybrid_status = hybrid_system.get_system_status()
                status['hybrid_learning_system'] = hybrid_status['hybrid_learning_system']
            except Exception as e:
                status['hybrid_learning_system'] = {'error': str(e)}
        
        tradetally_service = self.get_service('tradetally_service')
        if tradetally_service:
            try:
                tradetally_status = tradetally_service.get_sync_status()
                status['tradetally_service'] = tradetally_status
            except Exception as e:
                status['tradetally_service'] = {'error': str(e)}
            
        return status

# Global singleton instance
_service_locator = ServiceLocator()

def get_service_locator() -> ServiceLocator:
    """Get the global ServiceLocator instance"""
    return _service_locator

# Convenience functions for easy access
async def get_ibkr_adapter():
    """Get the shared IBKRAdapter"""
    return await get_service_locator().get_or_create_ibkr_adapter()

async def get_risk_manager():
    """Get the shared RiskManager"""
    return await get_service_locator().get_or_create_risk_manager()

async def get_mayordomo():
    """Get the shared SmallcapMayordomo"""
    return await get_service_locator().get_or_create_mayordomo()

def get_telegram_client():
    """Get the shared TelegramClient"""
    return get_service_locator().get_or_create_telegram_client()

async def get_trading_engine():
    """Get the shared TradingEngine"""
    return await get_service_locator().get_or_create_trading_engine()

def get_config():
    """Get the unified configuration"""
    return get_service_locator().get_config()