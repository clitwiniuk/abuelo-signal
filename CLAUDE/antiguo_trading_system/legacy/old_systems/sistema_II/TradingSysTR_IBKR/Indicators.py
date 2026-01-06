

from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple, Union,List,Optional
from enum import Enum
from datetime import datetime, timedelta
from Utils import *
from UtilIndicators import *

import pandas as pd



####### IndicatorDefinition	Define el comportamiento general del indicador (tipo, función, parámetros)
####### IndicatorInstance	Aplica esa definición sobre un DataFrame con memoria por símbolo
####### IndicatorFactory	Genera definiciones fácilmente desde id + parámetros


#######################################################################################################################################################


class TipoInd(str, Enum):

    SMA         =   "SMA"
    EMA         =   "EMA"
    VOLMED      =   "VOLMED"
    GAN         =   "GAN"
    STDEV       =   "STDEV"
    STOCH       =   "STOCH"
    RSI         =   "RSI"
    ATR         =   "ATR"



class IndicatorDefinition:
    def __init__(self, tipo: TipoInd, compute_fn: callable, bars: int,
                 source: str = "close", name: Optional[str] = None, **params):
        self.tipo = tipo
        self.compute_fn = compute_fn
        self.bars = bars
        self.source = source.lower()
        self.name = name or f"{tipo}_{bars}"
        self.params = params

    def run(self, df: pd.DataFrame, datos_salida: Optional[int] = None) -> Union[pd.Series, Dict[str, pd.Series]]:
        return self.compute_fn(
            df=df,
            bars=self.bars,
            source=self.source,
            name=self.name,
            datos_salida=datos_salida,
            extractor=extract_price_series,
            symbol=self.params.get("symbol"),
            **self.params
        )

######################################################################################################################################

class IndicatorInstance:
    def __init__(self, definition: IndicatorDefinition,
                 symbol: Optional[str] = None,
                 extend_df: bool = False):
        self.definition = definition
        self.symbol = symbol
        self.extend_df = extend_df
        self._last_index: Optional[pd.Timestamp] = None
        self._cached_result: Optional[Union[pd.Series, Dict[str, pd.Series]]] = None
        self.log = get_logger(f"{symbol or 'GENERIC'}_{definition.name}")

    def calculate(self, df: pd.DataFrame, datos_salida: Optional[int] = None) -> Union[pd.Series, Dict[str, pd.Series], pd.DataFrame]:
        current_index = df.index[-1]
        if self._last_index == current_index and self._cached_result is not None:
            self.log.info(f"[{self.symbol}] Usando resultado en caché para {self.definition.name}")
            return self._cached_result

        resultado = self.definition.run(df, datos_salida)
        self._cached_result = resultado
        self._last_index = current_index

        if self.extend_df:
            if isinstance(resultado, pd.Series):
                return df.assign(**{self.definition.name: resultado})
            elif isinstance(resultado, dict):
                return df.assign(**resultado)

        return resultado
    


######################################################################################################################################

def calcular_sma(df, bars, source, name, datos_salida, extractor, symbol=None, **kwargs):
    serie = extractor(df, source)
    total = bars + (datos_salida or 0) - 1
    serie = serie.tail(total)
    return serie.rolling(window=bars).mean().tail(datos_salida) if datos_salida else serie.rolling(window=bars).mean()

def calcular_ema(df, bars, source, name, datos_salida, extractor, symbol=None, **kwargs):
    serie = extractor(df, source)
    total = bars + (datos_salida or 0) - 1
    serie = serie.tail(total)
    return serie.ewm(span=bars, adjust=False).mean().tail(datos_salida) if datos_salida else serie.ewm(span=bars, adjust=False).mean()

def calcular_volmed(df, bars, source, name, datos_salida, extractor, symbol=None, threshold=0, **kwargs):
    if "volume" not in df.columns:
        raise ValueError("VOLMED requiere columna 'volume'.")
    total = bars + (datos_salida or 0) - 1
    vol = df["volume"].tail(total)
    avg = vol.rolling(window=bars).mean()
    flag = avg > threshold
    result = {f"{name}_avg": avg, f"{name}_over": flag}
    return {k: v.tail(datos_salida) for k, v in result.items()} if datos_salida else result

#############################################################################################################


class IndicatorFactory:
    _registry: Dict[TipoInd, callable] = {}

    @classmethod
    def register(cls, tipo: TipoInd):
        def wrapper(func):
            cls._registry[tipo] = func
            return func
        return wrapper

    @classmethod
    def create(cls, **kwargs) -> IndicatorDefinition:
        tipo = TipoInd(kwargs["id"])
        if tipo not in cls._registry:
            raise ValueError(f"Tipo de indicador no registrado: {tipo}")
        return cls._registry[tipo](**kwargs)


############################################################################################################################################
#                                                                BUILDERS                                                                  #
############################################################################################################################################
@IndicatorFactory.register(TipoInd.SMA)
def build_sma(**kwargs):
    config = {
        "tipo": TipoInd.SMA,
        "compute_fn": calcular_sma,
        "bars": 20,
        "source": "close",
        "name": "SMA"
    } | kwargs
    return IndicatorDefinition(**config)

@IndicatorFactory.register(TipoInd.EMA)
def build_ema(**kwargs):
    config = {
        "tipo": TipoInd.EMA,
        "compute_fn": calcular_ema,
        "bars": 10,
        "source": "close",
        "name": "EMA"
    } | kwargs
    return IndicatorDefinition(**config)

@IndicatorFactory.register(TipoInd.VOLMED)
def build_volmed(**kwargs):
    config = {
        "tipo": TipoInd.VOLMED,
        "compute_fn": calcular_volmed,
        "bars": 5,
        "source": "",
        "name": "VOLMED",
        "threshold": 100_000
    } | kwargs
    return IndicatorDefinition(**config)

@IndicatorFactory.register(TipoInd.GAN)
def build_Gan(**kwargs):
    config = {
        "tipo": TipoInd.GAN,
        "compute_fn": calcular_Gan,
        "bars": 5,
        "source": "",
        "name": "GAN",
       
    } | kwargs
    return IndicatorDefinition(**config)

@IndicatorFactory.register(TipoInd.STDEV)
def build_StDev(**kwargs):
    config = {
        "tipo": TipoInd.STDEV,
        "compute_fn": calcular_StDev,
        "bars": 5,
        "source": "",
        "name": "STDEV",
       
    } | kwargs
    return IndicatorDefinition(**config)

@IndicatorFactory.register(TipoInd.STOCH)
def build_Stoch(**kwargs):
    config = {
        "tipo": TipoInd.STOCH,
        "compute_fn": calcular_Stoch,
        "bars": 14,
        "SD": 3,
        "source": "",
        "name": "STOCH",
       
    } | kwargs
    return IndicatorDefinition(**config)



############################################################################################################################################
#                                                       CALCULOS DE INDICADORES                                                            #
############################################################################################################################################

def calcular_sma(df, bars, source, name, datos_salida, extractor, symbol=None, **kwargs):
    serie = extractor(df, source)
    total = bars + (datos_salida or 0) - 1
    serie = serie.tail(total)
    return serie.rolling(window=bars).mean().tail(datos_salida) if datos_salida else serie.rolling(window=bars).mean()

def calcular_ema(df, bars, source, name, datos_salida, extractor, symbol=None, **kwargs):
    serie = extractor(df, source)
    total = bars + (datos_salida or 0) - 1
    serie = serie.tail(total)
    return serie.ewm(span=bars, adjust=False).mean().tail(datos_salida) if datos_salida else serie.ewm(span=bars, adjust=False).mean()

def calcular_volmed(df, bars, source, name, datos_salida, extractor, symbol=None, threshold=0, **kwargs):
    if "volume" not in df.columns:
        raise ValueError("VOLMED requiere columna 'volume'.")
    total = bars + (datos_salida or 0) - 1
    vol = df["volume"].tail(total)
    avg = vol.rolling(window=bars).mean()
    flag = avg > threshold
    result = {f"{name}_avg": avg, f"{name}_over": flag}
    return {k: v.tail(datos_salida) for k, v in result.items()} if datos_salida else result


def calcular_Gan(df, bars, source, name, datos_salida, extractor, symbol=None,  **kwargs):
    serie = extractor(df, source)
   
    total = bars + (datos_salida or 0) #- 1
    serie = serie.tail(total)
    resultado=serie.rolling(window=bars).apply(lambda x: (x.iloc[-1] / x.iloc[0])-1)
    #resultado = serie.diff(periods=bars)

    resultado=resultado.tail(datos_salida)
    return resultado

def calcular_StDev(df, bars, source, name, datos_salida, extractor, symbol=None,  **kwargs):
    serie = extractor(df, source)
    
    total = bars + (datos_salida or 0) #- 1
    serie = serie.tail(total)

    resultado=serie.rolling(window=bars).std()
    #resultado = serie.diff(periods=bars)

    resultado=resultado.tail(datos_salida)
    return resultado

def calcular_Stoch(df, bars,SD, source, name, datos_salida, extractor, symbol=None,  **kwargs):
    serie = extractor(df, source)

    total = max(bars,SD) + (datos_salida or 0) #- 1
    serie = serie.tail(total)
    df=df.tail(total)

    L  = df['low'].rolling(window=bars).min()
    H  = df['high'].rolling(window=bars).max()

    serieK = 100 * (serie - L) / (H - L)

    serieD = serieK.rolling(window=SD).mean()

    #resultado={serieK, serieD}
    #resultado=resultado.tail(datos_salida)
    serieK=serieK.tail(datos_salida)
    serieK=serieD.tail(datos_salida)
    
    return serieK , serieD

    
    serie = extractor(df, source)

    total = bars + (datos_salida or 0) - 1 #-1 porque la celda de bar, se incluye
    serie = serie.tail(total)
    df=df.tail(total)

    L  = df['low'].rolling(window=bars).min()  #incluye barra en proceso
    H  = df['high'].rolling(window=bars).max()  #incluye barra en proceso
    
    
    print (f"H {H}")
    print (f" df {df}")

    print (f" serie {serie}")
    #paso= kwargs['paso']
    
    volPrix = pd.Series(index=df.index, dtype=float)
    frame= Frame(0,0,paso)
    
    
        #for i  in range(-bars,-1,1): 
    for i in range(bars-1, len(df)):
         # Extraer la ventana de tamaño n anterior a la fila actual (incluida)
        
        ix = df.index[i]   # El índice real de la fila actual - igual que H y L
        row = df.iloc[i]   # La fila actual
        sub = df.iloc[i -(bars-1):(i+1)] #ej:bars=5 -> ventana de 0 a 4 iloc[a:b] incluye a y excluye b
    
        frame.Clear()
        frame.Inicia(H[ix],L[ix],paso)
        for j in range(bars):      # o: for j in range(len(sub))  ← equivalente
            volB  = sub.iloc[j]["volume"]
            highB = sub.iloc[j]["high"]
            lowB  = sub.iloc[j]["low"]
            #print (f"ModificaBarFrame {highB}  {lowB}  {volB}")
            frame.ModificaBarFrame(highB,lowB,volB,"+")
        
        volPrix[ix] = frame.VolPrix(serie.iloc[i])
        print(frame.t_frame)
    
    #print(frame.t_frame)
    volPrix.tail(datos_salida)
    return volPrix