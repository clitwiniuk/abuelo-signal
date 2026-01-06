#!/usr/bin/env python3
"""
Test específico para el problema del botón de iniciar en Streamlit
Simula el comportamiento exacto del TradingSystemController
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from threading import Thread
import random

# Add the project root to Python path
current_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(current_dir))

# Mock Streamlit session state más realista
import types
st = types.SimpleNamespace()
st.session_state = types.SimpleNamespace()

# Initialize session state exactly like Streamlit
st.session_state.manual_symbols = ['PSTV']
st.session_state.system_config = None
st.session_state.trading_system = None
st.session_state.system_thread = None
st.session_state.system_running = False
st.session_state.positions = {}
st.session_state.daily_stats = {}

# Mock st functions with realistic behavior
error_messages = []
success_messages = []

def mock_error(msg):
    error_messages.append(msg)
    print(f"❌ STREAMLIT ERROR: {msg}")

def mock_success(msg):
    success_messages.append(msg)
    print(f"✅ STREAMLIT SUCCESS: {msg}")

st.error = mock_error
st.success = mock_success

# Mock st module
sys.modules['streamlit'] = st

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class TradingSystemController:
    """Exact copy of the TradingSystemController from streamlit_app_refactored.py"""
    
    def __init__(self):
        self.logger = logging.getLogger("TradingSystemController")
    
    def register_strategies(self):
        """Register all available strategies"""
        try:
            from strategies import register_strategy
            from strategies.macdv_strategy import MACDVStrategy
            register_strategy('macdv', MACDVStrategy)
            self.logger.info("All strategies registered successfully")
        except Exception as e:
            self.logger.error(f"Error registering strategies: {e}")
    
    def start_system(self, config, symbols=None):
        """Start trading system - EXACT COPY from working version"""
        if st.session_state.system_running:
            st.error("El sistema ya está en ejecución")
            return False
        
        try:
            self.register_strategies()
            
            # Generate random client ID
            config.broker_client_id = random.randint(100, 9999)
            
            # Create trading system
            from main import TradingSystemManager
            st.session_state.trading_system = TradingSystemManager(config, in_streamlit=True)
            
            # Start in separate thread
            st.session_state.system_thread = Thread(
                target=self._run_system_async, 
                args=(st.session_state.trading_system, symbols)
            )
            st.session_state.system_thread.daemon = True
            st.session_state.system_thread.start()
            
            st.session_state.system_running = True
            self.logger.info(f"System started with client_id: {config.broker_client_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting system: {e}")
            st.error(f"Error starting system: {e}")
            return False
    
    def _run_system_async(self, system, symbols=None):
        """Run system asynchronously - EXACT COPY from working version"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(system.initialize())
            loop.run_until_complete(system.start(symbols))
            
        except Exception as e:
            self.logger.error(f"Error in trading system: {e}")
        finally:
            st.session_state.system_running = False
            loop.close()

def test_button_behavior():
    """Test the exact button behavior from Streamlit"""
    
    print("🧪 TESTING: Streamlit Button Behavior Issues")
    print("="*60)
    
    # Create config
    from core.interfaces import TradingConfig
    config = TradingConfig(
        strategy_name='macdv',
        broker_client_id=1,
        broker_host='127.0.0.1',
        broker_port=7497
    )
    
    controller = TradingSystemController()
    
    print("\n🎯 Test 1: First button press (should work)")
    print(f"Initial system_running: {st.session_state.system_running}")
    
    result1 = controller.start_system(config, st.session_state.manual_symbols)
    print(f"Start result: {result1}")
    print(f"System running after start: {st.session_state.system_running}")
    print(f"Thread alive: {st.session_state.system_thread.is_alive() if st.session_state.system_thread else 'No thread'}")
    
    # Wait a moment for the thread to start
    import time
    time.sleep(2)
    print(f"System running after 2s: {st.session_state.system_running}")
    
    print("\n🎯 Test 2: Second button press (should show error)")
    result2 = controller.start_system(config, st.session_state.manual_symbols)
    print(f"Second start result: {result2}")
    print(f"Error messages: {error_messages}")
    
    print("\n🎯 Test 3: Check thread behavior")
    if st.session_state.system_thread:
        print(f"Thread is alive: {st.session_state.system_thread.is_alive()}")
        print(f"Thread is daemon: {st.session_state.system_thread.daemon}")
    
    # Wait for system to potentially finish
    time.sleep(5)
    print(f"System running after 5s total: {st.session_state.system_running}")
    
    print("\n🎯 Test 4: Try to start again after thread finishes")
    if not st.session_state.system_running:
        print("System is not running, trying to start again...")
        result3 = controller.start_system(config, st.session_state.manual_symbols)
        print(f"Third start result: {result3}")
    
    # Analyze the results
    print("\n📊 ANÁLISIS:")
    print(f"- Primera ejecución exitosa: {result1}")
    print(f"- Segunda ejecución bloqueada: {not result2}")
    print(f"- Errores mostrados: {len(error_messages)}")
    print(f"- Thread creado correctamente: {st.session_state.system_thread is not None}")
    
    if len(error_messages) > 0:
        print("✅ El botón funciona correctamente - previene múltiples ejecuciones")
    else:
        print("⚠️  Posible problema - no se está previniendo múltiples ejecuciones")

if __name__ == "__main__":
    test_button_behavior()