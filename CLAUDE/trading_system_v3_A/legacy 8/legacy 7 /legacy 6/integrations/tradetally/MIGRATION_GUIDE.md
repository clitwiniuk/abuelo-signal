# Migration Guide - Legacy to API-First Architecture

## 📋 Overview

This guide helps you migrate from the old **PostgreSQL-direct** architecture to the new **API-First** architecture.

**Migration Date:** October 25, 2025
**Deprecation Period:** 3 months (until January 2026)
**New Version:** 2.0.0

## 🔄 What Changed?

### Architecture

**Old (v1.x - DEPRECATED):**
```
Python → psycopg2 → PostgreSQL
```

**New (v2.x - CURRENT):**
```
Python → HTTP API → Node.js Backend → PostgreSQL
```

### File Structure

```
integrations/tradetally/
├── core/
│   ├── tradetally_api_client.py       ✅ NEW - Use this
│   ├── equity_manager.py              ✅ Still valid
│   └── __init__.py                    ✅ Updated
├── cli/
│   └── tradetally_cli.py              ✅ NEW - Renamed from tradetally_cli_new.py
├── legacy/                            ⚠️ DEPRECATED - Don't use
│   ├── tradetally_sync.py             ❌ Old
│   ├── tradetally_sync_hybrid.py      ❌ Old
│   ├── tradetally_manual_sync.py      ❌ Old
│   ├── tradetally_scheduled_sync.py   ❌ Old
│   ├── tradetally_cli.py              ❌ Old (original)
│   └── README.md                      📖 Deprecation notice
└── docs/
    ├── API_FIRST_ARCHITECTURE.md      📖 New architecture guide
    └── MIGRATION_GUIDE.md             📖 This file
```

## 🚀 Quick Migration

### 1. Update `.env.local`

**Remove these (no longer needed):**
```bash
# PG_HOST=localhost
# PG_PORT=5432
# PG_DATABASE=carlos
# PG_USER=carlos
# PG_PASSWORD=
```

**Keep/Add these:**
```bash
TRADETALLY_API_KEY=tt_live_xxxxxxxxxxxxx
TRADETALLY_BASE_URL=http://localhost:8001
TRADETALLY_USER_ID=your-uuid-here
TRADING_DB_PATH=trading_data.db
```

### 2. Update Dependencies

**Remove (if not used elsewhere):**
```bash
pip uninstall psycopg2-binary
```

**Keep:**
```bash
pip install requests python-dotenv
```

### 3. Update Code

**Old code:**
```python
from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration

sync = TradeTallyIntegration(
    api_key=api_key,
    base_url=base_url,
    db_path=db_path
)

result = sync.sync_all_trades()
```

**New code:**
```python
from integrations.tradetally.core.tradetally_api_client import TradeTallyAPIClient

client = TradeTallyAPIClient(
    api_key=api_key,
    base_url=base_url,
    db_path=db_path
)

result = client.sync_all_trades()
```

Or even simpler:
```python
from integrations.tradetally import TradeTallyAPIClient  # Auto-imported

client = TradeTallyAPIClient(api_key, base_url, db_path)
```

### 4. Update CLI Usage

**Old:**
```bash
python -m integrations.tradetally.cli.tradetally_cli sync
```

**New:**
```bash
python integrations/tradetally/cli/tradetally_cli.py sync
```

Commands are the same, just different invocation.

## 📊 Feature Comparison

| Feature | Old (v1.x) | New (v2.x) |
|---------|-----------|-----------|
| **Connection** | Direct PostgreSQL | REST API |
| **Auth** | Database credentials | API Key |
| **UUID Handling** | Manual casting needed | Handled by API |
| **Dependencies** | psycopg2 required | Only requests |
| **Error Handling** | DB-level errors | HTTP status codes |
| **Validation** | Client-side | Server-side |
| **Scalability** | Limited | High |
| **Security** | DB credentials exposed | API key only |
| **Monitoring** | Difficult | Easy (HTTP logs) |

## 🔍 Common Migration Issues

### Issue 1: Import Errors

**Error:**
```python
ModuleNotFoundError: No module named 'integrations.tradetally.core.tradetally_sync'
```

**Solution:**
```python
# Change this:
from integrations.tradetally.core.tradetally_sync import TradeTallyIntegration

# To this:
from integrations.tradetally.core.tradetally_api_client import TradeTallyAPIClient
```

### Issue 2: PostgreSQL Connection Errors

**Error:**
```
psycopg2.OperationalError: could not connect to server
```

**Solution:**
You don't need PostgreSQL connection anymore! The API handles it. Just ensure:
1. TradeTally backend is running: `cd tradetally/backend && npm start`
2. API key is configured in `.env.local`

### Issue 3: UUID Type Errors

**Error:**
```
operator does not exist: uuid = character varying
```

**Solution:**
This error should NOT occur in the new architecture. If you see it, you're using the old code. Switch to `TradeTallyAPIClient`.

## ✅ Migration Checklist

- [ ] Backup your current code
- [ ] Update `.env.local` with API key
- [ ] Remove PostgreSQL connection vars
- [ ] Update imports to use `TradeTallyAPIClient`
- [ ] Test with `python integrations/tradetally/cli/tradetally_cli.py test`
- [ ] Run a sync test: `python integrations/tradetally/cli/tradetally_cli.py sync --today`
- [ ] Verify data in TradeTally web UI
- [ ] Update any automated scripts
- [ ] Remove old code references
- [ ] Uninstall psycopg2 (if not needed elsewhere)

## 🆘 Need Help?

### Verify API is Working

```bash
# Test connection
python integrations/tradetally/cli/tradetally_cli.py test

# Check status
python integrations/tradetally/cli/tradetally_cli.py status

# Show config
python integrations/tradetally/cli/tradetally_cli.py config
```

### Test API Directly

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8001/api/v1/sync-metadata/status
```

### Check Backend

```bash
cd tradetally/backend
npm start
# Should see: Server running on port 8001
```

## 📚 Documentation

- [API-First Architecture Guide](./docs/API_FIRST_ARCHITECTURE.md)
- [Legacy Code Notice](./legacy/README.md)
- [TradeTally Backend API](../../tradetally/backend/src/routes/v1/sync-metadata.routes.js)

## 🗓️ Timeline

- **October 25, 2025**: New architecture released (v2.0.0)
- **November 2025**: Legacy code marked deprecated
- **December 2025**: Final warnings
- **January 2026**: Legacy code removed

## 💡 Why This Change?

1. **No more UUID errors** - API handles type conversions
2. **Better security** - API keys instead of DB credentials
3. **Easier to maintain** - Clear separation of concerns
4. **More scalable** - Can add more clients easily
5. **Industry standard** - REST API is universal
6. **Future-proof** - Can add WebSockets, caching, etc.

---

**Questions?** Check the [API-First Architecture Guide](./docs/API_FIRST_ARCHITECTURE.md) or create an issue.
