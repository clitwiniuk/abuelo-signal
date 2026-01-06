import logging
import requests
import pandas as pd
import os
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
CSV_PATH = os.getenv('CSV_PATH', 'finviz_data_visual.csv')

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("finviz_scraper.log"),
        logging.StreamHandler()
    ]
)

def initialize_csv():
    """Inicializa el archivo CSV con los encabezados correctos"""
    if not os.path.exists(CSV_PATH):
        df = pd.DataFrame(columns=[
            'date', 'ticker', 'price', 'change_percent',
            'volume', 'category', 'signal', 'timestamp'
        ])
        df.to_csv(CSV_PATH, index=False)
        logging.info(f"Archivo CSV creado en {CSV_PATH}")

def login_to_finviz():
    """Inicia sesión en Finviz y devuelve una sesión autenticada"""
    if not FINVIZ_EMAIL or not FINVIZ_PASSWORD:
        logging.warning("No hay credenciales de Finviz. Usando acceso público.")
        return None
    
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0'
        })
        
        session.get(FINVIZ_LOGIN_URL)
        login_data = {
            'email': FINVIZ_EMAIL,
            'password': FINVIZ_PASSWORD,
            'remember': 'on'
        }
        login_response = session.post(FINVIZ_LOGIN_URL, data=login_data, allow_redirects=True)
        
        if 'Invalid email or password' in login_response.text:
            logging.error("Login fallido: Credenciales incorrectas")
            return None
        
        logging.info("Login exitoso en Finviz")
        return session
        
    except Exception as e:
        logging.error(f"Error durante el login: {e}")
        return None

def clean_text(text):
    """Limpia el texto eliminando caracteres no deseados y espacios extras"""
    if not text:
        return ""
    return ' '.join(str(text).replace('\n', ' ').replace('\t', ' ').replace('\r', ' ').strip().split())

def extract_category(table):
    """Extrae la categoría de la tabla"""
    try:
        prev_sibling = table.find_previous_sibling()
        if not prev_sibling or not prev_sibling.get_text(strip=True):
            parent = table.find_parent()
            if parent:
                prev_sibling = parent.find_previous_sibling()
        if prev_sibling:
            category = clean_text(prev_sibling.get_text())
            if 'TickerLastChange' in category:
                category = category.split('TickerLastChange')[0].strip()
            return category if category else "General"
        return "General"
    except:
        return "General"

def scrape_finviz_tables(session=None):
    """Extrae y limpia las tablas preservando el orden visual de Finviz"""
    try:
        if session:
            response = session.get(FINVIZ_HOME_URL, timeout=15)
        else:
            response = requests.get(FINVIZ_HOME_URL, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        all_tables = soup.find_all(
            'table',
            {'class': lambda x: x and 'styled-table-new' in x and 'is-rounded' in x and 'is-condensed' in x}
        )

        if not all_tables:
            logging.warning("No se encontraron tablas con la clase 'styled-table-new'")
            return []

        # Dividir en dos columnas (izquierda y derecha)
        mid_index = len(all_tables) // 2
        left_tables = all_tables[:mid_index]
        right_tables = all_tables[mid_index:]

        def process_tables(tables):
            extracted = []
            for table in tables:
                category = extract_category(table)
                rows = table.find_all('tr')[1:]  # saltar encabezado
                for row in rows:
                    try:
                        cells = row.find_all('td')
                        if len(cells) < 5:
                            continue
                        ticker = clean_text(cells[0].get_text())
                        price = clean_text(cells[1].get_text())
                        change = clean_text(cells[2].get_text())
                        volume = clean_text(cells[3].get_text())
                        signal = clean_text(cells[5].get_text()) if len(cells) > 5 else category
                        
                        if not ticker or len(ticker) > 5 or not ticker.replace('-', '').isalpha():
                            continue
                        
                        try:
                            price_val = float(price.replace(',', '')) if price else None
                        except:
                            price_val = None
                        try:
                            change_pct = float(change.replace('%', '').replace('+', '')) if '%' in change else None
                        except:
                            change_pct = None
                        
                        # 🚫 Filtro: descartar si no hay ni precio ni cambio porcentual
                        if price_val is None and change_pct is None:
                            continue
                        
                        extracted.append({
                            'ticker': ticker.upper(),
                            'price': price_val,
                            'change_percent': change_pct,
                            'volume': volume,
                            'category': category,
                            'signal': signal
                        })
                    except Exception as e:
                        logging.warning(f"Error procesando fila: {e}")
                        continue
            return extracted

        # Orden visual: primero izquierda, luego derecha
        data = process_tables(left_tables) + process_tables(right_tables)
        logging.info(f"Se extrajeron {len(data)} registros en orden visual")
        return data

    except Exception as e:
        logging.error(f"Error al extraer datos: {e}")
        return []

def save_to_csv(data):
    """Guarda los datos sin alterar el orden visual"""
    if not data:
        logging.warning("No hay datos para guardar")
        return False
        
    today = datetime.now().strftime('%Y-%m-%d')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        for item in data:
            item['date'] = today
            item['timestamp'] = timestamp
        
        df_new = pd.DataFrame(data)
        df_new = df_new[['date', 'ticker', 'price', 'change_percent', 'volume', 'category', 'signal', 'timestamp']]
        
        # Guardar sin mezclar con registros anteriores (sobrescribir)
        df_new.to_csv(CSV_PATH, index=False, encoding='utf-8')
        logging.info(f"Guardados {len(data)} registros en {CSV_PATH}")
        return True
        
    except Exception as e:
        logging.error(f"Error al guardar datos en CSV: {e}")
        return False

def main():
    initialize_csv()
    session = login_to_finviz()
    data = scrape_finviz_tables(session)
    if data:
        print("\n=== Muestra de datos extraídos ===")
        print(pd.DataFrame(data[:10]).to_string(index=False))
        save_to_csv(data)
        print(f"\nTotal de registros procesados: {len(data)}")
        print(f"Datos guardados en: {CSV_PATH}")
    else:
        print("No se encontraron datos para guardar")

if __name__ == '__main__':
    main()
