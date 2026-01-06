# core/pipeline.py
"""
Trading Pipeline Pattern Implementation
Separates data collection, analysis, and execution for optimal performance
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import time

from core.interfaces import MarketData, Signal


class PipelineStage(ABC):
    """Base class for all pipeline stages"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Pipeline.{name}")
        self.metrics = {
            'execution_count': 0,
            'total_time': 0.0,
            'average_time': 0.0,
            'last_execution_time': 0.0
        }
    
    async def execute(self, input_data: Any) -> Any:
        """Execute the pipeline stage with metrics tracking"""
        start_time = time.time()
        
        try:
            self.logger.debug(f"🔄 Starting {self.name} stage")
            result = await self._process(input_data)
            
            execution_time = time.time() - start_time
            self._update_metrics(execution_time)
            
            self.logger.debug(f"✅ {self.name} completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"❌ {self.name} failed after {execution_time:.2f}s: {e}")
            raise
    
    @abstractmethod
    async def _process(self, input_data: Any) -> Any:
        """Process the input data (implemented by subclasses)"""
        pass
    
    def _update_metrics(self, execution_time: float):
        """Update stage performance metrics"""
        self.metrics['execution_count'] += 1
        self.metrics['total_time'] += execution_time
        self.metrics['average_time'] = self.metrics['total_time'] / self.metrics['execution_count']
        self.metrics['last_execution_time'] = execution_time
    
    def get_metrics(self) -> Dict[str, float]:
        """Get stage performance metrics"""
        return self.metrics.copy()


class TradingPipeline:
    """Main trading pipeline that orchestrates all stages"""
    
    def __init__(self, data_stage, analysis_stage, execution_stage):
        self.data_stage = data_stage
        self.analysis_stage = analysis_stage
        self.execution_stage = execution_stage
        self.logger = logging.getLogger("TradingPipeline")
        
        # Pipeline metrics
        self.pipeline_metrics = {
            'cycles_completed': 0,
            'total_pipeline_time': 0.0,
            'average_cycle_time': 0.0
        }
    
    async def run_cycle(self, symbols: List[str]) -> Dict[str, Any]:
        """Run a complete pipeline cycle"""
        cycle_start = time.time()
        
        try:
            self.logger.info(f"🚀 Starting pipeline cycle for {len(symbols)} symbols")
            
            # Stage 1: Data Collection (IBKR calls concentrated here)
            market_data = await self.data_stage.execute(symbols)
            self.logger.info(f"📊 Data collection completed: {len(market_data)} datasets")
            
            # Stage 2: Strategy Analysis (Pure computation, no IBKR calls)
            signals = await self.analysis_stage.execute(market_data)
            self.logger.info(f"🎯 Analysis completed: {len(signals)} signals generated")
            
            # Stage 3: Trading Execution (Minimal IBKR calls for orders only)
            execution_results = await self.execution_stage.execute(signals)
            orders_count = len(execution_results.get('orders', [])) if isinstance(execution_results, dict) else 0
            self.logger.info(f"💼 Execution completed: {orders_count} orders processed")
            
            # CRITICAL FIX: Synchronize positions between execution and analysis stages
            # This ensures strategies can track exits for positions opened in previous cycles
            await self._sync_positions_to_strategies()
            
            cycle_time = time.time() - cycle_start
            self._update_pipeline_metrics(cycle_time)
            
            self.logger.info(f"✅ Pipeline cycle completed in {cycle_time:.2f}s")
            
            return {
                'market_data': market_data,
                'signals': signals,
                'execution_results': execution_results,
                'cycle_time': cycle_time
            }
            
        except Exception as e:
            cycle_time = time.time() - cycle_start
            self.logger.error(f"❌ Pipeline cycle failed after {cycle_time:.2f}s: {e}")
            raise
    
    async def _sync_positions_to_strategies(self):
        """Synchronize current positions from execution stage to strategies and risk manager"""
        try:
            # Get current positions from execution stage
            execution_positions = getattr(self.execution_stage, 'positions', {})

            if execution_positions:
                self.logger.debug(f"🔄 Syncing {len(execution_positions)} positions to strategies and risk manager")

                # CRITICAL FIX: Sync positions to RiskManager first
                try:
                    from core.service_locator import ServiceLocator
                    service_locator = ServiceLocator()
                    risk_manager = await service_locator.get_or_create_risk_manager()
                    if risk_manager:
                        risk_manager.update_broker_positions(execution_positions)
                        self.logger.debug(f"✅ RiskManager positions updated: {list(execution_positions.keys())}")
                except Exception as e:
                    self.logger.error(f"❌ Failed to sync positions to RiskManager: {e}")

                # Notify all strategies in analysis stage about position updates
                for strategy in self.analysis_stage.executable_strategies:
                    if hasattr(strategy, 'on_position_update'):
                        for symbol, position_data in execution_positions.items():
                            # Create Position object from position data
                            from core.interfaces import Position
                            from datetime import datetime

                            # Extract all required fields with defaults
                            quantity = position_data.get('quantity', 0)
                            avg_price = position_data.get('avg_price', 0.0)
                            market_value = position_data.get('market_value', 0.0)

                            position = Position(
                                symbol=symbol,
                                quantity=quantity,
                                avg_price=avg_price,
                                market_price=avg_price,  # Use avg_price as market_price approximation
                                market_value=market_value,
                                unrealized_pnl=0.0,  # Default to 0 - will be calculated by strategy if needed
                                entry_time=datetime.now()  # Default to now - strategies can override if they have the real entry time
                            )
                            strategy.on_position_update(symbol, position)

        except Exception as e:
            self.logger.error(f"❌ Error syncing positions to strategies: {e}")
    
    def _update_pipeline_metrics(self, cycle_time: float):
        """Update pipeline performance metrics"""
        self.pipeline_metrics['cycles_completed'] += 1
        self.pipeline_metrics['total_pipeline_time'] += cycle_time
        self.pipeline_metrics['average_cycle_time'] = (
            self.pipeline_metrics['total_pipeline_time'] / 
            self.pipeline_metrics['cycles_completed']
        )
    
    def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Get comprehensive pipeline metrics"""
        return {
            'pipeline': self.pipeline_metrics.copy(),
            'data_stage': self.data_stage.get_metrics(),
            'analysis_stage': self.analysis_stage.get_metrics(),
            'execution_stage': self.execution_stage.get_metrics()
        }