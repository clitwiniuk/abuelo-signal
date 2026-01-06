# Trading System v3 - Reorganization Plan

## 🎯 Objetivo
Organizar el directorio `trading_system_v3` moviendo código obsoleto a `legacy/` sin afectar el funcionamiento del sistema actual.

---

## 📊 Estado Actual vs Propuesto

### **Directorios ACTIVOS (mantener)**
```
trading_system_v3/
├── adapters/           ✅ IBKR connection, broker adapters
├── core/               ✅ Service locator, risk manager, execution
├── scanner/            ✅ Intraday & swing scanners
├── strategies/         ✅ Workers & strategy engines
├── notifications/      ✅ Telegram notifications
├── utils/              ✅ Logging, helpers
├── logs/               ✅ System logs
├── docs/               ✅ Documentation
└── tests/              ✅ Unit tests
```

### **Directorios OBSOLETOS (mover a legacy/)**
```
legacy/
├── old_engines/        ❌ engine/ (deprecated pipeline)
├── old_execution/      ❌ execution/ (replaced by ExecutionEngineAdapter)
├── old_backtesting/    ❌ backtesting/, backtests/, results/
├── old_analysis/       ❌ analysis/, analytics/, optimization/
├── old_systems/        ❌ sistema_II/, sistema_III/, sistema_4/
├── old_data/           ❌ data_sources/, synthetic_data/
├── old_integrations/   ❌ integrations/, tradetally/ (if unused)
├── old_ui/             ❌ ui/ (if unused)
├── old_scripts/        ❌ Test scripts & one-off analysis
└── archives/           ❌ archive/, archived/, backup/
```

### **Archivos de Configuración/Datos (mantener en root)**
```
trading_system_v3/
├── config.ini          ✅ Main configuration
├── trader_main.py      ✅ Trader process
├── scanner_main.py     ✅ Scanner process
├── simple_main.py      ✅ Simple trader (if used)
├── requirements.txt    ✅ Dependencies
├── pytest.ini          ✅ Test configuration
├── trading_data.db     ✅ Active database
└── README.md           ✅ Project documentation
```

---

## 🗂️ Plan de Reorganización

### **Paso 1: Crear estructura legacy/ organizada**
```bash
mkdir -p legacy/{old_engines,old_execution,old_backtesting,old_analysis,old_systems,old_data,old_integrations,old_ui,old_scripts,archives}
```

### **Paso 2: Mover directorios obsoletos**

#### **A. Old Engines & Execution**
```bash
# Pipeline antiguo (reemplazado por workers)
mv engine/ legacy/old_engines/
mv execution/ legacy/old_execution/
```

#### **B. Backtesting & Analysis**
```bash
# Backtesting antiguo
mv backtesting/ legacy/old_backtesting/
mv backtests/ legacy/old_backtesting/results/
mv results/ legacy/old_backtesting/optimization_results/
mv optimization/ legacy/old_analysis/

# Analysis scripts
mv analysis/ legacy/old_analysis/
mv analytics/ legacy/old_analysis/analytics/
mv quality_core/ legacy/old_analysis/quality_core/
```

#### **C. Old Systems**
```bash
# Sistemas obsoletos (v1, v2, v3)
mv sistema_II/ legacy/old_systems/
mv sistema_III/ legacy/old_systems/
mv sistema_4/ legacy/old_systems/
```

#### **D. Data & Integrations**
```bash
# Old data sources
mv data_sources/ legacy/old_data/
mv synthetic_data/ legacy/old_data/
mv data/ legacy/old_data/raw_data/  # Si no se usa activamente

# Integrations (verificar si tradetally se usa)
mv integrations/ legacy/old_integrations/
# mv tradetally/ legacy/old_integrations/  # SOLO si no se usa
```

#### **E. Archives & Backups**
```bash
mv archive/ legacy/archives/
mv archived/ legacy/archives/archived/
mv backup/ legacy/archives/backup/
```

#### **F. Old Scripts & Tests**
```bash
# Test scripts one-off (mover a legacy/old_scripts/)
mv analyze_*.py legacy/old_scripts/
mv test_*_strategy.py legacy/old_scripts/
mv test_worker_*.py legacy/old_scripts/
mv test_strategies_*.py legacy/old_scripts/
mv simple_pattern_test.py legacy/old_scripts/
mv quick_backtest.py legacy/old_scripts/
mv run_backtest.py legacy/old_scripts/
mv trend_feature_calculator.py legacy/old_scripts/
mv turb_detailed_analysis.py legacy/old_scripts/
```

#### **G. Old Documentation & Reports**
```bash
# Move old markdown reports
mv *_audit_report.md legacy/archives/reports/
mv *_fixes_applied.md legacy/archives/reports/
mv *_revised_strategy.md legacy/archives/reports/
mv log_errors_fixed.md legacy/archives/reports/
mv ACTIVE_STRATEGIES_ANALYSIS.md legacy/archives/reports/
```

#### **H. Temporary & Build Files**
```bash
# Temporales (eliminar o mover)
mv temp/ legacy/archives/temp/
mv debug/ legacy/archives/debug/
mv build/ legacy/archives/build/
mv dist/ legacy/archives/dist/
```

---

## ✅ Verificación Post-Reorganización

### **Archivos que DEBEN quedar en root:**
```
✅ config.ini
✅ trader_main.py
✅ scanner_main.py
✅ simple_main.py (verificar si se usa)
✅ requirements.txt
✅ pytest.ini
✅ trading_data.db
✅ README.md
✅ .gitignore
```

### **Directorios que DEBEN quedar en root:**
```
✅ adapters/
✅ core/
✅ scanner/
✅ strategies/
✅ notifications/
✅ utils/
✅ logs/
✅ docs/
✅ tests/
✅ production/ (si se usa para deployment)
✅ scripts/ (solo si contiene scripts activos)
```

### **Verificar funcionamiento:**
```bash
# 1. Test imports
python -c "from core.service_locator import get_service_locator; print('✅ Core OK')"
python -c "from scanner.smallcap_daily_scanner import SmallcapDailyScanner; print('✅ Scanner OK')"
python -c "from strategies.worker_based_strategy_engine import WorkerBasedStrategyEngine; print('✅ Strategies OK')"

# 2. Run syntax check
python -m py_compile trader_main.py scanner_main.py

# 3. Check database access
python -c "import sqlite3; conn = sqlite3.connect('trading_data.db'); print('✅ Database OK'); conn.close()"
```

---

## 📝 Archivos de Configuración Obsoletos

### **Mover a legacy/archives/config/**
```bash
mkdir -p legacy/archives/config/
mv config_backup_*.ini legacy/archives/config/
mv config/ legacy/archives/config/old_config_dir/  # Si existe directorio config/
```

### **Bases de datos obsoletas**
```bash
# Verificar si se usan, si no:
mv optimization_results.db legacy/archives/databases/
mv database_quality.db legacy/archives/databases/
```

---

## 🚨 PRECAUCIONES

### **NO MOVER (sin verificar primero):**
1. **tradetally/** - Verificar si TradeTally sync está activo
2. **production/** - Puede contener scripts de deployment
3. **scripts/** - Puede tener scripts útiles (revisar contenido)
4. **ui/** - Si hay dashboard activo
5. **examples/** - Puede ser útil para referencia
6. **filters/** - Puede estar en uso
7. **hedging/** - Si hay lógica de hedging activa

### **Verificar antes de mover:**
```bash
# Buscar referencias en código activo
grep -r "from tradetally" trader_main.py scanner_main.py core/ strategies/ scanner/
grep -r "from production" trader_main.py scanner_main.py core/ strategies/ scanner/
grep -r "from filters" trader_main.py scanner_main.py core/ strategies/ scanner/
```

---

## 📊 Estructura Final Esperada

```
trading_system_v3/
│
├── adapters/              # ✅ IBKR & broker adapters
├── core/                  # ✅ Core services
├── scanner/               # ✅ Intraday & swing scanners
│   ├── intraday/
│   ├── swing/            # 🆕 Para swing trading
│   └── ...
├── strategies/            # ✅ Workers & engines
│   ├── workers/
│   ├── swing_workers/    # 🆕 Para swing trading
│   └── ...
├── notifications/         # ✅ Telegram & alerts
├── utils/                 # ✅ Utilities
├── logs/                  # ✅ System logs
├── docs/                  # ✅ Documentation
├── tests/                 # ✅ Unit tests
│
├── legacy/                # 🆕 Código obsoleto organizado
│   ├── old_engines/
│   ├── old_execution/
│   ├── old_backtesting/
│   ├── old_analysis/
│   ├── old_systems/
│   ├── old_data/
│   ├── old_integrations/
│   ├── old_ui/
│   ├── old_scripts/
│   └── archives/
│
├── config.ini
├── trader_main.py
├── scanner_main.py
├── requirements.txt
├── pytest.ini
├── trading_data.db
└── README.md
```

---

## 🔧 Comandos de Ejecución

### **Script de reorganización automática:**

```bash
#!/bin/bash
# reorganize.sh - Ejecutar desde trading_system_v3/

echo "🗂️ Starting reorganization..."

# 1. Crear estructura legacy
mkdir -p legacy/{old_engines,old_execution,old_backtesting,old_analysis,old_systems,old_data,old_integrations,old_ui,old_scripts,archives/{reports,config,databases,temp,debug}}

# 2. Mover engines & execution
[ -d engine ] && mv engine legacy/old_engines/
[ -d execution ] && mv execution legacy/old_execution/

# 3. Mover backtesting
[ -d backtesting ] && mv backtesting legacy/old_backtesting/
[ -d backtests ] && mv backtests legacy/old_backtesting/backtests/
[ -d results ] && mv results legacy/old_backtesting/results/
[ -d optimization ] && mv optimization legacy/old_analysis/

# 4. Mover analysis
[ -d analysis ] && mv analysis legacy/old_analysis/
[ -d analytics ] && mv analytics legacy/old_analysis/analytics/
[ -d quality_core ] && mv quality_core legacy/old_analysis/quality_core/

# 5. Mover old systems
[ -d sistema_II ] && mv sistema_II legacy/old_systems/
[ -d sistema_III ] && mv sistema_III legacy/old_systems/
[ -d sistema_4 ] && mv sistema_4 legacy/old_systems/

# 6. Mover data
[ -d data_sources ] && mv data_sources legacy/old_data/
[ -d synthetic_data ] && mv synthetic_data legacy/old_data/

# 7. Mover archives
[ -d archive ] && mv archive legacy/archives/
[ -d archived ] && mv archived legacy/archives/archived/
[ -d backup ] && mv backup legacy/archives/backup/

# 8. Mover temp
[ -d temp ] && mv temp legacy/archives/temp/
[ -d debug ] && mv debug legacy/archives/debug/
[ -d build ] && mv build legacy/archives/build/
[ -d dist ] && mv dist legacy/archives/dist/

# 9. Mover old scripts
mv analyze_*.py legacy/old_scripts/ 2>/dev/null
mv test_*_strategy.py legacy/old_scripts/ 2>/dev/null
mv test_worker_*.py legacy/old_scripts/ 2>/dev/null
mv test_strategies_*.py legacy/old_scripts/ 2>/dev/null
mv simple_pattern_test.py legacy/old_scripts/ 2>/dev/null
mv quick_backtest.py legacy/old_scripts/ 2>/dev/null
mv run_backtest.py legacy/old_scripts/ 2>/dev/null
mv trend_feature_calculator.py legacy/old_scripts/ 2>/dev/null
mv turb_detailed_analysis.py legacy/old_scripts/ 2>/dev/null
mv download_daily_ohlc.py legacy/old_scripts/ 2>/dev/null

# 10. Mover reports
mv *_audit_report.md legacy/archives/reports/ 2>/dev/null
mv *_fixes_applied.md legacy/archives/reports/ 2>/dev/null
mv *_revised_strategy.md legacy/archives/reports/ 2>/dev/null
mv log_errors_fixed.md legacy/archives/reports/ 2>/dev/null
mv ACTIVE_STRATEGIES_ANALYSIS.md legacy/archives/reports/ 2>/dev/null
mv real_trade_recommendations.txt legacy/archives/reports/ 2>/dev/null

# 11. Mover config backups
mv config_backup_*.ini legacy/archives/config/ 2>/dev/null

# 12. Mover databases obsoletas
mv optimization_results.db legacy/archives/databases/ 2>/dev/null
mv database_quality.db legacy/archives/databases/ 2>/dev/null

# 13. Mover JSON files
mv system_load_analysis.json legacy/archives/ 2>/dev/null
mv tradetally_sync_state.json legacy/archives/ 2>/dev/null

echo "✅ Reorganization complete!"
echo ""
echo "📊 Verifying system..."
python -c "from core.service_locator import get_service_locator; print('✅ Core imports OK')"
python -c "from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner; print('✅ Scanner imports OK')"
python -c "from strategies.worker_based_strategy_engine import WorkerBasedStrategyEngine; print('✅ Strategy imports OK')"
echo ""
echo "🎉 System reorganized successfully!"
```

---

## 📋 Checklist Post-Reorganización

- [ ] Ejecutar script de reorganización
- [ ] Verificar imports (core, scanner, strategies)
- [ ] Verificar que trader_main.py arranca sin errores
- [ ] Verificar que scanner_main.py arranca sin errores
- [ ] Verificar acceso a trading_data.db
- [ ] Revisar que logs/ sigue escribiendo
- [ ] Commit changes a git
- [ ] Actualizar README.md con nueva estructura
- [ ] Documentar en REORGANIZATION.md (este archivo)

---

## 🎯 Próximos Pasos

1. **Revisar plan** - Verificar que nada crítico se va a mover
2. **Backup completo** - `tar -czf trading_system_v3_backup_$(date +%Y%m%d).tar.gz trading_system_v3/`
3. **Ejecutar reorganización** - Correr script paso a paso
4. **Verificar funcionamiento** - Tests de imports y ejecución
5. **Commit a git** - Guardar estado limpio
6. **Continuar con swing trading** - Implementar Phase 1

---

**Version**: 1.0
**Created**: 2025-10-04
**Status**: Pending Approval & Execution
