import logging
from datetime import datetime
from typing import List, Optional
import pandas as pd
from ib_async import *
from ib_async.contract import Contract, Stock
from ib_async.order import Order, MarketOrder, LimitOrder, StopOrder
from ib_async.client import Client

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('IBKR Trading App')


class TradingApp:
    def __init__(self, host: str = '127.0.0.1', port: int = 7497, client_id: int = 1):
        """Inicializa la aplicación de trading con IBKR."""
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = None
        self.connected = False
        self.current_contract = None
        self.current_market_data = None
        self.account = None

    def connect(self) -> bool:
        """Establece conexión con TWS/IB Gateway."""
        try:
            util.startLoop()  # Necesario para entornos que no son asyncio
            
            self.ib = IB()
            self.ib.connect(self.host, self.port, self.client_id)
            
            # Verificar conexión
            if not self.ib.isConnected():
                logger.error("No se pudo establecer conexión con IBKR")
                return False
            
            self.connected = True
            logger.info(f"Conectado a IBKR en {self.host}:{self.port} (ClientID: {self.client_id})")
            
            # Obtener información de la cuenta (primera disponible)
            self.account = self.ib.managedAccounts()[0] if self.ib.managedAccounts() else None
            if self.account:
                logger.info(f"Cuenta configurada: {self.account}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error al conectar con IBKR: {str(e)}")
            self.connected = False
            return False

    def disconnect(self):
        """Cierra la conexión con IBKR."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            self.connected = False
            logger.info("Desconectado de IBKR")

    def search_contract(self, symbol: str, exchange: str = 'SMART', currency: str = 'USD') -> Optional[Contract]:
        """Busca y califica un contrato de acción."""
        if not self.connected:
            logger.warning("No conectado a IBKR")
            return None

        try:
            contract = Stock(symbol, exchange, currency)
            
            # Buscar símbolos coincidentes primero
            matches = self.ib.reqMatchingSymbols(symbol)
            if not matches:
                logger.warning(f"No se encontraron coincidencias para el símbolo {symbol}")
                return None
            
            # Calificar el contrato
            qualified = self.ib.qualifyContracts(contract)
            if not qualified:
                logger.warning(f"No se pudo calificar el contrato para {symbol}")
                return None
            
            self.current_contract = qualified[0]
            logger.info(f"Contrato encontrado: {self.current_contract}")
            return self.current_contract
        
        except Exception as e:
            logger.error(f"Error al buscar contrato: {str(e)}")
            return None

    def get_market_data(self, contract: Contract) -> Optional[dict]:
        """Obtiene datos de mercado para un contrato."""
        if not self.connected:
            logger.warning("No conectado a IBKR")
            return None

        try:
            # Suscribir a datos de mercado
            self.ib.reqMarketDataType(1)  # 1 = datos en tiempo real, 2 = congelados, 3 = retrasados
            
            # Obtener ticks básicos
            ticker = self.ib.reqTickers(contract)[0]
            
            self.current_market_data = {
                'symbol': contract.symbol,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'last': ticker.last,
                'close': ticker.close,
                'volume': ticker.volume,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            logger.info(f"Datos de mercado: {self.current_market_data}")
            return self.current_market_data
        
        except Exception as e:
            logger.error(f"Error al obtener datos de mercado: {str(e)}")
            return None

    def create_order(self, action: str, quantity: float, order_type: str, 
                    limit_price: float = None, stop_price: float = None) -> Optional[Order]:
        """Crea una orden de trading."""
        if not self.current_contract:
            logger.warning("Ningún contrato seleccionado")
            return None

        try:
            order = None
            
            if order_type.upper() == 'MARKET':
                order = MarketOrder(action.upper(), quantity)
            elif order_type.upper() == 'LIMIT' and limit_price:
                order = LimitOrder(action.upper(), quantity, limit_price)
            elif order_type.upper() == 'STOP' and stop_price:
                order = StopOrder(action.upper(), quantity, stop_price)
            elif order_type.upper() == 'STOP_LIMIT' and limit_price and stop_price:
                order = StopLimitOrder(action.upper(), quantity, limit_price, stop_price)
            else:
                logger.error("Tipo de orden no soportado o parámetros incorrectos")
                return None
            
            logger.info(f"Orden creada: {order}")
            return order
        
        except Exception as e:
            logger.error(f"Error al crear orden: {str(e)}")
            return None

    def place_order(self, order: Order) -> bool:
        """Envía una orden a IBKR."""
        if not self.connected or not self.current_contract:
            logger.warning("No conectado o ningún contrato seleccionado")
            return False

        try:
            trade = self.ib.placeOrder(self.current_contract, order)
            
            # Esperar confirmación (opcional, podría hacerse asíncrono)
            self.ib.sleep(1)
            
            if trade.orderStatus.status in ['Filled', 'Submitted', 'PreSubmitted']:
                logger.info(f"Orden {trade.order.orderId} enviada con éxito. Estado: {trade.orderStatus.status}")
                return True
            else:
                logger.warning(f"Problema con la orden. Estado: {trade.orderStatus.status}")
                return False
        
        except Exception as e:
            logger.error(f"Error al enviar orden: {str(e)}")
            return False

    def get_open_orders(self) -> List[dict]:
        """Obtiene las órdenes abiertas."""
        if not self.connected:
            logger.warning("No conectado a IBKR")
            return []

        try:
            orders = []
            for trade in self.ib.openTrades():
                orders.append({
                    'order_id': trade.order.orderId,
                    'symbol': trade.contract.symbol,
                    'action': trade.order.action,
                    'quantity': trade.order.totalQuantity,
                    'type': trade.order.orderType,
                    'status': trade.orderStatus.status,
                    'filled': trade.orderStatus.filled,
                    'remaining': trade.orderStatus.remaining
                })
            
            logger.info(f"Órdenes abiertas: {len(orders)}")
            return orders
        
        except Exception as e:
            logger.error(f"Error al obtener órdenes abiertas: {str(e)}")
            return []

    def cancel_order(self, order_id: int) -> bool:
        """Cancela una orden específica."""
        if not self.connected:
            logger.warning("No conectado a IBKR")
            return False

        try:
            for trade in self.ib.openTrades():
                if trade.order.orderId == order_id:
                    self.ib.cancelOrder(trade.order)
                    logger.info(f"Orden {order_id} cancelada")
                    return True
            
            logger.warning(f"No se encontró la orden {order_id} para cancelar")
            return False
        
        except Exception as e:
            logger.error(f"Error al cancelar orden: {str(e)}")
            return False

    def get_positions(self) -> List[dict]:
        """Obtiene las posiciones actuales."""
        if not self.connected:
            logger.warning("No conectado a IBKR")
            return []

        try:
            positions = []
            for pos in self.ib.positions():
                positions.append({
                    'symbol': pos.contract.symbol,
                    'position': pos.position,
                    'avg_cost': pos.avgCost
                })
            
            logger.info(f"Posiciones actuales: {len(positions)}")
            return positions
        
        except Exception as e:
            logger.error(f"Error al obtener posiciones: {str(e)}")
            return []
        
    # def create_bracket_order(self, action: str, quantity: float, limit_price: float, 
    #                         take_profit_price: float, stop_loss_price: float) -> Optional[List[Order]]:
    #     """Crea una orden bracket (entrada limitada con take-profit y stop-loss)."""
    #     if not self.current_contract:
    #         logger.warning("Ningún contrato seleccionado")
    #         return None

    #     try:
    #         # Crear la orden bracket
    #         bracket = bracketOrder(
    #             action=action.upper(),
    #             quantity=quantity,
    #             limitPrice=limit_price,
    #             takeProfitPrice=take_profit_price,
    #             stopLossPrice=stop_loss_price
    #         )
            
    #         logger.info(f"Orden bracket creada: {bracket}")
    #         return bracket
        
    #     except Exception as e:
    #         logger.error(f"Error al crear orden bracket: {str(e)}")
    #         return None

    async def place_bracket_order(self, contract, action: str, quantity: float, 
                                limit_price: float, take_profit: float, 
                                stop_loss: float) -> None:
        """
        Coloca una orden bracket (entrada límite con take profit y stop loss)
        
        Args:
            contract: Contrato sobre el que operar
            action: 'BUY' o 'SELL'
            quantity: Cantidad
            limit_price: Precio de entrada límite
            take_profit: Precio de take profit
            stop_loss: Precio de stop loss
        """
        try:
            # Crear la orden bracket
            bracket = bracketOrder(
                action=action,
                quantity=quantity,
                limitPrice=limit_price,
                takeProfitPrice=take_profit,
                stopLossPrice=stop_loss
            )
            
            # Colocar cada orden del bracket
            for order in bracket:
                await self.placeOrder(contract, order)
                
            logger.info("Órdenes bracket colocadas correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error al colocar órdenes bracket: {str(e)}")
            return False

    def get_head_timestamp(self, what_to_show: str = 'TRADES', use_rth: bool = True) -> Optional[datetime]:
        """Obtiene la fecha más antigua de datos disponibles para el contrato actual."""
        if not self.connected or not self.current_contract:
            logger.warning("No conectado o ningún contrato seleccionado")
            return None

        try:
            head_timestamp = self.ib.reqHeadTimeStamp(
                self.current_contract,
                whatToShow=what_to_show,
                useRTH=use_rth
            )
            logger.info(f"Head timestamp: {head_timestamp}")
            return head_timestamp
        
        except Exception as e:
            logger.error(f"Error al obtener head timestamp: {str(e)}")
            return None

    def get_historical_data(self, duration: str = '60 D', bar_size: str = '1 hour',
                        what_to_show: str = 'TRADES', use_rth: bool = True) -> Optional[pd.DataFrame]:
        """Obtiene datos históricos para el contrato actual."""
        if not self.connected or not self.current_contract:
            logger.warning("No conectado o ningún contrato seleccionado")
            return None

        try:
            bars = self.ib.reqHistoricalData(
                contract=self.current_contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=use_rth,
                formatDate=1
            )
            
            if not bars:
                logger.warning("No se obtuvieron datos históricos")
                return None
            
            df = util.df(bars)
            logger.info(f"Datos históricos obtenidos. Forma: {df.shape}")
            return df
        
        except Exception as e:
            logger.error(f"Error al obtener datos históricos: {str(e)}")
            return None

# Ejemplo de uso interactivo (parte modificada)
if __name__ == "__main__":
    app = TradingApp()
    
    if app.connect():
        print("\n--- Aplicación de Trading IBKR ---")
        print("1. Buscar contrato")
        print("2. Obtener datos de mercado")
        print("3. Obtener datos históricos")
        print("4. Crear y enviar orden")
        print("5. Crear y enviar orden bracket (limit + TP/SL)")
        print("6. Ver órdenes abiertas")
        print("7. Cancelar orden")
        print("8. Ver posiciones")
        print("9. Salir")
        
        while True:
            choice = input("\nSeleccione una opción (1-9): ")
            
            if choice == '1':
                symbol = input("Ingrese el símbolo (ej. AAPL): ").strip().upper()
                contract = app.search_contract(symbol)
                if contract:
                    print(f"\nContrato encontrado: {contract}")
            
            elif choice == '2':
                if app.current_contract:
                    market_data = app.get_market_data(app.current_contract)
                    if market_data:
                        print("\nDatos de mercado:")
                        for k, v in market_data.items():
                            print(f"{k}: {v}")
                else:
                    print("Primero busque un contrato (opción 1)")
                    
            # Nueva opción para datos históricos
            elif choice == '3':
                if app.current_contract:
                    print("\nOpciones de datos históricos:")
                    print("a. Ver fecha más antigua disponible")
                    print("b. Obtener datos históricos")
                    sub_choice = input("Seleccione una opción (a/b): ").lower()
                    
                    if sub_choice == 'a':
                        head_ts = app.get_head_timestamp()
                        if head_ts:
                            print(f"\nFecha más antigua disponible: {head_ts}")
                    
                    elif sub_choice == 'b':
                        duration = input("Duración (ej. '60 D', '1 W', '1 M'): ").strip()
                        bar_size = input("Tamaño de barra (ej. '1 hour', '1 day', '15 mins'): ").strip()
                        
                        df = app.get_historical_data(duration=duration, bar_size=bar_size)
                        if df is not None:
                            print("\nPrimeras 5 filas:")
                            print(df.head())
                            print("\nÚltimas 5 filas:")
                            print(df.tail())
                            
                            # Opción para guardar a CSV
                            save_csv = input("\n¿Guardar a CSV? (s/n): ").lower()
                            if save_csv == 's':
                                filename = f"{app.current_contract.symbol}_{duration.replace(' ', '')}_{bar_size.replace(' ', '')}.csv"
                                df.to_csv(filename, index=False)
                                print(f"Datos guardados en {filename}")
                    else:
                        print("Opción no válida")
                else:
                    print("Primero busque un contrato (opción 1)")
                    
            
            elif choice == '4':
                if app.current_contract:
                    action = input("Acción (BUY/SELL): ").strip().upper()
                    quantity = float(input("Cantidad: "))
                    order_type = input("Tipo de orden (MARKET/LIMIT/STOP): ").strip().upper()
                    
                    limit_price = None
                    stop_price = None
                    
                    if order_type == 'LIMIT':
                        limit_price = float(input("Precio límite: "))
                    elif order_type == 'STOP':
                        stop_price = float(input("Precio stop: "))
                    elif order_type == 'STOP_LIMIT':
                        limit_price = float(input("Precio límite: "))
                        stop_price = float(input("Precio stop: "))
                    
                    order = app.create_order(action, quantity, order_type, limit_price, stop_price)
                    if order:
                        if app.place_order(order):
                            print("Orden enviada con éxito")
                        else:
                            print("Error al enviar la orden")
                else:
                    print("Primero busque un contrato (opción 1)")
            
            elif choice == '5':
                if app.current_contract:
                    action = input("Acción (BUY/SELL): ").strip().upper()
                    quantity = float(input("Cantidad: "))
                    limit_price = float(input("Precio de entrada límite: "))
                    take_profit = float(input("Precio de take-profit: "))
                    stop_loss = float(input("Precio de stop-loss: "))
                    
                    bracket = app.create_bracket_order(action, quantity, limit_price, take_profit, stop_loss)
                    if bracket:
                        if app.place_bracket_order(bracket):
                            print("Orden bracket enviada con éxito")
                        else:
                            print("Error al enviar la orden bracket")
                else:
                    print("Primero busque un contrato (opción 1)")
            
            elif choice == '6':
                orders = app.get_open_orders()
                if orders:
                    print("\nÓrdenes abiertas:")
                    for i, order in enumerate(orders, 1):
                        print(f"{i}. ID: {order['order_id']} - {order['symbol']} {order['action']} {order['quantity']} "
                              f"({order['type']}) - Estado: {order['status']} - Llenado: {order['filled']}")
                else:
                    print("No hay órdenes abiertas")
            
            elif choice == '7':
                order_id = int(input("ID de orden a cancelar: "))
                if app.cancel_order(order_id):
                    print(f"Orden {order_id} cancelada")
                else:
                    print(f"No se pudo cancelar la orden {order_id}")
            
            elif choice == '8':
                positions = app.get_positions()
                if positions:
                    print("\nPosiciones actuales:")
                    for i, pos in enumerate(positions, 1):
                        print(f"{i}. {pos['symbol']} - Cantidad: {pos['position']} - Costo promedio: {pos['avg_cost']}")
                else:
                    print("No hay posiciones abiertas")
            
            elif choice == '9':
                app.disconnect()
                print("Saliendo de la aplicación...")
                break
            
            else:
                print("Opción no válida. Intente de nuevo.")