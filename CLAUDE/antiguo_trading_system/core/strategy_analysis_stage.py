# core/strategy_analysis_stage.py
"""
Strategy Analysis Stage - Pipeline Pattern  
Pure computation stage with NO external calls (IBKR, network, etc.)
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
import time

from core.pipeline import PipelineStage
from core.interfaces import MarketData, Signal, IStrategy


class StrategyAnalysisStage(PipelineStage):
    """
    Stage 2: Strategy Analysis
    - Pure computation only - NO IBKR calls
    - Processes pre-fetched market data
    - Runs all strategies in parallel
    - Generates trading signals
    - Ultra-fast execution (no external dependencies)
    """
    
    def __init__(self, strategies: List[IStrategy], risk_manager=None):
        super().__init__("StrategyAnalysis")
        self.strategies = strategies if isinstance(strategies, list) else [strategies]
        self.risk_manager = risk_manager

        # Helper to get strategy name safely
        def _strategy_name(s):
            attr = getattr(s, 'name', None)
            return attr() if callable(attr) else attr if attr is not None else s.__class__.__name__

        # STRATEGY REGISTRY PATTERN: Smart strategy filtering
        # If we receive a MultiStrategyEngine, use it directly (it handles internal coordination)
        # If we receive individual strategies, apply anti-duplication filtering
        
        has_multi_strategy_engine = any(
            hasattr(s, 'strategies') and isinstance(getattr(s, 'strategies'), dict) 
            for s in self.strategies
        )
        
        if has_multi_strategy_engine:
            # MultiStrategyEngine present - use ONLY it (no filtering needed)
            self.executable_strategies = [s for s in self.strategies if hasattr(s, 'strategies')]
            multi_engine = self.executable_strategies[0]
            engine_name = _strategy_name(multi_engine)
            self.logger.info(f"🎯 STRATEGY REGISTRY: Using MultiStrategyEngine '{engine_name}' with {len(multi_engine.strategies)} internal strategies")
            self.logger.info(f"   Engine class: {multi_engine.__class__.__name__}")
            self.logger.info(f"   Internal strategies: {list(multi_engine.strategies.keys())}")
            
            # DEBUG: Check if it's the ML engine specifically
            if 'ML' in engine_name or 'ml' in engine_name.lower():
                self.logger.info("🤖 ML Multi-Strategy Engine detected and active!")
        else:
            # Individual strategies - apply anti-duplication filtering
            managed_strategy_names = set()
            for s in self.strategies:
                if hasattr(s, 'get_managed_strategy_names') and callable(getattr(s, 'get_managed_strategy_names')):
                    managed_strategies = s.get_managed_strategy_names()
                    managed_names = []
                    for ms in managed_strategies:
                        if isinstance(ms, str):
                            managed_names.append(ms)
                        else:
                            managed_names.append(_strategy_name(ms))
                    
                    self.logger.info(f"Engine '{_strategy_name(s)}' manages: {', '.join(managed_names)}")
                    managed_strategy_names.update(managed_names)
            
            self.executable_strategies = [s for s in self.strategies if _strategy_name(s) not in managed_strategy_names]
            self.logger.info(f"🎯 STRATEGY REGISTRY: Using individual strategies: {[_strategy_name(s) for s in self.executable_strategies]}")

        # Analysis settings
        self.max_concurrent_analysis = 5  # Concurrent symbol analysis
        self.analysis_timeout = 3.0  # Max 3 seconds per symbol analysis

        # Metrics
        self.analysis_count = 0
        self.error_count = 0
        self.total_signals = 0
        self.start_time = None
        self.analysis_times = []
        self.signal_counts = {'total': 0, 'buy': 0, 'sell': 0, 'exit': 0}
        
        self.logger.info(f"🧠 StrategyAnalysisStage initialized: max_concurrent={self.max_concurrent_analysis}")
    
    async def _process(self, market_data: Dict[str, List[MarketData]]) -> List[Signal]:
        """
        Analyze market data and generate trading signals
        
        Args:
            market_data: Dict mapping symbol -> List[MarketData] 
            
        Returns:
            List of trading signals
        """
        if not market_data:
            self.logger.warning("📭 No market data to analyze")
            return []
        
        self.logger.info(f"🧠 Analyzing {len(market_data)} symbols: {list(market_data.keys())[:10]}{'...' if len(market_data) > 10 else ''}")
        
        analysis_tasks = []
        symbols = list(market_data.keys())
        semaphore = asyncio.Semaphore(self.max_concurrent_analysis)
        
        for symbol in symbols:
            bars = market_data[symbol]
            if bars:
                # Sincronizar historial completo de barras con la estrategia antes de analizar
                for strategy in self.executable_strategies:
                    if hasattr(strategy, 'bars_history'):
                        prev_len = len(strategy.bars_history.get(symbol, []))
                        strategy.bars_history[symbol] = bars
                        if prev_len == 0 and len(bars) > 0:
                            strategy.logger.info(f"[SYNC] bars_history inicializado para {symbol} con {len(bars)} barras")
                        elif prev_len != len(bars):
                            strategy.logger.debug(f"[SYNC] bars_history actualizado para {symbol}: {prev_len} → {len(bars)} barras")
                
                task = asyncio.create_task(
                    self._analyze_symbol_with_semaphore(semaphore, symbol, bars)
                )
                analysis_tasks.append(task)

        if not analysis_tasks:
            self.logger.warning("📭 No analysis tasks created")
            return []
        
        self.logger.info(f"⚡ Running {len(analysis_tasks)} analysis tasks concurrently")
        
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*analysis_tasks, return_exceptions=True),
                timeout=30.0
            )
            
            all_signals = []
            analysis_count, error_count = 0, 0
            
            for result in results:
                if isinstance(result, Exception):
                    error_count += 1
                    self.logger.debug(f"Analysis task failed: {result}")
                elif isinstance(result, list):
                    all_signals.extend(result)
                    analysis_count += 1
                elif result is not None:
                    all_signals.append(result)
                    analysis_count += 1
            
            valid_signals = await self._validate_signals(all_signals)
            self._update_signal_metrics(valid_signals)
            
            self.logger.info(f"✅ Analysis completed: {analysis_count} successful, {error_count} errors, {len(valid_signals)} signals")
            return valid_signals
            
        except asyncio.TimeoutError:
            self.logger.error("⏰ Strategy analysis timed out after 30s")
            for task in analysis_tasks:
                if not task.done():
                    task.cancel()
            return []
    
    async def _analyze_symbol_with_semaphore(self, semaphore: asyncio.Semaphore, symbol: str, bars: List[MarketData]) -> List[Signal]:
        """Analyze single symbol with concurrency control"""
        async with semaphore:
            return await self._analyze_symbol(symbol, bars)
    
    async def _analyze_symbol(self, symbol: str, bars: List[MarketData]) -> List[Signal]:
        """
        Analyze a single symbol - PURE COMPUTATION ONLY
        NO external calls allowed here
        """
        start_time = time.time()
        signals = []
        
        try:
            self.logger.debug(f"🔍 Analyzing {symbol} ({len(bars)} bars)")
            
            # Get latest bar for analysis
            if not bars:
                return []
            
            latest_bar = bars[-1]
            
            # CRITICAL: Use timeout to prevent blocking
            try:
                strategy_signals = await asyncio.wait_for(
                    self._run_strategy_analysis(latest_bar),
                    timeout=self.analysis_timeout
                )
                
                if strategy_signals:
                    for signal in strategy_signals:
                        # Attach market data to signal for extended hours pricing
                        signal.market_data = latest_bar
                        signals.append(signal)
                        self.logger.debug(f"🎯 Generated {signal.signal_type} signal for {symbol}")
                
            except asyncio.TimeoutError:
                self.logger.warning(f"⏰ Analysis timeout for {symbol} after {self.analysis_timeout}s")
                return []
            
            # Track analysis performance
            analysis_time = time.time() - start_time
            self.analysis_times.append(analysis_time)
            
            # Keep only recent performance data
            if len(self.analysis_times) > 100:
                self.analysis_times = self.analysis_times[-50:]
            
            self.logger.debug(f"✅ {symbol} analysis completed in {analysis_time:.3f}s")
            
            return signals
            
        except Exception as e:
            analysis_time = time.time() - start_time
            self.logger.error(f"❌ Analysis failed for {symbol} after {analysis_time:.3f}s: {e}")
            return []
    
    async def _run_strategy_analysis(self, bar: MarketData) -> List[Signal]:
        """
        Run strategy analysis on a single bar across ALL strategies
        This MUST be pure computation - no external calls
        """
        signals = []
        
        try:
            # Use run_in_executor to prevent blocking if strategy has sync components
            loop = asyncio.get_event_loop()
            
            # Process bar with ALL strategies
            for strategy in self.strategies:
                try:
                    # If strategy.on_bar is async, call it directly
                    if asyncio.iscoroutinefunction(strategy.on_bar):
                        signal = await strategy.on_bar(bar)
                    else:
                        # If strategy.on_bar is sync, run in executor
                        signal = await loop.run_in_executor(None, strategy.on_bar, bar)
                    
                    if signal:
                        signals.append(signal)
                        
                except Exception as e:
                    # Handle both MarketData objects and dict
                    symbol = getattr(bar, 'symbol', bar.get('symbol', 'UNKNOWN') if isinstance(bar, dict) else 'UNKNOWN')
                    self.logger.debug(f"❌ Strategy {strategy.__class__.__name__} failed for {symbol}: {e}")
                    continue
            
            return signals
            
        except Exception as e:
            self.logger.error(f"❌ Strategy analysis failed: {e}")
            return []
    
    async def _validate_signals(self, signals: List[Signal]) -> List[Signal]:
        """Validate and filter signals"""
        valid_signals = []
        
        for signal in signals:
            if self._is_valid_signal(signal):
                # Apply risk management if available
                if self.risk_manager:
                    try:
                        # CRITICAL FIX: Ensure risk manager has updated positions before validation
                        await self.risk_manager.sync_broker_positions()
                        
                        if await self.risk_manager.validate_signal(signal):
                            valid_signals.append(signal)
                            self.logger.debug(f"✅ Signal approved by risk manager: {signal.symbol}")
                        else:
                            self.logger.info(f"🚫 Signal rejected by risk manager: {signal.symbol} {signal.signal_type.value}")
                    except Exception as e:
                        self.logger.warning(f"Risk manager error for {signal.symbol}: {e}")
                        # Include signal anyway if risk manager fails
                        valid_signals.append(signal)
                else:
                    valid_signals.append(signal)
        
        return valid_signals
    
    def _is_valid_signal(self, signal: Signal) -> bool:
        """Basic signal validation"""
        if not signal:
            return False
        
        if not signal.symbol:
            return False
        
        if not signal.signal_type:
            return False
        
        if signal.price <= 0:
            return False
        
        return True
    
    def _update_signal_metrics(self, signals: List[Signal]):
        """Update signal generation metrics"""
        self.signal_counts['total'] += len(signals)
        
        for signal in signals:
            signal_type = str(signal.signal_type).lower()
            if 'buy' in signal_type or 'long' in signal_type:
                self.signal_counts['buy'] += 1
            elif 'sell' in signal_type or 'short' in signal_type:
                self.signal_counts['sell'] += 1
            elif 'exit' in signal_type:
                self.signal_counts['exit'] += 1
    
    def get_analysis_stats(self) -> Dict[str, float]:
        """Get analysis performance statistics"""
        if not self.analysis_times:
            return {'avg_analysis_time': 0.0, 'min_time': 0.0, 'max_time': 0.0}
        
        return {
            'avg_analysis_time': sum(self.analysis_times) / len(self.analysis_times),
            'min_time': min(self.analysis_times),
            'max_time': max(self.analysis_times),
            'total_analyses': len(self.analysis_times),
            **self.signal_counts
        }