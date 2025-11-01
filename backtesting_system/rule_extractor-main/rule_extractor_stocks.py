#!/usr/bin/env python
# coding: utf-8

# Rule Extractor adaptado para datos de stocks desde market_data.db
# Eliminados los pips, agregados retornos absolutos y porcentuales

# Librerías de manejo de datos
import pandas as pd
import numpy as np
import sqlite3

# Configuración de pandas para mejor visualización
pd.set_option('display.max_columns', 100)
pd.set_option('display.float_format', lambda x: '%.7f' % x)

# Librerías de análisis técnico y estadística
import talib as ta
from scipy.stats import pointbiserialr
from sklearn.feature_selection import mutual_info_regression

# Librerías de paralelización y optimización
import joblib
from joblib import Parallel, delayed, parallel_backend
# import cupy as cp  # Opcional para GPU, comentado si no está disponible

# Manejo de fechas y tiempo
import time
from datetime import datetime

# Librerías de bases de datos y almacenamiento
import os
import pickle
import hashlib

# Utilidades varias
import uuid
import itertools
import re
import gc
from tqdm import tqdm
from itertools import groupby

def transform_df_stock(symbol, db_path='../market_data.db', exposicion_dias=3,
                      threshold_pct=1.5, threshold_abs=0.05, short=False, date_column='DateTime'):
    """
    Función transform_df adaptada para stocks desde market_data.db
    - Elimina cálculo de pips
    - Agrega retornos absolutos (en precio) y porcentuales
    - Carga datos desde SQLite en lugar de CSV
    """

    # Conectar a la base de datos y cargar datos
    db_path_full = os.path.abspath(db_path)
    conn = sqlite3.connect(db_path_full)

    query = f"""
    SELECT bar_timestamp as DateTime,
           open_price as Open,
           high_price as High,
           low_price as Low,
           close_price as Close,
           volume as Volume
    FROM intraday_bars
    WHERE symbol = '{symbol}'
    ORDER BY bar_timestamp
    """

    df = pd.read_sql(query, conn)
    conn.close()

    # Verificar que hay datos
    if df.empty:
        print(f"No se encontraron datos para el símbolo {symbol}")
        return pd.DataFrame()

    print(f"Cargados {len(df)} registros para {symbol}")

    # Agregar columnas de tiempo para filtrar horas de mercado
    df['hour'] = pd.to_datetime(df[date_column]).dt.hour
    df['minute'] = pd.to_datetime(df[date_column]).dt.minute

    # Polygon.io data está en UTC. Mercado regular: 9:30 AM - 4:00 PM ET = 13:30 - 20:00 UTC
    # NOTA: Ajustar según zona horaria correcta si es necesario
    df['market_hours'] = (
        ((df['hour'] == 13) & (df['minute'] >= 30)) |  # 13:30 - 13:59 UTC (9:30-9:59 ET)
        ((df['hour'] >= 14) & (df['hour'] < 20)) |     # 14:00 - 19:59 UTC (10:00-15:59 ET)
        ((df['hour'] == 20) & (df['minute'] == 0))      # 20:00 UTC exactamente (16:00 ET)
    )

    print(f"Datos en horas de mercado: {df['market_hours'].sum()} de {len(df)}")

    # Calcular indicadores técnicos (OPTIMIZADO - reducir número de indicadores)

    # RSI - reducir períodos
    def rsi_function(i):
        rsi = ta.RSI(df['Close'], timeperiod=i)
        return pd.DataFrame(rsi, columns=[f'rsi_{i}'])

    rsi_periods = [2, 5, 10, 14, 20, 30]  # Reducido de 25 a 6 períodos
    rsi_dfs = pd.concat([rsi_function(i) for i in rsi_periods], axis=1)
    df = pd.concat([df, rsi_dfs], axis=1)
    del rsi_dfs
    gc.collect()

    # ADX - reducir períodos
    def adx_function(i):
        adx = ta.ADX(df['High'], df['Low'], df['Close'], timeperiod=i)
        return pd.DataFrame(adx, columns=[f'adx_{i}'])

    adx_periods = [5, 10, 14, 20, 30]  # Reducido de 25 a 5 períodos
    adx_dfs = pd.concat([adx_function(i) for i in adx_periods], axis=1)
    df = pd.concat([df, adx_dfs], axis=1)
    del adx_dfs
    gc.collect()

    # DI+ y DI- - reducir períodos
    def plus_di_function(i):
        plus_di = ta.PLUS_DI(df['High'], df['Low'], df['Close'], timeperiod=i)
        return pd.DataFrame(plus_di, columns=[f'plus_di_{i}'])

    def minus_di_function(i):
        minus_di = ta.MINUS_DI(df['High'], df['Low'], df['Close'], timeperiod=i)
        return pd.DataFrame(minus_di, columns=[f'minus_di_{i}'])

    di_periods = [5, 10, 14, 20, 30]  # Reducido
    plus_di_dfs = pd.concat([plus_di_function(i) for i in di_periods], axis=1)
    minus_di_dfs = pd.concat([minus_di_function(i) for i in di_periods], axis=1)
    df = pd.concat([df, plus_di_dfs, minus_di_dfs], axis=1)
    del plus_di_dfs, minus_di_dfs
    gc.collect()

    # Williams %R - reducir períodos
    def willr_function(i):
        willr = ta.WILLR(df['High'], df['Low'], df['Close'], timeperiod=i)
        return pd.DataFrame(willr, columns=[f'willr_{i}'])

    willr_periods = [5, 10, 14, 20, 30]  # Reducido
    willr_dfs = pd.concat([willr_function(i) for i in willr_periods], axis=1)
    df = pd.concat([df, willr_dfs], axis=1)
    del willr_dfs
    gc.collect()

    # Medias móviles - reducir drásticamente
    def ma_function(i):
        ma = ta.MA(df['Close'], timeperiod=i, matype=0)
        return pd.DataFrame(ma, columns=[f'sma_{i}'])

    ma_periods = [5, 10, 20, 50, 100, 200]  # Reducido de 150 a 6 períodos
    ma_dfs = pd.concat([ma_function(i) for i in ma_periods], axis=1)
    df = pd.concat([df, ma_dfs], axis=1)
    del ma_dfs
    gc.collect()

    # EMA - reducir
    def ema_function(i):
        ma = ta.EMA(df['Close'], timeperiod=i)
        return pd.DataFrame(ma, columns=[f'mema_{i}'])

    ema_periods = [5, 10, 20, 50, 100, 200]  # Reducido
    ema_dfs = pd.concat([ema_function(i) for i in ema_periods], axis=1)
    df = pd.concat([df, ema_dfs], axis=1)
    del ema_dfs
    gc.collect()

    # ATR - reducir períodos
    def atr_function(i):
        atr = ta.ATR(df['High'], df['Low'], df['Close'], timeperiod=i)
        return pd.DataFrame(atr, columns=[f'atr_{i}'])

    atr_periods = [5, 10, 14, 20, 30]  # Reducido
    atr_dfs = pd.concat([atr_function(i) for i in atr_periods], axis=1)
    df = pd.concat([df, atr_dfs], axis=1)
    del atr_dfs
    gc.collect()

    # STDEV - reducir
    def stdev_function(i):
        stdev = ta.STDDEV(df['Close'], timeperiod=i, nbdev=1)
        return pd.DataFrame(stdev, columns=[f'stdev_{i}'])

    stdev_periods = [5, 10, 14, 20, 30]  # Reducido
    stdev_dfs = pd.concat([stdev_function(i) for i in stdev_periods], axis=1)
    df = pd.concat([df, stdev_dfs], axis=1)
    del stdev_dfs
    gc.collect()

    # Bollinger Bands - reducir
    def bband_function(i, dev=2):
        upperband, middleband, lowerband = ta.BBANDS(df['Close'], timeperiod=i, nbdevup=dev, nbdevdn=dev, matype=0)
        return pd.DataFrame({f'bb_upper_{dev}_{i}': upperband, f'bb_lower_{dev}_{i}': lowerband})

    bb_periods = [10, 20, 30]  # Reducido significativamente
    for dev in [2]:  # Solo desviación estándar 2
        bband_dfs = pd.concat([bband_function(i, dev) for i in bb_periods], axis=1)
        df = pd.concat([df, bband_dfs], axis=1)
        del bband_dfs
        gc.collect()

    # Momentum - reducir
    def mom_function(i):
        momentum = ta.MOM(df['Close'], timeperiod=i)
        return pd.DataFrame(momentum, columns=[f'mom_{i}'])

    mom_periods = [2, 5, 10, 15, 20]  # Reducido
    momentum_dfs = pd.concat([mom_function(i) for i in mom_periods], axis=1)
    df = pd.concat([df, momentum_dfs], axis=1)
    del momentum_dfs
    gc.collect()

    # Aroon Oscillator - reducir
    def aaron_up_function(i):
        aroon_up = ta.AROONOSC(df['High'], df['Low'], timeperiod=i)
        return pd.DataFrame(aroon_up, columns=[f'aaro_{i}'])

    aroon_periods = [5, 10, 14, 20, 30]  # Reducido
    aaronu_dfs = pd.concat([aaron_up_function(i) for i in aroon_periods], axis=1)
    df = pd.concat([df, aaronu_dfs], axis=1)
    del aaronu_dfs
    gc.collect()

    # Aroon Up/Down - reducir
    def aaron_up_function2(i):
        _, aroon_up = ta.AROON(df['High'], df['Low'], timeperiod=i)
        return pd.DataFrame(aroon_up, columns=[f'aarou_{i}'])

    def aaron_dw_function2(i):
        aroon_down, _ = ta.AROON(df['High'], df['Low'], timeperiod=i)
        return pd.DataFrame(aroon_down, columns=[f'aarod_{i}'])

    aaronu_dfs = pd.concat([aaron_up_function2(i) for i in aroon_periods], axis=1)
    aaronu_dfs2 = pd.concat([aaron_dw_function2(i) for i in aroon_periods], axis=1)
    df = pd.concat([df, aaronu_dfs, aaronu_dfs2], axis=1)
    del aaronu_dfs, aaronu_dfs2
    gc.collect()

    # Limpiar duplicados
    duplicates = df.columns[df.columns.duplicated()]
    df = df.loc[:, ~df.columns.duplicated()]

    # Shift columns (mantener lógica original)
    def shift_column(column, i):
        shifted = df[column].shift(i)
        if('ibs_' in column):
            column = 'ibs'
        return shifted.rename(f'{column}_sft_{i}')

    columns = df.columns
    lista_shift = ['rsi', 'adx', 'plus_di', 'minus_di', 'willr', 'bb', 'atr', 'stdev', 'Close', 'High', 'Low', 'aaro', 'mom']
    indicator_columns = {col for col in columns if any(name in col for name in lista_shift)}

    shifted_columns = []
    shift_value = 3

    for column in indicator_columns:
        for i in range(1, shift_value + 1):
            shifted_series = shift_column(column, i)
            shifted_columns.append(shifted_series)

    df = pd.concat([df] + shifted_columns, axis=1)

    # Calcular RETORNOS ABSOLUTOS (sin pips)
    for i in range(2, 31, 2):
        ret_abs = []
        if short:
            # Para short: ganancia si precio baja, spread de 2 cents
            ret_abs = (df["Close"].shift(-1 * i) - df["Close"]) + 0.02
            ret_abs = pd.DataFrame(np.array(ret_abs) * -1, columns=[f"Return_Abs_{i}"])
        else:
            # Para long: ganancia si precio sube, spread de 2 cents
            ret_abs = (df["Close"].shift(-1 * i) - df["Close"]) - 0.02
            ret_abs = pd.DataFrame(np.array(ret_abs), columns=[f"Return_Abs_{i}"])

        df = pd.concat([df, ret_abs], axis=1)

    # Calcular RETORNOS PORCENTUALES
    for i in range(2, 31, 2):
        ret_pct = []
        if short:
            # Para short: ganancia si precio baja, spread de 0.2%
            ret_pct = ((df["Close"].shift(-1 * i) - df["Close"]) / df["Close"]) * 100 + 0.2
            ret_pct = pd.DataFrame(np.array(ret_pct) * -1, columns=[f"Return_Pct_{i}"])
        else:
            # Para long: ganancia si precio sube, spread de 0.2%
            ret_pct = ((df["Close"].shift(-1 * i) - df["Close"]) / df["Close"]) * 100 - 0.2
            ret_pct = pd.DataFrame(np.array(ret_pct), columns=[f"Return_Pct_{i}"])

        df = pd.concat([df, ret_pct], axis=1)

    # Retorno principal ABSOLUTO
    if short:
        ret_main_abs = (df["Close"].shift(-1 * exposicion_dias) - df["Close"]) + 0.02
        ret_main_abs = pd.DataFrame(np.array(ret_main_abs) * -1, columns=["Return_Abs"])
    else:
        ret_main_abs = (df["Close"].shift(-1 * exposicion_dias) - df["Close"]) - 0.02
        ret_main_abs = pd.DataFrame(np.array(ret_main_abs), columns=["Return_Abs"])

    # Retorno principal PORCENTUAL
    if short:
        ret_main_pct = ((df["Close"].shift(-1 * exposicion_dias) - df["Close"]) / df["Close"]) * 100 + 0.2
        ret_main_pct = pd.DataFrame(np.array(ret_main_pct) * -1, columns=["Return_Pct"])
    else:
        ret_main_pct = ((df["Close"].shift(-1 * exposicion_dias) - df["Close"]) / df["Close"]) * 100 - 0.2
        ret_main_pct = pd.DataFrame(np.array(ret_main_pct), columns=["Return_Pct"])

    df = pd.concat([df, ret_main_abs, ret_main_pct], axis=1)

    # Crear TARGETS SOLO para datos de horas de mercado
    df_market_hours = df[df['market_hours']].copy()

    # Targets absolutos solo en market hours
    target_abs = (df_market_hours["Return_Abs"] >= threshold_abs).astype(int)
    target_pct = (df_market_hours["Return_Pct"] >= threshold_pct).astype(int)

    # Inicializar columnas de targets con NaN
    df["Target_Abs"] = np.nan
    df["Target_Pct"] = np.nan

    # Asignar targets solo en filas de market hours
    df.loc[df['market_hours'], "Target_Abs"] = target_abs.values
    df.loc[df['market_hours'], "Target_Pct"] = target_pct.values

    # Targets para exposiciones múltiples
    for i in range(4, 31, 2):
        df[f'Target_Abs_{i}'] = np.nan
        df[f'Target_Pct_{i}'] = np.nan

        target_abs_i = (df_market_hours[f'Return_Abs_{i}'] >= threshold_abs).astype(int)
        target_pct_i = (df_market_hours[f'Return_Pct_{i}'] >= threshold_pct).astype(int)

        df.loc[df['market_hours'], f'Target_Abs_{i}'] = target_abs_i.values
        df.loc[df['market_hours'], f'Target_Pct_{i}'] = target_pct_i.values

    # Procesar fechas
    df[date_column] = pd.to_datetime(df[date_column])

    day_of_month = df[date_column].apply(lambda x: x.day)
    month = df[date_column].apply(lambda x: x.month)
    day_of_week = df[date_column].apply(lambda x: x.weekday())
    year = df[date_column].apply(lambda x: x.year)

    df[date_column] = df[date_column].dt.strftime('%d/%m/%Y %H:%M')

    new_columns = pd.concat([day_of_month.rename('day_of_month'), month.rename('month'), day_of_week.rename('day_of_week'), year.rename('year')], axis=1)
    df = pd.concat([df, new_columns], axis=1)

    return df

def split_data_validation(df, year_max_cut = '2022', year_min_cur= '2008'):
    data = df.query('year >= ' + year_max_cut).copy()
    df = df.query(year_min_cur+' < year <= 2022')
    df = df.reset_index(drop=True)
    return df, data

def map_creator(df):
    inicio = time.time()
    columns = df.columns
    no_sft_columns = [col for col in columns if 'sft' not in col]
    column_map = create_column_map(df, columns, no_sft_columns)
    fin = time.time()
    duracion = fin - inicio
    print("La duración del proceso fue de", duracion, "segundos")
    return column_map

def create_column_map(df, columns, no_sft_columns):
    column_map = {}
    rsi_columns = {col for col in columns if 'rsi_' in col}
    adx_columns = {col for col in columns if 'adx' in col}
    plus_di_columns = {col for col in columns if 'plus_di' in col}
    minus_di_columns = {col for col in columns if 'minus_di' in col}
    will_columns = {col for col in columns if 'willr' in col}
    sma_columns = {col for col in columns if 'sma' in col}
    mema_columns = {col for col in columns if 'mema' in col}
    ibs_columns = {col for col in columns if 'ibs_' in col}
    atr_columns = {col for col in columns if 'atr' in col}
    bbup_columns = {col for col in columns if 'bb_upper' in col}
    bbmid_columns = {col for col in columns if 'bb_middle' in col}
    bblow_columns = {col for col in columns if 'bb_lower' in col}
    macd_columns = {col for col in columns if 'macd' in col}
    macdsig_columns = {col for col in columns if 'macdsig' in col}
    macdh_columns = {col for col in columns if 'macdh' in col}
    ibsma_columns = {col for col in columns if 'ibma' in col}
    hh_columns = {col for col in columns if 'hh' in col}
    dayw_columns = {col for col in columns if 'day_of_week' in col}
    daym_columns = {col for col in columns if 'day_of_month' in col}
    ll_columns = {col for col in columns if 'll' in col}
    mom_columns = {col for col in columns if 'mom' in col}
    aaro_columns = {col for col in columns if 'aaro_' in col}
    roc_columns = {col for col in columns if 'roc' in col}
    stoch_columns = {col for col in columns if 'stoch' in col}
    stochk_columns = {col for col in columns if 'stochk' in col}
    stochd_columns = {col for col in columns if 'stochd' in col}
    stdev_columns = {col for col in columns if 'stdev' in col}
    aarod_columns = {col for col in columns if 'aarod_' in col}
    aarou_columns = {col for col in columns if 'aarou_' in col}

    for column in no_sft_columns:
        if 'rsi' in column:
            filtered_columns = rsi_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col and 'ibs' not in col}
            column_map[column] = [list(range(0, 101)), list(filtered_columns)]

        elif 'adx' in column:
            filtered_columns = adx_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(range(0, 101)), list(filtered_columns)]

        elif 'plus_di' in column:
            filtered_columns = plus_di_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(range(0, 101)), list(filtered_columns)]

        elif 'minus_di' in column:
            filtered_columns = minus_di_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(range(0, 101)), list(filtered_columns)]

        elif 'willr' in column:
            filtered_columns = will_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(x for x in range(0, -101, -1)), list(filtered_columns)]

        elif 'sma' in column:
            filtered_columns = sma_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(['Open', 'High', 'Low', 'Close', 'Close_sft_1', 'Close_sft_2', 'Close_sft_3', 'Low_sft_1', 'Low_sft_2', 'Low_sft_3', 'High_sft_1', 'High_sft_2', 'High_sft_3']), list(filtered_columns)]

        elif 'mema' in column:
            filtered_columns = mema_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(['Open', 'High', 'Low', 'Close', 'Close_sft_1', 'Close_sft_2', 'Close_sft_3', 'Low_sft_1', 'Low_sft_2', 'Low_sft_3', 'High_sft_1', 'High_sft_2', 'High_sft_3']), list(filtered_columns)]

        elif 'ibs_' in column:
            filtered_columns = ibs_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list([i / 100 for i in range(0, 101)]), list(filtered_columns)]

        elif 'atr' in column:
            filtered_columns = atr_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(filtered_columns)]

        elif 'bb_upper' in column:
            filtered_columns = bbup_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(['Open', 'High', 'Low', 'Close', 'Close_sft_1', 'Close_sft_2', 'Close_sft_3', 'Low_sft_1', 'Low_sft_2', 'Low_sft_3', 'High_sft_1', 'High_sft_2', 'High_sft_3']), list(filtered_columns)]

        elif 'bb_middle' in column:
            filtered_columns = bbmid_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(['Open', 'High', 'Low', 'Close', 'Close_sft_1', 'Close_sft_2', 'Close_sft_3', 'Low_sft_1', 'Low_sft_2', 'Low_sft_3', 'High_sft_1', 'High_sft_2', 'High_sft_3']), list(filtered_columns)]

        elif 'bb_lower' in column:
            filtered_columns = bblow_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(['Open', 'High', 'Low', 'Close', 'Close_sft_1', 'Close_sft_2', 'Close_sft_3', 'Low_sft_1', 'Low_sft_2', 'Low_sft_3', 'High_sft_1', 'High_sft_2', 'High_sft_3']), list(filtered_columns)]

        elif 'macd' in column:
            filtered_columns = macd_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(macdsig_columns)]

        elif 'macdsig' in column:
            filtered_columns = macdsig_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(macd_columns)]

        elif 'macdh' in column:
            filtered_columns = macdh_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(filtered_columns)]

        elif 'ibma' in column:
            filtered_columns = ibsma_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(ibs_columns)]

        elif 'hh' in column:
            filtered_columns = hh_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(['Open', 'High', 'Low', 'Close', 'Close_sft_1', 'Close_sft_2', 'Close_sft_3', 'Low_sft_1', 'Low_sft_2', 'Low_sft_3', 'High_sft_1', 'High_sft_2', 'High_sft_3'])]

        elif 'day_of_week' in column:
            filtered_columns = dayw_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list([i for i in range(0, 7)]), list([i for i in range(0, 7)])]

        elif 'day_of_month' in column:
            filtered_columns = daym_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list([i for i in range(1, 32)]), list([i for i in range(1, 32)])]

        elif 'mom' in column:
            filtered_columns = mom_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(filtered_columns)]

        elif 'aaro_' in column:
            filtered_columns = aaro_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(x for x in range(-100, 101, 1)), list(filtered_columns)]

        elif 'aarod_' in column:
            filtered_columns = aarod_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(x for x in range(0, 101)), list(filtered_columns)]

        elif 'aarou_' in column:
            filtered_columns = aarou_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(x for x in range(0, 101)), list(filtered_columns)]

        elif 'roc' in column:
            filtered_columns = roc_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(filtered_columns)]

        elif 'stochd' in column:
            filtered_columns = stochd_columns - {column}
            comun_columns = stoch_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            filtered_comun_columns = {col for col in comun_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(filtered_comun_columns)]

        elif 'stochk' in column:
            filtered_columns = stochk_columns - {column}
            comun_columns = stoch_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            filtered_comun_columns = {col for col in comun_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(filtered_comun_columns)]

        elif 'stdev' in column:
            filtered_columns = stdev_columns - {column}
            filtered_columns = {col for col in filtered_columns if 'condition' not in col}
            column_map[column] = [list(filtered_columns), list(filtered_columns)]

    return column_map

def crear_directorio(nombre_carpeta):
    try:
        os.makedirs(nombre_carpeta)
        print(f"Directorio '{nombre_carpeta}' creado con éxito.")
    except FileExistsError:
        print(f"El directorio '{nombre_carpeta}' ya existe.")
    except Exception as e:
        print(f"Error al crear el directorio '{nombre_carpeta}': {e}")

def get_available_tickers(db_path='../market_data.db'):
    """
    Obtiene la lista de tickers disponibles en market_data.db
    """
    try:
        conn = sqlite3.connect(db_path)
        tickers_df = pd.read_sql("""
            SELECT symbol, COUNT(*) as bars, MIN(date(bar_timestamp)) as first_date, MAX(date(bar_timestamp)) as last_date
            FROM intraday_bars
            GROUP BY symbol
            ORDER BY bars DESC
        """, conn)
        conn.close()
        return tickers_df
    except Exception as e:
        print(f"Error obteniendo tickers: {e}")
        return pd.DataFrame()

def validate_rules_on_ticker(df_rules, df_test, target_column='Target_Pct', return_column='Return_Pct'):
    """
    Valida el rendimiento de reglas en datos out-of-sample de un ticker específico
    """
    if df_rules is None or df_rules.empty or df_test.empty:
        return {'avg_win_rate': 0, 'total_trades': 0, 'avg_return': 0, 'rules_tested': 0}

    results = []
    for rule in df_rules['condition'].head(50):  # Probar top 50 reglas
        try:
            # Aplicar la regla al dataframe de test
            df_test_copy = df_test.copy()

            # Evaluar la condición
            condition_result = evaluate_rule_condition(df_test_copy, rule)

            if condition_result is None or len(condition_result) == 0:
                continue

            # Calcular métricas
            valid_targets = df_test_copy[target_column].dropna()
            valid_condition = condition_result[:len(valid_targets)]

            if len(valid_condition) == 0:
                continue

            trades = np.sum(valid_condition)
            if trades < 10:  # Mínimo 10 trades para ser significativo
                continue

            wins = np.sum(valid_condition & (valid_targets == 1))
            win_rate = wins / trades if trades > 0 else 0

            # Calcular retorno promedio
            valid_returns = df_test_copy[return_column].dropna()
            if len(valid_returns) >= len(valid_condition):
                valid_returns = valid_returns[:len(valid_condition)]
                avg_return = np.mean(valid_returns[valid_condition]) if np.sum(valid_condition) > 0 else 0
            else:
                avg_return = 0

            results.append({
                'rule': rule,
                'win_rate': win_rate,
                'trades': trades,
                'avg_return': avg_return
            })

        except Exception as e:
            continue

    if not results:
        return {'avg_win_rate': 0, 'total_trades': 0, 'avg_return': 0, 'rules_tested': 0}

    # Calcular métricas agregadas
    avg_win_rate = np.mean([r['win_rate'] for r in results])
    total_trades = sum([r['trades'] for r in results])
    avg_return = np.mean([r['avg_return'] for r in results])

    return {
        'avg_win_rate': round(avg_win_rate * 100, 2),
        'total_trades': total_trades,
        'avg_return': round(avg_return, 4),
        'rules_tested': len(results)
    }

def evaluate_rule_condition(df, rule):
    """
    Evalúa una condición de regla en un dataframe
    """
    try:
        # Parsear la regla (formato: "column operator value")
        parts = rule.split()
        if len(parts) != 3:
            return None

        column, operator, value = parts

        # Verificar que la columna existe
        if column not in df.columns:
            return None

        # Convertir valor a número si es posible
        try:
            value = float(value)
        except ValueError:
            # Si no es número, verificar que existe como columna
            if value not in df.columns:
                return None

        # Evaluar la condición
        if operator == '>=':
            if isinstance(value, str):
                result = df[column] >= df[value]
            else:
                result = df[column] >= value
        elif operator == '<=':
            if isinstance(value, str):
                result = df[column] <= df[value]
            else:
                result = df[column] <= value
        elif operator == '==':
            if isinstance(value, str):
                result = df[column] == df[value]
            else:
                result = df[column] == value
        elif operator == '>':
            if isinstance(value, str):
                result = df[column] > df[value]
            else:
                result = df[column] > value
        elif operator == '<':
            if isinstance(value, str):
                result = df[column] < df[value]
            else:
                result = df[column] < value
        else:
            return None

        return result.values

    except Exception as e:
        return None

# Función principal para ejecutar el rule extractor con stocks
def run_rule_extractor_stocks(symbol, db_path='../market_data.db', exposicion_dias=4,
                              threshold_pct=1.5, threshold_abs=0.05, short=False,
                              output_dir='results_stocks'):
    """
    Función principal para ejecutar el rule extractor con datos de stocks
    """

    print(f"🚀 RULE EXTRACTOR PARA STOCKS - {symbol}")
    print("=" * 50)

    # Crear directorio de resultados
    crear_directorio(output_dir)

    # Transformar datos
    print("📊 Transformando datos...")
    df = transform_df_stock(symbol, db_path, exposicion_dias, threshold_pct, threshold_abs, short)

    if df.empty:
        print(f"❌ No se pudieron cargar datos para {symbol}")
        return None, None

    # Filtrar datos de entrenamiento (SOLO horas de mercado)
    print("📅 Filtrando datos de entrenamiento...")
    df_train = df[df['market_hours']].copy()  # Solo datos de market hours
    # Para datos de stocks recientes, usar años más actuales
    df_train = df_train.query('year >= 2023')  # Ajustar según necesidad
    df_train = df_train.reset_index(drop=True)

    if len(df_train) < 1000:
        print(f"⚠️  Pocos datos de entrenamiento: {len(df_train)} registros")

    print(f"✅ Datos preparados: {len(df_train)} registros")

    # Crear mapa de columnas
    print("🗺️  Creando mapa de reglas...")
    column_map = map_creator(df_train)

    # OPTIMIZACIÓN: Liberar memoria antes de generar reglas
    gc.collect()

    # Generar todas las reglas posibles
    print("📋 Generando reglas...")
    all_rules = generate_all_rules(column_map, df_train)

    print(f"📊 Total de reglas generadas: {len(all_rules)}")

    # OPTIMIZACIÓN: Liberar mapa de columnas que ya no se necesita
    del column_map
    gc.collect()

    # Ejecutar evaluación de reglas
    print("🔬 Evaluando reglas...")
    start_time = time.time()

    # Elegir target (por defecto usamos porcentual)
    target_column = 'Target_Pct'

    df_rules, sorted_stats = evaluate_rules_numpy(df_train, all_rules, target_column,
                                                  output_file=f'{output_dir}/results_{symbol}.csv')

    elapsed_time = time.time() - start_time
    print(f"    ⏱️  Tiempo de evaluación: {elapsed_time:.2f} segundos")
    if df_rules is not None:
        print(f"✅ Reglas evaluadas: {len(df_rules)}")
        print(f"💾 Resultados guardados en {output_dir}/results_{symbol}.csv")

        # Mostrar top reglas
        if not df_rules.empty:
            top_rules = df_rules.head(10)
            print("\n🏆 TOP 10 REGLAS:")
            for idx, row in top_rules.iterrows():
                print(f"    {row['ticker']}: Win Rate {row['avg_win_rate']}%, {row['total_trades']} trades, Return {row['avg_return']}")

    # OPTIMIZACIÓN: Liberar memoria al final
    del df_train, all_rules
    gc.collect()

    return df_rules, sorted_stats

# Nueva función con validación out-of-sample por tickers
def run_rule_extractor_stocks_with_validation(db_path='../market_data.db',
                                            train_tickers=None, test_tickers=None,
                                            exposicion_dias=4, threshold_pct=1.5, threshold_abs=0.05,
                                            output_dir='results_stocks_validation'):
    """
    Rule extractor con validación out-of-sample por tickers
    Divide automáticamente los tickers en in-sample (80%) y out-of-sample (20%)
    """

    print("🚀 RULE EXTRACTOR CON VALIDACIÓN OUT-OF-SAMPLE POR TICKERS")
    print("=" * 60)

    # Crear directorio de resultados
    crear_directorio(output_dir)

    # Obtener tickers disponibles
    print("📊 Obteniendo lista de tickers disponibles...")
    tickers_df = get_available_tickers(db_path)

    if tickers_df.empty:
        print("❌ No se encontraron tickers en la base de datos")
        return None, None

    available_tickers = tickers_df['symbol'].tolist()
    print(f"✅ Encontrados {len(available_tickers)} tickers: {available_tickers[:10]}{'...' if len(available_tickers) > 10 else ''}")

    # Dividir en train/test si no se especificaron
    if train_tickers is None or test_tickers is None:
        # Auto-división: 80% train, 20% test
        split_idx = int(len(available_tickers) * 0.8)
        train_tickers = available_tickers[:split_idx]
        test_tickers = available_tickers[split_idx:]

    print(f"📈 In-sample tickers ({len(train_tickers)}): {train_tickers}")
    print(f"🧪 Out-of-sample tickers ({len(test_tickers)}): {test_tickers}")

    # Entrenar con tickers de in-sample
    print("\n🏋️  FASE 1: Entrenamiento con tickers in-sample...")
    all_train_data = []

    for ticker in train_tickers:
        print(f"  📊 Procesando {ticker}...")
        df_ticker = transform_df_stock(ticker, db_path, exposicion_dias, threshold_pct, threshold_abs)
        if not df_ticker.empty:
            market_data = df_ticker[df_ticker['market_hours']].copy()
            if len(market_data) > 0:
                all_train_data.append(market_data)
                print(f"    ✅ {len(market_data)} registros de market hours")
            else:
                print(f"    ⚠️  Sin datos de market hours")
        else:
            print(f"    ❌ Error cargando datos")

    if not all_train_data:
        print("❌ No hay datos de entrenamiento suficientes")
        return None, None

    # Combinar todos los datos de training
    df_train = pd.concat(all_train_data, ignore_index=True)
    print(f"\n✅ Datos de entrenamiento combinados: {len(df_train)} registros de {len(all_train_data)} tickers")

    # OPTIMIZACIÓN: Liberar lista de datos individuales
    del all_train_data
    gc.collect()

    # Generar reglas con datos de training
    print("\n🧠 Generando reglas...")
    column_map = map_creator(df_train)
    all_rules = generate_all_rules(column_map, df_train)
    print(f"📋 Reglas generadas: {len(all_rules)}")

    # OPTIMIZACIÓN: Liberar mapa de columnas
    del column_map
    gc.collect()

    # Evaluar reglas en training data
    print("🔬 Evaluando reglas en datos de entrenamiento...")
    df_rules, _ = evaluate_rules_numpy(df_train, all_rules, 'Target_Pct',
                                      output_file=f'{output_dir}/rules_insample.csv')

    if df_rules is None or df_rules.empty:
        print("❌ No se pudieron generar reglas")
        return None, None

    print(f"✅ Reglas evaluadas: {len(df_rules)}")

    # OPTIMIZACIÓN: Liberar datos de entrenamiento y reglas después de evaluación
    del df_train, all_rules
    gc.collect()

    # Mostrar top reglas de training
    if not df_rules.empty:
        top_rules = df_rules.head(5)
        print("\n🏆 TOP 5 REGLAS (In-sample):")
        for idx, row in top_rules.iterrows():
            print(f"  {row['condition'][:60]}... | Corr: {row['correlation']:.3f} | Win: {row['win_rate']}%")

    # FASE 2: Validación out-of-sample
    print("\n🧪 FASE 2: Validación out-of-sample...")
    validation_results = []

    for ticker in test_tickers:
        print(f"  📊 Validando en {ticker}...")
        df_test = transform_df_stock(ticker, db_path, exposicion_dias, threshold_pct, threshold_abs)
        if df_test.empty:
            print(f"    ❌ Error cargando datos de {ticker}")
            continue

        df_test_market = df_test[df_test['market_hours']].copy()
        if len(df_test_market) < 100:
            print(f"    ⚠️  Pocos datos de market hours: {len(df_test_market)}")
            continue

        # Evaluar rendimiento de las reglas en este ticker
        ticker_performance = validate_rules_on_ticker(df_rules, df_test_market)
        ticker_performance['ticker'] = ticker
        validation_results.append(ticker_performance)

        print(f"    ✅ Win Rate: {ticker_performance['avg_win_rate']:.2f}%, Trades: {ticker_performance['total_trades']}, Return: {ticker_performance['avg_return']:.4f}")

    # Resultados finales
    if validation_results:
        df_validation = pd.DataFrame(validation_results)

        # Estadísticas agregadas
        avg_win_rate = df_validation['avg_win_rate'].mean()
        total_trades = df_validation['total_trades'].sum()
        avg_return = df_validation['avg_return'].mean()

        print("\n📈 RESULTADOS DE VALIDACIÓN OUT-OF-SAMPLE:")
        print(f"   Win Rate Promedio: {avg_win_rate:.2f}%")
        print(f"   Total Trades: {total_trades}")
        print(f"   Retorno Promedio: {avg_return:.4f}")
        print(f"   Tickers validados: {len(validation_results)}")

        print("\n📊 Detalle por ticker:")
        for _, row in df_validation.iterrows():
            print(f"  {row['ticker']}: Win Rate {row['avg_win_rate']:.2f}%, Trades: {row['total_trades']}, Return: {row['avg_return']:.4f}")

        # Guardar resultados
        df_validation.to_csv(f'{output_dir}/validation_results.csv', index=False)
        print(f"\n💾 Resultados guardados en {output_dir}/")

        # OPTIMIZACIÓN: Liberar memoria
        del df_validation
        gc.collect()

        return df_rules, pd.DataFrame(validation_results)
    else:
        print("❌ No se pudieron validar las reglas")
        return df_rules, None

def generate_all_rules(column_map, df, max_rules_per_column=50):
    """
    Genera reglas con límite para evitar explosión de memoria
    """
    all_rules = []

    for column, (possible_values, related_columns) in column_map.items():
        if 'day' in column:
            operators = ['>', '<', '==', '>=', '<=']
        else:
            operators = ['>=', '<=']

        # Limitar valores posibles para evitar demasiadas reglas
        limited_values = possible_values[:max_rules_per_column // len(operators)]
        limited_related = related_columns[:max_rules_per_column // len(operators)]

        for value in limited_values:
            for operator in operators:
                condition = f"{column} {operator} {value}"
                all_rules.append(condition)

        for value in limited_related:
                for operator in operators:
                    related_condition = f"{column} {operator} {value}"
                    all_rules.append(related_condition)

        # Si ya tenemos muchas reglas, parar
        if len(all_rules) > 10000:  # Límite de 10k reglas
            print(f"Límite de reglas alcanzado: {len(all_rules)}")
            break

    print(f"Total reglas generadas: {len(all_rules)}")
    return all_rules

def generate_hash(s):
    try:
        first_part = re.findall(r'^\D+', s.split(' ')[0])[0]
        comparison_operator = re.findall(r'[<=>=]+', s)[0]
        try:
            second_part = re.findall(r'^\D+', s.split(' ')[2].split('_')[0])[0]
        except IndexError:
            second_part = 'num'
        combined = first_part + comparison_operator + second_part
        return hashlib.sha256(combined.encode()).hexdigest()
    except Exception as e:
        return 12345678910

def process_rule_chunk(df, data, df_columns, rule_chunk, target_values, target, returns_columns):
    chunk_results = {}
    chunk_stats = {}

    for rule in rule_chunk:
        try:
            parts = rule.split()
            if len(parts) == 3:
                column1, operator, column2_or_value = parts
                idx1 = df_columns.get_loc(column1)
                idx_return = df_columns.get_loc('Return_Pct')
                idx_return_abs = df_columns.get_loc('Return_Abs')

                try:
                    value = float(column2_or_value)
                    idx2 = None
                except ValueError:
                    idx2 = df_columns.get_loc(column2_or_value)

                # OPTIMIZACIÓN: Usar arrays de numpy directamente sin conversión intermedia
                if operator == '>=':
                    if idx2 is None:
                        condition_eval = (data[:, idx1] >= value)
                    else:
                        condition_eval = (data[:, idx1] >= data[:, idx2])
                elif operator == '<=':
                    if idx2 is None:
                        condition_eval = (data[:, idx1] <= value)
                    else:
                        condition_eval = (data[:, idx1] <= data[:, idx2])
                elif operator == '==':
                    if idx2 is None:
                        condition_eval = (data[:, idx1] == value)
                    else:
                        condition_eval = (data[:, idx1] == data[:, idx2])
                else:
                    continue

                ones_count = np.sum(condition_eval)
                if ones_count < 100:
                    continue

                correlation, _ = pointbiserialr(condition_eval.astype(np.int8), target)
                if np.isnan(correlation) or np.isinf(correlation):
                    continue

                length = len(condition_eval)
                zeros_count = length - ones_count
                win_rate = np.sum(condition_eval & target_values) / ones_count if ones_count > 0 else 0

                # OPTIMIZACIÓN: Cálculos más eficientes
                valid_returns = data[condition_eval, idx_return]
                valid_returns_abs = data[condition_eval, idx_return_abs]

                sum_returns = np.sum(valid_returns)
                sum_returns_abs = np.sum(valid_returns_abs)

                positive_returns = valid_returns[valid_returns > 0]
                negative_returns = valid_returns[valid_returns < 0]

                sum_positive_returns = np.sum(positive_returns) if len(positive_returns) > 0 else 0
                sum_negative_returns = np.sum(negative_returns) if len(negative_returns) > 0 else 0

                profit_factor = sum_positive_returns / -sum_negative_returns if sum_negative_returns != 0 else float('inf')

                # OPTIMIZACIÓN: Calcular profit factors de forma más eficiente
                optimal_pf = 0
                optimal_exposition = '4'
                profit_factors = {}

                for ret_col in returns_columns:
                    idx_return_col = df_columns.get_loc(ret_col)
                    col_returns = data[condition_eval, idx_return_col]
                    col_positive = col_returns[col_returns > 0]
                    col_negative = col_returns[col_returns < 0]

                    sum_pos_col = np.sum(col_positive) if len(col_positive) > 0 else 0
                    sum_neg_col = -np.sum(col_negative) if len(col_negative) > 0 else 0

                    pf_col = sum_pos_col / sum_neg_col if sum_neg_col != 0 else float('inf')

                    match = re.search(r'Return_Pct_(\d+)', ret_col)
                    number = match.group(1) if match else '4'
                    profit_factors[f'pf_{number}'] = pf_col

                    if pf_col != float('inf') and pf_col > optimal_pf:
                        optimal_pf = pf_col
                        optimal_exposition = number

                # OPTIMIZACIÓN: Evitar cálculos innecesarios si no hay suficientes datos
                if ones_count < 1000:  # Skip complex calculations for small samples
                    correlation_optimal = 0.0
                    win_rate_optimal = 0.0
                else:
                    target_optimal_col = f'Target_Pct_{optimal_exposition}'
                    if target_optimal_col in df.columns:
                        target_optimal = df[target_optimal_col].values
                        target_values_optimal = (target_optimal > 0).astype(np.int8)
                        correlation_optimal, _ = pointbiserialr(condition_eval.astype(np.int8), target_optimal)
                        if np.isnan(correlation_optimal) or np.isinf(correlation_optimal):
                            correlation_optimal = 0.0
                        win_rate_optimal = np.sum(condition_eval & target_values_optimal) / ones_count if ones_count > 0 else 0
                    else:
                        correlation_optimal = 0.0
                        win_rate_optimal = 0.0

                chunk_results[rule] = condition_eval.astype(np.int8)
                chunk_stats[rule] = {
                    'correlation': correlation,
                    'length': length,
                    'ones_count': ones_count,
                    'zeros_count': zeros_count,
                    'win_rate': round(win_rate * 100, 2),
                    'return_pct': sum_returns,
                    'return_abs': sum_returns_abs,
                    'hash': generate_hash(rule),
                    'optimal_exposition': optimal_exposition,
                    'correlation_optimal': correlation_optimal,
                    'win_rate_optimal': round(win_rate_optimal * 100, 2),
                    'profit_factor': profit_factor,
                }
                chunk_stats[rule].update(profit_factors)

        except Exception as e:
            continue  # Silenciar errores para mejor rendimiento

    return chunk_results, chunk_stats

def evaluate_rules_numpy(df, all_rules, target_column='Target_Pct', output_file='results_stocks.csv'):
    print('Starting rule evaluation process...', datetime.now().strftime('%d-%m-%Y %H:%M:%S'))

    # OPTIMIZACIÓN: Convertir a tipos de datos más eficientes
    df_optimized = df.copy()
    for col in df_optimized.select_dtypes(include=['float64']).columns:
        df_optimized[col] = df_optimized[col].astype('float32')
    for col in df_optimized.select_dtypes(include=['int64']).columns:
        df_optimized[col] = df_optimized[col].astype('int32')

    data = df_optimized.to_numpy()
    target = df_optimized[target_column].values
    target_values = (df_optimized[target_column] > 0).astype(np.int8).values

    num_cores = min(joblib.cpu_count(), 4)  # Limitar cores para evitar sobrecarga de memoria
    print(f"Using {num_cores} CPU cores for parallel processing")

    # Dividir reglas en chunks más pequeños
    chunk_size = max(100, len(all_rules) // (num_cores * 2))  # Chunks más pequeños
    rule_chunks = [all_rules[i:i + chunk_size] for i in range(0, len(all_rules), chunk_size)]

    returns_columns = [f'Return_Pct_{i}' for i in range(4, 31, 2)]

    # OPTIMIZACIÓN: Procesar en lotes y liberar memoria
    all_results = {}
    all_stats = {}

    for i, rule_chunk in enumerate(rule_chunks):
        print(f"Processing chunk {i+1}/{len(rule_chunks)}...")

        # Procesar chunk actual
        results = Parallel(n_jobs=num_cores, backend='threading')(
            delayed(process_rule_chunk)(df_optimized, data, df_optimized.columns, [rule], target_values, target, returns_columns)
            for rule in rule_chunk
        )

        # Agregar resultados del chunk
        for chunk_results, chunk_stats in results:
            all_results.update(chunk_results)
            all_stats.update(chunk_stats)

        # Liberar memoria cada 10 chunks
        if (i + 1) % 10 == 0:
            gc.collect()
            print(f"Memory cleanup at chunk {i+1}")

        # Si tenemos demasiados resultados, guardar parcialmente
        if len(all_results) > 50000:  # Límite de resultados en memoria
            print("Guardando resultados parciales...")
            temp_df = pd.DataFrame(all_results)
            temp_df['Target_Pct'] = df_optimized['Target_Pct'].copy()
            temp_df['Target_Abs'] = df_optimized['Target_Abs'].copy()
            temp_df['Return_Pct'] = df_optimized['Return_Pct'].copy()
            temp_df['Return_Abs'] = df_optimized['Return_Abs'].copy()

            for column_ in returns_columns:
                temp_df[column_] = df_optimized[column_].values

            partial_file = f"{output_file}.partial_{i}"
            try:
                temp_df.to_hdf(partial_file, key='result_df', mode='w')
            except ImportError:
                # Fallback a CSV si no está disponible pytables
                csv_partial = partial_file.replace('.h5', '.csv')
                temp_df.to_csv(csv_partial, index=False)
                print(f"Resultados parciales guardados como CSV: {csv_partial}")

            # Limpiar para siguiente lote
            all_results.clear()
            del temp_df
            gc.collect()

    # Crear DataFrame final
    if all_results:
        result_df = pd.DataFrame(all_results)
        result_df['Target_Pct'] = df_optimized['Target_Pct'].copy()
        result_df['Target_Abs'] = df_optimized['Target_Abs'].copy()
        result_df['Return_Pct'] = df_optimized['Return_Pct'].copy()
        result_df['Return_Abs'] = df_optimized['Return_Abs'].copy()

        for column_ in returns_columns:
            result_df[column_] = df_optimized[column_].values

        print('Ending process.. saving', datetime.now().strftime('%d-%m-%Y %H:%M:%S'), len(result_df))
        try:
            result_df.to_hdf(output_file, key='result_df', mode='w')
        except ImportError:
            # Fallback a CSV si no está disponible pytables
            csv_file = output_file.replace('.h5', '.csv')
            result_df.to_csv(csv_file, index=False)
            print(f"Guardado como CSV: {csv_file}")

    sorted_stats = sorted(all_stats.items(), key=lambda item: item[1]['correlation'], reverse=True)

    groups = groupby(sorted_stats, key=lambda item: item[1]['correlation'])
    unique_stats = [next(g) for _, g in groups]

    df_stats = pd.DataFrame([item[1] for item in unique_stats])
    df_stats['condition'] = [item[0] for item in unique_stats]
    df_stats = df_stats[['condition'] + [col for col in df_stats.columns if col != 'condition']]

    print('Process completed', datetime.now().strftime('%d-%m-%Y %H:%M:%S'))
    return df_stats, unique_stats

# Ejemplo de uso
if __name__ == "__main__":
    print("🚀 RULE EXTRACTOR PARA STOCKS - VERSIÓN OPTIMIZADA")
    print("=" * 60)
    print("Optimizaciones aplicadas:")
    print("- Reducidos indicadores técnicos (de ~500 a ~80 columnas)")
    print("- Limitado número de reglas generadas (máx 10k)")
    print("- Procesamiento por lotes con liberación de memoria")
    print("- Tipos de datos optimizados (float32/int32)")
    print("- Liberación explícita de memoria con gc.collect()")
    print("=" * 60)

    # Opción 1: Ejecutar para un símbolo específico (sin validación)
    # symbol = 'RR'  # Uno de los símbolos con más datos
    # df_rules, stats = run_rule_extractor_stocks(symbol)

    # Opción 2: Ejecutar con validación out-of-sample por tickers (RECOMENDADO)
    print("Ejecutando rule extractor con validación out-of-sample por tickers...")
    df_rules, validation_results = run_rule_extractor_stocks_with_validation()

    if df_rules is not None:
        print("\n✅ Rule extraction completado exitosamente!")
        print(f"📊 Reglas generadas: {len(df_rules)}")

        if validation_results is not None:
            print(f"🧪 Validación completada en {len(validation_results)} tickers")
        else:
            print("⚠️  Sin resultados de validación")
    else:
        print("❌ Error en la extracción de reglas")