# Trader Optimization Templates

# BATCH_PRICE_MANAGER

class BatchPriceManager:
    """Maneja suscripciones de precios en batch para todas las posiciones"""
    
    def __init__(self, ibkr_adapter):
        self.ibkr = ibkr_adapter
        self.active_subscriptions = {}
        self.price_callbacks = {}
        self.last_prices = {}
    
    async def subscribe_to_positions(self, symbols: List[str]):
        """Suscribirse a precios de múltiples posiciones"""
        for symbol in symbols:
            if symbol not in self.active_subscriptions:
                contract = await self.ibkr._get_contract(symbol)
                ticker = self.ibkr.ib.reqMktData(contract, '', False, False)
                
                # Set up callback for price updates
                ticker.updateEvent += self._on_price_update
                self.active_subscriptions[symbol] = ticker
                
    def _on_price_update(self, ticker):
        """Callback para updates de precio"""
        symbol = ticker.contract.symbol
        if ticker.marketPrice():
            self.last_prices[symbol] = float(ticker.marketPrice())
        
    def get_current_price(self, symbol: str) -> float:
        """Get precio actual desde cache (no API call)"""
        return self.last_prices.get(symbol, 0.0)
    
    async def cleanup(self):
        """Cancelar todas las suscripciones"""
        for symbol, ticker in self.active_subscriptions.items():
            self.ibkr.ib.cancelMktData(ticker.contract)
        self.active_subscriptions.clear()
            

# SMART_POSITION_CACHE

class SmartPositionCache:
    """Cache inteligente para posiciones con event-driven invalidation"""
    
    def __init__(self, ibkr_adapter):
        self.ibkr = ibkr_adapter
        self.cached_positions = {}
        self.last_update = None
        self.cache_ttl = 300  # 5 minutos
        self.pending_orders = set()
    
    async def get_positions(self) -> Dict[str, Position]:
        """Get posiciones con smart caching"""
        current_time = datetime.now()
        
        # Check si cache es válido
        if (self.last_update and 
            (current_time - self.last_update).total_seconds() < self.cache_ttl and
            not self.pending_orders):  # Si no hay órdenes pendientes
            return self.cached_positions
        
        # Refresh positions desde IBKR
        positions = await self._fetch_positions_from_ibkr()
        self.cached_positions = positions
        self.last_update = current_time
        self.pending_orders.clear()
        
        return positions
    
    def invalidate_on_order_fill(self, symbol: str):
        """Invalidar cache cuando hay order fill"""
        self.pending_orders.add(symbol)
    
    async def _fetch_positions_from_ibkr(self) -> Dict[str, Position]:
        """Fetch real positions from IBKR (actual API calls)"""
        # Original get_positions logic here
        pass
            

# ADAPTIVE_MONITORING

class AdaptiveMonitoringManager:
    """Ajusta frequency de monitoring basado en market conditions"""
    
    def __init__(self):
        self.monitoring_intervals = {
            'market_open': 30,      # 30 segundos durante market open
            'normal_hours': 60,     # 1 minuto durante horas normales  
            'lunch_time': 180,      # 3 minutos durante lunch
            'power_hour': 20,       # 20 segundos durante power hour
            'after_hours': 300      # 5 minutos after hours
        }
        
    def get_optimal_interval(self) -> int:
        """Get intervalo óptimo basado en hora actual"""
        current_hour = datetime.now().hour
        
        if 9 <= current_hour < 11:      # Market open
            return self.monitoring_intervals['market_open']
        elif 12 <= current_hour < 14:   # Lunch time
            return self.monitoring_intervals['lunch_time']
        elif 15 <= current_hour < 16:   # Power hour
            return self.monitoring_intervals['power_hour']
        elif 16 <= current_hour < 20:   # After hours
            return self.monitoring_intervals['after_hours']
        else:
            return self.monitoring_intervals['normal_hours']
            

