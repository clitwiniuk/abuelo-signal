# 📁 Estructura Organizada del Trading System v3

## 🎯 Nueva Organización

El directorio ha sido reorganizado para mayor claridad y mantenibilidad:

```
trading_system_v3/
├── 📋 ARCHIVOS PRINCIPALES
│   ├── main.py                    # Punto de entrada principal
│   ├── streamlit_app_v2.py       # App web Streamlit
│   ├── config.ini                # Configuración principal
│   └── pytest.ini               # Configuración de tests
│
├── 📚 DOCUMENTACIÓN
│   ├── README.md                 # Documentación principal
│   ├── SIMULATION_GUIDE.md      # Guía del sistema de simulación
│   ├── COMO_EJECUTAR_MOCK.md    # Cómo usar el mock adapter
│   ├── ADD_NEW_STRATEGY.md      # Cómo agregar estrategias
│   └── THREAD_SAFE_ADAPTER_README.md
│
├── 🏗️ COMPONENTES CORE
│   ├── adapters/                # Conectores (IBKR, CSV, Mock)
│   ├── core/                   # Lógica central del sistema
│   ├── strategies/             # Estrategias de trading
│   ├── engine/                 # Motor de trading
│   ├── filters/                # Filtros de símbolos
│   └── utils/                  # Utilidades compartidas
│
├── 🧪 TESTING Y DESARROLLO
│   ├── tests/                  # Tests unitarios y de integración
│   ├── simulation/             # Scripts de simulación
│   ├── scripts/
│   │   ├── runners/           # Scripts para ejecutar el sistema
│   │   ├── debug/             # Scripts de debugging
│   │   └── tools/             # Herramientas auxiliares
│   └── examples/              # Ejemplos de uso
│
├── 📊 DATOS Y CONFIGURACIÓN
│   ├── data/csv/              # Datos históricos descargados
│   ├── config/                # Archivos de configuración
│   ├── backtesting/           # Motor de backtesting
│   └── backtests/             # Configuraciones de backtests
│
├── 📈 RESULTADOS Y LOGS
│   ├── logs/                  # Archivos de log
│   ├── results/               # Resultados de backtests y optimización
│   └── temp/                  # Archivos temporales
│
└── 🗃️ ARCHIVO
    └── archived/
        ├── backups/           # Backups automáticos
        └── old_debug/         # Archivos debug antiguos
```

## 🚀 Comandos Principales Actualizados

### Para Simulación y Testing:
```bash
# Test básico del mock
python simulation/simple_mock_test.py

# Menú interactivo de simulación  
python scripts/runners/run_simulation.py

# Demo automatizada
python simulation/test_simulation_interactive.py
```

### Para Ejecutar el Sistema:
```bash
# Sistema principal
python main.py

# Con backtesting
python scripts/runners/run_backtest.py

# Sistema completo
python scripts/runners/run_trading_system.py
```

### Para Gestión de Datos:
```bash
# Descargar datos
python scripts/tools/download_menu.py

# Descarga inteligente
python scripts/tools/smart_download.py

# Verificar datos
python scripts/tools/data_verification.py
```

### Para Desarrollo:
```bash
# Tests
pytest tests/

# Debugging específico
python scripts/debug/debug_backtest.py

# Optimización
python scripts/tools/optuna_optimizer.py
```

## 📁 Descripción de Carpetas

### `/adapters`
Conectores e interfaces con fuentes de datos externas:
- **ibkr_adapter.py**: Conexión a Interactive Brokers
- **mock_ibkr_adapter.py**: Mock para desarrollo sin IBKR
- **csv_data_provider.py**: Carga datos desde CSV
- **polygon_downloader.py**: Descarga datos de Polygon.io

### `/core`
Lógica central y interfaces del sistema:
- **interfaces.py**: Definiciones de interfaces
- **simulation_manager.py**: Gestión de simulaciones
- **risk_manager.py**: Gestión de riesgo
- **events.py**: Sistema de eventos

### `/strategies`
Estrategias de trading implementadas:
- **base.py**: Clase base para estrategias
- **macdv_strategy.py**: Estrategia MACD + Volume
- **gap_go_strategy.py**: Estrategia Gap & Go
- **optimized_gap_go_strategy.py**: Gap & Go optimizada
- **volume_breakout_strategy.py**: Breakouts por volumen

### `/scripts`
Scripts organizados por propósito:

#### `/scripts/runners`
Scripts principales para ejecutar el sistema:
- **run_simulation.py**: Menú de simulación
- **run_backtest.py**: Ejecutar backtests
- **run_trading_system.py**: Sistema completo
- **simple_mock_test.py**: Test básico

#### `/scripts/tools`
Herramientas y utilidades:
- **download_menu.py**: Menú de descarga de datos
- **optuna_optimizer.py**: Optimización de parámetros
- **data_manager.py**: Gestión de datos
- **emergency_kill.py**: Parada de emergencia

#### `/scripts/debug`
Scripts de debugging y desarrollo:
- **debug_backtest.py**: Debug de backtesting
- **test_simulation_interactive.py**: Tests interactivos
- **verify_adapter.py**: Verificación de adapters

### `/simulation`
Sistema de simulación para desarrollo:
- **simple_mock_test.py**: Test básico del mock
- **test_simulation_interactive.py**: Demo automatizada

### `/data`
Datos del sistema:
- **csv/**: Datos históricos descargados (36 símbolos)

### `/config`
Configuraciones:
- **simulation_config.py**: Configuración para simulación
- **polygon_config.json**: Configuración de Polygon.io

### `/results`
Resultados de análisis:
- Resultados de backtests (.xlsx)
- Parámetros optimizados (.json)
- Configuraciones optimizadas (.ini)

### `/logs`
Archivos de registro:
- **trading_system.log**: Log principal
- **backtest.log**: Log de backtesting
- **test_adapter.log**: Log de tests

### `/archived`
Archivos archivados:
- **backups/**: Backups automáticos del sistema
- **old_debug/**: Scripts debug antiguos y archivos .backup

## 🎯 Flujo de Trabajo Recomendado

### 1. **Desarrollo y Testing**
```bash
# 1. Test básico
python simulation/simple_mock_test.py

# 2. Desarrollo con datos reales
python scripts/runners/run_simulation.py

# 3. Tests completos
pytest tests/
```

### 2. **Backtesting**
```bash
# 1. Ejecutar backtest
python scripts/runners/run_backtest.py

# 2. Optimizar parámetros
python scripts/tools/optuna_optimizer.py

# 3. Ver resultados en results/
```

### 3. **Producción**
```bash
# 1. Configurar en config.ini
# 2. Ejecutar sistema principal
python main.py

# O sistema completo
python scripts/runners/run_trading_system.py
```

## 🔧 Mantenimiento

### Limpieza Periódica
```bash
# Limpiar logs antiguos
rm logs/*.log.old

# Limpiar archivos temporales
rm -rf temp/*

# Archivar resultados antiguos
mv results/old_* archived/
```

### Backup
```bash
# Crear backup manual
cp -r strategies/ archived/backups/strategies_$(date +%Y%m%d)
```

## 📋 Ventajas de la Nueva Estructura

### ✅ **Claridad**
- Archivos organizados por función
- Fácil encontrar lo que necesitas
- Separación clara entre desarrollo y producción

### ✅ **Mantenibilidad**
- Archivos relacionados juntos
- Documentación centralizada
- Logs y resultados organizados

### ✅ **Escalabilidad**
- Fácil agregar nuevas estrategias
- Scripts organizados por categoría
- Tests separados del código principal

### ✅ **Desarrollo**
- Simulación aislada
- Debugging organizado
- Ejemplos claros

La reorganización mantiene toda la funcionalidad existente pero con una estructura mucho más limpia y mantenible.