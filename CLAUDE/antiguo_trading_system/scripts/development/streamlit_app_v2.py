# streamlit_app_v2.py
"""
Interfaz web con Streamlit para el nuevo sistema de trading.
Compatible con la arquitectura v2.0
"""

import streamlit as st
import asyncio
import nest_asyncio
import configparser
import os
import sys
import time
import pandas as pd
from threading import Thread
import logging
from datetime import datetime
from pathlib import Path
import atexit
import signal

# Aplicar nest_asyncio para permitir eventos anidados (necesario para Streamlit)
nest_asyncio.apply()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,  # Volver a INFO para menos ruido
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("StreamlitApp")

# Filtro para suprimir warnings de ScriptRunContext durante shutdown
class StreamlitWarningFilter(logging.Filter):
    def filter(self, record):
        return "missing ScriptRunContext" not in record.getMessage()

# Aplicar filtro a todos los loggers de streamlit
for name in logging.root.manager.loggerDict:
    if 'streamlit' in name.lower():
        logging.getLogger(name).addFilter(StreamlitWarningFilter())

# Cleanup handler para evitar errores de event loop
def cleanup_handler():
    """Cleanup graceful del sistema"""
    try:
        if 'trading_system' in st.session_state and st.session_state.trading_system:
            asyncio.run(st.session_state.trading_system.stop())
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Registrar cleanup handler
atexit.register(cleanup_handler)

# Los signal handlers pueden interferir con Streamlit, removidos

# PARCHE PARA ERRORES ARROW - AÑADIR AQUÍ
def safe_dataframe(data, **kwargs):
    """Versión segura que no causa errores Arrow"""
    try:
        # Convertir a DataFrame si no lo es
        if not isinstance(data, pd.DataFrame):
            data = pd.DataFrame(data)
        
        # Convertir todas las columnas a string
        for col in data.columns:
            data[col] = data[col].astype(str)
        
        return st._original_dataframe(data, **kwargs)
    except Exception:
        # Fallback: mostrar como texto
        st.write("**Datos (modo seguro):**")
        for _, row in data.iterrows():
            st.write(" | ".join([f"**{k}**: {v}" for k, v in row.items()]))

# Reemplazar st.dataframe
if not hasattr(st, '_original_dataframe'):
    st._original_dataframe = st.dataframe
    st.dataframe = safe_dataframe

# --- Auto-refresh UI cada 6 segundos para mantener estado actualizado ---
try:
    from streamlit_autorefresh import st_autorefresh
    # Refresca la app cada 6 000 ms (6 s). La variable count evita bucles infinitos.
    st_autorefresh(interval=6000, key="auto_refresh")
except ImportError:
    # Si la librería no está instalada, la UI seguirá funcionando sin refresco automático.
    pass
except RuntimeError:
    # Handle event loop closed errors gracefully
    pass

# Añadir el directorio actual al path para poder importar módulos
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Importar el nuevo sistema de trading
# Import core modules first (most critical)
try:
    from core.interfaces import TradingConfig
    from strategies import register_strategy, list_strategies
    print("✅ Core modules imported successfully")
except ImportError as e:
    st.error(f"Error importando módulos críticos: {e}")
    st.info("No se pueden cargar los módulos críticos del sistema.")
    st.stop()

# Import strategies (less critical - can work without some)
try:
    from strategies.macdv_strategy import MACDVStrategy
    from strategies.gap_go_strategy import GapGoStrategy  
    from strategies.orb_strategy import ORBStrategy
    from strategies.volume_momentum_strategy import VolumeMomentumStrategy
    from strategies.optimized_gap_go_strategy import OptimizedGapGoStrategy
    from strategies.volume_breakout_strategy import VolumeBreakoutStrategy
    from strategies.vwap_strategy import VWAPSmallcapsStrategy
    print("✅ Individual strategies imported successfully")
except ImportError as e:
    st.warning(f"Advertencia importando estrategias individuales: {e}")
    print(f"⚠️ Some individual strategies failed to import: {e}")

# Import main module (optional - only needed for full system)
TradingSystemManager = None
try:
    from main import TradingSystemManager
    print("✅ TradingSystemManager imported successfully")
except ImportError as e:
    st.warning(f"TradingSystemManager no disponible (requiere ib_insync): {e}")
    print(f"⚠️ TradingSystemManager not available: {e}")
    # Continue without TradingSystemManager - strategies can still be selected

# Variables globales para el estado del sistema (copias locales)
trading_system = st.session_state.get('trading_system') if 'trading_system' in st.session_state else None
system_thread = st.session_state.get('system_thread') if 'system_thread' in st.session_state else None
system_running = st.session_state.get('system_running', False)
positions = {}
last_update = datetime.now()
daily_stats = {}

# Inicializar el estado de la sesión de Streamlit
if 'manual_symbols' not in st.session_state:
    st.session_state.manual_symbols = []  # Lista de símbolos manuales

if 'system_config' not in st.session_state:
    st.session_state.system_config = None

# Garantizar claves para sistema y thread
if 'trading_system' not in st.session_state:
    st.session_state.trading_system = None
if 'system_thread' not in st.session_state:
    st.session_state.system_thread = None
if 'system_running' not in st.session_state:
    st.session_state.system_running = False

def load_config_from_ini() -> TradingConfig:
    """Cargar configuración desde config.ini"""
    logger.info("Iniciando carga de configuración...")
    config = configparser.ConfigParser()
    config_file = current_dir / 'config.ini'
    
    if config_file.exists():
        config.read(config_file)
        logger.info(f"Configuración cargada desde: {config_file}")
    else:
        logger.warning(f"No se encontró config.ini en {config_file}")
        config = configparser.ConfigParser()  # Config vacío con defaults
    
    # CREAR TRADINGCONFIG SOLO CON PARÁMETROS BÁSICOS - SIN close_positions_on_stop
    try:
        logger.info("Creando TradingConfig...")
        trading_config = TradingConfig(
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
        
        # AÑADIR ATRIBUTOS ADICIONALES DESPUÉS DE LA CREACIÓN
        trading_config.min_volume_avg = config.getint('VOLUME_FILTERS', 'min_volume_avg', fallback=50000)
        trading_config.min_volume_current = config.getint('VOLUME_FILTERS', 'min_volume_current', fallback=25000)
        trading_config.min_price = config.getfloat('VOLUME_FILTERS', 'min_price', fallback=1.0)
        trading_config.max_price = config.getfloat('VOLUME_FILTERS', 'max_price', fallback=25.0)
        trading_config.volume_spike_threshold = config.getfloat('VOLUME_FILTERS', 'volume_spike_threshold', fallback=1.5)
        trading_config.volume_period = config.getint('VOLUME_FILTERS', 'volume_period', fallback=20)
        trading_config.close_positions_on_stop = config.getboolean('TRADING', 'close_positions_on_stop', fallback=False)
        
        # AÑADIR PARÁMETROS DE RIESGO DE LA SECCIÓN [RISK]
        trading_config.max_portfolio_concentration = config.getfloat('RISK', 'max_portfolio_concentration', fallback=0.8)
        trading_config.max_portfolio_exposure = config.getfloat('RISK', 'max_portfolio_exposure', fallback=1200.0)
        trading_config.max_portfolio_volatility = config.getfloat('RISK', 'max_portfolio_volatility', fallback=0.50)
        trading_config.max_position_value = config.getfloat('RISK', 'max_position_value', fallback=1000.0)
        
        return trading_config
        
    except TypeError as e:
        # Si hay error con los parámetros, crear con defaults
        logger.error(f"Error creando TradingConfig: {e}")
        logger.info("Creando TradingConfig con valores por defecto...")
        
        # Crear con defaults y añadir atributos después
        trading_config = TradingConfig()
        
        # Sobrescribir con valores del config.ini
        trading_config.max_positions = config.getint('TRADING', 'max_positions', fallback=5)
        trading_config.max_risk_per_trade = config.getfloat('TRADING', 'max_risk_per_trade', fallback=0.02)
        trading_config.max_daily_loss = config.getfloat('TRADING', 'max_daily_loss', fallback=-500.0)
        trading_config.max_daily_trades = config.getint('TRADING', 'max_daily_trades', fallback=20)
        trading_config.enable_filters = config.getboolean('TRADING', 'use_volume_filter', fallback=True)
        trading_config.broker_host = config.get('IBKR', 'host', fallback='127.0.0.1')
        trading_config.broker_port = config.getint('IBKR', 'port', fallback=7497)
        trading_config.broker_client_id = config.getint('IBKR', 'client_id', fallback=1)
        trading_config.strategy_name = config.get('TRADING', 'strategy', fallback='macdv')
        trading_config.timeframe = config.get('TRADING', 'timeframe', fallback='1 min')
        trading_config.log_level = config.get('LOGGING', 'level', fallback='INFO')
        trading_config.log_file = config.get('LOGGING', 'file', fallback='trading_system.log')
        
        # Añadir atributos adicionales
        trading_config.min_volume_avg = config.getint('VOLUME_FILTERS', 'min_volume_avg', fallback=50000)
        trading_config.min_volume_current = config.getint('VOLUME_FILTERS', 'min_volume_current', fallback=25000)
        trading_config.min_price = config.getfloat('VOLUME_FILTERS', 'min_price', fallback=1.0)
        trading_config.max_price = config.getfloat('VOLUME_FILTERS', 'max_price', fallback=25.0)
        trading_config.volume_spike_threshold = config.getfloat('VOLUME_FILTERS', 'volume_spike_threshold', fallback=1.5)
        trading_config.volume_period = config.getint('VOLUME_FILTERS', 'volume_period', fallback=20)
        trading_config.close_positions_on_stop = config.getboolean('TRADING', 'close_positions_on_stop', fallback=False)
        
        # Añadir parámetros de riesgo de la sección [RISK]
        trading_config.max_portfolio_concentration = config.getfloat('RISK', 'max_portfolio_concentration', fallback=0.8)
        trading_config.max_portfolio_exposure = config.getfloat('RISK', 'max_portfolio_exposure', fallback=1200.0)
        trading_config.max_portfolio_volatility = config.getfloat('RISK', 'max_portfolio_volatility', fallback=0.50)
        trading_config.max_position_value = config.getfloat('RISK', 'max_position_value', fallback=1000.0)
        
        return trading_config

def save_config_to_ini(config: TradingConfig):
    """Guardar configuración actualizada a config.ini"""
    ini_config = configparser.ConfigParser()
    config_file = current_dir / 'config.ini'
    
    # Leer config existente si existe
    if config_file.exists():
        ini_config.read(config_file)
    
    # Actualizar secciones relevantes
    sections_to_update = {
        'TRADING': {
            'strategy': config.strategy_name,  # Usar 'strategy_name' para mantener consistencia
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
        },
        'VOLUME_FILTERS': {
            'min_volume_avg': str(getattr(config, 'min_volume_avg', 50000)),
            'min_volume_current': str(getattr(config, 'min_volume_current', 25000)),
            'min_price': str(getattr(config, 'min_price', 1.0)),
            'max_price': str(getattr(config, 'max_price', 25.0)),
            'volume_spike_threshold': str(getattr(config, 'volume_spike_threshold', 1.5)),
            'volume_period': str(getattr(config, 'volume_period', 20))
        }
    }
    
    for section_name, section_data in sections_to_update.items():
        if not ini_config.has_section(section_name):
            ini_config.add_section(section_name)
        
        for key, value in section_data.items():
            ini_config.set(section_name, key, value)
    
    # Guardar archivo
    with open(config_file, 'w') as f:
        ini_config.write(f)
    
    logger.info("Configuración guardada en config.ini")

def start_trading_system(symbols=None):
    """Inicia el sistema de trading en un thread separado"""
    global trading_system, system_thread, system_running
    
    if st.session_state.system_running:
        st.error("El sistema ya está en ejecución")
        return False
    
    try:
        # Registrar todas las estrategias disponibles
        register_strategy('macdv', MACDVStrategy)
        register_strategy('volume_breakout', VolumeBreakoutStrategy)
        register_strategy('vwap_smallcaps', VWAPSmallcapsStrategy)
        register_strategy('gap_go', GapGoStrategy)
        register_strategy('optimized_gap_go', OptimizedGapGoStrategy)
        register_strategy('orb', ORBStrategy)
        register_strategy('volume_momentum', VolumeMomentumStrategy)

        # Cargar configuración
        config = load_config_from_ini()
        st.session_state.system_config = config
        
        # Generar ID de cliente aleatorio para evitar conflictos
        import random
        config.broker_client_id = random.randint(100, 9999)
        
        # Crear sistema de trading - INDICAR QUE ESTAMOS EN STREAMLIT
        if TradingSystemManager is not None:
            st.session_state.trading_system = TradingSystemManager(config, in_streamlit=True)
            trading_system = st.session_state.trading_system
            
            # Iniciar en thread separado
            st.session_state.system_thread = Thread(target=run_system_async, args=(trading_system, symbols))
            st.session_state.system_thread.daemon = True
            st.session_state.system_thread.start()
            
            st.session_state.system_running = True
        else:
            st.error("❌ No se puede iniciar el sistema de trading: TradingSystemManager no disponible")
            st.info("💡 Para usar el sistema completo, instala las dependencias: `pip install ib_insync`")
            st.info("📋 Puedes ver las estrategias disponibles y la configuración sin ejecutar el trading.")
        logger.info(f"Sistema iniciado con client_id: {config.broker_client_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error iniciando sistema: {e}")
        st.error(f"Error iniciando sistema: {e}")
        return False

def run_system_async(system, symbols=None):
    """Ejecuta el sistema de trading de forma asíncrona"""
    global system_running
    
    try:
        # Crear nuevo evento loop para este thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Inicializar sistema
        loop.run_until_complete(system.initialize())
        
        # Iniciar sistema con símbolos
        loop.run_until_complete(system.start(symbols))
        
    except Exception as e:
        logger.error(f"Error en sistema de trading: {e}")
    finally:
        st.session_state.system_running = False
        loop.close()

def stop_trading_system():
    """Detiene el sistema de trading"""
    global trading_system, system_running
    
    if st.session_state.trading_system and st.session_state.system_running:
        try:
            # Crear loop temporal para detener el sistema
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(st.session_state.trading_system.stop())
            loop.close()
            
            st.session_state.system_running = False
            logger.info("Sistema detenido correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error deteniendo sistema: {e}")
            return False
    
    return True

def update_system_data():
    """Actualiza datos del sistema (posiciones, estadísticas, ejecuciones)"""
    global positions, daily_stats, last_update
    
    if st.session_state.trading_system and st.session_state.system_running:
        try:
            status = st.session_state.trading_system.get_status()
            positions = status.get('positions', {})
            daily_stats = status.get('daily_stats', {})
            last_update = datetime.now()
            
            # Log del estado para debugging
            logger.info(f"Datos actualizados: {len(positions)} posiciones, sistema running: {st.session_state.system_running}")
            
        except Exception as e:
            logger.error(f"Error actualizando datos del sistema: {e}")

def get_connection_status():
    """Obtiene el estado de conexión real del sistema"""
    if not st.session_state.trading_system or not st.session_state.system_running:
        return {
            'ibkr_connected': False,
            'system_running': False,
            'positions_count': 0,
            'last_update': 'N/A'
        }
    
    try:
        # Verificar estado de IBKR
        ibkr_connected = False
        if hasattr(st.session_state.trading_system, 'broker') and st.session_state.trading_system.broker:
            ibkr_connected = st.session_state.trading_system.broker.is_connected()
        
        status = st.session_state.trading_system.get_status()
        
        return {
            'ibkr_connected': ibkr_connected,
            'system_running': st.session_state.system_running,
            'positions_count': len(status.get('positions', {})),
            'monitored_symbols': len(status.get('monitored_symbols', set())),
            'last_update': last_update.strftime('%H:%M:%S') if last_update else 'N/A'
        }
    except Exception as e:
        logger.error(f"Error obteniendo estado de conexión: {e}")
        return {
            'ibkr_connected': False,
            'system_running': st.session_state.system_running,
            'positions_count': 0,
            'last_update': 'Error'
        }

def add_symbol_to_system(symbol):
    """Añade un símbolo al sistema en ejecución"""
    global trading_system
    
    if not st.session_state.trading_system or not st.session_state.system_running:
        # Si el sistema no está ejecutándose, añadir a la lista de espera
        if symbol not in st.session_state.manual_symbols:
            st.session_state.manual_symbols.append(symbol)
        return True
    
    try:
        # Crear loop temporal para añadir símbolo
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Intentar primero con validación
        result = loop.run_until_complete(trading_system.add_symbol(symbol, skip_validation=False))
        
        # Si falla la validación, ofrecer añadir sin validación
        if not result:
            logger.warning(f"Validación del símbolo {symbol} falló. Intentando añadir sin validación...")
            result = loop.run_until_complete(trading_system.add_symbol(symbol, skip_validation=True))
        
        loop.close()
        
        if result:
            # Añadir también a la lista de la sesión
            if symbol not in st.session_state.manual_symbols:
                st.session_state.manual_symbols.append(symbol)
            
            logger.info(f"Símbolo {symbol} añadido al sistema")
            return True
        else:
            logger.warning(f"No se pudo añadir el símbolo {symbol} - verificar logs para más detalles")
            return False
        
    except Exception as e:
        logger.error(f"Error añadiendo símbolo {symbol}: {e}")
        return False

def remove_symbol_from_system(symbol):
    """Elimina un símbolo del sistema"""
    global trading_system
    
    # Eliminar de la lista de la sesión
    if symbol in st.session_state.manual_symbols:
        st.session_state.manual_symbols.remove(symbol)
    
    if st.session_state.trading_system and st.session_state.system_running:
        try:
            # Crear loop temporal para eliminar símbolo
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(trading_system.remove_symbol(symbol))
            loop.close()
            
            logger.info(f"Símbolo {symbol} eliminado del sistema")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando símbolo {symbol}: {e}")
            return False
    
    return True

# Configuración de la página Streamlit
st.set_page_config(
    page_title="Sistema de Trading V2.0",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 Sistema de Trading V2.0 - Interfaz Web")
st.caption("Nueva arquitectura mejorada con gestión de riesgo avanzada")

# Sidebar para configuración
st.sidebar.header("⚙️ Configuración del Sistema")

# Cargar configuración actual con manejo de errores
try:
    if st.session_state.system_config is None:
        st.session_state.system_config = load_config_from_ini()
    config = st.session_state.system_config
except Exception as e:
    st.error(f"Error cargando configuración: {e}")
    st.error("Verifica que config.ini esté presente y tenga formato válido")
    st.stop()

# Configuración de estrategia
st.sidebar.subheader("📈 Estrategia")
try:
    available_strategies = list_strategies()
    
    # Priorizar multi_strategy en la lista para mejor visibilidad
    if 'multi_strategy' in available_strategies:
        available_strategies.remove('multi_strategy')
        available_strategies.insert(0, 'multi_strategy')
    
    # Encontrar el índice de la estrategia configurada en config.ini
    default_index = 0
    if config.strategy_name in available_strategies:
        default_index = available_strategies.index(config.strategy_name)

    selected_strategy = st.sidebar.selectbox(
        "Estrategia de Trading",
        options=available_strategies,
        index=default_index,
        help=f"Estrategia configurada por defecto en config.ini: {config.strategy_name}"
    )
    
    # Debug info para verificar carga correcta
    if config.strategy_name == 'multi_strategy':
        st.sidebar.success("✅ Multi-strategy configurada por defecto")
        
    # Show additional info for multi_strategy
    if selected_strategy == 'multi_strategy':
        st.sidebar.info("🎯 Multi-Strategy Engine activo")
        st.sidebar.markdown("**Estrategias incluidas:**")
        try:
            from strategies import get_strategy_class
            cls = get_strategy_class('multi_strategy')
            instance = cls()
            for strategy_name in instance.strategies.keys():
                st.sidebar.markdown(f"• {strategy_name}")
        except Exception as e:
            st.sidebar.markdown("• macdv_smallcaps")
            st.sidebar.markdown("• gap_go") 
            st.sidebar.markdown("• orb")
            st.sidebar.markdown("• volume_breakout")
            st.sidebar.markdown("• pmh_breakout")
except Exception as e:
    st.sidebar.error(f"Error cargando estrategias: {e}")
    # Fallback a estrategias básicas - multi_strategy primero
    available_strategies = ['multi_strategy', 'macdv', 'gap_go']
    default_fallback_index = 0 if config.strategy_name == 'multi_strategy' else 1
    selected_strategy = st.sidebar.selectbox(
        "Estrategia de Trading",
        options=available_strategies,
        index=default_fallback_index
    )

if selected_strategy != config.strategy_name:
    config.strategy_name = selected_strategy
    save_config_to_ini(config)
    
    # Actualizar en tiempo real si el sistema está en ejecución
    if 'trading_system' in st.session_state and st.session_state.trading_system is not None:
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(st.session_state.trading_system.update_config(config))
            st.sidebar.success(f"✅ Estrategia cambiada a: {selected_strategy.upper()}")
        except Exception as e:
            st.sidebar.error(f"⚠️ Error cambiando la estrategia: {e}")
            st.sidebar.warning("La estrategia se guardó pero no se pudo actualizar en tiempo real. Reinicia el sistema para aplicar los cambios.")
    else:
        st.sidebar.success(f"✅ Estrategia guardada. Se aplicará al iniciar el sistema: {selected_strategy.upper()}")

# Configuración de riesgo
st.sidebar.subheader("⚖️ Gestión de Riesgo")

new_max_positions = st.sidebar.slider(
    "Máximo de posiciones",
    min_value=1, max_value=10, value=config.max_positions
)

new_max_daily_loss = st.sidebar.number_input(
    "Pérdida máxima diaria ($)",
    min_value=-2000.0, max_value=-50.0, value=config.max_daily_loss, step=50.0
)

new_max_daily_trades = st.sidebar.slider(
    "Máximo trades por día",
    min_value=1, max_value=50, value=config.max_daily_trades
)

# Actualizar configuración si hay cambios
config_changed = False
if new_max_positions != config.max_positions:
    config.max_positions = new_max_positions
    config_changed = True

if new_max_daily_loss != config.max_daily_loss:
    config.max_daily_loss = new_max_daily_loss
    config_changed = True

if new_max_daily_trades != config.max_daily_trades:
    config.max_daily_trades = new_max_daily_trades
    config_changed = True

if config_changed:
    # Guardar en archivo
    save_config_to_ini(config)
    
    # Actualizar configuración en tiempo real si el sistema está en ejecución
    if 'trading_system' in st.session_state and st.session_state.trading_system is not None:
        try:
            # Ejecutar la actualización de forma síncrona
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(st.session_state.trading_system.update_config(config))
            st.sidebar.success("✅ Configuración actualizada en tiempo real")
        except Exception as e:
            st.sidebar.error(f"⚠️ Error actualizando configuración: {e}")
            st.sidebar.warning("La configuración se guardó pero no se pudo actualizar en tiempo real. Reinicia el sistema para aplicar los cambios.")
    else:
        st.sidebar.success("✅ Configuración guardada. Se aplicará al iniciar el sistema.")

# Configuración de filtros
st.sidebar.subheader("🔍 Filtros")
new_enable_filters = st.sidebar.checkbox(
    "Activar filtros de volumen",
    value=config.enable_filters
)

if new_enable_filters != config.enable_filters:
    config.enable_filters = new_enable_filters
    save_config_to_ini(config)
    
    # Actualizar en tiempo real si el sistema está en ejecución
    if 'trading_system' in st.session_state and st.session_state.trading_system is not None:
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(st.session_state.trading_system.update_config(config))
            st.sidebar.success("✅ Filtros actualizados en tiempo real")
        except Exception as e:
            st.sidebar.error(f"⚠️ Error actualizando filtros: {e}")
            st.sidebar.warning("Los filtros se guardaron pero no se pudieron actualizar en tiempo real. Reinicia el sistema para aplicar los cambios.")
    else:
        st.sidebar.success("✅ Filtros guardados. Se aplicarán al iniciar el sistema.")

# Pestañas principales
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎯 Control de Símbolos", "💼 Posiciones", "📊 Estadísticas", "📝 Ejecuciones", "⚙️ Sistema"])

# Pestaña 1: Control de Símbolos
with tab1:
    st.header("Control de Símbolos")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Añadir Símbolos")
        
        # Formulario para añadir símbolos individuales
        with st.form("add_symbol_form"):
            new_symbol = st.text_input("Símbolo", placeholder="AAPL").strip().upper()
            submitted = st.form_submit_button("➕ Añadir Símbolo")
            
            if submitted and new_symbol:
                if add_symbol_to_system(new_symbol):
                    st.success(f"✅ Símbolo {new_symbol} añadido")
                else:
                    st.error(f"❌ Error añadiendo {new_symbol}")
        
        # Formulario para añadir múltiples símbolos
        with st.form("add_multiple_symbols"):
            symbol_list = st.text_area(
                "Múltiples símbolos (separados por comas)",
                placeholder="AAPL, MSFT, GOOGL, TSLA"
            )
            submitted_multiple = st.form_submit_button("➕ Añadir Todos")
            
            if submitted_multiple and symbol_list:
                symbols = [s.strip().upper() for s in symbol_list.replace(',', ' ').split() if s.strip()]
                added_count = 0
                
                for symbol in symbols:
                    if symbol not in st.session_state.manual_symbols:
                        if add_symbol_to_system(symbol):
                            added_count += 1
                
                st.success(f"✅ Se añadieron {added_count} símbolos de {len(symbols)} intentados")
    
    with col2:
        st.subheader("Control del Sistema")
        
        # Estado del sistema
        if st.session_state.system_running:
            st.success("🟢 Sistema ACTIVO")
            
            if st.button("⏹️ Detener Sistema", type="secondary"):
                if stop_trading_system():
                    st.success("Sistema detenido")
                    st.rerun()
                else:
                    st.error("Error deteniendo sistema")
        else:
            st.error("🔴 Sistema INACTIVO")
            
            if st.button("▶️ Iniciar Sistema", type="primary"):
                symbols = st.session_state.manual_symbols if st.session_state.manual_symbols else None
                if start_trading_system(symbols):
                    st.success("Sistema iniciado")
                    st.rerun()
                else:
                    st.error("Error iniciando sistema")
        
        # Actualizar datos
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Actualizar Datos"):
                update_system_data()
                st.success("Datos actualizados")
        with col2:
            if st.button("🔧 Reset Circuit Breaker"):
                if st.session_state.get('trading_system') and st.session_state.trading_system.trading_engine:
                    st.session_state.trading_system.trading_engine.reset_circuit_breaker()
                    st.success("Circuit breaker reseteado para todos los símbolos")
                    st.rerun()
                else:
                    st.error("Sistema no está ejecutándose")
    
    # Lista de símbolos actuales - VERSIÓN SEGURA
    st.subheader("📈 Símbolos en Monitoreo")
    
    if st.session_state.manual_symbols:
        st.write(f"**Total de símbolos**: {len(st.session_state.manual_symbols)}")
        
        # Mostrar símbolos en formato grid con botones de eliminar
        for i, symbol in enumerate(st.session_state.manual_symbols):
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    status_icon = "🟢" if system_running else "⏸️"
                    status_text = "Activo" if system_running else "En espera"
                    st.write(f"**{symbol}**")
                
                with col2:
                    st.write(f"{status_icon} {status_text}")
                
                with col3:
                    if st.button("❌", key=f"remove_{symbol}_{i}", help=f"Eliminar {symbol}"):
                        remove_symbol_from_system(symbol)
                        st.rerun()
                
                if i < len(st.session_state.manual_symbols) - 1:
                    st.divider()
        
        # Alternativa: Tabla simple si se prefiere
        st.write("---")
        if st.button("📊 Ver como tabla", key="symbols_table_btn"):
            try:
                symbols_data = []
                for symbol in st.session_state.manual_symbols:
                    status = "🟢 Activo" if system_running else "⏸️ En espera"
                    symbols_data.append([str(symbol), str(status)])
                
                df_symbols = pd.DataFrame(symbols_data, columns=["Símbolo", "Estado"])
                
                # Asegurar tipos string
                df_symbols["Símbolo"] = df_symbols["Símbolo"].astype(str)
                df_symbols["Estado"] = df_symbols["Estado"].astype(str)
                
                st.dataframe(df_symbols, use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.error(f"Error mostrando tabla de símbolos: {e}")
    
    else:
        st.info("ℹ️ No hay símbolos en monitoreo. Añade algunos para empezar.")
        st.write("**Sugerencias**: AAPL, MSFT, GOOGL, TSLA, NVDA")

# Pestaña 2: Posiciones
with tab2:
    st.header("Posiciones Actuales")
    
    # Botón de actualización
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🔄 Actualizar", key="update_positions"):
            update_system_data()
    
    with col2:
        st.caption(f"Última actualización: {last_update.strftime('%H:%M:%S')}")
    
# Mostrar posiciones - VERSIÓN ULTRA SEGURA
    if positions:
        positions_list = []
        total_value = 0.0
        total_pnl = 0.0
        
        # Procesar posiciones de forma muy defensiva
        st.write("🔍 **Procesando posiciones...**")
        
        for symbol, position in positions.items():
            try:
                # Verificar que el objeto position tiene los atributos necesarios
                if not hasattr(position, 'quantity'):
                    st.warning(f"Posición {symbol} sin atributo 'quantity'")
                    continue
                    
                quantity_val = getattr(position, 'quantity', 0)
                if float(quantity_val) == 0:
                    continue  # Saltar posiciones vacías
                
                # Extraer datos de forma segura
                quantity = int(float(quantity_val))
                avg_price = float(getattr(position, 'avg_price', 0))
                market_price = float(getattr(position, 'market_price', 0))
                market_value = float(getattr(position, 'market_value', 0))
                unrealized_pnl = float(getattr(position, 'unrealized_pnl', 0))
                
                # Crear info de posición
                position_info = {
                    "symbol": str(symbol),
                    "quantity": quantity,
                    "avg_price": avg_price,
                    "market_price": market_price,
                    "market_value": market_value,
                    "unrealized_pnl": unrealized_pnl,
                    "side": "Long" if quantity > 0 else "Short"
                }
                
                positions_list.append(position_info)
                total_value += market_value
                total_pnl += unrealized_pnl
                
            except Exception as e:
                st.error(f"❌ Error procesando posición {symbol}: {e}")
                continue
        
        if positions_list:
            # Mostrar resumen con métricas
            st.subheader("📊 Resumen de Posiciones")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    label="Posiciones Abiertas",
                    value=len(positions_list)
                )
            with col2:
                st.metric(
                    label="Valor Total",
                    value=f"${total_value:.2f}"
                )
            with col3:
                pnl_delta = f"+${total_pnl:.2f}" if total_pnl >= 0 else f"${total_pnl:.2f}"
                st.metric(
                    label="PnL Total",
                    value=f"${total_pnl:.2f}",
                    delta=pnl_delta
                )
            
            # Mostrar tabla de posiciones - MODO SEGURO
            st.subheader("📋 Detalle de Posiciones")
            
            # Crear tabla manual sin usar st.dataframe
            for i, pos in enumerate(positions_list):
                with st.container():
                    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1.5, 1.5, 1.5, 1])
                    
                    with col1:
                        st.write(f"**{pos['symbol']}**")
                    with col2:
                        side_icon = "🟢" if pos['side'] == "Long" else "🔴"
                        st.write(f"{side_icon} {pos['side']}")
                    with col3:
                        st.write(f"Cantidad: {pos['quantity']}")
                    with col4:
                        st.write(f"Precio Prom: ${pos['avg_price']:.2f}")
                    with col5:
                        st.write(f"Precio Actual: ${pos['market_price']:.2f}")
                    with col6:
                        pnl_color = "🟢" if pos['unrealized_pnl'] >= 0 else "🔴"
                        st.write(f"{pnl_color} ${pos['unrealized_pnl']:.2f}")
                    
                    if i < len(positions_list) - 1:
                        st.divider()
            
            # Alternativa: Intentar mostrar DataFrame si es posible
            st.subheader("📊 Tabla Completa")
            try:
                # Crear DataFrame simple
                simple_data = []
                for pos in positions_list:
                    simple_data.append([
                        pos['symbol'],
                        f"{pos['quantity']} ({pos['side']})",
                        f"${pos['avg_price']:.2f}",
                        f"${pos['market_price']:.2f}",
                        f"${pos['market_value']:.2f}",
                        f"${pos['unrealized_pnl']:.2f}"
                    ])
                
                df_simple = pd.DataFrame(
                    simple_data,
                    columns=["Símbolo", "Cantidad (Lado)", "Precio Prom", "Precio Actual", "Valor", "PnL"]
                )
                
                # Asegurar que todo sea string
                for col in df_simple.columns:
                    df_simple[col] = df_simple[col].astype(str)
                
                st.dataframe(df_simple, use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.warning(f"No se pudo mostrar tabla DataFrame: {e}")
                st.info("Los datos se muestran arriba en formato manual")
        
        else:
            st.info("ℹ️ No hay posiciones abiertas válidas")
            
    else:
        st.info("ℹ️ No hay datos de posiciones disponibles")
        
        # Botón de debug para verificar el objeto positions
        if st.button("🔍 Debug: Verificar datos de posiciones"):
            st.write("**Contenido de 'positions':**")
            st.write(f"Tipo: {type(positions)}")
            st.write(f"Contenido: {positions}")

# Pestaña 3: Estadísticas
with tab3:
    st.header("Estadísticas del Sistema")
    
    if daily_stats:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Trades Diarios", daily_stats.get('daily_trades', 0))
        
        with col2:
            daily_pnl = daily_stats.get('daily_pnl', 0)
            st.metric("PnL Diario", f"${daily_pnl:.2f}")
        
        with col3:
            st.metric("Posiciones Activas", daily_stats.get('active_positions', 0))
        
        with col4:
            st.metric("Símbolos Monitoreados", daily_stats.get('monitored_symbols', 0))
        
        # Gráfico de rendimiento (placeholder)
        st.subheader("Rendimiento del Día")
        st.info("📊 Gráficos de rendimiento en desarrollo...")
        
    else:
        st.info("No hay estadísticas disponibles. Inicia el sistema para ver datos.")

# Pestaña 4: Ejecuciones
with tab4:
    st.header("📝 Ejecuciones y Órdenes")
    
    # Botón de actualización
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 Actualizar", key="update_executions"):
            update_system_data()
    
    # Obtener datos de ejecuciones si el sistema está activo
    executions_data = {}
    if st.session_state.trading_system and st.session_state.system_running:
        try:
            status = st.session_state.trading_system.get_status()
            executions_data = status.get('executions', {})
        except Exception as e:
            st.error(f"Error obteniendo datos de ejecuciones: {e}")
    
    # Filtros para ejecuciones
    st.subheader("Filtros")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filtro por símbolo
        symbols = ["Todos"]
        if executions_data:
            symbols.extend(list(set([ex.get('symbol', '') for ex in executions_data.values() if 'symbol' in ex])))
        selected_symbol = st.selectbox("Símbolo", options=symbols)
    
    with col2:
        # Filtro por tipo de orden
        order_types = ["Todos", "BUY", "SELL"]
        selected_order_type = st.selectbox("Tipo de Orden", options=order_types)
    
    with col3:
        # Filtro por estado
        status_types = ["Todos", "Filled", "Submitted", "Cancelled", "PreSubmitted", "PendingSubmit"]
        selected_status = st.selectbox("Estado", options=status_types)
    
    # Mostrar ejecuciones
    st.subheader("Órdenes y Ejecuciones")
    
    if executions_data:
        # Filtrar datos según selecciones
        filtered_executions = []
        
        for order_id, execution in executions_data.items():
            # Aplicar filtros
            if selected_symbol != "Todos" and execution.get('symbol', '') != selected_symbol:
                continue
            if selected_order_type != "Todos" and execution.get('action', '') != selected_order_type:
                continue
            if selected_status != "Todos" and execution.get('status', '') != selected_status:
                continue
            
            # Añadir a lista filtrada
            filtered_executions.append({
                "order_id": order_id,
                **execution
            })
        
        if filtered_executions:
            # Ordenar por timestamp (más reciente primero)
            filtered_executions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Mostrar cada ejecución en un expander
            for execution in filtered_executions:
                with st.expander(f"Orden #{execution.get('order_id')} - {execution.get('symbol')} {execution.get('action')} {execution.get('quantity')} @ {execution.get('price', 'MKT')} - {execution.get('status')}"): 
                    # Detalles básicos
                    st.write(f"**Símbolo:** {execution.get('symbol')}")
                    st.write(f"**Acción:** {execution.get('action')}")
                    st.write(f"**Cantidad:** {execution.get('quantity')}")
                    st.write(f"**Precio:** {execution.get('price', 'MKT')}")
                    st.write(f"**Estado:** {execution.get('status')}")
                    st.write(f"**Timestamp:** {execution.get('timestamp')}")
                    
                    # Fills (si existen)
                    if 'fills' in execution and execution['fills']:
                        st.subheader("Ejecuciones (Fills)")
                        
                        # Crear tabla de fills
                        fill_data = []
                        for fill in execution['fills']:
                            fill_data.append({
                                "Timestamp": fill.get('time', ''),
                                "Exchange": fill.get('exchange', ''),
                                "Cantidad": fill.get('shares', ''),
                                "Precio": fill.get('price', ''),
                                "Comisión": fill.get('commission', '0.0')
                            })
                        
                        # Convertir a DataFrame y mostrar
                        if fill_data:
                            try:
                                df_fills = pd.DataFrame(fill_data)
                                # Asegurar que todo sea string
                                for col in df_fills.columns:
                                    df_fills[col] = df_fills[col].astype(str)
                                st.dataframe(df_fills, use_container_width=True, hide_index=True)
                            except Exception as e:
                                # Fallback si hay error con DataFrame
                                st.error(f"Error mostrando tabla de fills: {e}")
                                for fill in fill_data:
                                    st.write(f"{fill['Timestamp']} - {fill['Exchange']} - {fill['Cantidad']} @ {fill['Precio']} - Comisión: {fill['Comisión']}")
                    
                    # Log de la orden
                    if 'log' in execution and execution['log']:
                        st.subheader("Log de la Orden")
                        for log_entry in execution['log']:
                            status_icon = "🟢" if log_entry.get('status') == "Filled" else "🔄"
                            st.write(f"{status_icon} {log_entry.get('time', '')} - **{log_entry.get('status', '')}** - {log_entry.get('message', '')}")
        else:
            st.info("No hay ejecuciones que coincidan con los filtros seleccionados")
    else:
        st.info("No hay datos de ejecuciones disponibles")
        
        # Mostrar ejemplo de datos de ejecución para referencia
        if st.button("Mostrar ejemplo de datos de ejecución"):
            st.code("""
            {
                "57848": {
                    "symbol": "PET",
                    "action": "BUY",
                    "quantity": 6200.0,
                    "price": "MKT",
                    "status": "Filled",
                    "timestamp": "2025-07-01 18:40:08",
                    "filled_quantity": 6200.0,
                    "avg_fill_price": 0.158953,
                    "fills": [
                        {
                            "time": "2025-07-01 18:39:50",
                            "exchange": "PEARL",
                            "shares": 100.0,
                            "price": 0.16,
                            "commission": 0.1942
                        },
                        // más fills...
                    ],
                    "log": [
                        {
                            "time": "2025-07-01 18:39:49",
                            "status": "PendingSubmit",
                            "message": "",
                            "errorCode": 0
                        },
                        // más entradas de log...
                    ]
                }
            }
            """, language="json")

# Pestaña 5: Sistema
with tab5:
    st.header("Información del Sistema")
    
    # Estado de conexiones - VERSIÓN MEJORADA
    st.subheader("Estado de Conexiones")
    
    # Obtener estado real del sistema
    connection_status = get_connection_status()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**🔌 IBKR Connection:**")
        if connection_status['ibkr_connected']:
            st.success("🟢 CONECTADO")
            st.write(f"Host: {config.broker_host}")
            st.write(f"Puerto: {config.broker_port}")
            st.write(f"Client ID: {config.broker_client_id}")
            st.write(f"Posiciones: {connection_status['positions_count']}")
        else:
            st.error("🔴 DESCONECTADO")
            if system_running:
                st.warning("⚠️ Sistema ejecutándose pero IBKR desconectado")
    
    with col2:
        st.write("**🤖 Sistema de Trading:**")
        if connection_status['system_running']:
            st.success("🟢 ACTIVO")
            st.write(f"Estrategia: {config.strategy_name.upper()}")
            st.write(f"Timeframe: {config.timeframe}")
            st.write(f"Símbolos: {connection_status.get('monitored_symbols', 0)}")
            st.write(f"Última actualización: {connection_status['last_update']}")
        else:
            st.error("🔴 INACTIVO")
    
    # Indicador de estado general
    if connection_status['ibkr_connected'] and connection_status['system_running']:
        st.success("✅ Sistema completamente operativo")
    elif connection_status['system_running']:
        st.warning("⚠️ Sistema activo pero problemas de conexión")
    else:
        st.error("❌ Sistema no operativo")
        
    
    # Configuración actual - VERSIÓN SEGURA
    st.subheader("⚙️ Configuración Actual")
    
    # Mostrar configuración en formato cards
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**📈 Trading:**")
        st.write(f"• **Estrategia**: {config.strategy_name.upper()}")
        st.write(f"• **Timeframe**: {config.timeframe}")
        st.write(f"• **Máx. Posiciones**: {config.max_positions}")
        st.write(f"• **Máx. Trades Diarios**: {config.max_daily_trades}")
        
    with col2:
        st.write("**⚖️ Gestión de Riesgo:**")
        st.write(f"• **Pérdida Máx. Diaria**: ${config.max_daily_loss:.2f}")
        st.write(f"• **Filtros Activados**: {'Sí' if config.enable_filters else 'No'}")
        st.write(f"• **Puerto IBKR**: {config.broker_port}")
        st.write(f"• **Host IBKR**: {config.broker_host}")
    
    # Alternativa: Tabla simple si el usuario quiere
    if st.button("📊 Ver como tabla", key="config_table_btn"):
        try:
            config_data = [
                ["Estrategia", str(config.strategy_name.upper())],
                ["Timeframe", str(config.timeframe)],
                ["Máx. Posiciones", str(config.max_positions)],
                ["Máx. Trades Diarios", str(config.max_daily_trades)],
                ["Pérdida Máx. Diaria", f"${config.max_daily_loss:.2f}"],
                ["Filtros Activados", "Sí" if config.enable_filters else "No"],
                ["Puerto IBKR", str(config.broker_port)]
            ]
            
            df_config = pd.DataFrame(config_data, columns=["Parámetro", "Valor"])
            
            # Asegurar tipos string
            df_config["Parámetro"] = df_config["Parámetro"].astype(str)
            df_config["Valor"] = df_config["Valor"].astype(str)
            
            st.dataframe(df_config, use_container_width=True, hide_index=True)
            
        except Exception as e:
            st.error(f"Error mostrando tabla de configuración: {e}")
    
    # Logs del sistema
    st.subheader("Logs Recientes")
    
    log_file = current_dir / config.log_file
    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                logs = f.readlines()
            
            # Mostrar últimas 20 líneas
            recent_logs = logs[-20:] if len(logs) > 20 else logs
            
            for log_line in recent_logs:
                if "ERROR" in log_line:
                    st.error(log_line.strip())
                elif "WARNING" in log_line:
                    st.warning(log_line.strip())
                elif "INFO" in log_line:
                    st.info(log_line.strip())
                else:
                    st.text(log_line.strip())
        except Exception as e:
            st.error(f"Error leyendo logs: {e}")
    else:
        st.info("No hay archivo de logs disponible")

# Footer con información del sistema
st.sidebar.markdown("---")
st.sidebar.subheader("💡 Estado del Sistema")

if system_running:
    st.sidebar.success("🟢 Sistema Activo")
    st.sidebar.write(f"Símbolos: {len(st.session_state.manual_symbols)}")
    st.sidebar.write(f"Posiciones: {len(positions)}")
else:
    st.sidebar.error("🔴 Sistema Inactivo")

st.sidebar.markdown("---")
st.sidebar.caption("Trading System V2.0")
st.sidebar.caption("Arquitectura mejorada con gestión de riesgo")