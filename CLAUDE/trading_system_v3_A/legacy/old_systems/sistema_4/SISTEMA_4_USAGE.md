# Sistema_4 - Distributed Trading System

## Arquitectura

Sistema_4 implementa la arquitectura distribuida descrita en el README.md original:

```
📊 Scanner Central → 👥 Workers Especializados → ⚙️ Execution Engine → 📈 IBKR
                    ↑                              ↑
                💾 SQLite Database ←→ 📡 Redis Messaging
```

### Componentes

1. **Scanner Central** (`scanner_central.py`)
   - Ejecuta cada 30s detectando oportunidades
   - Clasifica por tipo: GAP_GO, DAILY_PLAYS, MACDV, BULL_FLAG
   - Publica via Redis a workers

2. **Workers Especializados** (`workers/`)
   - `gap_go_worker.py` - Gaps significativos (2-15%)
   - `daily_plays_worker.py` - Setups de bounce con catalysts
   - `macdv_worker.py` - Momentum técnico + volumen
   - `bull_flag_worker.py` - Patrones de bandera alcista

3. **Execution Engine** (`execution/execution_engine.py`)
   - Motor centralizado de ejecución
   - Valida riesgo con Risk Manager
   - Ejecuta bracket orders automáticos

4. **Risk Manager** (`execution/risk_manager.py`)
   - Control de límites de portfolio
   - Previene over-trading
   - Coordina entre workers via SQLite

5. **Database Compartida** (`shared/database.py`)
   - SQLite para coordinación
   - Previene trades duplicados
   - Tracking de posiciones activas

## Flujo de Operación

### 1. Detección de Oportunidad
```
Scanner → Detecta ABC con gap 5.2%, volumen 3.1x
       ↓
SQLite → Guarda oportunidad como "GAP_GO"
       ↓
Redis  → Publica a channel "scanner_opportunities"
```

### 2. Análisis por Worker
```
GAP_GO Worker → Ve oportunidad ABC
             ↓
SQLite → reserve_symbol("ABC", "gap_go_worker_1")
       ↓
Análisis → Valida setup (gap, volumen, precio)
         ↓
Decision → "BUY 500 shares @ $4.25"
```

### 3. Ejecución Centralizada
```
Worker → Envía trade_request via Redis
       ↓
Execution Engine → Risk Manager validation
                ↓
IBKR → place_bracket_order(ABC, BUY, 500, stop: $4.12, target: $4.59)
     ↓
SQLite → add_position(ABC, gap_go_worker_1, ACTIVE)
```

### 4. Coordinación
```
Daily Worker → Ve ABC en SQLite como "OCUPADO" → ✅ Lo ignora
MACDV Worker → Ve ABC en SQLite como "OCUPADO" → ✅ Lo ignora
```

## Configuración

### Client IDs IBKR
- Scanner: `104`
- Execution Engine: `105`
- Evita conflictos con otros sistemas

### Parámetros por Estrategia

**GAP_GO Worker:**
- Gap: 2-15%
- Volumen: 500K-10M
- Stop: 3%, Target: 8%

**DAILY_PLAYS Worker:**
- Volumen mín: 300K
- Quality score mín: 60
- Catalysts preferidos: FDA, M&A, EARNINGS

**MACDV Worker:**
- Volumen ratio mín: 2.0x
- Momentum score mín: 0.6
- Stop: 3.5%, Target: 10%

**BULL_FLAG Worker:**
- Pole height: 3-25%
- Flag range máx: 3%
- Volumen breakout: 1.5x

### Risk Manager
- Portfolio: $10,000
- Max riesgo por trade: 1%
- Max trades diarios: 10
- Max símbolos por estrategia: 3

## Uso

### Ejecutar Sistema Completo
```bash
cd sistema_4
python main.py
```

Esto inicia automáticamente:
- ✅ Scanner central
- ✅ 4 workers especializados
- ✅ Execution engine
- ✅ Risk manager
- ✅ Coordinación SQLite + Redis

### Ejecutar Componentes Individuales

**Solo Scanner:**
```bash
python scanner_central.py
```

**Solo Worker Individual:**
```bash
python workers/gap_go_worker.py
python workers/daily_plays_worker.py
```

**Solo Execution Engine:**
```bash
python execution/execution_engine.py
```

## Logs

- `logs/sistema4_main.log` - Coordinador principal
- `logs/scanner.log` - Scanner central
- `logs/gap_go_worker.log` - Worker GAP_GO
- `logs/execution_engine.log` - Engine de ejecución

## Base de Datos

SQLite: `shared/sistema4.db`

**Tablas:**
- `positions` - Posiciones activas por worker
- `reservations` - Locks temporales en símbolos (5 min)
- `opportunities` - Oportunidades del scanner

**Consultas útiles:**
```sql
-- Ver posiciones activas
SELECT * FROM positions WHERE status = 'ACTIVE';

-- Ver reservas activas
SELECT * FROM reservations WHERE expires_at > datetime('now');

-- Ver oportunidades pendientes
SELECT * FROM opportunities WHERE processed = FALSE;
```

## Ventajas vs Sistema_III

### ✅ Simplicidad
- Cada worker se enfoca en UNA estrategia
- Lógica especializada y optimizada
- Fácil debug y mantenimiento

### ✅ Escalabilidad
- Agregar nueva estrategia = nuevo worker
- Workers independientes
- Sin ML complejo

### ✅ Control de Riesgo
- Risk Manager centralizado
- Un solo punto de control
- Coordinación via SQLite

### ✅ Sin Duplicación
- SQLite previene trades duplicados
- Workers coordinados automáticamente
- Execution engine único

## Troubleshooting

### Worker no recibe oportunidades
1. Verificar Redis conexión
2. Verificar channel subscription
3. Verificar tipo de oportunidad correcto

### Trades rechazados
1. Verificar Risk Manager logs
2. Verificar límites en config.ini
3. Verificar símbolo disponible en database

### Scanner no encuentra oportunidades
1. Verificar IBKR conexión (client_id 104)
2. Verificar mercado abierto
3. Verificar logs scanner para errores

### Conflictos client_id
- Sistema_4 usa 104-105
- Cambiar en config.ini si necesario
- No usar mismos IDs que otros sistemas