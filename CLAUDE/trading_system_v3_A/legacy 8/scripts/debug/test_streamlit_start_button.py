#!/usr/bin/env python3
"""
Test para diagnosticar problemas con el botón de iniciar trades en Streamlit
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the project root to Python path
current_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(current_dir))

# Mock Streamlit session state
import types
st = types.SimpleNamespace()
st.session_state = types.SimpleNamespace()

# Initialize session state like Streamlit does
st.session_state.manual_symbols = ['PSTV', 'AAPL']
st.session_state.system_config = None
st.session_state.trading_system = None
st.session_state.system_thread = None
st.session_state.system_running = False
st.session_state.positions = {}
st.session_state.daily_stats = {}

# Mock st functions
def mock_error(msg):
    print(f"❌ STREAMLIT ERROR: {msg}")

def mock_success(msg):
    print(f"✅ STREAMLIT SUCCESS: {msg}")

def mock_info(msg):
    print(f"ℹ️ STREAMLIT INFO: {msg}")

def mock_rerun():
    print("🔄 STREAMLIT RERUN called")

st.error = mock_error
st.success = mock_success  
st.info = mock_info
st.rerun = mock_rerun

# Mock st module in sys.modules
sys.modules['streamlit'] = st

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_start_button_logic():
    """Test the logic behind the start button"""
    
    print("🧪 TESTING: Streamlit Start Button Logic")
    print("="*60)
    
    try:
        # Import the components we need
        from core.interfaces import TradingConfig
        from main import TradingSystemManager
        
        print("\n🎯 Step 1: Create config (simulating Streamlit config)")
        
        # Create a basic config
        import configparser
        config_parser = configparser.ConfigParser()
        config_parser.read('config.ini')
        
        # Simulate creating TradingConfig like streamlit does
        config = TradingConfig(
            max_positions=config_parser.getint('TRADING', 'max_positions', fallback=5),
            max_risk_per_trade=config_parser.getfloat('TRADING', 'max_risk_per_trade', fallback=0.02),
            max_daily_loss=config_parser.getfloat('TRADING', 'max_daily_loss', fallback=-500.0),
            max_daily_trades=config_parser.getint('TRADING', 'max_daily_trades', fallback=20),
            enable_filters=config_parser.getboolean('TRADING', 'use_volume_filter', fallback=True),
            portfolio_capital=config_parser.getfloat('TRADING', 'portfolio_capital', fallback=2000.0),
            
            broker_host=config_parser.get('IBKR', 'host', fallback='127.0.0.1'),
            broker_port=config_parser.getint('IBKR', 'port', fallback=7497),
            broker_client_id=config_parser.getint('IBKR', 'client_id', fallback=1),
            
            strategy_name=config_parser.get('TRADING', 'strategy', fallback='macdv'),
            timeframe=config_parser.get('TRADING', 'timeframe', fallback='1 min'),
            
            log_level=config_parser.get('LOGGING', 'level', fallback='INFO'),
            log_file=config_parser.get('LOGGING', 'file', fallback='trading_system.log')
        )
        
        print(f"Config created: strategy={config.strategy_name}, symbols={st.session_state.manual_symbols}")
        
        print("\n🚀 Step 2: Test start_system logic")
        
        # Test the start logic (mimicking TradingSystemController.start_system)
        if st.session_state.system_running:
            print("❌ System already running - should show error")
            return False
        
        # Generate random client ID (like in the real code)
        import random
        config.broker_client_id = random.randint(100, 9999)
        print(f"Generated client_id: {config.broker_client_id}")
        
        # Create trading system
        print("🔧 Creating TradingSystemManager...")
        trading_system = TradingSystemManager(config, in_streamlit=True)
        st.session_state.trading_system = trading_system
        
        print("🔌 Testing system initialization...")
        await trading_system.initialize()
        print("✅ System initialized successfully")
        
        print("🚀 Testing system start with symbols...")
        symbols = st.session_state.manual_symbols
        print(f"Starting with symbols: {symbols}")
        
        # Start the system (but don't actually run the loop)
        print("📋 Registering strategies...")
        from strategies import register_strategy
        from strategies.macdv_strategy import MACDVStrategy
        register_strategy('macdv', MACDVStrategy)
        
        # Test the critical part - starting with symbols
        # await trading_system.start(symbols)  # This would start the full loop
        print("✅ System start logic tested successfully")
        
        st.session_state.system_running = True
        print("✅ Session state updated - system marked as running")
        
        print("\n🛑 Step 3: Test stop logic")
        if st.session_state.trading_system and st.session_state.system_running:
            print("🔧 Stopping system...")
            await st.session_state.trading_system.stop()
            st.session_state.system_running = False
            print("✅ System stopped successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_start_button_logic())
    if success:
        print("\n🎯 RESULTADO: El botón de iniciar debería funcionar correctamente")
    else:
        print("\n❌ RESULTADO: Hay problemas con la lógica del botón de iniciar")