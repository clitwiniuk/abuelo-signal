# ib_client.py - Adaptado para usar la librería Interactive-Brokers-Trading-Bot-master
from ibw.client import IBClient  # Importa la clase robusta de la otra librería
from configparser import ConfigParser
import pandas as pd

class IBKRConnection:
    def __init__(self, username, account):
        self.client = IBClient(username=username, account=account)
        self.client.create_session()  # Autenticación y conexión

    def get_account_data(self):
        # Devuelve cuentas asociadas
        return self.client.portfolio_accounts()

    def get_market_price(self, symbol):
        # Obtiene precio de mercado usando la API de IBTB
        # Este método puede requerir ajuste según la API real de IBClient
        # Aquí se asume que existe un método get_market_data
        try:
            price_data = self.client.get_market_data(symbol)
            return price_data
        except Exception as e:
            return f"Error obteniendo precio: {e}"


        if tickType == TickTypeEnum.LAST or tickType == TickTypeEnum.CLOSE:
            self.latest_price = price
            self.price_received.set()

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice,
                    permId, parentId, lastFillPrice, clientId, whyHeld,
                    mktCapPrice):
        self.executed_orders.append({
            "orderId": orderId,
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avgFillPrice": avgFillPrice
        })


        self.open_orders.append({
            "orderId": orderId,
            "symbol": contract.symbol,
            "action": order.action,
            "orderType": order.orderType,
            "totalQuantity": order.totalQuantity,
            "status": orderState.status
        })

    def historicalData(self, reqId: int, bar):
        self.historical_data.append({
            "date": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume
        })

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        self.historical_data_event.set()

    def start(self):
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        time.sleep(1)

    def stop(self):
        self.disconnect()

    def create_contract(self, symbol):
        contract = Contract()
        contract.symbol = symbol.upper()
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract

    def create_order(self, action, quantity, order_type="MKT", stop_price=None, limit_price=None):
        order = Order()
        order.action = action
        order.totalQuantity = int(quantity)  # Aseguramos enteros
        order.orderType = order_type

        if order_type == "STP" and stop_price:
            order.auxPrice = stop_price
        elif order_type == "LMT" and limit_price:
            order.lmtPrice = limit_price

        if hasattr(order, "EtradeOnly"):
            delattr(order, "EtradeOnly")

        return order

    def get_market_price(self, symbol):
        self.latest_price = None
        self.price_received.clear()

        contract = self.create_contract(symbol)
        self.reqMktData(1001, contract, "", False, False, [])

        if self.price_received.wait(timeout=5):
            self.cancelMktData(1001)
            return self.latest_price
        else:
            self.cancelMktData(1001)
            raise Exception("No se pudo obtener el precio de mercado.")

    def place_trade(self, action, symbol, quantity, order_type, stop_percent=None, limit_price=None):
        contract = self.create_contract(symbol)

        stop_price = None
        if order_type == "STP" and stop_percent:
            market_price = self.get_market_price(symbol)
            if market_price:
                stop_price = round(market_price * (1 - stop_percent / 100), 2)
            else:
                raise Exception("Precio de mercado no disponible para calcular el stop.")

        order = self.create_order(action, quantity, order_type, stop_price, limit_price)
        if hasattr(order, "EtradeOnly"):
            delattr(order, "EtradeOnly")
        self.placeOrder(self.order_id, contract, order)
        self.order_id += 1

    def get_open_orders(self):
        self.open_orders.clear()
        self.reqOpenOrders()
        time.sleep(1)
        return self.open_orders

    def get_executed_orders(self):
        return self.executed_orders

    def get_historical_data(self, symbol, duration="1 D", bar_size="5 mins"):
        self.historical_data.clear()
        self.historical_data_event.clear()

        contract = self.create_contract(symbol)
        self.reqHistoricalData(
            reqId=1002,
            contract=contract,
            endDateTime=datetime.now(timezone.utc).strftime("%Y%m%d %H:%M:%S"),
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[]
        )

        if self.historical_data_event.wait(timeout=10):
            return pd.DataFrame(self.historical_data)
        else:
            raise Exception("No se pudieron obtener los datos históricos.")
