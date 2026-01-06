#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LIQUIDITY SURGE MOMENTUM STRATEGY (v2.0)
By: QuantEdge
"""
import ibapi
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import *
from ibapi.scanner import ScannerSubscription
from ibapi.common import *
import pandas as pd
import numpy as np
import logging
import sqlite3
from datetime import datetime, timedelta
import pytz
import threading
import time
import yfinance as yf  # Fallback para fundamentales
from typing import Dict, List, Optional

# ============= CONFIGURACIÓN AVANZADA =============
class Config:
    IBKR_HOST = "127.0.0.1"
    IBKR_PORT = 7497  # 7496 para paper trading
    CLIENT_ID = 9999  # ID único
    
    # Filtros de mercado
    MIN_MARKET_CAP = 2e9  # $2B (excluir small caps)
    MIN_AVG_VOLUME = 2e6  # 2M acciones/día
    MAX_PRICE = 500  # Excluir acciones muy caras
    
    # Parámetros de la estrategia
    ENTRY_MOMENTUM_DAYS = 90  # Lookback momentum (3 meses)
    MIN_VOLATILITY_CHANGE = 0.3  # +30% vs media 20d
    LIQUIDITY_SURGE_RATIO = 1.8  # Volumen 80% > promedio
    
    # Gestión de riesgo (ajustado para mayor riesgo)
    RISK_PER_TRADE = 0.03  # 3% por operación
    MAX_DRAWDOWN = 0.20  # 20% de stop global
    PROFIT_TARGETS = [0.05, 0.10]  # Take profit escalonado
    
    # Base de datos y logs
    DB_PATH = "lsm_trades.db"
    LOG_PATH = "lsm_strategy.log"

# ============= SETUP PROFESIONAL =============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(Config.LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LSM_Strategy")

class TradeDB:
    """Base de datos SQLite para registro de operaciones"""
    def __init__(self):
        self.conn = sqlite3.connect(Config.DB_PATH)
        self._create_tables()
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY,
            symbol TEXT,
            signal_type TEXT,
            price REAL,
            timestamp DATETIME,
            momentum_score REAL,
            liquidity_ratio REAL,
            volatility_change REAL
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY,
            symbol TEXT,
            entry_time DATETIME,
            exit_time DATETIME,
            entry_price REAL,
            exit_price REAL,
            quantity INTEGER,
            pnl REAL,
            pnl_pct REAL,
            stop_price REAL,
            status TEXT,
            sharpe_ratio REAL
        )
        """)
        self.conn.commit()
    
    def log_signal(self, data: Dict):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO signals VALUES (
            NULL, ?, ?, ?, ?, ?, ?, ?
        )
        """, (
            data["symbol"],
            data["signal_type"],
            data["price"],
            data["timestamp"],
            data["momentum_score"],
            data["liquidity_ratio"],
            data["volatility_change"]
        ))
        self.conn.commit()
    
    def log_trade(self, data: Dict):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO trades VALUES (
            NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """, (
            data["symbol"],
            data["entry_time"],
            data["exit_time"],
            data["entry_price"],
            data["exit_price"],
            data["quantity"],
            data["pnl"],
            data["pnl_pct"],
            data["stop_price"],
            data["status"],
            data["sharpe_ratio"]
        ))
        self.conn.commit()

db = TradeDB()

# ============= ESTRATEGIA PRINCIPAL =============
class LiquiditySurgeMomentum(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.logger = logger
        self.db = db
        self.next_order_id = 1
        self.active_positions = {}
        self.pending_orders = {}
        self.universe = []
        self.account_value = 100_000  # Capital inicial (ajustar)
        
        # Datos de mercado
        self.historical_data = {}
        self.fundamentals = {}
        self.current_prices = {}
        
        # Conectar a IBKR
        self.connect(Config.IBKR_HOST, Config.IBKR_PORT, Config.CLIENT_ID)
        threading.Thread(target=self.run).start()
    
    # ----------- Métodos principales -----------
    def nextValidId(self, orderId: int):
        self.next_order_id = orderId
        self.logger.info(f"Conectado a IBKR. Next Order ID: {orderId}")
        self._initialize_strategy()
    
    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106]:  # Ignorar mensajes informativos
            self.logger.error(f"IBKR Error {errorCode}: {errorString}")
    
    def _initialize_strategy(self):
        """Inicia el flujo de la estrategia"""
        self.reqAccountUpdates(True, "")
        self._refresh_universe()
        
        # Programar actualización periódica
        self._schedule_tasks()
    
    def _schedule_tasks(self):
        """Programa tareas recurrentes"""
        threading.Timer(3600, self._check_positions).start()  # Cada hora
        threading.Timer(86400, self._refresh_universe).start()  # Diario
    
    # ----------- Gestión del universo -----------
    def _refresh_universe(self):
        """Actualiza la lista de acciones candidatas"""
        self.logger.info("Actualizando universo...")
        
        scanner = ScannerSubscription()
        scanner.instrument = "STK"
        scanner.locationCode = "STK.US.NASDAQ"
        scanner.scanCode = "HOT_BY_VOLUME"
        scanner.marketCapAbove = Config.MIN_MARKET_CAP
        scanner.avgVolumeAbove = Config.MIN_AVG_VOLUME
        scanner.abovePrice = 10  # Excluir penny stocks
        scanner.belowPrice = Config.MAX_PRICE
        
        self.reqScannerSubscription(1, scanner, [], [])
    
    def scannerData(self, reqId, rank, contractDetails, distance, benchmark, projection, legsStr):
        symbol = contractDetails.contract.symbol
        self.universe.append(symbol)
        self.logger.debug(f"Ticker añadido: {symbol}")
        
        # Obtener datos adicionales
        self._fetch_historical_data(symbol)
        self._fetch_fundamentals(symbol)
    
    def scannerDataEnd(self, reqId):
        self.logger.info(f"Universo actualizado. {len(self.universe)} tickers.")
        self._generate_signals()
    
    # ----------- Obtención de datos -----------
    def _fetch_historical_data(self, symbol: str):
        """Obtiene datos históricos para cálculo de momentum"""
        contract = self._create_contract(symbol)
        end_date = datetime.now().strftime("%Y%m%d %H:%M:%S")
        
        self.reqHistoricalData(
            reqId=self.next_order_id,
            contract=contract,
            endDateTime=end_date,
            durationStr=f"{Config.ENTRY_MOMENTUM_DAYS} D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[]
        )
        self.next_order_id += 1
    
    def _fetch_fundamentals(self, symbol: str):
        """Obtiene datos fundamentales como fallback"""
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            self.fundamentals[symbol] = {
                "roic": info.get("returnOnInvestedCapital", 0),
                "debtToEquity": info.get("debtToEquity", 0)
            }
        except Exception as e:
            self.logger.warning(f"Error al obtener fundamentales para {symbol}: {e}")
    
    def historicalData(self, reqId, bar):
        symbol = list(self.historical_data.keys())[reqId - 1]
        if symbol not in self.historical_data:
            self.historical_data[symbol] = []
        self.historical_data[symbol].append(bar.close)
    
    # ----------- Generación de señales -----------
    def _generate_signals(self):
        """Calcula señales de compra/venta"""
        for symbol in self.universe:
            if symbol not in self.historical_data or len(self.historical_data[symbol]) < 20:
                continue
                
            # Calcular métricas clave
            prices = pd.Series(self.historical_data[symbol])
            returns = prices.pct_change().dropna()
            
            momentum_score = (prices.iloc[-1] / prices.iloc[0] - 1) * 100  # Retorno %
            volatility = returns.std() * np.sqrt(252)  # Volatilidad anualizada
            current_vol = returns[-20:].std() * np.sqrt(252)
            vol_change = (current_vol - volatility) / volatility
            
            # Liquidity surge (volumen actual vs promedio)
            contract = self._create_contract(symbol)
            self.reqMktData(self.next_order_id, contract, "", False, False, [])
            self.next_order_id += 1
            
            # Umbrales para señales
            if (momentum_score > 15 and  # Momentum positivo fuerte
                vol_change > Config.MIN_VOLATILITY_CHANGE and  # Volatilidad creciente
                self.fundamentals.get(symbol, {}).get("roic", 0) > 0.10):  # ROIC >10%
                
                signal_data = {
                    "symbol": symbol,
                    "signal_type": "BUY",
                    "price": prices.iloc[-1],
                    "timestamp": datetime.now().isoformat(),
                    "momentum_score": momentum_score,
                    "liquidity_ratio": 0,  # Se actualiza con market data
                    "volatility_change": vol_change
                }
                self.db.log_signal(signal_data)
                self._place_trade(symbol, prices.iloc[-1])
    
    def tickPrice(self, reqId, tickType, price, attrib):
        """Procesa datos de mercado en tiempo real"""
        symbol = self.universe[reqId - 1]
        self.current_prices[symbol] = price
        
        # Calcular ratio de liquidez (volumen actual / promedio)
        if tickType == 8:  # Volume
            avg_volume = np.mean([d.volume for d in self.historical_data.get(symbol, [])])
            liquidity_ratio = price / avg_volume if avg_volume > 0 else 0
            
            if liquidity_ratio > Config.LIQUIDITY_SURGE_RATIO:
                self.logger.info(f"Liquidity surge detectado en {symbol}: {liquidity_ratio:.2f}x")
    
    # ----------- Ejecución de trades -----------
    def _place_trade(self, symbol: str, price: float):
        """Envía una orden con gestión de riesgo"""
        if symbol in self.active_positions:
            return
            
        # Calcular tamaño de posición
        account_risk = self.account_value * Config.RISK_PER_TRADE
        atr = np.mean([d.high - d.low for d in self.historical_data.get(symbol, [])][-14:])
        stop_loss = price - 1.5 * atr
        position_size = int(account_risk / (price - stop_loss))
        
        # Crear orden bracket (OCO)
        parent = Order()
        parent.orderId = self.next_order_id
        parent.action = "BUY"
        parent.orderType = "LMT"
        parent.totalQuantity = position_size
        parent.lmtPrice = price * 0.995  # Mejora el precio en 0.5%
        parent.transmit = False
        
        take_profit1 = Order()
        take_profit1.orderId = self.next_order_id + 1
        take_profit1.action = "SELL"
        take_profit1.orderType = "LMT"
        take_profit1.totalQuantity = position_size // 2
        take_profit1.lmtPrice = price * (1 + Config.PROFIT_TARGETS[0])
        take_profit1.parentId = parent.orderId
        take_profit1.transmit = False
        
        take_profit2 = Order()
        take_profit2.orderId = self.next_order_id + 2
        take_profit2.action = "SELL"
        take_profit2.orderType = "TRAIL"
        take_profit2.totalQuantity = position_size // 2
        take_profit2.trailingPercent = 5  # Trailing stop 5%
        take_profit2.parentId = parent.orderId
        take_profit2.transmit = True
        
        self.placeOrder(parent.orderId, self._create_contract(symbol), parent)
        self.placeOrder(take_profit1.orderId, self._create_contract(symbol), take_profit1)
        self.placeOrder(take_profit2.orderId, self._create_contract(symbol), take_profit2)
        
        self.next_order_id += 3
        self.active_positions[symbol] = {
            "entry_price": price,
            "stop_loss": stop_loss,
            "size": position_size
        }
        
        self.logger.info(f"Orden enviada para {symbol}: {position_size} acciones a ${price:.2f}")
    
    # ----------- Utilidades -----------
    def _create_contract(self, symbol: str) -> Contract:
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract
    
    def _check_positions(self):
        """Monitorea stops y cierra posiciones"""
        for symbol, pos in list(self.active_positions.items()):
            if self.current_prices.get(symbol, 0) < pos["stop_loss"]:
                self._close_position(symbol, "STOP_LOSS")
    
    def _close_position(self, symbol: str, reason: str):
        """Cierra una posición existente"""
        if symbol not in self.active_positions:
            return
            
        pos = self.active_positions.pop(symbol)
        contract = self._create_contract(symbol)
        
        order = Order()
        order.orderId = self.next_order_id
        order.action = "SELL"
        order.orderType = "MKT"
        order.totalQuantity = pos["size"]
        self.placeOrder(order.orderId, contract, order)
        
        self.next_order_id += 1
        self.logger.info(f"Cerrando {symbol} por {reason}")

# ============= EJECUCIÓN =============
if __name__ == "__main__":
    strategy = LiquiditySurgeMomentum()
    
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        strategy.logger.warning("Deteniendo estrategia...")
        strategy.disconnect()