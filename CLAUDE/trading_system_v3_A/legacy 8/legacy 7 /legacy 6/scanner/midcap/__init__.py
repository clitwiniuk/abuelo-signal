# scanner/midcap/__init__.py
"""
MidCap Scanner Module

Event-driven scanner for Mid-Cap stocks ($2B-$50B market cap, $10-$100 price)
Optimized for institutional-quality opportunities with catalyst detection.
"""

from .midcap_daily_scanner import (
    MidCapDailyScanner,
    MidCapPlay,
    MidCapOpportunityType
)

__all__ = [
    'MidCapDailyScanner',
    'MidCapPlay',
    'MidCapOpportunityType'
]
