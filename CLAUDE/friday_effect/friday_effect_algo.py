import os
import pandas as pd
import numpy as np
import time
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import warnings
from dotenv import load_dotenv
from polygon import RESTClient

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()
warnings.filterwarnings('ignore')

# Configuración de la API de Polygon
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
if not POLYGON_API_KEY:
    raise ValueError("No se encontró la API key de Polygon.io. Asegúrate de tener un archivo .env con POLYGON_API_KEY=tu_api_key")

# Constantes para el control de tasa
MAX_REQUESTS_PER_MINUTE = 5
MAX_RETRIES = 3

class FridayEffectAlgorithm:
    def __init__(self, 
                 min_market_cap: float = 300e6,  # $300M
                 max_market_cap: float = 2e9,    # $2B
                 min_avg_volume: float = 500000, # 500K shares/day
                 min_price: float = 5.0,
                 min_beta: float = 1.5,
                 lookback_days: int = 252):      # 1 year for statistics
        
        self.min_market_cap = min_market_cap
        self.max_market_cap = max_market_cap
        self.min_avg_volume = min_avg_volume
        self.min_price = min_price
        self.min_beta = min_beta
        self.lookback_days = lookback_days
        
        # Control de tasa para la API
        self._request_times = []
        self._last_request_time = 0
        
        # Small caps universe (ejemplo - en producción usar un screener más amplio)
        self.universe = [
            'ROKU', 'PINS', 'DKNG', 'PLTR', 'FSLY', 'NET', 'SNOW',
            'CRWD', 'ZM', 'DOCU', 'PTON', 'CVNA', 'DASH', 'ABNB',
            'RBLX', 'U', 'PATH', 'OPEN', 'HOOD', 'AFRM', 'UPST',
            'SQ', 'PYPL', 'SHOP', 'TWLO', 'OKTA', 'MDB', 'DDOG'
        ]
        
    def _throttle(self):
        """
        Controla la tasa de peticiones a la API para evitar errores 429.
        Limita a MAX_REQUESTS_PER_MINUTE peticiones por minuto.
        """
        now = time.time()
        
        # Eliminar peticiones antiguas (más de 60 segundos)
        self._request_times = [t for t in self._request_times if now - t < 60]
        
        # Si ya hemos alcanzado el límite, esperar
        if len(self._request_times) >= MAX_REQUESTS_PER_MINUTE:
            oldest_request = self._request_times[0]
            time_to_wait = 60 - (now - oldest_request)
            if time_to_wait > 0:
                logger.warning(f"Límite de tasa alcanzado. Esperando {time_to_wait:.1f} segundos...")
                time.sleep(time_to_wait + 1)  # +1 segundo de margen
                now = time.time()
                # Actualizar lista después de esperar
                self._request_times = [t for t in self._request_times if now - t < 60]
        
        # Añadir tiempo de espera base con jitter para evitar sincronización
        base_delay = max(1.0, (60 / MAX_REQUESTS_PER_MINUTE) - 1)
        wait_time = base_delay * (0.8 + 0.4 * random.random())
        
        # Esperar si la última petición fue muy reciente
        if self._last_request_time > 0:
            elapsed = now - self._last_request_time
            if elapsed < wait_time:
                time.sleep(wait_time - elapsed)
        
        # Registrar esta petición
        self._last_request_time = time.time()
        self._request_times.append(self._last_request_time)
        
    def get_stock_data(self, symbol: str, period: str = "2y") -> Optional[pd.DataFrame]:
        """Obtener datos históricos del ticker usando Polygon.io con control de tasa"""
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                # Aplicar control de tasa antes de la petición
                self._throttle()
                
                # Calcular fechas basadas en el periodo solicitado
                end_date = datetime.now()
                if period.endswith('y'):
                    years = int(period[:-1])
                    start_date = end_date - timedelta(days=years*365)
                elif period.endswith('d'):
                    days = int(period[:-1])
                    start_date = end_date - timedelta(days=days)
                else:
                    # Valor por defecto: 2 años
                    start_date = end_date - timedelta(days=730)  # 2 años

                # Formatear fechas para la API
                start_date_str = start_date.strftime('%Y-%m-%d')
                end_date_str = end_date.strftime('%Y-%m-%d')

                logger.info(f"Descargando datos para {symbol} (intento {attempt + 1}/{MAX_RETRIES})")
                
                # Inicializar cliente de Polygon
                client = RESTClient(api_key=POLYGON_API_KEY)
                
                # Obtener datos
                resp = []
                for aggs in client.list_aggs(
                    ticker=symbol,
                    multiplier=1,
                    timespan='day',
                    from_=start_date_str,
                    to=end_date_str,
                    limit=50000
                ):
                    resp.append(aggs)
                
                if not resp:
                    logger.warning(f"No se encontraron datos para {symbol}")
                    return None
                    
                # Convertir a DataFrame
                data = pd.DataFrame([{
                    'Open': agg.open,
                    'High': agg.high,
                    'Low': agg.low,
                    'Close': agg.close,
                    'Volume': agg.volume,
                    'timestamp': pd.to_datetime(agg.timestamp, unit='ms')
                } for agg in resp])
                
                if data.empty:
                    logger.warning(f"DataFrame vacío para {symbol}")
                    return None
                    
                # Establecer timestamp como índice
                data.set_index('timestamp', inplace=True)
                data.sort_index(inplace=True)
                
                return data
                
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1} para {symbol}: {str(e)}")
                
                # Manejar específicamente el error 429 (demasiadas peticiones)
                if "429" in str(e):
                    logger.error("Límite de tasa de la API alcanzado. Esperando 60 segundos...")
                    time.sleep(60)  # Esperar 60 segundos antes de reintentar
                
                # Retroceso exponencial
                wait_time = (2 ** attempt) * (0.5 + random.random() * 0.5)
                logger.warning(f"Esperando {wait_time:.2f} segundos antes de reintentar...")
                time.sleep(wait_time)
                
                attempt += 1
        
        logger.error(f"No se pudieron obtener datos para {symbol} después de {MAX_RETRIES} intentos")
        return None
    
    def get_stock_info(self, symbol: str) -> Dict:
        """Obtener información fundamental del ticker usando Polygon.io con control de tasa"""
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                # Aplicar control de tasa antes de la petición
                self._throttle()
                
                logger.info(f"Obteniendo información para {symbol} (intento {attempt + 1}/{MAX_RETRIES})")
                
                client = RESTClient(api_key=POLYGON_API_KEY)
                
                # Obtener detalles del ticker
                ticker_details = client.get_ticker_details(symbol)
                
                # Aplicar control de tasa antes de la segunda petición
                self._throttle()
                
                # Obtener market cap y otros datos fundamentales
                try:
                    # Usar el método correcto para obtener información de la empresa
                    # que incluye market_cap en la versión actual de la API
                    ticker_details = client.get_ticker_details(symbol)
                    market_cap = getattr(ticker_details, 'market_cap', 0)
                except Exception as e:
                    logger.warning(f"Error obteniendo market cap para {symbol}: {str(e)}")
                    market_cap = 0
                
                # Construir diccionario con la información
                info = {
                    'marketCap': market_cap,
                    'beta': getattr(ticker_details, 'beta', 1.0),
                    'averageVolume': getattr(ticker_details, 'weighted_shares_outstanding', 0),
                    'previousClose': getattr(ticker_details, 'prev_day', {}).get('c', 0) if hasattr(ticker_details, 'prev_day') else 0,
                    'fiftyTwoWeekHigh': getattr(ticker_details, 'day', {}).get('h', 0) if hasattr(ticker_details, 'day') else 0,
                    'fiftyTwoWeekLow': getattr(ticker_details, 'day', {}).get('l', 0) if hasattr(ticker_details, 'day') else 0,
                    'sector': getattr(ticker_details, 'sector', ''),
                    'industry': getattr(ticker_details, 'industry', ''),
                    'companyName': getattr(ticker_details, 'name', symbol)
                }
                
                return info
                
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1} para {symbol}: {str(e)}")
                
                # Manejar específicamente el error 429 (demasiadas peticiones)
                if "429" in str(e):
                    logger.error("Límite de tasa de la API alcanzado. Esperando 60 segundos...")
                    time.sleep(60)  # Esperar 60 segundos antes de reintentar
                
                # Retroceso exponencial
                wait_time = (2 ** attempt) * (0.5 + random.random() * 0.5)
                logger.warning(f"Esperando {wait_time:.2f} segundos antes de reintentar...")
                time.sleep(wait_time)
                
                attempt += 1
        
        logger.error(f"No se pudo obtener información para {symbol} después de {MAX_RETRIES} intentos")
        return {}
    
    def calculate_beta(self, stock_data: pd.DataFrame) -> float:
        """Calcular beta vs SPY"""
        try:
            spy_data = yf.download('SPY', period='1y', progress=False)
            
            # Alinear fechas
            common_dates = stock_data.index.intersection(spy_data.index)
            stock_returns = stock_data.loc[common_dates, 'Close'].pct_change().dropna()
            spy_returns = spy_data.loc[common_dates, 'Close'].pct_change().dropna()
            
            # Calcular beta
            covariance = np.cov(stock_returns, spy_returns)[0][1]
            spy_variance = np.var(spy_returns)
            beta = covariance / spy_variance if spy_variance != 0 else 1.0
            
            return beta
        except:
            return 1.0
    
    def filter_universe(self) -> List[str]:
        """Filtrar el universo según criterios de small caps"""
        filtered_tickers = []
        
        for ticker in self.universe:
            print(f"Evaluating {ticker}...")
            
            # Obtener datos
            data = self.get_stock_data(ticker)
            info = self.get_stock_info(ticker)
            
            if data is None or len(data) < 100:
                continue
                
            # Verificar precio mínimo
            current_price = data['Close'].iloc[-1]
            if current_price < self.min_price:
                continue
            
            # Verificar volumen promedio
            avg_volume = data['Volume'].tail(20).mean()
            if avg_volume < self.min_avg_volume:
                continue
            
            # Verificar market cap (si está disponible)
            market_cap = info.get('marketCap', 0)
            if market_cap > 0:
                if market_cap < self.min_market_cap or market_cap > self.max_market_cap:
                    continue
            
            # Calcular beta
            beta = self.calculate_beta(data)
            if beta < self.min_beta:
                continue
            
            print(f"✓ {ticker} - Price: ${current_price:.2f}, Beta: {beta:.2f}, Avg Volume: {avg_volume:,.0f}")
            filtered_tickers.append(ticker)
        
        return filtered_tickers
    
    def detect_friday_signal(self, data: pd.DataFrame, symbol: str) -> Dict:
        """Detectar señal de entrada para Friday Effect"""
        if len(data) < 20:
            return None
        
        # Obtener último día de trading
        last_date = data.index[-1]
        last_day_name = last_date.strftime('%A')
        
        # Solo operar viernes
        if last_day_name != 'Friday':
            return None
        
        # Calcular métricas necesarias
        current_price = data['Close'].iloc[-1]
        
        # Volatilidad reciente (ATR 14 días)
        high_low = data['High'] - data['Low']
        high_close = abs(data['High'] - data['Close'].shift(1))
        low_close = abs(data['Low'] - data['Close'].shift(1))
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr_14 = true_range.tail(14).mean()
        
        # Rendimiento semanal
        weekly_return = (current_price / data['Close'].iloc[-5] - 1) * 100 if len(data) >= 5 else 0
        
        # Volumen relativo
        avg_volume_20 = data['Volume'].tail(20).mean()
        current_volume = data['Volume'].iloc[-1]
        relative_volume = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1
        
        # RSI
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        
        # Criterios de entrada
        signal_strength = 0
        reasons = []
        
        # 1. Acción debe estar cerca de mínimos recientes (presión vendedora)
        min_5d = data['Low'].tail(5).min()
        if current_price <= min_5d * 1.02:  # Dentro del 2% del mínimo 5 días
            signal_strength += 2
            reasons.append("Near 5-day low")
        
        # 2. RSI oversold pero no extremo
        if 25 <= current_rsi <= 40:
            signal_strength += 2
            reasons.append(f"RSI oversold: {current_rsi:.1f}")
        
        # 3. Volumen por encima del promedio (institucionales vendiendo)
        if relative_volume >= 1.2:
            signal_strength += 1
            reasons.append(f"High volume: {relative_volume:.1f}x")
        
        # 4. Rendimiento semanal negativo
        if weekly_return < -2:
            signal_strength += 1
            reasons.append(f"Weekly decline: {weekly_return:.1f}%")
        
        # 5. Volatilidad elevada (oportunidad)
        volatility_percentile = (atr_14 / current_price) * 100
        if volatility_percentile > 3:
            signal_strength += 1
            reasons.append(f"High volatility: {volatility_percentile:.1f}%")
        
        # Señal válida si cumple al menos 3 criterios
        if signal_strength >= 3:
            return {
                'symbol': symbol,
                'date': last_date,
                'signal': 'BUY',
                'entry_price': current_price,
                'signal_strength': signal_strength,
                'reasons': reasons,
                'atr': atr_14,
                'rsi': current_rsi,
                'weekly_return': weekly_return,
                'relative_volume': relative_volume,
                'stop_loss': current_price - (atr_14 * 1.5),  # Stop loss sugerido
                'target_1': current_price + (atr_14 * 2),     # Target 1 (lunes/martes)
                'target_2': current_price + (atr_14 * 3)      # Target 2 (extensión)
            }
        
        return None
    
    def scan_universe(self) -> List[Dict]:
        """Escanear universo completo en busca de señales, procesando tickers en lotes"""
        print("🔍 Scanning universe for Friday Effect signals...\n")
        
        # Filtrar universo
        filtered_tickers = self.filter_universe()
        
        if not filtered_tickers:
            print("❌ No tickers passed the filtering criteria")
            return []
        
        print(f"\n📊 Scanning {len(filtered_tickers)} qualified tickers for signals...\n")
        
        signals = []
        
        # Procesar en lotes de 5 tickers (respetando el límite de API)
        batch_size = 5
        total_batches = (len(filtered_tickers) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(filtered_tickers))
            batch = filtered_tickers[start_idx:end_idx]
            
            logger.info(f"Procesando lote {batch_num + 1}/{total_batches}: {', '.join(batch)}")
            
            # Procesar cada ticker en el lote
            for ticker in batch:
                print(f"Evaluando {ticker}...")
                data = self.get_stock_data(ticker)
                if data is not None:
                    signal = self.detect_friday_signal(data, ticker)
                    if signal:
                        signals.append(signal)
                        print(f"🎯 SIGNAL FOUND: {ticker}")
                        print(f"   Price: ${signal['entry_price']:.2f}")
                        print(f"   Strength: {signal['signal_strength']}/7")
                        print(f"   Reasons: {', '.join(signal['reasons'])}")
                        print(f"   Targets: ${signal['target_1']:.2f} / ${signal['target_2']:.2f}")
                        print()
            
            # Si no es el último lote, esperar antes del siguiente lote
            # Esto es redundante con el throttling individual, pero añade una capa extra de seguridad
            if batch_num < total_batches - 1:
                wait_time = 10  # Esperar 10 segundos entre lotes como seguridad adicional
                logger.info(f"Esperando {wait_time} segundos antes del siguiente lote...")
                time.sleep(wait_time)
        
        return signals

# Ejemplo de uso del algoritmo
if __name__ == "__main__":
    # Inicializar algoritmo
    friday_algo = FridayEffectAlgorithm()
    
    # Buscar señales
    signals = friday_algo.scan_universe()
    
    print(f"\n📈 SUMMARY: Found {len(signals)} Friday Effect signals")
    
    if signals:
        print("\n" + "="*60)
        print("TRADING SIGNALS - FRIDAY EFFECT")
        print("="*60)
        
        for signal in signals:
            print(f"\nTicker: {signal['symbol']}")
            print(f"Entry Price: ${signal['entry_price']:.2f}")
            print(f"Stop Loss: ${signal['stop_loss']:.2f}")
            print(f"Target 1: ${signal['target_1']:.2f} (+{((signal['target_1']/signal['entry_price'])-1)*100:.1f}%)")
            print(f"Target 2: ${signal['target_2']:.2f} (+{((signal['target_2']/signal['entry_price'])-1)*100:.1f}%)")
            print(f"Signal Strength: {signal['signal_strength']}/7")
            print(f"RSI: {signal['rsi']:.1f}")
            print(f"Reasons: {', '.join(signal['reasons'])}")
    else:
        print("No signals found for this Friday. Check again next Friday!")
