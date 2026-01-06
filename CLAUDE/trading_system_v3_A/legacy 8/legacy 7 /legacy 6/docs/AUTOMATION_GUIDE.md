# Guía de Automatización del Sistema de Trading

## 🎯 Objetivo
Eliminar TODA intervención manual:
- ✅ Auto-login a TWS (sin contraseñas manuales)
- ✅ Auto-inicio a las 08:00 ET
- ✅ Auto-apagado a las 17:00 ET (after market close)
- ✅ Auto-detección de festivos/weekends
- ✅ Auto-reinicio si falla TWS o el trader
- ✅ Operación automática durante horario de mercado

---

## 📦 Paso 1: Instalar IBC (Solo UNA vez)

IBC (IBKR Controller) es el software que hace auto-login a TWS.

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3

# Ejecutar instalador
chmod +x scripts/automation/install_ibc.sh
./scripts/automation/install_ibc.sh
```

**Salida esperada:**
```
=================================================
IBC (IBKR Controller) Installation Script
=================================================

📥 Downloading IBC 3.18.0...
📂 Extracting IBC...
✅ IBC extracted to: /Users/carlos/ibc
🔧 Setting permissions...
📝 Creating IBC configuration...

✅ IBC Installation Complete!
```

---

## 🔐 Paso 2: Configurar Credenciales de IBKR (Solo UNA vez)

```bash
cd ~/ibc

# Copiar plantilla
cp config.ini.template config.ini

# Editar configuración
nano config.ini
```

**Editar estas líneas:**
```ini
# IBKR Credentials
IbLoginId=TU_USERNAME_IBKR      # ← Cambia esto
IbPassword=TU_PASSWORD_IBKR     # ← Cambia esto

# Trading Mode
TradingMode=paper                # ← paper o live
# TradingMode=live               # ← Descomentar para LIVE (¡CUIDADO!)

# TWS/Gateway Settings
IbDir=/Users/carlos/Jts          # ← Verifica que sea correcto
```

**Guardar:** `Ctrl+O` → `Enter` → `Ctrl+X`

⚠️ **SEGURIDAD:** Este archivo contiene tu contraseña en texto plano. NO lo subas a git.

---

## 🧪 Paso 3: Probar IBC Manualmente (Recomendado)

```bash
cd ~/ibc

# Opción A: Lanzar TWS (interfaz completa)
./twsstartmacos.sh

# Opción B: Lanzar Gateway (solo API, más ligero - RECOMENDADO)
./gatewaystartmacos.sh
```

**Debe suceder:**
1. ✅ TWS/Gateway se abre automáticamente
2. ✅ Login automático (sin pedir contraseña)
3. ✅ Conexión API habilitada
4. ✅ Ventana lista para operar

**Nota:** Gateway es más ligero y recomendado para trading automático.

**Si NO funciona:**
- Verifica `IbLoginId` y `IbPassword` en `config.ini`
- Verifica que `IbDir` apunte a la carpeta de TWS
- TWS debe estar instalado en `/Users/carlos/Jts`

**Cerrar TWS:** Simplemente cierra la ventana para continuar.

---

## 🚀 Paso 4: Configurar Supervisor (Ya está listo)

El supervisor ya está configurado con valores por defecto:

```bash
# Ver configuración actual
head -60 /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/scripts/automation/trading_system_supervisor.sh
```

**Configuración actual:**
```bash
STARTUP_HOUR=8     # 08:00 ET (morning)
SHUTDOWN_HOUR=17   # 17:00 ET (5:00 PM - after market close)

USE_MARKET_CALENDAR=true  # Auto-detecta festivos
```

**Para cambiar horarios (opcional):**
```bash
nano scripts/automation/trading_system_supervisor.sh

# Buscar líneas 49-50:
SHUTDOWN_HOUR=17   # ← Cambiar si quieres otro horario
STARTUP_HOUR=8     # ← Cambiar si quieres otro horario
```

---

## ▶️ Paso 5: Iniciar el Supervisor

### Opción A: Inicio Manual (Para probar)

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3

# Ejecutar supervisor en primer plano (para ver logs)
./scripts/automation/trading_system_supervisor.sh
```

**Verás:**
```
==================================================
🐕 Trading System Supervisor Started
==================================================
Schedule:
  - Startup:  8:00 ET
  - Shutdown: 17:00 ET (after market close)

Market Calendar:
  - Enabled: true
  - Today: HOLIDAY/WEEKEND (market closed)  ← Hoy es domingo

Health Checks:
  - Trading System: Every 60s
  - TWS Connection: Every 30s
==================================================

📅 2025-12-14 is NOT a trading day (holiday/weekend)
   Skipping today - system will sleep until tomorrow
```

**Para detener:** `Ctrl+C`

---

### Opción B: Inicio en Background (24/7)

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3

# Ejecutar en background
nohup ./scripts/automation/trading_system_supervisor.sh > /dev/null 2>&1 &

# Ver proceso
ps aux | grep supervisor
```

**Para ver logs:**
```bash
# Log del supervisor
tail -f logs/supervisor/supervisor.log

# Log de reinicios
tail -f logs/supervisor/restarts.log
```

**Para detener:**
```bash
# Encontrar PID
ps aux | grep supervisor

# Matar proceso
kill <PID>
```

---

### Opción C: Auto-inicio con macOS (launchd)

**Crear archivo de servicio:**
```bash
cat > ~/Library/LaunchAgents/com.trading.supervisor.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.supervisor</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/scripts/automation/trading_system_supervisor.sh</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>StandardOutPath</key>
    <string>/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/logs/supervisor/launchd.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/logs/supervisor/launchd_error.log</string>
    
    <key>WorkingDirectory</key>
    <string>/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3</string>
</dict>
</plist>
PLIST

# Cargar servicio
launchctl load ~/Library/LaunchAgents/com.trading.supervisor.plist

# Ver status
launchctl list | grep trading
```

**Para desactivar auto-inicio:**
```bash
launchctl unload ~/Library/LaunchAgents/com.trading.supervisor.plist
```

---

## 📅 Ejemplo de Funcionamiento Diario

### Lunes (Día de Trading)

**08:00 ET:**
```
✅ 2025-12-15 is a TRADING DAY (market closes at 16:00 ET)
🚀 Starting TWS...
⏳ Waiting for TWS to initialize (60s)...
✅ TWS is running (PID: 12345)
🚀 Starting trading system...
✅ Trading system started (PID: 12346)
```

**09:30 - 16:00 ET:**
```
[09:30:15] ✅ TWS health check: OK
[09:30:15] ✅ Trading system health check: OK
[09:31:15] ✅ TWS health check: OK
[09:31:15] ✅ Trading system health check: OK
...
```

**Si TWS falla (ej: 14:23 ET):**
```
[14:23:10] ❌ TWS health check failed
🔄 Restarting TWS...
🛑 Stopping TWS (PID: 12345)
🚀 Starting TWS...
✅ TWS restarted successfully
🔄 Restarting trading system...
✅ Trading system restarted successfully
```

**17:00 ET (5:00 PM - After Market Close):**
```
🌙 17:00 ET - Scheduled shutdown (after market close)
🛑 Stopping trading system...
🛑 Stopping TWS...
✅ All systems stopped

💤 Sleeping until 08:00 ET...
```

---

### Sábado/Domingo (Weekend)

**08:00 ET:**
```
📅 2025-12-14 is NOT a trading day (holiday/weekend)
   Skipping today - system will sleep until tomorrow

💤 Sleeping for 6 hours...
```

**14:00 ET (6 horas después):**
```
📅 2025-12-14 is NOT a trading day (holiday/weekend)
   Skipping today - system will sleep until tomorrow

💤 Sleeping for 6 hours...
```

**Ciclo se repite hasta el lunes.**

---

### Festivo (ej: Thanksgiving)

**08:00 ET:**
```
📅 2025-11-28 is NOT a trading day (holiday/weekend)
   Skipping today - system will sleep until tomorrow
⚠️  HOLIDAY: Thanksgiving - Market closed

💤 Sleeping for 6 hours...
```

**El sistema NO opera, pero sigue corriendo en background.**

---

### Early Close (ej: Black Friday - 13:00 ET close)

**08:00 ET:**
```
✅ 2025-11-29 is a TRADING DAY (market closes at 13:00 ET)
⚠️  EARLY CLOSE detected: Market closes at 13:00 ET instead of 16:00 ET

🚀 Starting TWS...
🚀 Starting trading system...
```

**13:00 ET (Early Close):**
```
⚠️  Market closing early at 13:00 ET
🛑 Stopping trading system...
✅ Trading system stopped
```

**17:00 ET:**
```
🌙 17:00 ET - Scheduled shutdown (after market close)
🛑 Stopping TWS...
```

---

## 📊 Monitoreo

### Ver Logs en Tiempo Real

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3

# Supervisor log
tail -f logs/supervisor/supervisor.log

# Restart log
tail -f logs/supervisor/restarts.log

# Trading system log
tail -f logs/trader.log

# Scanner log
tail -f logs/scanner.log
```

### Verificar Estado

```bash
# Ver procesos activos
ps aux | grep -E "supervisor|TWS|trader_main|scanner_main"

# Ver PIDs guardados
cat logs/supervisor/*.pid 2>/dev/null
```

### Estadísticas del Día

```bash
# Contar reinicios hoy
grep "$(date +%Y-%m-%d)" logs/supervisor/restarts.log | wc -l

# Ver última actividad
tail -20 logs/supervisor/supervisor.log
```

---

## 🛠️ Troubleshooting

### TWS no se auto-login

```bash
# Verificar config
cat ~/ibc/config.ini | grep -E "IbLoginId|IbPassword|TradingMode"

# Probar manualmente
cd ~/ibc
./scripts/DisplayBannerAndLaunch.sh
```

### Supervisor no detecta festivos

```bash
# Probar market calendar
python3 scripts/automation/check_market_day.py is_market_day
python3 scripts/automation/check_market_day.py get_next_trading_day
```

### Sistema no se reinicia

```bash
# Ver últimos errores
tail -50 logs/supervisor/supervisor.log

# Verificar permisos
ls -la scripts/automation/*.sh

# Hacer ejecutable
chmod +x scripts/automation/*.sh
```

---

## 🎯 Resumen: Lo que YA NO necesitas hacer

❌ **ANTES (Manual):**
1. Encender TWS manualmente cada día
2. Ingresar usuario y contraseña
3. Esperar a que TWS conecte
4. Ejecutar `python3 simple_main.py`
5. Monitorear si TWS se desconecta
6. Apagar todo a medianoche
7. Verificar si es festivo

✅ **AHORA (Automático):**
1. ~~Nada~~ (el supervisor lo hace TODO)

---

## 📝 Checklist de Configuración Inicial

- [ ] IBC instalado (`~/ibc` existe)
- [ ] Credenciales configuradas en `~/ibc/config.ini`
- [ ] IBC probado manualmente (auto-login funciona)
- [ ] `pandas_market_calendars` instalado (`pip3 install pandas_market_calendars`)
- [ ] Scripts ejecutables (`chmod +x scripts/automation/*.sh`)
- [ ] Supervisor probado manualmente
- [ ] (Opcional) Servicio launchd configurado para auto-inicio

---

## 🚨 Notas Importantes

1. **Seguridad:** `~/ibc/config.ini` contiene tu contraseña. Nunca lo subas a git.
2. **Paper vs Live:** Verifica `TradingMode` en `config.ini` antes de operar.
3. **TWS API:** Asegúrate de tener "Enable ActiveX and Socket Clients" en TWS settings.
4. **Horarios ET:** El sistema usa hora Eastern Time (NY).
5. **Logs:** Revisa logs regularmente para detectar problemas.

---

## 📞 Soporte

Si algo no funciona:
1. Revisa logs: `logs/supervisor/supervisor.log`
2. Verifica IBC: `cat ~/ibc/config.ini`
3. Prueba market calendar: `python3 scripts/automation/check_market_day.py is_market_day`
4. Ejecuta supervisor manualmente para ver errores en tiempo real

---

**Última actualización:** 2025-12-14
**Estado:** Production Ready ✅
