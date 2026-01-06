# Populate TradeTally Fields - Historical Backfill Tool

## Purpose

This script (`populate_tradetally_fields.py`) is a **historical data backfill tool** used to populate missing ML fields in trades that were created before the automatic field calculation was implemented.

## When to Use

⚠️ **You probably DON'T need this script** if:
- You're creating new trades (they now auto-populate all fields)
- All your trades already have `confidence`, `market_context_score`, and `trade_session` fields

✅ **Use this script only when:**
- You have OLD trades (before Oct 2025) missing ML fields
- You want to backfill historical data for analysis
- You've imported trades from another system

## What it Does

Calculates and populates these fields for **CLOSED** trades:

1. **`confidence`** (0-100): Strategy confidence based on:
   - Strategy type
   - PnL outcome
   - Trade duration

2. **`market_context_score`** (0-100): Market quality score based on:
   - Strategy type
   - Symbol characteristics
   - Market regime (if available)

3. **`trade_session`**: Trading session classification:
   - `premarket` (before 9:30 AM ET)
   - `first_hour` (9:30-10:30 AM ET)
   - `midday` (10:30 AM-3:00 PM ET)
   - `power_hour` (3:00-4:00 PM ET)
   - `afterhours` (after 4:00 PM ET)

4. **`signal_strength`** (0-100): Entry signal quality based on:
   - Volume ratio
   - Price momentum
   - Symbol strength

## How to Use

```bash
# Run from project root
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3

# Execute the script
python scripts/utils/populate_tradetally_fields.py
```

## Important Notes

### ⚠️ Only Affects Closed Trades
The script only updates trades with `status = 'CLOSED'`. Open trades are skipped.

### ⚠️ Doesn't Overwrite Existing Values
Fields that already have values will NOT be overwritten.

### ⚠️ New Trades Auto-Populate
As of October 2025, **all new trades automatically calculate these fields** at creation time in `core/trading_execution_stage.py`. You don't need to run this script for new trades.

## Technical Details

### Database Location
- Database: `trading_data.db` (SQLite)
- Table: `trades`

### Calculation Methods

**Confidence Calculation:**
- Base: 50%
- Strategy multipliers (1.2x for VWAP Reclaim, 1.1x for Gap&Go, etc.)
- PnL adjustment (+15% if positive, -10% if negative)
- Duration adjustment (+5% if >30 min, -5% if <5 min)

**Market Context Score:**
- Base: 60%
- Strategy bonuses (+15% for Gap/Breakout, +5% for VWAP, +10% for Swing)

**Trade Session:**
- Parses `entry_time` timestamp
- Converts to Eastern Time (US market hours)
- Maps to appropriate session

## Example Output

```
🔄 Iniciando población de campos TradeTally...
📊 Encontrados 245 trades para procesar
✅ Actualizado trade RR_20250826_200408_61131f14: {'confidence': 75.0, 'market_context_score': 60.0, 'trade_session': 'midday'}
✅ Actualizado trade NUKK_20250826_201240_75daf96b: {'confidence': 75.0, 'market_context_score': 60.0, 'trade_session': 'midday'}
...
🏁 Proceso completado. 245 trades actualizados
```

## Alternatives

Instead of running this script, you can also:

1. **Use the new auto-calculation** (preferred):
   - Just create new trades - they auto-populate

2. **Manual SQL update** for specific trades:
   ```sql
   UPDATE trades
   SET confidence = 70,
       market_context_score = 60,
       trade_session = 'midday'
   WHERE trade_id IN ('...', '...');
   ```

## Related Files

- **Auto-calculation code**: `core/trading_execution_stage.py` (lines 1186-1220)
  - `_calculate_trade_confidence()`
  - `_calculate_market_context_score()`
  - `_determine_trade_session()`

---

**Created:** October 2025
**Purpose:** Historical backfill only (not needed for new trades)
