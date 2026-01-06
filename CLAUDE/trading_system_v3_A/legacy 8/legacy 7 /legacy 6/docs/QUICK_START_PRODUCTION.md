# 🚀 QUICK START - SISTEMA SMALLCAPS INTRADAY PRODUCTION

**Guía rápida para poner en producción el sistema híbrido**

---

## ⚡ SETUP EN 5 MINUTOS

### 1. Variables de Entorno (Solo 2 nuevas)
```bash
export IBKR_ACCOUNT=tu_cuenta_ibkr        # Nueva
export TIINGO_API_KEY=tu_api_key_tiingo   # Nueva

# Todo lo demás viene de config.ini existente
```

### 2. Verificación Rápida
```bash
# Test sistema híbrido (30 segundos)
python production/test_hybrid_integration.py
```

### 3. Deployment Automático
```bash
# Deploy completo (1 minuto)
python production/deploy_smallcap_production.py
```

### 4. Iniciar Trading
```bash
# Start sistema (inmediato)
python production/start_smallcap_production.py
```

---

## 📊 COMPONENTES INTEGRADOS

### ✅ Aprovecha TODO tu código existente:
- **config.ini** → Configuración principal (sin cambios)
- **IBKRAdapter** → Conexiones reales IBKR
- **SmallcapMayordomo** → Risk management
- **MLMultiStrategyEngine** → Selección de estrategias
- **SmallcapDailyScanner** → Scanner híbrido IBKR+Tiingo

### ➕ Agrega solo lo nuevo:
- **HybridConfigManager** → Sistema de configuración híbrida
- **AlertSystem** → Alertas Slack/Email/Console
- **RealTimeMonitor** → Monitoreo continuo
- **PerformanceOptimizer** → Optimización automática

---

## 🎯 CONFIGURACIÓN SMALLCAPS

### Desde config.ini [DAILY_PLAYS_STRATEGY]:
```ini
min_price = 1.0          # $1-$15 (smallcaps)
max_price = 15.0
min_gap_percent = 10.0   # 10% gap mínimo
min_volume = 500000      # 500K volumen mínimo
stop_loss_pct = 0.06     # 6% stop loss
take_profit_pct = 0.12   # 12% take profit
max_hold_time = 120      # 2 horas máximo
```

### Auto-agregado por sistema híbrido:
- Scanning intervals (30s mercado regular, 60s premarket)
- Tiingo fallback y rate limiting
- Alertas automáticas para plays excepcionales
- Monitoreo de performance en tiempo real

---

## 📱 MONITOREO RÁPIDO

### Status en 1 comando:
```bash
cat production/status.json
```

### Dashboard live:
```bash
python production/simple_monitor.py
```

### Logs importantes:
```bash
tail -f logs/smallcap_production.log     # Log principal
tail -f logs/smallcap_alerts.log         # Alertas
```

---

## 🚨 TROUBLESHOOTING RÁPIDO

| Error | Solución |
|-------|----------|
| `IBKR_ACCOUNT no configurada` | `export IBKR_ACCOUNT=DU123456789` |
| `TWS no conecta` | Verificar TWS/Gateway en puerto 7497 |
| `TIINGO_API_KEY falta` | Obtener en https://api.tiingo.com |
| `Config híbrida falló` | `python production/hybrid_config_manager.py` |

---

## ✅ VALIDACIÓN DE SISTEMA

### Tests automáticos:
```bash
# Configuración híbrida
python production/test_hybrid_integration.py

# Stress test
python production/system_stress_test.py  

# Performance
python production/performance_optimizer.py
```

### Estado esperado:
- ✅ Sistema híbrido funcionando
- ✅ 42 secciones leídas desde config.ini
- ✅ Extensiones de producción agregadas
- ✅ Zero duplicación de parámetros
- ✅ Performance score >80/100

---

## 🎯 READY FOR PRODUCTION

### Checklist final:
- [ ] config.ini preservado al 100%
- [ ] Solo 2 variables de entorno nuevas
- [ ] Tests de integración ✅
- [ ] Sistema híbrido validado ✅
- [ ] Monitor en tiempo real activo ✅

### Para trading:
1. **Premarket**: Sistema escanea cada 60s
2. **Market hours**: Sistema escanea cada 30s  
3. **Plays encontrados**: Alertas automáticas
4. **Risk management**: SmallcapMayordomo activo
5. **ML decisions**: Strategy selection automática

---

**🚀 ¡Listo para trading smallcaps intraday en producción!**

*Sistema optimizado para smallcaps $1-$15, gaps >10%, volumen >500K*