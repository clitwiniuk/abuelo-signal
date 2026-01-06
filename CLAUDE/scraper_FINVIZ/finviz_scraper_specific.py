import logging
import requests
import pandas as pd
import sqlite3
import os
import time
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# URLs y configuración
FINVIZ_HOME_URL = 'https://finviz.com'
FINVIZ_LOGIN_URL = 'https://finviz.com/login.ashx'
FINVIZ_EMAIL = os.getenv('FINVIZ_EMAIL')
FINVIZ_PASSWORD = os.getenv('FINVIZ_PASSWORD')
DB_PATH = os.getenv('DB_PATH', 'tickers.db')

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("scraper_specific.log"),
        logging.StreamHandler()
    ]
)

def create_db_tables():
    """
    Crea las tablas necesarias en la base de datos si no existen
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Crear tabla para Top Gainers con clave compuesta (date, ticker)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS top_gainers (
            date DATE NOT NULL,
            ticker TEXT NOT NULL,
            last_price REAL,
            change_percent REAL,
            volume TEXT,
            signal TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, ticker)
        )
        ''')
        
        # Crear tabla para Top Losers con clave compuesta (date, ticker)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS top_losers (
            date DATE NOT NULL,
            ticker TEXT NOT NULL,
            last_price REAL,
            change_percent REAL,
            volume TEXT,
            signal TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, ticker)
        )
        ''')
        
        # Crear índices para búsquedas por ticker
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gainers_ticker ON top_gainers(ticker)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_losers_ticker ON top_losers(ticker)')
        
        # Crear índices para búsquedas por fecha
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gainers_date ON top_gainers(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_losers_date ON top_losers(date)')
        
        conn.commit()
        conn.close()
        logging.info("Tablas de base de datos creadas o verificadas correctamente")
        
    except Exception as e:
        logging.error(f"Error al crear tablas en la base de datos: {e}")
        raise  # Relanzar la excepción para manejo externo

def login_to_finviz():
    """
    Inicia sesión en Finviz utilizando las credenciales del archivo .env
    
    Returns:
        requests.Session: Sesión con autenticación activa o None si falla
    """
    if not FINVIZ_EMAIL or not FINVIZ_PASSWORD:
        logging.warning("No se encontraron credenciales de Finviz en el archivo .env. Usando acceso sin autenticación.")
        return None
    
    try:
        session = requests.Session()
        
        # Headers para simular un navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://finviz.com/',
            'Origin': 'https://finviz.com',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        session.headers.update(headers)
        
        # Primero obtener cookies y tokens CSRF visitando la página de login
        response = session.get(FINVIZ_LOGIN_URL)
        response.raise_for_status()
        
        # Preparar datos de login
        login_data = {
            'email': FINVIZ_EMAIL,
            'password': FINVIZ_PASSWORD,
            'remember': 'on'
        }
        
        # Realizar el login
        login_response = session.post(FINVIZ_LOGIN_URL, data=login_data, allow_redirects=True)
        login_response.raise_for_status()
        
        # Verificar si el login fue exitoso (comprobando si aparece el nombre de usuario o algún otro indicador)
        if 'Invalid email or password' in login_response.text:
            logging.error("Login fallido: Email o contraseña incorrectos")
            return None
        
        # Esperar un momento para que se establezca la sesión
        time.sleep(1)
        
        logging.info("Login exitoso en Finviz")
        return session
        
    except Exception as e:
        logging.error(f"Error durante el login en Finviz: {e}")
        return None

def scrape_finviz_specific_tables(session=None):
    """
    Extrae específicamente las tablas de Top Gainers y Top Losers de Finviz
    según el formato exacto proporcionado por el usuario.
    
    Returns:
        tuple: (gainers_data, losers_data) con los datos estructurados de ambas tablas
    """
    try:
        if session:
            # Si tenemos una sesión autenticada, la usamos
            response = session.get(FINVIZ_HOME_URL, timeout=15)
        else:
            # Si no hay sesión, hacemos una petición normal
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(FINVIZ_HOME_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Listas para almacenar los resultados
        gainers_data = []
        losers_data = []
        
        # Buscar todas las tablas en la página
        tables = soup.find_all('table')
        
        # Primero intentamos encontrar tablas con la estructura exacta que nos proporcionó el usuario
        for table in tables:
            # Verificar si es una tabla de señales (debe tener encabezados específicos)
            header_row = table.find('tr')
            if not header_row:
                continue
                
            headers = header_row.find_all(['th', 'td'])
            if not headers:
                continue
                
            header_texts = [h.get_text(strip=True).lower() for h in headers]
            
            # Verificar si es la tabla que buscamos (debe tener las columnas específicas)
            if any(col in ' '.join(header_texts) for col in ['ticker', 'last', 'change', 'volume', 'signal']):
                logging.info(f"Encontrada tabla con encabezados: {header_texts}")
                
                # Determinar índices de columnas
                ticker_idx = next((i for i, h in enumerate(header_texts) if 'ticker' in h), 0)
                last_idx = next((i for i, h in enumerate(header_texts) if 'last' in h), 1)
                change_idx = next((i for i, h in enumerate(header_texts) if 'change' in h), 2)
                volume_idx = next((i for i, h in enumerate(header_texts) if 'volume' in h), 3)
                signal_idx = next((i for i, h in enumerate(header_texts) if 'signal' in h), 4)
                
                # Procesar filas de datos (saltando encabezado)
                data_rows = table.find_all('tr')[1:]
                
                for row in data_rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) <= max(ticker_idx, last_idx, change_idx, volume_idx, signal_idx):
                        continue
                        
                    try:
                        # Extraer datos de cada columna
                        ticker = cells[ticker_idx].get_text(strip=True)
                        last_price = cells[last_idx].get_text(strip=True)
                        change_text = cells[change_idx].get_text(strip=True)
                        volume = cells[volume_idx].get_text(strip=True)
                        signal = cells[signal_idx].get_text(strip=True)
                        
                        # Verificar que el ticker sea válido (evitar filas vacías o con datos incorrectos)
                        if not ticker or ticker == 'Ticker' or len(ticker) > 10:
                            continue
                            
                        # Limpiar y formatear los datos
                        ticker = ticker.upper()
                        
                        try:
                            # Limpiar y convertir last_price a float
                            last_price = float(last_price.replace('$', '').replace(',', '').strip() or '0')
                            
                            # Limpiar y extraer el valor numérico de change_percent
                            change_percent = 0.0
                            if '%' in change_text:
                                change_percent = float(change_text.replace('%', '').replace('+', '').strip() or '0')
                                
                            # Limpiar volume
                            volume = volume.strip()
                            signal = signal.strip()
                            
                            # Crear diccionario con los datos limpios
                            ticker_data = {
                                'ticker': ticker,
                                'last_price': last_price,
                                'change_percent': change_percent,
                                'volume': volume,
                                'signal': signal
                            }
                            
                            # Determinar si es ganador o perdedor basado en el cambio porcentual
                            if change_percent > 0:
                                gainers_data.append(ticker_data)
                            else:
                                losers_data.append(ticker_data)
                                
                        except (ValueError, TypeError) as e:
                            logging.warning(f"Error al convertir datos para {ticker}: {e}")
                            continue
                            
                    except Exception as e:
                        logging.warning(f"Error al procesar fila: {e}")
                        continue
            
            # Procesar la tabla con la función específica si no se encontraron datos
            if not gainers_data and not losers_data:
                process_table_by_structure(table, gainers_data, losers_data)
        
        # Eliminar duplicados
        gainers_data = remove_duplicates_by_ticker(gainers_data)
        losers_data = remove_duplicates_by_ticker(losers_data)
        
        logging.info(f"Extraídos {len(gainers_data)} ganadores y {len(losers_data)} perdedores de Finviz")
        return gainers_data, losers_data
        
    except Exception as e:
        logging.error(f"Error al extraer datos de Finviz: {e}")
        return [], []

def process_table_by_structure(table, gainers_data, losers_data):
    """
    Procesa una tabla basada en la estructura específica de los ejemplos proporcionados
    
    Args:
        table: Objeto BeautifulSoup de la tabla
        gainers_data: Lista donde almacenar datos de ganadores
        losers_data: Lista donde almacenar datos de perdedores
    """
    try:
        rows = table.find_all('tr')
        if len(rows) < 2:  # Necesitamos al menos encabezado y una fila
            return
        
        # Extraer encabezados
        header_cells = rows[0].find_all(['th', 'td'])
        if not header_cells:
            return
            
        header_texts = [h.get_text(strip=True).lower() for h in header_cells]
        
        # Verificar si los encabezados coinciden con los ejemplos
        if not ('ticker' in ' '.join(header_texts) and 'last' in ' '.join(header_texts) and 'change' in ' '.join(header_texts)):
            return
        
        # Determinar índices de columnas
        ticker_idx = next((i for i, h in enumerate(header_texts) if 'ticker' in h), 0)
        last_idx = next((i for i, h in enumerate(header_texts) if 'last' in h or 'price' in h), 1)
        change_idx = next((i for i, h in enumerate(header_texts) if 'change' in h or '%' in h), 2)
        volume_idx = next((i for i, h in enumerate(header_texts) if 'volume' in h or 'vol' in h), 3)
        signal_idx = next((i for i, h in enumerate(header_texts) if 'signal' in h), -1)
        
        # Procesar filas de datos
        for row in rows[1:]:  # Saltar encabezado
            cells = row.find_all(['td', 'th'])
            if len(cells) <= max(ticker_idx, last_idx, change_idx):  # Necesitamos al menos ticker, precio y cambio
                continue
                
            try:
                # Extraer datos
                ticker = cells[ticker_idx].get_text(strip=True)
                
                # Verificar que sea un ticker válido
                if not ticker or len(ticker) > 5 or not ticker.replace('-', '').isalpha():
                    continue
                
                # Extraer otros datos
                last_price_text = cells[last_idx].get_text(strip=True) if last_idx < len(cells) else ''
                change_text = cells[change_idx].get_text(strip=True) if change_idx < len(cells) else ''
                volume_text = cells[volume_idx].get_text(strip=True) if volume_idx < len(cells) and volume_idx >= 0 else 'N/A'
                
                # Extraer señal si está disponible
                signal = cells[signal_idx].get_text(strip=True) if signal_idx >= 0 and signal_idx < len(cells) else ''
                
                # Si no hay señal explícita, determinar por el texto de la fila
                if not signal:
                    signal = 'Top Gainers' if 'gain' in row.get_text(strip=True).lower() else 'Top Losers'
                
                # Limpiar y convertir datos
                try:
                    last_price = float(last_price_text.replace('$', '').replace(',', '').strip() or '0')
                except (ValueError, TypeError):
                    last_price = 0.0
                
                try:
                    change_percent = 0.0
                    if change_text and '%' in change_text:
                        change_percent = float(change_text.replace('%', '').replace('+', '').strip() or '0')
                except (ValueError, TypeError):
                    change_percent = 0.0
                
                # Crear diccionario con los datos
                ticker_data = {
                    'ticker': ticker.upper().strip(),
                    'last_price': last_price,
                    'change_percent': change_percent,
                    'volume': volume_text,
                    'signal': signal
                }
                
                # Determinar si es gainer o loser basado en la señal
                if 'top gainers' in signal.lower() or change_percent > 0:
                    gainers_data.append(ticker_data)
                elif 'top losers' in signal.lower() or change_percent < 0:
                    losers_data.append(ticker_data)
                
            except Exception as e:
                        logging.debug(f"Error procesando fila: {e}")
                        continue
        
        # Si no encontramos las tablas con la estructura exacta, buscar tablas similares
        if not gainers_data and not losers_data:
            logging.info("No se encontraron tablas con la estructura exacta, buscando tablas similares...")
            
            # Buscar tablas con estructura similar a los ejemplos proporcionados
            for table in tables:
                # Verificar si la tabla tiene la estructura esperada
                rows = table.find_all('tr')
                if len(rows) < 2:  # Necesitamos al menos encabezado y una fila
                    continue
                
                # Verificar si es una tabla de ganadores o perdedores
                table_text = table.get_text(strip=True).lower()
                is_gainers_table = 'top gainers' in table_text or 'daily' in table_text and any(term in table_text for term in ['gain', 'up', 'rise'])
                is_losers_table = 'top losers' in table_text or 'daily' in table_text and any(term in table_text for term in ['lose', 'down', 'fall'])
                
                if not (is_gainers_table or is_losers_table):
                    continue
                
                # Procesar la tabla
                header_cells = rows[0].find_all(['th', 'td'])
                if not header_cells:
                    continue
                
                # Intentar identificar las columnas por su posición y contenido
                data_rows = rows[1:]  # Saltar encabezado
                
                for row in data_rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 3:  # Necesitamos al menos ticker, precio y cambio
                        continue
                    
                    try:
                        # Extraer datos (asumiendo estructura similar a los ejemplos)
                        ticker = cells[0].get_text(strip=True)
                        
                        # Verificar que sea un ticker válido
                        if not ticker or len(ticker) > 5 or not ticker.replace('-', '').isalpha():
                            continue
                        
                        # Extraer precio y cambio
                        last_price_text = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                        change_text = cells[2].get_text(strip=True) if len(cells) > 2 else ''
                        volume_text = cells[3].get_text(strip=True) if len(cells) > 3 else 'N/A'
                        
                        # Determinar señal basada en el contexto
                        signal = 'Top Gainers' if is_gainers_table else 'Top Losers'
                        
                        # Limpiar y convertir datos
                        try:
                            last_price = float(last_price_text.replace('$', '').replace(',', ''))
                        except (ValueError, TypeError):
                            last_price = None
                            
                        try:
                            change_percent = float(change_text.replace('%', '').replace('+', ''))
                        except (ValueError, TypeError):
                            change_percent = None
                        
                        # Crear diccionario con los datos
                        ticker_data = {
                            'ticker': ticker,
                            'last_price': last_price,
                            'change_percent': change_percent,
                            'volume': volume_text,
                            'signal': signal
                        }
                        
                        # Agregar a la lista correspondiente
                        if is_gainers_table:
                            gainers_data.append(ticker_data)
                        else:
                            losers_data.append(ticker_data)
                            
                    except Exception as e:
                        logging.debug(f"Error procesando fila: {e}")
                        continue
        
        # Método alternativo: buscar por estructura específica de las tablas proporcionadas como ejemplo
        if not gainers_data and not losers_data:
            logging.info("Buscando por estructura específica de las tablas de ejemplo...")
            
            # Buscar elementos que contengan texto similar a los encabezados de las tablas de ejemplo
            for element in soup.find_all(['div', 'table', 'tr']):
                element_text = element.get_text(strip=True).lower()
                
                # Verificar si contiene texto similar a los encabezados de las tablas de ejemplo
                if 'ticker' in element_text and 'last' in element_text and 'change' in element_text and 'volume' in element_text:
                    # Buscar la tabla cercana o usar esta si es una tabla
                    table = element if element.name == 'table' else element.find_next('table')
                    if not table:
                        continue
                    
                    # Procesar la tabla
                    process_table_by_structure(table, gainers_data, losers_data)
        
        # Eliminar duplicados y ordenar
        gainers_data = remove_duplicates_by_ticker(gainers_data)
        losers_data = remove_duplicates_by_ticker(losers_data)
        
        # Ordenar por cambio porcentual
        gainers_data.sort(key=lambda x: x['change_percent'] if x['change_percent'] is not None else -9999, reverse=True)
        losers_data.sort(key=lambda x: x['change_percent'] if x['change_percent'] is not None else 9999)
        
        logging.info(f"Extraídos {len(gainers_data)} ganadores y {len(losers_data)} perdedores de Finviz")
        return gainers_data, losers_data
    
    except Exception as e:
        logging.error(f"Error al scrapear tablas específicas de Finviz: {e}")
        return [], []

def process_table_by_structure(table, gainers_data, losers_data):
    """
    Procesa una tabla de Finviz para extraer datos de ganadores y perdedores
    
    Args:
        table: Objeto BeautifulSoup de la tabla
        gainers_data: Lista para almacenar datos de ganadores
        losers_data: Lista para almacenar datos de perdedores
    """
    try:
        # Verificar si la tabla tiene la estructura esperada
        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        if not all(h in ' '.join(headers) for h in ['ticker', 'last', 'change']):
            return
            
        # Procesar filas de datos
        for row in table.find_all('tr')[1:]:  # Saltar encabezado
            try:
                cells = row.find_all('td')
                if len(cells) < 4:  # Mínimo de columnas necesarias
                    continue
                    
                # Extraer datos básicos
                ticker = cells[0].get_text(strip=True)
                last_price_text = cells[1].get_text(strip=True)
                change_text = cells[2].get_text(strip=True)
                volume_text = cells[3].get_text(strip=True) if len(cells) > 3 else 'N/A'
                
                # Verificar que sea un ticker válido
                if not ticker or len(ticker) > 5 or not ticker.replace('-', '').isalpha():
                    continue
                
                # Limpiar y convertir datos numéricos
                try:
                    last_price = float(last_price_text.replace('$', '').replace(',', '').strip() or '0')
                except (ValueError, TypeError):
                    last_price = 0.0
                    
                try:
                    change_percent = 0.0
                    if change_text and '%' in change_text:
                        change_percent = float(change_text.replace('%', '').replace('+', '').strip() or '0')
                except (ValueError, TypeError):
                    change_percent = 0.0
                
                # Determinar si es ganador o perdedor
                is_gainer = change_percent > 0
                signal = 'Top Gainers' if is_gainer else 'Top Losers'
                
                # Crear diccionario con los datos
                ticker_data = {
                    'ticker': ticker.upper().strip(),
                    'last_price': last_price,
                    'change_percent': change_percent,
                    'volume': volume_text.strip(),
                    'signal': signal
                }
                
                # Agregar a la lista correspondiente
                if is_gainer:
                    gainers_data.append(ticker_data)
                else:
                    losers_data.append(ticker_data)
                    
            except Exception as e:
                logging.debug(f"Error procesando fila: {e}")
                continue
                
    except Exception as e:
        logging.error(f"Error procesando tabla: {e}")

def remove_duplicates_by_ticker(data_list):
    """
    Elimina duplicados de la lista manteniendo solo la primera aparición de cada ticker
    
    Args:
        data_list: Lista de diccionarios con datos de tickers
        
    Returns:
        list: Lista sin duplicados
    """
    seen_tickers = set()
    unique_data = []
    
    for item in data_list:
        ticker = item['ticker']
        if ticker not in seen_tickers:
            seen_tickers.add(ticker)
            unique_data.append(item)
    
    return unique_data

def save_to_csv(gainers_data, losers_data):
    """
    Guarda los datos extraídos en archivos CSV
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Convertir a DataFrames
    if gainers_data:
        gainers_df = pd.DataFrame(gainers_data)
        gainers_df.to_csv(f"finviz_gainers_{timestamp}.csv", index=False)
        logging.info(f"Guardados {len(gainers_data)} ganadores en finviz_gainers_{timestamp}.csv")
    
    if losers_data:
        losers_df = pd.DataFrame(losers_data)
        losers_df.to_csv(f"finviz_losers_{timestamp}.csv", index=False)
        logging.info(f"Guardados {len(losers_data)} perdedores en finviz_losers_{timestamp}.csv")

def save_to_db(gainers_data, losers_data):
    """
    Guarda los datos extraídos en la base de datos SQLite con fecha actual como clave
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Obtener la fecha actual en formato YYYY-MM-DD
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Guardar datos de ganadores con INSERT OR REPLACE para actualizar si ya existe
        if gainers_data:
            for gainer in gainers_data:
                try:
                    cursor.execute('''
                    INSERT OR REPLACE INTO top_gainers 
                    (date, ticker, last_price, change_percent, volume, signal, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        current_date,
                        gainer['ticker'],
                        gainer['last_price'],
                        gainer['change_percent'],
                        gainer['volume'],
                        gainer['signal'],
                        current_time
                    ))
                except Exception as e:
                    logging.error(f"Error al guardar ganador {gainer.get('ticker', '')}: {e}")
            
            logging.info(f"Guardados {len(gainers_data)} ganadores en la base de datos para la fecha {current_date}")
        
        # Guardar datos de perdedores con INSERT OR REPLACE para actualizar si ya existe
        if losers_data:
            for loser in losers_data:
                try:
                    cursor.execute('''
                    INSERT OR REPLACE INTO top_losers 
                    (date, ticker, last_price, change_percent, volume, signal, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        current_date,
                        loser['ticker'],
                        loser['last_price'],
                        loser['change_percent'],
                        loser['volume'],
                        loser['signal'],
                        current_time
                    ))
                except Exception as e:
                    logging.error(f"Error al guardar perdedor {loser.get('ticker', '')}: {e}")
                
            logging.info(f"Guardados {len(losers_data)} perdedores en la base de datos para la fecha {current_date}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logging.error(f"Error al guardar datos en la base de datos: {e}")
        raise  # Relanzar la excepción para manejo externo

def main():
    """
    Función principal
    """
    # Crear tablas en la base de datos si no existen
    create_db_tables()
    
    # Intentar login si hay credenciales disponibles
    session = login_to_finviz()
    if session:
        print("Usando sesión autenticada en Finviz para obtener datos completos")
    else:
        print("Usando acceso sin autenticación a Finviz (datos limitados)")
    
    # Extraer datos con la sesión (autenticada o no)
    gainers_data, losers_data = scrape_finviz_specific_tables(session)
    
    # Mostrar algunos resultados
    print(f"\n=== TOP GAINERS === (Total: {len(gainers_data)})")
    for i, gainer in enumerate(gainers_data[:10], 1):
        print(f"{i}. {gainer['ticker']} - {gainer['last_price']} - {gainer['change_percent']}% - {gainer['volume']} - {gainer['signal']}")
    
    print(f"\n=== TOP LOSERS === (Total: {len(losers_data)})")
    for i, loser in enumerate(losers_data[:10], 1):
        print(f"{i}. {loser['ticker']} - {loser['last_price']} - {loser['change_percent']}% - {loser['volume']} - {loser['signal']}")
    
    # Guardar resultados
    save_to_csv(gainers_data, losers_data)
    save_to_db(gainers_data, losers_data)
    
    print(f"\nDatos guardados en CSV y en la base de datos SQLite: {DB_PATH}")
    print(f"Total de tickers procesados: {len(gainers_data) + len(losers_data)}")
    
    # Mostrar información sobre la autenticación
    if not session:
        print("\nNOTA: Para obtener más tickers, configura tus credenciales de Finviz en el archivo .env")
        print("      Ejemplo: FINVIZ_EMAIL=tu_email@ejemplo.com\n      FINVIZ_PASSWORD=tu_contraseña")

if __name__ == '__main__':
    main()
