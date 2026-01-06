#!/usr/bin/env python3
"""
Worker Capabilities Configuration

Defines capabilities and preferences for each worker in the system.

Worker Contexts (Updated):
Worker              Priority    Compatible Contexts                    Horizon
DailyPlays          4           catalyst, trend                        Swing
MACDV               3           trend, momentum, catalyst              Swing short / intradía
MomentumBreakout    2           momentum, trend                        Intradía
VWAP Breakout       1           momentum, trend, catalyst              Intradía
VCP Smallcap        4           catalyst, momentum, trend              Intradía
VolumeAbsorption    3           range, momentum, trend, catalyst       Intradía
SmallCaps Long      4           catalyst, momentum, trend              Swing short
"""

from core.trade_arbiter import WorkerCapabilities, TradingHorizon
from core.context_engine import MarketContext


# Worker capabilities registry
WORKER_CAPABILITIES = {
    'daily_plays': WorkerCapabilities(
        name='daily_plays',
        priority=4,  # Highest priority
        compatible_contexts=[
            MarketContext.CATALYST,
            MarketContext.TREND
        ],
        horizon=TradingHorizon.SWING,
        historical_winrate=0.60,  # 60% winrate (adjust based on backtesting)
        avg_hold_time=48.0,  # 2 days average
        min_confidence=70.0  # Requires high confidence
    ),

    'macdv': WorkerCapabilities(
        name='macdv',
        priority=3,
        compatible_contexts=[
            MarketContext.TREND,        # Strong directional moves (primary)
            MarketContext.MOMENTUM,     # Momentum shifts (divergences)
            MarketContext.CATALYST      # Can work with catalyst-driven trends
        ],
        horizon=TradingHorizon.SWING_SHORT,
        historical_winrate=0.55,  # 55% winrate
        avg_hold_time=24.0,  # 1 day average
        min_confidence=60.0
    ),

    'momentum_breakout': WorkerCapabilities(
        name='momentum_breakout',
        priority=2,
        compatible_contexts=[
            MarketContext.MOMENTUM,
            MarketContext.TREND
        ],
        horizon=TradingHorizon.INTRADAY,
        historical_winrate=0.50,  # 50% winrate
        avg_hold_time=4.0,  # 4 hours average
        min_confidence=65.0
    ),

    'vwap': WorkerCapabilities(
        name='vwap',
        priority=1,  # Lowest priority
        compatible_contexts=[
            MarketContext.MOMENTUM,     # VWAP breakout is a momentum event
            MarketContext.TREND,        # Confirms trend direction
            MarketContext.CATALYST      # Can ride catalyst momentum
        ],
        horizon=TradingHorizon.INTRADAY,
        historical_winrate=0.52,  # 52% winrate
        avg_hold_time=3.0,  # 3 hours average
        min_confidence=55.0
    ),

    'vcp_smallcap': WorkerCapabilities(
        name='vcp_smallcap',
        priority=4,  # High priority (VCP is a high-probability setup)
        compatible_contexts=[
            MarketContext.CATALYST,
            MarketContext.MOMENTUM,
            MarketContext.TREND
        ],
        horizon=TradingHorizon.INTRADAY,  # Primarily intraday, but can hold longer
        historical_winrate=0.65,  # 65% winrate (VCP is high probability)
        avg_hold_time=6.0,  # 6 hours average (smallcaps can move quickly)
        min_confidence=80.0  # High confidence required (3+ contractions detected)
    ),

    'volume_absorption': WorkerCapabilities(
        name='volume_absorption',
        priority=3,  # Medium-high priority (institutional accumulation is powerful)
        compatible_contexts=[
            MarketContext.RANGE,      # Primary: detects accumulation in range-bound price action
            MarketContext.MOMENTUM,   # Secondary: breakout after absorption (high probability)
            MarketContext.TREND,      # Tertiary: absorption can signal trend continuation
            MarketContext.CATALYST    # Quaternary: catalyst + absorption = powerful combo
        ],
        horizon=TradingHorizon.INTRADAY,  # Typically 2-6 hours for absorption to play out
        historical_winrate=0.58,  # 58% winrate (institutional signals are reliable)
        avg_hold_time=4.0,  # 4 hours average (wait for breakout after accumulation)
        min_confidence=70.0  # High confidence required (2+ absorption events detected)
    ),

    'generic_01': WorkerCapabilities(
        name='generic_01',
        priority=5,  # HIGHEST PRIORITY (41.04% edge - best validated system)
        compatible_contexts=[
            MarketContext.CATALYST,   # Primary: news/catalyst-driven moves with low volume accumulation
            MarketContext.TREND,      # Secondary: positive momentum (daily_return > 0)
            MarketContext.MOMENTUM,   # Tertiary: momentum building
            MarketContext.RANGE       # Quaternary: accumulation in range
        ],
        horizon=TradingHorizon.INTRADAY,  # 6 hours optimal holding time
        historical_winrate=0.70,  # 70% estimated winrate (from 41% edge + 2:1 R:R)
        avg_hold_time=6.0,  # 6 hours average (validated optimal holding)
        min_confidence=65.0  # Medium-high confidence required
    ),

    'smallcaps_long': WorkerCapabilities(
        name='smallcaps_long',
        priority=4,  # High priority (17.64% edge - validated rule-based system)
        compatible_contexts=[
            MarketContext.CATALYST,   # Primary: catalyst-driven smallcap moves
            MarketContext.MOMENTUM,   # Secondary: momentum in smallcaps
            MarketContext.TREND       # Tertiary: trending smallcap moves
        ],
        horizon=TradingHorizon.SWING_SHORT,  # 1-3 days (adaptive based on signal strength)
        historical_winrate=0.65,  # 65% estimated winrate (from 17.64% edge + conservative exits)
        avg_hold_time=48.0,  # 2 days average (can be 1-3 days based on signals)
        min_confidence=70.0  # High confidence required (multi-rule validation)
    ),

    'outlier_penny_extreme': WorkerCapabilities(
        name='outlier_penny_extreme',
        priority=5,  # Medium-High priority (11.69% edge - EXTREME RISK outlier hunting)
        compatible_contexts=[
            MarketContext.CATALYST,   # Primary: volatile penny stocks with catalysts
            MarketContext.MOMENTUM,   # Secondary: momentum breakouts in penny stocks
        ],
        horizon=TradingHorizon.INTRADAY,  # Same day exit (no overnight positions)
        historical_winrate=0.546,  # 54.6% winrate (validated on 163 historical events)
        avg_hold_time=4.0,  # 4 hours average (intraday only, force exit at 15:45 ET)
        min_confidence=60.0  # Medium confidence (price < $5, PM range > 3%, volume > 1.5x)
    ),

    'ods_universal': WorkerCapabilities(
        name='ods_universal',
        priority=4,  # High priority (ODS-validated pattern-driven)
        compatible_contexts=[
            MarketContext.MOMENTUM,   # Primary: ODS momentum patterns (STRONG_BULLISH_OPEN)
            MarketContext.TREND,      # Secondary: trend drive patterns (TREND_DRIVE_BULLISH)
            MarketContext.CATALYST    # Tertiary: catalyst + ODS pattern combo
        ],
        horizon=TradingHorizon.INTRADAY,  # 6 hours max holding
        historical_winrate=0.62,  # 62% estimated (ODS patterns have edge)
        avg_hold_time=4.0,  # 4 hours average (intraday ODS)
        min_confidence=60.0  # Requires ODS strength >= 60
    ),

    'ods_swing_universal': WorkerCapabilities(
        name='ods_swing_universal',
        priority=4,  # High priority (ODS-validated multiday patterns)
        compatible_contexts=[
            MarketContext.MOMENTUM,   # Primary: strong ODS momentum (strength >= 70)
            MarketContext.TREND,      # Secondary: trend continuation with ODS
            MarketContext.CATALYST    # Tertiary: catalyst + strong ODS
        ],
        horizon=TradingHorizon.SWING,  # 1-7 days multiday holding
        historical_winrate=0.65,  # 65% estimated (strong ODS patterns for swing)
        avg_hold_time=72.0,  # 3 days average (1-7 days range)
        min_confidence=70.0  # Stricter: requires ODS strength >= 70
    ),

    'orb_breakout': WorkerCapabilities(
        name='orb_breakout',
        priority=3,  # Medium-high priority (ORB is proven intraday pattern)
        compatible_contexts=[
            MarketContext.MOMENTUM,   # Primary: opening range breakout = momentum
            MarketContext.TREND,      # Secondary: breakout in trend direction
            MarketContext.CATALYST    # Tertiary: catalyst + ORB breakout
        ],
        horizon=TradingHorizon.INTRADAY,  # Intraday only (9:30-15:56 ET)
        historical_winrate=0.58,  # 58% estimated (ORB is well-validated)
        avg_hold_time=5.0,  # 5 hours average
        min_confidence=65.0  # Medium-high confidence required
    ),
}


def get_worker_capabilities(worker_name: str) -> WorkerCapabilities:
    """
    Get capabilities for a worker

    Args:
        worker_name: Name of the worker (e.g., 'daily_plays', 'macdv')

    Returns:
        WorkerCapabilities

    Raises:
        KeyError if worker not found
    """
    if worker_name not in WORKER_CAPABILITIES:
        raise KeyError(f"Unknown worker: {worker_name}. Available: {list(WORKER_CAPABILITIES.keys())}")

    return WORKER_CAPABILITIES[worker_name]


def register_all_workers(arbiter):
    """
    Register all workers with the Trade Arbiter

    Args:
        arbiter: TradeArbiter instance
    """
    for worker_name, capabilities in WORKER_CAPABILITIES.items():
        arbiter.register_worker(capabilities)
