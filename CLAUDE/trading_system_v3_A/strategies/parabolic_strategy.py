# strategies/parabolic_strategy.py
"""
Parabolic Strategy: Catches early-stage parabolic moves (LONG).
Wraps ParabolicExtensionDetector for the RealisticStrategyEngine.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from .base import BaseStrategy
from core.interfaces import Signal, SignalType, Position, MarketData
from core.parabolic_extension_detector import ParabolicExtensionDetector
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config

class ParabolicStrategy(BaseStrategy):
    """
    Parabolic Strategy - Catch the accumulation/acceleration phase.
    """

    def __init__(self, parameters: Dict[str, Any] = None):
        fallback_defaults = {
            'parabolic_roc_period_short': 3,
            'parabolic_roc_period_medium': 5,
            'parabolic_roc_period_long': 10,
            'parabolic_early_stage_roc_threshold': 0.05,
            'parabolic_middle_stage_roc_threshold': 0.10,
            'parabolic_late_stage_roc_threshold': 0.20,
            'parabolic_acceleration_threshold': 1.5,
            'parabolic_min_quality_score': 60.0,
            'parabolic_min_price': 1.0,
            'parabolic_max_price': 20.0,
            'stop_loss_pct': 0.04,
            'take_profit_pct': 0.10,
            'trailing_activation': 0.05,
            'trailing_distance': 0.03,
            'max_position_hours': 2.0
        }

        super().__init__("ParabolicStrategy", fallback_defaults)

        try:
            config_params = self._load_strategy_config('PARABOLIC_STRATEGY', fallback_defaults)
            if parameters:
                config_params.update(parameters)
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for Parabolic strategy: {e}")

        # Initialize Detector
        self.detector = ParabolicExtensionDetector(config=self._parameters)
        self.stop_manager = get_stop_loss_manager()
        
        # State
        self.bars_history = {} # {symbol: [bars]}
        self.min_bars_needed = 20

        self.logger.info("🚀 Parabolic Strategy Initialized (Long-Focused)")

    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        symbol = bar.symbol
        
        # Maintain history
        if symbol not in self.bars_history:
            self.bars_history[symbol] = []
        self.bars_history[symbol].append(bar)
        
        # Keep buffer size manageable
        if len(self.bars_history[symbol]) > 100:
            self.bars_history[symbol] = self.bars_history[symbol][-100:]
            
        history = self.bars_history[symbol]
        if len(history) < self.min_bars_needed:
            return None

        # Check existing position exits via Stop Manager
        # (This logic is usually handled by the engine or common checks, 
        # but the strategy can also signal exits)
        # Here we rely on the Engine calling `should_exit` or StopManager monitoring.

        # Run Detector
        try:
            p_signal = self.detector.detect_parabolic_extension(symbol, history)
            
            if not p_signal:
                return None

            # ENTRY LOGIC
            # Only enter if EARLY stage and Valid Opportunity
            if p_signal.long_entry_opportunity:
                # Anti-overtrading and other checks are simpler here than WorkerLogic
                # assuming Engine handles position limits.
                
                # Check price range
                if not (self._parameters['parabolic_min_price'] <= bar.close <= self._parameters['parabolic_max_price']):
                    return None

                # Create Signal
                return Signal(
                    signal_id=f"Parabolic-ENTRY-{symbol}-{bar.timestamp.strftime('%H%M%S')}",
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    strength=p_signal.strength,
                    price=bar.close,
                    timestamp=bar.timestamp,
                    strategy_name="ParabolicStrategy",
                    metadata={
                        'stage': p_signal.stage,
                        'acceleration': p_signal.acceleration,
                        'exhaustion': p_signal.exhaustion_score,
                        'setup_type': 'parabolic_early_extension'
                    }
                )
            
            # EXIT LOGIC (Exhaustion) - Only relevant if we knew we had a position, 
            # but _analyze_bar is typically for entries in this architecture?
            # Actually Engine calls _analyze_bar for new signals. 
            # If we want to signal an exit for an existing position, we return EXIT_LONG.
            # But we don't know here if we have a position easily unless we track it 
            # or pass it in. 
            # `should_exit` method handles exits.
            
            return None

        except Exception as e:
            self.logger.error(f"Error in Parabolic analysis: {e}")
            return None

    def should_exit(self, symbol: str, position: Position, current_price: float) -> bool:
        """
        Check for exhaustion exit
        """
        # First check standard stop manager
        if self.stop_manager.check_exit_conditions(symbol, MarketData(
            timestamp=datetime.now(), 
            open=current_price, high=current_price, low=current_price, close=current_price, volume=0
        )):
            return True

        # Check Parabolic Exhaustion
        if symbol in self.bars_history:
            history = self.bars_history[symbol]
            p_signal = self.detector.detect_parabolic_extension(symbol, history)
            if p_signal and (p_signal.exit_warning or p_signal.stage == 'LATE'):
                self.logger.info(f"⚠️ Parabolic Exhaustion Exit for {symbol}")
                return True
        
        return False
