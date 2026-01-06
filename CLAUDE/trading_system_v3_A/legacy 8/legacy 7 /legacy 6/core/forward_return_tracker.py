"""
Forward Return Tracker - Captura precios futuros para análisis de TP/SL

Proceso background que:
1. Detecta señales pendientes de tracking (signal_events sin forward_tracked_at)
2. Programa capturas de precios a 5m, 15m, 60m, 240m
3. Calcula returns y actualiza signal_events
4. Calcula MFE/MAE (Max Favorable/Adverse Excursion)

Este tracker es CRÍTICO para:
- Optimizar TP basado en percentiles de forward returns
- Analizar señales rechazadas (no solo trades ejecutados)
- Validar timing óptimo de salida
- Detectar SL demasiado amplios

Author: Trading System
Date: 2025-11-09
"""

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Import price fetcher (reuse existing infrastructure)
try:
    from data.market_data_fetcher import MarketDataFetcher
except ImportError:
    MarketDataFetcher = None

from core.trade_event_logger import TradeEventLogger


class ForwardReturnTracker:
    """
    Background process para capturar forward returns

    Corre como asyncio task que:
    1. Cada 1 minuto busca señales pendientes
    2. Para cada señal, programa capturas de precio
    3. Actualiza signal_events con forward returns
    """

    def __init__(
        self,
        db_path: str = "trading_data.db",
        check_interval_seconds: int = 60
    ):
        """
        Args:
            db_path: Ruta a trading_data.db
            check_interval_seconds: Cada cuántos segundos buscar señales pendientes
        """
        self.db_path = db_path
        self.check_interval_seconds = check_interval_seconds
        self.logger = logging.getLogger(__name__)
        self.event_logger = TradeEventLogger(db_path=db_path)

        # Market data fetcher (for getting current prices)
        self.market_data_fetcher = None
        if MarketDataFetcher:
            try:
                self.market_data_fetcher = MarketDataFetcher()
            except Exception as e:
                self.logger.warning(f"Could not initialize MarketDataFetcher: {e}")

        # Tracking tasks (signal_id -> asyncio.Task)
        self.active_tasks: Dict[str, asyncio.Task] = {}

        self.is_running = False

        self.logger.info("🔍 Forward Return Tracker initialized")

    async def start(self):
        """
        Inicia el tracker (background loop)
        """
        if self.is_running:
            self.logger.warning("Tracker already running")
            return

        self.is_running = True
        self.logger.info("🚀 Forward Return Tracker started")

        try:
            while self.is_running:
                await self._check_pending_signals()
                await asyncio.sleep(self.check_interval_seconds)

        except asyncio.CancelledError:
            self.logger.info("Forward Return Tracker cancelled")
        except Exception as e:
            self.logger.error(f"Error in tracker loop: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            self.is_running = False

    async def stop(self):
        """
        Detiene el tracker
        """
        self.logger.info("🛑 Stopping Forward Return Tracker...")
        self.is_running = False

        # Cancel active tasks
        for signal_id, task in self.active_tasks.items():
            if not task.done():
                task.cancel()

        self.active_tasks.clear()
        self.logger.info("Forward Return Tracker stopped")

    async def _check_pending_signals(self):
        """
        Busca señales que necesitan forward tracking y programa capturas
        """
        try:
            # Get signals pending tracking (last 24h)
            pending = self.event_logger.get_pending_forward_tracking(hours_back=24)

            if not pending:
                return

            self.logger.debug(f"Found {len(pending)} signals pending forward tracking")

            for signal in pending:
                signal_id = signal['signal_id']

                # Skip if already being tracked
                if signal_id in self.active_tasks:
                    continue

                # Create tracking task
                task = asyncio.create_task(
                    self._track_signal_forward_returns(signal)
                )

                self.active_tasks[signal_id] = task

                # Cleanup task when done
                task.add_done_callback(
                    lambda t, sid=signal_id: self.active_tasks.pop(sid, None)
                )

        except Exception as e:
            self.logger.error(f"Error checking pending signals: {e}")

    async def _track_signal_forward_returns(self, signal: Dict):
        """
        Rastrea forward returns para una señal específica

        Args:
            signal: Dict con datos de signal_events
        """
        signal_id = signal['signal_id']
        symbol = signal['symbol']
        entry_price = signal['entry_price']
        signal_timestamp = datetime.fromisoformat(signal['timestamp'])

        self.logger.info(
            f"📊 Tracking forward returns for {symbol} @ ${entry_price:.2f} "
            f"(signal_id: {signal_id[:8]}...)"
        )

        try:
            # Calculate target timestamps
            t_5m = signal_timestamp + timedelta(minutes=5)
            t_15m = signal_timestamp + timedelta(minutes=15)
            t_60m = signal_timestamp + timedelta(minutes=60)
            t_240m = signal_timestamp + timedelta(minutes=240)

            now = datetime.now()

            # Track price at each interval
            returns = {}
            prices = []

            # 5-minute return
            if now >= t_5m:
                price_5m = await self._get_price_at_time(symbol, t_5m)
                if price_5m:
                    returns['forward_5m'] = (price_5m - entry_price) / entry_price
                    prices.append(price_5m)
            else:
                # Wait until 5m mark
                wait_seconds = (t_5m - now).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                    price_5m = await self._get_price_at_time(symbol, t_5m)
                    if price_5m:
                        returns['forward_5m'] = (price_5m - entry_price) / entry_price
                        prices.append(price_5m)

            # 15-minute return
            if now >= t_15m:
                price_15m = await self._get_price_at_time(symbol, t_15m)
                if price_15m:
                    returns['forward_15m'] = (price_15m - entry_price) / entry_price
                    prices.append(price_15m)
            else:
                wait_seconds = (t_15m - now).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                    price_15m = await self._get_price_at_time(symbol, t_15m)
                    if price_15m:
                        returns['forward_15m'] = (price_15m - entry_price) / entry_price
                        prices.append(price_15m)

            # 60-minute return
            if now >= t_60m:
                price_60m = await self._get_price_at_time(symbol, t_60m)
                if price_60m:
                    returns['forward_60m'] = (price_60m - entry_price) / entry_price
                    prices.append(price_60m)
            else:
                wait_seconds = (t_60m - now).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                    price_60m = await self._get_price_at_time(symbol, t_60m)
                    if price_60m:
                        returns['forward_60m'] = (price_60m - entry_price) / entry_price
                        prices.append(price_60m)

            # 240-minute return (4 hours)
            if now >= t_240m:
                price_240m = await self._get_price_at_time(symbol, t_240m)
                if price_240m:
                    returns['forward_240m'] = (price_240m - entry_price) / entry_price
                    prices.append(price_240m)
            else:
                wait_seconds = (t_240m - now).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                    price_240m = await self._get_price_at_time(symbol, t_240m)
                    if price_240m:
                        returns['forward_240m'] = (price_240m - entry_price) / entry_price
                        prices.append(price_240m)

            # Calculate MFE/MAE (max/min price reached)
            max_price = max(prices) if prices else None
            min_price = min(prices) if prices else None

            # Update signal_events
            self.event_logger.update_forward_returns(
                signal_id=signal_id,
                forward_5m=returns.get('forward_5m'),
                forward_15m=returns.get('forward_15m'),
                forward_60m=returns.get('forward_60m'),
                forward_240m=returns.get('forward_240m'),
                max_price=max_price,
                min_price=min_price
            )

            self.logger.info(
                f"✅ Forward tracking completed for {symbol}: "
                f"5m={returns.get('forward_5m', 0)*100:+.2f}%, "
                f"15m={returns.get('forward_15m', 0)*100:+.2f}%, "
                f"60m={returns.get('forward_60m', 0)*100:+.2f}%, "
                f"240m={returns.get('forward_240m', 0)*100:+.2f}%"
            )

        except asyncio.CancelledError:
            self.logger.debug(f"Tracking cancelled for {signal_id}")
        except Exception as e:
            self.logger.error(f"Error tracking signal {signal_id}: {e}")

    async def _get_price_at_time(
        self,
        symbol: str,
        timestamp: datetime
    ) -> Optional[float]:
        """
        Obtiene precio del símbolo en un timestamp específico

        Args:
            symbol: Símbolo
            timestamp: Timestamp target

        Returns:
            Precio o None si no disponible
        """
        try:
            # Strategy 1: Use MarketDataFetcher if available
            if self.market_data_fetcher:
                # Get 1-minute bar closest to target timestamp
                bars = await self._fetch_bars_around_time(symbol, timestamp)

                if bars:
                    # Find closest bar to target timestamp
                    closest_bar = min(
                        bars,
                        key=lambda b: abs(
                            (b.get('timestamp') - timestamp).total_seconds()
                        )
                    )
                    return closest_bar.get('close')

            # Strategy 2: Query trade_intraday_bars table
            price = self._get_price_from_db(symbol, timestamp)
            if price:
                return price

            # Strategy 3: Use current price if timestamp is very recent (< 5 min ago)
            if (datetime.now() - timestamp).total_seconds() < 300:
                if self.market_data_fetcher:
                    current_price = await self._get_current_price(symbol)
                    if current_price:
                        return current_price

            self.logger.warning(
                f"Could not get price for {symbol} at {timestamp.strftime('%H:%M:%S')}"
            )
            return None

        except Exception as e:
            self.logger.error(f"Error getting price for {symbol} at {timestamp}: {e}")
            return None

    async def _fetch_bars_around_time(
        self,
        symbol: str,
        timestamp: datetime,
        window_minutes: int = 5
    ) -> List[Dict]:
        """
        Fetches bars around a specific timestamp

        Args:
            symbol: Symbol
            timestamp: Target timestamp
            window_minutes: Window to search (±N minutes)

        Returns:
            List of bars
        """
        try:
            if not self.market_data_fetcher:
                return []

            # This would use your MarketDataFetcher to get bars
            # Implementation depends on your data provider
            # For now, return empty (will fall back to DB)
            return []

        except Exception as e:
            self.logger.error(f"Error fetching bars: {e}")
            return []

    def _get_price_from_db(
        self,
        symbol: str,
        timestamp: datetime,
        tolerance_minutes: int = 2
    ) -> Optional[float]:
        """
        Gets price from trade_intraday_bars or market_intraday_bars table

        Args:
            symbol: Symbol
            timestamp: Target timestamp
            tolerance_minutes: How many minutes tolerance for match

        Returns:
            Close price or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Try trade_intraday_bars first
            cursor.execute('''
                SELECT close_price
                FROM trade_intraday_bars
                WHERE symbol = ?
                  AND ABS((julianday(bar_timestamp) - julianday(?)) * 1440) <= ?
                ORDER BY ABS((julianday(bar_timestamp) - julianday(?)) * 1440)
                LIMIT 1
            ''', (symbol, timestamp, tolerance_minutes, timestamp))

            row = cursor.fetchone()

            if row:
                conn.close()
                return row[0]

            # Try market_intraday_bars
            cursor.execute('''
                SELECT close_price
                FROM market_intraday_bars
                WHERE symbol = ?
                  AND ABS((julianday(bar_timestamp) - julianday(?)) * 1440) <= ?
                ORDER BY ABS((julianday(bar_timestamp) - julianday(?)) * 1440)
                LIMIT 1
            ''', (symbol, timestamp, tolerance_minutes, timestamp))

            row = cursor.fetchone()
            conn.close()

            return row[0] if row else None

        except Exception as e:
            self.logger.error(f"Error querying DB for price: {e}")
            return None

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        Gets current live price for symbol

        Args:
            symbol: Symbol

        Returns:
            Current price or None
        """
        try:
            if not self.market_data_fetcher:
                return None

            # This would use your market data provider
            # Implementation depends on your setup
            return None

        except Exception as e:
            self.logger.error(f"Error getting current price: {e}")
            return None


# =============================================================================
# Standalone Runner (for testing or running as separate process)
# =============================================================================

async def main():
    """
    Standalone runner for Forward Return Tracker
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    tracker = ForwardReturnTracker(
        db_path="trading_data.db",
        check_interval_seconds=60  # Check every minute
    )

    print("=" * 80)
    print("FORWARD RETURN TRACKER - Standalone Mode")
    print("=" * 80)
    print()
    print("Starting tracker...")
    print("Press Ctrl+C to stop")
    print()

    try:
        await tracker.start()
    except KeyboardInterrupt:
        print("\n\nStopping tracker...")
        await tracker.stop()
        print("Tracker stopped")


if __name__ == "__main__":
    asyncio.run(main())
