"""
Estrategia RSI Oversold Bounce para Backtrader

Compra cuando RSI < 30 (oversold), vende cuando RSI > 70 (overbought)
Efectiva para small caps volátiles con rebotes intraday.
"""

import backtrader as bt
import numpy as np
from typing import Dict, Any, Optional
import logging
import sys
import os

# Agregar path para importar workers
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class RSIOverSoldStrategy(bt.Strategy):
    """
    Estrategia RSI Oversold Bounce para small caps

    Compra en oversold (RSI < 30), vende en overbought (RSI > 70)
    Perfecta para mercados volátiles con rebotes intraday.
    """

    params = (
        ('rsi_period', 14),          # Período RSI
        ('rsi_oversold', 30),        # Nivel oversold para compra
        ('rsi_overbought', 70),      # Nivel overbought para venta
        ('max_position_size', 0.10), # 10% del capital por posición
        ('min_volume', 10000),       # Volumen mínimo
        ('max_holding_bars', 50),    # Máximo 50 barras (1 hora)
    )

    def __init__(self):
        """Inicializar estrategia con indicadores"""
        self.logger = logging.getLogger('backtesting.rsi_oversold')

        # Indicadores
        self.rsi = bt.indicators.RSI(
            self.data.close,
            period=self.params.rsi_period
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
            if len(self.data) < self.params.rsi_period + 5:
                return

            # Verificar horario de trading (9:30 AM - 4:00 PM ET)
            current_time = self.data.datetime.datetime(0)
            if not self._is_market_hours(current_time):
                return

            symbol = self.data._name or 'UNKNOWN'
            current_price = float(self.dataclose[0])
            current_rsi = float(self.rsi[0])

            # Verificar si ya tenemos posición
            if symbol in self.active_positions:
                self._check_exit(symbol, current_rsi, current_price)
            else:
                self._check_entry(symbol, current_rsi, current_price)

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

    def _check_entry(self, symbol: str, rsi_value: float, current_price: float):
        """Verificar condiciones de entrada"""
        try:
            # Condiciones de entrada
            rsi_oversold = rsi_value <= self.params.rsi_oversold
            volume_ok = float(self.datavolume[0]) >= self.params.min_volume

            if rsi_oversold and volume_ok:
                self._execute_entry(symbol, current_price, rsi_value)

        except Exception as e:
            self.logger.error(f"Error checking entry: {e}")

    def _check_exit(self, symbol: str, rsi_value: float, current_price: float):
        """Verificar condiciones de salida"""
        try:
            position_data = self.active_positions[symbol]

            # Exit conditions
            rsi_overbought = rsi_value >= self.params.rsi_overbought
            max_holding_reached = (len(self.data) - position_data['entry_bar']) >= self.params.max_holding_bars

            # Calcular stop loss (5% loss)
            entry_price = position_data['entry_price']
            stop_loss = entry_price * 0.95

            stop_triggered = current_price <= stop_loss

            if rsi_overbought or max_holding_reached or stop_triggered:
                reason = "RSI_OVERBOUGHT" if rsi_overbought else "MAX_HOLDING" if max_holding_reached else "STOP_LOSS"
                self._execute_exit(symbol, reason, current_price)

        except Exception as e:
            self.logger.error(f"Error checking exit: {e}")

    def _execute_entry(self, symbol: str, price: float, rsi_value: float):
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
                'entry_rsi': rsi_value,
                'entry_time': self.data.datetime.datetime(),
                'entry_bar': len(self.data) - 1
            }

            self.executed_trades += 1

            self.logger.info(
                f"🎯 RSI_OVERSOLD ENTRY: {symbol} @ ${price:.2f} "
                f"Qty: {position_size} shares (${position_size * price:.2f}) "
                f"RSI: {rsi_value:.1f}"
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
                f"🔴 RSI_OVERSOLD EXIT: {symbol} @ ${current_price:.2f} "
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
        self.logger.info("RSI OVERSOLD BACKTEST RESULTS")
        self.logger.info("=" * 50)
        self.logger.info(f"Total Signals Generated: {self.total_signals}")
        self.logger.info(f"Trades Executed: {self.executed_trades}")
        self.logger.info(f"Final Portfolio Value: ${self.broker.getvalue():.2f}")
        self.logger.info(f"Total Return: ${total_return:.2f} ({total_return_pct:.2f}%)")
        self.logger.info(f"Win Rate: {win_rate:.1f}%")
        self.logger.info("=" * 50)