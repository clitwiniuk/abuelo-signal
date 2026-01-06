"""
Estrategia Volume Price Confirmation para Backtrader

Compra cuando precio sube con volumen alto, vende cuando precio baja con volumen alto.
Efectiva para confirmar momentum real en small caps.
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


class VolumePriceStrategy(bt.Strategy):
    """
    Estrategia Volume Price Confirmation para small caps

    Compra cuando precio sube + volumen alto
    Vende cuando precio baja + volumen alto
    """

    params = (
        ('volume_multiplier', 1.5),  # Volumen debe ser 1.5x promedio
        ('price_change_pct', 0.5),   # Cambio de precio mínimo 0.5%
        ('max_position_size', 0.10), # 10% del capital por posición
        ('max_holding_bars', 50),    # Máximo 50 barras (1 hora)
        ('volume_period', 20),       # Período para calcular promedio de volumen
    )

    def __init__(self):
        """Inicializar estrategia con indicadores"""
        self.logger = logging.getLogger('backtesting.volume_price')

        # Indicadores de volumen
        self.avg_volume = bt.indicators.SMA(
            self.data.volume,
            period=self.params.volume_period
        )

        # Tracking
        self.active_positions = {}
        self.total_signals = 0
        self.executed_trades = 0
        self._trade_results = []

        # Para compatibilidad con backtrader
        self.dataclose = self.data.close
        self.dataopen = self.data.open
        self.datavolume = self.data.volume

    def next(self):
        """Lógica principal ejecutada en cada barra"""
        try:
            # Verificar que tenemos suficientes datos
            if len(self.data) < self.params.volume_period + 5:
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
            if len(self.data) < 2:
                return

            # Calcular cambio de precio
            prev_close = float(self.dataclose[-1])
            price_change_pct = ((current_price - prev_close) / prev_close) * 100

            # Calcular volumen actual vs promedio
            current_volume = float(self.datavolume[0])
            avg_volume = float(self.avg_volume[0]) if len(self.avg_volume) > 0 else 0

            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Condiciones de entrada
            price_up = price_change_pct >= self.params.price_change_pct
            volume_high = volume_ratio >= self.params.volume_multiplier

            if price_up and volume_high:
                self._execute_entry(symbol, current_price, price_change_pct, volume_ratio)

        except Exception as e:
            self.logger.error(f"Error checking entry: {e}")

    def _check_exit(self, symbol: str, current_price: float):
        """Verificar condiciones de salida"""
        try:
            position_data = self.active_positions[symbol]

            # Verificar que tenemos suficientes datos
            if len(self.data) < 2:
                return

            # Calcular cambio de precio actual
            prev_close = float(self.dataclose[-1])
            price_change_pct = ((current_price - prev_close) / prev_close) * 100

            # Calcular volumen actual vs promedio
            current_volume = float(self.datavolume[0])
            avg_volume = float(self.avg_volume[0]) if len(self.avg_volume) > 0 else 0

            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Condiciones de salida: precio baja con volumen alto
            price_down = price_change_pct <= -self.params.price_change_pct
            volume_high = volume_ratio >= self.params.volume_multiplier

            # Stop loss (5% loss)
            entry_price = position_data['entry_price']
            stop_loss = entry_price * 0.95
            stop_triggered = current_price <= stop_loss

            # Max holding time
            max_holding_reached = (len(self.data) - position_data['entry_bar']) >= self.params.max_holding_bars

            if (price_down and volume_high) or stop_triggered or max_holding_reached:
                reason = "PRICE_DOWN_VOLUME" if (price_down and volume_high) else "STOP_LOSS" if stop_triggered else "MAX_HOLDING"
                self._execute_exit(symbol, reason, current_price)

        except Exception as e:
            self.logger.error(f"Error checking exit: {e}")

    def _execute_entry(self, symbol: str, price: float, price_change: float, volume_ratio: float):
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
                'entry_bar': len(self.data) - 1,
                'price_change': price_change,
                'volume_ratio': volume_ratio
            }

            self.executed_trades += 1

            self.logger.info(
                f"🎯 VOLUME_PRICE ENTRY: {symbol} @ ${price:.2f} "
                f"Qty: {position_size} shares (${position_size * price:.2f}) "
                f"Price Change: {price_change:.2f}%, Volume Ratio: {volume_ratio:.1f}x"
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
                f"🔴 VOLUME_PRICE EXIT: {symbol} @ ${current_price:.2f} "
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
        self.logger.info("VOLUME PRICE BACKTEST RESULTS")
        self.logger.info("=" * 50)
        self.logger.info(f"Total Signals Generated: {self.total_signals}")
        self.logger.info(f"Trades Executed: {self.executed_trades}")
        self.logger.info(f"Final Portfolio Value: ${self.broker.getvalue():.2f}")
        self.logger.info(f"Total Return: ${total_return:.2f} ({total_return_pct:.2f}%)")
        self.logger.info(f"Win Rate: {win_rate:.1f}%")
        self.logger.info("=" * 50)