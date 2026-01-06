import logging
import requests
import sqlite3
import os
import schedule
import time
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración
FINVIZ_HOME_URL = 'https://finviz.com'
FINVIZ_LOGIN_URL = 'https://finviz.com/login.ashx'
FINVIZ_EMAIL = os.getenv('FINVIZ_EMAIL')
FINVIZ_PASSWORD = os.getenv('FINVIZ_PASSWORD')
DB_PATH = os.getenv('DB_PATH', 'finviz_data.db')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("finviz_scraper.log"),
        logging.StreamHandler()
    ]
)

class FinvizDatabase:
    """Clase para manejar la base de datos SQLite"""
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None
        self._initialize_db()
    
    def _initialize_db(self):
        """Inicializa la base de datos con las tablas necesarias"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            cursor = self.conn.cursor()
            
            # Tabla para días
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS days (
                    day_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL
                )
            ''')
            
            # Tabla para eventos (horas de descarga)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day_id INTEGER NOT NULL,
                    event_time TEXT NOT NULL,
                    FOREIGN KEY (day_id) REFERENCES days (day_id),
                    UNIQUE(day_id, event_time)
                )
            ''')
            
            # Tabla para los datos de las acciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stocks (
                    stock_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    price REAL,
                    change_percent REAL,
                    volume TEXT,
                    category TEXT,
                    signal TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events (event_id)
                )
            ''')
            
            self.conn.commit()
            logging.info(f"Base de datos inicializada en {self.db_path}")
            
        except Exception as e:
            logging.error(f"Error al inicializar la base de datos: {e}")
            if self.conn:
                self.conn.rollback()
    
    def save_data(self, data):
        """Guarda los datos en la base de datos organizados por día y hora"""
        if not data:
            logging.warning("No hay datos para guardar")
            return False
        
        try:
            cursor = self.conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            current_time = datetime.now().strftime('%H:%M:%S')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Insertar el día si no existe
            cursor.execute('INSERT OR IGNORE INTO days (date) VALUES (?)', (today,))
            
            # Obtener el ID del día
            cursor.execute('SELECT day_id FROM days WHERE date = ?', (today,))
            day_id = cursor.fetchone()[0]
            
            # Insertar el evento (hora de descarga)
            cursor.execute(
                'INSERT OR IGNORE INTO events (day_id, event_time) VALUES (?, ?)',
                (day_id, current_time)
            )
            
            # Obtener el ID del evento
            cursor.execute(
                'SELECT event_id FROM events WHERE day_id = ? AND event_time = ?',
                (day_id, current_time)
            )
            event_id = cursor.fetchone()[0]
            
            # Insertar los datos de las acciones
            for item in data:
                cursor.execute('''
                    INSERT INTO stocks (
                        event_id, ticker, price, change_percent, 
                        volume, category, signal, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event_id,
                    item['ticker'].upper(),
                    item['price'],
                    item['change_percent'],
                    item['volume'],
                    item['category'],
                    item['signal'],
                    timestamp
                ))
            
            self.conn.commit()
            logging.info(f"Guardados {len(data)} registros en la base de datos")
            return True
            
        except Exception as e:
            logging.error(f"Error al guardar datos en la base de datos: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def close(self):
        """Cierra la conexión a la base de datos"""
        if self.conn:
            self.conn.close()
            logging.info("Conexión a la base de datos cerrada")

class FinvizScraper:
    """Clase para manejar el scraping de Finviz"""
    def __init__(self):
        self.session = None
        self.db = FinvizDatabase()
    
    def login(self):
        """Inicia sesión en Finviz y devuelve una sesión autenticada"""
        if not FINVIZ_EMAIL or not FINVIZ_PASSWORD:
            logging.warning("No hay credenciales de Finviz. Usando acceso público.")
            return None
        
        try:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0'
            })
            
            self.session.get(FINVIZ_LOGIN_URL)
            login_data = {
                'email': FINVIZ_EMAIL,
                'password': FINVIZ_PASSWORD,
                'remember': 'on'
            }
            login_response = self.session.post(FINVIZ_LOGIN_URL, data=login_data, allow_redirects=True)
            
            if 'Invalid email or password' in login_response.text:
                logging.error("Login fallido: Credenciales incorrectas")
                return None
            
            logging.info("Login exitoso en Finviz")
            return self.session
            
        except Exception as e:
            logging.error(f"Error durante el login: {e}")
            return None
    
    @staticmethod
    def clean_text(text):
        """Limpia el texto eliminando caracteres no deseados y espacios extras"""
        if not text:
            return ""
        return ' '.join(str(text).replace('\n', ' ').replace('\t', ' ').replace('\r', ' ').strip().split())
    
    @staticmethod
    def extract_category(table):
        """Extrae la categoría de la tabla"""
        try:
            prev_sibling = table.find_previous_sibling()
            if not prev_sibling or not prev_sibling.get_text(strip=True):
                parent = table.find_parent()
                if parent:
                    prev_sibling = parent.find_previous_sibling()
            if prev_sibling:
                category = FinvizScraper.clean_text(prev_sibling.get_text())
                if 'TickerLastChange' in category:
                    category = category.split('TickerLastChange')[0].strip()
                return category if category else "General"
            return "General"
        except:
            return "General"
    
    def scrape_tables(self):
        """Extrae y limpia las tablas preservando el orden visual de Finviz"""
        try:
            if self.session:
                response = self.session.get(FINVIZ_HOME_URL, timeout=15)
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
                    category = self.extract_category(table)
                    rows = table.find_all('tr')[1:]  # saltar encabezado
                    for row in rows:
                        try:
                            cells = row.find_all('td')
                            if len(cells) < 5:
                                continue
                            ticker = self.clean_text(cells[0].get_text())
                            price = self.clean_text(cells[1].get_text())
                            change = self.clean_text(cells[2].get_text())
                            volume = self.clean_text(cells[3].get_text())
                            signal = self.clean_text(cells[5].get_text()) if len(cells) > 5 else category
                            
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
                            
                            # Filtro: descartar si no hay ni precio ni cambio porcentual
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
    
    def run_scraping(self):
        """Ejecuta el scraping y guarda los datos"""
        if not self.session and (FINVIZ_EMAIL and FINVIZ_PASSWORD):
            self.login()
        
        data = self.scrape_tables()
        if data:
            self.db.save_data(data)
            logging.info("Datos guardados exitosamente")
        else:
            logging.warning("No se encontraron datos para guardar")
    
    def schedule_scraping(self):
        """Programa las ejecuciones automáticas"""
        # Horarios programados
        schedule.every().day.at("14:00").do(self.run_scraping).tag('daily_tasks')
        schedule.every().day.at("16:00").do(self.run_scraping).tag('daily_tasks')
        schedule.every().day.at("17:00").do(self.run_scraping).tag('daily_tasks')
        schedule.every().day.at("18:00").do(self.run_scraping).tag('daily_tasks')
        schedule.every().day.at("22:01").do(self.run_scraping).tag('daily_tasks')
        
        logging.info("Programador iniciado con los siguientes horarios:")
        for job in schedule.get_jobs('daily_tasks'):
            logging.info(f" - {job.at_time}")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Deteniendo el programador...")
        finally:
            self.db.close()

def main():
    scraper = FinvizScraper()
    
    # Ejecutar inmediatamente una vez al iniciar
    scraper.run_scraping()
    
    # Iniciar el programador para ejecuciones automáticas
    scraper.schedule_scraping()

if __name__ == '__main__':
    main()