import backtrader as bt
import json
import os
from core.base_strategy import SmallCapStrategy

class OptunaOptimizedStrategy(SmallCapStrategy):
    """
    Estrategia optimizada usando parámetros de Optuna

    Parámetros clave optimizados:
    - RSI: Detección de momentum y sobreventa/sobrecompra
    - ADX: Confirmación de tendencia fuerte
    - SMA: Filtro de tendencia direccional
    - TP/SL: Gestión de riesgo optimizada
    - Trailing Stop: Maximización de ganancias
    - Max Holding Period: Límite temporal de posiciones
    """

    params = (
        # Parámetros técnicos optimizados por Optuna
        ('rsi_period', 14),
        ('rsi_threshold', 70),
        ('sma_period', 20),
        ('adx_period', 14),
        ('adx_threshold', 25),

        # Gestión de riesgo optimizada
        ('tp_pct', 5.0),           # Take profit %
        ('sl_pct', -2.0),          # Stop loss %
        ('trailing_stop', True),   # Activar trailing stop
        ('trailing_pct', 1.0),     # Trailing stop %
        ('max_holding_period', 30), # Máximo de barras en posición (30 min)

        # Parámetros de posición
        ('position_size_pct', 95), # % del cash a usar (95% para dejar margen)

        # Archivo de parámetros optimizados
        ('params_file', None),     # Path al JSON con parámetros optimizados
        ('symbol', None),          # Símbolo para cargar parámetros específicos
    )

    def __init__(self):
        super().__init__()

        # Cargar parámetros optimizados si se especifica
        if self.p.params_file and self.p.symbol:
            self._load_optimized_params()

        # Indicadores técnicos
        self.rsi = bt.indicators.RSI(
            self.dataclose,
            period=self.p.rsi_period
        )

        self.sma = bt.indicators.SimpleMovingAverage(
            self.dataclose,
            period=self.p.sma_period
        )

        self.adx = bt.indicators.AverageDirectionalMovementIndex(
            self.data,
            period=self.p.adx_period
        )

        # Variables de control adicionales
        self.trailing_stop_price = None
        self.entry_bar = None

        # Log de parámetros
        self.log(f'📊 ESTRATEGIA OPTIMIZADA INICIADA')
        self.log(f'   RSI: {self.p.rsi_period} / {self.p.rsi_threshold}')
        self.log(f'   SMA: {self.p.sma_period}')
        self.log(f'   ADX: {self.p.adx_period} / {self.p.adx_threshold}')
        self.log(f'   TP/SL: {self.p.tp_pct}% / {self.p.sl_pct}%')
        self.log(f'   Trailing: {self.p.trailing_stop} ({self.p.trailing_pct}%)')
        self.log(f'   Max Hold: {self.p.max_holding_period} barras')

    def _load_optimized_params(self):
        """Carga parámetros optimizados desde archivo JSON"""
        try:
            with open(self.p.params_file, 'r') as f:
                data = json.load(f)

            # Buscar parámetros para el símbolo específico
            for ticker_data in data.get('optimization_summary', []):
                if ticker_data['ticker'] == self.p.symbol:
                    params = ticker_data['best_params']

                    # Actualizar solo parámetros que existen y son válidos
                    if params.get('best_value', [-999])[0] != -999:
                        self.p.rsi_period = params.get('rsi_period', self.p.rsi_period)
                        self.p.rsi_threshold = params.get('rsi_threshold', self.p.rsi_threshold)
                        self.p.sma_period = params.get('sma_period', self.p.sma_period)
                        self.p.adx_period = params.get('adx_period', self.p.adx_period)
                        self.p.adx_threshold = params.get('adx_threshold', self.p.adx_threshold)
                        self.p.tp_pct = params.get('tp_pct', self.p.tp_pct)
                        self.p.sl_pct = params.get('sl_pct', self.p.sl_pct)
                        self.p.trailing_stop = params.get('use_trailing', self.p.trailing_stop)
                        self.p.trailing_pct = params.get('trailing_pct', self.p.trailing_pct)
                        self.p.max_holding_period = params.get('max_holding_period', self.p.max_holding_period)

                        self.log(f'✅ Parámetros optimizados cargados para {self.p.symbol}')
                    else:
                        self.log(f'⚠️ Parámetros optimizados inválidos, usando defaults')
                    break
            else:
                self.log(f'⚠️ No se encontraron parámetros para {self.p.symbol}, usando defaults')

        except Exception as e:
            self.log(f'❌ Error cargando parámetros: {e}')

    def next(self):
        """Lógica principal de trading"""

        # Esperar suficientes barras para indicadores
        min_period = max(self.p.rsi_period, self.p.sma_period, self.p.adx_period)
        if len(self) < min_period + 1:
            return

        # Solo operar en horario regular de mercado
        if not self.is_market_hours('09:30', '16:00'):
            return

        # Si hay una orden pendiente, no hacer nada
        if self.order:
            return

        # Gestionar posición abierta
        if self.position:
            return self.manage_position()

        # Lógica de entrada: Combinación de señales técnicas
        entry_signal = self._check_entry_conditions()

        if entry_signal:
            # Calcular tamaño de posición
            available_cash = self.broker.getcash() * (self.p.position_size_pct / 100)
            size = int(available_cash / self.dataclose[0])

            if size > 0:
                self.log(f'🚀 SEÑAL DE ENTRADA - RSI:{self.rsi[0]:.1f} ADX:{self.adx[0]:.1f} Price:{self.dataclose[0]:.2f}')
                self.order = self.buy(size=size)
                self.entry_bar = len(self)

                # Calcular stop loss y target
                self.stop_loss = self.dataclose[0] * (1 + self.p.sl_pct / 100)
                self.target = self.dataclose[0] * (1 + self.p.tp_pct / 100)

                # Inicializar trailing stop
                if self.p.trailing_stop:
                    self.trailing_stop_price = self.stop_loss

                self.log(f'   Stop Loss: {self.stop_loss:.2f} | Target: {self.target:.2f}')

    def _check_entry_conditions(self):
        """
        Verifica condiciones de entrada basadas en parámetros optimizados

        Señal de entrada:
        1. RSI >= threshold (momentum alcista)
        2. Precio > SMA (tendencia alcista)
        3. ADX >= threshold (tendencia fuerte)
        """

        # Condición 1: RSI muestra momentum
        rsi_condition = self.rsi[0] >= self.p.rsi_threshold

        # Condición 2: Precio sobre SMA (tendencia alcista)
        sma_condition = self.dataclose[0] > self.sma[0]

        # Condición 3: ADX muestra tendencia fuerte
        adx_condition = self.adx[0] >= self.p.adx_threshold

        # Todas las condiciones deben cumplirse
        return rsi_condition and sma_condition and adx_condition

    def manage_position(self):
        """Gestión de posiciones abiertas"""

        if not self.position:
            return

        # No crear nuevas órdenes si ya hay una pendiente
        if self.order:
            return

        current_price = self.dataclose[0]
        current_profit = (current_price - self.buyprice) / self.buyprice
        bars_held = len(self) - self.entry_bar

        # Actualizar trailing stop si está activado
        if self.p.trailing_stop and current_profit > 0:
            new_trailing_stop = current_price * (1 - self.p.trailing_pct / 100)
            if new_trailing_stop > self.trailing_stop_price:
                old_stop = self.trailing_stop_price
                self.trailing_stop_price = new_trailing_stop
                self.log(f'📈 TRAILING STOP actualizado: {old_stop:.2f} -> {self.trailing_stop_price:.2f}')

        # 1. Check Take Profit
        if current_price >= self.target:
            self.log(f'✅ TAKE PROFIT - Precio: {current_price:.2f}, P&L: {current_profit*100:.2f}%')
            self.order = self.close()
            return

        # 2. Check Stop Loss (incluye trailing stop)
        stop_price = self.trailing_stop_price if self.p.trailing_stop else self.stop_loss
        if current_price <= stop_price:
            stop_type = "TRAILING STOP" if self.p.trailing_stop and stop_price > self.stop_loss else "STOP LOSS"
            self.log(f'🛑 {stop_type} - Precio: {current_price:.2f}, P&L: {current_profit*100:.2f}%')
            self.order = self.close()
            return

        # 3. Check max holding period
        if bars_held >= self.p.max_holding_period:
            self.log(f'⏰ TIME EXIT ({bars_held} barras) - P&L: {current_profit*100:.2f}%')
            self.order = self.close()
            return

        # Log periódico del estado de la posición
        if bars_held % 10 == 0:
            self.log(f'📊 Posición abierta: {bars_held} barras, P&L: {current_profit*100:.2f}%, '
                    f'Stop: {stop_price:.2f}, Target: {self.target:.2f}')
