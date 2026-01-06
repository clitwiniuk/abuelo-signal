#!/usr/bin/env python3
"""
Test Config System Compatibility
================================

Verifica que el config.ini tenga los parámetros en las secciones correctas
según lo que espera el ServiceLocator y otros componentes del sistema.
"""

import configparser
import sys
import os

def test_config_system_compatibility():
    """Test que verifica compatibilidad con el sistema"""
    
    print("🔧 CONFIG SYSTEM COMPATIBILITY TEST")
    print("=" * 50)
    
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    issues_found = []
    
    # Check 1: ServiceLocator required parameters in TRADING section
    print("\n📋 Check 1: ServiceLocator Required Parameters")
    trading_required = [
        'max_positions',
        'max_positions_per_symbol', 
        'max_daily_loss',
        'max_daily_trades',
        'max_position_value',
        'strategy',
        'active_profile',
        'enable_smallcap_mode',
        'scan_interval_seconds',
        'enable_hybrid_learning',
        'hybrid_max_strategies',
        'hybrid_learning_rate'
    ]
    
    for param in trading_required:
        if config.has_option('TRADING', param):
            value = config.get('TRADING', param)
            print(f"✅ TRADING.{param} = {value}")
        else:
            print(f"❌ TRADING.{param} MISSING")
            issues_found.append(f"TRADING.{param} required by ServiceLocator")
    
    # Check 2: Global parameters for strategies
    print("\n📋 Check 2: GLOBAL Parameters for Strategies")
    global_expected = [
        'min_price',
        'max_price', 
        'min_daily_volume',
        'long_only',
        'enable_ml_exits',
        'risk_per_trade'
    ]
    
    for param in global_expected:
        if config.has_option('GLOBAL', param):
            value = config.get('GLOBAL', param)
            print(f"✅ GLOBAL.{param} = {value}")
        else:
            print(f"⚠️ GLOBAL.{param} missing (strategies may use defaults)")
    
    # Check 3: No critical duplicates
    print("\n📋 Check 3: No Critical Parameter Conflicts")
    
    # These should be in TRADING only (ServiceLocator expects them there)
    trading_only = ['max_positions', 'max_daily_trades', 'max_daily_loss', 'max_position_value']
    
    for param in trading_only:
        in_global = config.has_option('GLOBAL', param)
        in_trading = config.has_option('TRADING', param)
        
        if in_trading and not in_global:
            print(f"✅ {param} correctly in TRADING only")
        elif in_global and in_trading:
            print(f"⚠️ {param} duplicated in both sections")
            issues_found.append(f"{param} duplicated - may cause conflicts")
        elif in_global and not in_trading:
            print(f"❌ {param} in GLOBAL but ServiceLocator expects it in TRADING")
            issues_found.append(f"{param} in wrong section")
        else:
            print(f"❌ {param} missing from both sections")
            issues_found.append(f"{param} missing entirely")
    
    # Check 4: Required sections exist
    print("\n📋 Check 4: Required Sections")
    required_sections = ['GLOBAL', 'TRADING', 'IBKR']
    for section in required_sections:
        if config.has_section(section):
            print(f"✅ Section [{section}] exists")
        else:
            if section == 'IBKR':
                print(f"⚠️ Section [{section}] missing (will use defaults)")
            else:
                print(f"❌ Section [{section}] REQUIRED")
                issues_found.append(f"Section {section} missing")
    
    # Check 5: Value validation
    print("\n📋 Check 5: Value Validation")
    
    try:
        # Test critical numeric values
        max_pos = config.getint('TRADING', 'max_positions', fallback=0)
        max_trades = config.getint('TRADING', 'max_daily_trades', fallback=0)
        max_loss = config.getfloat('TRADING', 'max_daily_loss', fallback=0)
        
        if max_pos > 0:
            print(f"✅ max_positions = {max_pos} (valid)")
        else:
            print(f"❌ max_positions = {max_pos} (invalid)")
            issues_found.append("max_positions must be > 0")
            
        if max_trades > 0:
            print(f"✅ max_daily_trades = {max_trades} (valid)")
        else:
            print(f"❌ max_daily_trades = {max_trades} (invalid)")
            issues_found.append("max_daily_trades must be > 0")
            
        if max_loss < 0:
            print(f"✅ max_daily_loss = {max_loss} (valid - negative limit)")
        else:
            print(f"❌ max_daily_loss = {max_loss} (should be negative)")
            issues_found.append("max_daily_loss should be negative")
    
    except Exception as e:
        print(f"❌ Error validating values: {e}")
        issues_found.append(f"Value validation error: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 SYSTEM COMPATIBILITY SUMMARY")
    print("=" * 50)
    
    if not issues_found:
        print("🚀 CONFIG IS SYSTEM-COMPATIBLE!")
        print("✅ All required parameters in correct sections")
        print("✅ ServiceLocator will find all needed values") 
        print("✅ No conflicts or missing critical parameters")
        return True
    else:
        print(f"⚠️ {len(issues_found)} compatibility issues found:")
        for issue in issues_found:
            print(f"   • {issue}")
        print("\n💡 These issues may cause system errors or unexpected behavior")
        return False

if __name__ == "__main__":
    success = test_config_system_compatibility()
    sys.exit(0 if success else 1)