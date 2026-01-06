"""
Market Regime Detector
======================
Detecta el régimen de mercado actual (BULL, BEAR, VOLATILE, LOW_LIQUIDITY)
y ajusta automáticamente los parámetros de entrada de los workers

Regímenes detectados:
- BULL_HIGH_LIQUIDITY: Mercado alcista con alto volumen (criterios estrictos)
- BULL_LOW_LIQUIDITY: Mercado alcista con bajo volumen (criterios relajados)
- BEAR_HIGH_VOL: Mercado bajista con alta volatilidad (muy conservador)
- BEAR_LOW_VOL: Mercado bajista consolidando (moderadamente conservador)
- CHOPPY: Mercado lateral sin tendencia clara (selectivo)
- PANIC: Mercado en pánico (desactivar entradas)
"""

import asyncio
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import numpy as np


class MarketRegime(Enum):
    """Regímenes de mercado detectables"""
    BULL_HIGH_LIQUIDITY = "bull_high_liquidity"
    BULL_LOW_LIQUIDITY = "bull_low_liquidity"
    BEAR_HIGH_VOL = "bear_high_vol"
    BEAR_LOW_VOL = "bear_low_vol"
    CHOPPY = "choppy"
    PANIC = "panic"
    UNKNOWN = "unknown"


@dataclass
class MarketConditions:
    """Condiciones actuales del mercado"""
    regime: MarketRegime
    spy_trend: float  # % change in SPY today
    spy_volatility: float  # VIX or ATR-based volatility
    volume_ratio: float  # Current volume vs average
    liquidity_score: float  # 0-100, based on spread + volume
    sentiment_score: float  # -100 to +100
    confidence: float  # 0-100, confidence in regime detection
    timestamp: datetime

    def is_favorable_for_entries(self) -> bool:
        """Determina si las condiciones son favorables para entradas"""
        # Pánico = NO entrar
        if self.regime == MarketRegime.PANIC:
            return False

        # Bear volátil = Muy selectivo
        if self.regime == MarketRegime.BEAR_HIGH_VOL and self.confidence > 70:
            return False

        return True

    def get_risk_adjustment_factor(self) -> float:
        """
        Factor de ajuste de riesgo (0.5 = muy conservador, 1.0 = normal, 1.5 = agresivo)
        """
        if self.regime == MarketRegime.BULL_HIGH_LIQUIDITY:
            return 1.2  # Ligeramente más agresivo
        elif self.regime == MarketRegime.BULL_LOW_LIQUIDITY:
            return 1.0  # Normal
        elif self.regime == MarketRegime.BEAR_LOW_VOL:
            return 0.7  # Conservador
        elif self.regime == MarketRegime.BEAR_HIGH_VOL:
            return 0.5  # Muy conservador
        elif self.regime == MarketRegime.CHOPPY:
            return 0.8  # Selectivo
        elif self.regime == MarketRegime.PANIC:
            return 0.0  # Sin entradas
        else:
            return 1.0  # Default


class MarketRegimeDetector:
    """
    Detector de régimen de mercado basado en SPY/QQQ

    Singleton - Una sola instancia compartida por todos los workers
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.logger = logging.getLogger("MarketRegimeDetector")

        # Current market conditions
        self.current_conditions: Optional[MarketConditions] = None

        # Update frequency
        self.update_interval_seconds = 900  # 15 minutos
        self.last_update: Optional[datetime] = None

        # Historical data cache
        self.spy_bars_cache = []
        self.vix_value_cache = None

        # IBKR adapter (injected)
        self.ibkr_adapter = None

        # Background task
        self.update_task = None
        self.is_running = False

        self._initialized = True
        self.logger.info("🌍 Market Regime Detector initialized")

    def set_ibkr_adapter(self, adapter):
        """Inject IBKR adapter for market data"""
        self.ibkr_adapter = adapter
        self.logger.info("✅ IBKR adapter injected into MarketRegimeDetector")

    async def start(self):
        """Start background regime detection"""
        if self.is_running:
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())
        self.logger.info("🚀 Market regime detection started (updates every 15min)")

    async def stop(self):
        """Stop background regime detection"""
        self.is_running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        self.logger.info("🛑 Market regime detection stopped")

    async def _update_loop(self):
        """Background loop to update market regime"""
        while self.is_running:
            try:
                await self.update_market_regime()
                await asyncio.sleep(self.update_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error updating market regime: {e}")
                await asyncio.sleep(60)  # Retry in 1 minute

    async def update_market_regime(self) -> MarketConditions:
        """
        Update market regime detection

        Returns:
            MarketConditions object with current regime
        """
        try:
            self.logger.info("🔍 Analyzing market regime...")

            # If no IBKR adapter, return default conditions
            if not self.ibkr_adapter:
                self.logger.warning("⚠️ No IBKR adapter - using default regime")
                self.current_conditions = self._get_default_conditions()
                return self.current_conditions

            # Fetch SPY data (1-minute bars, last 60 minutes)
            spy_bars = await self._fetch_spy_bars()

            if not spy_bars or len(spy_bars) < 30:
                self.logger.warning("⚠️ Insufficient SPY data - using cached regime")
                if self.current_conditions:
                    return self.current_conditions
                self.current_conditions = self._get_default_conditions()
                return self.current_conditions

            # Calculate market metrics
            spy_trend = self._calculate_spy_trend(spy_bars)
            spy_volatility = self._calculate_volatility(spy_bars)
            volume_ratio = self._calculate_volume_ratio(spy_bars)
            liquidity_score = self._calculate_liquidity_score(spy_bars, volume_ratio)
            sentiment_score = self._calculate_sentiment(spy_trend, spy_volatility)

            # Detect regime
            regime, confidence = self._detect_regime(
                spy_trend, spy_volatility, volume_ratio, liquidity_score, sentiment_score
            )

            # Create conditions object
            self.current_conditions = MarketConditions(
                regime=regime,
                spy_trend=spy_trend,
                spy_volatility=spy_volatility,
                volume_ratio=volume_ratio,
                liquidity_score=liquidity_score,
                sentiment_score=sentiment_score,
                confidence=confidence,
                timestamp=datetime.now()
            )

            self.last_update = datetime.now()

            # Log regime
            self.logger.info(
                f"📊 Market Regime: {regime.value.upper()} "
                f"(confidence: {confidence:.0f}%)"
            )
            self.logger.info(
                f"   SPY: {spy_trend:+.2f}%, Vol: {spy_volatility:.1f}%, "
                f"Volume: {volume_ratio:.1f}x, Liquidity: {liquidity_score:.0f}"
            )

            return self.current_conditions

        except Exception as e:
            self.logger.error(f"❌ Error detecting market regime: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

            # Return cached or default
            if self.current_conditions:
                return self.current_conditions
            return self._get_default_conditions()

    async def _fetch_spy_bars(self) -> list:
        """Fetch SPY 1-minute bars from IBKR"""
        try:
            # Request 60 minutes of SPY data
            from ib_insync import Stock
            spy = Stock('SPY', 'SMART', 'USD')

            # Qualify contract
            await self.ibkr_adapter.ib.qualifyContractsAsync(spy)

            # Request bars
            bars = await self.ibkr_adapter.ib.reqHistoricalDataAsync(
                spy,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True
            )

            self.spy_bars_cache = bars
            return bars

        except Exception as e:
            self.logger.debug(f"Could not fetch SPY bars: {e}")
            return self.spy_bars_cache  # Return cached

    def _calculate_spy_trend(self, bars) -> float:
        """Calculate SPY % change today"""
        if not bars or len(bars) < 2:
            return 0.0

        # Compare current price to first bar of day
        first_price = bars[0].open
        current_price = bars[-1].close

        return ((current_price - first_price) / first_price) * 100

    def _calculate_volatility(self, bars) -> float:
        """Calculate recent volatility (ATR-based)"""
        if not bars or len(bars) < 14:
            return 1.0  # Default volatility

        # Simple ATR calculation
        recent_bars = bars[-14:]
        ranges = [(bar.high - bar.low) for bar in recent_bars]
        atr = np.mean(ranges)

        # Normalize to percentage of price
        current_price = bars[-1].close
        atr_pct = (atr / current_price) * 100

        return atr_pct

    def _calculate_volume_ratio(self, bars) -> float:
        """Calculate volume ratio vs average"""
        if not bars or len(bars) < 30:
            return 1.0

        # Compare recent 15min volume to average
        recent_volume = sum(bar.volume for bar in bars[-15:])
        avg_volume = sum(bar.volume for bar in bars[-60:-15]) / 45 * 15

        if avg_volume == 0:
            return 1.0

        return recent_volume / avg_volume

    def _calculate_liquidity_score(self, bars, volume_ratio: float) -> float:
        """Calculate liquidity score (0-100)"""
        if not bars:
            return 50.0  # Default

        # Factors: volume ratio + tight spreads
        volume_score = min(volume_ratio * 30, 60)  # Max 60 points

        # Spread score (tight spreads = higher liquidity)
        recent_bars = bars[-10:]
        avg_spread = np.mean([(bar.high - bar.low) / bar.close for bar in recent_bars])
        spread_score = max(0, 40 - (avg_spread * 1000))  # Max 40 points

        return volume_score + spread_score

    def _calculate_sentiment(self, spy_trend: float, volatility: float) -> float:
        """Calculate market sentiment (-100 to +100)"""
        # Simple: positive trend = positive sentiment
        sentiment = spy_trend * 10  # -100 to +100 range

        # Penalize high volatility (fear)
        if volatility > 2.0:  # High volatility
            sentiment -= 20

        return max(-100, min(100, sentiment))

    def _detect_regime(
        self,
        spy_trend: float,
        volatility: float,
        volume_ratio: float,
        liquidity_score: float,
        sentiment: float
    ) -> Tuple[MarketRegime, float]:
        """
        Detect market regime based on metrics

        Returns:
            (MarketRegime, confidence_percentage)
        """
        confidence = 0.0

        # PANIC DETECTION (highest priority)
        if spy_trend < -2.0 and volatility > 3.0:
            return MarketRegime.PANIC, 90.0

        # BEAR HIGH VOL
        if spy_trend < -1.0 and volatility > 2.0:
            confidence = 75.0 + (abs(spy_trend) * 5)
            return MarketRegime.BEAR_HIGH_VOL, min(confidence, 95.0)

        # BEAR LOW VOL (consolidation after drop)
        if spy_trend < -0.5 and volatility < 1.5:
            confidence = 70.0
            return MarketRegime.BEAR_LOW_VOL, confidence

        # BULL HIGH LIQUIDITY
        if spy_trend > 0.5 and liquidity_score > 70:
            confidence = 80.0 + (spy_trend * 2)
            return MarketRegime.BULL_HIGH_LIQUIDITY, min(confidence, 95.0)

        # BULL LOW LIQUIDITY (Friday afternoons, low volume rallies)
        if spy_trend > 0.3 and liquidity_score < 60:
            confidence = 75.0
            return MarketRegime.BULL_LOW_LIQUIDITY, confidence

        # CHOPPY (no clear direction)
        if abs(spy_trend) < 0.3 and volatility < 1.5:
            confidence = 70.0
            return MarketRegime.CHOPPY, confidence

        # DEFAULT: Unknown (use cautious settings)
        return MarketRegime.UNKNOWN, 50.0

    def _get_default_conditions(self) -> MarketConditions:
        """Get default market conditions (used as fallback)"""
        return MarketConditions(
            regime=MarketRegime.UNKNOWN,
            spy_trend=0.0,
            spy_volatility=1.5,
            volume_ratio=1.0,
            liquidity_score=50.0,
            sentiment_score=0.0,
            confidence=50.0,
            timestamp=datetime.now()
        )

    def get_current_regime(self) -> Optional[MarketConditions]:
        """Get current market regime (cached)"""
        # If no update yet, trigger one synchronously
        if self.current_conditions is None:
            self.logger.warning("⚠️ No regime detected yet - using default")
            self.current_conditions = self._get_default_conditions()

        return self.current_conditions

    def should_allow_entries(self) -> bool:
        """Quick check: should workers allow entries in current regime?"""
        conditions = self.get_current_regime()
        if not conditions:
            return True  # Default to allowing entries

        return conditions.is_favorable_for_entries()


# Singleton accessor
_detector_instance = None

def get_market_regime_detector() -> MarketRegimeDetector:
    """Get singleton instance of market regime detector"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = MarketRegimeDetector()
    return _detector_instance
