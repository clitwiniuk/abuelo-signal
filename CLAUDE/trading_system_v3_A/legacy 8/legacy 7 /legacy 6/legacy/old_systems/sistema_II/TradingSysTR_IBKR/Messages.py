
from dataclasses import dataclass,field
from datetime import datetime
#from queue import Queue
from enum import Enum
from typing import Any, Dict, Optional,List,Literal
import time
import asyncio
import pandas as pd


class MsgType(Enum):
    HEARTBEAT       = "HEARTBEAT"
    PRICE_TICK      = "PRICE_TICK"
    ORDER_ENTRY     = "ORDER_ENTRY"
    ALERT           = "ALERT"
    SHUTDOWN        = "SHUTDOWN"
    TIMER           = "TIMER"
    HISTORIA        = "HISTORY"
    TR_BAR          = "TR_BAR"
    ORDER_STATUS    = "ORDER_STATUS"
    FILL_MSG        = "FILL_MSG"
    CONTROL         = "CONTROL"
    SCANNER         = "SCANNER"
    CANCEL_SCAN     = "CANCEL_SCAN"

    # Añade nuevos tipos aquí, asegurando consistencia.


# Clase base
@dataclass
class Message:
    type: MsgType
    source: str
    symbol: str

    def __post_init__(self):
        if not isinstance(self.type, MsgType):
            raise ValueError(f"Tipo de mensaje inválido: {self.type}")


# Subclase personalizada
@dataclass
class TimerMsg(Message):
    typeTimer: Literal["ALARM", "PERIODIC"]
    id:str
    set: datetime
    delay: int
    fin: Optional[datetime]
    notify: Optional[asyncio.Queue] = field(default=None, repr=False, compare=False)
    type: MsgType = field(default=MsgType.TIMER, init=False)
    
    def __post_init__(self):
        
        super().__post_init__()  # llama a la validación de Message
        if self.typeTimer not in {"ALARM", "PERIODIC"}:
            raise ValueError(f"Tipo de timer inválido: {self.typeTimer}")
   

@dataclass
class TickMsg(Message):
    time:   datetime  # ISO 8601    
    bid:    Optional[float]=None #LOS OPTIONAL AL FINAL
    ask:    Optional[float]=None
    last:   Optional[float]=None

    type: MsgType = field(default=MsgType.PRICE_TICK, init=False)


@dataclass
class TRBar(Message):
    time:   datetime  # ISO 8601    
    open:   Optional[float]=None #LOS OPTIONAL AL FINAL
    high:   Optional[float]=None
    low:    Optional[float]=None
    close:  Optional[float]=None
    vol:    Optional[float]=None

    type: MsgType = field(default=MsgType.TR_BAR, init=False)


@dataclass
class OrderMessage(Message):
    side: str  # BUY / SELL
    qty: int
    price: float
    tipoOrder: str
    st: Optional[float]=None
    tp: Optional[float]=None
    type: MsgType = field(default=MsgType.ORDER_ENTRY, init=False)
         
@dataclass
class CancelOrderMsg(Message):
    side: str  # BUY / SELL
    qty: int
    price: float
    tipoOrder: str
    st: Optional[float]=None
    tp: Optional[float]=None
    type: MsgType = field(default=MsgType.ORDER_ENTRY, init=False)
         


@dataclass
class HistoricalMsg(Message):

    inicio: datetime
    fin:    datetime
    bar_size: str  # e.g., '1 min', '5 min', '1 day'
    out_market:bool
    data: Optional[pd.DataFrame] =None # dataframe con columnas OHLCV
    type: MsgType = field(default=MsgType.HISTORIA, init=False)
   
@dataclass
class OrderStatusMsg(Message):
    orderId:    int
    status:     str
    filled:     float
    remaining:  float
    avgPrice:   float
    time:       str  # ISO 8601
    type: MsgType = field(default=MsgType.ORDER_STATUS, init=False)

@dataclass
class FillMsg(Message):
    price:  float
    qty:    float
    time:   str  # ISO 8601
    type:   MsgType = field(default=MsgType.FILL_MSG, init=False)
 


@dataclass
class ReqCancelScan(Message):
    type:   MsgType = field(default=MsgType.CANCEL_SCAN, init=False)
    


@dataclass
class ScanResultMsg(Message):
    type: MsgType = field(default=MsgType.SCANNER, init=False)
    scan_code: str
    results: List[str]
     


@dataclass
class ScanRequestMsg(Message):

    type: MsgType = field(default=MsgType.SCANNER, init=False)
    scan_code: str = 'TOP_PERC_GAIN'
    instrument: str = 'STK'
    location_code: str = 'STK.US.MAJOR'
    number_of_rows: int = 60

    # Filtros opcionales
    above_price: Optional[float] = None
    below_price: Optional[float] = None
    above_volume: Optional[int] = None
    market_cap_above: Optional[float] = None
    market_cap_below: Optional[float] = None
    moody_rating_above: Optional[str] = None
    moody_rating_below: Optional[str] = None
    sp_rating_above: Optional[str] = None
    sp_rating_below: Optional[str] = None
    maturity_date_above: Optional[str] = None
    maturity_date_below: Optional[str] = None
    coupon_rate_above: Optional[float] = None
    coupon_rate_below: Optional[float] = None
    exclude_convertible: Optional[bool] = None
    scanner_setting_pairs: Optional[str] = None
    stock_type_filter: Optional[str] = None    



class ControlAction(Enum):
    HEARTBEAT           = "HEARTBEAT"
    CANCEL_ORDERS       = "CANCEL_ORDERS"
    CIERRA_POSICION     = "CIERRA_POSICION"

    CANCEL_SUSCRIP      = "CANCEL_SUSCRIP"
    REQ_TR_BAR          = "REQ_TR_BAR"
    REQ_TICK            = "REQ_TICK"

    REQ_1MIN_BAR        = "REQ_1MIN_BAR"
    GET_PRICE           = "GET_PRICE"
    REQ_1MIN_TOT        = "REQ_1MIN_TOT"

@dataclass
class ControlMsg(Message):

    action: ControlAction  # e.g. "start", "stop", "resync"
    
    time:   Optional[str] = None
    type:   MsgType = field(default=MsgType.CONTROL, init=False)
 