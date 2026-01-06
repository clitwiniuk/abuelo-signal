# scanner/smallcap/smallcap_context.py
"""
SmallcapContext - Simplified context specifically for smallcap daily plays
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
import numpy as np

@dataclass
class SmallcapContext:
    """
    Contexto simplificado para smallcaps daily plays
    Enfocado solo en lo que realmente importa para estos trades
    """
    # Basic identifiers
    symbol: str
    timestamp: datetime
    
    # Price action (CRITICAL for smallcaps)
    current_price: float
    gap_percentage: float               # % gap from previous close
    premarket_high: float
    premarket_low: float
    
    # Volume (ESSENTIAL for breakouts)
    premarket_volume: int
    avg_daily_volume: int
    premarket_volume_ratio: float       # premarket_vol / avg_daily_vol
    
    # Catalyst information (DRIVER for smallcaps)
    news_catalyst_type: str             # FDA/EARNINGS/CONTRACT/M&A/OTHER
    news_age_hours: float               # Hours since news break
    catalyst_strength: int              # 1-10 scoring
    
    # Float & liquidity (SIZE matters for smallcaps)
    float_size: float                   # Shares outstanding
    market_cap: float                   # For sizing
    
    # Technical context (simplified)
    price_vs_premarket_high: float     # Current price relative to PM high
    volume_spike_confirmed: bool        # Volume >3x average
    
    # Regime (simplified - only what matters for smallcaps)
    market_fear_level: str              # LOW/MEDIUM/HIGH (VIX-based)
    
    # HTB Status (Hard to Borrow - indicates less short pressure)
    htb_status: bool = False            # True if hard to borrow
    htb_checked_time: Optional[datetime] = None  # When HTB was last checked
    
    def to_feature_vector(self) -> np.ndarray:
        """
        Convert to ML features - MUCH simpler than original TickerContext
        Now 11 features with HTB status included
        """
        features = [
            self.current_price,
            self.gap_percentage,
            self.premarket_volume_ratio,
            self.catalyst_strength,
            self.news_age_hours,
            float(self.float_size),
            self.price_vs_premarket_high,
            float(self.volume_spike_confirmed),
            self._encode_catalyst_type(),
            self._encode_fear_level(),
            float(self.htb_status)  # NEW: HTB as binary feature (1.0 = HTB, 0.0 = not HTB)
        ]
        return np.array(features, dtype=np.float32)
    
    def _encode_catalyst_type(self) -> float:
        """Encode catalyst type as numeric"""
        catalyst_map = {
            'FDA': 9.0,         # Highest impact for biotech
            'EARNINGS': 7.0,    # Strong but predictable
            'CONTRACT': 6.0,    # Moderate impact
            'M&A': 8.0,        # High impact
            'OTHER': 3.0       # Low impact
        }
        return catalyst_map.get(self.news_catalyst_type, 3.0)
    
    def _encode_fear_level(self) -> float:
        """Encode market fear as numeric"""
        fear_map = {
            'LOW': 1.0,     # Good for risk-on smallcap plays
            'MEDIUM': 0.5,  # Neutral
            'HIGH': 0.0     # Bad for smallcaps
        }
        return fear_map.get(self.market_fear_level, 0.5)
    
    def get_play_quality_score(self) -> float:
        """
        Quick quality assessment for this smallcap play
        Returns 0-10 score
        """
        score = 0.0
        
        # Gap quality (0-3 points)
        if self.gap_percentage > 0.25:     # 25%+
            score += 3.0
        elif self.gap_percentage > 0.15:   # 15%+  
            score += 2.0
        elif self.gap_percentage > 0.10:   # 10%+
            score += 1.0
            
        # Volume quality (0-3 points)
        if self.premarket_volume_ratio > 0.5:      # 50%+ of daily volume
            score += 3.0
        elif self.premarket_volume_ratio > 0.2:    # 20%+ of daily volume
            score += 2.0
        elif self.premarket_volume_ratio > 0.1:    # 10%+ of daily volume
            score += 1.0
            
        # Catalyst quality (0-3 points)
        score += self.catalyst_strength / 10.0 * 3.0
        
        # News freshness (0-1 point)
        if self.news_age_hours < 6:
            score += 1.0
        elif self.news_age_hours < 12:
            score += 0.5
            
        return min(score, 10.0)
    
    def is_tradeable(self) -> bool:
        """
        Quick filter for tradeable plays
        EMERGENCY: Ultra-relaxed filters to allow trading
        """
        # EMERGENCY: Minimal requirements to allow opportunities through
        if self.catalyst_strength < 2:         # At least strength 2 catalyst
            return False
            
        # Skip extreme conditions only
        if self.current_price < 0.50:          # Skip penny stocks under $0.50
            return False
            
        if self.current_price > 50.0:          # Skip very expensive stocks
            return False
            
        return True
    
    @classmethod
    def from_scanner_data(cls, scanner_data: Dict[str, Any]) -> 'SmallcapContext':
        """
        Create SmallcapContext from scanner data
        """
        # Extract from ProRealTime format
        symbol = scanner_data.get('symbol', '')
        gap_pct = float(scanner_data.get('gap_percent', 0)) / 100.0
        volume = int(scanner_data.get('volume', 0))
        price = float(scanner_data.get('price', 0))
        
        # This would be enhanced with real API calls for news/float data
        return cls(
            symbol=symbol,
            timestamp=datetime.now(),
            current_price=price,
            gap_percentage=gap_pct,
            premarket_high=price,  # Simplified - would get real PM high
            premarket_low=price * 0.95,  # Simplified
            premarket_volume=volume,
            avg_daily_volume=volume * 2,  # Simplified - would get real avg
            premarket_volume_ratio=0.5,  # Simplified
            news_catalyst_type='OTHER',  # Would be filled by news analyzer
            news_age_hours=2.0,  # Would be filled by news analyzer
            catalyst_strength=5,  # Would be filled by news analyzer
            float_size=50_000_000,  # Would be filled by API call
            market_cap=price * 50_000_000,
            price_vs_premarket_high=1.0,
            volume_spike_confirmed=True,
            market_fear_level='LOW'  # Would be filled by market analyzer
        )