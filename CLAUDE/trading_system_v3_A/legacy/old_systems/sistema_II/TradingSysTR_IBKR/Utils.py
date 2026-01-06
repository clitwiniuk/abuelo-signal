
from datetime import datetime, timedelta,timezone
import yaml
import os
from pathlib import Path
import pytz
from enum import Enum
from dataclasses import dataclass,fields
from typing import Any, Dict, Optional,List,Literal
import logging
from logging.handlers import RotatingFileHandler
import os

class Action(str, Enum):
    
    BUY     = "BUY"
    SELL    = "SELL"
 

#########################################################################################################################
# logger_config.py


class ContextLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        task_name = f"{self.extra['task_name']:<5}"  # izda 5 caracteres
        return f"[{task_name}] {msg}", kwargs



##################################################################
# Logger base global (único para todo el sistema)
_base_logger = logging.getLogger("SystemLogger")
_base_logger.setLevel(logging.DEBUG)
##################################################################



class DailySizeRotatingFileHandler(logging.Handler):
    def __init__(self, base_name='System', max_bytes=10 * 1024 * 1024, encoding='utf-8'):
        super().__init__()
        self.base_name = base_name
        self.max_bytes = max_bytes
        self.encoding = encoding
        self.date_str = self._current_date_str()
        self.file_index = 0
        self.stream = None
        self._open_new_file()

    def _current_date_str(self):
        return datetime.now().strftime('%Y%m%d')

    def _build_filename(self):
        return f'{self.base_name}{self.date_str}-{self.file_index}.log'

    def _open_new_file(self):
        if self.stream:
            self.stream.close()

        while True:
            filename = self._build_filename()
            if not os.path.exists(filename) or os.path.getsize(filename) < self.max_bytes:
                break
            self.file_index += 1

        self.stream = open(filename, 'a', encoding=self.encoding)

    def emit(self, record):
        current_date = self._current_date_str()
        if current_date != self.date_str:
            # Cambiar de día: reiniciar index
            self.date_str = current_date
            self.file_index = 0
            self._open_new_file()

        if self.stream.tell() >= self.max_bytes:
            self.file_index += 1
            self._open_new_file()

        msg = self.format(record)
        self.stream.write(msg + '\n')
        self.stream.flush()

    def close(self):
        if self.stream:
            self.stream.close()
        super().close()


##################################################################

class FixedWidthFormatter(logging.Formatter):
    def format(self, record):
        # Formatos de ancho fijo
        record.levelname = f"{record.levelname:^7}"   # <7 caracteres, alineado a la izquierda ^ para centrar
        record.asctime = self.formatTime(record, self.datefmt)
        return super().format(record)
##################################################################

def setup_logging_system(max_bytes=10 * 1024 * 1024):

    if not _base_logger.hasHandlers():
        
        """
        formatter = logging.Formatter(
            '[%(asctime)s][%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        """
        formatter = FixedWidthFormatter(
            '[%(asctime)s][%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
)
        # Handler consola
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        _base_logger.addHandler(ch)

        # Handler archivo
        #fh = logging.FileHandler('System.log', mode='a', encoding='utf-8')
        #fh.setFormatter(formatter)
        #_base_logger.addHandler(fh)


        # Archivo con rotación diaria y por tamaño
        dh = DailySizeRotatingFileHandler(max_bytes=max_bytes)
        dh.setFormatter(formatter)
        _base_logger.addHandler(dh)

##################################################################
#Función para obtener el logger adaptado
def get_logger(task_name: str) -> ContextLogger:
    return ContextLogger(_base_logger, {'task_name': task_name})

#########################################################################################################################

columnas_hist =[  "date",  "open",  "high",   "low",  "close",   "volume",  "average",  "barCount"]


@dataclass (frozen=True)
class OneBar:
    symbol:str
    date:datetime
    open:float
    high:float
    low:float
    close:float
    volume:int
    avg:        Optional[float]=None
    barCount:   Optional[float]=None


@dataclass (frozen=True)
class ColumnsData:
    SYMBOL:str      = "Symbol"
    BID:str         = "Bid"
    ASK:str         = "Ask"
    CAP:str         = "Cap"
    PVARDAY:str     = "PVarDay"
    CLOSE_DAY:str   = "CloseDay"
    HDAY:str        = "HDay"
    H1MIN:str       = "H1Min"
    LASTIME:datetime= "LastTime"

    O_NOW:str       = "OpenNow"
    H_NOW:str       = "HighNow"
    L_NOW:str       = "LowNow"
    VOL_NOW:str     = "VolNow"
   
    PROB:str        = "Prob"
    CASOS:str       = "Casos"
    CTRLDATA:str    = "CtrlData"

    def get_columns_value(self):
        return [getattr(self, field.name) for field in fields(self)]
    
    def get_column_names(self):
        return [field.name for field in fields(self)]


CData = ColumnsData()
#print (f" NOMBRE DATA CLASS {CData.get_column_names()}")
#print (f" VALUES DATA CLASS {CData.get_columns_value()}")
#########################################################################################################################

def load_config():
    # Ruta absoluta al archivo YAML (independiente del directorio de trabajo)
    #config_path = Path(__file__).parent.parent / "config" / "Settings.yml"
    config_path = 'Settings.yml'
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)


def set_time_zone():
    try:
        if(cfSys['zoneTime']=="UTC"):
            return pytz.UTC
        else:
            return pytz.timezone(cfSys['zoneTime'])
    except:
        print ("Error Timezone")
        return pytz.UTC
    



# Carga la configuración al importar el módulo
cfSys       = load_config()
timeZone    = set_time_zone()    


