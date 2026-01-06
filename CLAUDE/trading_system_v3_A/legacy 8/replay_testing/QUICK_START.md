# Quick Start - Replay Testing

## 🚀 Empezar Rápido

### 1. Verificar que tienes los datos necesarios

```bash
# Verificar que market_data.db existe y tiene datos
sqlite3 backtesting_system/market_data.db "SELECT COUNT(*) FROM bars WHERE DATE(timestamp) = '2025-10-31'"

# Verificar que trading_data.db existe y tiene trades
sqlite3 trading_data.db "SELECT COUNT(*) FROM trades WHERE DATE(entry_time) = '2025-10-31'"
```

### 2. Ejecutar primer replay (día específico, todos los workers)

```bash
# Replay del 31 de octubre con TODOS los workers
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --verbose
```

### 3. Replay con workers específicos

```bash
# Solo generic_01 y daily_plays
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers generic_01,daily_plays \
    --verbose
```

### 4. Replay de símbolos específicos

```bash
# Solo MSAI y DFSC (para investigar problemas específicos)
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --symbols MSAI,DFSC \
    --verbose
```

### 5. Replay de múltiples días

```bash
# Replay de toda la semana (todos los workers)
python replay_testing/run_replay.py \
    --start-date 2025-10-25 \
    --end-date 2025-10-31
```

### 6. Modo estricto (falla si hay discrepancias)

```bash
# Para CI/CD o testing automático
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --workers generic_01 \
    --strict
```

## 📊 Output Esperado

```
================================================================================
🔄 WORKER REPLAY TESTING SYSTEM
================================================================================

🔄 ReplayEngine initialized
   Market data: backtesting_system/market_data.db
   Trading data: trading_data.db

================================================================================
🔄 REPLAY SESSION: 2025-10-31
   Workers: generic_01, daily_plays, macdv
================================================================================

📊 Loaded data for 15 symbols
✅ Loaded 3 workers: generic_01, daily_plays, macdv

📈 Replaying EVENT: MSAI @ 2025-10-31 (538 bars)
   Event complete: 45 decisions, 3 simulated trades, 3 real trades, 2 discrepancies
   Workers evaluated: generic_01, daily_plays, macdv
   Workers traded: generic_01

📈 Replaying EVENT: DFSC @ 2025-10-31 (425 bars)
   Event complete: 32 decisions, 1 simulated trades, 1 real trades, 0 discrepancies
   Workers evaluated: generic_01, daily_plays
   Workers traded: daily_plays

================================================================================
✅ REPLAY COMPLETED in 3.2s
================================================================================
   Events: 15 (one per ticker)
   Bars processed: 6,543
   Decisions made: 189 (from 3 workers)
   Entries approved: 12
   Simulated trades: 12
   Total discrepancies: 2

📈 Events Summary:
  MSAI: 45 decisions, 3 simulated trades, 3 real trades ⚠️ (2 issues)
  DFSC: 32 decisions, 1 simulated trades, 1 real trades ✅

⚠️  Discrepancias found:
  - PRICE_MISMATCH: MSAI entry $2.13 != IBKR real $2.06
  - COOLDOWN_BUG: MSAI entry allowed despite cooldown

✅ Replay testing completed
```

## 🔍 Casos de Uso Comunes

### Investigar día problemático

```bash
# MSAI tuvo 3 stop losses seguidos el 31/10
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --worker generic_01 \
    --symbols MSAI \
    --verbose
```

### Verificar fix de código

```bash
# Antes del fix
git checkout before-fix
python replay_testing/run_replay.py --date 2025-10-31 --worker generic_01 > before.txt

# Después del fix
git checkout after-fix
python replay_testing/run_replay.py --date 2025-10-31 --worker generic_01 > after.txt

# Comparar
diff before.txt after.txt
```

### Regression testing

```bash
# Asegurar que cambios no rompieron workers
python replay_testing/run_replay.py \
    --start-date 2025-10-25 \
    --end-date 2025-10-31 \
    --worker generic_01 \
    --strict  # Falla si hay problemas
```

## 🛠️ Troubleshooting

### Error: "No market data found"

```bash
# Verificar que la fecha tiene datos
sqlite3 backtesting_system/market_data.db \
    "SELECT DATE(timestamp) as date, COUNT(*) as bars
     FROM bars
     GROUP BY DATE(timestamp)
     ORDER BY date DESC
     LIMIT 10"
```

### Error: "Failed to load worker"

```bash
# Verificar que el worker existe
ls strategies/workers/ | grep generic_01
```

### Performance lento

```bash
# Usar menos símbolos
python replay_testing/run_replay.py \
    --date 2025-10-31 \
    --worker generic_01 \
    --symbols MSAI  # Solo 1 símbolo
```

## 📝 Próximos Pasos

1. ✅ Ejecutar primer replay
2. ✅ Revisar discrepancias encontradas
3. 📊 Implementar verificador de decisiones (próximo paso)
4. 📊 Implementar comparador replay vs real
5. 📄 Generar reportes HTML
6. 🧪 Crear tests automatizados

## 🎓 Entender el Output

### Decisiones

- **ENTRY APPROVED**: Worker decidió entrar y pasó todas las validaciones
- **ENTRY REJECTED**: Worker rechazó la oportunidad (pattern <75%, cooldown, etc.)
- **ENTRY BLOCKED**: Worker quería entrar pero fue bloqueado (cooldown, position lock, etc.)
- **EXIT EXECUTED**: Worker cerró posición (stop loss, TP, EOD, etc.)

### Discrepancias

- **PRICE_MISMATCH**: Precio usado difiere del precio real de IBKR
- **COOLDOWN_BUG**: Sistema permitió entrada cuando debería estar en cooldown
- **PATTERN_ERROR**: Pattern completion incorrecto
- **MISSING_TRADE**: Replay entró pero real no (o viceversa)

## 📞 Ayuda

Si encuentras problemas:
1. Ejecuta con `--verbose` para ver más detalles
2. Revisa los logs en consola
3. Verifica que las bases de datos tienen datos
4. Asegúrate de usar la fecha correcta (YYYY-MM-DD)
