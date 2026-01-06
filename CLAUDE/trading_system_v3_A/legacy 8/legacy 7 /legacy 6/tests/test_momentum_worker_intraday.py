import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

# Mock dependencies BEFORE importing worker
sys.modules['core.trade_arbiter'] = MagicMock()
sys.modules['core.absorption_detector'] = MagicMock()
sys.modules['core.service_locator'] = MagicMock()
sys.modules['core.intraday_structure_classifier'] = MagicMock()

# Mock specific classes/enums
mock_phase = MagicMock()
mock_phase.MIDDAY = "MIDDAY"
mock_phase.AFTERNOON = "AFTERNOON"
sys.modules['core.intraday_structure_classifier'].IntradayPhase = mock_phase

from strategies.workers.momentum_breakout_worker_logic import MomentumBreakoutWorkerLogic

async def test_intraday_mover_bypass():
    print("🧪 Testing MomentumBreakoutWorkerLogic for INTRADAY_MOVER...")

    # Mock Engine and Risk Manager
    mock_engine = MagicMock()
    mock_risk_manager = MagicMock()
    
    # Mock Config
    mock_config = MagicMock()
    mock_config.lookback_bars = 5
    mock_config.min_volume_ratio = 1.2
    mock_config.min_price = 1.0
    mock_config.max_price = 25.0
    
    # Instantiate Worker
    worker = MomentumBreakoutWorkerLogic(mock_engine, mock_risk_manager, mock_config)
    
    # Mock internal methods to isolate the test
    # Create mock bars
    mock_bar = MagicMock()
    mock_bar.close = 10.0
    mock_bar.high = 10.1
    mock_bar.low = 9.9
    mock_bar.timestamp = 1600000000
    
    worker.get_bars_from_opportunity = MagicMock(return_value=[mock_bar] * 50) 
    worker._get_current_price = AsyncMock(return_value=10.0)
    worker.validate_vwap_strength = MagicMock(return_value=(True, "VWAP OK"))
    worker._verify_price_structure = MagicMock(return_value=(True, "Structure OK"))
    worker._confirm_volume_surge = MagicMock(return_value=True)
    worker.is_within_entry_hours = MagicMock(return_value=(True, 10.0))
    worker._check_if_extended = MagicMock(return_value=(False, 5.0)) # Default not extended
    
    # Mock Unified Position Manager
    mock_upm = MagicMock()
    mock_upm.is_symbol_blocked.return_value = False
    mock_upm.get_position.return_value = None  # No existing position
    sys.modules['core.service_locator'].get_unified_position_manager = AsyncMock(return_value=mock_upm)

    # Mock Intraday Structure
    mock_structure = MagicMock()
    mock_structure.current_phase = "MORNING"
    mock_structure.liquidity_sweep_detected = False
    mock_structure.trap_detected = False
    worker.get_intraday_structure_for_symbol = AsyncMock(return_value=mock_structure)

    # Mock Absorption
    worker.use_absorption_filter = False 

    # TEST CASE 1: Standard Opportunity (Should FAIL if no consolidation)
    print("\n📋 Test Case 1: Standard Opportunity (No Consolidation)")
    worker._detect_consolidation_after_momentum = MagicMock(return_value=(False, "No consolidation", 0.0))
    
    opp_standard = {
        'symbol': 'STD',
        'current_price': 10.0,
        'volume_ratio': 2.0,
        'opportunity_type': 'VOLUME_SURGE'
    }
    
    result_standard = await worker.should_enter(opp_standard)
    print(f"Result: {result_standard}")
    if result_standard is False:
        print("✅ SUCCESS: Standard opportunity correctly rejected without consolidation.")
    else:
        print("❌ FAILURE: Standard opportunity accepted despite missing consolidation.")

    # TEST CASE 2: INTRADAY_MOVER Opportunity (Should PASS even without consolidation)
    print("\n📋 Test Case 2: INTRADAY_MOVER Opportunity")
    
    opp_mover = {
        'symbol': 'FLYE',
        'current_price': 10.0,
        'volume_ratio': 2.0,
        'opportunity_type': 'INTRADAY_MOVER'
    }
    
    # Reset mocks
    worker._detect_consolidation_after_momentum.reset_mock()
    worker._check_if_extended.reset_mock()
    
    result_mover = await worker.should_enter(opp_mover)
    print(f"Result: {result_mover}")
    
    if result_mover is True:
        print("✅ SUCCESS: INTRADAY_MOVER accepted! (Bypassed consolidation check)")
    else:
        print("❌ FAILURE: INTRADAY_MOVER rejected.")
        
    # Verify consolidation check was NOT called
    if worker._detect_consolidation_after_momentum.call_count == 0:
         print("✅ Verification: _detect_consolidation_after_momentum was NOT called.")
    else:
         print(f"❌ Verification: _detect_consolidation_after_momentum WAS called {worker._detect_consolidation_after_momentum.call_count} times.")

    # Verify extension check was NOT called (or result ignored)
    if worker._check_if_extended.call_count == 0:
         print("✅ Verification: _check_if_extended was NOT called.")
    else:
         print(f"❌ Verification: _check_if_extended WAS called {worker._check_if_extended.call_count} times.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_intraday_mover_bypass())
