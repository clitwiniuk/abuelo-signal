# Regression Testing Guide for Trading Strategies

## Overview
This guide documents the systematic approach to regression testing and robustness validation for trading strategies. Use this methodology whenever you modify worker logic, thresholds, or filters to ensure changes improve performance without overfitting.

## Core Principles
1. **Out-of-Sample Testing:** Always test on data not used during development.
2. **Multiple Datasets:** Use at least 2-3 different ticker sets to verify robustness.
3. **Targeted Testing:** When a strategy yields 0 trades, verify it's due to lack of valid setups, not broken logic.
4. **Conservative is Good:** A strategy that stays flat in low-volatility conditions is disciplined, not broken.

## Tools & Scripts

### Simulation Scripts (`scripts/simulations/`)
- `simulate_momentum_adaptive.py` - Momentum Breakout strategy
- `simulate_vcp_pnl.py` - VCP Smallcap strategy
- `simulate_orb_pnl.py` - ORB strategy
- `simulate_daily_plays_pnl.py` - Daily Plays strategy
- `run_robustness_test.py` - Unified runner for all strategies

### Diagnostic Scripts (`scripts/diagnostics/`)
- `diagnose_momentum.py` - Detailed rejection analysis for Momentum
- `diagnose_vcp.py` - Detailed rejection analysis for VCP

## Step-by-Step Regression Testing Procedure

### Phase 1: Initial Dataset Selection
**Goal:** Select tickers that were NOT used during strategy development.

```bash
# Query for high-volume tickers
sqlite3 trading_data.db "
SELECT DISTINCT symbol, COUNT(*) as count 
FROM trades 
GROUP BY symbol 
ORDER BY count DESC 
LIMIT 30;
"
```

**Selection Criteria:**
- Exclude tickers used in original development/testing
- Prefer tickers with 10+ trades (sufficient data)
- Mix of price ranges ($1-$25)

### Phase 2: Run Baseline Simulation
**Goal:** Test strategies on the out-of-sample dataset.

```bash
# Edit run_robustness_test.py to set your ticker list
# Then run:
python3 scripts/simulations/run_robustness_test.py
```

**Expected Output:**
- Total trades per strategy
- Win rate
- Total P&L
- Average P&L per trade

### Phase 3: Interpret Results

#### Scenario A: Strategy Yields 0 Trades
**Don't panic!** This could be correct behavior.

**Action:** Run diagnostics to understand why:
```bash
# For Momentum:
python3 scripts/diagnostics/diagnose_momentum.py

# For VCP:
python3 scripts/diagnostics/diagnose_vcp.py
```

**Interpretation:**
- If diagnostics show "No momentum spikes detected" → **Correct behavior** (dataset lacks volatility)
- If diagnostics show rejections at specific filters → **Potential issue** (filter too strict)

#### Scenario B: Strategy Yields Trades with Poor Performance
**Red Flag!** This suggests overfitting or broken logic.

**Action:**
1. Review the trade log to identify patterns
2. Check if losses are concentrated in specific conditions
3. Re-examine recent threshold changes
4. Consider reverting changes if performance degraded

#### Scenario C: Strategy Yields Profitable Trades
**Good sign!** But verify it's not luck.

**Action:**
1. Check win rate (should be >50% for mean reversion, >40% for breakout)
2. Verify average P&L is positive
3. Ensure trade count is reasonable (not overtrading)

### Phase 4: Targeted Dataset Testing
**Goal:** If a strategy yielded 0 trades, verify it works when opportunities exist.

```bash
# Query for high-volatility tickers (ORB/Momentum candidates)
sqlite3 trading_data.db "
SELECT 
    t.symbol,
    (MAX(b.high_price) - MIN(b.low_price)) / MIN(b.low_price) * 100 as range_pct
FROM trade_intraday_bars b
JOIN trades t ON b.trade_id = t.trade_id
WHERE strftime('%H:%M', b.bar_timestamp) BETWEEN '14:30' AND '15:30'
  AND b.bar_timestamp >= datetime('now', '-7 days')
GROUP BY t.symbol
HAVING range_pct > 10
ORDER BY range_pct DESC
LIMIT 10;
"
```

**Selection Criteria:**
- **For ORB:** Tickers with >10% range in first hour (9:30-10:30)
- **For Momentum:** Tickers with >5% intraday moves
- **For VCP:** Tickers with multi-day consolidation patterns

Update `run_robustness_test.py` with this targeted set and re-run.

### Phase 5: Document Results
Create a report documenting:
1. **Dataset Used:** Ticker list and selection criteria
2. **Results:** Trades, win rate, P&L for each strategy
3. **Interpretation:** Why results make sense (or don't)
4. **Conclusion:** Is the strategy robust or overfitted?

## Common Pitfalls

### 1. Testing on Development Data
**Problem:** Using the same tickers you optimized on.
**Solution:** Always use fresh, unseen tickers.

### 2. Misinterpreting 0 Trades
**Problem:** Assuming 0 trades = broken strategy.
**Solution:** Run diagnostics to verify it's due to lack of valid setups.

### 3. Cherry-Picking Datasets
**Problem:** Only testing on datasets that show good results.
**Solution:** Test on at least 3 different sets (random, high-activity, targeted).

### 4. Ignoring Simulation Artifacts
**Problem:** Daily Plays uses synthetic catalyst data in simulations.
**Solution:** Understand that some strategies (like Daily Plays) require real market data to be fully validated.

## Example Workflow

```bash
# 1. Select out-of-sample tickers
sqlite3 trading_data.db "SELECT DISTINCT symbol FROM trades LIMIT 10;"

# 2. Update run_robustness_test.py with ticker list
# Edit: out_of_sample_symbols = ['TICKER1', 'TICKER2', ...]

# 3. Run simulation
python3 scripts/simulations/run_robustness_test.py

# 4. If 0 trades, run diagnostics
python3 scripts/diagnostics/diagnose_momentum.py
python3 scripts/diagnostics/diagnose_vcp.py

# 5. If still concerned, create targeted dataset
# Query for high-volatility tickers, update script, re-run

# 6. Document results in robustness_test_report.md
```

## Success Criteria
A strategy passes robustness testing if:
1. **Profitability:** Positive P&L on out-of-sample data
2. **Discipline:** Stays flat when no valid setups exist
3. **Consistency:** Similar performance across multiple datasets
4. **No Overfitting:** Doesn't show massive degradation on new data

## Maintenance
- Re-run regression tests after any major threshold changes
- Test quarterly with fresh data to ensure strategies remain valid
- Update this guide as new testing methodologies are developed
