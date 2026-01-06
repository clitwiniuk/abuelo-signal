# A/B Testing Setup - Trading System Comparison

## Objetivo

Comparar el rendimiento entre el sistema **ESTABLE** (v3_A) y el sistema **EXPERIMENTAL** (v3) para evaluar mejoras antes de implementarlas en producción.

## Configuración de Sistemas

### Sistema A - ESTABLE (`trading_system_v3_A`)

**Propósito**: Sistema de referencia estable basado en commit `e7c688296ac1a7a55bc0b33b2efe62e9a2abbe61`

**Configuración**:
- 📁 **Directorio**: `/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A`
- 💾 **Base de datos**: `trading_data.db` (nueva, vacía)
- 🔌 **Puerto IBKR**: `7497` (Paper Trading)
- 🆔 **Client ID**: `6000`
- 📊 **TradeTally**: HABILITADO (`http://localhost:8001/api/v2`)
- 🎯 **Modo**: Paper Trading (envía órdenes reales al paper account)
- 📋 **Workers**: Versión estable del commit e7c6882
- ❌ **No incluye**: Backtesting system, TradeTally DB local

### Sistema v3 - EXPERIMENTAL (`trading_system_v3`)

**Propósito**: Sistema de desarrollo con mejoras y experimentos

**Configuración**:
- 📁 **Directorio**: `/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3`
- 💾 **Base de datos**: `trading_data.db` (existente, con historial)
- 🔌 **Puerto IBKR**: `7497` (Paper Trading - mismo puerto, diferentes client_id)
- 🆔 **Client ID**: `6001` (diferente para evitar conflictos)
- 📊 **TradeTally**: HABILITADO (`http://localhost:8001/api/v2`)
- 🎯 **Modo**: Paper Trading (envía órdenes reales al paper account)
- 📋 **Workers**: Versión experimental con mejoras recientes
- ✅ **Incluye**:
  - Sistema de backtesting profesional
  - Mejoras en workers (momentum runner, daily plays optimizations)
  - ODS removido para logs más limpios

## Diferencias Clave

| Aspecto | Sistema A (Estable) | Sistema v3 (Experimental) |
|---------|---------------------|---------------------------|
| Workers | Versión commit e7c6882 | Versión con mejoras recientes |
| ODS | Habilitado (puede reducir confianza) | Deshabilitado (logs limpios) |
| Momentum Runner | No implementado | Implementado en daily_plays |
| Client ID | 6000 | 6001 |
| Base de datos | Nueva (vacía) | Existente (con historial) |

## Cómo Ejecutar Ambos Sistemas en Paralelo

### 1. Iniciar TWS Paper Trading

```bash
# Asegúrate de tener TWS corriendo en puerto 7497
# TWS -> File -> Global Configuration -> API -> Settings
# Enable ActiveX and Socket Clients ✓
# Socket port: 7497
# Trusted IP addresses: 127.0.0.1
```

### 2. Iniciar Sistema A (Estable)

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A

# Activar entorno virtual (si existe)
source venv/bin/activate

# Iniciar sistema
python trader_main.py

# O en background
nohup python trader_main.py > trader_A.out 2>&1 &
```

### 3. Iniciar Sistema v3 (Experimental)

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3

# Activar entorno virtual (si existe)
source venv/bin/activate

# Iniciar sistema
python trader_main.py

# O en background
nohup python trader_main.py > trader_v3.out 2>&1 &
```

## Verificación de Estado

### Verificar que ambos sistemas están corriendo

```bash
# Sistema A
ps aux | grep -i "trading_system_v3_A.*trader_main"

# Sistema v3
ps aux | grep -i "trading_system_v3.*trader_main"

# Ver logs en tiempo real
tail -f /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A/logs/trader.log
tail -f /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/logs/trader.log
```

### Verificar conexiones IBKR

```bash
# Verificar que ambos sistemas tengan diferentes client_id
grep "client_id" trading_system_v3_A/config.ini  # Debe ser 6000
grep "client_id" trading_system_v3/config.ini     # Debe ser 6001
```

## Comparación de Resultados

### Métricas a Comparar

1. **Número de trades ejecutados**
2. **Win rate**
3. **Profit factor**
4. **Average P&L por trade**
5. **Drawdown máximo**
6. **Sharpe ratio**
7. **Trades filtrados vs aceptados**

### Scripts de Comparación

#### 1. Comparar Trades del Día

```bash
# Sistema A
sqlite3 /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A/trading_data.db \
"SELECT COUNT(*), AVG(pnl), SUM(pnl) FROM trades WHERE date(entry_time) = date('now');"

# Sistema v3
sqlite3 /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db \
"SELECT COUNT(*), AVG(pnl), SUM(pnl) FROM trades WHERE date(entry_time) = date('now');"
```

#### 2. Comparar Win Rate

```bash
# Sistema A
sqlite3 /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A/trading_data.db \
"SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate
FROM trades
WHERE status = 'CLOSED' AND date(entry_time) >= date('now', '-7 days');"

# Sistema v3
sqlite3 /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db \
"SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate
FROM trades
WHERE status = 'CLOSED' AND date(entry_time) >= date('now', '-7 days');"
```

#### 3. Comparar por Worker/Strategy

```bash
# Sistema A
sqlite3 /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A/trading_data.db \
"SELECT
    strategy,
    COUNT(*) as trades,
    ROUND(AVG(pnl), 2) as avg_pnl,
    ROUND(SUM(pnl), 2) as total_pnl
FROM trades
WHERE status = 'CLOSED' AND date(entry_time) >= date('now', '-7 days')
GROUP BY strategy;"

# Sistema v3
sqlite3 /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db \
"SELECT
    strategy,
    COUNT(*) as trades,
    ROUND(AVG(pnl), 2) as avg_pnl,
    ROUND(SUM(pnl), 2) as total_pnl
FROM trades
WHERE status = 'CLOSED' AND date(entry_time) >= date('now', '-7 days')
GROUP BY strategy;"
```

## Integración Futura con TradeTally

Ambos sistemas están configurados para usar TradeTally. Para comparar visualmente:

1. **Opción 1**: Usar tags/categorías en TradeTally para diferenciar:
   - Sistema A: tag `stable`
   - Sistema v3: tag `experimental`

2. **Opción 2**: Crear dos cuentas en TradeTally:
   - Cuenta 1: "Paper Trading - Stable"
   - Cuenta 2: "Paper Trading - Experimental"

3. **Opción 3**: Usar un dashboard personalizado que compare ambas bases de datos

## Precauciones

⚠️ **IMPORTANTE**:

1. **Diferentes Client IDs**: Ambos sistemas usan client_id diferentes (6000 vs 6001) para evitar conflictos en TWS
2. **Bases de datos separadas**: Cada sistema escribe en su propia BD
3. **Monitoreo de recursos**: Dos sistemas corriendo consumen más CPU/memoria
4. **Logs separados**: Cada sistema tiene su propio directorio `logs/`
5. **Sin interferencia**: Los sistemas NO se comunican entre sí

## Troubleshooting

### Error: "Socket port has been reset"
- TWS solo permite cierto número de conexiones simultáneas
- Solución: Reiniciar TWS o verificar configuración de API en TWS

### Error: "Already connected with client_id X"
- Un sistema está intentando usar el mismo client_id
- Solución: Verificar que config.ini tenga client_id diferentes

### Error: "Database is locked"
- No debería ocurrir ya que cada sistema usa su propia BD
- Solución: Verificar que no haya procesos duplicados corriendo

### Logs no actualizándose
- Verificar que el proceso está corriendo: `ps aux | grep trader_main`
- Verificar permisos en directorio `logs/`

## Cronograma Sugerido

### Fase 1: Setup y Validación (Día 1)
- [x] Configurar ambos sistemas
- [ ] Iniciar ambos sistemas
- [ ] Verificar que no hay conflictos
- [ ] Verificar que ambos conectan a IBKR correctamente
- [ ] Verificar que ambos guardan trades en BD separadas

### Fase 2: Ejecución Paralela (Días 2-7)
- [ ] Dejar ambos sistemas corriendo durante 1 semana
- [ ] Monitorear logs diariamente
- [ ] Registrar cualquier problema o discrepancia

### Fase 3: Análisis (Día 8)
- [ ] Extraer métricas de ambas BD
- [ ] Comparar win rate, profit factor, drawdown
- [ ] Identificar qué sistema tuvo mejor performance
- [ ] Analizar trades específicos donde hubo diferencias

### Fase 4: Decisión (Día 9)
- [ ] Si v3 supera a v3_A: Promover cambios a producción
- [ ] Si v3_A es mejor: Revertir cambios en v3 y analizar por qué

## Notas

- Este setup permite testing A/B real sin riesgo de capital real (paper trading)
- Ambos sistemas ven las mismas oportunidades de mercado
- Las diferencias en resultados serán atribuibles a los cambios en el código
- TradeTally permitirá comparación visual en el futuro

---

**Última actualización**: 2025-12-02
**Versión Estable**: Commit `e7c688296ac1a7a55bc0b33b2efe62e9a2abbe61`
**Versión Experimental**: Latest (rama actual)
