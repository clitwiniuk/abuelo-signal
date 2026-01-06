# Dual-Mode Architecture Proposal
## Sistema Híbrido: Intraday + Daily Watchlist

**Fecha:** 2025-12-01
**Status:** PROPUESTA - Para desarrollo futuro
**Prioridad:** ALTA - Mejora crítica para capturar oportunidades que necesitan tiempo

---

## 📋 Contexto del Problema

### Problema Identificado

El sistema actual tiene **dos limitaciones críticas**:

1. **Overnight en Smallcaps es peligroso**:
   - Alta manipulación (gaps adversos frecuentes)
   - Liquidez baja (difícil cerrar posiciones rápidamente)
   - Volatilidad extrema (stops 10% demasiado amplios)
   - Catalysts se desvanecen rápidamente

2. **Perdemos oportunidades que necesitan tiempo**:
   - Scanners solo capturan momentum AHORA (intraday)
   - Plays que salen del scanner se olvidan completamente
   - No hay seguimiento de setups que evolucionan en daily chart
   - Perdemos big movers que consolidan días antes de explotar

### Conflicto Arquitectural

**Daily Plays Worker** tiene filtros **intraday** que bloquean entradas válidas desde **daily chart**:

```python
# Línea 828-834: daily_plays_worker_logic.py
vwap_valid, vwap_reason = self.validate_vwap_strength(bars, current_price)
if not vwap_valid:
    self.logger.warning(f"❌ {symbol}: REJECTED by VWAP filter")
    return False
```

**Problema:** VWAP intraday es irrelevante para un setup en daily chart que necesita días para desarrollarse.

---

## ✅ Solución Propuesta: Arquitectura Dual-Mode

### Concepto General

Sistema que **separa completamente** las decisiones intraday vs daily con dos conjuntos de parámetros independientes.

```
┌────────────────────────────────────────────────────────────────┐
│  SCANNER DETECTA OPPORTUNITY                                    │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  PLAYS ROUTER (NUEVO)                                          │
│  Decide: INTRADAY MODE vs DAILY MODE                           │
└────────────────────────────────────────────────────────────────┘
           ↓                              ↓
┌──────────────────────┐      ┌──────────────────────────┐
│  INTRADAY MODE       │      │  DAILY MODE              │
│  (Daily Plays Worker)│      │  (Watchlist Manager)     │
├──────────────────────┤      ├──────────────────────────┤
│ Filtros INTRADAY:    │      │ Filtros DAILY:           │
│ • VWAP 1-5min        │      │ • RSI daily              │
│ • RSI intraday       │      │ • Support/Resistance     │
│ • Pattern 75-95%     │      │ • Daily consolidation    │
│ • Volume spike NOW   │      │ • Multi-day setup        │
│ • Momentum inmediato │      │ • Catalyst evolución     │
│                      │      │                          │
│ ENTRADA: HOY         │      │ ENTRADA: Días después    │
│ SALIDA: Hoy (EOD)    │      │ SALIDA: 3-10 días        │
│ STOP: 3-5%           │      │ STOP: 8-12%              │
└──────────────────────┘      └──────────────────────────┘
```

---

## 🏗️ Componentes Nuevos

### 1. PlaysRouter (NUEVO)

**Responsabilidad:** Decidir MODE basado en características del setup

**Ubicación sugerida:** `core/plays_router.py`

**Lógica de decisión:**

```python
class PlaysRouter:
    """
    Router que decide MODE basado en características del setup
    """

    async def route_opportunity(self, opportunity: Dict) -> Tuple[str, Dict]:
        """
        Analiza opportunity y decide routing

        Returns:
            ('INTRADAY', config) o ('DAILY', config) o ('REJECT', reason)
        """
        symbol = opportunity['symbol']

        # Análisis dual: intraday + daily
        intraday_analysis = await self.analyze_intraday_setup(opportunity)
        daily_analysis = await self.analyze_daily_setup(symbol)

        # ===== ROUTE TO INTRADAY =====
        # Si setup perfecto AHORA (75-95% completion)
        if (intraday_analysis['pattern_completion'] >= 75 and
            intraday_analysis['pattern_completion'] <= 95 and
            intraday_analysis['volume_ratio'] >= 3.0 and
            intraday_analysis['vwap_strength'] == 'bullish' and
            daily_analysis['distance_to_resistance'] > 5.0):

            return 'INTRADAY', {
                'mode': 'intraday',
                'use_intraday_filters': True,
                'use_daily_filters': False,
                'expected_hold': '2-6 hours',
                'stop_loss_pct': 4.0,
                'take_profit_pct': 15.0
            }

        # ===== ROUTE TO DAILY WATCHLIST =====
        # Si setup interesante pero NO perfecto ahora
        elif (intraday_analysis['pattern_completion'] >= 50 and
              daily_analysis['setup_quality'] >= 60 and
              (daily_analysis['near_support'] or
               daily_analysis['consolidating'] or
               daily_analysis['trend'] == 'bullish_consolidation')):

            return 'DAILY', {
                'mode': 'daily',
                'use_intraday_filters': False,
                'use_daily_filters': True,
                'watch_for': daily_analysis['trigger_conditions'],
                'best_entry': daily_analysis['optimal_entry_price'],
                'stop_loss_pct': 10.0,
                'take_profit_pct': 40.0,
                'max_watch_days': 10
            }

        # ===== REJECT =====
        else:
            return 'REJECT', {
                'reason': 'Setup no cumple criterios intraday ni daily'
            }
```

**Criterios de routing detallados:**

**INTRADAY MODE:**
- Pattern completion 75-95% (catalyst aligning ahora)
- Volume explosivo (3x+)
- Momentum claro intraday
- VWAP bullish
- Daily chart sin resistencias cercanas (>5% away)
- **Objetivo:** Capturar movimiento HOY

**DAILY MODE:**
- Pattern completion 50-75% (setup prometedor pero no perfecto)
- Daily chart favorable (consolidación, near support, trend alcista)
- Catalyst fuerte pero momentum intraday débil
- Necesita tiempo para desarrollarse (días)
- **Objetivo:** Esperar mejor punto de entrada

---

### 2. PlaysWatchlistManager (NUEVO)

**Responsabilidad:** Gestionar plays en modo DAILY que esperan setup perfecto

**Ubicación sugerida:** `core/plays_watchlist_manager.py`

**Base de datos:**

```sql
CREATE TABLE plays_watchlist (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    detected_date DATE NOT NULL,

    -- Catalyst info
    catalyst_type TEXT,
    catalyst_strength INTEGER,
    quality_score REAL,

    -- Technical analysis (daily chart)
    current_price REAL,
    support_level REAL,
    resistance_level REAL,
    daily_rsi REAL,
    daily_trend TEXT,  -- 'bullish', 'bearish', 'neutral', 'consolidation'

    -- Entry conditions
    best_entry_price REAL,
    optimal_entry_conditions TEXT,  -- JSON con criterios

    -- Status tracking
    status TEXT,  -- 'active', 'watching', 'triggered', 'dead', 'traded'
    last_evaluated DATE,
    days_tracked INTEGER,
    max_watch_days INTEGER DEFAULT 10,

    -- Alerts
    alert_conditions TEXT,  -- JSON: ['breakout_resistance', 'volume_surge', etc]
    notified_at DATETIME,

    -- Performance tracking
    entry_price REAL,
    entry_date DATE,
    exit_price REAL,
    exit_date DATE,
    pnl_pct REAL,

    UNIQUE(symbol, detected_date)
);
```

**Funciones principales:**

```python
class PlaysWatchlistManager:
    """
    Gestiona plays en modo DAILY que esperan setup perfecto
    """

    async def add_to_watchlist(self, opportunity: Dict):
        """Añade play a watchlist con análisis daily"""
        # Guardar en DB con metadata
        # Configurar alert conditions

    async def evaluate_watchlist_daily(self):
        """
        Tarea DIARIA (EOD): Re-evalúa todos los plays en watchlist

        Para cada play:
        1. Re-analizar daily chart
        2. Check si trigger conditions se cumplen
        3. Si trigger → crear opportunity MODE='daily' → Redis
        4. Si setup invalidado → marcar 'dead'
        5. Si > max_watch_days → archive
        """

    async def analyze_daily_chart(self, symbol: str) -> Dict:
        """
        Análisis técnico en daily chart

        Returns:
            {
                'trend': 'bullish' | 'bearish' | 'consolidation',
                'daily_rsi': float,
                'near_support': bool,
                'near_resistance': bool,
                'support_level': float,
                'resistance_level': float,
                'distance_to_resistance': float,
                'consolidation_days': int,
                'volume_trend': 'increasing' | 'decreasing' | 'neutral',
                'catalyst_age_days': int,
                'trigger_conditions': List[str],
                'optimal_entry_price': float,
                'setup_quality': float  # 0-100
            }
        """

    def _check_triggers(self, daily_analysis: Dict, triggers: List[str]) -> bool:
        """
        Check si condiciones de trigger se cumplen

        Triggers posibles:
        - 'breakout_resistance': Price > resistance
        - 'volume_surge': Volume > 2x average
        - 'consolidation_complete': X días sin movimiento + breakout
        - 'support_bounce': Touch support + bounce
        - 'daily_rsi_oversold': RSI < 30
        """

    async def _send_alert(self, symbol: str, analysis: Dict):
        """Enviar alerta (Telegram, log, etc)"""
```

**Proceso diario (EOD):**

```
15:45 ET - Market close
  ↓
16:00 ET - Run evaluate_watchlist_daily()
  ↓
Para cada play en watchlist:
  1. Fetch daily bars (últimos 30 días)
  2. Calcular RSI, support/resistance, trend
  3. Check trigger conditions
  4. Si TRIGGERED:
     → Crear opportunity con MODE='daily'
     → Publicar a Redis
     → Actualizar status='triggered'
  5. Si setup INVALIDADO (resistance rota a la baja, trend bajista):
     → Marcar status='dead'
  6. Si days_tracked > max_watch_days:
     → Archive play
```

---

### 3. Modificaciones a Daily Plays Worker

**Archivo:** `strategies/workers/daily_plays_worker_logic.py`

**Cambios necesarios:**

```python
class DailyPlaysWorkerLogic(BaseWorkerLogic):
    """
    Worker ahora DUAL-MODE: puede operar intraday o daily
    """

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa entrada según MODE configurado en opportunity
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        # Obtener MODE desde opportunity (configurado por Router)
        mode = opportunity.get('mode', 'intraday')  # Default intraday

        if mode == 'intraday':
            return await self._should_enter_intraday(opportunity)
        elif mode == 'daily':
            return await self._should_enter_daily(opportunity)
        else:
            self.logger.error(f"Unknown mode: {mode}")
            return False

    async def _should_enter_intraday(self, opportunity: Dict) -> bool:
        """
        INTRADAY MODE: Filtros estrictos en timeframe 1-5min

        TODOS los filtros actuales:
        - VWAP validation
        - Pattern completion 75-95%
        - RSI intraday
        - Volume spike
        - Intraday structure
        - etc.
        """
        # CÓDIGO ACTUAL DE should_enter()
        # Sin cambios

    async def _should_enter_daily(self, opportunity: Dict) -> bool:
        """
        DAILY MODE: Filtros RELAJADOS para daily chart

        NO valida:
        - VWAP intraday (irrelevante)
        - Pattern completion intraday
        - Momentum instantáneo

        SÍ valida:
        - Daily trend favorable
        - Near support/breakout level
        - Daily RSI not overbought (<70)
        - Volume trend (daily)
        - Catalyst age (<14 days)
        """
        symbol = opportunity['symbol']
        daily_analysis = opportunity.get('daily_analysis', {})

        # Check 1: Daily trend favorable
        if daily_analysis.get('trend') not in ['bullish', 'bullish_consolidation']:
            self.logger.info(f"❌ {symbol}: Daily trend not bullish")
            return False

        # Check 2: Near support or breakout level
        near_support = daily_analysis.get('near_support', False)
        near_breakout = daily_analysis.get('near_breakout', False)
        if not (near_support or near_breakout):
            self.logger.info(f"❌ {symbol}: Not at favorable entry level")
            return False

        # Check 3: Daily RSI not overbought
        daily_rsi = daily_analysis.get('daily_rsi', 50)
        if daily_rsi > 70:
            self.logger.info(f"❌ {symbol}: Daily RSI overbought ({daily_rsi})")
            return False

        # Check 4: Volume confirmation (daily)
        volume_trend = daily_analysis.get('volume_trend', 'neutral')
        if volume_trend == 'declining':
            self.logger.info(f"❌ {symbol}: Volume declining on daily")
            return False

        # Check 5: Catalyst still valid
        catalyst_age_days = daily_analysis.get('catalyst_age_days', 0)
        if catalyst_age_days > 14:
            self.logger.info(f"❌ {symbol}: Catalyst too old ({catalyst_age_days} days)")
            return False

        self.logger.info(f"✅ {symbol}: DAILY MODE entry approved")
        return True

    async def should_exit(self, symbol: str, position: Dict, current_price: float) -> Tuple[bool, str]:
        """
        Exit logic adaptado al MODE
        """
        mode = position.get('mode', 'intraday')

        if mode == 'intraday':
            # Exits actuales: TP 15-20%, SL 3-5%, Trailing, EOD
            return await self._should_exit_intraday(symbol, position, current_price)
        elif mode == 'daily':
            # Exits más amplios: TP 40%, SL 10%, Trailing 15%/8%, NO EOD
            return await self._should_exit_daily(symbol, position, current_price)
```

**Config parameters (añadir a config.ini):**

```ini
[DAILY_PLAYS_STRATEGY]
# Existing intraday params...

# DAILY MODE params
daily_mode_enabled = true
daily_stop_loss_pct = 10.0
daily_take_profit_pct = 40.0
daily_trailing_activation = 15.0
daily_trailing_distance = 8.0
daily_max_hold_days = 10
```

---

## 📊 Flujo Completo del Sistema

### Ejemplo: Ticker AAPL con catalyst

```
DÍA 0 (9:35 AM):
1. Scanner detecta AAPL:
   - Catalyst: FDA approval news
   - Price: $145
   - Volume: 1.5x average (moderado)
   - Gap: 5%

2. PlaysRouter analiza:
   - Intraday analysis:
     * Pattern completion: 45% (no ready)
     * VWAP: Price below VWAP
     * Volume: 1.5x (no explosive)
     → INTRADAY: NO ❌

   - Daily analysis:
     * Trend: Bullish consolidation (15 días)
     * RSI daily: 42 (healthy)
     * Near support: $143 (1.4% away)
     * Distance to resistance: $155 (6.9% away)
     * Catalyst: FDA approval (STRONG)
     → DAILY: YES ✅

3. Router decision: MODE='daily' → Watchlist Manager

4. Watchlist Manager:
   - Save to plays_watchlist DB
   - Configure alerts:
     * "breakout above $155"
     * "volume surge >2x"
     * "support bounce at $143"
   - Status: 'watching'

DÍA 1-2:
5. EOD evaluation (16:00 ET):
   - Day 1: AAPL @ $146, volume low, consolidating → WAIT
   - Day 2: AAPL @ $147, volume low, still consolidating → WAIT

DÍA 3 (9:45 AM):
6. EOD evaluation previous day:
   - AAPL closed @ $154, high volume surge!
   - Approaching resistance $155
   - Alert condition met: "near breakout"

7. Watchlist Manager creates opportunity:
   {
       'symbol': 'AAPL',
       'mode': 'daily',  ← IMPORTANTE
       'current_price': 154.50,
       'daily_analysis': {
           'trend': 'bullish',
           'near_breakout': True,
           'resistance_level': 155,
           'daily_rsi': 58,
           'volume_trend': 'increasing',
           'catalyst_age_days': 3
       },
       'catalyst_type': 'FDA',
       'quality_score': 85
   }

8. Publish to Redis → Daily Plays Worker

9. Daily Plays Worker receives opportunity:
   - Detects MODE='daily'
   - Calls _should_enter_daily()
   - Validations:
     ✅ Daily trend bullish
     ✅ Near breakout level
     ✅ Daily RSI 58 (not overbought)
     ✅ Volume increasing
     ✅ Catalyst age 3 days (valid)
   - ENTRY APPROVED

10. Execute entry:
    - Entry price: $154.50
    - Stop loss: 10% → $139.05
    - Take profit: 40% → $216.30
    - Trailing: activate at +15% ($177.68)
    - Max hold: 10 days

11. Position monitoring:
    - Day 3: $157 (+1.6%)
    - Day 4: $163 (+5.5%)
    - Day 5: $178 (+15.2%) → Trailing activated!
    - Day 6: $185 (+19.7%)
    - Day 7: $182 → Trailing stop hit at $177.68
    - EXIT: +15% profit ✅

12. Watchlist Manager updates:
    - Status: 'traded'
    - Entry/exit recorded for performance tracking
```

---

## 📈 Ventajas del Sistema

### 1. No Pierdes Oportunidades
- Plays que hoy no son perfectos → watchlist
- Seguimiento continuo en daily chart
- Entras cuando setup se activa (días/semanas después)
- **Ejemplo:** Catalyst día 1 → consolida 5 días → breakout día 6 ✅

### 2. Mejor Risk/Reward
- Operas desde niveles más favorables (consolidaciones, pullbacks)
- No persigues momentum intraday ya agotado
- Stops más ajustados basados en estructura daily
- Targets más ambiciosos (40% vs 15%)

### 3. Menos Estrés
- Daytrading para setups perfectos HOY
- Watchlist para setups que necesitan tiempo
- No intentas overnight ciego en smallcaps manipuladas
- Evitas FOMO en momentum parabólico

### 4. Captura Big Movers
- Smallcaps que consolidan y luego explotan días después
- Entras en mejores puntos (no en FOMO)
- **Ejemplo real:** CRBG consolidó 8 días después de news, luego +120% en 3 días

### 5. Separación de Concerns
- Intraday mode: filtros intraday (VWAP, momentum instantáneo)
- Daily mode: filtros daily (RSI daily, consolidations, structure)
- No más conflictos entre timeframes

---

## 🎯 Métricas de Performance

### Trackear por MODE

**INTRADAY MODE:**
- Win rate
- Avg profit/loss
- Avg hold time
- Avg entries/day
- Mejor horario de entrada

**DAILY MODE:**
- Win rate
- Avg profit/loss (esperado: mayor que intraday)
- Avg hold time (días)
- Avg time in watchlist before trigger
- % plays que nunca triggerean
- % plays marcados como 'dead'

### Dashboard Watchlist

Información a mostrar:
- Plays actuales en watchlist
- Días tracked
- Distancia a trigger conditions
- Daily chart mini (visual)
- Catalyst info
- Alert status

---

## 🔧 Plan de Implementación (Futuro)

### Fase 1: Infraestructura Base
1. Crear tabla `plays_watchlist` en DB
2. Implementar `PlaysRouter` (lógica básica)
3. Implementar `PlaysWatchlistManager` (add/evaluate)
4. Tests unitarios

### Fase 2: Integración con Daily Plays Worker
1. Modificar `should_enter()` para soportar MODE
2. Crear `_should_enter_daily()` con filtros relajados
3. Crear `_should_exit_daily()` con exits amplios
4. Config parameters en config.ini

### Fase 3: Proceso Diario
1. Tarea EOD: `evaluate_watchlist_daily()`
2. Análisis daily chart (RSI, support/resistance, trend)
3. Trigger detection
4. Opportunity creation y publishing a Redis

### Fase 4: Monitoring y Alertas
1. Telegram alerts cuando play triggers
2. Dashboard simple para visualizar watchlist
3. Performance tracking por MODE

### Fase 5: Optimización
1. ML para mejorar routing decisions
2. Pattern recognition en daily chart
3. Backtesting de estrategia DAILY mode

---

## 📚 Referencias

**Archivos relacionados:**
- `strategies/workers/daily_plays_worker_logic.py` - Worker actual (intraday)
- `docs/ODS_SWING_OVERNIGHT_REVIEW.md` - Análisis overnight trading
- `docs/SWING_TRADING_ANALYSIS.md` - Análisis swing vs day trading
- `core/game_plan_manager.py` - Game planning (watchlist concept similar)

**Conceptos clave:**
- Dual-mode system: Intraday vs Daily
- Watchlist management: Track plays over days
- Trigger conditions: Alert cuando setup ready
- Timeframe separation: Filtros específicos por timeframe

---

## ⚠️ Consideraciones

### Riesgos
1. **Complejidad:** Sistema más complejo de mantener
2. **Capital allocation:** Dividir capital entre intraday y daily modes
3. **Falsos triggers:** Plays que triggerean pero fallan inmediatamente
4. **Stale catalysts:** News pierde relevancia después de días

### Mitigaciones
1. Empezar simple: Router con criterios básicos
2. Paper trading primero (30 días)
3. Strict trigger conditions para reducir falsos positivos
4. Catalyst age check (max 14 días)
5. Performance tracking detallado por mode

---

## 🚀 Próximos Pasos (cuando se implemente)

1. **Revisar y aprobar arquitectura**
2. **Definir criterios exactos de routing** (intraday vs daily)
3. **Crear schema DB** (plays_watchlist)
4. **Implementar PlaysRouter** (core logic)
5. **Implementar PlaysWatchlistManager** (add/evaluate)
6. **Modificar Daily Plays Worker** (dual-mode support)
7. **Testing en paper trading** (30 días mínimo)
8. **Deploy en producción** con capital limitado
9. **Monitorear performance** y ajustar parámetros

---

**Autor:** Claude + Carlos
**Última actualización:** 2025-12-01
