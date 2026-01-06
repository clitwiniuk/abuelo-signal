
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from strategies.workers.smallcap_vwap_runner_worker_logic import SmallcapVwapRunnerWorker

class MockConfig:
    def __init__(self, config_dict=None):
        self.config = config_dict or {}

    def getfloat(self, section, key, fallback=0.0):
        return self.config.get(section, {}).get(key, fallback)

@pytest.fixture
def worker():
    # Mock dependencies
    execution_engine = MagicMock()
    risk_manager = MagicMock()
    
    # Mock configuration
    config_dict = {
        'SMALLCAP_VWAP_RUNNER': {
            'min_quality': 65.0,
            'stop_loss_pct': 0.02,
            'vwap_buffer_pct': 0.01,
            'trailing_stop_pct': 0.03,
            'risk_per_trade': 0.01
        }
    }
    config_parser = MockConfig(config_dict)

    # Instantiate worker
    worker = SmallcapVwapRunnerWorker(
        execution_engine=execution_engine,
        risk_manager=risk_manager,
        config=config_parser
    )
    
    # Mock internal state usually handled by BaseWorkerLogic
    worker.active_positions = {}
    
    return worker

@pytest.mark.asyncio
async def test_should_enter_valid(worker):
    opportunity = {
        'symbol': 'TEST',
        'quality_score': 70,  # > 65
        'current_price': 10.0,
        'vwap': 9.5,          # Price > VWAP
        'open': 9.8,
        'close': 10.0         # Green bar
    }
    
    should_enter, confidence, reason = await worker.should_enter(opportunity)
    
    assert should_enter is True
    assert confidence == 70.0
    assert "Q=70" in reason

@pytest.mark.asyncio
async def test_should_enter_low_quality(worker):
    opportunity = {
        'symbol': 'TEST',
        'quality_score': 60,  # < 65
        'current_price': 10.0,
        'vwap': 9.5,
        'open': 9.8,
        'close': 10.0
    }
    should_enter, _, reason = await worker.should_enter(opportunity)
    assert should_enter is False
    assert "Quality" in reason

@pytest.mark.asyncio
async def test_should_enter_below_vwap(worker):
    opportunity = {
        'symbol': 'TEST',
        'quality_score': 70,
        'current_price': 9.0,
        'vwap': 9.5,          # Price < VWAP
        'open': 8.8,
        'close': 9.0
    }
    should_enter, _, reason = await worker.should_enter(opportunity)
    assert should_enter is False
    assert "Below VWAP" in reason

@pytest.mark.asyncio
async def test_should_enter_red_bar(worker):
    opportunity = {
        'symbol': 'TEST',
        'quality_score': 70,
        'current_price': 10.0,
        'vwap': 9.5,
        'open': 10.2,
        'close': 10.0         # Red bar
    }
    should_enter, _, reason = await worker.should_enter(opportunity)
    assert should_enter is False
    assert "Red bar" in reason

@pytest.mark.asyncio
async def test_calculate_position_size(worker):
    opportunity = {'vwap': 9.9}
    # Entry: 10.0
    # Stop PCT: 10.0 * (1 - 0.02) = 9.80
    # Stop VWAP: 9.9 * (1 - 0.01) = 9.801 -> 9.80
    # Initial Stop = 9.80
    # Risk per share = 0.20
    # Account size mock = 100,000
    # Risk amount = 100,000 * 0.01 = 1000
    # Shares = 1000 / 0.20 = 5000
    
    shares = await worker.calculate_position_size('TEST', 10.0, opportunity)
    assert shares == 5000

@pytest.mark.asyncio
async def test_exit_hard_stop(worker):
    worker.active_positions['TEST'] = {
        'dynamic_stop_price': 9.80
    }
    
    # Mock time to 10:00 AM to avoid EOD exit
    current_bar = {
        'close': 9.75, 
        'vwap': 9.70,
        'timestamp': datetime(2026, 1, 5, 10, 0)
    } 
    
    should_exit, reason = await worker.should_exit('TEST', {}, current_bar)
    assert should_exit is True
    assert "Stop hit" in reason

@pytest.mark.asyncio
async def test_exit_vwap_break(worker):
    worker.active_positions['TEST'] = {
        'dynamic_stop_price': 9.00
    }
    
    # Mock time to 10:00 AM
    current_bar = {
        'close': 9.50, 
        'vwap': 9.60,
        'timestamp': datetime(2026, 1, 5, 10, 0)
    } 
    
    should_exit, reason = await worker.should_exit('TEST', {}, current_bar)
    assert should_exit is True
    assert "VWAP break" in reason

@pytest.mark.asyncio
async def test_exit_eod(worker):
    worker.active_positions['TEST'] = {
        'dynamic_stop_price': 9.00
    }
    
    # Mock current time to 15:55 (15.91)
    current_bar = {
        'close': 10.0, 
        'vwap': 9.5,
        'timestamp': datetime(2026, 1, 5, 15, 55)
    } 
    
    should_exit, reason = await worker.should_exit('TEST', {}, current_bar)
    assert should_exit is True
    assert "EOD Exit" in reason

@pytest.mark.asyncio
async def test_trailing_stop_update(worker):
    worker.active_positions['TEST'] = {
        'dynamic_stop_price': 9.80, # Stop from entry at 10.0
        'high_water_mark': 10.0
    }
    
    # Price moves UP to 10.50
    current_bar = {'close': 10.50}
    
    await worker.update_position('TEST', {}, current_bar)
    
    # New high water mark: 10.50
    assert worker.active_positions['TEST']['high_water_mark'] == 10.50
    
    # New stop: 10.50 * (1 - 0.03) = 10.185
    assert worker.active_positions['TEST']['dynamic_stop_price'] == 10.185

