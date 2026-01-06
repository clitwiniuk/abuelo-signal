#!/usr/bin/env python3
"""
Strategy-Specific Scanner Dispatcher
===================================

Routes specific scanner types to appropriate strategies without breaking
the existing SmallcapDailyScanner functionality for daily_plays.

Architecture:
- SmallcapDailyScanner continues to work as-is for daily_plays strategy
- New specialized scanners for ORB, VWAP_RECLAIM, VCP, etc.
- Dispatcher coordinates all scanners and routes results appropriately
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from scanner.ibkr_native_scanner import IBKRNativeScanner, IBKRScanResult
from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
from adapters.ibkr_adapter import IBKRAdapter

logger = logging.getLogger(__name__)

class ScannerType(Enum):
    """Scanner types for different strategies"""
    DAILY_PLAYS = "daily_plays"          # Existing SmallcapDailyScanner
    ORB = "orb"                         # Opening Range Breakout
    VWAP_RECLAIM = "vwap_reclaim"       # VWAP Reclaim patterns
    VCP = "vcp"                         # Volatility Contraction Pattern
    MACD_MOMENTUM = "macd_momentum"     # MACD momentum plays (subset of daily_plays)

@dataclass
class StrategyOpportunity:
    """Represents an opportunity for a specific strategy"""
    strategy_type: str
    symbol: str
    scanner_type: str
    confidence_score: float
    metadata: Dict[str, Any]
    scan_timestamp: datetime
    ibkr_data: IBKRScanResult

class StrategySpecificScanner:
    """Base class for strategy-specific scanners"""
    
    def __init__(self, strategy_type: str, ibkr_adapter: Optional[IBKRAdapter] = None):
        self.strategy_type = strategy_type
        self.ibkr_adapter = ibkr_adapter
        self.logger = logging.getLogger(f"{__name__}.{strategy_type.upper()}Scanner")
    
    async def scan_opportunities(self) -> List[StrategyOpportunity]:
        """Override in subclasses"""
        raise NotImplementedError

class ORBScanner(StrategySpecificScanner):
    """Scanner for Opening Range Breakout opportunities"""
    
    def __init__(self, ibkr_adapter: Optional[IBKRAdapter] = None):
        super().__init__("orb", ibkr_adapter)
        self.ibkr_scanner = IBKRNativeScanner(ibkr_adapter)
    
    async def scan_opportunities(self) -> List[StrategyOpportunity]:
        """
        Find ORB opportunities:
        - Pre-market gaps (3-15%)
        - Consolidation near highs
        - Volume building for breakout
        """
        self.logger.info("🎯 Scanning for ORB opportunities...")
        
        try:
            # Get gap movers and pre-market data
            ibkr_results = await self.ibkr_scanner._run_single_scanner({
                'name': 'orb_candidates',
                'scan_code': 'TOP_PERC_GAIN',
                'instrument': 'STK',
                'location_code': 'STK.NASDAQ.NMS,STK.NYSE',
                'stock_type': 'ALL',
                'above_price': 2.0,      # Higher price floor for ORB
                'below_price': 50.0,     # Allow higher prices for ORB
                'above_volume': 100000,  # Lower volume requirement in pre-market
                'market_cap_below': 5000, # Allow larger caps for ORB
                'exclude_convertible': True
            })
            
            opportunities = []
            
            for result in ibkr_results:
                # ORB-specific filtering
                gap_pct = abs(result.gap_percentage)
                
                # ORB sweet spot: 3-15% gaps
                if 3.0 <= gap_pct <= 15.0:
                    # Calculate ORB confidence score
                    confidence = self._calculate_orb_confidence(result)
                    
                    if confidence >= 0.6:  # 60% confidence threshold
                        opportunity = StrategyOpportunity(
                            strategy_type="orb",
                            symbol=result.symbol,
                            scanner_type="orb_candidates",
                            confidence_score=confidence,
                            metadata={
                                'gap_percentage': gap_pct,
                                'gap_direction': 'up' if result.gap_percentage > 0 else 'down',
                                'volume_ratio': result.volume / result.avg_volume if result.avg_volume > 0 else 1.0,
                                'price_range': f'${result.current_price:.2f}',
                                'reason': f'{gap_pct:.1f}% gap with ORB potential'
                            },
                            scan_timestamp=datetime.now(),
                            ibkr_data=result
                        )
                        opportunities.append(opportunity)
            
            self.logger.info(f"🎯 Found {len(opportunities)} ORB opportunities")
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error scanning ORB opportunities: {e}")
            return []
    
    def _calculate_orb_confidence(self, result: IBKRScanResult) -> float:
        """Calculate ORB-specific confidence score"""
        score = 0.0
        
        # Gap size (optimal 5-10%)
        gap_pct = abs(result.gap_percentage)
        if 5.0 <= gap_pct <= 10.0:
            score += 0.4
        elif 3.0 <= gap_pct <= 15.0:
            score += 0.2
        
        # Volume consideration
        if result.avg_volume > 0:
            vol_ratio = result.volume / result.avg_volume
            if vol_ratio >= 1.5:
                score += 0.3
            elif vol_ratio >= 1.0:
                score += 0.1
        
        # Price range (ORB works better with higher prices)
        if result.current_price >= 5.0:
            score += 0.2
        elif result.current_price >= 2.0:
            score += 0.1
        
        # Market cap (mid-caps often better for ORB)
        if 100 <= result.market_cap <= 2000:  # $100M - $2B
            score += 0.1
        
        return min(score, 1.0)

class VWAPReclaimScanner(StrategySpecificScanner):
    """Scanner for VWAP Reclaim opportunities"""
    
    def __init__(self, ibkr_adapter: Optional[IBKRAdapter] = None):
        super().__init__("vwap_reclaim", ibkr_adapter)
        self.ibkr_scanner = IBKRNativeScanner(ibkr_adapter)
    
    async def scan_opportunities(self) -> List[StrategyOpportunity]:
        """
        Find VWAP Reclaim opportunities:
        - Stocks that dipped below VWAP
        - Now showing strength to reclaim
        - Volume confirmation
        """
        self.logger.info("📈 Scanning for VWAP Reclaim opportunities...")
        
        try:
            # Get most active stocks for VWAP analysis
            ibkr_results = await self.ibkr_scanner._run_single_scanner({
                'name': 'vwap_candidates',
                'scan_code': 'MOST_ACTIVE',
                'instrument': 'STK',
                'location_code': 'STK.NASDAQ.NMS,STK.NYSE',
                'stock_type': 'ALL',
                'above_price': 1.0,
                'below_price': 25.0,
                'above_volume': 500000,   # Need volume for VWAP calculation
                'market_cap_below': 3000,
                'exclude_convertible': True
            })
            
            opportunities = []
            current_time = datetime.now().time()
            
            # VWAP reclaim works best during market hours
            if time(9, 45) <= current_time <= time(15, 30):
                for result in ibkr_results:
                    confidence = self._calculate_vwap_confidence(result)
                    
                    if confidence >= 0.7:  # 70% confidence threshold
                        opportunity = StrategyOpportunity(
                            strategy_type="vwap_reclaim",
                            symbol=result.symbol,
                            scanner_type="vwap_candidates",
                            confidence_score=confidence,
                            metadata={
                                'volume_ratio': result.volume / result.avg_volume if result.avg_volume > 0 else 1.0,
                                'price': result.current_price,
                                'market_cap': result.market_cap,
                                'reason': 'VWAP reclaim setup with volume confirmation'
                            },
                            scan_timestamp=datetime.now(),
                            ibkr_data=result
                        )
                        opportunities.append(opportunity)
            
            self.logger.info(f"📈 Found {len(opportunities)} VWAP Reclaim opportunities")
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error scanning VWAP Reclaim opportunities: {e}")
            return []
    
    def _calculate_vwap_confidence(self, result: IBKRScanResult) -> float:
        """Calculate VWAP-specific confidence score"""
        score = 0.0
        
        # Volume is critical for VWAP
        if result.avg_volume > 0:
            vol_ratio = result.volume / result.avg_volume
            if vol_ratio >= 2.0:
                score += 0.4
            elif vol_ratio >= 1.5:
                score += 0.3
            elif vol_ratio >= 1.0:
                score += 0.1
        
        # Price range (VWAP works with various prices)
        if 3.0 <= result.current_price <= 20.0:
            score += 0.3
        elif 1.0 <= result.current_price <= 30.0:
            score += 0.2
        
        # Market cap preference
        if 50 <= result.market_cap <= 1000:  # $50M - $1B
            score += 0.2
        
        # Time bonus (VWAP reclaim better during market hours)
        current_time = datetime.now().time()
        if time(10, 0) <= current_time <= time(15, 0):
            score += 0.1
        
        return min(score, 1.0)

class StrategyScannerDispatcher:
    """
    Coordinates multiple strategy-specific scanners
    Routes opportunities to appropriate strategies
    """
    
    def __init__(self, ibkr_adapter: Optional[IBKRAdapter] = None):
        self.ibkr_adapter = ibkr_adapter
        self.logger = logging.getLogger(f"{__name__}.Dispatcher")
        
        # Initialize existing daily plays scanner
        self.daily_plays_scanner = SmallcapDailyScanner(ibkr_adapter)
        
        # Initialize strategy-specific scanners
        self.strategy_scanners = {
            ScannerType.ORB: ORBScanner(ibkr_adapter),
            ScannerType.VWAP_RECLAIM: VWAPReclaimScanner(ibkr_adapter),
            # Add more as needed
        }
        
        self.logger.info(f"Strategy Scanner Dispatcher initialized with {len(self.strategy_scanners)} specialized scanners")
    
    async def scan_all_strategies(self) -> Dict[str, List[Any]]:
        """
        Scan for opportunities across all strategies
        
        Returns:
            Dict mapping strategy names to their opportunities
        """
        self.logger.info("🚀 Starting multi-strategy scanning...")
        
        results = {}
        
        try:
            # Scan existing daily_plays (maintains backward compatibility)
            self.logger.info("📊 Scanning daily_plays...")
            daily_plays = await self.daily_plays_scanner.scan_daily_plays()
            results['daily_plays'] = daily_plays
            
            # Scan strategy-specific opportunities
            scanner_tasks = []
            for scanner_type, scanner in self.strategy_scanners.items():
                self.logger.info(f"🎯 Starting {scanner_type.value} scanner...")
                task = asyncio.create_task(scanner.scan_opportunities())
                scanner_tasks.append((scanner_type.value, task))
            
            # Wait for all strategy scanners to complete
            for strategy_name, task in scanner_tasks:
                try:
                    opportunities = await task
                    results[strategy_name] = opportunities
                    self.logger.info(f"✅ {strategy_name}: {len(opportunities)} opportunities found")
                except Exception as e:
                    self.logger.error(f"❌ {strategy_name} scanner failed: {e}")
                    results[strategy_name] = []
            
            # Summary
            total_opportunities = sum(len(opps) for opps in results.values())
            self.logger.info(f"🎯 Multi-strategy scan complete: {total_opportunities} total opportunities across {len(results)} strategies")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in multi-strategy scanning: {e}")
            return {'daily_plays': []}  # Fallback to daily plays only
    
    async def scan_specific_strategy(self, strategy_type: str) -> List[Any]:
        """Scan for a specific strategy only"""
        if strategy_type == 'daily_plays':
            return await self.daily_plays_scanner.scan_daily_plays()
        
        scanner_type = ScannerType(strategy_type)
        if scanner_type in self.strategy_scanners:
            return await self.strategy_scanners[scanner_type].scan_opportunities()
        else:
            self.logger.warning(f"Unknown strategy type: {strategy_type}")
            return []
    
    def get_available_strategies(self) -> List[str]:
        """Get list of available strategies"""
        strategies = ['daily_plays']
        strategies.extend([scanner_type.value for scanner_type in self.strategy_scanners.keys()])
        return strategies
    
    async def disconnect(self):
        """Cleanup all scanner connections"""
        try:
            await self.daily_plays_scanner.disconnect()
            for scanner in self.strategy_scanners.values():
                if hasattr(scanner, 'disconnect'):
                    await scanner.disconnect()
        except Exception as e:
            self.logger.error(f"Error disconnecting scanners: {e}")

# Example usage for testing
async def test_multi_strategy_scanning():
    """Test function to demonstrate multi-strategy scanning"""
    dispatcher = StrategyScannerDispatcher()
    
    try:
        # Scan all strategies
        all_results = await dispatcher.scan_all_strategies()
        
        print("\n🎯 MULTI-STRATEGY SCAN RESULTS:")
        print("=" * 50)
        
        for strategy, opportunities in all_results.items():
            print(f"\n{strategy.upper()}: {len(opportunities)} opportunities")
            
            if strategy == 'daily_plays':
                # SmallcapPlay objects
                for i, play in enumerate(opportunities[:3], 1):
                    print(f"  {i}. {play.symbol} - Quality: {play.quality_score:.1f}")
            else:
                # StrategyOpportunity objects
                for i, opp in enumerate(opportunities[:3], 1):
                    print(f"  {i}. {opp.symbol} - Confidence: {opp.confidence_score:.1%}")
        
        return all_results
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return {}
    
    finally:
        await dispatcher.disconnect()

if __name__ == "__main__":
    # Test the dispatcher
    asyncio.run(test_multi_strategy_scanning())