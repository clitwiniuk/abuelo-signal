"""
Manejador de datos CSV mejorado con integración a Polygon.io
Optimizado para cuentas gratuitas con límites de rate limiting
"""

import pandas as pd
import numpy as np
import requests
import time
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import glob
from dataclasses import dataclass

@dataclass
class PolygonConfig:
    """Configuración para Polygon.io"""
    api_key: str
    base_url: str = "https://api.polygon.io"
    free_tier_limit: int = 5  # 5 calls per minute for free tier
    wait_time: int = 65       # 65 seconds wait between batches
    
class PolygonDownloader:
    """
    Descargador de datos desde Polygon.io optimizado para cuenta gratuita
    """
    
    def __init__(self, api_key: str):
        self.config = PolygonConfig(api_key=api_key)
        self.session = requests.Session()
        self.calls_made = 0
        self.last_batch_time = None
        
    def _check_rate_limit(self):
        """Verifica y respeta el límite de rate limiting"""
        if self.calls_made >= self.config.free_tier_limit:
            if self.last_batch_time:
                elapsed = time.time() - self.last_batch_time
                if elapsed < self.config.wait_time:
                    wait_time = self.config.wait_time - elapsed
                    print(f"⏳ Rate limit alcanzado. Esperando {wait_time:.0f}s...")
                    time.sleep(wait_time)
            
            self.calls_made = 0
            self.last_batch_time = time.time()
    
    def get_ticker_data(self, symbol: str, start_date: str, end_date: str, data_directory: str = "data/") -> pd.DataFrame:
        # Guardar referencia al directorio de datos
        self.data_directory = data_directory
        """
        Descarga datos de 1 minuto para un ticker específico
        """
        self._check_rate_limit()
        
        # URL para agregados de 1 minuto
        url = f"{self.config.base_url}/v2/aggs/ticker/{symbol}/range/1/minute/{start_date}/{end_date}"
        
        params = {
            'apikey': self.config.api_key,
            'adjusted': 'true'
        }
        
        max_retries = 3
        retry_count = 0
        retry_delay = 12  # segundos
        
        while retry_count < max_retries:
            try:
                print(f"📥 Descargando {symbol}... ", end="")
                
                response = self.session.get(url, params=params, timeout=30)
                self.calls_made += 1
                
                # Si recibimos error 429 (rate limit), esperamos y reintentamos
                if response.status_code == 429:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"⏳ Rate limit (429). Reintento {retry_count}/{max_retries} en {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Duplicar tiempo de espera en cada reintento
                        continue
                    else:
                        print(f"❌ Error 429 después de {max_retries} reintentos")
                        return pd.DataFrame()
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'results' in data and data['results']:
                        df = pd.DataFrame(data['results'])
                    
                        # Convertir timestamp Unix a datetime con timezone UTC
                        df['timestamp'] = pd.to_datetime(df['t'], unit='ms').dt.tz_localize('UTC')
                        
                        # Renombrar columnas según estándar
                        column_mapping = {
                            'o': 'open',
                            'h': 'high', 
                            'l': 'low',
                            'c': 'close',
                            'v': 'volume'
                        }
                        df = df.rename(columns=column_mapping)
                        
                        # Seleccionar solo columnas necesarias
                        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                        
                        # Filtrar solo horario de mercado (9:30-16:00 EST)
                        df = self._filter_market_hours(df)
                        
                        print(f"✅ {len(df)} registros")
                        
                        # Guardar a CSV
                        csv_path = f"{self.data_directory}/{symbol}.csv"
                        # Convertir timestamp a string ISO y exportar directamente
                        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S%z')
                        df.to_csv(csv_path, index=False)
                    
                        return df
                    else:
                        print("❌ Sin datos")
                        return pd.DataFrame()
                else:
                    print(f"❌ Error {response.status_code}")
                    return pd.DataFrame()
                
            except Exception as e:
                print(f"❌ Error: {str(e)[:40]}")
                return pd.DataFrame()
    
    def _filter_market_hours(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filtra datos para incluir solo horario de mercado regular
        """
        if df.empty:
            return df
        
        try:
            # Asegurarse que timestamp tenga timezone (si no tiene, asignar UTC)
            if df['timestamp'].dt.tz is None:
                df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
                
            # Convertir a ET timezone
            df['timestamp'] = df['timestamp'].dt.tz_convert('US/Eastern')
            
            # Filtrar horario de mercado (9:30-16:00 ET)
            market_hours = (
                (df['timestamp'].dt.time >= pd.Timestamp('09:30').time()) &
                (df['timestamp'].dt.time <= pd.Timestamp('16:00').time()) &
                (df['timestamp'].dt.weekday < 5)  # Solo días laborables
            )
            
            return df[market_hours].copy()
        except Exception as e:
            print(f"Error al filtrar por horario de mercado: {str(e)}")
            return df

class EnhancedCSVDataHandler:
    """
    Manejador de datos CSV mejorado con integración a Polygon.io
    """
    
    def __init__(self, data_directory: str = "data/", polygon_api_key: str = None):
        self.data_directory = data_directory
        self.polygon_api_key = polygon_api_key
        self.downloader = PolygonDownloader(polygon_api_key) if polygon_api_key else None
        
        # Crear directorio si no existe
        os.makedirs(data_directory, exist_ok=True)
        
        # Smallcaps recomendados para testing (alta volatilidad)
        self.recommended_smallcaps = [
'ACDC', 'ADGM', 'ADVM', 'AEHR', 'AEVA', 'AFRI', 'AGEN', 'AGRO', 'AIFF', 'AIRS', 'AISP', 'AKYA', 'ALGS', 'ALMS', 'ALT', 'ALXO', 'AMTX', 'ANAB', 'ANRO', 'ANVS', 'ARCT', 'ARQQ', 'ARTV', 'ASPI', 'ASST', 'ATRA', 'AVAV', 'AVBP', 'AVXL', 'BBNX', 'BBW', 'BCAX', 'BDMD', 'BDTX', 'BIRD', 'BIVI', 'BKKT', 'BLNK', 'BMEA', 'BODI', 'BOSC', 'BPT', 'BSGM', 'BURU', 'BYND', 'BYRN', 'CABO', 'CAMP', 'CAPR', 'CAR', 'CDTX', 'CELU', 'CENT', 'CING', 'CMPO', 'CRBP', 'CRDF', 'CRMT', 'CSIQ', 'CTEV', 'CTGO', 'CTRN', 'CURV', 'DBI', 'DDS', 'DFDV', 'DIN', 'DMRC', 'DNA', 'DNTH', 'DOGZ', 'ELVN', 'ENLT', 'ENTA', 'EPSM', 'ESTA', 'FAT', 'FBIO', 'FBRX', 'FCEL', 'FENC', 'FFAI', 'FLWS', 'FOA', 'FRGT', 'FTCI', 'FULC', 'FWRD', 'GALT', 'GCO', 'GENK', 'GHRS', 'GLSI', 'GLUE', 'GOLF', 'GOOS', 'GORV', 'GPUS', 'GRAL', 'GRND', 'GRPN', 'GUTS', 'HAFN', 'HBIO', 'HIFS', 'HPK', 'HUMA', 'IBRX', 'IBTA', 'IMNN', 'IMPP', 'INBX', 'INDO', 'INMB', 'INSG', 'INZY', 'IRBT', 'JACK', 'JOUT', 'JSPR', 'KALA', 'KIRK', 'KLXE', 'KPTI', 'KRRO', 'KRUS', 'KSCP', 'LAZR', 'LEDS', 'LENZ', 'LEU', 'LFVN', 'LITM', 'LOVE', 'LRMR', 'LTBR', 'LTRY', 'LUCK', 'LVWR', 'MAXN', 'MAZE', 'MBOT', 'MBX', 'MCRB', 'MDGL', 'MDWD', 'MED', 'MFI', 'MLTX', 'MODV', 'MTEN', 'MVO', 'MWYN', 'NBR', 'NEGG', 'NGNE', 'NNE', 'NPWR', 'NRXP', 'NUKK', 'NVCT', 'NVFY', 'OKUR', 'ONEW', 'OPFI', 'ORKA', 'OSRH', 'PDYN', 'PEPG', 'PGY', 'PHAT', 'PLAY', 'PLCE', 'PLSE', 'POWL', 'PROP', 'PSHG', 'QMCO', 'QUBT', 'QUIK', 'RANI', 'RAPP', 'RDW', 'RENT', 'RH', 'RKT', 'RNAC', 'ROLR', 'RRGB', 'SAVA', 'SCLX', 'SCVL', 'SEDG', 'SEPN', 'SERV', 'SEZL', 'SGMT', 'SION', 'SKLZ', 'SKYE', 'SLDB', 'SPCB', 'SPCE', 'SPHR', 'SPIR', 'SPRY', 'STOK', 'STRM', 'SVCO', 'TBCH', 'TBPH', 'TCX', 'TECX', 'TELO', 'TENX', 'TIL', 'TKNO', 'TLYS', 'TMDX', 'TNGX', 'TNXP', 'TPIC', 'TRAK', 'TRML', 'TRUP', 'TSAT', 'TSSI', 'TYRA', 'TZUP', 'UFG', 'UFPT', 'UHAL', 'UMAC', 'UP', 'VATE', 'VEL', 'VRCA', 'VTLE', 'VUZI', 'WBTN', 'WEST', 'WRAP', 'WRLD', 'WTI', 'XFOR', 'XTIA', 'ZBIO', 'ZENA', 'ZEO', 'ZYXI'
        ]
        
        # Columnas requeridas
        self.required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    def interactive_download_menu(self):
        """
        Menú interactivo para descargar datos desde Polygon.io
        """
        if not self.polygon_api_key:
            print("❌ No se configuró API key de Polygon.io")
            return
        
        print("🚀 DESCARGADOR DE DATOS POLYGON.IO")
        print("=" * 50)
        print("📊 Configuración óptima para estrategias:")
        print("   • Temporalidad: 1 minuto (recomendado)")  
        print("   • Período recomendado: 30-90 días (más para backtesting)")
        print("   • Horario: Solo sesión regular (9:30-16:00 EST)")
        print("   • Límite cuenta gratuita: 5 tickers/minuto")
        print("   • Límite histórico: ~2 años (verificar plan)")
        print("   • Para estrategias como Gap & Go, se recomiendan al menos 60 días")
        print()
        
        while True:
            print("OPCIONES:")
            print("1. 📥 Descargar tickers recomendados")
            print("2. 📝 Descargar tickers personalizados") 
            print("3. 📊 Ver tickers recomendados")
            print("4. 📁 Analizar archivos CSV existentes")
            print("5. ❌ Salir")
            
            choice = input("\n👉 Selecciona opción (1-5): ").strip()
            
            if choice == '1':
                self._download_recommended_tickers()
            elif choice == '2':
                self._download_custom_tickers()
            elif choice == '3':
                self._show_recommended_tickers()
            elif choice == '4':
                self._analyze_existing_files()
            elif choice == '5':
                break
            else:
                print("❌ Opción inválida")
            
            print()
    
    def _download_recommended_tickers(self):
        """Descarga tickers recomendados en lotes"""
        print("\n📥 DESCARGA DE TICKERS RECOMENDADOS")
        print("-" * 40)
        
        # Configurar fechas (90 días hacia atrás por defecto)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        date_str_start = start_date.strftime('%Y-%m-%d')
        date_str_end = end_date.strftime('%Y-%m-%d')
        
        # Preguntar por fechas personalizadas
        use_custom_dates = input("¿Usar fechas personalizadas? (s/n, default=n): ").strip().lower()
        if use_custom_dates == 's':
            date_str_start = input(f"Fecha de inicio (YYYY-MM-DD, default={date_str_start}): ") or date_str_start
            date_str_end = input(f"Fecha de fin (YYYY-MM-DD, default={date_str_end}): ") or date_str_end
            
            try:
                # Validar formato de fechas
                start_date = datetime.strptime(date_str_start, '%Y-%m-%d')
                end_date = datetime.strptime(date_str_end, '%Y-%m-%d')
                
                # Validar que la fecha de inicio sea anterior a la de fin
                if start_date >= end_date:
                    print("⚠️  La fecha de inicio debe ser anterior a la fecha de fin. Usando fechas por defecto.")
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=90)
                    date_str_start = start_date.strftime('%Y-%m-%d')
                    date_str_end = end_date.strftime('%Y-%m-%d')
                    
            except ValueError as e:
                print(f"⚠️  Error en el formato de fechas: {e}. Usando fechas por defecto.")
                end_date = datetime.now()
                start_date = end_date - timedelta(days=90)
                date_str_start = start_date.strftime('%Y-%m-%d')
                date_str_end = end_date.strftime('%Y-%m-%d')
        
        # Calcular días totales del período
        days = (datetime.strptime(date_str_end, '%Y-%m-%d') - datetime.strptime(date_str_start, '%Y-%m-%d')).days
        
        print(f"📅 Período: {date_str_start} a {date_str_end} ({days} días)")
        print(f"🎯 Tickers disponibles: {len(self.recommended_smallcaps)}")
        
        # Preguntar cantidad
        try:
            max_tickers = int(input(f"👉 ¿Cuántos tickers descargar? (máx {len(self.recommended_smallcaps)}): "))
            max_tickers = min(max(max_tickers, 1), len(self.recommended_smallcaps))  # Asegurar al menos 1
        except:
            max_tickers = 15
            
        # Advertencia para períodos largos
        if days > 30:
            print(f"\n⚠️  ADVERTENCIA: El período seleccionado es de {days} días.")
            print("   - Polygon tiene límites de datos históricos para cuentas gratuitas.")
            print("   - Para períodos largos, considera dividir la descarga en lotes.")
            if not input("¿Continuar? (s/n): ").lower().startswith('s'):
                return
        
        selected_tickers = self.recommended_smallcaps[:max_tickers]
        
        print(f"\n🔄 Descargando {len(selected_tickers)} tickers...")
        print(f"⚠️  Tiempo estimado: {len(selected_tickers) * 13 // 5} minutos")
        
        self._download_ticker_batch(selected_tickers, date_str_start, date_str_end)
    
    def _download_custom_tickers(self):
        """Descarga tickers personalizados"""
        print("\n📝 DESCARGA PERSONALIZADA")
        print("-" * 30)
        
        tickers_input = input("👉 Ingresa tickers separados por comas (ej: AAPL,MSFT,TSLA): ").strip()
        if not tickers_input:
            return
        
        tickers = [t.strip().upper() for t in tickers_input.split(',')]
        
        # Configurar fechas
        print("\n📅 Configuración de fechas")
        print("1. Usar días hacia atrás")
        print("2. Especificar rango de fechas")
        date_choice = input("👉 Seleccione opción (1-2, default=1): ").strip()
        
        end_date = datetime.now()
        
        if date_choice == '2':
            # Opción 2: Rango de fechas personalizado
            while True:
                try:
                    start_date_str = input(f"Fecha de inicio (YYYY-MM-DD, default={end_date.strftime('%Y-%m-%d')}): ").strip()
                    end_date_str = input(f"Fecha de fin (YYYY-MM-DD, default={end_date.strftime('%Y-%m-%d')}): ").strip()
                    
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else end_date - timedelta(days=90)
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else end_date
                    
                    if start_date >= end_date:
                        print("⚠️  La fecha de inicio debe ser anterior a la fecha de fin. Intente nuevamente.")
                        continue
                        
                    days_back = (end_date - start_date).days
                    break
                    
                except ValueError:
                    print("⚠️  Formato de fecha inválido. Use YYYY-MM-DD")
        else:
            # Opción 1: Días hacia atrás (comportamiento original)
            days_back = input("👉 Días hacia atrás (default 90, max 365): ").strip()
            try:
                days_back = min(int(days_back) if days_back else 90, 365)  # Límite de 1 año para cuentas gratuitas
                start_date = end_date - timedelta(days=days_back)
            except:
                days_back = 90
                start_date = end_date - timedelta(days=days_back)
        
        date_str_start = start_date.strftime('%Y-%m-%d')
        date_str_end = end_date.strftime('%Y-%m-%d')
        
        # Mostrar resumen
        print(f"\n📊 Resumen de descarga:")
        print(f"   • Período: {date_str_start} a {date_str_end} ({days_back} días)")
        print(f"   • Tickers: {len(tickers)}")
        print(f"   • Tiempo estimado: {len(tickers) * 13 // 5} minutos")
        
        print(f"\n📅 Período: {date_str_start} a {date_str_end}")
        print(f"🎯 Tickers: {', '.join(tickers)}")
        
        self._download_ticker_batch(tickers, date_str_start, date_str_end)
    
    def _download_ticker_batch(self, tickers: List[str], start_date: str, end_date: str):
        """Descarga lote de tickers respetando rate limits"""
        successful_downloads = 0
        total_tickers = len(tickers)
        
        print(f"\n🚀 Iniciando descarga de {total_tickers} tickers")
        print("=" * 50)
        
        for i, ticker in enumerate(tickers, 1):
            print(f"[{i:2}/{total_tickers}] ", end="")
            
            # Verificar si ya existe (sin sufijo _5m)
            filename = f"{self.data_directory}{ticker}.csv"
            if os.path.exists(filename):
                print(f"📁 {ticker} ya existe - omitiendo")
                continue
            
            # Descargar datos
            df = self.downloader.get_ticker_data(ticker, start_date, end_date)
            
            if not df.empty:
                # Guardar CSV
                df.to_csv(filename, index=False)
                successful_downloads += 1
                
                # Mostrar estadísticas
                total_hours = len(df) / 12  # 12 períodos de 5min = 1 hora
                print(f"   💾 Guardado: {total_hours:.1f}h de datos")
            
            # Pausa entre llamadas individuales
            if i < total_tickers:
                time.sleep(1)
        
        print(f"\n✅ DESCARGA COMPLETADA")
        print(f"   🎯 Exitosos: {successful_downloads}/{total_tickers}")
        print(f"   📁 Archivos en: {self.data_directory}")
    
    def _show_recommended_tickers(self):
        """Muestra lista de tickers recomendados"""
        print("\n📊 TICKERS SMALLCAP RECOMENDADOS")
        print("-" * 40)
        print("✨ Seleccionados por alta volatilidad y volumen")
        print()
        
        for i, ticker in enumerate(self.recommended_smallcaps, 1):
            print(f"{i:2}. {ticker}", end="  ")
            if i % 6 == 0:  # 6 por línea
                print()
        
        if len(self.recommended_smallcaps) % 6 != 0:
            print()
        
        print(f"\n📈 Total disponibles: {len(self.recommended_smallcaps)}")
    
    def _analyze_existing_files(self):
        """Analiza archivos CSV existentes"""
        csv_files = glob.glob(f"{self.data_directory}*.csv")
        
        if not csv_files:
            print("📁 No se encontraron archivos CSV")
            return
        
        print(f"\n📊 ANÁLISIS DE ARCHIVOS EXISTENTES")
        print("=" * 50)
        
        total_size = 0
        valid_files = 0
        
        for csv_file in csv_files:
            filename = os.path.basename(csv_file)
            ticker = filename.replace('.csv', '').replace('_5m', '')
            
            try:
                df = pd.read_csv(csv_file)
                file_size = os.path.getsize(csv_file) / 1024  # KB
                total_size += file_size
                
                if self._validate_csv_structure(df):
                    valid_files += 1
                    
                    # Estadísticas básicas
                    days_span = "N/A"
                    if 'timestamp' in df.columns:
                        try:
                            df['timestamp'] = pd.to_datetime(df['timestamp'])
                            days_span = (df['timestamp'].max() - df['timestamp'].min()).days
                        except:
                            pass
                    
                    hours_data = len(df) / 12  # Asumiendo 5min intervals
                    
                    print(f"✅ {ticker:6} | {len(df):5} registros | {hours_data:5.1f}h | {days_span:2} días | {file_size:5.1f}KB")
                else:
                    print(f"❌ {ticker:6} | Formato inválido")
                    
            except Exception as e:
                print(f"❌ {ticker:6} | Error: {str(e)[:30]}")
        
        print(f"\n📊 RESUMEN:")
        print(f"   📁 Archivos totales: {len(csv_files)}")
        print(f"   ✅ Archivos válidos: {valid_files}")
        print(f"   💾 Tamaño total: {total_size:.1f}KB")
        
        if valid_files >= 5:
            print(f"   🚀 ¡Listo para ejecutar backtest!")
        else:
            print(f"   ⚠️  Se recomiendan al menos 5 archivos válidos")
    
    def _validate_csv_structure(self, df: pd.DataFrame) -> bool:
        """Valida estructura básica del CSV"""
        if df.empty:
            return False
        
        # Verificar columnas mínimas
        required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        available_cols = [col.lower() for col in df.columns]
        
        has_all_columns = all(col in available_cols for col in required)
        has_enough_data = len(df) > 100
        
        return has_all_columns and has_enough_data
    
    def load_all_csv_data(self) -> Dict[str, pd.DataFrame]:
        """
        Carga todos los archivos CSV válidos del directorio
        """
        csv_files = glob.glob(f"{self.data_directory}*.csv")
        data_dict = {}
        
        print(f"📁 Cargando archivos CSV desde {self.data_directory}")
        print("-" * 50)
        
        for csv_file in csv_files:
            filename = os.path.basename(csv_file)
            ticker = filename.replace('.csv', '').replace('_5m', '')
            
            try:
                df = pd.read_csv(csv_file)
                
                if self._validate_csv_structure(df):
                    # Normalizar columnas
                    df.columns = df.columns.str.lower()
                    
                    # Procesar timestamp
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df = df.set_index('timestamp')
                    df = df.sort_index()
                    
                    # Renombrar para compatibilidad
                    df = df.rename(columns={
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low', 
                        'close': 'Close',
                        'volume': 'Volume'
                    })
                    
                    # Calcular returns
                    df['Returns'] = df['Close'].pct_change()
                    df = df.dropna()
                    
                    data_dict[ticker] = df
                    
                    hours_data = len(df) / 12
                    print(f"✅ {ticker:6} | {len(df):5} registros | {hours_data:5.1f}h")
                else:
                    print(f"❌ {ticker:6} | Formato inválido")
                    
            except Exception as e:
                print(f"❌ {ticker:6} | Error: {str(e)[:40]}")
        
        print(f"\n✅ Cargados {len(data_dict)} archivos válidos")
        return data_dict

def setup_polygon_integration():
    """
    Configuración inicial para integración con Polygon.io
    """
    print("🔧 CONFIGURACIÓN POLYGON.IO")
    print("=" * 30)
    print("📝 Para usar este sistema necesitas:")
    print("   1. Cuenta gratuita en polygon.io")
    print("   2. API Key desde tu dashboard")
    print("   3. Límites: 5 calls/minuto en cuenta gratuita")
    print()
    
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        api_key = input("👉 Ingresa tu Polygon.io API Key: ").strip()
    
    if not api_key:
        print("❌ API Key requerida")
        return None
    
    # Crear directorio de datos
    data_dir = "data/"
    os.makedirs(data_dir, exist_ok=True)
    
    # Guardar configuración
    config = {
        'polygon_api_key': api_key,
        'data_directory': data_dir,
        'setup_date': datetime.now().isoformat()
    }
    
    with open('polygon_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Configuración guardada en polygon_config.json")
    print(f"📁 Directorio de datos: {data_dir}")
    
    return EnhancedCSVDataHandler(data_dir, api_key)

def load_existing_config() -> Optional[EnhancedCSVDataHandler]:
    """
    Carga configuración existente si está disponible
    """
    # First try to get API key from environment
    api_key = os.getenv('POLYGON_API_KEY')
    
    if os.path.exists('polygon_config.json'):
        try:
            with open('polygon_config.json', 'r') as f:
                config = json.load(f)
            
            data_dir = config.get('data_directory', 'data/')
            
            # If no API key from environment, fall back to config file (legacy support)
            if not api_key:
                api_key = config.get('polygon_api_key')
            
            if api_key:
                return EnhancedCSVDataHandler(data_dir, api_key)
        except:
            pass
    
    return None

# Función principal de uso
def main():
    """
    Función principal del sistema de descarga
    """
    print("🚀 SISTEMA DE DESCARGA DE DATOS PARA WAVELETS")
    print("=" * 55)
    
    # Intentar cargar configuración existente
    handler = load_existing_config()
    
    if not handler:
        print("🔧 Primera vez - configuración requerida")
        handler = setup_polygon_integration()
    else:
        print("✅ Configuración cargada desde polygon_config.json")
    
    if handler:
        print()
        handler.interactive_download_menu()
    else:
        print("❌ No se pudo configurar el sistema")

if __name__ == "__main__":
    main()
