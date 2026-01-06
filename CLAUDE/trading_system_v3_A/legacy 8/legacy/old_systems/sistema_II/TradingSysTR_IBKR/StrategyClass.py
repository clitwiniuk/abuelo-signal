from ThTimer import ThTimer

import pandas as pd

from datetime import *

from Messages import *
import asyncio
from   Utils import *
from   Operation import *
from   RiskMgmt import *
from   AlgoritmoClass import *
import pytz
import copy
#from ThStrategy import ThStrat

class OneStrategy:
    def __init__(   self, 
                    table_Scan:pd.DataFrame,
                    bloq_Scan,

                    table_Operation:Operation,
                    bloq_Operation,
                    timer: ThTimer,

                    ThStrat,
                ):
        self.id = "BASE"
        self.ThStrat = ThStrat
        self.t_Scan     = table_Scan
        self.lock_Scan = bloq_Scan

        self.t_Oper= table_Operation
        self.lock_Oper = bloq_Operation
        self.timer = timer

        self.tipoST= cfSys['Stop']['tipo']
        self.tipoTP= cfSys['TakeP']['tipo']
        self.tipoMM= cfSys['Mm']['tipo']

        self.kSt = cfSys['Stop']['Kst']
        self.kTp = cfSys['TakeP']['Ktp']
        self.Mm  = cfSys['Mm']['val']
        
        self.log =  get_logger("ST(0)")

        self.lastDay = datetime(1980, 1, 1, 00, 00, 0,tzinfo=timeZone)  # Año, mes, día, hora, minuto, segundo -> en timezone

        self.RM = RiskMgmt()
        self.RM.SetStop(self.tipoST,self.kSt)
        self.RM.SetTake(self.tipoTP,self.kTp)
        self.RM.SetMM(self.tipoMM,self.Mm)
        self.log.info(f" RISK-TIPOS {self.tipoMM}:{self.Mm}  {self.tipoST}:{self.kSt} {self.tipoTP}:{self.kTp}")
        self.AlgoCode= cfSys["System"]["Algoritmo"]
        self.mAlgo=self.CrearAlgoritmo(self.AlgoCode)
    
    
    def CrearAlgoritmo(self,id: str) -> CAlgo:
        if id == "A00":
            return Algo00(self.t_Scan,self.lock_Scan,self.t_Oper,self.lock_Oper)
        else:
            return CAlgo(id,self.t_Scan,self.lock_Scan,self.t_Oper,self.lock_Oper)

    async def GestionaEstrategia(self):
        return False
    
    async def Init(self):
        return False


################################################################################################################################################################################
#                                                                                                                                                                              #                                                                                                                                                              
#                                                                       STRATEGIA 00                                                                                           #                                                                                                                                                              
#                                                                                                                                                                              #                                                                                                                                                              
################################################################################################################################################################################                                                                                                                                                                              #                                                                                                                                                              
class Strat00(OneStrategy):
    def __init__(self, table_Scan, bloq_Scan, table_Operation, bloq_Operation, timer,ThStrat ):
        super().__init__( table_Scan, bloq_Scan, table_Operation, bloq_Operation,timer,ThStrat)
        self.id = "S00"        

    async def Init(self):
     ###   await self.LimpiaSistema() #esta estrateia limpia de ordenes el sistema al inicio
        return False
    
    async def GestionaEstrategia(self):
       
        hoy =self.timer.getNow()

        with self.lock_Oper:
            self.t_Oper.ShowAll()

        with self.lock_Scan:
            await self.ShowScanData()
            

        if(hoy.day != self.lastDay.day):
            #Comienzo del día
            self.log.info("GESTION CAMBIO DIA")
            #self.log.debug(f"TSCAN {self.t_Scan}")
            
        with self.lock_Scan:
            await self.SetPVarDay() #poner el close del dia anterior
            await self.CalculaProb() #poner el close del dia anterior
    
        await self.Opera()
        
      

    

    async def Opera(self):
        
        #IniOper = time.fromisoformat(cfSys['OperationTime']['ini'])
        #FinOper = time.fromisoformat(cfSys['OperationTime']['fin'])
       
        IniOper = datetime.strptime(cfSys['OperationTime']['Entryini'], '%H:%M').time()
        FinOper = datetime.strptime(cfSys['OperationTime']['Entryfin'], '%H:%M').time()
        OutTime = datetime.strptime(cfSys['OperationTime']['OutTime'], '%H:%M').time()
        
        now=self.timer.getNow()
        nowTime= now.time()
       
        ############ PRUEBA
        for index, row in self.t_Scan.iterrows():
            mSymbol=row[CData.SYMBOL]
            Entrada= self.mAlgo.Entrada(mSymbol)
        ############ PRUEBA
            
        if not self.isTimeToOperate():
            return
        
            #TIEMPO DE OPERACION
        for index, row in self.t_Scan.iterrows():
            mSymbol=row[CData.SYMBOL]

           
            if not self.isPriceActualizado(index):
                continue
            if not self.PreConditionToEntry(index):
                continue
            
            Entrada= self.mAlgo.Entrada(mSymbol)   

           
            if Entrada and "Send" not in row[CData.CTRLDATA] and not self.t_Oper.isEntryPosition(symbol=mSymbol):
                #envio orden si cumple PROB
                bid  = round(row[CData.BID],2)
                ask  = round(row[CData.ASK],2)
                stop = round(self.RM.GetStop(ask,"SELL"),2)
                tp   = round(self.RM.GetTake(bid,stop,"SELL"),2)
                lote = round(self.RM.GetLote(bid,stop),0)
                
                self.log.info( f"RIKS MNG price {ask} stop {stop}, tp {tp} lot {lote}")
                msgOrder = OrderMessage(
                            source="STRAT",
                            symbol=mSymbol,
                            side="SELL",
                            qty=lote,
                            price= bid,
                            tipoOrder="LMT",
                            st= stop,
                            tp= tp,
                            
                        )
                self.log.info(f"Send Order to BKR {msgOrder}")
                #await self.out_Bkr.put(msgOrder) #Envio mensaje al Broker
                await self.ThStrat.SendMsg( "BKR", msgOrder) #Envio mensaje al Broker

                self.t_Scan.at[index,CData.CTRLDATA]+="Send"
                    
    
        if(nowTime >OutTime ):
            await self.LimpiaSistema()
     
    
    def PreConditionToEntry(self,idx):
       
        with self.lock_Scan:
            probabilidad    = self.t_Scan.at[idx, CData.PROB]
            percVariationDay= self.t_Scan.at[idx, CData.PVARDAY]
            symbol = self.t_Scan.at[idx, CData.SYMBOL]
    

        if  probabilidad>cfSys['ParamOp']['minProb'] and percVariationDay>cfSys['ParamOp']['minHeap']:
            
            ctrlData =self.t_Scan.at[idx,CData.CTRLDATA]

            if "NO_PREC" in ctrlData:
                ctrlData.replace("NO_PREC","SI_PREC")
            elif not "PREC" in ctrlData:
                ctrlData+="_SI_PREC"
            self.t_Scan.at[idx,CData.CTRLDATA]=ctrlData    #pone subscriciones
            return True
        else:
            ctrlData =self.t_Scan.at[idx,CData.CTRLDATA]
            if "SI_PREC" in ctrlData:
                ctrlData.replace("SI_PREC","NO_PREC")
            elif not "PREC" in ctrlData:
                ctrlData+="_NO_PREC"
            self.t_Scan.at[idx,CData.CTRLDATA]=ctrlData    #elimina subscriciones
            return False


    def isPriceActualizado(self,idx):
        now=self.timer.getNow()
        with self.lock_Scan:
            lastTime = self.t_Scan.at[idx, CData.LASTIME]

        if lastTime is not None and (now-lastTime)<timedelta(minutes=5):
            return True
        else:
            return False

    def isTimeToOperate(self):
 
        IniOper = datetime.strptime(cfSys['OperationTime']['Entryini'], '%H:%M').time()
        FinOper = datetime.strptime(cfSys['OperationTime']['Entryfin'], '%H:%M').time()
        OutTime = datetime.strptime(cfSys['OperationTime']['OutTime'], '%H:%M').time()
       
        now=self.timer.getNow()
        nowTime= now.time()
       
        if(nowTime >IniOper and nowTime<FinOper):
            return True
        else:
            return False



    def extraer_ultimo_close(self,subdf):
        if isinstance(subdf, pd.DataFrame) and not subdf.empty and "close" in subdf.columns:
            return subdf["close"].iloc[-1]
        return None  # o np.nan, o un valor por defecto



    def extraer_lastTime_close(self,subdf):
        if isinstance(subdf, pd.DataFrame) and not subdf.empty and "close"in subdf.columns and "date" in subdf.columns:
            return subdf["date"].iloc[-1]
        return None  # o np.nan, o un valor por defecto

    async def CalculaProb(self):
        
        for index, row in self.t_Scan.iterrows():
            
           # if(~row[CData.CTRLDATA].str.contains("PROB", na=False)): contains para pandas
           bid=row[CData.BID]
           if  CData.HDAY in row[CData.CTRLDATA] and (bid>0) and "PROB" not in row[CData.CTRLDATA]: #no se ha calculado, pero hay datos de dia
                #PRUEBA   
                prob=100
                casos=100

                self.t_Scan.at[index,CData.PROB]=prob
                self.t_Scan.at[index,CData.CASOS]=casos
                symbol= self.t_Scan.at[index,CData.SYMBOL]
               
                if(prob<cfSys['ParamOp']['minProb'] ): #prob mayor que minimo y hay más de 100 dias
                
                    self.t_Scan.at[index,CData.CTRLDATA]+="_NO_PROB"    #elimina subscriciones
                    #await self.out_SData.put(msgCtrl) #Envio mensaje al CONTROL DATA (no al BKR)
                    msgCtrl = ControlMsg(
                            source="STRAT",
                            symbol=symbol,
                            action= ControlAction.CANCEL_SUSCRIP,
                        )
                    self.log.info(f"Cancel SUBSCRIPCION por PROBABILIDAD {symbol}")   
                    await self.ThStrat.SendMsg("SDATA",msgCtrl)
                else:
                    self.t_Scan.at[index,CData.CTRLDATA]+="_SI_PROB"
                    if(cfSys['ParamOp']['autoData']!="SI"):  
                        #  No tenia autodata-> pedir  
                        self.log.info(f"PIDE POR PROB-1MIN and TR {symbol}")    
                        msgCtrlData = ControlMsg(
                            source="STRAT",
                            symbol=symbol,
                            action= ControlAction.REQ_1MIN_TOT,
                        )
                        await self.ThStrat.SendMsg("SDATA",msgCtrlData)


    async def SetPVarDay(self):

        maskValid = (    (self.t_Scan[CData.BID] > 0) 
                &   (self.t_Scan[CData.CTRLDATA].str.contains(CData.H1MIN, na=False))   #hay historia
                &   (self.t_Scan[CData.CTRLDATA].str.contains(CData.HDAY, na=False))    #hay historia
            )
        
        
        maskValid = (    
                    (self.t_Scan[CData.BID] > 0) 
                #&   (self.t_Scan[CData.CTRLDATA].str.contains(CData.H1MIN, na=False))   #hay historia
                &   (self.t_Scan[CData.CTRLDATA].str.contains(CData.HDAY, na=False))    #hay historia
                &   (self.t_Scan[CData.CLOSE_DAY] != 0)    #hay historia
             )
       
        # Una vez que tengas la máscara correcta
        
        
        df=self.t_Scan.loc[maskValid, CData.HDAY]
        
        lastDate=self.extraer_lastTime_close(df)
        
        self.t_Scan.loc[maskValid, CData.CLOSE_DAY] = self.t_Scan.loc[maskValid, CData.HDAY].apply(self.extraer_ultimo_close)
        
        self.t_Scan.loc[maskValid, CData.PVARDAY]=100*(self.t_Scan.loc[maskValid, CData.BID]-self.t_Scan.loc[maskValid, CData.CLOSE_DAY])/self.t_Scan.loc[maskValid, CData.CLOSE_DAY]

    
    


    async def SendCancelOrders(self,symbol):   
       
        if (symbol==None or symbol=="ALL"):
            sendSymbol="ALL"
        else:
            sendSymbol=symbol
            
        msgCtrl = ControlMsg(
                source="STRAT",
                symbol=sendSymbol,
                action= ControlAction.CANCEL_ORDERS,
            )

        self.log.info(f"Cancel ORDERS {sendSymbol}")   
        await self.ThStrat.SendMsg("BKR",msgCtrl)
        #await self.out_Bkr.put(msgCtrl) #Envio mensaje al Broker        s

    async def SendCierraPosition(self,symbol):   
       
        if (symbol==None or symbol=="ALL"):
            sendSymbol="ALL"
        else:
            sendSymbol=symbol
            
        msgCtrl = ControlMsg(
                source="STRAT",
                symbol=sendSymbol,
                action= ControlAction.CIERRA_POSICION,
            )

        self.log.info(f"REQ CIERRA POSICION {sendSymbol}")   
        await self.ThStrat.SendMsg("BKR",msgCtrl)
        #await self.out_Bkr.put(msgCtrl) #Envio mensaje al Broker        s


    async def LimpiaSistema(self):
        await self.SendCancelOrders("ALL")
        await self.SendCierraPosition("ALL")


    async def ShowScanData(self):       
            
        self.log.info(f"------------------------------------------------------------------------------------------------------------------------------------ ")
        encabezado = "{:<10}{:>8}{:>8}{:>10}{:>12}{:>22}{:>8}{:>10}{:>10}{:>10}{:>10}{:>30}".format(
            "Symbol", "Bid", "Ask", "pVarDay", "CloseDay", "lastTick", "Casos", "Prob", "OpenHoy", "HighHoy", "VolHoy", "Ctrl")
        self.log.info(encabezado)
        #self.log.info("-" * len(encabezado))
        self.log.info(f"------------------------------------------------------------------------------------------------------------------------------------ ")
        
        for index, row in self.t_Scan.iterrows():
            last="---------- --:--:--"
            if(row[CData.LASTIME]!=None):
                last = row[CData.LASTIME].strftime("%Y-%m-%d %H:%M:%S")
            
                #if(row[CData.PVARDAY]>cfSys['ParamOp']['minHeap'] and row[CData.PROB]>cfSys['ParamOp']['minProb']):
                #if( row[CData.PROB]>cfSys['ParamOp']['minProb']):
                if(True):
                    linea = "{:<10}{:>8.2f}{:>8.2f}{:>10.2f}%{:>12.2f}{:>22}{:>8}{:>10.1f}%{:>10.1f}{:>10.1f}{:>10.0f}{:>30}".format(
                            row[CData.SYMBOL],
                            row[CData.BID],
                            row[CData.ASK],
                            row[CData.PVARDAY],
                            row[CData.CLOSE_DAY],
                            last,
                            row[CData.CASOS],
                            row[CData.PROB],
                            row[CData.O_NOW],
                            row[CData.H_NOW],
                            row[CData.VOL_NOW],
                            row[CData.CTRLDATA]
                        )
                    self.log.info(linea)
        
       
        self.log.info(f"=====================================================================================================================================")
        #self.t_Oper.ShowAllOrders()

