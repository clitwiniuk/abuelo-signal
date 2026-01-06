import backtrader as bt
from datetime import datetime
from core.base_strategy import SmallCapStrategy

class GapUpStrategy(SmallCapStrategy):
    params = (
        ('min_gap', 0.02),    # 2% gap mínimo
        ('max_gap', 0.08),    # 8% gap máximo
        ('volume_multiplier', 2.0),
    )

    def __init__(self):
        super().__init__()
        self.previous_close = self.datas[0].close(-1)  # Cierre anterior

    def next(self):
        # Esperar a que tengamos datos suficientes
        if len(self) < 2:
            return

        # Solo operar en horario de mercado temprano (9:35-10:30) - timeframe 1min
        if not self.is_market_hours('09:35', '16:30'):
            return

        # Si ya tenemos posición, no entrar en nueva
        if self.position:
            return

        # Calcular gap
        gap_percent = (self.dataopen[0] / self.previous_close[0]) - 1

        # Condiciones para entrada LONG
        if (self.params.min_gap <= gap_percent <= self.params.max_gap and
            self.datavolume[0] > self.datavolume.get(size=20).mean() * self.params.volume_multiplier and
            self.dataclose[0] > self.dataopen[0] and  # Precio por encima de apertura
            self.rsi[0] < 80):  # No sobrecomprado

            # Calcular tamaño de posición
            size = int(self.p.position_size / self.dataclose[0])

            # Entrar LONG
            self.log(f'SEÑAL GAP UP - Gap: {gap_percent:.2%}, Precio: {self.dataclose[0]:.2f}, Size: {size}')
            self.order = self.buy(size=size)

            # Configurar stop loss y target
            self.stop_loss = self.dataopen[0]  # Stop en precio de apertura
            self.target = self.dataopen[0] * (1 + gap_percent * 1.5)

    def manage_position(self):
        """Gestionar posición abierta"""
        if not self.position:
            return

        # Stop loss
        if self.dataclose[0] <= self.stop_loss:
            self.log(f'STOP LOSS - Precio: {self.dataclose[0]:.2f}')
            self.order = self.sell()

        # Target
        elif self.dataclose[0] >= self.target:
            self.log(f'TARGET ALCANZADO - Precio: {self.dataclose[0]:.2f}')
            self.order = self.sell()

        # Time-based exit (máximo 3 horas = 180 barras de 1min)
        elif len(self) - self.bar_executed >= 180:
            self.log('SALIDA POR TIEMPO')
            self.order = self.sell()