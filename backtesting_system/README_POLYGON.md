# Integración de Polygon.io para Backtesting Completo

## 📋 Descripción

Sistema optimizado para descargar datos históricos de **Polygon.io** SOLO para los días específicos en que tu scanner detectó oportunidades de trading. Usa una base de datos separada (`market_data.db`) para mantener organizados los datos de mercado.

### ¿Por qué este enfoque?

**Problema anterior**:
- Descargabas 30 días de datos para cada símbolo, aunque solo tradeaste 1 día
- Desperdiciabas API calls y tiempo
- Mezcla bas datos de mercado con datos operacionales

**Solución actual**:
- ✅ Descarga **solo los días** que el scanner detectó oportunidades
- ✅ Base de datos separada (`market_data.db` vs `trading_data.db`)
- ✅ Eficiente: 1 llamada API por oportunidad real
- ✅ Datos completos de pre/post market (4:00 AM - 8:00 PM)

---

## 🏗️ Arquitectura

### **Dos Bases de Datos Separadas**

```
trading_system_v3/
├── trading_data.db          # Datos operacionales
│   ├── trades               # Trades ejecutados por el scanner
│   ├── strategy_outcomes    # Resultados de estrategias
│   └── ...                  # Otras tablas operacionales
│
└── market_data.db           # Datos históricos de mercado
    └── intraday_bars        # Barras de 1min de Polygon (SOLO días de oportunidades)
```

### **Flujo de Datos**

1. **Scanner detecta oportunidad** → Guarda en `trading_data.db::trades`
2. **Descarga de Polygon** → Lee oportunidades de `trading_data.db`, descarga datos a `market_data.db`
3. **Backtesting** → Lee barras de `market_data.db` (o fallback a `trading_data.db`)

---

## 🚀 Instalación

### 1. Instalar SDK de Polygon

```bash
pip install polygon-api-client
```

### 2. Obtener API Key

1. Registrate gratis en [polygon.io](https://polygon.io/)
2. Obtén tu API key desde el dashboard
3. Configura la variable de entorno:

```bash
export POLYGON_API_KEY='tu_api_key_aqui'
```

O agrega a tu `.bashrc` / `.zshrc`:

```bash
echo 'export POLYGON_API_KEY="tu_api_key_aqui"' >> ~/.zshrc
source ~/.zshrc
```

---

## 📥 Uso

### **Modo Principal: Scanner Opportunities (RECOMENDADO)**

Descarga datos **solo para los días** en que el scanner detectó oportunidades:

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/backtesting_system

# Descargar últimas 10 oportunidades (DEFAULT)
python download_historical_data.py

# Descargar TODAS las oportunidades detectadas
python download_historical_data.py --all

# Limitar a 50 oportunidades
python download_historical_data.py --limit 50
```

**Output esperado**:
```
🚀 POLYGON HISTORICAL DATA DOWNLOADER
============================================================
📦 Base de datos: market_data.db (separada de trading_data.db)

🎯 MODO: Scanner Opportunities
   Descargará datos SOLO para días específicos detectados por el scanner

📊 Oportunidades disponibles: 225
   Limitado a: 10 (usa --all para descargar todas)

📋 Preview de oportunidades (primeras 5):
   1. ACHV - 2025-10-17 (daily_plays, 1 señales)
   2. ARTV - 2025-10-17 (daily_plays, 2 señales)
   3. CREV - 2025-10-17 (daily_plays, 2 señales)
   4. HIVE - 2025-10-17 (vwap_breakout, 1 señales)
   5. IONZ - 2025-10-17 (daily_plays, 1 señales)
   ... y 5 más

⏱️  Estimado:
   - Oportunidades a descargar: 10
   - Llamadas API: ~10
   - Tiempo estimado: ~2.0 minutos

¿Continuar con la descarga? (y/N):
```

### **Modo Legacy: Range Download**

Para casos especiales donde necesitas un rango de fechas completo:

```bash
# Descargar símbolo específico con rango de fechas
python download_historical_data.py \
    --mode range \
    --symbols AAPL,TSLA \
    --start 2024-01-01 \
    --end 2024-12-31
```

---

## 🧪 Verificar Datos Descargados

### Ver oportunidades disponibles en trading_data.db

```bash
sqlite3 /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db

-- Ver oportunidades únicas detectadas por el scanner
SELECT
    symbol,
    DATE(entry_time) as scan_date,
    strategy,
    COUNT(*) as signals_count
FROM trades
GROUP BY symbol, DATE(entry_time), strategy
ORDER BY scan_date DESC
LIMIT 10;
```

### Ver datos descargados en market_data.db

```bash
sqlite3 /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/market_data.db

-- Ver símbolos con datos descargados
SELECT
    symbol,
    DATE(MIN(bar_timestamp)) as first_date,
    DATE(MAX(bar_timestamp)) as last_date,
    COUNT(*) as total_bars
FROM intraday_bars
GROUP BY symbol
ORDER BY total_bars DESC;

-- Ver barras de un símbolo específico
SELECT * FROM intraday_bars
WHERE symbol = 'ACHV'
AND DATE(bar_timestamp) = '2025-10-17'
LIMIT 10;
```

---

## 🎯 Backtesting con los Nuevos Datos

El sistema usa automáticamente `market_data.db`:

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/backtesting_system

# El backtesting ahora usa datos de Polygon automáticamente
python run_backtest.py
```

El data feed tiene prioridad:
1. **market_data.db** (datos de Polygon) ✅
2. **trading_data.db** (fallback si no hay datos de Polygon)

---

## 📊 Comparación

| Aspecto | Modo Antiguo | Modo Nuevo |
|---------|--------------|------------|
| **Descarga** | 30 días × todos los símbolos | Solo días con oportunidades |
| **API Calls** | ~210 (10 símbolos × 21 días) | ~10 (solo 10 oportunidades) |
| **Tiempo** | ~42 minutos | ~2 minutos |
| **Almacenamiento** | Todo mezclado en trading_data.db | Separado en market_data.db |
| **Eficiencia** | ❌ Bajo | ✅ Alto |

---

## ⚙️ Rate Limiting

### Tier Gratuito de Polygon
- **5 llamadas/minuto**
- El downloader maneja esto automáticamente
- Progreso guardado en `polygon_download_log.json`

### Ejemplo de Cálculo

```
Oportunidades: 225
Tier gratuito: 5 calls/min
Tiempo estimado: 225 / 5 = 45 minutos
```

---

## 🔄 Reanudar Descargas

El sistema guarda progreso en `polygon_download_log.json`:

```bash
# Si se interrumpe, simplemente vuelve a ejecutar
python download_historical_data.py

# Solo descargará datos faltantes
```

Para forzar re-descarga:

```bash
rm polygon_download_log.json
python download_historical_data.py
```

---

## 📈 Ejemplo Completo

```bash
# 1. Configura API key (una sola vez)
export POLYGON_API_KEY='tu_api_key'

# 2. Descarga datos de oportunidades
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/backtesting_system
python download_historical_data.py --all

# 3. Verifica datos
sqlite3 ../market_data.db "SELECT symbol, COUNT(*) FROM intraday_bars GROUP BY symbol;"

# 4. Ejecuta backtest
python run_backtest.py
```

---

## 🐛 Troubleshooting

### "No se encontraron oportunidades"

**Causa**: La tabla `trades` está vacía.

**Solución**: Ejecuta el sistema de trading para generar oportunidades primero.

### "API key no configurada"

```bash
export POLYGON_API_KEY='tu_api_key'
# O usa --api-key en la línea de comandos
```

### "Rate limit exceeded"

El script ya maneja esto automáticamente. Si ves este error:
- Verifica que no tengas múltiples instancias corriendo
- Espera 60 segundos y vuelve a ejecutar

### "No data found for symbol"

Polygon no tiene datos para todos los símbolos. Verifica:
- El símbolo existe y está correctamente escrito
- El símbolo cotizó en las fechas solicitadas
- No es un símbolo muy pequeño/ilíquido

---

## 📚 Recursos

- [Polygon.io Docs](https://polygon.io/docs/stocks)
- [Python SDK](https://github.com/polygon-io/client-python)
- [API Reference](https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__range__multiplier___timespan___from___to)

---

## 🎉 Ventajas del Nuevo Sistema

1. **Eficiencia**: Solo descarga datos que realmente necesitas
2. **Organización**: Base de datos separada para datos de mercado
3. **Rapidez**: 20x más rápido que descargar rangos completos
4. **Escalabilidad**: Fácil agregar más datos sin afectar `trading_data.db`
5. **Flexibilidad**: Fallback automático a datos de IBKR si no hay datos de Polygon
