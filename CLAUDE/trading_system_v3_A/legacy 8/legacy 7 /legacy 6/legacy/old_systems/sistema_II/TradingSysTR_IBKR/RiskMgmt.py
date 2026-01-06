#import threading
import time
#from queue import Queue
import math
from ThTimer import ThTimer
import pandas as pd

from datetime import datetime, timedelta
from Messages import *
from ib_insync import IB, Stock, util,MarketOrder, LimitOrder,StopOrder,StopLimitOrder
import asyncio
from ib_insync import ScannerSubscription,util,ExecutionFilter
from Messages import *
from typing import Optional
from dataclasses import dataclass, field

from   Utils import *
from   Operation import *

from datetime import datetime


class TipoMM(str, Enum):
    FIX     = "FIX"
    PERC    = "PERC"
 
class TipoStop(str, Enum):
    NOSTOP  = "NOSTOP"
    FIX     = "FIX"
    PERC    = "PERC"

class TipoTake(str, Enum):
    NOTAKE  = "NOTAKE"
    FIX     = "FIX"
    PERC    = "PERC"
    BR      = "BR"


class RiskMgmt:
    def __init__(self):

        self.tipoST= TipoStop.NOSTOP
        self.tipoTP= TipoTake.NOTAKE
        self.tipoMM= TipoMM.FIX
        self.kSt = 0
        self.KTp = 0
        self.Mm  = 0
        self.log =  get_logger("RISK")


    def SetStop(self,tipo,kSt:float):
        try:
            self.tipoST=TipoStop(tipo)
            self.log.info (f"RISK MGNG :{self.tipoST} {tipo}")
            self.kSt=kSt

        except Exception as e:
            self.log.exception(f"RISK EXCEPTION: {e}")

    def SetTake(self,tipo,kTp:float):
        try:
            self.tipoTP=TipoTake(tipo)
            self.KTp=kTp

        except Exception as e:
            self.log.exception(f"RISK EXCEPTION: {e}")

    def SetMM(self,tipo,MM:float):
        try:
            self.tipoMM=TipoMM(tipo)
            self.Mm=MM

        except Exception as e:
            self.log.exception(f"RISK EXCEPTION: {e}")


    def GetStop(self,price, action):
       
        if(self.tipoST==TipoStop.NOSTOP):
            stAct= 0
            self.log.info (f"NO STOP {stAct:.3f}")

        elif(self.tipoST==TipoStop.PERC):
            stAct= price*float((self.kSt/100.00))
            self.log.info (f"PERC {stAct:.3f}")
                          
        elif(self.tipoST==TipoStop.FIX):
            stAct= self.kSt
            self.log.info (f"FIX {stAct:.3f}")
        else:
            stAct=0
            self.log.info (f"ELSE {stAct:.3f}")
        
        self.log.info (f"st ACT {stAct:.3f}")


        if (action == Action.BUY):
            stop = price-stAct
        else:
            stop = price+stAct

        
        return stop
    

    def GetTake(self,price, stop, action):
       
        if(self.tipoTP==TipoTake.NOTAKE):
            tpAct= 0

        elif(self.tipoTP==TipoTake.PERC):
            tpAct= price*self.ktp/100

        elif(self.tipoTP==TipoTake.FIX):
            tpAct= self.KTp

        elif(self.tipoTP==TipoTake.BR):
            diff= abs(price-stop)
            tpAct= diff*self.KTp
       
        else:
            tpAct=0
    
        if (action == Action.BUY):
            takeP = price+tpAct
        else:
            takeP = price-tpAct

        return takeP
    


    def GetLote(self,price, stop):
       

        if(self.tipoMM==TipoMM.FIX):
            riskMax=self.Mm
        elif(self.tipoMM==TipoMM.PERC):
            riskMax=cfSys['Mm']['cartera']*(self.Mm/100.00)
        else:
            riskMax=0

        perdTeo= abs(price-stop)
        
        lote=math.floor(riskMax/perdTeo)
    
        return lote