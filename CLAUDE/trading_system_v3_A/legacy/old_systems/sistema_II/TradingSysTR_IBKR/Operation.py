

from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple, Union,List,Optional
from enum import Enum
from datetime import datetime, timedelta
from Utils import *

class OrderStatus(str, Enum):

    REQUESTED   =   "Requested"
    PENDING     =   "Pending"
    CLOSED      =   "Closed"
    UNKNOW      =   "Unknow"
    # Estados comunes
    PEND_SUBMIT =   'PendingSubmit'     # Orden creada pero no enviada aún
    PEND_CANCEL =   'PendingCancel'     # Cancelación pendiente
    PRESUBMITED =   'PreSubmitted'      # Orden pre-enviada (fuera de horario)
    SUBMITTED   =   'Submitted'         # Orden enviada y activa
    CANCELED    =   'Cancelled'         # Orden cancelada
    FILLED      =   'Filled'            # Orden completamente ejecutada
    # Estados de ejecución parcial
    PARTIAL_FILL=   'PartiallyFilled'   # Orden parcialmente ejecutada
    # Estados de API
    API_PEND    =   'ApiPending'        # Pendiente en API
    API_CANCEL  =   'ApiCancelled'      # Cancelada por API
    # Estados especiales
    INACTIVE    =   'Inactive'          # Orden inactiva (ej: fuera de horario)
    


class Bracket(str, Enum):
    UNDEF   = "UNDEF"
    PADRE   = "PADRE"
    TP      = "TP"
    ST      = "ST"

ID_NODEF = 999999000


#Update(symbol,ID,qty,price,stat,permID,parentID,TIPO, time) 


@dataclass
class OneOrder:

    symbol: str
    #contract: object
    permID:int = 0
    orderID:int =0   
    tipoBracket:Bracket = Bracket.UNDEF
    status: OrderStatus = OrderStatus.UNKNOW.value

    qtyTot: int =0.0   #qty positiva-> BUY negativa -> SELL
    qtyFill: int = 0

    priceAvg: float = 0
    priceLim: float = 0.0
    
    parentID:int = 0
    OpenOrder: bool= True

@dataclass
class OneEntry:

    symbol: str
    #contract: object
    
    ID: int = None      # ID = None- orderID de parent si no hay permID o permID
    qtyTot: int =0.0   #qty positiva-> BUY negativa -> SELL
    qtyFill: int = 0
    priceAvg: float = 0
    priceLim: float = 0.0

    status: OrderStatus = OrderStatus.UNKNOW.value

    stLevel: float =0
    stID: int =0
   
    tpLevel: float = 0
    tpID: int =0

   
    #remaining_qty: int = 0
    
    permID:int = 0
    orderID:int =0


class OnePosition:
    
    ID:str
    symbol: str
    qty_tot: int
    qty_exec: int
    PriceAvg: float

    def __init__(self,symbol):
        self.Entries: Dict[Tuple[str, int], OneEntry] = {}
        self.symbol=symbol
        self.ID=0
        self.qty_tot=0
        self.qty_exec=0
        self.PriceAvg=0
    
    def _key(self, symbol: str, ID:int):
        return (symbol,ID)

class Operation:
    def __init__(self):
        # Indexamos por (symbol, ID y )
        # parent_orderId podria  ser None inicialmente ? esperamos que no
        
        # dictionario de:    -symbol    -qty    -ID optional
        self.Positions: Dict[str , OnePosition] = {}

        self.Orders: List[OneOrder] = []

        self.log =  get_logger("OPER")
        
        self.idNoDef = ID_NODEF

    #def _key(self, symbol: str):
    #    return (symbol)
    

    def VerificaStatus(self,status):
        # Verificar si es un enum o un string
        if isinstance(status, OrderStatus):
            # Ya es un enum, usarlo directamente
            actual_status = status
        elif isinstance(status, str):
            # Es un string, intentar convertirlo a enum
            try:
                actual_status = OrderStatus(status)
            except ValueError:
                #Status inválido: {status}")
                actual_status = OrderStatus.UNKNOW.value
        else:
            #f"Tipo no soportado: {type(status)}")
            actual_status = OrderStatus.UNKNOW.value
        
        return actual_status

    def DecideIDOrder(self,order:OneOrder):
        ID:int=0
        if(order.permID!=None and order.permID!=0):
            ID= order.permID
        elif(order.orderID!=None and order.orderID!=0):
            ID= order.orderID
        else:
            ID= self.idNoDef
            self.idNoDef+=1
            self.log.error(f"Order {order.symbol} sin DATOS ID")

        return ID
 
    def ActualizaEntry(self,entry:OneEntry,order:OneOrder):
        
        if  order.tipoBracket==Bracket.PADRE:
                
            entry.permID   = order.permID
            entry.orderID  = order.orderID

            entry.qtyTot=order.qtyTot
            entry.qtyFill=order.qtyFill

            entry.status=order.status
        
            entry.priceLim=order.priceLim
            entry.priceAvg=order.priceAvg
    
        elif order.tipoBracket==Bracket.ST:
            entry.stLevel= order.priceLim
            entry.stID   = order.ID

        elif order.tipoBracket==Bracket.TP:
            entry.tpLevel= order.priceLim
            entry.tpID   = order.ID
        
        else:
            self.log.error(f"ActualizaEntry {order.symbol} sin tipoBRACKET")
        
    
    def BuscaTickerOrderID(self,iPosition:OnePosition,orderID:int):

        symbol=iPosition.symbol
        ticket=None
        for key, entry in iPosition.Entries.items():
            if(entry.symbol==symbol and entry.orderID==orderID):
                ticket=iPosition.Entries.get(key)
                #ticket=entry
                break

        return ticket
    
    
    def InsertHija(self,iPosition:OnePosition,orderHija:OneOrder):

        #Busco donde instertar a través del parentID
        parentID= orderHija.parentID
        ID_hija= self.DecideIDOrder(orderHija)

        OrderPadre: Optional[OneOrder] = None

        for order in self.Orders:
          if order.symbol == iPosition.symbol and order.permID == parentID:
            OrderPadre = order
            break  # ← Útil si solo quieres el
        
        if(OrderPadre==None):
            for order in self.Orders:
                if order.symbol == iPosition.symbol and order.orderID == parentID:
                    OrderPadre = order
                    break  # ← Útil si solo quieres elbu
                    
        if(OrderPadre==None):
            self.log.warning(f"InsertHija {iPosition.symbol} Debe crear ORDEN PADRE FANTASMA que no está en las ordenes OPEN/EXECUTED")
            OrderPadre=OneOrder(symbol=iPosition.symbol,permID=parentID,orderID=parentID,parentID=0, qtyTot = -orderHija.qtyTot, qtyFill = orderHija.qtyTot, tipoBracket=Bracket.PADRE)
            OrderPadre.OpenOrder=False

        #Una vez resuelto incluida la order. busco el Entry del padre

        ticketPadre    = iPosition.Entries.get((iPosition.symbol,parentID))
        if (ticketPadre==None):
            ticketPadre=self.BuscaTickerOrderID(iPosition,parentID)

        if (ticketPadre==None):
            #definitivamente no está la entry. pero si estaba la order. hay que crearla
            self.InsertPadre(iPosition,OrderPadre)
            ticketPadre=self.BuscaTickerOrderID(iPosition,parentID)

        if (ticketPadre!=None):
            if(orderHija.tipoBracket==Bracket.ST):
                ticketPadre.stLevel=orderHija.priceLim
                ticketPadre.stID=ID_hija
                self.log.info(f"INSERT HIJA SetST")
            if(orderHija.tipoBracket==Bracket.TP):
                ticketPadre.tpLevel=orderHija.priceLim
                ticketPadre.tpID=ID_hija
                self.log.info(f"INSERT HIJA SetTP")

            self.log.info(f"InsertHija en PADRE id:{ticketPadre.ID} Perm-ORDER {ticketPadre.permID} {ticketPadre.orderID } qtyTot{ticketPadre.qtyTot} st:{ticketPadre.stLevel } tp:{ticketPadre.tpLevel }")
            self.log.info(f"InsertHija HECHO ORDER HIJA: Permid:{orderHija.permID} order:{orderHija.orderID} tipo{orderHija.tipoBracket} status{orderHija.status} parent{orderHija.parentID}")
        else:
            self.log.error(f"InsertHija ERROR SIN ENCONTRAR PADRE ORDER HIJA: Permid:{orderHija.permID} order:{orderHija.orderID} tipo:{orderHija.tipoBracket} parent:{orderHija.parentID}")


    def InsertPadre(self,iPosition:OnePosition,order:OneOrder):

        ID= self.DecideIDOrder(order)

        if(order.permID!=None and order.permID!=0):
            ID= order.permID
        elif(order.orderID!=None and order.orderID!=0):
            ID= order.orderID
        else:
            ID= self.idNoDef
            self.idNoDef+=1
            self.log.error(f"InsertPadre - Order {iPosition.symbol} sin DATOS ID")
        
        ## Chequear que no existe
        #ticketPerm  = iPosition.Entries.get(order.permID)
       
        ticketID    = iPosition.Entries.get((iPosition.symbol,ID))

        if(ticketID!=None):
            #Existe entrada con su ID
            self.ActualizaEntry(ticketID,order)
            self.log.info(f"InsertPadre ENTRY existente {iPosition.symbol} id {ticketID.ID} qtyTot {ticketID.qtyTot}")
        else:
            #No existe entrada con su ID. Debo crear una nueva entrada, y borrar la antigua si estaba con ordID
            newEntry=OneEntry(symbol=iPosition.symbol, ID=ID)
            self.ActualizaEntry(newEntry,order)
           
            #ticketOrder = iPosition.Entries.get((iPosition.symbol,order.orderID)) ## ojo, podria ser fantastma. Hay que buscar el OrderID
            ticketOrder=self.BuscaTickerOrderID(iPosition,order.orderID)
            if(ticketOrder!=None):
                #existía la orden, con orderID (bien por temporal, o por hijas st, )tp
                #Copio st-
                newEntry.stID=ticketOrder.stID
                newEntry.stLevel=ticketOrder.stLevel
                newEntry.tpID=ticketOrder.tpID
                newEntry.tpLevel=ticketOrder.tpLevel
                #borro toda la entrada con clave incluida. No se puede hacer por ticket
                del iPosition.Entries[(iPosition.symbol,order.orderID)]
                self.log.info(f"newEntry {newEntry}")
            
            #INSERTA CLAVE CORRECTA
            iPosition.Entries[(iPosition.symbol,ID)]=newEntry
            self.log.info(f"InsertPadre NEW ENTRY  {iPosition.symbol} id {newEntry.ID} qtyTot {newEntry.qtyTot}")

    def isOpenOrder(self,order:OneOrder):
        if(order.status==OrderStatus.REQUESTED.value):
            return True
        elif(order.status==OrderStatus.PENDING.value):
            return True
        elif(order.status==OrderStatus.PRESUBMITED.value):
            return True
        elif(order.status==OrderStatus.SUBMITTED.value):
            return True
        elif(order.status==OrderStatus.PEND_SUBMIT.value):
            return True
        elif(order.status==OrderStatus.UNKNOW.value):
            return True
        elif(order.status==OrderStatus.PEND_CANCEL.value):
            return True
        elif(order.status==OrderStatus.PARTIAL_FILL.value):
            return True
        elif(order.status==OrderStatus.API_PEND.value):
            return True
        #elif(order.status==OrderStatus.API_CANCEL.value):
        #    return True
        #elif(order.status==OrderStatus.INACTIVE.value):
        #    return True
        else:

            return False


 

    def RegeneraAllEntries(self,iPosition:OnePosition):
        symbol=iPosition.symbol
        iPosition.Entries.clear()
        self.log.info(f"RegeneraAllEntries to Position:{iPosition.symbol} ")

        numOrders=0
        
        for  order in self.Orders:
            if(order.symbol==symbol):

                if  order.tipoBracket==Bracket.PADRE and self.isOpenOrder(order):
                    self.InsertPadre(iPosition,order)
                    numOrders+=1

                elif order.tipoBracket==Bracket.ST and self.isOpenOrder(order):
                    self.InsertHija(iPosition,order)
                    numOrders+=1
                elif order.tipoBracket==Bracket.TP and self.isOpenOrder(order):
                    self.InsertHija(iPosition,order)
                    numOrders+=1
                else:
                    self.log.info(f"RegeneraAllEntries Order {symbol} id:{order.permID}-{order.orderID}. not OPEN: {order.status}")
        
        self.log.info(f"RegeneraAllEntries RESULT:{iPosition.symbol} num.Orders procesadas:{numOrders} qty-exec {iPosition.qty_exec} qty-tot {iPosition.qty_exec}")



    def SincroEntries(self,iPosition:OnePosition):
        
        qty_exec=iPosition.qty_exec
        qty_exec_entries=0
        qty_tot_entries=0
        self.RegeneraAllEntries(iPosition)

        for key, entry in iPosition.Entries.items():
            self.log.info(f"SincroEntries itera: {iPosition.symbol} entry {key} ID: {entry.ID} QtyTot: {entry.qtyTot}")
            qty_exec_entries+=entry.qtyFill
            qty_tot_entries +=entry.qtyTot

        if(qty_exec!=qty_exec_entries):
            #FALTA UNA EJECUION. Poner la entrada que falta, que es un EXECUTION ANTIGUO
            self.log.warning(f"SincroEntries {iPosition.symbol} CREA ENTRY FANTASMA que no está en las ordenes OPEN/EXECUTED")
            id= self.idNoDef
            self.idNoDef+=1
            qty_fantasma= qty_exec-qty_exec_entries
            OrderPadre=OneOrder(symbol=iPosition.symbol,permID=id,orderID=id,qtyTot = qty_fantasma,qtyFill = qty_fantasma,status=OrderStatus.FILLED.value,tipoBracket=Bracket.PADRE)
            qty_tot_entries+=qty_fantasma
            self.InsertPadre(iPosition,OrderPadre)
        
        iPosition.qty_tot=qty_tot_entries
       
        self.log.warning(f"SincroEntries RESULT:{iPosition.symbol} qty-exec:{iPosition.qty_exec} qty-tot:{iPosition.qty_tot}")

    def CreaPosition(self,symbol):
        ticket= self.Positions.get(symbol)
        if(ticket==None):
            ticket=self.Positions[symbol]=OnePosition(symbol=symbol)
        else:
            self.log.error(f"CreaPosition {symbol} Ya existe")

        return ticket



    def SincroOrdersOnlyOpen(self):
        for  order in self.Orders:
            symbol=order.symbol
            iPosition = self.Positions.get(symbol)
            if(iPosition==None ):
                if(order.qtyFill==0 and self.isOpenOrder(order)):
                    self.log.info(f"SincroOrdersOnlyOpen ({order.status})")
                    iPosition = self.CreaPosition(symbol)    
                    iPosition.qty_exec=order.qtyFill
                    iPosition.PriceAvg=order.priceAvg
                    #iPositio#n.time=time  
                    self.SincroEntries(iPosition)
                #else:
                #    self.log.error(f"SincroOrdersOnlyOpen {symbol} NO DEBERIA ENTRAR UNA ORDEN FILLED SIN POSITION")


    def UpdatePosition(self,symbol:str,qty:int,price:float, time: datetime):

        iPosition = self.Positions.get(symbol)
        if(iPosition==None):
            iPosition = self.CreaPosition(symbol)
        
        #YA existe la position antes o creada
        
 
        iPosition.qty_exec=qty
        iPosition.PriceAvg=price
        #iPositio#n.time=time 
        self.log.info(    f"[UpdatePosition] {iPosition.symbol} QtyExec. {iPosition.qty_exec} PriceAvg. {iPosition.PriceAvg}")
         
        self.SincroEntries(iPosition)
        #self.SincroOrdersOnlyOpen()


    def UpdateOrders(self,symbol,qtyTot,qtyFill,priceLim,priceAvg,status,permID,orderID,parentID,tipoBrk,time):

        OrderNew: Optional[OneOrder] = None    
        
        for order in self.Orders:
            if order.symbol == symbol and order.permID==permID and order.permID!=0 and order.permID!=None:
                OrderNew = order
                break  

        if(OrderNew==None):
            for order in self.Orders:
                if order.symbol == symbol and order.orderID==orderID and order.orderID!=0 and order.orderID!=None:
                    OrderNew = order
                    break  

        if(OrderNew!=None):
            #ya hay una orden. Solo ajustar a esa orden el permID, el estatus, 
            if(OrderNew.permID==None or OrderNew.permID==0):
                OrderNew.permID=permID

            if(OrderNew.orderID==None or OrderNew.orderID==0):    
                OrderNew.orderID=orderID

            if(OrderNew.qtyFill<qtyFill):    
                OrderNew.qtyFill=qtyFill

            OrderNew.status=status 
            OrderNew.priceAvg=priceAvg 

            if abs(qtyFill)>=abs(qtyTot) or not self.isOpenOrder(OrderNew): 
                OrderNew.OpenOrder=False

        else:
            OrderNew=OneOrder(symbol=symbol,permID=permID,orderID=orderID,qtyTot=qtyTot,qtyFill = qtyFill,priceLim= priceLim, priceAvg=priceAvg,tipoBracket=tipoBrk,parentID=parentID,status=status)
            if abs(qtyFill)>=abs(qtyTot) or not self.isOpenOrder(OrderNew): 
                OrderNew.OpenOrder=False
   
           
            self.Orders.append(OrderNew)        
        
        self.log.info(    f"UpdateOrders NEW ORDER  {OrderNew.symbol}-IDs:{OrderNew.permID}-{OrderNew.orderID}-tipo:{OrderNew.tipoBracket.value}-parentID:{OrderNew.parentID}   \tQtyTot:{OrderNew.qtyTot} priceLim:{OrderNew.priceLim:.2f}")
        
        self.UpdateOnePosition(symbol) # Por cambio de orden, reviso la posición de su symbol


    def UpdateOnePosition(self,symbol):

        for key, position in self.Positions.items():
            if(position.symbol== symbol):
                self.SincroEntries(position)

    def UpdateAllPosition(self):

        for key, position in self.Positions.items():
            self.SincroEntries(position)
 
    def ShowAllOrders(self):

        self.log.info(    f"--------------------------------------------------------------------------------------------------------------------------")
        for order in self.Orders:
            self.log.info(    f"ORDER {order.symbol}-IDs:{order.permID}-{order.orderID}-tipo:{order.tipoBracket.value}-status:{order.status} -parentID:{order.parentID}  \t\tQtyTot:{order.qtyTot} QtyFIll:{order.qtyFill} priceLim:{order.priceLim:.2f}")
        
        self.log.info(    f"--------------------------------------------------------------------------------------------------------------------------")
     

    def isEntryPosition(self,symbol):
                 
        for key, position in self.Positions.items():
            if(position.symbol==symbol):
                if(position.qty_tot!=0):
                    return True
                else:
                    return False
               
        return False
     

    def ShowAll(self):
        p=0
        e=0
        self.log.info(    f"-------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        self.log.info(    f"#-------------                                                    POSICIONES                                                                          ------------#")  
        self.log.info(    f"-------------------------------------------------------------------------------------------------------------------------------------------------------------------")
               
        for key, position in self.Positions.items():
            
            if(position.qty_tot==0 and position.qty_exec==0):
                continue #ni hasy ordenes, ni las piden
            self.log.info( f"OPERATION POSITION({p:>2})" f" {position.symbol:<12}" f" Qty ORD.:{position.qty_tot:>8}" f" Qty FILL:{position.qty_exec:>12}" f" Avg.Price:{position.PriceAvg:>8.2f}")
            e=0
            for kent, entry in position.Entries.items():
                #self.log.info( f"OPERATION POSITION({p})" f"{position.symbol:<25}" f" Qty ORDERED:{position.qty_tot:>8}" f" Qty FILL:{position.qty_exec:>8}" f" Avg.Price:{position.PriceAvg:>8.2f}")
                self.log.info( f"               ---({e:>2})" f" {entry.ID:<12}"        f" Qty ORD.:{entry.qtyTot:>8}"     f" Qty FILL:{entry.qtyFill:>12}" f" Avg.Price:{position.PriceAvg:>8.2f}" f"   - PriceLim:{entry.priceLim:>6.2f} -ST:{entry.stLevel:>8.2f}  -TP:{entry.tpLevel:>8.2f}")
                e+=1
            
            p+=1
            self.log.info(    f"===================================================================================================================================================================")
    
        
    
        return list(self.Positions.values())
    
    def Clear(self):
        self.Positions.clear()

    def ClearOrders(self):
        self.Orders.clear()