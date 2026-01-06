import threading
from queue import Queue
from Messages import TimerMsg
from ThTimer import ThTimer
import pandas as pd
import asyncio
from Messages import *
from  Utils import *
from  Operation import *
from datetime import *
import copy

class ThSymbolData:
    def __init__(self, 
                 
                    in_Bkr:     asyncio.Queue, 
                    in_Strat:   asyncio.Queue, 
                    in_Timer:   asyncio.Queue,

                    out_Bkr:    asyncio.Queue,
                    out_Strat:  asyncio.Queue,

                    table_Scan:pd.DataFrame,
                    bloq_Scan,
                    table_Operation:Operation,
                    bloq_Operation,
                    timer: ThTimer,
                    #logger

                ):
        
        #super().__init__(daemon=True) 
               
        self.in_Bkr     = in_Bkr 
        self.in_Strat   = in_Strat
        self.in_Timer   = in_Timer

        self.out_Bkr    = out_Bkr
        self.out_Strat  = out_Strat

        self.t_Scan     = table_Scan
        self.lock_Scan  = bloq_Scan

        self.t_Oper= table_Operation
        self.lock_Oper = bloq_Operation

        self.timer = timer
        self.log =  get_logger("SDATA")

        ################### OPERATIVOS ########################
        self.Time0 =    datetime(1980, 1, 1, 00, 00, 0,tzinfo=timeZone)  # Año, mes, día, hora, minuto, segundo -> en timezone
        self.lastDay =  self.Time0
        self.ScanActivo=False

        self.RxScan =   self.Time0

        ################### OPERATIVOS ########################

        self.log.info (f"TAREA [SDATA] INCIALIZADA id(t_Scan):{id(self.t_Scan)}  id(t_Oper):{id(self.t_Oper)}")
        msgPeriod = TimerMsg(
                            #type=MsgType.TIMER,  # se puede pasar o se ignora
                            source="SDATA",
                            symbol="ALL",
                            typeTimer="PERIODIC",
                            id= "FRAME",
                            set=self.timer.getNow(),
                            delay=10,
                            fin=self.timer.getNow()+timedelta(seconds=5),  #la primera entrada a los 5 sec
                            notify=self.in_Timer
                        )
            
        self.timer.SetTimer(msgPeriod)
        #self._stop_event = threading.Event()

 
    async def run(self):
        self.timer.RegisterTask("SDATA")
        try:
            ## Al INICIO lanza scanner
         
            while True:
                await self.read_msg()
                self.timer.SetTaskStatus("SDATA","idle")
                await asyncio.sleep(0.005)

        except Exception as e:
                self.log.error(f"Exception : {str(e)}")
    

    ### Arquitectura preferible para varias colas
    async def read_msg(self):

        try:
            msg = self.in_Bkr.get_nowait()
            self.timer.SetTaskStatus("SDATA","working")
            await self.process_msg_Bkr(msg)
        except asyncio.QueueEmpty:
            pass

        try:
            msg = self.in_Timer.get_nowait()
            self.timer.SetTaskStatus("SDATA","working")
            await self.process_msg_Timer(msg)
        except asyncio.QueueEmpty:
            pass

        try:
            msg = self.in_Strat.get_nowait()
            self.timer.SetTaskStatus("SDATA","working")
            await self.process_msg_Strat(msg)
        except asyncio.QueueEmpty:
            pass


    """
    async def read_msg(self):
        
        while not self.in_Bkr.empty():
            msg = await self.in_Bkr.get()
            await self.process_msg_Bkr(msg)

        while not self.in_Timer.empty():
            msg = await self.in_Timer.get()
            #self.log.info(f'mensaje timer {msg.set}')
            await self.process_msg_Timer(msg)

        while not self.in_Strat.empty():
            msg = await self.in_Strat.get()
            await self.process_msg_Strat(msg)

    """        

    async def process_msg_Timer(self,msg):
        # Responder con datos de precios, históricos, etc.
        self.log.info(f"Mensaje RX TIMER DATA: id={msg.id} -Set:{msg.set}- FIN:{msg.fin}")
        self.log.info (f"TAREA [SDATA] TIMER  id(t_Scan):{id(self.t_Scan)}  id(t_Oper):{id(self.t_Oper)}")
        await self.GestionaDataTime()


    async def GestionaDataTime(self):
        
        hoy =self.timer.getNow()
        horaNow = hoy.time()
        fechaNow= hoy.date()
     
        ##  PROCESO PRINCIPIO DIA

        T_IniScan = time.fromisoformat(cfSys['OperationTime']['iniScan'])
        T_FinScan = time.fromisoformat(cfSys['OperationTime']['finScan'])
   
        if(hoy.day != self.lastDay.day):
              
            # limpia Scan a principio de DIA
           
            # limpia Scan a principio de DIA: Eliminar todas las filas pero mantener la estructura de columnas
            with self.lock_Scan:
                self.t_Scan.drop(self.t_Scan.index, inplace=True)
            
            self.log.info(f"SCAN Inicio {T_IniScan} fin  {T_FinScan} now: {horaNow}")

            #Desactivo el scanner hasta hora comienzo, si está activo
            if(self.ScanActivo==True):
                await self.EnviaCancelScan() #pone a FALSE LA ACTIVACION
            
            self.lastDay= hoy

        ##  PROCESO INICIO SCAN 
        
        # Pido  scaner por encima de hora INI scan  and ScanActivo==False
        lastScanDay=self.RxScan.date()
        
        if(horaNow>=T_IniScan and horaNow<T_FinScan and self.ScanActivo==False and lastScanDay<fechaNow ):
            #Iniciar SCAN entre horas, si no esta activo y hoy no se recibio
            await self.EnviaRequestScan()

        if( horaNow>=T_FinScan and self.ScanActivo==True  ):
            #Iniciar SCAN entre horas, si no esta activo y hoy no se recibio
            await self.EnviaCancelScan()


        # cancelo scaner a hora fin scan ScanActivo==False




    """
        "TOP_PERC_GAIN"  Mayores ganancias porcentuales del día.
        "TOP_PERC_LOSE"  Mayores pérdidas porcentuales del día.
        "TOP_OPEN_PERC_GAIN"  Mayores ganancias en la apertura.
        "TOP_OPEN_PERC_LOSE"  Mayores pérdidas en la apertura.
        "TOP_TRADE_COUNT"  Más activos por número de operaciones.
        "TOP_TRADE_RATE"  Más activos por ratio de operaciones.
        "TOP_PRICE_RANGE"  Mayores rangos de precio del día.
    """

    async def EnviaRequestScan(self):

       
        msgSCAN = ScanRequestMsg(
                        source="SDATA",
                        symbol="ALL",

                        scan_code        =cfSys['Scanner']['code'],
                        instrument       =cfSys['Scanner']['instrument'],
                        location_code    =cfSys['Scanner']['location_code'],
                        number_of_rows   =cfSys['Scanner']['number_Symbol'],
                        above_price      =cfSys['Scanner']['above_price'],
                        above_volume     =cfSys['Scanner']['above_volume'],
                        market_cap_below =cfSys['Scanner']['market_cap_below'],
                        market_cap_above =cfSys['Scanner']['market_cap_above'],
                        )
        
        self.log.info(f'ENVIO REQUEST SCANNER {msgSCAN.scan_code}')
        #NO HACE FALTA self.RxScan=self.Time0
        self.ScanActivo=True
        await self.SendMsg("BKR",msgSCAN)

    async def EnviaCancelScan(self):
        msgCancel = ReqCancelScan(
                            source="SDATA",
                            symbol="ALL"
                        )
        
        await self.SendMsg("BKR",msgCancel)
        #await self.out_Bkr.put(msgCancel) #Envio mensaje al Broker  de momento solo un escan       
        self.log.info(f'ENVIO CANCEL SCANNER ')          
        self.ScanActivo=False
        # NO---.RxScan=self.Time0

    async def ProcesaMsgScan(self,msg):
        #self.log.debug(f'tscan { msg.results}')
        #self.log.info(f"RX SCANNER ")
        self.RxScan=self.timer.getNow()

        #await self.EnviaCancelScan()  #Esto no se hará aquí
         
        #self.log.debug(f"HEAD Symbols SCANNER RECIBIDO {msg.results[:5]}")  

        # Supongamos que msg.results es una lista de símbolos
        # Filtrar símbolos nuevos que no estén ya en t_Scan
        simbolos_existentes = set(self.t_Scan[CData.SYMBOL])        ## set hace que no se repitan los simbolos

        nuevos_simbolos = [s for s in msg.results if s not in simbolos_existentes]
        n_filas = len(nuevos_simbolos)
        self.log.debug(f"SCANNER RECIBIDO: HEAD NUEVOS {nuevos_simbolos[:5]}")  

        if n_filas > 0:
            # Crear DataFrame temporal con los nuevos símbolos
            df_nuevas = pd.DataFrame({CData.SYMBOL: nuevos_simbolos})

            # Inicializar columnas adicionales
            df_nuevas[CData.BID]        = 0.0
            df_nuevas[CData.ASK]        = 0.0
            df_nuevas[CData.CAP]        = 0.0
            df_nuevas[CData.PVARDAY]    = 0.0
            df_nuevas[CData.CLOSE_DAY]  = 0.0

            # Usar listas para columnas tipo objeto (evita errores de asignación)
            df_nuevas[CData.HDAY]       = [pd.DataFrame(columns=columnas_hist) for _ in range(n_filas)]
            df_nuevas[CData.H1MIN]      = [pd.DataFrame(columns=columnas_hist) for _ in range(n_filas)]

            df_nuevas[CData.LASTIME]    = None #pd.NaT
            df_nuevas[CData.CTRLDATA]   = ""
            df_nuevas[CData.H_NOW]      = 0.0
            df_nuevas[CData.L_NOW]      = 0.0
            df_nuevas[CData.O_NOW]      = 0.0
            df_nuevas[CData.VOL_NOW]    = 0.0

            # Añadir filas sin romper la referencia de t_Scan
            with self.lock_Scan:
                for i in range(n_filas):
                    self.t_Scan.loc[len(self.t_Scan)] = df_nuevas.iloc[i]

    
            #self.log.debug(f"t_scan {self.t_Scan}")  
            ## SOLO PARA LAS NUEVAS, PIDO LA INFO BASE DE SCAN
            
            #for index, row in self.t_Scan.iterrows():
            for i in range(n_filas):           
                #symbol= row[CData.SYMBOL]
                symbol=nuevos_simbolos[i]   #recorro nuevos simbolos
    
                await self.SendReqDayBar(symbol)

                """ SOLO PEDIRE MINUTOS DEL FOCUS"""
                
                if(cfSys['ParamOp']['autoTick']=="SI"):
                    await self.SendReqTick(symbol)
                

                if(cfSys['ParamOp']['autoData']=="SI"):    
                    await self.SendReq1MinBar(symbol)
                    await self.SendReqTRBar(symbol)


        #self.log.debug (f"TAREA [SDATA] SCANN id(t_Scan):{id(self.t_Scan)}  id(t_Oper):{id(self.t_Oper)}")       


    async def SendReqDayBar(self, symbol):
        inicio= self.timer.getNowUTC()-timedelta(days=350)
        fin =self.timer.getNowUTC()-timedelta(days=1) #historico DAY desde ayer
        fin=fin.replace(hour=23,minute=59,second=0)
        msgHisto = HistoricalMsg(
                source="SDATA",
                symbol=symbol,
                inicio=inicio,
                fin=fin,
                bar_size="1 day",
                out_market=False
            )
        #await self.out_Bkr.put(msgHisto) #Envio mensaje al Broker  
        await self.SendMsg("BKR",msgHisto)


    async def SendReq1MinBar(self, symbol):
        inicio= self.timer.getNowUTC()-timedelta(days=2)
        fin =self.timer.getNowUTC()
        """"""
        msgMin = HistoricalMsg(
                source="SDATA",
                symbol=symbol,
                inicio=inicio,
                fin=fin,
                bar_size="1 min",
                out_market=True
            )
        #await self.out_Bkr.put(msgMin) #Envio mensaje al Broker  
        await self.SendMsg("BKR",msgMin)


    async def SendReqTick(self, symbol):
                msgTick = TickMsg(
                        source="SDATA",
                        symbol=symbol,
                        time=self.timer.getNow()
                    )
                await self.SendMsg("BKR",msgTick)

    async def SendReqTRBar(self, symbol):
                msgTRBar = TRBar(
                        source="SDATA",
                        symbol=symbol,
                        time=self.timer.getNow()
                    )
                await self.SendMsg("BKR",msgTRBar)
            

    def limpiar_df_historia(self,df: pd.DataFrame) -> pd.DataFrame:
        """
        - No modifica la columna original 'date'
        - Crea un nuevo índice basado en datetime(date)
        - Elimina duplicados en el índice, manteniendo el último
        """
        df = df.copy()
        if "date" not in df.columns:
            self.log.error("El DataFrame no tiene columna 'date'")

        # Crear índice datetime a partir de 'date' (sin modificar la columna original)
        index_datetime = pd.to_datetime(df["date"])

        # Asignar el nuevo índice (datetime) sin tocar la columna 'date'
        df.index = index_datetime

        # Eliminar duplicados en el nuevo índice
        df = df[~df.index.duplicated(keep="last")]
        return df



    async def ProcesaDataDay1Min(self,symbol):
        self.log.info(f"PROCESA DATA 1MIN {symbol}")

        mask = (self.t_Scan[CData.SYMBOL] == symbol)
        indices_filtrados = self.t_Scan.index[mask]
        if not indices_filtrados.empty:
            idx = indices_filtrados[0]
            
            #df_h1min    = self.t_Scan.loc[mask, CData.H1MIN] #es serie de dataframes
            df_h1min    = self.t_Scan.at[idx, CData.H1MIN] #el data frame completo del index=idx
            
            dateNow=self.timer.getNow().date()
            
            finDateTime=self.timer.getNow().replace(hour=23,minute=59,second=00)
            timeLast=finDateTime.time()

            open=0
            high=0
            low=0
            vol=0
            
            for ix in range(0, len(df_h1min)):
            #for ix in range(len(df_h1min)-1, -1, -1):                
                today = df_h1min.iloc[ix]

                dateToday=today["date"]
                if(ix==0 or ix== len(df_h1min)-1 or ix== len(df_h1min)-2):
                   self.log.info(f"###################### data 1min {symbol:<8}--dateToday {dateToday}  -h:{today["high"]:>8}-l:{today["low"]:>8} vol:{today["volume"]:>15} open:{today["open"]:>8}")
                if(dateToday.date()== dateNow ):
                    
                    if(today["high"]>high or high==0):
                        high=today["high"]

                    if(today["low"]>high or low==0):
                        low=today["low"]

                    if( dateToday.time()<timeLast or open==0):
                        open=today["open"]
                        timeLast= dateToday.time()
                    vol += today["volume"]

            self.log.info(f"------------------------------------------DATA TOTAL DAY (1min) {symbol}--dateToday {dateToday} dateNow {dateNow} -h:{high}-l:{low} vol:{vol} open:{open}")
            self.t_Scan.at[idx, CData.H_NOW]    = high 
            self.t_Scan.at[idx, CData.L_NOW]    = low 
            self.t_Scan.at[idx, CData.VOL_NOW]  = vol 
            self.t_Scan.at[idx, CData.O_NOW]    = open 
        else:
            self.log.error(f"ProcesaDataDay1Min index error para {symbol}")

    async def ProcesaMsgHistoria(self,msg):
    
        if(msg.bar_size=="1 day"):
            colHist =CData.HDAY
            self.log.info(f"RX HISTORY {msg.symbol}  {msg.bar_size} {colHist}")
        elif msg.bar_size=="1 min":
            colHist =CData.H1MIN
            self.log.info(f"RX HISTORY {msg.symbol}  {msg.bar_size} {colHist}")
        else: 
            self.log.error(f"RX HISTORY BAR SIZE INCORRECTO  {msg.bar_size} ")
            colHist=""
            return
        
            
        try: 
            mask = (self.t_Scan[CData.SYMBOL] == msg.symbol)
            # Limpiar nuevo df recibido
            #self.log.info(f"HISTORIC DATA {msg.data}")
            df_nuevo = self.limpiar_df_historia(msg.data)

            # Obtener el existente (si lo hay)
            with self.lock_Scan:  
                df_existente = self.t_Scan.loc[mask, colHist].values[0]

            # Concatenar solo si hay entradas válidas
            dfs_validos = [
                df for df in [df_existente, df_nuevo]
                if isinstance(df, pd.DataFrame) and not df.empty and not df.isna().all().all()
            ]

            df_combinado = pd.concat(dfs_validos, ignore_index=True) if dfs_validos else pd.DataFrame(columns=columnas_hist)

            
            # Limpiar combinados
            df_final = self.limpiar_df_historia(df_combinado)
            
            with self.lock_Scan:  
                # Asignar como objeto a la celda
                idx = self.t_Scan.index[mask][0]  # obtener el índice real

                #self.t_Scan.loc[mask, "HDay"].values[0] = df_final
                self.t_Scan.at[idx, colHist] = df_final
                
                CtrlSinc = self.t_Scan.at[idx, CData.CTRLDATA]
                if colHist not in CtrlSinc:
                    CtrlSinc += colHist  # ✅ Más conciso
                self.t_Scan.at[idx, CData.CTRLDATA] = CtrlSinc
                
                df = self.t_Scan.loc[mask, colHist].values[0]
                if(colHist==CData.HDAY):
                    self.t_Scan.at[idx, CData.CLOSE_DAY] = df.iloc[-1]["close"]
                
                if(colHist==CData.H1MIN):
                    await self.ProcesaDataDay1Min(msg.symbol)
                self.log.debug(f"DATAFRAME {msg.symbol} {msg.bar_size} LAST CLOSE {df.iloc[-1]["close"]} ")
                #self.log.debug(f"DATAFRAME {msg.symbol} first value df_final {df.iloc[0]} ")
                #self.log.debug(f"DATAFRAME {msg.symbol} last value df_final {df.iloc[-1]} ")
                
                #self.log.info(f"DATAFRAME {msg.symbol} df_final {df_final} ")
                #self.log.info(f"DATAFRAME {msg.symbol} datos {self.t_Scan.loc[mask, colHist].values[0]} ")
            
        except Exception as e:
            self.log.error(f'HISTORY EXCEPTION- {e} nuevo {df_nuevo} existente {df_existente} combinado {df_combinado}')
            
            
            
            self.log.info (f"TAREA HISTORY id(t_Scan):{id(self.t_Scan)}  id(t_Oper):{id(self.t_Oper)}")



    async def ProcesaMsgTRBar(self,msg):

        #self.log.info(f"TR BARRA {msg}")
        #self.log.info(f"TR ESTA ES LA DATE date {msg.time}")

        nueva_barra = {
            "date":     msg.time, #pd.to_datetime(msg.time, utc=True),  # Usamos inicio de la barra como datetime
            "open":     msg.open,
            "high":     msg.high,
            "low":      msg.low,
            "close":    msg.close,
            "volume":   msg.vol,
            "average":  0,
            "barCount": 0
        }       
        
       
        nueva_barra["date"] = nueva_barra["date"].replace(microsecond=0)
        
        nueva_fila = pd.DataFrame([nueva_barra])
        
        #self.log.debug(f" NUEVA BAR {nueva_fila}")

        # Crear índice datetime a partir de 'date' (sin modificar la columna original)
        index_datetime = pd.to_datetime(nueva_fila["date"])
        # Asignar el nuevo índice (datetime) sin tocar la columna 'date'
        nueva_fila.index = index_datetime
        #self.log.debug(f" NUEVA BAR {nueva_fila}")

        #nueva_fila = pd.DataFrame([nueva_barra]).set_index("date")

       
        #nueva_fila['date'] = nueva_fila['date'].dt.tz_convert(cfSys['zoneTime']) #convertidas a TIMEZONE

        # Paso 2: obtener el índice de la nueva fila
        new_idx = pd.to_datetime(nueva_fila.index[0])  # suponiendo nueva_fila tiene un solo índice

     
        mask = (self.t_Scan[CData.SYMBOL] == msg.symbol)
        colHist =CData.H1MIN
        with self.lock_Scan:  
                # Asignar como objeto a la celda
                idx = self.t_Scan.index[mask][0]  # obtener el índice real
                df_hist = self.t_Scan.at[idx, colHist]
                if df_hist is None or not isinstance(df_hist, pd.DataFrame):
                    # Inicializar con columna y estructura correcta si es necesario
                    self.t_Scan.at[idx, colHist] = nueva_fila.copy()
                else:
                    df_hist.loc[new_idx] = nueva_fila.iloc[0]
                    df_hist.loc[new_idx, "date"] = new_idx
                    df_hist.sort_index(inplace=True)        

                await self.ProcesaDataDay1Min(msg.symbol)
                      
        return

    async def ProcesaMsgTick(self,msg):

        #self.log.debug(f"TICK SDATA {msg.symbol}  bid:{msg.bid}  ask:{msg.ask}") #ojo, solo en TR
        with self.lock_Scan:   
            mask = (self.t_Scan[CData.SYMBOL] == msg.symbol)
            self.t_Scan.loc[mask, [CData.BID, CData.ASK]] = [msg.bid,msg.ask]
            if(msg.time!=None):
                self.t_Scan.loc[mask, CData.LASTIME]=msg.time
            
            #self.log.info (f"TAREA [SDATA] DATA id(t_Scan):{id(self.t_Scan)}  id(t_Oper):{id(self.t_Oper)}")


    
    async def process_msg_Bkr(self,msg):
        
        # Procesar datos de mercado recibidos
        # Actualizar estructura interna de datos
        if msg.type == MsgType.SCANNER:
           
            await self.ProcesaMsgScan(msg)
      
        elif msg.type == MsgType.HISTORIA:
            await self.ProcesaMsgHistoria(msg)
           
        
        elif msg.type == MsgType.PRICE_TICK:
            await self.ProcesaMsgTick(msg)

        elif msg.type == MsgType.TR_BAR:
            self.log.info(f"Mensaje RX TR_BAR {msg}")
            await self.ProcesaMsgTRBar(msg)

        return
        

    async def ProcesaMsgControl(self,msg):
        if(msg.action == ControlAction.CANCEL_SUSCRIP):
            self.log.info(f"Mensaje RX CANCEL_SUSCRIP  {msg}")
            if (msg.symbol =="ALL"):
                self.log.info(f"Mensaje req CANCEL_SUSCRIP all SUSCRIPCION: {msg}")
            else:
                #await self.out_Bkr.put(msg) #Envio mensaje al Broker  
                self.log.info(f"Mensaje req CANCEL_SUSCRIP to BKR")
                msgCtrlData = ControlMsg(
                            source="SDATA",
                            symbol=msg.symbol,
                            action= ControlAction.CANCEL_SUSCRIP,
                        )
                await self.SendMsg("BKR",msgCtrlData)

        elif msg.action == ControlAction.REQ_TR_BAR:
                await self.SendReqTRBar(msg.symbol)

        elif msg.action == ControlAction.REQ_TICK:
                await self.SendReqTick(msg.symbol)

        elif msg.action == ControlAction.REQ_1MIN_BAR:
                await self.SendReq1MinBar(msg.symbol)
        
        elif msg.action == ControlAction.REQ_1MIN_TOT:
                await self.SendReq1MinBar(msg.symbol)
                await self.SendReqTRBar(msg.symbol)


        else:
                return
                



    async def process_msg_Strat(self,msg):
        # Responder con datos de precios, históricos, etc.

        if msg.type == MsgType.CONTROL:
            await self.ProcesaMsgControl(msg)
    


    async def SendMsg(self,destino,msg):
        self.log.debug(f"SEND MSSG destino  {destino}-----{msg.type}")
        if(destino=="BKR"):
            await self.out_Bkr.put(copy.deepcopy(msg)) #Envio mensaje a broker
        elif(destino=="STRAT"):
            await self.out_Strat.put(copy.deepcopy(msg)) #Envio mensaje al strat
        else:
            self.log.error(f"SEND MSSG destino sin definir {msg}")
            return
