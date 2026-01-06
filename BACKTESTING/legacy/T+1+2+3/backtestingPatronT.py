import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import random
import requests
import logging
from typing import Optional, Dict, Any

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backtest_patron_t.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuración de la API de Polygon.io
POLYGON_API_KEY = 'Gn56b6ujVDqEQPEG28vKJRBPkRsVpn9o'  # Reemplaza con tu API key

class VolumePatternAnalyzer:
    def __init__(self):
        self.results = []
        
    def get_historical_data(self, ticker: str, n_velas: int, max_retries: int = 3, retry_delay: int = 15) -> Optional[pd.DataFrame]:
        """Obtiene datos históricos diarios usando la API de Polygon.io
        
        Args:
            ticker: Símbolo del ticker a descargar
            n_velas: Número de velas necesarias para el análisis
            max_retries: Número máximo de reintentos en caso de error
            retry_delay: Tiempo de espera entre reintentos en segundos
            
        Returns:
            DataFrame con los datos OHLCV o None si hay un error
        """
        # Calcular fechas necesarias
        days_needed = n_velas + 10  # Margen adicional
        start_date = (datetime.now() - timedelta(days=days_needed * 2)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        for attempt in range(max_retries):
            try:
                # Esperar un tiempo aleatorio entre solicitudes (respetar límite de 5/min)
                if attempt > 0:
                    wait_time = random.uniform(15, 30)  # Espera más larga entre reintentos
                    logger.info(f"Esperando {wait_time:.1f} segundos antes del reintento {attempt + 1}...")
                    time.sleep(wait_time)
                else:
                    # Pequeña espera aleatoria incluso en primer intento
                    time.sleep(random.uniform(1, 3))
                
                logger.info(f"Obteniendo datos para {ticker} (intento {attempt + 1}/{max_retries})")
                
                # Construir URL y parámetros para la API de Polygon
                url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
                params = {
                    'apiKey': POLYGON_API_KEY,
                    'limit': days_needed * 2  # Pedir el doble para asegurar que tenemos suficientes datos
                }
                
                # Realizar la petición
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'results' in data and len(data['results']) > 0:
                        # Convertir a DataFrame
                        df = pd.DataFrame(data['results'])
                        
                        # Convertir timestamp a datetime y establecer como índice
                        df['timestamp'] = pd.to_datetime(df['t'], unit='ms')
                        df = df[['timestamp', 'o', 'h', 'l', 'c', 'v']]
                        df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                        df.set_index('date', inplace=True)
                        
                        # Ordenar por fecha (más antigua a más reciente)
                        df = df.sort_index()
                        
                        # Verificar que tenemos suficientes datos
                        if len(df) < n_velas + 5:
                            logger.warning(f"Datos insuficientes para {ticker} (se necesitan al menos {n_velas+5} velas, se obtuvieron {len(df)})")
                            continue
                            
                        logger.info(f"Datos obtenidos para {ticker}: {len(df)} velas desde {df.index[0].date()} hasta {df.index[-1].date()}")
                        return df
                    else:
                        logger.warning(f"No se encontraron datos para {ticker}")
                        return None
                        
                elif response.status_code == 429:  # Too Many Requests
                    wait_time = min(60 + (attempt * 30), 300)  # Espera hasta 5 minutos
                    logger.warning(f"Límite de tasa alcanzado. Esperando {wait_time} segundos...")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    logger.warning(f"Error en la respuesta para {ticker}: {response.status_code} {response.reason}")
                    time.sleep(retry_delay)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error de conexión para {ticker}: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error(f"No se pudo obtener datos para {ticker} después de {max_retries} intentos")
                time.sleep(retry_delay)
                
            except Exception as e:
                logger.error(f"Error inesperado para {ticker}: {str(e)}", exc_info=True)
                if attempt == max_retries - 1:
                    logger.error(f"No se pudo obtener datos para {ticker} debido a un error inesperado")
                time.sleep(retry_delay)
        
        return None

    def analyze_pattern(self, row):
        """Analiza un solo patrón
        
        Args:
            row: Fila del DataFrame con los datos del patrón
            
        Returns:
            Diccionario con los resultados del análisis o None si hay un error
        """
        ticker = row['ticker']
        n_velas = row['n_velas']
        
        logger.info(f"Analizando patrón para {ticker} con {n_velas} velas...")
        
        # Obtener datos históricos
        data = self.get_historical_data(ticker, n_velas)
        if data is None or len(data) < n_velas + 5:
            logger.warning(f"No hay suficientes datos para analizar {ticker}")
            return None
            
        try:
            # Asegurarse de que los datos estén ordenados cronológicamente
            data = data.sort_index(ascending=True)
            
            # Verificar que tenemos suficientes datos después de la limpieza
            if len(data) < n_velas + 5:
                logger.warning(f"Datos insuficientes después de limpieza para {ticker}")
                return None
            
            # Identificar el día del patrón (T) - usamos los datos más recientes
            t_day = data.iloc[-n_velas-1]  # -1 porque Python usa indexado 0
            
            # Identificar días siguientes
            t1_day = data.iloc[-n_velas] if len(data) >= n_velas else None
            t2_day = data.iloc[-n_velas+1] if len(data) >= n_velas-1 else None
            t3_day = data.iloc[-n_velas+2] if len(data) >= n_velas-2 else None
            
            # Calcular volumen relativo (media móvil de 20 días)
            volume_ma = data['volume'].rolling(window=20, min_periods=1).mean()
            volume_ratio = t_day['volume'] / volume_ma.iloc[-n_velas-1] if volume_ma.iloc[-n_velas-1] > 0 else 1.0
            
            # Calcular métricas clave
            result = {
                'ticker': ticker,
                'n_velas': n_velas,
                'T_date': data.index[-n_velas-1].strftime('%Y-%m-%d'),
                'T_volume': t_day['volume'],
                'T_close': t_day['close'],
                'T_volume_ma': volume_ma.iloc[-n_velas-1],
                'volume_ratio': volume_ratio,
                
                # Rendimiento en T+1
                'T1_open': t1_day['open'] if t1_day is not None else None,
                'T1_close': t1_day['close'] if t1_day is not None else None,
                'T1_high': t1_day['high'] if t1_day is not None else None,
                'T1_low': t1_day['low'] if t1_day is not None else None,
                'T1_pct_change': (t1_day['close'] - t1_day['open']) / t1_day['open'] * 100 if t1_day is not None and t1_day['open'] > 0 else None,
                'T1_high_pct': (t1_day['high'] - t1_day['open']) / t1_day['open'] * 100 if t1_day is not None and t1_day['open'] > 0 else None,
                
                # Rendimiento en T+2
                'T2_open': t2_day['open'] if t2_day is not None else None,
                'T2_close': t2_day['close'] if t2_day is not None else None,
                'T2_pct_change': (t2_day['close'] - t2_day['open']) / t2_day['open'] * 100 if t2_day is not None and t2_day['open'] > 0 else None,
                
                # Rendimiento en T+3
                'T3_open': t3_day['open'] if t3_day is not None else None,
                'T3_close': t3_day['close'] if t3_day is not None else None,
                'T3_pct_change': (t3_day['close'] - t3_day['open']) / t3_day['open'] * 100 if t3_day is not None and t3_day['open'] > 0 else None,
            }
            
            # Verificar si hay valores nulos o inválidos
            if any(v is None for v in result.values()):
                logger.warning(f"Datos incompletos para {ticker}, algunos valores son None")
            
            logger.info(f"Análisis completado para {ticker}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error analizando {ticker}: {str(e)}", exc_info=True)
            return None

    def run_analysis(self, input_csv, output_csv, max_tickers=None):
        """Ejecuta el análisis completo
        
        Args:
            input_csv (str): Ruta al archivo CSV de entrada
            output_csv (str): Ruta donde guardar los resultados
            max_tickers (int, opcional): Número máximo de tickers a procesar (útil para pruebas)
        """
        start_time = time.time()
        logger.info("="*70)
        logger.info("INICIO DEL ANÁLISIS DE PATRONES T+1+2+3")
        logger.info("="*70)
        
        try:
            # Leer archivo de entrada con separador de punto y coma
            df = pd.read_csv(input_csv, sep=';')
            
            # Mostrar información del archivo cargado
            logger.info(f"Archivo cargado: {input_csv}")
            logger.info(f"Total de tickers encontrados: {len(df)}")
            logger.info(f"Columnas: {df.columns.tolist()}")
            logger.info("\nPrimeras 5 entradas:")
            logger.info(f"\n{df.head().to_string(index=False)}")
            
            # Verificar que las columnas esperadas existen
            if 'ticker' not in df.columns or 'bars' not in df.columns:
                logger.error("El archivo CSV debe contener las columnas 'ticker' y 'bars'")
                return
            
            # Renombrar columnas si es necesario
            df = df.rename(columns={'bars': 'n_velas'})
            
            # Limitar el número de tickers para pruebas
            if max_tickers and max_tickers > 0:
                logger.info(f"Procesando solo los primeros {max_tickers} tickers (modo prueba)")
                df = df.head(max_tickers)
            
            # Procesar cada patrón
            total = len(df)
            logger.info(f"\n{'='*70}")
            logger.info(f"INICIANDO ANÁLISIS DE {total} TICKERS")
            logger.info(f"{'='*70}")
            
            # Contador para el lote actual
            batch_counter = 0
            batch_size = 5  # Tamaño del lote
            
            for i, row in df.iterrows():
                ticker = row['ticker']
                logger.info(f"\n{'='*50}")
                logger.info(f"PROCESANDO {i+1}/{total}: {ticker}")
                logger.info(f"Número de velas a analizar: {row['n_velas']}")
                
                try:
                    # Analizar el patrón
                    result = self.analyze_pattern(row)
                    
                    if result:
                        self.results.append(result)
                        logger.info(f"[OK] Análisis completado para {ticker}")
                    else:
                        logger.warning(f"No se pudo analizar {ticker}")
                    
                    # Incrementar el contador del lote
                    batch_counter += 1
                    
                    # Si hemos procesado un lote completo, esperar 60 segundos
                    if batch_counter >= batch_size:
                        logger.info(f"\n{'='*50}")
                        logger.info(f"Lote de {batch_size} tickers completado. Esperando 60 segundos...")
                        logger.info(f"{'='*50}")
                        time.sleep(60)
                        batch_counter = 0  # Reiniciar contador de lote
                    else:
                        # Pequeña espera aleatoria entre tickers del mismo lote (1-3 segundos)
                        wait_time = random.uniform(1, 3)
                        logger.info(f"Esperando {wait_time:.1f} segundos antes del siguiente ticker...")
                        time.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"Error procesando {ticker}: {str(e)}", exc_info=True)
                    # Si hay un error, esperar un poco más antes de continuar
                    time.sleep(5)
                    continue
            
            # Guardar resultados si hay datos
            if self.results:
                results_df = pd.DataFrame(self.results)
                
                # Ordenar columnas para mejor legibilidad
                columns_order = [
                    'ticker', 'n_velas', 'T_date', 'T_volume', 'T_volume_ma', 'volume_ratio', 'T_close',
                    'T1_open', 'T1_high', 'T1_low', 'T1_close', 'T1_pct_change', 'T1_high_pct',
                    'T2_open', 'T2_close', 'T2_pct_change',
                    'T3_open', 'T3_close', 'T3_pct_change'
                ]
                
                # Mantener solo las columnas que existen
                columns_order = [col for col in columns_order if col in results_df.columns]
                results_df = results_df[columns_order]
                
                # Guardar a CSV
                results_df.to_csv(output_csv, index=False, float_format='%.4f')
                
                # Mostrar resumen
                logger.info("\n" + "="*70)
                logger.info("RESUMEN DEL ANÁLISIS")
                logger.info("="*70)
                logger.info(f"Tickers analizados: {len(self.results)} de {total}")
                logger.info(f"Archivo de resultados: {output_csv}")
                
                # Calcular métricas
                self.calculate_metrics(results_df)
                
                # Mostrar tiempo de ejecución
                elapsed_time = (time.time() - start_time) / 60  # en minutos
                logger.info(f"\nTiempo total de ejecución: {elapsed_time:.1f} minutos")
                
            else:
                logger.warning("No se pudo analizar ningún patrón")
                
        except Exception as e:
            logger.error(f"Error inesperado durante el análisis: {str(e)}", exc_info=True)
        
        logger.info("\n" + "="*70)
        logger.info("FIN DEL ANÁLISIS")
        logger.info("="*70)

    def calculate_metrics(self, df):
        """Calcula y muestra métricas de rendimiento detalladas
        
        Args:
            df: DataFrame con los resultados del análisis
        """
        if df.empty:
            logger.warning("No hay datos para calcular métricas")
            return
            
        try:
            # Crear un resumen de métricas
            metrics = {
                'TOTAL_ACCIONES_ANALIZADAS': len(df),
                'TASA_EXITO_T1': (df['T1_pct_change'] > 0).mean() * 100,
                'TASA_EXITO_T2': (df['T2_pct_change'] > 0).mean() * 100,
                'TASA_EXITO_T3': (df['T3_pct_change'] > 0).mean() * 100,
                'PROMEDIO_RETORNO_T1': df['T1_pct_change'].mean(),
                'PROMEDIO_RETORNO_T2': df['T2_pct_change'].mean(),
                'PROMEDIO_RETORNO_T3': df['T3_pct_change'].mean(),
                'MEDIANA_RETORNO_T1': df['T1_pct_change'].median(),
                'MEDIANA_RETORNO_T2': df['T2_pct_change'].median(),
                'MEDIANA_RETORNO_T3': df['T3_pct_change'].median(),
                'MAX_RETORNO_T1': df['T1_pct_change'].max(),
                'MAX_RETORNO_T2': df['T2_pct_change'].max(),
                'MAX_RETORNO_T3': df['T3_pct_change'].max(),
                'MIN_RETORNO_T1': df['T1_pct_change'].min(),
                'MIN_RETORNO_T2': df['T2_pct_change'].min(),
                'MIN_RETORNO_T3': df['T3_pct_change'].min(),
                'VOLUMEN_PROMEDIO': df['T_volume'].mean(),
                'RATIO_VOLUMEN_PROMEDIO': df['volume_ratio'].mean(),
            }
            
            # Calcular métricas adicionales
            df['retorno_acumulado'] = (1 + df['T1_pct_change']/100) * (1 + df['T2_pct_change']/100) * (1 + df['T3_pct_change']/100) - 1
            metrics['RETORNO_ACUMULADO_PROMEDIO'] = df['retorno_acumulado'].mean() * 100
            metrics['SHARPE_RATIO'] = (df['T1_pct_change'].mean() / (df['T1_pct_change'].std() + 1e-10)) * (252**0.5)
            
            # Calcular métricas por número de velas
            metrics_por_velas = {}
            for n_velas in df['n_velas'].unique():
                subset = df[df['n_velas'] == n_velas]
                if len(subset) > 0:
                    metrics_por_velas[f'VELAS_{n_velas}_CANTIDAD'] = len(subset)
                    metrics_por_velas[f'VELAS_{n_velas}_TASA_EXITO_T1'] = (subset['T1_pct_change'] > 0).mean() * 100
                    metrics_por_velas[f'VELAS_{n_velas}_RETORNO_PROMEDIO_T1'] = subset['T1_pct_change'].mean()
            
            # Mostrar métricas
            logger.info("\n" + "="*70)
            logger.info("MÉTRICAS DE RENDIMIENTO DETALLADAS")
            logger.info("="*70)
            
            # Métricas generales
            logger.info("\nMÉTRICAS GENERALES:")
            logger.info("-"*50)
            for metric, value in metrics.items():
                if 'TASA' in metric or 'EXITO' in metric or 'SHARPE' in metric or 'RATIO' in metric.upper():
                    logger.info(f"{metric}: {value:.2f}%" if '%' in metric else f"{metric}: {value:.2f}")
                elif 'VOLUMEN' in metric:
                    logger.info(f"{metric}: {value:,.2f}")
                elif 'RETORNO' in metric or 'PROMEDIO' in metric or 'MEDIANA' in metric or 'MAX' in metric or 'MIN' in metric:
                    logger.info(f"{metric}: {value:.2f}%")
                else:
                    logger.info(f"{metric}: {value}")
            
            # Métricas por número de velas
            if metrics_por_velas:
                logger.info("\nMÉTRICAS POR NÚMERO DE VELAS:")
                logger.info("-"*50)
                for metric, value in metrics_por_velas.items():
                    if 'CANTIDAD' in metric:
                        logger.info(f"{metric}: {int(value)} acciones")
                    elif 'TASA' in metric or 'EXITO' in metric:
                        logger.info(f"{metric}: {value:.2f}%")
                    else:
                        logger.info(f"{metric}: {value:.2f}%")
            
            # Mejores y peores rendimientos
            for day in [1, 2, 3]:
                col = f'T{day}_pct_change'
                if col in df.columns:
                    logger.info(f"\nTOP 5 MEJORES RENDIMIENTOS T+{day}:")
                    logger.info("-"*50)
                    top5 = df.nlargest(5, col)[['ticker', 'T_date', col, 'volume_ratio']]
                    top5[col] = top5[col].round(2).astype(str) + '%'
                    top5['volume_ratio'] = top5['volume_ratio'].round(2)
                    logger.info("\n" + top5.to_string(index=False))
                    
                    logger.info(f"\nTOP 5 PEORES RENDIMIENTOS T+{day}:")
                    logger.info("-"*50)
                    bottom5 = df.nsmallest(5, col)[['ticker', 'T_date', col, 'volume_ratio']]
                    bottom5[col] = bottom5[col].round(2).astype(str) + '%'
                    bottom5['volume_ratio'] = bottom5['volume_ratio'].round(2)
                    logger.info("\n" + bottom5.to_string(index=False))
            
            # Análisis de volumen
            if 'volume_ratio' in df.columns:
                logger.info("\nANÁLISIS DE VOLUMEN:")
                logger.info("-"*50)
                vol_bins = pd.cut(df['volume_ratio'], 
                                bins=[0, 1, 1.5, 2, 3, float('inf')],
                                labels=['<1x', '1-1.5x', '1.5-2x', '2-3x', '>3x'])
                vol_stats = df.groupby(vol_bins)['T1_pct_change'].agg(['count', 'mean', 'median', 'std'])
                logger.info("\nRendimiento T+1 por ratio de volumen:")
                logger.info("\n" + vol_stats.to_string())
            
        except Exception as e:
            logger.error(f"Error al calcular métricas: {str(e)}", exc_info=True)

# Uso del código
if __name__ == "__main__":
    # Configuración
    INPUT_CSV = 'screener_completo.csv'
    OUTPUT_CSV = 'resultados_analisis.csv'
    MAX_TICKERS = None  # Procesar todos los tickers por defecto
    
    print("\n" + "="*70)
    print("INICIANDO BACKTEST DE PATRÓN T+1+2+3")
    print("="*70)
    print(f"Archivo de entrada: {INPUT_CSV}")
    print(f"Archivo de salida: {OUTPUT_CSV}")
    print(f"Máximo de tickers a procesar: {MAX_TICKERS if MAX_TICKERS else 'Todos'}")
    
    analyzer = VolumePatternAnalyzer()
    
    # Ejecutar análisis
    analyzer.run_analysis(
        input_csv=INPUT_CSV,
        output_csv=OUTPUT_CSV,
        max_tickers=MAX_TICKERS
    )
    
    print("\n" + "="*70)
    print("ANÁLISIS COMPLETADO")
    print("="*70)