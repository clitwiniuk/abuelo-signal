# Telegram Setup - Sistema III

## 📱 Configuración de Telegram

### 1. Crear Bot de Telegram

1. **Abrir Telegram y buscar @BotFather**
2. **Crear nuevo bot:**
   ```
   /newbot
   ```
3. **Seguir las instrucciones y obtener el TOKEN**

### 2. Obtener Chat ID

1. **Agregar el bot a tu chat/grupo**
2. **Enviar un mensaje al bot**
3. **Visitar:** `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
4. **Buscar el `chat_id` en la respuesta JSON**

### 3. Configurar config.ini

Edita `sistema_III/config.ini`:

```ini
[NOTIFICATIONS]
# Telegram notifications
telegram_enabled = true
telegram_bot_token = 1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef123
telegram_chat_id = -1001234567890

# Notification filters
notification_cooldown_seconds = 300
enable_notification_filter = true

# What to notify
notify_new_opportunities = true
notify_trade_executions = true
notify_position_closes = true
notify_risk_alerts = true
notify_system_status = true
notify_errors = true

# Notification levels
min_quality_score_notify = 75.0
min_gap_percent_notify = 2.0
min_volume_ratio_notify = 2.0
```

## 🤖 Comandos Disponibles

### Comandos Básicos
- `/status` - Estado general del sistema
- `/help` - Lista de comandos disponibles

### Monitoring
- `/positions` - Posiciones activas
- `/stats` - Estadísticas del día
- `/risk` - Estado de riesgo actual
- `/portfolio` - Resumen del portfolio
- `/health` - Health check de componentes

### Estrategias
- `/workers` - Estado de los workers
- `/opportunities` - Oportunidades recientes

### Control de Sistema
- `/emergency_stop` - Parada de emergencia (cierra todas las posiciones)
- `/restart_scanner` - Reiniciar scanner (en desarrollo)

### Notificaciones
- `/filter_status` - Estado del filtro anti-spam
- `/clear_notifications` - Limpiar cache de notificaciones

## 📡 Notificaciones Automáticas

El sistema envía notificaciones automáticas para:

### 🎯 Nuevas Oportunidades
```
🎯 Nueva Oportunidad

📊 AAPL - GAP_GO
💰 Precio: $150.25
📈 Gap: 3.2%
📊 Volumen: 2.5x
⭐ Quality: 85.2

🕐 09:35:15
```

### ✅ Trades Ejecutados
```
✅ Trade Ejecutado

📊 AAPL - GAP_GO
🎯 Cantidad: 100 shares
💰 Entrada: $150.25
🛑 Stop Loss: $146.75
🚀 Target: $159.75

🕐 09:35:20
```

### 💚 Posiciones Cerradas
```
💚 Posición Cerrada

📊 AAPL
💰 Precio: $159.80
📈 P&L: +$955.00
📝 Razón: PROFIT_TARGET

🕐 10:42:33
```

### 🚨 Alertas de Riesgo
```
🚨 Alerta de Riesgo

⚠️ DAILY_LOSS_LIMIT_APPROACHING
📝 Daily P&L: -$750.00 (75% of limit)

🕐 14:25:10
```

## 🚫 Sistema Anti-Spam

### Filtro Inteligente
- **Cooldown:** 5 minutos entre notificaciones del mismo símbolo
- **Cambios significativos:** Solo notifica si hay cambios importantes
- **Primera detección:** Siempre notifica nuevos símbolos

### Thresholds de Cambio
- **Precio:** >5% cambio
- **Gap:** >2% cambio
- **Volumen:** >50% cambio
- **Quality Score:** >1 punto cambio

## ⚙️ Configuración Avanzada

### Personalizar Notificaciones

```ini
# Desactivar notificaciones específicas
notify_new_opportunities = false
notify_trade_executions = true
notify_position_closes = true

# Ajustar thresholds
min_quality_score_notify = 80.0  # Solo calidad alta
min_gap_percent_notify = 3.0     # Solo gaps >3%
min_volume_ratio_notify = 3.0    # Solo volumen alto
```

### Ajustar Filtro Anti-Spam

```ini
# Cooldown más corto (2 minutos)
notification_cooldown_seconds = 120

# Desactivar filtro completamente
enable_notification_filter = false
```

## 🔧 Troubleshooting

### Bot no responde
1. Verificar `telegram_bot_token` correcto
2. Verificar `telegram_chat_id` correcto
3. Bot agregado al chat/grupo
4. `telegram_enabled = true`

### No llegan notificaciones
1. Verificar configuración de notificaciones
2. Revisar thresholds (pueden ser muy altos)
3. Comprobar filtro anti-spam con `/filter_status`
4. Limpiar cache con `/clear_notifications`

### Logs de Telegram
```bash
# Ver logs del sistema
tail -f logs/main.log | grep Telegram

# Ver logs específicos de notificaciones
tail -f logs/main.log | grep "TelegramClient\|notification"
```

## 🚀 Ejemplo de Uso

1. **Iniciar Sistema:**
   ```bash
   python main.py
   ```

2. **Recibir notificación de startup:**
   ```
   🚀 Estado del Sistema
   📍 Status: running
   📝 Sistema III está funcionando correctamente
   ```

3. **Monitorear con comandos:**
   ```
   /status  # Estado general
   /risk    # Verificar riesgo
   ```

4. **Durante trading recibir notificaciones automáticas de:**
   - Nuevas oportunidades detectadas
   - Trades ejecutados
   - Posiciones cerradas con P&L

5. **Control de emergencia:**
   ```
   /emergency_stop  # Si necesitas parar todo
   ```

El sistema está diseñado para funcionar de manera autónoma enviando todas las actualizaciones importantes a Telegram, permitiendo monitoreo completo desde el móvil.