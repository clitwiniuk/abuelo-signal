#!/usr/bin/env python3
"""
Test para verificar la corrección del PerformanceMonitor record_event
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PerformanceMonitorTest")

def test_record_event_method():
    """Test PerformanceMonitor record_event method"""
    try:
        from utils.performance_monitor import PerformanceMonitor
        
        print("🔍 Testing PerformanceMonitor record_event method...")
        
        # Create monitor
        monitor = PerformanceMonitor(sampling_interval=5.0)
        
        # Test record_event method exists
        if hasattr(monitor, 'record_event'):
            print("✅ record_event method exists")
            
            # Test calling the method
            monitor.record_event("scan_started")
            monitor.record_event("scan_error")
            monitor.record_event("test_event")
            
            print("✅ record_event method calls successful")
            
            # Test event counts
            if hasattr(monitor, 'get_event_counts'):
                event_counts = monitor.get_event_counts()
                print(f"✅ Event counts: {event_counts}")
                
                if 'scan_started' in event_counts and event_counts['scan_started'] == 1:
                    print("✅ scan_started event recorded correctly")
                else:
                    print("❌ scan_started event not recorded correctly")
                    return False
                    
            else:
                print("❌ get_event_counts method missing")
                return False
            
            # Test get_metrics includes event_counts
            metrics = monitor.get_metrics()
            if 'event_counts' in metrics:
                print("✅ event_counts included in metrics")
            else:
                print("❌ event_counts not included in metrics")
                return False
            
        else:
            print("❌ record_event method does not exist")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ PerformanceMonitor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_production_calls():
    """Test the specific calls from production runner"""
    try:
        from utils.performance_monitor import PerformanceMonitor
        
        print("🔍 Testing production runner calls...")
        
        monitor = PerformanceMonitor(sampling_interval=5.0)
        
        # These are the exact calls made in production
        if monitor:
            monitor.record_event("scan_started")
            print("✅ monitor.record_event('scan_started') works")
            
        if monitor:
            monitor.record_event("scan_error")
            print("✅ monitor.record_event('scan_error') works")
        
        return True
        
    except Exception as e:
        print(f"❌ Production calls test failed: {e}")
        return False

def run_all_tests():
    """Run all performance monitor tests"""
    print("🧪 TESTING PERFORMANCE MONITOR FIXES")
    print("=" * 50)
    
    tests = [
        ("record_event Method", test_record_event_method),
        ("Production Calls", test_production_calls)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        print("-" * 30)
        
        try:
            result = test_func()
            results.append(result)
            
        except Exception as e:
            print(f"❌ {test_name}: FAILED - {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    success_rate = (passed / total) * 100
    
    print("\n" + "=" * 50)
    print("📊 PERFORMANCE MONITOR TEST SUMMARY")
    print("=" * 50)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {total - passed} ❌")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("\n🟢 PERFORMANCE MONITOR: FIXED AND READY")
    else:
        print("\n🔴 PERFORMANCE MONITOR: STILL HAS ISSUES")
    
    return success_rate == 100

if __name__ == "__main__":
    run_all_tests()