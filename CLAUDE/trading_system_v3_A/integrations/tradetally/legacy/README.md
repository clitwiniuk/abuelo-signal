# Legacy Files - Deprecated

⚠️ **These files are DEPRECATED and should not be used in new code.**

## Why Deprecated?

The old architecture used **direct PostgreSQL access** from Python, which caused:
- ❌ UUID type mismatch errors
- ❌ High coupling between systems
- ❌ Difficult to maintain
- ❌ Hard to scale
- ❌ Security concerns (direct DB access)

## New Architecture

Use the **API-First architecture** instead:

📖 See: [API_FIRST_ARCHITECTURE.md](../docs/API_FIRST_ARCHITECTURE.md)

### Migration Path

| Old (Deprecated) | New (Use This) |
|-----------------|----------------|
| `tradetally_sync.py` | `tradetally_api_client.py` |
| `tradetally_sync_hybrid.py` | `tradetally_api_client.py` |
| `tradetally_manual_sync.py` | `tradetally_api_client.py` |
| `tradetally_scheduled_sync.py` | `tradetally_api_client.py` |
| `tradetally_cli.py` | `tradetally_cli_new.py` |

### Quick Migration Example

**Old way (deprecated):**
```python
from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration

sync = TradeTallyIntegration(api_key, base_url, db_path)
sync.sync_all_trades()
```

**New way (recommended):**
```python
from integrations.tradetally.core.tradetally_api_client import TradeTallyAPIClient

client = TradeTallyAPIClient(api_key, base_url, db_path)
client.sync_all_trades()
```

## Files in This Folder

### Sync Scripts (PostgreSQL-direct)
- `tradetally_sync.py` - Old sync with PostgreSQL
- `tradetally_sync_hybrid.py` - Old hybrid sync
- `tradetally_manual_sync.py` - Old manual sync
- `tradetally_scheduled_sync.py` - Old scheduled sync

### CLI & Tools
- `tradetally_cli.py` - Old CLI (replaced by `cli/tradetally_cli.py`)
- `tradetally_debug.py` - Debug tool for old system
- `create_test_data.py` - Test data creator (old schema)

## Deprecation Date

**October 25, 2025** - Migrated to API-First architecture

## Removal Plan

These files will be removed in **3 months** (January 2026) to give time for migration.

If you still need these files, please migrate to the new API-First architecture ASAP.
