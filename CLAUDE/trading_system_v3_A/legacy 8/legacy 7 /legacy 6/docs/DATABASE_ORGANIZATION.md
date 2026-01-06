# Database Organization Guide

## 📊 Database Structure by Purpose

### 🎯 MAIN SYSTEM DATABASE
- **File**: `trading_data.db`
- **Purpose**: Primary system database for active trading
- **Used by**: 
  - `core/database_manager.py` (DatabaseManager)
  - `scanner/scanner_intelligence.py` (ScannerIntelligence)  
  - `streamlit_app_v4.py` (Main interface)
- **Tables**: trades, daily_stats, trading_journal, manual_symbols, position_risk_config, advanced_trading_results
- **Status**: ✅ Active - Single source of truth

### 🏭 ENVIRONMENT-SPECIFIC DATABASES
- **File**: `production/trading_data.db`
- **Purpose**: Production environment database
- **Used by**: Production deployment scripts
- **Status**: ✅ Keep separate - Production isolation

- **File**: `tests/trading_data.db`
- **Purpose**: Testing environment database
- **Used by**: Test suites and unit tests
- **Status**: ✅ Keep separate - Testing isolation

### 📚 HISTORICAL DATA
- **File**: `data/trading_history.db`
- **Purpose**: Historical trading data archive
- **Used by**: Historical analysis tools
- **Status**: ✅ Keep separate - Archive purpose

### 📝 SYSTEM LOGS
- **File**: `logs/trading_data.db`  
- **Purpose**: System logging and audit trail
- **Used by**: Logging systems
- **Status**: ✅ Keep separate - Logging isolation

### 🤖 ML EXPERIMENTS
- **Files**: `examples/learning_system/*.db`
- **Purpose**: Machine Learning experiments and research
- **Used by**: ML research scripts
- **Status**: ✅ Keep separate - Research sandbox

### 💾 BACKUPS
- **Directory**: `backups/`
- **Purpose**: Database backups and snapshots
- **Structure**:
  - `backups/legacy/` - Old backup files
  - `backups/[date]/` - Timestamped backups
- **Status**: ✅ Organized by date

### 🗃️ ARCHIVED SYSTEMS
- **Directory**: `archive/old_scanner_system/`
- **Files**: `scanner_learning.db`, `scanner_intelligence_old.py`
- **Purpose**: Previous scanner system version
- **Status**: ✅ Archived safely

## 🔗 Database-Script Mapping

### Core System Scripts
- `core/database_manager.py` → `trading_data.db`
- `scanner/scanner_intelligence.py` → `trading_data.db` 
- `streamlit_app_v4.py` → `trading_data.db`

### Utility Scripts
- `reset_database_complete.py` → Multiple databases (reset tool)
- `tools/db_to_synthetic_ticker.py` → `trading_data.db` (data generation)
- `analyze_db_data.py` → `trading_data.db` (analysis tool)

### Test Scripts
- `tests/comprehensive_v4_tests/test_*.py` → `tests/trading_data.db`

## 📋 Best Practices

### ✅ DO
- Use `trading_data.db` for all active system operations
- Keep environment databases separate (prod, test, dev)
- Maintain regular backups in organized directories
- Document database purpose and ownership

### ❌ DON'T  
- Mix production and test data
- Create duplicate databases without purpose
- Store backups in root directory
- Delete archived systems without documentation

## 🔄 Migration Notes

### Recent Changes (2025-08-19)
- Consolidated scanner system to use main `trading_data.db`
- Archived old `scanner_learning.db` system
- Added `advanced_trading_results` table for ML integration
- Organized backup files into structured directories

### Future Considerations
- Consider periodic archival of old trades to `data/trading_history.db`
- Implement automated backup rotation
- Monitor database sizes and performance