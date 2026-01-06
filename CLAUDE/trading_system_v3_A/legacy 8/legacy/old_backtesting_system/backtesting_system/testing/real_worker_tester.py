"""
Real Worker Tester
==================

Herramienta para testear los workers REALES de trading_system_v3
SIN ejecutar órdenes reales, solo para verificar decisiones.

Usa los workers reales (MacdvWorkerLogic, etc.) pero mockea las dependencias
para que puedan ser testados sin ejecutar órdenes en IBKR.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Agregar directorios al path
root_dir = str(Path(__file__).parent.parent.parent)  # Ir hasta trading_system_v3
sys.path.append(root_dir)
sys.path.append(str(Path(__file__).parent))  # Agregar backtesting_system

logger = logging.getLogger(__name__)


class MockExecutionEngine:
    """Mock de ExecutionEngine para testing sin ejecutar órdenes reales"""
    
    def __init__(self):
        self.broker = MockBroker()
        self.worker_positions = {}  # Para simular posiciones de workers
        self.logger = logger
        
    async def load_opportunity_bars(self, opportunity: Dict[str, Any]) -> List[Any]:
        """Mock para cargar barras de datos"""
        # Extraer datos de la oportunidad
        bars_data = opportunity.get('bars', [])
        
        # Si no hay barras en la oportunidad, usar datos mock
        if not bars_data:
            return self._create_mock_bars()
        
        # Convertir datos mock a objetos bar si es necesario
        return self._convert_to_bar_objects(bars_data)
    
    def _create_mock_bars(self, count: int = 50) -> List[Any]:
        """Crear barras mock para testing"""
        import random
        from datetime import datetime, timedelta
        
        bars = []
        base_price = 10.0
        
        for i in range(count):
            # Generar precio realista
            price_change = random.uniform(-0.05, 0.05)  # ±5% por barra
            base_price *= (1 + price_change)
            
            # Crear bar mock
            bar = MockBar(
                close=base_price,
                high=base_price * random.uniform(1.001, 1.01),
                low=base_price * random.uniform(0.99, 0.999),
                open=base_price * random.uniform(0.995, 1.005),
                volume=random.randint(10000, 100000),
                timestamp=datetime.now() - timedelta(minutes=count-i)
            )
            bars.append(bar)
        
        return bars
    
    def _convert_to_bar_objects(self, bars_data: List[Dict]) -> List[Any]:
        """Convertir datos de barras a objetos bar"""
        from datetime import datetime
        
        bars = []
        for data in bars_data:
            bar = MockBar(
                close=float(data.get('close', 0)),
                high=float(data.get('high', 0)),
                low=float(data.get('low', 0)),
                open=float(data.get('open', 0)),
                volume=int(data.get('volume', 0)),
                timestamp=datetime.fromisoformat(data.get('timestamp', '')) if data.get('timestamp') else datetime.now()
            )
            bars.append(bar)
        
        return bars


class MockBroker:
    """Mock de broker para testing sin IBKR real"""
    
    def __init__(self):
        self.ib = MockIB()
        self.logger = logger


class MockIB:
    """Mock de IB interface para testing"""
    
    def __init__(self):
        self.logger = logger
        
    def reqHistoricalDataAsync(self, contract, **kwargs):
        """Mock de datos históricos"""
        f = asyncio.Future()
        f.set_result([])
        return f


class MockRiskManager:
    """Mock de RiskManager para testing"""
    
    def __init__(self):
        self.logger = logger


class MockBar:
    """Mock de bar object para compatibilidad"""
    
    def __init__(self, close: float, high: float, low: float, open: float, 
                 volume: int, timestamp):
        self.close = close
        self.high = high  
        self.low = low
        self.open = open
        self.volume = volume
        self.timestamp = timestamp
        self.vwap = close  # Mock VWAP


class RealWorkerTester:
    """Tester para workers reales de trading_system_v3"""
    
    def __init__(self, worker_name: str):
        self.worker_name = worker_name
        self.execution_engine = MockExecutionEngine()
        self.risk_manager = MockRiskManager()
        self.worker = None
        self.test_results = []
        
    def create_mock_config(self) -> object:
        """Crear configuración mock para worker"""
        class MockConfig:
            def __init__(self):
                # Configuración básica para workers
                self.min_volume_ratio = 0.7
                self.vwap_distance_threshold = 2.0
                self.volume_requirement = 1.5
                self.quality_threshold = 60.0
                
        return MockConfig()
    
    async def load_real_worker(self):
        """Cargar el worker real especificado"""
        try:
            if self.worker_name == 'macdv':
                from strategies.workers.macdv_worker_logic import MacdvWorkerLogic
                config = self.create_mock_config()
                self.worker = MacdvWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=config
                )
                
            elif self.worker_name == 'daily_plays':
                from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic
                config = self.create_mock_config()
                self.worker = DailyPlaysWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=config
                )
                
            elif self.worker_name == 'vwap':
                from strategies.workers.vwap_worker_logic import VWAPWorkerLogic
                config = self.create_mock_config()
                self.worker = VWAPWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=config
                )
                
            elif self.worker_name == 'generic_01':
                from strategies.workers.generic_01_worker_logic import Generic01WorkerLogic
                config = self.create_mock_config()
                self.worker = Generic01WorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=config
                )
                
            elif self.worker_name == 'volume_absorption':
                from strategies.workers.volume_absorption_worker_logic import VolumeAbsorptionWorkerLogic
                config = self.create_mock_config()
                self.worker = VolumeAbsorptionWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=config
                )
                
            elif self.worker_name == 'momentum_breakout':
                from strategies.workers.momentum_breakout_worker_logic import MomentumBreakoutWorkerLogic
                config = self.create_mock_config()
                self.worker = MomentumBreakoutWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=config
                )
                
            elif self.worker_name == 'vcp_smallcap':
                from strategies.workers.vcp_smallcap_worker_logic import VCPSmallcapWorkerLogic
                config = self.create_mock_config()
                self.worker = VCPSmallcapWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=config
                )

            elif self.worker_name == 'smallcaps_long':
                from strategies.workers.smallcaps_long_worker_logic import SmallCapsLongWorkerLogic
                config = self.create_mock_config()
                self.worker = SmallCapsLongWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=config
                )
                
            else:
                raise ValueError(f"Worker desconocido: {self.worker_name}")
            
            logger.info(f"✅ Worker real cargado: {self.worker_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cargando worker real {self.worker_name}: {e}")
            return False
    
    async def test_opportunity(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """Testear una oportunidad específica con el worker real"""
        
        if not self.worker:
            await self.load_real_worker()
        
        if not self.worker:
            return {
                'success': False,
                'error': f"No se pudo cargar worker {self.worker_name}",
                'decision': False
            }
        
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            logger.info(f"🧪 Testeando {symbol} con worker {self.worker_name}")
            
            # Verificar si el worker tiene el método should_enter
            if hasattr(self.worker, 'should_enter'):
                decision = await self.worker.should_enter(opportunity)
                return {
                    'success': True,
                    'decision': decision,
                    'worker_method': 'should_enter'
                }
            else:
                logger.warning(f"⚠️ Worker {self.worker_name} no tiene método should_enter")
                return {
                    'success': False,
                    'error': f"Worker {self.worker_name} no implementa should_enter",
                    'decision': False
                }
                
        except Exception as e:
            logger.error(f"❌ Error testeando oportunidad: {e}")
            return {
                'success': False,
                'error': str(e),
                'decision': False
            }
    
    async def test_real_opportunities(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Testear con oportunidades reales de la base de datos"""
        
        try:
            from core.data_loader_real import DataLoaderReal
            
            # Cargar oportunidades reales
            data_loader = DataLoaderReal()
            opportunities = data_loader.load_real_opportunities(
                symbols=symbols,
                start_date=None,
                end_date=None,
                min_volume=10000,
                pattern_type='all'
            )
            
            # Filtrar únicas
            unique_opportunities = []
            seen_combinations = set()
            
            for opp in opportunities:
                symbol = opp.get('symbol', '')
                timestamp = opp.get('timestamp', '')
                date_part = timestamp[:10] if len(timestamp) >= 10 else timestamp
                unique_key = f"{symbol}_{date_part}"
                
                if unique_key not in seen_combinations:
                    seen_combinations.add(unique_key)
                    unique_opportunities.append(opp)
            
            logger.info(f"📊 Cargadas {len(unique_opportunities)} oportunidades únicas para testing")
            
            # Testear primeras oportunidades
            test_count = min(10, len(unique_opportunities))
            test_results = []
            
            for i, opportunity in enumerate(unique_opportunities[:test_count]):
                result = await self.test_opportunity(opportunity)
                result['opportunity'] = opportunity
                test_results.append(result)
                
                logger.info(f"   Test {i+1}/{test_count}: {opportunity.get('symbol')} -> {result['decision']}")
            
            return test_results
            
        except Exception as e:
            logger.error(f"❌ Error testeando oportunidades reales: {e}")
            return []
    
    async def test_custom_opportunity(self, symbol: str = 'TEST_STOCK',
                                    gap_percentage: float = 3.0,
                                    volume_ratio: float = 1.5,
                                    current_price: float = 8.5,
                                    quality_score: float = 70,
                                    catalyst_type: str = 'NEWS') -> Dict[str, Any]:
        """Testear con oportunidad personalizada"""
        
        opportunity = {
            'symbol': symbol,
            'gap_percentage': gap_percentage,
            'volume_ratio': volume_ratio,
            'current_price': current_price,
            'quality_score': quality_score,
            'catalyst_type': catalyst_type,
            'bars': []
        }
        
        logger.info(f"🧪 Testeando oportunidad personalizada:")
        logger.info(f"   Símbolo: {symbol}")
        logger.info(f"   Gap: {gap_percentage}%")
        logger.info(f"   Volumen: {volume_ratio}x")
        logger.info(f"   Precio: ${current_price}")
        logger.info(f"   Calidad: {quality_score}")
        logger.info(f"   Catalyst: {catalyst_type}")
        
        return await self.test_opportunity(opportunity)


async def test_all_real_workers():
    """Testear todos los workers reales disponibles"""
    
    workers_to_test = [
        'macdv', 'daily_plays', 'vwap', 'generic_01',
        'volume_absorption', 'momentum_breakout', 'vcp_smallcap'
    ]
    
    results = {}
    
    for worker_name in workers_to_test:
        logger.info(f"\n{'='*50}")
        logger.info(f"🧪 TESTEANDO WORKER REAL: {worker_name.upper()}")
        logger.info(f"{'='*50}")
        
        try:
            tester = RealWorkerTester(worker_name)
            
            # Testear con oportunidad personalizada estándar
            result = await tester.test_custom_opportunity()
            
            results[worker_name] = result
            
            if result['success']:
                logger.info(f"✅ {worker_name}: DECISION = {result['decision']}")
            else:
                logger.error(f"❌ {worker_name}: ERROR = {result['error']}")
                
        except Exception as e:
            logger.error(f"❌ Error testeando {worker_name}: {e}")
            results[worker_name] = {
                'success': False,
                'error': str(e),
                'decision': False
            }
    
    # Resumen
    logger.info(f"\n{'='*50}")
    logger.info(f"📊 RESUMEN DE TESTING DE WORKERS REALES")
    logger.info(f"{'='*50}")
    
    for worker_name, result in results.items():
        if result['success']:
            decision = "✅ APROBADO" if result['decision'] else "❌ RECHAZADO"
            logger.info(f"{worker_name:<20}: {decision}")
        else:
            logger.info(f"{worker_name:<20}: ❌ ERROR - {result['error']}")
    
    return results


if __name__ == "__main__":
    # Ejecutar testing completo
    results = asyncio.run(test_all_real_workers())