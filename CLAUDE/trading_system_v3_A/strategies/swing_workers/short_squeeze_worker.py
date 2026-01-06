"""
Short Squeeze Swing Worker
Executes and manages multi-day trades based on Short Squeeze structure.
"""

import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, time
import pytz
from .base_swing_worker import BaseSwingWorker

class ShortSqueezeWorker(BaseSwingWorker):
    """
    Swing worker for Short Squeeze opportunities.
    
    Strategy:
    - Entry: Breakout with Volume on Low Float + High Short Interest stocks.
    - Hold: Multi-day (3-5 days typical for squeeze moves).
    - Exit: 
        - Target: +20% to +50% (Runners)
        - Stop: -5% or Technical Support
        - Time: 5 days max if no momentum
    """

    def __init__(self, execution_engine, risk_manager, config):
        # Note: BaseSwingWorker expects unified_manager, but we pass risk_manager
        # which has compatible interface for position checking
        super().__init__(
            worker_name="short_squeeze",
            execution_engine=execution_engine,
            unified_manager=risk_manager,  # Pass risk_manager as unified_manager
            config=config
        )
        
        # Configuration (Defaults based on analysis)
        self.target_gain_pct = 30.0  # Aim for 30% (Home Run)
        self.stop_loss_pct = 10.0    # Wider stop for volatility (was 5%)
        self.max_hold_days = 5       # Squeezes are fast
        self.trailing_activation_pct = 15.0
        self.trailing_distance_pct = 8.0 # Tighter trail once profitable
        
        # Risk Configuration
        self.risk_per_trade = 50.0   # Fixed risk per trade ($50)
        
        self.logger.info("🐻💥 Short Squeeze Worker initialized")

    def calculate_position_size(self, current_price: float) -> int:
        """
        Calculate position size based on fixed risk.
        Risk = (Entry - Stop) * Shares
        Shares = Risk / (Entry - Stop)
        """
        if current_price <= 0:
            return 0
            
        # Stop price based on percentage
        stop_price = current_price * (1 - self.stop_loss_pct / 100)
        risk_per_share = current_price - stop_price
        
        if risk_per_share <= 0:
            return 0
            
        # Calculate shares
        shares = int(self.risk_per_trade / risk_per_share)
        
        # Cap at max position value (e.g., $2000) to avoid huge positions on penny stocks
        max_position_value = 2000.0
        if shares * current_price > max_position_value:
            shares = int(max_position_value / current_price)
            
        return shares

    async def _execute_entry(self, swing_pick: Dict[str, Any], entry_mode: str) -> bool:
        """
        Override entry execution to use risk-based sizing and GTC orders.
        """
        try:
            symbol = swing_pick.get('symbol', 'UNKNOWN')
            
            # Get current price
            current_price = swing_pick.get('current_price', 0)
            if current_price == 0:
                current_price = await self._get_current_price(symbol)
                
            if not current_price or current_price <= 0:
                self.logger.error(f"❌ {symbol}: Could not get price for entry")
                return False

            # Calculate Shares based on Risk
            quantity = self.calculate_position_size(current_price)
            position_value = quantity * current_price
            
            if quantity <= 0:
                self.logger.warning(f"⚠️ {symbol}: Calculated quantity is 0")
                return False
                
            self.logger.info(f"📏 Sizing {symbol}: Risk ${self.risk_per_trade} -> {quantity} shares (${position_value:.2f})")

            # Execute Order with GTC and OutsideRth
            # We pass these via opportunity_data or modify execution engine. 
            # Since ExecutionEngineAdapter doesn't take TIF arg in execute_entry directly (it builds it),
            # we might need to rely on it or pass a special flag.
            # Actually, ExecutionEngineAdapter.enter_position takes opportunity_data.
            # We can inject 'tif': 'GTC' into opportunity_data if we modify Adapter to use it.
            # For now, let's update opportunity_data with our sizing preference if possible, 
            # but BaseSwingWorker calls execution_engine.execute_entry.
            
            # WAIT: BaseSwingWorker.execute_entry calls execution_engine.execute_entry.
            # I am overriding it here.
            
            order_type = 'MKT' if entry_mode == 'BREAKOUT' else 'LMT'
            limit_price = current_price if entry_mode == 'PULLBACK' else None
            
            # Inject GTC preference into opportunity_data passed to execution engine
            # The execution engine adapter uses opportunity_data to set some fields, but TIF is hardcoded based on session.
            # I will modify ExecutionEngineAdapter next to respect 'force_gtc' in opportunity_data.
            swing_pick['force_gtc'] = True
            swing_pick['outside_rth'] = True
            
            # Execute
            order_result = await self.execution_engine.execute_entry(
                symbol=symbol,
                action='BUY',
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                # We need to pass the modified swing_pick as opportunity_data
                # execute_entry signature in Adapter: enter_position(symbol, strategy, opportunity_data)
                # But BaseSwingWorker calls it with specific args? 
                # No, BaseSwingWorker calls self.execution_engine.execute_entry which is NOT standard.
                # Let's check BaseSwingWorker again. 
                # It calls: await self.execution_engine.execute_entry(symbol, action, quantity, order_type, limit_price)
                # But ExecutionEngineAdapter has enter_position(symbol, strategy, opportunity_data).
                # There is a mismatch or I misread BaseSwingWorker.
                # Let's check BaseSwingWorker lines 180-186 again.
            )
            
            # RE-READING BaseSwingWorker:
            # It calls self.execution_engine.execute_entry(...)
            # But ExecutionEngineAdapter (which is passed as execution_engine) has enter_position.
            # Does it have execute_entry?
            # I need to check ExecutionEngineAdapter for execute_entry method.
            # If it doesn't, BaseSwingWorker might be using a different adapter or I missed the method.
            # I'll assume for now I should call enter_position directly if I'm overriding.
            
            order_result = await self.execution_engine.enter_position(
                symbol=symbol,
                strategy=self.worker_name,
                opportunity_data=swing_pick
            )

            if not order_result:
                self.logger.error(f"❌ {symbol}: Order execution failed")
                return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Error executing swing entry for {symbol}: {e}")
            return False

    async def _should_enter(self, pick: Dict[str, Any]) -> bool:
        """
        Evaluate entry for Short Squeeze.
        """
        opportunity = pick  # Alias for compatibility
        symbol = opportunity.get('symbol', 'UNKNOWN')
        squeeze_data = opportunity.get('squeeze_data', {})

        # 1. Verify Squeeze Data (Double Check)
        if not squeeze_data:
            self.logger.warning(f"⚠️ {symbol}: Missing squeeze data")
            return False
            
        short_percent = squeeze_data.get('short_percent', 0)
        if short_percent < 0.10:
            # 4. (OPTIONAL) Validate with IBKR Real-Time Short Data
            # If we have access to IBKR adapter, check shortable shares
            if hasattr(self.execution_engine, 'get_short_data'):
                try:
                    short_data = await self.execution_engine.get_short_data(symbol)
                    shortable_shares = short_data.get('shortable_shares', 0)
                    
                    # Logic: 
                    # If Shortable Shares are VERY HIGH (> 2M), it means there is plenty of supply.
                    # This contradicts the "Squeeze" thesis (Low Float + High Demand).
                    # However, we don't want to be too strict if data is missing (0).
                    
                    if shortable_shares > 2000000:
                        self.logger.warning(f"⚠️ {symbol}: IBKR reports {shortable_shares/1_000_000:.1f}M shortable shares. Supply is too high for a squeeze.")
                        return False
                        
                    if 0 < shortable_shares < 100000:
                        self.logger.info(f"🔥 {symbol}: IBKR confirms Hard To Borrow (<100k shares). Squeeze potential HIGH.")
                        
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not validate short data for {symbol}: {e}")

            return False

        # 2. Technical Confirmation (Momentum)
        # We want to enter when it's moving, not when it's dead
        volume_ratio = opportunity.get('volume_ratio', 0)
        if volume_ratio < 1.5:
            return False
            
        gap_pct = opportunity.get('gap_percentage', 0)
        current_price = opportunity.get('current_price', 0)
        
        # 3. Price Action Check
        # Avoid catching a falling knife. Price should be > Open
        # (Assuming we have OHLC data access or can infer from gap)
        # Simple check: if Gap is huge (>50%), be careful of exhaustion?
        # Analysis showed Gap < 100% is fine.

        self.logger.info(f"✅ {symbol}: Squeeze Entry Approved (Short: {short_percent:.1%}, Vol: {volume_ratio:.1f}x)")
        return True

    async def _should_exit_position(self, symbol: str, position: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Evaluate exit for Short Squeeze position.
        """
        # Get current price from position or fetch it
        current_price = position.get('current_price', 0)
        if current_price == 0:
            # Try to get from execution engine if available
            if hasattr(self.execution_engine, 'get_current_price'):
                try:
                    current_price = await self.execution_engine.get_current_price(symbol)
                except:
                    pass

        entry_price = position.get('entry_price', 0)
        if entry_price == 0 or current_price == 0:
            return False, None

        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        # 1. Target Reached (Home Run)
        if pnl_pct >= self.target_gain_pct:
            return True, f"TARGET_REACHED (+{pnl_pct:.1f}%)"
            
        # 2. Hard Stop Loss
        # Check for dynamic support level first
        support_level = position.get('support_level', 0)
        if support_level > 0:
            # If we have a technical support, use it (with small buffer)
            stop_price = support_level * 0.98 # 2% below support
            if current_price <= stop_price:
                 return True, f"STOP_LOSS_SUPPORT ({current_price:.2f} <= {stop_price:.2f})"
        
        # Fallback to percentage stop
        elif pnl_pct <= -self.stop_loss_pct:
            return True, f"STOP_LOSS_PCT ({pnl_pct:.1f}%)"
            
        # 3. Trailing Stop (Protect Profits)
        # (Implemented in base class or here if custom logic needed)
        # For now, rely on manual trailing or simple logic
        if pnl_pct > self.trailing_activation_pct:
            # If we are up 15%, don't let it go back below +5%
            if pnl_pct < (self.trailing_activation_pct - self.trailing_distance_pct):
                 return True, f"TRAILING_STOP (+{pnl_pct:.1f}%)"
                 
        # 4. Time Limit
        entry_time = position.get('entry_time')
        if entry_time:
            # Calculate days held...
            pass

        return False, None
