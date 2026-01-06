#import threading
import time
#from queue import Queue

from ThTimer import ThTimer
import pandas as pd

from datetime import *
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
import copy

class ThBkr:

    def __init__(self, 
                 
                    in_SData: asyncio.Queue, 
                    in_Strat: asyncio.Queue, 
                    in_Timer: asyncio.Queue,

                    out_SData: asyncio.Queue,
                    out_Strat: asyncio.Queue,

                    table_Scan:pd.DataFrame,
                    bloq_Scan,
                    
                    table_Operation:Operation,
                    bloq_Operation,

                    timer: ThTimer,
                    #logger

                ):
        
        #super().__init__(daemon=True)     
        #    
        self.in_SData   = in_SData 
        self.in_Strat   = in_Strat
        self.in_Timer   = in_Timer

        self.out_SData  = out_SData
        self.out_Strat  = out_Strat

        self.t_Scan= table_Scan
        self.lock_Scan = bloq_Scan

        self.t_Oper= table_Operation
        self.lock_Oper = bloq_Operation

        self.timer = timer
      
        self.client = IB()
        self.connected = False
        self.keep_running = True
        self.lastConnect = datetime(1980, 1, 1, 00, 00, 0,tzinfo=timeZone)  # Año, mes, día, hora, minuto, segundo -> en timezone
     
        self.retry_count = 0
        self.max_retries = 3
        self.heartbeat=0

        #self._stop_event = threading.Event()
        
        #self.subscribed_contracts = {}
        self.subscribed_tickers = {}
        self.subscribed_rtbar   = {}
        self.client.errorEvent          += self.on_ibkr_error
        self.client.disconnectedEvent   += self.on_ibkr_disconnected
        self.client.accountValueEvent   += self.on_account_value

        self.barAggregator = SimpleBarAggregator(interval_seconds=60)
        self.ScanActivado=False
        """
        self.client.orderStatusEvent    += self.on_order_status
        self.client.execDetailsEvent    += self.on_exec_details
        self.client.positionEvent       += self.on_position_update
        """
        self.scanData = None

        msgPeriod = TimerMsg(
                    #type=MsgType.TIMER,  # se puede pasar o se ignora
                    source="BKR",
                    symbol="ALL",
                    typeTimer="PERIODIC",
                    id= "HEARTBEAT",
                    set=self.timer.getNow(),
                    delay=15,   #15 segundos
                    fin=None,
                    notify=in_Timer
            )
        self.timer.SetTimer(msgPeriod)
        self.log =  get_logger("BKR")  
        
    """
    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.log.info(" RUN INICIADO")
        ## SUBSCRIBE ON CALLBACK
         
        while self.keep_running:
            if not self.connected:
                await self.try_connect()
            
            try:
                await asyncio.gather(
                    self.sincro(),
                    self.request_loop(),
                    )
                
            except Exception as e:
                self.log.error(f" XX Excepción de operación: {e}")
                self.connected = False
                await self.cleanup_connection()
                await asyncio.sleep(1)
            finally:
                await self.cleanup_connection()
        
            await asyncio.sleep(0.1)     # Previene CPU spin en caso de desconexión continua
            
    async def request_loop(self):
        try:
            while self.keep_running and self.connected:
                await self.check_requests()
                
                await asyncio.sleep(0.01)
        except Exception as e:
            self.log.error(f"EXCEPCION request_loop: {e}")


    """
    async def run(self):
        try:
            self.loop = asyncio.get_running_loop()
            self.log.info(" RUN INICIADO")
            self.timer.RegisterTask("BKR_PADRE")

            # Crear tareas independientes
            Strat_task = None
            SData_task = None
            Timer_task = None

            while self.keep_running:
                if not self.connected:
                    self.timer.SetTaskStatus("BKR_PADRE","working")
                    await self.try_connect()
                    self.timer.SetTaskStatus("BKR_PADRE","idle")
                    await asyncio.sleep(0.5)
                try:
                    # Lanzar tareas si no existen o ya finalizaron
                    #await asyncio.sleep(1)
                    if self.connected:
                        if Strat_task is None or Strat_task.done():
                            self.timer.RegisterTask("BKR_STRAT")
                            Strat_task = asyncio.create_task(self.procesar_strat_loop())
                        
                        if SData_task is None or SData_task.done():
                            self.timer.RegisterTask("BKR_SDATA")
                            SData_task = asyncio.create_task(self.procesar_sdata_loop())

                        if Timer_task is None or Timer_task.done():
                            self.timer.RegisterTask("BKR_TIMER")
                            Timer_task = asyncio.create_task(self.procesar_timer_loop())

                    # Esperar un poco para mantener control del ciclo
                    self.timer.SetTaskStatus("BKR_PADRE","idle")
                    await asyncio.sleep(0.005)

                except Exception as e:
                    self.log.error(f" XX Excepción de THBRK: {e}")
                    self.connected = False
                    if  self.connected:
                        await self.cleanup_connection()
                    await asyncio.sleep(1)

                #finally: # Si lo pongo se desconecta
                    #if(self.connected): 
                    #    self.connected = False
                    #    #await self.cleanup_connection()

            await asyncio.sleep(0.05)  # Previene spin del CPU
        
        except asyncio.CancelledError:
            self.log.info("RUN cancelado por asyncio.CancelledError")
            self.keep_running = False
            self.connected = False

        finally:
            self.log.info("RUN FINALIZADO, limpiando conexión...")
            await self.cleanup_connection()  # Si es sync
            self.client=None
            self.connected = False
        #AL SALIR
        #await self.cleanup_connection()
    #FIN

    async def procesar_strat_loop(self):
        while self.keep_running and self.connected:
            try:
                #while not self.in_Strat.empty():
                msg = await self.in_Strat.get()
                self.timer.SetTaskStatus("BKR_STRAT","working")
                await self.process_msg_Strat(msg) # ojo VALIDO solo si hay una cola en el loop, y no bloquea la siguiente
                self.timer.SetTaskStatus("BKR_STRAT","idle")
                
                await asyncio.sleep(0)  #  cede el turno al event loop
                # procesar mensaje desde Strategy
            except Exception as e:
                self.log.exception(f"Error STRAT procesar_strat_loop: {e}")
        
            finally:
                await asyncio.sleep(0)  #  cede el turno al event loop

    async def procesar_sdata_loop(self):
        while self.keep_running and self.connected:
            try:
                #while not self.in_SData.empty():
                msg = await self.in_SData.get()
                self.timer.SetTaskStatus("BKR_SDATA","working")
                await self.process_msg_Sdata(msg) # ojo VALIDO solo si hay una cola en el loop, y no bloquea la siguiente
                self.timer.SetTaskStatus("BKR_SDATA","idle")
                await asyncio.sleep(0)  #  cede el turno al event loop
                # procesar mensaje desde ControlData
            except Exception as e:
                self.log.exception(f"Error BKR_SDATA procesar_sdata_loop: {e}")
            finally:
                await asyncio.sleep(0)  #  cede el turno al event loop

    async def procesar_timer_loop(self):
        while self.keep_running and self.connected:
            try:
                
                #while not self.in_Timer.empty():
                msg = await self.in_Timer.get() # ojo VALIDO solo si hay una cola en el loop, y no bloquea la siguiente
                self.timer.SetTaskStatus("BKR_TIMER","working")
                await self.process_msg_Timer(msg)
                self.timer.SetTaskStatus("BKR_TIMER","idle")
                await asyncio.sleep(0)  #  cede el turno al event loop
            except Exception as e:
                self.log.error(f"Error TIMER procesar_timer_loop: {e}")
            finally:
                await asyncio.sleep(0)  #  cede el turno al event loop

    async def process_msg_Timer(self,msg):
        self.log.info(f"Mensaje RX TIMER: id={msg.id} -Set:{msg.set}- FIN:{msg.fin}")
        if(msg.id=="HEARTBEAT"):
             
            #await self.ProcesaHeartBeat()
            await self.sincro()
            self.lastConnect=self.timer.getNow()
    
    async def sincro(self):
        try:
            if self.connected:
                limit = self.lastConnect+timedelta(minutes=1)
                if self.timer.getNow()>limit:
                    self.client.orderStatusEvent    -= self.on_order_status
                    self.client.execDetailsEvent    -= self.on_exec_details
                    self.client.positionEvent       -= self.on_position_update
                    self.t_Oper.Positions.clear()
                    # En la sincronizacion, no seria preciso tratar ni reqAllOpenOrdersAsync ni reqPositionsAsync ya que los eventos está en callback
                    # preferible anular los callbacks, tratar todo, apuntar en Operaciones, y resolver
                    # De todos modos, Se tratan por si se perdió alguno y no están sincronizados
                    # De reqExecutionsAsync solo hay que tomar permiID y fecha, para incluir en cualquier posición activa. Se comprueba con simbolo, cantidad y precio
                    #
                    
                    #print("😊 👍❤️ ❌✅⚠️🚀📌🔒📅🔍🔄🖥️💾")
                    self.log.warning(f"[SINCRO] ------------------------COMIENZA SINCRONIZACION  {self.timer.getNow().strftime("%Y-%m-%d %H:%M:%S")}---------------------------------------------------")
                    await self.SincroAllOperation()

                    self.lastConnect=self.timer.getNow()      

                    self.log.warning(f"[SINCRO] SINCRONIZACION DONE {self.timer.getNow().strftime("%Y-%m-%d %H:%M:%S")}")
                    self.t_Oper.ShowAll()

                    # PREPARO DE NUEVO LOS CALLBACKS
                    self.client.orderStatusEvent    += self.on_order_status
                    self.client.execDetailsEvent    += self.on_exec_details
                    self.client.positionEvent       += self.on_position_update

               
                #await asyncio.sleep(30)
                
        except Exception as e:
            self.log.exception(f"sincro() EXCEPTION: {e}")

    async def try_connect(self):

        if self.retry_count >= self.max_retries:
            #self.log.debug(f"[ThBkr] XX Máximo de reintentos alcanzado ({self.max_retries}). Esperando sin reconectar.")
            self.retry_count =0
            await asyncio.sleep(15)
            return

        self.log.info(f" Intentando conectar a IBKR... {cfSys['ibkr']['host']},{cfSys['ibkr']['port']}, clientId={cfSys['ibkr']['clientId']} (intento {self.retry_count + 1})")
        try:
            await self.client.connectAsync(cfSys['ibkr']['host'],cfSys['ibkr']['port'], clientId=cfSys['ibkr']['clientId'])
            #self.client.connect('127.0.0.1', 7497, clientId=1)
            if self.client.isConnected():
                self.connected = True
                self.retry_count = 0
                self.log.info("Conectado a IBKR")
                # Usamos el loop principal para llamar reqAllOpenOrders
                #await asyncio.sleep(0)
                #await self.client.reqAllOpenOrders()
                #self.client.reqAccountUpdates(True) #no hace falta pedirlo si esta subscrdito

                #await self.ReqHistoric( "AAPL", startTime=getNow()-timedelta(days=400), endTime=getNow(), barSize='1 day')
                
                #ticker=await self.GetPrice( "AAPL")
                #self.log.debug(ticker)

                #self.SubscribePrice("AAPL")

                #await self.SetOrder(symbol='AAPL', accion='BUY', cantidad=50, tipo_orden="LMT",precio_limite=211.4,stop_loss=None,take_profit=None)# stop_loss=190.0,take_profit=250.0)
                #await self.SetOrder(symbol='AAPL', accion='BUY', cantidad=100, tipo_orden="LMT",precio_limite=150.0, stop_loss=145.0)
               

        except Exception as e:
            self.retry_count += 1
            self.log.warning(f"Conexión fallida ({self.retry_count}): exception type= {e}")
            
            await asyncio.sleep(1)

    async def cleanup_connection(self):
        try:
            if self.client:
                if(self.ScanActivado==True):
                    self.CancelScanData( self.scanData) #problemas con dobles suscripciones
                self.client.disconnect()
                self.log.warning("Cliente desconectado")
        except Exception as e:
            self.log.warning(f"Error al desconectar: {e}")
        finally:
            self.connected = False
 
    async def SincroAllOperation(self):

        await self.sincroOpenOrders()
        await self.sincroExecutionOrders()      
        await self.sincroPositions()

    async def sincroPositions(self):
        posiciones= await self.client.reqPositionsAsync() #activará estatus      
        if(posiciones):
            with self.lock_Oper:
                self.t_Oper.Clear()

            self.log.info(f"[SINCRO] POSICIONES EN SISTEMA")
            for  position in posiciones:
                """
                print(f"POSITION: {position}")
                print(f"📌 Symbol: {position.contract.symbol}")
                print(f"📌 QTY:     {position.position}")
                print(f"💰 avgPrice: {position.avgCost:.2f}")
                print("—" * 40)
                """
                symbol=position.contract.symbol
                qty = position.position
                price=position.avgCost
                self.log.info (f"[SINCRO] POSITION: {symbol} qty:{qty}")
                with self.lock_Oper:
                    self.t_Oper.UpdatePosition(symbol,qty,price, self.timer.getNow())
                
        else:
            self.log.info(f"[SINCRO] NO HAY POSICIONES ACTIVAS")

        with self.lock_Oper:
            self.t_Oper.SincroOrdersOnlyOpen()

    async def sincroOpenOrders(self):

        open_orders = await self.client.reqAllOpenOrdersAsync() #activará estatus  
        if open_orders:
            self.log.info("[SINCRO] Órdenes OPEN encontradas")
            
            with self.lock_Oper:
                self.t_Oper.ClearOrders()

            for trade in open_orders:

                """
                print(f"📦 Símbolo:      {contract.symbol} ({contract.secType})")
                print(f"🆔 PermID:       {order_status.permId}")
                print(f"🆔 PARENT ID:    {order_status.parentId}")
                print(f"🔢 Qty Order:    {order.totalQuantity}")
                print(f"🎯 Acción:       {order.action}") 
                print(f"💰 LMT Price:    {order.lmtPrice}")
                print(f"📌 Estado: {trade.orderStatus.status}")
                print(f"🔢 Cantidad filled: {order_status.filled}")
                print(f"🔢 Cantidad remaining: {order_status.remaining}")
                print(f"💰 avgPrice: {order_status.avgFillPrice:.2f}")
                print(f"🕒 Fecha/Hora: {trade.log[0].time.strftime("%Y-%m-%d %H:%M:%S")}") 
                print(f"📌 type: {order.orderType}")
                print("-" * 40)    
                """
                #print(trade)

                contract = trade.contract
                order = trade.order
                order_status = trade.orderStatus
                
                symbol  = contract.symbol
                qtyTot  = order.totalQuantity
                qtyFill = order_status.filled
                #price=order.lmtPrice
                
                status = trade.orderStatus.status
                permID = order_status.permId
                parentID= order_status.parentId
                orderID = order.orderId
                orderType = order.orderType
                
                priceLim=0.0
                priceAvg=order_status.avgFillPrice

                if(parentID==0):
                    tipoBrk = Bracket.PADRE
                    if  order.action == 'SELL': 
                        qtyTot*=-1

                    if  orderType=="LMT":
                        priceLim=order.lmtPrice
                    else:
                        priceLim=0
                        
                elif isinstance(trade.order,(StopOrder, StopLimitOrder)) or orderType=="STP":
                    tipoBrk  = Bracket.ST
                    priceLim= order.auxPrice
                else: 
                    tipoBrk  = Bracket.TP
                    priceLim=order.lmtPrice

                time= self.timer.getNow()

                self.log.info (f"[SINCRO] ORDER-TRADE: {symbol} qty:{qtyTot} permID:{permID} orderID:{orderID} status:{status} parentID {parentID}-")
                with self.lock_Oper:
                    self.t_Oper.UpdateOrders(symbol,qtyTot,qtyFill,priceLim,priceAvg,status,permID,orderID,parentID,tipoBrk, time) 

        else:
            self.log.info("[SINCRO] NO HAY ORDERS OPEN")

        self.t_Oper.ShowAllOrders()

    async def sincroExecutionOrders(self):
        filtro = ExecutionFilter()#time="20250701 00:00:00")

        ejecuciones=await self.client.reqExecutionsAsync(filtro) 
        if ejecuciones:
            #print (ejecuciones)
            self.log.info(f"[SINCRO] EXECUTIONS ENCONTRADAS")

            for fill in ejecuciones:
                                            
                """
                print("—" * 40)
                print(f"📌 Símbolo: {fill.contract.symbol}")
                print(f"🔢 Cantidad: {ejec.shares}")
                print(f"🆔 PermID: {ejec.permId}")
                print(f"🕒 Fecha/Hora: {ejec.time.strftime("%Y-%m-%d %H:%M:%S")}")
                print(f"💰 Precio: {ejec.price}")
                print("—" * 40)
                """
                """
                execution.execId          # ID único de la ejecución
                execution.time            # Fecha y hora exacta de ejecución
                execution.acctNumber      # Número de cuenta
                execution.exchange        # Bolsa donde ocurrió la ejecución
                execution.side            # 'BUY' o 'SELL'
                execution.shares          # Cantidad ejecutada
                execution.price           # Precio al que se ejecutó
                execution.orderId         # ID de la orden
                execution.permId          # ID permanente de la orden
                execution.clientId        # ID del cliente que envió la orden
                execution.cumQty          # Cantidad acumulada ejecutada
                execution.avgPrice        # Precio promedio de ejecución acumulada
                execution.liquidity       # Código de liquidez (1 = added, 2 = removed, etc.)
                execution.modelCode       # Modelo de cuenta si aplica
                execution.lastLiquidity   # Última categorización de liquidez aplicada
                """

                
                symbol = fill.contract.symbol
                ejec   = fill.execution

                permID      = ejec.permId
                orderID     = ejec.orderId
                parentID    = 0
           
                qtyTot      = ejec.cumQty
                qtyFill     = ejec.shares

                side        = ejec.side  

                priceAvg    = ejec.avgPrice
                priceLim    = 0

                tipoBrk= Bracket.PADRE #porque se ha rellenado, pero podría ser un stop
                status = OrderStatus.FILLED.value
                time = ejec.time  
                if(side=="SELL" or side=="SLD"):
                    qtyTot*=-1
                    qtyFill*=-1

                self.log.info (f"[SINCRO] EXECUTION: {symbol} qty:{qtyFill} side:{side}- permID:{permID}")   
                with self.lock_Oper:                     
                    self.t_Oper.UpdateOrders(symbol,qtyTot,qtyFill,priceLim,priceAvg,status,permID,orderID,parentID,tipoBrk, time)    
                    ### NO EN SINCRO self.t_Oper.UpdateAllPosition()
            #self.t_Oper.ShowAllOrders()
        else:
            self.log.info(f"[SINCRO] NO ENCONTRADAS EXECUTIONS ")

    async def process_msg_Sdata(self,msg):
        self.log.info(f"Mensaje recibido SDATA: {msg.type} --- {msg.symbol}")
        
        if msg.type == MsgType.SCANNER :
            if isinstance(msg, ScanRequestMsg):

                self.ScanActivado=True
                await self.SetScan(
                    scan_code=msg.scan_code,
                    instrument=msg.instrument,
                    location_code=msg.location_code,
                    number_of_rows=msg.number_of_rows,
                    above_price=msg.above_price,
                    below_price=msg.below_price,
                    above_volume=msg.above_volume,
                    market_cap_above=msg.market_cap_above,
                    market_cap_below=msg.market_cap_below,
                    moody_rating_above=msg.moody_rating_above,
                    moody_rating_below=msg.moody_rating_below,
                    sp_rating_above=msg.sp_rating_above,
                    sp_rating_below=msg.sp_rating_below,
                    maturity_date_above=msg.maturity_date_above,
                    maturity_date_below=msg.maturity_date_below,
                    coupon_rate_above=msg.coupon_rate_above,
                    coupon_rate_below=msg.coupon_rate_below,
                    exclude_convertible=msg.exclude_convertible,
                    scanner_setting_pairs=msg.scanner_setting_pairs,
                    stock_type_filter=msg.stock_type_filter
                )
        
        elif msg.type == MsgType.HISTORIA:
            self.log.info(f"RX-SDATA HISTORIA {msg.symbol}  {msg.inicio}  {msg.fin}  {msg.bar_size}")
            await self.ReqHistoric( msg.symbol, msg.inicio, msg.fin, msg.bar_size,msg.out_market)

        elif msg.type == MsgType.CANCEL_SCAN:
            self.log.info(f"Req CANCEL SCAN")
            self.CancelScanData( self.scanData)
    
        elif msg.type == MsgType.PRICE_TICK:
            self.log.info(f"Req PRICE TICK")
            #await self.GetPrice(msg.symbol)
            await self.SubscribePrice(msg.symbol)

        elif msg.type == MsgType.TR_BAR:
            self.log.info(f"Req TR BAR")
            await self.SubscribeRealTimeBars(symbol=msg.symbol,bar_size="5 secs")
            
        elif msg.type == MsgType.CONTROL:       #TAMBIEN PUEDE LLEGAR MENSAJE CONTROL DE SDATA
            self.log.info(f"Req CONTROL SDATA")
            await self.ProcesaMensajeControl(msg)
               
        else:
            return

    async def ProcesaMensajeOrder(self,msg):

        symbol=msg.symbol
        accion=msg.side
        cantidad= msg.qty
        tipo_orden=msg.tipoOrder
        if(msg.tipoOrder=="LMT"):
            precio_limite=msg.price
        else:
            precio_limite=0
        if msg.st!=None:
            stop_loss=msg.st
        else:
            stop_loss=None
        
        if msg.tp!=None:
            take_profit=msg.tp
        else:
            take_profit=None
       
        #await self.SetOrder(symbol='AAPL', accion='BUY', cantidad=100, tipo_orden="LMT",precio_limite=150.0, stop_loss=145.0)
        #await self.SetOrder(symbol='AAPL', accion='BUY', cantidad=50, tipo_orden="LMT",precio_limite=211.4, stop_loss=190.0,take_profit=250.0)

        await self.SetOrder(symbol=symbol, accion=accion, cantidad=cantidad, tipo_orden=tipo_orden,precio_limite=precio_limite, stop_loss=stop_loss,take_profit=take_profit)

    def CancelOrderSymbol(self,symbol: str):
        
        open_trades = self.client.openTrades()
        canceladas = 0

        for trade in open_trades:
            if trade.contract.symbol.upper() == symbol.upper():
                self.client.cancelOrder(trade.order)
                canceladas += 1
                self.log.debug(f"Orden cancelada: {trade.order.orderId} para {symbol}")

        if canceladas == 0:
            self.log.debug(f"No se encontraron órdenes abiertas para el símbolo '{symbol}'")

    def CierraPosición_Brackets(self,symbol: str):
        """
        Cierra la posición abierta para un símbolo específico y cancela cualquier orden bracket asociada.
        """
        symbol = symbol.upper()
        posiciones = self.client.positions()
        trades = self.client.openTrades()
        cerradas = 0
        brackets_canceladas = 0

        # Cierre de posición
        for pos in posiciones:
            symbActual =pos.contract.symbol.upper()
            if symbActual == symbol or symbol=="ALL":
                cantidad = abs(pos.position)
                if cantidad == 0:
                    continue
                accion = 'SELL' if pos.position > 0 else 'BUY'
                contrato_cierre = self.create_contract(symbActual)

                orden_cierre = MarketOrder(accion, cantidad,outsideRth=True)
                
                self.client.placeOrder(contrato_cierre, orden_cierre)
                cerradas += 1
                self.log.debug(f"ORDERED Cierre posición: {accion} {cantidad} de {symbol}")

        # Cancelación de brackets (stops/takes)
        for trade in trades:
            contrato = trade.contract
            orden = trade.order

            if contrato.symbol.upper() == symbol and orden.parentId != 0:
                self.client.cancelOrder(orden)
                brackets_canceladas += 1
                self.log.debug(f"Orden bracket cancelada (ID: {orden.orderId})")

        if cerradas == 0:
            self.log.debug(f"No se encontró posición abierta para '{symbol}'")
        if brackets_canceladas == 0:
            self.log.debug(f"No se encontraron brackets activos para '{symbol}'")

    async def ProcesaMensajeControl(self,msg):

        if(msg.action == ControlAction.CANCEL_ORDERS):
            if (msg.symbol =="ALL"):
                self.log.info(f"Mensaje req CANCEL_ORDERS  ALL")
                self.client.reqGlobalCancel()
            else:
                self.log.info(f"Mensaje req CANCEL_ORDERS: {msg.symbol}")
                self.CancelOrderSymbol(msg.symbol)

        elif(msg.action == ControlAction.CIERRA_POSICION):
            self.log.info(f"Mensaje req CIERRA POSICION: {msg.symbol}")
            self.CierraPosición_Brackets(msg.symbol)

        elif(msg.action == ControlAction.CANCEL_SUSCRIP):
            self.log.info(f"Mensaje RX REQ CANCEL_SUSCRIP TR: {msg.symbol}")
            if(msg.symbol!="ALL"):
                self.CancelRealTimeBars( msg.symbol)
                self.CancelPrice( msg.symbol)

        elif(msg.action == ControlAction.GET_PRICE):
            self.log.info(f"Mensaje RX REQ GET_PRICE : {msg.symbol}")
            self.GetPrice( msg.symbol)
            """
            elif(msg.action == ControlAction.REQ_1MIN_BAR):
            self.log.info(f"Mensaje RX REQ_1MIN_BAR : {msg.symbol}")

            self.Send( msg.symbol)
            """     
        else:
            return      

    async def process_msg_Strat(self,msg):
        self.log.info(f"Mensaje recibido STRAT: {msg}")
        if(msg.type == MsgType.ORDER_ENTRY):
            await self.ProcesaMensajeOrder(msg)
  
        elif(msg.type == MsgType.CONTROL):
            self.log.info(f"Req CONTROL STRAT")
            await self.ProcesaMensajeControl(msg)
        
        
        else:
            return


    """
    Tipo	            Método/evento	            Destino
    Market Data	        on_tick_update	            out_SData
    Order Status	    on_order_status	            out_Strat
    Execution/Fill	    on_exec_details	            out_Strat
    Históricos (manual)	await reqHistoricalData()	out_SData
    """

    def create_contract(self, symbol):
        return Stock(symbol, 'SMART', 'USD')

    def max_duration_for_bar_size(self, bar_size: str) -> tuple[timedelta, str]:
        MAX_DURATION_PER_BARSIZE = {
            '1 secs':  '30 M',
            '5 secs':  '3 H',
            '15 secs': '6 H',
            '30 secs': '12 H',
            '1 min':   '1 W',
            '2 mins':  '2 W',
            '3 mins':  '3 W',
            '5 mins':  '1 M',
            '15 mins': '2 M',
            '30 mins': '3 M',
            '1 hour':  '6 M',
            '1 day':   '1 Y',
            '1 week':  '2 Y',
            '1 month': '5 Y'
        }
        mapping = {
            '1 secs':  timedelta(minutes=30),
            '5 secs':  timedelta(hours=3),
            '15 secs': timedelta(hours=6),
            '30 secs': timedelta(hours=12),
            '1 min':   timedelta(days=7),
            '2 mins':  timedelta(days=14),
            '3 mins':  timedelta(days=21),
            '5 mins':  timedelta(days=30),
            '15 mins': timedelta(days=60),
            '30 mins': timedelta(days=90),
            '1 hour':  timedelta(days=180),
            '1 day':   timedelta(days=365),
            '1 week':  timedelta(days=730),
            '1 month': timedelta(days=1825),  # ≈5 años
            }
    
        try:
            valst, vtime = bar_size.strip().split()
            if valst.isdigit():
                val = int(valst) #if val.isdigit() else 1  # Usa 1 como fallback
            else:
                val= 1  # Usa 1 como fallback
           
           
            #self.log.debug( f'max duration val {valst} time {vtime} valor int {val}')

            #_, unit = bar_size.strip().lower().split()
            #parse_bar_size = lambda s: (int(s.strip().split()[0]), s.strip().split()[1].lower())
            if vtime== 'secs' or vtime== 'sec':
                return  timedelta(minutes=30),'1800 S'

            if vtime== 'min' or vtime== 'mins':
                if(val<=3):
                    return  timedelta(days=7),'1 W'
                else:
                    return  timedelta(days=30),'1 M'
                
            if vtime== 'hour' or vtime== 'hours':
                return  timedelta(days=180),'6 M'

            if vtime== 'day' or vtime== 'days'or vtime== 'week'or vtime== 'weeks'or vtime== 'month'or vtime== 'months':
                return  timedelta(days=365),'1 Y'
            else:
                self.log.exception(f"Formato de barSize inválido: '{bar_size}'")
                raise ValueError("Exception de barSize")
            
        except ValueError as e:
                self.log.exception(f"Exception value {e}")

    mappingTipoSize = {
        
                    'min':   timedelta(minutes=1),
                    'mins':  timedelta(minutes=1),
                    'hour':  timedelta(minutes=60),
                    'day':   timedelta(days=1),
                    'week':  timedelta(days=7),
                    'month': timedelta(days=30),  
                    }

    def duration_bar_size(self, duration_total:timedelta, bar_size: str)-> tuple[timedelta, str]:
        
        
        duration_size = 0

        try:
            valst, vtime = bar_size.strip().split()
            if valst.isdigit():
                val = int(valst) #if val.isdigit() else 1  # Usa 1 como fallback
                duration_size = self.mappingTipoSize.get(vtime)*val
            else:
                val= 1  # Usa 1 como fallback
                duration_size = 1

                        
            if duration_total>timedelta(days=360):
                years=(duration_total//timedelta(days=360))+1
                durStr= str(years)+' Y'
            
            elif duration_total>timedelta(days=7):
                weeks=(duration_total//timedelta(days=7))+1
                durStr= str(weeks)+' W'
            
            elif duration_total>timedelta(days=1):
                days=(duration_total//timedelta(days=1))+1
                durStr= str(days)+' D'

            elif duration_total>timedelta(hours=1):
                hours=(duration_total//timedelta(hours=1))+1
                durStr= str(hours)+' H'
            
            elif duration_total>timedelta(minutes=1):
                minutes=((duration_total//timedelta(minutes=1))+1)*60
                rdurStr= str(minutes)+' S'
            else:
                durStr= '0 S'
            
            return duration_size, durStr
        

        except ValueError as e:
            self.log.exception(f"Exception value {e}")
            durStr= '0 S'
            return duration_size, durStr
 
    async def ReqHistoric(self, symbol, startTime, endTime, barSize,outMarket):

        contract=self.create_contract(symbol)
        #await ib.qualifyContractsAsync(contract)
                    
        #maxima duration periodica a solicitar segun barSize
                    
        max_duration, max_duration_str =self.max_duration_for_bar_size(bar_size= barSize)
        # endTime estará siempre en zona TimeZone (america)

        """
        current_end= getNowUTC() #-timedelta(days=1)  #parece que debe ser UTC
        ny_tz = pytz.timezone('America/New_York')
        now_ny = datetime.now(ny_tz)
        now_utc = now_ny.astimezone(pytz.utc)
        current_end=now_utc
        """

        startTimeUTC=startTime.astimezone(pytz.utc)

        if(endTime==""):
            currentEndUTC=self.timer.getNowUTC()
        else:
            #currentEndUTC=endTime.astimezone(pytz.utc)
            currentEndUTC=endTime
        
        CurrentUTCstr = currentEndUTC.strftime('%Y%m%d %H:%M:%S UTC')
     
        ##check duration and str
        durationPending= currentEndUTC-startTimeUTC
        if(durationPending>=max_duration):
            duration_str= max_duration_str
        else:
            duration_size, duration_str= self.duration_bar_size( durationPending, barSize)
            if duration_str=="0 S" or durationPending<duration_size:
                currentEndUTC=startTimeUTC
         ##check duration and str

        all_data = []
        self.log.debug( f'Req HISTORIC {symbol}: INI UTC :{startTimeUTC.strftime("%Y%m%d %H:%M:%S")} -FIN UTC:{currentEndUTC.strftime("%Y%m%d %H:%M:%S") }')

        if outMarket: mRTH=False 
        else:         mRTH=True
        
        while currentEndUTC > startTimeUTC:
            success = False
            retries = 0
            while not success and retries < 3:
                try:
                    
                    
                    CurrentUTCstr = currentEndUTC.strftime('%Y%m%d %H:%M:%S UTC')
                    self.log.debug(f'{symbol}: oneHISTORIC Retry:{retries} hasta {CurrentUTCstr} "{barSize}"-duration "{duration_str}" -max_duration {max_duration_str}"...')
                        
                    bars = await self.client.reqHistoricalDataAsync(
                            contract,
                            endDateTime=CurrentUTCstr,
                            durationStr=duration_str,
                            barSizeSetting=barSize,
                            whatToShow='TRADES',
                            useRTH=mRTH, #false incluye pre y post market
                            formatDate=1,
                            keepUpToDate=False,
                            timeout=3
                        )

                    if not bars:
                        self.log.info(f'{symbol}: sin datos para este tramo.')
                        sleep_time = 1
                    else:
                        df = util.df(bars)
                        #self.log.debug(f'LAST BARS RX {df.iloc[-1]}')
                        # Asegúrate de que la columna 'date' sea datetime con zona UTC
                        df['date'] = pd.to_datetime(df['date'], utc=True)
    
                        #en caso que sea mayor que u dia, la hora viene a 00.00 y siempre retrasa un dia

                        valst, vtime = barSize.strip().split()
                        deltaSize = self.mappingTipoSize.get(vtime)
                        if(deltaSize < timedelta(days=1)):
                            df['date'] = df['date'].dt.tz_convert(cfSys['zoneTime']) #convertidas a TIMEZONE
                        #self.log.debug(f'TOTAL DF {df}')
                        
                        all_data.append(df)
                        self.log.debug(f"----------------------------------------------")
                        self.log.debug(f"{symbol} {barSize} TOTAL:{len(df)} registros.")
                        self.log.debug(f' LAST TIME MSG {df.iloc[-1]["date"]} close {df.iloc[-1]["close"]}')
                        self.log.debug(f"----------------------------------------------")
                        sleep_time = 0.01
                        success = True
                        
                except Exception as e:
                    retries += 1
                    sleep_time = 3
                    self.log.exception(f'{symbol}: error al solicitar HISTORY (intento {retries}) -> {e}')
                    if retries >= 3:
                        self.log.error(f'{symbol}: se superó el máximo de reintentos. Abortando.')
                        #break  # salir completamente si 3 errores seguidos

                await asyncio.sleep(sleep_time)
                #await asyncio.sleep(0.0005)

                if  success:
                    # CREO QUE ESTO SOLO EN CASO SUCCESS - si no fue exitosa pero no hubo excepción grave (como datos vacíos), avanzamos igual
                    currentEndUTC -= (max_duration)
                    
                    ##check duration and str
                    durationPending= currentEndUTC-startTimeUTC
                    if(durationPending>=max_duration):
                        duration_str= max_duration_str
                    else:
                        duration_size, duration_str= self.duration_bar_size( durationPending, barSize)
                        if duration_str=="0 S" or durationPending<duration_size:
                            currentEndUTC=startTimeUTC
                    ##check duration and str
                else:
                    #no success
                    retries += 1
                    await asyncio.sleep(0.5)

                            

        ## fin de envios
        df_final = pd.concat(all_data, ignore_index=True)
            
        #self.log.debug(df_final)
        msgHisto = HistoricalMsg(
                            source="BRK",
                            symbol=symbol,
                            inicio=startTime,
                            fin=endTime,
                            bar_size=barSize,
                            out_market=outMarket,
                            data=df_final
                        )
        #await self.out_SData.put(msgHisto)       
        await self.SendMsg("SDATA",msgHisto)



    async def SubscribeRealTimeBars(self, symbol, bar_size="5 secs"):
        """
        Subscribe a barras en tiempo real
        bar_size: "5 secs", "10 secs", "15 secs", "30 secs", "1 min", etc.
        """
        try:
            if symbol not in self.subscribed_rtbar:
                # no suscrito
                contract = self.create_contract(symbol)
                
                # Subscribirse a barras en tiempo real
                bars = self.client.reqRealTimeBars(
                    contract=contract,
                    barSize=5,#'5 secs',
                    whatToShow='TRADES',  # TRADES, MIDPOINT, BID, ASK
                    useRTH=False  # True para horario regular, False para extended hours
                )
                
                # Conectar el callback para nuevas barras
                bars.updateEvent += self.on_realtime_bar
                 # Guardar la subscripción
                self.subscribed_rtbar[symbol] = bars
                self.log.info(f"Suscrito a barras de {bar_size} para {symbol}")
                return bars
            else:
                self.log.warning(f"ANTERIORMENTE YA Suscrito a barras de {bar_size} para {symbol}")
       
        except Exception as e:
            self.log.error(f"Error suscribiéndose a barras RT para {symbol}: {e}")
            return None

    def CancelRealTimeBars(self, symbol):
        """
        Cancelar suscripción a barras en tiempo real
        """
        try:

            bars = self.subscribed_rtbar.pop(symbol, None)  # devuelve y elimina el valor de symbol
            if bars:
                bars.updateEvent.clear()
                self.client.cancelRealTimeBars(bars)
                self.log.info(f"Cancelada suscripción RT para {symbol}")
                
        except Exception as e:
            self.log.error(f"Error cancelando suscripción RT para {symbol}: {e}")

    async def GetPrice(self, symbol):
        if symbol not in self.subscribed_tickers:
            contract = self.create_contract(symbol)
            self.log.debug(f"REQ- GetPrice {symbol}")
            ticker=None
            try:
                ticker = self.client.reqMktData(contract,'',snapshot=True)                ## esto es un tick o ultimo dato
                await asyncio.sleep(0.5) 
                if ticker != None:
                    if ticker.bid >0 or ticker.bid==-1:
                        mTime=self.timer.getNow()
                        if(ticker.bid==-1): mTime=None
                        self.log.debug(f" GET PRICE {symbol} BID:{ticker.bid}")
                        msgTick = TickMsg(
                                    source="BKR",
                                    symbol=symbol,
                                    bid=ticker.bid,
                                    ask=ticker.ask,
                                    last=ticker.last,
                                    time=mTime
                            )
                        await self.SendMsg("SDATA",msgTick)
                        #asyncio.create_task(self.out_SData.put(msgTick)) ## en funciones no async

                        return ticker
            except:   
                self.log.exception(f"EXCEPTION EN Get Price {symbol}")
        else:
            self.log.warning(f"El precio para {symbol} está Suscrito en evento periodico")
        
        return None        

    async def SubscribePrice(self, symbol):
        if symbol not in self.subscribed_tickers:
            contract = self.create_contract(symbol)
            
            ticker = self.client.reqMktData(contract)                ## esto es un tick o ultimo dato
            self.log.debug(f"ticker SUSCRIBE PRICE {symbol}")############ {ticker}")
            ticker.updateEvent += self.on_tick_update
            self.subscribed_tickers[symbol] = ticker
            
            self.log.debug(f"SUBCRIBED TICk {symbol} ")


    def CancelPrice(self, symbol):
        try:
            ticker = self.subscribed_tickers.pop(symbol, None)  # devuelve y elimina el valor de symbol
            if ticker:
                                   #borro el callback antes de cancelar
                #ticker.updateEvent -= self.on_tick_update
                self.log.info(f"Cancelado TICKS  para {symbol} ")#############{ticker}")                
                self.client.cancelMktData(ticker.contract)               # esto es un tick o ultimo dato
                ticker.updateEvent.clear()   #esto después de cancelMKT o da una exception
                
            else:
                self.log.warning(f"No encontratado cancelacion TICKS solicitada para {symbol}")
        
        except Exception as e:
            self.log.error(f"CancelPrice Error cancelando suscripción TICKS para {symbol}: {e}")
   
   
   
   
    """
        sub.numberOfRows,
        sub.instrument,
        sub.locationCode,
        sub.scanCode,
        sub.abovePrice,
        sub.belowPrice,
        sub.aboveVolume,
        sub.marketCapAbove,
        sub.marketCapBelow,
        sub.moodyRatingAbove,
        sub.moodyRatingBelow,
        sub.spRatingAbove,
        sub.spRatingBelow,
        sub.maturityDateAbove,
        sub.maturityDateBelow,
        sub.couponRateAbove,
        sub.couponRateBelow,
        sub.excludeConvertible,
        sub.averageOptionVolumeAbove,
        sub.scannerSettingPairs,
        sub.stockTypeFilter,

        scanCode disponibles comúnmente
        TOP_PERC_GAIN       – Altas ganadoras por porcentaje en tiempo real
        TOP_PERC_LOSE       – Pérdidas más profundas porcentuales
        MOST_ACTIVE         – Activos con mayor volumen de operaciones
        ALL_SYMBOLS_ASC     – Todos los símbolos en orden alfabético ascendente
        ALL_SYMBOLS_DESC    – Todos los símbolos en orden alfabético descendente
        HOT_BY_PRICE        – Mayores movimientos absolutos de precio
        HOT_BY_VOLUME       – Más “calientes” por volumen
        HIGH_OPEN_GAP       – Huecos de apertura más grandes (apertura vs cierre)
        HIGH_DIVIDEND_YIELD     – Rentabilidad por dividendo más alta
        HIGH_DIVIDEND_YIELD_IB  – Variante IB específica (si disponible)
        HIGH_PERC_GAIN          – Similar a TOP_PERC_GAIN (sin “TOP_”)
        HIGH_PE_RATIO           – Ratios P/E más altos

        HIGH_OPT_IMP_VOLAT                      – Opciones con mayor volatilidad implícita
        HIGH_OPT_OPEN_INTEREST_PUT_CALL_RATIO
        HIGH_OPT_VOLUME_PUT_CALL_RATIO
        HIGH_QUICK_RATIO, HIGH_RETURN_ON_EQUITY, etc.


        TOP_PERC_GAIN
        TOP_PERC_LOSE
        MOST_ACTIVE
        ALL_SYMBOLS_ASC
        ALL_SYMBOLS_DESC
        HOT_BY_PRICE
        HOT_BY_PRICE_RANGE
        HOT_BY_VOLUME
        HIGH_OPEN_GAP
        LOW_OPEN_GAP
        HIGH_DIVIDEND_YIELD
        HIGH_DIVIDEND_YIELD_IB
        LIMIT_UP_DOWN
        HIGH_PE_RATIO
        HIGH_PRICE_2_BOOK_RATIO
        LOW_PE_RATIO
        LOW_PRICE_2_BOOK_RATIO
        HIGH_QUICK_RATIO
        LOW_QUICK_RATIO
        HIGH_RETURN_ON_EQUITY
        LOW_RETURN_ON_EQUITY
        HIGH_GROWTH_RATE
        LOW_GROWTH_RATE
        HOT_BY_OPT_VOLUME
        HIGH_OPT_IMP_VOLAT
        LOW_OPT_IMP_VOLAT
        HIGH_OPT_IMP_VOLAT_OVER_HIST
        LOW_OPT_IMP_VOLAT_OVER_HIST
        HIGH_OPT_OPEN_INTEREST_PUT_CALL_RATIO
        LOW_OPT_OPEN_INTEREST_PUT_CALL_RATIO
        HIGH_OPT_VOLUME_PUT_CALL_RATIO
        LOW_OPT_VOLUME_PUT_CALL_RATIO
        HIGH_VS_13W_HL
        LOW_VS_13W_HL
        HIGH_VS_26W_HL
        LOW_VS_26W_HL
        HIGH_VS_52W_HL
        LOW_VS_52W_HL
        HALTED

        
    """
    
    async def SetScan(self,
            scan_code: str = 'TOP_PERC_GAIN',
            instrument: str = 'STK',
            location_code: str = 'STK.US.MAJOR',
            number_of_rows: int = 60,

            # Filtros opcionales
            above_price: Optional[float] = None,
            below_price: Optional[float] = None,
            above_volume: Optional[int] = None,
            market_cap_above: Optional[float] = None,
            market_cap_below: Optional[float] = None,
            moody_rating_above: Optional[str] = None,
            moody_rating_below: Optional[str] = None,
            sp_rating_above: Optional[str] = None,
            sp_rating_below: Optional[str] = None,
            maturity_date_above: Optional[str] = None,
            maturity_date_below: Optional[str] = None,
            coupon_rate_above: Optional[float] = None,
            coupon_rate_below: Optional[float] = None,
            exclude_convertible: Optional[bool] = None,
            scanner_setting_pairs: Optional[str] = None,
            stock_type_filter: Optional[str] = None
        ):
        self.log.debug(f" Enviando escáner: ")

    
        scan_sub = ScannerSubscription()

        scan_sub.instrument = instrument
        scan_sub.locationCode = location_code
        scan_sub.scanCode = scan_code
        scan_sub.numberOfRows = number_of_rows

        # Aplicar filtros si están definidos
        if above_price      is not None: scan_sub.abovePrice = above_price
        if below_price      is not None: scan_sub.belowPrice = below_price
        if above_volume     is not None: scan_sub.aboveVolume = above_volume
        if market_cap_above is not None: scan_sub.marketCapAbove = market_cap_above
        if market_cap_below is not None: scan_sub.marketCapBelow = market_cap_below
        if moody_rating_above   is not None: scan_sub.moodyRatingAbove = moody_rating_above
        if moody_rating_below   is not None: scan_sub.moodyRatingBelow = moody_rating_below
        if sp_rating_above      is not None: scan_sub.spRatingAbove = sp_rating_above
        if sp_rating_below      is not None: scan_sub.spRatingBelow = sp_rating_below
        if maturity_date_above  is not None: scan_sub.maturityDateAbove = maturity_date_above
        if maturity_date_below  is not None: scan_sub.maturityDateBelow = maturity_date_below
        if coupon_rate_above    is not None: scan_sub.couponRateAbove = coupon_rate_above
        if coupon_rate_below    is not None: scan_sub.couponRateBelow = coupon_rate_below
        if exclude_convertible  is not None: scan_sub.excludeConvertible = exclude_convertible
        if scanner_setting_pairs    is not None: scan_sub.scannerSettingPairs = scanner_setting_pairs
        if stock_type_filter        is not None: scan_sub.stockTypeFilter = stock_type_filter
        
        
        """
        sub = ScannerSubscription(
            instrument='STK',
            locationCode='STK.US.MAJOR',
            scanCode='TOP_PERC_GAIN',
            abovePrice = 0.5,
            aboveVolume= 20000,
            marketCapBelow = 2_000_000_000,
            marketCapAbove=  500_000,
            )
        """
        self.scanData = self.client.reqScannerSubscription(scan_sub)
        
        self.scanData.updateEvent         += self.onScanData

        #self.log.info (f"scan_sub{ scan_sub}")

    def CancelScanData(self,scanData):
        self.client.cancelScannerSubscription(scanData)
        self.scanData.updateEvent -= self.onScanData
        self.ScanActivado=False
        #self.scanData.updateEvent.clear()
        #self.scanData = None
 
    async def SetOrder(self,
         
            symbol: str,
            accion:str,
            cantidad: float,
            tipo_orden: str = 'MKT',
            precio_limite: float = None,
            stop_loss: float = None,
            take_profit: float = None,
            outsideRth=True
            ):
         
        self.log.info(f"Set Order API {symbol} {accion}, {cantidad}")
        """
            Coloca una orden bracket (entrada + take profit + stop loss)
            Args:
                symbol: Símbolo de la acción
                action: 'BUY' o 'SELL'
                cantidad: Cantidad de acciones
                tipo_orden (MKT-LIM)
                precio_limite: Precio de entrada (None para market order)
                stop_loss: Precio de stop loss
                take_profit: Precio de take profit
        """
        try:
            contrato = self.create_contract(symbol)
            #await self.client.qualifyContractsAsync(contrato)

            ordenes_hijas = []
            placed_trades = []

            if tipo_orden not in ['MKT', 'LMT']:
                self.log.error(f"{symbol} con Order LMT o MKT")
                raise ValueError(f"Tipo de orden '{tipo_orden}' no reconocido. Usa 'MKT'")
                                 
            if tipo_orden == 'LMT' and precio_limite is None:
                self.log.error(f"{symbol} con Order LMT sin precio Límite.")
                raise ValueError("Exception de barSize")

            if accion != 'BUY' and accion != 'SELL':
                self.log.error(f"{symbol} Accion ni BUY ni SELL.")
                raise ValueError("Exception de BUY-SELL")
                       
            cantidad_abs = abs(cantidad)
            
            # Orden principal
            if precio_limite is None:
                # Market order
                parent_order = MarketOrder(accion, cantidad_abs,outsideRth)
            else:
                # Limit order
                parent_order = LimitOrder(accion, cantidad_abs, precio_limite,outsideRth=True)

            # Configuración para órdenes bracket
            
            parent_order.orderId = self.client.client.getReqId()
            parent_order.transmit = False  # No transmitir hasta que tengamos todas las órdenes
            parent_id = parent_order.orderId

                           
            # HIJAS
            children_trades = {}
            tp_order=None
            sl_order=None

            # Take Profit Order
            if take_profit is not None:
                tp_action = 'SELL' if accion == 'BUY' else 'BUY'
                tp_order = LimitOrder(tp_action, cantidad_abs, take_profit,outsideRth=True)
                
                tp_order.orderId =  self.client.client.getReqId()
                tp_order.parentId = parent_id
                tp_order.transmit = False
                ordenes_hijas.append(tp_order)
            
            # Stop Loss Order
            if stop_loss is not None:
                sl_action = 'SELL' if accion == 'BUY' else 'BUY'
                sl_order = StopOrder(sl_action, cantidad_abs, stop_loss,outsideRth=True)
                
                sl_order.orderId = self.client.client.getReqId()
                sl_order.parentId = parent_id
                sl_order.transmit = True  # La última orden transmite todas
                ordenes_hijas.append(sl_order)
           

            if take_profit and stop_loss:
                tp_order.transmit = False
                sl_order.transmit = True
            elif take_profit:
                tp_order.transmit = True  # hay tp, pero no sl
            elif stop_loss:
                sl_order.transmit = True  # hay sl, pero no tp  
            else:
                parent_order.transmit = True

            #Envio ordenes
            
            self.log.info(f"Enviando PARENT") 

            trade_parent = self.client.placeOrder(contrato, parent_order)
                       
            #self.log.info(f"Enviando PARENT") 

            #await asyncio.sleep(0.1)  # Espera breve para asegurar procesamiento
            self.log.info(f"Orden PARENT colocada: {parent_order.action} {parent_order.totalQuantity} {symbol}")
            placed_trades.append(trade_parent)
            
        



            # Enviar resto de las órdenes
            for order in ordenes_hijas:
                trade = self.client.placeOrder(contrato, order)
                
                placed_trades.append(trade)
                self.log.info(f"Orden HIJA : {order.action} {order.totalQuantity} {symbol}")
            return placed_trades

                         
        except ValueError as e:
            self.log.error(f"SET ORDER - Exception value {e}")

    async def ProcesaHeartBeat(self):
        if  self.client.isConnected():
            limit = self.lastConnect+ timedelta(minutes=1)
            if self.timer.getNow()>limit: #Ahora conectado, pero estuve mas de un minuto sin conexión o al principio
                 kk=1
            self.lastConnect=self.timer.getNow()
                 
        else:
            self.log.warning(f"PERDIDA CONEXION conexión con IBKR. {self.timer.getNow()}")
            self.retry_count  =0            

    async def SendMsg(self,destino,msg):
        #self.log.debug(f"SEND MSSG destino  {destino}")
        if(destino=="SDATA"):
            await self.out_SData.put(copy.deepcopy(msg)) #Envio mensaje a SDATA
        elif(destino=="STRAT"):
            await self.out_Strat.put(copy.deepcopy(msg)) #Envio mensaje al strat
        else:
            self.log.error(f"SEND MSSG destino sin definir {msg}")
            return



    ###################################################################################################################################
    #                                                                                                                                 #
    #                                                   CALLBACKS                                                                     #
    #                                                                                                                                 #
    ###################################################################################################################################

    def on_account_value(self,accountValue):
        if accountValue.tag == "AccountCode":
            self.log.info(f" {accountValue.tag}: value {accountValue.value} currency {accountValue.currency}")
        
    async def on_tick_update(self, ticker):
        self.timer.SetTaskStatus("BKR_PADRE","working")

        data = {
            "type": "tick",
            "symbol": ticker.contract.symbol,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "last": ticker.last,
            "time": self.timer.getNow().isoformat()
        }
        #self.log.debug(f"RX TICK IBKR {ticker.contract.symbol} bid:{ticker.bid} last:{ticker.last}")
        
        msgTick = TickMsg(
                source="BKR",
                symbol=ticker.contract.symbol,
                time=self.timer.getNow(),
                bid=ticker.bid,
                ask=ticker.ask,
                last=ticker.last,
                
        )
        #asyncio.create_task(self.out_SData.put(msgTick)) ## en funciones no async
        await self.SendMsg("SDATA",msgTick)
        self.timer.SetTaskStatus("BKR_PADRE","idle")

    def on_order_status(self, trade):
        """
        Callback que recibe SOLO un objeto Trade
        """
        self.timer.SetTaskStatus("BKR_PADRE","working")
        try:
        
            order_status = trade.orderStatus
            parent_id= trade.order.parentId
            if parent_id==0  or parent_id==None: parent_id=None

            # Log sin caracteres especiales para evitar errores de codificación
            self.log.info(f"[ORDER STAT] {trade.contract.symbol} | Orden {order_status.orderId} permID:{order_status.permId} :{order_status.status} | Padre:{trade.order.parentId} |"
                        f"filled: {order_status.filled} | remaining: {order_status.remaining} | "
                        f"avgPrice: {order_status.avgFillPrice} ")
                        
            if hasattr(trade, 'contract') and trade.contract is not None:
                #contiene contract
                contract = trade.contract
                symbol = contract.symbol
            else:
                contract = None
                symbol=""
                self.log.warning(f"[ORDER STAT] NO CONTIENE CONTRACT") 

            if hasattr(trade, 'order') and trade.order is not None:
                #contiene order
                order = trade.order
            else:
                order=None
                self.log.warning(f"[ORDER STAT] NO CONTIENE ORDER") 

            if hasattr(trade, 'orderStatus') and trade.orderStatus is not None:
                #contiene contract
                orderStatus = trade.orderStatus
            else:
                orderStatus = None
                self.log.warning(f"[ORDER STAT] NO CONTIENE STATUS") 
           
            """
            self.log.debug(f"------------------------------------------------------------------------")
            self.log.debug(f"[ORDER STAT] TRADE {trade}")
            self.log.debug(f"------------------------------------------------------------------------")
            self.log.debug(f"[ORDER STAT] ORDER {order}")
            self.log.debug(f"------------------------------------------------------------------------")
            self.log.debug(f"[ORDER STAT] STAT  {order_status}")
            """
            symbol      = contract.symbol
            
            qtyTot      = order.totalQuantity
            orderID     = order.orderId
            orderType   = order.orderType
            
            permID      = orderStatus.permId     #se puede sacar de Order

            parentID    = orderStatus.parentId  #se puede sacar de Order

            status      = orderStatus.status
            qtyFill     = orderStatus.filled
            priceAvg    = orderStatus.avgFillPrice
           
            priceLim=0

            if(parentID==0):
                tipoBrk = Bracket.PADRE
                if  order.action == 'SELL': 
                    qtyTot *=-1
                    qtyFill*=-1


                if  orderType=="LMT":
                    priceLim=order.lmtPrice
                else:
                    priceLim=0
                    
            elif isinstance(trade.order,(StopOrder, StopLimitOrder)) or orderType=="STP":
                tipoBrk  = Bracket.ST
                priceLim    = order.auxPrice
            else: 
                tipoBrk     = Bracket.TP
                priceLim    = order.lmtPrice
           
            time= self.timer.getNow()
            with self.lock_Oper:                     
                    self.t_Oper.UpdateOrders(symbol,qtyTot,qtyFill,priceLim,priceAvg,status,permID,orderID,parentID,tipoBrk,time)
                    #self.t_Oper.UpdateAllPosition()
                    #self.t_Oper.ShowAll()
         
            
            #if hasattr(self, 'out_Strat') and self.out_Strat:
            #    asyncio.create_task(self.out_Strat.put(data))
    
        except Exception as e:
            self.log.exception(f"Error procesando status de orden: {e}")   
        finally:
            self.timer.SetTaskStatus("BKR_PADRE","idle")


    def on_exec_details(self, trade, fill):
        self.timer.SetTaskStatus("BKR_PADRE","working")

        """
            self.log.debug(f"------------------------------------------------------------------------")
            self.log.debug(f"[ORDER STAT] TRADE {trade}")
            self.log.debug(f"------------------------------------------------------------------------")
            self.log.debug(f"[ORDER STAT] FILL {fill}")
            self.log.debug(f"------------------------------------------------------------------------")
            
        """
        """
            Datos REPETIDOS:
            fill.orderId = trade.order.orderId
            fill.contract.symbol = trade.contract.symbol
            fill.exchange = trade.contract.exchange
            fill.contract.secType = trade.contract.secType
            fill.contract.currency = trade.contract.currency
            fill.clientId = trade.order.clientId
            fill.permId = trade.order.permId
        """
        #contract = trade.contract
        contract = getattr(trade, 'contract', None)
        if contract:
            symbol = contract.symbol
        else:
            symbol = ""
            self.log.warning(f"[ORDER STAT] NO CONTIENE CONTRACT")


        order       = trade.order
        orderID     = order.orderId
        permID      = order.permId
        parentID    = order.parentId
        orderType   = order.orderType
        qtyTot      = order.totalQuantity
        
        orderStatus = trade.orderStatus
        status      = orderStatus.status
        #permID      = orderStatus.permId
        #parentID    = orderStatus.parentId
        
        priceAvg    = fill.execution.price
        qtyFill     = fill.execution.shares

        priceLim=0

        if(parentID==0):
            tipoBrk = Bracket.PADRE
            if  order.action == 'SELL': 
                qtyTot*=-1

            if  orderType=="LMT":
                priceLim=order.lmtPrice
            else:
                priceLim=0
                
        elif isinstance(trade.order,(StopOrder, StopLimitOrder)) or orderType=="STP":
            tipoBrk  = Bracket.ST
            priceLim    = order.auxPrice
        else: 
            tipoBrk     = Bracket.TP
            priceLim    = order.lmtPrice

        self.log.info(f"[ORDER EXEC DETAIL] {trade.contract.symbol} ORDER ID{orderID} permID{permID} - {status} | Padre {parentID} |"
                f"filled: {qtyFill} | "
                f"avgPrice: {priceAvg:.2f} | "
                )
               
     
      
        #en caso filled, hay que actualizar precio

    
        time= self.timer.getNow()

        with self.lock_Oper:                     
            self.t_Oper.UpdateOrders(symbol,qtyTot,qtyFill,priceLim,priceAvg,status,permID,orderID,parentID,tipoBrk,time)
            #self.t_Oper.UpdateAllPosition()
            #self.t_Oper.ShowAll()
    
        #asyncio.create_task(self.out_Strat.put(data))
        self.timer.SetTaskStatus("BKR_PADRE","idle")

        

    def on_ibkr_error(self, reqId, errorCode, errorString, contract=None):
        self.timer.SetTaskStatus("BKR_PADRE","working")
        if(errorCode==2104 or errorCode==2106 or errorCode==2158 ):
            return
        self.log.error(f" Error {errorCode}: {errorString}")
        # Desconexiones comunes: 1100 (lost), 1101 (restored), 1300 (disconnected)
        if errorCode in (1100, 1300):
            self.connected = False
        self.timer.SetTaskStatus("BKR_PADRE","idle")

    def on_ibkr_disconnected(self):
        self.log.warning("Desconexión detectada")
        self.connected = False

    async def on_realtime_bar(self, bars, hasNewBar):
        self.timer.SetTaskStatus("BKR_PADRE","working")
        """
        Callback para nuevas barras en tiempo real
        """
        try:
            if hasNewBar:
                
                # Obtener la última barra
                last_bar = bars[-1]
                
                lastDate= last_bar.time # este campo ya es un datetime

                barLast=OneBar(
                        symbol  = bars.contract.symbol,
                        date    = lastDate,
                        open    = last_bar.open_,
                        high    = last_bar.high,
                        low     = last_bar.low,
                        close   = last_bar.close,
                        volume  = last_bar.volume,
                        barCount= last_bar.count,
                        #avg=     last_bar.avg  # Weighted Average Price
                            )
                #self.log.debug(f"[BAR] {bars.contract.symbol} {last_bar}")    
                self.log.debug(f"[BAR] {bars.contract.symbol} {barLast.date} h:{barLast.high} l:{barLast.low} c:{barLast.close} vol:{barLast.volume}")   
                symbol = bars.contract.symbol
                agg_bar = self.barAggregator.updateBar(barLast)
                if agg_bar:                
                    TimeInZone= agg_bar["time"].astimezone(timeZone) #convertidas a TIMEZONE si no es df
                    msgTRBar = TRBar(
                            source="BKR",
                            symbol  = agg_bar["symbol"],
                            time    = TimeInZone,
 
                            open    = agg_bar["open"],
                            high    = agg_bar["high"],
                            low     = agg_bar["low"],
                            close   = agg_bar["close"],
                            vol     = agg_bar["volume"]
                        )
                    self.log.debug(f"[BAR] TO SEND SDATA {msgTRBar.symbol}")
                    await self.SendMsg("SDATA",msgTRBar)
                
                    
                
                
                    
        except Exception as e:
            self.log.exception(f"Error procesando barra RT: {e}")

        finally:
            self.timer.SetTaskStatus("BKR_PADRE","idle")

    async def onScanData(self,scanData):
        self.timer.SetTaskStatus("BKR_PADRE","working")
        #self.log.info (f"scan_sscanData recived { scanData}")

        symbols = []  # Lista para almacenar los símbolos
        for scan in scanData:
            contract = scan.contractDetails.contract
            symbol = contract.symbol
            symbols.append(symbol) 
            #self.log.debug( f"dato {scan.rank}")

        self.log.debug(f"HEAD Symbols SCANNER RECIBIDO {symbols[:5]}")                      
        self.log.debug(f"SCANNER TOTAL SYMBOL RX= {len(scanData)}")
        msgResult = ScanResultMsg(
                source="BKR",
                symbol="ALL",
                scan_code="",
                results=symbols
            )
        #asyncio.create_task(self.out_SData.put(msgResult)) ## en funciones no async
        await self.SendMsg("SDATA",msgResult)
        self.timer.SetTaskStatus("BKR_PADRE","idle")


    def on_position_update(self,position):
        self.timer.SetTaskStatus("BKR_PADRE","working")
        self.log.info(f"[POSITION] Cuenta: {position.account} | {position.contract.symbol} | Pos: {position.position} | Precio Promedio: {position.avgCost}")

        symbol=position.contract.symbol
        qty = position.position
        price=position.avgCost
        self.t_Oper.UpdatePosition(symbol,qty,price, self.timer.getNow())
        self.timer.SetTaskStatus("BKR_PADRE","idle")



    ###################################################################################################################################
    #                                                                                                                                 #
    #                                             FIN TRATAMIENTO   CALLBACKS                                                         #
    #                                                                                                                                 #
    ###################################################################################################################################



###################################################################################################################################
#                                                   Bar agregator                                                                 #
###################################################################################################################################


from datetime import datetime, timedelta

class SimpleBarAggregator:
    def __init__(self, interval_seconds=60):
        self.interval = timedelta(seconds=interval_seconds)
        self.agg_data = {}

    def _get_next_cutoff(self, now:datetime):
        # Redondeamos hacia el próximo múltiplo de intervalo con sec=00
        secs = now.second + now.minute * 60
        remainder = secs % self.interval.total_seconds()
        cutoff = now + timedelta(seconds=(self.interval.total_seconds() - remainder))
        cutoff = cutoff.replace(microsecond=0)
        return cutoff

    def updateBar(self, bar:OneBar):

        symbol = bar.symbol
        
        now = bar.date.replace(microsecond=0)

        if symbol not in self.agg_data:
            # Primera barra: inicializamos
            next_cutoff = self._get_next_cutoff(now)
            self.agg_data[symbol] = {
                "cutoff": next_cutoff,
                "start_time": now,  # GUARDAMOS el inicio de la barra
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "count": bar.barCount,
                "volume_sum": bar.volume
            }
            return None

        agg = self.agg_data[symbol]

        # Actualizamos acumulados
        #agg["high"] = max(agg["high"], bar.high)
        #agg["low"] = min(agg["low"], bar.low)
        #agg["close"] = bar.close
        #agg["volume"] += bar.volume
        #agg["count"] += bar.barCount
        #agg["volume_sum"] += bar.volume

        # Verificamos si se alcanzó el corte
        if now >= agg["cutoff"]:
            final_bar = {
                "symbol": symbol,
                "time": agg["start_time"],  # 🕒 USAMOS el comienzo real
                "open": agg["open"],
                "high": agg["high"],
                "low": agg["low"],
                "close": agg["close"],
                "volume": agg["volume"],
                "count": agg["count"],
            }
            # Reiniciar agregación para el próximo corte
            next_cutoff = self._get_next_cutoff(agg["cutoff"])
            self.agg_data[symbol] = {
                "cutoff": next_cutoff,
                "start_time": now,  # Comienzo de la nueva barra
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "count": bar.barCount,
                "volume_sum": bar.volume
            }
            return final_bar
        else:
            agg["high"] = max(agg["high"], bar.high)
            agg["low"] = min(agg["low"], bar.low)
            agg["close"] = bar.close
            agg["volume"] += bar.volume
            agg["count"] += bar.barCount
            agg["volume_sum"] += bar.volume
            
        
        return None
