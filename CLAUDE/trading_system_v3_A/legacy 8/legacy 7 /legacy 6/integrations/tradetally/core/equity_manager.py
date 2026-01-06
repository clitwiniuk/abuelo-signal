#!/usr/bin/env python3
"""
TradeTally Equity Manager
========================

Sistema para gestionar y actualizar equity automáticamente en TradeTally.

Como TradeTally no tiene endpoint directo para equity, utilizamos diferentes
estrategias para mantener el balance actualizado.
"""

import requests
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from integrations.tradetally.config.tradetally_config import TradeTallyConfig

logger = logging.getLogger(__name__)

class TradeTallyEquityManager:
    """
    Gestor de equity para TradeTally
    """
    
    def __init__(self, config: TradeTallyConfig = None):
        self.config = config or TradeTallyConfig()
        self.base_url = self.config.base_url.replace('/api/v2', '')  # Remove api version
        self.headers = {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json'
        }
    
    def get_current_analytics(self) -> Dict:
        """Obtener analytics actuales de TradeTally"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v2/analytics/overview",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting analytics: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"Error fetching analytics: {e}")
            return {}
    
    def get_equity_curve(self) -> Dict:
        """Obtener curva de equity si está disponible"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v2/analytics/charts?type=equity",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Equity curve not available: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.warning(f"Error fetching equity curve: {e}")
            return {}
    
    def calculate_current_equity(self, starting_balance: float = None) -> float:
        """
        Calcular equity actual basado en analytics
        
        Args:
            starting_balance: Balance inicial (si no se proporciona, se estima)
        
        Returns:
            float: Equity actual estimado
        """
        analytics = self.get_current_analytics()
        
        if not analytics:
            logger.error("No analytics data available")
            return 0.0
        
        # Si no tenemos balance inicial, usar una estimación
        if starting_balance is None:
            starting_balance = self.estimate_starting_balance(analytics)
        
        # Equity = Balance inicial + PnL total - Comisiones - Fees
        total_pnl = analytics.get('totalPnl', 0)
        total_commission = analytics.get('totalCommission', 0)
        total_fees = analytics.get('totalFees', 0)
        
        current_equity = starting_balance + total_pnl - total_commission - total_fees
        
        logger.info(f"Calculated equity: ${current_equity:.2f}")
        logger.info(f"  Starting balance: ${starting_balance:.2f}")
        logger.info(f"  Total PnL: ${total_pnl:.2f}")
        logger.info(f"  Total commission: ${total_commission:.2f}")
        logger.info(f"  Total fees: ${total_fees:.2f}")
        
        return current_equity
    
    def estimate_starting_balance(self, analytics: Dict) -> float:
        """
        Estimar balance inicial basado en analytics
        """
        # Estrategia simple: asumir que empezamos con suficiente capital
        # para el trade más grande + un margen
        largest_win = analytics.get('largestWin', 1000)
        largest_loss = abs(analytics.get('largestLoss', -1000))
        max_trade = max(largest_win, largest_loss)
        
        # Estimar balance inicial como 10x el trade más grande
        estimated_balance = max_trade * 10
        
        # Mínimo razonable para day trading
        estimated_balance = max(estimated_balance, 25000)
        
        logger.info(f"Estimated starting balance: ${estimated_balance:.2f}")
        return estimated_balance
    
    def create_balance_adjustment_trade(self, target_equity: float, current_equity: float, reason: str = "Balance adjustment") -> bool:
        """
        Crear un trade de ajuste para actualizar el balance
        
        Args:
            target_equity: Equity objetivo
            current_equity: Equity actual
            reason: Razón del ajuste
        
        Returns:
            bool: True si el trade se creó exitosamente
        """
        adjustment_amount = target_equity - current_equity
        
        if abs(adjustment_amount) < 1.0:  # No ajustar cantidades menores a $1
            logger.info("No adjustment needed (amount < $1)")
            return True
        
        # Crear trade de ajuste
        adjustment_trade = {
            "symbol": "CASH",
            "side": "long" if adjustment_amount > 0 else "short",
            "entryTime": datetime.now().isoformat(),
            "exitTime": datetime.now().isoformat(),
            "entryPrice": 1.0,
            "exitPrice": 1.0,
            "quantity": 1,
            "pnl": adjustment_amount,
            "commission": 0.0,
            "fees": 0.0,
            "notes": f"{reason} - Automated equity update: ${adjustment_amount:+.2f}",
            "strategy": "Balance Adjustment",
            "setup": "Equity Update",
            "broker": self.config.broker_name,
            "isPublic": False
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v2/trades",
                json=adjustment_trade,
                headers=self.headers
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Balance adjustment trade created: ${adjustment_amount:+.2f}")
                return True
            else:
                logger.error(f"Failed to create adjustment trade: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating adjustment trade: {e}")
            return False
    
    def sync_equity_from_broker(self, broker_equity: float) -> bool:
        """
        Sincronizar equity desde el broker
        
        Args:
            broker_equity: Equity actual del broker
        
        Returns:
            bool: True si se sincronizó exitosamente
        """
        current_equity = self.calculate_current_equity()
        
        if current_equity == 0:
            logger.error("Cannot calculate current equity")
            return False
        
        difference = broker_equity - current_equity
        
        if abs(difference) < 10.0:  # Tolerancia de $10
            logger.info(f"Equity already in sync (difference: ${difference:.2f})")
            return True
        
        logger.info(f"Syncing equity: TradeTally ${current_equity:.2f} -> Broker ${broker_equity:.2f}")
        
        return self.create_balance_adjustment_trade(
            target_equity=broker_equity,
            current_equity=current_equity,
            reason="Broker sync"
        )
    
    def auto_update_equity(self, force_update: bool = False) -> Dict:
        """
        Actualización automática de equity
        
        Args:
            force_update: Forzar actualización incluso si no es necesaria
        
        Returns:
            Dict: Resultado de la actualización
        """
        result = {
            'success': False,
            'current_equity': 0,
            'analytics': {},
            'action_taken': 'none',
            'message': ''
        }
        
        try:
            # Obtener analytics actuales
            analytics = self.get_current_analytics()
            if not analytics:
                result['message'] = "Could not fetch analytics"
                return result
            
            result['analytics'] = analytics
            
            # Calcular equity actual
            current_equity = self.calculate_current_equity()
            result['current_equity'] = current_equity
            
            # En modo automático, simplemente reportamos el estado
            # El equity se mantiene automáticamente via trades
            result['success'] = True
            result['action_taken'] = 'calculated'
            result['message'] = f"Current equity: ${current_equity:.2f} (calculated from trades)"
            
            return result
            
        except Exception as e:
            logger.error(f"Error in auto_update_equity: {e}")
            result['message'] = f"Error: {e}"
            return result
    
    def get_equity_status(self) -> Dict:
        """Obtener estado completo del equity"""
        analytics = self.get_current_analytics()
        equity_curve = self.get_equity_curve()
        current_equity = self.calculate_current_equity()
        
        return {
            'current_equity': current_equity,
            'total_pnl': analytics.get('totalPnl', 0),
            'total_trades': analytics.get('totalTrades', 0),
            'win_rate': analytics.get('winRate', 0),
            'total_commission': analytics.get('totalCommission', 0),
            'total_fees': analytics.get('totalFees', 0),
            'max_drawdown': analytics.get('maxDrawdown', 0),
            'has_equity_curve': bool(equity_curve),
            'last_updated': datetime.now().isoformat()
        }


def main():
    """Test del equity manager"""
    print("🏦 TRADETALLY EQUITY MANAGER TEST")
    print("=" * 50)
    
    manager = TradeTallyEquityManager()
    
    # Test 1: Get current status
    print("📊 Getting equity status...")
    status = manager.get_equity_status()
    
    print(f"Current equity: ${status['current_equity']:.2f}")
    print(f"Total PnL: ${status['total_pnl']:.2f}")
    print(f"Total trades: {status['total_trades']}")
    print(f"Win rate: {status['win_rate']:.1f}%")
    
    # Test 2: Auto update
    print("\n🔄 Running auto update...")
    result = manager.auto_update_equity()
    
    if result['success']:
        print(f"✅ {result['message']}")
    else:
        print(f"❌ {result['message']}")
    
    print("\n🎉 Equity manager test completed!")


if __name__ == "__main__":
    main()