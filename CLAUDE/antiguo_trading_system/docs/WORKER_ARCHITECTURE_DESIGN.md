# 🏗️ Worker-Based Architecture Design
## Sistema de Trading con Workers Lógicos

**Fecha:** 2025-09-30
**Rama:** `worker-based-architecture`
**Objetivo:** Migrar de SimpleStrategyEngine monolítico a workers lógicos asíncronos

---

## 📊 ARQUITECTURA ACTUAL vs PROPUESTA

### **Actual (Monolítico)**
```
scanner_main.py (IBKR 6120)
    └─▶ Redis Pub "opportunities"

trader_main.py (IBKR 6000)
    ├─▶ Recibe opportunities
    └─▶ SimpleStrategyEngine
        ├─▶ _rule_based_selection()  ← Secuencial
        ├─▶ gap_go.analyze()
        ├─▶ daily_plays.analyze()
        ├─▶ macdv.analyze()
        └─▶ bull_flag.analyze()
```

**Problema:** Todas las estrategias se evalúan secuencialmente en un solo hilo.

---

### **Propuesta (Workers Lógicos)**
```
scanner_main.py (IBKR 6120)
    └─▶ Redis Pub "opportunities"

trader_main.py (IBKR 6000)
    ├─▶ ExecutionEngine (compartido)
    ├─▶ RiskManager (compartido)
    └─▶ WorkerBasedStrategyEngine
        ├─▶ GapGoWorkerLogic (async task)
        │   ├─▶ Escucha opportunities
        │   ├─▶ Evalúa con GapGoStrategy
        │   ├─▶ Ejecuta trades (ExecutionEngine)
        │   └─▶ Monitorea posiciones propias
        │
        ├─▶ DailyPlaysWorkerLogic (async task)
        │   └─▶ ...mismo patrón
        │
        ├─▶ MacdvWorkerLogic (async task)
        │   └─▶ ...mismo patrón
        │
        └─▶ BullFlagWorkerLogic (async task)
            └─▶ ...mismo patrón
```

**Ventajas:**
- ✅ Evaluación paralela con `asyncio`
- ✅ Logs separados por worker
- ✅ Monitoreo independiente por estrategia
- ✅ Solo 2 conexiones IBKR (como ahora)
- ✅ Fácil añadir/quitar workers

---

## 🧩 COMPONENTES A CREAR

### **1. BaseWorkerLogic** (Clase base abstracta)
```python
# strategies/workers/base_worker_logic.py

class BaseWorkerLogic(ABC):
    """
    Clase base para todos los workers lógicos
    Proporciona funcionalidad común de ejecución y monitoreo
    """

    def __init__(
        self,
        worker_name: str,
        strategy: IStrategy,
        execution_engine: ExecutionEngine,
        risk_manager: RiskManager
    ):
        self.worker_name = worker_name
        self.strategy = strategy
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        self.active_positions = {}  # {symbol: position_data}
        self.logger = logging.getLogger(f"Worker.{worker_name}")

    async def run(self):
        """Loop principal del worker - monitoreo de posiciones"""
        while True:
            await self._monitor_positions()
            await asyncio.sleep(1)

    async def process_opportunity(self, opportunity: Dict) -> bool:
        """
        Evalúa oportunidad y ejecuta si cumple criterios
        Cada worker implementa su lógica en should_enter()
        """
        symbol = opportunity['symbol']

        # Check si ya tenemos posición
        if symbol in self.active_positions:
            self.logger.debug(f"⏭️ {symbol}: Ya en posición, skip")
            return False

        # Evaluar entrada con estrategia específica
        if await self.should_enter(opportunity):
            return await self._execute_entry(opportunity)

        return False

    @abstractmethod
    async def should_enter(self, opportunity: Dict) -> bool:
        """Cada worker implementa su lógica de entrada"""
        pass

    @abstractmethod
    async def should_exit(self, symbol: str, position: Dict, current_price: float) -> tuple[bool, str]:
        """Cada worker implementa su lógica de salida"""
        pass

    async def _execute_entry(self, opportunity: Dict) -> bool:
        """Ejecuta entrada usando ExecutionEngine compartido"""
        symbol = opportunity['symbol']

        try:
            self.logger.info(f"🎯 {self.worker_name}: Entering {symbol}")

            position = await self.execution_engine.enter_position(
                symbol=symbol,
                strategy=self.worker_name
            )

            if position:
                self.active_positions[symbol] = {
                    'position': position,
                    'entry_time': datetime.now(),
                    'opportunity_data': opportunity
                }
                self.logger.info(f"✅ {self.worker_name}: Position opened {symbol}")
                return True

        except Exception as e:
            self.logger.error(f"❌ {self.worker_name}: Entry failed {symbol}: {e}")

        return False

    async def _monitor_positions(self):
        """Monitorea posiciones activas y ejecuta salidas"""
        for symbol, data in list(self.active_positions.items()):
            try:
                # Obtener precio actual
                current_price = await self.execution_engine.get_current_price(symbol)

                # Evaluar salida
                should_exit, reason = await self.should_exit(
                    symbol,
                    data['position'],
                    current_price
                )

                if should_exit:
                    await self._execute_exit(symbol, reason)

            except Exception as e:
                self.logger.error(f"❌ Error monitoring {symbol}: {e}")

    async def _execute_exit(self, symbol: str, reason: str):
        """Ejecuta salida usando ExecutionEngine compartido"""
        try:
            self.logger.info(f"🚪 {self.worker_name}: Exiting {symbol} - {reason}")

            await self.execution_engine.close_position(symbol, reason)
            del self.active_positions[symbol]

            self.logger.info(f"✅ {self.worker_name}: Position closed {symbol}")

        except Exception as e:
            self.logger.error(f"❌ Exit failed {symbol}: {e}")
```

---

### **2. GapGoWorkerLogic** (Implementación concreta)
```python
# strategies/workers/gap_go_worker_logic.py

class GapGoWorkerLogic(BaseWorkerLogic):
    """Worker para estrategia Gap-Go"""

    def __init__(self, execution_engine, risk_manager):
        from strategies.gap_go_strategy import GapGoStrategy

        super().__init__(
            worker_name="gap_go",
            strategy=GapGoStrategy(),
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración específica Gap-Go
        self.min_gap = 8.0
        self.min_volume_ratio = 2.0

    async def should_enter(self, opportunity: Dict) -> bool:
        """Lógica específica Gap-Go"""
        gap = abs(opportunity.get('gap_percentage', 0))
        volume_ratio = opportunity.get('volume_ratio', 0)

        # Criterios Gap-Go
        if gap >= self.min_gap and volume_ratio >= self.min_volume_ratio:
            self.logger.info(
                f"✅ Gap-Go criteria met: gap={gap:.1f}%, vol={volume_ratio:.1f}x"
            )
            return True

        return False

    async def should_exit(self, symbol: str, position: Dict, current_price: float) -> tuple[bool, str]:
        """Lógica de salida Gap-Go"""
        entry_price = position.get('entry_price', 0)

        if entry_price == 0:
            return False, ""

        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Take profit 15%
        if pnl_pct >= 15.0:
            return True, f"TAKE_PROFIT_15% (PnL: {pnl_pct:.1f}%)"

        # Stop loss 3%
        if pnl_pct <= -3.0:
            return True, f"STOP_LOSS_3% (PnL: {pnl_pct:.1f}%)"

        return False, ""
```

---

### **3. WorkerBasedStrategyEngine** (Orquestador)
```python
# strategies/worker_based_strategy_engine.py

class WorkerBasedStrategyEngine:
    """
    Orquestador de workers lógicos
    Reemplaza SimpleStrategyEngine con arquitectura paralela
    """

    def __init__(self, execution_engine, risk_manager):
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        self.logger = logging.getLogger("WorkerBasedEngine")

        # Crear workers
        self.workers = {
            'gap_go': GapGoWorkerLogic(execution_engine, risk_manager),
            'daily_plays': DailyPlaysWorkerLogic(execution_engine, risk_manager),
            'macdv': MacdvWorkerLogic(execution_engine, risk_manager),
            'bull_flag': BullFlagWorkerLogic(execution_engine, risk_manager)
        }

        self.worker_tasks = []

    async def start(self):
        """Inicia todos los workers como tasks asíncronos"""
        self.logger.info("🚀 Starting worker-based strategy engine...")

        for name, worker in self.workers.items():
            task = asyncio.create_task(worker.run())
            self.worker_tasks.append(task)
            self.logger.info(f"✅ Worker {name} started")

    async def process_opportunity(self, opportunity: Dict):
        """
        Distribuye oportunidad a workers relevantes
        Evaluación en paralelo
        """
        symbol = opportunity['symbol']

        # Determinar qué workers deben procesar
        relevant_workers = self._match_workers(opportunity)

        if not relevant_workers:
            self.logger.debug(f"⚪ {symbol}: No relevant workers")
            return

        self.logger.info(f"🎯 {symbol}: Routing to workers: {relevant_workers}")

        # Procesar en paralelo
        tasks = [
            self.workers[worker_name].process_opportunity(opportunity)
            for worker_name in relevant_workers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log resultados
        for worker_name, result in zip(relevant_workers, results):
            if isinstance(result, Exception):
                self.logger.error(f"❌ {worker_name} failed: {result}")
            elif result:
                self.logger.info(f"✅ {worker_name} entered position")

    def _match_workers(self, opportunity: Dict) -> List[str]:
        """Determina qué workers son relevantes para esta oportunidad"""
        workers = []

        gap = abs(opportunity.get('gap_percentage', 0))
        volume_ratio = opportunity.get('volume_ratio', 0)
        catalyst_type = opportunity.get('catalyst_type', '')

        # Gap-Go: Gaps grandes
        if gap >= 8.0 and volume_ratio >= 2.0:
            workers.append('gap_go')

        # Daily Plays: Catalysts + volumen
        if catalyst_type in ['FDA', 'M&A', 'EARNINGS'] and volume_ratio >= 3.0:
            workers.append('daily_plays')

        # MACDV: Técnico sin gaps grandes
        if gap <= 5.0 and volume_ratio >= 1.5:
            workers.append('macdv')

        # Bull Flag: Patrones
        if volume_ratio >= 2.0 and gap <= 3.0:
            workers.append('bull_flag')

        return workers

    async def stop(self):
        """Detiene todos los workers"""
        self.logger.info("🛑 Stopping all workers...")
        for task in self.worker_tasks:
            task.cancel()
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
```

---

## 🔄 INTEGRACIÓN CON TRADER_MAIN.PY

```python
# trader_main.py (modificaciones)

class IndependentTrader:
    async def initialize(self):
        # ... código existente ...

        # CAMBIO: Usar WorkerBasedStrategyEngine
        from strategies.worker_based_strategy_engine import WorkerBasedStrategyEngine

        self.strategy_engine = WorkerBasedStrategyEngine(
            execution_engine=self.trading_engine,
            risk_manager=self.risk_manager
        )

        # Iniciar workers
        await self.strategy_engine.start()

        self.logger.info("✅ Worker-based strategy engine initialized")

    async def _handle_scanner_opportunities(self, opportunities):
        """Delega a strategy engine"""
        for opp in opportunities:
            await self.strategy_engine.process_opportunity(opp)
```

---

## 📋 PLAN DE IMPLEMENTACIÓN

### **Fase 1: Base (Día 1)**
1. ✅ Crear rama `worker-based-architecture`
2. [ ] Crear `strategies/workers/base_worker_logic.py`
3. [ ] Crear `strategies/workers/gap_go_worker_logic.py`
4. [ ] Testing aislado del worker

### **Fase 2: Engine (Día 2)**
5. [ ] Crear `strategies/worker_based_strategy_engine.py`
6. [ ] Integrar en `trader_main.py`
7. [ ] Testing con 1 worker (gap_go)

### **Fase 3: Expansión (Día 3-4)**
8. [ ] Crear `daily_plays_worker_logic.py`
9. [ ] Crear `macdv_worker_logic.py`
10. [ ] Crear `bull_flag_worker_logic.py`

### **Fase 4: Optimización (Día 5)**
11. [ ] Logs separados por worker
12. [ ] Métricas por worker
13. [ ] Testing completo

---

## 🎯 CRITERIOS DE ÉXITO

- [x] Sistema mantiene 2 conexiones IBKR (no más)
- [ ] Workers evalúan oportunidades en paralelo
- [ ] Cada worker monitorea sus propias posiciones
- [ ] Logs separados y claros por worker
- [ ] Performance igual o mejor que sistema actual
- [ ] Código más mantenible y extensible

---

## 🚨 RIESGOS Y MITIGACIONES

| Riesgo | Mitigación |
|--------|-----------|
| Race conditions en ExecutionEngine | Usar locks en métodos críticos |
| Workers duplican posiciones | Check de posición activa antes de entrar |
| Logs demasiado verbosos | Niveles DEBUG/INFO bien definidos |
| Performance degradado | Benchmarking antes/después |

---

**Próximo paso:** Implementar `BaseWorkerLogic` 🚀


_________________________-----------------------____________________

WORKER MOMENTUM BREAKOUT

Perfecto! El worker de Momentum Breakout ha sido completamente reconstruido con edge profesional.
📊 RESUMEN DE MEJORAS - Momentum Breakout Worker
❌ ANTES (Worker ROTO):
# Simplista y peligroso
- ✗ NO validaba VWAP
- ✗ NO verificaba estructura de precio
- ✗ Solo 3 barras verdes = entrada
- ✗ NO verificaba si venía de downtrend
- ✗ NO verificaba extensión desde base
- ✗ Breakout detection superficial
✅ AHORA (Worker PROFESIONAL - Mark Minervini Style):
# 5 Reglas Profesionales Obligatorias

RULE 1: VWAP Validation ✅
- Precio DEBE estar > VWAP
- Evita entradas en downtrends como AUUD

RULE 2: Price Structure ✅
- Verifica higher lows (uptrend)
- Rechaza si precio < 95% del promedio 10-bar
- Detecta downtrend structure
- Score: Higher lows en al menos 2/3 segmentos

RULE 3: Quality Breakout (60%+ requerido) ✅
- Breakout desde CONSOLIDACIÓN (no random spike)
- Tight consolidation (< 5% range ideal)
- Múltiples tests de resistencia (2-3+)
- Clean breakout (> 0.5% por encima del high)
- Quality Score: 0-100%

RULE 4: Volume Surge ✅
- Volumen > 120% del promedio
- Trend de volumen creciente (últimas 3 barras)
- O highest volume del período

RULE 5: NOT Extended ✅
- < 10% desde base/consolidation low
- < 15% desde 20-bar low
- Evita comprar tops como AUUD
🎯 EDGE REAL:
El worker ahora tiene un edge profesional basado en:
Minervini VCP - Volatility Contraction Pattern
IBD Breakouts - Proper base + volume + structure
Institutional buying - Multiple tests + tight range = absorption
🔴 AUUD habría sido RECHAZADO por:
⚪ AUUD: REJECTED - Price below VWAP (downtrend)
⚪ AUUD: REJECTED - Downtrend structure (only 0/3 segments with higher lows)  
⚪ AUUD: REJECTED - Price 8.2% below 10-bar average (downtrend)
⚪ AUUD: Too extended from base (12.3% > 10%)
El worker ahora es robusto, profesional y con edge real basado en principios probados de momentum breakouts institucionales.


----------------------


Ahora la lógica es jerárquica e inteligente. Déjame explicar cómo funciona ahora:
🎯 NUEVA LÓGICA JERÁRQUICA (Corregida)
✅ Reglas Inteligentes:
Jerarquía de Timeframes:
1min (más rápido) → 5min → 15min → 30min (más lento)

REGLA CLAVE: Los timeframes RÁPIDOS siguen a los LENTOS, no al revés
📊 Ejemplos Prácticos:
Caso 1: Dominante = 5min ✅
1min:  BEARISH   ← IGNORADO (más rápido que dominante)
5min:  BULLISH   ← DOMINANTE (el que manda)
15min: BULLISH   ← Debe confirmar (más lento)
30min: NEUTRAL   ← Debe confirmar (más lento)

✅ APROBADO: Dominante bullish + 2/3 higher TFs bullish (66%)
Reason: "Dominant=5min (bullish), Higher TFs: 2/3 bullish, Lower TFs ignored: ['1min']"
Caso 2: Dominante = 5min pero 30min contradice ❌
1min:  BULLISH   ← IGNORADO
5min:  BULLISH   ← DOMINANTE
15min: NEUTRAL   
30min: BEARISH   ← CONTRADICE (más lento que dominante)

❌ RECHAZADO: 1 higher TF bearish ['30min'] (contradicts 5min)
Caso 3: Dominante = 30min ✅
1min:  BEARISH   ← IGNORADO (mucho más rápido)
5min:  NEUTRAL   ← IGNORADO (más rápido)
15min: NEUTRAL   ← IGNORADO (más rápido)
30min: BULLISH   ← DOMINANTE (el que manda todo)

✅ APROBADO: Dominante bullish + 1/1 higher TFs bullish (100%)
Reason: "Dominant=30min (bullish), Higher TFs: 1/1 bullish, Lower TFs ignored: ['1min', '5min', '15min']"
Caso 4: Dominante = 1min (edge case) ⚠️
1min:  BULLISH   ← DOMINANTE
5min:  NEUTRAL   
15min: BEARISH   ← Permitido (1 bearish max cuando dominant=1min)
30min: BULLISH   

✅ APROBADO (con excepción): 1 bearish permitido cuando dominant=1min
Reason: "Dominant=1min (bullish), Higher TFs: 2/4 bullish"
🧠 Lógica del Sistema:
Principio fundamental:
Los timeframes lentos marcan la tendencia principal.
Los timeframes rápidos son solo el timing de entrada.
Por lo tanto:
Si dominante = 5min: Los timeframes > 5min (15m, 30m) DEBEN confirmar
Si dominante = 30min: Ya es la tendencia principal, no necesita confirmación mayor
Timeframes menores que el dominante son IGNORADOS (van a seguir al dominante)
✅ Ventajas de la Nueva Lógica:
Adaptativa: Si el mejor timeframe es 5min, entra con 5min
Jerárquica: Solo verifica que timeframes superiores no contradigan
Inteligente: No espera innecesariamente a timeframes que el ticker no usa
Realista: Respeta que timeframes lentos marcan tendencia
🎯 DFLI ahora:
📊 Analyzing 4 timeframes: ['1min', '5min', '15min', '30min']

1min:  Score=65, BULLISH
5min:  Score=70, BULLISH    ← Dominante (mejor score ponderado)
15min: Score=45, NEUTRAL
30min: Score=20, BEARISH    ← CONTRADICE

🎯 Dominant TF=5min, Score=70/100

Verificando consensus:
- Dominante (5min): BULLISH ✓
- Higher TFs: 5min, 15min, 30min
  - 5min: BULLISH ✓
  - 15min: NEUTRAL (ok)
  - 30min: BEARISH ✗

❌ RECHAZADO: 1 higher TF bearish ['30min'] (contradicts 5min)
Ahora el sistema es 100% lógico y adaptativo - usa el timeframe correcto automáticamente y solo verifica que timeframes superiores no contradigan.