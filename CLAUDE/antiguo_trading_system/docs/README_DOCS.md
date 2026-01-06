# 📚 Documentación del Trading System v3

## 📋 Índice de Documentación

### 🚀 **Guías de Inicio Rápido**
- **[COMO_EJECUTAR_MOCK.md](COMO_EJECUTAR_MOCK.md)** - Cómo usar el sistema con mock adapter
- **[SIMULATION_GUIDE.md](SIMULATION_GUIDE.md)** - Guía completa del sistema de simulación
- **[ESTRUCTURA_ORGANIZADA.md](ESTRUCTURA_ORGANIZADA.md)** - Nueva estructura del proyecto

### 🏗️ **Desarrollo y Configuración**
- **[ADD_NEW_STRATEGY.md](ADD_NEW_STRATEGY.md)** - Cómo agregar nuevas estrategias
- **[strategy_selection.md](strategy_selection.md)** - Selección y configuración de estrategias
- **[THREAD_SAFE_ADAPTER_README.md](THREAD_SAFE_ADAPTER_README.md)** - Documentación del adapter thread-safe

### 📈 **Estrategias y Trading**
- **[gap_go_procedure_guide.md](gap_go_procedure_guide.md)** - Procedimientos para estrategia Gap & Go
- **[README_MULTI_STRATEGY.md](README_MULTI_STRATEGY.md)** - Sistema multi-estrategia

### 📊 **Operativa y Demo**
- **[Operativa demo TWS.numbers](Operativa demo TWS.numbers)** - Demo de operativa con TWS

## 🎯 **Quick Start Recomendado**

### 1. **Primera Vez**
```bash
# Leer primero
docs/ESTRUCTURA_ORGANIZADA.md
docs/COMO_EJECUTAR_MOCK.md

# Ejecutar test básico
python simulation/simple_mock_test.py
```

### 2. **Desarrollo de Estrategias**
```bash
# Leer documentación
docs/ADD_NEW_STRATEGY.md
docs/strategy_selection.md

# Ejecutar tests
python scripts/runners/run_backtest.py
```

### 3. **Simulación Avanzada**
```bash
# Leer guía completa
docs/SIMULATION_GUIDE.md

# Ejecutar simulación completa
python scripts/runners/run_simulation.py
```

## 📁 **Estructura de la Documentación**

```
docs/
├── README_DOCS.md              # Este índice
├── COMO_EJECUTAR_MOCK.md      # Ejecución con mock ⭐
├── SIMULATION_GUIDE.md        # Simulación completa ⭐
├── ESTRUCTURA_ORGANIZADA.md   # Nueva estructura ⭐
├── ADD_NEW_STRATEGY.md        # Desarrollo de estrategias
├── strategy_selection.md      # Selección de estrategias
├── gap_go_procedure_guide.md  # Procedimientos Gap & Go
├── README_MULTI_STRATEGY.md   # Sistema multi-estrategia
├── THREAD_SAFE_ADAPTER_README.md  # Adapter thread-safe
└── Operativa demo TWS.numbers # Demo operativa
```

⭐ = Documentos más importantes para empezar

## 🔍 **Buscar por Tema**

### **Mock y Simulación**
- `COMO_EJECUTAR_MOCK.md` - Uso del mock adapter
- `SIMULATION_GUIDE.md` - Simulación completa

### **Estrategias de Trading**
- `ADD_NEW_STRATEGY.md` - Crear estrategias
- `strategy_selection.md` - Configurar estrategias
- `gap_go_procedure_guide.md` - Estrategia Gap & Go específica
- `README_MULTI_STRATEGY.md` - Sistema multi-estrategia

### **Arquitectura y Estructura**
- `ESTRUCTURA_ORGANIZADA.md` - Organización del proyecto
- `THREAD_SAFE_ADAPTER_README.md` - Adapter técnico

### **Operativa**
- `Operativa demo TWS.numbers` - Demo con TWS real

## 🚀 **Flujo de Lectura Recomendado**

### **Para Nuevos Usuarios:**
1. `ESTRUCTURA_ORGANIZADA.md` - Entender la organización
2. `COMO_EJECUTAR_MOCK.md` - Primer test
3. `SIMULATION_GUIDE.md` - Simulación completa

### **Para Desarrolladores:**
1. `ADD_NEW_STRATEGY.md` - Crear estrategias
2. `strategy_selection.md` - Configurar estrategias
3. `THREAD_SAFE_ADAPTER_README.md` - Aspectos técnicos

### **Para Trading Avanzado:**
1. `README_MULTI_STRATEGY.md` - Sistema multi-estrategia
2. `gap_go_procedure_guide.md` - Procedimientos específicos
3. `Operativa demo TWS.numbers` - Operativa real

---

💡 **Tip:** Usa `python start.py` para acceso rápido a todas las funcionalidades del sistema.