# Trading Patterns Summary
Complete reference for Day Trading and Swing Trading patterns

---

## 📊 DAY TRADING - Intraday Patterns

**Price Range:** $1.00 - $15.00 (Smallcap focus)

**Time Horizon:** Minutes to hours (max 8 hours hold)

**Position Size:** $100-$200 per position

**Capital Allocation:** 60% ($1,200 from $2,000 total)

---

### 1️⃣ GAP-GO Worker

**Pattern:** Premarket High (PMH) Breakout

**Entry Criteria:**
- Gap ≥ 8%
- Price: $1-$15
- Volume ≥ 0.7x average
- **PMH Breakout:** Price breaks premarket high (4:00-9:30 AM) with volume
- Price ABOVE VWAP (strength confirmation)
- Entry window: 9:30-9:45 AM

**Exit Strategy:**
- Stop loss: 3%
- Take profit: 15%
- Quick target: 6% (partial exit)
- Trailing stop: Activate at 3%, trail 2%
- Time limit: 6 hours
- EOD exit: 15:56 ET

**Example:**
```
AAPL opens with 10% gap (from $100 to $110)
PMH (4:00-9:30 AM): $112
9:35 AM: Price breaks $112 with 2x volume → ENTER
Target: $126.50 (+15%)
Stop: $106.70 (-3%)
```

---

### 2️⃣ MACDV Worker

**Pattern:** MACD Bullish Divergence (Technical Reversal)

**Entry Criteria:**
- Gap < 5% (normal movement, NO extreme gaps)
- Price: $1-$15
- Volume ≥ 0.7x average
- **MACD Bullish Divergence:** Price makes lower low, MACD makes higher low
- RSI < 40 preferred (oversold)
- Price ABOVE VWAP
- Trading hours: 12:00 PM - 3:45 PM ET (post-lunch optimal)
- Min confirmations: 2 scans (2 minutes)

**Exit Strategy:**
- Stop loss: 4%
- Take profit: 10%
- Trailing stop: Activate at 8%, trail 4%
- Time limit: 4 hours
- EOD exit: 15:56 ET

**Example:**
```
TSLA at 12:30 PM
Price: $205 (down from $210)
MACD: Rising (divergence)
RSI: 35 (oversold)
Price > VWAP → ENTER
Target: $225.50 (+10%)
Stop: $196.80 (-4%)
```

---

### 3️⃣ BULL FLAG Worker

**Pattern:** Intraday Bull Flag (Continuation Pattern)

**Entry Criteria:**
- Gap: 3-8% (moderate)
- Price: $1-$15
- Volume ≥ 0.7x average
- **Flagpole:** Sharp move 30-60% in 5-30 minutes
- **Flag:** Consolidation with 5-20% pullback in 5-20 minutes
- **Breakout:** Price breaks flag high with 1.5x volume
- Price ABOVE VWAP
- Trading hours: 9:30 AM - 3:45 PM ET
- Min confirmations: 2 scans

**Exit Strategy:**
- Stop loss: 5%
- Take profit: 15%
- Trailing stop: Activate at 10%, trail 4%
- Time limit: 6 hours
- EOD exit: 15:56 ET

**Example:**
```
NVDA
9:45 AM: Moves from $500 to $530 in 10 min (flagpole +6%)
9:55 AM: Consolidates $525-$528 for 8 min (flag)
10:03 AM: Breaks $530 with volume → ENTER
Target: $609.50 (+15%)
Stop: $503.50 (-5%)
```

---

### 4️⃣ DAILY PLAYS Worker

**Pattern:** Catalyst-Driven + First 30min Breakout + Reversal

**Entry Criteria - Mode 1 (Catalyst):**
- Strong catalyst: FDA, M&A, EARNINGS, BREAKTHROUGH, CONTRACT
- Catalyst strength ≥ 6/10
- Price: $1-$15
- Volume ≥ 0.7x average
- Quality score ≥ 50
- Price ABOVE VWAP
- Min confirmations: 1 scan (30 seconds - fast entry)

**Entry Criteria - Mode 2 (First 30min Breakout):**
- Breaks 9:30-10:00 AM high
- Volume 1.5x average on breakout
- Price above EMA9
- Price ABOVE VWAP

**Entry Criteria - Mode 3 (Reversal - Oversold Bounce):**
- **4+ reversal signals (of 6):**
  1. RSI < 35 (oversold)
  2. Near 30-day support (< 3% away)
  3. 3+ consecutive down days
  4. MACD histogram increasing
  5. Volume declining (exhaustion)
  6. Price stabilizing (low volatility)
- **Relaxed requirements when reversal detected:**
  - Catalyst optional
  - Volume ≥ 1.5x (vs 2.0x)
  - Quality score ≥ 40 (vs 50)
  - VWAP requirement relaxed

**Exit Strategy:**
- Stop loss: 5%
- Take profit: 20% (higher targets for catalysts)
- Quick target: 7%
- Trailing stop: Activate at 3%, trail 2%
- Time limit: 8 hours
- EOD exit: 15:56 ET

**Example - Catalyst:**
```
SAVA - FDA approval news
Catalyst: FDA (strength 8/10)
Gap: 15%
Volume: 5x average
9:32 AM: Consolidates above VWAP → ENTER
Target: +20%
Stop: -5%
```

**Example - First 30min:**
```
AMD
9:30-10:00: High $105
10:15 AM: Breaks $105.50 with 2x volume → ENTER
Target: $126 (+20%)
Stop: $100.25 (-5%)
```

**Example - Reversal:**
```
PLTR
Down 3 consecutive days
RSI: 32 (oversold)
Price: $18.50, 30-day support: $18.00 (2.7% away)
MACD: Histogram increasing
Volume: Declining (exhaustion)
→ ENTER (oversold bounce expected)
Target: $22.20 (+20%)
Stop: $17.58 (-5%)
```

---

## 🏛️ SWING TRADING - Consolidation Patterns

**Price Range:** $1.00 - $15.00 (Smallcap focus - SAME as day trading)

**Time Horizon:** Days to weeks (max 30 days hold)

**Position Size:** $300-$400 per position

**Capital Allocation:** 40% ($800 from $2,000 total)

**Max Positions:** 2 simultaneous

---

### Pattern Types (Daily Timeframe)

All patterns require:
- Consolidation: 20-120 days (4 weeks to 6 months)
- Price range: $1-$15
- Max consolidation range: 25%
- Min breakout score: 70/100
- Current price within 5% of resistance

---

### 1️⃣ ASCENDING TRIANGLE ⬆️📐

**Characteristics:**
- Higher lows (ascending support)
- Flat resistance (horizontal ceiling)
- Bullish continuation pattern
- Best pattern for breakouts

**Score:** 25/25 points (HIGHEST)

**Visual:**
```
      Resistance ─────────────────
    /     /       /         /
   /     /       /         /  ← Higher lows
  /     /       /         /
 /     /       /         /
Support
```

**Requirements:**
- Min resistance touches: 3
- Min support touches: 2
- Ascending slope > 0.0001
- Volume compression: 0.5-0.7 ideal

---

### 2️⃣ BULL FLAG 🚩

**Characteristics:**
- Both highs and lows declining slightly
- Follows strong prior move
- Tight consolidation range
- Continuation pattern

**Score:** 22/25 points

**Visual:**
```
      \  \  \  \    ← Slight decline
       \  \  \  \
        ──────────  ← Tight range
```

**Requirements:**
- Both slopes negative
- Prior strong move required
- Volume declining in flag

---

### 3️⃣ FLAT BASE ━━━

**Characteristics:**
- Horizontal highs
- Horizontal lows
- Tight range consolidation
- Clean base building

**Score:** 20/25 points

**Visual:**
```
─────────────────── ← Flat resistance

─────────────────── ← Flat support
```

**Requirements:**
- Both slopes near zero
- Low volatility
- Volume compression

---

### 4️⃣ CUP & HANDLE ☕

**Characteristics:**
- U-shaped formation (cup)
- Small consolidation (handle)
- Longer pattern duration
- Strong breakout expected

**Score:** 23/25 points

**Visual:**
```
\               / \  ← Handle
 \             /
  \___________/  ← Cup (U-shape)
```

**Requirements:**
- Cup depth reasonable
- Handle tight consolidation
- Volume pattern: high → low → high

---

### 5️⃣ DESCENDING TRIANGLE ⬇️📐

**Characteristics:**
- Lower highs
- Flat support
- Weaker pattern
- Less preferred

**Score:** 15/25 points (LOWEST - less desirable)

**Visual:**
```
\     \       \         \
 \     \       \         \  ← Lower highs
  \     \       \         \
Support ─────────────────────
```

**Requirements:**
- Min support touches: 2
- Descending high slope
- Use with caution

---

### Breakout Scoring System (0-100)

**1. Pattern Quality (25 points max):**
- Ascending Triangle: 25 pts ⭐
- Cup & Handle: 23 pts
- Bull Flag: 22 pts
- Flat Base: 20 pts
- Descending Triangle: 15 pts

**2. Volume Compression (20 points max):**
- Ideal ratio: 0.5-0.7 (late volume = 50-70% of early) → 20 pts
- Good: 0.4-0.5 or 0.7-0.8 → 15 pts
- OK: 0.3-0.4 or 0.8-0.9 → 10 pts
- Poor: Other → 5 pts

**3. Consolidation Duration (20 points max):**
- Optimal: 60-90 days → 20 pts
- Good: 30-60 days → 15 pts
- Short: 20-30 days → 10 pts
- Long: 90-120 days → 5 pts

**4. Proximity to Resistance (20 points max):**
- Very close: <1% → 20 pts
- Close: 1-2% → 15 pts
- Near: 2-3% → 10 pts
- Far: 3-5% → 5 pts

**5. Support/Resistance Touches (15 points max):**
- Excellent: 5+ touches → 15 pts
- Good: 4 touches → 12 pts
- OK: 3 touches → 9 pts
- Minimum: 2 touches → 6 pts

**Minimum Score Required:** 70/100

---

### Dual Entry Modes

**BREAKOUT Mode (gap <3%):**
- Entry: Market order at market open (9:30-9:45 AM)
- Conditions: Gap <3%, volume >1.5x, confirms strength
- Best for: Controlled gaps, high probability

**PULLBACK Mode (gap >5%):**
- Entry: Limit order on pullback to old resistance
- Conditions:
  - Price retraces to resistance level (now support)
  - MACDV shows bullish divergence
  - RSI < 40 (oversold)
  - Volume > 1.2x
- Best for: Large gaps, avoid buying tops

---

### Exit Strategy (Swing)

**Priority Order:**

1. **Stop Loss:** 10% below support
2. **Target:** 50% gain from entry
3. **Trailing Stop:**
   - Activate at 15% gain
   - Trail 8% below highest price
4. **Time Limit:** 30 days (free capital)

**Example:**
```
Entry: $100
Support: $95
Stop: $85.50 (10% below support)
Target: $150 (+50%)

If reaches $120 (+20%):
  → Trailing activates
  → High: $125
  → Trail stop: $115 (8% below high)
  → If drops to $115 → EXIT (+15% gain locked)
```

---

## 📋 Quick Comparison

| Aspect | Day Trading | Swing Trading |
|--------|-------------|---------------|
| **Price Range** | $1 - $15 | $1 - $15 |
| **Timeframe** | Minutes/Hours | Days/Weeks |
| **Data Used** | 1-min bars | Daily bars |
| **Hold Time** | Max 8 hours | Max 30 days |
| **Position Size** | $100-$200 | $300-$400 |
| **Capital** | 60% ($1,200) | 40% ($800) |
| **Max Positions** | ~6-12 | 2 |
| **Stop Loss** | 3-5% | 10% |
| **Target** | 10-20% | 50% |
| **Patterns** | PMH, MACDV, Bull Flag, Catalyst | Triangle, Cup, Flag, Base |
| **Scan Time** | Every 30 sec | Daily at 15:40 ET |

---

## 🚫 Duplicate Prevention

**UnifiedPositionManager** ensures:
- ✅ No same symbol in multiple day strategies
- ✅ No same symbol in day + swing simultaneously
- ✅ Capital limits respected (60/40 split)
- ✅ Positions freed on exit

**Example:**
```
Gap-Go enters AAPL → BLOCKS MACDV, Bull Flag, Daily Plays, AND Swing on AAPL
Gap-Go exits AAPL → All workers can now evaluate AAPL again
```

---

## 📊 Filter Summary

All trading (day + swing) applies these universal filters:

1. **Price Range:** $1.00 - $15.00 (smallcap focus)
2. **VWAP Strength:** Price must be ABOVE VWAP (day trading)
3. **Volume:** Minimum thresholds (varies by strategy)
4. **Quality Score:** Pattern/setup quality (varies by strategy)
5. **Duplicate Check:** Symbol not held elsewhere
6. **Capital Check:** Sufficient capital available

---

*Last updated: 2025-01-04*
