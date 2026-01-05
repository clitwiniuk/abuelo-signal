# Solución Error 322 IBKR - Subscription Leak

## Síntomas
```
Error 322: Maximum number of account summary requests exceeded;
desubscribe to previous request first
```

## Causa Root
El archivo `core/brokers/live_ibkr_broker.py` estaba usando `accountSummaryAsync()` que crea **suscripciones persistentes** sin cancelarlas, causando un leak.

## Cambios Aplicados

### 1. Archivo Modificado: `core/brokers/live_ibkr_broker.py`

**Antes (MALO)**:
```python
async def get_account_summary(self):
    summary = await self.ib.accountSummaryAsync(self.account_id)  # ❌ Leak!
```

**Después (BUENO)**:
```python
async def get_account_summary(self):
    # Cache para evitar llamadas excesivas
    if cache_valid:
        return cached_data

    # Suscribirse
    await self.ib.reqAccountUpdatesAsync(subscribe=True, acctCode=self.account_id)

    # Obtener datos
    account_values = self.ib.accountValues(account=self.account_id)

    # ✅ DESUSCRIBIRSE inmediatamente
    await self.ib.reqAccountUpdatesAsync(subscribe=False, acctCode=self.account_id)

    return result
```

**Características añadidas**:
- ✅ Cache de 5 segundos
- ✅ Subscribe/Unsubscribe explícito
- ✅ Método `cleanup()` para limpieza al desconectar

### 2. Script de Emergencia Creado

**Ubicación**: `scripts/cleanup_ibkr_subscriptions.py`

## Pasos de Resolución Inmediata

### Paso 1: Detener Todos los Procesos
```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A

# Matar procesos Python relacionados
pkill -f "python.*trader_main.py"
pkill -f "python.*scanner_main.py"

# Verificar que no quede nada
ps aux | grep -i "python.*trading_system"
```

### Paso 2: Reiniciar TWS/Gateway
1. Cerrar completamente TWS o IB Gateway
2. Esperar **30 segundos** completos
3. Reiniciar TWS/Gateway
4. Esperar a que conecte completamente

### Paso 3: Ejecutar Script de Limpieza (Opcional)
```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A

python3 scripts/cleanup_ibkr_subscriptions.py
```

### Paso 4: Reiniciar Sistema
```bash
# Activar entorno virtual
source venv/bin/activate  # o el path correcto

# Iniciar trader
python trader_main.py
```

### Paso 5: Verificar Logs
```bash
tail -f logs/trader.log | grep -E "Error 322|account summary"
```

**Señales de éxito**:
- ✅ No aparece más "Error 322"
- ✅ Ves logs de "Requesting account summary"
- ✅ Ves logs de "Cancelled account update subscriptions"

## Prevención Futura

### Mejores Prácticas

1. **Siempre cancelar suscripciones**:
```python
# Patrón correcto
await ib.reqAccountUpdatesAsync(subscribe=True, acctCode=account)
# ... usar datos ...
await ib.reqAccountUpdatesAsync(subscribe=False, acctCode=account)  # ✅
```

2. **Usar cache cuando sea posible**:
```python
# Evitar llamadas excesivas a IBKR
if time_since_last_call < 5_seconds:
    return cached_data
```

3. **Cleanup al desconectar**:
```python
async def disconnect(self):
    await self.broker.cleanup()  # Cancelar suscripciones
    await self.ib.disconnect()
```

## Monitoring

### Comando para detectar leaks temprano:
```bash
# Monitorear logs en tiempo real
tail -f logs/trader.log | grep -i "error\|warning" | grep -v "1102"
```

### Señales de que hay un leak:
- Múltiples mensajes "Requesting account summary" en < 5 segundos
- TWS muestra múltiples conexiones del mismo client_id
- Error 322 aparece después de varias horas de operación

## Contactos de Emergencia

Si el problema persiste:
1. Verificar que no hay otros scripts Python conectados a IBKR
2. Cambiar `client_id` en config a un valor único (ej: 4150, 4151)
3. Reiniciar completamente TWS
4. Si todo falla: Contactar soporte IBKR (típicamente problema de cuenta)

## Notas Técnicas

**Error 1102 NO es un error**: Es solo una notificación de reconexión exitosa. Puedes ignorarlo.

**Límites de IBKR**:
- Máximo ~50 suscripciones simultáneas por client
- Account summary: Máximo 1-2 activas
- Market data: Depende de tu suscripción

**Arquitectura correcta**:
```
Client → Cache → IBKR API
         ↑
         └─ Subscribe/Unsubscribe cycle
```

## Changelog

- **2026-01-05**: Fix implementado en `live_ibkr_broker.py`
- **2026-01-05**: Script de limpieza creado
- **2026-01-05**: Documentación añadida
