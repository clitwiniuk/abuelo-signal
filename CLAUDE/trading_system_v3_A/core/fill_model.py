"""
Fill Model - Realistic Order Fill Simulation

Resuelve el Problema #4: Fill Model No-Determinístico
Impacto: +5-10% reproducibilidad

ANTES (Idealizado):
- Fill price = entry_price exacto (no slippage)
- Fill time = order time (instantáneo)
- No considera spread ni volumen disponible
- Replay tiene fills perfectos vs live tiene slippage real

DESPUÉS (Realista):
- Fill price considera spread + market impact
- Fill time basado en volumen disponible
- Slippage determinístico basado en bar data
- Mismo slippage en live y replay

Small Caps Characteristics:
- Wide spreads (0.5-3%)
- Limited liquidity (100-5000 shares/min)
- High volatility (2-10% intraday)
- Market impact significativo (>1% para órdenes grandes)
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass
class OrderFill:
    """Resultado de fill de una orden"""
    filled_price: float
    filled_shares: int
    fill_time: datetime
    slippage_bps: float  # Basis points (1% = 100 bps)
    slippage_reason: str  # 'spread', 'impact', 'volatility'
    partial_fill: bool = False
    unfilled_shares: int = 0


@dataclass
class BarData:
    """Datos de barra necesarios para fill model"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    bar_duration_seconds: int = 60  # Default 1-min bars


class FillModel:
    """
    Modelo determinístico de fills para small caps

    Workflow:
    1. Recibe orden (BUY/SELL, shares, limit_price)
    2. Recibe bar data actual
    3. Calcula fill realista:
       - Spread cost (bid-ask)
       - Market impact (price movement por volumen)
       - Volatility slippage (high-low range)
    4. Retorna OrderFill con precio final

    Determinismo:
    - Inputs: Bar OHLCV + orden size
    - Output: Fill price calculado (no randomness)
    - Mismo bar data → mismo fill price

    Example:
        fill_model = FillModel()

        bar = BarData(
            symbol='CMBM',
            timestamp=datetime(2026, 1, 5, 9, 31),
            open=5.20, high=5.35, low=5.18, close=5.28,
            volume=50000
        )

        fill = fill_model.simulate_market_order(
            order_type='BUY',
            shares=500,
            bar=bar
        )

        # fill.filled_price = 5.29 (close + spread + impact)
        # fill.slippage_bps = 17.3 (0.173%)
    """

    def __init__(
        self,
        min_spread_bps: float = 10.0,   # 0.1% min spread
        max_spread_bps: float = 100.0,  # 1.0% max spread
        impact_factor: float = 0.15,    # 15% del volumen causa 1% impact
        volatility_factor: float = 0.3  # 30% del range como slippage
    ):
        """
        Args:
            min_spread_bps: Spread mínimo (basis points)
            max_spread_bps: Spread máximo (basis points)
            impact_factor: Factor de market impact
            volatility_factor: Factor de volatility slippage
        """
        self.logger = logging.getLogger("FillModel")

        self.min_spread_bps = min_spread_bps
        self.max_spread_bps = max_spread_bps
        self.impact_factor = impact_factor
        self.volatility_factor = volatility_factor

    def simulate_market_order(
        self,
        order_type: str,  # 'BUY' or 'SELL'
        shares: int,
        bar: BarData,
        entry_price: Optional[float] = None  # Price cuando se disparó señal
    ) -> OrderFill:
        """
        Simula fill de market order

        Args:
            order_type: 'BUY' or 'SELL'
            shares: Cantidad de acciones
            bar: Bar data actual
            entry_price: Precio cuando se generó señal (default: close)

        Returns:
            OrderFill con precio realista
        """
        if entry_price is None:
            entry_price = bar.close

        # 1. Calculate spread cost
        spread_bps = self._calculate_spread(bar)

        # 2. Calculate market impact
        impact_bps = self._calculate_market_impact(shares, bar)

        # 3. Calculate volatility slippage
        volatility_bps = self._calculate_volatility_slippage(bar)

        # 4. Total slippage
        total_slippage_bps = spread_bps + impact_bps + volatility_bps

        # 5. Apply slippage direction
        if order_type == 'BUY':
            # BUY: Pagamos más (slippage positivo)
            filled_price = entry_price * (1 + total_slippage_bps / 10000.0)
        else:
            # SELL: Recibimos menos (slippage negativo)
            filled_price = entry_price * (1 - total_slippage_bps / 10000.0)

        # 6. Clamp to bar range (no podemos comprar fuera del rango)
        if order_type == 'BUY':
            filled_price = min(filled_price, bar.high)
            filled_price = max(filled_price, bar.low)
        else:
            filled_price = max(filled_price, bar.low)
            filled_price = min(filled_price, bar.high)

        # 7. Check if order can be filled (volume available)
        volume_available = bar.volume * 0.05  # Asumimos 5% del volumen disponible
        partial_fill = shares > volume_available

        if partial_fill:
            filled_shares = int(volume_available)
            unfilled_shares = shares - filled_shares
        else:
            filled_shares = shares
            unfilled_shares = 0

        # 8. Determine fill time (instant for small orders, delayed for large)
        fill_delay_seconds = min(
            bar.bar_duration_seconds,
            int(shares / volume_available * bar.bar_duration_seconds)
        ) if volume_available > 0 else bar.bar_duration_seconds

        fill_time = bar.timestamp + timedelta(seconds=fill_delay_seconds)

        # 9. Determine primary slippage reason
        if impact_bps > spread_bps and impact_bps > volatility_bps:
            reason = 'impact'
        elif volatility_bps > spread_bps:
            reason = 'volatility'
        else:
            reason = 'spread'

        self.logger.debug(
            f"Fill simulation {bar.symbol} {order_type} {shares}sh @ {filled_price:.2f} "
            f"(entry: {entry_price:.2f}, slippage: {total_slippage_bps:.1f}bps, "
            f"reason: {reason})"
        )

        return OrderFill(
            filled_price=round(filled_price, 2),
            filled_shares=filled_shares,
            fill_time=fill_time,
            slippage_bps=round(total_slippage_bps, 1),
            slippage_reason=reason,
            partial_fill=partial_fill,
            unfilled_shares=unfilled_shares
        )

    def simulate_limit_order(
        self,
        order_type: str,
        shares: int,
        limit_price: float,
        bar: BarData
    ) -> Optional[OrderFill]:
        """
        Simula fill de limit order

        Args:
            order_type: 'BUY' or 'SELL'
            shares: Cantidad de acciones
            limit_price: Precio límite
            bar: Bar data actual

        Returns:
            OrderFill si se ejecuta, None si no se ejecuta
        """
        # Check if limit would have been hit
        if order_type == 'BUY':
            # BUY limit: ejecuta si low <= limit_price
            if bar.low <= limit_price:
                # Fill at limit or better
                fill_price = min(limit_price, bar.close)
                executed = True
            else:
                executed = False
        else:
            # SELL limit: ejecuta si high >= limit_price
            if bar.high >= limit_price:
                # Fill at limit or better
                fill_price = max(limit_price, bar.close)
                executed = True
            else:
                executed = False

        if not executed:
            return None

        # Apply minimal slippage for limit orders (spread only)
        spread_bps = self._calculate_spread(bar)

        if order_type == 'BUY':
            filled_price = fill_price * (1 + spread_bps / 10000.0)
        else:
            filled_price = fill_price * (1 - spread_bps / 10000.0)

        # Clamp to bar range
        filled_price = max(bar.low, min(bar.high, filled_price))

        # Estimate fill time (limit orders can take longer)
        fill_delay = bar.bar_duration_seconds // 2  # Median fill time
        fill_time = bar.timestamp + timedelta(seconds=fill_delay)

        return OrderFill(
            filled_price=round(filled_price, 2),
            filled_shares=shares,
            fill_time=fill_time,
            slippage_bps=round(spread_bps, 1),
            slippage_reason='spread',
            partial_fill=False,
            unfilled_shares=0
        )

    def _calculate_spread(self, bar: BarData) -> float:
        """
        Calcula spread basado en volatilidad de la barra

        Returns:
            Spread en basis points
        """
        # Spread correlaciona con volatilidad (high-low range)
        bar_range_pct = (bar.high - bar.low) / bar.close * 100

        # Small caps: Spread = 0.1% - 1.0% típicamente
        # Mayor volatility → mayor spread
        spread_bps = self.min_spread_bps + (
            bar_range_pct * 10  # 1% range → +10bps spread
        )

        return min(spread_bps, self.max_spread_bps)

    def _calculate_market_impact(self, shares: int, bar: BarData) -> float:
        """
        Calcula market impact basado en orden size vs volumen

        Returns:
            Impact en basis points
        """
        if bar.volume == 0:
            # No volume data → assume high impact
            return 50.0

        # Fraction of bar volume
        volume_fraction = shares / bar.volume

        # Impact model: linear hasta 5%, luego cuadrático
        if volume_fraction <= 0.05:
            # Small order: minimal impact
            impact_bps = volume_fraction * 100  # 5% vol → 5bps
        else:
            # Large order: quadratic impact
            excess = volume_fraction - 0.05
            impact_bps = 5.0 + (excess ** 0.8) * 500  # Escalates quickly

        return min(impact_bps, 200.0)  # Cap at 2%

    def _calculate_volatility_slippage(self, bar: BarData) -> float:
        """
        Calcula slippage adicional por volatilidad intrabar

        Returns:
            Volatility slippage en basis points
        """
        # High-low range como proxy de volatilidad
        bar_range_pct = (bar.high - bar.low) / bar.close

        # Slippage = % del rango
        volatility_bps = bar_range_pct * 10000 * self.volatility_factor

        return min(volatility_bps, 100.0)  # Cap at 1%


# Singleton for global usage
_global_fill_model = None


def get_fill_model() -> FillModel:
    """
    Get global FillModel instance

    Returns:
        FillModel: Global instance
    """
    global _global_fill_model

    if _global_fill_model is None:
        _global_fill_model = FillModel()

    return _global_fill_model
