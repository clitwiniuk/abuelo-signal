# 🚀 Cómo Ejecutar el Sistema de Backtesting

## **MÉTODO MÁS FÁCIL: Menú Interactivo**

```bash
python CLAUDE/trading_system_v3/backtesting_system/menu_principal.py
```

### **¿Qué hace?**
- Te muestra un menú con 6 opciones
- Solo necesitas escribir números (1-6)
- No necesitas memorizar comandos largos
- Todo es interactivo y guiado

### **Opciones del Menú:**
1️⃣ **Listar Workers Disponibles** - Ver todos los workers
2️⃣ **Test Individual de Worker** - Probar un worker específico  
3️⃣ **Comparación Multi-Worker** - Comparar varios workers
4️⃣ **Benchmark Completo** - Test completo del sistema
5️⃣ **Ver Resultados Generados** - Ver archivos de resultados
6️⃣ **Ejecutar Demo Completo** - Demo automático

### **Ejemplo de uso:**
```
$ python CLAUDE/trading_system_v3/backtesting_system/menu_principal.py

🎯 SISTEMA DE BACKTESTING PROFESIONAL
============================================================

📋 OPCIONES DISPONIBLES:
1️⃣  Listar Workers Disponibles
2️⃣  Test Individual de Worker
3️⃣  Comparación Multi-Worker
4️⃣  Benchmark Completo
5️⃣  Ver Resultados Generados
6️⃣  Ejecutar Demo Completo
0️⃣  Salir

Selecciona una opción: 1

📋 WORKERS DISPONIBLES PARA BACKTESTING:
==================================================
  1. macdv               : MACD Divergence Strategy
  2. daily_plays         : Daily Catalyst Plays
  3. vwap                : VWAP Strategy
  [...]

Presiona Enter para continuar...
```

## **MÉTODOS ALTERNATIVOS**

### **Demo Completo Directo:**
```bash
python CLAUDE/trading_system_v3/backtesting_system/examples/demo_backtesting.py
```

### **CLI Avanzado:**
```bash
python CLAUDE/trading_system_v3/backtesting_system/main.py --list-workers
python CLAUDE/trading_system_v3/backtesting_system/main.py --worker macdv --patterns 50
python CLAUDE/trading_system_v3/backtesting_system/main.py --benchmark --all-workers
```

## **📍 UBICACIÓN ACTUAL**
- **Directorio base:** `/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/`
- **Sistema reorganizado:** `CLAUDE/trading_system_v3/backtesting_system/`
- **Menú principal:** `CLAUDE/trading_system_v3/backtesting_system/menu_principal.py`

## **✅ SISTEMA REORGANIZADO Y FUNCIONAL**
- ✅ Estructura profesional organizada
- ✅ Workers reales integrados (7 workers)
- ✅ Menú interactivo súper fácil de usar
- ✅ Resultados organizados automáticamente
- ✅ Documentación completa
- ✅ Demo verificado y funcionando

**¡Solo ejecuta el menú principal y sigue las instrucciones en pantalla!** 🎯