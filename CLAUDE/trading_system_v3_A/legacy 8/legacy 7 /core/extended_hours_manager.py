# core/extended_hours_manager.py
"""
Extended Hours Trading Manager
Handles premarket and aftermarket trading logic with intelligent limit orders
"""

import logging
from typing import Optional, Tuple
from datetime import datetime, time
from zoneinfo import ZoneInfo
from enum import Enum

from core.interfaces import OrderType, OrderSide, MarketData


class MarketSession(Enum):
    PREMARKET = "PREMARKET"
    REGULAR = "REGULAR" 
    AFTERHOURS = "AFTERHOURS"
    CLOSED = "CLOSED"


class ExtendedHoursManager:
    """
    Manager for extended hours trading logic
    - Detects market session
    - Calculates intelligent limit prices
    - Handles bid/ask spread analysis
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ExtendedHoursManager")
        
        # Extended hours settings
        self.premarket_start = time(4, 0)   # 4:00 AM ET
        self.premarket_end = time(9, 30)    # 9:30 AM ET
        self.regular_start = time(9, 30)    # 9:30 AM ET
        self.regular_end = time(16, 0)      # 4:00 PM ET
        self.afterhours_start = time(16, 0) # 4:00 PM ET
        self.afterhours_end = time(20, 0)   # 8:00 PM ET
        
        # Spread analysis settings
        self.max_spread_threshold = 0.10    # Max 10 cents spread
        self.spread_penetration_factor = 0.3  # 30% into spread
        self.min_price_improvement = 0.01   # Min 1 cent improvement
        
        self.logger.info("🕐 ExtendedHoursManager initialized")
    
    def get_market_session(self) -> MarketSession:
        """Get current market session"""
        try:
            # Get US Eastern time
            us_now = datetime.now(ZoneInfo("America/New_York"))
            current_time = us_now.time()
            
            if self.premarket_start <= current_time < self.premarket_end:
                return MarketSession.PREMARKET
            elif self.regular_start <= current_time < self.regular_end:
                return MarketSession.REGULAR
            elif self.afterhours_start <= current_time < self.afterhours_end:
                return MarketSession.AFTERHOURS
            else:
                return MarketSession.CLOSED
                
        except Exception as e:
            self.logger.error(f"Error detecting market session: {e}")
            return MarketSession.CLOSED
    
    def requires_limit_order(self, session: MarketSession) -> bool:
        """Check if session requires limit orders"""
        return session in [MarketSession.PREMARKET, MarketSession.AFTERHOURS]
    
    def get_order_type(self, session: MarketSession) -> OrderType:
        """Get appropriate order type for session"""
        if self.requires_limit_order(session):
            return OrderType.LIMIT
        return OrderType.MARKET
    
    def calculate_limit_price(self, market_data: MarketData, side: OrderSide, 
                            session: MarketSession) -> Tuple[float, str]:
        """
        Calculate intelligent limit price for extended hours
        
        Returns:
            Tuple[float, str]: (limit_price, reasoning)
        """
        try:
            # If no bid/ask data, fall back to last price with buffer
            if not market_data.bid or not market_data.ask:
                return self._fallback_limit_price(market_data, side, session)
            
            bid = market_data.bid
            ask = market_data.ask
            spread = ask - bid
            mid_price = (bid + ask) / 2
            
            # Check spread sanity
            if spread > self.max_spread_threshold:
                self.logger.warning(f"Wide spread detected for {market_data.symbol}: ${spread:.4f}")
                return self._wide_spread_strategy(market_data, side, session)
            
            # Calculate penetration into spread
            if side == OrderSide.BUY:
                # Buy: Bid + penetration toward ask
                penetration = spread * self.spread_penetration_factor
                limit_price = bid + penetration
                
                # Ensure minimum improvement over bid
                limit_price = max(limit_price, bid + self.min_price_improvement)
                
                reasoning = f"BUY limit: bid({bid:.4f}) + {self.spread_penetration_factor*100:.0f}% spread"
                
            else:  # SELL
                # Sell: Ask - penetration toward bid  
                penetration = spread * self.spread_penetration_factor
                limit_price = ask - penetration
                
                # Ensure minimum improvement under ask
                limit_price = min(limit_price, ask - self.min_price_improvement)
                
                reasoning = f"SELL limit: ask({ask:.4f}) - {self.spread_penetration_factor*100:.0f}% spread"
            
            # Round to appropriate tick size
            limit_price = self._round_to_tick_size(limit_price, market_data.last_price)
            
            self.logger.debug(f"💰 {market_data.symbol} {session.value}: {reasoning} = ${limit_price:.4f}")
            
            return limit_price, reasoning
            
        except Exception as e:
            self.logger.error(f"Error calculating limit price for {market_data.symbol}: {e}")
            return self._fallback_limit_price(market_data, side, session)
    
    def _fallback_limit_price(self, market_data: MarketData, side: OrderSide, 
                            session: MarketSession) -> Tuple[float, str]:
        """Fallback pricing when no bid/ask available"""
        last_price = market_data.last_price or market_data.close
        
        # Use wider buffer for extended hours
        buffer_pct = 0.02 if session in [MarketSession.PREMARKET, MarketSession.AFTERHOURS] else 0.01
        
        if side == OrderSide.BUY:
            limit_price = last_price * (1 + buffer_pct)
            reasoning = f"Fallback BUY: last({last_price:.4f}) + {buffer_pct*100:.0f}%"
        else:
            limit_price = last_price * (1 - buffer_pct)
            reasoning = f"Fallback SELL: last({last_price:.4f}) - {buffer_pct*100:.0f}%"
        
        limit_price = self._round_to_tick_size(limit_price, last_price)
        
        self.logger.warning(f"🔄 {market_data.symbol}: Using fallback pricing - {reasoning}")
        
        return limit_price, reasoning
    
    def _wide_spread_strategy(self, market_data: MarketData, side: OrderSide,
                            session: MarketSession) -> Tuple[float, str]:
        """Strategy for wide spreads - be more conservative"""
        bid = market_data.bid
        ask = market_data.ask
        spread = ask - bid
        
        # Use smaller penetration for wide spreads
        conservative_factor = 0.15  # Only 15% into spread
        
        if side == OrderSide.BUY:
            limit_price = bid + (spread * conservative_factor)
            reasoning = f"Wide spread BUY: bid + {conservative_factor*100:.0f}% (spread: ${spread:.4f})"
        else:
            limit_price = ask - (spread * conservative_factor)
            reasoning = f"Wide spread SELL: ask - {conservative_factor*100:.0f}% (spread: ${spread:.4f})"
        
        limit_price = self._round_to_tick_size(limit_price, market_data.last_price)
        
        self.logger.info(f"📊 {market_data.symbol}: {reasoning}")
        
        return limit_price, reasoning
    
    def _round_to_tick_size(self, price: float, reference_price: float) -> float:
        """Round price to appropriate tick size"""
        try:
            if reference_price >= 1.0:
                # Stocks $1+ trade in penny increments
                return round(price, 2)
            else:
                # Sub-dollar stocks trade in 0.0001 increments
                return round(price, 4)
        except:
            return round(price, 4)
    
    def validate_extended_hours_order(self, market_data: MarketData, 
                                    order_type: OrderType, limit_price: Optional[float],
                                    session: MarketSession) -> Tuple[bool, str]:
        """Validate order for extended hours trading"""
        
        # Check if extended hours session
        if not self.requires_limit_order(session):
            return True, "Regular hours - all order types allowed"
        
        # Must be limit order in extended hours
        if order_type != OrderType.LIMIT:
            return False, f"Extended hours ({session.value}) requires LIMIT orders only"
        
        # Must have limit price
        if not limit_price:
            return False, "LIMIT order requires limit_price"
        
        # Validate reasonable price
        reference_price = market_data.last_price or market_data.close
        price_deviation = abs(limit_price - reference_price) / reference_price
        
        if price_deviation > 0.20:  # 20% deviation
            return False, f"Limit price {limit_price:.4f} too far from reference {reference_price:.4f}"
        
        return True, f"Extended hours order validated for {session.value}"
    
    def get_session_info(self) -> dict:
        """Get current session information"""
        session = self.get_market_session()
        us_now = datetime.now(ZoneInfo("America/New_York"))
        
        return {
            'current_session': session.value,
            'us_time': us_now.strftime("%H:%M:%S ET"),
            'requires_limit_orders': self.requires_limit_order(session),
            'session_times': {
                'premarket': f"{self.premarket_start.strftime('%H:%M')}-{self.premarket_end.strftime('%H:%M')} ET",
                'regular': f"{self.regular_start.strftime('%H:%M')}-{self.regular_end.strftime('%H:%M')} ET", 
                'afterhours': f"{self.afterhours_start.strftime('%H:%M')}-{self.afterhours_end.strftime('%H:%M')} ET"
            }
        }