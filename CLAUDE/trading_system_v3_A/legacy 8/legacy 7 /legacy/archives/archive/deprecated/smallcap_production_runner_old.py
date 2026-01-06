# production/smallcap_production_runner.py
"""
PRODUCCIÓN - Runner Principal para Smallcaps Intraday
Aprovecha TODO el código existente del proyecto para implementación real
"""

# Global instance for Telegram command access
_global_runner_instance = None

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
import signal
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any
import json
import hashlib
from dataclasses import asdict

# Aprovechar código existente del proyecto
try:
    from adapters.ibkr_adapter import IBKRAdapter
    from core.risk_manager import create_smallcap_mayordomo, get_mayordomo_status
    from core.performance_metrics import get_performance_tracker
    from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
    from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
    from scanner.hybrid_scanner import HybridScanner
    from scanner.tiingo_data_provider import TiingoDataProvider
    from core.interfaces import TradingConfig
    from production.hybrid_config_manager import HybridConfigManager
    
    # CRITICAL: Import TradingEngine for actual trade execution
    from engine.trading_engine import TradingEngine
    from core.events import AsyncEventBus
    
    # Telegram notifications (aprovechando sistema existente)
    from notifications.telegram_client import (
        send_message as telegram_send_message,
        start_command_listener,
        stop_command_listener,
        is_enabled as telegram_is_enabled
    )
    
    # Comandos específicos smallcaps para Telegram
    from production.telegram_smallcap_commands import SmallcapTelegramCommands, send_smallcap_help
    
    # ML Trading Journal System (Elite ML Enhancement)
    try:
        from strategies.ml_journal_integration import MLJournalIntegration, ContextEnhancer
        from strategies.ml_trading_journal import MLTradingJournal
        from strategies.advanced_pattern_discovery import AdvancedTradeClassifier, PatternMiner, EdgeDiscoveryEngine
        ML_JOURNAL_AVAILABLE = True
    except ImportError as e:
        logging.warning(f"ML Journal not available: {e}")
        ML_JOURNAL_AVAILABLE = False
        MLJournalIntegration = None
        MLTradingJournal = None
    
    # Opcional - fallbacks si no existen
    try:
        from utils.performance_monitor import PerformanceMonitor
    except ImportError:
        PerformanceMonitor = None
        
    try:
        from utils.log_config import setup_logging
    except ImportError:
        def setup_logging(level="INFO", log_file=None):
            logging.basicConfig(
                level=getattr(logging, level),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

except ImportError as e:
    print(f"❌ Error importando componentes del proyecto: {e}")
    print("💡 Asegúrate de que todos los componentes estén disponibles")
    sys.exit(1)

class SmallcapProductionRunner:
    """
    Runner de Producción para Smallcaps Intraday
    
    Integra todos los componentes existentes del proyecto:
    - IBKRAdapter para conexiones reales
    - SmallcapMayordomo para gestión de posiciones
    - Scanner híbrido IBKR+Tiingo
    - ML Strategy Engine 
    - Performance monitoring
    """
    
    def __init__(self, config_path: str = None, test_mode: bool = False):
        global _global_runner_instance
        _global_runner_instance = self  # Allow Telegram commands to access this instance
        
        self.logger = logging.getLogger("SmallcapProduction")
        
        # Test mode for verifying TradingEngine integration
        self.test_mode = test_mode
        if test_mode:
            self.logger.info("🧪 MODO TEST ACTIVADO - Mayordomo será más permisivo")
        
        # Usar HybridConfigManager para configuración
        try:
            self.hybrid_config = HybridConfigManager()
            self.config = self._load_hybrid_config()
            self.logger.info("✅ Configuración híbrida cargada desde config.ini + extensiones")
        except Exception as e:
            self.logger.error(f"❌ Error cargando configuración híbrida: {e}")
            self.config = self._load_fallback_config(config_path)
        
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # Cache para evitar alertas duplicadas
        self.alert_cache = {}  # {symbol: {timestamp, price, message_hash}}
        self.alert_cooldown_minutes = 30  # No re-alertar el mismo símbolo por 30 min
        
        # Componentes core (aprovechando código existente)
        self.ibkr_adapter: Optional[IBKRAdapter] = None
        self.tiingo_provider: Optional[TiingoDataProvider] = None
        self.hybrid_scanner: Optional[HybridScanner] = None
        self.smallcap_scanner: Optional[SmallcapDailyScanner] = None
        self.ml_engine: Optional[MLMultiStrategyEngine] = None
        self.mayordomo: Optional[Any] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None
        
        # Performance tracking para sistema multicapa
        self.multilayer_tracker = get_performance_tracker()
        
        # CRITICAL: Add TradingEngine for actual trade execution
        self.trading_engine: Optional[TradingEngine] = None
        self.event_bus: Optional[AsyncEventBus] = None
        
        # ML Journal System (Elite ML Enhancement)
        self.ml_journal_integration: Optional[MLJournalIntegration] = None
        self.ml_journal: Optional[MLTradingJournal] = None
        
        # Estado de producción
        self.scan_count = 0
        self.total_plays_found = 0
        self.active_positions = {}
        self.last_scan_time = None
        self.recent_plays = []  # Store last plays for Telegram command
        
        # Comandos específicos de Telegram
        self.telegram_commands = SmallcapTelegramCommands(self)
        
        # Setup signal handlers para shutdown graceful
        self._setup_signal_handlers()
        
        self.logger.info("🚀 SmallcapProductionRunner inicializado")
    
    def _load_hybrid_config(self) -> Dict[str, Any]:
        """Cargar configuración usando HybridConfigManager"""
        
        # Obtener configuración completa híbrida
        complete_config = self.hybrid_config.get_complete_hybrid_config()
        
        # Extraer configuraciones específicas para fácil acceso
        base_config = complete_config["base_config"]
        production_ext = complete_config["production_extensions"]
        
        # Construir configuración para el runner
        runner_config = {
            "environment": "production",
            "trading_mode": "smallcaps_intraday",
            "config_source": "hybrid",
            
            # IBKR desde config.ini + env vars
            "ibkr": self.hybrid_config.get_ibkr_config(),
            
            # Trading params desde config.ini
            "trading": self.hybrid_config.get_trading_params(),
            
            # Smallcap strategy desde config.ini [DAILY_PLAYS_STRATEGY]
            "smallcap_strategy": self.hybrid_config.get_smallcap_strategy_config(),
            
            # Tiingo desde extensiones de producción
            "tiingo": production_ext["tiingo"],
            
            # Scanning intervals desde extensiones
            "scanning_intervals": production_ext["scanning_intervals"],
            
            # Monitoring desde extensiones  
            "monitoring": {
                "log_level": "INFO",
                "metrics_collection_interval": production_ext["production_monitoring"].get("metrics_collection_interval", 60),
                "health_check_interval_seconds": production_ext["production_monitoring"].get("health_check_interval_seconds", 60),
                "auto_restart_on_failure": production_ext["production_monitoring"].get("auto_restart_on_failure", True)
            },
            
            # Alertas desde extensiones (Slack, Email, etc.)
            "alerts": production_ext["production_alerts"],
            
            # Telegram desde config.ini existente
            "telegram": production_ext["telegram"],
            
            # Hybrid scanner config desde extensiones
            "hybrid_scanner": production_ext["hybrid_scanner"],
            
            # Safety settings desde extensiones
            "safety": production_ext["live_trading_safety"],
            
            # Trading hours desde config.ini
            "trading_hours": {
                "market_open": float(base_config.get("global", {}).get("market_open_hour", "9.5")),
                "market_close": float(base_config.get("global", {}).get("market_close_hour", "16.0")),
                "no_entry_after": float(base_config.get("global", {}).get("no_entry_after", "14.0")),
                "enable_premarket": True,  # Agregado - faltaba
                "premarket_start": 4.0
            },
            
            # Scanning config
            "scanning": {
                "interval_seconds": production_ext["scanning_intervals"]["regular_market_seconds"],
                "max_symbols": 100,
                "filters": self.hybrid_config.get_smallcap_strategy_config()
            },
            
            # Risk config desde trading params
            "risk": {
                "max_positions": self.hybrid_config.get_trading_params()["max_positions"],
                "position_size": 0.02,  # 2% por posición
                "daily_loss_limit": self.hybrid_config.get_trading_params()["daily_loss_limit"]
            },
            
            # ML Engine config (nuevo - faltaba)
            "ml_engine": {
                "enabled": True,
                "strategy_selection": True,
                "contextual_bandit": True,
                "performance_feedback": True
            },
            
            # Performance monitoring config
            "monitoring": {
                "sampling_interval": 5.0,
                "enabled": True,
                "log_level": "INFO"
            }
        }
        
        return runner_config
    
    def _load_fallback_config(self, config_path: str) -> Dict[str, Any]:
        """Configuración fallback si HybridConfigManager falla"""
        
        # Configuración base mínima para smallcaps intraday
        base_config = {
            "environment": "production",
            "trading_mode": "smallcaps_intraday",
            "config_source": "fallback",
            
            # IBKR Settings básicos
            "ibkr": {
                "host": os.getenv("IBKR_HOST", "127.0.0.1"),
                "port": int(os.getenv("IBKR_PORT", "7497")),
                "client_id": int(os.getenv("IBKR_CLIENT_ID", "100")),
                "account": os.getenv("IBKR_ACCOUNT", ""),
                "timeout": 30
            },
            
            # Tiingo Settings
            "tiingo": {
                "api_key": os.getenv("TIINGO_API_KEY", ""),
                "rate_limit": 1000,  # requests/hour
                "timeout": 15
            },
            
            # Smallcap Scanning (aprovechando SmallcapDailyScanner)
            "scanning": {
                "interval_seconds": 30,           # Scan cada 30 segundos
                "premarket_interval": 60,         # Más lento en premarket
                "min_gap_percentage": 0.08,       # 8% gap mínimo
                "min_volume": 500_000,            # 500K volumen mínimo
                "min_volume_ratio": 2.0,          # 2x volumen promedio
                "min_price": 0.50,                # $0.50 mínimo
                "max_price": 15.00,               # $15 máximo (smallcaps)
                "max_results": 20,                # Top 20 plays
                "quality_threshold": 6.0          # Score mínimo 6/10
            },
            
            # Risk Management (aprovechando SmallcapMayordomo)
            "risk": {
                "max_positions": 5,               # Max 5 posiciones simultáneas
                "position_size": 0.02,            # 2% por posición
                "daily_loss_limit": 0.05,         # 5% pérdida diaria máx
                "intraday_only": True,            # Solo intraday
                "extended_hours": False           # Solo horario regular
            },
            
            # ML Engine (aprovechando multi_strategy_engine_ml)
            "ml_engine": {
                "enabled": True,
                "strategy_selection": True,
                "contextual_bandit": True,
                "performance_feedback": True
            },
            
            # Performance monitoring
            "monitoring": {
                "sampling_interval": 5.0,
                "enabled": True
            },
            
            # Horarios de Trading
            "trading_hours": {
                "market_open": "09:30",
                "market_close": "16:00",
                "premarket_start": "04:00",
                "enable_premarket": True,
                "enable_afterhours": False
            },
            
            # Monitoreo (aprovechando PerformanceMonitor)
            "monitoring": {
                "enabled": True,
                "metrics_interval": 60,          # Métricas cada minuto
                "alert_latency_ms": 5000,        # Alerta si >5s latencia
                "alert_error_rate": 0.05,        # Alerta si >5% errores
                "log_level": "INFO"
            }
        }
        
        # Si hay config file específico, hacer merge
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                    self._deep_merge(base_config, file_config)
            except Exception as e:
                logging.warning(f"Error loading config file {config_path}: {e}")
        
        return base_config
    
    def _deep_merge(self, base: dict, override: dict):
        """Merge configs recursively"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _setup_signal_handlers(self):
        """Setup signal handlers para shutdown graceful"""
        def signal_handler(signum, frame):
            self.logger.info(f"📥 Señal recibida: {signum}. Iniciando shutdown graceful...")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def initialize(self) -> bool:
        """
        Inicializar todos los componentes de producción
        Aprovecha TODOS los componentes existentes del proyecto
        """
        try:
            self.logger.info("🔧 Inicializando componentes de producción...")
            
            # 1. Setup logging (aprovechando log_config existente)
            log_level = self.config.get("monitoring", {}).get("log_level", "INFO")
            # Setup log file path relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_file_path = os.path.join(project_root, "logs", "smallcap_production.log")
            
            setup_logging(
                level=log_level,
                log_file=log_file_path
            )
            
            # 2. Inicializar IBKR Adapter (aprovechando código existente)
            self.logger.info("📡 Conectando a IBKR...")
            self.ibkr_adapter = IBKRAdapter(
                host=self.config["ibkr"]["host"],
                port=self.config["ibkr"]["port"],
                client_id=self.config["ibkr"]["client_id"]
            )
            await self.ibkr_adapter.connect()
            self.logger.info("✅ IBKR conectado")
            
            # 3. Inicializar Tiingo Provider
            self.logger.info("🌐 Configurando Tiingo...")
            self.tiingo_provider = TiingoDataProvider(
                api_key=self.config["tiingo"]["api_key"]
            )
            self.logger.info("✅ Tiingo configurado")
            
            # 4. Inicializar Scanner Híbrido (aprovechando implementación)
            self.logger.info("🔍 Configurando scanner híbrido...")
            self.hybrid_scanner = HybridScanner()
            
            # 5. Inicializar SmallcapDailyScanner (aprovechando código existente)
            self.logger.info("🔍 Inicializando SmallcapDailyScanner...")
            try:
                self.smallcap_scanner = SmallcapDailyScanner()
                self.logger.info("✅ SmallcapDailyScanner inicializado correctamente")
            except Exception as e:
                self.logger.error(f"❌ Error inicializando SmallcapDailyScanner: {e}")
                self.smallcap_scanner = None
            self.logger.info("✅ Scanner híbrido configurado")
            
            # 6. Crear TradingConfig para Risk Manager
            try:
                trading_config = TradingConfig()
                # Configurar parámetros específicos para smallcaps
                if hasattr(trading_config, 'max_positions'):
                    trading_config.max_positions = self.config["risk"]["max_positions"]
                if hasattr(trading_config, 'position_size'):
                    trading_config.position_size = self.config["risk"]["position_size"]
                if hasattr(trading_config, 'daily_loss_limit'):
                    trading_config.daily_loss_limit = self.config["risk"]["daily_loss_limit"]
                
                # 7. Inicializar SmallcapMayordomo (aprovechando implementación existente)
                self.logger.info("🎯 Inicializando SmallcapMayordomo...")
                # CRITICAL FIX: Pass shared broker for position synchronization
                self.mayordomo = create_smallcap_mayordomo(trading_config, broker=self.ibkr_adapter)
                
                if self.ibkr_adapter:
                    self.logger.info("✅ SmallcapMayordomo inicializado con broker compartido para sincronización de posiciones")
                else:
                    self.logger.warning("⚠️ SmallcapMayordomo inicializado sin conexión al broker - no habrá auto-sync")
                self.logger.info("✅ SmallcapMayordomo inicializado")
            except Exception as e:
                self.logger.warning(f"⚠️ Error inicializando Mayordomo: {e}")
                self.mayordomo = None
            
            # 8. Inicializar ML Strategy Engine (aprovechando código existente)
            if self.config["ml_engine"]["enabled"]:
                self.logger.info("🧠 Inicializando ML Strategy Engine...")
                # Create parameters dict for MLMultiStrategyEngine
                ml_parameters = {
                    "smallcap_ml_enabled": True,
                    "smallcap_mayordomo_enabled": True,
                    "smallcap_price_threshold": 15.0,
                    "ibkr_adapter": self.ibkr_adapter
                }
                self.ml_engine = MLMultiStrategyEngine(parameters=ml_parameters)
                self.logger.info("✅ ML Strategy Engine inicializado")
            
            # 8.5. Inicializar ML Journal System (Elite ML Enhancement)
            if ML_JOURNAL_AVAILABLE and self.config["ml_engine"]["enabled"]:
                self.logger.info("🧠📊 Inicializando ML Trading Journal (Elite Enhancement)...")
                try:
                    self.ml_journal_integration = MLJournalIntegration(
                        hybrid_config_manager=self.hybrid_config,
                        ml_engine=self.ml_engine
                    )
                    await self.ml_journal_integration.initialize()
                    self.logger.info("✅ ML Trading Journal inicializado - ML transformado a nivel ELITE")
                except Exception as e:
                    self.logger.error(f"❌ Error inicializando ML Journal: {e}")
                    self.ml_journal_integration = None
            
            # 9. Inicializar Performance Monitor (aprovechando utils existente)
            if PerformanceMonitor:
                self.logger.info("📊 Configurando performance monitor...")
                # PerformanceMonitor expects sampling_interval, not config
                sampling_interval = self.config.get("monitoring", {}).get("sampling_interval", 5.0)
                self.performance_monitor = PerformanceMonitor(sampling_interval=sampling_interval)
                self.performance_monitor.start()
                self.logger.info("✅ Performance monitor activo")
            else:
                self.logger.warning("⚠️ PerformanceMonitor no disponible")
                self.performance_monitor = None
            
            # 10. CRITICAL: Initialize TradingEngine for actual trade execution
            self.logger.info("⚡ Inicializando TradingEngine para ejecución de trades...")
            await self._initialize_trading_engine()
            
            # 11. Inicializar Telegram (aprovechando sistema existente)
            self.logger.info("📱 Configurando Telegram...")
            await self._initialize_telegram()
            
            self.logger.info("🚀 TODOS los componentes inicializados correctamente")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando componentes: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _initialize_trading_engine(self):
        """Initialize TradingEngine for actual trade execution"""
        try:
            # 1. Initialize Event Bus
            self.event_bus = AsyncEventBus()
            self.logger.info("✅ Event bus inicializado")
            
            # 2. Create TradingConfig from our config
            trading_config = TradingConfig()
            
            # Map our config to TradingConfig
            trading_params = self.hybrid_config.get_trading_params()
            
            trading_config.long_only = self.config.get("trading", {}).get("long_only", True)
            trading_config.max_positions = trading_params.get("max_positions", 5)
            trading_config.position_size = self.config.get("risk", {}).get("position_size", 0.02)
            trading_config.daily_loss_limit = trading_params.get("daily_loss_limit", 100.0)
            trading_config.risk_per_trade = trading_params.get("risk_per_trade", 0.015)
            
            # CRITICAL: Map position sizing parameters from config.ini
            trading_config.max_position_value = trading_params.get("max_position_value", 200.0)
            trading_config.min_quantity = trading_params.get("min_quantity", 10)
            
            # Map pyramid trading parameters (DISABLED by default)
            trading_config.allow_pyramiding = trading_params.get("allow_pyramiding", False)
            trading_config.max_pyramid_levels = trading_params.get("max_pyramid_levels", 1)
            trading_config.pyramid_profit_threshold = trading_params.get("pyramid_profit_threshold", 0.05)
            trading_config.pyramid_size_fraction = trading_params.get("pyramid_size_fraction", 0.5)
            trading_config.pyramid_cooldown_minutes = trading_params.get("pyramid_cooldown_minutes", 30)
            
            self.logger.info("✅ TradingConfig creado para smallcaps")
            self.logger.info(f"💰 Position sizing: max_value=${trading_config.max_position_value}, min_qty={trading_config.min_quantity}")
            
            # Log pyramid configuration status
            pyramid_status = "🔺 ENABLED" if trading_config.allow_pyramiding else "🚫 DISABLED"
            self.logger.info(f"🔺 Pyramid trading: {pyramid_status}")
            if trading_config.allow_pyramiding:
                self.logger.info(f"   └─ Max levels: {trading_config.max_pyramid_levels}, Min profit: {trading_config.pyramid_profit_threshold:.1%}")
            else:
                self.logger.info(f"   └─ Anti-martingala protection: Active")
            
            # 3. Initialize TradingEngine with all components
            # CRITICAL FIX: Use IBKR as data provider since Tiingo doesn't have connect()
            self.trading_engine = TradingEngine(
                config=trading_config,
                data_provider=self.ibkr_adapter,    # Use IBKR as data provider (has connect())
                broker=self.ibkr_adapter,           # Use IBKR for execution (same instance)
                strategy=self.ml_engine,            # Use ML engine as strategy
                risk_manager=self.mayordomo,        # Use Mayordomo as risk manager
                filters=[]                          # No additional filters needed
            )
            
            # 4. Initialize and START the TradingEngine pipeline
            await self.trading_engine.initialize()
            self.logger.info("✅ TradingEngine inicializado")
            
            # CRITICAL FIX: Start the pipeline in background to process signals
            self.trading_engine_task = asyncio.create_task(self.trading_engine.start())
            self.logger.info("🚀 TradingEngine pipeline iniciado en background")
            self.logger.info("🎯 Sistema listo para ejecutar trades automáticamente")
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando TradingEngine: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.trading_engine = None
    
    async def _initialize_telegram(self):
        """Inicializar sistema de Telegram"""
        try:
            telegram_config = self.config.get("telegram", {})
            
            if not telegram_config.get("enabled", False):
                self.logger.info("📱 Telegram deshabilitado en configuración")
                return
            
            if not telegram_config.get("bot_token") or not telegram_config.get("chat_id"):
                self.logger.warning("⚠️ Credenciales de Telegram faltantes")
                return
            
            # Verificar que el sistema de Telegram esté disponible
            if not telegram_is_enabled():
                self.logger.warning("⚠️ Sistema de Telegram no disponible")
                return
            
            # Iniciar command listener si está habilitado
            if telegram_config.get("command_listener_enabled", False):
                # Registrar nuestro handler de comandos específicos
                self._register_telegram_command_handler()
                start_command_listener()
                self.logger.info("✅ Telegram command listener iniciado")
            
            # Enviar mensaje de inicio
            startup_message = f"""
🚀 **SISTEMA SMALLCAPS INTRADAY INICIADO**
═══════════════════════════════════

🎯 **Configuración:**
• Scanner: Cada {self.config['scanning']['interval_seconds']}s
• Filtros: ${self.config['smallcap_strategy']['min_price']}-${self.config['smallcap_strategy']['max_price']}, Gap >{self.config['smallcap_strategy']['min_gap_percent']}%
• Risk: Max {self.config['risk']['max_positions']} posiciones
• ML Engine: {'✅ Activo' if self.config['ml_engine']['enabled'] else '❌ Desactivado'}

📱 **Comandos disponibles:**
/menu - Ver menú completo
/smallcap - Status sistema específico
/scanner - Estado del scanner híbrido
/plays - Plays recientes detectados
/stats - Estadísticas generales
/trades - Trades ejecutados
/log 50 - Logs del sistema

🟢 Sistema listo para trading smallcaps intraday
            """
            
            telegram_send_message(startup_message, parse_mode="Markdown")
            self.logger.info("✅ Telegram inicializado y mensaje de startup enviado")
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando Telegram: {e}")
    
    def _register_telegram_command_handler(self):
        """Registrar handler de comandos específicos de smallcaps"""
        try:
            # Importar el módulo de telegram_client para extender su funcionalidad
            import notifications.telegram_client as telegram_client
            
            # Guardar el handler original
            original_handle_command = telegram_client._handle_command
            
            # Crear nuevo handler que incluye comandos específicos
            def enhanced_handle_command(text: str):
                # Primero intentar manejar con comandos específicos
                if self.telegram_commands.handle_smallcap_command(text):
                    return  # Comando manejado por sistema específico
                
                # Si no fue manejado, usar el handler original
                original_handle_command(text)
            
            # Reemplazar el handler
            telegram_client._handle_command = enhanced_handle_command
            
            self.logger.info("✅ Handler de comandos smallcaps registrado")
            
        except Exception as e:
            self.logger.error(f"Error registrando handler de comandos: {e}")
    
    def get_performance_summary(self):
        """Get multi-layer performance summary"""
        try:
            summary = self.multilayer_tracker.get_performance_summary()
            effectiveness = self.multilayer_tracker.get_layer_effectiveness()
            recommendations = self.multilayer_tracker.should_simplify_system()
            
            summary_text = "📊 **PERFORMANCE MULTICAPA**\n\n"
            
            # Check if we have any data
            total_signals = sum(stats.get('total_signals', 0) for layer, stats in summary.items() if layer != 'recent_performance')
            
            if total_signals == 0:
                summary_text += "⏳ **SISTEMA INICIANDO**\n"
                summary_text += "• Sin trades completados aún\n"
                summary_text += "• Performance tracking activado ✅\n"
                summary_text += "• Esperando primeros trades...\n\n"
                
                # Show current session info
                summary_text += f"📈 **SESIÓN ACTUAL**\n"
                summary_text += f"• Scans completados: {self.scan_count}\n"
                summary_text += f"• Plays encontrados: {self.total_plays_found}\n"
                summary_text += f"• Última actividad: {self.last_scan_time.strftime('%H:%M:%S') if self.last_scan_time else 'N/A'}\n\n"
                
                # Show active tracking
                active_trades = len(self.multilayer_tracker.active_trades)
                completed_trades = len(self.multilayer_tracker.completed_trades)
                summary_text += f"🔄 **TRACKING STATUS**\n"
                summary_text += f"• Trades activos: {active_trades}\n"
                summary_text += f"• Trades completados: {completed_trades}\n"
                summary_text += f"• Sistema: {'🟢 FUNCIONANDO' if self.is_running else '🔴 PARADO'}\n"
                
                return summary_text
            
            # Layer performance (when we have data)
            for layer, stats in summary.items():
                if layer != 'recent_performance':
                    effectiveness_status = effectiveness.get(layer, 'UNKNOWN')
                    summary_text += f"**{layer.upper()}**\n"
                    summary_text += f"• Accuracy: {stats['accuracy_rate']}\n"
                    summary_text += f"• Total señales: {stats['total_signals']}\n"
                    summary_text += f"• PnL total: {stats['total_pnl']}\n"
                    summary_text += f"• Estado: {effectiveness_status}\n\n"
            
            # Recent performance
            if 'recent_performance' in summary:
                recent = summary['recent_performance']
                summary_text += f"**RENDIMIENTO RECIENTE (7D)**\n"
                summary_text += f"• Trades: {recent['trades_last_7d']}\n"
                summary_text += f"• PnL: {recent['pnl_last_7d']}\n"
                summary_text += f"• Duración promedio: {recent['avg_duration_hours']}\n\n"
            
            # Recommendations
            if recommendations['simplify_recommended']:
                summary_text += "🔧 **RECOMENDACIONES**\n"
                for reason in recommendations['reasons']:
                    summary_text += f"• {reason}\n"
                for action in recommendations['actions']:
                    summary_text += f"-> {action}\n"
            
            return summary_text
            
        except Exception as e:
            self.logger.error(f"Error getting performance summary: {e}")
            return "❌ Error obteniendo estadísticas de performance"
    
    def _should_send_alert(self, symbol: str, price: float, message: str) -> bool:
        """Verificar si debemos enviar la alerta (evitar duplicados)"""
        now = datetime.now()
        message_hash = hashlib.md5(message.encode()).hexdigest()[:8]
        
        # Limpiar cache viejo (más de 2 horas)
        cutoff_time = now - timedelta(hours=2)
        symbols_to_remove = []
        for sym, data in self.alert_cache.items():
            if data['timestamp'] < cutoff_time:
                symbols_to_remove.append(sym)
        
        for sym in symbols_to_remove:
            del self.alert_cache[sym]
        
        # Verificar si ya enviamos alerta para este símbolo recientemente
        if symbol in self.alert_cache:
            last_alert = self.alert_cache[symbol]
            time_diff = now - last_alert['timestamp']
            
            # Si es el mismo mensaje dentro del cooldown, no enviar
            if (time_diff.total_seconds() < self.alert_cooldown_minutes * 60 and 
                last_alert['message_hash'] == message_hash):
                return False
                
            # Si es mensaje diferente pero precio muy similar (< 2% cambio), no enviar
            if last_alert['price'] > 0:
                price_change_pct = abs(price - last_alert['price']) / last_alert['price']
                if price_change_pct < 0.02 and time_diff.total_seconds() < 15 * 60:  # 15 min para cambios menores
                    return False
        
        # Actualizar cache
        self.alert_cache[symbol] = {
            'timestamp': now,
            'price': price,
            'message_hash': message_hash
        }
        
        return True

    def _send_telegram_alert(self, message: str, alert_type: str = "INFO"):
        """Enviar alerta via Telegram con rate limiting"""
        try:
            telegram_config = self.config.get("telegram", {})
            
            if not telegram_config.get("enabled", False):
                return
            
            # Verificar configuración específica de smallcap alerts
            smallcap_alerts = telegram_config.get("smallcap_alerts", {})
            
            # Determinar si enviar basado en tipo de alerta
            should_send = False
            if alert_type == "EXCEPTIONAL_PLAY" and smallcap_alerts.get("exceptional_plays", True):
                should_send = True
            elif alert_type == "POSITION_UPDATE" and smallcap_alerts.get("position_updates", True):
                should_send = True
            elif alert_type == "ERROR" and smallcap_alerts.get("error_alerts", True):
                should_send = True
            elif alert_type == "INFO":
                should_send = True
            
            if should_send:
                telegram_send_message(message, parse_mode="Markdown")
                
        except Exception as e:
            self.logger.error(f"Error enviando alerta Telegram: {e}")
    
    async def _check_exceptional_plays_telegram(self, plays):
        """Verificar y alertar plays excepcionales via Telegram"""
        try:
            exceptional_thresholds = self.config.get("alerts", {}).get("exceptional_play_thresholds", {})
            min_gap = exceptional_thresholds.get("min_gap_for_alert", 0.15)  # 15%
            min_volume_ratio = exceptional_thresholds.get("min_volume_ratio_for_alert", 5.0)  # 5x
            min_quality_score = exceptional_thresholds.get("min_quality_score_for_alert", 8.0)  # Score >8
            
            exceptional_plays = []
            
            for play in plays:
                # Verificar criterios de plays excepcionales
                is_exceptional = False
                reasons = []
                
                # Gap excepcional
                if hasattr(play.context, 'gap_percentage') and play.context.gap_percentage >= min_gap:
                    is_exceptional = True
                    reasons.append(f"Gap {play.context.gap_percentage*100:.1f}%")
                
                # Volumen excepcional
                if hasattr(play.context, 'premarket_volume_ratio') and play.context.premarket_volume_ratio >= min_volume_ratio:
                    is_exceptional = True
                    reasons.append(f"Vol {play.context.premarket_volume_ratio:.1f}x")
                
                # Quality score excepcional
                if hasattr(play, 'quality_score') and play.quality_score >= min_quality_score:
                    is_exceptional = True
                    reasons.append(f"Score {play.quality_score:.1f}")
                
                if is_exceptional:
                    exceptional_plays.append((play, reasons))
            
            # Enviar alertas para plays excepcionales (con deduplicación)
            if exceptional_plays:
                # Filtrar plays que no deben ser re-alertados
                filtered_plays = []
                for play, reasons in exceptional_plays:
                    current_price = getattr(play.context, 'current_price', 0)
                    
                    # Crear mensaje individual para el play
                    individual_message = f"{play.symbol}: {', '.join(reasons)}, ${current_price:.2f}"
                    
                    # Verificar si debemos enviar alerta para este símbolo
                    if self._should_send_alert(play.symbol, current_price, individual_message):
                        filtered_plays.append((play, reasons))
                        self.logger.info(f"✅ Nueva alerta aprobada para {play.symbol} @ ${current_price:.2f}")
                    else:
                        self.logger.debug(f"🔇 Alerta duplicada filtrada para {play.symbol} @ ${current_price:.2f}")
                
                # Solo enviar si hay plays nuevos/únicos
                if filtered_plays:
                    alert_message = "🔥 **PLAYS EXCEPCIONALES DETECTADOS** 🔥\n"
                    alert_message += "═══════════════════════════════════\n\n"
                    
                    for play, reasons in filtered_plays:
                        current_price = getattr(play.context, 'current_price', 0)
                        volume = getattr(play.context, 'volume', 0)
                        
                        alert_message += f"🎯 **{play.symbol}**\n"
                        alert_message += f"• Precio: ${current_price:.2f}\n"
                        alert_message += f"• Volumen: {volume:,}\n"
                        alert_message += f"• Criterios: {', '.join(reasons)}\n"
                        if hasattr(play, 'catalyst'):
                            alert_message += f"• Catalyst: {play.catalyst.catalyst_type}\n"
                        alert_message += "\n"
                    
                    alert_message += f"📊 Total: {len(filtered_plays)} plays excepcionales"
                    
                    self._send_telegram_alert(alert_message, "EXCEPTIONAL_PLAY")
                    self.logger.info(f"📱 Enviada alerta Telegram para {len(filtered_plays)} plays excepcionales nuevos")
                else:
                    self.logger.debug("🔇 Todas las alertas fueron filtradas como duplicadas")
                
        except Exception as e:
            self.logger.error(f"Error verificando plays excepcionales para Telegram: {e}")
    
    async def run_production_scanning(self):
        """
        Loop principal de scanning de producción
        Optimizado para smallcaps intraday
        """
        self.logger.info("🔄 Iniciando loop de scanning de producción...")
        self.is_running = True
        
        while self.is_running and not self.shutdown_event.is_set():
            try:
                self.logger.debug(f"🔄 Loop iteration - checking trading time...")
                
                # Verificar si estamos en horario de trading
                if not self._is_trading_time():
                    self.logger.info(f"⏰ Fuera de horario de trading - esperando 1 minuto...")
                    await asyncio.sleep(60)  # Esperar 1 minuto si fuera de horario
                    continue
                
                scan_start_time = datetime.now()
                
                # Performance tracking
                if self.performance_monitor:
                    self.performance_monitor.record_event("scan_started")
                
                # 1. Ejecutar scan usando SmallcapDailyScanner (código existente)
                self.logger.info(f"🔍 Ejecutando scan #{self.scan_count + 1}...")
                
                if self.smallcap_scanner is None:
                    self.logger.error("❌ SmallcapDailyScanner no está inicializado, saltando scan")
                    await asyncio.sleep(self.config["scanning"]["interval_seconds"])
                    continue
                
                plays = await self.smallcap_scanner.scan_daily_plays(force_refresh=True)
                
                if plays:
                    self.logger.info(f"📈 Encontrados {len(plays)} plays de calidad")
                    self.total_plays_found += len(plays)
                    
                    # Store recent plays for Telegram command
                    self.recent_plays = plays[:10]  # Keep last 10 plays
                    
                    # 2. Alertas Telegram para plays excepcionales
                    try:
                        # Use asyncio.wait_for to timeout Telegram alerts if they hang
                        await asyncio.wait_for(
                            self._check_exceptional_plays_telegram(plays), 
                            timeout=10.0  # Max 10 seconds for Telegram
                        )
                        self.logger.info("✅ Alertas Telegram completadas")
                    except asyncio.TimeoutError:
                        self.logger.warning("⚠️ Timeout en alertas Telegram - continuando con Mayordomo")
                    except Exception as e:
                        self.logger.error(f"⚠️ Error en alertas Telegram: {e} - continuando con Mayordomo")
                    
                    # 3. Primero procesar con ML Engine para obtener estrategias recomendadas
                    strategies_info = {}
                    if self.ml_engine:
                        strategies_info = await self._analyze_plays_with_ml_engine(plays)
                    
                    # 4. Evaluar plays con SmallcapMayordomo usando info de estrategias
                    self.logger.info(f"🔍 Evaluando {len(plays)} plays con SmallcapMayordomo...")
                    for play in plays:
                        self.logger.info(f"🎯 Evaluando play: {play.symbol} con Mayordomo")
                        strategy_info = strategies_info.get(play.symbol, {})
                        await self._evaluate_play_with_mayordomo(
                            play, 
                            strategies_recommended=strategy_info.get('strategies_recommended', ['default']),
                            selected_strategy=strategy_info.get('selected_strategy', 'gap_and_go'),
                            strategy_confidence=strategy_info.get('strategy_confidence', 0.5)
                        )
                    
                    # 5. Log resultados
                    self._log_scan_results(plays, scan_start_time)
                
                else:
                    self.logger.info("⏸️ No se encontraron plays de calidad en este scan")
                
                # Update counters
                self.scan_count += 1
                self.last_scan_time = datetime.now()
                
                # Performance tracking
                if self.performance_monitor:
                    scan_duration = (datetime.now() - scan_start_time).total_seconds()
                    self.performance_monitor.record_event("scan_completed")
                    # Log scan metrics instead of recording as metrics
                    self.logger.info(f"📊 Scan metrics: duration={scan_duration:.1f}s, plays={len(plays) if plays else 0}")
                
                # Esperar hasta el próximo scan
                await self._wait_for_next_scan()
                
            except Exception as e:
                self.logger.error(f"❌ Error en loop de scanning: {e}")
                if self.performance_monitor:
                    self.performance_monitor.record_event("scan_error")
                
                # Esperar antes de retry
                await asyncio.sleep(30)
    
    async def _evaluate_play_with_mayordomo(self, play, strategies_recommended=None, selected_strategy=None, strategy_confidence=0.5):
        """Evaluar play usando SmallcapMayordomo (aprovechando código existente)"""
        self.logger.info(f"🔄 INICIANDO evaluación Mayordomo para {play.symbol}")
        try:
            # 📊 Start performance tracking for this trade flow
            finbert_result = {
                'catalyst_type': play.catalyst.catalyst_type,
                'catalyst_strength': play.catalyst.strength,
                'confidence': getattr(play.catalyst, 'confidence', 0.7)
            }
            
            trade_flow = self.multilayer_tracker.start_trade_flow(
                symbol=play.symbol,
                finbert_result=finbert_result,
                strategies=strategies_recommended or ['default'],
                selected_strategy=selected_strategy or 'gap_and_go',
                strategy_confidence=strategy_confidence
            )
            
            # Evaluar si abrir posición - crear diccionario opportunity
            new_opportunity = {
                'symbol': play.symbol,
                'catalyst_type': play.catalyst.catalyst_type,
                'catalyst_strength': play.catalyst.strength,
                'gap_percentage': play.context.gap_percentage,
                'volume_ratio': play.context.premarket_volume_ratio,
                'current_price': play.context.current_price
            }
            
            # 🧪 TEST MODE: Force approval for testing
            if self.test_mode and play.quality_score >= 5.0:
                self.logger.info(f"🧪 TEST MODE: Forzando aprobación para {play.symbol} (Quality Score: {play.quality_score:.1f})")
                decision = {
                    "action": "OPEN_POSITION",
                    "reason": "TEST_MODE_OVERRIDE",
                    "position_size": 0.02,  # 2% position size
                    "confidence": 0.95,
                    "test_mode": True
                }
            else:
                self.logger.info(f"🎯 Solicitando evaluación del Mayordomo para {play.symbol}")
                decision = self.mayordomo.evaluate_position_rotation(new_opportunity)
                self.logger.info(f"🔍 Decisión del Mayordomo para {play.symbol}: {decision}")
            
            if decision and decision.get("action") == "OPEN_POSITION":
                self.logger.info(f"🎯 Mayordomo recomienda ABRIR posición en {play.symbol}")
                
                # CRITICAL: Register daily play ONLY after approval
                self.mayordomo.register_daily_play(
                    symbol=play.symbol,
                    catalyst_type=play.catalyst.catalyst_type,
                    catalyst_strength=play.catalyst.strength,
                    gap_percentage=play.context.gap_percentage,
                    volume_ratio=play.context.premarket_volume_ratio,
                    entry_price=play.context.current_price
                )
                
                # 📊 Update performance tracking - trade execution approved
                self.multilayer_tracker.update_trade_execution(
                    symbol=play.symbol,
                    executed=True,
                    entry_price=play.context.current_price
                )
                
                # CRITICAL: Execute trade through TradingEngine
                if self.trading_engine:
                    await self._execute_trade_via_engine(play, decision)
                else:
                    self.logger.warning(f"⚠️ TradingEngine no disponible - no se puede ejecutar trade para {play.symbol}")
            else:
                # 📊 Update performance tracking - trade execution rejected
                self.multilayer_tracker.update_trade_execution(
                    symbol=play.symbol,
                    executed=False
                )
                
        except Exception as e:
            self.logger.error(f"Error evaluando play {play.symbol} con mayordomo: {e}")
    
    async def complete_trade_tracking(self, symbol: str, exit_price: float, pnl: float):
        """Complete trade tracking with final PnL"""
        try:
            trade_flow = self.multilayer_tracker.complete_trade(symbol, exit_price, pnl)
            self.logger.info(f"📊 Trade tracking completed for {symbol}: PnL=${pnl:.2f}")
            return trade_flow
        except Exception as e:
            self.logger.error(f"Error completing trade tracking for {symbol}: {e}")
    
    async def _execute_trade_via_engine(self, play, decision):
        """Execute trade through TradingEngine"""
        try:
            self.logger.info(f"⚡ Ejecutando trade para {play.symbol} via TradingEngine...")
            
            # 1. First add the symbol to TradingEngine monitoring
            success = await self.trading_engine.add_symbol(play.symbol, skip_validation=True)
            if not success:
                self.logger.error(f"❌ No se pudo agregar {play.symbol} al TradingEngine")
                return False
            
            # 2. Create signal from play and decision
            from core.interfaces import Signal, SignalType
            
            signal = Signal(
                signal_id="",  # Will be auto-generated
                symbol=play.symbol,
                signal_type=SignalType.LONG,  # Smallcaps are long-only
                strength=min(play.quality_score / 10.0, 1.0),  # Normalize to 0-1
                price=play.context.current_price,
                timestamp=datetime.now(),
                strategy_name="SmallcapMayordomo",
                metadata={
                    "catalyst_type": play.catalyst.catalyst_type,
                    "catalyst_strength": play.catalyst.strength,
                    "gap_percentage": play.context.gap_percentage,
                    "volume_ratio": play.context.premarket_volume_ratio,
                    "quality_score": play.quality_score,
                    "mayordomo_decision": decision
                }
            )
            
            # 3. Use TradingEngine pipeline directly instead of individual stages
            # The TradingEngine already has a pipeline that coordinates all stages
            self.logger.info(f"🔄 Ejecutando a través del pipeline completo de TradingEngine...")
            
            # The TradingEngine pipeline handles everything internally
            # We just need to make sure the symbol is being monitored and the engine will process it
            
            # Create mock market data to trigger analysis
            from core.interfaces import MarketData
            
            mock_market_data = MarketData(
                timestamp=datetime.now(),
                open=play.context.current_price * 0.99,
                high=play.context.current_price * 1.02,
                low=play.context.current_price * 0.98,
                close=play.context.current_price,
                volume=int(play.context.avg_daily_volume * play.context.premarket_volume_ratio),
                symbol=play.symbol
            )
            
            # Store signal in strategy for pipeline to pick up
            if hasattr(self.trading_engine.strategy, 'pending_signals'):
                if not hasattr(self.trading_engine.strategy, 'pending_signals'):
                    self.trading_engine.strategy.pending_signals = {}
                self.trading_engine.strategy.pending_signals[play.symbol] = signal
                self.logger.info(f"📋 Señal almacenada para {play.symbol} - será procesada por el pipeline")
            else:
                # Alternative: inject signal into analysis stage directly
                if hasattr(self.trading_engine, 'analysis_stage') and hasattr(self.trading_engine.analysis_stage, 'strategies'):
                    # Find the ML engine strategy and inject the signal
                    for strategy in self.trading_engine.analysis_stage.strategies:
                        if hasattr(strategy, 'inject_signal'):
                            await strategy.inject_signal(signal)
                            break
                    self.logger.info(f"💉 Señal inyectada directamente al análisis para {play.symbol}")
            
            # Send Telegram notification about signal generation
            telegram_message = f"""
🎯 **SEÑAL GENERADA**
════════════════════════

📊 **{play.symbol}**
• Precio: ${play.context.current_price:.2f}
• Gap: {play.context.gap_percentage*100:+.1f}%
• Volumen: {play.context.premarket_volume_ratio:.1f}x
• Catalyst: {play.catalyst.catalyst_type}
• Quality Score: {play.quality_score:.1f}/10

🧠 **Señal:**
• Tipo: {signal.signal_type.value}
• Confianza: {signal.strength:.1%}
• Estrategia: {signal.strategy_name}

⚡ Pipeline procesará automáticamente...
            """
            self._send_telegram_alert(telegram_message, "POSITION_UPDATE")
            
            self.logger.info(f"✅ Trade setup completado para {play.symbol} - pipeline se encargará del resto")
            return True
                
        except Exception as e:
            self.logger.error(f"❌ Error ejecutando trade para {play.symbol}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def _analyze_plays_with_ml_engine(self, plays):
        """Analizar plays con ML Engine para obtener estrategias recomendadas"""
        strategies_info = {}
        try:
            for play in plays:
                # Standard ML Engine processing - create TickerContext object
                from strategies.ml_strategy_selector import TickerContext
                
                ticker_context = TickerContext(
                    symbol=play.symbol,
                    current_price=play.context.current_price,
                    avg_volume_10=play.context.avg_daily_volume,
                    avg_volume_50=play.context.avg_daily_volume,
                    volatility_10=0.2,  # Default
                    volatility_50=0.2,
                    price_change_1h=play.context.gap_percentage,
                    price_change_4h=play.context.gap_percentage,
                    rsi_14=50.0,  # Default
                    volume_ratio_current=play.context.premarket_volume_ratio,
                    volume_spike_frequency=0.1,
                    hour_of_day=datetime.now().hour + datetime.now().minute/60.0,
                    minutes_from_open=120,  # Default
                    is_first_hour=datetime.now().hour <= 10,
                    is_last_hour=datetime.now().hour >= 15,
                    market_trend=0.0,
                    sector_performance=0.0,
                    breakout_success_rate=0.5,
                    mean_reversion_tendency=0.5
                )
                
                # Evaluar con ML engine para obtener estrategias
                strategies_recommended = []
                selected_strategy = "gap_and_go"  # Default strategy
                strategy_confidence = 0.5
                
                if hasattr(self.ml_engine, '_smallcap_mayordomo_select_strategies'):
                    strategy_decision = await self.ml_engine._smallcap_mayordomo_select_strategies(play.symbol, ticker_context)
                    
                    if strategy_decision:
                        self.logger.info(f"🧠 ML Engine recomienda estrategia para {play.symbol}: {strategy_decision}")
                        # Extract strategy information for performance tracking
                        if isinstance(strategy_decision, dict):
                            selected_strategy = strategy_decision.get('strategy', 'gap_and_go')
                            strategy_confidence = strategy_decision.get('confidence', 0.7)
                            strategies_recommended = strategy_decision.get('alternatives', [selected_strategy])
                        else:
                            selected_strategy = str(strategy_decision)
                            strategies_recommended = [selected_strategy]
                
                # Store strategy info for this play
                strategies_info[play.symbol] = {
                    'strategies_recommended': strategies_recommended or [selected_strategy],
                    'selected_strategy': selected_strategy,
                    'strategy_confidence': strategy_confidence
                }
                
                # ELITE ML ENHANCEMENT: Process with ML Journal Integration
                if self.ml_journal_integration and hasattr(play, 'context'):
                    try:
                        # Create basic context from play data
                        from strategies.ml_strategy_selector import TickerContext
                        
                        basic_context = TickerContext(
                            symbol=play.symbol,
                            current_price=play.context.current_price,
                            avg_volume_10=play.context.avg_daily_volume,
                            avg_volume_50=play.context.avg_daily_volume,
                            volatility_10=0.2,  # Default
                            volatility_50=0.2,
                            price_change_1h=play.context.gap_percentage,
                            price_change_4h=play.context.gap_percentage,
                            rsi_14=50.0,  # Default
                            volume_ratio_current=play.context.premarket_volume_ratio,
                            volume_spike_frequency=0.1,
                            hour_of_day=datetime.now().hour + datetime.now().minute/60.0,
                            minutes_from_open=120,  # Default
                            is_first_hour=datetime.now().hour <= 10,
                            is_last_hour=datetime.now().hour >= 15,
                            market_trend=0.0,
                            sector_performance=0.0,
                            breakout_success_rate=0.5,
                            mean_reversion_tendency=0.5
                        )
                        
                        # Create mock market data
                        from core.interfaces import MarketData
                        market_data = MarketData(
                            timestamp=datetime.now(),
                            open=play.context.current_price * 0.95,
                            high=play.context.current_price * 1.05,
                            low=play.context.current_price * 0.93,
                            close=play.context.current_price,
                            volume=int(play.context.avg_daily_volume * play.context.premarket_volume_ratio),
                            symbol=play.symbol
                        )
                        
                        # Get enhanced signal from ML Journal
                        enhanced_signal, confidence = await self.ml_journal_integration.enhance_signal_generation(
                            play.symbol, market_data, basic_context
                        )
                        
                        if enhanced_signal and confidence > 0.6:
                            self.logger.info(f"🧠📊 ELITE ML Signal for {play.symbol}: "
                                           f"Confidence={confidence:.2f}, "
                                           f"Enhanced Features={enhanced_signal.metadata.get('enhanced_features_count', 'N/A')}")
                            
                            # Store enhanced signal for potential execution
                            if not hasattr(self, 'enhanced_signals'):
                                self.enhanced_signals = {}
                            self.enhanced_signals[play.symbol] = enhanced_signal
                        
                    except Exception as e:
                        self.logger.error(f"Error in ML Journal enhancement for {play.symbol}: {e}")
            
            return strategies_info
                
        except Exception as e:
            self.logger.error(f"Error procesando plays con ML engine: {e}")
            return {}
    
    def _log_scan_results(self, plays, scan_start_time):
        """Log detallado de resultados del scan"""
        scan_duration = (datetime.now() - scan_start_time).total_seconds()
        
        # Log summary
        self.logger.info(f"📊 SCAN COMPLETADO #{self.scan_count + 1}:")
        self.logger.info(f"   ⏱️  Duración: {scan_duration:.2f}s")
        self.logger.info(f"   📈 Plays encontrados: {len(plays)}")
        self.logger.info(f"   🎯 Total plays sesión: {self.total_plays_found}")
        
        # Log top plays
        if plays:
            self.logger.info("   🏆 TOP PLAYS:")
            for i, play in enumerate(plays[:5], 1):  # Top 5
                self.logger.info(f"      {i}. {play.symbol}: Gap {play.context.gap_percentage*100:+.1f}%, "
                               f"Vol {play.context.premarket_volume_ratio:.1f}x, Score {play.quality_score:.1f}")
    
    def _is_trading_time(self) -> bool:
        """Verificar si estamos en horario de trading - USA EST/EDT"""
        from zoneinfo import ZoneInfo
        
        # Obtener hora actual en EST/EDT (NASDAQ timezone)
        est_now = datetime.now(ZoneInfo("America/New_York")).time()
        
        # Horarios configurados (EST/EDT)
        market_open = time(9, 30)  # 9:30 AM EST/EDT
        market_close = time(16, 0)  # 4:00 PM EST/EDT
        premarket_start = time(4, 0)  # 4:00 AM EST/EDT
        
        # Debug logging (only when needed)
        self.logger.debug(f"🕐 EST time: {est_now}, Market: {market_open}-{market_close}, Premarket: {premarket_start}")
        
        # Durante horario regular
        if market_open <= est_now <= market_close:
            self.logger.debug(f"✅ Inside regular market hours")
            return True
        
        # Durante premarket si está habilitado
        if self.config["trading_hours"]["enable_premarket"] and premarket_start <= est_now < market_open:
            self.logger.debug(f"✅ Inside premarket hours")
            return True
        
        self.logger.debug(f"❌ Outside trading hours")
        return False
    
    async def _wait_for_next_scan(self):
        """Esperar hasta el próximo scan basado en horario"""
        if self._is_trading_time():
            # Durante horario de trading
            now = datetime.now().time()
            if time(4, 0) <= now < time(9, 30):  # Premarket
                interval = self.config["scanning_intervals"]["premarket_seconds"]
            else:  # Regular hours
                interval = self.config["scanning"]["interval_seconds"]
        else:
            interval = 300  # 5 minutos fuera de horario
        
        await asyncio.sleep(interval)
    
    def get_status(self) -> Dict[str, Any]:
        """Obtener status actual del sistema"""
        mayordomo_status = get_mayordomo_status(self.mayordomo) if self.mayordomo else {}
        
        # Get ML Journal status if available
        ml_journal_status = {}
        if self.ml_journal_integration:
            try:
                ml_journal_status = self.ml_journal_integration.get_integration_status()
            except Exception as e:
                ml_journal_status = {"error": str(e)}
        
        return {
            "is_running": self.is_running,
            "scan_count": self.scan_count,
            "total_plays_found": self.total_plays_found,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "active_positions": len(self.active_positions),
            "ibkr_connected": self.ibkr_adapter.is_connected() if self.ibkr_adapter else False,
            "mayordomo_status": mayordomo_status,
            "ml_engine_enabled": self.ml_engine is not None,
            "ml_journal_status": ml_journal_status,
            "performance_monitor_active": self.performance_monitor.running if self.performance_monitor else False
        }
    
    async def generate_elite_ml_report(self) -> str:
        """Generate elite ML Journal report"""
        if not self.ml_journal_integration:
            return "ML Journal Integration not available"
        
        try:
            elite_report = await self.ml_journal_integration.generate_elite_report()
            return elite_report
        except Exception as e:
            return f"Error generating elite report: {e}"
    
    async def shutdown(self):
        """Shutdown graceful del sistema"""
        global _global_runner_instance
        _global_runner_instance = None  # Clear global reference
        
        self.logger.info("🛑 Iniciando shutdown del sistema...")
        self.is_running = False
        
        # Cleanup componentes
        if self.performance_monitor:
            self.performance_monitor.stop()
        
        if self.ibkr_adapter:
            await self.ibkr_adapter.disconnect()
        
        if self.tiingo_provider:
            # Close any open connections
            pass
        
        # Cleanup Telegram
        try:
            if self.config.get("telegram", {}).get("enabled", False):
                self._send_telegram_alert("🛑 **SISTEMA SMALLCAPS DETENIDO**\n\nSistema apagado correctamente.", "INFO")
                stop_command_listener()
                self.logger.info("📱 Telegram command listener detenido")
        except Exception as e:
            self.logger.error(f"Error cerrando Telegram: {e}")
        
        self.logger.info("✅ Shutdown completado")

# Script principal
async def main():
    """Función principal para ejecutar el sistema de producción"""
    
    # Check for test mode argument
    test_mode = "--test" in sys.argv
    
    if test_mode:
        print("🧪 SISTEMA DE PRODUCCIÓN SMALLCAPS INTRADAY - MODO TEST")
        print("🧪 Mayordomo será más permisivo para testing")
    else:
        print("🚀 SISTEMA DE PRODUCCIÓN SMALLCAPS INTRADAY")
    print("=" * 60)
    
    # Crear runner
    runner = SmallcapProductionRunner(test_mode=test_mode)
    
    try:
        # Inicializar sistema
        if not await runner.initialize():
            print("❌ Error inicializando sistema")
            return
        
        if test_mode:
            print("✅ Sistema inicializado en MODO TEST. Mayordomo override activo...")
        else:
            print("✅ Sistema inicializado. Iniciando scanning...")
        
        # Ejecutar loop principal
        await runner.run_production_scanning()
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupción manual detectada")
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Shutdown graceful
        await runner.shutdown()

if __name__ == "__main__":
    # Configurar event loop para Windows si es necesario
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Ejecutar sistema
    asyncio.run(main())