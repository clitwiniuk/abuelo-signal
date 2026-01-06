#!/usr/bin/env python3
"""
Worker Capabilities Configuration

Defines capabilities and preferences for each worker in the system.

Worker Contexts (Updated):
Worker              Priority    Compatible Contexts                    Horizon
DailyPlays          4           catalyst, trend                        Swing
MomentumBreakout    2           momentum, trend                        Intraday
VWAP Breakout       1           momentum, trend, catalyst              Intraday
VCP Smallcap        4           catalyst, momentum, trend              Intraday
VolumeAbsorption    3           range, momentum, trend, catalyst       Intraday
BuyTheDip           4           trend, catalyst, momentum              Intraday
BuyAndHold          4           trend, catalyst, momentum              Swing Short
SmallCaps Long      4           catalyst, momentum, trend              Swing Short
LivermoreIntraday   4           catalyst, momentum, trend              Intraday
Generic 01          5           catalyst, trend, momentum, range       Intraday
DailyPlays Midcap   3           catalyst, momentum                     Swing
Balance Day         3           range, momentum                        Intraday
Outlier Penny       5           catalyst, momentum                     Intraday
ODS Universal       4           momentum, trend, catalyst              Intraday
ODS Swing           4           momentum, trend, catalyst              Swing
Parabolic           5           momentum, trend, catalyst              Scalp
Holy Grail          4           trend, momentum, catalyst              Swing Short
Short Parabolic     5           momentum, catalyst                     Intraday (SHORT)
Gap Fade            4           momentum, range                        Intraday (SHORT)
Short Squeeze       4           catalyst, momentum, trend              Swing Short (LONG)
SmallCaps Reversal  4           momentum, catalyst                     Intraday (SHORT)
"""

from core.trade_arbiter import WorkerCapabilities, TradingHorizon
from core.context_engine import MarketContext


# Worker capabilities registry
WORKER_CAPABILITIES = {
    'daily_plays': WorkerCapabilities(
        name='daily_plays',
        priority=4,  # Highest priority (Main driver: Catalyst + Technicals)
        compatible_contexts=[
            MarketContext.CATALYST,   # Primary: News/Catalyst driven
            MarketContext.TREND       # Secondary: Daily chart trend alignment
        ],
        horizon=TradingHorizon.SWING,  # Multi-day hold for trend realization
        historical_winrate=0.60,  # 60% estimated (Target: Capture 1-3 day runner)
        avg_hold_time=48.0,  # 2 days average
        min_confidence=70.0  # Requires high confidence (Catalyst Check required)
    ),



    'momentum_breakout': WorkerCapabilities(
        name='momentum_breakout',
        priority=2,
        compatible_contexts=[
            MarketContext.MOMENTUM,
            MarketContext.TREND,
            MarketContext.CATALYST
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

    'buy_the_dip': WorkerCapabilities(
        name='buy_the_dip',
        priority=4,  # High priority (dip buying in confirmed uptrends is high probability)
        compatible_contexts=[
            MarketContext.TREND,      # Primary: requires uptrend (VWAP positive slope)
            MarketContext.CATALYST,   # Secondary: catalyst-driven uptrends (from scanner)
            MarketContext.MOMENTUM    # Tertiary: momentum continuation after dip
        ],
        horizon=TradingHorizon.INTRADAY,  # 2 hours max holding (quick dip-and-rip)
        historical_winrate=0.60,  # 60% estimated (buying dips in uptrends is reliable)
        avg_hold_time=2.0,  # 2 hours average (quick scalp on bounce)
        min_confidence=65.0  # Medium-high confidence required (VWAP + ATR-based dip)
    ),

    'buy_and_hold': WorkerCapabilities(
        name='buy_and_hold',
        priority=4,  # High priority (immediate entry on strong morning setups)
        compatible_contexts=[
            MarketContext.TREND,      # Primary: requires uptrend (price above VWAP)
            MarketContext.CATALYST,   # Secondary: catalyst-driven momentum from scanner
            MarketContext.MOMENTUM    # Tertiary: momentum continuation
        ],
        horizon=TradingHorizon.SWING_SHORT,  # Can hold for hours to capture runners
        historical_winrate=0.60,  # 60% estimated (buying strength in uptrends)
        avg_hold_time=4.0,  # 4 hours average (morning session entry, hold with trailing stop)
        min_confidence=60.0  # Medium-high confidence required (quality score + VWAP)
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

    'daily_plays_midcap': WorkerCapabilities(
        name='daily_plays_midcap',
        priority=3,  # Mid priority
        compatible_contexts=[
            MarketContext.CATALYST,
            MarketContext.MOMENTUM
        ],
        horizon=TradingHorizon.SWING,
        historical_winrate=0.62,
        avg_hold_time=72.0,  # 3 days
        min_confidence=65.0
    ),

    'balance_day': WorkerCapabilities(
        name='balance_day',
        priority=3,  # Medium priority (Niche strategy for range days)
        compatible_contexts=[
            MarketContext.RANGE,      # Primary: Range-bound / Balance days
            MarketContext.MOMENTUM    # Secondary: Reversal momentum at extremes
        ],
        horizon=TradingHorizon.INTRADAY,
        historical_winrate=0.58,  # Estimated
        avg_hold_time=1.5,  # 1.5 hours
        min_confidence=60.0
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

    'parabolic': WorkerCapabilities(
        name='parabolic',
        priority=5,  # HIGHEST priority (parabolic patterns are powerful momentum events)
        compatible_contexts=[
            MarketContext.MOMENTUM,   # Primary: parabolic = extreme momentum
            MarketContext.TREND,      # Secondary: parabolic in trending market
            MarketContext.CATALYST    # Tertiary: catalyst-driven parabolic moves
        ],
        horizon=TradingHorizon.SCALP,  # Scalp/very short intraday (1-3 hours typical)
        historical_winrate=0.68,  # 68% estimated (high due to EARLY entry + exhaustion exit)
        avg_hold_time=1.5,  # 1.5 hours average (fast in, fast out)
        min_confidence=70.0  # High confidence required (EARLY stage only)
    ),

    'holy_grail': WorkerCapabilities(
        name='holy_grail',
        priority=4,  # High priority (Linda Raschke/Connors proven strategy)
        compatible_contexts=[
            MarketContext.TREND,      # Primary: requires strong trend (ADX > 30)
            MarketContext.MOMENTUM,   # Secondary: momentum continuation after retracement
            MarketContext.CATALYST    # Tertiary: trend + catalyst combo
        ],
        horizon=TradingHorizon.SWING_SHORT,  # Typically 1-3 days for trend continuation
        historical_winrate=0.62,  # 62% estimated (classic proven strategy)
        avg_hold_time=36.0,  # 1.5 days average (swing short)
        min_confidence=70.0  # High confidence required (ADX > 30 + EMA retracement)
    ),

    'short_parabolic': WorkerCapabilities(
        name='short_parabolic',
        priority=5,  # HIGHEST priority (Reversals on exhausted parabolic moves are gold)
        compatible_contexts=[
            MarketContext.MOMENTUM,   # Primary: fading extreme momentum
            MarketContext.CATALYST    # Secondary: catalyst-driven pumps often dump
        ],
        horizon=TradingHorizon.INTRADAY,  # Strictly intraday
        historical_winrate=0.60,  # 60% estimated (reversals are precise)
        avg_hold_time=3.0,  # 3 hours average (fade the move)
        min_confidence=75.0  # Very high confidence required (LATE stage only)
    ),

    'livermore_intraday': WorkerCapabilities(
        name='livermore_intraday',
        priority=4,  # High priority (Intraday execution for Daily Plays / Catalyst candidates)
        compatible_contexts=[
            MarketContext.CATALYST,   # Primary: "The Event" - Daily Plays with News/Catalyst
            MarketContext.MOMENTUM,   # Secondary: "The Continuity" - Daily Plays with Volume/Momentum
            MarketContext.TREND       # Tertiary: Trending Daily Plays
        ],
        horizon=TradingHorizon.INTRADAY,  # Intraday state machine (Observation → Pause → Entry)
        historical_winrate=0.62,  # 62% estimated (stateful strategy with precise entry timing)
        avg_hold_time=4.0,  # 4 hours average (waits for confirmation before entry)
        min_confidence=65.0  # Medium-high confidence required (multi-state validation)
    ),

    'gap_fade': WorkerCapabilities(
        name='gap_fade',
        priority=4,  # High priority (Gap fades are reliable mean-reversion setups)
        compatible_contexts=[
            MarketContext.MOMENTUM,   # Primary: fading momentum gaps without catalyst
            MarketContext.RANGE       # Secondary: gaps that fail and return to range
        ],
        horizon=TradingHorizon.INTRADAY,  # Strictly intraday (entry 10-11am, exit by 15:45)
        historical_winrate=0.65,  # 65% estimated (62-68% expected per worker docs)
        avg_hold_time=4.0,  # 4 hours average (10am entry to 15:45 exit)
        min_confidence=70.0  # High confidence required (gap >= 5%, VWAP resistance, volume decline)
    ),

    'short_squeeze': WorkerCapabilities(
        name='short_squeeze',
        priority=4,  # High priority (Proactive candidates Day 0-7)
        compatible_contexts=[
            MarketContext.CATALYST,   # Primary: catalyst-driven candidates
            MarketContext.MOMENTUM,   # Secondary: momentum follow-through
            MarketContext.TREND       # Tertiary: trend resumption
        ],
        horizon=TradingHorizon.SWING_SHORT,  # 1-3 days typical for squeeze follow-through
        historical_winrate=0.60,  # 60% estimated
        avg_hold_time=24.0,  # 1 day average
        min_confidence=70.0  # High confidence required (watchlist verified)
    ),

    'smallcaps_short_reversal': WorkerCapabilities(
        name='smallcaps_short_reversal',
        priority=4,  # High priority (Mean reversion with strict confirmation - high win rate)
        compatible_contexts=[
            MarketContext.MOMENTUM,   # Primary: fading parabolic momentum in small caps
            MarketContext.CATALYST    # Secondary: fading catalyst-driven pumps after exhaustion
        ],
        horizon=TradingHorizon.INTRADAY,  # Strictly intraday (1-6 hours typical hold)
        historical_winrate=0.65,  # 65% estimated (60-70% expected with strict confirmations)
        avg_hold_time=3.0,  # 3 hours average (quick reversals in small caps)
        min_confidence=75.0  # Very high confidence required (4-step process with confirmations)
    ),
    'vcp_strict_long': WorkerCapabilities(
        name='vcp_strict_long',
        priority=4,
        compatible_contexts=[MarketContext.CATALYST, MarketContext.MOMENTUM, MarketContext.TREND],
        horizon=TradingHorizon.INTRADAY,
        historical_winrate=0.65,
        avg_hold_time=6.0,
        min_confidence=80.0
    ),
    'vcp_strict_short': WorkerCapabilities(
        name='vcp_strict_short',
        priority=4,
        compatible_contexts=[MarketContext.MOMENTUM, MarketContext.TREND, MarketContext.RANGE],
        horizon=TradingHorizon.INTRADAY,
        historical_winrate=0.60,
        avg_hold_time=4.0,
        min_confidence=75.0
    ),
    'catalyst_dna': WorkerCapabilities(
        name='catalyst_dna',
        priority=4,  # High priority (Market DNA philosophy - trade with real aggression)
        compatible_contexts=[
            MarketContext.CATALYST,   # Primary: Strong catalyst = Aggression entering
            MarketContext.MOMENTUM,   # Secondary: Momentum at DNA level (VWAP)
            MarketContext.TREND       # Tertiary: Trending with VWAP support
        ],
        horizon=TradingHorizon.INTRADAY,  # Intraday only (2 hours max)
        historical_winrate=0.60,  # 60% realistic for smallcaps (optimized from 72%)
        avg_hold_time=1.5,  # 1.5 hours average (tight entries at DNA level)
        min_confidence=75.0  # High confidence required (quality score >= 75, optimized from 70)
    ),

    'smallcap_vwap_runner': WorkerCapabilities(
        name='smallcap_vwap_runner',
        priority=4,  # High priority (Robust simple strategy)
        compatible_contexts=[
            MarketContext.CATALYST,   # Quality score implies catalyst
            MarketContext.MOMENTUM,   # Price > VWAP implies momentum
            MarketContext.TREND       # Green bar implies trend
        ],
        horizon=TradingHorizon.INTRADAY,
        historical_winrate=0.55,  # Conservative estimate
        avg_hold_time=2.0,  # Short hold
        min_confidence=60.0
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
