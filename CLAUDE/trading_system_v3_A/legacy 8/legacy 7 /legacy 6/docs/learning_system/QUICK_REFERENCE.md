# Learning System - Referencia Rápida

## ⏰ **TIMING CRÍTICO - LEE ESTO PRIMERO**

### **🌅 CUÁNDO Meter Datos:**
- ✅ **9:45-10:15 AM ET** → MOMENTO ÓPTIMO
- ❌ **Antes 9:45 AM** → Solo datos premarket (red flags)
- ⚠️ **Después 10:30 AM** → Window de oportunidad cerrándose

📖 **Guía completa**: [TIMING_GUIDE.md](TIMING_GUIDE.md)

## 🚀 Quick Start

### **Ejecutar Sistema**
```bash
# Streamlit con learning integrado
streamlit run quality_trading_standalone.py

# Demo completo del sistema
python examples/learning_system/demo_complete_system.py

# Tests del sistema
python examples/learning_system/test_integrated_learning.py
```

### **Monitoreo y Administración**
```bash
# Ver estadísticas del learning
python quality_core/learning_monitor.py stats

# Ver predicciones recientes (últimas 10)
python quality_core/learning_monitor.py predictions

# Ver predicciones recientes (últimas 20)
python quality_core/learning_monitor.py predictions --limit 20

# Actualizar resultados pendientes (simulación)
python quality_core/learning_monitor.py update --dry-run

# Actualizar resultados pendientes (real)
python quality_core/learning_monitor.py update

# Exportar datos para análisis
python quality_core/learning_monitor.py export learning_data.json

# Reset completo del sistema (¡CUIDADO!)
python quality_core/learning_monitor.py reset --confirm
```

## 📊 Comandos de Debug

### **Verificar Setup**
```bash
# Verificar imports de Streamlit
python tools/learning_system/test_streamlit_imports.py

# Test completo del sistema integrado
python examples/learning_system/test_integrated_learning.py

# Demo funcional con tickers reales
python examples/learning_system/demo_complete_system.py
```

### **Acceso Directo a Base de Datos**
```bash
# SQLite command line
sqlite3 learning_system.db

# Ver todas las tablas
.tables

# Ver predicciones recientes
SELECT ticker, predicted_grade, predicted_score, timestamp 
FROM predictions 
ORDER BY timestamp DESC 
LIMIT 10;

# Ver resultados trackeados
SELECT p.ticker, p.predicted_grade, r.final_result, r.return_eod
FROM predictions p
JOIN prediction_results r ON p.id = r.prediction_id
ORDER BY p.timestamp DESC;
```

## 🎯 API Reference

### **Advanced Setup Analyzer**
```python
from quality_core.advanced_setup_analyzer import analyze_setup_comprehensive

# Análisis básico
result = analyze_setup_comprehensive(
    ticker="PPSI",
    current_price=4.42,
    current_volume=80_600_000,
    premarket_gap_pct=42.1
)

# Con base de datos custom
result = analyze_setup_comprehensive(
    ticker="PPSI",
    current_price=4.42,
    current_volume=80_600_000,
    premarket_gap_pct=42.1,
    learning_db_path="custom_learning.db"
)

# Resultado incluye:
# result['grade']           # A+, A, A-, B+, B, C, D
# result['overall_score']   # 0-100
# result['recommendation']  # STRONG BUY, BUY, etc.
# result['red_flags']       # Lista de problemas detectados
# result['key_factors']     # Lista de factores positivos
```

### **Learning System Direct**
```python
from quality_core.learning_system import AutoLearningSystem

# Inicializar sistema
learning_system = AutoLearningSystem("learning_system.db")

# Ver estadísticas
stats = learning_system.get_system_stats()
print(f"Total predictions: {stats['total_predictions']}")
print(f"Learning enabled: {stats['learning_enabled']}")
print(f"Current weights: {stats['current_weights']}")

# Actualizar resultados y aprender
results = learning_system.update_results_and_learn()
print(f"Updated {results['updated_results']} results")

# Obtener pesos actuales
weights = learning_system.get_current_weights()
```

## ⚖️ Factor Weights

### **Default Weights**
```python
default_weights = {
    'consolidation': 0.30,  # 30% - Más importante
    'timing': 0.25,         # 25% - Timing del movimiento  
    'volume': 0.25,         # 25% - Interés institucional
    'news': 0.20           # 20% - Calidad del catalizador
}
```

### **Weight Evolution Example**
```python
# Al principio (default)
weights = {'consolidation': 0.30, 'timing': 0.25, 'volume': 0.25, 'news': 0.20}

# Después de 50 predicciones con resultados
# Si consolidation correlaciona más con éxito:
weights = {'consolidation': 0.35, 'timing': 0.22, 'volume': 0.23, 'news': 0.20}

# Después de 100 predicciones
# Si timing se vuelve más predictivo:
weights = {'consolidation': 0.32, 'timing': 0.28, 'volume': 0.22, 'news': 0.18}
```

## 🔴 Red Flags Comunes

### **Timing Red Flags**
- `"Excessive premarket movement - likely exhausted"` → Gap >80% en premarket
- `"Losing momentum in regular hours"` → Debilidad después de gap fuerte

### **Consolidation Red Flags**  
- `"Weak or no consolidation pattern"` → <30 score en consolidación
- `"Insufficient historical data for analysis"` → Sin datos históricos

### **Volume Red Flags**
- `"Distribution pattern detected"` → Correlación precio-volumen negativa
- `"Low overall quality score"` → Score general <40

## 📈 Scoring System

### **Factor Scores (0-100)**
```python
# Consolidation Scoring
if consolidation_months >= 4: score += 40      # Excelente
elif consolidation_months >= 3: score += 30   # Muy bueno  
elif consolidation_months >= 2: score += 20   # Bueno
elif consolidation_months >= 1: score += 10   # Moderado

# Room to run scoring  
if distance >= 100: score += 40    # 100%+ room to run
elif distance >= 80: score += 35   # 80%+ room to run
elif distance >= 50: score += 25   # 50%+ room to run

# Volume scoring
if volume_ratio >= 10: score += 40     # Volumen excepcional
elif volume_ratio >= 5: score += 35    # Volumen muy alto
elif volume_ratio >= 3: score += 25    # Volumen alto
```

### **Overall Grades**
```python
if overall_score >= 85: grade = 'A+'    # Excelente setup
elif overall_score >= 75: grade = 'A'   # Muy buen setup
elif overall_score >= 65: grade = 'A-'  # Buen setup
elif overall_score >= 55: grade = 'B+'  # Setup promedio+
elif overall_score >= 45: grade = 'B'   # Setup promedio
elif overall_score >= 35: grade = 'C'   # Setup debajo promedio
else: grade = 'D'                       # Setup malo
```

## 🔧 Configuration

### **Learning Parameters**
```python
# En quality_core/learning_system.py - WeightLearningSystem
learning_rate = 0.1                    # Velocidad de ajuste (0.1 = 10%)
min_samples_for_learning = 20          # Mínimo para activar learning
weight_bounds = (0.05, 0.50)          # Límites de pesos (5%-50%)
```

### **Database Paths**
```python
# Default en analyze_setup_comprehensive
default_path = "learning_system.db"

# Test databases  
test_path = "examples/learning_system/test_learning.db"
demo_path = "examples/learning_system/learning_system.db"
```

## 📊 Typical Workflows

### **Desarrollo/Testing**
```bash
# 1. Verificar setup
python tools/learning_system/test_streamlit_imports.py

# 2. Ejecutar tests
python examples/learning_system/test_integrated_learning.py

# 3. Ver demo
python examples/learning_system/demo_complete_system.py

# 4. Lanzar Streamlit
streamlit run quality_trading_standalone.py
```

### **Producción/Monitoreo**
```bash
# 1. Ver estado del sistema
python quality_core/learning_monitor.py stats

# 2. Actualizar resultados pendientes
python quality_core/learning_monitor.py update

# 3. Ver predicciones recientes
python quality_core/learning_monitor.py predictions --limit 20

# 4. Exportar datos para análisis
python quality_core/learning_monitor.py export daily_export.json
```

### **Troubleshooting**
```bash
# 1. Verificar imports
python tools/learning_system/test_streamlit_imports.py

# 2. Verificar base de datos
sqlite3 learning_system.db ".tables"

# 3. Ver logs
tail -f trading_system.log | grep -i "learning"

# 4. Reset si necesario
python quality_core/learning_monitor.py reset --confirm
```

## 🎯 Casos de Uso Típicos

### **Análisis PPSI (Problemático)**
```python
result = analyze_setup_comprehensive("PPSI", 4.42, 80_600_000, 42.1)
# Expected: Grade C o D, red flags por premarket exhausted
```

### **Setup Ideal (Hipotético)**
```python
result = analyze_setup_comprehensive("IDEAL", 3.50, 5_000_000, 15.0)
# Expected: Grade A o A+, consolidation months > 3, good room to run
```

### **Monitoreo Diario**
```bash
# Morning routine
python quality_core/learning_monitor.py stats
python quality_core/learning_monitor.py update
streamlit run quality_trading_standalone.py

# Evening routine  
python quality_core/learning_monitor.py update
python quality_core/learning_monitor.py predictions --limit 10
```

---

## 📞 Support

Para problemas comunes:

1. **Import errors** → `test_streamlit_imports.py`
2. **Database issues** → `learning_monitor.py stats`  
3. **No predictions** → Verificar que Streamlit esté loggeando
4. **Learning not working** → Necesita >20 predictions con resultados
5. **Wrong grades** → Sistema aprende gradualmente, dale tiempo

¡Sistema listo para uso productivo! 🚀