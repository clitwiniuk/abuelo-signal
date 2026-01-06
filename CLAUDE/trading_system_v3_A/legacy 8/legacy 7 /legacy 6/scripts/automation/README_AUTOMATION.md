# 🤖 Automatización del Sistema de Trading (macOS)

Guía completa para configurar el sistema de trading 100% automático en Mac.

**Resultado final**: El sistema se iniciará automáticamente a las 08:00 ET y se apagará a medianoche, con reinicio automático si TWS se desconecta o el sistema crashea.

---

## 📋 Requisitos Previos

- ✅ macOS (probado en macOS 13+)
- ✅ TWS instalado (versión 10.19+ recomendada)
- ✅ Python 3.9+ con venv configurado
- ✅ Cuenta de IBKR (paper o live)
- ✅ Homebrew instalado (se instalará automáticamente si falta)

---

## 🚀 Instalación Rápida (15 minutos)

### Paso 1: Instalar IBC (Login Automático de TWS)

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/scripts/automation

# Hacer ejecutable
chmod +x install_ibc.sh

# Instalar IBC
./install_ibc.sh
```

**Salida esperada**:
```
✅ IBC Installation Complete!
📍 Installation Directory: /Users/carlos/ibc
```

### Paso 2: Configurar Credenciales de IBKR

```bash
# Copiar template de configuración
cd ~/ibc
cp config.ini.template config.ini

# Editar con tus credenciales
nano config.ini
```

**Editar estas líneas**:
```ini
IbLoginId=TU_USERNAME_IBKR
IbPassword=TU_PASSWORD_IBKR
TradingMode=paper    # Cambiar a 'live' para trading real
```

**Guardar**: `Ctrl+O`, `Enter`, `Ctrl+X`

⚠️ **SEGURIDAD**: Este archivo contiene tu contraseña en texto plano. No lo compartas ni lo subas a git.

### Paso 3: Verificar Ruta de TWS

```bash
# Verificar dónde está instalado TWS
ls -la ~/Jts

# Si TWS está en otra ubicación, editar config.ini:
nano ~/ibc/config.ini

# Actualizar la línea IbDir si es necesario:
# IbDir=/Ruta/Correcta/A/TWS
```

### Paso 4: Probar IBC Manualmente

```bash
cd ~/ibc
./scripts/DisplayBannerAndLaunch.sh
```

**Resultado esperado**:
- TWS se abre automáticamente
- Login automático (sin necesidad de ingresar credenciales)
- Disclaimer aceptado automáticamente

Si funciona correctamente, **cierra TWS** (`Cmd+Q`) y continúa.

### Paso 5: Configurar el Supervisor

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/scripts/automation

# Hacer ejecutable
chmod +x trading_system_supervisor.sh

# Verificar configuración
nano trading_system_supervisor.sh
```

**Verificar estas variables** (líneas 35-40):
```bash
PROJECT_ROOT="/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3"
IBC_DIR="$HOME/ibc"
VENV_DIR="$PROJECT_ROOT/venv"
PYTHON="$VENV_DIR/bin/python"
TRADER_MAIN="$PROJECT_ROOT/trader_main.py"
```

Si las rutas son correctas, guarda y cierra.

### Paso 6: Iniciar el Sistema Automático

```bash
# Iniciar el supervisor
./trading_system_supervisor.sh start
```

**Salida esperada**:
```
🚀 Starting Trading System Supervisor...
✅ Supervisor started (PID: 12345)
📋 Logs: /Users/carlos/.../logs/supervisor/supervisor.log

To stop: ./trading_system_supervisor.sh stop
To check status: ./trading_system_supervisor.sh status
```

### Paso 7: Verificar Estado

```bash
# Ver estado del sistema
./trading_system_supervisor.sh status
```

**Salida esperada**:
```
==================================================
Trading System Supervisor Status
==================================================
✅ Supervisor: RUNNING (PID: 12345)
✅ TWS: RUNNING (PID: 12346)
✅ Trading System: RUNNING (PID: 12347)

Current ET Time: 2025-12-13 15:30:00 EST
Trading Hours: YES
==================================================
```

---

## 📊 Comandos Disponibles

### Control del Sistema

```bash
# Iniciar todo (supervisor + TWS + trading system)
./trading_system_supervisor.sh start

# Detener todo
./trading_system_supervisor.sh stop

# Reiniciar todo
./trading_system_supervisor.sh restart

# Ver estado actual
./trading_system_supervisor.sh status
```

### Ver Logs

```bash
# Log del supervisor (general)
tail -f ../../logs/supervisor/supervisor.log

# Log de reinicios (solo eventos críticos)
tail -f ../../logs/supervisor/restarts.log

# Log del trading system
tail -f ../../logs/supervisor/trader.log

# Log de TWS
tail -f ../../logs/supervisor/tws.log
```

---

## ⏰ Schedule Automático

El sistema opera con este horario (ET timezone):

| Hora | Acción |
|------|--------|
| **08:00 ET** | 🌅 Inicio automático (TWS + Trading System) |
| **08:00 - 23:59 ET** | 🤖 Operación activa + Watchdog monitoring |
| **00:00 ET** (Medianoche) | 🌙 Apagado automático (cierra todo) |
| **00:00 - 07:59 ET** | 😴 Sistema dormido (ahorra recursos) |

### Modificar Horarios

Edita el script:
```bash
nano trading_system_supervisor.sh

# Líneas 45-46:
SHUTDOWN_HOUR=0    # Cambiar hora de apagado
STARTUP_HOUR=8     # Cambiar hora de inicio
```

Ejemplo para empezar a las 07:30 ET:
```bash
STARTUP_HOUR=7
```

---

## 🛡️ Protecciones Automáticas

### 1. Auto-Restart de TWS
Si TWS se desconecta (ej: a medianoche):
- ✅ Detectado en <30 segundos
- ✅ Reinicia TWS automáticamente vía IBC
- ✅ Login automático
- ✅ Reinicia trading system después

### 2. Auto-Restart del Trading System
Si el trading system crashea:
- ✅ Detectado en <60 segundos
- ✅ Reinicia automáticamente
- ✅ Restaura posiciones activas
- ✅ Continúa trading

### 3. Límite de Reintentos
Si falla 3 veces consecutivas:
- ⚠️ Detiene intentos automáticos
- ⚠️ Requiere intervención manual
- ⚠️ Notifica en logs

### 4. Cooldown Period
Entre reinicios: **5 minutos** de espera mínima
- Evita loops infinitos de reinicio
- Permite que el sistema se estabilice

---

## 🔍 Monitoreo y Troubleshooting

### Ver Estado en Tiempo Real

```bash
# Terminal 1: Logs del supervisor
tail -f ../../logs/supervisor/supervisor.log

# Terminal 2: Estado cada 10 segundos
watch -n 10 './trading_system_supervisor.sh status'
```

### Problemas Comunes

#### ❌ "IBC not found"
```bash
# Instalar IBC primero
./install_ibc.sh
```

#### ❌ "IBC config not found"
```bash
# Crear y configurar config.ini
cd ~/ibc
cp config.ini.template config.ini
nano config.ini  # Agregar credenciales
```

#### ❌ TWS no inicia automáticamente
```bash
# Verificar IBC config
cd ~/ibc
nano config.ini

# Verificar que:
# - IbLoginId está correcto
# - IbPassword está correcto
# - TradingMode está configurado (paper o live)
```

#### ❌ Trading system no inicia
```bash
# Verificar ruta del virtualenv
ls -la venv/bin/python

# Si no existe, crear:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### ❌ "Max restart attempts reached"
```bash
# Ver logs para identificar causa
cat ../../logs/supervisor/restarts.log

# Reiniciar manualmente después de fix
./trading_system_supervisor.sh restart
```

---

## 🔒 Seguridad

### Protección de Credenciales

El archivo `~/ibc/config.ini` contiene tu contraseña de IBKR en texto plano.

**Recomendaciones**:

1. **Permisos restrictivos**:
```bash
chmod 600 ~/ibc/config.ini
```

2. **Excluir de backups**:
```bash
# Agregar a .gitignore
echo "~/ibc/config.ini" >> ~/.gitignore

# Excluir de Time Machine
tmutil addexclusion ~/ibc/config.ini
```

3. **Usar Paper Trading inicialmente**:
```ini
TradingMode=paper  # Probar primero con paper trading
```

4. **Cambiar a Live con cuidado**:
```ini
TradingMode=live   # Solo cuando estés 100% seguro
```

---

## 🚀 Iniciar al Boot del Mac (Opcional)

Para que el sistema se inicie automáticamente cuando enciendes tu Mac:

### Crear LaunchAgent

```bash
# Crear directorio si no existe
mkdir -p ~/Library/LaunchAgents

# Crear archivo de LaunchAgent
cat > ~/Library/LaunchAgents/com.trading.supervisor.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.supervisor</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/scripts/automation/trading_system_supervisor.sh</string>
        <string>start</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <false/>

    <key>StandardOutPath</key>
    <string>/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/logs/supervisor/launchd.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/logs/supervisor/launchd_error.log</string>
</dict>
</plist>
EOF

# Cargar LaunchAgent
launchctl load ~/Library/LaunchAgents/com.trading.supervisor.plist
```

**Para desactivar**:
```bash
launchctl unload ~/Library/LaunchAgents/com.trading.supervisor.plist
```

---

## 📈 Próximos Pasos

Ahora que tienes el sistema automatizado:

1. ✅ **Probar en Paper Trading** (al menos 1 semana)
2. ✅ **Monitorear logs diariamente** (primeros 3 días)
3. ✅ **Verificar reinicios automáticos** funcionan correctamente
4. ✅ **Configurar alertas** (Telegram/email) para eventos críticos
5. ✅ **Backtest strategy** con datos históricos
6. ✅ **Gradual rollout** a live trading (pequeñas posiciones primero)

---

## 🆘 Soporte

Si encuentras problemas:

1. **Revisa logs**:
   ```bash
   cat logs/supervisor/restarts.log
   tail -100 logs/supervisor/supervisor.log
   ```

2. **Verifica estado**:
   ```bash
   ./trading_system_supervisor.sh status
   ```

3. **Reinicio limpio**:
   ```bash
   ./trading_system_supervisor.sh stop
   sleep 5
   ./trading_system_supervisor.sh start
   ```

4. **Prueba manual**:
   ```bash
   # TWS manual
   cd ~/ibc
   ./scripts/DisplayBannerAndLaunch.sh

   # Trading system manual
   cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
   source venv/bin/activate
   python trader_main.py
   ```

---

## ✅ Checklist Final

Antes de dejar el sistema corriendo solo:

- [ ] IBC instalado y probado manualmente
- [ ] Credenciales de IBKR configuradas en `~/ibc/config.ini`
- [ ] Trading mode configurado (`paper` o `live`)
- [ ] Supervisor inicia correctamente (`./trading_system_supervisor.sh start`)
- [ ] Estado muestra todo verde (`status`)
- [ ] Logs no muestran errores críticos
- [ ] Schedule configurado correctamente (08:00-00:00 ET)
- [ ] Probado reinicio automático (matar TWS manualmente y ver si reinicia)
- [ ] LaunchAgent configurado (opcional, para boot automático)
- [ ] Backups de config.ini realizados

---

**¡Sistema completamente automatizado! 🎉**

El sistema ahora:
- ✅ Se inicia solo a las 08:00 ET
- ✅ Se apaga solo a medianoche
- ✅ Reinicia TWS automáticamente si se desconecta
- ✅ Reinicia trading system si crashea
- ✅ No requiere intervención manual diaria
- ✅ Login automático (sin contraseñas)
