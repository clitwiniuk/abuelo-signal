import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import time
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

class NASDAQBreakoutScanner:
    def __init__(self, 
                 max_market_cap: float = 500_000_000,  # 500M USD
                 max_float: float = 50_000_000,        # 50M shares
                 min_volume: int = 100_000,            # Volumen mínimo diario
                 min_price: float = 1.0,               # Precio mínimo
                 max_price: float = 50.0,              # Precio máximo
                 consolidation_days: int = 10,         # Días mínimos de consolidación
                 breakout_threshold: float = 0.02):    # 2% para considerar breakout
        
        self.max_market_cap = max_market_cap
        self.max_float = max_float
        self.min_volume = min_volume
        self.min_price = min_price
        self.max_price = max_price
        self.consolidation_days = consolidation_days
        self.breakout_threshold = breakout_threshold
        
    def get_nasdaq_tickers(self) -> List[str]:
        """Obtiene lista de tickers del NASDAQ"""
        try:
            # Usando una lista de tickers NASDAQ comunes (puedes expandir esta lista)
            url = "https://api.nasdaq.com/api/screener/stocks"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Lista alternativa de tickers NASDAQ populares
            nasdaq_tickers = [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
                'ADBE', 'PYPL', 'INTC', 'CMCSA', 'PEP', 'AVGO', 'TXN', 'QCOM',
                'COST', 'TMUS', 'CHTR', 'INTU', 'AMGN', 'SBUX', 'GILD', 'MDLZ',
                'BKNG', 'ISRG', 'REGN', 'ADP', 'VRTX', 'ATVI', 'FISV', 'CSX',
                'BIIB', 'ILMN', 'AMAT', 'MRNA', 'ASML', 'KLAC', 'LRCX', 'SNPS',
                'CDNS', 'MCHP', 'ORLY', 'CSGP', 'PAYX', 'FAST', 'VRSK', 'CTSH',
                'DDOG', 'CRWD', 'ZM', 'DOCU', 'OKTA', 'SPLK', 'WDAY', 'TEAM',
                'SHOP', 'SQ', 'ROKU', 'TWLO', 'SNAP', 'SPOT', 'UBER', 'LYFT',
                'ABNB', 'COIN', 'HOOD', 'RBLX', 'RIVN', 'LCID', 'PLTR', 'SNOW'
            ]
            
            # Agregar más tickers de pequeña capitalización
            small_cap_tickers = [
                'SAVA', 'BBIG', 'PROG', 'ATER', 'BGFV', 'IRNT', 'OPAD', 'PHUN',
                'DWAC', 'BENE', 'ANY', 'GREE', 'SPRT', 'MMAT', 'TRCH', 'NEGG',
                'XELA', 'CLOV', 'WISH', 'SOFI', 'PLBY', 'GOEV', 'NKLA', 'RIDE',
                'WKHS', 'BLNK', 'CHPT', 'EVGO', 'FFIE', 'MULN', 'CENN', 'PTRA',
                'ARVL', 'CANOO', 'HYLN', 'SHLL', 'VLDR', 'LAZR', 'LIDR', 'OUST',
                'MVIS', 'KOPN', 'MICT', 'JAGX', 'SNDL', 'ZSAN', 'COCP', 'EARS',
                'NAKD', 'SIRI', 'ZYNE', 'TRNX', 'TOPS', 'SHIP', 'GLBS', 'CTRM',
                'CASTOR', 'TBLT', 'SESN', 'JAGX', 'VYNE', 'IMMP', 'ADMP', 'OCGN'
            ]
            
            all_tickers = nasdaq_tickers + small_cap_tickers
            return list(set(all_tickers))  # Eliminar duplicados
            
        except Exception as e:
            print(f"Error obteniendo tickers: {e}")
            return []
    
    def get_stock_info(self, ticker: str) -> Dict:
        """Obtiene información fundamental de una acción"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Obtener datos históricos
            hist = stock.history(period="3mo")
            if hist.empty:
                return None
                
            current_price = hist['Close'].iloc[-1]
            avg_volume = hist['Volume'].tail(20).mean()
            
            return {
                'ticker': ticker,
                'current_price': current_price,
                'market_cap': info.get('marketCap', 0),
                'float_shares': info.get('floatShares', info.get('sharesOutstanding', 0)),
                'avg_volume': avg_volume,
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'hist_data': hist
            }
            
        except Exception as e:
            print(f"Error obteniendo info para {ticker}: {e}")
            return None
    
    def detect_consolidation(self, hist_data: pd.DataFrame) -> Dict:
        """Detecta patrones de consolidación"""
        try:
            if len(hist_data) < self.consolidation_days:
                return {'in_consolidation': False, 'reason': 'Insufficient data'}
            
            # Tomar los últimos días para análisis
            recent_data = hist_data.tail(self.consolidation_days)
            
            # Calcular rango de precios
            high_max = recent_data['High'].max()
            low_min = recent_data['Low'].min()
            price_range = (high_max - low_min) / low_min
            
            # Calcular volatilidad
            returns = recent_data['Close'].pct_change().dropna()
            volatility = returns.std()
            
            # Detectar consolidación
            # 1. Rango de precios estrecho (menos del 15%)
            # 2. Baja volatilidad
            # 3. Volumen consistente
            
            avg_volume = recent_data['Volume'].mean()
            volume_cv = recent_data['Volume'].std() / avg_volume if avg_volume > 0 else 1
            
            is_consolidating = (
                price_range < 0.15 and  # Rango menor al 15%
                volatility < 0.05 and   # Baja volatilidad
                volume_cv < 1.5         # Volumen relativamente consistente
            )
            
            # Detectar posible breakout
            current_price = hist_data['Close'].iloc[-1]
            resistance_level = recent_data['High'].max()
            support_level = recent_data['Low'].min()
            
            distance_to_resistance = (resistance_level - current_price) / current_price
            distance_to_support = (current_price - support_level) / current_price
            
            breakout_potential = distance_to_resistance < self.breakout_threshold
            
            return {
                'in_consolidation': is_consolidating,
                'price_range_pct': price_range * 100,
                'volatility': volatility,
                'volume_cv': volume_cv,
                'resistance_level': resistance_level,
                'support_level': support_level,
                'current_price': current_price,
                'distance_to_resistance_pct': distance_to_resistance * 100,
                'distance_to_support_pct': distance_to_support * 100,
                'breakout_potential': breakout_potential,
                'reason': 'Consolidating' if is_consolidating else 'Not consolidating'
            }
            
        except Exception as e:
            return {'in_consolidation': False, 'reason': f'Error: {e}'}
    
    def passes_filters(self, stock_info: Dict) -> bool:
        """Verifica si una acción pasa todos los filtros"""
        try:
            # Filtro de precio
            if stock_info['current_price'] < self.min_price or stock_info['current_price'] > self.max_price:
                return False
            
            # Filtro de market cap
            if stock_info['market_cap'] > self.max_market_cap:
                return False
            
            # Filtro de float (si está disponible)
            if stock_info['float_shares'] and stock_info['float_shares'] > self.max_float:
                return False
            
            # Filtro de volumen
            if stock_info['avg_volume'] < self.min_volume:
                return False
            
            return True
            
        except Exception as e:
            print(f"Error en filtros: {e}")
            return False
    
    def scan_stocks(self) -> List[Dict]:
        """Escanea todas las acciones y encuentra candidatos"""
        tickers = self.get_nasdaq_tickers()
        candidates = []
        
        print(f"Escaneando {len(tickers)} tickers...")
        
        for i, ticker in enumerate(tickers):
            try:
                print(f"Procesando {ticker} ({i+1}/{len(tickers)})")
                
                # Obtener información de la acción
                stock_info = self.get_stock_info(ticker)
                if not stock_info:
                    continue
                
                # Verificar filtros básicos
                if not self.passes_filters(stock_info):
                    continue
                
                # Analizar consolidación
                consolidation_info = self.detect_consolidation(stock_info['hist_data'])
                
                # Si está en consolidación, agregar a candidatos
                if consolidation_info['in_consolidation']:
                    candidate = {
                        'ticker': ticker,
                        'current_price': stock_info['current_price'],
                        'market_cap': stock_info['market_cap'],
                        'float_shares': stock_info['float_shares'],
                        'avg_volume': stock_info['avg_volume'],
                        'sector': stock_info['sector'],
                        'industry': stock_info['industry'],
                        'price_range_pct': consolidation_info['price_range_pct'],
                        'volatility': consolidation_info['volatility'],
                        'resistance_level': consolidation_info['resistance_level'],
                        'support_level': consolidation_info['support_level'],
                        'distance_to_resistance_pct': consolidation_info['distance_to_resistance_pct'],
                        'breakout_potential': consolidation_info['breakout_potential'],
                        'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    candidates.append(candidate)
                    print(f"✓ {ticker} - Candidato encontrado!")
                
                # Pausa para evitar rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error procesando {ticker}: {e}")
                continue
        
        return candidates
    
    def save_to_csv(self, candidates: List[Dict], filename: str = None) -> str:
        """Guarda los candidatos en un archivo CSV"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'nasdaq_breakout_candidates_{timestamp}.csv'
        
        df = pd.DataFrame(candidates)
        
        if not df.empty:
            # Ordenar por potencial de breakout y proximidad a resistencia
            df = df.sort_values(['breakout_potential', 'distance_to_resistance_pct'], 
                               ascending=[False, True])
            
            # Formatear números
            df['current_price'] = df['current_price'].round(2)
            df['market_cap'] = df['market_cap'].apply(lambda x: f"{x:,.0f}")
            df['float_shares'] = df['float_shares'].apply(lambda x: f"{x:,.0f}" if x else "N/A")
            df['avg_volume'] = df['avg_volume'].apply(lambda x: f"{x:,.0f}")
            df['price_range_pct'] = df['price_range_pct'].round(2)
            df['volatility'] = df['volatility'].round(4)
            df['resistance_level'] = df['resistance_level'].round(2)
            df['support_level'] = df['support_level'].round(2)
            df['distance_to_resistance_pct'] = df['distance_to_resistance_pct'].round(2)
        
        df.to_csv(filename, index=False)
        return filename

def main():
    # Configuración personalizable
    scanner = NASDAQBreakoutScanner(
        max_market_cap=500_000_000,    # 500M USD
        max_float=50_000_000,          # 50M shares
        min_volume=100_000,            # Volumen mínimo diario
        min_price=1.0,                 # Precio mínimo
        max_price=50.0,                # Precio máximo
        consolidation_days=10,         # Días de consolidación
        breakout_threshold=0.02        # 2% para breakout
    )
    
    print("=== NASDAQ Breakout Scanner ===")
    print(f"Filtros aplicados:")
    print(f"- Market Cap máximo: ${scanner.max_market_cap:,}")
    print(f"- Float máximo: {scanner.max_float:,} shares")
    print(f"- Volumen mínimo: {scanner.min_volume:,}")
    print(f"- Rango de precios: ${scanner.min_price} - ${scanner.max_price}")
    print(f"- Días de consolidación: {scanner.consolidation_days}")
    print(f"- Umbral de breakout: {scanner.breakout_threshold*100}%")
    print()
    
    # Escanear acciones
    candidates = scanner.scan_stocks()
    
    print(f"\n=== RESULTADOS ===")
    print(f"Candidatos encontrados: {len(candidates)}")
    
    if candidates:
        # Guardar en CSV
        filename = scanner.save_to_csv(candidates)
        print(f"Resultados guardados en: {filename}")
        
        # Mostrar top 5 candidatos
        print(f"\nTop 5 candidatos:")
        for i, candidate in enumerate(candidates[:5]):
            print(f"{i+1}. {candidate['ticker']}")
            print(f"   Precio: ${candidate['current_price']}")
            print(f"   Distancia a resistencia: {candidate['distance_to_resistance_pct']:.2f}%")
            print(f"   Potencial de breakout: {candidate['breakout_potential']}")
            print()
    else:
        print("No se encontraron candidatos con los filtros actuales.")

if __name__ == "__main__":
    main()
