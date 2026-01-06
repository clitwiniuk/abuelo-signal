# Entry Competition Fix - Missing 'opportunity' Parameter

## Problem
`EntryCompetition.register_entry()` was being called without the required `opportunity` parameter, causing a TypeError:

```
TypeError: EntryCompetition.register_entry() missing 1 required positional argument: 'opportunity'
```

## Root Cause
The method signature requires 5 parameters:
```python
def register_entry(
    self,
    symbol: str,
    strategy: str,
    opportunity: dict,  # ← Missing in call
    pattern_completion: float,
    bar_index: Optional[int] = None
)
```

But it was being called with only 3 parameters in `execution_engine_adapter.py`:
```python
competition_result = await self.competition.register_entry(
    symbol=symbol,
    strategy=strategy,
    pattern_completion=pattern_completion
)
```

## Solution Applied
Added the missing `opportunity` parameter to all `register_entry()` calls.

### Files Fixed

#### v3 System:
1. **CLAUDE/trading_system_v3/core/execution_engine_adapter.py:169-174**
   - Added `opportunity=opportunity_data` parameter
   
2. **CLAUDE/trading_system_v3/tests/test_entry_competition.py:28, 31, 34, 62, 65**
   - Updated all test calls to include opportunity dict

#### v3_A System:
1. **CLAUDE/trading_system_v3_A/core/execution_engine_adapter.py:169-174**
   - Added `opportunity=opportunity_data` parameter
   
2. **CLAUDE/trading_system_v3_A/tests/test_entry_competition.py:28, 31, 34, 62, 65**
   - Updated all test calls to include opportunity dict

## Changes Made

### execution_engine_adapter.py (both v3 and v3_A)
```python
# Before:
competition_result = await self.competition.register_entry(
    symbol=symbol,
    strategy=strategy,
    pattern_completion=pattern_completion
)

# After:
competition_result = await self.competition.register_entry(
    symbol=symbol,
    strategy=strategy,
    opportunity=opportunity_data,  # ← Added
    pattern_completion=pattern_completion
)
```

### tests/test_entry_competition.py (both v3 and v3_A)
```python
# Before:
return await comp.register_entry(symbol, "WorkerA", 80.0)

# After:
return await comp.register_entry(symbol, "WorkerA", {"symbol": symbol}, 80.0)
```

## Files Already Correct
The following files were already using the correct signature and didn't need changes:
- `test_entry_competition.py` (root level in both v3 and v3_A)
- All calls in these files already included the opportunity parameter

## Testing
After this fix:
- Workers can now successfully register entry attempts
- Entry competition will work properly for concurrent worker entries
- Tests should pass without TypeError

## Impact
This fixes the error preventing workers (like `smallcap_vwap_runner`) from entering positions when opportunities are detected.

---
**Date**: 2026-01-06
**Systems**: v3, v3_A
**Status**: ✅ Fixed
