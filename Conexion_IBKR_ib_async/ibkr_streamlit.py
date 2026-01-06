import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import logging
from datetime import datetime
import streamlit as st
from ib_async import IB, Contract, Order, util

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('IBKR Streamlit App')

class TradingApp:
    def __init__(self):
        self.ib = None
        self.connected = False
        self.current_contract = None
        
        # Inicializar el bucle de eventos una sola vez
        try:
            self.loop = asyncio.get_event_loop()
        except:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        
        # Configuración de conexión
        self.host = '127.0.0.1'
        self.port = 7497
        self.client_id = 1

    async def connect(self):
        """Establece conexión con TWS/IB Gateway."""
        try:
            if self.ib is None:
                self.ib = IB()
                
            if not self.ib.isConnected():
                await self.ib.connect(self.host, self.port, self.client_id)
                self.connected = True
                logger.info("Conectado a IBKR")
                return True
            return True
            
        except Exception as e:
            logger.error(f"Error al conectar: {str(e)}")
            self.connected = False
            return False

    async def disconnect(self):
        """Cierra la conexión con IBKR."""
        if self.ib and self.ib.isConnected():
            await self.ib.disconnect()
            self.connected = False
            logger.info("Desconectado de IBKR")

    async def search_contract(self, symbol: str):
        """Busca y califica un contrato."""
        try:
            contract = Contract(symbol=symbol, secType='STK', exchange='NASDAQ', currency='USD')
            qualified = await self.ib.qualifyContracts(contract)
            if qualified:
                self.current_contract = qualified[0]
                logger.info(f"Contrato encontrado: {self.current_contract}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error al buscar contrato: {str(e)}")
            return False

    async def get_market_data(self):
        """Obtiene datos de mercado."""
        if not self.current_contract:
            return None
            
        try:
            ticker = await self.ib.reqMktData(self.current_contract)
            await asyncio.sleep(1)  # Esperar datos
            return {
                'bid': ticker.bid,
                'ask': ticker.ask,
                'last': ticker.last,
                'time': datetime.now().strftime('%H:%M:%S')
            }
        except Exception as e:
            logger.error(f"Error obteniendo datos: {str(e)}")
            return None

    async def place_order(self, action, quantity, order_type='MKT', limit_price=None):
        """Envía una orden."""
        try:
            order = Order()
            order.action = action.upper()
            order.totalQuantity = quantity
            order.orderType = order_type.upper()
            
            if order_type.upper() == 'LMT':
                order.lmtPrice = limit_price
                
            trade = await self.ib.placeOrder(self.current_contract, order)
            logger.info(f"Orden enviada: {trade}")
            return trade
        except Exception as e:
            logger.error(f"Error enviando orden: {str(e)}")
            return None

# Configuración de Streamlit
st.title("IBKR Trading App con Streamlit")

# Inicializar la aplicación en el estado de sesión
if 'app' not in st.session_state:
    st.session_state.app = TradingApp()
    st.session_state.connected = False

# UI de Conexión
col1, col2 = st.columns(2)
with col1:
    if st.button("Conectar a IBKR") and not st.session_state.connected:
        try:
            # Ejecutar en el bucle de eventos
            result = asyncio.run_coroutine_threadsafe(
                st.session_state.app.connect(),
                st.session_state.app.loop
            ).result()
            
            if result:
                st.session_state.connected = True
                st.success("Conectado!")
            else:
                st.error("Error al conectar")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

with col2:
    if st.button("Desconectar") and st.session_state.connected:
        try:
            asyncio.run_coroutine_threadsafe(
                st.session_state.app.disconnect(),
                st.session_state.app.loop
            ).result()
            st.session_state.connected = False
            st.success("Desconectado!")
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Buscar contrato
symbol = st.text_input("Símbolo (ej. AAPL):", "AAPL")
if st.button("Buscar Contrato") and st.session_state.connected:
    try:
        result = asyncio.run_coroutine_threadsafe(
            st.session_state.app.search_contract(symbol),
            st.session_state.app.loop
        ).result()
        
        if result:
            st.success(f"Contrato para {symbol} encontrado!")
        else:
            st.error("Contrato no encontrado")
    except Exception as e:
        st.error(f"Error: {str(e)}")

# Datos de mercado
if st.button("Obtener Datos") and st.session_state.connected and st.session_state.app.current_contract:
    try:
        data = asyncio.run_coroutine_threadsafe(
            st.session_state.app.get_market_data(),
            st.session_state.app.loop
        ).result()
        
        if data:
            st.write("Último precio:", data['last'])
            st.write("Bid/Ask:", f"{data['bid']}/{data['ask']}")
    except Exception as e:
        st.error(f"Error: {str(e)}")

# Panel de trading
st.subheader("Enviar Orden")
if st.session_state.connected and st.session_state.app.current_contract:
    action = st.selectbox("Acción", ["BUY", "SELL"])
    quantity = st.number_input("Cantidad", min_value=1, value=100)
    order_type = st.selectbox("Tipo de Orden", ["MKT", "LMT"])
    
    limit_price = None
    if order_type == "LMT":
        limit_price = st.number_input("Precio Límite", min_value=0.01, value=100.0)
    
    if st.button("Enviar Orden"):
        try:
            trade = asyncio.run_coroutine_threadsafe(
                st.session_state.app.place_order(action, quantity, order_type, limit_price),
                st.session_state.app.loop
            ).result()
            
            if trade:
                st.success("Orden enviada correctamente!")
            else:
                st.error("Error al enviar orden")
        except Exception as e:
            st.error(f"Error: {str(e)}")