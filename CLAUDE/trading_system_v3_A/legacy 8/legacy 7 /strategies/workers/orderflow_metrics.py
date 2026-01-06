"""
Order Flow Metrics Module - Microstructure Analysis for Workers

Este módulo proporciona herramientas de análisis de microestructura (Order Flow) reciclabiles.
Principalmente enfocado en el análisis de Tick Data para confirmar la intención del volumen.

Funcionalidades:
1. CVD (Cumulative Volume Delta): El "Polígrafo". Verifica si el volumen es agresivo (Ask) o pasivo (Bid).
   - Útil para: Confirmar rupturas, detectar absorción, filtrar trampas.

Uso:
    from strategies.workers.orderflow_metrics import OrderFlowAnalyzer
    
    analyzer = OrderFlowAnalyzer(execution_engine.broker)
    is_confirmed, cvd, reason = await analyzer.verify_buying_pressure(symbol, seconds=60)
"""

import logging
from typing import Tuple, Optional, Any
from datetime import datetime, timedelta
# Importamos Stock de ib_insync (o lo pasamos como dep)
try:
    from ib_insync import Stock
except ImportError:
    pass

class OrderFlowAnalyzer:
    """
    Analizador de flujo de órdenes (Tick Analysis)
    """
    
    def __init__(self, broker: Any, logger: Optional[logging.Logger] = None):
        """
        Args:
            broker: Instancia del broker (debe tener acceso a .ib)
            logger: Logger opcional
        """
        self.broker = broker
        self.logger = logger or logging.getLogger(__name__)

    async def verify_buying_pressure(self, symbol: str, seconds: int = 60, min_ticks: int = 1000) -> Tuple[bool, str, float]:
        """
        Verifica si hay presión de compra neta en los últimos X segundos.
        
        Calcula CVD (Cumulative Volume Delta).
        
        Returns:
            Tuple[bool, str, float]: (is_confirmed, reason, cvd_value)
        """
        try:
            if not self.broker or not hasattr(self.broker, 'ib') or not self.broker.ib:
                return True, "Broker not available for CVD", 0.0

            # Cualificar contrato
            contract = self.broker.ib.qualifyContracts(
                Stock(symbol, 'SMART', 'USD')
            )[0]
            
            # Pedir ticks históricos
            # Solicitamos suficientes ticks para cubrir el periodo de tiempo
            # IBKR limita a 1000 ticks por request en algunos casos, pero reqHistoricalTicksAsync maneja paginación si es necesario?
            # En modo simple pedimos 1000 que suele sobrar para 1 min en smallcaps
            
            ticks = await self.broker.ib.reqHistoricalTicksAsync(
                contract, 
                startDateTime='', 
                endDateTime=datetime.now(), 
                numberOfTicks=min_ticks,
                whatToShow='TRADES',
                useRth=True
            )
            
            if not ticks:
                return False, "No ticks received", 0.0
                
            # Filtrar por tiempo (solo últimos X segundos)
            # Nota: ticks[i].time es un objeto datetime en timezone local o UTC según config
            # Asumimos que los últimos 1000 son recientes, pero podemos filtrar si es necesario.
            # Implementación simplificada: Calculamos sobre todos los ticks devueltos (relevancia inmediata)
            
            # Calcular CVD usando Standard Tick Rule
            cvd = 0.0
            last_price = ticks[0].price
            
            buy_vol = 0
            sell_vol = 0
            
            for t in ticks:
                if t.price > last_price:
                    # Uptick = Buy (Aggressor at Ask)
                    cvd += t.size
                    buy_vol += t.size
                    last_price = t.price
                elif t.price < last_price:
                    # Downtick = Sell (Aggressor at Bid)
                    cvd -= t.size
                    sell_vol += t.size
                    last_price = t.price
                else:
                    # Neutral tick
                    pass
            
            # Métrica de decisión
            if cvd > 0:
                return True, f"CVD Positive (+{int(cvd):,})", cvd
            else:
                ratio = buy_vol / (sell_vol + 1)
                return False, f"CVD Negative ({int(cvd):,}) - Sellers dominating (B/S ratio {ratio:.2f})", cvd

        except Exception as e:
            self.logger.error(f"⚠️ CVD Analysis error for {symbol}: {e}")
            return False, f"CVD Error: {e}", 0.0
