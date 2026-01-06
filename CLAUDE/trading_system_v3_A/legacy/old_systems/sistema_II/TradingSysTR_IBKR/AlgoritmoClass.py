

import  pandas as pd
from    datetime import *
from    Utils import *
from    Operation import *
from    Indicators import *

class CAlgo:
    def __init__(self, 
                    id: str,
                    table_Scan:pd.DataFrame,
                    bloq_Scan,

                    table_Operation:Operation,
                    bloq_Operation,
     ):
        self.id = id
        self.nombre = "BASE"
        self.t_Scan     = table_Scan
        self.lock_Scan = bloq_Scan

        self.t_Oper= table_Operation
        self.lock_Oper = bloq_Operation



    def Entrada(self):
        print ("ERROR")
        return False

################################################################################################################################################################################
#                                                                                                                                                                              #                                                                                                                                                              
#                                                                       ALGORITMO 00                                                                                           #                                                                                                                                                              
#                                                                                                                                                                              #                                                                                                                                                              
################################################################################################################################################################################                                                                                                                                                                              #                                                                                                                                                              


#Caso 1: Cálculo directo sin estado (batch para múltiples símbolos)
#    ema_def = IndicatorFactory.create(id="EMA", bars=20, source="hlcc", name="EMA20")
#    resultado = ema_def.run(df, datos_salida=10)


#Caso 2: Instancia con memoria para flujo en tiempo rea
#   ema_def = IndicatorFactory.create(id="EMA", bars=20, source="close", name="EMA20")
#   ema_live = IndicatorInstance(ema_def, symbol="AAPL")
#   valor_actual = ema_live.calculate(df_actualizado, datos_salida=1)



class Algo00(CAlgo):
    def __init__(self, table_Scan, bloq_Scan, table_Operation, bloq_Operation):
        super().__init__("A00", table_Scan, bloq_Scan, table_Operation, bloq_Operation)
        self.nombre = "A00"        
        self.log =  get_logger(self.nombre)

       


        # ✅ Definición única sin estado
        self.smaVol = IndicatorFactory.create(id=TipoInd.SMA, bars=3, source="volume", name="SMA3")
        self.Gan    = IndicatorFactory.create(id=TipoInd.GAN, bars=3, source="close", name="GAN3")    

        self.Stoch  = IndicatorFactory.create(id=TipoInd.STOCH, bars=14,SD=3, source="close", name="STOCH")
        
    def Entrada(self,symbol):
        #df_resultado = self.ema_def.run(df_msft, datos_salida=20)
        self.log.info(f"checking entrada ALGORITMO 00 {symbol}")

        mask = (self.t_Scan[CData.SYMBOL] == symbol)

        ind_filtrados = self.t_Scan.index[mask]
        df_entry=pd.DataFrame
        if not ind_filtrados.empty:
            idx = ind_filtrados[0]
            df_entry    = self.t_Scan.at[idx, CData.HDAY] #el data frame completo del index=idx


       
        SK, SD  = self.Stoch.run(df_entry, datos_salida=5)
       
        
        #df_resultado = self.Gan.run(df_entry, datos_salida=15)
        #self.log.info(f" resultado INDICADOR {symbol} SK {SK}")
        #self.log.info(f" resultado INDICADOR {symbol} SD {SD}")
       
        if SK.iloc[-1] >80 :
            return True
        
        
        return False

    


