import backtrader as bt
from datetime import datetime, time
import logging

class VWAP(bt.Indicator):
    """
    VWAP Indicator - Volume Weighted Average Price
    Calcula el precio medio ponderado por volumen
    """
    lines = ('vwap',)
    params = (('period', 30),)  # Período de lookback para VWAP

    def __init__(self):
        # Calcular precio típico: (H + L + C) / 3
        self.typical_price = (self.data.high + self.data.low + self.data.close) / 3.0
        self.tp_volume = self.typical_price * self.data.volume

    def next(self):
        # Usar período móvil para evitar acumulación infinita
        period = min(self.p.period, len(self))

        if period == 0:
            self.lines.vwap[0] = self.data.close[0]
            return

        # Sumar típico_precio * volumen y volumen para el período
        sum_tp_vol = sum([self.tp_volume[-i] for i in range(period)])
        sum_vol = sum([self.data.volume[-i] for i in range(period)])

        # Evitar división por cero
        if sum_vol > 0:
            self.lines.vwap[0] = sum_tp_vol / sum_vol
        else:
            self.lines.vwap[0] = self.data.close[0]

class SmallCapStrategy(bt.Strategy):
    """
    Estrategia base para small caps con funcionalidades comunes
    """
    params = (
        ('position_size', 2000),  # Tamaño de posición en dólares
        ('max_positions', 1),     # Máximo número de posiciones simultáneas
        ('commission', 0.001),    # Comisión por trade (0.1%)
    )

    def __init__(self):
        # Referencias a datos para facilitar el acceso
        self.dataopen = self.datas[0].open
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.datavolume = self.datas[0].volume

        # Indicadores comunes
        self.sma20 = bt.indicators.SimpleMovingAverage(self.dataclose, period=20)
        self.rsi = bt.indicators.RSI(self.dataclose, period=14)
        self.vwap = VWAP(self.data)

        # Variables de control
        self.order = None
        self.bar_executed = None
        self.stop_loss = None
        self.target = None
        self.buyprice = None

        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def log(self, txt, dt=None):
        """Método de logging"""
        dt = dt or self.datas[0].datetime.date(0)
        self.logger.info(f'{dt.isoformat()} {txt}')

    def notify_order(self, order):
        """Notificación de órdenes"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'COMPRA EJECUTADA - Precio: {order.executed.price:.2f}, '
                        f'Cantidad: {order.executed.size:.0f}')
                self.buyprice = order.executed.price
                self.bar_executed = len(self)
            elif order.issell():
                self.log(f'VENTA EJECUTADA - Precio: {order.executed.price:.2f}, '
                        f'Cantidad: {order.executed.size:.0f}')

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Orden cancelada/margin/rechazada')

        self.order = None

    def notify_trade(self, trade):
        """Notificación de trades completados"""
        if not trade.isclosed:
            return

        profit_loss = trade.pnl
        profit_loss_pct = (profit_loss / self.buyprice) * 100 if self.buyprice else 0

        self.log(f'TRADE CERRADO - P&L: ${profit_loss:.2f} ({profit_loss_pct:.2f}%)')

    def next(self):
        """Método principal - debe ser implementado por subclases"""
        raise NotImplementedError("Subclases deben implementar el método next()")

    def manage_position(self):
        """Método para gestionar posiciones abiertas - debe ser implementado por subclases"""
        raise NotImplementedError("Subclases deben implementar el método manage_position()")

    def is_market_hours(self, start_time='09:30', end_time='16:00'):
        """Verificar si estamos en horario de mercado regular (con conversión de zona horaria)"""
        current_time = self.datas[0].datetime.time(0)

        # Los datos están en horario de España (UTC+1/UTC+2), pero el mercado es USA (UTC-5/UTC-4)
        # Convertir la hora española a hora USA restando 6 horas (aproximadamente)
        # España: UTC+1 en invierno, UTC+2 en verano
        # USA EST: UTC-5 en invierno, UTC-4 en verano
        # Diferencia aproximada: 6-7 horas

        # Para simplificar, asumimos diferencia de 6 horas
        # Hora España 15:00 = Hora USA 9:00
        usa_hour = (current_time.hour - 6) % 24
        usa_minute = current_time.minute
        usa_time = time(usa_hour, usa_minute)

        start = datetime.strptime(start_time, '%H:%M').time()
        end = datetime.strptime(end_time, '%H:%M').time()

        return start <= usa_time <= end