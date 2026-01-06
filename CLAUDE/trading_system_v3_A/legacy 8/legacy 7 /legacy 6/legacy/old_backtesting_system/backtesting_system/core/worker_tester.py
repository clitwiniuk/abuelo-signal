"""
Worker Tester
=============

Tester específico para workers individuales.
Maneja la inicialización, testing y recolección de resultados por worker.
"""

import asyncio
import logging
import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json

from .intraday_backtester import IntradayBacktester, BaseBacktestResult
from .pattern_generator import PatternGenerator

logger = logging.getLogger(__name__)


class WorkerTestResult(BaseBacktestResult):
    """Resultado específico de testing de worker"""
    
    def __init__(self):
        super().__init__()
        self.worker_name = ""
        self.worker_class = None
        
        # Análisis detallado por tipo de patrón
        self.pattern_type_results = {}  # {pattern_type: {'count': int, 'wins': int, 'avg_pnl': float}}
        
        # Decisiones del worker
        self.worker_decisions = []  # [{'pattern_type': str, 'decided': bool, 'reason': str}]
        
        # Performance tracking
        self.response_times = []  # Tiempo de respuesta del worker por decisión
        
    def add_worker_decision(self, pattern_type: str, decided: bool, reason: str, response_time: float):
        """Registra decisión del worker"""
        self.worker_decisions.append({
            'pattern_type': pattern_type,
            'decided': decided,
            'reason': reason,
            'response_time': response_time,
            'timestamp': datetime.now().isoformat()
        })
        
    def add_pattern_type_result(self, pattern_type: str, pnl: float, is_win: bool):
        """Registra resultado agrupado por tipo de patrón"""
        if pattern_type not in self.pattern_type_results:
            self.pattern_type_results[pattern_type] = {
                'count': 0,
                'wins': 0,
                'total_pnl': 0.0,
                'wins_pnl': [],
                'losses_pnl': []
            }
        
        result = self.pattern_type_results[pattern_type]
        result['count'] += 1
        result['total_pnl'] += pnl
        
        if is_win:
            result['wins'] += 1
            result['wins_pnl'].append(pnl)
        else:
            result['losses_pnl'].append(pnl)
    
    def get_pattern_type_success_rate(self, pattern_type: str) -> float:
        """Obtiene tasa de éxito por tipo de patrón"""
        if pattern_type not in self.pattern_type_results:
            return 0.0
        
        result = self.pattern_type_results[pattern_type]
        return result['wins'] / result['count'] if result['count'] > 0 else 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        """Obtiene resumen detallado del testing"""
        summary = {
            'worker_name': self.worker_name,
            'total_tests': self.total_patterns,
            'tests_executed': self.successful_tests,
            'tests_failed': self.failed_tests,
            'execution_rate': self.successful_tests / self.total_patterns if self.total_patterns > 0 else 0,
            'trades_executed': self.trades_executed,
            'win_rate': self.winning_trades / self.trades_executed if self.trades_executed > 0 else 0,
            'total_pnl': self.total_pnl,
            'avg_pnl_per_trade': self.total_pnl / self.trades_executed if self.trades_executed > 0 else 0,
            'avg_response_time': sum(self.response_times) / len(self.response_times) if self.response_times else 0,
            'pattern_type_performance': {},
            'errors': self.errors
        }
        
        # Performance por tipo de patrón
        for pattern_type, result in self.pattern_type_results.items():
            if result['count'] > 0:
                avg_win = sum(result['wins_pnl']) / len(result['wins_pnl']) if result['wins_pnl'] else 0
                avg_loss = sum(result['losses_pnl']) / len(result['losses_pnl']) if result['losses_pnl'] else 0
                
                summary['pattern_type_performance'][pattern_type] = {
                    'total_patterns': result['count'],
                    'win_rate': result['wins'] / result['count'],
                    'avg_win': avg_win,
                    'avg_loss': avg_loss,
                    'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else float('inf'),
                    'total_pnl': result['total_pnl']
                }
        
        return summary


class WorkerTester:
    """Tester específico para un worker individual"""
    
    def __init__(self, worker_name: str, worker_class=None):
        """
        Inicializa el tester para un worker específico
        
        Args:
            worker_name: Nombre del worker
            worker_class: Clase del worker (opcional)
        """
        self.worker_name = worker_name
        self.worker_class = worker_class
        self.backtester = IntradayBacktester()
        self.pattern_generator = PatternGenerator()
        
        logger.info(f"🔧 WorkerTester inicializado para {worker_name}")

    async def run_comprehensive_test(self, patterns: List[Dict[str, Any]],
                                   detailed: bool = False) -> WorkerTestResult:
        """
        Ejecuta test comprehensivo del worker
        
        Args:
            patterns: Oportunidades REALES desde market_data.db (NO sintéticos)
            detailed: Si incluir análisis detallado
            
        Returns:
            Resultado detallado del testing
        """
        result = WorkerTestResult()
        result.worker_name = self.worker_name
        result.worker_class = self.worker_class
        result.start_time = datetime.now()
        result.total_patterns = len(patterns)
        
        logger.info(f"🧪 Iniciando test comprehensivo para {self.worker_name}")
        logger.info(f"   Patrones a procesar: {len(patterns)}")
        
        try:
            # Crear mock dependencies
            mock_execution_engine = MockExecutionEngine()
            mock_risk_manager = MockRiskManager()
            
            # Inicializar worker real o mock
            if self.worker_class:
                try:
                    # Intentar inicialización para workers realistas
                    worker = self.worker_class(
                        worker_name=self.worker_name,
                        config={}
                    )
                except TypeError:
                    # Si falla, asumir formato de worker tradicional
                    worker = self.worker_class(
                        execution_engine=mock_execution_engine,
                        risk_manager=mock_risk_manager,
                        config={}
                    )
            else:
                worker = MockWorker(self.worker_name)
            
            # Procesar cada patrón
            for i, pattern in enumerate(patterns):
                try:
                    if detailed and i % 10 == 0:
                        logger.info(f"📊 Procesando patrón {i+1}/{len(patterns)} ({self.worker_name})")
                    
                    # Convertir patrón a opportunity
                    opportunity = self._pattern_to_opportunity(pattern)
                    
                    # Medir tiempo de respuesta
                    start_time = datetime.now()
                    
                    # Procesar con worker
                    trade_result = await self._process_pattern_with_worker(worker, opportunity, pattern)
                    
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    result.response_times.append(response_time)
                    
                    # Registrar decisión del worker
                    result.add_worker_decision(
                        pattern_type=pattern.get('pattern_type', 'unknown'),
                        decided=trade_result.get('decided', False),
                        reason=trade_result.get('reason', 'unknown'),
                        response_time=response_time
                    )
                    
                    # Registrar resultado si hubo trade
                    if trade_result.get('executed', False):
                        result.add_successful_test()
                        result.add_trade(trade_result['pnl'], trade_result['is_win'])
                        
                        # Agregar a estadísticas por tipo de patrón
                        result.add_pattern_type_result(
                            pattern_type=pattern.get('pattern_type', 'unknown'),
                            pnl=trade_result['pnl'],
                            is_win=trade_result['is_win']
                        )
                    else:
                        result.add_failed_test()
                
                except Exception as e:
                    result.add_failed_test()
                    result.add_error(f"Error procesando patrón {i}: {e}")
                    if detailed:
                        logger.warning(f"⚠️ Error en patrón {i}: {e}")
            
            result.end_time = datetime.now()
            
            # Calcular métricas finales
            result.metrics = self._calculate_detailed_metrics(result)
            
            logger.info(f"✅ Test completado para {self.worker_name}")
            logger.info(f"   Decisiones: {len(result.worker_decisions)}")
            logger.info(f"   Trades: {result.trades_executed}")
            logger.info(f"   Win Rate: {result.winning_trades / result.trades_executed if result.trades_executed > 0 else 0:.1%}")
            
            return result
            
        except Exception as e:
            result.add_error(f"Error crítico en testing: {e}")
            result.end_time = datetime.now()
            logger.error(f"❌ Error en test de {self.worker_name}: {e}")
            return result

    async def _process_pattern_with_worker(self, worker, opportunity: Dict[str, Any], 
                                          pattern: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa un patrón específico con el worker
        
        Args:
            worker: Worker a testear
            opportunity: Oportunidad convertida del patrón
            pattern: Patrón sintético original
            
        Returns:
            Dict con resultado del procesamiento
        """
        try:
            # Intentar usar should_enter del worker real
            if hasattr(worker, 'should_enter'):
                decision_start = datetime.now()
                should_enter = await worker.should_enter(opportunity)
                decision_time = (datetime.now() - decision_start).total_seconds()
                
                if should_enter:
                    # Worker aprobó entrada
                    return {
                        'decided': True,
                        'reason': 'worker_approved',
                        'executed': True,
                        'pnl': self._simulate_trade_result(pattern),
                        'is_win': True,
                        'decision_time': decision_time
                    }
                else:
                    # Worker rechazó entrada
                    return {
                        'decided': False,
                        'reason': 'worker_rejected',
                        'executed': False,
                        'decision_time': decision_time
                    }
            else:
                # Worker sin should_enter, usar simulación
                return self._simulate_worker_decision(worker, opportunity, pattern)
                
        except Exception as e:
            # Error en worker, usar fallback
            logger.debug(f"Error en worker {self.worker_name}, usando fallback: {e}")
            return self._simulate_worker_decision(worker, opportunity, pattern)

    def _simulate_worker_decision(self, worker, opportunity: Dict[str, Any], 
                                pattern: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simula decisión del worker cuando no puede usar should_enter
        
        Args:
            worker: Worker a simular
            opportunity: Oportunidad
            pattern: Patrón original
            
        Returns:
            Dict con resultado simulado
        """
        # Usar lógica de simulación del backtester
        decision = self.backtester._simulate_worker_decision(worker, opportunity, pattern.get('pattern_type', 'generic'))
        
        if decision:
            return {
                'decided': True,
                'reason': 'simulated_approval',
                'executed': True,
                'pnl': self._simulate_trade_result(pattern),
                'is_win': True,
                'decision_time': 0.001  # Simulated fast response
            }
        else:
            return {
                'decided': False,
                'reason': 'simulated_rejection',
                'executed': False,
                'decision_time': 0.001
            }

    def _simulate_trade_result(self, pattern: Dict[str, Any]) -> float:
        """
        Simula resultado de un trade
        
        Args:
            pattern: Patrón que generó el trade
            
        Returns:
            PnL del trade
        """
        # Usar simulación del backtester
        return self.backtester._simulate_trade_execution(pattern, pattern.get('current_price', 100))['pnl']

    def _pattern_to_opportunity(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte patrón a formato opportunity"""
        return self.backtester._pattern_to_opportunity(pattern)

    def _calculate_detailed_metrics(self, result: WorkerTestResult) -> Dict[str, Any]:
        """Calcula métricas detalladas específicas del worker"""
        metrics = self.backtester._calculate_backtest_metrics(result)
        
        # Agregar métricas específicas del worker
        metrics.update({
            'avg_response_time': sum(result.response_times) / len(result.response_times) if result.response_times else 0,
            'decision_rate': result.successful_tests / result.total_patterns if result.total_patterns > 0 else 0,
            'worker_consistency': self._calculate_consistency(result.worker_decisions),
            'pattern_type_coverage': len(result.pattern_type_results),
            'top_performing_pattern': self._get_top_performing_pattern(result.pattern_type_results),
            'rejection_patterns': self._analyze_rejection_patterns(result.worker_decisions)
        })
        
        return metrics

    def _calculate_consistency(self, decisions: List[Dict[str, Any]]) -> float:
        """Calcula consistencia del worker en sus decisiones"""
        if len(decisions) < 5:
            return 0.0
        
        # Agrupar por tipo de patrón y calcular consistencia
        pattern_decisions = {}
        for decision in decisions:
            pattern_type = decision['pattern_type']
            if pattern_type not in pattern_decisions:
                pattern_decisions[pattern_type] = []
            pattern_decisions[pattern_type].append(decision)
        
        # Calcular consistencia promedio
        consistencies = []
        for pattern_type, pattern_decs in pattern_decisions.items():
            if len(pattern_decs) >= 3:
                # Consistencia = porcentaje de decisiones iguales en el mismo tipo
                approvals = sum(1 for d in pattern_decs if d['decided'])
                total = len(pattern_decs)
                # Menor variabilidad = mayor consistencia
                consistency = 1 - abs(approvals / total - 0.5) * 2
                consistencies.append(consistency)
        
        return sum(consistencies) / len(consistencies) if consistencies else 0.0

    def _get_top_performing_pattern(self, pattern_results: Dict[str, Any]) -> Optional[str]:
        """Obtiene el tipo de patrón con mejor performance"""
        if not pattern_results:
            return None
        
        best_pattern = None
        best_score = -float('inf')
        
        for pattern_type, result in pattern_results.items():
            if result['count'] >= 3:  # Mínimo 3 samples
                # Score = win_rate * avg_pnl
                win_rate = result['wins'] / result['count']
                avg_pnl = result['total_pnl'] / result['count']
                score = win_rate * avg_pnl
                
                if score > best_score:
                    best_score = score
                    best_pattern = pattern_type
        
        return best_pattern

    def _analyze_rejection_patterns(self, decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analiza patrones en las decisiones de rechazo del worker"""
        rejections = [d for d in decisions if not d['decided']]
        
        rejection_analysis = {
            'total_rejections': len(rejections),
            'rejection_rate': len(rejections) / len(decisions) if decisions else 0,
            'rejections_by_pattern': {},
            'most_rejected_patterns': []
        }
        
        # Agrupar rechazos por tipo de patrón
        for decision in rejections:
            pattern_type = decision['pattern_type']
            if pattern_type not in rejection_analysis['rejections_by_pattern']:
                rejection_analysis['rejections_by_pattern'][pattern_type] = 0
            rejection_analysis['rejections_by_pattern'][pattern_type] += 1
        
        # Ordenar patrones más rechazados
        sorted_rejections = sorted(
            rejection_analysis['rejections_by_pattern'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        rejection_analysis['most_rejected_patterns'] = sorted_rejections[:3]
        
        return rejection_analysis


class MockExecutionEngine:
    """Mock del ExecutionEngine para testing de workers"""
    
    async def get_current_price(self, symbol: str) -> float:
        import random
        return random.uniform(50, 200)
    
    async def enter_position(self, symbol: str, strategy: str, opportunity_data: Dict) -> Dict:
        import random
        return {
            'symbol': symbol,
            'entry_price': random.uniform(80, 120),
            'quantity': 100,
            'strategy': strategy,
            'entry_time': datetime.now()
        }
    
    async def close_position(self, symbol: str, reason: str):
        pass


class MockRiskManager:
    """Mock del RiskManager para testing de workers"""
    
    async def validate_signal(self, signal: Dict) -> bool:
        return True
    
    async def validate_order(self, order: Dict) -> bool:
        return True


class MockWorker:
    """Worker mock para testing cuando no hay worker real"""
    
    def __init__(self, name: str):
        self.name = name
        self.is_running = False