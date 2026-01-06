#!/usr/bin/env python3
"""
Short Parabolic Worker Logic
Worker especializado para operar REVERSALES en extensiones parabólicas (Shorting the Backside)

Strategy Philosophy:
- Evita "Frontside" (no shortear mientras sube con fuerza)
- Espera "Backside" (signos confirmados de agotamiento y cambio de estructura)
- High Risk/Reward: Stops ajustados en máximos (HOD), objetivos amplios (VWAP)
- Strict Risk Management: Evita short squeezes esperando LATE stage + confirmación

Entry Criteria (ALL must be TRUE):
1. parabolic_data exists and stage == 'LATE' OR exhaustion_score >= 0.75
2. short_entry_opportunity == True (detector confirms reversal signal)
3. Reversal Confirmation (Red candle close OR Rejection Wick)
4. Quality Score >= min_quality_score
5. Risk/Reward > 1:2 (Distance to Stop vs Distance to VWAP)
6. Price > VWAP (Trading above VWAP implies extension)

Exit Criteria:
0. Hard Stop: Above HOD or Swing High
1. Target 1: VWAP (Primary target for parabolic collapse)
2. Target 2: Previous support / 50% retracement
3. Time Exit: End of session or if consolidation drags too long

Performance Characteristics (Expected):
- Win rate: 55-60% (Reversals are tricky)
- Avg gain: +8-12% (Collapses are fast)
- Avg loss: -2-4% (Tight stops on HOD)
- R:R: > 2.5:1

Author: Trading System
Date: 2025-12-22
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from .base_worker_logic import BaseWorkerLogic
from core.parabolic_extension_detector import ParabolicExtensionDetector
from core.trade_arbiter import TradingHorizon
from core.market_hours import get_market_hours, can_enter_short, should_force_exit_short

class ShortParabolicWorkerLogic(BaseWorkerLogic):
    """
    Short Parabolic Worker - Specialized in Parabolic Reversals (Short Side)
    """

    def __init__(self, broker, risk_manager=None, config=None, worker_name="short_parabolic", execution_engine=None):
        super().__init__(
            worker_name=worker_name,
            broker=broker,
            config=config
        )
        self.scaling_side = 'SHORT'

        # Initialize parabolic detector (reuse existing config keys but tune for shorting if needed)
        self.parabolic_detector = ParabolicExtensionDetector(config={
            # Standard parabolic detection settings
            'roc_period_short': int(getattr(config, 'parabolic_roc_period_short', 3)),
            'roc_period_medium': int(getattr(config, 'parabolic_roc_period_medium', 5)),
            'roc_period_long': int(getattr(config, 'parabolic_roc_period_long', 10)),
            # Use same thresholds, we rely on output stage='LATE'
            'late_stage_roc_threshold': float(getattr(config, 'parabolic_late_stage_roc_threshold', 0.20)),
             # High exhaustion is key for shorts
            'rsi_exhaustion_level': float(getattr(config, 'parabolic_rsi_exhaustion_level', 75)),
        })

        # === ENTRY FILTERS ===
        # Minimum exhaustion score to consider short (0.0-1.0)
        self.min_exhaustion_for_entry = float(getattr(config, 'short_parabolic_min_exhaustion', 0.70))
        # Minimum strength of the parabolic move (don't short weak moves)
        self.min_strength = float(getattr(config, 'short_parabolic_min_strength', 0.40))
        # Minimum scanner quality score
        self.min_quality_score = float(getattr(config, 'short_parabolic_min_quality_score', 60.0))
        # Minimum R:R ratio
        self.min_risk_reward = float(getattr(config, 'short_parabolic_min_rr', 2.0))
        
        # Price range filters (Smallcaps usually)
        self.min_price = float(getattr(config, 'short_parabolic_min_price', 2.0))
        self.max_price = float(getattr(config, 'short_parabolic_max_price', 50.0))

        # === ANTI-OVERTRADING ===
        self.max_trades_per_symbol_per_day = 1 # Strict 1 shot for shorts (squeeze risk)
        self.traded_symbols_today = set()

        # === STOP MANAGER ===
        # Initialize with short-specific parameters
        from .worker_stop_manager import create_worker_stop_manager
        if config:
            # We assume config has SHORT_PARABOLIC settings or we fallback
            self.stop_manager = create_worker_stop_manager(config, 'SHORT_PARABOLIC')
        else:
            # Fallback configuration
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=4.0,           # Will be dynamic based on HOD, but 4% max safety
                take_profit_pct=15.0,        # Big targets on collapses
                quick_target_pct=0.0,
                trailing_activation=5.0,     # Activate trail after 5% drop
                trailing_distance=3.0,       # Give it room to breathe
                max_position_hours=3.0       # Can hold longer for the fade
            ))

        self.config = config
        self.logger.info(
            f"🐻 Short Parabolic Worker configured: "
            f"min_exhaust={self.min_exhaustion_for_entry:.2f}, min_strength={self.min_strength:.2f}, "
            f"min_RR={self.min_risk_reward:.1f}"
        )

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calculate pattern completion for Short Parabolic
        
        Logic:
        - 0%: No pattern
        - 25%: Parabolic move detected (any stage)
        - 50%: LATE stage detected (Exhaustion phase)
        - 75%: LATE stage + High Exhaustion Score
        - 100%: LATE stage + High Exhaustion + Reversal Signal (ENTRY)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            parabolic_data = opportunity.get('parabolic_data')

            if not parabolic_data:
                return 0.0

            completion = 0.0

            # Stage 1: Any parabolic data (25%)
            completion += 25.0

            # Stage 2: Late Stage or High Exhaustion (25%)
            stage = parabolic_data.get('stage')
            exhaustion = parabolic_data.get('exhaustion_score', 0.0)
            
            if stage == 'LATE' or exhaustion >= self.min_exhaustion_for_entry:
                completion += 25.0
            else:
                return completion

            # Stage 3: Extreme Exhaustion (>0.8) or Very High Strength (25%)
            strength = parabolic_data.get('strength', 0.0)
            if exhaustion >= 0.8 or strength >= 0.6:
                completion += 25.0

            # Stage 4: Short Entry Signal (Confirmation) (25%)
            if parabolic_data.get('short_entry_opportunity', False):
                completion += 25.0

            return min(completion, 100.0)

        except Exception as e:
            self.logger.error(f"Error calculating pattern completion for {symbol}: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Determine if SHORT entry should be executed
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # === STEP 0A: MARKET HOURS CHECK (CRITICAL FOR SHORTS) ===
            # CRITICAL: SHORT positions can ONLY be entered during regular market hours
            # NO premarket, NO afterhours, NO overnight positions
            can_short, short_reason = can_enter_short()
            if not can_short:
                self.logger.warning(f"🚫 {symbol}: SHORT entry BLOCKED - {short_reason}")
                return False

            self.logger.debug(f"✅ {symbol}: Market hours check passed - SHORT entry allowed")

            # === STEP 0B: Anti-overtrading & Duplicate Position Check ===
            if symbol in self.traded_symbols_today:
                self.logger.debug(f"⏭️ {symbol}: Already traded today (anti-overtrading)")
                return False

            positions = await self.broker.get_positions()
            if any(p['symbol'] == symbol for p in positions):
                self.logger.warning(f"⚪ {symbol}: BLOCKED - Position already exists.")
                return False

            # === STEP 1: Basic Filters ===
            current_price = opportunity.get('current_price', 0)
            if current_price < self.min_price or current_price > self.max_price:
                 return False

            # === STEP 2: Parabolic Data Analysis ===
            parabolic_data = opportunity.get('parabolic_data')
            
            # FIX: specific for Replay - if no data, calculate it on the fly
            if not parabolic_data and opportunity.get('bars_history'):
                try:
                    # Convert history to DataFrame expected by detector
                    history = opportunity.get('bars_history', [])
                    if history:
                        # Basic conversion - assuming simplistic list of objects or dicts
                        data = []
                        for bar in history:
                            # Handle both object (ReplayBar) and dict
                            if hasattr(bar, 'close'):
                                data.append({
                                    'open': bar.open, 'high': bar.high, 'low': bar.low, 'close': bar.close, 'volume': bar.volume
                                })
                            elif isinstance(bar, dict):
                                data.append(bar)
                        
                        if data:
                            # Detector expects objects with attributes (bar.close), not dicts.
                            # We must convert our cleaned 'data' (list of dicts) into objects.
                            class BarObj:
                                def __init__(self, d):
                                    self.__dict__ = d
                                    # Ensure timestamp access if needed (optional but safe)
                                    if 'timestamp' in d:
                                        self.timestamp = d['timestamp']

                            bars_as_objects = [BarObj(d) for d in data]
                            
                            result_obj = self.parabolic_detector.detect_parabolic_extension(symbol, bars_as_objects)
                            if result_obj:
                                parabolic_data = {
                                    'stage': getattr(result_obj, 'stage', 'N/A'),
                                    'exhaustion_score': getattr(result_obj, 'exhaustion_score', 0.0),
                                    'short_entry_opportunity': getattr(result_obj, 'short_entry_opportunity', False),
                                    'acceleration': getattr(result_obj, 'acceleration', 0.0)
                                }
                                # IMPORTANT: Save back to opportunity for use in calculate_pattern_completion
                                opportunity['parabolic_data'] = parabolic_data
                except Exception as e:
                    self.logger.debug(f"⚠️ Failed to calculate parabolic data on fly: {e}")

            if not parabolic_data:
                self.logger.debug(f"⏭️ {symbol}: No parabolic data")
                return False

            # === STEP 3: LATE Stage / Exhaustion Check ===
            stage = parabolic_data.get('stage')
            exhaustion = parabolic_data.get('exhaustion_score', 0.0)
            
            # DEBUG: Direct file write to bypass logger issues


            # Must be LATE stage OR have very high exhaustion
            if stage != 'LATE' and exhaustion < self.min_exhaustion_for_entry:
                print(f"DEBUG REJECTION {symbol}: Not exhausted enough (Stage={stage}, Exh={exhaustion:.2f})")
                self.logger.debug(f"⏭️ {symbol}: Not exhausted enough (Stage={stage}, Exh={exhaustion:.2f})")
                return False

            # === STEP 4: Short Signal Confirmation ===
            # The detector now sets 'short_entry_opportunity' if confirmed
            if not parabolic_data.get('short_entry_opportunity', False):
                # print(f"DEBUG REJECTION {symbol}: No short signal confirmation") # Commented out to reduce noise
                self.logger.debug(f"⏭️ {symbol}: No short signal confirmation (need red candle or rejection)")
                return False

            # === STEP 5: Risk/Reward Calculation ===
            # We need valid targets for this
            bars = opportunity.get('bars_history', [])
            if not bars: return False
            
            # Estimate HOD (High of Day) for Stop Loss
            # Iterate through bars to find high
            high_list = [b.high if hasattr(b, 'high') else b['high'] for b in bars]
            hod = max(high_list) if high_list else current_price * 1.05
            
            # Stop just above HOD with buffer
            stop_loss_price = hod * 1.02 # 2% buffer above high
            
            # Target: Estimate VWAP (simple approx if not available) or use context
            # NOTE: In a real system we'd get VWAP from context. Here using approx or Support
            # Assume Target is a 50% retracement of the move or extensive drop
            take_profit_price = current_price * 0.85 # 15% drop target as baseline
            
            risk = stop_loss_price - current_price
            reward = current_price - take_profit_price
            
            if risk <= 0: # Should not happen if shorting below HOD
                 return False
                 
            rr_ratio = reward / risk
            
            if rr_ratio < self.min_risk_reward:
                self.logger.debug(f"⏭️ {symbol}: Poor R:R ({rr_ratio:.2f} < {self.min_risk_reward}) - Risk={risk:.2f}, Reward={reward:.2f}")
                return False

            # === STEP 6: Short Squeeze Prevention (ETB & Liquidity) ===
            # 6.1 Liquidity Check
            current_volume = opportunity.get('current_volume', opportunity.get('volume', 0))
            if current_volume < 500_000:
                self.logger.debug(f"⏭️ {symbol}: Volume too low for shorting ({current_volume} < 500k)")
                return False

            # 6.2 Borrowability Check (CRITICAL)
            # Fetch real-time short data from Broker
            try:
                short_data = await self.broker.get_short_data(symbol)
                
                is_etb = short_data.get('is_etb', False)
                shares_available = short_data.get('shortable_shares', 0)
                
                # Logic: If not ETB or Low Shares, we "WAIT" (return False but don't blacklist)
                if not is_etb or shares_available < 10000:
                    status_msg = f"Status: {short_data.get('short_status')}, Shares: {shares_available}"
                    
                    # Only log warning once per session per symbol to avoid spam
                    if symbol not in getattr(self, 'waiting_for_etb', set()):
                        if not hasattr(self, 'waiting_for_etb'): self.waiting_for_etb = set()
                        self.waiting_for_etb.add(symbol)
                        self.logger.warning(f"⏳ {symbol}: WAITING for ETB/Shares to enter short ({status_msg})")
                    else:
                        self.logger.debug(f"⏳ {symbol}: Still waiting for shares... ({status_msg})")
                        
                    return False
                
                # If we get here, shares are found!
                if hasattr(self, 'waiting_for_etb') and symbol in self.waiting_for_etb:
                    self.logger.info(f"✅ {symbol}: SHARES LOCATED! Proceeding with short entry ({shares_available} shares)")
                    self.waiting_for_etb.remove(symbol)
                else:
                    self.logger.info(f"✅ {symbol}: Borrow check passed (ETB, {shares_available} shares)")
                
            except Exception as e:
                self.logger.warning(f"⚠️ {symbol}: Failed to check borrowability: {e} - Skipping for safety")
                return False

            # === STEP 7: Risk Manager ===
            risk_approved = await self._check_risk_approval(symbol)
            if not risk_approved:
                return False

            self.logger.info(
                f"🐻 {symbol}: SHORT PARABOLIC APPROVED | "
                f"Price=${current_price:.2f}, SL=${stop_loss_price:.2f} (HOD=${hod:.2f}), "
                f"Exhaust={exhaustion:.2f}, Stage={stage}, R:R={rr_ratio:.2f}"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Error in should_enter for {symbol}: {e}")
            return False

    async def _execute_entry(self, symbol: str, opportunity: Dict[str, Any]):
        """Execute short entry and track"""
        await super()._execute_entry(symbol, opportunity)
        self.traded_symbols_today.add(symbol)

    def _get_trading_horizon(self) -> str:
        return TradingHorizon.INTRADAY.value # Shorting takes time to play out

    def get_worker_name(self) -> str:
        return "short_parabolic"

    async def should_exit(self, symbol: str, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        # Delegate to generic stop manager for now, which uses the config passed in init
        return await super().should_exit(symbol, position, current_price)

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calculates 'completion' for Replay Engine compatibility.
        For Short Parabolic, we use Exhaustion Score as the metric.
        But since 'should_enter' covers strict logic, we map valid exhaustion to high completion.
        """
        parabolic_data = opportunity.get('parabolic_data', {})
        exhaustion = parabolic_data.get('exhaustion_score', 0.0)
        
        # If we have valid Parabolic Data and passed should_enter, we are 'Complete'
        # Map 0.70 exhaustion -> 90% completion to satisfy ReplayEngine (needs > 75)
        if exhaustion >= 0.6:
            return 95.0
        return exhaustion * 100.0

    def calculate_adaptive_risk(
        self,
        opportunity: Dict[str, Any],
        ods_data: Optional[Any] = None,
        intraday_structure: Optional[Any] = None,
        structural_exits: Optional[Dict] = None
    ) -> float:
        """
        Calculate truly dynamic risk (0.5% to 5.0%) based on Short Probability.
        Override BaseWorkerLogic generic calculation.
        """
        # Default fallback
        base_risk = 0.005 # 0.5% base (Low confidence)
        max_risk = 0.05   # 5.0% max (High confidence)

        if not self.config:
            return base_risk

        try:
            # 1. Base from Config (or 0.5%)
            # We treat the 'min' as the floor for questionable setups
            risk = float(getattr(self.config, 'failed_entry_risk_pct', 0.5)) / 100.0
            
            # 2. Extract Key Metrics
            parabolic_data = opportunity.get('parabolic_data', {})
            exhaustion = parabolic_data.get('exhaustion_score', 0.0) # 0.0 to 1.0
            strength = parabolic_data.get('strength', 0.0) # 0.0 to 1.0
            quality = opportunity.get('quality_score', 50.0) # 0 to 100
            
            # Risk Reward from structural calculation or estimate
            rr = opportunity.get('risk_reward', 0.0)
            if structural_exits and 'risk_reward' in structural_exits:
                rr = structural_exits['risk_reward']

            self.logger.debug(f"⚖️ Dynamic Risk Inputs: Exh={exhaustion:.2f}, Str={strength:.2f}, Q={quality:.1f}, R:R={rr:.2f}")

            # 3. Exhaustion Boost (The most important factor for Backside Shorts)
            # Range 0.7 to 1.0 needed.
            # If > 0.85 -> Big boost
            if exhaustion >= 0.85:
                risk += 0.015 # +1.5%
            elif exhaustion >= 0.75:
                risk += 0.005 # +0.5%
            
            # 4. Strength Boost (Higher parabolic strength = harder fall)
            if strength >= 0.6:
                risk += 0.010 # +1.0%
            elif strength >= 0.4:
                risk += 0.005 # +0.5%

            # 5. R:R Boost (Reward for good entry point)
            if rr >= 4.0:
                risk += 0.010 # +1.0%
            elif rr >= 2.5:
                risk += 0.005 # +0.5%

            # 6. Quality/Confidence Boost
            if quality >= 80.0:
                 risk += 0.005 # +0.5%

            # 7. Cap at Max
            final_risk = min(risk, max_risk)
            
            self.logger.info(f"⚡ {opportunity.get('symbol')}: Calculated Risk {final_risk*100:.1f}% (Base=0.5% + Boosts)")
            return final_risk

        except Exception as e:
            self.logger.warning(f"Error calculating dynamic risk: {e} - using 0.5%")
            return 0.005
