# ✅ First Day Checklist - Scanner Improvements

**Fecha**: 2025-12-04 (Primera sesión con mejoras)
**Sistema**: trading_system_v3

---

## 🌅 PRE-MARKET (7:30-9:30 AM ET)

### 7:30 AM - Startup

```bash
# Terminal 1: Scanner
cd trading_system_v3
python scanner_main.py

# Terminal 2: Trader
python trader_main.py
```

**Verificar en logs**:
- [ ] Scanner: "✅ Early Bird Mode enabled (Phase 2)"
- [ ] Trader: "✅ ORB Priority Queue enabled (Phase 3)"

---

### 8:00-9:30 AM - Monitor Pre-Market Activity

**Archivo**: `logs/scanner.log`

**Buscar estas líneas** (tail -f):
```bash
tail -f logs/scanner.log | grep -E "EARLY BIRD|LARGE GAP|🐦|🚀"
```

**Ejemplos de lo que deberías ver**:
```
🐦 EARLY BIRD qualified: XXXX (gap=25.5%, price=$4.50, pm_vol=50,000, vol_ratio=2.5x)
🚀 XXXX: LARGE GAP OVERRIDE - Gap 35.2% >= 20% - AUTO-QUALIFIED
🐦 PRE-MARKET: XXXX qualified for Early Bird (will be sent at 9:30 AM)
```

**Checklist**:
- [ ] Al menos 1 símbolo calificado con "EARLY BIRD qualified"
- [ ] Gaps >20% tienen "LARGE GAP OVERRIDE"
- [ ] Mensaje "qualified for Early Bird (will be sent at 9:30 AM)"

**Si NO ves símbolos calificados**:
- ⚠️ Normal si el mercado está tranquilo
- ⚠️ Revisar que IBKR scanner está activo
- ⚠️ Verificar conexión IBKR (port 7497)

---

## 🔔 MARKET OPEN (9:30 AM ET)

### 9:30:00 AM - Early Bird Send

**Archivo**: `logs/scanner.log`

**Buscar EXACTAMENTE a las 9:30 AM**:
```bash
grep "Market OPEN" logs/scanner.log
```

**Lo que deberías ver**:
```
🔔 Market OPEN - Sending 3 Early Bird opportunities
📤 Early Bird: XXXX qualified (gap=25.5%, Q=85.2)
📤 Early Bird: YYYY qualified (gap=33.7%, Q=88.0)
📤 Early Bird: ZZZZ qualified (gap=5.7%, Q=78.5)
```

**Checklist**:
- [ ] Mensaje "Market OPEN - Sending X Early Bird opportunities"
- [ ] X >= 1 (al menos un símbolo enviado)
- [ ] Cada símbolo tiene "Early Bird: [SYMBOL] qualified"

**Si dice "No Early Bird opportunities"**:
- ⚠️ Normal si no hubo calificados en pre-market
- ⚠️ Continuar monitoreando - Phase 1 (LARGE_GAP_OVERRIDE) sigue activo

---

### 9:30-9:31 AM - Trader Reception

**Archivo**: `logs/trader.log`

**Buscar inmediatamente después de 9:30**:
```bash
grep "ORB Priority" logs/trader.log
```

**Lo que deberías ver**:
```
📡 Received 3 opportunities from scanner
🎯 ORB Priority: Processing XXXX (Early Bird)
🏹 Routing XXXX directly to ORB worker
✅ ORB Priority: XXXX ACCEPTED by ORB worker
```

**O**:
```
🎯 ORB Priority: Processing XXXX (Early Bird)
🏹 Routing XXXX directly to ORB worker
⚪ ORB Priority: XXXX REJECTED by ORB worker, routing to all workers
```

**Checklist**:
- [ ] "📡 Received X opportunities" (X debe coincidir con scanner)
- [ ] "🎯 ORB Priority: Processing [SYMBOL]"
- [ ] "🏹 Routing [SYMBOL] directly to ORB worker"
- [ ] Mensaje de ACCEPTED o REJECTED

**Si NO ves "ORB Priority"**:
- ❌ Flag 'early_bird' no llegó en opportunity dict
- ❌ Revisar scanner: SmallcapPlay debe tener 'early_bird': True

---

## 📊 ORB WINDOW (9:30-10:00 AM)

### Monitor ORB Worker Activity

**Archivo**: `logs/trader.log`

**Buscar evaluaciones ORB**:
```bash
grep -A 5 "ORB.*evaluating\|ORB.*ENTRY" logs/trader.log
```

**Lo que deberías ver (si acepta)**:
```
[ORB Worker] Evaluating XXXX for entry
[ORB Worker] ✅ ENTRY SIGNAL: XXXX at $4.52
[ORB Worker] Opening range: $4.45-$4.50
[ORB Worker] Breakout confirmed, entering position
```

**Checklist**:
- [ ] ORB worker evaluando símbolos Early Bird
- [ ] Si setup válido: "ENTRY SIGNAL"
- [ ] Trade ejecutado en window 9:30-10:00 AM

**Si ORB rechaza todos**:
- ⚠️ Normal - no todos los días hay setups válidos
- ⚠️ Verificar que otros workers están evaluando (fallback)
- ⚠️ Revisar parámetros ORB en config.ini

---

## 📈 POST-MARKET (After 4:00 PM)

### Analysis Query

**Base de datos**: `trading_data.db`

```sql
-- Check scanner opportunities received
SELECT
    symbol,
    gap_percentage,
    volume_ratio,
    quality_score,
    opportunity_type,
    detected_at
FROM scanner_opportunities
WHERE DATE(detected_at) = DATE('now')
ORDER BY detected_at;

-- Check trades executed by ORB worker
SELECT
    symbol,
    entry_price,
    entry_time,
    exit_price,
    exit_time,
    pnl,
    worker_name
FROM trades
WHERE DATE(entry_time) = DATE('now')
AND worker_name = 'orb_breakout';

-- Check all trades for the day
SELECT
    worker_name,
    COUNT(*) as num_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    SUM(pnl) as total_pnl
FROM trades
WHERE DATE(entry_time) = DATE('now')
GROUP BY worker_name;
```

---

## 📊 Success Metrics

### Baseline (Yesterday - Before Improvements):
- ORB Trades: **0**
- Early Bird symbols detected: **0** (no system)
- Scanner rejections for large gaps: **3** (IRBT, QCLS, MSTX)

### Expected (Today - With Improvements):
- ORB Trades: **1-2** ✅
- Early Bird symbols qualified: **2-5** ✅
- Scanner rejections for large gaps: **0** ✅

### Key Performance Indicators:

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Early Bird qualified (pre-market) | >= 1 | ___ | ⏳ |
| Sent at 9:30 AM | 100% of qualified | ___ | ⏳ |
| ORB Priority routing | 100% of Early Bird | ___ | ⏳ |
| ORB Trades executed | >= 1 | ___ | ⏳ |
| Large gaps (>20%) auto-qualified | 100% | ___ | ⏳ |

---

## 🚨 Troubleshooting

### Problem: No Early Bird qualified in pre-market

**Possible Causes**:
1. Market too quiet (no gaps >5%)
2. IBKR scanner not active pre-market
3. Timezone issue (not using ET)

**Solution**:
```bash
# Check scanner log for timezone
grep "premarket_hours" logs/scanner.log

# Verify IBKR connection active
grep "IBKR.*connected" logs/scanner.log
```

---

### Problem: Early Bird sent but Trader doesn't receive

**Possible Causes**:
1. Redis connection issue
2. Bridge not working

**Solution**:
```bash
# Check Redis
redis-cli ping

# Check scanner log for "Publishing"
grep "Publishing.*opportunities" logs/scanner.log

# Check trader log for "Received"
grep "Received.*opportunities" logs/trader.log
```

---

### Problem: ORB Priority not triggering

**Possible Causes**:
1. Flag 'early_bird' missing in opportunity dict
2. ORBPriorityQueue not initialized

**Solution**:
```bash
# Check trader startup
grep "ORB Priority Queue enabled" logs/trader.log

# Check flag in opportunity
grep -A 10 "Received.*opportunities" logs/trader.log | grep "early_bird"
```

---

### Problem: ORB rejects all symbols

**Possible Causes**:
1. Parameters too restrictive
2. ORB range not formed yet
3. No valid breakout setup

**Solution**:
```bash
# Check ORB rejection reasons
grep "ORB.*REJECTED\|ORB.*rejected" logs/trader.log

# Verify ORB config
grep -A 5 "ORB_STRATEGY" config.ini
```

**Config to check**:
```ini
[ORB_STRATEGY]
min_avg_volume = 30000        # Should be 30k, not 100k
min_orb_range_pct = 0.010     # Should be 1.0%, not 1.5%
```

---

## 📝 Notes Section

**Pre-Market Activity** (8:00-9:30 AM):
- Number of symbols qualified: _______
- Symbols: _______________________
- Largest gap detected: ______%

**Market Open** (9:30 AM):
- Early Bird symbols sent: _______
- Time sent (should be 9:30:00): _______

**ORB Window** (9:30-10:00 AM):
- ORB evaluations: _______
- ORB acceptances: _______
- Trades executed: _______

**Issues Encountered**:
- _________________________________
- _________________________________

**Observations**:
- _________________________________
- _________________________________

---

## ✅ End of Day Summary

**Did the improvements work?**
- [ ] YES - System captured opportunities that would have been missed
- [ ] PARTIAL - Some improvements worked, others need tuning
- [ ] NO - System needs debugging (see troubleshooting)

**Next Steps**:
- If YES: Continue monitoring, gather more data
- If PARTIAL: Identify what worked and what didn't
- If NO: Review logs, check troubleshooting section

**Save this checklist with today's date for future reference.**

---

**🚀 Good luck with the first day of improved scanner system!**
