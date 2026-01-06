#!/usr/bin/env python3
"""
IBKR-Specific Compliance Configuration
Custom rules for Interactive Brokers that differ from standard US PDT rules
"""

from typing import Dict, List
from dataclasses import dataclass

@dataclass
class IBKRComplianceRules:
    """IBKR-specific compliance rules"""
    broker: str = "IBKR"
    pdt_enforcement: bool = False  # IBKR doesn't enforce PDT on small accounts
    allows_unlimited_day_trades: bool = True  # IBKR allows unlimited day trades
    min_equity_for_pdt: float = 0  # No minimum equity requirement
    day_trade_limit: int = 999  # Effectively unlimited
    
    # Margin rules (still apply)
    standard_margin_requirement: float = 50.0  # 50%
    penny_stock_margin: float = 100.0  # 100% for stocks <$5
    maintenance_margin_rate: float = 25.0  # 25%
    
    # IBKR-specific features
    supports_fractional_shares: bool = True
    allows_premarket_trading: bool = True
    allows_afterhours_trading: bool = True

class IBKRComplianceChecker:
    """IBKR-specific compliance checker"""
    
    def __init__(self):
        self.rules = IBKRComplianceRules()
    
    def check_pdt_compliance(self, day_trades_used: int, account_equity: float, 
                           account_type: str) -> Dict:
        """
        Check PDT compliance for IBKR accounts
        IBKR doesn't enforce PDT rules on accounts <$25K
        """
        
        return {
            "is_compliant": True,  # IBKR always compliant for PDT
            "violations": [],
            "warnings": [],
            "day_trades_remaining": 999,  # Unlimited
            "reason": "IBKR does not enforce PDT restrictions on small accounts"
        }
    
    def check_margin_compliance(self, trade_size: float, buying_power: float,
                               stock_price: float, account_equity: float) -> Dict:
        """Check margin requirements (still apply for IBKR)"""
        
        violations = []
        warnings = []
        
        # Determine margin requirement
        if stock_price < 5.0:
            margin_requirement = trade_size * (self.rules.penny_stock_margin / 100)
        else:
            margin_requirement = trade_size * (self.rules.standard_margin_requirement / 100)
        
        # Check if sufficient buying power
        if margin_requirement > buying_power:
            violations.append(f"Insufficient buying power: ${margin_requirement:,.0f} required, ${buying_power:,.0f} available")
        
        # Check maintenance margin
        maintenance_required = account_equity * (self.rules.maintenance_margin_rate / 100)
        if account_equity < maintenance_required * 1.1:  # 10% buffer
            warnings.append("Account close to maintenance margin requirement")
        
        return {
            "is_compliant": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "margin_required": margin_requirement,
            "margin_type": "penny_stock" if stock_price < 5.0 else "standard"
        }
    
    def get_max_position_size(self, buying_power: float, stock_price: float, 
                             account_type: str) -> float:
        """Calculate maximum position size for IBKR account"""
        
        if account_type.upper() == "CASH":
            return buying_power  # Cash accounts limited to available cash
        
        # Margin accounts
        if stock_price < 5.0:
            # Penny stocks require 100% margin
            return buying_power
        else:
            # Standard stocks allow 2:1 leverage
            return buying_power * 2.0
    
    def check_extended_hours_compliance(self, time_of_day: float) -> Dict:
        """Check if extended hours trading is allowed"""
        
        # IBKR allows premarket (4:00-9:30 ET) and afterhours (16:00-20:00 ET)
        is_premarket = 4.0/24 <= time_of_day < 9.5/24
        is_afterhours = 16.0/24 <= time_of_day < 20.0/24
        is_extended_hours = is_premarket or is_afterhours
        
        return {
            "allows_trading": True,  # IBKR allows extended hours
            "is_extended_hours": is_extended_hours,
            "session": "PREMARKET" if is_premarket else "AFTERHOURS" if is_afterhours else "REGULAR",
            "warnings": ["Extended hours trading has additional risks"] if is_extended_hours else []
        }

# Singleton instance for global use
ibkr_compliance = IBKRComplianceChecker()