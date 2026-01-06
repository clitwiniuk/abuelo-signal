from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order

import threading
import time

class IBKRClient(EWrapper, EClient):
    def __init__(self, ip="127.0.0.1", port=7497, client_id=1):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self.order_id = None
        self.order_statuses = {}  # orderId -> (status, filled, remaining, avgFillPrice)
        self.last_order_id = None
        self.connect(ip, port, client_id)
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        time.sleep(1)  # Espera a que conecte

    def nextValidId(self, orderId):
        self.order_id = orderId

    def error(self, reqId, errorCode, errorString):
        print(f"IBKR Error {errorCode}: {errorString}")

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        print(f"OrderStatus. Id: {orderId}, Status: {status}, Filled: {filled}, Remaining: {remaining}")
        self.order_statuses[orderId] = (status, filled, remaining, avgFillPrice)
        self.last_order_id = orderId

    def get_last_order_status(self):
        if self.last_order_id is not None and self.last_order_id in self.order_statuses:
            status, filled, remaining, avgFillPrice = self.order_statuses[self.last_order_id]
            return {
                'order_id': self.last_order_id,
                'status': status,
                'filled': filled,
                'remaining': remaining,
                'avgFillPrice': avgFillPrice
            }
        return None

    def place_simple_order(self, symbol, qty, action, order_type="MKT", price=None):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        order = Order()
        order.action = action
        order.totalQuantity = int(qty)
        order.orderType = order_type
        if order_type == "LMT" and price is not None:
            order.lmtPrice = float(price)

        # Espera explícita a tener order_id válido
        timeout = 10  # segundos
        waited = 0
        while self.order_id is None and waited < timeout:
            time.sleep(0.1)
            waited += 0.1
        if self.order_id is None:
            print("ERROR: No se recibió nextValidId, no se puede enviar la orden.")
            return

        print(f"Enviando orden con order_id={self.order_id}")
        self.placeOrder(self.order_id, contract, order)
        self.last_order_id = self.order_id
        self.order_id += 1
