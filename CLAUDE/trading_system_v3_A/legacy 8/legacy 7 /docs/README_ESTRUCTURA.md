# 📁 Estructura del Trading System v3

## 🚀 Archivos Principales (Raíz)
```
simple_main.py    # 🎯 PUNTO DE ENTRADA PRINCIPAL
trader_main.py    # ⚡ Proceso de trading
scanner_main.py   # 🔍 Proceso de scanner
```

## 📂 Estructura Organizada

### `core/` - Motores y componentes principales
- `ml_volume_engine.py` - Motor ML de volumen
- `ml_exit_engine.py` - Motor ML de salida
- `continuous_learning_engine.py` - Motor de aprendizaje continuo
- `trading_feedback_hook.py` - Hook de feedback
- `service_locator.py` - Localizador de servicios
- Otros componentes críticos del sistema

### `strategies/` - Estrategias de trading
- `ml_strategy_selector.py` - Selector ML de estrategias
- Todas las estrategias individuales

### `adapters/` - Adaptadores de brokers
- `ibkr_adapter.py` - Adaptador Interactive Brokers

### `data/ml_models/` - Modelos ML entrenados
- `strategy_selector.json` - Modelo Thompson Sampling
- `continuous_learning_state.json` - Estado CLE
- Otros modelos ML

### `scripts/` - Scripts organizados por categoría

#### `scripts/training/` - Scripts de entrenamiento ML
- `train_ml_strategy_selector.py`
- `train_ml_exit_engine.py`
- `train_ml_volume_engine.py`
- `train_continuous_learning_engine.py`
- `train_ml_performance_monitor.py`

#### `scripts/testing/` - Scripts de testing
- `test_*.py` - Todos los scripts de prueba
- `final_streamlit_test.py`
- `run_morning_test.py`

#### `scripts/analysis/` - Scripts de análisis
- `analyze_*.py` - Scripts de análisis
- `debug_*.py` - Scripts de debugging
- `diagnose_*.py` - Scripts de diagnóstico
- `calculate_existing_confidence.py`
- `check_*.py` - Scripts de verificación

#### `scripts/maintenance/` - Scripts de mantenimiento
- `clean_*.py` - Scripts de limpieza
- `fix_*.py` - Scripts de reparación
- `reset_*.py` - Scripts de reset
- `sync_*.py` - Scripts de sincronización
- `create_*.py` - Scripts de creación

#### `scripts/development/` - Scripts de desarrollo
- `streamlit_*.py` - Aplicaciones Streamlit
- `trading_dashboard.py` - Dashboard
- `deploy_*.py` - Scripts de deployment
- `validate_*.py` - Scripts de validación
- `compare_*.py` - Scripts de comparación
- Mains alternativos (`unified_main.py`, etc.)

### `backup/` - Archivos de respaldo

#### `backup/obsolete_code/` - Código obsoleto
- `codigo_obsoleto/` - Directorio original movido

#### `backup/old_models/` - Modelos antiguos
- `backup_*_models/` - Backups de modelos

## 🎯 Uso del Sistema

### Ejecutar el sistema principal:
```bash
python simple_main.py
```

### Entrenar modelos ML:
```bash
python scripts/training/train_ml_strategy_selector.py
python scripts/training/train_ml_volume_engine.py
python scripts/training/train_ml_exit_engine.py
python scripts/training/train_continuous_learning_engine.py
```

### Testing y análisis:
```bash
python scripts/testing/test_ml_strategy_selector.py
python scripts/analysis/analyze_system_pipeline.py
```

## ⚠️ Importante
- **NUNCA mover** los archivos de la raíz (`simple_main.py`, `trader_main.py`, `scanner_main.py`)
- Las carpetas `core/`, `strategies/`, `adapters/` contienen código crítico del sistema
- Los scripts en `scripts/` son herramientas auxiliares organizadas por función

## 🏆 Beneficios de la Reorganización
- ✅ Raíz limpia con solo archivos esenciales
- ✅ Scripts organizados por función
- ✅ Fácil navegación y mantenimiento
- ✅ Separación clara entre código principal y herramientas
- ✅ Sistema principal intacto y funcional