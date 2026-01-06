"""
IBKR Commission Calculator
Calcula comisiones estimadas basadas en las tarifas oficiales de IBKR
"""

from typing import Tuple
from decimal import Decimal, ROUND_HALF_UP

class IBKRCommissionCalculator:
    """Calculador de comisiones para IBKR US stocks"""
    
    # Tarifas IBKR Tiered (más común)
    TIERED_RATE_PER_SHARE = 0.0035  # $0.0035 por acción
    TIERED_MIN_COMMISSION = 0.35    # Mínimo $0.35 por orden
    TIERED_MAX_PCT = 0.01          # Máximo 1% del valor del trade
    
    # Tarifas IBKR Fixed 
    FIXED_BASE = 1.00              # $1.00 hasta 300 acciones
    FIXED_THRESHOLD = 300          # 300 acciones umbral
    FIXED_ADDITIONAL_RATE = 0.0035 # $0.0035 por acción adicional
    
    # Fees regulatorias (solo en ventas)
    SEC_FEE_RATE = 0.0000278       # $0.0000278 por $1 vendido
    FINRA_TAF_RATE = 0.000166      # $0.000166 por acción vendida
    FINRA_TAF_MAX = 7.27           # Máximo $7.27 por orden
    CLEARING_FEE = 0.00002         # $0.00002 por acción
    
    @staticmethod
    def round_currency(amount: float) -> float:
        """Redondear a 2 decimales usando reglas bancarias"""
        decimal_amount = Decimal(str(amount))
        return float(decimal_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    
    @classmethod
    def calculate_tiered_commission(cls, quantity: int, price: float, side: str) -> Tuple[float, dict]:
        """
        Calcular comisión usando estructura Tiered
        
        Args:
            quantity: Número de acciones
            price: Precio por acción
            side: 'BUY' o 'SELL'
        
        Returns:
            Tuple[total_commission, breakdown_dict]
        """
        trade_value = quantity * price
        
        # Comisión base Tiered
        base_commission = quantity * cls.TIERED_RATE_PER_SHARE
        
        # Aplicar mínimo
        base_commission = max(base_commission, cls.TIERED_MIN_COMMISSION)
        
        # Aplicar máximo (1% del valor del trade)
        max_commission = trade_value * cls.TIERED_MAX_PCT
        base_commission = min(base_commission, max_commission)
        
        breakdown = {
            'base_commission': cls.round_currency(base_commission),
            'sec_fee': 0.0,
            'finra_taf': 0.0,
            'clearing_fee': 0.0
        }
        
        # Fees adicionales solo en ventas
        if side.upper() == 'SELL':
            # SEC Fee
            sec_fee = trade_value * cls.SEC_FEE_RATE
            breakdown['sec_fee'] = cls.round_currency(sec_fee)
            
            # FINRA TAF
            finra_taf = min(quantity * cls.FINRA_TAF_RATE, cls.FINRA_TAF_MAX)
            breakdown['finra_taf'] = cls.round_currency(finra_taf)
            
            # Clearing Fee
            clearing_fee = quantity * cls.CLEARING_FEE
            breakdown['clearing_fee'] = cls.round_currency(clearing_fee)
        
        total_commission = sum(breakdown.values())
        return cls.round_currency(total_commission), breakdown
    
    @classmethod 
    def calculate_fixed_commission(cls, quantity: int, price: float, side: str) -> Tuple[float, dict]:
        """
        Calcular comisión usando estructura Fixed
        
        Args:
            quantity: Número de acciones
            price: Precio por acción  
            side: 'BUY' o 'SELL'
        
        Returns:
            Tuple[total_commission, breakdown_dict]
        """
        trade_value = quantity * price
        
        # Comisión base Fixed
        if quantity <= cls.FIXED_THRESHOLD:
            base_commission = cls.FIXED_BASE
        else:
            additional_shares = quantity - cls.FIXED_THRESHOLD
            base_commission = cls.FIXED_BASE + (additional_shares * cls.FIXED_ADDITIONAL_RATE)
        
        breakdown = {
            'base_commission': cls.round_currency(base_commission),
            'sec_fee': 0.0,
            'finra_taf': 0.0, 
            'clearing_fee': 0.0
        }
        
        # Fees adicionales solo en ventas
        if side.upper() == 'SELL':
            # SEC Fee
            sec_fee = trade_value * cls.SEC_FEE_RATE
            breakdown['sec_fee'] = cls.round_currency(sec_fee)
            
            # FINRA TAF
            finra_taf = min(quantity * cls.FINRA_TAF_RATE, cls.FINRA_TAF_MAX)
            breakdown['finra_taf'] = cls.round_currency(finra_taf)
            
            # Clearing Fee
            clearing_fee = quantity * cls.CLEARING_FEE
            breakdown['clearing_fee'] = cls.round_currency(clearing_fee)
        
        total_commission = sum(breakdown.values())
        return cls.round_currency(total_commission), breakdown
    
    @classmethod
    def calculate_commission(cls, quantity: int, price: float, side: str, 
                           plan: str = 'tiered') -> Tuple[float, dict]:
        """
        Calcular comisión total estimada
        
        Args:
            quantity: Número de acciones
            price: Precio por acción
            side: 'BUY' o 'SELL'  
            plan: 'tiered' (default) o 'fixed'
        
        Returns:
            Tuple[total_commission, breakdown_dict]
        """
        if plan.lower() == 'fixed':
            return cls.calculate_fixed_commission(quantity, price, side)
        else:
            return cls.calculate_tiered_commission(quantity, price, side)
    
    @classmethod
    def calculate_round_trip_commission(cls, quantity: int, entry_price: float, 
                                      exit_price: float, plan: str = 'tiered') -> Tuple[float, dict]:
        """
        Calcular comisión total para un trade completo (entrada + salida)
        
        Args:
            quantity: Número de acciones
            entry_price: Precio de entrada
            exit_price: Precio de salida
            plan: 'tiered' (default) o 'fixed'
        
        Returns:
            Tuple[total_commission, breakdown_dict]
        """
        # Comisión de entrada (BUY)
        entry_commission, entry_breakdown = cls.calculate_commission(
            quantity, entry_price, 'BUY', plan
        )
        
        # Comisión de salida (SELL) 
        exit_commission, exit_breakdown = cls.calculate_commission(
            quantity, exit_price, 'SELL', plan
        )
        
        # Combinar breakdown
        combined_breakdown = {
            'entry_commission': entry_commission,
            'exit_commission': exit_commission,
            'entry_breakdown': entry_breakdown,
            'exit_breakdown': exit_breakdown,
            'total_base': cls.round_currency(entry_breakdown['base_commission'] + exit_breakdown['base_commission']),
            'total_fees': cls.round_currency(sum([
                exit_breakdown['sec_fee'],
                exit_breakdown['finra_taf'], 
                exit_breakdown['clearing_fee']
            ]))
        }
        
        total_commission = cls.round_currency(entry_commission + exit_commission)
        return total_commission, combined_breakdown


def main():
    """Función de testing"""
    calculator = IBKRCommissionCalculator()
    
    # Test casos típicos
    test_cases = [
        (100, 25.50, 26.75, 'tiered'),   # Trade pequeño
        (500, 15.25, 14.80, 'tiered'),   # Trade medio
        (1000, 5.50, 6.20, 'tiered'),    # Trade grande
        (100, 25.50, 26.75, 'fixed'),    # Same con Fixed
        (500, 15.25, 14.80, 'fixed'),    # Same con Fixed
    ]
    
    print("🧮 IBKR Commission Calculator - Test Cases")
    print("=" * 60)
    
    for quantity, entry_price, exit_price, plan in test_cases:
        total_comm, breakdown = calculator.calculate_round_trip_commission(
            quantity, entry_price, exit_price, plan
        )
        
        trade_value = quantity * entry_price
        commission_pct = (total_comm / trade_value) * 100
        
        print(f"\n📊 {quantity} shares @ ${entry_price} -> ${exit_price} ({plan.upper()})")
        print(f"   Trade Value: ${trade_value:,.2f}")
        print(f"   Total Commission: ${total_comm:.2f} ({commission_pct:.3f}%)")
        print(f"   Entry: ${breakdown['entry_commission']:.2f}")
        print(f"   Exit: ${breakdown['exit_commission']:.2f} (includes fees)")


if __name__ == "__main__":
    main()