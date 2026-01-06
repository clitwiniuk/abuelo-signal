#import threading
#from queue import Queue
from ThTimer import ThTimer
import pandas as pd

from datetime import *

from Messages import *
import asyncio
from   Utils import *
from   Operation import *
import pytz
import copy
from   StrategyClass import *

class ThStrat:

    def __init__(self, 
                    in_Sdata: asyncio.Queue, 
                    in_Bkr: asyncio.Queue, 
                    in_Timer: asyncio.Queue,
                    
                    out_Bkr: asyncio.Queue,
                    out_SData: asyncio.Queue,

                    table_Scan:pd.DataFrame,
                    bloq_Scan,

                    table_Operation:Operation,
                    bloq_Operation,
                    timer: ThTimer,
                    #logger
                    ):

       # super().__init__(daemon=True)

        self.in_Sdata= in_Sdata 
        self.in_Bkr = in_Bkr
        self.in_Timer= in_Timer
        self.out_Bkr=out_Bkr
        self.out_SData = out_SData

        self.t_Scan     = table_Scan
        self.lock_Scan = bloq_Scan

        self.t_Oper= table_Operation
        self.lock_Oper = bloq_Operation

        self.timer = timer
        
        
        self.entryMsg=0
    

        self.log =  get_logger("STRAT")
        self.log.info (f"TAREA [STRAT] INCIALIZADA id(t_Scan):{id(self.t_Scan)}  id(t_Oper):{id(self.t_Oper)}")
        
        self.msgPeriod = TimerMsg(
                    #type=MsgType.TIMER,  # se puede pasar o se ignora
                    source="STRAT",
                    symbol="ALL",
                    typeTimer="PERIODIC",
                    id= "GESTION",
                    set=self.timer.getNow(),
                    delay=10,
                    fin=None,
                    notify=self.in_Timer
                )
        
        msgAlarm = TimerMsg(
                    #type=MsgType.TIMER,  # se puede pasar o se ignora
                    id="TIMEOUT_1",
                    source="STRAT",
                    symbol="ALL",
                    typeTimer="ALARM",
                    set=self.timer.getNow(),
                    delay=25,
                    fin=None,
                    notify=self.in_Timer
                )
       
        
        #self.timer.Set_timer(msgPeriod)
        #self.timer.Set_timer(msgAlarm)
        
        #self._stop_event = threading.Event()
       
        self.test =False
        self.StratCode= cfSys["System"]["Strategy"]
        self.mStrat=self.CrearStrategy(self.StratCode)

       
    def CrearStrategy(self,id: str) -> OneStrategy:

        if id == "S00":
            return Strat00(
                            table_Scan      = self.t_Scan,
                            bloq_Scan       = self.lock_Scan,
                            table_Operation = self.t_Oper,
                            bloq_Operation  = self.lock_Oper,
                            timer           = self.timer,
                            ThStrat         = self
                            )
                
                
        else:
            return  OneStrategy(    
                        table_Scan      = self.t_Scan,
                        bloq_Scan       = self.lock_Scan,
                        table_Operation = self.t_Oper,
                        bloq_Operation  = self.lock_Oper,
                        timer           = self.timer,
                        ThStrat         = self
                        )


    #END INIT

    async def run(self):
        await self.mStrat.Init()
        await asyncio.sleep(10) #al menos 30
        self.timer.RegisterTask("STRAT")
        self.msgPeriod = TimerMsg(
                    #type=MsgType.TIMER,  # se puede pasar o se ignora
                    source="STRAT",
                    symbol="ALL",
                    typeTimer="PERIODIC",
                    id= "GESTION",
                    set=self.timer.getNow(),
                    delay=10,
                    fin=None,
                    notify=self.in_Timer
                )
      
        self.timer.SetTimer(self.msgPeriod)
        try:
            while True:
                await self.read_msg()
                self.timer.SetTaskStatus("STRAT","idle")
                await asyncio.sleep(0.005)

        except Exception as e:
            self.log.error(f"Exception : {str(e)}")



    async def read_msg(self):
                     
        self.entryMsg +=1
    
        try:
            msg = self.in_Sdata.get_nowait()
            self.timer.SetTaskStatus("STRAT","working")
            await self.process_msg_Sdata(msg)
        except asyncio.QueueEmpty:
            pass

        try:
            msg = self.in_Timer.get_nowait()
            self.timer.SetTaskStatus("STRAT","working")
            await self.process_msg_Timer(msg)
        except asyncio.QueueEmpty:
            pass


    """       
    async def read_msg(self):
                     
        self.entryMsg +=1
    
    #self.log.(f'Strart entry {self.entry}')
        while not self.in_Sdata.empty():
            msg = await self.in_Sdata.get()
            await self.process_msg_Sdata(msg)

        while not self.in_Timer.empty():
            msg = await self.in_Timer.get()
            await self.process_msg_Timer(msg)
    """
  


    async def process_msg_Sdata(self,msg):
        self.log.info(f"Mensaje recibido SDATA: {msg}")

    
    async def process_msg_Timer(self,msg):

        retraso= self.timer.getNow()-msg.fin
        
        self.log.info(f"Mensaje RX TIMER: id={msg.id}- FIN:{msg.fin}- zone:{msg.fin.tzinfo} -RetrasoTimer mseg:{int(retraso.total_seconds()*1000)} ")      #es "timezone-aware" no NAIVE
        self.log.info (f"TAREA [STRAT] TIMER  id(t_Scan):{id(self.t_Scan)}  id(t_Oper):{id(self.t_Oper)}")
        ###self.timer.ShowTaksTime()
            

        if isinstance(msg, TimerMsg):
            try:
                if msg.id == "GESTION":
                    await self.mStrat.GestionaEstrategia()
        
            except:
                self.log.exception(f"EXCEPTION Mensaje TIMER {msg}")


    async def SendMsg(self,destino,msg):
        self.log.info(f"SEND MSSG destino  {msg}, destino {destino}")
        if(destino=="SDATA"):
            await self.out_SData.put(copy.deepcopy(msg)) #Envio mensaje al SDATA
            self.log.info(f"SEND MSG SDATA")
  
        elif(destino=="BKR"):
            await self.out_Bkr.put(copy.deepcopy(msg)) #Envio mensaje al Broker
            self.log.info(f"SEND MSGBKR")
  
        else:
            self.log.error(f"SEND MSSG destino sin definir {msg}")
            return
        
        