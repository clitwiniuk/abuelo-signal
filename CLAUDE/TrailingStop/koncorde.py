import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.volume import MFIIndicator
from ta.volatility import BollingerBands

def calculate_koncorde(df, m=15, longitudPVI=90, longitudNVI=90, longitudMFI=14, boLength=25, mult=2.0):
    tprice = df[['Open', 'High', 'Low', 'Close']].mean(axis=1)

    df['PVI'] = 1000.0
    df['NVI'] = 1000.0  # Valor inicial normalizado
    
    # Calcular PVI y NVI con protección contra overflow
    for i in range(1, len(df)):
        pct_change = np.clip(df['Close'].pct_change().iloc[i], -0.5, 0.5)
        
        if df['Volume'].iloc[i] > df['Volume'].iloc[i - 1]:
            # Calcular PVI con límites
            new_pvi = df['PVI'].iloc[i - 1] * (1 + pct_change)
            df.at[df.index[i], 'PVI'] = np.clip(new_pvi, 1e-10, 1e10)
            df.at[df.index[i], 'NVI'] = df['NVI'].iloc[i - 1]
        else:
            # Calcular NVI con límites
            new_nvi = df['NVI'].iloc[i - 1] * (1 + pct_change)
            df.at[df.index[i], 'NVI'] = np.clip(new_nvi, 1e-10, 1e10)
            df.at[df.index[i], 'PVI'] = df['PVI'].iloc[i - 1]

    # Normalizar NVI para evitar valores extremos
    df['NVI'] = (df['NVI'] - df['NVI'].rolling(50, min_periods=1).mean()) / df['NVI'].rolling(50, min_periods=1).std()
    df['NVI'] = np.clip(df['NVI'], -3, 3)  # Limitar a 3 desviaciones estándar

    pvim = df['PVI'].ewm(span=m).mean()
    pvimax = pvim.rolling(window=longitudPVI).max()
    pvimin = pvim.rolling(window=longitudPVI).min()
    oscp = (df['PVI'] - pvim) * 100 / (pvimax - pvimin)

    nvim = df['NVI'].ewm(span=m).mean()
    nvimax = nvim.rolling(window=longitudNVI).max()
    nvimin = nvim.rolling(window=longitudNVI).min()
    azul = (df['NVI'] - nvim) * 100 / (nvimax - nvimin)

    mfi = MFIIndicator(high=df['High'], low=df['Low'], close=df['Close'], volume=df['Volume'], window=longitudMFI)
    xmf = mfi.money_flow_index()

    rsi = RSIIndicator(close=tprice, window=14).rsi()

    bb = BollingerBands(close=tprice, window=boLength, window_dev=mult)
    OB1 = (bb.bollinger_hband() + bb.bollinger_lband()) / 2
    OB2 = bb.bollinger_hband() - bb.bollinger_lband()
    BollOsc = ((tprice - OB1) / OB2) * 100

    def calc_stoch(src, high, low, length=21, smooth=3):
        ll = low.rolling(window=length).min()
        hh = high.rolling(window=length).max()
        k = 100 * (src - ll) / (hh - ll)
        return k.rolling(window=smooth).mean()

    stoc = calc_stoch(tprice, df['High'], df['Low'])

    marron = (rsi + xmf + BollOsc + (stoc / 3)) / 2
    verde = marron + oscp
    media = marron.ewm(span=m).mean()

    koncorde_df = pd.DataFrame({
        'verde': verde,
        'marron': marron,
        'azul': azul,
        'media': media,
        'precio': df['Close']
    }, index=df.index)

    return koncorde_df.dropna()