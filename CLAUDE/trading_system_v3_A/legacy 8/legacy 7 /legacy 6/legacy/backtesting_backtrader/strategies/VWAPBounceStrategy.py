import backtrader as bt
from datetime import datetime
from core.base_strategy import SmallCapStrategy

class VWAPBounceStrategy(SmallCapStrategy):
    params = (
        ('vwap_deviation_min', -0.03),  # -3% bajo VWAP
        ('vwap_deviation_max', -0.01),  # -1% bajo VWAP
        ('rsi_oversold', 40),
    )

    def next(self):
        if len(self) < 20:
            return

        # Solo operar en horario de medio día (10:30-14:00) - timeframe 1min
        if not self.is_market_hours('10:30', '20:00'):
            return

        if self.position:
            return self.manage_position()

        # Calcular desviación VWAP
        vwap_deviation = (self.dataclose[0] / self.vwap[0]) - 1

        # Calcular volumen promedio de los últimos 20 períodos
        avg_volume = sum([self.datavolume[-i] for i in range(min(20, len(self)))]) / min(20, len(self))

        # Condiciones para entrada LONG
        if (self.params.vwap_deviation_min <= vwap_deviation <= self.params.vwap_deviation_max and
            self.rsi[0] < self.params.rsi_oversold and
            self.dataclose[0] > self.datalow[0] * 1.005 and  # No en mínimos del día
            self.datavolume[0] > avg_volume * 1.2):

            size = int(self.p.position_size / self.dataclose[0])

            self.log(f'SEÑAL VWAP BOUNCE - Dev: {vwap_deviation:.2%}, Precio: {self.dataclose[0]:.2f}, Size: {size}')
            self.order = self.buy(size=size)

            # Stop y target
            self.stop_loss = self.datalow[0] * 0.995
            self.target = self.vwap[0]  # Objetivo: volver a VWAP

    def manage_position(self):
        if not self.position:
            return

        # Stop loss
        if self.dataclose[0] <= self.stop_loss:
            self.log(f'VWAP STOP LOSS - Precio: {self.dataclose[0]:.2f}')
            self.order = self.sell()

        # Target
        elif self.dataclose[0] >= self.target:
            self.log(f'VWAP TARGET - Precio: {self.dataclose[0]:.2f}')
            self.order = self.sell()

        # Time exit (2 horas máximo = 120 barras de 1min)
        elif len(self) - self.bar_executed >= 120:
            self.log('VWAP TIME EXIT')
            self.order = self.sell()