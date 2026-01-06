# TIER 1 FEATURES - IMPLEMENTATION PLAN
## TradeTally Advanced Analytics for Algorithmic Trading

**Date:** 2025-11-29
**Objective:** Transform TradeTally into the best journal for algorithmic stock traders

---

## CURRENT STATE ANALYSIS

### ✅ Strong Foundation
- **Architecture:** Hybrid SQLite + PostgreSQL (excellent for performance)
- **Tech Stack:** Vue 3 + Tailwind CSS, Node.js/Express, PM2 multi-instance
- **Data Coverage:** Comprehensive trade fields (MAE, MFE, confidence, ML metrics, sector, etc.)
- **AI Integration:** Google Gemini already integrated
- **Basic Analytics:** Win rate, profit factor, Sharpe, symbol stats, day-of-week, hold time
- **Edge Discovery Service:** Basic correlation analysis exists

### ❌ Critical Gaps for Algorithmic Trading
1. **No multidimensional analysis** - Cannot cross multiple dimensions dynamically
2. **No AI pattern detection** - Gemini is used for recommendations, not pattern mining
3. **No custom metrics** - All metrics are hardcoded
4. **Limited filtering** - Simple AND conditions only, no complex queries

---

## TIER 1 FEATURES (4 GAME CHANGERS)

### 1. PIVOT GRID / DYNAMIC ANALYSIS TABLE ⭐⭐⭐⭐⭐
**Priority:** HIGHEST
**Impact:** MAXIMUM - Unlocks hidden edges in your system
**Complexity:** MEDIUM-HIGH

#### What It Does
- Excel-like pivot table for trades
- Cross any dimension with any metric dynamically
- Example: "Show me Win Rate by [Strategy] x [Day of Week] x [Price Range] x [Hour]"
- Real-time calculations with filters

#### Technical Approach

**Backend:**
- New model: `/backend/src/models/PivotAnalysis.js`
- New route: `GET /api/analytics/pivot`
- New controller method: `analyticsController.getPivotAnalysis`
- Query builder that generates SQL dynamically based on:
  - **Row Dimensions** (e.g., strategy, symbol, day_of_week)
  - **Column Dimensions** (e.g., price_range, hour)
  - **Metrics** (e.g., win_rate, avg_pnl, profit_factor, count)
  - **Filters** (existing filter system)

**Available Dimensions:**
```javascript
const AVAILABLE_DIMENSIONS = {
  // Basic
  'strategy': 'Strategy',
  'symbol': 'Symbol',
  'sector': 'Sector (Finnhub)',
  'side': 'Long/Short',
  'broker': 'Broker',

  // Time-based
  'day_of_week': 'Day of Week',
  'hour_of_day': 'Hour of Day',
  'trade_session': 'Session (premarket, first_hour, etc.)',
  'month': 'Month',
  'quarter': 'Quarter',

  // Price-based
  'entry_price_range': 'Entry Price Range ($0-10, $10-50, $50-100, $100+)',
  'symbol_price_tier': 'Price Tier (penny, small, mid, large)',

  // Volume-based
  'quantity_range': 'Position Size Range',
  'volume_ratio': 'Volume Ratio (high, medium, low)',

  // Performance-based
  'pnl_range': 'P&L Range',
  'hold_time': 'Hold Time Category',

  // ML-specific
  'strategy_confidence': 'Strategy Confidence Bucket',
  'ml_signal_quality': 'ML Signal Quality Bucket',
  'market_context_score': 'Market Context Bucket',

  // Tags
  'tags': 'Tag (each tag becomes a dimension)'
}
```

**Available Metrics:**
```javascript
const AVAILABLE_METRICS = {
  // Basic
  'count': 'Trade Count',
  'total_pnl': 'Total P&L',
  'avg_pnl': 'Average P&L',

  // Win/Loss
  'win_count': 'Wins',
  'loss_count': 'Losses',
  'win_rate': 'Win Rate %',

  // Performance
  'avg_win': 'Average Win',
  'avg_loss': 'Average Loss',
  'profit_factor': 'Profit Factor',
  'best_trade': 'Best Trade',
  'worst_trade': 'Worst Trade',

  // Risk
  'sharpe_ratio': 'Sharpe Ratio',
  'avg_mae': 'Avg MAE',
  'avg_mfe': 'Avg MFE',
  'max_drawdown': 'Max Drawdown',

  // Custom (user-defined)
  'r_multiple': 'R-Multiple',
  'expectancy': 'Expectancy'
}
```

**SQL Generation Strategy:**
```sql
-- Example: Win Rate by Strategy x Day of Week
WITH base_trades AS (
  SELECT
    strategy,
    EXTRACT(DOW FROM trade_date) as day_of_week,
    pnl,
    CASE WHEN pnl > 0 THEN 1 ELSE 0 END as is_win
  FROM trades
  WHERE user_id = $1
    AND [filters]
)
SELECT
  strategy,
  day_of_week,
  COUNT(*) as trade_count,
  SUM(is_win) as wins,
  ROUND((SUM(is_win) * 100.0 / COUNT(*)), 2) as win_rate,
  ROUND(AVG(pnl), 2) as avg_pnl
FROM base_trades
GROUP BY strategy, day_of_week
ORDER BY strategy, day_of_week
```

**Frontend:**
- New view: `/frontend/src/views/analytics/PivotGridView.vue`
- Components:
  - `PivotGridBuilder.vue` - Drag-and-drop interface for dimensions/metrics
  - `PivotGridTable.vue` - Rendered table with drill-down
  - `PivotGridChart.vue` - Visual representation (heatmap, bar chart)

**UI Features:**
- Drag dimensions to Rows/Columns
- Drag metrics to Values
- Click cells to drill down
- Export to CSV
- Save favorite pivot configurations
- Conditional formatting (color cells by value)

**Example Use Cases:**
1. "Which strategy performs best on Tuesdays between 10-11am?"
2. "What's my win rate by price tier across all strategies?"
3. "Does my momentum strategy work better on high vs low volume days?"

**Libraries Needed:**
- None (custom implementation using Vue 3 reactivity)
- OR: Consider `vue3-pivottable` if we want to speed up (evaluate first)

---

### 2. AI PATTERN DETECTION ⭐⭐⭐⭐⭐
**Priority:** HIGHEST
**Impact:** MAXIMUM - Automated discovery of non-obvious correlations
**Complexity:** MEDIUM (we already have Gemini)

#### What It Does
- Automatically analyzes trade history
- Detects patterns like: "You lose 80% more when entry is in first 5 minutes"
- Surfaces hidden correlations without manual exploration
- Generates actionable insights

#### Technical Approach

**Backend:**
- Extend existing `EdgeDiscoveryService.js` (already has correlation logic!)
- New method: `analyzePatterns(userId, startDate, endDate)`
- Leverage existing:
  - `analyzeIndicatorCorrelations()` ✅ Already exists
  - `detectMarketRegimes()` ✅ Already exists
  - `analyzeWorkerAttribution()` ✅ Already exists (worker = strategy + symbol)

**New Pattern Detectors:**

**a) Time-Based Patterns**
```javascript
async detectTimePatterns(trades) {
  // Patterns to detect:
  // 1. "Win rate drops 30% after 11am"
  // 2. "Monday performance is -$50 vs Friday +$120"
  // 3. "First trade of day wins 65%, subsequent trades 45%"
  // 4. "Trades held <5min lose 70% of the time"

  return {
    hourly: analyzeByHour(trades),
    daily: analyzeByDay(trades),
    firstTradeEffect: analyzeFirstTrade(trades),
    holdTimeOptimal: findOptimalHoldTime(trades)
  };
}
```

**b) Entry Condition Patterns**
```javascript
async detectEntryPatterns(trades) {
  // Patterns to detect:
  // 1. "Entries near HOD (high of day) lose 60%"
  // 2. "Gap up >2% correlates with -$30 avg loss"
  // 3. "Low volume entries (volume_ratio < 0.5) underperform"
  // 4. "High confidence signals (>0.8) win 75%"

  return {
    priceLevel: analyzePriceLevelEntry(trades),
    gapEffect: analyzeGapEffect(trades),
    volumeEffect: analyzeVolumeEffect(trades),
    confidenceAccuracy: analyzeConfidenceCalibration(trades)
  };
}
```

**c) Strategy Interaction Patterns**
```javascript
async detectStrategyPatterns(trades) {
  // Patterns to detect:
  // 1. "Momentum strategy works on volatility >3%, fails <1%"
  // 2. "Breakout strategy wins 80% on Mondays, 40% Fridays"
  // 3. "Mean reversion outperforms 2-4pm"
  // 4. "Strategy A + Symbol X = toxic combination"

  return {
    volatilityDependency: analyzeVolatilityDependency(trades),
    timeSensitivity: analyzeStrategyTiming(trades),
    symbolFit: analyzeStrategySymbolFit(trades),
    toxicCombinations: findToxicCombinations(trades)
  };
}
```

**d) Cluster Analysis (Advanced)**
```javascript
async detectClusterPatterns(trades) {
  // Use k-means or hierarchical clustering to find trade groups
  // Example: "Group A (35% of trades) has 80% win rate"
  //          "Group B (15% of trades) has 20% win rate"
  // Then identify characteristics of each group

  return {
    clusters: performClustering(trades),
    clusterCharacteristics: describeC lusters(clusters),
    recommendations: generateClusterRecommendations(clusters)
  };
}
```

**AI Integration with Gemini:**
```javascript
async generatePatternInsights(patterns, trades) {
  // Send patterns to Gemini for natural language summary
  const prompt = `
    Analiza los siguientes patrones detectados en un sistema de trading algorítmico:

    ${JSON.stringify(patterns, null, 2)}

    Genera:
    1. Top 3 insights más importantes
    2. Recomendaciones específicas para mejorar el sistema
    3. Riesgos o problemas identificados
    4. Oportunidades no aprovechadas

    Responde en español, de forma concisa y accionable.
  `;

  const insights = await gemini.generateInsights(prompt);
  return insights;
}
```

**New Route:**
- `GET /api/analytics/ai-patterns?startDate=X&endDate=Y`
- Returns:
```json
{
  "period": { "startDate": "2025-01-01", "endDate": "2025-11-29" },
  "totalTrades": 1250,
  "patternsDetected": 23,
  "patterns": {
    "timeBased": [...],
    "entryConditions": [...],
    "strategyInteractions": [...],
    "clusters": [...]
  },
  "topInsights": [
    {
      "type": "time_pattern",
      "severity": "high",
      "impact": -$450,
      "description": "Trades entered after 11am underperform by $35/trade on average",
      "affected_trades": 180,
      "recommendation": "Avoid entries after 11am or adjust position sizing"
    }
  ],
  "aiSummary": "Your system has 3 critical weaknesses..."
}
```

**Frontend:**
- New view: `/frontend/src/views/analytics/AIPatternDiscovery.vue`
- Features:
  - Visual pattern cards with severity badges
  - Drill-down into each pattern
  - Apply filters based on pattern recommendations
  - "Fix This" button → creates filters automatically
  - Export patterns to PDF

**Caching:**
- Pattern detection is expensive → cache results for 1 hour
- Invalidate cache when new trades are added

---

### 3. CUSTOM METRICS / CALCULATED FIELDS ⭐⭐⭐⭐⭐
**Priority:** HIGH
**Impact:** HIGH - Essential for algo trading (every system has unique metrics)
**Complexity:** MEDIUM

#### What It Does
- Users define their own metrics: `R-Multiple`, `Expectancy`, `Kelly Criterion`, etc.
- Formulas use existing fields: `pnl`, `entry_price`, `quantity`, `mae`, `mfe`
- Metrics appear everywhere: dashboard, pivot grid, charts, filters

#### Technical Approach

**Backend:**
- New model: `/backend/src/models/CustomMetric.js`
- New table: `custom_metrics`

```sql
CREATE TABLE custom_metrics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL,
  formula TEXT NOT NULL,  -- e.g., "(pnl / abs(mae)) || 0"
  description TEXT,
  category VARCHAR(50),  -- 'risk', 'performance', 'custom'
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, name)
);
```

**Formula Engine:**
- Use a safe expression evaluator
- Supported operators: `+`, `-`, `*`, `/`, `abs()`, `max()`, `min()`, `round()`, `||` (default)
- Available variables: All trade fields + existing metrics

**Example Custom Metrics:**
```javascript
const EXAMPLE_METRICS = {
  'r_multiple': {
    name: 'R-Multiple',
    formula: 'pnl / abs(entry_price - stop_loss_price)',
    description: 'Profit/Loss in terms of initial risk',
    category: 'risk'
  },
  'expectancy': {
    formula: '(win_rate / 100) * avg_win - ((100 - win_rate) / 100) * abs(avg_loss)',
    description: 'Expected value per trade',
    category: 'performance'
  },
  'efficiency_ratio': {
    formula: 'pnl / (abs(mae) + abs(mfe))',
    description: 'How efficiently you captured the move',
    category: 'execution'
  },
  'risk_reward_actual': {
    formula: 'abs(mfe) / abs(mae)',
    description: 'Actual risk/reward based on MAE/MFE',
    category: 'risk'
  },
  'position_size_pct': {
    formula: '(quantity * entry_price) / capital_at_trade_time * 100',
    description: 'Position size as % of capital',
    category: 'risk'
  }
};
```

**Formula Evaluation:**
```javascript
// Use expr-eval library for safe evaluation
const Parser = require('expr-eval').Parser;

function evaluateCustomMetric(formula, tradeData) {
  try {
    const parser = new Parser();
    const expr = parser.parse(formula);

    // Create context with all available fields
    const context = {
      ...tradeData,
      // Computed fields
      win_rate: calculateWinRate(tradeData),
      avg_win: calculateAvgWin(tradeData),
      avg_loss: calculateAvgLoss(tradeData)
    };

    const result = expr.evaluate(context);
    return isFinite(result) ? result : null;
  } catch (error) {
    console.error('Formula evaluation error:', error);
    return null;
  }
}
```

**New Routes:**
- `POST /api/custom-metrics` - Create metric
- `GET /api/custom-metrics` - List user metrics
- `PUT /api/custom-metrics/:id` - Update metric
- `DELETE /api/custom-metrics/:id` - Delete metric
- `POST /api/custom-metrics/:id/validate` - Test formula
- `GET /api/custom-metrics/:id/calculate` - Calculate for all trades

**Integration Points:**

1. **Analytics Queries** - Add custom metrics to SELECT
```sql
SELECT
  *,
  -- Standard metrics
  pnl, win_rate, profit_factor,
  -- Custom metrics (dynamically generated)
  (pnl / abs(mae)) as r_multiple,
  ((win_rate / 100) * avg_win - ((100 - win_rate) / 100) * abs(avg_loss)) as expectancy
FROM trades
```

2. **Pivot Grid** - Available as metrics
3. **Filters** - Filter by custom metric value
4. **Charts** - Plot custom metrics over time

**Frontend:**
- New view: `/frontend/src/views/settings/CustomMetricsView.vue`
- Components:
  - `CustomMetricForm.vue` - Create/edit metrics
  - `FormulaBuilder.vue` - Visual formula builder (drag fields + operators)
  - `MetricPreview.vue` - Live preview with sample trades
  - `MetricsList.vue` - Manage user metrics

**UI Features:**
- Autocomplete for available fields
- Formula validation in real-time
- Test with sample trades before saving
- Import/export metric definitions
- Share metrics with community (optional)

**Library:**
- `expr-eval` for safe formula evaluation

---

### 4. ADVANCED FILTERING SYSTEM ⭐⭐⭐⭐
**Priority:** HIGH
**Impact:** HIGH - Required for deep analysis
**Complexity:** MEDIUM

#### What It Does
- Complex queries: `(Strategy = "Momentum" AND Win = true AND MFE > 2%) OR (Tags contains "breakout")`
- Filter history / favorites
- Quick filters for common patterns
- Filter by custom metrics

#### Technical Approach

**Backend:**
- Enhance existing filter system in `Trade.findByUser()`
- New query builder: `/backend/src/utils/advancedFilterBuilder.js`

**Filter DSL (Domain Specific Language):**
```javascript
const FILTER_EXAMPLE = {
  type: 'AND',  // or 'OR'
  conditions: [
    {
      field: 'strategy',
      operator: '=',
      value: 'Momentum'
    },
    {
      type: 'OR',
      conditions: [
        {
          field: 'pnl',
          operator: '>',
          value: 100
        },
        {
          field: 'tags',
          operator: 'contains',
          value: 'breakout'
        }
      ]
    },
    {
      field: 'custom:r_multiple',  // Custom metric
      operator: '>',
      value: 2
    }
  ]
};
```

**Supported Operators:**
```javascript
const OPERATORS = {
  '=': 'equals',
  '!=': 'not equals',
  '>': 'greater than',
  '>=': 'greater or equal',
  '<': 'less than',
  '<=': 'less or equal',
  'contains': 'contains (for arrays/strings)',
  'not_contains': 'does not contain',
  'in': 'in list',
  'not_in': 'not in list',
  'between': 'between two values',
  'is_null': 'is null',
  'is_not_null': 'is not null'
};
```

**SQL Generation:**
```javascript
function buildWhereClause(filterTree, params) {
  if (filterTree.field) {
    // Leaf node: single condition
    return buildCondition(filterTree, params);
  } else {
    // Branch node: AND/OR
    const clauses = filterTree.conditions.map(cond => buildWhereClause(cond, params));
    const operator = filterTree.type === 'AND' ? ' AND ' : ' OR ';
    return `(${clauses.join(operator)})`;
  }
}

function buildCondition(condition, params) {
  const { field, operator, value } = condition;

  // Handle custom metrics
  if (field.startsWith('custom:')) {
    const metricName = field.split(':')[1];
    const formula = getCustomMetricFormula(metricName);
    return `(${formula}) ${operator} $${params.add(value)}`;
  }

  // Standard fields
  switch (operator) {
    case 'contains':
      if (Array.isArray(value)) {
        return `${field} && $${params.add(value)}`;  // PostgreSQL array overlap
      } else {
        return `${field} LIKE $${params.add('%' + value + '%')}`;
      }
    case 'between':
      return `${field} BETWEEN $${params.add(value[0])} AND $${params.add(value[1])}`;
    default:
      return `${field} ${operator} $${params.add(value)}`;
  }
}
```

**New Table: Saved Filters**
```sql
CREATE TABLE saved_filters (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL,
  description TEXT,
  filter_json JSONB NOT NULL,  -- The filter tree
  is_favorite BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, name)
);
```

**New Routes:**
- `POST /api/filters` - Save filter
- `GET /api/filters` - List saved filters
- `PUT /api/filters/:id` - Update filter
- `DELETE /api/filters/:id` - Delete filter
- `POST /api/filters/validate` - Validate filter syntax

**Quick Filters (Presets):**
```javascript
const QUICK_FILTERS = {
  'winning_trades': { field: 'pnl', operator: '>', value: 0 },
  'losing_trades': { field: 'pnl', operator: '<', value: 0 },
  'today': { field: 'trade_date', operator: '=', value: 'TODAY' },
  'this_week': { field: 'trade_date', operator: 'between', value: ['WEEK_START', 'TODAY'] },
  'this_month': { field: 'trade_date', operator: 'between', value: ['MONTH_START', 'TODAY'] },
  'large_positions': { field: 'quantity', operator: '>', value: 1000 },
  'high_conviction': { field: 'strategy_confidence', operator: '>', value: 0.8 },
  'after_hours': { field: 'trade_session', operator: 'in', value: ['premarket', 'afterhours'] }
};
```

**Frontend:**
- Component: `/frontend/src/components/analytics/AdvancedFilterBuilder.vue`
- Features:
  - Visual query builder (similar to MongoDB Compass)
  - Add/remove condition groups
  - Drag to reorder
  - Live trade count as you build
  - Save filter with name
  - Quick filter buttons
  - Filter history (last 10 filters)

**UI Example:**
```
┌─ AND ────────────────────────────────────────┐
│ Strategy [=] [Momentum ▼]                    │
│                                              │
│ ┌─ OR ──────────────────────────────────┐   │
│ │ P&L [>] [100]                         │   │
│ │ Tags [contains] [breakout]            │   │
│ └───────────────────────────────────────┘   │
│                                              │
│ R-Multiple [>] [2]                           │
│                                              │
│ [+ Add Condition] [+ Add Group]              │
└──────────────────────────────────────────────┘

Matching: 42 trades    [Save Filter] [Apply]
```

---

## IMPLEMENTATION PHASING

### PHASE 1: Foundation (Week 1-2)
**Goal:** Set up data structures and backend logic

**Tasks:**
1. ✅ Create `custom_metrics` table + model
2. ✅ Create `saved_filters` table + model
3. ✅ Implement formula evaluator for custom metrics
4. ✅ Implement advanced filter SQL builder
5. ✅ Create API routes for custom metrics CRUD
6. ✅ Create API routes for saved filters CRUD

**Deliverables:**
- Backend can handle custom metrics
- Backend can parse complex filter trees
- Unit tests for formula evaluator
- Unit tests for SQL builder

---

### PHASE 2: Pivot Grid (Week 3-4)
**Goal:** Build the most important feature first

**Tasks:**
1. ✅ Design pivot grid backend logic
2. ✅ Create dynamic SQL generator for pivot queries
3. ✅ New route: `GET /api/analytics/pivot`
4. ✅ Frontend: `PivotGridView.vue`
5. ✅ Frontend: `PivotGridBuilder.vue` (drag-drop)
6. ✅ Frontend: `PivotGridTable.vue` (render + drill-down)
7. ✅ Frontend: Export to CSV
8. ✅ Integration with existing filters
9. ✅ Add to main navigation

**Deliverables:**
- Working pivot grid
- Users can cross any 2 dimensions
- Drill-down functionality
- Export capability

---

### PHASE 3: AI Pattern Detection (Week 5-6)
**Goal:** Automated pattern discovery

**Tasks:**
1. ✅ Extend `EdgeDiscoveryService.js` with new pattern detectors
2. ✅ Implement time-based pattern detector
3. ✅ Implement entry condition pattern detector
4. ✅ Implement strategy interaction detector
5. ✅ Integrate with Gemini for insights
6. ✅ New route: `GET /api/analytics/ai-patterns`
7. ✅ Frontend: `AIPatternDiscovery.vue`
8. ✅ Caching layer for expensive pattern detection
9. ✅ Add to analytics dashboard

**Deliverables:**
- AI discovers patterns automatically
- Natural language insights from Gemini
- Visual pattern cards
- Actionable recommendations

---

### PHASE 4: Advanced Filters + Polish (Week 7-8)
**Goal:** Complete the system with advanced filtering

**Tasks:**
1. ✅ Implement `AdvancedFilterBuilder.vue`
2. ✅ Visual query builder UI
3. ✅ Quick filter presets
4. ✅ Filter history
5. ✅ Save/load filters
6. ✅ Integrate advanced filters across all views
7. ✅ Custom metrics UI (`CustomMetricsView.vue`)
8. ✅ Polish & bug fixes
9. ✅ Documentation

**Deliverables:**
- Complex filtering works everywhere
- Users can save favorite filters
- Custom metrics fully functional
- All 4 Tier 1 features integrated

---

## DATABASE MIGRATIONS

### Migration 1: Custom Metrics
```sql
-- 001_create_custom_metrics.sql
CREATE TABLE custom_metrics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL,
  formula TEXT NOT NULL,
  description TEXT,
  category VARCHAR(50) DEFAULT 'custom',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, name)
);

CREATE INDEX idx_custom_metrics_user ON custom_metrics(user_id);
```

### Migration 2: Saved Filters
```sql
-- 002_create_saved_filters.sql
CREATE TABLE saved_filters (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL,
  description TEXT,
  filter_json JSONB NOT NULL,
  is_favorite BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, name)
);

CREATE INDEX idx_saved_filters_user ON saved_filters(user_id);
CREATE INDEX idx_saved_filters_favorite ON saved_filters(user_id, is_favorite);
```

### Migration 3: Pattern Cache
```sql
-- 003_create_pattern_cache.sql
CREATE TABLE ai_pattern_cache (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  patterns_json JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '1 hour'),
  UNIQUE(user_id, start_date, end_date)
);

CREATE INDEX idx_pattern_cache_user_dates ON ai_pattern_cache(user_id, start_date, end_date);
CREATE INDEX idx_pattern_cache_expires ON ai_pattern_cache(expires_at);
```

---

## NPM DEPENDENCIES

### Backend
```json
{
  "expr-eval": "^2.0.2"  // Safe formula evaluation
}
```

### Frontend
```json
{
  // No new dependencies needed! Using Vue 3 + Tailwind
}
```

---

## SUCCESS METRICS

### User Impact
- ✅ Can discover edge in <5 minutes (Pivot Grid)
- ✅ Receives actionable insights automatically (AI Patterns)
- ✅ Can track system-specific metrics (Custom Metrics)
- ✅ Can filter trades with surgical precision (Advanced Filters)

### Technical Metrics
- Pivot Grid query: <500ms for 10k trades
- AI Pattern detection: <3s for 5k trades (cached 1h)
- Custom metric evaluation: <100ms for 1k trades
- Filter parsing + SQL generation: <50ms

### Business Metrics
- TradeTally becomes **the best journal for algo traders**
- Competitive advantage over Tradervue, Tradezella, TraderSync, TradesViz
- Users can answer: "Where am I? What needs improving? How far can I go?"

---

## RISKS & MITIGATION

### Risk 1: SQL Injection in Dynamic Queries
**Mitigation:** Always use parameterized queries, validate user input, whitelist allowed fields

### Risk 2: Formula Injection in Custom Metrics
**Mitigation:** Use `expr-eval` which is sandboxed, limit allowed functions, validate formulas

### Risk 3: Performance Degradation with Complex Pivots
**Mitigation:** Add query timeouts, limit pivot dimensions to 3, optimize with proper indexes

### Risk 4: AI Pattern Detection Too Slow
**Mitigation:** Implement caching, run analysis async, allow users to schedule analysis

---

## POST-TIER 1 (Future Enhancements)

Once Tier 1 is complete, consider:
- Trade Replay (debug system tick-by-tick)
- Backtesting Module (test strategies on historical data)
- Strategy Comparison View (side-by-side)
- Equity Curve Overlays (correlations between strategies)
- Benchmark Comparison (vs SPY, QQQ)
- Trade Correlation Analysis (systemic risk)
- Playbooks (strategy documentation)
- Rule-based Alerts (max loss/day breached)

---

## CONCLUSION

This plan transforms TradeTally from a good trading journal into **the ultimate evaluation tool for algorithmic stock traders**.

The 4 Tier 1 features address the critical gaps:
1. **Pivot Grid** → Multidimensional exploration
2. **AI Pattern Detection** → Automated insight discovery
3. **Custom Metrics** → System-specific KPIs
4. **Advanced Filtering** → Surgical analysis

With these features, you'll be able to answer:
- **"Where am I?"** → Pivot Grid shows exact performance across all dimensions
- **"What needs improving?"** → AI Patterns reveals hidden weaknesses
- **"How far can I go?"** → Custom Metrics track system limits

**Let's build this! 🚀**
