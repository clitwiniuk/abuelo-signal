# Database Data Visualizer

## 🎯 Descripción

Visualizador que conecta **directamente a tu base de datos SQLite** del scanner y muestra velas japonesas **100% reales** con variaciones auténticas de precio y volumen.

## 🚀 Ventajas vs CSV

| Aspecto | CSV Sintético | Base de Datos Directa |
|---------|--------------|----------------------|
| **Datos** | Artificiales/Normalizados | 100% Reales |
| **Variaciones** | Pequeñas/Uniformes | Auténticas del mercado |
| **Explosiones** | Simuladas | Detectadas por tu scanner |
| **Velocidad** | Necesita generar CSV | Instantáneo |
| **Flexibilidad** | Archivo fijo | Selección dinámica |

## 📊 Características

### ✅ **Datos Auténticos:**
- Conecta a `ScannerEvents`, `ScannerData` y `OHLCData`
- Velas japonesas con variaciones reales de precio
- Explosiones de volumen genuinas del scanner
- Sin normalización ni manipulación

### 🎯 **Modos de Visualización:**
1. **Evento Único:** Máximo detalle de una explosión específica
2. **Múltiples Eventos:** Comparar varias explosiones
3. **Top Explosiones:** Las mejores detecciones por ratio de volumen

### 📈 **Información Detallada:**
- Estadísticas de variación de precios
- Top 3 velas con mayor movimiento
- Identificación de tickers por vela
- Volúmenes y ratios reales

## 🔧 Uso

### **Básico:**
```bash
cd trading_system_v3
python tools/db_data_visualizer.py
```

### **Workflow Típico:**
1. **Conectar a BD:** Proporciona la ruta de tu SQLite
2. **Ver eventos:** Lista de últimas 30 explosiones detectadas
3. **Seleccionar modo:**
   - Evento único para análisis detallado
   - Múltiples eventos para comparación
   - Top explosiones para mejores casos

## 📋 Interfaz de Selección

```
📋 ÚLTIMOS 30 EVENTOS CON EXPLOSIONES DE VOLUMEN:
--------------------------------------------------------------------------------
#   Ticker   Fecha        Hora     Vol    %       Precio
--------------------------------------------------------------------------------
1   AAPL     2024-02-28   15:30    25.3x  +8.4%   $175.23
2   TSLA     2024-02-28   14:45    18.7x  -12.1%  $201.45
3   NVDA     2024-02-28   13:22    31.2x  +15.6%  $785.90
...

🎯 SELECCIÓN DE EVENTOS:
1. Ver evento único (máximo detalle)
2. Ver múltiples eventos (comparación)  
3. Ver top explosiones (mejores ratios)
```

## 📊 Información Mostrada

### **Estadísticas de Variación:**
```
📊 ESTADÍSTICAS DE VARIACIÓN DE PRECIOS:
   💰 Rango precio total: $174.20 - $178.90
   📊 Rango promedio por vela: $0.850
   📊 Cuerpo promedio de vela: $0.420
   📊 Variación promedio: 2.34%

🔥 TOP 3 VELAS CON MAYOR VARIACIÓN:
   1. AAPL 15:31 | ↗️ 4.2% | Vol: 2,450,000
   2. AAPL 15:33 | ↘️ 3.8% | Vol: 1,890,000
   3. AAPL 15:35 | ↗️ 2.9% | Vol: 1,234,000
```

### **Gráfico Dual:**
- **Panel Superior:** Velas japonesas con variaciones reales
- **Panel Inferior:** Volumen con explosiones marcadas
- **Colores:** Verde (alcista), Rojo (bajista), Naranja (explosión)

## 🎨 Características Visuales

### **Velas Japonesas Auténticas:**
- **Cuerpo variable:** Altura según diferencia Open-Close
- **Mechas reales:** Muestran High-Low verdaderos
- **Colores inteligentes:** Explosiones destacadas en naranja
- **Sin gaps artificiales:** Datos continuos

### **Etiquetado Inteligente:**
- **≤50 barras:** Ticker + Hora (AAPL 15:30)
- **≤200 barras:** Solo hora (15:30)
- **>200 barras:** Fecha + Hora (02-28 15:30)

## 🔍 Casos de Uso

### **1. Análisis Detallado de Explosión:**
```bash
# Seleccionar evento único para ver todos los detalles
python tools/db_data_visualizer.py
# → Opción 1 → Evento #5
```

### **2. Comparación de Múltiples Tickers:**
```bash
# Ver varios eventos juntos
# → Opción 2 → "1,3,5,7"
```

### **3. Estudio de Mejores Casos:**
```bash
# Top 10 explosiones más fuertes
# → Opción 3
```

## 📈 Queries SQL Utilizadas

### **Eventos Disponibles:**
```sql
SELECT se.id_event, se.ticker, se.timestamp, sd.ratio_vol, sd.percent_var
FROM ScannerEvents se
JOIN ScannerData sd ON se.id_event = sd.id_event
WHERE sd.ratio_vol >= 5.0
ORDER BY se.timestamp DESC
```

### **Datos OHLC:**
```sql
SELECT oh.date, oh.open, oh.high, oh.low, oh.close, oh.volume
FROM OHLCData oh
WHERE oh.id_event = ?
ORDER BY oh.date
```

## ⚡ Performance

- **Conexión directa:** Sin archivos intermedios
- **Consultas optimizadas:** Solo datos necesarios
- **Límites inteligentes:** Max 500 barras por visualización
- **Cache de conexión:** Reutiliza conexión durante la sesión

## 🎯 Resultado Esperado

**Ahora verás:**
- ✅ **Velas con diferentes tamaños** según variación real de precio
- ✅ **Explosiones auténticas** detectadas por tu scanner
- ✅ **Datos sin manipular** directos de la base de datos
- ✅ **Variaciones significativas** que reflejen la realidad del mercado
- ✅ **Selección flexible** de eventos específicos

## 🚨 Requisitos

- Base de datos SQLite con estructura del scanner
- Tablas: `ScannerEvents`, `ScannerData`, `OHLCData`
- Python: pandas, matplotlib, sqlite3

## 📝 Notas

- El visualizador detecta automáticamente explosiones por ratio de volumen
- Los datos mostrados son exactamente los detectados por tu scanner
- No hay normalización ni modificación de precios
- Ideal para validar la efectividad de tu sistema de detección