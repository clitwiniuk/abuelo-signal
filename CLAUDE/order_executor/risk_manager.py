"""
Módulo de gestión de riesgo para el sistema de trading
Proporciona validaciones de riesgo para las operaciones
"""

import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from datetime import datetime, time

# Configuración de precisión decimal
getcontext().prec = 8

logger = logging.getLogger(__name__)

@dataclass
class RiskParameters:
    """Parámetros de riesgo configurables"""
    max_position_size_pct: float = 5.0  # % máximo del capital por posición
    max_strategy_risk_pct: float = 15.0  # % máximo del capital por estrategia
    max_daily_loss_pct: float = 5.0  # % máximo de pérdida diaria
    max_drawdown_pct: float = 20.0  # Drawdown máximo permitido
    max_leverage: float = 4.0  # Apalancamiento máximo
    max_orders_per_day: int = 50  # Máximo de operaciones por día
    allowed_trading_hours: List[Tuple[time, time]] = field(
        default_factory=lambda: [
            (time(9, 30), time(16, 0))  # Horario de negociación por defecto
        ]
    )
    blacklist: List[str] = field(default_factory=list)  # Símbolos bloqueados

class RiskManager:
    """
    Gestiona el riesgo de las operaciones de trading
    """
    
    def __init__(self, account_value: float, risk_params: Optional[RiskParameters] = None):
        """
        Inicializa el gestor de riesgo
        
        Args:
            account_value: Valor total de la cuenta
            risk_params: Parámetros de riesgo personalizados
        """
        self.account_value = Decimal(str(account_value))
        self.risk_params = risk_params or RiskParameters()
        self.daily_trades = 0
        self.daily_pnl = Decimal('0')
        self.max_daily_loss = self.account_value * Decimal(str(self.risk_params.max_daily_loss_pct / 100))
        self.positions = {}  # ticker -> posición info
        self.strategy_exposure = {}  # strategy_id -> exposición
        
        # Registrar inicio
        logger.info(f"Risk Manager inicializado con cuenta de ${account_value:,.2f}")
    
    def validate_order(
        self, 
        ticker: str, 
        quantity: int, 
        price: float, 
        action: str,
        strategy_id: str
    ) -> Tuple[bool, str]:
        """
        Valida una orden contra las reglas de riesgo
        
        Args:
            ticker: Símbolo a operar
            quantity: Cantidad de acciones/contratos
            price: Precio de entrada
            action: 'BUY' o 'SELL'
            strategy_id: ID de la estrategia
            
        Returns:
            tuple: (es_válida, razón)
        """
        try:
            # Convertir a Decimal para precisión
            qty = Decimal(str(quantity))
            px = Decimal(str(price))
            
            # 1. Validar símbolo
            if ticker.upper() in [s.upper() for s in self.risk_params.blacklist]:
                return False, f"{ticker} está en la lista negra"
            
            # 2. Validar horario de negociación
            if not self._is_trading_hour():
                return False, "Fuera del horario de negociación"
            
            # 3. Validar tamaño de posición
            position_value = qty * px
            max_position_value = self.account_value * Decimal(str(self.risk_params.max_position_size_pct / 100))
            
            if position_value > max_position_value:
                return False, (
                    f"Tamaño de posición (${position_value:,.2f}) excede el máximo "
                    f"permitido (${max_position_value:,.2f} - {self.risk_params.max_position_size_pct}% de la cuenta)"
                )
            
            # 4. Validar exposición por estrategia
            strategy_exposure = self.strategy_exposure.get(strategy_id, Decimal('0'))
            max_strategy_exposure = self.account_value * Decimal(str(self.risk_params.max_strategy_risk_pct / 100))
            
            if action.upper() == 'BUY' and (strategy_exposure + position_value) > max_strategy_exposure:
                return False, (
                    f"Exposición de estrategia (${strategy_exposure + position_value:,.2f}) excede el máximo "
                    f"permitido (${max_strategy_exposure:,.2f} - {self.risk_params.max_strategy_risk_pct}% de la cuenta)"
                )
            
            # 5. Validar pérdida diaria
            if self.daily_pnl < -self.max_daily_loss:
                return False, (
                    f"Pérdida diaria (${abs(self.daily_pnl):,.2f}) excede el máximo "
                    f"permitido (${self.max_daily_loss:,.2f} - {self.risk_params.max_daily_loss_pct}% de la cuenta)"
                )
            
            # 6. Validar apalancamiento
            total_exposure = sum(pos['value'] for pos in self.positions.values() if pos['value'] > 0)
            leverage = (total_exposure + (position_value if action.upper() == 'BUY' else 0)) / self.account_value
            
            if leverage > self.risk_params.max_leverage:
                return False, (
                    f"Apalancamiento ({leverage:.2f}x) excede el máximo permitido "
                    f"({self.risk_params.max_leverage}x)"
                )
            
            # 7. Validar límite de operaciones diarias
            if self.daily_trades >= self.risk_params.max_orders_per_day:
                return False, (
                    f"Límite de operaciones diarias alcanzado ({self.risk_params.max_orders_per_day})"
                )
            
            return True, "Validación de riesgo exitosa"
            
        except Exception as e:
            logger.error(f"Error en validación de riesgo: {e}")
            return False, f"Error en validación de riesgo: {str(e)}"
    
    def update_position(
        self, 
        ticker: str, 
        quantity: int, 
        price: float, 
        action: str,
        strategy_id: str
    ) -> None:
        """
        Actualiza el estado de las posiciones después de una operación
        """
        try:
            ticker = ticker.upper()
            qty = Decimal(str(quantity))
            px = Decimal(str(price))
            
            # Actualizar contador de operaciones
            self.daily_trades += 1
            
            # Actualizar exposición por estrategia
            position_value = qty * px
            if action.upper() == 'BUY':
                self.strategy_exposure[strategy_id] = self.strategy_exposure.get(strategy_id, Decimal('0')) + position_value
            else:
                self.strategy_exposure[strategy_id] = self.strategy_exposure.get(strategy_id, Decimal('0')) - position_value
                # No permitir exposición negativa
                if self.strategy_exposure[strategy_id] < 0:
                    self.strategy_exposure[strategy_id] = Decimal('0')
            
            # Actualizar posición
            if ticker not in self.positions:
                self.positions[ticker] = {
                    'quantity': Decimal('0'),
                    'avg_price': Decimal('0'),
                    'value': Decimal('0')
                }
            
            pos = self.positions[ticker]
            
            if action.upper() == 'BUY':
                new_qty = pos['quantity'] + qty
                if new_qty > 0:
                    pos['avg_price'] = (
                        (pos['quantity'] * pos['avg_price']) + (qty * px)
                    ) / new_qty
                pos['quantity'] = new_qty
            else:
                pos['quantity'] -= qty
                if pos['quantity'] <= 0:
                    pos['quantity'] = Decimal('0')
                    pos['avg_price'] = Decimal('0')
            
            pos['value'] = pos['quantity'] * (px if pos['quantity'] > 0 else pos['avg_price'])
            
            # Limpiar posición si es necesario
            if pos['quantity'] == 0:
                del self.positions[ticker]
                
        except Exception as e:
            logger.error(f"Error al actualizar posición: {e}")
    
    def update_pnl(self, pnl_delta: float) -> None:
        """Actualiza el P&L diario"""
        self.daily_pnl += Decimal(str(pnl_delta))
    
    def reset_daily_stats(self) -> None:
        """Reinicia las estadísticas diarias"""
        self.daily_trades = 0
        self.daily_pnl = Decimal('0')
        logger.info("Estadísticas diarias reiniciadas")
    
    def _is_trading_hour(self) -> bool:
        """Verifica si es horario de negociación"""
        now = datetime.now().time()
        return any(start <= now <= end for start, end in self.risk_params.allowed_trading_hours)
    
    def get_risk_summary(self) -> Dict:
        """Devuelve un resumen del estado de riesgo actual"""
        total_exposure = sum(pos['value'] for pos in self.positions.values())
        
        return {
            'account_value': float(self.account_value),
            'daily_pnl': float(self.daily_pnl),
            'daily_trades': self.daily_trades,
            'max_daily_loss': float(self.max_daily_loss),
            'total_exposure': float(total_exposure),
            'leverage': float(total_exposure / self.account_value if self.account_value > 0 else 0),
            'strategy_exposure': {k: float(v) for k, v in self.strategy_exposure.items()},
            'positions': {
                ticker: {
                    'quantity': float(pos['quantity']),
                    'avg_price': float(pos['avg_price']),
                    'value': float(pos['value'])
                } for ticker, pos in self.positions.items()
            }
        }
