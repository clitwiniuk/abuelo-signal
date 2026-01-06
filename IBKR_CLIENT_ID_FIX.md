# IBKR Client ID Conflict Fix

## Problem
Error 326 was occurring when trying to run the EOD OHLC downloader:
```
IBKR Error 326: Unable to connect as the client id is already in use. 
Retry with a unique client id.
```

## Root Cause
Multiple IBKR connections were attempting to use the same `client_id`, causing conflicts:
- **Trader main**: Uses client_id `6000` (from config.ini)
- **EOD Downloader**: Was hardcoded to use client_id `9999`
- When both tried to connect simultaneously → Error 326

## Solution Applied
Changed the EOD OHLC downloader to use a unique client ID that doesn't conflict with the trader.

### Changes Made

#### 1. scripts/maintenance/download_eod_ohlc.py
Changed client_id from `9999` to `8001`:

```python
# Before:
self.ibkr = IBKRAdapter(
    host="127.0.0.1",
    port=7497,
    client_id=9999  # Conflicts with trader!
)

# After:
self.ibkr = IBKRAdapter(
    host="127.0.0.1",
    port=7497,
    client_id=8001  # Unique ID for EOD downloads
)
```

#### 2. config.ini
Added documentation of all client IDs in use:

```ini
[IBKR]
host = 127.0.0.1
port = 7497
# Client IDs en uso:
# 6000 - Trader principal
# 8001 - EOD OHLC downloader
# 100-999 - Workers/scanners (según configuración)
client_id = 6000
```

## Client ID Assignment Strategy

To avoid future conflicts, use this ID allocation scheme:

| Range | Purpose | Example |
|-------|---------|---------|
| 6000 | Main trader | trader_main.py |
| 8000-8999 | Maintenance scripts | EOD downloader: 8001 |
| 100-999 | Scanners/Workers | Dynamic allocation from config |
| 9000-9999 | Testing/Development | Unit tests, debugging |

## IBKR Client ID Rules

1. **Unique IDs Required**: Each simultaneous connection to IBKR must have a unique client_id
2. **Maximum Connections**: TWS/IB Gateway supports ~32 simultaneous connections
3. **ID Range**: Valid range is 0-9999
4. **Persistence**: IDs can be reused after disconnection

## Files Changed
- `scripts/maintenance/download_eod_ohlc.py` - Changed client_id from 9999 to 8001
- `config.ini` - Added documentation of client ID allocation

---
**Date**: 2026-01-06
**System**: v3_A
**Status**: ✅ Fixed
