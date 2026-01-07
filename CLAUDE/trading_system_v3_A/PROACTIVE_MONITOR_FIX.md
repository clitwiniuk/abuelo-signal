# Proactive Monitor Fix - Bars Fetching for VWAP Analysis

## Problem Statement

### The LVRO Case (January 5, 2026)

LVRO moved +77% (0.70 → 1.24) on Day 5 after being detected as an ULTIMATE squeeze on Day 0/1:
- **Day 0/1 (Jan 2)**: +144% move, 7544x relative volume, quality 90 (ULTIMATE)
- **Day 5 (Jan 5)**: +77% continuation move with "red to green" pattern
- **Result**: Trade was MISSED despite being in the proactive watchlist

### Root Cause Analysis

The proactive monitor (`_monitor_watchlist()`) was monitoring LVRO correctly every minute via IBKR, but **could not evaluate entry conditions** due to missing bars data.

**Flow Breakdown:**

1. ✅ LVRO correctly added to `proactive_candidates` table on Jan 2
2. ✅ Proactive monitor fetching price from IBKR every minute
3. ✅ Creating opportunity dict and calling `should_enter()`
4. ❌ **BUG**: Opportunity dict missing `bars_history`
5. ❌ `should_enter()` calls `get_bars_from_opportunity()` → returns empty list
6. ❌ Cannot calculate VWAP → entry rejected at line 276
7. ❌ Trade never entered despite meeting all other criteria

**Code Evidence:**

```python
# OLD CODE (lines 132-142)
opportunity = {
    'symbol': symbol,
    'current_price': snapshot.get('price', 0),
    'volume_ratio': snapshot.get('volume_ratio', 1.0),
    'timestamp': datetime.now(),
    'source': 'PROACTIVE_MONITOR',
    # ❌ MISSING: 'bars_history' for VWAP calculation
}

# Result in should_enter() (line 274):
bars = self.get_bars_from_opportunity(opportunity)
if not bars:
    return False  # ❌ Always rejected!
```

## Solution Implemented

### Changes Made

**File:** `strategies/workers/short_squeeze_worker_logic.py`

#### 1. New Method: `_fetch_intraday_bars()` (lines 248-291)

```python
async def _fetch_intraday_bars(self, symbol: str) -> list:
    """
    Fetch intraday bars for VWAP and volume analysis.

    This is the CRITICAL FIX for proactive monitoring.
    Without bars, should_enter() cannot calculate VWAP and will reject the opportunity.
    """
    try:
        # Fetch 1-minute bars for today (up to 390 bars = full trading day)
        bars_data = await self.execution_engine.broker.get_bars(
            symbol=symbol,
            timeframe='1 min',
            count=390
        )

        if not bars_data or len(bars_data) == 0:
            self.logger.debug(f"📊 {symbol}: No intraday bars available from IBKR")
            return []

        # Convert MarketData objects to dict format expected by get_bars_from_opportunity
        bars_history = []
        for bar in bars_data:
            bars_history.append({
                'timestamp': bar.timestamp if hasattr(bar, 'timestamp') else datetime.now(),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume if hasattr(bar, 'volume') else 0
            })

        self.logger.debug(f"📊 {symbol}: Fetched {len(bars_history)} intraday bars for analysis")
        return bars_history

    except Exception as e:
        self.logger.warning(f"📊 {symbol}: Error fetching intraday bars: {e}")
        return []
```

#### 2. Updated `_monitor_watchlist()` (lines 132-180)

```python
# CRITICAL FIX: Fetch intraday bars for VWAP analysis
bars_history = await self._fetch_intraday_bars(symbol)

if not bars_history:
    self.logger.warning(f"⚠️ {symbol}: No bars available for VWAP analysis, skipping evaluation")
    continue

# Get candidate pattern info for logging
pattern_type = candidate.get('pattern_type', 'UNKNOWN')
days_since = candidate.get('days_since_detection', 0)
current_price = snapshot.get('price', 0)

self.logger.info(
    f"✅ {symbol}: Proactive evaluation ready "
    f"(Day {days_since}, Pattern: {pattern_type}, Price: ${current_price:.2f}, Bars: {len(bars_history)})"
)

# Construct opportunity with bars_history
opportunity = {
    'symbol': symbol,
    'current_price': current_price,
    'volume_ratio': snapshot.get('volume_ratio', 1.0),
    'timestamp': datetime.now(),
    'source': 'PROACTIVE_MONITOR',
    'bars_history': bars_history,  # ✅ FIX: Add bars for VWAP/volume analysis
}
```

#### 3. Enhanced Logging

Added comprehensive logging to track:
- Bars fetch success/failure
- Number of bars fetched
- Pattern type and days since detection
- Entry evaluation results

## Expected Behavior After Fix

### Scenario: LVRO-like continuation on Day 5

**Before Fix:**
```
🧐 Monitoring 6 proactive candidates: ['AZI', 'ZNTL', 'LVRO', 'PRZO', 'ATLN', 'SOPA']
[No further logs - silently rejected due to missing bars]
```

**After Fix:**
```
🧐 Monitoring 6 proactive candidates: ['AZI', 'ZNTL', 'LVRO', 'PRZO', 'ATLN', 'SOPA']
📊 LVRO: Fetched 234 intraday bars for analysis
✅ LVRO: Proactive evaluation ready (Day 5, Pattern: GREEN_DAY_1, Price: $1.15, Bars: 234)
👀 LVRO: Found in Proactive Watchlist! (Day 5, Pattern: GREEN_DAY_1)
📊 LVRO Levels: Resistance=$1.49, Day1High=$1.49, Structure=INSIDE_DAY
💰 LVRO: VWAP = $1.08, Price = $1.15 (+6.48% above VWAP)
🚀 LVRO: PROACTIVE TRIGGER: triggered entry logic from internal monitor!
```

## Benefits

1. **Captures Continuation Patterns**: Can now trade Day 2-7 setups that weren't detected by scanner
2. **VWAP Analysis Works**: Full intraday data enables proper VWAP reclaim detection
3. **Volume Validation**: Can calculate real relative volume from bars
4. **Better Logging**: Clear visibility into why candidates are accepted/rejected
5. **No Scanner Dependency**: Works even if scanner doesn't detect the symbol that day

## Testing

### Active Proactive Candidates (as of Jan 7, 2026)

| Symbol | Pattern     | Status    | Days Since | Detection Date |
|--------|-------------|-----------|------------|----------------|
| AZI    | GREEN_DAY_1 | WATCHING  | 1          | 2026-01-06     |
| ZNTL   | GREEN_DAY_1 | WATCHING  | 1          | 2026-01-06     |
| LVRO   | GREEN_DAY_1 | WATCHING  | 5          | 2026-01-02     |
| PRZO   | GREEN_DAY_1 | WATCHING  | 5          | 2026-01-02     |
| ATLN   | GREEN_DAY_1 | WATCHING  | 5          | 2026-01-02     |
| SOPA   | GREEN_DAY_1 | TRIGGERED | 12         | 2025-12-26     |

### Test Script

Run `test_proactive_bars_fetch.py` to validate bars fetching for current candidates:

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A
python test_proactive_bars_fetch.py
```

## Performance Considerations

### API Call Impact

- **Before**: 1 API call per candidate (price only)
- **After**: 2 API calls per candidate (price + bars)
- **Frequency**: Every 60 seconds per candidate
- **Max candidates**: 50 (configurable)
- **Total**: ~100 API calls/minute worst case (well within IBKR limits)

### Optimization

Bars are fetched on-demand per candidate, not batch-cached. This ensures:
- Fresh data for entry decisions
- No stale VWAP calculations
- Minimal memory footprint

If performance becomes an issue with many candidates, consider:
- Batch bars fetching
- Caching bars with 1-minute TTL
- Using BatchPriceManager for VWAP streaming

## Related Issues

### Why Scanner Didn't Detect LVRO on Jan 5

The scanner only detects stocks meeting premarket/gap/volume criteria at market open. LVRO on Day 5:
- No significant premarket gap
- Opened red (below previous close)
- Only showed strength intraday with "red to green" pattern

**This is exactly why proactive monitoring is critical** - it catches continuation plays that don't gap up.

## Future Enhancements

Consider adding:

1. **Red-to-Green Pattern Detection**
   - Track when price crosses above previous close intraday
   - Specific entry trigger for this pattern
   - See `should_enter()` lines 314-351 for pattern framework

2. **Intraday Structure Analysis**
   - Detect higher lows on 15-min timeframe
   - Flag "quiet accumulation" patterns
   - Alert on volume spikes above daily average

3. **Smart Bar Caching**
   - Cache bars with 1-min expiry
   - Reduce API calls by ~50%
   - Shared cache across all workers

## Commit Message

```
fix: Add intraday bars fetching to proactive monitor for VWAP analysis

CRITICAL FIX: Proactive monitor couldn't evaluate entries because opportunity
dicts lacked bars_history, causing VWAP calculation to fail.

Root cause: LVRO missed on Jan 5 despite +77% move because:
- Proactive monitor created opportunity dicts without bars_history
- should_enter() requires bars for VWAP calculation
- Without VWAP, all proactive entries were silently rejected

Solution:
- Added _fetch_intraday_bars() method to fetch 1-min bars from IBKR
- Updated _monitor_watchlist() to include bars_history in opportunity
- Enhanced logging to track bars fetch success/failure

Benefits:
- Can now capture Day 2-7 continuation patterns
- Full VWAP/volume analysis for proactive candidates
- Works even when scanner doesn't detect the symbol that day

Files modified:
- strategies/workers/short_squeeze_worker_logic.py

Related: LVRO analysis, proactive scanner improvement
```

## Date

**Implemented**: January 7, 2026
**Author**: Claude Code
**Issue**: LVRO missed opportunity on Jan 5, 2026
