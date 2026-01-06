# Sistema de Datos OHLC para Backtest

## 📋 Descripción

Sistema automático para descargar y almacenar datos OHLC (Open, High, Low, Close, Volume) de 1 minuto para todos los símbolos operados durante el día. Estos datos son esenciales para:

- 📊 **Backtesting**: Reproducir condiciones exactas del mercado
- 📈 **Análisis post-trade**: Estudiar el comportamiento de precio después de entrada/salida
- 🔍 **Forward testing**: Validar estrategias con datos reales
- 📉 **Performance analysis**: Mejorar timing de entradas y salidas

## 🏗️ Arquitectura

### Descarga End-of-Day (EOD)

El sistema descarga datos **al final del día** (22:00 hora española = 16:00 ET) para mayor eficiencia:

```
22:00 España (16:00 ET - After Market Close)
       ↓
[download_eod_ohlc.py ejecuta]
       ↓
1. Lee símbolos operados hoy desde trading_data.db
2. Descarga barras de 1 minuto de IBKR (9:30 AM - 4:00 PM ET)
3. Guarda en trade_ohlc_snapshots + trade_intraday_bars
4. Genera reporte de éxito/fallos
```

### Estructura de Datos

**Tabla `trade_ohlc_snapshots`** - Resumen por trade:
- Datos OHLC del día completo
- Barras de entry/exit específicas
- JSON con todas las barras intraday
- Premarket high, gap %, etc.

**Tabla `trade_intraday_bars`** - Barras individuales:
- Cada barra de 1 minuto por separado
- Timestamp, OHLC, volume
- Marcadores: `is_entry_bar`, `is_exit_bar`
- Secuencia numerada para análisis temporal

## 🚀 Uso

### 1. Configuración Inicial

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3

# Programar descarga automática diaria
./scripts/maintenance/schedule_eod_download.sh
```

Esto crea un cron job que ejecuta el script automáticamente a las 22:00 cada día.

### 2. Ejecución Manual

Para descargar datos de un día específico (útil para backfill):

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
python3 scripts/maintenance/download_eod_ohlc.py
```

### 3. Verificar Datos

```python
import sqlite3

conn = sqlite3.connect('trading_data.db')

# Ver resumen de datos disponibles
query = """
SELECT
    COUNT(*) as total_trades,
    COUNT(DISTINCT symbol) as unique_symbols,
    MIN(date(entry_time)) as first_date,
    MAX(date(entry_time)) as last_date
FROM trade_ohlc_snapshots
"""
print(conn.execute(query).fetchone())

# Ver trades con datos OHLC
query = """
SELECT symbol, trading_date, day_open, day_high, day_low, day_close
FROM trade_ohlc_snapshots
ORDER BY trading_date DESC
LIMIT 10
"""
for row in conn.execute(query):
    print(row)
```

### 4. Extraer Datos para Backtest

```python
import sqlite3
import json

def get_trade_ohlc(trade_id: str):
    """Obtener todos los datos OHLC de un trade"""
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()

    # Get snapshot
    cursor.execute("""
        SELECT symbol, trading_date, intraday_bars, entry_time, exit_time
        FROM trade_ohlc_snapshots
        WHERE trade_id = ?
    """, (trade_id,))

    row = cursor.fetchone()
    if not row:
        return None

    symbol, date, bars_json, entry, exit = row
    bars = json.loads(bars_json)

    # Get individual bars
    cursor.execute("""
        SELECT bar_timestamp, open_price, high_price, low_price, close_price, volume
        FROM trade_intraday_bars
        WHERE trade_id = ?
        ORDER BY bar_sequence
    """, (trade_id,))

    detailed_bars = cursor.fetchall()

    return {
        'symbol': symbol,
        'date': date,
        'entry_time': entry,
        'exit_time': exit,
        'bars': bars,
        'detailed_bars': detailed_bars
    }

# Uso
data = get_trade_ohlc('YOUR_TRADE_ID')
if data:
    print(f"Symbol: {data['symbol']}")
    print(f"Total bars: {len(data['bars'])}")
```

## 📊 Estructura de Tablas

### `trade_ohlc_snapshots`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| trade_id | TEXT | ID único del trade |
| symbol | TEXT | Símbolo operado |
| trading_date | TEXT | Fecha de trading |
| day_open | REAL | Precio de apertura del día |
| day_high | REAL | Máximo del día |
| day_low | REAL | Mínimo del día |
| day_close | REAL | Cierre del día |
| day_volume | INTEGER | Volumen total del día |
| entry_time | TIMESTAMP | Hora de entrada al trade |
| entry_price | REAL | Precio de entrada |
| entry_bar | TEXT (JSON) | Barra OHLC de entrada |
| exit_time | TIMESTAMP | Hora de salida (nullable) |
| exit_price | REAL | Precio de salida (nullable) |
| exit_bar | TEXT (JSON) | Barra OHLC de salida (nullable) |
| premarket_high | REAL | Máximo premarket (nullable) |
| gap_percent | REAL | % de gap (nullable) |
| market_open_price | REAL | Precio al abrir mercado (nullable) |
| intraday_bars | TEXT (JSON) | Todas las barras del día |

### `trade_intraday_bars`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| trade_id | TEXT | ID del trade padre |
| bar_timestamp | TIMESTAMP | Timestamp de la barra |
| timeframe | TEXT | Temporalidad ('1min') |
| open_price | REAL | Precio de apertura |
| high_price | REAL | Precio máximo |
| low_price | REAL | Precio mínimo |
| close_price | REAL | Precio de cierre |
| volume | INTEGER | Volumen |
| bar_sequence | INTEGER | Secuencia numérica |
| is_entry_bar | BOOLEAN | Si es la barra de entrada |
| is_exit_bar | BOOLEAN | Si es la barra de salida |

## 🔧 Mantenimiento

### Ver logs de descarga

```bash
tail -f logs/ohlc_downloader.log
```

### Verificar cron job

```bash
crontab -l | grep download_eod_ohlc
```

### Eliminar cron job

```bash
crontab -l | grep -v 'download_eod_ohlc.py' | crontab -
```

### Backfill datos históricos

Si necesitas descargar datos de días anteriores:

```python
# TODO: Crear script de backfill
# Por ahora, el sistema solo descarga datos del día actual
```

## ⚠️ Limitaciones

1. **Solo datos del día actual**: El sistema descarga datos del día en que se ejecuta
2. **Requiere IBKR conectado**: Debe haber conexión a Interactive Brokers
3. **Market hours only**: Solo datos de 9:30 AM - 4:00 PM ET
4. **Rate limiting**: Delay de 1 segundo entre símbolos para evitar throttling
5. **No premarket/afterhours**: Solo regular trading hours

## 📝 Notas

- Los datos se descargan **después del cierre del mercado** para garantizar completitud
- Se usa client_id **9999** para no interferir con el trader activo
- Los datos se almacenan en SQLite para facilidad de acceso
- JSON se usa para almacenar barras completas (más flexible que columnas individuales)
- El sistema sobrescribe datos si ya existen (INSERT OR REPLACE)

## 🎯 Próximos Pasos

1. ✅ Sistema EOD funcionando
2. ⏳ Script de backfill para días anteriores
3. ⏳ Dashboard de visualización de datos OHLC
4. ⏳ Integración con sistema de backtest
5. ⏳ Exportar a CSV/Parquet para análisis en Python/R

## 🆘 Troubleshooting

**Problema**: No se descargan datos

```bash
# Verificar conexión IBKR
ps aux | grep "TWS\|IB Gateway"

# Verificar logs
tail -50 logs/ohlc_downloader.log

# Ejecutar manualmente para debug
python3 scripts/maintenance/download_eod_ohlc.py
```

**Problema**: Cron job no se ejecuta

```bash
# Verificar que el cron job existe
crontab -l

# Ver logs del sistema
tail -f /var/log/system.log | grep CRON

# Verificar permisos
ls -la scripts/maintenance/download_eod_ohlc.py
```

**Problema**: Faltan datos de algunos símbolos

- Verificar que IBKR tenga permisos de datos en tiempo real para esos símbolos
- Algunos símbolos pueden no tener datos históricos disponibles
- Revisar `logs/ohlc_downloader.log` para errores específicos
