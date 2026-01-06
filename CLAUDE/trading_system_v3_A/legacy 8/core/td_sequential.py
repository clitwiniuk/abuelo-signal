"""
TD Sequential (DeMark) Indicator Logic
Core module for identifying exhaustion setups.
"""

from typing import List, Dict, Optional, Tuple, Any

class TDSequentialDetector:
    """
    Calculates TD Sequential counts (Setup and Countdown).
    Focuses on the TD Setup (9-count) for early exhaustion detection.
    """
    
    def __init__(self, setup_max: int = 9):
        self.setup_max = setup_max

    def calculate_setup(self, bars: List) -> int:
        """
        Calculates the current TD Setup count.
        A bullish setup count increases if Close > Close[4].
        A bearish setup count increases if Close < Close[4].
        We focus on Bullish Setup for long exhaustion.
        
        Returns:
            int: Current count (positive for bullish, negative for bearish)
        """
        if not bars or len(bars) < self.setup_max + 4:
            return 0
            
        count = 0
        direction = 0 # 1 for bullish, -1 for bearish
        
        # We look back to find the start of the current sequence
        # The logic: TD Setup is a series of 9 consecutive bars where
        # close is higher/lower than close 4 bars ago.
        
        # Let's iterate backwards to find the current active sequence
        for i in range(len(bars) - 1, self.setup_max - 5, -1):
            curr_bar = bars[i]
            ref_bar = bars[i-4]
            
            if curr_bar.close > ref_bar.close:
                if direction == -1: # Sequence broke
                    break
                direction = 1
                count += 1
            elif curr_bar.close < ref_bar.close:
                if direction == 1: # Sequence broke
                    break
                direction = -1
                count -= 1
            else:
                break # Close equal is a break in TD
                
        return count

    def get_exhaustion_score(self, bars: List) -> Dict[str, Any]:
        """
        Provides a structured exhaustion report based on DeMark counts.
        """
        count = self.calculate_setup(bars)
        
        return {
            'setup_count': count,
            'is_exhausted': abs(count) >= self.setup_max,
            'is_near_exhaustion': abs(count) >= self.setup_max - 1,
            'direction': 'BULLISH' if count > 0 else 'BEARISH' if count < 0 else 'NEUTRAL'
        }
