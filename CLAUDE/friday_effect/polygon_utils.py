import os
import pandas as pd
import time
import logging
import requests
from typing import List, Dict, Optional
from polygon import RESTClient
from dotenv import load_dotenv

# Configuración básica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('polygon_utils')

# Cargar variables de entorno (para API_KEY)
load_dotenv()

# Configuración por defecto - pueden ser sobrescritas cuando se llama a las funciones
DAYS_BEFORE_EVENT = 60  # Días predeterminados para buscar datos históricos

def fetch_ohlcv_polygon(ticker: str, days: int = DAYS_BEFORE_EVENT, api_key: str = None, 
                      max_retries: int = 3, retry_delay: int = 10, api_delay: int = 12) -> Optional[pd.DataFrame]:
    """
    Descarga los datos OHLCV diarios de un ticker desde Polygon.io usando el cliente REST oficial.
    """
    if api_key is None:
        api_key = os.getenv('POLYGON_API_KEY')
    
    if not api_key:
        raise ValueError("No se proporcionó API_KEY y no está configurada en las variables de entorno")
    
    for attempt in range(max_retries):
        try:
            client = RESTClient(api_key=api_key)
            
            # Calcular fechas de inicio y fin
            end_date = time.strftime('%Y-%m-%d')
            start_date = time.strftime('%Y-%m-%d', time.localtime(time.time() - days * 86400))
            
            logger.info(f"Obteniendo datos para {ticker} desde {start_date} hasta {end_date} (Intento {attempt + 1}/{max_retries})")
            
            # Obtener los datos OHLC
            aggs = []
            for agg in client.list_aggs(
                ticker=ticker,
                multiplier=1,
                timespan='day',
                from_=start_date,
                to=end_date,
                limit=days
            ):
                aggs.append(agg)
            
            if not aggs:
                logger.warning(f"No se encontraron datos para {ticker}")
                return None
                
            # Convertir a DataFrame
            df = pd.DataFrame([{
                'timestamp': pd.Timestamp(agg.timestamp, unit='ms'),
                'open': agg.open,
                'high': agg.high,
                'low': agg.low,
                'close': agg.close,
                'volume': agg.volume
            } for agg in aggs])
            
            # Añadir columna de fecha en formato YYYY-MM-DD para facilitar su uso
            df['date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
            
            # Ordenar por fecha
            df = df.sort_values('timestamp')
            
            # Esperar antes de la próxima llamada API
            time.sleep(api_delay)
            
            return df
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Error al obtener datos de Polygon.io para {ticker}: {str(e)}")
                return None
            else:
                logger.warning(f"Error en intento {attempt + 1}/{max_retries} para {ticker}: {str(e)}")
                logger.info(f"Esperando {retry_delay} segundos antes del siguiente intento...")
                time.sleep(retry_delay)

def filter_valid_polygon_tickers(tickers: List[str], api_key: str = None) -> List[str]:
    """Filtra y retorna solo los tickers que existen en Polygon.io (NASDAQ)."""
    if api_key is None:
        api_key = os.getenv('POLYGON_API_KEY')
    
    if not api_key:
        raise ValueError("No se proporcionó API_KEY y no está configurada en las variables de entorno")
    
    valid_tickers = set()
    url = f"https://api.polygon.io/v3/reference/tickers"
    params = {
        'market': 'stocks',
        'exchange': 'NASDAQ',
        'active': 'true',
        'limit': 1000,
        'apiKey': api_key
    }
    
    try:
        logger.info("Consultando tickers válidos en Polygon.io")
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'results' in data:
            valid_tickers = set([item['ticker'] for item in data['results']])
            logger.info(f"Se encontraron {len(valid_tickers)} tickers válidos en Polygon")
    except Exception as e:
        logger.error(f"Error consultando tickers válidos en Polygon: {e}")
        return []
    
    filtered = [t for t in tickers if t in valid_tickers]
    not_found = [t for t in tickers if t not in valid_tickers]
    
    if not_found:
        logger.warning(f"Tickers no encontrados en Polygon y serán omitidos: {not_found}")
    
    logger.info(f"Tickers válidos a procesar: {filtered}")
    return filtered

def batch_download_polygon(tickers: List[str], days: int = DAYS_BEFORE_EVENT, 
                         batch_size: int = 5, wait_seconds: int = 60, 
                         api_key: str = None) -> Dict[str, pd.DataFrame]:
    """Descarga datos OHLCV de Polygon para los tickers en lotes."""
    if api_key is None:
        api_key = os.getenv('POLYGON_API_KEY')
    
    # Filtrar tickers válidos primero
    valid_tickers = filter_valid_polygon_tickers(tickers, api_key)
    
    if not valid_tickers:
        logger.warning("No se encontraron tickers válidos para descargar")
        return {}
    
    all_data = {}
    
    for i in range(0, len(valid_tickers), batch_size):
        batch = valid_tickers[i:i+batch_size]
        logger.info(f"Descargando batch {i//batch_size + 1}/{(len(valid_tickers)-1)//batch_size + 1}: {batch}")
        
        for ticker in batch:
            df = fetch_ohlcv_polygon(ticker, days, api_key)
            if df is not None:
                all_data[ticker] = df
                logger.info(f"Datos descargados para {ticker}: {len(df)} registros")
            else:
                logger.warning(f"No se pudieron obtener datos para {ticker}")
            
            # Pequeño delay entre tickers para evitar rate limit
            time.sleep(1.5)
        
        if i + batch_size < len(valid_tickers):
            logger.info(f"Esperando {wait_seconds} segundos antes del próximo batch...")
            time.sleep(wait_seconds)
    
    return all_data
