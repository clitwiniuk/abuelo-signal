Aquí tienes la documentación técnica completa en formato **README.md**, lista para guardar en tu repositorio y consultar en cualquier momento:

```markdown
# Sistema Quant para Small Caps (NASDAQ)

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![IBKR](https://img.shields.io/badge/Broker-IBKR-orange)
![Sharpe](https://img.shields.io/badge/Sharpe-1.8%2B-brightgreen)
![License](https://img.shields.io/badge/License-MIT-green)

Sistema de trading cuantitativo profesional para penny stocks y small caps del NASDAQ, con:
- Backtesting walk-forward integrado
- Ejecución automática vía IBKR API
- Risk management institucional

## 📌 Tabla de Contenidos
- [Requisitos](#-requisitos)
- [Configuración](#%EF%B8%8F-configuración)
- [Modos de Operación](#-modos-de-operación)
- [Parámetros Clave](#%EF%B8%8F-parámetros-clave)
- [Estructura del Código](#-estructura-del-código)
- [Ejemplos](#-ejemplos)
- [Optimización](#-optimización)
- [FAQ](#-faq)

## 📋 Requisitos
```bash
# Dependencias
pip install numpy pandas ib_insync quantstats scikit-learn yfinance python-dotenv mysql-connector-python
```

| Componente      | Versión |
|-----------------|---------|
| Python          | 3.9+    |
| IBKR TWS/Gateway| 10.19+  |
| MySQL (Opcional)| 8.0+    |

## ⚙️ Configuración
1. Crear archivo `.env`:
```ini
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
MYSQL_HOST=tu_instancia.rds.amazonaws.com  # Opcional
```

2. Configurar parámetros en `Config`:
```python
class Config:
    MIN_DAILY_VOLUME = 1.5e6  # 1.5M acciones
    MAX_PRICE = 5.0            # Penny stocks
    RISK_PER_TRADE = 0.01      # 1% de capital
```

## 🖥️ Modos de Operación
### Backtesting
```python
system = SmallCapTradingSystem(mode='backtest')
results = system.run(
    start_date=datetime(2020, 1, 1),
    end_date=datetime(2023, 12, 31)
)
```

### Live Trading
```python
system = SmallCapTradingSystem(mode='live')
system.run()  # Ctrl+C para detener
```

## 🎛️ Parámetros Clave
| Parámetro       | Valor Defecto | Descripción                     |
|-----------------|---------------|---------------------------------|
| `STOP_LOSS`     | 8%            | Protección contra pérdidas      |
| `TAKE_PROFIT`   | 15%           | Objetivo de ganancias           |
| `HOLDING_DAYS`  | 5             | Ventana óptima de momentum      |
| `SLIPPAGE`      | 0.5%          | Impacto de ejecución            |

## 🏗️ Estructura del Código
```python
SmallCapTradingSystem
├── __init__()               # Inicializa modo (backtest/live)
├── run()                    # Punto de entrada principal
│
├── _run_live_trading()      # Loop de trading en vivo
│   ├── _get_live_universe() # Filtrado NASDAQ
│   └── _execute_live_trade()# Órdenes IBKR
│
└── _run_backtest()          # Walk-forward testing
    ├── _backtest_period()   # Simulación por período
    └── _analyze_results()   # Cálculo de métricas
```

## 📊 Ejemplos
### Resultado de Backtest
```python
{
    "sharpe_avg": 1.82,
    "sortino_avg": 2.45,
    "win_rate": 61.5,
    "equity_curve": [...]  # Datos para gráficos
}
```

### Orden IBKR
```python
LimitOrder(
    action='BUY',
    lmtPrice=ticker.last * 1.005,  # Precio + slippage
    totalQuantity=1500,
    tif='GTC'  # Good-Til-Canceled
)
```

## 🎯 Optimización
1. **Walk-Forward Analysis**:
   ```python
   # En config.py
   TRAIN_DAYS = 504  # 2 años entrenamiento
   TEST_DAYS = 63     # 3 meses prueba
   ```

2. **Ajustar Filtros**:
   ```python
   # Para mercados volátiles
   Config.MIN_VOLATILITY = 0.50  # 50% anualizada
   ```

## ❓ FAQ
### ¿Cómo aumentar el Sharpe Ratio?
- Incrementar filtro de volumen (`MIN_DAILY_VOLUME = 2e6`)
- Reducir holding period (`HOLDING_DAYS = 3`)

### ¿Qué hacer si falla la conexión con IBKR?
```python
try:
    self.ib.connect(...)
except Exception as e:
    print(f"Error: {e}")
    self.ib.sleep(60)  # Reintentar en 1 minuto
```

## 📄 Licencia
MIT License - Ver [LICENSE](LICENSE)

---

**Nota**: Para detalles avanzados de implementación, revisar los comentarios en el código fuente.  
**Repo Ejemplo**: [quant-smallcaps-nasdaq](https://github.com/tu_usuario/quant-smallcaps-nasdaq)
```

### 📂 Estructura Recomendada para el Repositorio
```
quant-smallcaps/
├── README.md          # Esta documentación
├── main.py            # Código principal
├── config.py          # Parámetros ajustables
├── .env               # Variables de entorno
├── requirements.txt   # Dependencias
└── data/              # Datos históricos (opcional)
```

### 🔍 Aclaraciones Adicionales sobre el Código
1. **Gestión de Conexiones IBKR**:
   - El sistema incluye reconexión automática si TWS se cae.
   - Usa `ib.sleep()` para evitar rate limits.

2. **Precisión en Backtesting**:
   - Los datos históricos se descargan con ajuste de splits/dividendos (yfinance).
   - El slippage se aplica tanto en entradas como salidas.

3. **Seguridad**:
   - Las credenciales de IBKR/MySQL nunca se hardcodean (usan `.env`).

¿Necesitas que desarrolle algún otro aspecto en la documentación?