"""
Worker Update Handling - Mixin for intelligent opportunity re-evaluation
Add this to workers to enable smart update handling
"""

from typing import Dict, Any
import logging


class UpdateHandlerMixin:
    """
    Mixin to add intelligent update handling to workers.
    
    Usage:
        class MyWorker(BaseWorkerLogic, UpdateHandlerMixin):
            def should_reevaluate_update(self, opportunity):
                # Custom logic here
                pass
    """
    
    def should_reevaluate_update(self, opportunity: Dict[str, Any]) -> bool:
        """
        Determine if this worker should re-evaluate an updated opportunity.
        
        Override in subclasses for worker-specific logic.
        
        Args:
            opportunity: Opportunity dict with potential 'is_update' and 'update_reason' fields
            
        Returns:
            True if worker should re-evaluate, False to skip
        """
        # If not an update, always evaluate (first time)
        if not opportunity.get('is_update'):
            return True
        
        update_reason = opportunity.get('update_reason', '')
        
        # Default behavior: re-evaluate on significant changes
        significant_reasons = [
            'CATALYST_CHANGE',
            'VOLUME_SURGE',
            'BREAKOUT',
            'QUALITY_UPGRADE',
            'NEW_OPPORTUNITY_TYPE'
        ]
        
        if update_reason in significant_reasons:
            if hasattr(self, 'logger'):
                self.logger.info(f"🔄 {opportunity.get('symbol')}: Re-evaluating due to {update_reason}")
            return True
        
        # Skip periodic refreshes and minor updates by default
        if hasattr(self, 'logger'):
            self.logger.debug(f"⏭️ {opportunity.get('symbol')}: Skipping update ({update_reason})")
        return False


class CatalystSensitiveUpdateHandler(UpdateHandlerMixin):
    """
    Update handler for catalyst-sensitive workers (Daily Plays, Buy & Hold).
    Only re-evaluates when catalysts change.
    """
    
    def should_reevaluate_update(self, opportunity: Dict[str, Any]) -> bool:
        if not opportunity.get('is_update'):
            return True
        
        update_reason = opportunity.get('update_reason', '')
        
        # Catalyst-sensitive: only care about catalyst changes
        if update_reason == 'CATALYST_CHANGE':
            if hasattr(self, 'logger'):
                self.logger.info(f"📰 {opportunity.get('symbol')}: Re-evaluating due to new catalyst")
            return True
        
        # Also re-evaluate on new opportunity types (might be catalyst-driven)
        if update_reason == 'NEW_OPPORTUNITY_TYPE':
            if hasattr(self, 'logger'):
                self.logger.info(f"🆕 {opportunity.get('symbol')}: Re-evaluating new opportunity type")
            return True
        
        # Ignore volume/price changes
        if hasattr(self, 'logger'):
            self.logger.debug(f"⏭️ {opportunity.get('symbol')}: Ignoring {update_reason} (catalyst-only worker)")
        return False


class VolumeSensitiveUpdateHandler(UpdateHandlerMixin):
    """
    Update handler for volume-sensitive workers (Momentum, Parabolic).
    Re-evaluates on volume surges and breakouts.
    """
    
    def should_reevaluate_update(self, opportunity: Dict[str, Any]) -> bool:
        if not opportunity.get('is_update'):
            return True
        
        update_reason = opportunity.get('update_reason', '')
        
        # Volume-sensitive: care about volume and price action
        if update_reason in ['VOLUME_SURGE', 'BREAKOUT']:
            if hasattr(self, 'logger'):
                self.logger.info(f"💥 {opportunity.get('symbol')}: Re-evaluating due to {update_reason}")
            return True
        
        # Also re-evaluate on quality upgrades (might indicate strengthening momentum)
        if update_reason == 'QUALITY_UPGRADE':
            if hasattr(self, 'logger'):
                self.logger.info(f"⬆️ {opportunity.get('symbol')}: Re-evaluating quality upgrade")
            return True
        
        # Ignore catalyst changes (not our focus)
        if hasattr(self, 'logger'):
            self.logger.debug(f"⏭️ {opportunity.get('symbol')}: Ignoring {update_reason} (volume-focused worker)")
        return False


class TimeSensitiveUpdateHandler(UpdateHandlerMixin):
    """
    Update handler for time-sensitive workers (ORB).
    Only operates in specific time windows.
    """
    
    def __init__(self, cutoff_time_str: str = "10:00"):
        """
        Args:
            cutoff_time_str: Time after which to ignore all updates (HH:MM format)
        """
        from datetime import datetime
        self.cutoff_time = datetime.strptime(cutoff_time_str, "%H:%M").time()
    
    def should_reevaluate_update(self, opportunity: Dict[str, Any]) -> bool:
        from datetime import datetime
        
        if not opportunity.get('is_update'):
            return True
        
        # Check if we're still in the time window
        current_time = datetime.now().time()
        if current_time > self.cutoff_time:
            if hasattr(self, 'logger'):
                self.logger.debug(f"⏰ {opportunity.get('symbol')}: Outside time window, ignoring update")
            return False
        
        # Within time window, re-evaluate on any significant change
        update_reason = opportunity.get('update_reason', '')
        significant_reasons = ['VOLUME_SURGE', 'BREAKOUT', 'QUALITY_UPGRADE']
        
        if update_reason in significant_reasons:
            if hasattr(self, 'logger'):
                self.logger.info(f"⏰ {opportunity.get('symbol')}: Re-evaluating {update_reason} (within time window)")
            return True
        
        return False
