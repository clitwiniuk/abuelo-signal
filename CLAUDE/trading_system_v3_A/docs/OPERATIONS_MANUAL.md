# 📋 MANUAL DE OPERACIONES - SISTEMA SMALLCAPS INTRADAY

**Sistema de Trading Híbrido - Aprovecha config.ini + Extensiones de Producción**

---

## 🎯 RESUMEN EJECUTIVO

Este sistema de trading automatizado está optimizado para **smallcaps intraday** usando un enfoque híbrido que:
- ✅ **Aprovecha tu `config.ini` existente al 100%** - Sin duplicar configuración
- ✅ **Solo agrega extensiones necesarias** para producción (Tiingo, alertas, monitoreo)
- ✅ **Integra todos los componentes existentes** (IBKRAdapter, SmallcapMayordomo, ML Engine)
- ✅ **Elimina dependencia de ProRealTime** - Sistema completamente autónomo

---

## 🚀 INICIO RÁPIDO

### 1. Configuración Mínima Requerida

**Variables de entorno (solo 2 nuevas):**
```bash
# Variables que NO están en config.ini
export IBKR_ACCOUNT=tu_cuenta_ibkr
export TIINGO_API_KEY=tu_api_key_tiingo

# Opcional - para alertas
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...
export EMAIL_TO=trader@tuempresa.com
```

**Todo lo demás se lee desde tu `config.ini` existente:**
- IBKR conexión (host, port, client_id)
- Parámetros de trading (capital, límites, horarios)
- Configuración smallcaps (min_price, max_price, gaps, volumen)
- Estrategias y risk management

### 2. Deployment en 3 Pasos

```bash
# 1. Validar sistema híbrido
python production/test_hybrid_integration.py

# 2. Deployment completo
python production/deploy_smallcap_production.py

# 3. Iniciar sistema
python production/start_smallcap_production.py
```

---

## 📊 COMPONENTES DEL SISTEMA

### Sistema Híbrido de Configuración
- **`HybridConfigManager`** - Lee config.ini + extensiones
- **`config.ini`** - Tu configuración existente (fuente principal)
- **Extensiones de producción** - Solo parámetros nuevos (Tiingo, alertas, intervalos)

### Componentes Core (Aprovechados)
- **`adapters/ibkr_adapter.py`** - Conexiones reales a Interactive Brokers
- **`core/risk_manager.py`** - SmallcapMayordomo para gestión de posiciones
- **`strategies/multi_strategy_engine_ml.py`** - Selección de estrategias con ML
- **`scanner/smallcap/smallcap_daily_scanner.py`** - Scanner híbrido IBKR + Tiingo
- **`scanner/hybrid_scanner.py`** - Fallback entre fuentes de datos

### Nuevos Componentes de Producción
- **`production/smallcap_production_runner.py`** - Orquestador principal
- **`production/alert_system.py`** - Alertas multi-canal (Slack, Email, File, Console)
- **`production/real_time_monitor.py`** - Monitoreo continuo del sistema
- **`production/performance_optimizer.py`** - Optimización de latencia y memoria

---

## ⚙️ CONFIGURACIÓN DETALLADA

### config.ini - Secciones Utilizadas

**`[IBKR]` - Conexión a Interactive Brokers**
```ini
host = 127.0.0.1
port = 7497                # 7497=real, 7496=paper
client_id = 4148
# IBKR_ACCOUNT se lee desde variable de entorno
```

**`[TRADING]` - Parámetros Generales**
```ini
portfolio_capital = 2000.0
max_positions = 10
strategy = ml_multi_strategy
active_profile = PRODUCTION
```

**`[GLOBAL]` - Límites y Horarios**
```ini
daily_loss_limit = 100.0
max_daily_trades = 5
market_open_hour = 9.5
market_close_hour = 16.0
no_entry_after = 14.0
```

**`[DAILY_PLAYS_STRATEGY]` - Configuración Smallcaps**
```ini
min_price = 1.0                    # Rango de precios smallcaps
max_price = 15.0
min_volume = 500000                # Volumen mínimo
min_gap_percent = 10.0             # Gap mínimo para alertas
stop_loss_pct = 0.06               # 6% stop loss
take_profit_pct = 0.12             # 12% take profit
max_hold_time = 120                # Máximo 2 horas
```

---

## 🔄 PROCEDIMIENTOS OPERATIVOS

### Startup Diario

1. **Verificar Prerequisites**
   ```bash
   # Verificar TWS/Gateway activo
   netstat -an | grep 7497
   
   # Verificar variables de entorno
   echo $IBKR_ACCOUNT
   echo $TIINGO_API_KEY
   ```

2. **Ejecutar Tests Pre-Trading**
   ```bash
   # Test configuración híbrida
   python production/test_hybrid_integration.py
   
   # Test de stress (opcional)
   python production/system_stress_test.py
   
   # Benchmark de performance (opcional)
   python production/performance_optimizer.py
   ```

3. **Iniciar Sistema**
   ```bash
   # Opción 1: Startup script generado
   python production/start_smallcap_production.py
   
   # Opción 2: Runner directo
   python production/smallcap_production_runner.py
   ```

### Monitoreo Durante Operación

**Dashboard en Tiempo Real**
```bash
# Monitor completo
python production/real_time_monitor.py

# Monitor simple
python production/simple_monitor.py
```

**Archivos de Status**
- `production/status.json` - Estado actual del sistema
- `production/dashboard_data.json` - Datos para dashboard
- `logs/real_time_metrics.jsonl` - Historial de métricas

**Logs Importantes**
- `logs/smallcap_production.log` - Log principal del sistema
- `logs/smallcap_alerts.log` - Historial de alertas
- `logs/simple_metrics.jsonl` - Métricas simplificadas

---

## 🚨 TROUBLESHOOTING

### Problemas Comunes

**"IBKR_ACCOUNT no configurada"**
```bash
# Verificar variable de entorno
echo $IBKR_ACCOUNT
# Configurar si falta
export IBKR_ACCOUNT=DU123456789
```

**"Error conectando a IBKR"**
```bash
# Verificar TWS/Gateway activo
netstat -an | grep 7497
# Verificar puerto en config.ini [IBKR] port=7497
```

**"TIINGO_API_KEY no configurada"**
```bash
# Obtener API key en https://api.tiingo.com
export TIINGO_API_KEY=tu_api_key_aqui
```

**"HybridConfigManager falló"**
```bash
# Verificar config.ini existe y es válido
python production/hybrid_config_manager.py
```

### Comandos de Diagnóstico Rápido
```bash
# Status del sistema
cat production/status.json | jq '.system_health'

# Últimas 10 líneas del log
tail -10 logs/smallcap_production.log

# Test configuración
python production/test_hybrid_integration.py

# Performance check
python production/performance_optimizer.py
```

---

## 📈 OPTIMIZACIÓN Y TUNING

### Configuración Smallcaps en config.ini
```ini
# En [DAILY_PLAYS_STRATEGY]
min_price = 1.0                    # Ajustar según mercado
max_price = 15.0                   # Límite superior smallcaps
min_gap_percent = 10.0             # Sensibilidad a gaps
min_volume = 500000                # Liquidez mínima
volume_multiplier = 2.0            # Spike de volumen requerido
```

### Risk Parameters
```ini
# En [GLOBAL] 
daily_loss_limit = 100.0           # Límite pérdida diaria
max_daily_trades = 5               # Límite trades por día
risk_per_trade = 0.015             # 1.5% riesgo por trade
```

---

## 📋 CHECKLIST DE DEPLOYMENT

### Pre-Deployment
- [ ] Variables de entorno configuradas (IBKR_ACCOUNT, TIINGO_API_KEY)
- [ ] TWS/Gateway activo y configurado
- [ ] config.ini validado con HybridConfigManager
- [ ] Tests de integración pasados

### Deployment
- [ ] `python production/deploy_smallcap_production.py` ejecutado exitosamente
- [ ] Archivos de configuración generados
- [ ] Scripts de startup creados

### Post-Deployment
- [ ] Sistema iniciado con `start_smallcap_production.py`
- [ ] Monitoreo en tiempo real activo
- [ ] Métricas de performance dentro de thresholds

---

**📈 ¡Sistema listo para trading smallcaps intraday en producción!**