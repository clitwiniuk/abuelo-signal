import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------
DB_PATH = "market_data.db"
TABLE_INTRADAY = "intraday_bars"
TABLE_DAILY = "daily_bars"
TRADES_CSV = "trades.csv"

TZ_DISPLAY_DEFAULT = "Europe/Madrid"
DIAS_CONTEXTO = 4

# ------------------------------------------------------------
# CARGA DE TRADES (ahora las horas del CSV son UTC)
# ------------------------------------------------------------
def _normalizar_columnas(df):
    mapeo = {}
    for col in df.columns:
        col_limpio = col.strip().replace(' ', '_')
        if col_limpio.lower() in ('entrytime_et', 'entrytime_es'):
            mapeo[col] = 'EntryTime'
        elif col_limpio.lower() in ('exittime_et', 'exittime_es'):
            mapeo[col] = 'ExitTime'
        elif col_limpio.lower() == 'bartime_et':
            mapeo[col] = 'EntryTime'
        elif col_limpio.lower() == 'exitprice':
            mapeo[col] = 'ExitPrice'
        elif col_limpio.lower() == 'entryprice':
            mapeo[col] = 'EntryPrice'
    if mapeo:
        df.rename(columns=mapeo, inplace=True)
    return df

# Detect timezone of time columns: ES suffix → Europe/Madrid, ET suffix → America/New_York
def _detectar_tz_csv(df_original):
    for col in df_original.columns:
        c = col.strip().lower()
        if 'entrytime_es' in c or 'exittime_es' in c:
            return 'Europe/Madrid'
    return 'America/New_York'

@st.cache_data
def cargar_trades():
    trades_raw = pd.read_csv(TRADES_CSV)
    tz_csv = _detectar_tz_csv(trades_raw)

    trades = _normalizar_columnas(trades_raw)

    # Detectar columna de hora de entrada
    col_hora_entrada = None
    if 'EntryTime' in trades.columns:
        col_hora_entrada = 'EntryTime'
    else:
        st.error("No se encontró columna de hora de entrada (EntryTime_ET, EntryTime_ES ni BarTime_ET).")
        st.stop()

    # Construir datetime y localizar en la zona del CSV, luego convertir a UTC
    fecha_hora_entrada = trades['EntryDate'].astype(str) + ' ' + trades[col_hora_entrada].astype(str)
    trades['EntryTime_UTC'] = (
        pd.to_datetime(fecha_hora_entrada, format='%Y-%m-%d %H:%M', errors='coerce')
        .dt.tz_localize(tz_csv, ambiguous='infer', nonexistent='shift_forward')
        .dt.tz_convert('UTC')
    )

    # Salida
    if 'ExitTime' in trades.columns and 'ExitPrice' in trades.columns:
        fecha_hora_salida = trades['EntryDate'].astype(str) + ' ' + trades['ExitTime'].astype(str)
        trades['ExitTime_UTC'] = (
            pd.to_datetime(fecha_hora_salida, format='%Y-%m-%d %H:%M', errors='coerce')
            .dt.tz_localize(tz_csv, ambiguous='infer', nonexistent='shift_forward')
            .dt.tz_convert('UTC')
        )
    else:
        trades['ExitTime_UTC'] = pd.NaT
        trades['ExitPrice'] = np.nan

    trades['Ganancia'] = trades['Result'].apply(lambda x: True if str(x).strip() == '✓' else False)
    return trades

# ------------------------------------------------------------
# TICKERS DISPONIBLES
# ------------------------------------------------------------
@st.cache_data
def obtener_tickers_con_datos():
    with sqlite3.connect(DB_PATH) as conn:
        tickers_intraday = pd.read_sql_query(
            f"SELECT DISTINCT symbol FROM {TABLE_INTRADAY}", conn
        )['symbol'].tolist()
    trades = cargar_trades()
    tickers_trades = trades['Symbol'].unique().tolist()
    return sorted(set(tickers_intraday) & set(tickers_trades))

# ------------------------------------------------------------
# CARGA DE BARRAS
# ------------------------------------------------------------
def cargar_intraday_dia(symbol, fecha_utc_str):
    with sqlite3.connect(DB_PATH) as conn:
        query = f"""
            SELECT bar_timestamp, open, high, low, close, volume
            FROM {TABLE_INTRADAY}
            WHERE symbol = ? AND bar_timestamp >= ? AND bar_timestamp < ?
            ORDER BY bar_timestamp
        """
        inicio = fecha_utc_str + 'T00:00:00+00:00'
        fin    = fecha_utc_str + 'T23:59:59+00:00'
        df = pd.read_sql_query(query, conn, params=(symbol, inicio, fin))
    df['bar_timestamp'] = pd.to_datetime(df['bar_timestamp'], utc=True)
    return df

def cargar_diarias_contexto(symbol, burst_date_str, num_dias=DIAS_CONTEXTO):
    with sqlite3.connect(DB_PATH) as conn:
        query = f"""
            SELECT trading_date, open, high, low, close, volume
            FROM {TABLE_DAILY}
            WHERE symbol = ? AND trading_date >= ?
            ORDER BY trading_date
        """
        df = pd.read_sql_query(query, conn, params=(symbol, burst_date_str))
    df = df.head(num_dias + 1)
    df['trading_date'] = pd.to_datetime(df['trading_date'])
    return df

# ------------------------------------------------------------
# INTERFAZ
# ------------------------------------------------------------
st.set_page_config(layout="wide")
st.title("📊 Analizador de Operaciones – Diario + Intradía")

st.sidebar.header("⚙️ Configuración")

tz_display = st.sidebar.selectbox(
    "Zona horaria",
    options=["Europe/Madrid", "America/New_York", "Europe/London", "Europe/Berlin", "Asia/Tokyo"],
    index=0
)

tickers_validos = obtener_tickers_con_datos()
if not tickers_validos:
    st.error("No hay símbolos comunes.")
    st.stop()

symbol = st.sidebar.selectbox("Símbolo", tickers_validos)

trades = cargar_trades()
ops_simbolo = trades[trades['Symbol'] == symbol].copy()

if ops_simbolo.empty:
    st.warning(f"No hay operaciones para {symbol}")
    st.stop()

# Opciones del desplegable (hora ya en la zona de visualización)
ops_simbolo['Opcion'] = ops_simbolo.apply(
    lambda r: f"#{r['TN']} | Entrada: {r['EntryDate']} {pd.Timestamp(r['EntryTime_UTC']).tz_convert(tz_display).strftime('%H:%M') if pd.notna(r['EntryTime_UTC']) else '??'} | Burst: {r['BurstDate']} | {'✓' if r['Ganancia'] else '✗'} PnL: {r['PnL$']}$",
    axis=1
)
opcion_seleccionada = st.sidebar.selectbox("Selecciona una operación", ops_simbolo['Opcion'].tolist())

idx = ops_simbolo[ops_simbolo['Opcion'] == opcion_seleccionada].index[0]
trade = ops_simbolo.loc[idx]

entry_date = trade['EntryDate']
burst_date = trade['BurstDate']

st.sidebar.markdown(f"**Entrada:** {entry_date}  \n**Burst:** {burst_date}")

# ------------------------------------------------------------
# CARGA DE DATOS
# ------------------------------------------------------------
daily_bars = cargar_diarias_contexto(symbol, burst_date, DIAS_CONTEXTO)
entry_date_utc = pd.Timestamp(entry_date).strftime('%Y-%m-%d')
intra_bars = cargar_intraday_dia(symbol, entry_date_utc)
ops_del_dia = ops_simbolo[ops_simbolo['EntryDate'] == entry_date].copy()

# ------------------------------------------------------------
# PREPARACIÓN DE TIMESTAMPS PARA VISUALIZACIÓN
# ------------------------------------------------------------
if not intra_bars.empty:
    intra_bars['bar_timestamp'] = intra_bars['bar_timestamp'].dt.tz_convert(tz_display)
    intra_bars['typical_price'] = (intra_bars['high'] + intra_bars['low'] + intra_bars['close']) / 3
    intra_bars['cum_pv'] = (intra_bars['typical_price'] * intra_bars['volume']).cumsum()
    intra_bars['cum_vol'] = intra_bars['volume'].cumsum()
    intra_bars['vwap'] = intra_bars['cum_pv'] / intra_bars['cum_vol']

if not ops_del_dia.empty:
    # Convertir UTC -> zona display
    ops_del_dia['EntryTime_display'] = ops_del_dia['EntryTime_UTC'].dt.tz_convert(tz_display)
    if 'ExitTime_UTC' in ops_del_dia.columns:
        # Algunos pueden ser NaT, convertir solo los válidos
        mask = ops_del_dia['ExitTime_UTC'].notna()
        ops_del_dia['ExitTime_UTC'] = pd.to_datetime(ops_del_dia['ExitTime_UTC'], utc=True)
        ops_del_dia['ExitTime_display'] = ops_del_dia['ExitTime_UTC'].dt.tz_convert(tz_display)
        ops_del_dia.loc[~mask, 'ExitTime_display'] = pd.NaT
    else:
        ops_del_dia['ExitTime_display'] = pd.NaT

# ------------------------------------------------------------
# LAYOUT
# ------------------------------------------------------------
col_izq, col_der = st.columns([0.4, 0.6])

with col_izq:
    st.subheader(f"📆 Diario – {symbol} (Burst +{DIAS_CONTEXTO} días)")
    if daily_bars.empty:
        st.warning("No hay datos diarios.")
    else:
        fig_diario = go.Figure()
        fig_diario.add_trace(go.Candlestick(
            x=daily_bars['trading_date'],
            open=daily_bars['open'], high=daily_bars['high'],
            low=daily_bars['low'], close=daily_bars['close'],
            increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
        ))
        fig_diario.add_vrect(
            x0=pd.Timestamp(burst_date), x1=pd.Timestamp(burst_date) + timedelta(days=1),
            fillcolor="yellow", opacity=0.2, line_width=0
        )
        if entry_date != burst_date:
            fig_diario.add_vrect(
                x0=pd.Timestamp(entry_date), x1=pd.Timestamp(entry_date) + timedelta(days=1),
                fillcolor="orange", opacity=0.2, line_width=0
            )
        fig_diario.update_layout(height=500, margin=dict(l=20, r=20, t=30, b=20), hovermode='x')
        st.plotly_chart(fig_diario, use_container_width=True, config={'scrollZoom': True})

with col_der:
    st.subheader(f"⏱️ Intradía {entry_date} ({tz_display})")
    if intra_bars.empty:
        st.warning(f"No hay barras intradía para {symbol} el {entry_date}")
    else:
        fig_intra = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.7, 0.3], subplot_titles=(f"{symbol} {entry_date}", "Volumen")
        )

        fig_intra.add_trace(go.Candlestick(
            x=intra_bars['bar_timestamp'], open=intra_bars['open'], high=intra_bars['high'],
            low=intra_bars['low'], close=intra_bars['close'],
            increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
        ), row=1, col=1)

        fig_intra.add_trace(go.Scatter(
            x=intra_bars['bar_timestamp'], y=intra_bars['vwap'], mode='lines',
            line=dict(color='orange', width=1.5), name='VWAP'
        ), row=1, col=1)

        for _, op in ops_del_dia.iterrows():
            es_seleccionada = (op['TN'] == trade['TN'])
            color = 'green' if op['Ganancia'] else 'red'
            size = 12 if es_seleccionada else 8

            ent_simbolo = 'triangle-down' if op['Ganancia'] else 'triangle-up'
            fig_intra.add_trace(go.Scatter(
                x=[op['EntryTime_display']], y=[op['EntryPrice']],
                mode='markers+text' if es_seleccionada else 'markers',
                marker=dict(color=color, size=size, symbol=ent_simbolo),
                text=f"#{op['TN']} E {op['EntryPrice']:.2f}" if es_seleccionada else None,
                textposition="top center", showlegend=False,
                hovertemplate=f"<b>Op #{op['TN']} ENTRADA</b><br>Precio: {op['EntryPrice']:.4f}<br>Hora: %{{x|%H:%M:%S}}<br>PnL: {op['PnL$']} $<br>MFE: {op['MFE%']}%<br>MAE: {op['MAE%']}%<extra></extra>"
            ), row=1, col=1)

            if pd.notna(op.get('ExitTime_display')) and pd.notna(op.get('ExitPrice')):
                fig_intra.add_trace(go.Scatter(
                    x=[op['ExitTime_display']], y=[op['ExitPrice']],
                    mode='markers+text' if es_seleccionada else 'markers',
                    marker=dict(color=color, size=size, symbol='circle'),
                    text=f"#{op['TN']} X {op['ExitPrice']:.2f}" if es_seleccionada else None,
                    textposition="top center", showlegend=False,
                    hovertemplate=f"<b>Op #{op['TN']} SALIDA</b><br>Precio: {op['ExitPrice']:.4f}<br>Hora: %{{x|%H:%M:%S}}<br>Tipo: {op.get('Exit', '')}<extra></extra>"
                ), row=1, col=1)

        colores_vol = ['#26a69a' if c >= o else '#ef5350' for c, o in zip(intra_bars['close'], intra_bars['open'])]
        fig_intra.add_trace(go.Bar(
            x=intra_bars['bar_timestamp'], y=intra_bars['volume'],
            marker_color=colores_vol, showlegend=False, hovertemplate='Vol: %{y}'
        ), row=2, col=1)

        fig_intra.update_layout(height=600, margin=dict(l=20, r=20, t=40, b=20),
                                hovermode='x unified', xaxis_rangeslider_visible=False)
        fig_intra.update_xaxes(title_text="Hora", row=2, col=1)
        fig_intra.update_yaxes(title_text="Precio", row=1, col=1)
        fig_intra.update_yaxes(title_text="Volumen", row=2, col=1)

        st.plotly_chart(fig_intra, use_container_width=True, config={'scrollZoom': True})

    st.subheader("🧾 Operaciones de este día")
    if not ops_del_dia.empty:
        ops_del_dia['Hora_Entrada'] = ops_del_dia['EntryTime_display'].dt.strftime('%H:%M:%S')
        ops_del_dia['Hora_Salida'] = ops_del_dia['ExitTime_display'].apply(lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '')
        cols_mostrar = ['TN', 'Hora_Entrada', 'EntryPrice', 'Hora_Salida', 'ExitPrice', 'Result', 'PnL$', 'MFE%', 'MAE%', 'Exit', 'Quality']
        cols_existentes = [c for c in cols_mostrar if c in ops_del_dia.columns]
        st.dataframe(ops_del_dia[cols_existentes].sort_values('Hora_Entrada'), use_container_width=True)
    else:
        st.info("Ninguna operación este día.")