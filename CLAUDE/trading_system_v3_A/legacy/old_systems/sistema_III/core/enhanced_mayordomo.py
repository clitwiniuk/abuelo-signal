#!/usr/bin/env python3
"""
Enhanced Mayordomo con Game Planning integrado
Combina el sistema actual con metodología profesional de Game Planning
+ MARKET CONDITION ANALYSIS para timing inteligente de entradas
"""

from typing import Dict, List, Optional
import logging
from datetime import datetime, time, timezone, timedelta
from .risk_manager import SmallcapMayordomo
from .game_plan_manager import GamePlanManager, TierLevel
import pandas as pd
import numpy as np

# Import market condition analysis
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from analysis.strategy_feature_enhancer import (
        enhance_macdv_features, 
        enhance_breakout_features, 
        enhance_orb_features,
        get_market_condition_summary
    )
    MARKET_CONDITIONS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Market condition analysis not available: {e}")
    MARKET_CONDITIONS_AVAILABLE = False

class EnhancedGamePlanMayordomo(SmallcapMayordomo):
    """
    Mayordomo mejorado con Game Planning profesional
    
    Mejoras clave:
    1. Pre-planificación diaria (antes de apertura)
    2. Ejecución ultra-rápida (decisiones pre-computadas)
    3. Sistema de tiers para priorización
    4. Escenarios What-If para diferentes condiciones
    5. Tracking de adherencia al plan
    """
    
    def __init__(self, config, broker=None, logger: logging.Logger = None):
        # Initialize parent Mayordomo
        super().__init__(config, broker, logger)
        
        # Initialize Game Plan Manager
        self.game_plan = GamePlanManager(config, self.logger)
        
        # Enhanced tracking
        self.daily_plan_created = False
        self.market_open_time = time(9, 30)  # 9:30 AM
        self.pre_market_time = time(8, 30)   # 8:30 AM for planning
        
        self.enhanced_stats = {
            'decisions_from_plan': 0,
            'decisions_reactive': 0,
            'plan_adherence_rate': 0.0,
            'average_decision_time_ms': 0.0,
            'tier_a_executions': 0,
            'tier_b_executions': 0,
            'tier_c_executions': 0
        }
        
        # DELAY + RETRY System
        self.delay_queue = {}  # symbol -> delay_info
        self.retry_attempts = {}  # symbol -> attempt_count
        self.max_retry_attempts = 3
        self.current_bar_counts = {}  # symbol -> bar_count (for timing delays)
        self.delayed_stop_orders = {}  # symbol -> stop_order_info (synchronized with delays)
        self.delayed_position_orders = {
            'trailing_stops': {},      # symbol -> trailing_stop_info
            'take_profit_targets': {}, # symbol -> take_profit_info  
            'ml_exits': {},           # symbol -> ml_exit_info
        }
        
        # ML Training Data Preservation
        self.ml_training_buffer = []  # Store all decisions for ML learning
        self.training_buffer_size = 20  # Flush every 20 decisions
        
        # Market condition analysis stats
        self.market_condition_stats = {
            'total_analyses': 0,
            'delayed_decisions': 0,
            'rejected_decisions': 0,
            'executed_decisions': 0,
            'successful_delays': 0,  # Delays that improved outcome
            'failed_delays': 0       # Delays that worsened outcome
        }
        
        self.logger.info("🎯 Enhanced Game Plan Mayordomo initialized")
    
    def create_daily_game_plan(self, pre_market_watchlist: List[Dict]) -> bool:
        """
        EJECUTAR PRE-MARKET (8:30 AM) - Crear plan del día
        
        Args:
            pre_market_watchlist: Lista de oportunidades identificadas pre-market
            
        Returns:
            bool: True si el plan se creó exitosamente
        """
        try:
            self.logger.info("🌅 INICIANDO CREACIÓN DE GAME PLAN DIARIO")
            self.logger.info("=" * 60)
            
            # Crear game plan usando el manager
            daily_plan = self.game_plan.create_daily_game_plan(pre_market_watchlist)
            
            if daily_plan:
                self.daily_plan_created = True
                self.enhanced_stats['planned_opportunities'] = len(daily_plan)
                
                # Log del plan creado
                self._log_daily_plan(daily_plan)
                
                self.logger.info("✅ GAME PLAN DIARIO CREADO EXITOSAMENTE")
                self.logger.info("🚀 Sistema listo para ejecución ultra-rápida")
                
                return True
            else:
                self.logger.error("❌ Error creando game plan diario")
                return False
                
        except Exception as e:
            self.logger.error(f"💥 Error en create_daily_game_plan: {e}")
            return False
    
    def evaluate_position_rotation(self, opportunity: Dict) -> Dict:
        """
        ENHANCED EXECUTION - Con Game Planning + Market Conditions + DELAY/RETRY System
        
        Esta función es llamada por el trader cuando llega una oportunidad.
        Ahora incluye análisis de market conditions y sistema de delay/retry.
        """
        start_time = datetime.now()
        symbol = opportunity.get('symbol', 'UNKNOWN')
        
        try:
            # 1. Update bar count for timing (needed for delays)
            self._update_bar_count(symbol)
            
            # 2. Check if this is a retry from delay queue
            if symbol in self.delay_queue:
                return self._handle_delayed_retry(symbol, opportunity)
            
            # 3. Get base decision (game plan or reactive)
            if self.daily_plan_created and symbol in self.game_plan.daily_game_plan:
                base_decision = self._execute_planned_decision(symbol, opportunity)
                self.enhanced_stats['decisions_from_plan'] += 1
                decision_source = 'planned'
            else:
                base_decision = super().evaluate_position_rotation(opportunity)
                self.enhanced_stats['decisions_reactive'] += 1
                decision_source = 'reactive'
                self.logger.warning(f"⚠️ {symbol} no está en game plan - usando decisión reactiva")
            
            # 4. If base decision is not EXECUTE, return as is
            if base_decision.get('action') != 'EXECUTE':
                return self._finalize_decision(base_decision, start_time, symbol, decision_source)
            
            # 5. MARKET CONDITION ANALYSIS - Only for EXECUTE decisions
            timing_decision = self._evaluate_market_timing(symbol, opportunity, base_decision)
            
            # 6. Handle timing decision
            if timing_decision['action'] == 'DELAY':
                return self._handle_delay_decision(symbol, timing_decision, opportunity, base_decision)
            elif timing_decision['action'] == 'REJECT':
                return self._finalize_decision(timing_decision, start_time, symbol, decision_source)
            else:  # EXECUTE
                enhanced_decision = self._merge_decisions(base_decision, timing_decision)
                return self._finalize_decision(enhanced_decision, start_time, symbol, decision_source)
            
            # Log decision con contexto
            self._log_enhanced_decision(symbol, decision, opportunity)
            
            return decision
            
        except Exception as e:
            self.logger.error(f"💥 Error en evaluate_position_rotation para {symbol}: {e}")
            # Fallback to parent method
            return super().evaluate_position_rotation(opportunity)
    
    def _execute_planned_decision(self, symbol: str, live_opportunity: Dict) -> Dict:
        """
        Ejecutar decisión basada en game plan pre-computado
        ULTRA-RÁPIDO - Sin cálculos complejos
        """
        
        # Get instant decision from game plan
        decision = self.game_plan.get_instant_decision(symbol, live_opportunity)
        
        if decision['action'] == 'EXECUTE':
            # Additional validation con las reglas del mayordomo original
            enhanced_decision = self._validate_planned_execution(symbol, decision, live_opportunity)
            
            # Track tier execution
            tier = decision.get('tier', 'unknown')
            if tier == 'A':
                self.enhanced_stats['tier_a_executions'] += 1
            elif tier == 'B':
                self.enhanced_stats['tier_b_executions'] += 1
            elif tier == 'C':
                self.enhanced_stats['tier_c_executions'] += 1
            
            return enhanced_decision
        else:
            return decision
    
    def _validate_planned_execution(self, symbol: str, planned_decision: Dict, opportunity: Dict) -> Dict:
        """
        Validar ejecución planificada con reglas del mayordomo
        Combina velocidad del plan con validaciones de riesgo
        """
        
        # 1. Check position limits (usando lógica original)
        current_positions = len([pos for pos in self.broker_positions.values() 
                               if isinstance(pos, dict) and abs(pos.get('position', 0)) > 0])
        
        max_positions = getattr(self.config, 'max_positions', 15)
        
        if current_positions >= max_positions:
            return {
                'action': 'REJECT',
                'reason': f'Maximum positions reached ({current_positions}/{max_positions})'
            }
        
        # 2. Check existing position for symbol
        if self._has_existing_position(symbol):
            return {
                'action': 'REJECT', 
                'reason': 'Already have position in this symbol'
            }
        
        # 3. Risk validation passed - execute planned decision
        planned_decision['validation'] = 'PASSED'
        planned_decision['positions_used'] = f"{current_positions + 1}/{max_positions}"
        
        return planned_decision
    
    def _log_daily_plan(self, daily_plan: Dict):
        """Log detallado del game plan creado"""
        
        tier_a = [p for p in daily_plan.values() if p.tier == TierLevel.TIER_A]
        tier_b = [p for p in daily_plan.values() if p.tier == TierLevel.TIER_B] 
        tier_c = [p for p in daily_plan.values() if p.tier == TierLevel.TIER_C]
        
        self.logger.info("📋 GAME PLAN DIARIO:")
        
        if tier_a:
            self.logger.info("🔥 TIER A (Primary Focus):")
            for entry in tier_a[:5]:  # Top 5
                self.logger.info(f"   #{entry.priority_rank} {entry.symbol} - "
                               f"Score: {entry.quality_score:.1f} | "
                               f"Setup: {entry.setup_type.value}")
        
        if tier_b:
            self.logger.info("⚡ TIER B (Secondary):")
            for entry in tier_b[:3]:  # Top 3
                self.logger.info(f"   #{entry.priority_rank} {entry.symbol} - "
                               f"Score: {entry.quality_score:.1f}")
        
        if tier_c:
            self.logger.info(f"📈 TIER C: {len(tier_c)} symbols (correlated/low prob)")
    
    def _log_enhanced_decision(self, symbol: str, decision: Dict, opportunity: Dict):
        """Enhanced logging con contexto del game plan"""
        
        action = decision['action']
        reason = decision.get('reason', 'No reason')
        exec_time = decision.get('execution_time_ms', 0)
        tier = decision.get('tier', 'N/A')
        
        if action == 'EXECUTE':
            confidence = decision.get('confidence', 0)
            self.logger.info(f"✅ EXECUTE {symbol} (Tier {tier}) - "
                           f"Confidence: {confidence:.2f} | "
                           f"Reason: {reason} | "
                           f"Speed: {exec_time:.1f}ms")
        else:
            self.logger.info(f"🚫 {action} {symbol} (Tier {tier}) - "
                           f"{reason} | "
                           f"Speed: {exec_time:.1f}ms")
    
    def _update_execution_stats(self, decision: Dict, execution_time_ms: float):
        """Update enhanced statistics"""
        
        # Update average execution time
        total_decisions = (self.enhanced_stats['decisions_from_plan'] + 
                          self.enhanced_stats['decisions_reactive'])
        
        if total_decisions > 0:
            current_avg = self.enhanced_stats['average_decision_time_ms']
            self.enhanced_stats['average_decision_time_ms'] = (
                (current_avg * (total_decisions - 1) + execution_time_ms) / total_decisions
            )
        
        # Update plan adherence rate
        if total_decisions > 0:
            self.enhanced_stats['plan_adherence_rate'] = (
                self.enhanced_stats['decisions_from_plan'] / total_decisions
            )
    
    def _has_existing_position(self, symbol: str) -> bool:
        """Check if we have existing position (from parent class)"""
        return (symbol in self.broker_positions and 
                abs(self.broker_positions[symbol].get('position', 0)) > 0)
    
    # =============================
    # MARKET TIMING & DELAY SYSTEM
    # =============================
    
    def _update_bar_count(self, symbol: str):
        """Update bar count for timing delays"""
        self.current_bar_counts[symbol] = self.current_bar_counts.get(symbol, 0) + 1
    
    def _evaluate_market_timing(self, symbol: str, opportunity: Dict, base_decision: Dict) -> Dict:
        """Evaluate market timing using our market condition analyzer"""
        
        if not MARKET_CONDITIONS_AVAILABLE:
            return {'action': 'EXECUTE', 'reason': 'Market condition analysis not available'}
        
        try:
            # Get market data from opportunity
            market_data = opportunity.get('market_data')
            strategy_name = opportunity.get('strategy', 'unknown')
            
            if not market_data:
                self.logger.warning(f"No market data available for {symbol} - proceeding with execution")
                return {'action': 'EXECUTE', 'reason': 'No market data available'}
            
            # Enhance features based on strategy
            if 'macdv' in strategy_name.lower():
                enhanced_features = enhance_macdv_features(
                    opportunity.get('features', {}), market_data, symbol
                )
            elif 'breakout' in strategy_name.lower():
                enhanced_features = enhance_breakout_features(
                    opportunity.get('features', {}), market_data, symbol
                )
            elif 'orb' in strategy_name.lower():
                enhanced_features = enhance_orb_features(
                    opportunity.get('features', {}), market_data, symbol
                )
            else:
                # Default to MACDV enhancement
                enhanced_features = enhance_macdv_features(
                    opportunity.get('features', {}), market_data, symbol
                )
            
            # Extract timing metrics
            overbought_penalty = enhanced_features.get('overbought_penalty', 0)
            entry_quality = enhanced_features.get('entry_quality_score', 0.5)
            timing_confidence = enhanced_features.get('timing_confidence_multiplier', 1.0)
            market_grade = enhanced_features.get('market_condition_grade', 'C')
            
            # Store ML training data
            self._store_ml_training_data(symbol, opportunity, enhanced_features, base_decision)
            
            # Timing decision logic
            timing_decision = self._make_timing_decision(
                symbol, overbought_penalty, entry_quality, timing_confidence, market_grade
            )
            
            # Update stats
            self.market_condition_stats['total_analyses'] += 1
            self.market_condition_stats[f"{timing_decision['action'].lower()}_decisions"] += 1
            
            return timing_decision
            
        except Exception as e:
            self.logger.error(f"Error in market timing analysis for {symbol}: {e}")
            return {'action': 'EXECUTE', 'reason': f'Market timing analysis failed: {e}'}
    
    def _make_timing_decision(self, symbol: str, overbought_penalty: float, 
                            entry_quality: float, timing_confidence: float, 
                            market_grade: str) -> Dict:
        """Make timing decision based on market conditions"""
        
        # Critical overbought - must reject
        if overbought_penalty > 0.8 or market_grade in ['F']:
            return {
                'action': 'REJECT',
                'reason': f'Critically overbought - Grade: {market_grade}, Penalty: {overbought_penalty:.2f}',
                'market_analysis': {
                    'overbought_penalty': overbought_penalty,
                    'entry_quality': entry_quality,
                    'timing_confidence': timing_confidence,
                    'market_grade': market_grade
                }
            }
        
        # Moderate overbought or poor quality - delay
        elif overbought_penalty > 0.5 or entry_quality < 0.4 or market_grade == 'D':
            delay_bars = self._calculate_delay_bars(overbought_penalty, entry_quality, market_grade)
            return {
                'action': 'DELAY',
                'reason': f'Moderate timing issues - Grade: {market_grade}, Quality: {entry_quality:.2f}',
                'retry_in_bars': delay_bars,
                'market_analysis': {
                    'overbought_penalty': overbought_penalty,
                    'entry_quality': entry_quality,
                    'timing_confidence': timing_confidence,
                    'market_grade': market_grade
                }
            }
        
        # Good timing - execute with enhanced confidence
        else:
            return {
                'action': 'EXECUTE',
                'reason': f'Good market timing - Grade: {market_grade}, Quality: {entry_quality:.2f}',
                'enhanced_timing_confidence': timing_confidence,
                'market_analysis': {
                    'overbought_penalty': overbought_penalty,
                    'entry_quality': entry_quality,
                    'timing_confidence': timing_confidence,
                    'market_grade': market_grade
                }
            }
    
    def _calculate_delay_bars(self, overbought_penalty: float, entry_quality: float, market_grade: str) -> int:
        """Calculate optimal delay bars based on conditions"""
        
        # Base delay
        if market_grade == 'D':
            base_delay = 5
        elif overbought_penalty > 0.7:
            base_delay = 4  
        elif overbought_penalty > 0.6:
            base_delay = 3
        else:
            base_delay = 2
        
        # Adjust for entry quality
        if entry_quality < 0.3:
            base_delay += 1
        
        # Smallcaps need shorter delays (more volatile)
        return min(base_delay, 5)  # Max 5 bars delay
    
    def _handle_delay_decision(self, symbol: str, timing_decision: Dict, 
                             opportunity: Dict, base_decision: Dict) -> Dict:
        """Handle delay decision by adding to delay queue"""
        
        delay_info = {
            'symbol': symbol,
            'original_opportunity': opportunity,
            'base_decision': base_decision,
            'timing_decision': timing_decision,
            'delay_start_bar': self.current_bar_counts.get(symbol, 0),
            'retry_in_bars': timing_decision['retry_in_bars'],
            'attempt': self.retry_attempts.get(symbol, 0) + 1,
            'timestamp': datetime.now()
        }
        
        self.delay_queue[symbol] = delay_info
        self.retry_attempts[symbol] = delay_info['attempt']
        
        self.logger.info(
            f"⏸️ DELAYED {symbol}: {timing_decision['reason']} "
            f"(Retry in {timing_decision['retry_in_bars']} bars, Attempt #{delay_info['attempt']})"
        )
        
        return {
            'action': 'DELAY',
            'symbol': symbol,
            'reason': timing_decision['reason'],
            'retry_in_bars': timing_decision['retry_in_bars'],
            'attempt': delay_info['attempt'],
            'market_analysis': timing_decision.get('market_analysis', {}),
            'timestamp': delay_info['timestamp'].isoformat()
        }
    
    def _handle_delayed_retry(self, symbol: str, opportunity: Dict) -> Dict:
        """Handle retry of delayed opportunity"""
        
        delay_info = self.delay_queue[symbol]
        current_bar = self.current_bar_counts.get(symbol, 0)
        bars_since_delay = current_bar - delay_info['delay_start_bar']
        
        if bars_since_delay >= delay_info['retry_in_bars']:
            # Time for retry - re-evaluate market conditions
            attempt = delay_info['attempt']
            
            self.logger.info(f"🔄 RETRY {symbol}: Attempt #{attempt} after {bars_since_delay} bars")
            
            # Check max attempts
            if attempt >= self.max_retry_attempts:
                # Max attempts reached - reject
                del self.delay_queue[symbol]
                self.retry_attempts.pop(symbol, None)
                
                return {
                    'action': 'REJECT',
                    'reason': f'Max retry attempts ({self.max_retry_attempts}) reached',
                    'attempts_made': attempt,
                    'original_reason': delay_info['timing_decision']['reason']
                }
            
            # Remove from delay queue for fresh evaluation  
            del self.delay_queue[symbol]
            
            # Re-evaluate with fresh market conditions
            fresh_timing_decision = self._evaluate_market_timing(
                symbol, opportunity, delay_info['base_decision']
            )
            
            if fresh_timing_decision['action'] == 'EXECUTE':
                # Successful retry
                self.market_condition_stats['successful_delays'] += 1
                enhanced_decision = self._merge_decisions(
                    delay_info['base_decision'], fresh_timing_decision
                )
                enhanced_decision['retry_success'] = True
                enhanced_decision['attempts_made'] = attempt
                
                # Signal that delayed stop orders for this symbol should now be processed
                enhanced_decision['process_delayed_stops'] = True
                
                return enhanced_decision
            
            elif fresh_timing_decision['action'] == 'DELAY':
                # Still need to delay - create new delay
                return self._handle_delay_decision(symbol, fresh_timing_decision, opportunity, delay_info['base_decision'])
            
            else:  # REJECT
                # Conditions worsened - reject
                self.market_condition_stats['failed_delays'] += 1
                fresh_timing_decision['attempts_made'] = attempt
                return fresh_timing_decision
        
        else:
            # Still waiting
            remaining_bars = delay_info['retry_in_bars'] - bars_since_delay
            return {
                'action': 'WAITING',
                'reason': f'Still waiting for retry ({remaining_bars} bars remaining)',
                'bars_remaining': remaining_bars,
                'attempt': delay_info['attempt'],
                'original_reason': delay_info['timing_decision']['reason']
            }
    
    def _store_ml_training_data(self, symbol: str, opportunity: Dict, 
                              market_conditions: Dict, base_decision: Dict):
        """Store ML training data for continuous learning"""
        
        training_record = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'strategy': opportunity.get('strategy', 'unknown'),
            
            # Original opportunity data
            'entry_price': opportunity.get('entry_price', 0),
            'volume_ratio': opportunity.get('volume_ratio', 1.0),
            'original_features': opportunity.get('features', {}),
            
            # Market condition features
            'market_condition_features': market_conditions,
            'overbought_penalty': market_conditions.get('overbought_penalty', 0),
            'entry_quality_score': market_conditions.get('entry_quality_score', 0.5),
            'timing_confidence_multiplier': market_conditions.get('timing_confidence_multiplier', 1.0),
            'market_grade': market_conditions.get('market_condition_grade', 'C'),
            
            # Base mayordomo decision
            'base_mayordomo_action': base_decision.get('action', 'UNKNOWN'),
            'base_decision_confidence': base_decision.get('confidence', 0.5),
            
            # Context
            'concurrent_positions': len([pos for pos in self.broker_positions.values() 
                                       if isinstance(pos, dict) and abs(pos.get('position', 0)) > 0]),
            'hour_of_day': datetime.now(timezone(timedelta(hours=-5))).hour + datetime.now(timezone(timedelta(hours=-5))).minute / 60.0,
            'retry_attempt': self.retry_attempts.get(symbol, 0),
            
            # To be filled later
            'timing_decision': None,
            'final_outcome': None,
            'trade_pnl': None
        }
        
        self.ml_training_buffer.append(training_record)
        
        # Periodic flush to prevent memory buildup
        if len(self.ml_training_buffer) >= self.training_buffer_size:
            self._flush_ml_training_data()
    
    def _flush_ml_training_data(self):
        """Flush ML training data to storage"""
        if not self.ml_training_buffer:
            return
        
        try:
            # Here you would save to database or file
            # For now, just log the count
            self.logger.info(f"💾 Flushed {len(self.ml_training_buffer)} ML training records")
            
            # TODO: Implement actual storage
            # self._save_to_ml_training_database(self.ml_training_buffer)
            
            # Clear buffer
            self.ml_training_buffer.clear()
            
        except Exception as e:
            self.logger.error(f"Error flushing ML training data: {e}")
    
    def _finalize_decision(self, decision: Dict, start_time: datetime, 
                          symbol: str, decision_source: str) -> Dict:
        """Finalize decision with timing and logging"""
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        decision['execution_time_ms'] = execution_time
        decision['decision_source'] = decision_source
        decision['symbol'] = symbol
        decision['timestamp'] = datetime.now().isoformat()
        
        # Update stats
        self._update_execution_stats(decision, execution_time)
        
        # Enhanced logging
        self._log_enhanced_decision(symbol, decision, {})
        
        return decision
    
    def _merge_decisions(self, base_decision: Dict, timing_decision: Dict) -> Dict:
        """Merge base decision with timing decision"""
        
        merged = base_decision.copy()
        merged.update({
            'enhanced_by_market_timing': True,
            'timing_confidence': timing_decision.get('enhanced_timing_confidence', 1.0),
            'market_analysis': timing_decision.get('market_analysis', {}),
            'timing_reason': timing_decision.get('reason', 'Good timing confirmed')
        })
        
        return merged
    
    def update_ml_trade_outcome(self, symbol: str, trade_outcome: Dict):
        """
        Update ML training data with actual trade outcomes - CRITICAL for learning
        Call this when a trade is closed to provide feedback for ML
        """
        try:
            # Find recent training records for this symbol and update outcomes
            updated_count = 0
            
            for training_record in self.ml_training_buffer:
                if (training_record['symbol'] == symbol and 
                    training_record.get('final_outcome') is None):
                    
                    # Update with actual trade outcome
                    training_record['final_outcome'] = trade_outcome
                    training_record['trade_pnl'] = trade_outcome.get('pnl_pct', 0)
                    training_record['trade_success'] = trade_outcome.get('pnl_pct', 0) > 0
                    
                    # Evaluate if delay/reject decisions were beneficial
                    timing_decision = training_record.get('timing_decision')
                    if timing_decision == 'DELAYED':
                        # If trade was profitable after delay, delay was good
                        training_record['delay_was_beneficial'] = training_record['trade_success']
                        if training_record['delay_was_beneficial']:
                            self.market_condition_stats['successful_delays'] += 1
                        else:
                            self.market_condition_stats['failed_delays'] += 1
                    
                    updated_count += 1
                    
                    self.logger.debug(f"🧠 Updated ML training data for {symbol}: "
                                    f"PnL: {trade_outcome.get('pnl_pct', 0):.1%}")
            
            if updated_count > 0:
                self.logger.info(f"📊 Updated {updated_count} ML training records for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error updating ML trade outcome for {symbol}: {e}")
    
    def get_delay_queue_status(self) -> Dict:
        """Get current status of delay queue for monitoring"""
        return {
            'active_delays': len(self.delay_queue),
            'symbols_delayed': list(self.delay_queue.keys()),
            'retry_attempts': dict(self.retry_attempts),
            'delayed_stop_orders': len(self.delayed_stop_orders),
            'delayed_trailing_stops': len(self.delayed_position_orders['trailing_stops']),
            'delayed_take_profits': len(self.delayed_position_orders['take_profit_targets']),
            'delayed_ml_exits': len(self.delayed_position_orders['ml_exits']),
            'ml_training_buffer_size': len(self.ml_training_buffer),
            'market_condition_stats': self.market_condition_stats.copy()
        }
    
    def register_delayed_stop_order(self, symbol: str, stop_order_info: Dict) -> None:
        """Register a stop order that should be synchronized with delayed entry"""
        self.delayed_stop_orders[symbol] = {
            'stop_order_info': stop_order_info,
            'registered_at_bar': self.current_bar_counts.get(symbol, 0),
            'delay_info': self.delay_queue.get(symbol)
        }
        
        self.logger.info(f"🛡️  Registered delayed stop order for {symbol} - "
                        f"Will sync with entry execution")
    
    def should_delay_stop_order(self, symbol: str) -> bool:
        """Check if stop order for symbol should be delayed due to pending entry"""
        return symbol in self.delay_queue or symbol in self.delayed_stop_orders
    
    def should_delay_position_order(self, symbol: str, order_type: str) -> bool:
        """Check if any position-related order should be delayed due to pending entry"""
        return (symbol in self.delay_queue or 
                symbol in self.delayed_stop_orders or
                symbol in self.delayed_position_orders.get(order_type, {}))
    
    def register_delayed_trailing_stop(self, symbol: str, trailing_info: Dict) -> None:
        """Register a trailing stop that should be synchronized with delayed entry"""
        self.delayed_position_orders['trailing_stops'][symbol] = {
            'trailing_info': trailing_info,
            'registered_at_bar': self.current_bar_counts.get(symbol, 0),
            'delay_info': self.delay_queue.get(symbol)
        }
        
        self.logger.info(f"📈 Registered delayed trailing stop for {symbol} - "
                        f"Will sync with entry execution")
    
    def register_delayed_take_profit(self, symbol: str, profit_info: Dict) -> None:
        """Register a take profit that should be synchronized with delayed entry"""
        self.delayed_position_orders['take_profit_targets'][symbol] = {
            'profit_info': profit_info,
            'registered_at_bar': self.current_bar_counts.get(symbol, 0),
            'delay_info': self.delay_queue.get(symbol)
        }
        
        self.logger.info(f"🎯 Registered delayed take profit for {symbol} - "
                        f"Will sync with entry execution")
    
    def register_delayed_ml_exit(self, symbol: str, ml_exit_info: Dict) -> None:
        """Register an ML exit that should be synchronized with delayed entry"""
        self.delayed_position_orders['ml_exits'][symbol] = {
            'ml_exit_info': ml_exit_info,
            'registered_at_bar': self.current_bar_counts.get(symbol, 0),
            'delay_info': self.delay_queue.get(symbol)
        }
        
        self.logger.info(f"🧠 Registered delayed ML exit for {symbol} - "
                        f"Will sync with entry execution")
    
    def process_delayed_stop_orders(self, symbol: str) -> None:
        """Process any delayed stop orders when entry is finally executed"""
        if symbol in self.delayed_stop_orders:
            stop_info = self.delayed_stop_orders.pop(symbol)
            self.logger.info(f"🛡️  Processing delayed stop order for {symbol} after entry execution")
            
            # Return the stop order info so the trading execution stage can create it
            return stop_info.get('stop_order_info')
        return None
    
    def get_delayed_stop_order_info(self, symbol: str) -> Dict:
        """Get delayed stop order info for a symbol without removing it"""
        if symbol in self.delayed_stop_orders:
            return self.delayed_stop_orders[symbol].get('stop_order_info')
        return None
    
    def process_all_delayed_orders(self, symbol: str) -> Dict:
        """Process all delayed orders when entry is finally executed"""
        processed_orders = {
            'stop_order': None,
            'trailing_stop': None,
            'take_profit': None,
            'ml_exit': None
        }
        
        # Process delayed stop orders
        if symbol in self.delayed_stop_orders:
            stop_info = self.delayed_stop_orders.pop(symbol)
            processed_orders['stop_order'] = stop_info.get('stop_order_info')
            self.logger.info(f"🛡️  Processing delayed stop order for {symbol}")
        
        # Process delayed trailing stops
        if symbol in self.delayed_position_orders['trailing_stops']:
            trailing_info = self.delayed_position_orders['trailing_stops'].pop(symbol)
            processed_orders['trailing_stop'] = trailing_info.get('trailing_info')
            self.logger.info(f"📈 Processing delayed trailing stop for {symbol}")
        
        # Process delayed take profits
        if symbol in self.delayed_position_orders['take_profit_targets']:
            profit_info = self.delayed_position_orders['take_profit_targets'].pop(symbol)
            processed_orders['take_profit'] = profit_info.get('profit_info')
            self.logger.info(f"🎯 Processing delayed take profit for {symbol}")
        
        # Process delayed ML exits
        if symbol in self.delayed_position_orders['ml_exits']:
            ml_info = self.delayed_position_orders['ml_exits'].pop(symbol)
            processed_orders['ml_exit'] = ml_info.get('ml_exit_info')
            self.logger.info(f"🧠 Processing delayed ML exit for {symbol}")
        
        return processed_orders
    
    def get_daily_performance_report(self) -> Dict:
        """
        Generar reporte de performance diario
        Incluye métricas de game planning
        """
        
        base_report = {
            'timestamp': datetime.now().isoformat(),
            'game_plan_created': self.daily_plan_created,
        }
        
        if self.daily_plan_created:
            # Game plan metrics
            game_plan_report = self.game_plan.generate_daily_report()
            base_report.update(game_plan_report)
            
            # Enhanced mayordomo metrics
            base_report['execution_stats'] = self.enhanced_stats
            
            # Decision speed comparison
            planned_decisions = self.enhanced_stats['decisions_from_plan']
            reactive_decisions = self.enhanced_stats['decisions_reactive']
            
            base_report['decision_breakdown'] = {
                'planned_decisions': planned_decisions,
                'reactive_decisions': reactive_decisions,
                'plan_coverage': planned_decisions / (planned_decisions + reactive_decisions) if (planned_decisions + reactive_decisions) > 0 else 0
            }
            
            # Tier execution breakdown
            base_report['tier_execution'] = {
                'tier_a': self.enhanced_stats['tier_a_executions'],
                'tier_b': self.enhanced_stats['tier_b_executions'], 
                'tier_c': self.enhanced_stats['tier_c_executions']
            }
            
            # Market condition & timing system metrics
            base_report['market_timing_system'] = self.market_condition_stats.copy()
            base_report['market_timing_system']['delay_success_rate'] = (
                self.market_condition_stats['successful_delays'] / 
                max(1, self.market_condition_stats['delayed_decisions'])
            )
            
            # Current delay queue status
            base_report['delay_queue_status'] = {
                'symbols_delayed': len(self.delay_queue),
                'active_delays': list(self.delay_queue.keys()),
                'retry_attempts_active': len(self.retry_attempts),
                'ml_training_buffer_size': len(self.ml_training_buffer)
            }
        
        return base_report
    
    def should_create_daily_plan(self) -> bool:
        """
        Determinar si es momento de crear el game plan diario
        Se ejecuta PRE-MARKET
        """
        current_time = datetime.now().time()
        
        # Create plan between 8:30 AM - 9:25 AM
        return (not self.daily_plan_created and 
                self.pre_market_time <= current_time < self.market_open_time)
    
    def reset_daily_plan(self):
        """Reset para nuevo día de trading"""
        self.daily_plan_created = False
        self.game_plan = GamePlanManager(self.config, self.logger)
        
        # Reset enhanced stats
        self.enhanced_stats = {
            'decisions_from_plan': 0,
            'decisions_reactive': 0,
            'plan_adherence_rate': 0.0,
            'average_decision_time_ms': 0.0,
            'tier_a_executions': 0,
            'tier_b_executions': 0,
            'tier_c_executions': 0
        }
        
        # Reset delay/retry system
        self.delay_queue.clear()
        self.retry_attempts.clear()
        self.current_bar_counts.clear()
        self.delayed_stop_orders.clear()
        
        # Reset delayed position orders
        for order_type in self.delayed_position_orders:
            self.delayed_position_orders[order_type].clear()
        
        # Flush any remaining ML training data
        if self.ml_training_buffer:
            self._flush_ml_training_data()
        
        # Reset market condition stats
        self.market_condition_stats = {
            'total_analyses': 0,
            'delayed_decisions': 0,
            'rejected_decisions': 0,
            'executed_decisions': 0,
            'successful_delays': 0,
            'failed_delays': 0
        }
        
        self.logger.info("🆕 Daily plan reset - Ready for new trading day with market timing system")