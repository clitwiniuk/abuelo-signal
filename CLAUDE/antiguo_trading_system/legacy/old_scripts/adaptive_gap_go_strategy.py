#!/usr/bin/env python3
"""
Adaptive Gap & Go Strategy - Ejemplo del Sistema Híbrido
Estrategia tradicional Gap&Go que aprende y adapta sus parámetros usando trade write-ups

CARACTERÍSTICAS:
✅ Estrategia base estática (Gap&Go tradicional)
✅ Parámetros que se adaptan basado en resultados
✅ Integración con sistema de write-ups
✅ Salvaguardas anti-overfitting incluidas
"""

import logging
import asyncio
import numpy as np
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Union
from dataclasses import asdict

# Imports del framework adaptativo
from analysis.adaptive_strategy_framework import (
    AdaptiveStrategyBase, 
    create_adaptive_parameter,
    AntiOverfittingValidator
)
from analysis.bias_aware_writeup import BiasAwareAnalysisEngine

# Imports del sistema base
from core.interfaces import IStrategy, Signal, SignalType, MarketData
from strategies.gap_go_strategy import GapGoStrategy  # Estrategia base original

class AdaptiveGapGoStrategy(AdaptiveStrategyBase, IStrategy):
    """
    Gap & Go Strategy que aprende de cada trade
    
    PARÁMETROS ADAPTATIVOS (máximo 5 para evitar complejidad):
    1. gap_threshold - Mínimo gap % requerido
    2. volume_multiplier - Multiplicador de volumen vs promedio
    3. breakout_confirmation - % adicional sobre high para confirmar
    4. stop_loss_percent - % de stop loss
    5. take_profit_percent - % de take profit
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # Inicializar framework adaptativo
        super().__init__("AdaptiveGapGo")
        
        # Configuración base
        self._parameters = parameters or {}
        self.logger = logging.getLogger("Strategy.AdaptiveGapGo")
        
        # Inicializar estrategia base (para fallback)
        self.base_strategy = GapGoStrategy(parameters)
        
        # Sistema de análisis
        self.analysis_engine = None
        asyncio.create_task(self._initialize_analysis_engine())
        
        # Tracking de performance
        self.trades_executed = []
        self.adaptation_log = []
        
        self.logger.info("🧠 Adaptive Gap&Go Strategy initialized with ML learning")
    
    async def _initialize_analysis_engine(self):
        """Inicializar motor de análisis de forma asíncrona"""
        try:
            from analysis.bias_aware_writeup import create_bias_aware_analyzer
            self.analysis_engine = await create_bias_aware_analyzer()
        except Exception as e:
            self.logger.warning(f"Could not initialize analysis engine: {e}")
    
    def _initialize_adaptive_parameters(self):
        """Definir los 5 parámetros adaptativos máximo"""
        
        # 1. Gap Threshold - ¿Qué tan grande debe ser el gap?
        self.adaptive_params["gap_threshold"] = create_adaptive_parameter(
            name="gap_threshold",
            default_value=0.02,  # 2% gap mínimo
            min_val=0.005,       # 0.5% mínimo
            max_val=0.08,        # 8% máximo
            max_change_pct=0.15, # Máximo 15% cambio por vez
            confidence_threshold=0.65
        )
        
        # 2. Volume Multiplier - ¿Cuánto volumen necesitamos?
        self.adaptive_params["volume_multiplier"] = create_adaptive_parameter(
            name="volume_multiplier", 
            default_value=1.5,   # 1.5x volumen promedio
            min_val=1.0,         # Al menos volumen promedio
            max_val=3.0,         # Máximo 3x promedio
            max_change_pct=0.2,  # Máximo 20% cambio
            confidence_threshold=0.6
        )
        
        # 3. Breakout Confirmation - ¿Cuánto adicional sobre el high?
        self.adaptive_params["breakout_confirmation"] = create_adaptive_parameter(
            name="breakout_confirmation",
            default_value=0.01,  # 1% adicional sobre high
            min_val=0.002,       # 0.2% mínimo
            max_val=0.03,        # 3% máximo
            max_change_pct=0.25, # Puede cambiar más, es crítico
            confidence_threshold=0.7
        )
        
        # 4. Stop Loss - ¿Dónde poner el stop?
        self.adaptive_params["stop_loss_percent"] = create_adaptive_parameter(
            name="stop_loss_percent",
            default_value=0.03,  # 3% stop loss
            min_val=0.015,       # 1.5% mínimo
            max_val=0.08,        # 8% máximo
            max_change_pct=0.15, # Cambios conservadores
            confidence_threshold=0.75  # Alta confianza para cambios
        )
        
        # 5. Take Profit - ¿Cuándo tomar ganancias?
        self.adaptive_params["take_profit_percent"] = create_adaptive_parameter(
            name="take_profit_percent",
            default_value=0.06,  # 6% take profit
            min_val=0.025,       # 2.5% mínimo
            max_val=0.15,        # 15% máximo
            max_change_pct=0.2,  # Puede ser más agresivo
            confidence_threshold=0.6
        )
        
        self.logger.info("📊 Initialized 5 adaptive parameters with safety bounds")
    
    def _generate_base_signal(self, market_data: MarketData) -> Optional[Dict]:
        """Generar señal usando lógica Gap&Go tradicional"""
        
        try:
            # Usar estrategia base para señal inicial
            base_signals = self.base_strategy.generate_signals([market_data])
            
            if not base_signals:
                return None
            
            base_signal = base_signals[0]
            
            # Convertir a formato compatible
            return {
                'symbol': base_signal.symbol,
                'signal_type': base_signal.signal_type,
                'price': base_signal.price,
                'confidence': base_signal.confidence,
                'timestamp': datetime.now(),
                'strategy': 'gap_go_base'
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error generating base signal: {e}")
            return None
    
    def _apply_adaptive_parameters(self, base_signal: Dict, market_data: MarketData) -> Dict:
        """Aplicar parámetros adaptativos a la señal base"""
        
        adapted_signal = base_signal.copy()
        
        try:
            # Obtener valores adaptativos actuales
            gap_threshold = self.adaptive_params["gap_threshold"].current_value
            volume_mult = self.adaptive_params["volume_multiplier"].current_value
            breakout_conf = self.adaptive_params["breakout_confirmation"].current_value
            
            # Aplicar filtros adaptativos
            
            # 1. Verificar gap threshold adaptativo
            if hasattr(market_data, 'gap_percent'):
                gap_pct = getattr(market_data, 'gap_percent', 0)
                if abs(gap_pct) < gap_threshold:
                    self.logger.debug(f"🚫 Gap {gap_pct:.2%} below adaptive threshold {gap_threshold:.2%}")
                    return None  # Rechazar señal
            
            # 2. Verificar volumen adaptativo
            if hasattr(market_data, 'volume_ratio'):
                vol_ratio = getattr(market_data, 'volume_ratio', 1.0)
                if vol_ratio < volume_mult:
                    self.logger.debug(f"🚫 Volume ratio {vol_ratio:.1f} below adaptive threshold {volume_mult:.1f}")
                    return None
            
            # 3. Ajustar precio de entrada con confirmación adaptativa
            if adapted_signal['signal_type'] == SignalType.BUY:
                # Requerir breakout adicional adaptativo
                original_price = adapted_signal['price']
                adaptive_price = original_price * (1 + breakout_conf)
                adapted_signal['price'] = adaptive_price
                adapted_signal['adaptive_adjustment'] = breakout_conf
                
                self.logger.debug(f"🎯 Adaptive entry: ${original_price:.2f} → ${adaptive_price:.2f} (+{breakout_conf:.1%})")
            
            # 4. Calcular stops adaptativos
            stop_loss_pct = self.adaptive_params["stop_loss_percent"].current_value
            take_profit_pct = self.adaptive_params["take_profit_percent"].current_value
            
            entry_price = adapted_signal['price']
            adapted_signal['stop_loss'] = entry_price * (1 - stop_loss_pct)
            adapted_signal['take_profit'] = entry_price * (1 + take_profit_pct)
            
            # Mejorar confianza si parámetros son estables
            stability_avg = np.mean([p.stability_score for p in self.adaptive_params.values()])
            adapted_signal['confidence'] *= (0.8 + 0.2 * stability_avg)  # Boost si estable
            
            # Marcar como adaptativo
            adapted_signal['strategy'] = 'adaptive_gap_go'
            adapted_signal['parameters_snapshot'] = {
                name: param.current_value for name, param in self.adaptive_params.items()
            }
            
            return adapted_signal
            
        except Exception as e:
            self.logger.error(f"❌ Error applying adaptive parameters: {e}")
            return base_signal  # Fallback to base signal
    
    async def learn_from_trade_result(self, trade_result: Dict[str, Any]) -> Dict[str, Any]:
        """Aprender del resultado del trade - Punto clave del sistema híbrido"""
        
        learning_summary = {
            "parameters_updated": [],
            "analysis_quality": "unknown",
            "insights_generated": [],
            "system_health": "unknown"
        }
        
        try:
            self.logger.info(f"🧠 Learning from trade: {trade_result.get('symbol', '')} PnL: ${trade_result.get('pnl', 0):+.2f}")
            
            # 1. Generar análisis bias-aware
            if self.analysis_engine:
                analysis_result = await self.analysis_engine.analyze_trade_with_safeguards(trade_result)
                
                learning_summary["analysis_quality"] = analysis_result.get("system_health", "unknown")
                
                # Solo proceder si análisis tiene calidad suficiente
                writeup = analysis_result.get("writeup")
                if writeup and writeup.quality_metrics.overall_score() > 0.6:
                    
                    # 2. Aprender usando framework adaptativo
                    adaptation_result = self.learn_from_trade(trade_result)
                    learning_summary["parameters_updated"] = adaptation_result.get("parameters_updated", [])
                    
                    # 3. Extraer insights específicos de Gap&Go
                    insights = await self._extract_gapgo_insights(writeup, trade_result)
                    learning_summary["insights_generated"] = insights
                    
                    # 4. Log del aprendizaje
                    self.adaptation_log.append({
                        "timestamp": datetime.now(),
                        "trade_result": trade_result,
                        "analysis_quality": writeup.quality_metrics.overall_score(),
                        "parameters_changed": len(adaptation_result.get("parameters_updated", [])),
                        "insights_count": len(insights)
                    })
                    
                    # Notificar vía Telegram si hay cambios significativos
                    if len(adaptation_result.get("parameters_updated", [])) > 0:
                        await self._send_adaptation_notification(trade_result, adaptation_result)
                
                else:
                    self.logger.warning("⚠️ Analysis quality too low for learning")
            
            # Guardar trade para historia
            self.trades_executed.append(trade_result)
            
            # Limitar historia (anti-complejidad)
            if len(self.trades_executed) > 200:
                self.trades_executed = self.trades_executed[-150:]  # Mantener últimos 150
            
        except Exception as e:
            self.logger.error(f"❌ Error in learning process: {e}")
            learning_summary["error"] = str(e)
        
        return learning_summary
    
    async def _extract_gapgo_insights(self, writeup, trade_result: Dict) -> List[str]:
        """Extraer insights específicos de Gap&Go del analysis"""
        
        insights = []
        
        # Insight sobre timing
        if writeup.time_of_entry:
            entry_time = writeup.time_of_entry
            success = writeup.pnl > 0
            
            if success and entry_time:
                insights.append(f"Time {entry_time} showed success - consider prioritizing morning gaps")
            elif not success and entry_time:
                insights.append(f"Time {entry_time} failed - may need different approach for this time")
        
        # Insight sobre volumen
        if writeup.volume_avg_comparison > 0:
            vol_ratio = writeup.volume_avg_comparison
            if writeup.pnl > 0 and vol_ratio > 2.0:
                insights.append(f"High volume ({vol_ratio:.1f}x) correlated with success")
            elif writeup.pnl < 0 and vol_ratio < 1.2:
                insights.append(f"Low volume ({vol_ratio:.1f}x) may have contributed to failure")
        
        # Insight sobre gap size (específico de Gap&Go)
        gap_size = trade_result.get('gap_percent', 0)
        if gap_size != 0:
            if writeup.pnl > 0 and gap_size > 0.03:
                insights.append(f"Large gap ({gap_size:.1%}) successful - consider raising threshold")
            elif writeup.pnl < 0 and gap_size < 0.015:
                insights.append(f"Small gap ({gap_size:.1%}) failed - threshold may be too low")
        
        return insights[:5]  # Máximo 5 insights
    
    async def _send_adaptation_notification(self, trade_result: Dict, adaptation_result: Dict):
        """Notificar adaptaciones importantes vía Telegram"""
        
        try:
            from notifications.telegram_client import send_message
            
            symbol = trade_result.get('symbol', 'Unknown')
            pnl = trade_result.get('pnl', 0)
            updates = adaptation_result.get('parameters_updated', [])
            
            if updates:
                pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                
                message = f"""🧠 **ADAPTIVE STRATEGY LEARNED**
═══════════════════════════════

{pnl_emoji} **{symbol}** Gap&Go Trade: ${pnl:+.2f}

🔧 **Parameters Updated:**"""
                
                for update in updates[:3]:  # Máximo 3
                    param_name = update['parameter'].replace('_', ' ').title()
                    old_val = update['old_value']
                    new_val = update['new_value']
                    message += f"\n• {param_name}: {old_val:.3f} → {new_val:.3f}"
                
                message += f"""

📊 **System Health:**
• Parameters Stability: {np.mean([p.stability_score for p in self.adaptive_params.values()]):.1%}
• Total Adaptations: {len(self.adaptation_log)}

🎯 Strategy evolving based on real performance
═══════════════════════════════"""
                
                send_message(message, use_html=True)
                
        except Exception as e:
            self.logger.warning(f"Could not send adaptation notification: {e}")
    
    def _calculate_parameter_update(self, parameter, trade_result: Dict, performance_metric: float) -> Optional[float]:
        """Cálculo específico de Gap&Go para actualizaciones de parámetros"""
        
        pnl = trade_result.get('pnl', 0)
        param_name = parameter.name
        current_val = parameter.current_value
        
        # Lógica específica por parámetro
        if param_name == "gap_threshold":
            gap_size = trade_result.get('gap_percent', 0)
            if pnl > 0 and gap_size > current_val * 1.5:
                # Gap grande exitoso - aumentar threshold ligeramente
                return current_val * 1.03
            elif pnl < 0 and gap_size < current_val * 1.2:
                # Gap pequeño fallido - aumentar threshold
                return current_val * 1.05
        
        elif param_name == "volume_multiplier":
            vol_ratio = trade_result.get('volume_ratio', 1.0)
            if pnl > 0 and vol_ratio > current_val * 1.3:
                # Alto volumen exitoso - mantener o aumentar ligeramente
                return current_val * 1.02
            elif pnl < 0 and vol_ratio < current_val * 0.9:
                # Bajo volumen fallido - aumentar requerimiento
                return current_val * 1.08
        
        elif param_name == "breakout_confirmation":
            if pnl < 0:
                # Trade fallido - ser más conservador, requerir más confirmación
                return current_val * 1.05
            elif pnl > 0:
                # Trade exitoso - podemos ser ligeramente más agresivos
                return current_val * 0.98
        
        elif param_name == "stop_loss_percent":
            if pnl < 0 and abs(pnl) > 100:  # Pérdida grande
                # Aumentar stop loss para próximas
                return current_val * 1.08
            elif pnl > 0:
                # Trade exitoso - stop actual fue OK
                return current_val * 0.99
        
        elif param_name == "take_profit_percent":
            if pnl > 0:
                profit_pct = trade_result.get('max_profit_reached', 0)
                if profit_pct > current_val * 1.5:
                    # Dejamos dinero en la mesa - aumentar TP
                    return current_val * 1.05
        
        return None  # No cambio sugerido
    
    # Implementar métodos abstractos de IStrategy
    @property
    def name(self) -> str:
        return "Adaptive Gap & Go"
    
    @property 
    def parameters(self) -> Dict[str, Any]:
        return {name: param.current_value for name, param in self.adaptive_params.items()}
    
    def initialize(self):
        """Initialize strategy"""
        self.logger.info("🎯 Adaptive Gap&Go Strategy initialized")
    
    def on_bar(self, bar: MarketData):
        """Process new bar data"""
        # This will be called by the trading engine
        pass
    
    def on_position_update(self, position):
        """Handle position updates"""
        # This will be called when positions change
        pass
    
    def calculate_position_size(self, signal: Signal, available_capital: float) -> int:
        """Calculate position size for signal"""
        # Use adaptive position sizing
        stop_loss_pct = self.adaptive_params["stop_loss_percent"].current_value
        risk_per_trade = 0.02  # 2% risk per trade
        
        # Calculate position size based on risk
        risk_amount = available_capital * risk_per_trade
        price_per_share = signal.price
        stop_loss_price = price_per_share * (1 - stop_loss_pct)
        risk_per_share = price_per_share - stop_loss_price
        
        if risk_per_share > 0:
            position_size = int(risk_amount / risk_per_share)
            return max(1, min(position_size, 1000))  # Min 1, max 1000 shares
        
        return 100  # Default fallback
    
    def should_exit(self, position, current_price: float, current_time) -> tuple[bool, str]:
        """Determine if position should be exited using adaptive parameters"""
        
        if not position:
            return False, "No position"
        
        try:
            entry_price = position.avg_cost if hasattr(position, 'avg_cost') else position.price
            current_pnl_pct = (current_price - entry_price) / entry_price
            
            # Get adaptive exit parameters
            stop_loss_pct = self.adaptive_params["stop_loss_percent"].current_value
            take_profit_pct = self.adaptive_params["take_profit_percent"].current_value
            
            # Stop loss check
            if current_pnl_pct <= -stop_loss_pct:
                return True, f"Adaptive stop loss hit: {current_pnl_pct:.2%}"
            
            # Take profit check
            if current_pnl_pct >= take_profit_pct:
                return True, f"Adaptive take profit hit: {current_pnl_pct:.2%}"
            
            return False, "Hold position"
            
        except Exception as e:
            self.logger.error(f"Error in should_exit: {e}")
            return False, "Error in exit logic"
    
    def generate_signals(self, market_data_list: List[MarketData]) -> List[Signal]:
        """Implementación para interfaz IStrategy"""
        signals = []
        
        for market_data in market_data_list:
            try:
                # Generar señal adaptativa
                signal_dict = self.generate_signal(market_data)
                
                if signal_dict:
                    # Convertir a Signal object
                    signal = Signal(
                        symbol=signal_dict['symbol'],
                        signal_type=signal_dict['signal_type'],
                        price=signal_dict['price'],
                        confidence=signal_dict['confidence'],
                        timestamp=signal_dict.get('timestamp', datetime.now()),
                        metadata=signal_dict
                    )
                    signals.append(signal)
            
            except Exception as e:
                self.logger.error(f"Error generating signal for {getattr(market_data, 'symbol', 'unknown')}: {e}")
        
        return signals
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Info de la estrategia adaptativa"""
        
        base_info = {
            "name": "Adaptive Gap & Go",
            "type": "Adaptive ML Strategy",
            "version": "1.0",
            "parameters_count": len(self.adaptive_params),
            "trades_learned_from": len(self.trades_executed),
            "adaptations_made": len(self.adaptation_log)
        }
        
        # Añadir estado de parámetros
        params_info = {}
        for name, param in self.adaptive_params.items():
            params_info[name] = {
                "current_value": param.current_value,
                "default_value": param.bounds.default_value,
                "stability_score": param.stability_score,
                "adaptations_count": len(param.update_history)
            }
        
        base_info["adaptive_parameters"] = params_info
        
        # Health check
        system_health = self.get_strategy_health_report()
        base_info["system_health"] = system_health["overall_health"]
        
        return base_info

# Factory function para fácil uso
def create_adaptive_gap_go_strategy(parameters: Dict[str, Any] = None) -> AdaptiveGapGoStrategy:
    """Factory para crear estrategia adaptativa Gap&Go"""
    return AdaptiveGapGoStrategy(parameters)

if __name__ == "__main__":
    # Test de la estrategia adaptativa
    print("🧪 Testing Adaptive Gap&Go Strategy")
    print("=" * 50)
    
    strategy = create_adaptive_gap_go_strategy()
    info = strategy.get_strategy_info()
    
    print(f"Strategy: {info['name']}")
    print(f"Type: {info['type']}")
    print(f"Parameters: {info['parameters_count']}")
    print(f"Health: {info['system_health']}")
    
    # Test parameter bounds
    param = strategy.adaptive_params["gap_threshold"]
    print(f"\nGap Threshold Parameter:")
    print(f"  Current: {param.current_value:.3f}")
    print(f"  Bounds: {param.bounds.min_value:.3f} - {param.bounds.max_value:.3f}")
    print(f"  Stability: {param.stability_score:.2f}")
    
    print("\n✅ Adaptive Gap&Go Strategy Ready!")