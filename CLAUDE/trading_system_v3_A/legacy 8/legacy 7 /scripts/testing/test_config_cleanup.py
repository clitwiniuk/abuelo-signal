#!/usr/bin/env python3
"""
Test Config Cleanup
===================

Verifica que el config.ini consolidado no tenga parámetros duplicados
y que los valores sean consistentes.
"""

import configparser
import sys
import os

def test_config_cleanup():
    """Test que verifica limpieza del config.ini"""
    
    print("🧹 CONFIG CLEANUP VALIDATION TEST")
    print("=" * 50)
    
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    # Parámetros que estaban duplicados - verificar solo en GLOBAL
    duplicated_params = [
        'max_daily_trades',
        'max_concurrent_positions', 
        'daily_loss_limit',
        'risk_per_trade',
        'market_open_time',
        'market_close_time'
    ]
    
    issues_found = []
    
    # Check 1: Parámetros consolidados están en GLOBAL
    print("\n📋 Check 1: Consolidated parameters in GLOBAL")
    for param in duplicated_params:
        if config.has_option('GLOBAL', param):
            value = config.get('GLOBAL', param)
            print(f"✅ {param} = {value}")
        else:
            print(f"❌ {param} missing from GLOBAL")
            issues_found.append(f"{param} missing from GLOBAL")
    
    # Check 2: No hay duplicados en TRADING
    print("\n📋 Check 2: No duplicates in TRADING")
    trading_params = dict(config.items('TRADING')) if config.has_section('TRADING') else {}
    
    found_duplicates = []
    for param in duplicated_params:
        if param in trading_params:
            found_duplicates.append(param)
            print(f"⚠️ {param} still duplicated in TRADING: {trading_params[param]}")
    
    if not found_duplicates:
        print("✅ No duplicated parameters found in TRADING")
    else:
        issues_found.extend(found_duplicates)
    
    # Check 3: Valores consolidados son correctos
    print("\n📋 Check 3: Consolidated values are reasonable")
    
    expected_values = {
        'max_daily_trades': '50',  # Higher value chosen
        'max_concurrent_positions': '30',  # Higher value chosen  
        'daily_loss_limit': '300.0',  # Higher value chosen
        'risk_per_trade': '0.05',  # Higher value chosen
        'hybrid_max_strategies': '3'  # Updated for diversity
    }
    
    for param, expected in expected_values.items():
        if config.has_option('GLOBAL', param):
            actual = config.get('GLOBAL', param)
            if actual == expected:
                print(f"✅ {param} = {actual} (correct)")
            else:
                print(f"⚠️ {param} = {actual} (expected {expected})")
                issues_found.append(f"{param} value mismatch")
        elif config.has_option('TRADING', param):
            actual = config.get('TRADING', param)
            if actual == expected:
                print(f"✅ {param} = {actual} (correct, in TRADING)")
            else:
                print(f"⚠️ {param} = {actual} (expected {expected}, in TRADING)")
    
    # Check 4: Sections exist
    print("\n📋 Check 4: Required sections exist")
    required_sections = ['GLOBAL', 'TRADING']
    for section in required_sections:
        if config.has_section(section):
            print(f"✅ Section [{section}] exists")
        else:
            print(f"❌ Section [{section}] missing")
            issues_found.append(f"Section {section} missing")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 CONFIG CLEANUP SUMMARY")
    print("=" * 50)
    
    if not issues_found:
        print("🚀 CONFIG CLEANUP SUCCESSFUL!")
        print("✅ No duplicated parameters")
        print("✅ Values properly consolidated") 
        print("✅ Configuration is clean and consistent")
        return True
    else:
        print(f"⚠️ {len(issues_found)} issues found:")
        for issue in issues_found:
            print(f"   • {issue}")
        return False

if __name__ == "__main__":
    success = test_config_cleanup()
    sys.exit(0 if success else 1)