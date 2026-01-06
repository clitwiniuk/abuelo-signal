# streamlit_app_refactored.py
"""
Streamlit Trading App - Refactored Version
Based on working streamlit_app_v2.py from commit 1f2edf2 with clean code improvements
"""

import streamlit as st
import asyncio
import nest_asyncio
import configparser
import sys
import pandas as pd
from threading import Thread
import logging
from notifications import telegram_client
telegram_client.start_command_listener()  # listen for /log commands
from datetime import datetime, date
from pathlib import Path
import atexit
import random

# Apply nest_asyncio for nested event loops (required for Streamlit)
nest_asyncio.apply()

# === CONFIGURATION AND SETUP ===

class StreamlitConfig:
    """Centralized configuration for Streamlit app"""
    
    @staticmethod
    def setup_logging():
        """Setup logging configuration (idempotent)"""
        root = logging.getLogger()
        if root.handlers:
            # Streamlit reloads the script: clear handlers to avoid duplicates
            root.handlers.clear()
        
        # Setup both console and file logging
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # File handler - same as main.py uses
        file_handler = logging.FileHandler("trading_system.log", encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        logging.basicConfig(
            level=logging.INFO,
            handlers=[console_handler, file_handler],
            force=True  # Py≥3.8 ensures previous handlers are removed
        )
        
        logger = logging.getLogger("StreamlitApp")
        
        # Filter to suppress ScriptRunContext warnings during shutdown
        class StreamlitWarningFilter(logging.Filter):
            def filter(self, record):
                return "missing ScriptRunContext" not in record.getMessage()
        
        # Apply filter to all streamlit loggers
        for name in logging.root.manager.loggerDict:
            if 'streamlit' in name.lower():
                logging.getLogger(name).addFilter(StreamlitWarningFilter())
        
        return logger
    
    @staticmethod
    def setup_page():
        """Configure Streamlit page"""
        st.set_page_config(
            page_title="Sistema de Trading V3.0",
            page_icon="🚀",
            layout="wide"
        )
    
    @staticmethod
    def setup_auto_refresh():
        """Setup auto-refresh component"""
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=6000, key="auto_refresh")
        except ImportError:
            pass
        except RuntimeError:
            pass
    
    @staticmethod
    def setup_safe_dataframe():
        """Apply safe DataFrame patch to prevent Arrow errors"""
        def safe_dataframe(data, **kwargs):
            """Safe version that prevents Arrow errors"""
            try:
                if not isinstance(data, pd.DataFrame):
                    data = pd.DataFrame(data)
                
                for col in data.columns:
                    data[col] = data[col].astype(str)
                
                return st._original_dataframe(data, **kwargs)
            except Exception:
                st.write("**Datos (modo seguro):**")
                for _, row in data.iterrows():
                    st.write(" | ".join([f"**{k}**: {v}" for k, v in row.items()]))
        
        if not hasattr(st, '_original_dataframe'):
            st._original_dataframe = st.dataframe
            st.dataframe = safe_dataframe

# === CONFIGURATION MANAGER ===

class ConfigManager:
    """Handles configuration loading and saving"""
    
    def __init__(self, config_file: str = "config.ini"):
        self.config_file = Path(config_file)
        self.logger = logging.getLogger("ConfigManager")
    
    def load_config(self):
        """Load configuration from config.ini - EXACT COPY from working version"""
        from core.interfaces import TradingConfig
        
        self.logger.info("Loading configuration...")
        config = configparser.ConfigParser()
        
        if self.config_file.exists():
            config.read(self.config_file)
            self.logger.info(f"Configuration loaded from: {self.config_file}")
        else:
            self.logger.warning(f"No config.ini found at {self.config_file}")
            config = configparser.ConfigParser()
        
        try:
            self.logger.info("Creating TradingConfig...")
            trading_config = TradingConfig(
                max_positions=config.getint('TRADING', 'max_positions', fallback=5),
                max_risk_per_trade=config.getfloat('TRADING', 'max_risk_per_trade', fallback=0.02),
                max_daily_loss=config.getfloat('TRADING', 'max_daily_loss', fallback=-500.0),
                max_daily_trades=config.getint('TRADING', 'max_daily_trades', fallback=20),
                enable_filters=config.getboolean('TRADING', 'use_volume_filter', fallback=True),
                portfolio_capital=config.getfloat('TRADING', 'portfolio_capital', fallback=2000.0),
                
                broker_host=config.get('IBKR', 'host', fallback='127.0.0.1'),
                broker_port=config.getint('IBKR', 'port', fallback=7497),
                broker_client_id=config.getint('IBKR', 'client_id', fallback=1),
                
                strategy_name=config.get('TRADING', 'strategy', fallback='macdv'),
                timeframe=config.get('TRADING', 'timeframe', fallback='1 min'),
                
                log_level=config.get('LOGGING', 'level', fallback='INFO'),
                log_file=config.get('LOGGING', 'file', fallback='trading_system.log')
            )
            
            # Add additional attributes
            self._add_additional_attributes(trading_config, config)
            return trading_config
            
        except Exception as e:
            self.logger.error(f"Error creating TradingConfig: {e}")
            return self._create_fallback_config()
    
    def _add_additional_attributes(self, trading_config, config):
        """Add additional attributes to trading config"""
        trading_config.min_volume_avg = config.getint('VOLUME_FILTERS', 'min_volume_avg', fallback=50000)
        trading_config.min_volume_current = config.getint('VOLUME_FILTERS', 'min_volume_current', fallback=25000)
        # Use GLOBAL values as primary source, VOLUME_FILTERS as fallback
        global_min_price = config.getfloat('GLOBAL', 'min_price', fallback=1.0)
        global_max_price = config.getfloat('GLOBAL', 'max_price', fallback=25.0)
        
        trading_config.min_price = config.getfloat('VOLUME_FILTERS', 'min_price', fallback=global_min_price)
        trading_config.max_price = config.getfloat('VOLUME_FILTERS', 'max_price', fallback=global_max_price)
        trading_config.volume_spike_threshold = config.getfloat('VOLUME_FILTERS', 'volume_spike_threshold', fallback=1.5)
        trading_config.volume_period = config.getint('VOLUME_FILTERS', 'volume_period', fallback=20)
        trading_config.close_positions_on_stop = config.getboolean('TRADING', 'close_positions_on_stop', fallback=False)
        
        trading_config.max_portfolio_concentration = config.getfloat('RISK', 'max_portfolio_concentration', fallback=0.8)
        trading_config.max_portfolio_exposure = config.getfloat('RISK', 'max_portfolio_exposure', fallback=1200.0)
        trading_config.max_portfolio_volatility = config.getfloat('RISK', 'max_portfolio_volatility', fallback=0.50)
        trading_config.max_position_value = config.getfloat('RISK', 'max_position_value', fallback=1000.0)
        
        # Add active_profile to TradingConfig
        trading_config.active_profile = config.get('TRADING', 'active_profile', fallback='TESTING')
    
    def _create_fallback_config(self):
        """Create fallback configuration"""
        from core.interfaces import TradingConfig
        self.logger.info("Creating fallback TradingConfig...")
        return TradingConfig()
    
    def save_config(self, config):
        """Save configuration to config.ini"""
        ini_config = configparser.ConfigParser()
        
        if self.config_file.exists():
            ini_config.read(self.config_file)
        
        sections_to_update = {
            'TRADING': {
                'strategy': config.strategy_name,
                'max_positions': str(config.max_positions),
                'max_daily_trades': str(config.max_daily_trades),
                'max_daily_loss': str(config.max_daily_loss),
                'max_risk_per_trade': str(config.max_risk_per_trade),
                'use_volume_filter': str(config.enable_filters).lower(),
                'timeframe': config.timeframe
            },
            'IBKR': {
                'host': config.broker_host,
                'port': str(config.broker_port),
                'client_id': str(config.broker_client_id)
            }
        }
        
        for section_name, section_data in sections_to_update.items():
            if not ini_config.has_section(section_name):
                ini_config.add_section(section_name)
            
            for key, value in section_data.items():
                ini_config.set(section_name, key, value)
        
        with open(self.config_file, 'w') as f:
            ini_config.write(f)
        
        self.logger.info("Configuration saved to config.ini")

# === TRADING SYSTEM MANAGER ===

class TradingSystemController:
    """Controls trading system operations"""
    
    def __init__(self):
        self.logger = logging.getLogger("TradingSystemController")
    
    def register_strategies(self):
        """Register all available strategies"""
        try:
            from strategies import register_strategy
            from strategies.macdv_strategy import MACDVStrategy
            from strategies.gap_go_strategy import GapGoStrategy
            from strategies.orb_strategy import ORBStrategy
            from strategies.volume_momentum_strategy import VolumeMomentumStrategy
            from strategies.optimized_gap_go_strategy import OptimizedGapGoStrategy
            from strategies.volume_breakout_strategy import VolumeBreakoutStrategy
            from strategies.vwap_strategy import VWAPSmallcapsStrategy
            
            register_strategy('macdv', MACDVStrategy)
            register_strategy('volume_breakout', VolumeBreakoutStrategy)
            register_strategy('vwap_smallcaps', VWAPSmallcapsStrategy)
            register_strategy('gap_go', GapGoStrategy)
            register_strategy('optimized_gap_go', OptimizedGapGoStrategy)
            register_strategy('orb', ORBStrategy)
            register_strategy('volume_momentum', VolumeMomentumStrategy)
            
            self.logger.info("All strategies registered successfully")
        except Exception as e:
            self.logger.error(f"Error registering strategies: {e}")
    
    def start_system(self, config, symbols=None):
        """Start trading system - EXACT COPY from working version"""
        if st.session_state.system_running:
            st.error("El sistema ya está en ejecución")
            return False
        
        try:
            self.register_strategies()
            
            # Generate random client ID
            config.broker_client_id = random.randint(100, 9999)
            
            # Create trading system
            from main import TradingSystemManager
            st.session_state.trading_system = TradingSystemManager(config, in_streamlit=True)
            
            # Start in separate thread
            st.session_state.system_thread = Thread(
                target=self._run_system_async, 
                args=(st.session_state.trading_system, symbols)
            )
            st.session_state.system_thread.daemon = True
            st.session_state.system_thread.start()
            
            st.session_state.system_running = True
            self.logger.info(f"System started with client_id: {config.broker_client_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting system: {e}")
            st.error(f"Error starting system: {e}")
            return False
    
    def _run_system_async(self, system, symbols=None):
        """Run system asynchronously - EXACT COPY from working version"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(system.initialize())
            loop.run_until_complete(system.start(symbols))
            
        except Exception as e:
            self.logger.error(f"Error in trading system: {e}")
        finally:
            st.session_state.system_running = False
            loop.close()
    
    def stop_system(self):
        """Stop trading system"""
        if st.session_state.trading_system and st.session_state.system_running:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                loop.run_until_complete(st.session_state.trading_system.stop())
                loop.close()
                
                st.session_state.system_running = False
                self.logger.info("System stopped successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Error stopping system: {e}")
                return False
        
        return True
    
    def add_symbol(self, symbol):
        """Add symbol to system with duplicate checking"""
        # Check for duplicates first
        current_symbols = st.session_state.get('manual_symbols', [])
        if symbol in current_symbols:
            self.logger.info(f"Symbol {symbol} already exists in manual symbols list")
            return False  # Don't add duplicates
            
        # Add to UI state
        st.session_state.manual_symbols.append(symbol)
        save_manual_symbols()  # Persist changes
        
        if not st.session_state.trading_system or not st.session_state.system_running:
            return True
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                st.session_state.trading_system.add_symbol(symbol, skip_validation=False)
            )
            
            if not result:
                result = loop.run_until_complete(
                    st.session_state.trading_system.add_symbol(symbol, skip_validation=True)
                )
            
            loop.close()
            
            # If adding to trading system failed, remove from UI state
            if not result:
                st.session_state.manual_symbols.remove(symbol)
                save_manual_symbols()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error adding symbol {symbol}: {e}")
            # Remove from UI state if there was an error
            if symbol in st.session_state.manual_symbols:
                st.session_state.manual_symbols.remove(symbol)
                save_manual_symbols()
            return False
    
    def remove_symbol(self, symbol):
        """Remove symbol from system"""
        if symbol in st.session_state.manual_symbols:
            st.session_state.manual_symbols.remove(symbol)
            save_manual_symbols()  # Persist changes
        
        if st.session_state.trading_system and st.session_state.system_running:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(st.session_state.trading_system.remove_symbol(symbol))
                loop.close()
                return True
            except Exception as e:
                self.logger.error(f"Error removing symbol {symbol}: {e}")
                return False
        
        return True

# === DATA MANAGER ===

class DataManager:
    """Handles data updates and status"""
    
    def __init__(self):
        self.logger = logging.getLogger("DataManager")
    
    def update_system_data(self):
        """Update system data with enhanced debugging"""
        if st.session_state.trading_system and st.session_state.system_running:
            try:
                status = st.session_state.trading_system.get_status()
                positions = status.get('positions', {})
                
                # Debug logging (only when needed)
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"🔍 Status keys: {status.keys()}")
                    self.logger.debug(f"🔍 Positions type: {type(positions)}")
                    self.logger.debug(f"🔍 Positions content: {positions}")
                
                st.session_state.positions = positions
                st.session_state.daily_stats = status.get('daily_stats', {})
                st.session_state.last_update = datetime.now()
                
                # Restore risk management for existing positions after system restart
                if positions:
                    restored_count = db_manager.restore_risk_management_for_existing_positions(positions)
                    if restored_count > 0:
                        self.logger.info(f"🔧 Restored risk management for {restored_count} positions")
                
                # Only log when there are positions or at DEBUG level
                position_count = len(st.session_state.positions)
                if position_count > 0:
                    self.logger.info(f"Data updated: {position_count} positions")
                elif self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"Data updated: {position_count} positions")
                
            except Exception as e:
                self.logger.error(f"Error updating system data: {e}")
    
    def get_connection_status(self, config):
        """Get connection status"""
        if not st.session_state.trading_system or not st.session_state.system_running:
            return {
                'ibkr_connected': False,
                'system_running': False,
                'positions_count': 0,
                'last_update': 'N/A'
            }
        
        try:
            ibkr_connected = False
            if hasattr(st.session_state.trading_system, 'broker') and st.session_state.trading_system.broker:
                ibkr_connected = st.session_state.trading_system.broker.is_connected()
            
            status = st.session_state.trading_system.get_status()
            
            return {
                'ibkr_connected': ibkr_connected,
                'system_running': st.session_state.system_running,
                'positions_count': len(status.get('positions', {})),
                'monitored_symbols': len(status.get('monitored_symbols', set())),
                'last_update': st.session_state.get('last_update', datetime.now()).strftime('%H:%M:%S')
            }
        except Exception as e:
            self.logger.error(f"Error getting connection status: {e}")
            return {
                'ibkr_connected': False,
                'system_running': st.session_state.system_running,
                'positions_count': 0,
                'last_update': 'Error'
            }

# === INITIALIZE COMPONENTS ===

# Setup
logger = StreamlitConfig.setup_logging()
StreamlitConfig.setup_page()

# Custom CSS to reduce margins and padding
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    .main .block-container {
        max-width: 100%;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    h1 {
        margin-top: 0rem !important;
        margin-bottom: 0.5rem !important;
    }
</style>
""", unsafe_allow_html=True)
# StreamlitConfig.setup_auto_refresh()  # DISABLED: Moved to specific tabs to avoid scanner refresh issues
StreamlitConfig.setup_safe_dataframe()

# Add cleanup handler
def cleanup_handler():
    """Cleanup graceful del sistema"""
    try:
        if 'trading_system' in st.session_state and st.session_state.trading_system:
            asyncio.run(st.session_state.trading_system.stop())
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

atexit.register(cleanup_handler)

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import trading system components
try:
    from core.interfaces import TradingConfig
    from main import TradingSystemManager
    from strategies import list_strategies
    from core.database_manager import get_database_manager
except ImportError as e:
    st.error(f"Error importing trading system components: {e}")
    st.stop()

# Initialize managers
config_manager = ConfigManager()
trading_controller = TradingSystemController()
data_manager = DataManager()
db_manager = get_database_manager()

def save_manual_symbols():
    """Save manual symbols to database"""
    try:
        db_manager.set_manual_symbols(st.session_state.manual_symbols)
    except Exception as e:
        st.error(f"Error guardando símbolos: {e}")

# Initialize session state
if 'manual_symbols' not in st.session_state:
    # Load manual symbols from database
    try:
        saved_symbols = db_manager.get_manual_symbols()
        st.session_state.manual_symbols = saved_symbols
    except Exception as e:
        st.session_state.manual_symbols = []
if 'system_config' not in st.session_state:
    st.session_state.system_config = None
if 'trading_system' not in st.session_state:
    st.session_state.trading_system = None
if 'system_thread' not in st.session_state:
    st.session_state.system_thread = None
if 'system_running' not in st.session_state:
    st.session_state.system_running = False
if 'positions' not in st.session_state:
    st.session_state.positions = {}
if 'daily_stats' not in st.session_state:
    st.session_state.daily_stats = {}
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()

# === MAIN APP ===

st.title("📊 Trading Dashboard")

# Load configuration
try:
    if st.session_state.system_config is None:
        st.session_state.system_config = config_manager.load_config()
    config = st.session_state.system_config
except Exception as e:
    st.error(f"Error loading configuration: {e}")
    st.stop()

# === SIDEBAR DESIGN ===

# App branding at top
st.sidebar.markdown("""
<div style="text-align: center; padding: 0.6rem 0; margin-bottom: 1rem; border-bottom: 2px solid #f0f2f6;">
    <h3 style="margin: 0.2rem 0;">Trading System</h3>
    <p style="color: #888; font-size: 0.8rem; margin: 0;">V3.0 Professional</p>
</div>
""", unsafe_allow_html=True)

# System Status Card - Most Important
st.sidebar.markdown("### 🔋 Estado del Sistema")
status_container = st.sidebar.container()
with status_container:
    # Operating Mode Indicator (smaller, at top)
    active_profile = getattr(config, 'active_profile', 'TESTING')
    if active_profile.upper() == 'PRODUCTION':
        profile_emoji = "🚨"
        profile_text = "PRODUCTION"
        profile_color = "#ffe6e6"
        text_color = "#cc0000"  # Dark red text
    else:
        profile_emoji = "🧪"
        profile_text = "TESTING" 
        profile_color = "#e6f3ff"
        text_color = "#0066cc"  # Dark blue text
    
    st.markdown(f"""
    <div style="background-color: {profile_color}; padding: 0.3rem; border-radius: 0.3rem; margin-bottom: 0.5rem; text-align: center; color: {text_color};">
        <small>{profile_emoji} <strong>Modo: {profile_text}</strong></small>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    # Connection status
    connection_status = data_manager.get_connection_status(config)
    
    with col1:
        if connection_status['ibkr_connected']:
            st.success("🟢 IBKR")
        else:
            st.error("🔴 IBKR")
    
    with col2:
        if st.session_state.system_running:
            st.success("🟢 Active")
        else:
            st.error("🔴 Stopped")
    
    # Quick metrics when running
    if st.session_state.system_running:
        positions_count = len(st.session_state.get('positions', {}))
        symbols_count = len(st.session_state.manual_symbols)
        
        # Get active profile for detailed info
        active_profile = getattr(config, 'active_profile', 'TESTING')
        if active_profile.upper() == 'PRODUCTION':
            profile_emoji = "🚨"
            profile_color = "#ffe6e6"
            text_color = "#cc0000"  # Dark red text
        else:
            profile_emoji = "🧪"
            profile_color = "#e6f3ff"
            text_color = "#0066cc"  # Dark blue text
        
        st.sidebar.markdown(f"""
        <div style="background-color: {profile_color}; padding: 0.5rem; border-radius: 0.3rem; margin: 0.5rem 0; color: {text_color};">
            <small>
                📊 <strong>{positions_count}</strong> posiciones activas<br>
                📈 <strong>{symbols_count}</strong> símbolos monitoreados<br>
                {profile_emoji} <strong>Modo:</strong> {active_profile.upper()}
            </small>
        </div>
        """, unsafe_allow_html=True)

st.sidebar.markdown("---")

# Strategy Configuration - Collapsed by default
with st.sidebar.expander("📈 Estrategia de Trading", expanded=False):
    try:
        available_strategies = list_strategies()
        default_index = 0
        if config.strategy_name in available_strategies:
            default_index = available_strategies.index(config.strategy_name)

        selected_strategy = st.selectbox(
            "Seleccionar estrategia",
            options=available_strategies,
            index=default_index,
            help=f"Actual: {config.strategy_name}",
            key="strategy_selector"
        )
        
        # Show strategy info
        st.info(f"🎯 Estrategia activa: **{config.strategy_name.upper()}**")
        
    except Exception as e:
        st.error("❌ Error cargando estrategias")
        available_strategies = ['macdv', 'gap_go', 'multi_strategy', 'ml_multi_strategy']
        selected_strategy = st.selectbox(
            "Seleccionar estrategia",
            options=available_strategies,
            index=0,
            key="strategy_selector_fallback"
        )

    # Update strategy if changed
    if selected_strategy != config.strategy_name:
        config.strategy_name = selected_strategy
        config_manager.save_config(config)
        st.success(f"✅ Actualizada: {selected_strategy.upper()}")

# Risk Management - Collapsed by default  
with st.sidebar.expander("⚖️ Gestión de Riesgo", expanded=False):
    new_max_positions = st.slider(
        "Máximo posiciones",
        min_value=1, max_value=10, 
        value=config.max_positions,
        help="Número máximo de posiciones simultáneas"
    )

    new_max_daily_loss = st.number_input(
        "Pérdida máxima diaria ($)",
        min_value=-2000.0, max_value=-50.0, 
        value=config.max_daily_loss, 
        step=50.0,
        help="Límite de pérdida por día de trading"
    )
    
    # Show current risk metrics
    st.info(f"📊 Límites actuales:\n- **{config.max_positions}** posiciones máx\n- **${config.max_daily_loss}** pérdida máx")

    # Update config if changed
    config_changed = False
    if new_max_positions != config.max_positions:
        config.max_positions = new_max_positions
        config_changed = True

    if new_max_daily_loss != config.max_daily_loss:
        config.max_daily_loss = new_max_daily_loss
        config_changed = True

    if config_changed:
        config_manager.save_config(config)
        st.success("✅ Configuración guardada")

# Clean up obsolete session state variables from previous scanner implementations
def cleanup_obsolete_scanner_vars():
    """Remove obsolete scanner variables from session state"""
    obsolete_vars = [
        'hybrid_scan_results', 'hybrid_scan_symbols', 'hybrid_scanner_interface',
        'tiingo_configured', 'tiingo_api_key'
    ]
    for var in obsolete_vars:
        if var in st.session_state:
            del st.session_state[var]

# Clean up on app start
cleanup_obsolete_scanner_vars()

# Main tabs - Complete trading workflow  
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Trading & Scanner", "💼 Portfolio", "📊 Analytics", "⚙️ Sistema"])

# Tab 1: Unified Trading & Scanner (Intelligent ticker discovery and management)
with tab1:
    # Enable auto-refresh for trading tab (live data needed)
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=6000, key="trading_refresh")
    except ImportError:
        pass
    except RuntimeError:
        pass
    
    # Initialize scanner intelligence
    try:
        import sys
        sys.path.append('./scanner')
        from scanner_intelligence import ScannerIntelligence, ScannerConfig, TradingResult, SentimentType
        scanner_ai = ScannerIntelligence()
        config = scanner_ai.load_config()
    except Exception as e:
        st.error(f"Error loading scanner intelligence: {e}")
        scanner_ai = None
        config = None
    
    st.header("🎯 Trading & Scanner Inteligente")
    
    # Update system data when trading tab is accessed
    if st.session_state.get('system_running', False):
        data_manager.update_system_data()
    
    # Crear layout principal: Scanner + Trading Controls
    scanner_tab, trading_tab, learning_tab = st.tabs(["🔍 Scanner Inteligente", "📈 Trading Control", "🧠 ML Learning"])
    
    # === SCANNER INTELIGENTE TAB ===
    with scanner_tab:
        col1, col2 = st.columns([2, 1])
        
        with col2:
            st.subheader("⚙️ Configuración Scanner")
            
            if config and scanner_ai:
                # Filtro de sentimiento
                sentiment_options = ["ONLY_POSITIVE", "POSITIVE_NEUTRAL"]
                sentiment_labels = ["Solo POSITIVOS", "POSITIVOS + NEUTRALES"]
                current_sentiment = config.sentiment_filter
                
                sentiment_filter = st.selectbox(
                    "Tipo de catalizadores:",
                    options=sentiment_options,
                    format_func=lambda x: sentiment_labels[sentiment_options.index(x)],
                    index=sentiment_options.index(current_sentiment),
                    help="Solo POSITIVOS = Más conservador\nPOSITIVOS + NEUTRALES = Más permisivo"
                )
                
                # Configuración avanzada
                max_float = st.number_input(
                    "Float máximo (millones)",
                    min_value=1, max_value=1000, value=int(config.max_float/1_000_000), step=10
                ) * 1_000_000
                
                min_gap = st.number_input(
                    "Gap mínimo (%)", 
                    min_value=5.0, max_value=50.0, value=config.min_gap_percent, step=2.5
                )
                
                auto_add_threshold = st.slider(
                    "ML Score para auto-add",
                    min_value=0.3, max_value=0.9, value=config.auto_add_threshold, step=0.05,
                    help="Score mínimo para añadir automáticamente al trading"
                )
                
                learning_enabled = st.checkbox(
                    "🧠 Aprendizaje automático", 
                    value=config.learning_enabled,
                    help="El sistema aprende de tus trades para mejorar"
                )
                
                # Guardar configuración
                if st.button("💾 Guardar Config"):
                    new_config = ScannerConfig(
                        sentiment_filter=sentiment_filter,
                        max_float=max_float,
                        min_gap_percent=min_gap,
                        min_volume=config.min_volume,
                        auto_add_threshold=auto_add_threshold,
                        learning_enabled=learning_enabled
                    )
                    scanner_ai.save_config(new_config)
                    st.success("✅ Configuración guardada")
                    st.rerun()
                
                # Mostrar estadísticas de aprendizaje
                if learning_enabled:
                    stats = scanner_ai.get_learning_stats()
                    st.markdown("---")
                    st.subheader("📊 Stats ML")
                    st.metric("Noticias analizadas", stats['total_news_analyzed'])
                    st.metric("Trades realizados", stats['total_trades'])
                    if stats['total_trades'] > 0:
                        st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
            else:
                st.error("❌ Sistema ML no disponible")
        
        with col1:
            st.subheader("📋 ProRealTime Scanner")
            st.markdown("Pega datos del ProScreener con análisis automático de noticias:")
            
            # Área para datos PRT
            prt_data = st.text_area(
                "Datos ProScreener",
                height=200,
                placeholder='"TICKER"\t"NAME"\t"%VAR"\t"VAR"\t"LAST"\t"TIME"\t"VOLUME"\n"ATNF"\t"180 LIFE SCIENCES"\t"+206.59%"\t"+6.90"\t"10.24"\t"07:00:33"\t"225M"',
                help="Copia y pega directamente desde ProRealTime"
            )
            
            # Procesar scanner
            if st.button("🧠 Analizar con IA", type="primary", use_container_width=True):
                if prt_data.strip() and scanner_ai:
                    st.info("🔍 Analizando tickers con IA...")
                    
                    # Extraer tickers
                    import re
                    ticker_pattern = r'"([A-Z]{2,5})"'
                    found_tickers = re.findall(ticker_pattern, prt_data)
                    
                    # Remover header si existe
                    if 'TICKER' in found_tickers:
                        found_tickers.remove('TICKER')
                    
                    unique_tickers = list(set(found_tickers))
                    
                    if unique_tickers:
                        results = []
                        auto_added = []
                        
                        # Simular análisis de noticias (en producción sería real)
                        for ticker in unique_tickers:
                            # Por ahora simulamos análisis básico
                            news_analysis = scanner_ai.analyze_ticker_news(ticker, "")
                            ml_score = scanner_ai.calculate_ml_score(ticker)
                            
                            # Auto-add si cumple criterios
                            should_add = scanner_ai.should_auto_add_ticker(ticker, config)
                            
                            results.append({
                                'Ticker': ticker,
                                'ML Score': f"{ml_score:.2f}",
                                'Sentiment': news_analysis.sentiment.value if news_analysis else 'neutral',
                                'Catalyst': news_analysis.catalyst_type.value if news_analysis else 'other',
                                'Auto-Add': '✅' if should_add else '❌'
                            })
                            
                            if should_add:
                                auto_added.append(ticker)
                        
                        # Mostrar resultados
                        st.subheader(f"📊 Análisis de {len(results)} tickers")
                        df = pd.DataFrame(results)
                        st.dataframe(df, use_container_width=True)
                        
                        # Auto-add tickers
                        if auto_added:
                            if 'manual_symbols' not in st.session_state:
                                st.session_state.manual_symbols = []
                            
                            new_symbols = [t for t in auto_added if t not in st.session_state.manual_symbols]
                            if new_symbols:
                                st.session_state.manual_symbols.extend(new_symbols)
                                st.success(f"🤖 Auto-añadidos {len(new_symbols)} tickers: {', '.join(new_symbols)}")
                        
                        # Guardar para trading tab
                        st.session_state['scanner_results'] = results
                        st.session_state['scanner_tickers'] = unique_tickers
                    else:
                        st.warning("⚠️ No se encontraron tickers válidos")
                else:
                    st.error("❌ Necesitas datos PRT y sistema ML activo")
    
    # === TRADING CONTROL TAB ===
    with trading_tab:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Show symbol count in header
            current_count = len(st.session_state.get('manual_symbols', []))
            st.subheader(f"Gestión de Símbolos ({current_count} monitoreando)")
            
            # Mostrar resultados del scanner si existen
            if st.session_state.get('scanner_results'):
                st.info("📊 Resultados del último escaneo disponibles abajo")
            
            # Add symbol form with support for multiple symbols
            with st.form("add_symbol_form"):
                new_symbols_input = st.text_input("Añadir nuevo símbolo(s)", placeholder="AAPL, MSFT, GOOGL...")
                submitted = st.form_submit_button("➕ Añadir Símbolo(s)", type="primary")
                
                if submitted and new_symbols_input.strip():
                    # Split by comma and clean each symbol
                    symbols_to_add = [s.strip().upper() for s in new_symbols_input.split(',') if s.strip()]
                    
                    if not symbols_to_add:
                        st.error("❌ No se encontraron símbolos válidos")
                    else:
                        import re
                        added_symbols = []
                        failed_symbols = []
                        duplicate_symbols = []
                        invalid_symbols = []
                        
                        for symbol in symbols_to_add:
                            # Validate symbol format
                            if not re.match(r'^[A-Z0-9\.\-]+$', symbol) or len(symbol) < 1 or len(symbol) > 8:
                                invalid_symbols.append(symbol)
                            # Check for duplicates
                            elif symbol in st.session_state.get('manual_symbols', []):
                                duplicate_symbols.append(symbol)
                            # Try to add symbol
                            else:
                                try:
                                    if 'manual_symbols' not in st.session_state:
                                        st.session_state.manual_symbols = []
                                    st.session_state.manual_symbols.append(symbol)
                                    added_symbols.append(symbol)
                                except Exception as e:
                                    failed_symbols.append(f"{symbol} ({str(e)})")
                        
                        # Show results
                        if added_symbols:
                            st.success(f"✅ Añadidos: {', '.join(added_symbols)}")
                        if duplicate_symbols:
                            st.warning(f"⚠️ Ya monitoreando: {', '.join(duplicate_symbols)}")
                        if invalid_symbols:
                            st.error(f"❌ Formato inválido: {', '.join(invalid_symbols)}")
                        if failed_symbols:
                            st.error(f"❌ Error: {', '.join(failed_symbols)}")
            
            # Current symbols list with management
            if st.session_state.get('manual_symbols'):
                st.subheader("📋 Símbolos Actuales")
                
                # Create DataFrame for better display
                symbols_data = []
                for symbol in st.session_state.manual_symbols:
                    # Get ML score if available
                    ml_score = scanner_ai.calculate_ml_score(symbol) if scanner_ai else 0.0
                    symbols_data.append({
                        'Símbolo': symbol,
                        'ML Score': f"{ml_score:.2f}",
                        'Estado': '🟢 Activo'
                    })
                
                df_symbols = pd.DataFrame(symbols_data)
                st.dataframe(df_symbols, use_container_width=True, hide_index=True)
                
                # Bulk actions
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("🗑️ Limpiar Todo"):
                        st.session_state.manual_symbols = []
                        st.success("🗑️ Lista limpiada")
                        st.rerun()
                
                with col_b:
                    # Copy symbols button
                    if st.button("📋 Copiar Lista"):
                        symbols_text = ", ".join(st.session_state.manual_symbols)
                        st.text_area(
                            f"📋 Lista de {len(st.session_state.manual_symbols)} símbolos:",
                            value=symbols_text,
                            height=100,
                            key="symbols_copy_area"
                        )
                        st.info("💡 Ctrl+A para seleccionar todo, Ctrl+C para copiar")
                
                with col_c:
                    # Remove specific symbols
                    symbol_to_remove = st.selectbox(
                        "Eliminar símbolo:",
                        options=["Seleccionar..."] + st.session_state.manual_symbols,
                        key="remove_symbol_select"
                    )
                    if symbol_to_remove != "Seleccionar..." and st.button("❌ Eliminar"):
                        st.session_state.manual_symbols.remove(symbol_to_remove)
                        st.success(f"❌ Eliminado: {symbol_to_remove}")
                        st.rerun()
            
            # Show scanner results if available
            if st.session_state.get('scanner_results'):
                st.markdown("---")
                st.subheader("🔍 Últimos Resultados del Scanner")
                scanner_df = pd.DataFrame(st.session_state['scanner_results'])
                st.dataframe(scanner_df, use_container_width=True, hide_index=True)
                
                # Quick add from scanner results
                available_tickers = [r['Ticker'] for r in st.session_state['scanner_results'] 
                                   if r['Ticker'] not in st.session_state.get('manual_symbols', [])]
                
                if available_tickers:
                    selected_from_scanner = st.multiselect(
                        "Añadir desde scanner:",
                        options=available_tickers,
                        help="Selecciona tickers del scanner para añadir a trading"
                    )
                    
                    if st.button("➕ Añadir Seleccionados") and selected_from_scanner:
                        if 'manual_symbols' not in st.session_state:
                            st.session_state.manual_symbols = []
                        st.session_state.manual_symbols.extend(selected_from_scanner)
                        st.success(f"✅ Añadidos: {', '.join(selected_from_scanner)}")
                        st.rerun()
        
        with col2:
            st.subheader("🎛️ Control del Sistema")
            
            # System status
            system_running = st.session_state.get('system_running', False)
            if system_running:
                st.success("🟢 Sistema ACTIVO")
            else:
                st.error("🔴 Sistema INACTIVO")
            
            # Quick system controls
            if not system_running:
                if st.button("▶️ Iniciar Sistema", type="primary"):
                    symbols = st.session_state.get('manual_symbols', [])
                    if symbols:
                        st.write(f"🔍 Iniciando con {len(symbols)} símbolos")
                        if trading_controller.start_system(config, symbols):
                            st.success("Sistema iniciado")
                            st.rerun()
                    else:
                        st.warning("⚠️ Añade símbolos antes de iniciar")
            else:
                if st.button("⏹️ Detener Sistema", type="secondary"):
                    trading_controller.stop_system()
                    st.success("Sistema detenido")
                    st.rerun()
            
            st.markdown("---")
            
            # Quick actions
            if st.button("🔄 Actualizar Datos"):
                data_manager.update_system_data()
                st.success("Datos actualizados")
            
            if st.button("🔄 Reiniciar Sistema"):
                if st.session_state.system_running:
                    trading_controller.stop_system()
                st.session_state.clear()
                st.success("✅ Sistema reiniciado")
                st.rerun()
    
    # === ML LEARNING TAB ===
    with learning_tab:
        if scanner_ai:
            st.subheader("🧠 Machine Learning & Feedback")
            
            # Learning stats
            stats = scanner_ai.get_learning_stats()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📰 Noticias Analizadas", stats['total_news_analyzed'])
            with col2:
                st.metric("📈 Trades Registrados", stats['total_trades'])
            with col3:
                if stats['total_trades'] > 0:
                    st.metric("🎯 Win Rate", f"{stats['win_rate']:.1f}%")
                else:
                    st.metric("🎯 Win Rate", "No data")
            
            # Quick feedback form
            st.subheader("📝 Feedback Rápido de Trade")
            with st.form("quick_feedback"):
                feedback_ticker = st.selectbox(
                    "Ticker",
                    options=st.session_state.get('manual_symbols', []),
                    help="Selecciona el ticker que tradeaste"
                )
                
                col_a, col_b = st.columns(2)
                with col_a:
                    entry_price = st.number_input("Precio entrada", min_value=0.01, step=0.01)
                    was_profitable = st.radio("Resultado", ["✅ Ganancia", "❌ Pérdida", "🤝 Breakeven"])
                
                with col_b:
                    exit_price = st.number_input("Precio salida", min_value=0.01, step=0.01)
                    notes = st.text_area("Notas", placeholder="¿Qué aprendiste de este trade?")
                
                if st.form_submit_button("💾 Guardar Feedback"):
                    if feedback_ticker and entry_price > 0 and exit_price > 0:
                        pnl = exit_price - entry_price
                        profitable = was_profitable == "✅ Ganancia"
                        
                        result = TradingResult(
                            ticker=feedback_ticker,
                            trade_date=date.today(),
                            entry_price=entry_price,
                            exit_price=exit_price,
                            pnl=pnl,
                            was_profitable=profitable,
                            hold_duration_minutes=None,
                            strategy_used="manual",
                            notes=notes
                        )
                        
                        scanner_ai.add_trading_result(result)
                        st.success(f"✅ Feedback guardado para {feedback_ticker}")
                        st.rerun()
                    else:
                        st.error("❌ Completa todos los campos")
            
            # Best patterns
            if stats['best_patterns']:
                st.subheader("🏆 Mejores Patrones Aprendidos")
                patterns_data = []
                for pattern_type, success_rate, confidence, sample_size in stats['best_patterns']:
                    patterns_data.append({
                        'Patrón': pattern_type.replace('_', ' ').title(),
                        'Success Rate': f"{success_rate:.1%}",
                        'Confianza': f"{confidence:.2f}",
                        'Muestras': sample_size
                    })
                
                patterns_df = pd.DataFrame(patterns_data)
                st.dataframe(patterns_df, use_container_width=True, hide_index=True)
        else:
            st.error("❌ Sistema ML no disponible")

# Tab 2: Portfolio Monitoring (Second - Monitor positions)  
with tab2:
    # Enable auto-refresh for portfolio tab (live data needed)
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=6000, key="portfolio_refresh")
    except ImportError:
        pass
    except RuntimeError:
        pass
    
    st.header("💼 Portfolio - Posiciones Actuales")
    
    # Always update positions when tab is accessed (every tab change)
    data_manager.update_system_data()
    
    # Optional: Also do periodic refresh if system is running (longer interval since tab changes are frequent)
    if st.session_state.get('system_running', False):
        import time
        current_time = time.time()
        if 'last_background_refresh' not in st.session_state:
            st.session_state.last_background_refresh = current_time
        
        # Background refresh every 30 seconds (less frequent since tab changes handle most updates)
        if current_time - st.session_state.last_background_refresh > 30:
            st.session_state.last_background_refresh = current_time
            st.rerun()  # This will trigger the tab refresh logic above
    
    positions = st.session_state.get('positions', {})
    
    if positions:
        # Calculate summary metrics first
        total_market_value = 0
        total_unrealized_pnl = 0
        winning_positions = 0
        
        for symbol, position in positions.items():
            if isinstance(position, dict):
                market_value = position.get('market_value', 0)
                unrealized_pnl = position.get('unrealized_pnl', 0)
            else:
                # Handle IBKR PortfolioItem objects with correct field names
                qty = getattr(position, 'position', getattr(position, 'quantity', 0))
                market_price = getattr(position, 'marketPrice', getattr(position, 'market_price', 0))
                market_value = getattr(position, 'marketValue', getattr(position, 'market_value', qty * market_price))
                unrealized_pnl = getattr(position, 'unrealizedPNL', getattr(position, 'unrealized_pnl', 0))
            
            total_market_value += market_value
            total_unrealized_pnl += unrealized_pnl
            if unrealized_pnl > 0:
                winning_positions += 1
        
        # Summary metrics at the top - More prominent
        st.subheader("📊 Resumen del Portfolio")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Posiciones", len(positions))
        with col2:
            st.metric("Valor Total", f"${total_market_value:.2f}")
        with col3:
            pnl_pct = (total_unrealized_pnl/total_market_value*100) if total_market_value > 0 else 0
            color = "normal" if total_unrealized_pnl >= 0 else "inverse"
            st.metric("PnL Total", f"${total_unrealized_pnl:.2f}", delta=f"{pnl_pct:.2f}%")
        with col4:
            st.metric("Posiciones Ganadoras", f"{winning_positions}/{len(positions)}")
        
        # Position details table
        def get_symbol_strategy(symbol, position):
            """Get strategy for a symbol"""
            try:
                # Try to get strategy from session state or position data
                strategies = st.session_state.get('symbol_strategies', {})
                return strategies.get(symbol, 'Manual')
            except:
                return 'Manual'
        
        positions_data = []
        for symbol, position in positions.items():
            try:
                if isinstance(position, dict):
                    # Dictionary format
                    qty = position.get('quantity', 0)
                    avg_price = position.get('avg_cost', 0)
                    market_price = position.get('market_price', 0)
                    market_value = position.get('market_value', 0)
                    unrealized_pnl = position.get('unrealized_pnl', 0)
                else:
                    # IBKR PortfolioItem object - Use proper field names
                    qty = getattr(position, 'position', getattr(position, 'quantity', 0))
                    avg_price = getattr(position, 'averageCost', getattr(position, 'avg_cost', 0))
                    market_price = getattr(position, 'marketPrice', getattr(position, 'market_price', 0))
                    market_value = getattr(position, 'marketValue', getattr(position, 'market_value', qty * market_price))
                    unrealized_pnl = getattr(position, 'unrealizedPNL', getattr(position, 'unrealized_pnl', 0))
                
                if qty == 0:  # Skip zero quantity positions
                    continue
                
                # Calculate percentage change
                if avg_price > 0:
                    pct_change = ((market_price - avg_price) / avg_price) * 100
                else:
                    pct_change = 0
                
                # Calculate stop loss and take profit (example values)
                stop_loss_price = avg_price * 0.97  # 3% stop loss
                take_profit_price = avg_price * 1.06  # 6% take profit
                
                # Check if these are manually set (would come from database/config)
                # For now, mark as calculated with asterisk
                stop_loss_info = f"${stop_loss_price:.2f}*"
                take_profit_info = f"${take_profit_price:.2f}*"
                
                # Try to get actual stop/take profit from session state or trading system
                symbol_config = st.session_state.get('symbol_configs', {}).get(symbol, {})
                if symbol_config.get('stop_loss'):
                    stop_loss_info = f"${symbol_config['stop_loss']:.2f}"
                if symbol_config.get('take_profit'):
                    take_profit_info = f"${symbol_config['take_profit']:.2f}"
                
                # If no manual config, use default calculated values with asterisk
                if not symbol_config:
                    default_stop_loss = avg_price * 0.97
                    default_take_profit = avg_price * 1.06
                    stop_loss_info = f"${default_stop_loss:.2f}*"
                    take_profit_info = f"${default_take_profit:.2f}*"
                
                positions_data.append({
                    'Símbolo': symbol,
                    'Cantidad': int(qty),
                    'Precio Entrada': f"${avg_price:.4f}",
                    'Precio Actual': f"${market_price:.4f}",
                    'Stop Loss': stop_loss_info,
                    'Take Profit': take_profit_info,
                    'Valor Mercado': f"${market_value:.2f}",
                    'PnL ($)': f"${unrealized_pnl:.2f}",
                    'PnL (%)': f"{pct_change:.2f}%",
                    'Estrategia': get_symbol_strategy(symbol, position),
                    'Estado': '🟢 Ganando' if unrealized_pnl >= 0 else '🔴 Pérdida'
                })
            except Exception as e:
                # Log error but continue processing other positions
                st.error(f"Error processing position for {symbol}: {e}")
                continue
        
        # Display table - More prominent
        st.subheader("📈 Detalle de Posiciones")
        df = pd.DataFrame(positions_data)
        # Display DataFrame with tighter column widths (pixel values) to remove horizontal scroll
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "Símbolo": st.column_config.TextColumn("Símbolo", width="60"),
                "Cantidad": st.column_config.NumberColumn("Cantidad", width="60", format="%d"),
                "Precio Entrada": st.column_config.TextColumn("Precio Entrada", width="90"),
                "Precio Actual": st.column_config.TextColumn("Precio Actual", width="90"),
                "Stop Loss": st.column_config.TextColumn("Stop Loss", width="90"),
                "Take Profit": st.column_config.TextColumn("Take Profit", width="90"),
                "Valor Mercado": st.column_config.TextColumn("Valor Mercado", width="90"),
                "PnL ($)": st.column_config.TextColumn("PnL ($)", width="70"),
                "PnL (%)": st.column_config.TextColumn("PnL (%)", width="70"),
                "Estrategia": st.column_config.TextColumn("Estrategia", width="110"),
                "Estado": st.column_config.TextColumn("Estado", width="70")
            }
        )
        
        # Explanation for asterisk values
        st.caption("💡 **Nota:** Los valores con asterisco (*) son calculados automáticamente (Stop Loss: -3%, Take Profit: +6%). Los valores sin asterisco son configurados manualmente.")
        
        # Enhanced update info with auto-refresh status
        last_update_time = st.session_state.last_update.strftime('%H:%M:%S')
        time_diff = (datetime.now() - st.session_state.last_update).total_seconds()
        
        if time_diff < 30:
            update_status = f"🟢 Actualizado hace {int(time_diff)}s"
        elif time_diff < 120:
            update_status = f"🟡 Actualizado hace {int(time_diff//60)}min {int(time_diff%60)}s"
        else:
            update_status = f"🔴 Última actualización: {last_update_time}"
        
        system_status = "🟢 Auto-refresh activo" if st.session_state.get('system_running', False) else "🔴 Sistema inactivo"
        st.caption(f"{update_status} | {system_status}")
        
    else:
        # No positions - Show cleaner message
        st.info("ℹ️ No hay posiciones activas")
        
        # Show connection status when no positions
        connection_status = data_manager.get_connection_status(config)
        
        col1, col2 = st.columns(2)
        with col1:
            if connection_status['ibkr_connected']:
                st.success("🟢 Conectado a IBKR")
            else:
                st.error("🔴 Desconectado de IBKR")
        
        with col2:
            if connection_status['system_running']:
                st.success("🟢 Sistema Activo")
            else:
                st.error("🔴 Sistema Inactivo")

# Tab 3: Analytics - Trading Performance & History
with tab3:
    # Enable auto-refresh for analytics tab (live data needed)
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=6000, key="analytics_refresh")
    except ImportError:
        pass
    except RuntimeError:
        pass
    
    st.header("📊 Analytics - Performance & Historial")
    
    # Update system data when analytics tab is accessed
    if st.session_state.get('system_running', False):
        data_manager.update_system_data()
    
    # Analytics tabs
    analytics_tab1, analytics_tab2, analytics_tab3 = st.tabs(["📈 Performance", "📋 Trades History", "📝 Journal"])
    
    with analytics_tab1:
        st.subheader("📊 Performance Overview")
        
        # Date range selector
        col1, col2 = st.columns(2)
        with col1:
            days_back = st.selectbox("Período", [7, 15, 30, 60, 90], index=2)
        with col2:
            if st.button("🔄 Actualizar Analytics"):
                st.success("Analytics actualizados")
        
        # Get today's stats
        today_stats = db_manager.calculate_daily_stats()
        
        # Display today's performance
        st.subheader("🎯 Performance de Hoy")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Trades Hoy", today_stats['total_trades'])
        with col2:
            st.metric("Win Rate", f"{today_stats['win_rate']:.1f}%")
        with col3:
            delta_color = "normal" if today_stats['total_pnl'] >= 0 else "inverse"
            st.metric("PnL Hoy", f"${today_stats['total_pnl']:.2f}")
        with col4:
            st.metric("Avg PnL/Trade", f"${today_stats['avg_pnl']:.2f}")
        
        # Strategy performance chart
        st.subheader("📈 Performance por Estrategia")
        strategy_performance = db_manager.get_strategy_performance(days_back)
        
        if not strategy_performance.empty:
            # Display as chart
            col1, col2 = st.columns(2)
            
            with col1:
                # PnL by strategy bar chart
                st.bar_chart(strategy_performance.set_index('strategy')['total_pnl'])
                st.caption("PnL Total por Estrategia")
            
            with col2:
                # Win rate by strategy
                st.bar_chart(strategy_performance.set_index('strategy')['win_rate'])
                st.caption("Win Rate por Estrategia (%)")
            
            # Detailed table
            st.subheader("📋 Detalles por Estrategia")
            strategy_performance['total_pnl'] = strategy_performance['total_pnl'].round(2)
            strategy_performance['avg_pnl'] = strategy_performance['avg_pnl'].round(2)
            strategy_performance['win_rate'] = strategy_performance['win_rate'].round(1)
            
            st.dataframe(
                strategy_performance,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "strategy": "Estrategia",
                    "total_trades": st.column_config.NumberColumn("Total Trades", format="%d"),
                    "total_pnl": st.column_config.NumberColumn("PnL Total", format="$%.2f"),
                    "avg_pnl": st.column_config.NumberColumn("PnL Promedio", format="$%.2f"),
                    "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1f%%"),
                    "profitable_trades": st.column_config.NumberColumn("Trades Ganadores", format="%d")
                }
            )
        else:
            st.info("ℹ️ No hay datos de performance para mostrar")
    
    with analytics_tab2:
        st.subheader("📋 Historial de Trades")
        
        # Date range filter
        col1, col2, col3 = st.columns(3)
        with col1:
            show_days = st.selectbox("Mostrar últimos:", [1, 7, 15, 30], index=1, key="history_days")
        with col2:
            strategy_filter = st.selectbox("Filtrar por estrategia:", ["Todas"] + ["MACDV", "VolumeBreakout", "Manual"], key="strategy_filter")
        with col3:
            if st.button("🔄 Actualizar Historial"):
                st.success("Historial actualizado")
        
        # Get recent trades
        recent_trades = db_manager.get_recent_trades(days=show_days)
        
        if strategy_filter != "Todas":
            recent_trades = recent_trades[recent_trades['strategy'] == strategy_filter]
        
        if not recent_trades.empty:
            # Format the DataFrame for better display
            display_trades = recent_trades.copy()
            display_trades['entry_time'] = pd.to_datetime(display_trades['entry_time']).dt.strftime('%m/%d %H:%M')
            display_trades['exit_time'] = pd.to_datetime(display_trades['exit_time']).dt.strftime('%m/%d %H:%M')
            display_trades['pnl'] = display_trades['pnl'].round(2)
            display_trades['entry_price'] = display_trades['entry_price'].round(4)
            display_trades['exit_price'] = display_trades['exit_price'].round(4)
            
            # Add status column
            display_trades['status_icon'] = display_trades['pnl'].apply(lambda x: '🟢' if x > 0 else '🔴' if x < 0 else '🟡')
            
            st.dataframe(
                display_trades[['entry_time', 'symbol', 'strategy', 'entry_price', 'exit_price', 'pnl', 'status_icon']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "entry_time": "Entrada",
                    "symbol": "Símbolo", 
                    "strategy": "Estrategia",
                    "entry_price": st.column_config.NumberColumn("Precio Entrada", format="$%.4f"),
                    "exit_price": st.column_config.NumberColumn("Precio Salida", format="$%.4f"),
                    "pnl": st.column_config.NumberColumn("PnL", format="$%.2f"),
                    "status_icon": "Estado"
                }
            )
            
            # Summary stats
            total_pnl = display_trades['pnl'].sum()
            win_rate = (display_trades['pnl'] > 0).mean() * 100
            avg_winner = display_trades[display_trades['pnl'] > 0]['pnl'].mean() if (display_trades['pnl'] > 0).any() else 0
            avg_loser = display_trades[display_trades['pnl'] < 0]['pnl'].mean() if (display_trades['pnl'] < 0).any() else 0
            
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Trades", len(display_trades))
            with col2:
                st.metric("PnL Total", f"${total_pnl:.2f}")
            with col3:
                st.metric("Win Rate", f"{win_rate:.1f}%")
            with col4:
                profit_factor = abs(avg_winner / avg_loser) if avg_loser != 0 else float('inf')
                st.metric("Profit Factor", f"{profit_factor:.2f}")
        else:
            st.info("ℹ️ No hay trades recientes para mostrar")
    
    with analytics_tab3:
        st.subheader("📝 Trading Journal")
        
        # Simple journal entry form
        st.markdown("Registra observaciones, lecciones aprendidas y notas importantes:")
        
        with st.form("journal_entry"):
            col1, col2 = st.columns(2)
            with col1:
                entry_date = st.date_input("Fecha", datetime.now().date())
                entry_type = st.selectbox("Tipo", ["Trade Note", "Market Observation", "Strategy Insight", "Lesson Learned"])
            
            with col2:
                related_symbol = st.text_input("Símbolo relacionado (opcional)", placeholder="AAPL")
                tags = st.text_input("Tags", placeholder="breakout, volume, fomo")
            
            content = st.text_area("Contenido", height=150, placeholder="Describe lo que observaste, aprendiste o quieres recordar...")
            
            if st.form_submit_button("💾 Guardar Entrada"):
                if content.strip():
                    # In a real implementation, this would save to database
                    entry_data = {
                        'date': entry_date,
                        'type': entry_type,
                        'symbol': related_symbol if related_symbol else None,
                        'tags': tags if tags else None,
                        'content': content
                    }
                    
                    # Store in session state for now (in production, use database)
                    if 'journal_entries' not in st.session_state:
                        st.session_state.journal_entries = []
                    
                    st.session_state.journal_entries.append(entry_data)
                    st.success("✅ Entrada guardada en el journal")
                    st.rerun()
                else:
                    st.error("❌ El contenido no puede estar vacío")
        
        # Display recent journal entries
        st.markdown("---")
        st.subheader("📖 Entradas Recientes")
        
        if st.session_state.get('journal_entries'):
            for i, entry in enumerate(reversed(st.session_state.journal_entries[-10:])):  # Last 10 entries
                with st.expander(f"{entry['type']} - {entry['date']}"):
                    if entry.get('symbol'):
                        st.badge(entry['symbol'], type="secondary")
                    if entry.get('tags'):
                        for tag in entry['tags'].split(','):
                            st.badge(tag.strip(), type="outline")
                    st.write(entry['content'])
        else:
            st.info("ℹ️ No hay entradas de journal. ¡Empieza escribiendo tu primera entrada!")

# Tab 4: Sistema  
with tab4:
    st.header("Información del Sistema")
    
    # Update system data when system tab is accessed
    if st.session_state.get('system_running', False):
        data_manager.update_system_data()
    
    # Connection status
    st.subheader("Estado de Conexiones")
    connection_status = data_manager.get_connection_status(config)
                        elif symbol in st.session_state.get('manual_symbols', []):
                            duplicate_symbols.append(symbol)
                        # Try to add symbol
                        else:
                            if trading_controller.add_symbol(symbol):
                                added_symbols.append(symbol)
                            else:
                                failed_symbols.append(symbol)
                    
                    # Show results
                    if added_symbols:
                        st.success(f"✅ Símbolos añadidos: {', '.join(added_symbols)}")
                    if duplicate_symbols:
                        st.warning(f"⚠️ Símbolos ya existentes: {', '.join(duplicate_symbols)}")
                    if invalid_symbols:
                        st.error(f"❌ Símbolos con formato inválido: {', '.join(invalid_symbols)}")
                    if failed_symbols:
                        st.error(f"❌ Error añadiendo símbolos: {', '.join(failed_symbols)}")
                    
                    if added_symbols:
                        st.rerun()  # Force UI refresh to show new symbols
        
        # Clear all symbols button
        if st.session_state.manual_symbols:  # Only show if there are symbols to clear
            if st.button("🗑️ Eliminar Todos los Símbolos", type="secondary", help="Eliminar todos los símbolos de la lista"):
                st.session_state.manual_symbols = []
                save_manual_symbols()
                st.success("✅ Todos los símbolos han sido eliminados")
                st.rerun()
        
        # Show current symbols in a cleaner way
        if st.session_state.manual_symbols:
            st.subheader("📈 Símbolos en Monitoreo")
            
            # Fix corrupted symbol list if needed
            fixed_symbols = []
            for item in st.session_state.manual_symbols:
                if isinstance(item, str) and ',' in item:
                    # Split comma-separated string into individual symbols
                    symbols = [s.strip().upper() for s in item.split(',') if s.strip()]
                    fixed_symbols.extend(symbols)
                else:
                    fixed_symbols.append(str(item).strip().upper())
            
            # Update session state with fixed symbols
            if fixed_symbols != st.session_state.manual_symbols:
                st.session_state.manual_symbols = list(set(fixed_symbols))  # Remove duplicates
                save_manual_symbols()  # Persist changes
                st.rerun()
            
            for symbol in st.session_state.manual_symbols:
                col_sym, col_status, col_action = st.columns([3, 3, 1])
                with col_sym:
                    st.write(f"**{symbol}**")
                with col_status:
                    status = "🟢 Activo" if st.session_state.system_running else "⏸️ En espera"
                    st.write(status)
                with col_action:
                    if st.button("🗑️", key=f"remove_{symbol}", help=f"Eliminar {symbol}"):
                        trading_controller.remove_symbol(symbol)
                        st.rerun()
        else:
            st.info("ℹ️ No hay símbolos configurados manualmente")
    
    with col2:
        st.subheader("Control del Sistema")
        
        if st.session_state.system_running:
            st.success("🟢 Sistema ACTIVO")
            if st.button("⏹️ Detener Sistema", type="secondary"):
                if trading_controller.stop_system():
                    st.success("Sistema detenido")
                    st.rerun()
        else:
            st.error("🔴 Sistema INACTIVO")  
            if st.button("▶️ Iniciar Sistema", type="primary"):
                # Get symbols from multiple sources
                all_symbols = []
                clean_symbols = []
                position_symbols = []
                
                # 1. Manual symbols from UI
                if st.session_state.manual_symbols:
                    # Clean and validate symbols before passing to system
                    for item in st.session_state.manual_symbols:
                        if isinstance(item, str):
                            # Split any comma-separated strings
                            if ',' in item:
                                sub_symbols = [s.strip().upper() for s in item.split(',') if s.strip()]
                                clean_symbols.extend(sub_symbols)
                            else:
                                clean_symbols.append(item.strip().upper())
                    all_symbols.extend(clean_symbols)
                
                # 2. Symbols from existing broker positions
                if st.session_state.positions:
                    position_symbols = [symbol.upper() for symbol in st.session_state.positions.keys()]
                    all_symbols.extend(position_symbols)
                    st.info(f"📊 Detectadas posiciones existentes: {', '.join(position_symbols)}")
                
                # 3. Remove duplicates and finalize
                symbols = list(set(all_symbols)) if all_symbols else None
                
                if symbols:
                    st.write(f"🔍 Debug - Starting system with symbols: {symbols}")
                    st.write(f"   - Manual: {len(clean_symbols)}")
                    st.write(f"   - Positions: {len(position_symbols)}")
                
                if trading_controller.start_system(config, symbols):
                    st.success("Sistema iniciado")
                    st.rerun()
        
        st.markdown("---")
        
        # Quick actions
        st.subheader("Acciones Rápidas")

        
            
        if st.button("🔄 Reiniciar Sistema (Fix Símbolos)", type="secondary"):
            # Force stop system and clear corrupted symbol data
            if st.session_state.system_running:
                trading_controller.stop_system()
            # Clean up session state
            st.session_state.clear()
            st.success("✅ Sistema reiniciado - datos de símbolos limpiados")
            st.rerun()
        
        if st.button("🔄 Actualizar Datos"):
            data_manager.update_system_data()
            st.success("Datos actualizados")
        
        # Copy symbols button in quick actions
        if st.session_state.get('manual_symbols', []):
            if st.button("📋 Mostrar Lista de Símbolos", help="Mostrar símbolos para copiar manualmente"):
                symbols_text = ", ".join(st.session_state.manual_symbols)
                
                # Show in a text area for easy selection and copy
                st.text_area(
                    f"📋 Lista de {len(st.session_state.manual_symbols)} símbolos (selecciona todo y copia):",
                    value=symbols_text,
                    height=100,
                    key="symbols_copy_area"
                )
                
                st.success("✅ Símbolos mostrados arriba - selecciona todo el texto y cópialo")
                st.info("💡 Ctrl+A para seleccionar todo, Ctrl+C para copiar")

# Tab 2: Portfolio Monitoring (Second - Monitor positions)
with tab2:
    # Enable auto-refresh for portfolio tab (live data needed)
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=6000, key="portfolio_refresh")
    except ImportError:
        pass
    except RuntimeError:
        pass
    
    st.header("💼 Portfolio - Posiciones Actuales")
    
    # Always update positions when tab is accessed (every tab change)
    data_manager.update_system_data()
    
    # Optional: Also do periodic refresh if system is running (longer interval since tab changes are frequent)
    if st.session_state.get('system_running', False):
        import time
        current_time = time.time()
        if 'last_background_refresh' not in st.session_state:
            st.session_state.last_background_refresh = current_time
        
        # Background refresh every 30 seconds (less frequent since tab changes handle most updates)
        if current_time - st.session_state.last_background_refresh > 30:
            st.session_state.last_background_refresh = current_time
            st.rerun()  # This will trigger the tab refresh logic above
    
    positions = st.session_state.get('positions', {})
    
    if positions:
        # Calculate summary metrics first
        total_market_value = 0
        total_unrealized_pnl = 0
        winning_positions = 0
        
        for symbol, position in positions.items():
            if isinstance(position, dict):
                market_value = position.get('market_value', 0)
                unrealized_pnl = position.get('unrealized_pnl', 0)
            else:
                # Handle IBKR PortfolioItem objects with correct field names
                qty = getattr(position, 'position', getattr(position, 'quantity', 0))
                market_price = getattr(position, 'marketPrice', getattr(position, 'market_price', 0))
                market_value = getattr(position, 'marketValue', getattr(position, 'market_value', qty * market_price))
                unrealized_pnl = getattr(position, 'unrealizedPNL', getattr(position, 'unrealized_pnl', 0))
            
            total_market_value += market_value
            total_unrealized_pnl += unrealized_pnl
            if unrealized_pnl > 0:
                winning_positions += 1
        
        # Summary metrics at the top - More prominent
        st.subheader("📊 Resumen del Portfolio")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Posiciones", len(positions))
        with col2:
            st.metric("Valor Total", f"${total_market_value:.2f}")
        with col3:
            pnl_pct = (total_unrealized_pnl/total_market_value*100) if total_market_value > 0 else 0
            color = "normal" if total_unrealized_pnl >= 0 else "inverse"
            st.metric("PnL Total", f"${total_unrealized_pnl:.2f}", delta=f"{pnl_pct:.2f}%")
        with col4:
            st.metric("Posiciones Ganadoras", f"{winning_positions}/{len(positions)}")
        
        st.markdown("---")  # Separator
        
        # Function to determine specific strategy used for each symbol
        def get_symbol_strategy(symbol, position_info):
            """Return strategy for symbol, preferring stored field over database lookup"""
            # First, check if position has strategy stored
            if isinstance(position_info, dict) and position_info.get('strategy'):
                return position_info['strategy']
            
            # Try to get strategy from recent trades in database
            try:
                recent_trades = db_manager.get_recent_trades(symbol=symbol, days=1)
                if not recent_trades.empty:
                    latest_strategy = recent_trades.iloc[0]['strategy']
                    if latest_strategy and latest_strategy != 'unknown':
                        strategy_display_names = {
                            'macdv': 'MACDV Smallcaps',
                            'macdv_smallcaps': 'MACDV Smallcaps',
                            'gap_go': 'Gap&Go',
                            'orb': 'ORB',
                            'volume_breakout': 'Volume Breakout',
                            'pmh_breakout': 'PMH Breakout',
                            'explosive_volume': 'Explosive Volume',
                            'volume_momentum': 'Volume Momentum',
                            'vwap_smallcaps': 'VWAP Smallcaps'
                        }
                        return strategy_display_names.get(latest_strategy, latest_strategy.title())
            except Exception:
                pass  # Fallback to manual mapping
            
            # Fallback to manual symbol mapping for known cases
            strategies_map = {
                'ORIS': 'MACDV Smallcaps',
                'BTBD': 'Gap&Go', 
                'PBM': 'ORB',
                'COMM': 'Volume Breakout',
                'BTAI': 'PMH Breakout'
            }
            
            # For current positions, try to infer strategy based on price/market characteristics
            if symbol not in strategies_map:
                try:
                    if isinstance(position_info, dict):
                        avg_price = position_info.get('avg_price', 0)
                    else:
                        avg_price = getattr(position_info, 'averageCost', 0)
                    
                    # Inference based on price ranges (rough heuristic)
                    if avg_price < 2.0:
                        return 'Smallcaps (MACDV/Explosive)'
                    elif 2.0 <= avg_price < 10.0:
                        return 'Mid-Small (Multi-Strategy)'
                    else:
                        return 'Large Cap (ORB/Gap&Go)'
                except:
                    pass
            
            return strategies_map.get(symbol, 'Multi-Strategy')
        
        # Create DataFrame for table display
        positions_data = []
        
        for symbol, position in positions.items():
            if isinstance(position, dict):
                qty = position.get('quantity', 0)
                avg_price = position.get('avg_price', 0)
                market_price = position.get('market_price', 0)
                market_value = position.get('market_value', 0)
                unrealized_pnl = position.get('unrealized_pnl', 0)
            else:
                # Handle IBKR PortfolioItem objects with correct field names
                qty = getattr(position, 'position', getattr(position, 'quantity', 0))
                avg_price = getattr(position, 'averageCost', getattr(position, 'avg_price', 0))
                market_price = getattr(position, 'marketPrice', getattr(position, 'market_price', 0))
                market_value = getattr(position, 'marketValue', getattr(position, 'market_value', qty * market_price))
                unrealized_pnl = getattr(position, 'unrealizedPNL', getattr(position, 'unrealized_pnl', 0))
            
            # Calculate percentage change
            pct_change = ((market_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            # Get risk management info
            risk_config = db_manager.get_position_risk_config(symbol)
            stop_loss_info = "N/A"
            take_profit_info = "N/A"
            
            if not risk_config.empty:
                latest_config = risk_config.iloc[0]
                if pd.notna(latest_config.get('stop_loss_price')):
                    stop_loss_info = f"${latest_config['stop_loss_price']:.2f}"
                if pd.notna(latest_config.get('take_profit_price')):
                    take_profit_info = f"${latest_config['take_profit_price']:.2f}"
            else:
                # Fallback: Calculate default stop loss/take profit based on entry price
                # Use typical smallcap percentages: 3% stop loss, 6% take profit
                default_stop_loss = avg_price * 0.97  # 3% below entry
                default_take_profit = avg_price * 1.06  # 6% above entry
                stop_loss_info = f"${default_stop_loss:.2f}*"  # * indicates calculated
                take_profit_info = f"${default_take_profit:.2f}*"
            
            positions_data.append({
                'Símbolo': symbol,
                'Cantidad': int(qty),
                'Precio Entrada': f"${avg_price:.4f}",
                'Precio Actual': f"${market_price:.4f}",
                'Stop Loss': stop_loss_info,
                'Take Profit': take_profit_info,
                'Valor Mercado': f"${market_value:.2f}",
                'PnL ($)': f"${unrealized_pnl:.2f}",
                'PnL (%)': f"{pct_change:.2f}%",
                'Estrategia': get_symbol_strategy(symbol, position),
                'Estado': '🟢 Ganando' if unrealized_pnl >= 0 else '🔴 Pérdida'
            })
        
        # Display table - More prominent
        st.subheader("📈 Detalle de Posiciones")
        df = pd.DataFrame(positions_data)
        # Display DataFrame with tighter column widths (pixel values) to remove horizontal scroll
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "Símbolo": st.column_config.TextColumn("Símbolo", width="60"),
                "Cantidad": st.column_config.NumberColumn("Cantidad", width="60", format="%d"),
                "Precio Entrada": st.column_config.TextColumn("Precio Entrada", width="90"),
                "Precio Actual": st.column_config.TextColumn("Precio Actual", width="90"),
                "Stop Loss": st.column_config.TextColumn("Stop Loss", width="90"),
                "Take Profit": st.column_config.TextColumn("Take Profit", width="90"),
                "Valor Mercado": st.column_config.TextColumn("Valor Mercado", width="90"),
                "PnL ($)": st.column_config.TextColumn("PnL ($)", width="70"),
                "PnL (%)": st.column_config.TextColumn("PnL (%)", width="70"),
                "Estrategia": st.column_config.TextColumn("Estrategia", width="110"),
                "Estado": st.column_config.TextColumn("Estado", width="70")
            }
        )
        
        # Explanation for asterisk values
        st.caption("💡 **Nota:** Los valores con asterisco (*) son calculados automáticamente (Stop Loss: -3%, Take Profit: +6%). Los valores sin asterisco son configurados manualmente.")
        
        # Enhanced update info with auto-refresh status
        last_update_time = st.session_state.last_update.strftime('%H:%M:%S')
        time_diff = (datetime.now() - st.session_state.last_update).total_seconds()
        
        if time_diff < 30:
            update_status = f"🟢 Actualizado hace {int(time_diff)}s"
        elif time_diff < 120:
            update_status = f"🟡 Actualizado hace {int(time_diff//60)}min {int(time_diff%60)}s"
        else:
            update_status = f"🔴 Última actualización: {last_update_time}"
        
        system_status = "🟢 Auto-refresh activo" if st.session_state.get('system_running', False) else "🔴 Sistema inactivo"
        st.caption(f"{update_status} | {system_status}")
        
    else:
        # No positions - Show cleaner message
        st.info("ℹ️ No hay posiciones activas")
        
        # Show connection status when no positions
        connection_status = data_manager.get_connection_status(config)
        
        col1, col2 = st.columns(2)
        with col1:
            if connection_status['ibkr_connected']:
                st.success("🟢 Conectado a IBKR")
            else:
                st.error("🔴 Desconectado de IBKR")
        
        with col2:
            if connection_status['system_running']:
                st.success("🟢 Sistema Activo")
            else:
                st.error("🔴 Sistema Inactivo")

# Tab 3: Analytics - Trading Performance & History
with tab3:
    # Enable auto-refresh for analytics tab (live data needed)
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=6000, key="analytics_refresh")
    except ImportError:
        pass
    except RuntimeError:
        pass
    
    st.header("📊 Analytics - Performance & Historial")
    
    # Update system data when analytics tab is accessed
    if st.session_state.get('system_running', False):
        data_manager.update_system_data()
    
    # Analytics tabs
    analytics_tab1, analytics_tab2, analytics_tab3 = st.tabs(["📈 Performance", "📋 Trades History", "📝 Journal"])
    
    with analytics_tab1:
        st.subheader("📊 Performance Overview")
        
        # Date range selector
        col1, col2 = st.columns(2)
        with col1:
            days_back = st.selectbox("Período", [7, 15, 30, 60, 90], index=2)
        with col2:
            if st.button("🔄 Actualizar Analytics"):
                st.success("Analytics actualizados")
        
        # Get today's stats
        today_stats = db_manager.calculate_daily_stats()
        
        # Display today's performance
        st.subheader("🎯 Performance de Hoy")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Trades Hoy", today_stats['total_trades'])
        with col2:
            st.metric("Win Rate", f"{today_stats['win_rate']:.1f}%")
        with col3:
            delta_color = "normal" if today_stats['total_pnl'] >= 0 else "inverse"
            st.metric("PnL Hoy", f"${today_stats['total_pnl']:.2f}")
        with col4:
            if today_stats['total_trades'] > 0:
                st.metric("Avg PnL/Trade", f"${today_stats['total_pnl']/today_stats['total_trades']:.2f}")
            else:
                st.metric("Avg PnL/Trade", "$0.00")
        
        st.markdown("---")
        
        # Strategy performance
        st.subheader("🎯 Performance por Estrategia")
        strategy_perf = db_manager.get_strategy_performance(days=days_back)
        
        if not strategy_perf.empty:
            st.dataframe(
                strategy_perf,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "strategy": st.column_config.TextColumn("Estrategia", width="medium"),
                    "total_trades": st.column_config.NumberColumn("Trades", width="small"),
                    "win_rate": st.column_config.NumberColumn("Win Rate (%)", width="small"),
                    "total_pnl": st.column_config.NumberColumn("PnL Total ($)", width="medium"),
                    "avg_pnl": st.column_config.NumberColumn("PnL Promedio ($)", width="medium"),
                    "best_trade": st.column_config.NumberColumn("Mejor Trade ($)", width="medium"),
                    "worst_trade": st.column_config.NumberColumn("Peor Trade ($)", width="medium")
                }
            )
        else:
            st.info("ℹ️ No hay datos de estrategias para el período seleccionado")
    
    with analytics_tab2:
        st.subheader("📋 Historial de Trades")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_symbol = st.selectbox("Filtrar por Símbolo", ["Todos"] + list(st.session_state.get('positions', {}).keys()))
        with col2:
            filter_strategy = st.selectbox("Filtrar por Estrategia", 
                                         ["Todas", "MACDV Smallcaps", "Gap&Go", "ORB", "Volume Breakout", "PMH Breakout"])
        with col3:
            trades_limit = st.number_input("Número de trades", min_value=10, max_value=500, value=50)
        
        # Get trades from database
        symbol_filter = None if filter_symbol == "Todos" else filter_symbol
        strategy_filter = None if filter_strategy == "Todas" else filter_strategy
        
        trades_df = db_manager.get_trades(
            symbol=symbol_filter,
            strategy=strategy_filter,
            limit=trades_limit
        )
        
        if not trades_df.empty:
            # Format the dataframe for display
            display_df = trades_df[[
                'symbol', 'strategy', 'side', 'quantity', 'entry_price', 
                'exit_price', 'pnl', 'status', 'entry_time'
            ]].copy()
            
            # Convert numeric columns to object type to allow mixed types (numbers and None/strings)
            display_df['exit_price'] = display_df['exit_price'].astype('object')
            display_df['pnl'] = display_df['pnl'].astype('object')
            
            # Get current positions to enhance open trades
            current_positions = st.session_state.get('positions', {})
            
            # Enhance data for better display
            for idx, row in display_df.iterrows():
                symbol = row['symbol']
                
                # Fix 1: Replace unknown strategy and get specific multi-strategy info
                if pd.isna(row['strategy']) or row['strategy'] in ['unknown', None, '']:
                    if symbol in current_positions:
                        pos_strategy = current_positions[symbol].get('strategy', 'Multi-Strategy')
                        display_df.at[idx, 'strategy'] = pos_strategy if pos_strategy != 'unknown' else 'Multi-Strategy'
                    else:
                        # Try to get specific strategy from database for this trade
                        try:
                            latest_strategy = db_manager.get_latest_strategy(symbol)
                            display_df.at[idx, 'strategy'] = latest_strategy if latest_strategy else 'Multi-Strategy'
                        except:
                            display_df.at[idx, 'strategy'] = 'Multi-Strategy'
                
                # Also fix "unknown" strategy (not just empty)
                if row['strategy'] == 'unknown':
                    display_df.at[idx, 'strategy'] = 'Multi-Strategy'
                
                # If still Multi-Strategy, try to get more specific info from database
                if display_df.at[idx, 'strategy'] == 'Multi-Strategy':
                    # Check if we can get more specific strategy info from trade notes
                    if not pd.isna(row.get('notes', '')):
                        notes = str(row.get('notes', ''))
                        # Extract strategy from notes if available
                        if 'signal:' in notes.lower():
                            # Extract signal type which might indicate strategy
                            signal_part = notes.split('signal:')[1].split(',')[0].strip()
                            if 'LONG' in signal_part or 'SHORT' in signal_part:
                                display_df.at[idx, 'strategy'] = f"Multi-Strategy ({signal_part})"
                
                # Fix 2 & 3: For open positions, show current price and calculate live PnL
                if row['status'] == 'OPEN':
                    if symbol in current_positions:
                        pos = current_positions[symbol]
                        
                        # Get current market data
                        if isinstance(pos, dict):
                            current_price = pos.get('market_price', pos.get('avg_price', row['entry_price']))
                            # Calculate unrealized PnL
                            entry_price = row['entry_price']
                            quantity = row['quantity']
                            if row['side'] == 'BUY':
                                unrealized_pnl = (current_price - entry_price) * quantity
                            else:  # SELL
                                unrealized_pnl = (entry_price - current_price) * quantity
                        else:
                            # Handle IBKR PortfolioItem objects
                            current_price = getattr(pos, 'marketPrice', getattr(pos, 'market_price', row['entry_price']))
                            unrealized_pnl = getattr(pos, 'unrealizedPNL', getattr(pos, 'unrealized_pnl', 0))
                        
                        # Update display values
                        display_df.at[idx, 'exit_price'] = current_price
                        display_df.at[idx, 'pnl'] = unrealized_pnl
                        
                        # Enhanced status with PnL indicator
                        pnl_indicator = "🟢" if unrealized_pnl > 0 else "🔴" if unrealized_pnl < 0 else "⚪"
                        display_df.at[idx, 'status'] = f"OPEN {pnl_indicator}"
                    else:
                        # Position marked as OPEN but not in current_positions - likely closed externally
                        display_df.at[idx, 'status'] = "CLOSED (External)"
                        
                        # Calculate real PnL using current market price instead of None
                        try:
                            symbol = row['symbol']
                            entry_price = row['entry_price']
                            quantity = row['quantity']
                            
                            # Try to get current market price using synchronous methods only
                            current_market_price = None
                            
                            # Method 1: Try to get from trading system data manager (synchronous)
                            if st.session_state.trading_system and hasattr(st.session_state.trading_system, 'data_manager'):
                                try:
                                    # Check if get_latest_data is synchronous
                                    latest_data = st.session_state.trading_system.data_manager.get_latest_data(symbol)
                                    # Ensure we don't have a coroutine
                                    if latest_data and not hasattr(latest_data, '__await__'):
                                        current_market_price = latest_data.close
                                except Exception as e:
                                    # Skip if method is async or fails
                                    pass
                            
                            # Method 2: Try to get from cached market data if available
                            if not current_market_price:
                                try:
                                    # Look for cached market data in the trading system
                                    if hasattr(st.session_state.trading_system, 'market_data_cache'):
                                        cached_data = st.session_state.trading_system.market_data_cache.get(symbol)
                                        if cached_data and hasattr(cached_data, 'close'):
                                            current_market_price = cached_data.close
                                except:
                                    pass
                            
                            # Method 3: Use yfinance for real-time price (synchronous)
                            if not current_market_price:
                                try:
                                    import yfinance as yf
                                    ticker = yf.Ticker(symbol)
                                    
                                    # Try current price from info
                                    info = ticker.info
                                    current_market_price = info.get('currentPrice') or info.get('regularMarketPrice')
                                    
                                    # If no current price, try recent history
                                    if not current_market_price:
                                        hist = ticker.history(period="1d", interval="5m")
                                        if not hist.empty:
                                            current_market_price = float(hist['Close'].iloc[-1])
                                            
                                except Exception as e:
                                    # yfinance failed, continue to fallback
                                    pass
                            
                            # Method 4: Fallback - estimate using entry price (conservative approach)
                            if not current_market_price or current_market_price <= 0:
                                # Use entry price as conservative estimate for external closes
                                current_market_price = entry_price
                                st.info(f"ℹ️ Usando precio de entrada como estimación para {symbol}")
                            
                            # Ensure we have valid numbers for calculation
                            current_market_price = float(current_market_price)
                            entry_price = float(entry_price)
                            quantity = float(quantity)
                            
                            # Calculate PnL based on position side
                            if row['side'] == 'BUY':
                                realized_pnl = (current_market_price - entry_price) * quantity
                            else:  # SELL
                                realized_pnl = (entry_price - current_market_price) * quantity
                            
                            # Update with calculated values
                            display_df.at[idx, 'exit_price'] = round(current_market_price, 2)
                            display_df.at[idx, 'pnl'] = round(realized_pnl, 2)
                            
                            # Add indicator for estimated vs real price
                            if abs(current_market_price - entry_price) < 0.01:  # Essentially same price
                                display_df.at[idx, 'status'] = "CLOSED (External - Estimated)"
                            else:
                                display_df.at[idx, 'status'] = "CLOSED (External - Market Price)"
                                
                        except Exception as e:
                            # If all methods fail, use entry price as fallback
                            try:
                                display_df.at[idx, 'exit_price'] = float(row['entry_price'])
                                display_df.at[idx, 'pnl'] = 0.0  # Conservative estimate
                                display_df.at[idx, 'status'] = "CLOSED (External - Fallback)"
                            except:
                                display_df.at[idx, 'exit_price'] = 0.0
                                display_df.at[idx, 'pnl'] = 0.0
                                display_df.at[idx, 'status'] = "CLOSED (External - Error)"
                            st.warning(f"⚠️ Error calculando PnL para {row['symbol']}: {str(e)[:100]}")
            
            # Format datetime
            display_df['entry_time'] = pd.to_datetime(display_df['entry_time']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Display DataFrame with optimized column widths (pixel values)
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                height=400,  # Fixed height with scroll
                column_config={
                    "symbol": st.column_config.TextColumn("Símbolo", width=70),
                    "strategy": st.column_config.TextColumn("Estrategia", width=140),
                    "side": st.column_config.TextColumn("Lado", width=50),
                    "quantity": st.column_config.NumberColumn("Qty", width=60),
                    "entry_price": st.column_config.NumberColumn("Precio Entrada", width=100, format="$%.4f"),
                    "exit_price": st.column_config.TextColumn("Precio Salida", width=100),  # Text to handle "Unknown"
                    "pnl": st.column_config.TextColumn("PnL", width=80),  # Text to handle "Unknown"
                    "status": st.column_config.TextColumn("Estado", width=120),
                    "entry_time": st.column_config.TextColumn("Fecha/Hora", width=110)
                }
            )
        else:
            st.info("ℹ️ No hay trades registrados con los filtros seleccionados")
    
    with analytics_tab3:
        st.subheader("📝 Trading Journal")
        
        # Journal entry form
        with st.expander("✍️ Nueva Entrada de Journal", expanded=False):
            journal_date = st.date_input("Fecha", value=date.today())
            market_notes = st.text_area("Notas del Mercado", placeholder="¿Cómo estuvo el mercado hoy? Volatilidad, tendencias...")
            strategy_notes = st.text_area("Notas de Estrategia", placeholder="¿Qué estrategias funcionaron mejor? ¿Cuáles no?")
            lessons_learned = st.text_area("Lecciones Aprendidas", placeholder="¿Qué aprendiste hoy? ¿Qué harías diferente?")
            mood_rating = st.slider("Estado de Ánimo (1-5)", 1, 5, 3)
            
            if st.button("💾 Guardar Entrada"):
                if db_manager.save_journal_entry(
                    journal_date, market_notes, strategy_notes, lessons_learned, mood_rating
                ):
                    st.success("✅ Entrada de journal guardada")
                else:
                    st.error("❌ Error guardando entrada")
        
        # Display recent journal entries
        st.subheader("📚 Entradas Recientes")
        journal_entries = db_manager.get_journal_entries(days=30)
        
        if not journal_entries.empty:
            for _, entry in journal_entries.iterrows():
                with st.expander(f"📅 {entry['date']} - Mood: {'⭐' * entry['mood_rating']}", expanded=False):
                    if entry['market_notes']:
                        st.write("**📈 Mercado:**", entry['market_notes'])
                    if entry['strategy_notes']:
                        st.write("**🎯 Estrategia:**", entry['strategy_notes'])
                    if entry['lessons_learned']:
                        st.write("**💡 Lecciones:**", entry['lessons_learned'])
        else:
            st.info("ℹ️ No hay entradas de journal. ¡Empieza escribiendo tu primera entrada!")

# Tab 4: Scanner - Daily Plays Filter integrado
with tab4:
    st.header("📊 Daily Plays Filter")
    st.markdown("Filtro avanzado para plays del día con datos de ProRealTime")
    
    # Create scanner interface
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.subheader("⚙️ Configuración")
        
        max_float = st.number_input(
            "Float máximo (millones)",
            min_value=1,
            max_value=1000,
            value=100,
            step=10
        ) * 1_000_000
        
        # Sentiment filter selector
        st.subheader("🎯 Filtro de Catalizadores")
        sentiment_filter = st.radio(
            "Tipo de catalizadores a incluir:",
            options=["Solo POSITIVOS", "POSITIVOS + NEUTRALES"],
            index=0,  # Default to strict
            help="Solo POSITIVOS = Más conservador, menos señales pero mayor calidad\nPOSITIVOS + NEUTRALES = Más permisivo, más señales pero menor calidad"
        )
        
        # Show current criteria
        sentiment_mode = "Solo POSITIVOS" if sentiment_filter == "Solo POSITIVOS" else "POSITIVOS + NEUTRALES"
        criteria_info = f"""
        **Criterios actuales:**
        - 📊 Float máximo: {max_float:,.0f} acciones
        - 📈 Gap mínimo: 10% (filtrado en PRT)
        - 📊 Volumen premarket: >500K (filtrado en PRT)
        - 📰 Catalizadores: {sentiment_mode}
        """
        st.markdown(criteria_info)
        
        # Keywords expandable section
        with st.expander("📰 Palabras clave de catalizadores"):
            keywords = [
                "FDA", "earnings", "acquisition", "merger", "clinical", 
                "breakthrough", "partnership", "contract", "innovation",
                "bitcoin", "crypto", "oil", "gas", "drilling"
            ]
            st.markdown("**Algunos ejemplos:**")
            for i in range(0, len(keywords), 3):
                cols = st.columns(3)
                for j, keyword in enumerate(keywords[i:i+3]):
                    if j < len(cols):
                        cols[j].write(f"• {keyword}")
    
    with col1:
        st.subheader("📋 Datos de ProRealTime")
        st.markdown("Pega aquí los datos del ProScreener:")
        
        # Large text area for PRT data
        prt_data = st.text_area(
            "Datos ProScreener",
            height=300,
            placeholder='"Ticker"    "Nombre"    "%Var"    "Var"    "Último"    "Inserción"    "Volumen"\n"ATNF"    "180 LIFE SCIENCES"    "+206,59%"    "+6,90"    "10,24(c)"    "07:00:33"    "225M"\n"AAL"    "AMERICAN AIRLINES GROUP INC."    "+12,09%"    "+1,40"    "12,98(c)"    "07:00:33"    "115M"',
            help="Copia y pega directamente desde ProRealTime ProScreener - Soporta ambos formatos automáticamente"
        )
        
        # Filter button
        if st.button("🔍 Filtrar Tickers", type="primary", use_container_width=True):
            if prt_data.strip():
                # Simple processing without external dependencies
                st.info("📊 Procesando datos de ProRealTime...")
                
                # Basic parsing - extract tickers from the data
                import re
                ticker_pattern = r'"([A-Z]{2,5})"'
                found_tickers = re.findall(ticker_pattern, prt_data)
                
                if found_tickers:
                    # Remove header if present
                    if 'Ticker' in found_tickers:
                        found_tickers.remove('Ticker')
                    
                    # Basic deduplication
                    unique_tickers = list(set(found_tickers))
                    
                    # Store results
                    st.session_state['scanner_tickers'] = unique_tickers
                    st.success(f"✅ Encontrados {len(unique_tickers)} tickers únicos de ProRealTime!")
                    
                    # Show note about full functionality
                    st.info("ℹ️ Filtrado básico aplicado. Para análisis completo de float y noticias, ver la sección 'Scanner Avanzado' más abajo.")
                else:
                    st.warning("⚠️ No se encontraron tickers válidos en los datos.")
            else:
                st.error("Por favor, pega los datos de ProRealTime")
    
    # Results section
    st.header("🎯 Resultados")
    
    if 'scanner_tickers' in st.session_state:
        tickers = st.session_state['scanner_tickers']
        
        if tickers:
            # Display results in different formats
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📋 Lista para copiar")
                ticker_string = ', '.join(tickers)
                st.text_area(
                    "Tickers filtrados:",
                    value=ticker_string,
                    height=100,
                    help="Copia esta lista para usar en tu trading system"
                )
                
                # Add to trading system button
                if st.button("➕ Agregar todos al Trading System", type="secondary", use_container_width=True):
                    if 'manual_symbols' not in st.session_state:
                        st.session_state.manual_symbols = []
                    
                    added_count = 0
                    for ticker in tickers:
                        if ticker not in st.session_state.manual_symbols:
                            st.session_state.manual_symbols.append(ticker)
                            added_count += 1
                    
                    if added_count > 0:
                        st.success(f"✅ Agregados {added_count} símbolos al trading system")
                        st.rerun()
                    else:
                        st.info("Todos los símbolos ya están en el trading system")
            
            with col2:
                st.subheader("📊 Lista detallada")
                df = pd.DataFrame(tickers, columns=['Ticker'])
                df['Index'] = range(1, len(df) + 1)
                df = df[['Index', 'Ticker']]
                st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Download button
            st.download_button(
                label="💾 Descargar lista como CSV",
                data=pd.DataFrame(tickers, columns=['Ticker']).to_csv(index=False),
                file_name=f"daily_plays_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ No se encontraron tickers que cumplan los criterios")
    
    # Instructions
    with st.expander("📖 Instrucciones de uso"):
        st.markdown("""
        ### Cómo usar este filtro:
        
        1. **En ProRealTime ProScreener:**
           - Configura filtros para volumen premarket >500K
           - Configura gap positivo >10%
           - Exporta o copia los resultados
        
        2. **En esta interfaz:**
           - Pega los datos en el área de texto
           - Ajusta el float máximo si es necesario
           - Haz clic en "Filtrar Tickers"
        
        3. **Resultado:**
           - Lista de tickers extraídos de ProRealTime
           - Posibilidad de agregar directamente al trading system
        
        ### Formatos soportados de ProRealTime:
        
        **Formato nuevo (recomendado):**
        ```
        "Ticker"    "Nombre"    "%Var"    "Var"    "Último"    "Inserción"    "Volumen"
        "ATNF"    "180 LIFE SCIENCES"    "+206,59%"    "+6,90"    "10,24(c)"    "07:00:33"    "225M"
        ```
        
        **Formato anterior (también compatible):**
        ```
        "Ticker"    "Nombre"    "Criterio"    "%Var"    "Var"    "Inserción"    "Último"    "Volumen"
        "TLRY"    "TILRAY BRANDS INC."    "6"    "+0,34%"    "+0,0031"    "20:03:57"    "0,9231"    "289M"
        ```
        
        ### Nota sobre funcionalidad avanzada:
        Esta versión integrada extrae tickers de ProRealTime para uso inmediato. 
        Para análisis más profundo con:
        - Filtrado automático por float shares
        - Análisis de noticias y catalizadores
        - Sentiment analysis con IA
        
        Ver la sección "Scanner Avanzado Disponible" al final de esta página.
        """)
    
    # Enhanced functionality note
    with st.expander("🚀 Scanner Avanzado Disponible"):
        st.markdown("""
        **¿Necesitas funcionalidad completa de análisis?**
        
        El scanner completo está disponible en el directorio `scanner/` con:
        - ✅ Filtrado automático por float shares
        - ✅ Análisis de noticias en tiempo real 
        - ✅ Detección de catalizadores
        - ✅ Sentiment analysis con IA
        - ✅ Múltiples fuentes de noticias
        
        **Para usar el scanner completo:**
        ```bash
        cd scanner
        streamlit run web_interface.py
        ```
        
        **O integrar directamente aquí:**
        Si prefieres tener toda la funcionalidad aquí, podemos integrar las dependencias completas del scanner.
        """)
        
        if st.button("🔧 Integrar Scanner Completo", help="Esto requerirá instalar dependencias adicionales"):
            st.info("📋 Para integrar el scanner completo, necesitarás instalar:\n- yahooquery\n- aiohttp\n- Módulos de news_sources")
            st.code("pip install yahooquery aiohttp", language="bash")

# Tab 5: System
with tab5:
    st.header("Información del Sistema")
    
    # Update system data when system tab is accessed
    if st.session_state.get('system_running', False):
        data_manager.update_system_data()
    
    # Connection status
    st.subheader("Estado de Conexiones")
    connection_status = data_manager.get_connection_status(config)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**🔌 IBKR Connection:**")
        if connection_status['ibkr_connected']:
            st.success("🟢 CONECTADO")
        else:
            st.error("🔴 DESCONECTADO")
    
    with col2:
        st.write("**🤖 Sistema de Trading:**")
        if connection_status['system_running']:
            st.success("🟢 ACTIVO")
            st.write(f"Estrategia: {config.strategy_name.upper()}")
        else:
            st.error("🔴 INACTIVO")

# Footer with useful links and info
st.sidebar.markdown("---")

# Quick Actions
with st.sidebar.expander("⚡ Acciones Rápidas", expanded=True):
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Refresh", use_container_width=True, help="Actualizar datos"):
            data_manager.update_system_data()
            st.rerun()
    
    with col2:
        if st.button("📊 Status", use_container_width=True, help="Ver estado completo"):
            # This could redirect to System tab or show a popup
            st.info("Estado visible arriba ⬆️")
    

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="text-align: center; color: #666; font-size: 0.7rem;">
    <p style="margin: 0.2rem 0;">💼 <strong>Portfolio Management</strong></p>
    <p style="margin: 0.2rem 0;">⚡ Real-time Trading Engine</p>
    <p style="margin: 0.2rem 0;">🛡️ Risk Management Enabled</p>
    <br>
    <p style="margin: 0; color: #888;">Built with ❤️ for Professional Trading</p>
</div>
""", unsafe_allow_html=True)