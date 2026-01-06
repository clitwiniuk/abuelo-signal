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

    # Extended Hours Trading
    enable_extended_hours_trading: bool = True
    allow_premarket_entries: bool = True
    allow_afterhours_entries: bool = True

    # Worker Enable/Disable Flags
    volume_absorption_worker_enabled: bool = False  # Disabled by default (institutional accumulation)
    generic_01_strategy_enabled: bool = True  # Low volume accumulation worker
    smallcaps_long_strategy_enabled: bool = True  # Rule-based smallcap strategy
    outlier_penny_extreme_strategy_enabled: bool = True  # Penny stock outlier hunter

    # Strategy Workers (estos son los que NECESITAS que funcionen)
    macdv_strategy_enabled: bool = True  # MACDV worker
    daily_plays_strategy_enabled: bool = True  # Daily Plays worker
    orb_strategy_enabled: bool = True  # ORB (Opening Range Breakout) worker
    vwap_breakout_strategy_enabled: bool = True  # VWAP Breakout worker
    momentum_breakout_strategy_enabled: bool = True  # Momentum Breakout worker
    vcp_strategy_enabled: bool = True  # VCP Smallcap worker
    balance_day_strategy_enabled: bool = True  # Balance Day Range Trading worker

    # Universal Pattern-Driven Workers (ODS-based)
    ods_universal_strategy_enabled: bool = True  # ODS Universal worker (intraday pattern-driven)
    ods_swing_universal_strategy_enabled: bool = True  # ODS Swing Universal worker (multiday 1-7 days)

class ServiceLocator:
    """
    Patrón Singleton + Service Locator
    
    SOLUCIONA:
    - ✅ Múltiples IBKRAdapters → Una sola instancia compartida
    - ✅ Múltiples RiskManagers → Un solo estado de posiciones
    - ✅ Múltiples TelegramClients → Notificaciones unificadas
    - ✅ Configuraciones conflictivas → Una sola fuente de verdad
    - ✅ Sistemas duplicados → Un sistema unificado
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
                tradetally_base_url=parser.get('TRADETALLY', 'base_url', fallback='https://app.tradetally.com/api/v2'),

                # Extended Hours Trading
                enable_extended_hours_trading=parser.getboolean('GLOBAL', 'enable_extended_hours_trading', fallback=True),
                allow_premarket_entries=parser.getboolean('GLOBAL', 'allow_premarket_entries', fallback=True),
                allow_afterhours_entries=parser.getboolean('GLOBAL', 'allow_afterhours_entries', fallback=True),

                # Worker Enable/Disable Flags (read from their respective strategy sections)
                volume_absorption_worker_enabled=parser.getboolean('VOLUME_ABSORPTION_WORKER', 'enabled', fallback=False),
                generic_01_strategy_enabled=parser.getboolean('GENERIC_01_STRATEGY', 'enabled', fallback=False),
                smallcaps_long_strategy_enabled=parser.getboolean('SMALLCAPS_LONG_STRATEGY', 'enabled', fallback=False),
                outlier_penny_extreme_strategy_enabled=parser.getboolean('OUTLIER_PENNY_EXTREME_STRATEGY', 'enabled', fallback=False),

                # Strategy Workers (MACD, ORB, Daily Plays, Momentum, etc.)
                macdv_strategy_enabled=parser.getboolean('MACDV_STRATEGY', 'enabled', fallback=True),
                daily_plays_strategy_enabled=parser.getboolean('DAILY_PLAYS_STRATEGY', 'enabled', fallback=True),
                orb_strategy_enabled=parser.getboolean('ORB_STRATEGY', 'enabled', fallback=True),
                balance_day_strategy_enabled=parser.getboolean('BALANCE_DAY_STRATEGY', 'enabled', fallback=True),
                vwap_breakout_strategy_enabled=parser.getboolean('VWAP_BREAKOUT_STRATEGY', 'enabled', fallback=True),
                momentum_breakout_strategy_enabled=parser.getboolean('MOMENTUM_BREAKOUT_STRATEGY', 'enabled', fallback=True),
                vcp_strategy_enabled=parser.getboolean('VCP_STRATEGY', 'enabled', fallback=True),

                # Universal Pattern-Driven Workers
                ods_universal_strategy_enabled=parser.getboolean('ODS_UNIVERSAL_STRATEGY', 'enabled', fallback=True),
                ods_swing_universal_strategy_enabled=parser.getboolean('ODS_SWING_UNIVERSAL_STRATEGY', 'enabled', fallback=True)
            )
            
            self._logger.info(f"✅ Unified config loaded from {config_file}")
            self._logger.info(f"   Mode: {'PRODUCTION' if self._config.production_mode else 'MOCK'}")
            self._logger.info(f"   Client ID: {self._config.client_id}")
            self._logger.info(f"   Strategy: {self._config.strategy_name}")
            self._logger.info(f"   Smallcap Mode: {self._config.enable_smallcap_mode}")
            self._logger.info(f"   Workers Enabled:")
            self._logger.info(f"     ❌ Disabled Workers:")
            self._logger.info(f"        - volume_absorption: {self._config.volume_absorption_worker_enabled}")
            self._logger.info(f"        - generic_01: {self._config.generic_01_strategy_enabled}")
            self._logger.info(f"        - smallcaps_long: {self._config.smallcaps_long_strategy_enabled}")
            self._logger.info(f"        - outlier_penny_extreme: {self._config.outlier_penny_extreme_strategy_enabled}")
            self._logger.info(f"     ✅ Active Workers (Pattern-Independent):")
            self._logger.info(f"        - macdv: {self._config.macdv_strategy_enabled}")
            self._logger.info(f"        - daily_plays: {self._config.daily_plays_strategy_enabled}")
            self._logger.info(f"        - orb: {self._config.orb_strategy_enabled}")
            self._logger.info(f"        - balance_day: {self._config.balance_day_strategy_enabled}")
            self._logger.info(f"        - vwap_breakout: {self._config.vwap_breakout_strategy_enabled}")
            self._logger.info(f"        - momentum_breakout: {self._config.momentum_breakout_strategy_enabled}")
            self._logger.info(f"        - vcp: {self._config.vcp_strategy_enabled}")
            self._logger.info(f"     🎯 Universal Pattern-Driven Workers:")
            self._logger.info(f"        - ods_universal (intraday): {self._config.ods_universal_strategy_enabled}")
            self._logger.info(f"        - ods_swing_universal (1-7 days): {self._config.ods_swing_universal_strategy_enabled}")
            
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

            # Return the newly registered service
            return telegram_client

        return telegram
    
    async def get_or_create_trading_engine(self):
        """
        DEPRECATED: Legacy TradingEngine is no longer used in worker-based system.
        Use get_or_create_ibkr_adapter() and get_or_create_risk_manager() instead.

        This method is kept for backward compatibility only.
        """
        self._logger.warning(
            "⚠️ get_or_create_trading_engine() is DEPRECATED. "
            "Worker-based system does not need TradingEngine. "
            "Returning None - use ExecutionEngineAdapter with broker+risk_manager instead."
        )
        return None

        # OLD CODE DISABLED - All legacy TradingEngine code commented out
        # engine = self.get_service('trading_engine')
        # if engine is None:
        #     config = self.get_config()
        #     ... (all legacy code removed)
    
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
    
    async def get_or_create_unified_position_manager(self):
        """Get or create THE SINGLE UnifiedPositionManager instance - PREVENTS DUPLICATES"""
        position_manager = self.get_service('unified_position_manager')

        if position_manager is None:
            self._logger.info("💼 Creating SINGLE UnifiedPositionManager instance")

            try:
                # Import here to avoid circular imports
                from core.unified_position_manager import UnifiedPositionManager
                import configparser

                # Read swing trading config
                config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
                parser = configparser.ConfigParser()
                parser.read(config_path)

                # Read capital config from UNIFIED_POSITION_MANAGER section
                total_capital = parser.getfloat('UNIFIED_POSITION_MANAGER', 'total_capital', fallback=3000.0)

                swing_config = {}
                if 'UNIFIED_POSITION_MANAGER' in parser:
                    swing_config = {
                        'day_capital_percentage': parser.getfloat('UNIFIED_POSITION_MANAGER', 'day_capital_percentage', fallback=0.60),
                        'swing_capital_percentage': parser.getfloat('UNIFIED_POSITION_MANAGER', 'swing_capital_percentage', fallback=0.40)
                    }

                # Create with capital from config.ini
                position_manager = UnifiedPositionManager(
                    total_capital=total_capital,
                    config=swing_config
                )

                self.register_service('unified_position_manager', position_manager)
                self._logger.info("✅ UnifiedPositionManager created - DUPLICATE PREVENTION ACTIVE")

            except Exception as e:
                self._logger.error(f"❌ Error creating UnifiedPositionManager: {e}")
                import traceback
                self._logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                return None

        return position_manager

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
                # Import new API-First auto-sync system (WebSocket + File Watcher)
                from integrations.tradetally.core.tradetally_autosync import TradeTallyAutoSync, SQLiteWatcher
                from watchdog.observers import Observer
                import os

                # Get project root for database path
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_path = os.path.join(project_root, "trading_data.db")

                # Create TradeTally auto-sync service (WebSocket + File Watcher)
                # This service monitors trading_data.db for changes and syncs automatically
                tradetally_service = TradeTallyAutoSync(
                    api_key=config.tradetally_api_key,
                    base_url=config.tradetally_base_url,
                    db_path=db_path
                )

                # Connect to WebSocket for real-time sync
                tradetally_service.connect()

                # Start file watcher for database changes
                observer = Observer()
                event_handler = SQLiteWatcher(tradetally_service)
                db_dir = os.path.dirname(db_path)
                observer.schedule(event_handler, db_dir, recursive=False)
                observer.start()

                # Store both service and observer for cleanup
                self.register_service('tradetally_service', tradetally_service)
                self.register_service('tradetally_observer', observer)

                self._logger.info("✅ TradeTally auto-sync service created - WebSocket + File Watcher active")

            except ImportError as e:
                self._logger.warning(f"⚠️ TradeTally auto-sync not available: Missing dependency '{e.name}'")
                self._logger.info(f"💡 Install with: pip install python-socketio watchdog")
                self._logger.info(f"📝 You can still use manual sync: ./tt-manage.sh sync")
                return None
            except Exception as e:
                self._logger.error(f"❌ Error creating TradeTally service: {e}")
                import traceback
                self._logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                return None

        return tradetally_service

    def get_ods_classifier(self):
        """Get or create ODS Classifier service"""
        ods_classifier = self.get_service('ods_classifier')

        if ods_classifier is None:
            from core.ods_classifier import ODSClassifier

            ods_classifier = ODSClassifier()
            self.register_service('ods_classifier', ods_classifier)

            self._logger.info("✅ ODSClassifier service created - Opening Drive Structure analysis enabled")

        return ods_classifier

    def get_intraday_structure_classifier(self):
        """Get or create Intraday Structure Classifier service"""
        intraday_classifier = self.get_service('intraday_structure_classifier')

        if intraday_classifier is None:
            from core.intraday_structure_classifier import IntradayStructureClassifier

            intraday_classifier = IntradayStructureClassifier()

            # Inject ODS Classifier dependency
            ods_classifier = self.get_ods_classifier()
            intraday_classifier.set_ods_classifier(ods_classifier)

            self.register_service('intraday_structure_classifier', intraday_classifier)

            self._logger.info("✅ IntradayStructureClassifier service created - 6 pattern system enabled")

        return intraday_classifier

    async def get_or_create_tradetally_manual_service(self):
        """Get or create TradeTally manual sync service (independent of scheduler)"""
        manual_service = self.get_service('tradetally_manual_service')

        if manual_service is None:
            config = self.get_config()

            if not config.enable_tradetally_sync:
                self._logger.info("📊 TradeTally sync disabled in config")
                return None

            self._logger.info("🔧 Creating TradeTally manual sync service")

            try:
                # Import here to avoid circular imports
                from integrations.tradetally.core.tradetally_manual_sync import TradeTallyManualSync
                import os

                # Get project root for database path
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_path = os.path.join(project_root, "trading_data.db")

                # Create manual service (independent of scheduler)
                manual_service = TradeTallyManualSync(
                    api_key=config.tradetally_api_key,
                    base_url=config.tradetally_base_url,
                    db_path=db_path
                )

                self.register_service('tradetally_manual_service', manual_service)
                self._logger.info("✅ TradeTally manual service created - Independent of scheduler")

            except Exception as e:
                self._logger.error(f"❌ Error creating TradeTally manual service: {e}")
                import traceback
                self._logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                return None

        return manual_service
    
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

async def get_unified_position_manager():
    """Get the shared UnifiedPositionManager"""
    return await get_service_locator().get_or_create_unified_position_manager()

def get_telegram_client():
    """Get the shared TelegramClient"""
    return get_service_locator().get_or_create_telegram_client()

async def get_trading_engine():
    """Get the shared TradingEngine"""
    return await get_service_locator().get_or_create_trading_engine()

def get_config():
    """Get the unified configuration"""
    return get_service_locator().get_config()