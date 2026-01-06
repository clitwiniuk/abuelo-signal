#!/usr/bin/env python3
"""
Debug script for Service Locator TradeTally configuration
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_service_locator():
    """Debug service locator configuration"""
    print("🔍 DEBUG: Service Locator TradeTally Configuration")
    print("=" * 60)
    
    try:
        # Import service locator
        from core.service_locator import get_service_locator
        
        print("Step 1: Getting Service Locator...")
        service_locator = get_service_locator()
        
        print("Step 2: Getting configuration...")
        config = service_locator.get_config()
        
        print(f"Config object: {config}")
        print(f"TradeTally sync enabled: {config.enable_tradetally_sync}")
        print(f"TradeTally API key: {config.tradetally_api_key[:20]}..." if hasattr(config, 'tradetally_api_key') and config.tradetally_api_key else "No API key")
        print(f"TradeTally base URL: {config.tradetally_base_url}" if hasattr(config, 'tradetally_base_url') else "No base URL")
        
        print("\nStep 3: Checking existing TradeTally service...")
        existing_service = service_locator.get_service('tradetally_service')
        print(f"Existing service: {existing_service}")
        
        if existing_service:
            print("Service exists - checking its configuration...")
            if hasattr(existing_service, 'base_url'):
                print(f"Service base URL: {existing_service.base_url}")
            if hasattr(existing_service, 'api_key'):
                print(f"Service API key: {existing_service.api_key[:20]}...")
        
        print("\nStep 4: Testing manual service creation...")
        print("This will show what configuration is actually being used...")
        
        # Try to get or create the service
        import asyncio
        async def test_create():
            try:
                service = await service_locator.get_or_create_tradetally_service()
                if service:
                    print(f"✅ Service created successfully!")
                    print(f"Service type: {type(service)}")
                    if hasattr(service, 'integration') and service.integration:
                        print(f"Integration base URL: {service.integration.base_url}")
                        print(f"Integration API key: {service.integration.api_key[:20]}...")
                    
                    # Test manual sync to see the real error
                    print("\nStep 5: Testing manual sync...")
                    result = service.manual_sync()
                    print(f"Manual sync result: {result}")
                else:
                    print("❌ Service creation returned None")
            except Exception as e:
                print(f"❌ Error creating service: {e}")
                import traceback
                traceback.print_exc()
        
        asyncio.run(test_create())
        
    except Exception as e:
        print(f"❌ Error in debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_service_locator()