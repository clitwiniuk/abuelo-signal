#!/usr/bin/env python3
"""
Detailed debug of healthy high profits logic
"""

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interfaces import MarketData, Position

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DetailedDebug")

def analyze_healthy_high_logic():
    """Manually step through the logic to see what's happening"""
    
    # Test parameters
    symbol = "TEST"
    entry_price = 10.00
    current_price = 11.20
    profit_pct = 0.12  # 12%
    # Create time directly in ET timezone
    test_time = datetime(2025, 9, 4, 15, 35, tzinfo=ZoneInfo("America/New_York"))  # 3:35 PM ET
    
    logger.info(f"🔍 Analyzing: {symbol} with {profit_pct:.1%} profit at {test_time}")
    
    # Step 1: Time analysis
    try:
        et_time = test_time.astimezone(ZoneInfo("America/New_York"))
        hour = et_time.hour
        minute = et_time.minute
        logger.info(f"   Time conversion: UTC {test_time} -> ET {et_time} (Hour: {hour}, Minute: {minute})")
    except Exception as e:
        logger.error(f"   ❌ Time conversion failed: {e}")
        return
    
    # Step 2: Threshold determination
    if hour >= 15 and minute >= 30:  # Last 30 minutes
        min_profit_threshold = 0.06  # 6% minimum to consider exit
        healthy_profit_threshold = 0.10  # 10% = healthy high
        great_profit_threshold = 0.15   # 15% = great profit
        time_mode = "End-of-day"
    elif hour >= 14:  # 2 PM onwards  
        min_profit_threshold = 0.08  # 8% minimum
        healthy_profit_threshold = 0.12  # 12% = healthy high
        great_profit_threshold = 0.18   # 18% = great profit
        time_mode = "Afternoon"
    else:  # Before 2 PM - be more patient
        min_profit_threshold = 0.10  # 10% minimum
        healthy_profit_threshold = 0.15  # 15% = healthy high
        great_profit_threshold = 0.22   # 22% = great profit
        time_mode = "Morning"
        
    logger.info(f"   📊 {time_mode} thresholds: Min={min_profit_threshold:.1%}, Healthy={healthy_profit_threshold:.1%}, Great={great_profit_threshold:.1%}")
    
    # Step 3: Profit check
    meets_min = profit_pct >= min_profit_threshold
    meets_healthy = profit_pct >= healthy_profit_threshold
    meets_great = profit_pct >= great_profit_threshold
    
    logger.info(f"   💰 Profit checks: Min={meets_min}, Healthy={meets_healthy}, Great={meets_great}")
    
    if not meets_min:
        logger.info(f"   ❌ Profit {profit_pct:.1%} < minimum {min_profit_threshold:.1%} - WOULD NOT EXIT")
        return
    
    # Step 4: Price vs highs analysis (simulate)
    # Let's say recent high is $11.37 (from our debug)
    recent_high = 11.37
    price_from_high = (recent_high - current_price) / recent_high
    near_high = price_from_high <= 0.02  # Within 2%
    
    logger.info(f"   📈 Recent high: ${recent_high:.2f}, Current: ${current_price:.2f}")
    logger.info(f"   📈 Price from high: {price_from_high:.1%}, Near high: {near_high}")
    
    if not near_high:
        logger.info(f"   ❌ Not near highs ({price_from_high:.1%} > 2%) - WOULD NOT EXIT")
        return
    
    # Step 5: Volume analysis (simulate)
    volume_ratio = 2.0  # From test
    healthy_volume = 1.5 <= volume_ratio <= 4.0
    
    logger.info(f"   📊 Volume ratio: {volume_ratio:.1f}x, Healthy volume: {healthy_volume}")
    
    # Step 6: Decision matrix
    logger.info(f"\n🎯 DECISION MATRIX:")
    
    # GREAT PROFIT + Near highs = Always exit
    if meets_great and near_high:
        logger.info(f"   ✅ GREAT PROFIT EXIT: {profit_pct:.1%} profit + near highs")
        return "EXIT - Great profit"
        
    # HEALTHY PROFIT + Near highs + End of day = Exit
    elif meets_healthy and near_high and hour >= 15:
        logger.info(f"   ✅ HEALTHY EOD EXIT: {profit_pct:.1%} profit + near highs + EOD")
        return "EXIT - Healthy EOD"
        
    # HEALTHY PROFIT + Near highs + Healthy volume + Momentum slowing = Exit  
    elif meets_healthy and near_high and healthy_volume:  # Removed momentum for now
        logger.info(f"   ✅ HEALTHY HIGH EXIT: {profit_pct:.1%} + near highs + healthy volume")
        return "EXIT - Healthy high"
        
    # MINIMUM PROFIT + Near highs + Very end of day = Exit
    elif meets_min and near_high and hour == 15 and minute >= 45:
        logger.info(f"   ✅ LATE DAY EXIT: {profit_pct:.1%} + near highs + market close")
        return "EXIT - Late day"
    
    logger.info(f"   ❌ NO EXIT CONDITIONS MET")
    logger.info(f"      - Great profit: {meets_great}")
    logger.info(f"      - Healthy + EOD: {meets_healthy and near_high and hour >= 15}")
    logger.info(f"      - Healthy + Volume: {meets_healthy and near_high and healthy_volume}")
    logger.info(f"      - Min + Late: {meets_min and near_high and hour == 15 and minute >= 45}")
    
    return "HOLD"

if __name__ == "__main__":
    result = analyze_healthy_high_logic()
    print(f"\n🎯 Final result: {result}")