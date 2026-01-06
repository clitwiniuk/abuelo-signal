import streamlit as st
from ibapi_simple_client import IBKRClient

st.set_page_config(page_title="Test IBKR API", layout="centered")
st.title("Test IBKR Order Execution (ibapi)")

ticker = st.text_input("Ticker", value="AAPL")
qty = st.number_input("Cantidad", min_value=1, step=1)
order_type = st.selectbox("Tipo de orden", ["MKT", "LMT"])
price = None
if order_type == "LMT":
    price = st.number_input("Precio límite", min_value=0.0, step=0.01)
action = st.selectbox("Acción", ["BUY", "SELL"])

if "ibkr" not in st.session_state:
    st.session_state["ibkr"] = None

if st.button("Conectar IBKR"):
    st.session_state["ibkr"] = IBKRClient()
    st.success("Conectado a IBKR (TWS/IB Gateway)")

if st.session_state["ibkr"]:
    if st.button("Enviar orden"):
        try:
            st.session_state["ibkr"].place_simple_order(
                symbol=ticker,
                qty=qty,
                action=action,
                order_type=order_type,
                price=price if order_type == "LMT" else None
            )
            st.success(f"Orden enviada: {action} {qty} {ticker} ({order_type}{' @'+str(price) if order_type=='LMT' else ''})")
        except Exception as e:
            st.error(f"Error enviando orden: {e}")
    # Mostrar estado de la última orden
    last_status = st.session_state["ibkr"].get_last_order_status()
    if last_status:
        st.info(f"Última orden: ID={last_status['order_id']} | Estado={last_status['status']} | Filled={last_status['filled']} | Remaining={last_status['remaining']} | Precio Medio={last_status['avgFillPrice']}")
    else:
        st.info("No hay estado de orden disponible.")

st.write("---\nDebes tener TWS o IB Gateway abierto y aceptar conexiones API (puerto 7497 por defecto).")
