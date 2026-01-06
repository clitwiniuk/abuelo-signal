# scanner/config.py
"""
Configuration file for Daily Plays Filter Scanner
"""

import os
from typing import Optional

class ScannerConfig:
    """Configuration for the scanner"""
    
    # NewsAPI Configuration
    NEWSAPI_KEY: Optional[str] = os.getenv('NEWSAPI_API_KEY')  # Get from environment
    
    # Default filter criteria
    DEFAULT_MAX_FLOAT_SHARES = 100_000_000  # 100M shares
    DEFAULT_MIN_GAP_PERCENT = 10.0
    DEFAULT_MIN_PREMARKET_VOLUME = 500_000
    
    # News search configuration
    NEWS_DAYS_BACK = 7
    
    # SEC EDGAR configuration
    SEC_COMPANY_NAME = "Daily Plays Scanner"
    SEC_EMAIL = "scanner@example.com"
    
    @classmethod
    def get_newsapi_key(cls) -> Optional[str]:
        """Get NewsAPI key from environment or return None"""
        return cls.NEWSAPI_KEY
    
    @classmethod
    def has_newsapi_key(cls) -> bool:
        """Check if NewsAPI key is available"""
        return cls.NEWSAPI_KEY is not None and len(cls.NEWSAPI_KEY.strip()) > 0

# Instructions for getting API keys
SETUP_INSTRUCTIONS = """
🔑 API Keys Setup:

1. NewsAPI (Optional but recommended):
   - Go to: https://newsapi.org/register
   - Get free API key (30,000 requests/month)
   - Set environment variable: NEWSAPI_API_KEY=your_key_here
   - Or edit config.py directly

2. SEC EDGAR (Free):
   - No API key needed
   - Uses official SEC endpoints
   - Rate limited by SEC (10 requests/second)

3. Yahoo Finance (Free):
   - No API key needed
   - Built into yahooquery
   - Rate limited by Yahoo

Without NewsAPI key:
- Scanner will work with Yahoo + SEC only
- Reduced news coverage
- Still functional for most use cases
"""