"""Consolidation Breakout Swing Worker

Main swing worker implementing dual entry modes:
- BREAKOUT: Small gap <3%, enter market open
- PULLBACK: Large gap >5%, wait for retrace + MACDV + RSI confirmation

Exit logic:
- Stop loss below support
- Target profit 50%
- Trailing stop at +15%/8%
- Time stop 30 days
"""

import asyncio
import logging
from datetime import datetime, timedelta
import talib
import pandas as pd

from .base_swing_worker import BaseSwingWorker
from core.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

class ConsolidationBreakoutWorker(BaseSwingWorker):
    def __init__(self, execution_engine, unified_manager, config_loader: ConfigLoader):
        super().__init__('consolidation_breakout', execution_engine, unified_manager, config_loader.get_section('SWING_WORKER'))
        self.config = config_loader.get_section('SWING_TRADING')

    async def _should_enter(self, pick: dict) -> bool:
        """Entry logic from scanner pick"""
        symbol = pick['symbol']
        
        # Premarket gap check
        gap = await self._get_premarket_gap(symbol)
        if gap > self.config.get('max_dangerous_gap_pct', 5.0):
            logger.info(f"⏳ {symbol}: Large gap {gap:.1f}%, waiting for PULLBACK")
            return await self._check_pullback_entry(pick)

        # Opening validation
        if not await self._validate_opening(symbol, pick):
            return False

        logger.info(f"✅ {symbol}: All BREAKOUT checks passed")
        return True

    async def _get_premarket_gap(self, symbol: str) -> float:
        """Get premarket gap %"""
        # Fetch premarket high/low vs prev close
        prev_close = await self.execution_engine.get_previous_close(symbol)
        current_price = await self.execution_engine.get_current_price(symbol)
        if prev_close:
            return ((current_price - prev_close) / prev_close) * 100
        return 0.0

    async def _validate_opening(self, symbol: str, pick: dict) -> bool:
        """Validate opening price and volume"""
        current_price = await self.execution_engine.get_current_price(symbol)
        if current_price < pick['support']:
            logger.info(f"❌ {symbol}: Opened below support ${pick['support']:.2f}")
            return False

        # Opening volume
        opening_vol = await self.execution_engine.get_volume_last_n_bars(symbol, 5)
        avg_vol = pick.get('avg_volume_90d', 100000)
        if opening_vol < avg_vol * self.config.get('min_opening_volume_ratio', 1.5):
            logger.info(f"❌ {symbol}: Low opening volume {opening_vol:,.0f} < {avg_vol*1.5:,.0f}")
            return False

        # Price action first 5 min
        if await self._detect_strong_selling_pressure(symbol):
            logger.info(f"❌ {symbol}: Selling pressure detected")
            return False

        return True

    async def _check_pullback_entry(self, pick: dict) -> bool:
        """Check pullback conditions"""
        symbol = pick['symbol']
        current_price = await self.execution_engine.get_current_price(symbol)
        
        # Pullback to resistance (now support)
        if current_price > pick['resistance'] * 0.98:
            logger.info(f"⏳ {symbol}: No pullback yet")
            return False

        # MACDV bullish
        macd_data = await self.execution_engine.get_macd_data(symbol)
        if not self._is_macd_bullish(macd_data):
            return False

        # RSI oversold
        rsi = await self.execution_engine.get_rsi(symbol)
        if rsi > self.config.get('pullback_rsi_oversold', 40):
            return False

        # Volume increasing
        vol_ratio = await self.execution_engine.get_volume_ratio_last_n_bars(symbol, 10)
        if vol_ratio < self.config.get('pullback_min_volume_ratio', 1.2):
            return False

        logger.info(f"✅ {symbol}: PULLBACK entry confirmed")
        return True

    def _is_macd_bullish(self, macd_data: pd.DataFrame) -> bool:
        """Check MACD bullish cross or divergence"""
        macd_line = macd_data['macd']
        signal_line = macd_data['signal']
        return macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]

    async def _should_exit_position(self, symbol: str, position: dict) -> tuple[bool, Optional[str]]:
        """Exit logic"""
        current_price = await self.execution_engine.get_current_price(symbol)
        entry_price = position['entry_price']
        pnl_pct = (current_price - entry_price) / entry_price * 100

        # Stop loss
        stop_loss = position['support'] * (1 - self.config.get('stop_loss_pct', 0.10))
        if current_price <= stop_loss:
            return True, f"STOP_LOSS ({pnl_pct:.1f}%)"

        # Time stop
        days_held = (datetime.now() - position['entry_time']).days
        if days_held >= self.config.get('max_hold_days', 30):
            return True, f"TIME_STOP ({pnl_pct:.1f}%)"

        # Trailing stop
        if pnl_pct >= self.config.get('trailing_stop_activation_pct', 15.0):
            trailing_stop = self._calculate_trailing_stop(current_price, pnl_pct)
            if current_price <= trailing_stop:
                return True, f"TRAILING_STOP ({pnl_pct:.1f}%)"

        # Target
        target = self.config.get('target_profit_pct', 50.0)
        if pnl_pct >= target:
            return True, f"TARGET ({pnl_pct:.1f}%)"

        # Distribution
        if await self._detect_distribution_pattern(symbol) and pnl_pct > 10:
            return True, f"DISTRIBUTION ({pnl_pct:.1f}%)"

        return False, None

    def _calculate_trailing_stop(self, current_price: float, pnl_pct: float) -> float:
        """Calculate trailing stop"""
        trail_pct = self.config.get('trailing_stop_distance_pct', 8.0) / 100
        return current_price * (1 - trail_pct)

    async def _detect_distribution_pattern(self, symbol: str) -> bool:
        """Detect distribution (high volume no price advance)"""
        # Simple heuristic: high vol, low price change
        vol = await self.execution_engine.get_volume_last_n_bars(symbol, 5)
        price_change = await self.execution_engine.get_price_change_pct_last_n_bars(symbol, 5)
        return vol > 2 * await self.execution_engine.get_avg_volume(symbol) and abs(price_change) < 1.0