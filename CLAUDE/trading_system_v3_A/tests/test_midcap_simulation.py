import sys
import os
import asyncio
import logging
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from enum import Enum

# Setup path to include the project root
sys.path.append('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3')

# Define mock Enum BEFORE imports
class ODSDayType(Enum):
    TREND_DRIVE_BULLISH = "TREND_DRIVE_BULLISH"
    TREND_DRIVE_BEARISH = "TREND_DRIVE_BEARISH"
    FAILED_DRIVE = "FAILED_DRIVE"
    BALANCE_DAY = "BALANCE_DAY"
    PENDING = "PENDING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    STRONG_BULLISH_OPEN = "STRONG_BULLISH_OPEN"

# Setup mocks for missing dependencies
sys.modules['pandas_ta'] = MagicMock()
sys.modules['strategies.workers.holy_grail_worker_logic'] = MagicMock()
sys.modules['strategies.workers.vcp_worker_logic'] = MagicMock()
sys.modules['strategies.workers.bull_flag_worker_logic'] = MagicMock()

# Mock the core.ods_classifier module
ods_classifier_mock = MagicMock()
ods_classifier_mock.ODSDayType = ODSDayType
sys.modules['core.ods_classifier'] = ods_classifier_mock

from strategies.workers.daily_plays_midcap_worker_logic import DailyPlaysMidCapWorkerLogic
from core.trade_arbiter import TradingHorizon

class TestMidCapSimulation(unittest.TestCase):
    def setUp(self):
        # Setup mocks
        self.execution_engine = MagicMock()
        self.risk_manager = MagicMock()
        self.config = MagicMock()
        
        # Mock config.getfloat and getint
        def mock_getfloat(section, key, fallback=None):
            if key == 'min_price': return 10.0
            if key == 'max_price': return 250.0 
            if key == 'min_quality_score': return 65.0
            if key == 'min_volume_ratio': return 2.0
            if key == 'reversal_quality_score_relaxed': return 45.0
            if key == 'daily_rsi_overbought': return 70.0
            if key == 'daily_resistance_min_distance_pct': return 2.0
            if key == 'daily_max_consecutive_up_days': return 5
            return fallback
            
        def mock_getboolean(section, key, fallback=None):
            if key == 'enable_ods_filters': return True
            if key == 'enable_reversal_mode': return True
            if key == 'enable_first_30min_breakout': return False
            if key == 'ods_filter_failed_drive': return True
            if key == 'ods_filter_balance_day': return True
            return fallback

        self.config.getfloat.side_effect = mock_getfloat
        self.config.getboolean.side_effect = mock_getboolean
        self.config.getint.return_value = 8 # ema_period
        
        # Initialize worker
        self.worker = DailyPlaysMidCapWorkerLogic(
            self.execution_engine,
            self.risk_manager,
            self.config
        )
        
        # Mock external services in BaseWorkerLogic
        self.worker.ods_classifier = MagicMock()
        self.worker.event_logger = MagicMock()
        self.worker.swing_analyzer = MagicMock()

    def create_mock_bar(self, open_p, high, low, close_p, vol):
        bar = MagicMock()
        bar.open = open_p
        bar.high = high
        bar.low = low
        bar.close = close_p
        bar.volume = vol
        return bar

    async def run_scenario(self, name, opportunity, bars_daily=None, bars_1min=None):
        print(f"\n--- TESTING SCENARIO: {name} ---")
        
        # Set bars
        if bars_daily:
            opportunity['bars_daily'] = bars_daily
            
        if bars_1min:
            opportunity['bars'] = bars_1min
        else:
            # For VWAP to work, current_price must be near bars prices
            # Default bars around current_price
            price = opportunity.get('current_price', 100.0)
            opportunity['bars'] = [self.create_mock_bar(price, price+0.1, price-0.1, price, 1000) for _ in range(20)]
            
        # Mock risk manager approval
        self.risk_manager.check_entry_approval.return_value = (True, "OK")
        
        # Setup Daily Context result
        daily_ctx = opportunity.get('daily_potential', {
            'is_safe': True,
            'reason': 'Safe trend',
            'daily_rsi': 50,
            'distance_to_resistance': 15.0
        })
        
        # Create patches
        patches = [
            patch.object(self.worker, '_analyze_daily_potential_for_signal', new_callable=AsyncMock, return_value=daily_ctx),
            patch.object(self.worker, '_check_daily_context', new_callable=AsyncMock, return_value=daily_ctx),
            patch.object(self.worker, 'is_within_entry_hours', return_value=(True, 10.5))
        ]
        
        # Apply patches
        for p in patches: p.start()
        
        try:
            # Patch ODS calculation (Async)
            ods_mock = MagicMock()
            ods_mock.strength = 8
            ods_mock.day_type = ODSDayType.STRONG_BULLISH_OPEN
            ods_mock.range_pct = 2.0
            ods_mock.volume_ratio = 3.0
            ods_mock.distance_from_open_pct = 1.0
            
            with patch.object(self.worker, 'get_ods_for_symbol', new_callable=AsyncMock) as mock_get_ods:
                mock_get_ods.return_value = ods_mock
                
                # Run the entry evaluation
                result = await self.worker.should_enter(opportunity)
                
                # Print results
                print(f"RESULT for {opportunity['symbol']}: {'✅ APPROVED' if result else '❌ REJECTED'}")
                return result
        finally:
            for p in patches: p.stop()

    def test_overbought_rejection(self):
        """Scenario 1: High RSI and many up days - should reject"""
        loop = asyncio.get_event_loop()
        
        opp = {
            'symbol': 'TSLA',
            'current_price': 180.0,
            'quality_score': 70.0,
            'catalyst_strength': 8,
            'catalyst_type': 'EARNINGS',
            'volume_ratio': 2.5,
            'daily_potential': {
                'is_safe': False,
                'rsi_daily': 75.0, # Overbought
                'consecutive_days_up': 6,
                'distance_to_resistance': 10.0,
                'reason': 'RSI daily overbought (75.0 > 70)'
            }
        }
        
        result = loop.run_until_complete(self.run_scenario("OVERBOUGHT_REJECTION", opp))
        self.assertFalse(result)

    def test_resistance_collision(self):
        """Scenario 2: Price too close to major resistance - should reject"""
        loop = asyncio.get_event_loop()
        
        opp = {
            'symbol': 'NVDA',
            'current_price': 148.5,
            'quality_score': 75.0,
            'catalyst_strength': 9,
            'catalyst_type': 'NEWS',
            'volume_ratio': 3.0,
            'daily_potential': {
                'is_safe': False,
                'rsi_daily': 55.0,
                'distance_to_resistance': 1.0, # Too close (1%)
                'resistance_level': 150.0,
                'reason': 'Too close to resistance (1.0% < 2.0%)'
            }
        }
        
        result = loop.run_until_complete(self.run_scenario("RESISTANCE_COLLISION", opp))
        self.assertFalse(result)

    def test_blue_sky_breakout(self):
        """Scenario 3: Blue sky setup (near 52w high) - should approve even if RSI is highish"""
        loop = asyncio.get_event_loop()
        
        opp = {
            'symbol': 'AAPL',
            'current_price': 235.0,
            'quality_score': 80.0,
            'catalyst_strength': 9,
            'catalyst_type': 'BREAKTHROUGH',
            'volume_ratio': 4.0,
            'daily_potential': {
                'can_swing': True,
                'is_safe': True,
                'is_blue_sky': True, 
                'is_52_week_high': True,
                'rsi_daily': 68.0, 
                'distance_to_resistance': 999.0, # No ceiling
                'reasons': ['🌤️ BLUE SKY POTENTIAL']
            }
        }
        
        result = loop.run_until_complete(self.run_scenario("BLUE_SKY_BREAKOUT", opp))
        self.assertTrue(result)
        self.assertEqual(opp.get('trading_horizon'), 'SWING')

    def test_reversal_setup(self):
        """Scenario 4: Reversal mode - oversold and near support - should approve"""
        loop = asyncio.get_event_loop()
        
        opp = {
            'symbol': 'DIS',
            'current_price': 92.0,
            'quality_score': 50.0, # Quality score relaxed for reversal
            'catalyst_strength': 0,
            'catalyst_type': 'TECHNICAL',
            'volume_ratio': 1.8,
            'daily_potential': {
                'is_safe': True,
                'reversal': {
                    'is_reversal': True,
                    'signal_count': 5,
                    'reversal_score': 5
                },
                'rsi_daily': 28.0, # Oversold
                'distance_to_support_pct': 1.5,
                'reasons': ['Oversold Reversal Signal']
            }
        }
        
        result = loop.run_until_complete(self.run_scenario("REVERSAL_SETUP", opp))
        self.assertTrue(result)

    def test_optimal_swing_play(self):
        """Scenario 5: Perfect setup - clean trend, catalyst, space to move"""
        loop = asyncio.get_event_loop()
        
        opp = {
            'symbol': 'AMD',
            'current_price': 160.0,
            'quality_score': 72.0,
            'catalyst_strength': 8,
            'catalyst_type': 'EARNINGS',
            'volume_ratio': 3.5,
            'daily_potential': {
                'is_safe': True,
                'rsi_daily': 52.0,
                'distance_to_resistance': 12.0, # Plenty of room
                'reasons': ['Strong catalyst', 'Space to move']
            }
        }
        
        result = loop.run_until_complete(self.run_scenario("OPTIMAL_SWING_PLAY", opp))
        self.assertTrue(result)
        self.assertEqual(opp.get('trading_horizon'), 'SWING')

if __name__ == '__main__':
    unittest.main()
