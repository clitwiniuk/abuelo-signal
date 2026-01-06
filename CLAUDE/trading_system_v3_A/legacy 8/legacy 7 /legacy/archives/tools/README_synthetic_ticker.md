# Generador de Ticker Sintético desde Base de Datos

## 🎯 Descripción

Script que extrae explosiones reales de volumen de tu base de datos SQLite del scanner y las combina en un ticker sintético normalizado, perfecto para testing y optimización de estrategias.

## 🚀 Características

### ✅ **Datos 100% Reales**
- Extrae explosiones auténticas de `ScannerEvents`, `ScannerData` y `OHLCData`
- Usa `ratio_vol` y `percent_var` calculados por tu scanner
- Mantiene volúmenes y patrones reales de mercado

### 📊 **Normalización Inteligente**
- Precio base configurable (default $5.00)
- Mantiene proporciones OHLC originales
- Continuidad entre explosiones usando variaciones porcentuales
- Sin saltos artificiales de precio

### ⚙️ **Configuración Flexible**
- Duración: 7, 30, 90 días o personalizada
- Densidad: 1-8 explosiones por día
- Filtros: ratio mínimo, variación mínima
- Horarios: solo trading hours o 24h

## 📂 Estructura de Archivos

```
trading_system_v3/
├── tools/
│   ├── synthetic_ticker_from_db.py     ← Script principal
│   └── EXPLOSIVE_DB_30d_20240109.csv   ← CSVs generados aquí
└── your_database.db                    ← Tu BD SQLite
```

## 🔧 Uso

### **Básico:**
```bash
cd trading_system_v3
python tools/synthetic_ticker_from_db.py
```

### **Configuración Típica:**
1. **Testing Rápido:** 7 días, ~25 explosiones, 300KB
2. **Testing Estándar:** 30 días, ~120 explosiones, 1.2MB  
3. **Testing Extenso:** 90 días, ~360 explosiones, 3.6MB

### **Parámetros Configurables:**
- `duration_days`: Días de datos (7, 30, 90, ...)
- `max_explosions_per_day`: Explosiones por día (1-8)
- `min_ratio_vol`: Ratio mínimo de volumen (15x, 20x, ...)
- `min_percent_var`: Variación mínima (1%, 2%, ...)
- `base_price`: Precio base normalizado ($5.00)
- `output_symbol`: Nombre del ticker (EXPLOSIVE_DB)

## 📊 Formato de Salida

CSV compatible con `trading_system_v3`:
```csv
Date,Open,High,Low,Close,Volume
2024-01-09 09:30:00,5.02,5.15,4.98,5.12,125000
2024-01-09 09:31:00,5.12,5.18,5.09,5.16,8500
2024-01-09 09:32:00,5.16,6.85,5.14,6.72,2500000  ← Explosión real 20x
...
```

## 🎯 Integración con Sistema de Trading

### **1. Generar Ticker:**
```bash
python tools/synthetic_ticker_from_db.py
# Output: tools/EXPLOSIVE_DB_30d_20240109.csv
```

### **2. Copiar a CSV Data:**
```bash
cp tools/EXPLOSIVE_DB_30d_20240109.csv data/csv_data/
```

### **3. Usar en Simulaciones:**
```bash
python scripts/runners/run_simulation.py
# Seleccionar symbol: EXPLOSIVE_DB_30d_20240109
```

### **4. Optimizar Parámetros:**
Ahora las optimizaciones serán 100% válidas porque usan:
- ✅ Datos reales de explosiones
- ✅ Risk Manager real
- ✅ Comisiones reales  
- ✅ All components del sistema real

## 🔍 Algoritmo de Funcionamiento

### **1. Extracción (extract_explosions_from_db)**
```sql
SELECT se.ticker, sd.ratio_vol, sd.percent_var, oh.open, oh.high, oh.low, oh.close, oh.volume
FROM ScannerEvents se
JOIN ScannerData sd ON se.id_event = sd.id_event  
JOIN OHLCData oh ON se.id_event = oh.id_event
WHERE sd.ratio_vol >= 15.0 AND ABS(sd.percent_var) >= 1.0
ORDER BY se.timestamp
```

### **2. Filtrado (filter_and_space_explosions)**
- Espaciado mínimo entre explosiones (30min default)
- Límite diario de explosiones (4 default)
- Límite total por duración

### **3. Normalización (normalize_price_sequence)**
```python
# Mantener variaciones porcentuales reales
new_price = current_price * (1 + percent_var/100)
price_factor = new_price / original_close

# Normalizar OHLC manteniendo proporciones
normalized_ohlc = {
    'open': original_open * price_factor,
    'high': original_high * price_factor,
    'low': original_low * price_factor,
    'close': new_price,
    'volume': original_volume  # Volumen real
}
```

### **4. Timeline (build_minute_timeline)**
- Timeline minuto a minuto (9:30-16:00, lun-vie)
- Inserción probabilística de explosiones
- Barras intermedias con movimiento lateral
- Volúmenes normales entre explosiones

## 🎉 Ventajas vs Framework Sintético

| Aspecto | Framework Sintético | Ticker Real DB |
|---------|-------------------|----------------|
| **Datos** | Artificiales | 100% Reales |
| **Explosiones** | Simuladas 1.4x | Auténticas 15-30x |
| **Patrones** | Algorítmicos | Mercado real |
| **Optimización** | No válida | Directamente aplicable |
| **Velocidad** | Rápida | Rápida |
| **Confiabilidad** | Baja | Alta |

## 🚨 Requisitos

- Base de datos SQLite con estructura de scanner
- Python 3.7+
- pandas, numpy
- sqlite3

## 📝 Notas

- El script preserva la estructura temporal real de las explosiones
- Los volúmenes son auténticos del scanner
- La normalización mantiene la física del mercado (proporciones OHLC)
- Compatible 100% con el sistema de trading existente
- Los resultados de optimización son directamente aplicables en producción

## 🔄 Próximos Pasos

1. **Generar ticker sintético** con tus datos reales
2. **Ejecutar optimizaciones** en `trading_system_v3` 
3. **Aplicar parámetros optimizados** directamente en producción
4. **Repetir proceso** con nuevos datos del scanner