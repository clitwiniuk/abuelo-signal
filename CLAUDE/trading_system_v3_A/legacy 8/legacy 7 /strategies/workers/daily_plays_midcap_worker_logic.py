"""
Daily Plays Mid-Cap Worker Logic
Worker específico para estrategias de Middle Caps ($2B - $50B)
Inherits logic from DailyPlaysWorkerLogic but uses specific MidCap configuration
"""

from typing import Dict, Any
from .daily_plays_worker_logic import DailyPlaysWorkerLogic

class DailyPlaysMidCapWorkerLogic(DailyPlaysWorkerLogic):
    """
    Daily Plays Worker for MID CAPS ($2B - $50B)
    Uses the same logic as Daily Plays (breakouts, reversals) but tuned for
    institutional-grade stocks (higher liquidity, steadier moves).
    """
    
    def __init__(self, broker, risk_manager=None, config=None, execution_engine=None):
        # Override config section BEFORE calling super().__init__
        self.config_section = 'DAILY_PLAYS_MIDCAP_STRATEGY'
        
        super().__init__(
            broker=broker,
            risk_manager=risk_manager,
            config=config
        )
        # Override worker name to be distinct
        self.worker_name = "daily_plays_midcap"
        self.logger.info(f"🎯 Daily Plays MID-CAP Worker initialized (Section: {self.config_section})")

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evaluate entry for MidCaps.
        Also forces SWING mode if conditions met.
        """
        # Call parent logic first
        should = await super().should_enter(opportunity)
        
        if should:
             # Force SWING mode for Mid Caps (allow overnight hold)
             # This flag is read by WorkerStopManager to skip EOD exit
             opportunity['EOD_safe'] = True
             opportunity['trading_horizon'] = 'SWING'
             
             self.logger.info(f"🦅 {opportunity.get('symbol')}: Forced SWING mode for Mid-Cap (EOD Safe)")
             
        return should
