# backtest_config.py
"""
Configuration file for backtesting system.
Configuraciones predefinidas optimizadas para datos de 1 minuto y sesión completa.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
from backtesting.backtest_engine import BacktestConfig


class BacktestConfigurations:
    """Configuraciones predefinidas de backtest para diferentes escenarios"""
    
    @staticmethod
    def get_default_1min_config() -> BacktestConfig:
        """Configuración por defecto optimizada para datos de 1 minuto"""
        # Usar datos recientes (últimos 3 meses) para trading intradía
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # 3 meses de datos
        
        return BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000.0,
            commission_per_trade=1.0,
            commission_pct=0.001,  # 0.1%
            slippage_pct=0.001,    # 0.1%
            max_positions=3,
            risk_per_trade=0.02,   # 2%
            data_frequency="1min"  # Base de 1 minuto
        )
    
    @staticmethod
    def get_default_5min_config() -> BacktestConfig:
        """Configuración por defecto para datos de 5 minutos (convertidos desde 1min)"""
        # Usar datos recientes (últimos 3 meses) para trading intradía
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # 3 meses de datos
        
        return BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000.0,
            commission_per_trade=1.0,
            commission_pct=0.001,
            slippage_pct=0.001,
            max_positions=3,
            risk_per_trade=0.02,
            data_frequency="5min"
        )
    
    @staticmethod
    def get_fast_test_config() -> BacktestConfig:
        """Configuración para pruebas rápidas (período muy corto)"""
        # Usar datos muy recientes (últimas 2 semanas) para pruebas rápidas
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)  # 2 semanas de datos
        
        return BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000.0,
            commission_per_trade=1.0,
            commission_pct=0.001,
            slippage_pct=0.001,
            max_positions=3,
            risk_per_trade=0.02,
            data_frequency="5min"
        )
    
    @staticmethod
    def get_optimization_config() -> BacktestConfig:
        """Configuración optimizada para optimización de parámetros"""
        return BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 6, 30),
            initial_capital=10000.0,
            commission_per_trade=1.0,
            commission_pct=0.001,
            slippage_pct=0.001,
            max_positions=3,
            risk_per_trade=0.02,
            data_frequency="5min"
        )
    
    @staticmethod
    def get_low_commission_config() -> BacktestConfig:
        """Configuración con comisiones bajas para estrategias de alta frecuencia"""
        return BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_capital=10000.0,
            commission_per_trade=0.5,   # Comisión fija menor
            commission_pct=0.0005,      # Comisión porcentual menor
            slippage_pct=0.0005,        # Menor slippage
            max_positions=5,            # Más posiciones permitidas
            risk_per_trade=0.015,       # Menor riesgo por trade
            data_frequency="1min"
        )
    
    @staticmethod
    def get_high_frequency_config() -> BacktestConfig:
        """Configuración para estrategias de alta frecuencia (1min base)"""
        return BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 3, 31),  # Período más corto
            initial_capital=25000.0,         # Mayor capital
            commission_per_trade=0.25,       # Comisiones muy bajas
            commission_pct=0.0002,           # 0.02%
            slippage_pct=0.0002,            # Menor slippage
            max_positions=8,                 # Más posiciones
            risk_per_trade=0.01,            # Menor riesgo
            data_frequency="1min"
        )


class StrategyConfigurations:
    """Configuraciones predefinidas de parámetros de estrategias"""
    
    @staticmethod
    def get_macdv_1min_optimized() -> Dict[str, Any]:
        """Parámetros MACDV optimizados para datos de 1min (convertidos a timeframes superiores)"""
        return {
            # MACD parameters (adaptados para conversión)
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            
            # Volume parameters
            'volume_period': 20,
            'volume_threshold': 1.5,
            
            # Moving averages
            'ma_short': 10,
            'ma_long': 21,
            
            # RSI parameters
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            
            # ADX parameters
            'adx_period': 14,
            'adx_threshold': 25,
            
            # Bollinger Bands
            'bb_period': 20,
            'bb_std': 2.0,
            
            # Risk management (optimizado para intraday)
            'stop_loss_pct': 0.03,
            'take_profit_pct': 0.06,
            'max_hold_hours': 4,  # Máximo 4 horas para intraday
            
            # Position sizing
            'max_position_value': 1000.0,
            'min_quantity': 1,
            
            # Entry conditions
            'min_conditions': 4,
            
            # History
            'max_history_bars': 200
        }
    
    @staticmethod
    def get_macdv_default_5min() -> Dict[str, Any]:
        """Parámetros MACDV por defecto para 5 minutos"""
        return {
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'volume_period': 20,
            'volume_threshold': 1.5,
            'ma_short': 10,
            'ma_long': 21,
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'adx_period': 14,
            'adx_threshold': 25,
            'bb_period': 20,
            'bb_std': 2.0,
            'stop_loss_pct': 0.03,
            'take_profit_pct': 0.06,
            'max_hold_hours': 4,
            'max_position_value': 1000.0,
            'min_quantity': 1,
            'min_conditions': 4,
            'max_history_bars': 200
        }
        
    @staticmethod
    def get_macdv_default_10min() -> Dict[str, Any]:
        """Parámetros MACDV optimizados para 10 minutos"""
        return {
            'macd_fast': 6,          # Ajustado para timeframe de 10min
            'macd_slow': 14,         # Reducido para capturar tendencias medias
            'macd_signal': 4,        # Señal más rápida
            'volume_period': 15,     # Período de volumen ajustado
            'volume_threshold': 1.2,  # Umbral de volumen más bajo
            'ma_short': 5,           # Media corta más reactiva
            'ma_long': 13,           # Media larga ajustada (Fibonacci)
            'rsi_period': 9,         # RSI más sensible
            'rsi_oversold': 35,      # Niveles ajustados
            'rsi_overbought': 65,
            'adx_period': 12,        # ADX más sensible
            'adx_threshold': 18,     # Umbral ADX más bajo
            'bb_period': 18,         # Bandas de Bollinger ajustadas
            'bb_std': 1.8,           # Bandas más ajustadas
            'stop_loss_pct': 0.035,  # Stop loss ligeramente más amplio
            'take_profit_pct': 0.07, # Take profit ajustado
            'max_hold_hours': 6,     # Más tiempo de retención
            'max_position_value': 1000.0,
            'min_quantity': 1,
            'min_conditions': 4,     # Mínimo de condiciones requeridas
            'max_history_bars': 150,  # Menos barras de historial necesarias
            'min_trade_duration': 3,  # Mínimo 30 minutos por operación
            'max_trade_duration': 24  # Máximo 4 horas por operación
        }
    
    @staticmethod
    def get_macdv_premarket() -> Dict[str, Any]:
        """Parámetros MACDV específicos para premarket (4:00-9:30 ET)"""
        params = StrategyConfigurations.get_macdv_1min_optimized()
        params.update({
            'stop_loss_pct': 0.02,          # Stop loss más ajustado para premarket
            'take_profit_pct': 0.04,        # Take profit más conservador
            'volume_threshold': 2.0,        # Mayor volumen requerido
            'max_hold_hours': 2,            # Salir antes de la apertura
            'min_conditions': 5,            # Más condiciones para mayor seguridad
        })
        return params
    
    @staticmethod
    def get_macdv_regular() -> Dict[str, Any]:
        """Parámetros MACDV para sesión regular (9:30-16:00 ET)"""
        params = StrategyConfigurations.get_macdv_1min_optimized()
        params.update({
            'stop_loss_pct': 0.03,
            'take_profit_pct': 0.06,
            'volume_threshold': 1.5,
            'max_hold_hours': 4,
            'min_conditions': 4,
        })
        return params
    
    @staticmethod
    def get_macdv_afterhours() -> Dict[str, Any]:
        """Parámetros MACDV para afterhours (16:00-20:00 ET)"""
        params = StrategyConfigurations.get_macdv_1min_optimized()
        params.update({
            'stop_loss_pct': 0.04,          # Stop loss más amplio para afterhours
            'take_profit_pct': 0.08,        # Take profit más ambicioso
            'volume_threshold': 2.0,         # Requiere más volumen por la menor liquidez
            'min_conditions': 5,             # Necesita más confirmaciones
            'max_hold_hours': 2              # Menor tiempo de retención
        })
        return params
        
    @staticmethod
    def get_gap_go_params() -> Dict[str, Any]:
        """Parámetros para la estrategia Gap & Go"""
        return {
            'gap_percent_threshold': 1.0,     # Mínimo gap porcentual para considerar
            'min_volume_ratio': 1.5,          # Ratio de volumen mínimo respecto al promedio
            'max_hold_time': 240,             # Tiempo máximo de retención en minutos
            'stop_loss_pct': 0.02,            # Stop loss del 2%
            'take_profit_pct': 0.04,          # Take profit del 4%
            'max_position_value': 2000.0,      # Valor máximo por posición
            'min_position_value': 100.0,       # Valor mínimo por posición
            'max_risk_per_trade': 0.02,        # Riesgo máximo por operación (2%)
            'min_quantity': 1                  # Cantidad mínima de acciones
        }
        
    @staticmethod
    def get_optimized_gap_go_params() -> Dict[str, Any]:
        """Parámetros optimizados para la estrategia Gap & Go"""
        return {
            'gap_percent_threshold': 0.8,      # Mínimo gap porcentual para considerar
            'min_volume_ratio': 1.8,           # Ratio de volumen mínimo más alto
            'max_hold_time': 180,              # Tiempo máximo de retención más corto
            'stop_loss_pct': 0.015,            # Stop loss más ajustado
            'take_profit_pct': 0.06,           # Take profit más ambicioso
            'trailing_stop_activation': 0.02,  # Activación del trailing stop
            'trailing_stop_distance': 0.01,    # Distancia del trailing stop
            'max_position_value': 1500.0,      # Valor máximo por posición
            'min_position_value': 150.0,       # Valor mínimo por posición
            'max_risk_per_trade': 0.015,       # Riesgo por operación más bajo
            'min_quantity': 1,                 # Cantidad mínima de acciones
            'breakout_buffer': 0.01,           # Buffer para confirmación de breakout
            'gap_fill_buffer': 0.02            # Buffer para confirmación de gap fill
        }
    
    @staticmethod
    def get_macdv_conservative() -> Dict[str, Any]:
        """Parámetros MACDV conservadores (menor riesgo, condiciones más estrictas)"""
        params = StrategyConfigurations.get_macdv_1min_optimized()
        params.update({
            'stop_loss_pct': 0.02,          # Stop loss más ajustado
            'take_profit_pct': 0.04,        # Take profit menor
            'min_conditions': 5,            # Más condiciones requeridas
            'volume_threshold': 2.0,        # Mayor volumen
            'max_hold_hours': 2,            # Holding más corto
            'max_position_value': 500.0     # Posiciones más pequeñas
        })
        return params
    
    @staticmethod
    def get_macdv_aggressive() -> Dict[str, Any]:
        """Parámetros MACDV agresivos (mayor riesgo, condiciones más flexibles)"""
        params = StrategyConfigurations.get_macdv_1min_optimized()
        params.update({
            'stop_loss_pct': 0.05,          # Stop loss más amplio
            'take_profit_pct': 0.10,        # Take profit mayor
            'min_conditions': 3,            # Menos condiciones
            'volume_threshold': 1.2,        # Menor volumen requerido
            'max_hold_hours': 8,            # Holding más largo
            'max_position_value': 2000.0    # Posiciones más grandes
        })
        return params
    
    @staticmethod
    def get_macdv_scalping() -> Dict[str, Any]:
        """Parámetros MACDV para scalping (muy corto plazo)"""
        params = StrategyConfigurations.get_macdv_1min_optimized()
        params.update({
            'macd_fast': 8,                 # MACD más rápido
            'macd_slow': 21,
            'stop_loss_pct': 0.015,         # Stop loss muy ajustado
            'take_profit_pct': 0.03,        # Take profit rápido
            'max_hold_hours': 1,            # Máximo 1 hora
            'min_conditions': 3,            # Menos condiciones para más señales
            'ma_short': 5,                  # MAs más cortas
            'ma_long': 13
        })
        return params
        
    @staticmethod
    def get_orb_params() -> Dict[str, Any]:
        """Parámetros para la estrategia Opening Range Breakout (ORB)"""
        return {
            # Opening range parameters
            'opening_range_minutes': 15,     # Rango de apertura de 15 minutos
            'range_min_size': 0.03,          # Tamaño mínimo del rango (3%)
            'range_max_size': 0.12,          # Tamaño máximo del rango (12%)
            
            # Volume parameters
            'volume_spike_threshold': 3.5,   # Umbral de volumen para entrada (3.5x promedio)
            'volume_confirmation_threshold': 2.5,  # Confirmación de volumen (2.5x)
            'volume_period': 20,             # Período para cálculo de volumen promedio
            
            # Price filters
            'min_price': 1.00,               # Precio mínimo
            'max_price': 15.00,              # Precio máximo
            'min_dollar_volume': 200000,     # Volumen en dólares mínimo
            
            # Breakout confirmation
            'breakout_min_size': 0.01,       # Tamaño mínimo de breakout (1%)
            'consolidation_bars': 2,         # Barras de consolidación requeridas
            
            # Risk management
            'stop_loss_pct': 0.07,           # Stop loss del 7%
            'profit_target': 0.20,           # Objetivo de beneficio del 20%
            'trailing_stop_activation': 0.10, # Activar trailing stop al 10%
            'trailing_stop_distance': 0.05,   # Distancia del trailing stop (5%)
            
            # Position sizing
            'max_position_value': 2000.0,     # Valor máximo por posición
            'min_position_value': 500.0,      # Valor mínimo por posición
            'risk_per_trade': 0.01,           # Riesgo por operación (1%)
            'min_quantity': 100,              # Cantidad mínima de acciones
            'commission_per_share': 0.01,     # Comisión por acción
            'min_commission': 1.0,            # Comisión mínima por operación
            
            # Additional filters
            'max_gap_size': 0.15,             # Tamaño máximo de gap (15%)
            'min_conditions': 5,               # Mínimo de condiciones requeridas
            
            # History requirements
            'max_history_bars': 100            # Barras de historial máximas
        }
        
    @staticmethod
    def get_volume_momentum_params() -> Dict[str, Any]:
        """Parámetros para la estrategia Volume Momentum"""
        return {
            # Volume analysis
            'volume_surge_multiplier': 2.5,    # Multiplicador de volumen (2.5x promedio)
            'volume_lookback_hours': 8,        # Horas de análisis de volumen
            'volume_timeframe_minutes': 30,    # Timeframe para análisis de volumen
            'min_absolute_volume': 750000,     # Volumen mínimo absoluto
            'float_rotation_threshold': 0.15,  # Umbral de rotación de flotante
            
            # Price and market cap filters
            'min_price': 1.5,                  # Precio mínimo
            'max_price': 20.0,                 # Precio máximo
            'max_market_cap': 750000000,       # Capitalización de mercado máxima
            'max_spread_pct': 0.4,             # Spread máximo permitido
            'min_daily_volume': 1500000,       # Volumen diario mínimo
            
            # VWAP parameters
            'vwap_period': 15,                 # Período VWAP
            'vwap_deviation_threshold': 0.008,  # Umbral de desviación VWAP
        }
        
    @staticmethod
    def get_volume_breakout_params():
        """Parámetros para la estrategia Volume Breakout"""
        return {
            # Parámetros de detección de breakout
            'volume_threshold': 2.5,        # Multiplicador sobre volumen promedio
            'price_threshold': 0.015,       # Cambio mínimo de precio (1.5%)
            'lookback_period': 20,          # Período para calcular volumen promedio
            'consolidation_bars': 5,        # Barras de consolidación antes del breakout
            'max_consolidation_range': 0.03, # Rango máximo durante consolidación (3%)
            
            # Filtros técnicos
            'min_price': 1.0,               # Precio mínimo para operar
            'max_price': 20.0,              # Precio máximo para operar
            'min_avg_volume': 100000,       # Volumen promedio mínimo
            'rsi_period': 14,               # Período RSI
            'rsi_threshold': 50,            # Nivel RSI para confirmar dirección
            'use_vwap_filter': True,        # Usar VWAP como filtro
            
            # Gestión de riesgo
            'stop_loss_pct': 0.04,          # Stop loss (4%)
            'take_profit_pct': 0.12,        # Take profit (12%)
            'trailing_stop_pct': 0.03,      # Trailing stop (3%)
            'max_bars_held': 60,            # Máximo de barras a mantener posición
            'risk_per_trade': 0.01,         # Riesgo por operación (1%)
            
            # Timing
            'start_time': '09:45',          # Hora de inicio (15 min después de apertura)
            'end_time': '15:45',            # Hora de fin (15 min antes de cierre)
            'avoid_first_minutes': 15,      # Evitar primeros minutos de la sesión
            
            # Posición
            'max_position_value': 2000.0,   # Valor máximo de posición
            'min_position_value': 500.0     # Valor mínimo de posición
        }
        
    @staticmethod
    def get_vwap_smallcaps_params() -> Dict[str, Any]:
        """Parámetros para la estrategia VWAP Smallcaps"""
        return {
            # Parámetros VWAP
            'vwap_periods': [1, 5, 10],     # Períodos para cálculo de VWAP
            'vwap_std_dev': 2.0,           # Desviación estándar para bandas VWAP
            'vwap_lookback': 20,           # Barras para análisis de VWAP
            
            # Filtros técnicos
            'min_price': 1.0,              # Precio mínimo para operar
            'max_price': 20.0,             # Precio máximo para operar
            'min_avg_volume': 150000,      # Volumen promedio mínimo
            'volume_surge_factor': 1.5,    # Factor de aumento de volumen
            'rsi_period': 14,              # Período RSI
            'rsi_oversold': 30,            # Nivel RSI sobreventa
            'rsi_overbought': 70,          # Nivel RSI sobrecompra
            'use_macd_filter': True,       # Usar MACD como filtro adicional
            'macd_fast': 12,               # Período rápido MACD
            'macd_slow': 26,               # Período lento MACD
            'macd_signal': 9,              # Período señal MACD
            
            # Gestión de riesgo
            'stop_loss_pct': 0.03,         # Stop loss (3%)
            'take_profit_pct': 0.09,       # Take profit (9%)
            'trailing_stop_pct': 0.02,     # Trailing stop (2%)
            'max_bars_held': 120,          # Máximo de barras a mantener posición
            'risk_per_trade': 0.01,        # Riesgo por operación (1%)
            
            # Timing
            'start_time': '09:45',         # Hora de inicio (15 min después de apertura)
            'end_time': '15:45',           # Hora de fin (15 min antes de cierre)
            'avoid_first_minutes': 15,     # Evitar primeros minutos de la sesión
            
            # Posición
            'max_position_value': 2000.0,  # Valor máximo de posición
            'min_position_value': 500.0,   # Valor mínimo de posición
            'max_positions': 3,            # Máximo número de posiciones simultáneas
            
            # Parámetros específicos de VWAP
            'vwap_entry_threshold': 0.005, # Umbral para entrada (0.5% desde VWAP)
            'vwap_exit_threshold': 0.01,   # Umbral para salida (1% desde VWAP)
            'use_vwap_bands': True,        # Usar bandas de VWAP
            'band_entry_mode': 'touch',    # Modo de entrada en bandas ('touch', 'cross')
            'require_volume_confirmation': True,  # Requerir confirmación de volumen
            'max_daily_trades': 8,         # Máximo de operaciones diarias
            
            # Performance tracking
            'profit_factor_threshold': 1.5, # Umbral de factor de beneficio
            'win_rate_threshold': 0.4,     # Umbral de tasa de acierto
            'max_drawdown_threshold': 0.15 # Umbral máximo de drawdown
        }
    
    @staticmethod
    def get_macdv_basic_grid() -> Dict[str, List]:
        """Grid básico para optimización MACDV"""
        return {
            'macd_fast': [8, 12, 16],
            'macd_slow': [21, 26, 30],
            'stop_loss_pct': [0.02, 0.03, 0.04],
            'take_profit_pct': [0.04, 0.06, 0.08],
            'min_conditions': [3, 4, 5],
            'volume_threshold': [1.2, 1.5, 2.0]
        }
    
    @staticmethod
    def get_macdv_extended_grid() -> Dict[str, List]:
        """Grid extendido para optimización exhaustiva"""
        return {
            'macd_fast': [6, 8, 10, 12, 14, 16],
            'macd_slow': [18, 21, 24, 26, 28, 30, 32],
            'macd_signal': [6, 9, 12],
            'stop_loss_pct': [0.015, 0.02, 0.025, 0.03, 0.035, 0.04],
            'take_profit_pct': [0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10],
            'min_conditions': [3, 4, 5, 6],
            'volume_threshold': [1.0, 1.2, 1.5, 1.8, 2.0, 2.5],
            'max_hold_hours': [1, 2, 3, 4, 6, 8],
            'ma_short': [5, 8, 10, 13],
            'ma_long': [13, 18, 21, 26]
        }
    
    @staticmethod
    def get_macdv_risk_focused_grid() -> Dict[str, List]:
        """Grid enfocado en optimización de risk management"""
        return {
            'stop_loss_pct': [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05],
            'take_profit_pct': [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12],
            'max_hold_hours': [0.5, 1, 2, 3, 4, 6, 8, 12],
            'min_conditions': [2, 3, 4, 5, 6],
            'max_position_value': [500, 750, 1000, 1500, 2000]
        }
    
    @staticmethod
    def get_session_specific_grid() -> Dict[str, List]:
        """Grid para optimización específica por sesión"""
        return {
            'premarket_stop_loss': [0.01, 0.015, 0.02, 0.025],
            'regular_stop_loss': [0.02, 0.025, 0.03, 0.035],
            'afterhours_stop_loss': [0.015, 0.02, 0.025, 0.03],
            'premarket_volume_threshold': [2.0, 2.5, 3.0],
            'regular_volume_threshold': [1.2, 1.5, 1.8],
            'afterhours_volume_threshold': [2.0, 2.5, 3.0],
            'session_max_hold_hours': [1, 2, 3, 4]
        }




class OptimizationConfigurations:
    """Wrapper class that exposes static parameter grids for optimizations.
    It delegates to the corresponding methods implemented inside
    `StrategyConfigurations` so that existing code that expects an
    `OptimizationConfigurations` class continues to work without
    duplicating logic.
    """

    # --- MACD-V grids -----------------------------------------------------
    @staticmethod
    def get_macdv_basic_grid():
        """Return a basic optimization grid for MACDV parameters."""
        return StrategyConfigurations.get_macdv_basic_grid()

    @staticmethod
    def get_macdv_extended_grid():
        """Return an extended optimization grid for an exhaustive search."""
        return StrategyConfigurations.get_macdv_extended_grid()

    @staticmethod
    def get_macdv_risk_focused_grid():
        """Return an optimization grid focused on risk-management variables."""
        return StrategyConfigurations.get_macdv_risk_focused_grid()

    # --- Session-specific grid -------------------------------------------
    @staticmethod
    def get_session_specific_grid():
        """Return a grid designed for session-specific MACDV optimisation."""
        return StrategyConfigurations.get_session_specific_grid()


class SymbolConfigurations:
    """Configuraciones de símbolos para diferentes escenarios"""
    
    @staticmethod
    def get_smallcap_tech() -> List[str]:
        """Smallcaps tecnológicas con alta volatilidad"""
        return ["RIOT", "MARA", "SAVA", "SPCE", "TLRY", "SNDL", "CLOV", "WISH"]
    
    @staticmethod
    def get_smallcap_biotech() -> List[str]:
        """Smallcaps biotecnológicas"""
        return ["OCGN", "GEVO", "NVAX", "MRNA", "BNTX", "VXRT", "INO", "DVAX"]
    
    @staticmethod
    def get_meme_stocks() -> List[str]:
        """Acciones meme populares"""
        return ["GME", "AMC", "BBBY", "KOSS", "EXPR", "NAKD", "NOK", "BB"]
    
    @staticmethod
    def get_tech_giants() -> List[str]:
        """Grandes tecnológicas (para comparación)"""
        return ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA", "AMZN", "META", "NFLX"]
    
    @staticmethod
    def get_volatile_smallcaps() -> List[str]:
        """Smallcaps con alta volatilidad intradiaria"""
        return ["DWAC", "PHUN", "MARK", "GREE", "PROG", "ATER", "BBIG", "SPRT"]
    
    @staticmethod
    def get_minimal_test_set() -> List[str]:
        """Set mínimo para pruebas rápidas"""
        return ["AAPL", "GOOGL", "MSFT"]
    
    @staticmethod
    def get_diverse_portfolio() -> List[str]:
        """Portfolio diversificado por sectores"""
        return [
            "AAPL",   # Tech
            "GOOGL",  # Tech
            "JPM",    # Finance
            "JNJ",    # Healthcare
            "XOM",    # Energy
            "WMT",    # Retail
            "DIS",    # Entertainment
            "BA"      # Industrial
        ]


class DataConfigurations:
    """Configuraciones relacionadas con datos"""
    
    @staticmethod
    def get_data_folder_path() -> str:
        """Ruta por defecto de la carpeta de datos"""
        return "data"
    
    @staticmethod
    def get_timeframe_preferences() -> Dict[str, int]:
        """Preferencias de timeframes (orden de prioridad)"""
        return {
            "1min": 1,    # Máxima prioridad
            "5min": 2,
            "15min": 3,
            "30min": 4,
            "1H": 5,
            "1D": 6
        }
    
    @staticmethod
    def get_session_hours() -> Dict[str, Dict[str, str]]:
        """Definición de horarios de sesión (ET)"""
        return {
            "premarket": {"start": "04:00", "end": "09:30"},
            "regular": {"start": "09:30", "end": "16:00"},
            "afterhours": {"start": "16:00", "end": "20:00"}
        }
    
    @staticmethod
    def get_expected_csv_format() -> Dict[str, Any]:
        """Formato CSV esperado"""
        return {
            "required_columns": ["timestamp", "open", "high", "low", "close", "volume"],
            "timestamp_formats": [
                "%Y-%m-%d %H:%M:%S%z",  # Con timezone
                "%Y-%m-%d %H:%M:%S",    # Sin timezone
                "%Y-%m-%d %H:%M",       # Sin segundos
            ],
            "alternative_names": {
                "datetime": "timestamp",
                "date": "timestamp",
                "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"
            }
        }


# Funciones helper para configuración rápida
def create_custom_backtest_config(
    start_date: str,
    end_date: str,
    initial_capital: float = 10000.0,
    commission_per_trade: float = 1.0,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.001,
    max_positions: int = 3,
    risk_per_trade: float = 0.02,
    data_frequency: str = "5min"
) -> BacktestConfig:
    """Crear configuración de backtest personalizada"""
    return BacktestConfig(
        start_date=datetime.strptime(start_date, "%Y-%m-%d"),
        end_date=datetime.strptime(end_date, "%Y-%m-%d"),
        initial_capital=initial_capital,
        commission_per_trade=commission_per_trade,
        commission_pct=commission_pct,
        slippage_pct=slippage_pct,
        max_positions=max_positions,
        risk_per_trade=risk_per_trade,
        data_frequency=data_frequency
    )


def create_custom_macdv_params(**kwargs) -> Dict[str, Any]:
    """Crear parámetros MACDV personalizados"""
    default_params = StrategyConfigurations.get_macdv_1min_optimized()
    default_params.update(kwargs)
    return default_params


# Configuraciones rápidas predefinidas
def get_quick_test_setup():
    """Setup completo para pruebas rápidas"""
    return {
        'config': BacktestConfigurations.get_fast_test_config(),
        'strategy_params': StrategyConfigurations.get_macdv_default_5min(),
        'symbols': SymbolConfigurations.get_minimal_test_set()
    }


def get_full_backtest_setup():
    """Setup completo para backtesting completo"""
    return {
        'config': BacktestConfigurations.get_default_1min_config(),
        'strategy_params': StrategyConfigurations.get_macdv_1min_optimized(),
        'symbols': SymbolConfigurations.get_smallcap_tech()
    }


def get_optimization_setup():
    """Setup completo para optimización de parámetros"""
    return {
        'config': BacktestConfigurations.get_optimization_config(),
        'param_grid': OptimizationConfigurations.get_macdv_basic_grid(),
        'symbols': SymbolConfigurations.get_minimal_test_set()
    }


def get_session_specific_setup(session: str = "regular"):
    """Setup específico por sesión de trading"""
    strategy_params = {
        "premarket": StrategyConfigurations.get_macdv_premarket(),
        "regular": StrategyConfigurations.get_macdv_regular(),
        "afterhours": StrategyConfigurations.get_macdv_afterhours()
    }
    
    return {
        'config': BacktestConfigurations.get_default_1min_config(),
        'strategy_params': strategy_params.get(session, StrategyConfigurations.get_macdv_regular()),
        'symbols': SymbolConfigurations.get_smallcap_tech(),
        'session': session
    }


# Validación de configuraciones
def validate_backtest_config(config: BacktestConfig) -> List[str]:
    """Validar configuración de backtest"""
    warnings = []
    
    if config.start_date >= config.end_date:
        warnings.append("Start date must be before end date")
    
    if config.initial_capital <= 0:
        warnings.append("Initial capital must be positive")
    
    if config.commission_pct < 0 or config.commission_pct > 0.01:
        warnings.append("Commission percentage seems unusually high (>1%)")
    
    if config.slippage_pct < 0 or config.slippage_pct > 0.01:
        warnings.append("Slippage percentage seems unusually high (>1%)")
    
    if config.risk_per_trade <= 0 or config.risk_per_trade > 0.1:
        warnings.append("Risk per trade should be between 0 and 10%")
    
    if config.max_positions <= 0:
        warnings.append("Max positions must be positive")
    
    # Verificar período de backtest
    duration = config.end_date - config.start_date
    if duration.days < 30:
        warnings.append("Backtest period is very short (<30 days)")
    
    return warnings


def validate_strategy_params(params: Dict[str, Any]) -> List[str]:
    """Validar parámetros de estrategia"""
    warnings = []
    
    # Validación MACD
    if params.get('macd_fast', 0) >= params.get('macd_slow', 0):
        warnings.append("MACD fast period should be less than slow period")
    
    # Validación risk management
    if params.get('stop_loss_pct', 0) <= 0:
        warnings.append("Stop loss percentage must be positive")
    
    if params.get('take_profit_pct', 0) <= 0:
        warnings.append("Take profit percentage must be positive")
    
    if params.get('stop_loss_pct', 0) >= params.get('take_profit_pct', 0):
        warnings.append("Take profit should be larger than stop loss")
    
    # Validación volumen
    if params.get('volume_threshold', 0) <= 1.0:
        warnings.append("Volume threshold should be > 1.0")
    
    # Validación moving averages
    if params.get('ma_short', 0) >= params.get('ma_long', 0):
        warnings.append("Short MA period should be less than long MA period")
    
    return warnings


if __name__ == "__main__":
    # Ejemplos de uso
    print("📊 BACKTEST CONFIGURATIONS - Examples")
    print("=" * 50)
    
    # Test configuraciones básicas
    config_1min = BacktestConfigurations.get_default_1min_config()
    config_5min = BacktestConfigurations.get_default_5min_config()
    
    print("✅ Configuraciones disponibles:")
    print(f"   1min config: {config_1min.data_frequency}")
    print(f"   5min config: {config_5min.data_frequency}")
    
    # Test parámetros de estrategia
    params_1min = StrategyConfigurations.get_macdv_1min_optimized()
    params_premarket = StrategyConfigurations.get_macdv_premarket()
    
    print(f"\n📈 Estrategias disponibles:")
    print(f"   1min optimized: stop_loss={params_1min['stop_loss_pct']}")
    print(f"   Premarket: stop_loss={params_premarket['stop_loss_pct']}")
    
    # Test validación
    warnings = validate_backtest_config(config_1min)
    if warnings:
        print(f"\n⚠️  Configuration warnings:")
        for warning in warnings:
            print(f"   - {warning}")
    else:
        print(f"\n✅ Configuration is valid")
    
    # Test setups rápidos
    quick_setup = get_quick_test_setup()
    full_setup = get_full_backtest_setup()
    
    print(f"\n🚀 Quick setups:")
    print(f"   Quick test: {len(quick_setup['symbols'])} symbols")
    print(f"   Full backtest: {len(full_setup['symbols'])} symbols")
    
    print(f"\n✨ Ready to use with:")
    print("   from backtest_config import get_full_backtest_setup")
    print("   setup = get_full_backtest_setup()")
    print("   config = setup['config']")
    print("   params = setup['strategy_params']")
