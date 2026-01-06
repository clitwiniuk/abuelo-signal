# Workers Activos - Configuración de Prueba

**Fecha**: 2025-12-18
**Objetivo**: Evaluar workers complementarios con CERO interferencia

---

## ✅ Workers Habilitados (2)

### 1. VCP Smallcap (`vcp_smallcap`)
**Estrategia**: Volatility Contraction Pattern - Entrada anticipada pre-breakout

**Características**:
- **Timing**: Todo el día (9:30-16:00 ET)
- **Precio**: $1.00 - $25.00
- **Patrón**: Contracciones de volatilidad (consolidación)
- **Volumen**: Declinando en cada contracción (acumulación)
- **Entry**: 80-90% del patrón completo (ANTES del breakout)
- **Hold Time**: Máximo 6 horas

**Exits**:
- Take Profit: 15%
- Stop Loss: 5%
- Trailing: 8% activation, 4% distance
- Time-based: 6 horas

**Filosofía**: Entrar ANTES del breakout, cuando el patrón está 80-85% completo.

---

### 2. Parabolic Extension (`parabolic`)
**Estrategia**: Detección de aceleración parabólica EARLY-stage

**Características**:
- **Timing**: Todo el día (9:30-16:00 ET)
- **Precio**: $0.50 - $15.00
- **Patrón**: Aceleración de precio (ROC creciente)
- **Volumen**: Creciente (confirmación de momentum)
- **Entry**: Solo EARLY stage (antes que sea obvio)
- **Hold Time**: Máximo 1.5 horas (scalp/intraday)

**Exits**:
- Take Profit: 10%
- Stop Loss: 4%
- Trailing: 5% activation, 2.5% distance
- Time-based: 1.5 horas
- **PRIORITY EXIT**: Si detecta LATE stage o exhaustion → SALIR INMEDIATAMENTE

**Filosofía**: Entrar cuando detecta aceleración TEMPRANA, salir al primer signo de exhaustion.

---

## 🔄 Complementariedad (CERO Interferencia)

### Por qué NO interfieren:

1. **Fase del Ciclo Opuesta**:
   - VCP: Opera en **consolidación** (pre-breakout)
   - Parabolic: Opera en **aceleración** (post-breakout)

2. **Volumen Opuesto**:
   - VCP: Volumen **declinando** (acumulación silenciosa)
   - Parabolic: Volumen **creciente** (confirmación de momentum)

3. **Timing del Entry**:
   - VCP: Entra cuando el precio está **comprimido**
   - Parabolic: Entra cuando el precio está **acelerando**

4. **Secuencia Natural**:
   ```
   1. VCP detecta consolidación → ENTRA
   2. VCP breakout ocurre → SALE con profit
   3. Si el breakout acelera → Parabolic detecta y ENTRA
   4. Parabolic captura extensión → SALE en exhaustion
   ```

**Probabilidad de Interferencia**: **<2%**

Solo interferirían si VCP detecta patrón exactamente cuando Parabolic detecta aceleración en el mismo ticker, lo cual es técnicamente imposible (son fases opuestas).

---

## 📊 Esperado Hoy (2025-12-18)

### VCP:
- **Entries esperados**: 0-2 trades
- **Tipo de setups**: Consolidaciones de 30-45 min con volumen declinando
- **Tickers típicos**: Smallcaps con noticias/catalizadores, formando VCP intraday

### Parabolic:
- **Entries esperados**: 0-1 trades
- **Tipo de setups**: Runners que aceleran en EARLY stage (antes de +20%)
- **Tickers típicos**: Momentum runners con aceleración clara pero no sobreextendida

### Coexistencia:
- **Conflictos esperados**: 0 (fases opuestas del ciclo)
- **Beneficio**: Cobertura completa del ciclo (pre-move + durante-move)

---

## 🔬 Plan de Evaluación

### HOY (2025-12-18):
1. ✅ Habilitar VCP + Parabolic
2. ⏳ Dejar correr SIN modificaciones todo el día
3. ⏳ Recolectar trades de ambos workers
4. ⏳ Observar si hay interferencias

### MAÑANA (2025-12-19):
1. Validar fidelidad del replay:
   ```bash
   cd scientific_backtest/
   python validate_replay_fidelity.py --worker vcp_smallcap --days 1
   python validate_replay_fidelity.py --worker parabolic --days 1
   ```

2. Si match rate >95%, ejecutar backtest:
   ```bash
   python backtest_all_workers.py --workers vcp_smallcap parabolic
   ```

3. Revisar resultados:
   ```bash
   open backtest_comparison.html
   ```

4. Tomar decisiones basadas en data:
   - ✅ MANTENER si consistencia >75%
   - ⚠️ MONITOREAR si consistencia 50-75%
   - ❌ DESHABILITAR si consistencia <50%

---

## ⚠️ Recordatorios Importantes

1. **NO MODIFICAR** parámetros hoy - Dejar que recolecte datos limpios
2. **NO AGREGAR** filtros adicionales antes del backtest
3. **NO TOCAR** configuración hasta completar validación científica
4. **SÍ OBSERVAR** comportamiento y tomar notas mentales
5. **SÍ CONFIAR** en el backtest para decisiones finales

---

## 📝 Notas de Configuración

**Backup creado**: `config.ini.backup_before_disable_workers`

**Workers deshabilitados** (29 total):
- daily_plays, momentum_breakout, holy_grail, orb, balance_day
- vwap_breakout, volume_absorption, macdv, buy_and_hold, buy_the_dip
- [... y 19 más]

**Workers habilitados** (2 total):
- vcp_smallcap ✅
- parabolic ✅

---

**Configuración lista para evaluación científica** 🧪
