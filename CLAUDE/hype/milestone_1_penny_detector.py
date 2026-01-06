#!/usr/bin/env python3
"""
HITO 1 - Plan B: Detector con Alpha Vantage (más confiable para pennystocks)
Criterios: Precio < $5, Cambio % > 10%, Volumen > 500K
Incluye: Premarket + Regular hours

Instalación:
pip install requests

Configuración:
1. Obtén API key gratuita: https://www.alphavantage.co/support/#api-key
2. Reemplaza 'YOUR_API_KEY' abajo

Uso:
python milestone_1_penny_detector.py
"""

import requests
import json
from datetime import datetime, timedelta
import time

# ========================================
# CONFIGURACIÓN
# ========================================
API_KEY = "ZN0S7RQRZ2KDNYHZ"  # ⚠️ REEMPLAZA CON TU API KEY
BASE_URL = "https://www.alphavantage.co/query"

# Criterios para penny stocks
MAX_PRICE = 5.0        # < $5
MIN_CHANGE_PCT = 10.0  # > 10%
MIN_VOLUME = 500000    # > 500K

def get_top_gainers_losers():
    """Obtiene top gainers y losers del día desde Alpha Vantage"""
    try:
        params = {
            'function': 'TOP_GAINERS_LOSERS',
            'apikey': API_KEY
        }
        
        response = requests.get(BASE_URL, params=params, timeout=15)
        data = response.json()
        
        if "top_gainers" not in data:
            print(f"❌ Error en API: {data}")
            return []
        
        # Combinar gainers y losers
        all_movers = []
        all_movers.extend(data.get("top_gainers", []))
        all_movers.extend(data.get("top_losers", []))
        
        return all_movers
        
    except Exception as e:
        print(f"❌ Error obteniendo top movers: {e}")
        return []

def get_intraday_data(symbol):
    """Obtiene datos intradía incluyendo premarket"""
    try:
        params = {
            'function': 'TIME_SERIES_INTRADAY',
            'symbol': symbol,
            'interval': '5min',
            'apikey': API_KEY,
            'extended_hours': 'true',  # ⭐ Incluye premarket/afterhours
            'outputsize': 'compact'
        }
        
        response = requests.get(BASE_URL, params=params, timeout=10)
        data = response.json()
        
        if "Time Series (5min)" not in data:
            return None
        
        time_series = data["Time Series (5min)"]
        
        # Obtener el último precio disponible
        latest_time = max(time_series.keys())
        latest_data = time_series[latest_time]
        
        current_price = float(latest_data["4. close"])
        volume = int(latest_data["5. volume"])
        
        # Calcular volumen total del día
        today = datetime.now().strftime("%Y-%m-%d")
        daily_volume = 0
        for timestamp, data_point in time_series.items():
            if timestamp.startswith(today):
                daily_volume += int(data_point["5. volume"])
        
        return {
            'current_price': current_price,
            'volume': daily_volume,
            'last_update': latest_time,
            'last_volume': volume
        }
        
    except Exception as e:
        print(f"❌ Error datos intradía {symbol}: {str(e)[:30]}...")
        return None

def parse_mover_data(mover):
    """Parsea datos de un mover del endpoint TOP_GAINERS_LOSERS"""
    try:
        symbol = mover.get("ticker", "").upper()
        price = float(mover.get("price", 0))
        change_percent = float(mover.get("change_percentage", "0%").replace("%", ""))
        volume = int(mover.get("volume", 0))
        
        return {
            'symbol': symbol,
            'price': price,
            'change_percent': change_percent,
            'volume': volume,
            'source': 'top_movers'
        }
    except Exception as e:
        return None

def check_penny_criteria(stock_data):
    """Verifica si cumple criterios de penny mover"""
    if not stock_data:
        return False
        
    price_ok = stock_data['price'] < MAX_PRICE and stock_data['price'] > 0
    change_ok = abs(stock_data['change_percent']) > MIN_CHANGE_PCT
    volume_ok = stock_data['volume'] > MIN_VOLUME
    
    return price_ok and change_ok and volume_ok

def get_session_info():
    """Determina en qué sesión estamos"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    
    # EST timezone (aproximado)
    if hour < 9 or (hour == 9 and minute < 30):
        return "🌅 Premarket", "premarket"
    elif hour >= 16:
        return "🌙 Afterhours", "afterhours"  
    else:
        return "🕐 Regular", "regular"

def main():
    session_emoji, session = get_session_info()
    
    print("🔍 DETECTOR PENNY MOVERS (ALPHA VANTAGE)")
    print(f"📊 Criterios: Precio < ${MAX_PRICE}, Cambio > {MIN_CHANGE_PCT}%, Volumen > {MIN_VOLUME:,}")
    print(f"🕐 Hora: {datetime.now().strftime('%H:%M:%S')} - Sesión: {session_emoji}")
    print("-" * 80)
    
    if API_KEY == "YOUR_API_KEY":
        print("❌ ERROR: Necesitas configurar tu API_KEY de Alpha Vantage")
        print("📋 Pasos:")
        print("   1. Ve a: https://www.alphavantage.co/support/#api-key")
        print("   2. Regístrate gratis")
        print("   3. Copia el API key y reemplaza 'YOUR_API_KEY' en línea 22")
        return
    
    print("📈 Obteniendo top movers del día...")
    
    # Obtener top gainers y losers
    all_movers = get_top_gainers_losers()
    
    if not all_movers:
        print("❌ No se pudieron obtener datos de movers")
        return
    
    print(f"🎯 Analizando {len(all_movers)} movers...")
    print("-" * 80)
    
    penny_movers = []
    processed = 0
    
    for mover in all_movers:
        stock_data = parse_mover_data(mover)
        if not stock_data:
            continue
            
        processed += 1
        symbol = stock_data['symbol']
        
        print(f"📊 {symbol} ({processed}/{len(all_movers)})...", end=" ")
        
        if check_penny_criteria(stock_data):
            # Obtener datos más detallados si es candidato
            detailed_data = get_intraday_data(symbol)
            if detailed_data:
                stock_data.update(detailed_data)
            
            penny_movers.append(stock_data)
            print(f"✅ PENNY MOVER!")
        else:
            reason = []
            if stock_data['price'] >= MAX_PRICE:
                reason.append(f"precio=${stock_data['price']:.2f}")
            if abs(stock_data['change_percent']) <= MIN_CHANGE_PCT:
                reason.append(f"cambio={stock_data['change_percent']:+.1f}%")
            if stock_data['volume'] <= MIN_VOLUME:
                reason.append(f"vol={stock_data['volume']:,}")
            
            print(f"❌ ({', '.join(reason)})")
        
        # Pausa para respetar rate limit (5 calls/min)
        if processed % 5 == 0 and processed < len(all_movers):
            print("   ⏳ Pausa (rate limit)...")
            time.sleep(60)  # 1 minuto cada 5 calls
    
    # ========================================
    # RESULTADOS
    # ========================================
    print("\n" + "="*80)
    print(f"🎯 PENNY MOVERS DETECTADOS: {len(penny_movers)}")
    print("="*80)
    
    if penny_movers:
        # Ordenar por cambio porcentual (valor absoluto)
        penny_movers.sort(key=lambda x: abs(x['change_percent']), reverse=True)
        
        print(f"{'TICKER':<8} {'PRECIO':<8} {'CAMBIO%':<10} {'VOLUMEN':<15} {'SESIÓN'}")
        print("-" * 80)
        
        for stock in penny_movers:
            change_emoji = "📈" if stock['change_percent'] > 0 else "📉"
            
            print(f"{change_emoji} {stock['symbol']:<8} "
                  f"${stock['price']:<7.2f} "
                  f"{stock['change_percent']:+8.1f}% "
                  f"{stock['volume']:<14,} "
                  f"{session_emoji}")
        
        print(f"\n🚀 ¡Encontrados {len(penny_movers)} penny movers con potencial!")
        
    else:
        print("❌ No se encontraron penny movers que cumplan todos los criterios")
        print(f"\n💡 Esto podría significar:")
        print(f"   - Mercado estable hoy ({session})")
        print(f"   - Criterios muy estrictos (cambio > {MIN_CHANGE_PCT}%)")
        print(f"   - La mayoría de movers están sobre ${MAX_PRICE}")
    
    print(f"\n✅ HITO 1 COMPLETADO - {datetime.now().strftime('%H:%M:%S')}")
    print("🔧 Alpha Vantage funcionando correctamente")

if __name__ == "__main__":
    main()