# 📊 Sistema de Backtesting con Datos Reales

## 🎯 **NUEVA FUNCIONALIDAD: Datos Reales de market_data.db**

### **¿Qué es?**
El sistema ahora puede usar **datos reales históricos** de tu base de datos `market_data.db` en lugar de datos sintéticos generados artificialmente.

### **¿Por qué es mejor?**
- ✅ **Datos reales de Polygon.io** (235,492 barras de 1 minuto)
- ✅ **186 símbolos** con datos históricos (Agosto-Octubre 2025)
- ✅ **Oportunidades históricas reales** detectadas automáticamente
- ✅ **Patrones reales del mercado**: gaps, breakouts, volume spikes, MACD signals
- ✅ **Resultados más confiables** para decisiones de trading

---

## 🚀 **Cómo Usar Datos Reales**

### **Opción 1: Menú Interactivo (Recomendado)**
```bash
python CLAUDE/trading_system_v3/backtesting_system/menu_principal.py
```

**En el menú:**
1. Selecciona **Opción 6** (Configuración)
2. Elige **"2. Datos REALES (desde market_data.db)"**
3. El sistema verificará automáticamente tu base de datos
4. Aplica la configuración y continúa con los tests

### **Opción 2: Test Directo**
```bash
python CLAUDE/trading_system_v3/backtesting_system/test_datos_reales.py
```

**Elige:**
- **Opción 1**: Test completo del sistema (datos reales vs sintéticos)
- **Opción 2**: Test solo del data loader

### **Opción 3: Programático**
```python
from core.backtest_runner import BacktestRunner

# Crear runner con datos reales
runner = BacktestRunner(use_real_data=True)

# Ejecutar test con datos reales
metrics = await runner.run_single_worker_test(
    worker_name="macdv",
    num_patterns=50,
    visualize=True
)
```

---

## 📈 **Lo que Obtienes con Datos Reales**

### **Oportunidades Históricas Reales**
El sistema detecta automáticamente estos patrones en tus datos históricos:

- **Gap-Go Patterns**: Gaps significativos (>2%) detectados
- **Breakout Patterns**: Rupturas de resistencias técnicas  
- **Volume Spike Patterns**: Picos de volumen anómalos
- **MACD Signal Patterns**: Señales de cruce MACD histórico

### **Ejemplo de Resultados:**
```
✅ 8,091 oportunidades reales cargadas

📝 Ejemplos de oportunidades:
   1. ABAT - gap_go - Quality: 72.0
   2. ABAT - gap_go - Quality: 77.4  
   3. ABAT - gap_go - Quality: 61.5
```

### **Estadísticas de tu Base de Datos:**
```
📈 Resumen de market_data.db:
   Total barras: 235,492
   Símbolos: 186
   Período: 2025-08-26 a 2025-10-18
   Top símbolos:
   - RR: 13,239 barras
   - IONZ: 9,112 barras
   - BITF: 7,068 barras
```

---

## 🔄 **Datos Reales vs Sintéticos**

| **Aspecto** | **Datos Reales** | **Datos Sintéticos** |
|-------------|------------------|---------------------|
| **Fuente** | market_data.db (Polygon) | Generación automática |
| **Confiabilidad** | ✅ Alta | ⚖️ Media |
| **Patrones** | Reales del mercado | Simulados |
| **Volumen** | Datos reales | Estimado |
| **Calidad** | Basada en datos históricos | Basada en algoritmos |
| **Velocidad** | Rápida (datos existentes) | Rápida |
| **Cobertura** | 186 símbolos | Ilimitada |

---

## ⚙️ **Configuración**

### **Ubicación de la Base de Datos**
El sistema busca automáticamente `market_data.db` en:
1. `CLAUDE/trading_system_v3/market_data.db` ⭐ (Principal)
2. `CLAUDE/trading_system_v3/backtesting_system/market_data.db`
3. Otras ubicaciones comunes

### **Estructura de Datos**
Tu `market_data.db` debe tener tabla `intraday_bars`:
```sql
CREATE TABLE intraday_bars (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    bar_timestamp TIMESTAMP NOT NULL,
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    volume INTEGER NOT NULL,
    vwap REAL,
    source TEXT DEFAULT 'polygon'
);
```

---

## 🎯 **Casos de Uso**

### **1. Validación de Workers con Datos Reales**
```python
# Testear si tu worker "macdv" funciona bien con datos reales
metrics = await runner.run_single_worker_test("macdv", num_patterns=100)
```

### **2. Comparación: Datos Reales vs Sintéticos**
```bash
# En el menú, opción 1 (test individual)
# 1. Ejecutar con datos sintéticos
# 2. Cambiar a datos reales (opción 6)
# 3. Ejecutar el mismo test
# 4. Comparar resultados
```

### **3. Benchmark Completo con Datos Históricos**
```bash
# Menú > Opción 4 (Benchmark Completo)
# Testea todos los workers con tus datos históricos reales
```

---

## 📊 **Ejemplo de Salida**

### **Con Datos Reales:**
```
📊 FUENTE DE DATOS ACTUAL: REALES (market_data.db)

📋 Workers disponibles:
  • macdv               : MACD Divergence Strategy
  • daily_plays         : Daily Catalyst Plays
  [...]

📊 Cargando oportunidades reales desde market_data.db...
   Oportunidades reales cargadas: 100
   Quality promedio: 68.5

✅ Test completado!
📊 Resultados:
   Win Rate: 72.0%
   Average Return: +0.15%
   Total Trades: 45
```

### **Ventajas de los Datos Reales:**
- **Win Rate más confiable** (basado en oportunidades que realmente ocurrieron)
- **Patrones auténticos** (gaps, breakouts, volumen que realmente pasaron)
- **Resultados reproducibles** (mismo dataset para todos los workers)

---

## 🛠️ **Troubleshooting**

### **Error: "market_data.db no encontrado"**
```bash
# Verificar que la base de datos existe
find . -name "market_data.db" -type f

# Debe mostrar rutas como:
# ./CLAUDE/trading_system_v3/market_data.db
```

### **Error: "Tabla intraday_bars no existe"**
```bash
# Verificar estructura de la base de datos
sqlite3 CLAUDE/trading_system_v3/market_data.db "PRAGMA table_info(intraday_bars);"
```

### **Base de datos vacía**
```bash
# Verificar datos
sqlite3 CLAUDE/trading_system_v3/market_data.db "SELECT COUNT(*) FROM intraday_bars;"
```

---

## 🎯 **Resumen**

### **✅ Sistema Completamente Mejorado:**
1. **Datos Reales**: market_data.db con 235K+ barras de 1 minuto
2. **186 Símbolos**: Cobertura amplia de activos
3. **8K+ Oportunidades**: Patrones históricos detectados automáticamente
4. **Menú Interactivo**: Configuración fácil entre datos reales/sintéticos
5. **Compatibilidad**: Funciona con el sistema existente

### **🚀 Listo para Usar:**
```bash
python CLAUDE/trading_system_v3/backtesting_system/menu_principal.py
```

**¡Ahora puedes probar tus workers con datos reales del mercado!** 📈