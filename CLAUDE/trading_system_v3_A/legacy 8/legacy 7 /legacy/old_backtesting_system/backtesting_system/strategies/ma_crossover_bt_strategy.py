"""
Estrategia Moving Average Crossover para Backtrader

Compra cuando EMA corta cruza arriba EMA larga, vende cuando cruza abajo.
Simple pero efectiva para tendencias en small caps.
"""

import backtrader as bt
import numpy as np
from typing import Dict, Any, Optional
import logging
import sys
import os
from datetime import timedelta

# Agregar path para importar workers
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class MACrossoverStrategy(bt.Strategy):
    """
    Estrategia Moving Average Crossover para small caps

    EMA(9) cruza arriba EMA(21) = COMPRA
    EMA(9) cruza abajo EMA(21) = VENTA
    """

    params = (
        ('fast_period', 9),          # EMA rápida
        ('slow_period', 21),         # EMA lenta
        ('max_position_size', 0.10), # 10% del capital por posición
        ('min_volume', 10000),       # Volumen mínimo
        ('max_holding_bars', 100),   # Máximo 100 barras (2 horas)
    )

    def __init__(self):
        """Inicializar estrategia con indicadores"""
        self.logger = logging.getLogger('backtesting.ma_crossover')

        # Indicadores
        self.fast_ema = bt.indicators.EMA(
            self.data.close,
            period=self.params.fast_period
        )

        self.slow_ema = bt.indicators.EMA(
            self.data.close,
            period=self.params.slow_period
        )

        # Tracking
        self.active_positions = {}
        self.total_signals = 0
        self.executed_trades = 0
        self._trade_results = []

        # Para compatibilidad con backtrader
        self.dataclose = self.data.close
        self.datavolume = self.data.volume

    def next(self):
        """Lógica principal ejecutada en cada barra"""
        try:
            # Verificar que tenemos suficientes datos
            if len(self.data) < self.params.slow_period + 5:
                return

            # Verificar horario de trading (9:30 AM - 4:00 PM ET)
            current_time = self.data.datetime.datetime(0)
            if not self._is_market_hours(current_time):
                return

            symbol = self.data._name or 'UNKNOWN'
            current_price = float(self.dataclose[0])

            # Verificar si ya tenemos posición
            if symbol in self.active_positions:
                self._check_exit(symbol, current_price)
            else:
                self._check_entry(symbol, current_price)

        except Exception as e:
            self.logger.error(f"Error in next(): {e}")

    def _is_market_hours(self, current_time) -> bool:
        """Verificar si estamos en horario de mercado regular"""
        try:
            # Convertir a hora del este (ET)
            et_time = current_time - timedelta(hours=4)  # UTC-4 para ET
            hour = et_time.hour
            minute = et_time.minute

            # Market hours: 9:30 AM - 4:00 PM ET
            current_minutes = hour * 60 + minute
            market_open = 9 * 60 + 30  # 9:30 AM
            market_close = 16 * 60     # 4:00 PM

            return market_open <= current_minutes <= market_close

        except Exception:
            return True  # Si hay error, permitir trading

    def _check_entry(self, symbol: str, current_price: float):
        """Verificar condiciones de entrada"""
        try:
            # Verificar que tenemos suficientes datos
            if len(self.fast_ema) < 2 or len(self.slow_ema) < 2:
                return

            # Condiciones de entrada: Fast EMA cruza arriba Slow EMA
            fast_prev = float(self.fast_ema[-1])
            fast_curr = float(self.fast_ema[0])
            slow_prev = float(self.slow_ema[-1])
            slow_curr = float(self.slow_ema[0])

            # Crossover: fast cruza arriba de slow
            crossover_up = (fast_prev <= slow_prev) and (fast_curr > slow_curr)

            # Confirmación adicional: fast > slow (trend up)
            trend_up = fast_curr > slow_curr

            volume_ok = float(self.datavolume[0]) >= self.params.min_volume

            if crossover_up and trend_up and volume_ok:
                self._execute_entry(symbol, current_price)

        except Exception as e:
            self.logger.error(f"Error checking entry: {e}")

    def _check_exit(self, symbol: str, current_price: float):
        """Verificar condiciones de salida"""
        try:
            position_data = self.active_positions[symbol]

            # Verificar que tenemos suficientes datos
            if len(self.fast_ema) < 2 or len(self.slow_ema) < 2:
                return

            # Condiciones de salida: Fast EMA cruza abajo Slow EMA
            fast_prev = float(self.fast_ema[-1])
            fast_curr = float(self.fast_ema[0])
            slow_prev = float(self.slow_ema[-1])
            slow_curr = float(self.slow_ema[0])

            # Crossunder: fast cruza abajo de slow
            crossunder_down = (fast_prev >= slow_prev) and (fast_curr < slow_curr)

            # Stop loss (5% loss)
            entry_price = position_data['entry_price']
            stop_loss = entry_price * 0.95
            stop_triggered = current_price <= stop_loss

            # Max holding time
            max_holding_reached = (len(self.data) - position_data['entry_bar']) >= self.params.max_holding_bars

            if crossunder_down or stop_triggered or max_holding_reached:
                reason = "MA_CROSSUNDER" if crossunder_down else "STOP_LOSS" if stop_triggered else "MAX_HOLDING"
                self._execute_exit(symbol, reason, current_price)

        except Exception as e:
            self.logger.error(f"Error checking exit: {e}")

    def _execute_entry(self, symbol: str, price: float):
        """Ejecutar entrada"""
        try:
            # Calcular tamaño de posición
            position_size = self._calculate_position_size(price)

            if position_size <= 0:
                return

            # Ejecutar orden
            order = self.buy(
                size=position_size,
                price=price,
                exectype=bt.Order.Market
            )

            # Registrar posición
            self.active_positions[symbol] = {
                'entry_price': price,
                'size': position_size,
                'entry_time': self.data.datetime.datetime(),
                'entry_bar': len(self.data) - 1
            }

            self.executed_trades += 1

            self.logger.info(
                f"🎯 MA_CROSSOVER ENTRY: {symbol} @ ${price:.2f} "
                f"Qty: {position_size} shares (${position_size * price:.2f}) "
                f"Fast EMA: {self.fast_ema[0]:.2f}, Slow EMA: {self.slow_ema[0]:.2f}"
            )

        except Exception as e:
            self.logger.error(f"Error executing entry: {e}")

    def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """Ejecutar salida"""
        try:
            if symbol not in self.active_positions:
                return

            position_data = self.active_positions[symbol]
            entry_price = position_data['entry_price']
            size = position_data['size']

            # Calcular PnL
            pnl = (current_price - entry_price) * size
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            # Ejecutar orden de venta
            order = self.sell(
                size=size,
                price=current_price,
                exectype=bt.Order.Market
            )

            self.logger.info(
                f"🔴 MA_CROSSOVER EXIT: {symbol} @ ${current_price:.2f} "
                f"PnL: ${pnl:.2f} ({pnl_pct:.2f}%) | Reason: {reason}"
            )

            # Track result
            self._trade_results.append(pnl)
            del self.active_positions[symbol]

        except Exception as e:
            self.logger.error(f"Error executing exit for {symbol}: {e}")

    def _calculate_position_size(self, price: float) -> int:
        """Calcular tamaño de posición"""
        try:
            capital = self.broker.getvalue()
            max_position_value = capital * self.params.max_position_size

            if price <= 0:
                return 0

            max_shares = int(max_position_value / price)

            # Mínimo 100 shares
            return max(max_shares, 100)

        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 100

    def notify_order(self, order):
        """Notificación de órdenes"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.logger.info(
                    f"✅ BUY EXECUTED: {order.data._name} @ ${order.executed.price:.2f} "
                    f"Qty: {order.executed.size}"
                )
            elif order.issell():
                self.logger.info(
                    f"✅ SELL EXECUTED: {order.data._name} @ ${order.executed.price:.2f} "
                    f"Qty: {order.executed.size}"
                )

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.logger.warning(f"❌ ORDER FAILED: {order.status}")

    def notify_trade(self, trade):
        """Notificación de trades completados"""
        if trade.isclosed:
            symbol = trade.data._name
            pnl = trade.pnl
            pnl_pct = (pnl / trade.price) * 100

            self.logger.info(
                f"💰 TRADE CLOSED: {symbol} | "
                f"PnL: ${pnl:.2f} ({pnl_pct:.2f}%) | "
                f"Duration: {trade.barlen if hasattr(trade, 'barlen') else 'N/A'} bars"
            )

    def stop(self):
        """Método llamado al finalizar el backtest"""
        total_return = self.broker.getvalue() - self.broker.startingcash
        total_return_pct = (total_return / self.broker.startingcash) * 100

        winning_trades = sum(1 for pnl in self._trade_results if pnl > 0)
        total_trades = len(self._trade_results)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        self.logger.info("=" * 50)
        self.logger.info("MA CROSSOVER BACKTEST RESULTS")
        self.logger.info("=" * 50)
        self.logger.info(f"Total Signals Generated: {self.total_signals}")
        self.logger.info(f"Trades Executed: {self.executed_trades}")
        self.logger.info(f"Final Portfolio Value: ${self.broker.getvalue():.2f}")
        self.logger.info(f"Total Return: ${total_return:.2f} ({total_return_pct:.2f}%)")
        self.logger.info(f"Win Rate: {win_rate:.1f}%")
        self.logger.info("=" * 50)