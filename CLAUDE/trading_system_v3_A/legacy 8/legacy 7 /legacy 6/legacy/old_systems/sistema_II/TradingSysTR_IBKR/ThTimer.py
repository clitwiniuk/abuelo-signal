#import threading
import time
from queue import Queue
from typing import Optional, Dict, Tuple, Union,List,Optional
from enum import Enum
from datetime import *
from Messages import TimerMsg
import pandas as pd
import traceback
import asyncio
from   Utils import *
import copy

@dataclass
class OneTask:
    name: str
    timeEntryStatus:datetime
    status:int = "idle"
    maxTimeWorking =timedelta(seconds=0)
    maxTimeIdle= timedelta(seconds=0)
    timeInIdle=timedelta(seconds=0)
    timeInWork=timedelta(seconds=0)


class ThTimer:
    def __init__(self, 
            out_Strat   :asyncio.Queue,
            out_Bkr     :asyncio.Queue,
            out_Sdata   :asyncio.Queue,
            interval    :float,
            #logger,
            ):
    

        #super().__init__(daemon=True)
        self.out_Strat  = out_Strat
        self.out_Bkr    = out_Bkr
        self.out_Sdata  = out_Sdata

        self.interval = interval
        
        columnas = ["Source","Symbol","TypeTimer","Id","Set","Delay","Fin","Notify"]
        self.signals=pd.DataFrame(columns=columnas)

        self.log =  get_logger("TIMER")

        ############ FUTUR SIMULATION
        #self.simulated = settings.get('simulated', False)
        #self.current_time = settings.get('start_time') if self.simulated else None
        #self.end_time = settings.get('end_time') if self.simulated else None
        #self.delta = settings.get('delta', timedelta(minutes=1))

        
        self.task_status: Dict[str , OneTask] = {}
        self.RegisterTask("SYS")

       #para threads
        #self._stop_event = threading.Event()



    def RegisterTask(self, task_name):
        if task_name not in self.task_status:
            self.task_status[task_name] = OneTask(name=task_name, status="idle",timeEntryStatus=self.getNow())
    
    def SetTaskStatus(self, task_name, status):
        iTask= self.task_status.get(task_name)

        if iTask!=None:
            nowStatus = iTask.status
            if(status== nowStatus):
                return # Entra mucho en idle
            
            timeNow= self.getNow()
            if(status=="idle" and nowStatus=="working"):
                timeWorking= timeNow-iTask.timeEntryStatus
                if(timeWorking>iTask.maxTimeWorking): 
                    iTask.maxTimeWorking=timeWorking

            elif(status=="working" and nowStatus=="idle"):
                timeIdle= timeNow-iTask.timeEntryStatus
                if(timeIdle>iTask.maxTimeIdle): 
                    iTask.maxTimeIdle=timeIdle

            #elif (status=="idle" and nowStatus=="idle"):
            #    self.log.error(f"-------------Sincronizando IDLES {task_name} estados now:{status} antes:{nowStatus}---------------")
            
            iTask.status=status 
            iTask.timeEntryStatus=timeNow

            #chequeo sistema completo
            iTaskSys=self.task_status.get("SYS")
            nowStatusSys = iTaskSys.status
            if self.AllTaskIdle():
                statSys="idle"
            else:
                statSys="working"

            if(nowStatusSys!= statSys):
                if(statSys=="idle" ):
                    timeWorking= timeNow-iTaskSys.timeEntryStatus
                    if(timeWorking>iTaskSys.maxTimeWorking): 
                        iTaskSys.maxTimeWorking=timeWorking

                    iTaskSys.timeInWork+=timeWorking

                elif(statSys=="working"):
                    timeIdle= timeNow-iTaskSys.timeEntryStatus
                    if(timeIdle>iTaskSys.maxTimeIdle): 
                        iTaskSys.maxTimeIdle=timeIdle
                    
                    iTaskSys.timeInIdle+=timeIdle
                                   
                iTaskSys.status=statSys 
                iTaskSys.timeEntryStatus=timeNow
            else:
                iTaskSys.timeInStatus=timeNow-iTaskSys.timeEntryStatus
        else:
            self.RegisterTask(task_name)


    def AllTaskIdle(self):
        for name, task in self.task_status.items():
          if(task.name!="SYS" and task.status!="idle"):
            return False
        return True
        #all(task.status == 'idle' for name, task in self.task_status.items(): task.name!="SYS )
        

    def ShowTaksTime(self):
        self.log.info(f"----------------------- STATUS TAKS----------------------------------------")
        for key, task in self.task_status.items():
            secWork = int(task.maxTimeWorking.total_seconds())
            msWork =    task.maxTimeWorking.microseconds // 1000
           
            secIdle = int(task.maxTimeIdle.total_seconds())
            msIdle =    task.maxTimeIdle.microseconds // 1000
            if(task.name=="SYS"):
                secWStat = int(task.timeInWork.total_seconds())
                msWStat =    task.timeInWork.microseconds // 1000
                secIStat = int(task.timeInIdle.total_seconds())
                msIStat =    task.timeInIdle.microseconds // 1000
                self.log.info(f"TASK {task.name:<10} status:{task.status:<15} Max.Time Working:{secWork:02}:{msWork:03}  Max.Time IDLE:{secIdle:02}:{msIdle:03} Time in WORK:{secWStat:04}:{msWStat:03} Time in IDLE:{secIStat:04}:{msIStat:03} ")
            else:
                self.log.info(f"TASK {task.name:<10} status:{task.status:<15} Max.Time Working:{secWork:02}:{msWork:03}  Max.Time IDLE:{secIdle:02}:{msIdle:03} ")

        self.log.info(f"----------------------- STATUS TAKS----------------------------------------")
        return
    

    """
    def advance_time(self):
        if self.simulated:
            self.current_time += self.delta
            if self.current_time >= self.end_time:
                raise SimulationEnd()
    """
     
        
    async def BuscaTimeVencido(self):
        now =  self.getNow()
        for index, fila in self.signals.iterrows():
            
            if now>=fila['Fin'] :
                #Timer vencido
                msgPeriod = TimerMsg(
                    #type=MsgType.TIMER,  # se puede pasar o se ignora
                    source      =fila["Source"],
                    symbol      =fila["Symbol"],
                    typeTimer   =fila["TypeTimer"],
                    id          =fila["Id"],
                    set         =fila["Set"],
                    delay       =fila["Delay"],
                    fin         =fila["Fin"],
                    #notify      =fila["Notify"], no hace falta en el mensaje de vuelta
                )
                msgTimer=copy.deepcopy(msgPeriod)

                await fila['Notify'].put(msgTimer)
                if fila['TypeTimer'] =="PERIODIC":
                    self.signals.at[index,'Fin']  = fila['Fin']+timedelta(seconds=fila['Delay'])
                else:
                    self.signals.drop(index, inplace=True)
                    self.log.info(self.signals)
        

    async def run(self):
        try:
           
            while True:
                now =  self.getNow()
                await self.BuscaTimeVencido()


                fecha_formateada = now.strftime("%d/%m/%Y %H:%M:%S")
                #self.log.info(fecha_formateada)  # Ejemplo: 27/06/2025 15:30:45


                await asyncio.sleep(0.1)
                #await asyncio.sleep(delay)
            
        except Exception as e:
            self.log.error(f"ERROR en [TIMER]: {e}")
            #traceback.print_exc()  # Imprime el stack trace

            
        

    def SetTimer( self, msg:TimerMsg):
        
        self.log.debug("SET TIMER")
        
        if msg.fin==None:
            msg.fin= msg.set+timedelta(seconds=msg.delay)
        msg.fin=msg.fin.replace(microsecond=0)
        row = {
                "Source"    : msg.source,
                "Symbol"    : msg.symbol,
                "TypeTimer" : msg.typeTimer, 
                "Id"        : msg.id,
                "Set"       : msg.set,
                "Delay"     : msg.delay,
                "Fin"       : msg.fin,
                "Notify"    : msg.notify,
            }               

        if msg.typeTimer == "PERIODIC":
            mask = (
                (self.signals["TypeTimer"] == "PERIODIC") &
                (self.signals["Notify"] == msg.notify) & 
                (self.signals["Id"] == msg.id)
            )
            if mask.any():
                self.log.warning(f"[WARNING] Timer PERIODIC ya definido  {msg.Symbol},source:{msg.source}- {msg.notify}")
                self.signals.loc[mask, ["Delay", "Fin"]] = [msg.delay, msg.fin]
            else:
                self.signals.loc[len(self.signals)] = row #añadir row al final
        else:             
            self.signals.loc[len(self.signals)] = row #añadir row al final
             
        self.log.debug(f" MENSAJE SET TIMER :signals. {self.signals["TypeTimer"].iloc[-1]}")            
        self.log.debug(self.signals.head())
        
    def getNow(self):
        #return self.current_time if self.simulated else datetime.now()
        return datetime.now(timeZone)

    def getNowUTC(self):
        
        return datetime.now(pytz.utc)

    def getNowLocal(self):
        
        return datetime.now()
