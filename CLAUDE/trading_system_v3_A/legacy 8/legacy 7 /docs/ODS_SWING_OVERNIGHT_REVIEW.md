# ODS Swing Overnight Architecture Review

## ✅ Arquitectura Correcta y Funcional

**ODS Swing Universal** ya está **integrado y funcionando**:

**Flujo**:
```
Scanner (smallcap_daily) → Redis → Trader → WorkerBasedEngine → ods_swing_universal_worker
  ↓
ODS Classifier detecta STRONG_BULLISH_OPEN → Worker evalúa → Entry EOD (15:00-15:55)
  ↓
Hold overnight (1-7 days) → Exits: SL10%, Target20%, Trailing12%/6%
```

**Componentes**:
- **Worker**: [`strategies/workers/ods_swing_universal_worker_logic.py`](strategies/workers/ods_swing_universal_worker_logic.py) - Lógica completa.
- **Scheduler**: [`core/swing_scheduler.py`](core/swing_scheduler.py) - Iniciado en trader_main.py.
- **Capabilities**: [`core/worker_capabilities_config.py`](core/worker_capabilities_config.py) - Horizon=SWING.
- **Unified Manager**: Previene duplicados day/swing.
- **DB**: swing_trades table.
- **Execution**: GTC limits for overnight.

**Por qué no trades**:
- Strict criteria: min_ods_strength=70, vol=2x, EOD window 15:00-15:55.
- Scanner opportunities no trigger strong ODS.

## 🎯 Mejoras para Más Trades Overnight

1. **Relax Criteria**:
   - min_strength 70→60
   - vol 2x→1.5x
   - Entry window 14:30-15:55

2. **Config Params**:
   Add [ODS_SWING_UNIVERSAL]
   ```
   min_ods_strength = 60
   min_volume_ratio = 1.5
   eod_entry_start = 14:30
   ```

3. **Debug Logging**: Add to worker.

## 📋 Plan
- Update worker relax params.
- Restart trader.
- Monitor logs for ODS swing entries.

Arquitectura **correcta** para overnight swing via ODS.