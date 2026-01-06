# config/simulation_config.py
"""
Configuration for simulation and development environment.
Shows how to use MockIBKRAdapter instead of real IBKR connection.
"""

from core.interfaces import TradingConfig
from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.simulation_manager import SimulationManager


class SimulationConfig(TradingConfig):
    """Extended trading config for simulation mode"""
    
    def __init__(self):
        super().__init__()
        
        # Enable simulation mode
        self.simulation_mode = True
        self.debug_mode = False  # Set to True for very permissive risk checks
        
        # Simulation-specific settings
        self.use_mock_broker = True
        self.csv_data_path = "data/csv"
        self.simulation_speed = 1.0  # 1x real-time
        
        # Risk management for simulation (more permissive)
        self.max_positions = 10
        self.max_risk_per_trade = 0.05  # 5% per trade
        self.max_daily_loss = -500.0
        self.max_daily_trades = 50
        self.max_position_value = 2000.0  # $2000 max per position
        self.max_portfolio_exposure = 8000.0  # $8000 total exposure
        self.max_portfolio_concentration = 0.3  # 30% max in one position
        
        # Portfolio settings for simulation
        self.portfolio_capital = 10000.0  # Start with $10k
        
        # Trading hours configuration - SIMULATION MODE
        self.trading_hours_mode = "SIMULATION_MODE"  # Usar modo simulación
        self.market_open_time = "09:30"  # US time
        self.market_close_time = "16:00"  # US time
        # Horarios de simulación en ES (equivalente a 9:30-16:00 ET)
        self.simulation_start_es = "15:30"  # 15:30 ES = 9:30 ET
        self.simulation_end_es = "22:00"   # 22:00 ES = 16:00 ET
        # Extended hours (no usados en simulación)
        self.premarket_start = "04:00"
        self.premarket_end = "09:30"
        self.afterhours_start = "16:00"
        self.afterhours_end = "20:00"
        
        # Load from config.ini if available
        self._load_trading_hours_from_config()
        
        # Strategy settings
        self.strategy_name = "multi_strategy"
        self.timeframe = "1 min"
        
        # Logging
        self.log_level = "INFO"
        self.log_file = "simulation.log"
    
    def _load_trading_hours_from_config(self):
        """Carga la configuración de horarios desde config.ini"""
        try:
            import configparser
            from pathlib import Path
            
            config_path = Path(__file__).parent.parent / "config.ini"
            if config_path.exists():
                config = configparser.ConfigParser()
                config.read(config_path)
                
                if 'TRADING' in config:
                    trading_section = config['TRADING']
                    
                    # Modo de trading - mantener SIMULATION_MODE para simulaciones
                    # No sobrescribir si ya está configurado como SIMULATION_MODE
                    if self.trading_hours_mode != "SIMULATION_MODE":
                        self.trading_hours_mode = trading_section.get('trading_hours_mode', 'SIMULATION_MODE')
                    
                    # Horarios regulares (US market)
                    self.market_open_time = trading_section.get('market_open_time', '09:30')
                    self.market_close_time = trading_section.get('market_close_time', '16:00')
                    
                    # Horarios de simulación (datos ES) - mantener configuración forzada
                    if self.trading_hours_mode == "SIMULATION_MODE":
                        # Mantener horarios configurados: 15:30-22:00 ES
                        pass  # No sobrescribir
                    else:
                        self.simulation_start_es = trading_section.get('simulation_start_es', '15:30')
                        self.simulation_end_es = trading_section.get('simulation_end_es', '22:00')
                    
                    # Horarios extendidos
                    self.premarket_start = trading_section.get('premarket_start', '04:00')
                    self.premarket_end = trading_section.get('premarket_end', '09:30')
                    self.afterhours_start = trading_section.get('afterhours_start', '16:00')
                    self.afterhours_end = trading_section.get('afterhours_end', '20:00')
                    
                    print(f"📊 Modo trading cargado: {self.trading_hours_mode}")
                    if self.trading_hours_mode == "SIMULATION_MODE":
                        print(f"🇪🇸 Simulación: {self.simulation_start_es}-{self.simulation_end_es} ES (= {self.market_open_time}-{self.market_close_time} ET mercado regular)")
                    elif self.trading_hours_mode == "DEMO_MODE":
                        print(f"🇺🇸 Demo/Real: {self.market_open_time}-{self.market_close_time} ET")
                    else:
                        print(f"🕐 Horario extendido habilitado")
                        
        except Exception as e:
            print(f"⚠️ Error cargando config trading hours: {e}")
    
    def is_trading_time(self, timestamp) -> bool:
        """Verifica si un timestamp está en horario de trading permitido
        
        Maneja diferentes modos:
        - SIMULATION_MODE: Datos CSV en ES (10:00-16:00 ES = premarket+regular parcial US)
        - DEMO_MODE: Datos demo/real en ET (9:30-16:00 ET = regular US)
        - EXTENDED_HOURS: Horario extendido completo
        """
        try:
            # Extraer hora y minuto del timestamp
            if hasattr(timestamp, 'hour'):
                hour = timestamp.hour
                minute = timestamp.minute
            else:
                # Fallback para otros formatos
                return True  # Permitir si no podemos determinar
            
            if self.trading_hours_mode == "SIMULATION_MODE":
                # Para datos CSV en horario español: permitir 15:30-22:00 ES
                # Esto equivale exactamente a 9:30-16:00 ET (horario regular de mercado US)
                start_parts = self.simulation_start_es.split(':')
                start_hour = int(start_parts[0])
                start_minute = int(start_parts[1])
                
                end_parts = self.simulation_end_es.split(':')
                end_hour = int(end_parts[0])
                end_minute = int(end_parts[1])
                
                # Convertir tiempo actual a minutos para comparar con precisión
                current_minutes = hour * 60 + minute
                start_minutes = start_hour * 60 + start_minute
                end_minutes = end_hour * 60 + end_minute
                
                if start_minutes <= current_minutes <= end_minutes:
                    return True
                return False
            
            elif self.trading_hours_mode == "DEMO_MODE":
                # Para datos demo/real en horario US: 9:30-16:00 ET
                if hour < 9 or hour > 16:
                    return False
                if hour == 9 and minute < 30:
                    return False
                if hour == 16 and minute > 0:
                    return False
                return True
            
            else:  # EXTENDED_HOURS
                # Horario extendido completo: 4:00-20:00 ET
                if 4 <= hour <= 20:
                    return True
                return False
                
        except Exception:
            # Si hay error, permitir por defecto
            return True


def create_simulation_adapters(config: SimulationConfig):
    """
    Create adapters for simulation environment.
    Returns mock broker and CSV data provider instead of real IBKR.
    FIXED: Use the same broker instance for both direct access and simulation manager.
    """
    
    # Create mock broker
    mock_broker = MockIBKRAdapter(
        data_path=config.csv_data_path,
        simulation_mode=config.simulation_mode
    )
    
    # Create CSV data provider
    csv_provider = CSVDataProvider(
        data_path=config.csv_data_path,
        auto_load=True
    )
    
    # Create simulation manager
    sim_manager = SimulationManager(
        config=config,
        data_path=config.csv_data_path
    )
    
    # CRITICAL FIX: Replace the simulation manager's broker with our broker
    # This ensures there's only ONE instance
    sim_manager.mock_broker = mock_broker
    
    return {
        'broker': mock_broker,
        'data_provider': csv_provider,
        'simulation_manager': sim_manager
    }


def get_development_symbols():
    """Get list of symbols for development/testing"""
    return [
        # Large caps for stable testing
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',
        
        # ETFs for diversification testing
        'SPY', 'QQQ', 'IWM',
        
        # Some small caps for smallcap strategy testing
        'PLTR', 'BB', 'AMC', 'GME', 'MVIS'
    ]


def setup_simulation_environment():
    """
    Complete setup for simulation environment.
    Use this instead of real IBKR setup during development.
    """
    
    # Create configuration
    config = SimulationConfig()
    
    # Create adapters
    adapters = create_simulation_adapters(config)
    
    # Return everything needed for simulation
    return {
        'config': config,
        'broker': adapters['broker'],
        'data_provider': adapters['data_provider'],
        'simulation_manager': adapters['simulation_manager'],
        'symbols': get_development_symbols()
    }


# Example usage in main trading engine
"""
# Instead of using real IBKR adapter:
# from adapters.thread_safe_ibkr_adapter import ThreadSafeIBKRAdapter
# broker = ThreadSafeIBKRAdapter(host="127.0.0.1", port=7497, client_id=1)

# Use simulation setup:
sim_env = setup_simulation_environment()
broker = sim_env['broker']
data_provider = sim_env['data_provider']
config = sim_env['config']
simulation_manager = sim_env['simulation_manager']

# Initialize simulation
await simulation_manager.initialize(create_sample_data=True)

# Now use broker and data_provider as normal - they implement the same interfaces!
"""