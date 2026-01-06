# Swing Trading System - Architecture Documentation

## 🎯 Overview

Sistema dual de trading que integra **Day Trading (intraday)** y **Swing Trading (position)** en la misma infraestructura, permitiendo operar smallcaps con dos enfoques complementarios.

---

## 📊 Diferencias Clave: Day Trading vs Swing Trading

| Aspecto | Day Trading (Actual) | Swing Trading (Nuevo) |
|---------|---------------------|---------------------|
| **Timeframe** | 1-5 minutos | Daily/Weekly charts |
| **Holding Period** | Minutos a horas (cierre EOD) | Semanas a meses |
| **Scan Frequency** | Cada 30 segundos | 1 vez al día (15:40 ET) |
| **Patrones Buscados** | Gaps, explosiones volumen, MACD divergencias | Consolidaciones largas (semanas/meses) |
| **Tipo de Entrada** | Market/Limit inmediata | Market order al abrir (post-escaneo EOD) |
| **Stop Loss** | Ajustado 4-5% | Amplio 8-15% (bajo consolidación) |
| **Target Profit** | 10-20% | 50-200% (big runners) |
| **Max Positions** | 30 tickers | 2 tickers (best setups only) |
| **Capital Allocation** | Pequeñas posiciones ($100-200) | Posiciones mayores ($500-1000) |

---

## 🏗️ Arquitectura del Sistema

### **Estructura de Directorios**

```
trading_system_v3/
├── scanner/
│   ├── intraday/                    # Scanners actuales (30s interval)
│   │   ├── smallcap_daily_scanner.py
│   │   └── ibkr_native_scanner.py
│   └── swing/                       # NUEVO - Swing scanners (EOD)
│       ├── swing_consolidation_scanner.py
│       └── consolidation_pattern_detector.py
│
├── strategies/
│   ├── workers/                     # Day trading workers (actual)
│   │   ├── gap_go_worker_logic.py
│   │   ├── macdv_worker_logic.py
│   │   └── daily_plays_worker_logic.py
│   └── swing_workers/               # NUEVO - Swing trading workers
│       ├── base_swing_worker.py
│       └── consolidation_breakout_worker.py
│
├── core/
│   ├── execution_engine_adapter.py  # Shared (day + swing)
│   ├── risk_manager.py              # Shared (day + swing)
│   └── swing_position_manager.py    # NUEVO - Gestión posiciones swing
│
└── docs/
    └── SWING_TRADING_ARCHITECTURE.md (este archivo)
```

---

## 🔍 Swing Scanner - Consolidation Detection

### **Objetivo**
Detectar smallcaps que han consolidado durante **semanas o meses** y están cerca de un breakout potencial para capturar movimientos grandes (50-200%).

### **Criterios de Escaneo EOD (15:40 ET)**

#### **1. Filtros Básicos (Smallcap Focus)**
```python
min_price = 1.0
max_price = 15.0
min_market_cap = 10M
max_market_cap = 500M
min_avg_volume_90d = 100K shares/day
```

#### **2. Detección de Consolidación Larga**
- **Duración mínima**: 4 semanas (20 trading days)
- **Duración máxima**: 6 meses (120 trading days)
- **Rango de consolidación**:
  - High-Low < 25% del precio medio
  - Volatilidad decreciente (ATR descendente)
- **Toques de resistencia**: Mínimo 3 tests del nivel superior
- **Toques de soporte**: Mínimo 2 tests del nivel inferior
- **Volumen decreciente**: Durante consolidación (señal de compresión)

#### **3. Setup de Breakout Potencial**
- **Precio actual**: Dentro del 5% superior del rango de consolidación
- **Volumen reciente**: Incremento en últimos 3-5 días (señal de acumulación)
- **RSI**: Entre 45-65 (no sobrecomprado, con momentum)
- **MACD**: Cruce alcista o cerca de cruce
- **Patrón técnico**:
  - Triángulo ascendente
  - Cup & Handle
  - Bull flag (weekly)
  - Flat base

#### **4. Contexto Fundamental (Opcional)**
- **News catalyst**: Earnings próximos, FDA approval pending, etc.
- **Sector strength**: Sector en tendencia alcista
- **Insider buying**: Compras recientes de insiders
- **Short interest**: >10% (potencial short squeeze)

### **Output del Scanner**
```python
{
    'symbol': 'ABCD',
    'pattern': 'ASCENDING_TRIANGLE',
    'consolidation_days': 45,
    'resistance': 8.50,
    'support': 6.20,
    'current_price': 8.35,
    'distance_to_resistance': 1.8%,
    'volume_compression': 0.65,  # 65% of avg during consolidation
    'breakout_score': 85,  # 0-100 composite score
    'risk_reward_ratio': 3.5,  # (target - entry) / (entry - stop)
    'catalyst': 'Earnings in 2 weeks',
    'scan_time': '2025-10-04 15:40:00'
}
```

---

## 📈 Swing Workers - Consolidation Breakout Strategy

### **ConsolidationBreakoutWorker**

#### **Entry Logic (Ejecutado Next Day Market Open)**
```python
# Triggered at market open (9:30 ET) if swing scanner detectó setup EOD anterior

def should_enter(self, opportunity):
    """
    Evalúa si entrar en breakout de consolidación
    """
    # 1. Pre-market gap check
    premarket_gap = self.get_premarket_gap(symbol)
    if premarket_gap > 5%:
        # Gap demasiado grande, esperar pullback
        return False

    # 2. Opening price validation
    open_price = self.get_opening_price(symbol)
    if open_price < opportunity['support']:
        # Abrió bajo soporte, invalidado
        return False

    # 3. Opening volume confirmation
    opening_volume = self.get_opening_volume(symbol, bars=5)
    avg_volume = opportunity['avg_volume_90d']
    if opening_volume < avg_volume * 1.5:
        # Sin volumen, no hay convicción
        return False

    # 4. Price action first 5 minutes
    if self.detect_strong_selling_pressure(symbol):
        # Distribution, no acumulación
        return False

    # ALL CHECKS PASSED
    return True

def execute_entry(self, symbol, opportunity):
    """
    Entrada a mercado en market open
    """
    entry_price = self.get_current_price(symbol)

    # Calculate position size (swing = larger positions)
    position_size = self.calculate_swing_position_size(
        symbol=symbol,
        entry_price=entry_price,
        stop_loss=opportunity['support'] * 0.995,  # -0.5% bajo soporte
        risk_per_trade=0.02  # 2% del capital total
    )

    # Market order (demo no permite pre/after market)
    order = Order(
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=position_size,
        order_type=OrderType.MARKET
    )

    # Execute via ExecutionEngineAdapter (shared)
    trade = await self.execution_engine.enter_position(
        symbol=symbol,
        strategy='swing_consolidation_breakout',
        opportunity_data=opportunity
    )

    return trade
```

#### **Exit Logic (Swing Management)**
```python
def should_exit(self, position):
    """
    Lógica de salida para swing trades
    Mucho más permisiva que day trading
    """
    symbol = position['symbol']
    entry_price = position['entry_price']
    current_price = self.get_current_price(symbol)
    pnl_pct = ((current_price - entry_price) / entry_price) * 100

    # PRIORITY 1: Stop Loss (bajo consolidación)
    stop_loss = position['opportunity_data']['support'] * 0.995
    if current_price <= stop_loss:
        return True, f"STOP_LOSS (PnL: {pnl_pct:.2f}%)"

    # PRIORITY 2: Time-based stop (máximo 3 meses)
    days_held = (datetime.now() - position['entry_time']).days
    if days_held >= 90:
        return True, f"MAX_HOLD_TIME (PnL: {pnl_pct:.2f}%)"

    # PRIORITY 3: Trailing stop (activa a +15%)
    if pnl_pct >= 15.0:
        trailing_stop = self.calculate_trailing_stop(
            symbol=symbol,
            entry_price=entry_price,
            current_price=current_price,
            activation_pct=15.0,
            trail_distance_pct=8.0  # Trail 8% below peak
        )
        if current_price <= trailing_stop:
            return True, f"TRAILING_STOP (PnL: {pnl_pct:.2f}%)"

    # PRIORITY 4: Target profit (50% mínimo, hasta 200%)
    target_profit = position['opportunity_data'].get('target_profit', 50.0)
    if pnl_pct >= target_profit:
        return True, f"TARGET_PROFIT (PnL: {pnl_pct:.2f}%)"

    # PRIORITY 5: Patrón de distribución detectado
    if self.detect_distribution_pattern(symbol):
        if pnl_pct > 10.0:  # Solo si ya ganaste algo
            return True, f"DISTRIBUTION_DETECTED (PnL: {pnl_pct:.2f}%)"

    # HOLD - Swing trades necesitan tiempo
    return False, None
```

---

## 🚫 Gestión de Duplicados

### **Problema: Overlapping Positions**

Necesitamos prevenir:
1. **Duplicado intraday**: Day trader y swing trader comprando mismo ticker
2. **Duplicado swing-swing**: Mismo ticker seleccionado dos días consecutivos
3. **Conflicto de capital**: No tener suficiente capital para ambas operativas

### **Solución: Unified Position Registry**

#### **1. Registro Centralizado**
```python
# core/unified_position_manager.py

class UnifiedPositionManager:
    """
    Gestiona TODAS las posiciones (day + swing) para evitar duplicados
    """

    def __init__(self):
        self.day_positions = {}   # {symbol: position_data}
        self.swing_positions = {} # {symbol: position_data}
        self.reserved_capital = {'day': 0.0, 'swing': 0.0}

    def can_open_position(self, symbol: str, strategy_type: str) -> bool:
        """
        Verifica si se puede abrir posición sin duplicar

        Args:
            symbol: Ticker a operar
            strategy_type: 'day' o 'swing'

        Returns:
            True si NO hay conflicto
        """
        # Check 1: ¿Ya existe posición day?
        if symbol in self.day_positions:
            self.logger.warning(f"⚠️ {symbol} already held in day trading")
            return False

        # Check 2: ¿Ya existe posición swing?
        if symbol in self.swing_positions:
            self.logger.warning(f"⚠️ {symbol} already held in swing trading")
            return False

        # Check 3: ¿Hay capital disponible?
        available_capital = self.get_available_capital(strategy_type)
        if available_capital < self.get_min_position_value(strategy_type):
            self.logger.warning(f"⚠️ Insufficient capital for {strategy_type}")
            return False

        return True

    def reserve_position(self, symbol: str, strategy_type: str, capital: float):
        """Reserva posición y capital"""
        if strategy_type == 'day':
            self.day_positions[symbol] = {'reserved': True, 'capital': capital}
        else:
            self.swing_positions[symbol] = {'reserved': True, 'capital': capital}

        self.reserved_capital[strategy_type] += capital
```

#### **2. Integration en Workers**

**Day Workers** (gap_go, macdv, etc.):
```python
# strategies/workers/gap_go_worker_logic.py

async def process_opportunity(self, opportunity):
    symbol = opportunity['symbol']

    # CHECK DUPLICADOS ANTES DE EVALUAR
    if not self.unified_manager.can_open_position(symbol, 'day'):
        self.logger.info(f"⚪ {symbol}: Blocked (swing position exists or capital limit)")
        return False

    # ... resto de lógica actual
```

**Swing Workers**:
```python
# strategies/swing_workers/consolidation_breakout_worker.py

async def process_opportunity(self, opportunity):
    symbol = opportunity['symbol']

    # CHECK DUPLICADOS ANTES DE EVALUAR
    if not self.unified_manager.can_open_position(symbol, 'swing'):
        self.logger.info(f"⚪ {symbol}: Blocked (day position exists or capital limit)")
        return False

    # ... lógica de entrada
```

#### **3. Prevención Swing-Swing (Mismo Ticker Días Consecutivos)**

```python
# scanner/swing/swing_consolidation_scanner.py

class SwingConsolidationScanner:

    def __init__(self):
        self.recent_swing_picks = {}  # {symbol: last_pick_date}
        self.cooldown_days = 5  # No repetir mismo ticker en 5 días

    def filter_recent_picks(self, candidates: List[Dict]) -> List[Dict]:
        """
        Filtra tickers que ya fueron seleccionados recientemente
        """
        today = datetime.now().date()
        filtered = []

        for candidate in candidates:
            symbol = candidate['symbol']

            # Check si fue pickeado recientemente
            if symbol in self.recent_swing_picks:
                last_pick = self.recent_swing_picks[symbol]
                days_since = (today - last_pick).days

                if days_since < self.cooldown_days:
                    self.logger.info(
                        f"⚪ {symbol}: Skipped (picked {days_since} days ago, "
                        f"cooldown: {self.cooldown_days} days)"
                    )
                    continue

            filtered.append(candidate)

        return filtered

    def select_top_2_setups(self, candidates: List[Dict]) -> List[Dict]:
        """
        Selecciona los 2 mejores setups del día
        """
        # Filter recientes
        available = self.filter_recent_picks(candidates)

        # Sort by breakout_score (higher = better)
        sorted_candidates = sorted(
            available,
            key=lambda x: x['breakout_score'],
            reverse=True
        )

        # Take top 2
        top_2 = sorted_candidates[:2]

        # Register picks
        today = datetime.now().date()
        for pick in top_2:
            self.recent_swing_picks[pick['symbol']] = today

        self.logger.info(f"✅ Selected TOP 2 swing setups: {[p['symbol'] for p in top_2]}")

        return top_2
```

---

## 💰 Capital Allocation

### **Portfolio Segmentation**

```python
# config.ini

[SWING_TRADING]
enabled = true
max_swing_positions = 2
swing_capital_percentage = 0.70  # 70% del capital total para swing
min_swing_position_value = 500.0
max_swing_position_value = 1000.0
risk_per_swing_trade = 0.02  # 2% riesgo por trade
scan_time = 15:40  # EOD scan time (ET)

[DAY_TRADING]
enabled = true
max_day_positions = 30
day_capital_percentage = 0.30  # 30% del capital para day trading
min_day_position_value = 50.0
max_day_position_value = 200.0
risk_per_day_trade = 0.012  # 1.2% riesgo por trade
```

### **Ejemplo con $2000 Portfolio**

| Type | Capital | Max Positions | Position Size | Risk/Trade |
|------|---------|---------------|---------------|------------|
| **Swing** | $1400 (70%) | 2 | $500-1000 | $28 (2%) |
| **Day** | $600 (30%) | 5-10 activas | $100-200 | $7.2 (1.2%) |

**Ventajas**:
- Swing captura big moves (50-200%)
- Day aprovecha volatilidad intraday (10-20%)
- Capital dedicado previene overleveraging
- Risk management separado y controlado

---

## ⏰ Execution Schedule

### **Daily Workflow**

```
09:30 ET - Market Open
├─ Swing Workers: Check if yesterday's EOD picks triggered
│  ├─ Execute market orders for top 2 picks (if conditions met)
│  └─ Monitor first 5-10 minutes for confirmation
│
├─ Day Trading: Business as usual
│  └─ Scan every 30s, enter/exit intraday
│
15:30 ET - Pre-EOD Window
├─ Day Trading: Start closing positions (end_of_day_exit_time)
│
15:40 ET - Swing Scanner Execution
├─ Swing Scanner: Analyze daily charts
│  ├─ Detect consolidations (4 weeks - 6 months)
│  ├─ Score breakout setups (0-100)
│  ├─ Filter recent picks (cooldown)
│  ├─ Select TOP 2 setups
│  └─ Save to database for next day execution
│
15:58 ET - EOD Close
├─ Day positions: Force close all remaining
├─ Swing positions: HOLD (can be held weeks/months)
│
16:00 ET - Market Close
└─ Generate daily report:
   ├─ Day trading: PnL, win rate, trades executed
   └─ Swing: Pending picks for tomorrow, open positions status
```

---

## 📊 Database Schema

### **Swing Trades Table**

```sql
CREATE TABLE swing_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    strategy TEXT DEFAULT 'swing_consolidation_breakout',

    -- Entry
    scan_date DATE NOT NULL,           -- Día que fue detectado
    entry_date DATE,                   -- Día que entró (puede ser NULL si no ejecutó)
    entry_price REAL,
    quantity INTEGER,
    entry_commission REAL,

    -- Setup details
    consolidation_days INTEGER,
    resistance_level REAL,
    support_level REAL,
    breakout_score REAL,
    pattern_type TEXT,

    -- Exit
    exit_date DATE,
    exit_price REAL,
    exit_commission REAL,
    exit_reason TEXT,

    -- Performance
    pnl_gross REAL,
    pnl_net REAL,
    pnl_percentage REAL,
    days_held INTEGER,

    status TEXT DEFAULT 'PENDING',  -- PENDING, OPEN, CLOSED, CANCELLED

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_swing_symbol ON swing_trades(symbol);
CREATE INDEX idx_swing_status ON swing_trades(status);
CREATE INDEX idx_swing_scan_date ON swing_trades(scan_date);
```

### **Swing Picks Cache (Evitar Duplicados)**

```sql
CREATE TABLE swing_picks_cache (
    symbol TEXT PRIMARY KEY,
    last_pick_date DATE NOT NULL,
    pick_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔧 Configuration (config.ini)

```ini
[SWING_TRADING]
# Enable/disable swing trading module
enabled = true

# Position limits
max_swing_positions = 2
min_swing_position_value = 500.0
max_swing_position_value = 1000.0

# Capital allocation
swing_capital_percentage = 0.70  # 70% of total capital

# Risk management
risk_per_swing_trade = 0.02  # 2% risk per trade
max_swing_stop_loss_pct = 0.15  # 15% max stop loss
min_risk_reward_ratio = 2.0  # Minimum 2:1 R:R

# Scanner configuration
scan_time = 15:40  # EOD scan time (ET)
min_consolidation_days = 20  # 4 weeks minimum
max_consolidation_days = 120  # 6 months maximum
min_breakout_score = 70  # 0-100 scale
cooldown_days = 5  # Don't re-pick same symbol for N days

# Entry filters
max_premarket_gap_pct = 5.0  # Skip if gap > 5%
min_opening_volume_ratio = 1.5  # Opening volume vs avg
entry_confirmation_minutes = 5  # Wait N minutes after open

# Exit parameters
target_profit_pct = 50.0  # Minimum target profit
trailing_stop_activation_pct = 15.0  # Activate trailing at +15%
trailing_stop_distance_pct = 8.0  # Trail 8% below peak
max_hold_days = 90  # Maximum 3 months hold

# Pattern detection
enable_triangle_detection = true
enable_cup_handle_detection = true
enable_bull_flag_detection = true
enable_flat_base_detection = true

# Fundamental filters (optional)
require_catalyst = false
min_short_interest_pct = 0.0  # 0 = disabled
check_insider_buying = false
```

---

## 🚀 Implementation Phases

### **Phase 1: Core Infrastructure (Week 1)**
- [ ] Create `swing/` directory structure
- [ ] Implement `SwingConsolidationScanner`
- [ ] Implement `ConsolidationPatternDetector` (TA-Lib integration)
- [ ] Create database tables (`swing_trades`, `swing_picks_cache`)
- [ ] Add `[SWING_TRADING]` section to config.ini

### **Phase 2: Position Management (Week 2)**
- [ ] Implement `UnifiedPositionManager` (prevent duplicates)
- [ ] Create `SwingPositionManager` (manage swing trades lifecycle)
- [ ] Integrate duplicate checks in day trading workers
- [ ] Capital allocation logic (70/30 split)

### **Phase 3: Workers & Execution (Week 3)**
- [ ] Implement `BaseSwingWorker`
- [ ] Implement `ConsolidationBreakoutWorker`
- [ ] Integration with `ExecutionEngineAdapter` (shared)
- [ ] Entry logic at market open (post-EOD scan)
- [ ] Exit logic (stop loss, trailing, time-based)

### **Phase 4: Scheduling & Automation (Week 4)**
- [ ] EOD scanner scheduler (15:40 ET daily)
- [ ] Market open execution trigger (9:30 ET)
- [ ] Daily report generation
- [ ] Telegram notifications (swing picks, entries, exits)

### **Phase 5: Testing & Refinement (Week 5)**
- [ ] Backtest on historical data (6 months)
- [ ] Paper trading validation (2 weeks)
- [ ] Performance metrics tracking
- [ ] Documentation updates

---

## 📈 Expected Performance

### **Swing Trading Targets**

| Metric | Conservative | Realistic | Optimistic |
|--------|-------------|-----------|------------|
| **Win Rate** | 40% | 50% | 60% |
| **Avg Winner** | +40% | +60% | +100% |
| **Avg Loser** | -10% | -8% | -6% |
| **Risk:Reward** | 2:1 | 3:1 | 5:1 |
| **Trades/Month** | 4-6 | 6-8 | 8-10 |
| **Monthly Return** | +8% | +12% | +20% |

### **Combined System (Day + Swing)**

Con **$2000 portfolio**:
- **Day Trading** ($600): +5-10% monthly (conservador)
- **Swing Trading** ($1400): +10-15% monthly (captando runners)
- **Combined**: +12-20% monthly potencial

**Ventaja clave**: Swing captura los big moves que day trading no puede sostener overnight.

---

## 🎓 Learning Resources

### **Consolidation Patterns Study**
- **Cup & Handle**: William O'Neil (CANSLIM)
- **Flat Base**: Mark Minervini (SEPA)
- **VCP (Volatility Contraction Pattern)**: Mark Minervini
- **Darvas Box**: Nicolas Darvas

### **Recommended Reading**
1. "How to Make Money in Stocks" - William O'Neil
2. "Trade Like a Stock Market Wizard" - Mark Minervini
3. "Think & Trade Like a Champion" - Mark Minervini
4. "The Darvas System" - Nicolas Darvas

---

## 📝 Notes & Considerations

### **Why Market Orders (vs Limit Orders)?**
- **Demo limitation**: TWS demo no permite pre/after market
- **Simplicity**: Menos complejidad técnica (no gestionar GTC orders)
- **Execution certainty**: Market order garantiza entrada
- **Trade-off**: Posible slippage (1-2%), aceptable en smallcaps volátiles

### **Why Top 2 Only?**
- **Quality over quantity**: Forzar selectividad
- **Capital concentration**: Posiciones significativas ($500-1000)
- **Gestión manejable**: Fácil monitorear 2 posiciones swing
- **Evitar dilución**: Mejor 2 setups A+ que 10 setups B

### **Risk Management Philosophy**
- **Swing = Mayor riesgo, Mayor reward**
- **Stop loss amplio**: Permite breathing room (8-15%)
- **Time-based stop**: Máximo 3 meses (evitar dead money)
- **Trailing stop agresivo**: Proteger ganancias a +15%

---

## 🔄 Future Enhancements

### **Possible Additions (Post-MVP)**
1. **Sector Rotation**: Preferir sectores en tendencia alcista
2. **Earnings Calendar**: Evitar/buscar earnings plays
3. **Short Squeeze Scanner**: Priorizar high short interest
4. **Multiple Timeframes**: Analizar weekly + monthly confirmación
5. **Machine Learning**: Scoring automático de patrones
6. **Position Pyramiding**: Agregar a posiciones ganadoras
7. **Swing Hedge**: Short positions en bear markets

---

## 📞 Contact & Support

**Document Version**: 1.0
**Last Updated**: 2025-10-04
**Author**: Trading System Architecture Team
**Status**: Design Phase - Pending Implementation

---

## ✅ Approval Checklist

- [ ] Architecture reviewed and approved
- [ ] Database schema validated
- [ ] Risk management parameters confirmed
- [ ] Capital allocation percentages agreed
- [ ] Scanner criteria finalized
- [ ] Worker logic validated
- [ ] Duplicate prevention strategy approved
- [ ] Ready for Phase 1 implementation

---

**Next Steps**: Review this document, suggest modifications, then proceed with Phase 1 implementation.


-----



✅ Phase 1 del Swing Trading System - COMPLETADA!
Hemos implementado con éxito la infraestructura core del sistema swing trading:
✅ Lo que hemos logrado:
Estructura de directorios ✅
scanner/swing/ - Escáneres EOD
strategies/swing_workers/ - Workers de swing trading
Base de datos ✅
Tabla swing_trades - Trades de posición (días/semanas)
Tabla swing_picks_cache - Evita duplicados (cooldown 5 días)
Índices optimizados para queries rápidas
Configuración ✅
Sección [SWING_TRADING] en config.ini
Distribución capital: 40% swing ($800), 60% day ($1,200)
Posiciones swing: $300-400 cada una (máx 2)
Parámetros: Stop 15%, Target 50%, Trailing 15%/8%
SwingConsolidationScanner ✅
Escaneo EOD a las 15:40 ET (21:40 España)
Carga configuración desde config.ini
Sistema de cooldown (5 días)
Selección top 2 setups por breakout score
Guardado en base de datos para ejecución mañana
📋 Próximos pasos (Phase 2-5):
Phase 2: Pattern Detection
Implementar ConsolidationPatternDetector
Detección de consolidaciones (20-120 días)
Identificar patrones (triángulos, cup & handle, etc.)
Calcular breakout scores
Phase 3: Position Management
UnifiedPositionManager (prevenir duplicados day/swing)
Capital allocation logic (40/60 split)
Phase 4: Swing Workers
BaseSwingWorker
ConsolidationBreakoutWorker
Entry/exit logic
Phase 5: Integration & Testing
Integrar con scanner_main.py (EOD execution)
Integrar con trader_main.py (market open execution)
Testing & refinamiento



✅ Phase 2 COMPLETADA - Con Estrategia Mejorada!
📊 Lo implementado:
ConsolidationPatternDetector con DUAL ENTRY MODES (Breakout vs Pullback):
🎯 Modo 1: BREAKOUT Entry (Gap pequeño <3%)
Entry al market open si NO hay gap grande
Confirmación:
Volumen fuerte primeros 5 minutos
Precio mantiene sobre resistencia
Patrón intacto
Risk: Menor (entrada controlada)
Reward: Captura todo el movimiento
🎯 Modo 2: PULLBACK Entry (Gap grande >5%) ⭐ TU SUGERENCIA
Si gap premarket >5% → NO entrar al open
Esperar retroceso a antigua resistencia (ahora soporte)
Confirmación triple:
MACDV: Divergencia alcista o cruce bullish
RSI: Oversold (<40) + rebote
Volume: Aumentando en el bounce
Entry: Limit order en zona soporte
Ventajas:
✅ Mejor precio entrada (no compras el top)
✅ Stop más ajustado (bajo soporte)
✅ R:R superior (3:1 o mejor)
✅ Evita FOMO de premarket gap
📈 Características del detector:
Consolidación detection (20-120 días)
Pattern recognition:
Ascending Triangle (mejor bullish)
Bull Flag
Flat Base
Cup & Handle
Breakout scoring (0-100):
Calidad patrón (25pts)
Compresión volumen (20pts)
Duración óptima (20pts)
Proximidad resistencia (20pts)
Toques soporte/resistencia (15pts)
Pullback levels calculator:
Primary entry (antigua resistencia)
Secondary entry (Fibonacci 50%)
Stop loss (2% bajo soporte)
Target (50% upside)
🔧 Configuración agregada:
# Dual entry modes
max_safe_gap_pct = 3.0              # <3% = BREAKOUT mode
max_dangerous_gap_pct = 5.0         # >5% = PULLBACK mode

# Pullback confirmation
enable_macdv_pullback_confirmation = true
pullback_rsi_oversold = 40.0
pullback_min_volume_ratio = 1.2
💡 Ejemplo de uso:
Escenario: Scanner detecta ABCD en consolidación 45 días EOD (15:40):
Patrón: Ascending Triangle
Breakout score: 85/100
Current: $8.50, Resistance: $9.00
Entry mode: PULLBACK (volumen surge últimos días)
Next Day:
Premarket gap +8% → $9.18
Sistema decide: WAIT FOR PULLBACK
Durante el día:
Pullback a $8.95 (antigua resistencia)
MACDV: Bullish cross
RSI: 38 (oversold) → rebote a 45
Volume: Aumentando
Entry: $8.97 (limit order)
Stop: $8.25 (2% bajo soporte $8.40)
Target: $13.50 (50% upside)
R:R: 6.5:1 🎯
¿Quieres que continuemos con Phase 3 (UnifiedPositionManager para prevenir duplicados) o prefieres hacer algún ajuste a lo implementado?


----



✅ Phase 4 completado! He implementado el sistema completo de swing trading workers: 1. BaseSwingWorker (base_swing_worker.py):
Clase base para todos los swing workers
Posiciones $300-400 (vs $100-200 day trading)
Máximo 2 posiciones swing simultáneas
Integración con UnifiedPositionManager
Gestión completa de entrada/salida
2. ConsolidationBreakoutWorker (consolidation_breakout_worker.py): Dual Entry Modes (tu mejora clave):
BREAKOUT: Gap <3% → entrada market open (9:30-9:45 AM)
PULLBACK: Gap >5% → espera retroceso con MACDV + RSI <40
BREAKOUT logic (9:30-9:45 AM):
Gap <3% (movimiento controlado)
Volumen >1.5x confirmación
Entrada inmediata market order
PULLBACK logic (horario regular):
Precio retrocede a resistencia anterior (ahora soporte)
MACDV bullish + RSI <40 (oversold)
Volumen >1.2x confirmación
Entrada limit order
Exit strategy:
Stop loss: 10% bajo soporte
Target: 50% ganancia
Trailing stop: activa a 15%, trail 8%
Time-based: salida a 30 días

-----


¡Tienes toda la razón! Me confundí. Déjame corregir:
📊 DAY TRADING - Rangos y Patrones
Rango de precios: $1 - $15 (todos los workers)
Patrones que REALMENTE busca cada worker:
1. GAP-GO: Gap ≥8% + PMH Breakout 2. MACDV: MACD Bullish Divergence (gap <5%) 3. BULL FLAG: Pattern intraday (flagpole + flag + breakout) 4. DAILY PLAYS: Catalyst-driven + First 30min breakout + Reversal
🏛️ SWING TRADING - Patrones DIFERENTES
Ahora déjame mostrarte los patrones de CONSOLIDACIÓN que el swing scanner está SUPUESTO a detectar:
Read consolidation_pattern_detector.py (lines 2-101)
Read consolidation_pattern_detector.py (lines 201-300)
Perfecto! Ahora sí está claro. Aquí la distinción correcta:
🏛️ SWING TRADING - Patrones de CONSOLIDACIÓN (20-120 días)
Rango de precios: NO especificado aún
El scanner swing NO tiene límites de precio definidos actualmente. ¿Quieres que use el mismo rango $1-$15 o prefieres otro rango para swing?
Patrones que detecta (DAILY timeframe):
1. ASCENDING TRIANGLE ⬆️📐
Características:
- Lows subiendo (higher lows)
- Resistance plana (flat ceiling)
- Duración: 20-120 días
- Breakout alcista probable

Puntuación: 25/25 pts (MEJOR patrón bullish)

Ejemplo visual:
      Resistance ─────────────────
    /     /       /         /
   /     /       /         /  ← Higher lows
  /     /       /         /
 /     /       /         /
Support
2. BULL FLAG 🚩
Características:
- Ambos (highs y lows) declinando levemente
- Después de movimiento fuerte previo
- Consolidación ordenada
- Continuación alcista

Puntuación: 22/25 pts

Ejemplo visual:
      \  \  \  \    ← Slight decline
       \  \  \  \
        ──────────  ← Tight range
3. FLAT BASE ━━━
Características:
- Highs y lows planos
- Rango horizontal estricto
- Consolidación limpia
- Base sólida para breakout

Puntuación: 20/25 pts

Ejemplo visual:
─────────────────── ← Flat resistance
                     
─────────────────── ← Flat support
4. CUP & HANDLE ☕
Características:
- Forma de U (cup)
- Handle (pequeña consolidación)
- Patrón más largo
- Breakout fuerte esperado

Puntuación: 23/25 pts

Ejemplo visual:
\               / \  ← Handle
 \             /
  \___________/  ← Cup (U-shape)
5. DESCENDING TRIANGLE ⬇️📐
Características:
- Highs bajando (lower highs)
- Support plano
- Patrón más débil
- Menos preferido

Puntuación: 15/25 pts (MENOS deseable)

Ejemplo visual:
\     \       \         \
 \     \       \         \  ← Lower highs
  \     \       \         \
Support ─────────────────────
Sistema de Puntuación de Breakout (0-100)
El scanner calcula un Breakout Score basado en:
Pattern Quality (25 pts):
Ascending Triangle: 25 pts ⭐
Cup & Handle: 23 pts
Bull Flag: 22 pts
Flat Base: 20 pts
Descending Triangle: 15 pts
Volume Compression (20 pts):
Ideal: 0.5-0.7 ratio = 20 pts
Volumen late = 50-70% del volumen early
Menos compresión = menos puntos
Consolidation Duration (20 pts):
60-90 días = 20 pts (óptimo)
30-60 días = 15 pts
20-30 días = 10 pts
90 días = 5 pts
Proximity to Resistance (20 pts):
<1% de resistencia = 20 pts
1-2% = 15 pts
2-3% = 10 pts
3-5% = 5 pts
Support/Resistance Touches (15 pts):
5+ touches = 15 pts
4 touches = 12 pts
3 touches = 9 pts
2 touches = 6 pts
Mínimo para considerar: 70/100 pts
Criterios de Consolidación:
min_consolidation_days = 20    # 4 semanas mínimo
max_consolidation_days = 120   # 6 meses máximo
max_range_pct = 25%            # Rango máximo 25%
min_resistance_touches = 3     # Al menos 3 toques
min_support_touches = 2        # Al menos 2 toques
Diferencias Clave vs Day Trading:
Aspecto	Day Trading	Swing Trading
Timeframe	Minutos/Horas	Semanas/Meses
Datos	Barras 1-min	Barras diarias
Patrones	Intraday (PMH, MACDV, flags intraday)	Consolidación larga (20-120 días)
Duración hold	Horas (máx 8h)	Días/Semanas (máx 30 días)
Stops	Ajustados (3-5%)	Amplios (10%)
Targets	Moderados (10-20%)	Grandes (50%)
Preguntas para ajustar:
¿Qué rango de precios quieres para swing?
Opción A: Mismo que day trading ($1-$15)
Opción B: Rango diferente (ej: $5-$50 para stocks más grandes)
Opción C: Sin límite de precio
¿Algún patrón que quieras eliminar o priorizar?
Actualmente todos están implementados
Podemos desactivar Descending Triangle si lo consideras débil
¿Score mínimo 70/100 está bien o quieres ser más/menos estricto?


------


¡Excelente pregunta! Déjame explicarte la diferencia fundamental:
¿Por qué Day Trading NECESITA múltiples workers pero Swing NO?
DAY TRADING - Múltiples Workers NECESARIOS 🔴
Razón: Cada patrón tiene LÓGICA DE DETECCIÓN COMPLETAMENTE DIFERENTE 1. Gap-Go Worker:
# Detecta PMH (Premarket High) en tiempo real
- Calcula PMH de barras 4:00-9:30 AM
- Detecta consolidación bajo PMH (15 min)
- Detecta breakout de PMH con volumen
- Lógica intraday compleja
2. MACDV Worker:
# Calcula MACD en tiempo real y busca divergencias
- Calcula EMA(12), EMA(26), MACD line, Signal line
- Compara precio vs MACDV para divergencias
- Busca oversold (RSI < 40)
- Solo opera 12:00-15:45 PM
3. Bull Flag Worker:
# Máquina de estados para detectar pattern intraday
- State: SCANNING → POLE → FLAG → BREAKOUT
- Detecta flagpole (30-60% en 5-30 min)
- Detecta flag (consolidación 5-20%)
- Detecta breakout con volumen
4. Daily Plays Worker:
# Lee noticias y detecta catalysts
- Busca FDA, M&A, EARNINGS en news
- Detecta first 30-min high breakout
- Detecta 6 señales de reversión
- Lógica multi-modal
Cada uno tiene CÓDIGO DIFERENTE para DETECTAR el patrón.
SWING TRADING - Un Solo Worker SUFICIENTE 🟢
Razón: El SCANNER ya hizo todo el trabajo de detección Flujo:
┌─────────────────────────────────────────────────┐
│  EOD SCANNER (15:40 ET)                         │
│  - Descarga 120 días de datos DAILY             │
│  - ConsolidationPatternDetector:                │
│    ✓ Detecta consolidación (20-120 días)       │
│    ✓ Identifica tipo: Triangle/Cup/Flag/Base   │
│    ✓ Calcula resistance/support                │
│    ✓ Calcula breakout score (0-100)            │
│    ✓ Determina entry_mode (BREAKOUT/PULLBACK)  │
│  - Guarda en database                           │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  WORKER (next day)                              │
│  - Lee pick de database                         │
│  - Ya sabe:                                     │
│    • Tipo de patrón                             │
│    • Resistance level                           │
│    • Support level                              │
│    • Entry mode (BREAKOUT/PULLBACK)             │
│  - Solo necesita:                               │
│    ✓ Esperar entry mode trigger                │
│    ✓ Ejecutar orden                             │
│    ✓ Monitorear exits                           │
└─────────────────────────────────────────────────┘
El worker NO necesita detectar el patrón, solo ejecutar y monitorear.
Comparación:
Aspecto	Day Trading	Swing Trading
¿Quién detecta el patrón?	Worker en tiempo real	Scanner EOD (offline)
Complejidad de detección	Alta (intraday)	Baja (ya detectado)
Datos necesarios	Stream 1-min en vivo	Daily bars pre-cargados
Velocidad requerida	Milisegundos	Horas
Lógica diferente por patrón?	✅ SÍ (PMH vs MACD vs Flag)	❌ NO (todos igual)
¿Entry/Exit difieren por patrón swing?
Actualmente NO, todos usan: Entry:
BREAKOUT mode: Market open si gap <3%
PULLBACK mode: Pullback + MACDV + RSI <40
Exit:
Stop: 10% bajo support
Target: 50% ganancia
Trailing: 15% activation, 8% trail
Time: 30 días
PERO podríamos hacerlo más específico:
Ejemplo - Si quisieras workers específicos:
AscendingTriangleWorker:
# Target específico para triángulo
triangle_height = resistance - support
target = resistance + triangle_height  # Proyección

# Stop específico
stop = support * 0.98  # 2% bajo support (menos agresivo)

# Entry más agresivo
entry_mode = 'BREAKOUT'  # Siempre breakout para triángulos
CupHandleWorker:
# Target basado en profundidad del cup
cup_depth = cup_high - cup_low
target = breakout_point + cup_depth  # Proyección clásica

# Stop en handle low
stop = handle_low * 0.97

# Entry más conservador
entry_mode = 'PULLBACK'  # Esperar pullback después de breakout inicial
Entonces, ¿necesitas workers específicos por patrón?
Opción A - Mantener 1 worker (ACTUAL): ✅ Simple, funcional
Pro: Menos código, más fácil mantener
Pro: Scanner ya hace el trabajo duro
Con: No aprovecha características únicas de cada patrón
Opción B - Crear workers específicos: 🔧 Más optimizado
Pro: Target/stops ajustados al patrón
Pro: Entry timing específico
Con: Más código, más complejidad
¿Qué prefieres? Si quieres workers específicos, puedo implementarlos rápidamente usando el patrón base que ya existe.