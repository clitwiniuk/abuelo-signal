# core/performance_metrics.py
"""
Performance Metrics para sistema multicapa
Trackea efectividad de: FinBERT → Strategy Selection → Execution
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class LayerPerformance:
    """Métricas de performance para cada layer"""
    layer_name: str
    total_signals: int = 0
    profitable_signals: int = 0
    total_pnl: float = 0.0
    avg_confidence: float = 0.0
    signal_history: List[Dict] = field(default_factory=list)
    
    @property
    def accuracy_rate(self) -> float:
        """Tasa de acierto"""
        return self.profitable_signals / max(self.total_signals, 1)
    
    @property
    def avg_pnl_per_signal(self) -> float:
        """PnL promedio por señal"""
        return self.total_pnl / max(self.total_signals, 1)

@dataclass
class TradeFlow:
    """Trackea el flujo completo de un trade"""
    symbol: str
    timestamp: datetime
    
    # FinBERT Layer
    finbert_catalyst: str
    finbert_strength: int
    finbert_confidence: float
    finbert_decision: str  # APPROVE/REJECT
    
    # Strategy Layer
    strategies_recommended: List[str]
    strategy_selected: str
    strategy_confidence: float
    strategy_decision: str  # APPROVE/REJECT
    
    # Execution Layer
    executed: bool
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    duration_hours: Optional[float] = None
    
    # Performance Attribution
    finbert_attribution: Optional[float] = None  # PnL attributed to FinBERT accuracy
    strategy_attribution: Optional[float] = None # PnL attributed to strategy selection
    execution_attribution: Optional[float] = None # PnL attributed to execution timing

class MultiLayerPerformanceTracker:
    """
    Trackea performance de sistema multicapa:
    FinBERT (catalyst detection) → Strategy Selection → Execution
    """
    
    def __init__(self, log_file: str = "logs/multilayer_performance.json"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True)
        
        # Performance por layer
        self.layers: Dict[str, LayerPerformance] = {
            'finbert': LayerPerformance('FinBERT_Catalyst'),
            'strategy': LayerPerformance('Strategy_Selection'),
            'execution': LayerPerformance('Trade_Execution'),
            'overall': LayerPerformance('Overall_System')
        }
        
        # Trade flows activos
        self.active_trades: Dict[str, TradeFlow] = {}
        self.completed_trades: List[TradeFlow] = []
        
        # Load historical data
        self._load_historical_data()
        
        logger.info("🎯 MultiLayerPerformanceTracker initialized")
    
    def start_trade_flow(self, symbol: str, finbert_result: Dict, strategies: List[str], 
                        selected_strategy: str, strategy_confidence: float) -> TradeFlow:
        """Iniciar tracking de un nuevo trade flow"""
        
        trade_flow = TradeFlow(
            symbol=symbol,
            timestamp=datetime.now(),
            finbert_catalyst=finbert_result.get('catalyst_type', 'UNKNOWN'),
            finbert_strength=finbert_result.get('catalyst_strength', 0),
            finbert_confidence=finbert_result.get('confidence', 0.0),
            finbert_decision='APPROVE',  # Si llegó aquí, fue aprobado
            strategies_recommended=strategies,
            strategy_selected=selected_strategy,
            strategy_confidence=strategy_confidence,
            strategy_decision='APPROVE',  # Si llegó aquí, fue aprobado
            executed=False
        )
        
        self.active_trades[symbol] = trade_flow
        
        # Update FinBERT metrics
        self._update_layer_signal('finbert', finbert_result, True)
        
        # Update Strategy metrics
        strategy_info = {
            'strategies': strategies,
            'selected': selected_strategy,
            'confidence': strategy_confidence
        }
        self._update_layer_signal('strategy', strategy_info, True)
        
        logger.info(f"🎬 Trade flow started: {symbol} | FinBERT: {finbert_result.get('catalyst_type')} "
                   f"({finbert_result.get('catalyst_strength')}/10) | Strategy: {selected_strategy}")
        
        return trade_flow
    
    def update_trade_execution(self, symbol: str, executed: bool, entry_price: Optional[float] = None):
        """Update cuando se ejecuta (o no) el trade"""
        if symbol not in self.active_trades:
            logger.warning(f"Trade flow not found for {symbol}")
            return
        
        trade_flow = self.active_trades[symbol]
        trade_flow.executed = executed
        trade_flow.entry_price = entry_price
        
        # Update execution metrics
        execution_info = {
            'symbol': symbol,
            'executed': executed,
            'entry_price': entry_price
        }
        self._update_layer_signal('execution', execution_info, executed)
        
        logger.info(f"⚡ Trade execution: {symbol} | Executed: {executed} | Price: {entry_price}")
    
    def complete_trade(self, symbol: str, exit_price: float, pnl: float):
        """Completar un trade y calcular attribution"""
        if symbol not in self.active_trades:
            logger.warning(f"Active trade not found for {symbol}")
            return
        
        trade_flow = self.active_trades.pop(symbol)
        
        # Complete trade data
        trade_flow.exit_price = exit_price
        trade_flow.pnl = pnl
        
        if trade_flow.entry_price:
            duration = datetime.now() - trade_flow.timestamp
            trade_flow.duration_hours = duration.total_seconds() / 3600
        
        # Calculate performance attribution
        self._calculate_attribution(trade_flow)
        
        # Update layer performances with final PnL
        is_profitable = pnl > 0
        
        # FinBERT attribution
        self._update_layer_pnl('finbert', trade_flow.finbert_attribution, is_profitable)
        
        # Strategy attribution  
        self._update_layer_pnl('strategy', trade_flow.strategy_attribution, is_profitable)
        
        # Execution attribution
        self._update_layer_pnl('execution', trade_flow.execution_attribution, is_profitable)
        
        # Overall performance
        self._update_layer_pnl('overall', pnl, is_profitable)
        
        # Store completed trade
        self.completed_trades.append(trade_flow)
        
        # Save to disk
        self._save_performance_data()
        
        logger.info(f"✅ Trade completed: {symbol} | PnL: ${pnl:.2f} | Duration: {trade_flow.duration_hours:.1f}h")
        
        return trade_flow
    
    def _calculate_attribution(self, trade: TradeFlow):
        """Calcular attribution de PnL a cada layer"""
        if not trade.pnl:
            return
        
        total_pnl = trade.pnl
        
        # FinBERT Attribution: Basado en catalyst strength y accuracy
        finbert_weight = 0.4  # 40% del PnL atribuido a catalyst detection
        strength_factor = trade.finbert_strength / 10.0  # Normalize to 0-1
        confidence_factor = trade.finbert_confidence
        
        trade.finbert_attribution = total_pnl * finbert_weight * strength_factor * confidence_factor
        
        # Strategy Attribution: Basado en strategy selection accuracy
        strategy_weight = 0.35  # 35% del PnL atribuido a strategy selection
        strategy_factor = trade.strategy_confidence
        
        trade.strategy_attribution = total_pnl * strategy_weight * strategy_factor
        
        # Execution Attribution: Resto del PnL
        execution_weight = 0.25  # 25% del PnL atribuido a execution timing
        trade.execution_attribution = total_pnl * execution_weight
    
    def _update_layer_signal(self, layer: str, signal_data: Dict, approved: bool):
        """Update layer con nueva señal"""
        layer_perf = self.layers[layer]
        layer_perf.total_signals += 1
        
        # Store signal in history
        signal_record = {
            'timestamp': datetime.now().isoformat(),
            'data': signal_data,
            'approved': approved
        }
        layer_perf.signal_history.append(signal_record)
        
        # Keep only last 1000 signals
        if len(layer_perf.signal_history) > 1000:
            layer_perf.signal_history = layer_perf.signal_history[-1000:]
    
    def _update_layer_pnl(self, layer: str, pnl_attribution: float, is_profitable: bool):
        """Update layer performance con PnL"""
        if pnl_attribution is None:
            return
            
        layer_perf = self.layers[layer]
        layer_perf.total_pnl += pnl_attribution
        
        if is_profitable:
            layer_perf.profitable_signals += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtener resumen de performance"""
        summary = {}
        
        for layer_name, layer_perf in self.layers.items():
            summary[layer_name] = {
                'accuracy_rate': f"{layer_perf.accuracy_rate:.1%}",
                'total_signals': layer_perf.total_signals,
                'profitable_signals': layer_perf.profitable_signals,
                'total_pnl': f"${layer_perf.total_pnl:.2f}",
                'avg_pnl_per_signal': f"${layer_perf.avg_pnl_per_signal:.2f}"
            }
        
        # Recent performance (last 7 days)
        recent_trades = [t for t in self.completed_trades 
                        if t.timestamp > datetime.now() - timedelta(days=7)]
        
        summary['recent_performance'] = {
            'trades_last_7d': len(recent_trades),
            'pnl_last_7d': f"${sum(t.pnl for t in recent_trades if t.pnl):.2f}",
            'avg_duration_hours': f"{sum(t.duration_hours for t in recent_trades if t.duration_hours) / max(len(recent_trades), 1):.1f}h"
        }
        
        return summary
    
    def get_layer_effectiveness(self) -> Dict[str, str]:
        """Determinar efectividad de cada layer"""
        effectiveness = {}
        
        for layer_name, layer_perf in self.layers.items():
            if layer_perf.total_signals < 10:
                effectiveness[layer_name] = "INSUFFICIENT_DATA"
            elif layer_perf.accuracy_rate >= 0.7:
                effectiveness[layer_name] = "EXCELLENT"
            elif layer_perf.accuracy_rate >= 0.6:
                effectiveness[layer_name] = "GOOD"
            elif layer_perf.accuracy_rate >= 0.5:
                effectiveness[layer_name] = "MODERATE"
            else:
                effectiveness[layer_name] = "POOR"
        
        return effectiveness
    
    def should_simplify_system(self) -> Dict[str, Any]:
        """Determinar si el sistema debería simplificarse"""
        effectiveness = self.get_layer_effectiveness()
        
        recommendations = {
            'simplify_recommended': False,
            'reasons': [],
            'actions': []
        }
        
        # Check if strategy layer is adding value
        if (effectiveness.get('strategy') in ['POOR', 'MODERATE'] and 
            effectiveness.get('finbert') in ['GOOD', 'EXCELLENT']):
            
            recommendations['simplify_recommended'] = True
            recommendations['reasons'].append('Strategy layer underperforming vs FinBERT')
            recommendations['actions'].append('Consider direct FinBERT → Execution for high-confidence signals')
        
        # Check if overall system is too complex
        overall_accuracy = self.layers['overall'].accuracy_rate
        finbert_accuracy = self.layers['finbert'].accuracy_rate
        
        if overall_accuracy < finbert_accuracy * 0.8:  # Overall is much worse than FinBERT alone
            recommendations['simplify_recommended'] = True
            recommendations['reasons'].append('System complexity reducing overall performance')
            recommendations['actions'].append('Test simplified FinBERT-only mode for high-strength catalysts')
        
        return recommendations
    
    def _load_historical_data(self):
        """Load historical performance data"""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    
                    # Load layers data
                    if 'layers' in data:
                        for layer_name, layer_data in data['layers'].items():
                            if layer_name in self.layers:
                                layer = self.layers[layer_name]
                                layer.total_signals = layer_data.get('total_signals', 0)
                                layer.profitable_signals = layer_data.get('profitable_signals', 0)
                                layer.total_pnl = layer_data.get('total_pnl', 0.0)
                                layer.signal_history = layer_data.get('signal_history', [])
                    
                    logger.info("📊 Historical performance data loaded")
        except Exception as e:
            logger.warning(f"Could not load historical data: {e}")
    
    def _save_performance_data(self):
        """Save performance data to disk"""
        try:
            data = {
                'layers': {},
                'last_updated': datetime.now().isoformat()
            }
            
            for layer_name, layer_perf in self.layers.items():
                data['layers'][layer_name] = {
                    'total_signals': layer_perf.total_signals,
                    'profitable_signals': layer_perf.profitable_signals,
                    'total_pnl': layer_perf.total_pnl,
                    'signal_history': layer_perf.signal_history[-100:]  # Keep last 100
                }
            
            with open(self.log_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Could not save performance data: {e}")

# Singleton instance
_performance_tracker: Optional[MultiLayerPerformanceTracker] = None

def get_performance_tracker() -> MultiLayerPerformanceTracker:
    """Get global performance tracker instance"""
    global _performance_tracker
    if _performance_tracker is None:
        _performance_tracker = MultiLayerPerformanceTracker()
    return _performance_tracker