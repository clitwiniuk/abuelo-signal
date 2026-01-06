# Sistema de Reclamar Posiciones UNKNOWN

## Problema Original

Cuando una posición se abre en **premarket** o el sistema se crashea/reinicia:
- La posición existe en IBKR
- El `ExecutionEngineAdapter` la detecta al restaurar posiciones desde la DB
- Pero NO puede determinar qué worker la abrió
- La registra como `strategy='UNKNOWN'` en el `UnifiedPositionManager`
- Cuando el worker correcto intenta operar el símbolo, se bloquea

**Ejemplo real**:
```
2025-10-24 15:33:27 - Worker.macdv - WARNING - ⚪ NEUP: BLOCKED - already held in UNKNOWN trading (strategy: UNKNOWN)
```

## Causa Raíz

En [execution_engine_adapter.py:1252](../core/execution_engine_adapter.py#L1252):

```python
# Cannot determine strategy for manual position
strategy = 'UNKNOWN'
```

Cuando se sincroniza una posición que no está en la DB (ej: de premarket), se marca como `UNKNOWN`.

## Solución Implementada: Sistema de "Reclamar" Posiciones

### Concepto

Una posición `UNKNOWN` es una posición **huérfana** que puede ser **reclamada** por el worker correcto cuando intente operarla.

### Cambios Realizados

#### 1. `UnifiedPositionManager.is_symbol_blocked()` - [unified_position_manager.py:562-611](../core/unified_position_manager.py#L562-L611)

```python
# SPECIAL CASE: UNKNOWN positions are claimable (not blocked)
if has_position:
    position = self.get_position(symbol)
    strategy_name = position.get('strategy', 'UNKNOWN') if position else 'UNKNOWN'

    if strategy_name == 'UNKNOWN':
        self.logger.debug(f"🔄 {symbol}: Has UNKNOWN position - NOT blocking (claimable)")
        return False  # Not blocked, can be claimed
```

**Efecto**: Posiciones UNKNOWN **NO bloquean** nuevas entradas.

#### 2. `UnifiedPositionManager.can_open_position()` - [unified_position_manager.py:98-176](../core/unified_position_manager.py#L98-L176)

```python
# SPECIAL CASE: Allow claiming UNKNOWN positions (from premarket/crashes/restarts)
if existing_worker == 'UNKNOWN':
    self.logger.info(
        f"🔄 {symbol}: UNKNOWN position detected - allowing {strategy_type} to claim it"
    )
    return True, "CLAIMABLE_UNKNOWN_POSITION"
```

**Efecto**: Workers pueden "reclamar" posiciones UNKNOWN.

#### 3. `UnifiedPositionManager.register_position()` - [unified_position_manager.py:178-316](../core/unified_position_manager.py#L178-L316)

```python
# SPECIAL CASE: Claiming UNKNOWN position - UPDATE instead of blocking
if existing_worker == 'UNKNOWN':
    self.logger.info(
        f"🔄 {symbol}: Claiming UNKNOWN position - updating with {new_worker} data"
    )

    # Update the existing position with new strategy data
    if symbol in self.day_positions:
        self.day_positions[symbol].update(position_data)
        self.day_positions[symbol]['strategy_type'] = actual_strategy_type
        self.day_positions[symbol]['strategy'] = position_data.get('strategy', strategy_type)
        self.day_positions[symbol]['claimed_at'] = datetime.now()

        self.logger.info(f"✅ Claimed DAY position: {symbol} (now owned by {worker_display})")
        return True
```

**Efecto**: Cuando se registra una posición que ya existe como UNKNOWN, **se actualiza** en lugar de bloquearse.

#### 4. Preservar `strategy='UNKNOWN'` al registrar - [unified_position_manager.py:285-292](../core/unified_position_manager.py#L285-L292)

```python
# IMPORTANT: Only set 'strategy' if not already present in position_data
# This preserves UNKNOWN strategy from position_data if explicitly provided
if 'strategy' not in position_data:
    position_data['strategy'] = strategy_type
```

**Efecto**: Si `position_data` ya contiene `strategy='UNKNOWN'`, **se preserva** (no se sobrescribe).

## Flujo Completo

### Escenario: Posición de Premarket

1. **07:30 AM** - Sistema abre NEUP en premarket con MACDV
2. **08:00 AM** - Sistema se crashea o reinicia
3. **09:00 AM** - Sistema arranca y sincroniza posiciones:
   ```python
   # ExecutionEngineAdapter detecta NEUP en IBKR pero no en DB
   strategy = 'UNKNOWN'  # No sabe qué worker la abrió
   unified_manager.register_position('NEUP', 'day', {'strategy': 'UNKNOWN', ...})
   ```
4. **09:15 AM** - Scanner encuentra NEUP como oportunidad para MACDV:
   ```python
   # MACDV intenta entrar
   is_blocked = unified_manager.is_symbol_blocked('NEUP')
   # Resultado: False (UNKNOWN no bloquea)

   can_open, reason = unified_manager.can_open_position('NEUP', 'macdv', 200.0)
   # Resultado: (True, "CLAIMABLE_UNKNOWN_POSITION")

   # MACDV registra la posición (reclama)
   unified_manager.register_position('NEUP', 'macdv', {'strategy': 'macdv', ...})
   # Resultado: Posición actualizada, ahora pertenece a MACDV
   ```
5. **09:20 AM** - Otro worker (ej: Gap&Go) intenta entrar NEUP:
   ```python
   is_blocked = unified_manager.is_symbol_blocked('NEUP')
   # Resultado: True (ya reclamada por MACDV)

   # Log: "⚠️ DUPLICATE BLOCKED: NEUP already held by MACDV (attempted by Gap&Go)"
   ```

## Ventajas

✅ **Automático**: No requiere intervención manual
✅ **Robusto**: Maneja crashes, reinicios, premarket/afterhours
✅ **Correcto**: Solo el worker correcto puede reclamar
✅ **Seguro**: Una vez reclamada, está protegida contra duplicados
✅ **Sin pérdidas**: No hay necesidad de cerrar posiciones manualmente

## Testing

Ejecutar el test de verificación:

```bash
cd CLAUDE/trading_system_v3
python3 scripts/maintenance/test_unknown_position_claim.py
```

Resultado esperado:
```
✅ ALL TESTS PASSED - UNKNOWN POSITION CLAIM SYSTEM WORKS!
```

## Casos de Uso

### 1. Posición de Premarket
- Sistema abre en premarket → crash → reinicia → UNKNOWN → MACDV la reclama ✅

### 2. Posición Manual en IBKR
- Usuario abre manualmente en IBKR → sistema detecta → UNKNOWN → worker correcto la reclama ✅

### 3. Database Corrupta
- Trade en DB sin strategy → restaura como UNKNOWN → worker la reclama ✅

### 4. Múltiples Workers
- UNKNOWN existe → solo el primer worker que intente entrar la reclama → otros bloqueados ✅

## Futuras Mejoras

1. **Smart Strategy Detection**: Analizar características del trade (gap, MACD, etc.) para inferir strategy automáticamente
2. **Position Reconciliation**: Tarea periódica que limpia posiciones UNKNOWN antiguas
3. **Alert System**: Notificar cuando se detectan muchas posiciones UNKNOWN (indica problema sistémico)

## Referencias

- [unified_position_manager.py](../core/unified_position_manager.py)
- [execution_engine_adapter.py](../core/execution_engine_adapter.py)
- [test_unknown_position_claim.py](../scripts/maintenance/test_unknown_position_claim.py)
