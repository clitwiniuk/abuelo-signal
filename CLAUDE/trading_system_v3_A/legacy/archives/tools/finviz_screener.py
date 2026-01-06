#!/usr/bin/env python3
"""
Finviz Smallcaps Screener
=========================

Screener que utiliza Finviz para filtrar tickers smallcaps con características 
favorables para day trading y descarga sus datos de 1 minuto.

Basado en el código original datos_finviz.py pero adaptado para screening diario.

Criterios de filtrado (aplicados via Finviz):
- Precio: $1 - $5 
- Short Float: >35%
- Volumen: >500K
- Market Cap: <500M
- RSI: <45
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import os
import sys
import time
from typing import List, Dict, Optional
import json

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")
    DOTENV_AVAILABLE = False

# Importar Polygon handler
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'tools'))
try:
    from polygon_csv_handler import PolygonDownloader
    POLYGON_AVAILABLE = True
except ImportError:
    print("⚠️  polygon_csv_handler not found. Check path.")
    POLYGON_AVAILABLE = False

try:
    from finvizfinance.screener.overview import Overview
    from finvizfinance.quote import finvizfinance
    FINVIZ_AVAILABLE = True
except ImportError:
    print("⚠️  finvizfinance not installed. Install with: pip install finvizfinance")
    FINVIZ_AVAILABLE = False


class FinvizSmallcapsScreener:
    """Screener usando Finviz para filtrar smallcaps con potencial day trading"""
    
    def __init__(self, polygon_api_key: str = None):
        self.filtered_data_dir = "finviz_filtered_data"
        self.screener_results_dir = "finviz_screener_results"
        
        # Crear directorios
        os.makedirs(self.filtered_data_dir, exist_ok=True)
        os.makedirs(self.screener_results_dir, exist_ok=True)
        
        # Configurar Polygon downloader
        self.polygon_api_key = polygon_api_key or os.getenv('POLYGON_API_KEY')
        if self.polygon_api_key and POLYGON_AVAILABLE:
            self.polygon_downloader = PolygonDownloader(self.polygon_api_key)
            self.use_polygon = True
        else:
            self.polygon_downloader = None
            self.use_polygon = False
        
        # Criterios de filtrado para Finviz
        self.finviz_filters = {
            'Price': ['1to5'],                    # $1-$5
            'Market Cap': ['+Small (over $300mln)'],  # >$300M but we'll filter <$500M manually
            'Average Volume': ['+Over 500K'],      # >500K volume
            'Float Short': ['High (>15%)'],       # High short interest
            'RSI (14)': ['Oversold (<30)'],       # RSI oversold (we'll adjust to <45 manually)
        }
        
        # Criterios adicionales para filtro manual
        self.manual_criteria = {
            'max_market_cap': 500e6,     # $500M
            'max_rsi': 45.0,             # RSI <45
            'min_short_float': 35.0,     # >35% short float
        }
        
        print("🎯 Finviz Smallcaps Screener initialized")
        print(f"📂 Data directory: {self.filtered_data_dir}/")
        print(f"📊 Results directory: {self.screener_results_dir}/")
        print(f"📥 Data source: {'Polygon.io' if self.use_polygon else 'YFinance (fallback)'}")
    
    def convert_to_number(self, value):
        """Convierte strings de Finviz a números (basado en tu código original)"""
        if isinstance(value, str):
            value = value.replace(',', '')
            if 'B' in value:
                value = float(value.replace('B', '')) * 1e9
            elif 'M' in value:
                value = float(value.replace('M', '')) * 1e6
            elif 'K' in value:
                value = float(value.replace('K', '')) * 1e3
            elif '%' in value:
                value = float(value.replace('+', '').replace('%', '')) / 100
            try:
                value = float(value)
                if value < 0 or value > 1e12:
                    print(f"Valor fuera de rango detectado: {value}")
                    return None
                return value
            except ValueError:
                print(f"No se pudo convertir el valor: {value}")
                return None
        return value

    def get_finviz_screener_results(self) -> List[str]:
        """
        Obtiene tickers del screener de Finviz usando los filtros definidos
        """
        print(f"\n🔍 RUNNING FINVIZ SCREENER")
        print("-" * 50)
        
        if not FINVIZ_AVAILABLE:
            print("❌ finvizfinance package not available")
            return []
        
        try:
            # Crear screener de Finviz
            fviz = Overview()
            
            # Configurar filtros menos restrictivos para Finviz
            # Haremos filtros más específicos manualmente
            basic_filters = {
                'Price': '$1 to $5',               # $1-$5
                'Average Volume': 'Over 500K',     # >500K volume
                'Market Cap.': 'Small ($300mln to $2bln)',  # Small cap
            }
            
            print("🔍 Applying Finviz filters:")
            for key, value in basic_filters.items():
                print(f"   {key}: {value}")
            
            # Aplicar filtros
            fviz.set_filter(filters_dict=basic_filters)
            
            # Obtener resultados
            df = fviz.screener_view()
            
            if df is None or df.empty:
                print("❌ No results from Finviz screener")
                return []
            
            tickers = df['Ticker'].tolist()
            print(f"✅ Finviz returned {len(tickers)} tickers")
            
            # Mostrar algunos ejemplos
            print("📊 Sample tickers:")
            for ticker in tickers[:10]:
                print(f"   {ticker}")
            if len(tickers) > 10:
                print(f"   ... and {len(tickers) - 10} more")
            
            return tickers
            
        except Exception as e:
            print(f"❌ Error with Finviz screener: {e}")
            return []

    def get_finviz_ticker_data(self, ticker: str) -> Optional[Dict]:
        """
        Obtiene datos detallados de un ticker desde Finviz (basado en tu código)
        """
        try:
            stock = finvizfinance(ticker)
            fundamentals = stock.ticker_fundament()

            if not fundamentals:
                return None

            data = {
                'ticker': ticker,
                'fecha': date.today().isoformat(),
                'price': self.convert_to_number(fundamentals.get('Price', 'No disponible')),
                'float_shares': self.convert_to_number(fundamentals.get('Shs Float', 'No disponible')),
                'exchange': fundamentals.get('Exchange', 'No disponible'),
                'country': fundamentals.get('Country', 'No disponible'),
                'avg_volume': self.convert_to_number(fundamentals.get('Avg Volume', 'No disponible')),
                'shs_outstand': self.convert_to_number(fundamentals.get('Shs Outstand', 'No disponible')),
                'market_cap': self.convert_to_number(fundamentals.get('Market Cap', 'No disponible')),
                'inst_own': self.convert_to_number(fundamentals.get('Inst Own', 'No disponible')),
                'short_float': self.convert_to_number(fundamentals.get('Short Float', 'No disponible')),
                'rel_volume': self.convert_to_number(fundamentals.get('Rel Volume', 'No disponible')),
                'rsi': self.convert_to_number(fundamentals.get('RSI (14)', 'No disponible')),
                'perf_week': self.convert_to_number(fundamentals.get('Perf Week', 'No disponible')),
                'perf_month': self.convert_to_number(fundamentals.get('Perf Month', 'No disponible')),
            }
            
            return data
            
        except Exception as e:
            print(f"   ❌ Error getting data for {ticker}: {str(e)[:50]}")
            return None

    def filter_tickers_manually(self, tickers: List[str]) -> List[Dict]:
        """
        Aplica filtros adicionales manualmente a los tickers de Finviz
        """
        print(f"\n🔍 APPLYING MANUAL FILTERS TO {len(tickers)} TICKERS")
        print("-" * 50)
        print("Additional criteria:")
        print(f"   💎 Market Cap: <${self.manual_criteria['max_market_cap']/1e6:.0f}M")
        print(f"   📉 RSI: <{self.manual_criteria['max_rsi']:.1f}")
        print(f"   📊 Short Float: >{self.manual_criteria['min_short_float']:.1f}%")
        print()
        
        filtered_tickers = []
        
        for i, ticker in enumerate(tickers):
            data = self.get_finviz_ticker_data(ticker)
            
            if data is None:
                continue
            
            # Aplicar filtros manuales
            price = data.get('price', 0)
            market_cap = data.get('market_cap', 0)
            rsi = data.get('rsi', 100)  # Default alto si no hay RSI
            short_float = data.get('short_float', 0)
            volume = data.get('avg_volume', 0)
            
            # Checks
            price_ok = 1.0 <= price <= 5.0 if price else False
            mcap_ok = market_cap <= self.manual_criteria['max_market_cap'] if market_cap else False
            rsi_ok = rsi <= self.manual_criteria['max_rsi'] if rsi else False
            short_ok = short_float >= self.manual_criteria['min_short_float'] if short_float else False
            volume_ok = volume >= 500000 if volume else False
            
            # Debug output
            status = "✅" if all([price_ok, mcap_ok, rsi_ok, short_ok, volume_ok]) else "❌"
            print(f"   {status} {ticker:<6} | "
                  f"${price or 0:<5.2f} | "
                  f"MCap: {(market_cap or 0)/1e6:<5.0f}M | "
                  f"RSI: {rsi or 0:<5.1f} | "
                  f"SF: {short_float or 0:<5.1f}% | "
                  f"Vol: {(volume or 0)/1000:<5.0f}K")
            
            if all([price_ok, mcap_ok, rsi_ok, short_ok, volume_ok]):
                filtered_tickers.append(data)
            
            # Rate limiting para evitar bloqueo de Finviz
            time.sleep(0.5)
        
        print(f"\n🎯 MANUAL FILTERING RESULTS: {len(filtered_tickers)}/{len(tickers)} tickers passed")
        return filtered_tickers

    def download_minute_data(self, ticker: str, target_date: str = None) -> bool:
        """
        Descarga datos de 1 minuto para un ticker usando Polygon.io o fallback a yfinance
        """
        if target_date is None:
            target_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Determinar rango de fechas (últimos 7 días)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        try:
            print(f"📥 Downloading {ticker} minute data ({start_str} to {end_str})...")
            
            # Usar Polygon.io si está disponible
            if self.use_polygon:
                # Configurar directorio temporal para Polygon
                temp_dir = f"{self.filtered_data_dir}/temp/"
                os.makedirs(temp_dir, exist_ok=True)
                
                # Usar el downloader de Polygon
                df = self.polygon_downloader.get_ticker_data(
                    ticker, start_str, end_str, temp_dir
                )
                
                if not df.empty:
                    # Mover archivo del directorio temporal al final
                    temp_file = f"{temp_dir}{ticker}.csv"
                    final_filename = f"{ticker}_{target_date.replace('-', '')}.csv"
                    final_filepath = os.path.join(self.filtered_data_dir, final_filename)
                    
                    if os.path.exists(temp_file):
                        os.rename(temp_file, final_filepath)
                        print(f"   ✅ Polygon: Saved {len(df)} bars to {final_filename}")
                        
                        # Limpiar directorio temporal
                        try:
                            os.rmdir(temp_dir)
                        except:
                            pass
                        
                        return True
                else:
                    print(f"   ❌ Polygon: No data available for {ticker}")
                    return False
            
            else:
                # Fallback a yfinance si Polygon no está disponible
                print("   📊 Using yfinance fallback...")
                import yfinance as yf
                
                stock = yf.Ticker(ticker)
                data = stock.history(period="7d", interval="1m")
                
                if data.empty:
                    print(f"   ❌ YFinance: No data available for {ticker}")
                    return False
                
                # Guardar CSV
                filename = f"{ticker}_{target_date.replace('-', '')}.csv"
                filepath = os.path.join(self.filtered_data_dir, filename)
                
                # Formatear datos para compatibilidad con Polygon format
                data_formatted = data.copy()
                data_formatted.index = data_formatted.index.tz_localize(None)
                data_formatted = data_formatted.reset_index()
                data_formatted.rename(columns={
                    'Datetime': 'timestamp',
                    'Open': 'open',
                    'High': 'high', 
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                }, inplace=True)
                
                # Guardar
                data_formatted.to_csv(filepath, index=False)
                print(f"   ✅ YFinance: Saved {len(data)} bars to {filename}")
                return True
                
        except Exception as e:
            print(f"   ❌ Error downloading {ticker}: {str(e)[:50]}")
            return False

    def save_screener_results(self, filtered_tickers: List[Dict]) -> str:
        """
        Guarda los resultados del screener
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Guardar como JSON (datos completos)
        json_filename = f"finviz_screener_{timestamp}.json"
        json_filepath = os.path.join(self.screener_results_dir, json_filename)
        
        with open(json_filepath, 'w') as f:
            json.dump(filtered_tickers, f, indent=2)
        
        # Guardar como CSV (resumen)
        if filtered_tickers:
            df = pd.DataFrame(filtered_tickers)
            csv_filename = f"finviz_screener_{timestamp}.csv"
            csv_filepath = os.path.join(self.screener_results_dir, csv_filename)
            df.to_csv(csv_filepath, index=False)
            
            print(f"✅ Results saved:")
            print(f"   📄 {json_filename}")
            print(f"   📊 {csv_filename}")
        
        return json_filepath

    def run_daily_screen(self, download_data: bool = True) -> Dict:
        """
        Ejecuta el screener completo diario usando Finviz
        """
        print("🚀 RUNNING FINVIZ DAILY SMALLCAPS SCREENER")
        print("=" * 60)
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        start_time = time.time()
        
        # 1. Obtener tickers desde Finviz
        finviz_tickers = self.get_finviz_screener_results()
        
        if not finviz_tickers:
            print("❌ No tickers returned from Finviz screener")
            return {'error': 'No tickers from Finviz'}
        
        # 2. Aplicar filtros manuales adicionales
        filtered_tickers = self.filter_tickers_manually(finviz_tickers)
        
        # 3. Guardar resultados
        results_file = self.save_screener_results(filtered_tickers)
        
        # 4. Descargar datos si se solicita
        downloaded_count = 0
        if download_data and filtered_tickers:
            print(f"\n📥 DOWNLOADING MINUTE DATA")
            print("-" * 50)
            
            for ticker_data in filtered_tickers:
                ticker = ticker_data['ticker']
                if self.download_minute_data(ticker):
                    downloaded_count += 1
                time.sleep(1)  # Rate limiting
        
        elapsed_time = time.time() - start_time
        
        # 5. Resumen final
        print(f"\n📊 FINVIZ SCREENING COMPLETED")
        print("=" * 60)
        print(f"⏱️  Total time: {elapsed_time:.1f} seconds")
        print(f"🔍 Finviz tickers retrieved: {len(finviz_tickers)}")
        print(f"✅ Tickers passed manual filters: {len(filtered_tickers)}")
        print(f"📥 Data files downloaded: {downloaded_count}")
        print(f"📄 Results saved: {os.path.basename(results_file)}")
        
        if filtered_tickers:
            print(f"\n🏆 TOP CANDIDATES:")
            for ticker_data in filtered_tickers[:5]:  # Top 5
                price = ticker_data.get('price', 0)
                rsi = ticker_data.get('rsi', 0)
                short_float = ticker_data.get('short_float', 0)
                print(f"   🎯 {ticker_data['ticker']} | "
                      f"${price:.2f} | "
                      f"RSI: {rsi:.1f} | "
                      f"SF: {short_float:.1f}%")
        
        return {
            'finviz_count': len(finviz_tickers),
            'filtered_count': len(filtered_tickers),
            'downloaded_count': downloaded_count,
            'results_file': results_file,
            'filtered_tickers': filtered_tickers
        }


def main():
    """Función principal"""
    
    print("🎯 FINVIZ SMALLCAPS SCREENER WITH POLYGON.IO")
    print("=" * 60)
    
    # Configurar Polygon API key desde .env
    polygon_api_key = os.getenv('POLYGON_API_KEY')
    
    if not polygon_api_key:
        print("⚠️  POLYGON_API_KEY not found in environment")
        print()
        print("📝 Configuration options:")
        print("   1. 📄 Create .env file in project root:")
        print("      POLYGON_API_KEY=your_api_key_here")
        print("      (See .env.example for template)")
        print("   2. 🖥️  Set environment variable:")
        print("      export POLYGON_API_KEY=your_api_key")
        print("   3. ⌨️  Enter manually (temporary)")
        print()
        
        if DOTENV_AVAILABLE:
            print("✅ python-dotenv is available - you can use .env file")
        else:
            print("❌ python-dotenv not installed - install with: pip install python-dotenv")
        
        polygon_api_key = input("👉 Enter Polygon API key (or press Enter to use yfinance): ").strip()
        
        if polygon_api_key:
            # Offer to save to .env file
            save_to_env = input("💾 Save this API key to .env file? (y/n): ").strip().lower()
            if save_to_env == 'y':
                try:
                    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
                    
                    # Read existing .env if it exists
                    existing_content = ""
                    if os.path.exists(env_path):
                        with open(env_path, 'r') as f:
                            lines = f.readlines()
                        
                        # Filter out existing POLYGON_API_KEY lines
                        lines = [line for line in lines if not line.startswith('POLYGON_API_KEY=')]
                        existing_content = ''.join(lines)
                    
                    # Write updated .env
                    with open(env_path, 'w') as f:
                        f.write(existing_content)
                        if existing_content and not existing_content.endswith('\n'):
                            f.write('\n')
                        f.write(f'POLYGON_API_KEY={polygon_api_key}\n')
                    
                    print(f"✅ API key saved to {env_path}")
                    print("💡 Restart the script to load from .env automatically")
                    
                except Exception as e:
                    print(f"❌ Error saving to .env file: {e}")
        else:
            print("📊 Will use yfinance fallback for data download")
    
    screener = FinvizSmallcapsScreener(polygon_api_key=polygon_api_key)
    
    # Mostrar configuración
    print(f"📊 Data source: {'Polygon.io' if screener.use_polygon else 'YFinance (fallback)'}")
    print(f"🔍 Finviz available: {'✅' if FINVIZ_AVAILABLE else '❌'}")
    print()
    
    try:
        # Verificar que finvizfinance esté disponible
        if not FINVIZ_AVAILABLE:
            print("❌ Please install finvizfinance: pip install finvizfinance")
            return
        
        # Ejecutar screener completo
        results = screener.run_daily_screen(download_data=True)
        
        if 'error' not in results:
            print(f"\n🎉 Finviz screening completed successfully!")
            print(f"📊 Check results in: {screener.screener_results_dir}/")
            print(f"📁 Check data files in: {screener.filtered_data_dir}/")
        else:
            print(f"❌ Screening failed: {results['error']}")
        
    except KeyboardInterrupt:
        print("\n👋 Screening cancelled by user")
    except Exception as e:
        print(f"\n❌ Error during screening: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()