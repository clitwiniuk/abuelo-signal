# 🚀 Plan de Migración Minimalista para market_data.db

## 📋 Resumen del Plan

Este plan documenta la **migración mínima** desde la estructura actual de `market_data.db` a la nueva estructura con eventos y contexto histórico.

---

## 🎯 Objetivo

Implementar **modificaciones mínimas** que incluyen:
- Agregar campo `event_id` a tabla `intraday_bars` existente
- Crear nueva tabla `daily_ohlcv_history` para 60 días de contexto histórico
- Mantener **100% compatibilidad** con `/smallcaps-algorithm` existente

---

## 📊 Cambios Específicos

### ❌ Estructura Actual
```
market_data.db
├── intraday_bars (estructura plana)
│   ├── symbol, bar_timestamp, OHLCV, volume
│   └── Sin vinculación a eventos específicos
└── download_metadata (básico)
```

### ✅ Estructura Después de Migración
```
market_data.db
├── intraday_bars (modificada)
│   ├── event_id INTEGER          -- NUEVO CAMPO
│   ├── symbol, bar_timestamp, OHLCV, volume
│   └── Datos del día con event_id
└── daily_ohlcv_history (nueva tabla)
    ├── event_id INTEGER NOT NULL -- Link al evento
    ├── symbol TEXT NOT NULL
    ├── history_date DATE NOT NULL
    ├── days_before_event INTEGER -- 1, 2, 3, ... 60
    ├── OHLCV, volume
    └── catalyst_type TEXT         -- Dato adicional
```

---

## 🗄️ Scripts de Migración Minimalista

### 1. Script de Inicialización
**Archivo:** `scripts/init_market_database_minimal.py`

```bash
# Ejecutar para aplicar modificaciones mínimas
cd trading_system_v3
python scripts/init_market_database_minimal.py
```

**Resultado:**
- Agrega campo `event_id` a tabla `intraday_bars`
- Crea tabla `daily_ohlcv_history` con estructura básica
- Backup automático del archivo existente

### 2. Downloader Mejorado
**Archivo:** `backtesting_system/data/polygon_data_downloader_minimal.py`

**Funcionalidades mínimas:**
- `get_or_create_event_id()` → Crear ID único para (symbol + date)
- `download_symbol_date_with_event()` → Datos intradiarios con event_id
- `download_daily_history_minimal()` → 60 días de contexto histórico
- `download_minimal_complete()` → Proceso completo optimizado

---

## ⚡ Proceso de Migración (5 minutos)

### Paso 1: Backup (1 min)
```bash
# Crear backup de la base de datos actual
cp market_data.db market_data_backup_$(date +%Y%m%d_%H%M%S).db
```

### Paso 2: Aplicar Modificaciones Mínimas (1 min)
```bash
# Ejecutar script de inicialización
python scripts/init_market_database_minimal.py
```

**Resultado esperado:**
```
🚀 Inicializando modificaciones mínimas: market_data.db
📦 Backup creado: market_data.db.backup_[timestamp]
📊 Agregando event_id a tabla intraday_bars...
📈 Creando tabla daily_ohlcv_history...
⚡ Creando índices...
✅ Base de datos actualizada exitosamente!
   - event_id en intraday_bars: ✅
   - Nueva tabla daily_ohlcv_history
```

### Paso 3: Test con Downloader Minimal (10 min)
```bash
# Test con 1 evento para verificar funcionamiento
cd backtesting_system
python data/polygon_data_downloader_minimal.py --limit 1
```

**Verificación:**
```bash
# Verificar que se agregó event_id
sqlite3 market_data.db "PRAGMA table_info(intraday_bars) | grep event_id"

# Verificar nueva tabla
sqlite3 market_data.db "SELECT COUNT(*) FROM daily_ohlcv_history;"

# Verificar datos con event_id
sqlite3 market_data.db "SELECT COUNT(*) FROM intraday_bars WHERE event_id IS NOT NULL;"
```

### Paso 4: Descarga Masiva (Variable)
```bash
# Descargar todas las oportunidades
python data/polygon_data_downloader_minimal.py

# O por lotes si necesario
python data/polygon_data_downloader_minimal.py --limit 20
```

---

## 📊 Estructura de Datos para smallcaps-algorithm

### Query Principal (Sin Cambios)
```sql
-- Tu código existente en smallcaps-algorithm sigue funcionando igual
SELECT symbol, bar_timestamp, open_price, high_price, low_price, close_price, volume
FROM intraday_bars 
WHERE symbol = 'AAPL' AND DATE(bar_timestamp) = '2024-11-15';
```

### Nuevo: Datos con Event ID
```sql
-- Nuevo: Obtener datos intradiarios con event_id
SELECT symbol, bar_timestamp, open_price, high_price, low_price, close_price, volume, event_id
FROM intraday_bars 
WHERE symbol = 'AAPL' AND event_id IS NOT NULL;

-- Nuevo: Obtener 60 días de contexto histórico
SELECT symbol, history_date, days_before_event, close_price, catalyst_type
FROM daily_ohlcv_history 
WHERE symbol = 'AAPL'
ORDER BY days_before_event DESC;
```

### Ejemplo: Datos Completos para Análisis
```sql
-- Datos intradiarios del evento + contexto histórico
SELECT 
    ib.symbol,
    ib.bar_timestamp,
    ib.open_price, ib.high_price, ib.low_price, ib.close_price, ib.volume,
    ib.event_id,
    dh.history_date as historical_date,
    dh.days_before_event,
    dh.close_price as historical_close,
    dh.catalyst_type

FROM intraday_bars ib

-- Unir datos históricos
LEFT JOIN daily_ohlcv_history dh ON ib.event_id = dh.event_id

WHERE ib.symbol = 'AAPL' AND ib.event_id = 12345
ORDER BY ib.bar_timestamp ASC, dh.days_before_event DESC;
```

---

## 🎯 Beneficios del Enfoque Minimalista

### ✅ **Compatibilidad Total**
- Tu código en `/smallcaps-algorithm` **no necesita cambios**
- Queries existentes siguen funcionando exactamente igual
- Campo `event_id` es opcional para análisis existentes

### ✅ **Datos Adicionales Útiles**
- `event_id` permite vincular datos intradiarios con eventos específicos
- `daily_ohlcv_history` provee contexto histórico para rule extraction
- `catalyst_type` en datos históricos para análisis de patrones

### ✅ **Implementación Rápida**
- Solo 5 minutos para aplicar modificaciones
- Test inmediato con 1 evento
- Descarga completa en 2-10 horas dependiendo del volumen

---

## 🚀 Comandos de Ejecución

### Ejecución Rápida
```bash
# 1. Aplicar modificaciones mínimas
python scripts/init_market_database_minimal.py

# 2. Test con 1 evento
cd backtesting_system
python data/polygon_data_downloader_minimal.py --limit 1

# 3. Descarga completa si el test funciona
python data/polygon_data_downloader_minimal.py
```

### Ejecución por Lotes
```bash
# Descargar en lotes de 10
python data/polygon_data_downloader_minimal.py --limit 10
```

---

## 📈 Resultado Final

Después de la migración tendrás:

1. **market_data.db** con modificaciones mínimas aplicadas
2. **Campo `event_id`** en tabla `intraday_bars` para vincular datos con eventos
3. **Nueva tabla `daily_ohlcv_history`** con 60 días de contexto histórico
4. **Compatibilidad 100%** con tu código existente en `/smallcaps-algorithm`
5. **Datos en crudo** optimizados para análisis de rule extraction

**¡Listo para análisis con contexto histórico! 🚀**

---

## ✅ Checklist Final

- [ ] Backup de `market_data.db` creado
- [ ] Script `init_market_database_minimal.py` ejecutado exitosamente
- [ ] Campo `event_id` visible en tabla `intraday_bars`
- [ ] Tabla `daily_ohlcv_history` creada
- [ ] Test con 1 evento completado
- [ ] Verificación de integridad de datos
- [ ] Descarga masiva ejecutada
- [ ] Código de `/smallcaps-algorithm` funciona sin cambios