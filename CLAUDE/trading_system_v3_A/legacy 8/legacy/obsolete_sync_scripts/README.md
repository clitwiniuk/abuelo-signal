# Obsolete Sync Scripts

This directory contains **deprecated synchronization scripts** from the old TradeTally sync system.

## Deprecation Notice

⚠️ **These scripts are NO LONGER USED** as of October 2025.

The system has been migrated to:
- **API-First Architecture** (v2.0.0)
- **Real-time WebSocket synchronization**
- **Automatic file-watching sync daemon**

## Files in this directory

### Sync State Files (JSON)
- `tradetally_sync_state.json` - Old sync state tracker
- `tradetally_sync_state.json.backup` - Backup of old state

### Manual Sync Scripts (Python)
- `reset_tradetally_sync.py` - Manual reset of old sync state
- `reset_sync_auto.py` - Auto-reset script for old system
- `debug_tradetally_sync.py` - Debug tool for old sync issues

### Shell Scripts
- `sync_trades.sh` - Bash wrapper for manual sync

### Test Scripts
- `test_tradetally_fields.py` - Field testing script

## Why were these deprecated?

The old system used **manual/scheduled synchronization** which required:
- Manual execution or cron jobs
- State tracking files
- Multiple debug/reset scripts
- No real-time updates

The new system provides:
- ✅ **Real-time sync** via WebSocket
- ✅ **Automatic file watching** (watchdog)
- ✅ **No manual intervention** needed
- ✅ **Cleaner architecture** with API separation

## What to use instead?

### Starting the system:
```bash
tt-manage start
```

This automatically starts:
1. Backend (API + WebSocket server)
2. Frontend (Vite dev server)
3. Auto-sync daemon (file watcher + WebSocket client)

### Checking sync status:
```bash
python integrations/tradetally/cli/tradetally_cli.py status
```

### Manual sync (if needed):
```bash
python integrations/tradetally/cli/tradetally_cli.py sync
```

## Can I delete these files?

**Yes**, these files can be safely deleted if you don't need the historical reference.

They are kept here only for:
- Historical reference
- Emergency rollback (unlikely needed)
- Understanding the old architecture

---

**Last updated:** October 25, 2025
**Deprecated in:** TradeTally v2.0.0 (API-First Architecture)
