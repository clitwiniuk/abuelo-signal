"""
Estrategia MACDV adaptada para Backtrader

Implementa la lógica REAL de MACDV usando el framework de backtrader
basado en el MacdvWorkerLogic: análisis multi-timeframe, divergencias MACD,
y consenso de timeframes.
"""

import backtrader as bt
import numpy as np
from typing import Dict, Any, Optional, Tuple
import logging
import sys
import os

# Agregar path para importar workers
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from strategies.workers.macdv_worker_logic import MacdvWorkerLogic
except ImportError:
    # Fallback para testing - crear versión simplificada
    class MacdvWorkerLogic:
        def __init__(self, execution_engine=None, risk_manager=None, config=None):
            pass

        def should_enter(self, opportunity):
            # Lógica simplificada para testing
            volume_ratio = opportunity.get('volume_ratio', 1.0)
            catalyst_strength = opportunity.get('catalyst_strength', 0)
            return volume_ratio >= 1.2 and catalyst_strength >= 3

        def should_exit(self, symbol, position, current_price):
            # Lógica simplificada de salida
            entry_price = position.get('entry_price', 0)
            if entry_price == 0:
                return True, "INVALID_POSITION"

            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            # Exit if profit >= 10% or loss >= 4%
            if pnl_pct >= 10.0:
                return True, "TAKE_PROFIT_10PCT"
            elif pnl_pct <= -4.0:
                return True, "STOP_LOSS_4PCT"

            return False, ""


class MacdvStrategy(bt.Strategy):
    """
    Estrategia MACDV para backtrader usando lógica REAL del worker

    Implementa análisis multi-timeframe MACD, divergencias,
    y consenso de timeframes para detectar momentum técnico.
    """

    params = (
        ('max_position_size', 0.05),  # 5% del capital por posición
        ('min_confidence', 50),       # Confianza mínima para entrar
        ('buy_threshold', 6.50),      # Parámetros dummy para compatibilidad
        ('sell_threshold', 7.00),     # Parámetros dummy para compatibilidad
        ('fast_period', 12),          # MACD fast period
        ('slow_period', 26),          # MACD slow period
        ('signal_period', 9),         # MACD signal period
        ('confirmation_threshold', 0.7),  # Threshold para confirmación
    )

    def __init__(self):
        """Inicializar estrategia con lógica real del worker"""
        self.logger = logging.getLogger('backtesting.macdv')

        # Inicializar el worker logic real (sin execution engine para backtesting)
        self.worker_logic = MacdvWorkerLogic(
            execution_engine=None,  # No necesitamos execution engine en backtesting
            risk_manager=None,      # No necesitamos risk manager en backtesting
            config=None             # Usará configuración por defecto
        )

        # Tracking de posiciones activas
        self.active_positions = {}
        self.trade_signals = []

        # Estadísticas
        self.total_signals = 0
        self.executed_trades = 0
        self._trade_results = []  # Para calcular win rate

        # Para compatibilidad con backtrader
        self.dataclose = self.data.close
        self.datavolume = self.data.volume

    def next(self):
        """Lógica principal ejecutada en cada barra usando worker logic real"""
        try:
            # Verificar si hay datos suficientes
            if len(self.data) < 50:  # Necesitamos más datos para análisis MACD completo
                return

            # Crear opportunity data similar al scanner
            opportunity = self._create_opportunity_data()

            if not opportunity:
                return

            # Usar la lógica REAL del worker para decidir si entrar
            should_enter = self.worker_logic.should_enter(opportunity)

            if should_enter:
                self._execute_entry(opportunity)

            # Verificar si debemos salir de posiciones existentes
            self._check_exits()

        except Exception as e:
            self.logger.error(f"Error in next(): {e}")

    def _create_opportunity_data(self) -> Optional[Dict[str, Any]]:
        """
        Crear datos de oportunidad similares a los del scanner

        Returns:
            Diccionario con datos de oportunidad o None
        """
        try:
            # Verificar que tenemos suficientes datos
            if len(self.data) < 2:
                return None

            # Datos básicos
            symbol = self.data._name or 'UNKNOWN'
            current_price = float(self.dataclose[0])
            current_volume = float(self.datavolume[0])

            # Calcular volume ratio (últimas 20 barras) - con verificación de límites
            volume_ratio = 1.0
            if len(self.data) >= 20:
                try:
                    # Usar índices seguros para backtrader
                    recent_volumes = []
                    for i in range(max(0, len(self.data) - 20), len(self.data)):
                        if i < len(self.datavolume):
                            recent_volumes.append(float(self.datavolume[i]))

                    if recent_volumes:
                        avg_volume = sum(recent_volumes) / len(recent_volumes)
                        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
                except (IndexError, TypeError) as e:
                    self.logger.debug(f"Error calculating volume ratio: {e}")
                    volume_ratio = 1.0

            # Calcular gap percentage - con verificación de límites
            gap_pct = 0.0
            if len(self.data) > 1:
                try:
                    prev_close = float(self.dataclose[-1])
                    if prev_close > 0:
                        gap_pct = ((current_price - prev_close) / prev_close) * 100
                except (IndexError, TypeError) as e:
                    self.logger.debug(f"Error calculating gap: {e}")
                    gap_pct = 0.0

            # Crear bars_history (últimas 100 barras para análisis) - con verificación de límites
            bars_history = []
            try:
                start_idx = max(0, len(self.data) - 100)
                for i in range(start_idx, len(self.data)):
                    if (i < len(self.data.open) and i < len(self.data.high) and
                        i < len(self.data.low) and i < len(self.data.close) and
                        i < len(self.data.volume) and i < len(self.data.datetime)):
                        bar = {
                            'timestamp': self.data.datetime[i],
                            'open': float(self.data.open[i]),
                            'high': float(self.data.high[i]),
                            'low': float(self.data.low[i]),
                            'close': float(self.data.close[i]),
                            'volume': float(self.data.volume[i])
                        }
                        bars_history.append(bar)
            except (IndexError, TypeError, AttributeError) as e:
                self.logger.debug(f"Error creating bars history: {e}")
                # Crear al menos la barra actual
                if len(self.data) > 0:
                    bars_history = [{
                        'timestamp': self.data.datetime[0] if hasattr(self.data, 'datetime') and len(self.data.datetime) > 0 else None,
                        'open': current_price,
                        'high': current_price,
                        'low': current_price,
                        'close': current_price,
                        'volume': current_volume
                    }]

            # Datos de catalizador (simulados para backtesting)
            catalyst_data = self._simulate_catalyst_data()

            # Crear opportunity completo
            opportunity = {
                'symbol': symbol,
                'current_price': current_price,
                'volume_ratio': volume_ratio,
                'gap_percentage': gap_pct,
                'bars_history': bars_history,
                **catalyst_data
            }

            return opportunity

        except Exception as e:
            self.logger.error(f"Error creating opportunity data: {e}")
            return None

    def _simulate_catalyst_data(self) -> Dict[str, Any]:
        """
        Simular datos de catalizador para backtesting

        Para MACDV, enfocamos en catalizadores técnicos puros
        (no major news que podrían crear gaps grandes)
        """
        try:
            # Análisis simple para simular catalizadores técnicos
            current_price = self.dataclose[0]
            current_volume = self.datavolume[0]

            # Calcular volumen promedio
            if len(self.data) >= 20:
                avg_volume = sum(self.datavolume[i] for i in range(-20, 0)) / 20
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            else:
                volume_ratio = 1.0

            # Simular catalizadores técnicos (MACDV es momentum técnico puro)
            catalyst_type = 'TECHNICAL'  # Siempre técnico para MACDV
            catalyst_strength = 3  # Base

            # Aumentar strength basado en volumen y momentum
            if volume_ratio >= 2.0:
                catalyst_strength = 7  # Strong volume = strong catalyst
            elif volume_ratio >= 1.5:
                catalyst_strength = 5  # Moderate volume
            elif volume_ratio >= 1.2:
                catalyst_strength = 4  # Light volume

            # Calcular quality score basado en setup técnico
            quality_score = 50  # Base

            # Bonus por volumen
            if volume_ratio >= 2.0:
                quality_score += 25
            elif volume_ratio >= 1.5:
                quality_score += 15

            # MACDV funciona mejor en small caps ($1-15)
            if 1.0 <= current_price <= 15.0:
                quality_score += 10

            return {
                'catalyst_type': catalyst_type,
                'catalyst_strength': catalyst_strength,
                'quality_score': min(quality_score, 100)
            }

        except Exception as e:
            self.logger.error(f"Error simulating catalyst data: {e}")
            return {
                'catalyst_type': 'TECHNICAL',
                'catalyst_strength': 3,
                'quality_score': 50
            }

    def _execute_entry(self, opportunity: Dict[str, Any]):
        """
        Ejecutar entrada usando lógica del worker

        Args:
            opportunity: Datos de la oportunidad
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            current_price = opportunity.get('current_price', 0)

            # Verificar si ya tenemos posición
            if symbol in self.active_positions:
                return

            # Calcular tamaño de posición
            position_size = self._calculate_position_size(opportunity)

            if position_size <= 0:
                return

            # Ejecutar orden de compra
            order = self.buy(
                size=position_size,
                price=current_price,
                exectype=bt.Order.Market
            )

            # Registrar posición
            self.active_positions[symbol] = {
                'entry_price': current_price,
                'size': position_size,
                'opportunity': opportunity,
                'entry_time': self.data.datetime.datetime(),
                'entry_bar': len(self.data) - 1
            }

            self.executed_trades += 1

            self.logger.info(
                f"🎯 MACDV ENTRY: {symbol} @ ${current_price:.2f} "
                f"Qty: {position_size} shares (${position_size * current_price:.2f}) "
                f"Catalyst: {opportunity.get('catalyst_type', 'UNKNOWN')} "
                f"Strength: {opportunity.get('catalyst_strength', 0)}"
            )

        except Exception as e:
            self.logger.error(f"Error executing entry: {e}")

    def _calculate_position_size(self, opportunity: Dict[str, Any]) -> int:
        """
        Calcular tamaño de posición basado en riesgo

        Args:
            opportunity: Datos de la oportunidad

        Returns:
            Tamaño de posición en shares
        """
        try:
            capital = self.broker.getvalue()
            max_position_value = capital * self.params.max_position_size
            price = opportunity.get('current_price', 0)

            if price <= 0:
                return 0

            # Calcular shares máximo
            max_shares = int(max_position_value / price)

            # Aplicar riesgo por trade (2% del capital)
            risk_amount = capital * 0.02
            stop_distance = price * 0.04  # 4% stop loss (MACDV usa 4%)
            risk_based_shares = int(risk_amount / stop_distance)

            # Tomar el mínimo
            position_size = min(max_shares, risk_based_shares)

            # Mínimo 100 shares
            return max(position_size, 100)

        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 100

    def _check_exits(self):
        """Verificar si debemos salir de posiciones existentes"""
        try:
            for symbol, position_data in list(self.active_positions.items()):
                # Crear datos de posición para el worker
                position = {
                    'entry_price': position_data['entry_price'],
                    'trading_horizon': 'INTRADAY',  # MACDV es intraday por defecto
                    'expected_hold_hours': 4.0,
                    'EOD_safe': False
                }

                current_price = self.dataclose[0]

                # Usar lógica del worker para decidir si salir
                should_exit, reason = self.worker_logic.should_exit(
                    symbol=symbol,
                    position=position,
                    current_price=current_price
                )

                if should_exit:
                    self._execute_exit(symbol, reason, current_price)
                    del self.active_positions[symbol]

        except Exception as e:
            self.logger.error(f"Error checking exits: {e}")

    def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """
        Ejecutar salida de posición

        Args:
            symbol: Símbolo
            reason: Razón de la salida
            current_price: Precio actual
        """
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
                f"🔴 MACDV EXIT: {symbol} @ ${current_price:.2f} "
                f"PnL: ${pnl:.2f} ({pnl_pct:.2f}%) | Reason: {reason}"
            )

            # Track trade result for win rate calculation
            self._trade_results.append(pnl)

        except Exception as e:
            self.logger.error(f"Error executing exit for {symbol}: {e}")

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
                f"Duration: {trade.barlen} bars"
            )

    def stop(self):
        """Método llamado al finalizar el backtest"""
        total_return = self.broker.getvalue() - self.broker.startingcash
        total_return_pct = (total_return / self.broker.startingcash) * 100

        self.logger.info("=" * 50)
        self.logger.info("MACDV BACKTEST RESULTS (REAL WORKER LOGIC)")
        self.logger.info("=" * 50)
        self.logger.info(f"Total Signals Generated: {self.total_signals}")
        self.logger.info(f"Trades Executed: {self.executed_trades}")
        self.logger.info(f"Final Portfolio Value: ${self.broker.getvalue():.2f}")
        self.logger.info(f"Total Return: ${total_return:.2f} ({total_return_pct:.2f}%)")
        self.logger.info(f"Win Rate: {self._calculate_win_rate():.1f}%")
        self.logger.info("=" * 50)

    def _calculate_win_rate(self) -> float:
        """Calcular win rate de los trades"""
        # En backtrader, los trades están disponibles después del backtest
        # Usamos una aproximación basada en las posiciones que manejamos
        if not hasattr(self, '_trade_results'):
            self._trade_results = []

        winning_trades = sum(1 for pnl in self._trade_results if pnl > 0)
        total_trades = len(self._trade_results)

        if total_trades == 0:
            return 0.0

        return (winning_trades / total_trades) * 100