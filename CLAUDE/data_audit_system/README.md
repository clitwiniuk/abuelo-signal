# Data Audit System — auditoría de datos intradía 1-min para small caps

Responde a la pregunta: **¿es este dataset apto para validar o refutar una
hipótesis de trading?** No solo detecta huecos: cataloga sesgos (look-ahead,
survivorship, deriva del scanner) y marca qué porciones de los datos son
fiables y cuáles no.

Diseñado para ejecutarse tras cada descarga nueva; cada ejecución queda
registrada en `audit_history.jsonl` (historial de validaciones) y
`metadata_history.jsonl` (qué datos existían en cada momento).

## Uso

```bash
# Demo autocontenida (datos sintéticos con errores sembrados):
python3 run_audit.py --demo

# Uso real:
python3 run_audit.py <carpeta_datos> <carpeta_salida> \
    --contract contract.yaml \
    --scanner-log scanner_log.jsonl \
    --reference tickers_historicos.csv \
    --source IBKR --format parquet
```

Desde Python:

```python
from data_audit import run_data_audit, audit_trade

results = run_data_audit("data/", "audit_output/",
                         scanner_log="scanner_log.jsonl",
                         reference_tickers_csv="universe_ref.csv",
                         strategy_fn=mi_estrategia,   # replay temporal opcional
                         source_name="IBKR")

# Auditar una operación simulada (¿estaban los datos disponibles y limpios?):
verdict = audit_trade({"ticker": "ABCD", "decision_time": "2026-06-23T15:00:00Z"},
                      results["df"], results["violations"])
```

## Formatos de entrada

- **Velas**: CSV/Parquet con columnas `ticker|symbol`,
  `timestamp|dt|datetime|bar_timestamp`, `open,high,low,close,volume`,
  `downloaded_at`. Timestamps naive se asumen ET (convención legacy);
  aware se respetan. La fecha de sesión se deriva siempre del timestamp en ET.
- **Referencia de universo** (survivorship): CSV `ticker,list_date,delist_date`
  (delist_date vacío = activo).
- **Log del scanner**: JSON/JSONL de snapshots
  `{"fecha", "parametros", "lista_tickers_devueltos"}`.

## Salidas (en `output_folder`)

| Fichero | Contenido |
|---|---|
| `data_health_report.html` | Informe autocontenido: scores, timeline por día, tickers NO APTOS, violaciones |
| `violations.csv` | Todas las violaciones (ticker, date, check_type, severity, detail) |
| `clean_data.parquet` | Solo filas válidas (los originales nunca se tocan) |
| `annotated_data.parquet` | Dataset completo con columna `is_valid` |
| `scores_by_day.csv` / `scores_by_ticker_day.csv` | Score 0-100 |
| `meta_*.json` + `metadata_history.jsonl` | Trazabilidad: sha256, fuente, rango, scanner |
| `audit_history.jsonl` | Una línea por ejecución de auditoría |

## Checks implementados

**Integridad (M2)**: días de mercado faltantes (calendario NASDAQ real vía
`pandas_market_calendars`), cobertura de velas por día, volumen 0/negativo/NaN,
volumen diario mínimo, OHLC incoherente, precios 0/NaN, saltos de precio sin
volumen acorde, gaps overnight sospechosos de split no ajustado, velas
congeladas (halt/dato congelado), timestamps duplicados, universo mínimo por día.

**Sesgos (M3)**: look-ahead vía `downloaded_at` + test de replay temporal con
`PointInTimeView` (la estrategia solo ve datos hasta el cierre de D-1; accesos
futuros quedan registrados), survivorship (muertos ausentes, desapariciones sin
delisting, tickers huérfanos), scanner-changing bias (deriva de universo >30%
sin cambio de parámetros; cambios de parámetros parten el backtest en regímenes).

## Decisiones de diseño para small caps (difieren del estándar)

1. **Gap overnight >50% NO es error automático**: en un universo de top gainers
   los gaps enormes son el setup. Solo es CRITICAL si el volumen no lo confirma
   (patrón de split/reverse-split no ajustado).
2. **Velas faltantes ≠ error**: en 1-min, un minuto sin trades no genera vela.
   Cobertura baja es WARNING de liquidez, no CRITICAL de integridad.
3. **Saltos intradía >10% con volumen acorde no se marcan**: son los pumps que
   se quieren tradear; sin volumen sí (dato corrupto).

## Contrato

Umbrales en `data_audit/contract.py` (`DEFAULT_CONTRACT`), sobreescribibles
por YAML — ver `contract.example.yaml`. Score por ticker-día parte de 100 y
resta 25/10/2 por violación CRITICAL/WARNING/INFO; bajo 70 = NO APTO.
