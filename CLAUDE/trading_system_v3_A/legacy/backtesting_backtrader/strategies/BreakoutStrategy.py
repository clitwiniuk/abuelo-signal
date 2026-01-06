import backtrader as bt
from datetime import datetime
from core.base_strategy import SmallCapStrategy

class BreakoutStrategy(SmallCapStrategy):
    params = (
        ('consolidation_bars', 60),  # 1 hora en timeframe 1min
        ('volume_multiplier', 1.5),
    )

    def __init__(self):
        super().__init__()
        self.consolidation_high = bt.indicators.Highest(self.datahigh, period=self.p.consolidation_bars)
        self.consolidation_low = bt.indicators.Lowest(self.datalow, period=self.p.consolidation_bars)

    def next(self):
        # DEBUG: Log detallado de cada barra
        if len(self) % 5 == 0:
            current_time = self.datas[0].datetime.time(0)
            usa_hour = (current_time.hour - 6) % 24
            usa_time = f"{usa_hour:02d}:{current_time.minute:02d}"
            market_hours = self.is_market_hours("09:30", "16:00")
            self.log(f'BARRA {len(self)} - ESP: {current_time}, USA: {usa_time}, Market: {market_hours}, Price: {self.dataclose[0]:.2f}')

        if len(self) < self.p.consolidation_bars + 1:
            return

        # Solo operar en horario regular de mercado (9:30-22:00 España)
        if not self.is_market_hours('09:30', '22:00'):
            return

        # Si hay una orden pendiente, no hacer nada
        if self.order:
            return

        if self.position:
            return self.manage_position()

        # Calcular rango de consolidación
        consolidation_range = (self.consolidation_high[0] - self.consolidation_low[0]) / self.consolidation_low[0]

        # DEBUG: Log de condiciones de breakout
        breakout_condition = self.dataclose[0] > self.consolidation_high[0]
        range_condition = consolidation_range < 0.05
        self.log(f'CONDITIONS - Range: {consolidation_range:.2%} (<5%: {range_condition}), Breakout: {breakout_condition}, High: {self.consolidation_high[0]:.2f}, Close: {self.dataclose[0]:.2f}')

        # Condiciones breakout LONG - RELAJADAS PARA TESTING
        if range_condition and breakout_condition:
            self.log(f'🚀 SEÑAL BREAKOUT DETECTADA! - Precio: {self.dataclose[0]:.2f}, Rango: {consolidation_range:.2%}')
            # Usar 95% del cash disponible para dejar margen para comisiones
            available_cash = self.broker.getcash() * 0.95
            size = int(available_cash / self.dataclose[0])
            self.log(f'EXECUTING ORDER - Cash: ${self.broker.getcash():.2f}, Size: {size} acciones')
            self.order = self.buy(size=size)
            self.stop_loss = self.consolidation_low[0]
            self.target = self.dataclose[0] * 1.05  # 5% objetivo (más amplio)
            return

        # Calcular rango de consolidación silenciosamente

    def manage_position(self):
        if not self.position:
            return

        # No crear nuevas órdenes si ya hay una pendiente
        if self.order:
            return

        current_profit = (self.dataclose[0] - self.buyprice) / self.buyprice

        # Stop loss
        if self.dataclose[0] <= self.stop_loss:
            self.log(f'BREAKOUT STOP LOSS - Precio: {self.dataclose[0]:.2f}, P&L: {current_profit*100:.2f}%')
            self.order = self.close()  # Cerrar posición completa

        # Target
        elif self.dataclose[0] >= self.target:
            self.log(f'BREAKOUT TARGET - Precio: {self.dataclose[0]:.2f}, P&L: {current_profit*100:.2f}%')
            self.order = self.close()  # Cerrar posición completa

        # Trailing stop después de +1%
        elif current_profit > 0.01:
            new_stop = self.buyprice * 1.005  # Asegurar 0.5% ganancia
            if new_stop > self.stop_loss:
                self.stop_loss = new_stop

        # Time exit (1 hora = 60 barras de 1min)
        elif len(self) - self.bar_executed >= 60:
            self.log(f'BREAKOUT TIME EXIT - P&L: {current_profit*100:.2f}%')
            self.order = self.close()  # Cerrar posición completa