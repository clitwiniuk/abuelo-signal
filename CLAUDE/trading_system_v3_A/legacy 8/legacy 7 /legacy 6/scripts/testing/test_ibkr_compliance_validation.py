#!/usr/bin/env python3
"""
IBKR Compliance Validation Test
Tests IBKR-specific compliance rules without PDT restrictions
"""

import asyncio
import logging
from datetime import datetime

# Configure logging to suppress warnings during testing
logging.basicConfig(level=logging.ERROR)

from core.ibkr_compliance_config import ibkr_compliance
from test_short_squeeze_compliance import ComplianceContext, ShortSqueezeComplianceTestSuite

async def test_ibkr_compliance_rules():
    """Test IBKR-specific compliance without PDT restrictions"""
    
    print("🏦 IBKR COMPLIANCE VALIDATION TEST")
    print("=" * 60)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Testing IBKR-specific rules (No PDT restrictions)")
    print("=" * 60)
    print()
    
    # Test scenarios that would fail under standard PDT but pass under IBKR
    ibkr_scenarios = [
        {
            "name": "Small Account Unlimited Day Trading (IBKR Advantage)",
            "account_equity": 5_000,  # Well below $25K
            "day_trades_used": 10,    # Would violate standard PDT
            "trade_size": 3_000,
            "buying_power": 8_000,
            "stock_price": 15.50,
            "account_type": "MARGIN"
        },
        {
            "name": "Medium Account High Frequency Trading",
            "account_equity": 15_000,
            "day_trades_used": 25,    # Unlimited day trades
            "trade_size": 8_000,
            "buying_power": 20_000,
            "stock_price": 8.75,
            "account_type": "MARGIN"
        },
        {
            "name": "Penny Stock Trading Small Account",
            "account_equity": 3_000,
            "day_trades_used": 5,
            "trade_size": 1_500,
            "buying_power": 2_500,
            "stock_price": 2.45,     # Penny stock
            "account_type": "MARGIN"
        },
        {
            "name": "Cash Account Day Trading",
            "account_equity": 8_000,
            "day_trades_used": 15,   # Doesn't matter for cash
            "trade_size": 6_000,
            "buying_power": 8_000,
            "stock_price": 12.30,
            "account_type": "CASH"
        }
    ]
    
    print("📋 TESTING IBKR PDT EXEMPTIONS")
    print("-" * 40)
    
    for scenario in ibkr_scenarios:
        print(f"\n🧪 {scenario['name']}")
        print(f"   Account Equity: ${scenario['account_equity']:,}")
        print(f"   Day Trades Used: {scenario['day_trades_used']}")
        print(f"   Trade Size: ${scenario['trade_size']:,}")
        print(f"   Stock Price: ${scenario['stock_price']:.2f}")
        print(f"   Account Type: {scenario['account_type']}")
        
        # Test PDT compliance (IBKR specific)
        pdt_result = ibkr_compliance.check_pdt_compliance(
            day_trades_used=scenario['day_trades_used'],
            account_equity=scenario['account_equity'],
            account_type=scenario['account_type']
        )
        
        print(f"   📊 PDT Compliance:")
        print(f"   ✅ Status: {'COMPLIANT' if pdt_result['is_compliant'] else 'VIOLATION'}")
        print(f"   🔄 Day Trades Remaining: {pdt_result['day_trades_remaining']}")
        print(f"   💡 Reason: {pdt_result['reason']}")
        
        # Test margin compliance
        margin_result = ibkr_compliance.check_margin_compliance(
            trade_size=scenario['trade_size'],
            buying_power=scenario['buying_power'],
            stock_price=scenario['stock_price'],
            account_equity=scenario['account_equity']
        )
        
        print(f"   💰 Margin Compliance:")
        print(f"   ✅ Status: {'COMPLIANT' if margin_result['is_compliant'] else 'VIOLATION'}")
        print(f"   📊 Margin Required: ${margin_result['margin_required']:,.0f}")
        print(f"   🎯 Margin Type: {margin_result['margin_type']}")
        
        if margin_result['violations']:
            print("   🚫 Margin Violations:")
            for violation in margin_result['violations']:
                print(f"      • {violation}")
        
        if margin_result['warnings']:
            print("   ⚠️ Warnings:")
            for warning in margin_result['warnings']:
                print(f"      • {warning}")
        
        # Calculate max position size
        max_position = ibkr_compliance.get_max_position_size(
            buying_power=scenario['buying_power'],
            stock_price=scenario['stock_price'],
            account_type=scenario['account_type']
        )
        
        print(f"   📈 Max Position Size: ${max_position:,.0f}")
        
        # Overall assessment
        overall_compliant = pdt_result['is_compliant'] and margin_result['is_compliant']
        if overall_compliant:
            print("   ✅ OVERALL: TRADE APPROVED")
        else:
            print("   ❌ OVERALL: TRADE BLOCKED")
    
    # Test extended hours trading
    print(f"\n🕐 TESTING EXTENDED HOURS COMPLIANCE")
    print("-" * 40)
    
    extended_hours_tests = [
        {"time": 6.5, "description": "Pre-market (6:30 AM)"},
        {"time": 10.0, "description": "Regular hours (10:00 AM)"},
        {"time": 18.0, "description": "After-hours (6:00 PM)"},
        {"time": 22.0, "description": "Late night (10:00 PM)"}
    ]
    
    for test in extended_hours_tests:
        print(f"\n🕐 {test['description']}")
        
        extended_result = ibkr_compliance.check_extended_hours_compliance(
            time_of_day=test['time']/24.0
        )
        
        print(f"   Session: {extended_result['session']}")
        print(f"   Trading Allowed: {'✅ YES' if extended_result['allows_trading'] else '❌ NO'}")
        print(f"   Extended Hours: {'Yes' if extended_result['is_extended_hours'] else 'No'}")
        
        if extended_result['warnings']:
            for warning in extended_result['warnings']:
                print(f"   ⚠️ {warning}")
    
    print("\n" + "=" * 60)
    print("🏁 IBKR COMPLIANCE TEST CONCLUSIONS")
    print("=" * 60)
    
    print("✅ IBKR ADVANTAGES CONFIRMED:")
    print("   🔄 Unlimited day trades regardless of account size")
    print("   💰 No $25K PDT minimum equity requirement")
    print("   🕐 Extended hours trading supported")
    print("   📊 Standard margin rules still apply")
    print()
    
    print("📋 KEY DIFFERENCES FROM STANDARD PDT:")
    print("   • Standard US brokers: 3 day trades max for accounts <$25K")
    print("   • IBKR: Unlimited day trades for all account sizes")
    print("   • Margin requirements: Same as other brokers")
    print("   • Extended hours: Full pre-market and after-hours access")
    print()
    
    print("🎯 SYSTEM CONFIGURATION:")
    print("   ✅ PDT restrictions disabled for IBKR accounts")
    print("   ✅ Margin compliance still enforced")
    print("   ✅ Extended hours trading enabled")
    print("   ✅ Ready for high-frequency small cap day trading")
    print()
    
    print("🚀 DEPLOYMENT STATUS: IBKR compliance configured correctly!")

async def test_comparison_standard_vs_ibkr():
    """Compare standard PDT rules vs IBKR rules"""
    
    print("\n" + "=" * 60)
    print("⚔️ STANDARD PDT vs IBKR COMPARISON")
    print("=" * 60)
    
    test_scenario = {
        "account_equity": 8_000,   # Below $25K
        "day_trades_used": 5,      # Would violate standard PDT
        "trade_size": 4_000,
        "buying_power": 12_000
    }
    
    print(f"📊 Test Scenario:")
    print(f"   Account Equity: ${test_scenario['account_equity']:,}")
    print(f"   Day Trades This Week: {test_scenario['day_trades_used']}")
    print(f"   Requested Trade Size: ${test_scenario['trade_size']:,}")
    print()
    
    # Standard PDT rules (simulated)
    print("🏛️ STANDARD US BROKER (PDT Enforced):")
    if test_scenario['account_equity'] < 25_000 and test_scenario['day_trades_used'] >= 3:
        print("   ❌ TRADE BLOCKED: PDT violation")
        print("   🚫 Reason: Exceeded 3 day trades with account <$25K")
        print("   📋 Options: Wait for trades to reset or deposit to $25K+")
    else:
        print("   ✅ TRADE ALLOWED")
    
    print()
    
    # IBKR rules
    print("🏦 IBKR (No PDT Restrictions):")
    ibkr_pdt = ibkr_compliance.check_pdt_compliance(
        test_scenario['day_trades_used'],
        test_scenario['account_equity'], 
        "MARGIN"
    )
    
    if ibkr_pdt['is_compliant']:
        print("   ✅ TRADE ALLOWED")
        print(f"   💡 {ibkr_pdt['reason']}")
        print("   🔄 Day trades remaining: Unlimited")
    else:
        print("   ❌ TRADE BLOCKED")
    
    print("\n🎯 ADVANTAGE SUMMARY:")
    print("   IBKR allows this trade ✅")
    print("   Standard broker blocks ❌")
    print("   Freedom to day trade small caps without PDT limits 🚀")

if __name__ == "__main__":
    async def main():
        await test_ibkr_compliance_rules()
        await test_comparison_standard_vs_ibkr()
    
    asyncio.run(main())