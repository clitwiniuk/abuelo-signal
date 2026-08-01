"""
Market Replay Engine — candle-by-candle day replay for practice trading.

Generates realistic smallcap intraday scenarios with specific patterns
(morning panic, VWAP bounce, ORB, halt, etc.) and manages replay state
including positions, P&L, and performance scoring.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
import random
import json


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ReplayTrade:
    """A single trade executed during a replay session."""
    trade_id: int
    side: str  # "BUY" or "SELL"
    entry_bar: int
    entry_price: float
    size: int
    stop_loss: float
    take_profit: float
    setup: str = ""
    exit_bar: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # "manual", "stop_loss", "take_profit", "eod"
    pnl: float = 0.0
    r_multiple: float = 0.0


@dataclass
class ReplayState:
    """Full state of a running replay session."""
    scenario_id: str = ""
    scenario_name: str = ""
    current_bar: int = 0
    total_bars: int = 0
    is_playing: bool = False
    is_finished: bool = False
    speed: float = 1.0  # multiplier
    capital: float = 25000.0
    starting_capital: float = 25000.0
    open_position: Optional[ReplayTrade] = None
    closed_trades: List[ReplayTrade] = field(default_factory=list)
    next_trade_id: int = 1
    daily_pnl: float = 0.0
    max_equity: float = 25000.0
    max_drawdown: float = 0.0
    paused_for_education: bool = False
    education_message: str = ""
    education_type: str = ""  # "briefing", "tip", "warning", "post_trade"


# ---------------------------------------------------------------------------
# Scenario definitions — curated smallcap day patterns
# ---------------------------------------------------------------------------

SCENARIOS: List[Dict] = [
    {
        "id": "morning_panic_easy",
        "name": "Morning Panic Dip — Easy",
        "difficulty": "easy",
        "setup": "Morning Panic Dip",
        "description": "Stock gaps up 40% on earnings. Panic sellers dump it 25% from HOD in the first 15 minutes, "
                       "then it finds support and bounces back 15%. Classic morning panic dip buy.",
        "briefing": (
            "**Pre-Market Analysis:**\n"
            "- Stock gapped up 40% on strong earnings beat\n"
            "- Float: 8M shares (low float = high volatility)\n"
            "- Pre-market volume: 5x average\n\n"
            "**What to watch:**\n"
            "- Wait for the panic selling to exhaust (volume dry-up)\n"
            "- Look for a long lower wick candle near a whole-dollar level\n"
            "- Entry ONLY after a green candle confirms the bounce\n"
            "- Stop below the panic low\n\n"
            "**Common mistake:** Buying too early during the panic. Wait for confirmation."
        ),
        "pattern": "panic_dip",
        "base_price": 8.50,
        "gap_pct": 0.40,
        "volatility": 0.025,
        "total_minutes": 120,
        "level_required": 1,
    },
    {
        "id": "morning_panic_hard",
        "name": "Morning Panic Dip — Hard (Trap)",
        "difficulty": "hard",
        "setup": "Morning Panic Dip",
        "description": "Looks like a panic dip but the bounce fails. Tests your ability to cut losses quickly.",
        "briefing": (
            "**Pre-Market Analysis:**\n"
            "- Stock gapped up 30% on speculative news\n"
            "- Float: 25M shares (medium float)\n"
            "- Short interest: 18%\n\n"
            "**What to watch:**\n"
            "- The bounce attempt may fail — be ready to cut fast\n"
            "- If the bounce doesn't reclaim VWAP within 5 bars, get out\n"
            "- Volume on the bounce should INCREASE, not decrease\n\n"
            "**Key lesson:** Not every panic dip is a buy. Failed bounces are normal."
        ),
        "pattern": "failed_panic",
        "base_price": 5.20,
        "gap_pct": 0.30,
        "volatility": 0.030,
        "total_minutes": 120,
        "level_required": 2,
    },
    {
        "id": "vwap_bounce_easy",
        "name": "VWAP Bounce — Easy",
        "difficulty": "easy",
        "setup": "VWAP Bounce",
        "description": "Stock trends up from open, pulls back to VWAP, and bounces cleanly. Textbook setup.",
        "briefing": (
            "**Pre-Market Analysis:**\n"
            "- Stock up 15% on sector momentum (not news-specific)\n"
            "- RVol: 3x (decent, not extreme)\n"
            "- SPY is green — favorable market conditions\n\n"
            "**What to watch:**\n"
            "- After the initial push, wait for a pullback TO the VWAP line\n"
            "- Entry when price touches VWAP and prints a green candle\n"
            "- Stop just below VWAP (tight risk)\n"
            "- Target: prior high of day (HOD)\n\n"
            "**Pro tip:** The best VWAP bounces happen between 10:00-11:00 AM."
        ),
        "pattern": "vwap_bounce",
        "base_price": 12.00,
        "gap_pct": 0.15,
        "volatility": 0.015,
        "total_minutes": 150,
        "level_required": 1,
    },
    {
        "id": "vwap_bounce_hard",
        "name": "VWAP Bounce — Hard (Chop)",
        "difficulty": "hard",
        "setup": "VWAP Bounce",
        "description": "Multiple VWAP tests with false bounces before the real move. Tests patience and discipline.",
        "briefing": (
            "**Pre-Market Analysis:**\n"
            "- Stock up 10% but with mixed signals\n"
            "- SPY is flat — no directional tailwind\n\n"
            "**What to watch:**\n"
            "- First VWAP touch may fail — wait for the SECOND touch\n"
            "- Look for volume confirmation (volume spike on bounce candle)\n"
            "- If it breaks VWAP with volume, FLIP your bias short\n\n"
            "**Key lesson:** Choppy days require smaller size and wider stops."
        ),
        "pattern": "vwap_chop",
        "base_price": 15.00,
        "gap_pct": 0.10,
        "volatility": 0.020,
        "total_minutes": 150,
        "level_required": 2,
    },
    {
        "id": "orb_breakout",
        "name": "Opening Range Breakout",
        "difficulty": "medium",
        "setup": "Opening Range Breakout",
        "description": "Stock consolidates in first 15 minutes then breaks out with volume. Clean ORB setup.",
        "briefing": (
            "**Pre-Market Analysis:**\n"
            "- Stock up 8% on analyst upgrade\n"
            "- Above all moving averages on daily chart\n"
            "- Volume concentrated at market open\n\n"
            "**What to watch:**\n"
            "- Mark the high and low of the first 15 minutes\n"
            "- BUY when price breaks above the opening range HIGH with volume\n"
            "- Stop below the opening range LOW (or midpoint for tighter risk)\n"
            "- Target: 1.5x-2x the opening range height\n\n"
            "**Pro tip:** ORBs work best when the opening range is TIGHT (low volatility compression)."
        ),
        "pattern": "orb_breakout",
        "base_price": 22.00,
        "gap_pct": 0.08,
        "volatility": 0.012,
        "total_minutes": 180,
        "level_required": 2,
    },
    {
        "id": "orb_fake_breakout",
        "name": "ORB — Fake Breakout (Trap)",
        "difficulty": "hard",
        "setup": "Opening Range Breakout",
        "description": "The ORB breaks out but immediately reverses. Classic bull trap that teaches risk management.",
        "briefing": (
            "**Pre-Market Analysis:**\n"
            "- Stock up 5% on weak catalyst\n"
            "- Approaching daily resistance at $25\n"
            "- Short interest: 22%\n\n"
            "**What to watch:**\n"
            "- The breakout may be a TRAP — shorts squeezing briefly then dumping\n"
            "- If the breakout candle has a long upper wick → WARNING\n"
            "- If volume DECREASES after breakout → likely fake\n"
            "- Be ready to cut immediately if it re-enters the range\n\n"
            "**Key lesson:** Volume confirms breakouts. No volume = no conviction."
        ),
        "pattern": "orb_fake",
        "base_price": 24.00,
        "gap_pct": 0.05,
        "volatility": 0.018,
        "total_minutes": 180,
        "level_required": 3,
    },
    {
        "id": "halt_resume",
        "name": "Trading Halt & Resume",
        "difficulty": "hard",
        "setup": "Morning Panic Dip",
        "description": "Stock halts on circuit breaker (LULD) during a massive spike, then resumes with extreme volatility.",
        "briefing": (
            "**Pre-Market Analysis:**\n"
            "- Stock up 80% on FDA approval\n"
            "- Float: 3M shares (ULTRA low float)\n"
            "- This WILL halt — be prepared\n\n"
            "**What to watch:**\n"
            "- NEVER chase into a halt — you can't exit\n"
            "- After resume, wait 2-3 bars to see direction\n"
            "- The first move after a halt is often a FAKE — wait for the second move\n"
            "- Size DOWN on halt plays (50% normal size max)\n\n"
            "**Key lesson:** Halts are NOT your friend. They trap traders. Trade the resume, not the halt."
        ),
        "pattern": "halt_resume",
        "base_price": 3.50,
        "gap_pct": 0.80,
        "volatility": 0.045,
        "total_minutes": 90,
        "level_required": 3,
    },
    {
        "id": "first_red_day",
        "name": "First Red Day (Short)",
        "difficulty": "hard",
        "setup": "First Red Day",
        "description": "After 4 green days of a runner, the stock prints its first red day. Short opportunity.",
        "briefing": (
            "**Pre-Market Analysis:**\n"
            "- Stock ran 200% in 4 days on hype\n"
            "- Today gapping DOWN 8% — first red day\n"
            "- Previous support at $18 (day 2 close)\n\n"
            "**What to watch:**\n"
            "- Short when price fails to reclaim VWAP\n"
            "- Cover at prior support levels (not all at once — scale out)\n"
            "- Stop above HOD (if it reclaims HOD, the short thesis is dead)\n"
            "- WARNING: First red days can bounce hard intraday\n\n"
            "**Key lesson:** Short selling requires PATIENCE. Let the setup come to you."
        ),
        "pattern": "first_red_day",
        "base_price": 25.00,
        "gap_pct": -0.08,
        "volatility": 0.022,
        "total_minutes": 210,
        "level_required": 3,
    },
    {
        "id": "grinder_up",
        "name": "Steady Grinder Up — Easy Day",
        "difficulty": "easy",
        "setup": "VWAP Bounce",
        "description": "Stock steadily grinds higher all day on strong volume. Low stress, high probability.",
        "briefing": (
            "**Pre-Market Analysis:**\n"
            "- Stock up 12% on inclusion in index\n"
            "- Institutional buying expected all day\n"
            "- Very high volume pre-market\n\n"
            "**What to watch:**\n"
            "- This is a HOLD day — don't overtrade\n"
            "- Buy on any dip to VWAP or rising moving average\n"
            "- Let winners run — trail your stop behind each higher low\n"
            "- Target: ride until momentum slows (volume decreases)\n\n"
            "**Pro tip:** On strong trend days, every dip is a buying opportunity."
        ),
        "pattern": "grinder_up",
        "base_price": 18.00,
        "gap_pct": 0.12,
        "volatility": 0.010,
        "total_minutes": 240,
        "level_required": 1,
    },
    {
        "id": "afternoon_breakout",
        "name": "Afternoon Breakout",
        "difficulty": "medium",
        "setup": "Opening Range Breakout",
        "description": "Stock consolidates all morning then breaks out at 2 PM on volume. Tests patience.",
        "briefing": (
            "**Pre-Market Analysis:**\n"
            "- Stock flat to slightly up in AM session\n"
            "- Building a tight range near HOD\n"
            "- Volume picking up gradually\n\n"
            "**What to watch:**\n"
            "- WAIT for the breakout — don't buy the consolidation\n"
            "- Afternoon breakouts that work tend to run into close\n"
            "- Volume must expand on the break\n"
            "- If it doesn't break by 3 PM, pass on it\n\n"
            "**Key lesson:** Patience is an edge. The best traders wait for their pitch."
        ),
        "pattern": "afternoon_breakout",
        "base_price": 14.00,
        "gap_pct": 0.06,
        "volatility": 0.008,
        "total_minutes": 270,
        "level_required": 2,
    },
]


# ---------------------------------------------------------------------------
# Scenario data generation
# ---------------------------------------------------------------------------

def _generate_panic_dip(cfg: Dict) -> pd.DataFrame:
    """Morning panic dip: gap up → sharp sell-off → bounce."""
    n = cfg["total_minutes"]
    base = cfg["base_price"] * (1 + cfg["gap_pct"])
    vol = cfg["volatility"]

    prices = [base]
    volumes = []

    for i in range(n):
        pct = i / n
        if pct < 0.12:
            # Sharp sell-off (first ~15 min)
            drift = -0.008 + np.random.normal(0, vol * 1.5)
            v_mult = 4.0
        elif pct < 0.18:
            # Capitulation / bottom
            drift = -0.002 + np.random.normal(0, vol * 0.8)
            v_mult = 5.0
        elif pct < 0.35:
            # Bounce
            drift = 0.005 + np.random.normal(0, vol)
            v_mult = 3.0
        elif pct < 0.55:
            # Consolidation
            drift = 0.001 + np.random.normal(0, vol * 0.6)
            v_mult = 1.5
        else:
            # Slow grind
            drift = 0.0005 + np.random.normal(0, vol * 0.5)
            v_mult = 1.0

        new_price = prices[-1] * (1 + drift)
        prices.append(max(new_price, base * 0.4))
        volumes.append(int(np.random.uniform(200000, 800000) * v_mult))

    volumes.append(volumes[-1])
    return _prices_to_ohlcv(prices, volumes, n)


def _generate_failed_panic(cfg: Dict) -> pd.DataFrame:
    """Panic dip that bounces briefly then fails to new lows."""
    n = cfg["total_minutes"]
    base = cfg["base_price"] * (1 + cfg["gap_pct"])
    vol = cfg["volatility"]

    prices = [base]
    volumes = []

    for i in range(n):
        pct = i / n
        if pct < 0.12:
            drift = -0.007 + np.random.normal(0, vol * 1.3)
            v_mult = 4.0
        elif pct < 0.22:
            # Weak bounce (trap)
            drift = 0.003 + np.random.normal(0, vol)
            v_mult = 2.0
        elif pct < 0.35:
            # Rollover
            drift = -0.004 + np.random.normal(0, vol)
            v_mult = 2.5
        elif pct < 0.60:
            # New lows
            drift = -0.003 + np.random.normal(0, vol * 0.8)
            v_mult = 2.0
        else:
            # Choppy bottom
            drift = -0.0005 + np.random.normal(0, vol * 0.6)
            v_mult = 1.0

        new_price = prices[-1] * (1 + drift)
        prices.append(max(new_price, base * 0.2))
        volumes.append(int(np.random.uniform(200000, 600000) * v_mult))

    volumes.append(volumes[-1])
    return _prices_to_ohlcv(prices, volumes, n)


def _generate_vwap_bounce(cfg: Dict) -> pd.DataFrame:
    """Trend up → pullback to VWAP → bounce to new HOD."""
    n = cfg["total_minutes"]
    base = cfg["base_price"] * (1 + cfg["gap_pct"])
    vol = cfg["volatility"]

    prices = [base]
    volumes = []

    for i in range(n):
        pct = i / n
        if pct < 0.15:
            # Initial push up
            drift = 0.004 + np.random.normal(0, vol)
            v_mult = 3.0
        elif pct < 0.30:
            # Pullback to VWAP
            drift = -0.003 + np.random.normal(0, vol * 0.7)
            v_mult = 1.5
        elif pct < 0.35:
            # VWAP touch + bounce
            drift = 0.001 + np.random.normal(0, vol * 0.5)
            v_mult = 3.0
        elif pct < 0.55:
            # Push to new HOD
            drift = 0.003 + np.random.normal(0, vol * 0.8)
            v_mult = 2.5
        elif pct < 0.70:
            # Second pullback
            drift = -0.001 + np.random.normal(0, vol * 0.6)
            v_mult = 1.2
        else:
            # Afternoon drift
            drift = 0.001 + np.random.normal(0, vol * 0.5)
            v_mult = 1.0

        new_price = prices[-1] * (1 + drift)
        prices.append(max(new_price, base * 0.7))
        volumes.append(int(np.random.uniform(150000, 500000) * v_mult))

    volumes.append(volumes[-1])
    return _prices_to_ohlcv(prices, volumes, n)


def _generate_vwap_chop(cfg: Dict) -> pd.DataFrame:
    """Multiple VWAP tests with false bounces."""
    n = cfg["total_minutes"]
    base = cfg["base_price"] * (1 + cfg["gap_pct"])
    vol = cfg["volatility"]

    prices = [base]
    volumes = []

    for i in range(n):
        pct = i / n
        # Oscillate around VWAP with decreasing amplitude
        cycle = np.sin(pct * 12 * np.pi) * vol * (1 - pct * 0.3)
        drift = cycle + np.random.normal(0, vol * 0.6)

        if pct > 0.65:
            # Finally breaks one direction
            drift += 0.003

        v_mult = 1.5 + abs(cycle) * 30

        new_price = prices[-1] * (1 + drift)
        prices.append(max(new_price, base * 0.7))
        volumes.append(int(np.random.uniform(100000, 400000) * v_mult))

    volumes.append(volumes[-1])
    return _prices_to_ohlcv(prices, volumes, n)


def _generate_orb_breakout(cfg: Dict) -> pd.DataFrame:
    """Tight opening range then clean breakout."""
    n = cfg["total_minutes"]
    base = cfg["base_price"] * (1 + cfg["gap_pct"])
    vol = cfg["volatility"]

    prices = [base]
    volumes = []

    for i in range(n):
        pct = i / n
        if pct < 0.08:
            # Opening range (tight consolidation)
            drift = np.random.normal(0, vol * 0.4)
            v_mult = 2.5
        elif pct < 0.12:
            # Breakout bar
            drift = 0.008 + np.random.normal(0, vol * 0.5)
            v_mult = 5.0
        elif pct < 0.30:
            # Follow-through
            drift = 0.003 + np.random.normal(0, vol * 0.7)
            v_mult = 3.0
        elif pct < 0.50:
            # Pullback / consolidation
            drift = -0.0005 + np.random.normal(0, vol * 0.5)
            v_mult = 1.5
        elif pct < 0.65:
            # Second push
            drift = 0.002 + np.random.normal(0, vol * 0.6)
            v_mult = 2.0
        else:
            # Afternoon drift
            drift = 0.0005 + np.random.normal(0, vol * 0.4)
            v_mult = 1.0

        new_price = prices[-1] * (1 + drift)
        prices.append(max(new_price, base * 0.8))
        volumes.append(int(np.random.uniform(100000, 400000) * v_mult))

    volumes.append(volumes[-1])
    return _prices_to_ohlcv(prices, volumes, n)


def _generate_orb_fake(cfg: Dict) -> pd.DataFrame:
    """Fake breakout that reverses."""
    n = cfg["total_minutes"]
    base = cfg["base_price"] * (1 + cfg["gap_pct"])
    vol = cfg["volatility"]

    prices = [base]
    volumes = []

    for i in range(n):
        pct = i / n
        if pct < 0.08:
            drift = np.random.normal(0, vol * 0.4)
            v_mult = 2.0
        elif pct < 0.12:
            # Fake breakout
            drift = 0.006 + np.random.normal(0, vol * 0.5)
            v_mult = 4.0
        elif pct < 0.20:
            # Reversal
            drift = -0.006 + np.random.normal(0, vol * 0.8)
            v_mult = 3.5
        elif pct < 0.40:
            # Breakdown below range
            drift = -0.003 + np.random.normal(0, vol * 0.6)
            v_mult = 2.5
        elif pct < 0.60:
            # Consolidation at lows
            drift = -0.0005 + np.random.normal(0, vol * 0.4)
            v_mult = 1.2
        else:
            # Slow recovery or more selling
            drift = np.random.normal(0, vol * 0.5)
            v_mult = 1.0

        new_price = prices[-1] * (1 + drift)
        prices.append(max(new_price, base * 0.7))
        volumes.append(int(np.random.uniform(80000, 350000) * v_mult))

    volumes.append(volumes[-1])
    return _prices_to_ohlcv(prices, volumes, n)


def _generate_halt_resume(cfg: Dict) -> pd.DataFrame:
    """Parabolic move → halt → volatile resume."""
    n = cfg["total_minutes"]
    base = cfg["base_price"] * (1 + cfg["gap_pct"])
    vol = cfg["volatility"]

    prices = [base]
    volumes = []

    halt_bar = int(n * 0.15)
    resume_bar = halt_bar + 5  # 5 bars of halt

    for i in range(n):
        pct = i / n
        if i < halt_bar:
            # Parabolic move up
            drift = 0.012 + np.random.normal(0, vol * 1.2)
            v_mult = 6.0
        elif i < resume_bar:
            # HALT — price frozen
            drift = 0
            v_mult = 0
        elif i < resume_bar + 3:
            # Resume — violent move (random direction)
            drift = np.random.choice([-0.015, 0.015]) + np.random.normal(0, vol * 2)
            v_mult = 8.0
        elif pct < 0.50:
            # Post-halt volatility
            drift = -0.003 + np.random.normal(0, vol * 1.5)
            v_mult = 4.0
        elif pct < 0.70:
            # Settling
            drift = -0.001 + np.random.normal(0, vol * 0.8)
            v_mult = 2.0
        else:
            drift = np.random.normal(0, vol * 0.6)
            v_mult = 1.0

        new_price = prices[-1] * (1 + drift)
        prices.append(max(new_price, base * 0.3))
        volumes.append(int(np.random.uniform(300000, 1200000) * max(v_mult, 0.1)))

    volumes.append(volumes[-1])
    return _prices_to_ohlcv(prices, volumes, n)


def _generate_first_red_day(cfg: Dict) -> pd.DataFrame:
    """Gap down on first red day after a multi-day run."""
    n = cfg["total_minutes"]
    base = cfg["base_price"] * (1 + cfg["gap_pct"])  # gaps DOWN
    vol = cfg["volatility"]

    prices = [base]
    volumes = []

    for i in range(n):
        pct = i / n
        if pct < 0.10:
            # Morning bounce attempt
            drift = 0.003 + np.random.normal(0, vol)
            v_mult = 3.0
        elif pct < 0.20:
            # Fails at VWAP
            drift = -0.004 + np.random.normal(0, vol * 0.8)
            v_mult = 2.5
        elif pct < 0.45:
            # Trending down
            drift = -0.002 + np.random.normal(0, vol * 0.7)
            v_mult = 2.0
        elif pct < 0.55:
            # Dead cat bounce
            drift = 0.002 + np.random.normal(0, vol * 0.6)
            v_mult = 1.5
        elif pct < 0.75:
            # Resuming downtrend
            drift = -0.0015 + np.random.normal(0, vol * 0.6)
            v_mult = 1.8
        else:
            # EOD selling
            drift = -0.001 + np.random.normal(0, vol * 0.5)
            v_mult = 1.2

        new_price = prices[-1] * (1 + drift)
        prices.append(max(new_price, base * 0.5))
        volumes.append(int(np.random.uniform(150000, 500000) * v_mult))

    volumes.append(volumes[-1])
    return _prices_to_ohlcv(prices, volumes, n)


def _generate_grinder_up(cfg: Dict) -> pd.DataFrame:
    """Steady uptrend all day — easy trend following."""
    n = cfg["total_minutes"]
    base = cfg["base_price"] * (1 + cfg["gap_pct"])
    vol = cfg["volatility"]

    prices = [base]
    volumes = []

    for i in range(n):
        pct = i / n
        # Steady uptrend with small pullbacks
        drift = 0.0015 + np.random.normal(0, vol * 0.6)
        # Occasional small dips
        if random.random() < 0.08:
            drift -= 0.003
        v_mult = 2.0 - pct * 0.8  # volume decreases over day

        new_price = prices[-1] * (1 + drift)
        prices.append(max(new_price, base * 0.85))
        volumes.append(int(np.random.uniform(100000, 400000) * max(v_mult, 0.5)))

    volumes.append(volumes[-1])
    return _prices_to_ohlcv(prices, volumes, n)


def _generate_afternoon_breakout(cfg: Dict) -> pd.DataFrame:
    """Morning consolidation → afternoon breakout."""
    n = cfg["total_minutes"]
    base = cfg["base_price"] * (1 + cfg["gap_pct"])
    vol = cfg["volatility"]

    prices = [base]
    volumes = []
    breakout_bar = int(n * 0.60)

    for i in range(n):
        pct = i / n
        if i < breakout_bar:
            # Tight consolidation
            drift = np.random.normal(0, vol * 0.3)
            v_mult = 0.8
        elif i < breakout_bar + 5:
            # Breakout
            drift = 0.006 + np.random.normal(0, vol * 0.5)
            v_mult = 5.0
        elif pct < 0.80:
            # Follow-through
            drift = 0.003 + np.random.normal(0, vol * 0.6)
            v_mult = 3.0
        else:
            # Into close
            drift = 0.001 + np.random.normal(0, vol * 0.4)
            v_mult = 2.0

        new_price = prices[-1] * (1 + drift)
        prices.append(max(new_price, base * 0.85))
        volumes.append(int(np.random.uniform(80000, 300000) * max(v_mult, 0.3)))

    volumes.append(volumes[-1])
    return _prices_to_ohlcv(prices, volumes, n)


PATTERN_GENERATORS = {
    "panic_dip": _generate_panic_dip,
    "failed_panic": _generate_failed_panic,
    "vwap_bounce": _generate_vwap_bounce,
    "vwap_chop": _generate_vwap_chop,
    "orb_breakout": _generate_orb_breakout,
    "orb_fake": _generate_orb_fake,
    "halt_resume": _generate_halt_resume,
    "first_red_day": _generate_first_red_day,
    "grinder_up": _generate_grinder_up,
    "afternoon_breakout": _generate_afternoon_breakout,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prices_to_ohlcv(prices: List[float], volumes: List[int], n: int) -> pd.DataFrame:
    """Convert a minute-by-minute price series into 1-min OHLCV bars."""
    # Group prices into bars (1 price = 1 bar for simplicity)
    bars = []
    start_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)

    for i in range(min(n, len(prices) - 1)):
        o = prices[i]
        c = prices[i + 1]
        noise = abs(c - o) * 0.3 + abs(np.random.normal(0, abs(c - o) * 0.2 + 0.01))
        h = max(o, c) + abs(noise)
        l = min(o, c) - abs(noise)

        bars.append({
            "time": start_time + timedelta(minutes=i),
            "open": round(o, 4),
            "high": round(h, 4),
            "low": round(l, 4),
            "close": round(c, 4),
            "volume": volumes[i] if i < len(volumes) else 100000,
        })

    df = pd.DataFrame(bars)
    df.set_index("time", inplace=True)

    # Calculate VWAP
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()

    # EMA 9
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()

    return df


def generate_scenario_data(scenario_id: str, seed: Optional[int] = None) -> Tuple[Dict, pd.DataFrame]:
    """Generate OHLCV data for a given scenario.

    Returns (scenario_config, dataframe).
    """
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if scenario is None:
        raise ValueError(f"Unknown scenario: {scenario_id}")

    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)
    else:
        # Use current time for randomness
        np.random.seed(int(datetime.now().timestamp()) % 2**31)
        random.seed(int(datetime.now().timestamp()) % 2**31)

    generator = PATTERN_GENERATORS.get(scenario["pattern"])
    if generator is None:
        raise ValueError(f"No generator for pattern: {scenario['pattern']}")

    df = generator(scenario)
    return scenario, df


def get_scenarios_for_level(level: int) -> List[Dict]:
    """Return scenarios available for the user's current level."""
    return [s for s in SCENARIOS if s["level_required"] <= level]


# ---------------------------------------------------------------------------
# Replay logic
# ---------------------------------------------------------------------------

def create_replay_state(scenario_id: str, capital: float = 25000.0) -> ReplayState:
    """Initialize a fresh replay state."""
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    name = scenario["name"] if scenario else scenario_id
    return ReplayState(
        scenario_id=scenario_id,
        scenario_name=name,
        capital=capital,
        starting_capital=capital,
        max_equity=capital,
    )


def execute_buy(state: ReplayState, df: pd.DataFrame, size: int,
                stop_loss: float, take_profit: float, setup: str = "") -> str:
    """Open a long position at the current bar's close price."""
    if state.open_position is not None:
        return "Already have an open position. Close it first."

    bar = df.iloc[state.current_bar]
    price = float(bar["close"])

    # Simulate slippage (0.1-0.3% for smallcaps)
    slippage = price * np.random.uniform(0.001, 0.003)
    fill_price = round(price + slippage, 4)

    cost = fill_price * size
    if cost > state.capital:
        return f"Insufficient capital. Need ${cost:,.2f}, have ${state.capital:,.2f}"

    trade = ReplayTrade(
        trade_id=state.next_trade_id,
        side="BUY",
        entry_bar=state.current_bar,
        entry_price=fill_price,
        size=size,
        stop_loss=stop_loss,
        take_profit=take_profit,
        setup=setup,
    )
    state.open_position = trade
    state.next_trade_id += 1
    return f"BOUGHT {size} shares @ ${fill_price:.2f} (slippage: ${slippage:.4f})"


def execute_sell(state: ReplayState, df: pd.DataFrame, reason: str = "manual") -> str:
    """Close the open position at the current bar's close."""
    if state.open_position is None:
        return "No open position to close."

    bar = df.iloc[state.current_bar]
    price = float(bar["close"])

    # Slippage on exit
    slippage = price * np.random.uniform(0.001, 0.003)
    fill_price = round(price - slippage, 4)

    trade = state.open_position
    trade.exit_bar = state.current_bar
    trade.exit_price = fill_price
    trade.exit_reason = reason

    if trade.side == "BUY":
        trade.pnl = round((fill_price - trade.entry_price) * trade.size, 2)
    else:
        trade.pnl = round((trade.entry_price - fill_price) * trade.size, 2)

    risk = abs(trade.entry_price - trade.stop_loss)
    if risk > 0:
        trade.r_multiple = round(trade.pnl / (risk * trade.size), 2)

    state.capital += trade.pnl
    state.daily_pnl += trade.pnl

    # Track drawdown
    if state.capital > state.max_equity:
        state.max_equity = state.capital
    dd = (state.max_equity - state.capital) / state.max_equity * 100
    if dd > state.max_drawdown:
        state.max_drawdown = dd

    state.closed_trades.append(trade)
    state.open_position = None

    emoji = "+" if trade.pnl >= 0 else ""
    return (f"SOLD {trade.size} shares @ ${fill_price:.2f} | "
            f"P&L: {emoji}${trade.pnl:.2f} ({trade.r_multiple:.1f}R) | "
            f"Reason: {reason}")


def advance_bar(state: ReplayState, df: pd.DataFrame) -> Optional[str]:
    """Advance the replay by one bar. Returns a message if a stop/target was hit."""
    if state.current_bar >= len(df) - 1:
        state.is_finished = True
        state.is_playing = False
        # Force-close any open position at EOD
        if state.open_position:
            return execute_sell(state, df, reason="eod")
        return None

    state.current_bar += 1
    bar = df.iloc[state.current_bar]

    # Check stop loss / take profit
    if state.open_position:
        trade = state.open_position
        if trade.side == "BUY":
            if float(bar["low"]) <= trade.stop_loss:
                # Hit stop loss
                trade.exit_bar = state.current_bar
                trade.exit_price = trade.stop_loss
                trade.exit_reason = "stop_loss"
                trade.pnl = round((trade.stop_loss - trade.entry_price) * trade.size, 2)
                risk = abs(trade.entry_price - trade.stop_loss)
                trade.r_multiple = -1.0 if risk > 0 else 0
                state.capital += trade.pnl
                state.daily_pnl += trade.pnl
                state.closed_trades.append(trade)
                state.open_position = None
                return f"STOP LOSS HIT @ ${trade.stop_loss:.2f} | P&L: ${trade.pnl:.2f}"

            if float(bar["high"]) >= trade.take_profit:
                trade.exit_bar = state.current_bar
                trade.exit_price = trade.take_profit
                trade.exit_reason = "take_profit"
                trade.pnl = round((trade.take_profit - trade.entry_price) * trade.size, 2)
                risk = abs(trade.entry_price - trade.stop_loss)
                trade.r_multiple = round(trade.pnl / (risk * trade.size), 2) if risk > 0 else 0
                state.capital += trade.pnl
                state.daily_pnl += trade.pnl
                if state.capital > state.max_equity:
                    state.max_equity = state.capital
                state.closed_trades.append(trade)
                state.open_position = None
                return f"TAKE PROFIT HIT @ ${trade.take_profit:.2f} | P&L: +${trade.pnl:.2f}"

    return None


# ---------------------------------------------------------------------------
# Education tips (contextual)
# ---------------------------------------------------------------------------

CONTEXTUAL_TIPS = {
    "bought_above_vwap": (
        "You bought ABOVE VWAP. In smallcap trading, the best long entries "
        "are AT or BELOW VWAP. Buying above means you're chasing — "
        "your risk/reward is worse because your stop needs to be wider."
    ),
    "bought_below_vwap": (
        "Good entry near VWAP. When price is near VWAP, you can use a tight "
        "stop just below the recent low, giving you excellent risk/reward."
    ),
    "stop_too_wide": (
        "Your stop loss is more than 5% away from entry. In smallcap trading, "
        "wide stops = big losses. Consider reducing size or tightening your stop. "
        "A good rule: if you can't find a logical stop within 3%, the setup isn't clean."
    ),
    "good_rr": (
        "Nice risk/reward setup. With a 3:1+ R:R, you only need to be right "
        "33% of the time to break even. That's the mathematical edge of good setups."
    ),
    "revenge_trade": (
        "WARNING: You just took a loss and immediately entered a new trade. "
        "This is classic revenge trading. Take a 5-minute pause after every loss "
        "to reset your emotions before the next trade."
    ),
    "overtrading": (
        "You've taken 3+ trades in this session. Quality over quantity — "
        "the best traders take 1-3 high-quality trades per day, not 10 mediocre ones."
    ),
    "no_trade_is_ok": (
        "Remember: not trading IS a valid position. If you don't see your setup, "
        "sit on your hands. The market will be there tomorrow."
    ),
}


def get_entry_feedback(state: ReplayState, df: pd.DataFrame) -> str:
    """Generate educational feedback after a trade entry."""
    if state.open_position is None:
        return ""

    trade = state.open_position
    bar = df.iloc[trade.entry_bar]
    vwap = float(bar.get("vwap", trade.entry_price))

    tips = []

    # Check if bought above VWAP
    if trade.side == "BUY" and trade.entry_price > vwap * 1.01:
        tips.append(CONTEXTUAL_TIPS["bought_above_vwap"])
    elif trade.side == "BUY" and trade.entry_price <= vwap * 1.01:
        tips.append(CONTEXTUAL_TIPS["bought_below_vwap"])

    # Check stop width
    stop_pct = abs(trade.entry_price - trade.stop_loss) / trade.entry_price
    if stop_pct > 0.05:
        tips.append(CONTEXTUAL_TIPS["stop_too_wide"])

    # Check R:R
    rr = abs(trade.take_profit - trade.entry_price) / max(abs(trade.entry_price - trade.stop_loss), 0.01)
    if rr >= 3:
        tips.append(CONTEXTUAL_TIPS["good_rr"])

    # Check for revenge trading
    if len(state.closed_trades) > 0:
        last = state.closed_trades[-1]
        if last.pnl < 0 and (trade.entry_bar - last.exit_bar) < 3:
            tips.append(CONTEXTUAL_TIPS["revenge_trade"])

    # Check overtrading
    if len(state.closed_trades) >= 3:
        tips.append(CONTEXTUAL_TIPS["overtrading"])

    return "\n\n".join(tips) if tips else ""


def get_exit_feedback(trade: ReplayTrade) -> str:
    """Generate educational feedback after a trade exit."""
    messages = []

    if trade.pnl > 0:
        messages.append(f"Winner: +${trade.pnl:.2f} ({trade.r_multiple:.1f}R)")
        if trade.r_multiple >= 2:
            messages.append("Excellent R-multiple. This is the kind of trade that builds accounts.")
        if trade.exit_reason == "take_profit":
            messages.append("Target hit cleanly. Good planning and patience.")
    else:
        messages.append(f"Loser: ${trade.pnl:.2f} ({trade.r_multiple:.1f}R)")
        if trade.exit_reason == "stop_loss":
            messages.append(
                "Stop loss honored. This is GOOD discipline — protecting capital "
                "is more important than being right. Every pro takes losses."
            )
        elif trade.exit_reason == "manual":
            messages.append(
                "Manual exit before stop. Good if you saw the setup deteriorate. "
                "Cutting losses early (before the stop) is a sign of experience."
            )

    return "\n".join(messages)


# ---------------------------------------------------------------------------
# Scorecard
# ---------------------------------------------------------------------------

def generate_scorecard(state: ReplayState) -> Dict:
    """Generate a performance scorecard for the completed replay."""
    trades = state.closed_trades
    if not trades:
        return {
            "total_trades": 0,
            "message": "No trades taken. Sometimes the best trade is no trade.",
        }

    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl < 0]

    total_pnl = sum(t.pnl for t in trades)
    win_rate = len(winners) / len(trades) * 100 if trades else 0
    avg_winner = sum(t.pnl for t in winners) / len(winners) if winners else 0
    avg_loser = sum(t.pnl for t in losers) / len(losers) if losers else 0
    avg_r = sum(t.r_multiple for t in trades) / len(trades) if trades else 0

    gross_profit = sum(t.pnl for t in winners)
    gross_loss = abs(sum(t.pnl for t in losers))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Grade the session
    grade = "F"
    grade_msg = ""
    if len(trades) == 0:
        grade = "N/A"
        grade_msg = "No trades taken."
    elif total_pnl > 0 and win_rate >= 50 and avg_r >= 1.5:
        grade = "A"
        grade_msg = "Excellent session. Profitable, disciplined, and good R-multiples."
    elif total_pnl > 0 and avg_r >= 1.0:
        grade = "B"
        grade_msg = "Good session. Profitable with decent risk management."
    elif total_pnl > 0:
        grade = "C"
        grade_msg = "Profitable but room for improvement on entry quality."
    elif total_pnl > -state.starting_capital * 0.02:
        grade = "C-"
        grade_msg = "Small loss. You managed risk well even though the trades didn't work."
    elif all(t.exit_reason == "stop_loss" for t in losers):
        grade = "D+"
        grade_msg = "Losses but stops were honored. Discipline is there, work on entry selection."
    else:
        grade = "D"
        grade_msg = "Significant losses. Review your entries and risk management."

    return {
        "total_trades": len(trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "avg_winner": round(avg_winner, 2),
        "avg_loser": round(avg_loser, 2),
        "avg_r_multiple": round(avg_r, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "INF",
        "max_drawdown": round(state.max_drawdown, 2),
        "grade": grade,
        "grade_message": grade_msg,
        "capital_final": round(state.capital, 2),
        "capital_return_pct": round((state.capital - state.starting_capital) / state.starting_capital * 100, 2),
    }
