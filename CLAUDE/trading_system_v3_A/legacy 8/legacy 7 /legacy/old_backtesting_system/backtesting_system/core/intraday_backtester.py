"""
Intraday Backtester
===================

Framework principal para ejecutar backtests intraday de workers de trading.
Proporciona infraestructura común para todos los tipos de testing.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import random


logger = logging.getLogger(__name__)


class BaseBacktestResult:
    """Resultado base de un backtest"""
    
    def __init__(self):
        self.worker_name = ""
        self.start_time = None
        self.end_time = None
        self.total_patterns = 0
        self.successful_tests = 0
        self.failed_tests = 0
        self.trades_executed = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.metrics = {}
        self.errors = []
        
    def add_error(self, error: str):
        """Agregar error al resultado"""
        self.errors.append(f"{datetime.now()}: {error}")
        
    def add_successful_test(self):
        """Marcar test como exitoso"""
        self.successful_tests += 1
        
    def add_failed_test(self):
        """Marcar test como fallido"""
        self.failed_tests += 1
        
    def add_trade(self, pnl: float, is_win: bool):
        """Agregar resultado de trade"""
        self.trades_executed += 1
        self.total_pnl += pnl
        if is_win:
            self.winning_trades += 1
        else:
            self.losing_trades += 1


class IntradayBacktester:
    """Backtester principal para testing intraday de workers"""
    
    def __init__(self, initial_capital: float = 100000.0, commission: float = 0.001):
        """
        Inicializa el backtester
        
        Args:
            initial_capital: Capital inicial para el backtest
            commission: Comisión por trade (0.1% = 0.001)
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.results = []
        
        logger.info(f"💰 IntradayBacktester inicializado - Capital: ${initial_capital:,.2f}, Comisión: {commission:.1%}")

    async def simulate_worker_execution(self, worker_class, patterns: List[Dict], 
                                      detailed_logging: bool = False) -> BaseBacktestResult:
        """
        Simula la ejecución de un worker con patrones dados
        
        Args:
            worker_class: Clase del worker a testear
            patterns: Lista de patrones sintéticos
            detailed_logging: Si loggear detalles
            
        Returns:
            Resultado del backtest
        """
        result = BaseBacktestResult()
        result.worker_name = worker_class.__name__ if worker_class else "MockWorker"
        result.start_time = datetime.now()
        
        try:
            logger.info(f"🧪 Simulando worker: {result.worker_name} con {len(patterns)} patrones")
            
            # Mock dependencies (ExecutionEngine, RiskManager)
            mock_execution_engine = MockExecutionEngine()
            mock_risk_manager = MockRiskManager()
            
            # Inicializar worker
            if worker_class:
                worker = worker_class(
                    execution_engine=mock_execution_engine,
                    risk_manager=mock_risk_manager,
                    config={}
                )
            else:
                # Mock worker
                worker = MockWorker(result.worker_name)
            
            # Procesar cada patrón
            for i, pattern in enumerate(patterns):
                try:
                    if detailed_logging and i % 10 == 0:
                        logger.info(f"📊 Procesando patrón {i+1}/{len(patterns)}")
                    
                    # Convertir patrón a formato opportunity
                    opportunity = self._pattern_to_opportunity(pattern)
                    
                    # Simular proceso del worker
                    trade_result = await self._simulate_worker_processing(worker, opportunity, pattern)
                    
                    if trade_result['executed']:
                        result.add_successful_test()
                        result.add_trade(trade_result['pnl'], trade_result['is_win'])
                    else:
                        result.add_failed_test()
                        
                except Exception as e:
                    result.add_failed_test()
                    result.add_error(f"Error procesando patrón {i}: {e}")
                    if detailed_logging:
                        logger.warning(f"⚠️ Error en patrón {i}: {e}")
            
            result.end_time = datetime.now()
            
            # Calcular métricas finales
            result.metrics = self._calculate_backtest_metrics(result)
            
            logger.info(f"✅ Backtest completado: {result.successful_tests} tests exitosos, "
                       f"{result.winning_trades} trades ganadores")
            
            return result
            
        except Exception as e:
            result.add_error(f"Error crítico en backtest: {e}")
            result.end_time = datetime.now()
            logger.error(f"❌ Error en backtest: {e}")
            return result

    def _pattern_to_opportunity(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte patrón sintético a formato opportunity del scanner"""
        return {
            'symbol': pattern.get('symbol', 'TEST'),
            'current_price': pattern.get('current_price', 100.0),
            'gap_percentage': pattern.get('gap_percentage', 0.0),
            'volume_ratio': pattern.get('volume_ratio', 1.0),
            'catalyst_type': pattern.get('catalyst_type', 'NONE'),
            'quality_score': pattern.get('quality_score', 50.0),
            'scan_timestamp': datetime.now().isoformat(),
            'bars': pattern.get('bars', []),
            'pattern_type': pattern.get('pattern_type', 'generic')
        }

    async def _simulate_worker_processing(self, worker, opportunity: Dict[str, Any], 
                                        pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Simula el procesamiento de una oportunidad por el worker"""
        
        # Simular decisión del worker (basada en pattern_type)
        pattern_type = pattern.get('pattern_type', 'generic')
        should_enter = self._simulate_worker_decision(worker, opportunity, pattern_type)
        
        if not should_enter:
            return {'executed': False, 'reason': 'worker_rejected'}
        
        # Simular ejecución de trade
        entry_price = opportunity['current_price']
        trade_result = self._simulate_trade_execution(pattern, entry_price)
        
        return {
            'executed': True,
            'entry_price': entry_price,
            'pnl': trade_result['pnl'],
            'is_win': trade_result['pnl'] > 0,
            'exit_reason': trade_result['exit_reason'],
            'hold_time': trade_result['hold_time']
        }

    def _simulate_worker_decision(self, worker, opportunity: Dict[str, Any], 
                                pattern_type: str) -> bool:
        """
        Simula la decisión de entrada del worker
        
        Estrategia:
        - Workers tienen preferencias por ciertos tipos de patrones
        - Calidad del patrón influye en la decisión
        - Factores aleatorios para simular variabilidad del mercado
        """
        
        quality_score = opportunity.get('quality_score', 50)
        gap_pct = abs(opportunity.get('gap_percentage', 0))
        volume_ratio = opportunity.get('volume_ratio', 1.0)
        
        # Base probability por tipo de patrón
        pattern_preferences = {
            'gap_go': 0.15 if gap_pct > 5 else 0.05,
            'bull_flag': 0.20 if 3 <= gap_pct <= 8 else 0.05,
            'macdv': 0.25,
            'daily_plays': 0.30,
            'vwap_breakout': 0.22,
            'momentum_breakout': 0.18,
            'generic': 0.10
        }
        
        base_probability = pattern_preferences.get(pattern_type, 0.10)
        
        # Ajustar por calidad
        quality_multiplier = (quality_score - 50) / 100  # -0.5 a +0.5
        adjusted_probability = base_probability * (1 + quality_multiplier)
        
        # Ajustar por volumen
        if volume_ratio > 2.0:
            adjusted_probability *= 1.2
        elif volume_ratio < 0.5:
            adjusted_probability *= 0.8
        
        # Factor aleatorio (simula incertidumbre del mercado)
        random_factor = random.uniform(0.8, 1.2)
        final_probability = max(0, min(1, adjusted_probability * random_factor))
        
        return random.random() < final_probability

    def _simulate_trade_execution(self, pattern: Dict[str, Any], entry_price: float) -> Dict[str, Any]:
        """Simula la ejecución de un trade y su resultado"""
        
        pattern_type = pattern.get('pattern_type', 'generic')
        pattern_quality = pattern.get('quality_score', 50) / 100  # 0-1
        
        # Define expected outcomes por tipo de patrón
        pattern_outcomes = {
            'gap_go': {'win_rate': 0.62, 'avg_win': 0.12, 'avg_loss': -0.06},
            'bull_flag': {'win_rate': 0.58, 'avg_win': 0.15, 'avg_loss': -0.05},
            'macdv': {'win_rate': 0.65, 'avg_win': 0.10, 'avg_loss': -0.05},
            'daily_plays': {'win_rate': 0.70, 'avg_win': 0.08, 'avg_loss': -0.04},
            'vwap_breakout': {'win_rate': 0.68, 'avg_win': 0.11, 'avg_loss': -0.05},
            'momentum_breakout': {'win_rate': 0.63, 'avg_win': 0.13, 'avg_loss': -0.06},
            'generic': {'win_rate': 0.50, 'avg_win': 0.08, 'avg_loss': -0.08}
        }
        
        # Get baseline para este patrón
        baseline = pattern_outcomes.get(pattern_type, pattern_outcomes['generic'])
        
        # Adjust por calidad del patrón
        quality_adjustment = (pattern_quality - 0.5) * 0.2  # +/- 10% basado en calidad
        
        # Determinar si es ganador
        effective_win_rate = max(0, min(1, baseline['win_rate'] + quality_adjustment))
        is_win = random.random() < effective_win_rate
        
        # Calcular PnL
        if is_win:
            avg_win = baseline['avg_win'] * (1 + quality_adjustment)
            pnl = random.normalvariate(avg_win, avg_win * 0.3)  # Variabilidad
        else:
            avg_loss = baseline['avg_loss'] * (1 - quality_adjustment)
            pnl = random.normalvariate(avg_loss, abs(avg_loss) * 0.4)
        
        # Tiempo de hold (en minutos)
        hold_time = random.uniform(15, 180)  # 15 min a 3 horas
        
        # Exit reason simulado
        exit_reasons = ['profit_target', 'stop_loss', 'time_limit', 'pattern_break']
        exit_reason = random.choice(exit_reasons)
        
        return {
            'pnl': pnl,
            'hold_time': hold_time,
            'exit_reason': exit_reason
        }

    def _calculate_backtest_metrics(self, result: BaseBacktestResult) -> Dict[str, Any]:
        """Calcula métricas del backtest"""
        
        metrics = {}
        
        # Métricas básicas
        metrics['total_patterns'] = result.total_patterns
        metrics['successful_tests'] = result.successful_tests
        metrics['failed_tests'] = result.failed_tests
        metrics['total_trades'] = result.trades_executed
        
        # Métricas de trades
        if result.trades_executed > 0:
            metrics['win_rate'] = result.winning_trades / result.trades_executed
            
            # PnL metrics
            winning_trades_pnl = []
            losing_trades_pnl = []
            
            # Reconstruct PnL per trade (simplificado)
            avg_win = result.total_pnl / result.trades_executed * 2 if result.winning_trades > 0 else 0
            avg_loss = result.total_pnl / result.trades_executed * 2 if result.losing_trades > 0 else 0
            
            metrics['avg_return'] = avg_win * result.winning_trades / result.trades_executed + \
                                   avg_loss * result.losing_trades / result.trades_executed
            metrics['profit_factor'] = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
            
        else:
            metrics['win_rate'] = 0.0
            metrics['avg_return'] = 0.0
            metrics['profit_factor'] = 0.0
        
        # Métricas de tiempo
        if result.start_time and result.end_time:
            duration = (result.end_time - result.start_time).total_seconds()
            metrics['duration_seconds'] = duration
            metrics['patterns_per_second'] = result.total_patterns / duration if duration > 0 else 0
        
        return metrics


class MockExecutionEngine:
    """Mock del ExecutionEngine para testing"""
    
    async def get_current_price(self, symbol: str) -> float:
        """Simula obtención de precio actual"""
        return random.uniform(50, 200)
    
    async def enter_position(self, symbol: str, strategy: str, opportunity_data: Dict) -> Dict:
        """Mock entry position"""
        return {
            'symbol': symbol,
            'entry_price': random.uniform(80, 120),
            'quantity': 100,
            'strategy': strategy,
            'entry_time': datetime.now()
        }
    
    async def close_position(self, symbol: str, reason: str):
        """Mock close position"""
        pass


class MockRiskManager:
    """Mock del RiskManager para testing"""
    
    async def validate_signal(self, signal: Dict) -> bool:
        """Mock signal validation"""
        return True
    
    async def validate_order(self, order: Dict) -> bool:
        """Mock order validation"""
        return True


class MockWorker:
    """Worker mock para cuando no hay dependencies reales"""
    
    def __init__(self, name: str):
        self.name = name
        self.is_running = False