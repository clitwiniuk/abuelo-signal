from ThBkr import ThBkr
from ThSymbolData import ThSymbolData
from ThStrategy import ThStrat
from ThTimer import ThTimer
from queue import Queue
from threading import Lock
from datetime import datetime,timedelta,timezone

import pandas as pd
import asyncio
import yaml
from   Utils import *
from   Operation import *

"""
main.py
├── ThBr (Thread)
├── ThTimer (Thread) ← genera eventos periódicos y alarmas
└── ThStrat (Thread)
└── ThSymbolData(Thread)

Shared tabla Contrato. Scan y Focus
"""

async def main():

    # 1. Crear estructuras compartidas
    #columnas =[ "Symbol", "Bid", "Ask", "Cap", "PVarDay", "CloseDay", "HDay", "H1Min", "LastTime" "CtrlData"]

    #columnas =[ col.value for col in CData] como Enum

    Columnas_dataclass = CData.get_columns_value()
    
    t_Scan = pd.DataFrame(columns=Columnas_dataclass)            #    "Symbol, Bid Ask, Cap, PVarDay, CloseDay, HDay, H1Min,"

    
    empty_history_df = pd.DataFrame(columns=columnas_hist)
    #empty_history_df.set_index("date", inplace=True) #el indice es date

    # Asegurar que la columna HDay pueda almacenar objetos
    
    t_Scan[CData.CTRLDATA] = t_Scan[CData.CTRLDATA].astype("string")
    t_Scan[CData.LASTIME]  = pd.to_datetime(t_Scan[CData.LASTIME]) # t_Scan[CData.LASTIME].astype("datetime64[ns]")

    t_Scan[CData.HDAY] = None
    t_Scan[CData.HDAY] = t_Scan[CData.HDAY].astype(object)
    
    t_Scan[CData.H1MIN] = None
    t_Scan[CData.H1MIN] = t_Scan[CData.H1MIN].astype(object)
   #for i in t_Scan.index:
    #    t_Scan.at[i, "HDay"] = empty_history_df.copy()

    #t_Focus= pd.DataFrame(columns=columnas)               # o un pandas.DataFrame

    t_Oper = Operation()

    lock_Scan   = Lock()    
    
    lock_Oper = Lock()

    # Comunicación entre threads
    q_Bkr_Sdata = asyncio.Queue(maxsize=0)
    q_Sdata_Bkr = asyncio.Queue(maxsize=0)
    
    q_Bkr_Strat = asyncio.Queue(maxsize=0)
    q_Strat_Bkr = asyncio.Queue(maxsize=0)

    q_Sdata_Strat = asyncio.Queue(maxsize=0)
    q_Strat_Sdata = asyncio.Queue(maxsize=0)

    q_Timer_Sdata = asyncio.Queue(maxsize=0)
    q_Timer_Bkr   = asyncio.Queue(maxsize=0)
    q_Timer_Strat = asyncio.Queue(maxsize=0)



   
    
    log=setup_logging_system() #solo una vez
    
    # TOMAR LOG threads
    log =  get_logger("SYS")
    
    log.info(cfSys)
    
    log.info("#################################################################################################################")
    log.info("#                                                                                                               #")
    log.info("#                                             INICIANDO TAREAS                                                  #")
    log.info("#                                                                                                               #")
    log.info("#################################################################################################################")
    
    log.info(f"configuracion {cfSys}")
    log.info (f"#COLUMNAS DATAFRAME BASE {Columnas_dataclass}")
    
    mTimer = ThTimer(
        out_Strat   =q_Timer_Strat,
        out_Bkr     =q_Timer_Bkr,
        out_Sdata   =q_Timer_Sdata,
        interval    =1.0,              #1 segundo
        #logger  = logger_Timer
    )

   
    mStrategy = ThStrat(
        in_Sdata    =q_Sdata_Strat,
        in_Bkr      =q_Bkr_Strat,
        in_Timer    =q_Timer_Strat,

        out_Bkr     =q_Strat_Bkr,
        out_SData   =q_Strat_Sdata, #no usado en principio
       

        table_Scan=t_Scan,
        bloq_Scan=lock_Scan,

        table_Operation=t_Oper,
        bloq_Operation=lock_Oper,

        timer= mTimer,
        #logger = logger_Strat,
      
    )   

    mBkr = ThBkr(
        in_SData    =q_Sdata_Bkr, 
        in_Strat    =q_Strat_Bkr,
        in_Timer    =q_Timer_Bkr,

        out_SData   =q_Bkr_Sdata, 
        out_Strat   =q_Bkr_Strat,
 
        table_Scan=t_Scan,
        bloq_Scan=lock_Scan,

        table_Operation=t_Oper,
        bloq_Operation=lock_Oper,

        timer= mTimer,
        #logger  = logger_Bkr,
    )


    mControlData = ThSymbolData(
        in_Bkr      =q_Bkr_Sdata,
        in_Strat    =q_Strat_Sdata,
        in_Timer    =q_Timer_Sdata,        

        out_Bkr     =q_Sdata_Bkr,
        out_Strat   =q_Sdata_Strat,#No usado en principio
    

        table_Scan=t_Scan,
        bloq_Scan=lock_Scan,
        
        table_Operation=t_Oper,
        bloq_Operation=lock_Oper,

        timer= mTimer,
        #logger  = logger_Sdata,
       )

    try: 
        log.info("LANZANDO TAREAS")
        await asyncio.gather(
        
            mTimer.run(), 
            mBkr.run(),   
            mControlData.run(),
            mStrategy.run(),
           
            
            )

    except asyncio.CancelledError:
        log.info("Tareas canceladas por el bucle")
    finally:
        log.info("Finalizando...")

  


if __name__ == "__main__":
   try:
            asyncio.run(main())
   except   KeyboardInterrupt:
        print(" Interrupción por teclado detectada (Ctrl+C)")
