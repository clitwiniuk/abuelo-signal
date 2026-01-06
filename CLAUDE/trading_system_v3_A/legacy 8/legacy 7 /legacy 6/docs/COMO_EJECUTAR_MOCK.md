# 🚀 Cómo Ejecutar el Sistema con Mock

## ✅ Estado Actual
Ya has descargado los datos y el sistema mock está funcionando correctamente. Aquí te explico las diferentes formas de ejecutarlo.

## 📋 Opciones Disponibles

### 1. 🎮 Test Básico del Mock (RECOMENDADO PARA EMPEZAR)
```bash
python simulation/simple_mock_test.py
```
**¿Qué hace?**
- ✅ Conecta al sistema mock
- ✅ Carga datos CSV existentes (PLTR, TSLA, etc.)
- ✅ Ejecuta una orden de compra simulada
- ✅ Muestra el P&L y posiciones

**Resultado esperado:**
```
🚀 TEST SIMPLE DEL SISTEMA MOCK
✅ Broker conectado: True
✅ Data provider conectado: True
📊 Símbolos disponibles: 36
🎯 TEST CON PLTR
   📈 Última barra: $152.03 (Vol: 268,531)
   💰 Precio actual: $152.25
   ✅ Orden colocada: [order-id]
   📊 Posición: 100 @ $152.29
   💰 Valor: $15,234.00
```

### 2. 🎮 Menú Interactivo de Simulación
```bash
python scripts/runners/run_simulation.py
```
**¿Qué incluye?**
- Test rápido con símbolos
- Test de estrategias específicas
- Backtest completo
- Estadísticas del broker
- Pruebas de órdenes manuales

### 3. 📊 Descargar Más Datos (Si los necesitas)
```bash
python scripts/tools/download_menu.py
```
Pero **ya tienes 36 símbolos descargados**, incluyendo:
- PLTR, TSLA, NVDA, AMD
- GME, AMC, BB, MVIS
- AAPL, COIN, SOFI, etc.

## 🔧 Componentes del Sistema Mock

### MockIBKRAdapter
- ✅ Simula Interactive Brokers completamente
- ✅ Ejecuta órdenes realistas con slippage
- ✅ Gestiona posiciones y balance
- ✅ Calcula P&L en tiempo real

### CSVDataProvider  
- ✅ Carga datos reales descargados de Polygon.io
- ✅ 36 símbolos con datos de minuto
- ✅ Cache optimizado para rendimiento
- ✅ Formatos estándar OHLCV

## 🎯 Ejemplo Práctico Paso a Paso

### 1. Ejecutar Test Básico
```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
python simulation/simple_mock_test.py
```

### 2. Ver el Output
```
📊 Símbolos disponibles: 36
🎯 TEST CON PLTR
   📈 Última barra: $152.03
   💰 Precio actual: $152.25
   ✅ Orden colocada
   📊 Posición: 100 @ $152.29
   💵 Balance: $-5,244.23  # Usaste $15,234 para comprar
   📈 Total Value: $9,989.77  # Valor total de portfolio
```

### 3. Entender los Resultados
- **Balance negativo**: Normal, usaste más cash del disponible (margin)
- **Total Value**: Valor total incluyendo posiciones
- **P&L**: Diferencia vs. los $10,000 iniciales

## 🛠️ Personalizar el Sistema

### Cambiar Símbolos de Prueba
En `simple_mock_test.py` línea 45:
```python
symbol = "TSLA"  # Cambiar por cualquier símbolo disponible
```

### Ajustar Parámetros de Trading
En `simple_mock_test.py` línea 60:
```python
quantity=50,  # Cambiar cantidad
```

### Modificar Balance Inicial
En `adapters/mock_ibkr_adapter.py`:
```python
self._account_balance = 25000.0  # Cambiar de $10k a $25k
```

## 📈 Estrategias Disponibles

El sistema incluye múltiples estrategias:
- **MACDVStrategy**: MACD + Volume
- **GapGoStrategy**: Gap trading
- **VolumeBreakoutStrategy**: Breakouts por volumen
- **ORBStrategy**: Opening Range Breakout
- **PMHBreakoutStrategy**: Premarket High breakout

## 🔍 Próximos Pasos

### Para Development:
1. ✅ Ejecuta `simple_mock_test.py` para verificar todo funciona
2. ✅ Modifica parámetros y prueba diferentes símbolos
3. ✅ Desarrolla tus propias estrategias usando el mock

### Para Backtesting:
1. Usa `run_simulation.py` opción 3 (Backtest completo)
2. Analiza múltiples símbolos simultáneamente
3. Compara diferentes períodos de tiempo

### Para Live Trading (Cuando estés listo):
1. Cambia `simulation_mode = False` en config
2. Conecta a TWS/Gateway real
3. Usa los mismos scripts pero con datos live

## 🚨 Importantes

### ✅ Ventajas del Mock
- **Cero riesgo**: No pierdes dinero real
- **Velocidad**: Test instantáneos 
- **Consistencia**: Mismos datos siempre
- **Debug fácil**: Control total del entorno

### ⚠️ Limitaciones
- **No real market conditions**: No gaps, no slippage extremo
- **Data histórica**: No refleja condiciones actuales
- **Simplified fills**: Ejecución perfecta vs. realidad

## 🎯 Comando Rápido para Empezar

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
python simulation/simple_mock_test.py
```

¡Y ya tienes el sistema funcionando con datos reales en simulación!