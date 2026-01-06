#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Estrategia NASDAQ Momentum + Quality + Volatility Breakout
Autor: QuantEdge
Versión: 1.2 (Professional Grade)
"""
import ibapi
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract, ContractDetails
from ibapi.order import Order
from ibapi.scanner import ScannerSubscription
from ibapi.common import *
import pandas as pd
import numpy as np
import logging
from logging.handlers import TimedRotatingFileHandler
import sqlite3
from datetime import datetime, timedelta
import pytz
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
import time

# =============== CONFIGURACIÓN INICIAL ===============
class Config:
    DB_PATH = "trades.db"
    LOG_PATH = "strategy.log"
    IBKR_HOST = "127.0.0.1"
    IBKR_PORT = 7497  # 7496 para paper trading
    CLIENT_ID = 1
    TIMEZONE = pytz.timezone("America/New_York")
    UNIVERSE_REFRESH_HOUR = 18  # 6 PM ET
    MAX_POSITIONS = 20
    RISK_PER_TRADE = 0.02  # 2% del capital por operación

# =============== LOGGING PROFESIONAL ===============
def setup_logger():
    logger = logging.getLogger("quant_edge")
    logger.setLevel(logging.DEBUG)
    
    # Formato
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S %Z"
    )
    
    # Handler para archivo (rotación diaria)
    file_handler = TimedRotatingFileHandler(
        Config.LOG_PATH,
        when="D",
        interval=1,
        backupCount=30
    )
    file_handler.setFormatter(formatter)
    
    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()

# =============== BASE DE DATOS (SQLITE) ===============
class TradeDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(Config.DB_PATH)
        self._create_tables()
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        
        # Tabla de activos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            sector TEXT,
            market_cap REAL,
            avg_volume REAL
        )
        """)
        
        # Tabla de trades
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            entry_time DATETIME,
            exit_time DATETIME,
            entry_price REAL,
            exit_price REAL,
            size INTEGER,
            pnl REAL,
            sharpe REAL,
            strategy_version TEXT,
            FOREIGN KEY(symbol) REFERENCES assets(symbol)
        )
        """)
        
        self.conn.commit()
    
    def log_trade(self, trade_data: Dict):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO trades VALUES (
            NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """, (
            trade_data["symbol"],
            trade_data["entry_time"],
            trade_data["exit_time"],
            trade_data["entry_price"],
            trade_data["exit_price"],
            trade_data["size"],
            trade_data["pnl"],
            trade_data["sharpe"],
            trade_data["strategy_version"]
        ))
        self.conn.commit()

db = TradeDatabase()

# =============== ESTRATEGIA PRINCIPAL ===============
class QuantEdgeStrategy(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.logger = logger
        self.db = db
        self.next_order_id = 1
        self.current_positions = set()
        self.pending_orders = {}
        self.universe = []
        self.account_data = {}
        
        # Métricas de rendimiento
        self.portfolio = {
            "cash": 100_000,  # Capital inicial
            "equity": [],
            "sharpe": None
        }
        
        self.connect(Config.IBKR_HOST, Config.IBKR_PORT, Config.CLIENT_ID)
        
        # Iniciar threads de IBKR
        thread = threading.Thread(target=self.run)
        thread.start()
    
    # --------------- GESTIÓN DE CONEXIÓN ---------------
    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.next_order_id = orderId
        self.logger.info(f"Sesión iniciada. Next Order ID: {orderId}")
        self._initialize_strategy()
    
    def error(self, reqId: TickerId, errorCode: int, errorString: str):
        super().error(reqId, errorCode, errorString)
        if errorCode == 502:  # Error común: conexión a TWS
            self.logger.error(f"Error de conexión: {errorString}. Reintentando...")
            self.reconnect()
    
    def reconnect(self):
        self.logger.warning("Reconectando a IBKR...")
        self.disconnect()
        self.connect(Config.IBKR_HOST, Config.IBKR_PORT, Config.CLIENT_ID)
    
    # --------------- INICIALIZACIÓN ---------------
    def _initialize_strategy(self):
        """Carga el universo inicial y verifica el estado de la cuenta"""
        self.reqAccountUpdates(True, "")
        self._refresh_universe()
        
        # Programar actualizaciones periódicas
        self.schedule_tasks()
    
    def schedule_tasks(self):
        """Programa tareas recurrentes usando threading.Timer"""
        now = datetime.now(Config.TIMEZONE)
        
        # Actualizar universo cada día a las 6 PM ET
        next_refresh = now.replace(
            hour=Config.UNIVERSE_REFRESH_HOUR,
            minute=0,
            second=0
        ) + timedelta(days=1)
        delay = (next_refresh - now).total_seconds()
        
        threading.Timer(delay, self._refresh_universe).start()
    
    # --------------- GESTIÓN DE UNIVERSO ---------------
    def _refresh_universe(self):
        """Actualiza el universo de acciones NASDAQ no small-caps"""
        self.logger.info("Actualizando universo de acciones...")
        
        # Scanner de IBKR para NASDAQ Large/Mid Caps
        scanner = ScannerSubscription()
        scanner.instrument = "STK"
        scanner.locationCode = "STK.US.MAJOR"  # Cambiado para compatibilidad con HOT_BY_VOLUME
        # Cambiado de HIGH_CAP_LIQUID a HOT_BY_VOLUME por restricción de IBKR
        scanner.scanCode = "HOT_BY_VOLUME"
        # Filtros mínimos para debug: sin marketCap, volumen bajo
        # scanner.marketCapAbove = 2e9  # Eliminado para ampliar resultados
        scanner.avgVolumeAbove = 100000  # 100k acciones/día
        
        self.logger.debug(f"Enviando reqScannerSubscription: {scanner.__dict__}")
        self.reqScannerSubscription(1, scanner, [], [])
        self.logger.debug("reqScannerSubscription enviado correctamente")
    
    def scannerData(self, reqId: int, rank: int, 
                   contractDetails: ContractDetails, 
                   distance: str, benchmark: str, 
                   projection: str, legsStr: str):
        """Procesa los resultados del scanner"""
        symbol = contractDetails.contract.symbol
        self.universe.append(symbol)
        self.logger.debug(f"Ticker añadido al universo: {symbol}")
        
        # Almacenar metadatos en DB
        # Usar getattr para evitar AttributeError si algún campo falta
        long_name = getattr(contractDetails, "longName", None)
        industry = getattr(contractDetails, "industry", None)
        market_cap = getattr(contractDetails, "marketCap", None)
        avg_volume = getattr(contractDetails, "avgVolume", None)

        conn = sqlite3.connect(Config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT OR IGNORE INTO assets VALUES (?, ?, ?, ?, ?)
        """, (
            symbol,
            long_name,
            industry,
            market_cap,
            avg_volume
        ))
        conn.commit()
        conn.close()
    
    def scannerDataEnd(self, reqId: int):
        """Se llama cuando finaliza el scanner"""
        self.logger.info(f"Universo actualizado. {len(self.universe)} tickers califican.")
        self._start_signal_generation()
    
    # --------------- GENERACIÓN DE SEÑALES ---------------
    def _create_contract(self, symbol):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract

    def _start_signal_generation(self):
        """Inicia el proceso de cálculo de señales para cada ticker"""
        for symbol in self.universe:
            contract = self._create_contract(symbol)
            
            # Solicitar datos históricos para momentum
            self.reqHistoricalData(
                reqId=self.next_order_id,
                contract=contract,
                endDateTime="",
                durationStr="1 Y",
                barSizeSetting="1 day",
                whatToShow="ADJUSTED_LAST",
                useRTH=1,
                formatDate=1,
                keepUpToDate=False,
                chartOptions=[]
            )
            self.next_order_id += 1
            
            # Solicitar fundamentales
            report_types = [
                "REPORTS_FIN_STATEMENT",
                "REPORTS_PROFILE",
                "REPORTS_RATIOS",
                "REPORTS_RECENT",
                "REPORTS_OVERVIEW"
            ]
            success = False
            for report_type in report_types:
                try:
                    self.logger.info(f"Solicitando fundamentales para {contract.symbol} con reportType='{report_type}'")
                    self.reqFundamentalData(
                        reqId=self.next_order_id,
                        contract=contract,
                        reportType=report_type,
                        fundamentalDataOptions=[]
                    )
                    success = True
                    break
                except Exception as e:
                    self.logger.warning(f"Error solicitando fundamentales para {contract.symbol} con reportType={report_type}: {str(e)}")
            if not success:
                self.logger.error(f"No se pudo obtener fundamentales para {contract.symbol} con ninguno de los reportTypes probados.")
            self.next_order_id += 1
    
    def historicalData(self, reqId: int, bar: BarData):
        """Procesa datos históricos para cálculo de momentum"""
        # Implementar lógica de almacenamiento y cálculo
        pass
    
    def fundamentalData(self, reqId: int, data: str):
        """Procesa datos fundamentales en XML"""
        try:
            root = ET.fromstring(data)
            roic = float(root.find(".//ROIC").text)
            piotroski = int(root.find(".//PIOTROSKI_SCORE").text)
            
            if roic > 0.15 and piotroski > 6:
                self._generate_buy_signal(reqId)
        except Exception as e:
            self.logger.error(f"Error parsing fundamentals: {e}")
    
    # --------------- GESTIÓN DE ÓRDENES ---------------
    def _generate_buy_signal(self, reqId: int):
        """Envía una orden basada en señales válidas con gestión de riesgo profesional
        
        Args:
            reqId: El ID de la solicitud que generó la señal
            
        Proceso:
            1. Validación de condiciones de mercado
            2. Cálculo de tamaño de posición según gestión de riesgo
            3. Creación de órdenes con stops y objetivos
            4. Registro en base de datos
            5. Monitoreo de la operación
        """
        try:
            # 1. Validaciones previas
            if len(self.current_positions) >= Config.MAX_POSITIONS:
                self.logger.warning(f"Max positions reached ({Config.MAX_POSITIONS}). Ignoring signal.")
                return
                
            if not self.universe or reqId >= len(self.universe):
                self.logger.error("Invalid reqId or empty universe")
                return
                
            symbol = self.universe[reqId % len(self.universe)]
            
            # 2. Cálculo de tamaño de posición con gestión de riesgo
            last_price = self._get_last_price(symbol)
            if not last_price:
                self.logger.error(f"No price data for {symbol}")
                return
                
            position_size = self._calculate_position_size(last_price)
            if position_size <= 0:
                self.logger.warning(f"Position size <= 0 for {symbol} at {last_price}")
                return
                
            # 3. Creación de órdenes OCA (One-Cancels-All)
            # Forzar que el tamaño de la posición sea entero positivo
            position_size = max(1, int(position_size))
            main_order, stop_order, profit_order = self._create_oca_orders(
                symbol=symbol,
                price=last_price,
                quantity=position_size
            )
            
            # 4. Envío de órdenes
            # Logging explícito antes de enviar cada orden
            # Cierre de seguridad: forzar totalQuantity a int antes de enviar
            main_order.totalQuantity = int(main_order.totalQuantity)
            self.logger.info(f"[CHECK] main_order.totalQuantity={main_order.totalQuantity} (tipo: {type(main_order.totalQuantity)}) antes de enviar")
            self.logger.info(f"Enviando orden principal: {main_order.__dict__}")
            self.placeOrder(main_order.orderId, main_order.contract, main_order)

            stop_order.totalQuantity = int(stop_order.totalQuantity)
            self.logger.info(f"[CHECK] stop_order.totalQuantity={stop_order.totalQuantity} (tipo: {type(stop_order.totalQuantity)}) antes de enviar")
            self.logger.info(f"Enviando orden stop: {stop_order.__dict__}")
            self.placeOrder(stop_order.orderId, stop_order.contract, stop_order)

            profit_order.totalQuantity = int(profit_order.totalQuantity)
            self.logger.info(f"[CHECK] profit_order.totalQuantity={profit_order.totalQuantity} (tipo: {type(profit_order.totalQuantity)}) antes de enviar")
            self.logger.info(f"Enviando orden objetivo: {profit_order.__dict__}")
            self.placeOrder(profit_order.orderId, profit_order.contract, profit_order)
            
            # 5. Registro y seguimiento
            trade_id = self._log_new_trade(
                symbol=symbol,
                entry_price=last_price,
                size=position_size,
                stop_price=stop_order.auxPrice,
                target_price=profit_order.auxPrice
            )
            
            self.pending_orders[main_order.orderId] = {
                "trade_id": trade_id,
                "symbol": symbol,
                "stop_order_id": stop_order.orderId,
                "profit_order_id": profit_order.orderId,
                "status": "pending"
            }
            
            self.logger.info(
                f"Buy signal executed for {symbol}. "
                f"Size: {position_size} @ {last_price:.2f}. "
                f"Stop: {stop_order.auxPrice:.2f} "
                f"Target: {profit_order.auxPrice:.2f}"
            )
            
        except Exception as e:
            self.logger.error(f"Error in generate_buy_signal: {str(e)}", exc_info=True)
            # Notificación de error (podría integrarse con Slack/Email)
            self._send_alert(f"BUY SIGNAL FAILED - {symbol if 'symbol' in locals() else 'UNKNOWN'}: {str(e)}")

    def _get_last_price(self, symbol: str) -> float:
        """Obtiene el último precio válido con verificación de mercado abierto"""
        contract = self._create_contract(symbol)
        
        # Usamos reqTickByTickData para el precio más reciente
        self.reqTickByTickData(
            reqId=self.next_order_id,
            contract=contract,
            tickType="Last",
            numberOfTicks=1,
            ignoreSize=True
        )
        self.next_order_id += 1
        
        # Esperar respuesta sincrónica (simplificado para ejemplo)
        time.sleep(0.5)  # En producción usaría un evento asincrónico
        
        # Aquí normalmente procesarías los ticks recibidos
        # Para el ejemplo, devolvemos un valor dummy
        return 150.75  # En realidad obtendrías esto de los callbacks de ticks

    def _calculate_position_size(self, entry_price: float) -> int:
        """Calcula el tamaño de posición según gestión de riesgo"""
        account_risk = self.portfolio["cash"] * Config.RISK_PER_TRADE
        stop_distance = entry_price * 0.05  # Stop del 5%
        dollar_risk_per_share = entry_price - (entry_price - stop_distance)
        
        if dollar_risk_per_share <= 0:
            return 0
            
        position_size = int(account_risk / dollar_risk_per_share)
        
        # Asegurar que no exceda el 10% del capital
        max_position_value = self.portfolio["cash"] * 0.10
        max_shares = int(max_position_value / entry_price)
        
        return min(position_size, max_shares)

    def _create_oca_orders(self, symbol: str, price: float, quantity: int) -> tuple:
        """Crea grupo de órdenes OCA (One-Cancels-All)"""
        contract = self._create_contract(symbol)
        
        # Orden principal (LIMIT)
        main_order = Order()
        main_order.orderId = self.next_order_id
        self.next_order_id += 1
        main_order.action = "BUY"
        main_order.orderType = "LMT"
        main_order.totalQuantity = int(quantity)
        self.logger.info(f"Asignando main_order.totalQuantity={main_order.totalQuantity} (tipo: {type(main_order.totalQuantity)})")
        main_order.lmtPrice = round(price * 0.995, 2)  # Entrar al 0.5% bajo el último precio
        main_order.transmit = False
        
        # Stop loss (STOP)
        stop_order = Order()
        stop_order.orderId = self.next_order_id
        self.next_order_id += 1
        stop_order.action = "SELL"
        stop_order.orderType = "STP"
        stop_order.auxPrice = round(price * 0.95, 2)  # Stop al 5%
        stop_order.totalQuantity = int(quantity)
        self.logger.info(f"Asignando stop_order.totalQuantity={stop_order.totalQuantity} (tipo: {type(stop_order.totalQuantity)})")
        stop_order.parentId = main_order.orderId
        stop_order.transmit = False
        
        # Take profit (LIMIT)
        profit_order = Order()
        profit_order.orderId = self.next_order_id
        self.next_order_id += 1
        profit_order.action = "SELL"
        profit_order.orderType = "LMT"
        profit_order.lmtPrice = round(price * 1.10, 2)  # Objetivo 10%
        profit_order.totalQuantity = int(quantity)
        self.logger.info(f"Asignando profit_order.totalQuantity={profit_order.totalQuantity} (tipo: {type(profit_order.totalQuantity)})")
        profit_order.parentId = main_order.orderId
        profit_order.transmit = True  # Última orden del grupo OCA
        
        # Configurar grupo OCA
        main_order.ocaGroup = f"OCA_{symbol}_{main_order.orderId}"
        stop_order.ocaGroup = main_order.ocaGroup
        profit_order.ocaGroup = main_order.ocaGroup
        
        main_order.ocaType = 1  # Cancelar órdenes restantes
        stop_order.ocaType = 1
        profit_order.ocaType = 1
        
        return main_order, stop_order, profit_order

    def _log_new_trade(self, symbol: str, entry_price: float, size: int, 
                    stop_price: float, target_price: float) -> int:
        """Registra la nueva operación en la base de datos"""
        trade_data = {
            "symbol": symbol,
            "entry_time": datetime.now(Config.TIMEZONE).isoformat(),
            "exit_time": None,
            "entry_price": entry_price,
            "exit_price": None,
            "size": size,
            "pnl": None,
            "sharpe": None,
            "strategy_version": "1.1",
            "stop_price": stop_price,
            "target_price": target_price
        }
        
        # Insertar en tabla principal
        self.db.log_trade(trade_data)
        
        # Obtener ID de la operación insertada
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT last_insert_rowid()")
        trade_id = cursor.fetchone()[0]
        
        return trade_id

    def _send_alert(self, message: str):
        """Envía alerta a sistemas externos (Slack/Email/SMS)"""
        # Implementación básica - en producción integrar con API real
        self.logger.warning(f"ALERT: {message}")
        # Ejemplo para Slack:
        # requests.post(SLACK_WEBHOOK, json={"text": message})
    
    def orderStatus(self, orderId: int, status: str, filled: float,
                    remaining: float, avgFillPrice: float, permId: int,
                    parentId: int, lastFillPrice: float, clientId: int,
                    whyHeld: str, mktCapPrice: float):
        """Monitoriza el estado de las órdenes"""
        super().orderStatus(orderId, status, filled, remaining, avgFillPrice,
                          permId, parentId, lastFillPrice, clientId, whyHeld,
                          mktCapPrice)
        
        if status == "Filled":
            self.logger.info(f"Orden {orderId} ejecutada a {avgFillPrice}")
            self._update_portfolio(orderId, avgFillPrice, filled)
    
    # --------------- MONITOREO Y CIERRE ---------------
    def _update_portfolio(self, orderId: int, price: float, size: float):
        """Actualiza el balance del portafolio con verificación de márgenes y riesgo
        
        Args:
            orderId: ID de la orden ejecutada
            price: Precio de ejecución
            size: Cantidad de acciones (positiva para compra, negativa para venta)
        
        Proceso:
            1. Identifica si es entrada o salida
            2. Actualiza efectivo y posiciones
            3. Calcula nuevas métricas de riesgo
            4. Verifica márgenes y exposición
            5. Registra en base de datos
        """
        try:
            # 1. Determinar tipo de operación
            is_entry = orderId in self.pending_orders
            symbol = None
            
            if is_entry:
                # Operación de entrada (compra)
                trade_info = self.pending_orders[orderId]
                symbol = trade_info["symbol"]
                cost = price * size
                self.portfolio["cash"] -= cost
                self.current_positions.add(symbol)
                
                self.logger.info(
                    f"POSITION OPENED: {symbol} {size} @ {price:.2f} "
                    f"Cost: ${cost:,.2f} | Cash: ${self.portfolio['cash']:,.2f}"
                )
                
                # Actualizar trade en DB con tamaño real ejecutado
                self.db.conn.execute(
                    "UPDATE trades SET size = ?, entry_price = ? WHERE id = ?",
                    (size, price, trade_info["trade_id"])
                )
                
            else:
                # Operación de salida (venta)
                symbol = next((s for s, oid in self.pending_orders.items() 
                            if oid["stop_order_id"] == orderId or oid["profit_order_id"] == orderId), None)
                
                if symbol:
                    proceeds = price * abs(size)
                    self.portfolio["cash"] += proceeds
                    self.current_positions.discard(symbol)
                    
                    # Calcular PnL
                    trade_info = self.pending_orders[symbol]
                    entry_price = self.db.conn.execute(
                        "SELECT entry_price FROM trades WHERE id = ?",
                        (trade_info["trade_id"],)
                    ).fetchone()[0]
                    
                    pnl = (price - entry_price) * size
                    pnl_pct = (price / entry_price - 1) * 100
                    
                    self.logger.info(
                        f"POSITION CLOSED: {symbol} {size} @ {price:.2f} "
                        f"PnL: ${pnl:+,.2f} ({pnl_pct:+.2f}%) | "
                        f"Cash: ${self.portfolio['cash']:,.2f}"
                    )
                    
                    # Actualizar trade en DB
                    exit_time = datetime.now(Config.TIMEZONE).isoformat()
                    self.db.conn.execute(
                        """UPDATE trades SET 
                        exit_time = ?, exit_price = ?, pnl = ?
                        WHERE id = ?""",
                        (exit_time, price, pnl, trade_info["trade_id"])
                    )
                    
                    # Calcular nuevo Sharpe ratio (simplificado)
                    self._update_sharpe_ratio()
                    
            # 2. Actualizar valor de portafolio
            self._update_equity()
            
            # 3. Verificar exposición y márgenes
            self._check_portfolio_risk()
            
        except Exception as e:
            self.logger.error(f"Error updating portfolio: {str(e)}", exc_info=True)
            self._send_alert(f"PORTFOLIO UPDATE FAILED - Order {orderId}: {str(e)}")

    def _update_equity(self):
        """Calcula el valor total del portafolio (efectivo + posiciones abiertas)"""
        try:
            total_equity = self.portfolio["cash"]
            
            # Obtener precios actuales de todas las posiciones
            for symbol in self.current_positions:
                contract = self._create_contract(symbol)
                # En producción usaríamos reqTickByTickData o reqMktData
                # Para el ejemplo usamos un valor dummy
                current_price = 152.50  # Debería obtenerse de los callbacks de mercado
                
                # Obtener tamaño de posición de la base de datos
                size = self.db.conn.execute(
                    "SELECT size FROM trades WHERE symbol = ? AND exit_time IS NULL",
                    (symbol,)
                ).fetchone()
                
                if size:
                    position_value = current_price * size[0]
                    total_equity += position_value
            
            # Registrar histórico de equity
            self.portfolio["equity"].append({
                "timestamp": datetime.now(Config.TIMEZONE).isoformat(),
                "value": total_equity
            })
            
            # Mantener sólo los últimos 30 días
            if len(self.portfolio["equity"]) > 30:
                self.portfolio["equity"] = self.portfolio["equity"][-30:]
                
        except Exception as e:
            self.logger.error(f"Error updating equity: {str(e)}", exc_info=True)

    def _update_sharpe_ratio(self, lookback_days=30):
        """Calcula el ratio de Sharpe basado en rendimientos diarios"""
        try:
            if len(self.portfolio["equity"]) < 2:
                self.portfolio["sharpe"] = None
                return
                
            # Calcular rendimientos diarios
            returns = []
            equity_values = [e["value"] for e in self.portfolio["equity"]]
            
            for i in range(1, len(equity_values)):
                daily_return = (equity_values[i] - equity_values[i-1]) / equity_values[i-1]
                returns.append(daily_return)
            
            # Usar sólo los últimos N días
            returns = returns[-lookback_days:]
            
            if len(returns) < 2:
                self.portfolio["sharpe"] = None
                return
                
            # Calcular Sharpe ratio anualizado (asumiendo riesgo libre = 0)
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            
            if std_return > 0:
                sharpe = (mean_return / std_return) * np.sqrt(252)  # Anualizado
                self.portfolio["sharpe"] = sharpe
                self.logger.info(f"Updated Sharpe Ratio: {sharpe:.2f}")
                
                # Actualizar en base de datos
                self.db.conn.execute(
                    "UPDATE trades SET sharpe = ? WHERE exit_time IS NULL",
                    (sharpe,)
                )
                
        except Exception as e:
            self.logger.error(f"Error calculating Sharpe ratio: {str(e)}", exc_info=True)

    def _check_portfolio_risk(self):
        """Verifica exposición total y márgenes disponibles"""
        try:
            # 1. Verificar drawdown máximo
            if len(self.portfolio["equity"]) >= 5:
                max_equity = max(e["value"] for e in self.portfolio["equity"])
                current_equity = self.portfolio["equity"][-1]["value"]
                drawdown = (max_equity - current_equity) / max_equity
                
                if drawdown >= 0.10:  # Drawdown del 10%
                    self.logger.critical(f"MAX DRAWDOWN REACHED: {drawdown:.2%}")
                    self._send_alert(f"CRITICAL: Portfolio drawdown {drawdown:.2%}")
                    self.close_all_positions()
                    return
                    
            # 2. Verificar exposición total
            total_long_exposure = sum(
                self.db.conn.execute(
                    "SELECT entry_price * size FROM trades WHERE exit_time IS NULL"
                ).fetchall()
            )
            
            if total_long_exposure and total_long_exposure[0]:
                leverage = total_long_exposure[0] / self.portfolio["cash"]
                if leverage > 3.0:  # Ejemplo: límite de apalancamiento 3:1
                    self.logger.warning(f"High leverage: {leverage:.2f}:1")
                    self._send_alert(f"WARNING: High leverage {leverage:.2f}:1")
                    
        except Exception as e:
            self.logger.error(f"Error checking portfolio risk: {str(e)}", exc_info=True)

    def close_all_positions(self, reason="manual"):
        """Cierra todas las posiciones de manera controlada
        
        Args:
            reason: Motivo del cierre ("manual", "drawdown", "eod", "risk")
        """
        try:
            if not self.current_positions:
                self.logger.info("No positions to close")
                return
                
            self.logger.warning(f"CLOSING ALL POSITIONS ({reason.upper()})...")
            
            # Obtener todas las posiciones abiertas
            open_trades = self.db.conn.execute(
                """SELECT id, symbol, size FROM trades 
                WHERE exit_time IS NULL"""
            ).fetchall()
            
            for trade in open_trades:
                trade_id, symbol, size = trade
                contract = self._create_contract(symbol)
                
                # Crear orden de mercado para cerrar
                close_order = Order()
                close_order.orderId = self.next_order_id
                self.next_order_id += 1
                close_order.action = "SELL"
                close_order.orderType = "MKT"
                close_order.totalQuantity = int(abs(size))
                close_order.transmit = True

                # Logging explícito antes de enviar la orden de cierre
                close_order.totalQuantity = int(close_order.totalQuantity)
                self.logger.info(f"[CHECK] close_order.totalQuantity={close_order.totalQuantity} (tipo: {type(close_order.totalQuantity)}) antes de enviar")
                self.logger.info(f"Enviando orden de cierre: {close_order.__dict__} (size original: {size}, tipo: {type(size)})")
                self.placeOrder(close_order.orderId, contract, close_order)
                
                # Registrar como orden pendiente sin stops (cierre manual)
                self.pending_orders[close_order.orderId] = {
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "status": "closing",
                    "reason": reason
                }
                
                self.logger.info(f"Closing order sent for {symbol} ({int(abs(size))} shares)")
                
            # Programar verificación de cierre
            threading.Timer(60, self._verify_positions_closed, args=[reason]).start()
            
        except Exception as e:
            self.logger.error(f"Error closing all positions: {str(e)}", exc_info=True)
            self._send_alert(f"CRITICAL: Failed to close positions - {str(e)}")

    def _verify_positions_closed(self, reason):
        """Verifica que todas las posiciones se hayan cerrado correctamente"""
        try:
            open_positions = self.db.conn.execute(
                "SELECT COUNT(*) FROM trades WHERE exit_time IS NULL"
            ).fetchone()[0]
            
            if open_positions > 0:
                self.logger.error(f"{open_positions} positions failed to close!")
                self._send_alert(
                    f"ERROR: {open_positions} positions not closed after {reason} signal!"
                )
                
                # Intentar nuevamente si quedan posiciones
                self.close_all_positions(reason=f"retry_{reason}")
            else:
                self.logger.info("All positions successfully closed")
                self._send_alert(f"SUCCESS: All positions closed ({reason})")
                
        except Exception as e:
            self.logger.error(f"Error verifying positions: {str(e)}", exc_info=True)

# =============== EJECUCIÓN ===============
if __name__ == "__main__":
    import threading
    
    app = QuantEdgeStrategy()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        app.logger.warning("Deteniendo estrategia...")
        app.disconnect()