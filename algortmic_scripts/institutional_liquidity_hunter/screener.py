import pandas as pd
from ib_insync import *
import talib as ta
import numpy as np
import requests

class SmallCapScreener:
    def __init__(self, ib_client):
        self.ib = ib_client
        self.universe = self.get_nasdaq_universe()  # Base de acciones NASDAQ

    def get_nasdaq_universe(self):
        """Descarga el universo inicial desde NASDAQ"""
        url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=5000"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        print("STATUS:", response.status_code)
        try:
            data = response.json()
        except Exception as e:
            print("[ERROR] No se pudo decodificar JSON:", e)
            return []
        # Nuevo path correcto:
        if 'data' in data and 'table' in data['data'] and 'rows' in data['data']['table']:
            rows = data['data']['table']['rows']
            universe = []
            for stock in rows:
                mc_raw = stock.get('marketCap')
                if mc_raw:
                    try:
                        mc = float(mc_raw.replace(",", ""))
                    except Exception:
                        continue
                    if 300e6 <= mc <= 2e9:
                        universe.append(stock['symbol'])
            return universe
        else:
            print("Estructura inesperada:", data)
            return []

    def apply_filters(self, symbol):
        """Aplica filtros cuantitativos clave"""
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr='30 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )
            df = util.df(bars)
            
            if len(df) < 20:  # Mínimo de datos
                return False

            # ---- Criterios Fundamentales ----
            try:
                fund = self.ib.reqFundamentalData(contract, 'ReportsFinSummary')
                if fund:
                    # Si tienes un parser XML para fund, úsalo aquí
                    # Ejemplo placeholder:
                    debt_to_equity = float(fund.get('debtToEquity', 1)) if hasattr(fund, 'get') else 1
                    if debt_to_equity > 0.5:
                        return False
                else:
                    print(f"[INFO] No fundamental data for {symbol}, solo se aplican filtros técnicos.")
            except Exception as e:
                print(f"[INFO] No fundamental data for {symbol}: {e} (solo filtros técnicos)")
                # No return, sigue con filtros técnicos

            # ---- Criterios Técnicos ----
            df['rsi_14'] = ta.RSI(df['close'], 14)
            df['atr_14'] = ta.ATR(df['high'], df['low'], df['close'], 14)
            df['adv_20'] = df['volume'].rolling(20).mean()
            
            last_close = df['close'].iloc[-1]
            last_volume = df['volume'].iloc[-1]

            # Filtros (ajustables):
            filters = {
                'liquidity': last_volume > 0.5 * df['adv_20'].iloc[-1],
                'volatility': (df['atr_14'].iloc[-1] / last_close) > 0.02,
                'momentum': (df['rsi_14'].iloc[-1] < 65) and (last_close > df['close'].rolling(50).mean().iloc[-1]),
                'price': 10 <= last_close <= 50,
                'spread': self.get_current_spread(symbol) < 0.005 * last_close
            }
            
            return all(filters.values())
            
        except Exception as e:
            print(f"Error filtrando {symbol}: {str(e)}")
            return False

    def get_current_spread(self, symbol):
        """Calcula el spread bid-ask en tiempo real"""
        contract = Stock(symbol, 'SMART', 'USD')
        ticker = self.ib.reqMktData(contract)
        self.ib.sleep(2)
        return (ticker.ask - ticker.bid) / ticker.midpoint()

    def scan_top_candidates(self, n=20):
        """Retorna los mejores n tickers según score"""
        scored = []
        for symbol in self.universe[:500]:  # Limitar para demo
            if self.apply_filters(symbol):
                # Score = Volatilidad + Momentum + Liquidez
                bars = self.ib.reqHistoricalData(...)  # Obtener datos nuevamente
                score = (
                    0.4 * (ta.ATR(bars.high, bars.low, bars.close, 14)[-1] / bars.close[-1]) +
                    0.3 * (bars.close[-1] / bars.close.rolling(50).mean()[-1] - 1) +
                    0.3 * np.log(bars.volume[-1] / bars.volume.rolling(20).mean()[-1])
                )
                scored.append((symbol, score))
        
        # Ordenar y seleccionar top N
        scored.sort(key=lambda x: x[1], reverse=True)
        return [x[0] for x in scored[:n]]

# ---- Uso ----
if __name__ == "__main__":
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)
    
    screener = SmallCapScreener(ib)
    top_symbols = screener.scan_top_candidates(n=15)
    print("Top Small Caps para operar hoy:", top_symbols)
    
    ib.disconnect()