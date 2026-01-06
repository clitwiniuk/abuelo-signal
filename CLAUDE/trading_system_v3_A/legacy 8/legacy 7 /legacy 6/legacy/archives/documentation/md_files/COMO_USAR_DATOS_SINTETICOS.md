# 🎯 Cómo Usar Datos Sintéticos - Guía Completa

## ✅ NUEVAS OPCIONES DISPONIBLES

Ahora en el menú principal (`python start.py`) tienes 3 nuevas opciones:

```
🎯 DATOS SINTÉTICOS
12. Generar datos sintéticos desde DB
13. Ejecutar sistema con datos sintéticos  ← ¡NUEVA!
14. Backtest con datos sintéticos
```

---

## 🚀 PASO A PASO - PRIMERA VEZ

### 1. **Generar Datos Sintéticos**
```bash
python start.py
# Seleccionar opción: 12
```

Esto extrae **200 eventos reales** de explosiones de volumen de tu base de datos y crea:
- **174 archivos CSV** con días completos de trading
- **events_metadata.csv** con información de timing exacto

### 2. **Ejecutar Sistema con Datos Sintéticos**
```bash
python start.py
# Seleccionar opción: 13
```

Esto lanza el sistema de trading usando los datos sintéticos con:
- **5 símbolos predeterminados**: AAAA, AAAB, AAAC, AAAD, AAAE
- **Modo TESTING** (MockAdapter + datos sintéticos)
- **Análisis en tiempo real** de eventos reales de explosión

---

## 📊 QUÉ VERÁS AL EJECUTAR

Cuando selecciones la **opción 13**, verás:

```
🎯 SISTEMA DE TRADING CON DATOS SINTÉTICOS
============================================================
📊 Eventos disponibles: 200
📁 Símbolos sintéticos: 174  
📈 Ratio volumen promedio: 17.4x
📅 Período: 2025-02-25 a 2025-02-28
============================================================

🤖 IMPROVED TRADING SYSTEM
============================================================
Commands:
  add <SYMBOL>     - Add symbol to monitor
  remove <SYMBOL>  - Remove symbol from monitoring  
  status           - Show system status
  positions        - Show current positions
  stop/quit/exit   - Stop the system
  Ctrl+C           - Quick exit

📈 Símbolos configurados: AAAA, AAAB, AAAC, AAAD, AAAE
💡 Puedes agregar más con: add <SYMBOL>
```

---

## 🎮 COMANDOS INTERACTIVOS DISPONIBLES

Una vez ejecutándose, puedes usar estos comandos:

### **Agregar Más Símbolos Sintéticos**
```bash
> add AABF    # Agregar símbolo AABF
> add AACM    # Agregar símbolo AACM  
> add AADT    # Agregar símbolo AADT
```

### **Ver Estado del Sistema**
```bash
> status
```
Muestra:
- Símbolos monitoreados
- Posiciones activas
- Órdenes pendientes
- Estadísticas del día

### **Ver Posiciones**
```bash
> positions
```

### **Remover Símbolos**
```bash
> remove AAAA
```

### **Parar el Sistema**
```bash
> stop
# O presionar Ctrl+C
```

---

## 📈 SÍMBOLOS SINTÉTICOS DISPONIBLES

Tienes **174 símbolos** disponibles, cada uno representa un día real de trading con explosión de volumen:

- **AAAA** - DHAI (10.4x ratio volumen)
- **AAAB** - LGVN (9.8x ratio volumen)  
- **AAAC** - CLRO (12.2x ratio volumen)
- **AAAD** - APYX (6.7x ratio volumen)
- **AAAE** - PSTV (6.5x ratio volumen)
- ... y **169 más**

Cada símbolo contiene:
- ✅ **Datos OHLCV reales** del día completo
- ✅ **Evento de explosión** con timing exacto
- ✅ **Variaciones auténticas** de precio y volumen
- ✅ **Condiciones reales** de mercado

---

## 🎯 INFORMACIÓN DE EVENTOS

Cada símbolo proporciona información detallada del evento:

```python
# Por ejemplo, para AAAA:
{
    'original_ticker': 'DHAI',
    'event_timestamp': '2025-02-28 22:30:09.506561',  # Momento exacto
    'ratio_vol': 10.4,          # 10.4x volumen normal  
    'percent_var': 19.9,        # 19.9% variación precio
    'total_bars': 458,          # Barras en el dataset
}
```

Esto significa que la estrategia puede:
- **Saber exactamente** cuándo ocurrió la explosión
- **Usar datos previos** para calcular indicadores
- **Entrar después** del evento si es necesario
- **Backtestear** con condiciones reales

---

## 🔄 DIFERENCIAS CON MODO NORMAL

| Aspecto | Modo Normal | Modo Sintético |
|---------|-------------|----------------|
| **Datos** | CSV estáticos o IBKR | Eventos reales de explosión |
| **Símbolos** | AAPL, TSLA, etc. | AAAA, AAAB, etc. |
| **Variedad** | Condiciones mixtas | Explosiones de volumen |
| **Timing** | Sin eventos específicos | Timing exacto de eventos |
| **Backtesting** | Genérico | Enfocado en explosiones |

---

## 🧪 OTRAS OPCIONES DISPONIBLES

### **Opción 12: Generar Datos**
- Extrae nuevos eventos de la DB
- Configurable (ratios, fechas, cantidad)
- Actualiza datos sintéticos

### **Opción 14: Backtest Sintético**  
- Backtesting masivo sobre 200 eventos
- Estadísticas de rendimiento completas
- Análisis de edge con datos reales
- Gráficos de rendimiento

---

## 🏆 VENTAJAS CLAVE

### **Para Desarrollo de Estrategias:**
- ✅ **200 escenarios reales** de explosiones de volumen
- ✅ **Timing exacto** para entrada/salida precisa
- ✅ **Condiciones auténticas** de volatilidad
- ✅ **Datos históricos** pero controlados

### **Para Validación:**
- ✅ **Testear edge real** con explosiones auténticas
- ✅ **Comparar estrategias** en mismas condiciones  
- ✅ **Validar risk management** en alta volatilidad
- ✅ **Medir performance** consistente

### **Para Backtesting:**
- ✅ **174 días únicos** de trading
- ✅ **Eventos documentados** con metadatos
- ✅ **Resultados reproducibles**
- ✅ **Análisis estadístico** robusto

---

## 💡 CONSEJOS DE USO

1. **Empieza con pocos símbolos** (AAAA-AAAE) para observar comportamiento
2. **Usa 'status'** frecuentemente para monitorear
3. **Experimenta con diferentes símbolos** para ver variaciones
4. **Observa los logs** para entender las decisiones de la estrategia
5. **Combina con backtesting** (opción 14) para análisis completo

---

## 🎯 OBJETIVO CUMPLIDO

Con estas nuevas opciones tienes todo lo necesario para:

> **"verificar que estrategia funciona y que estrategia no funciona"**

Usando **datos reales de explosiones de volumen** con:
- ✅ **Timing exacto** de los eventos
- ✅ **Condiciones auténticas** de mercado  
- ✅ **200 escenarios diferentes** para probar
- ✅ **Sistema completo** de trading integrado

El sistema está **listo para validar estrategias con datos reales** mientras mantiene el control y reproducibilidad necesarios para el desarrollo.

---

*¡Ahora puedes probar tus estrategias con explosiones reales de volumen!*