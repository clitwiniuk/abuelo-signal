"""
Módulo para conexión con Interactive Brokers API
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
from typing import Optional, List, Dict, Tuple
import streamlit as st
import socket
import threading

# Intentar importar IBKR API
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.ticktype import TickTypeEnum, TickTypeEnum
    from ibapi.common import *
    from ibapi.utils import iswrapper
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    st.warning("IBKR API no disponible. Instala con: pip install ibapi")

class IBKRApp(EWrapper, EClient):
    """Cliente de Interactive Brokers para obtener datos de mercado"""
    
    def __init__(self, client_id: int, port: int):
        EClient.__init__(self, self)
        self.client_id = client_id
        self.port = port
        self.connected = False
        self.error_messages = []
        self.connection_event = threading.Event()
        
        # Datos de mercado
        self.historical_data = []
        self.received_data = False
        self.data_lock = threading.Lock()
        
    @iswrapper
    def error(self, reqId, errorCode, errorString):
        """Manejar errores de IBKR"""
        error_msg = f"Error {reqId}: {errorCode} - {errorString}"
        self.error_messages.append(error_msg)
        logging.error(f"IBKR Error: {error_msg}")
        
        # Error específico de conexión
        if errorCode in [502, 503, 504]:  # Connection errors
            self.connected = False
        elif errorCode == 200:  # No security definition
            logging.warning(f"No security definition for reqId {reqId}")
        elif errorCode == 162:  # Historical market data Service error
            logging.warning(f"Historical data error for reqId {reqId}")
            
    @iswrapper
    def connectAck(self):
        """Confirmación de conexión"""
        self.connected = True
        self.connection_event.set()
        logging.info(f"Conectado a IBKR con client_id {self.client_id}")
        
    @iswrapper
    def nextValidId(self, orderId):
        """ID válido recibido - conexión completa"""
        self.connected = True
        self.connection_event.set()
        logging.info(f"Conexión IBKR establecida con orderId {orderId}")
        
    @iswrapper
    def disconnect(self):
        """Desconexión"""
        self.connected = False
        self.connection_event.clear()
        logging.info(f"Desconectado de IBKR")
        
    @iswrapper
    def historicalData(self, reqId, bar):
        """Recibir datos históricos"""
        with self.data_lock:
            self.historical_data.append({
                'date': pd.to_datetime(bar.date),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            })
            self.received_data = True
            
    @iswrapper
    def historicalDataEnd(self, reqId, start, end):
        """Fin de datos históricos"""
        logging.info(f"Datos históricos completados para reqId {reqId}")

def check_port_available(port: int) -> bool:
    """Verificar si un puerto está disponible para conexión"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except:
        return False

class IBKRConnection:
    """Gestor de conexiones múltiples a IBKR"""
    
    def __init__(self):
        self.connections = []
        self.current_connection = 0
        self.max_connections = 3
        
        # Configuración actualizada de puertos y client IDs
        self.configs = [
            {'client_id': 5001, 'port': 7497},    # Puerto estándar TWS
            {'client_id': 6031, 'port': 4001},    # Puerto alternativo
            {'client_id': 6004, 'port': 4002},    # Puerto alternativo
            {'client_id': 5001, 'port': 63813},   # Tus puertos personalizados
            {'client_id': 6031, 'port': 63824},
            {'client_id': 6004, 'port': 63832},
        ]
        
    def check_tws_running(self) -> bool:
        """Verificar si TWS/Gateway está corriendo"""
        available_ports = []
        for config in self.configs:
            if check_port_available(config['port']):
                available_ports.append(config['port'])
        
        if available_ports:
            st.info(f"🔌 Puertos TWS detectados: {available_ports}")
            return True
        else:
            st.warning("⚠️ No se detectó TWS/Gateway corriendo en los puertos configurados")
            st.info("💡 Asegúrate que TWS o Gateway esté corriendo y API habilitada")
            return False
        
    def connect(self) -> bool:
        """Conectar a IBKR usando múltiples configuraciones"""
        if not IBKR_AVAILABLE:
            st.error("❌ IBKR API no instalada. Ejecuta: pip install ibapi")
            return False
            
        # Primero verificar si TWS está corriendo
        if not self.check_tws_running():
            return False
            
        for config in self.configs:
            try:
                # Verificar puerto disponible
                if not check_port_available(config['port']):
                    logging.info(f"Puerto {config['port']} no disponible, intentando siguiente...")
                    continue
                
                app = IBKRApp(config['client_id'], config['port'])
                
                # Intentar conexión
                logging.info(f"Intentando conectar a puerto {config['port']} con client_id {config['client_id']}")
                app.connect("127.0.0.1", config['port'], config['client_id'])
                
                # Iniciar thread
                thread = threading.Thread(target=lambda: app.run())
                thread.daemon = True
                thread.start()
                
                # Esperar conexión con timeout
                if app.connection_event.wait(timeout=10):
                    if app.connected:
                        self.connections.append(app)
                        logging.info(f"✅ Conectado: client_id {config['client_id']}, port {config['port']}")
                        return True
                    else:
                        app.disconnect()
                else:
                    logging.warning(f"Timeout conectando a puerto {config['port']}")
                    app.disconnect()
                    
            except Exception as e:
                logging.error(f"Error conectando con client_id {config['client_id']}, port {config['port']}: {e}")
                continue
                
        return False
    
    def get_connection(self) -> Optional[IBKRApp]:
        """Obtener una conexión disponible"""
        if not self.connections:
            return None
            
        # Rotar entre conexiones para balancear carga
        conn = self.connections[self.current_connection]
        self.current_connection = (self.current_connection + 1) % len(self.connections)
        
        return conn if conn.connected else None
    
    def disconnect_all(self):
        """Desconectar todas las conexiones"""
        for conn in self.connections:
            if conn.connected:
                conn.disconnect()
        self.connections.clear()

# Instancia global de IBKR
ibkr_manager = IBKRConnection()

def create_stock_contract(symbol: str) -> Contract:
    """Crear contrato para stock"""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"
    contract.currency = "USD"
    contract.exchange = "SMART"
    contract.primaryExchange = "NASDAQ"  # Para small caps
    return contract

def get_ibkr_historical_data(symbol: str, duration: str = "5 D", bar_size: str = "1 min") -> Optional[pd.DataFrame]:
    """
    Obtener datos históricos de IBKR
    
    Args:
        symbol: Símbolo del stock
        duration: Duración (ej: "5 D", "1 M", "1 Y")
        bar_size: Tamaño de barra (ej: "1 min", "5 mins", "1 hour", "1 day")
    
    Returns:
        DataFrame con datos OHLCV
    """
    if not IBKR_AVAILABLE:
        return None
        
    # Obtener conexión disponible
    app = ibkr_manager.get_connection()
    if not app:
        return None
    
    try:
        # Crear contrato
        contract = create_stock_contract(symbol)
        
        # Limpiar datos anteriores
        with app.data_lock:
            app.historical_data.clear()
            app.received_data = False
        
        # Solicitar datos históricos
        reqId = int(time.time()) % 1000000  # ID único
        app.reqHistoricalData(
            reqId,
            contract,
            "",
            duration,
            bar_size,
            "TRADES",
            1,
            1,
            False,
            []
        )
        
        # Esperar datos
        timeout = 15  # 15 segundos máximo
        start_time = time.time()
        
        while not app.received_data and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        # Procesar datos recibidos
        with app.data_lock:
            if app.historical_data:
                df = pd.DataFrame(app.historical_data)
                df.set_index('date', inplace=True)
                df.sort_index(inplace=True)
                
                # Calcular indicadores adicionales
                df['vwap'] = calculate_vwap(df)
                df['volume_sma'] = df['volume'].rolling(window=20).mean()
                
                return df
            else:
                return None
                
    except Exception as e:
        logging.error(f"Error obteniendo datos de IBKR para {symbol}: {e}")
        return None

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calcular VWAP"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    return vwap

def initialize_ibkr() -> bool:
    """Inicializar conexión a IBKR"""
    if not IBKR_AVAILABLE:
        st.warning("IBKR API no está disponible. Instala con: pip install ibapi")
        return False
    
    with st.spinner("🔌 Conectando a IBKR..."):
        success = ibkr_manager.connect()
        if success:
            st.success(f"✅ Conectado a IBKR ({len(ibkr_manager.connections)} conexiones)")
        else:
            st.error("❌ No se pudo conectar a IBKR")
            st.info("📝 Requisitos:")
            st.info("1. TWS o Gateway corriendo")
            st.info("2. API Connections habilitado")
            st.info("3. Puertos configurados (7497, 4001, 4002, 63813, 63824, 63832)")
    
    return success

def cleanup_ibkr():
    """Limpiar conexiones IBKR"""
    ibkr_manager.disconnect_all()

# Mapeo de timeframes de Streamlit a IBKR
TIMEFRAME_MAP = {
    "1m": ("5 D", "1 min"),
    "5m": ("5 D", "5 mins"),
    "15m": ("5 D", "15 mins"),
    "1h": ("1 M", "1 hour"),
    "1d": ("1 Y", "1 day")
}

def get_stock_data_ibkr(symbol: str, timeframe: str = "5m") -> Optional[pd.DataFrame]:
    """
    Obtener datos de IBKR con mapeo de timeframe
    
    Args:
        symbol: Símbolo del stock
        timeframe: Timeframe ("1m", "5m", "15m", "1h", "1d")
    
    Returns:
        DataFrame con datos OHLCV
    """
    if not IBKR_AVAILABLE or not ibkr_manager.connections:
        return None
    
    duration, bar_size = TIMEFRAME_MAP.get(timeframe, ("5 D", "5 mins"))
    return get_ibkr_historical_data(symbol, duration, bar_size)
