# app.py
import streamlit as st
from ib_client import IBKRConnection
import pandas as pd

st.set_page_config(page_title="IBKR Trading App", layout="centered")
st.title("IBKR Trading Interface")

# Sidebar para configuración
import os
from configparser import ConfigParser

def cargar_credenciales_desde_config():
    config_path = os.path.join("config", "config.ini")
    config = ConfigParser()
    if os.path.exists(config_path):
        config.read(config_path)
        if config.has_section('main'):
            return (
                config.get('main', 'REGULAR_USERNAME', fallback=''),
                config.get('main', 'REGULAR_ACCOUNT', fallback='')
            )
    return ('', '')

with st.sidebar:
    st.header("Configuración de conexión")
    usar_config = st.checkbox("Usar credenciales de config.ini", value=True)
    username = ''
    account = ''
    if usar_config:
        username, account = cargar_credenciales_desde_config()
        st.info('Cargando usuario y cuenta desde config.ini')
    username = st.text_input("Usuario IBKR", value=username)
    account = st.text_input("Cuenta IBKR", value=account)

    col1, col2 = st.columns(2)
    with col1:
        conectar = st.button("Conectar IBKR")
    with col2:
        desconectar = st.button("Desconectar")

    if conectar:
        st.session_state['conectando'] = True
        st.session_state['conexion_error'] = ''
        try:
            st.session_state['ibkr'] = IBKRConnection(username, account)
            st.session_state['conectado'] = True
            st.session_state['conectando'] = False
            st.success("Conectado a IBKR")
        except Exception as e:
            st.session_state['conectado'] = False
            st.session_state['conectando'] = False
            st.session_state['conexion_error'] = str(e)
            st.error(f"Error al conectar: {e}")
    if desconectar:
        st.session_state['ibkr'] = None
        st.session_state['conectado'] = False
        st.session_state['conectando'] = False
        st.session_state['conexion_error'] = ''
        st.success("Desconectado.")

# Feedback de conexión en la UI principal
if st.session_state.get('conectando', False):
    st.info("Conectando a IBKR...")
elif st.session_state.get('conexion_error', ''):
    st.error(f"Error al conectar: {st.session_state['conexion_error']}")
elif st.session_state.get('conectado', False) and st.session_state.get('ibkr', None):
    ibkr = st.session_state['ibkr']
    st.success("Conectado a IBKR")
    st.subheader("Datos de cuenta")
    st.write(ibkr.get_account_data())

    st.subheader("Precio de mercado")
    symbol = st.text_input("Ticker", value="AAPL")
    if st.button("Consultar precio"):
        precio = ibkr.get_market_price(symbol)
        st.write(f"Precio de {symbol}: {precio}")

    st.subheader("Enviar orden")
    qty = st.number_input("Cantidad", min_value=1, step=1)
    action = st.selectbox("Acción", ["BUY", "SELL"])
    order_type = st.selectbox(
        "Tipo de orden",
        ["MKT", "LMT", "STP", "STP LMT", "TRAIL"]
    )

    price = None
    stop_price = None
    trailing_amount = None

    if order_type == "LMT":
        price = st.number_input("Precio límite", min_value=0.0, step=0.01)
    elif order_type == "STP":
        stop_price = st.number_input("Precio Stop", min_value=0.0, step=0.01)
    elif order_type == "STP LMT":
        stop_price = st.number_input("Precio Stop", min_value=0.0, step=0.01)
        price = st.number_input("Precio límite", min_value=0.0, step=0.01)
    elif order_type == "TRAIL":
        trailing_amount = st.number_input("Trailing Amount", min_value=0.01, step=0.01)

    if st.button("Enviar orden"):
        # Prepara los argumentos según el tipo de orden
        extra_kwargs = {}
        if order_type == "LMT":
            extra_kwargs['price'] = price
        elif order_type == "STP":
            extra_kwargs['stop_price'] = stop_price
        elif order_type == "STP LMT":
            extra_kwargs['stop_price'] = stop_price
            extra_kwargs['price'] = price
        elif order_type == "TRAIL":
            extra_kwargs['trailing_amount'] = trailing_amount
        try:
            resultado = ibkr.place_order(
                symbol, qty, action, order_type,
                **extra_kwargs
            )
            st.write("Resultado orden:", resultado)
        except Exception as e:
            st.error(f"Error al enviar orden: {e}")

    st.subheader("Datos Históricos")
    try:
        hist_data = ibkr.get_historical_data(symbol)
        if not hist_data.empty:
            st.dataframe(hist_data)
        else:
            st.warning("No se encontraron datos históricos.")
    except Exception as e:
        st.error(f"Error al obtener datos históricos: {str(e)}")
else:
    st.info("Introduce tus credenciales y conecta para comenzar a operar.")

# Refrescar cada 10 segundos
st.rerun()
