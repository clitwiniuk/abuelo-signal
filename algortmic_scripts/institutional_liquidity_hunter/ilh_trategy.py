import numpy as np
import pandas as pd
from ib_insync import *
import talib as ta
import pytz
from datetime import datetime, time

class ILHStrategy:
    def __init__(self, ib_client, capital=500):
        self.ib = ib_client
        self.capital = capital
        self.timezone = pytz.timezone('US/Eastern')
        
    def detect_icebergs(self, symbol):
        """Detecta órdenes ocultas mediante el análisis del order book"""
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.reqMarketDataType(3)  # Frozen market data
        
        # Obtener order book (niveles 2)
        book = self.ib.reqMktDepth(contract, numRows=5)
        self.ib.sleep(2)  # Esperar datos
        
        # Análisis de liquidez
        bid_vol = sum(level.size for level in book.bids)
        ask_vol = sum(level.size for level in book.asks)
        imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        
        # Iceberg detection (órdenes grandes en el book)
        largest_bid = max(level.size for level in book.bids)
        largest_ask = max(level.size for level in book.asks)
        is_iceberg = largest_bid > 5 * np.mean([level.size for level in book.bids][1:])
        
        return {
            'imbalance': imbalance,
            'iceberg': is_iceberg,
            'spread': book.asks[0].price - book.bids[0].price
        }

    def check_liquidity_gap(self, symbol):
        """Identifica gaps de liquidez en el tape"""
        trades = self.ib.reqHistoricalTicks(
            Stock(symbol, 'SMART', 'USD'),
            startDateTime='',
            endDateTime='',
            numberOfTicks=1000,
            whatToShow='TRADES'
        )
        df = util.df(trades)
        
        if len(df) < 100:
            return False
            
        # Calcula el liquidity gap
        df['mid'] = (df['price'].shift(1) + df['price']) / 2
        df['gap'] = df['price'].diff().abs() > 2 * df['mid'].rolling(10).std()
        recent_gaps = df['gap'].tail(5).sum()
        
        return recent_gaps >= 2  # Múltiples gaps recientes

    def get_regime(self, symbol):
        """Clasifica el régimen de mercado (HMM simplificado)"""
        bars = self.ib.reqHistoricalData(
            Stock(symbol, 'SMART', 'USD'),
            endDateTime='',
            durationStr='5 D',
            barSizeSetting='1 hour',
            whatToShow='TRADES'
        )
        df = util.df(bars)
        
        # Features para clasificación
        atr = ta.ATR(df['high'], df['low'], df['close'], 14)[-1]
        rsi = ta.RSI(df['close'], 14)[-1]
        volume_change = df['volume'].pct_change()[-1]
        
        if (atr > 0.02 * df['close'].mean()) and (volume_change > 0.5):
            return 'trending'
        elif (rsi < 35) or (rsi > 65):
            return 'reversal'
        else:
            return 'neutral'

    def execute_trade(self, symbol):
        """Lógica principal de trading"""
        # Filtros iniciales
        if not self.is_trading_hours() or self.has_earnings(symbol):
            return False
            
        # Análisis de mercado
        regime = self.get_regime(symbol)
        book_data = self.detect_icebergs(symbol)
        liquidity_gap = self.check_liquidity_gap(symbol)
        
        # Condiciones de entrada
        entry_conditions = {
            'trending': (
                book_data['imbalance'] > 0.3 and 
                book_data['spread'] < 0.005 * book_data['asks'][0].price
            ),
            'reversal': (
                liquidity_gap and 
                book_data['iceberg'] and
                book_data['imbalance'] < -0.2
            ),
            'neutral': False  # No operar en mercados planos
        }
        
        if not entry_conditions.get(regime, False):
            return False
            
        # Ejecución
        contract = Stock(symbol, 'SMART', 'USD')
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting='5 mins',
            whatToShow='TRADES'
        )
        df = util.df(bars)
        
        # Risk management
        atr = ta.ATR(df['high'], df['low'], df['close'], 14)[-1]
        entry = df['close'].iloc[-1]
        stop_loss = entry - (1.5 * atr if regime == 'trending' else 0.8 * atr)
        take_profit = entry + (3.0 * atr if regime == 'trending' else 1.5 * atr)
        
        # Order placement (OCO Bracket)
        bracket = self.ib.bracketOrder(
            action='BUY',
            quantity=int((self.capital * 0.01) / (entry - stop_loss)),
            limitPrice=entry,
            takeProfitPrice=take_profit,
            stopLossPrice=stop_loss
        )
        return self.ib.placeOrder(contract, bracket[0])

    # ---- Utilities ----
    def is_trading_hours(self):
        now = datetime.now(self.timezone).time()
        return time(9, 45) <= now <= time(11, 30) or time(13, 15) <= now <= time(15, 45)

    def has_earnings(self, symbol):
        # Implementar con API de earnings (ej. AlphaVantage)
        return False

# ---- Uso ----
if __name__ == "__main__":
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)
    
    # Small caps pre-filtradas (ejemplo)
    symbols = ['MRNS', 'AVRO', 'CRNX', 'KNSA', 'RAPT', 'ATRI', 'CORT', 'LXRX']
    
    strategy = ILHStrategy(ib)
    for symbol in symbols:
        print(f"Procesando {symbol}...")
        strategy.execute_trade(symbol)
    
    ib.disconnect()