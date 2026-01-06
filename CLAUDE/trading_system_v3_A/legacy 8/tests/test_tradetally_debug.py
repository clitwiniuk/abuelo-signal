#!/usr/bin/env python3
"""
Test TradeTally Integration with Debug Logging
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_tradetally_integration():
    """Test TradeTally integration with detailed debug logging"""
    print("🚀 Starting TradeTally Debug Test...")
    
    try:
        # First, let's test the configuration loading
        print("\n" + "="*50)
        print("STEP 1: Testing Configuration Loading")
        print("="*50)
        
        from config.tradetally_config import config
        print(f"Configuration loaded successfully!")
        print(f"Is configured: {config.is_configured()}")
        print(f"Config dict: {config.get_config_dict()}")
        
        print("\n" + "="*50)
        print("STEP 2: Testing TradeTally Integration Creation")
        print("="*50)
        
        # Now test creating the integration
        from integrations.tradetally_sync import TradeTallyIntegration
        
        if not config.is_configured():
            print("❌ Configuration not valid, cannot proceed with integration test")
            return False
        
        # Create integration instance
        integration = TradeTallyIntegration(
            api_key=config.api_key,
            base_url=config.base_url,
            db_path=config.db_path
        )
        
        print("\n" + "="*50)
        print("STEP 3: Testing API Connection")
        print("="*50)
        
        # Test connection
        connection_result = integration.test_connection()
        print(f"Connection test result: {connection_result}")
        
        return connection_result
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("TradeTally Integration Debug Test")
    print("=" * 50)
    
    success = test_tradetally_integration()
    
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")