# CRITICAL BUG: Swing Positions Lost on Restart

## Problem

SwingScheduler does NOT restore active swing positions after trader restart:
- `self.active_positions = {}` starts empty
- No restoration from database
- Positions become orphaned in broker
- No monitoring, no exits

## Impact

1. **Lost tracking:** Swing position in broker but not monitored
2. **No exits:** Stop loss, target, trailing stop won't trigger
3. **Capital leak:** UnifiedPositionManager doesn't know position exists
4. **Duplicate risk:** Could enter same symbol again (no blocking)

## Solution Required

### 1. Add restoration method to SwingScheduler.__init__()

```python
def __init__(self, scanner, worker, logger=None):
    # ... existing init ...

    # Restore active positions from database
    self._restore_active_positions()

def _restore_active_positions(self):
    """Restore active swing positions from database"""
    try:
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all ACTIVE swing trades
        cursor.execute("""
            SELECT symbol, entry_price, quantity, entry_date,
                   support_level, resistance_level, pattern_type,
                   breakout_score
            FROM swing_trades
            WHERE status = 'ACTIVE'
        """)

        for row in cursor.fetchall():
            symbol = row[0]
            self.active_positions[symbol] = {
                'symbol': symbol,
                'entry_price': row[1],
                'quantity': row[2],
                'entry_date': row[3],
                'support': row[4],
                'resistance': row[5],
                'pattern_type': row[6],
                'breakout_score': row[7]
            }

            self.logger.info(
                f"🔄 Restored swing position: {symbol} @ ${row[1]:.2f}"
            )

        conn.close()

        if len(self.active_positions) > 0:
            self.logger.info(
                f"✅ Restored {len(self.active_positions)} swing position(s)"
            )

    except Exception as e:
        self.logger.error(f"❌ Error restoring swing positions: {e}")
```

### 2. Re-register with UnifiedPositionManager

```python
def _restore_active_positions(self):
    # ... database restoration ...

    # Re-register with UnifiedPositionManager
    from core.service_locator import get_unified_position_manager
    import asyncio

    async def reregister():
        unified_manager = await get_unified_position_manager()

        for symbol, pos in self.active_positions.items():
            if unified_manager and not unified_manager.is_symbol_blocked(symbol):
                position_value = pos['entry_price'] * pos['quantity']
                unified_manager.register_position(
                    symbol=symbol,
                    strategy_type='swing',
                    position_data=pos
                )
                self.logger.info(f"💼 Re-registered {symbol} with UnifiedPositionManager")

    # Run async reregistration
    asyncio.run(reregister())
```

### 3. Database schema includes entry_time

Currently swing_trades table has:
- entry_date (DATE)

Should also have:
- entry_time (TIMESTAMP) - for accurate days_held calculation

## Testing Steps

1. Start trader
2. Enter swing position (AAPL @ $100)
3. Verify in database: `SELECT * FROM swing_trades WHERE status='ACTIVE'`
4. Kill trader: `pkill -9 -f trader_main.py`
5. Restart trader
6. Check logs: Should see "🔄 Restored swing position: AAPL @ $100"
7. Verify UnifiedPositionManager: `is_symbol_blocked('AAPL')` should return True
8. Verify monitoring: Position should continue to be checked for exits

## Priority

🔴 **CRITICAL** - Must fix before production

Without this fix:
- Swing positions lost on any restart
- Money at risk with no monitoring
- System integrity compromised
