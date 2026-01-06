# testing/monkey_tester.py
"""
Monkey Testing Module: SISTEMA GENERALIZADO DE TESTING
Ejecuta cualquier estrategia contra datos históricos con múltiples escenarios
OPTIMIZADO PARA TESTING INTRADAY DE ESTRATEGIAS
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
from typing import Dict, List, Any, Optional, Tuple
import json
import random
from dataclasses import dataclass, asdict
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import sys
import os

# Añadir el directorio raíz del proyecto al PYTHONPATH
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))
print(f"Añadido al PYTHONPATH: {project_root}")

# Ahora podemos importar los módulos del proyecto
from core.interfaces import MarketData, Signal, SignalType
from strategies.base import BaseStrategy
from strategies.macdv_strategy import MACDVStrategy
from strategies.volume_breakout_strategy import VolumeBreakoutStrategy
from strategies.volume_momentum_strategy import VolumeMomentumStrategy


@dataclass
class MonkeyTestConfig:
    """Configuración para monkey testing"""
    # Datos de testing
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    symbols: List[str] = None
    timeframe: str = "1Min"
    
    # Parámetros de monkey testing
    num_monkey_runs: int = 50               # Número de ejecuciones aleatorias
    parameter_variance: float = 0.3         # 30% variación en parámetros
    random_seed: int = 42
    
    # Capital y riesgo
    initial_capital: float = 25000.0
    max_risk_per_trade: float = 0.02
    commission_per_share: float = 0.005
    min_commission: float = 1.0
    slippage_bps: int = 5
    
    # Filtros de datos
    min_volume: int = 10000
    min_price: float = 1.0
    max_price: float = 100.0
    
    # Configuración de outputs
    generate_plots: bool = True
    save_results: bool = True
    results_dir: str = "tests/monkey_test_results"
    verbose: bool = True
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["AAPL", "MSFT", "AMZN", "GOOGL", "META"]


@dataclass
class TradeResult:
    """Resultado individual de un trade"""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    signal_type: SignalType


@dataclass
class MonkeyTestResult:
    """Resultado de un monkey test individual"""
    run_id: int
    params: Dict[str, Any]
    
    # Métricas de rendimiento
    final_capital: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    
    # Métricas de riesgo
    max_consecutive_losses: int
    largest_loss: float
    average_hold_time: float
    
    # Trades detallados
    trades: List[TradeResult]


class MonkeyDataGenerator:
    """Generador de datos realistas para monkey testing"""
    
    def __init__(self, config: MonkeyTestConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.min_history_bars = 200  # Aumentado para estrategias que requieren más historial como MACDV
    
    def generate_realistic_intraday_data(self, symbol: str, date: datetime) -> List[MarketData]:
        """Generar datos intraday realistas para un símbolo"""
        np.random.seed(self.config.random_seed + hash(symbol + str(date)) % 1000)
        
        # Parámetros base para el símbolo
        base_price = random.uniform(20.0, 150.0)  # Precios más realistas para acciones como AAPL
        daily_volatility = random.uniform(0.03, 0.12)  # Aumentada a 3-12% volatilidad diaria para generar más señales
        base_volume = random.randint(300000, 2000000)  # Mayor volumen para símbolos líquidos
        
        # Ajustar volatilidad y volumen según el símbolo
        if symbol == 'AAPL':
            daily_volatility = random.uniform(0.04, 0.10)  # Aumentada para AAPL
            base_volume = random.randint(800000, 3000000)  # AAPL tiene alto volumen
        elif symbol == 'MSFT':
            daily_volatility = random.uniform(0.035, 0.09)  # MSFT moderadamente volátil
            base_volume = random.randint(600000, 2500000)
        elif symbol == 'GOOGL':
            daily_volatility = random.uniform(0.04, 0.11)  # GOOGL más volátil
            base_volume = random.randint(500000, 2000000)
        
        bars = []
        current_price = base_price
        
        # Generar suficiente historial para estrategias que requieren muchas barras (como MACDV)
        # Primero generamos barras históricas para días anteriores
        history_days = 20  # Aumentado a 20 días de historial para MACDV
        
        # Generar tendencias para crear oportunidades de trading
        # Cada 3-5 días, cambiar la dirección de la tendencia
        trend_direction = 1 if random.random() > 0.5 else -1  # Tendencia inicial (alcista o bajista)
        trend_days = 0
        trend_strength = random.uniform(0.001, 0.005)  # Fuerza de la tendencia (drift diario)
        
        for day_offset in range(history_days, 0, -1):
            history_date = date - timedelta(days=day_offset)
            # Saltamos fines de semana
            if history_date.weekday() >= 5:  # 5=sábado, 6=domingo
                continue
            
            # Cambiar tendencia cada 3-5 días para crear más oportunidades de trading
            trend_days += 1
            if trend_days >= random.randint(3, 5):
                trend_direction *= -1  # Invertir tendencia
                trend_strength = random.uniform(0.001, 0.005)  # Nueva fuerza de tendencia
                trend_days = 0
                self.logger.debug(f"Cambio de tendencia para {symbol} en fecha {history_date}: {'alcista' if trend_direction > 0 else 'bajista'}")
            
            # Aplicar tendencia al precio base
            base_price *= (1 + trend_direction * trend_strength * random.uniform(0.8, 1.2))
                
            self.logger.debug(f"Generando historial para {symbol} en fecha {history_date}, tendencia: {'alcista' if trend_direction > 0 else 'bajista'}")
            # Pasar la tendencia al generador de datos diarios
            history_bars = self._generate_single_day_data(symbol, history_date, base_price, daily_volatility, base_volume, trend_direction)
            bars.extend(history_bars)
            # Actualizar el precio base para el siguiente día
            if history_bars:
                base_price = history_bars[-1].close
        
        # Ahora generamos las barras para el día actual
        current_day_bars = self._generate_single_day_data(symbol, date, base_price, daily_volatility, base_volume)
        bars.extend(current_day_bars)
        
        self.logger.info(f"Generadas {len(bars)} barras para {symbol} (incluyendo {len(bars)-len(current_day_bars)} barras históricas)")
        return bars
        
    def _generate_single_day_data(self, symbol: str, date: datetime, base_price: float, daily_volatility: float, base_volume: int, trend_direction: int = 0) -> List[MarketData]:
        """Genera datos para un solo día de trading
        
        Args:
            symbol: Símbolo para el que generar datos
            date: Fecha para la que generar datos
            base_price: Precio base inicial
            daily_volatility: Volatilidad diaria (porcentaje decimal)
            base_volume: Volumen base diario
            trend_direction: Dirección de la tendencia (1=alcista, -1=bajista, 0=neutral)
            
        Returns:
            Lista de objetos MarketData con los datos generados
        """
        bars = []
        current_price = base_price
        current_time = datetime.combine(date, time(9, 30))
        end_time = datetime.combine(date, time(16, 0))
        
        # Crear patrones específicos para MACDV
        # MACDV busca cruces de MACD con divergencia de volumen
        # Necesitamos crear periodos con tendencia clara y cambios de volumen
        
        # Dividir el día en 3-4 segmentos con diferentes patrones
        segments = random.randint(3, 4)
        minutes_per_segment = (end_time - current_time).total_seconds() / 60 / segments
        current_segment = 0
        segment_start_time = current_time
        
        # Definir patrones para cada segmento
        segment_patterns = []
        for _ in range(segments):
            # Cada segmento tiene su propia micro-tendencia y patrón de volumen
            # 1=alcista fuerte, 0=neutral, -1=bajista fuerte
            micro_trend = random.choice([1, 1, 0, -1, -1]) if trend_direction == 0 else trend_direction
            # Patrón de volumen: 1=creciente, 0=estable, -1=decreciente
            volume_pattern = random.choice([1, 0, -1])
            # Volatilidad del segmento (relativa a la volatilidad diaria)
            segment_volatility = random.uniform(0.7, 1.5)
            segment_patterns.append((micro_trend, volume_pattern, segment_volatility))
        
        # Crear algunos patrones específicos para MACDV
        # Al menos un segmento debe tener tendencia alcista con aumento de volumen (condición ideal para MACDV)
        if random.random() < 0.7:  # 70% probabilidad de crear patrón favorable
            macdv_segment = random.randint(0, segments-1)
            segment_patterns[macdv_segment] = (1, 1, random.uniform(1.2, 1.8))  # Tendencia alcista con aumento de volumen
        
        # Crear un segmento con divergencia de volumen (precio sube pero volumen baja)
        if random.random() < 0.5:  # 50% probabilidad
            divergence_segment = random.randint(0, segments-1)
            segment_patterns[divergence_segment] = (1, -1, random.uniform(1.0, 1.5))  # Precio sube pero volumen baja
        
        while current_time < end_time:
            # Determinar en qué segmento estamos
            minutes_elapsed = (current_time - segment_start_time).total_seconds() / 60
            if minutes_elapsed >= minutes_per_segment and current_segment < segments - 1:
                current_segment += 1
                segment_start_time = current_time
            
            # Obtener patrón del segmento actual
            micro_trend, volume_pattern, segment_volatility = segment_patterns[current_segment]
            
            # Generar variación de precio realista con tendencia
            minute_volatility = daily_volatility / np.sqrt(390) * segment_volatility  # 390 minutos de trading
            # Añadir componente de tendencia al cambio de precio
            trend_bias = micro_trend * minute_volatility * current_price * random.uniform(0.5, 1.5)
            price_change = np.random.normal(trend_bias, minute_volatility * current_price)
            
            # Añadir patrones intraday realistas
            hour = current_time.hour
            minute = current_time.minute
            
            # Mayor volatilidad en apertura y cierre
            if (hour == 9 and minute < 60) or (hour >= 15 and minute >= 30):
                price_change *= 1.8  # Aumentado para crear más oportunidades
            
            # Menor volatilidad en mediodía
            elif 11 <= hour <= 14:
                price_change *= 0.6
            
            # Simular gaps ocasionales
            if random.random() < 0.08:  # Aumentado a 8% probabilidad de gap
                gap_size = random.uniform(-0.04, 0.06)  # Ampliado a -4% a +6%
                price_change += current_price * gap_size
            
            new_price = max(0.5, current_price + price_change)
            
            # Generar OHLC realista
            high_low_range = abs(price_change) * random.uniform(1.5, 3.0)  # Ampliado el rango
            high = new_price + random.uniform(0, high_low_range)
            low = new_price - random.uniform(0, high_low_range)
            
            # Asegurar consistencia OHLC
            high = max(high, current_price, new_price)
            low = min(low, current_price, new_price)
            
            # Generar volumen realista basado en el patrón del segmento
            volume_multiplier = 1.0
            
            # Ajustar volumen según el patrón del segmento
            if volume_pattern == 1:  # Volumen creciente
                progress = minutes_elapsed / minutes_per_segment  # 0 al inicio del segmento, 1 al final
                volume_multiplier *= (1.0 + progress * 2.0)  # Aumenta hasta 3x durante el segmento
            elif volume_pattern == -1:  # Volumen decreciente
                progress = minutes_elapsed / minutes_per_segment
                volume_multiplier *= (3.0 - progress * 2.0)  # Disminuye desde 3x hasta 1x
            
            # Mayor volumen en movimientos grandes (necesario para MACDV)
            if abs(price_change) / current_price > 0.015:  # Umbral reducido para más eventos
                volume_multiplier *= random.uniform(2.5, 6.0)  # Aumentado para crear más señales
            
            # Mayor volumen en apertura y cierre
            if (hour == 9 and minute < 45) or (hour == 15 and minute >= 30):
                volume_multiplier *= random.uniform(1.8, 3.5)  # Aumentado
                
            # Crear picos de volumen ocasionales (necesarios para MACDV)
            if random.random() < 0.06:  # 6% probabilidad de pico de volumen
                volume_multiplier *= random.uniform(3.0, 8.0)  # Pico significativo
                
            volume = int(base_volume * volume_multiplier * random.uniform(0.8, 1.2))
            
            # Crear objeto MarketData
            bar = MarketData(
                symbol=symbol,
                timestamp=current_time,
                open=current_price,
                high=high,
                low=low,
                close=new_price,
                volume=volume
            )
            
            bars.append(bar)
            current_price = new_price
            current_time += timedelta(minutes=1)
        
        return bars


class StrategyParameterMutator:
    """Mutador de parámetros para estrategias"""
    
    def __init__(self, config: MonkeyTestConfig):
        self.variance = config.parameter_variance
        self.random_seed = config.random_seed
        random.seed(self.random_seed)
        np.random.seed(self.random_seed)
    
    def mutate_parameters(self, base_params: Dict[str, Any], run_id: int) -> Dict[str, Any]:
        """Mutar parámetros para un run específico"""
        # Para el primer run, usar parámetros base sin mutación
        if run_id == 0:
            return base_params.copy()
        
        # Establecer semilla para reproducibilidad pero variación entre runs
        random.seed(self.random_seed + run_id)
        np.random.seed(self.random_seed + run_id)
        
        mutated_params = {}
        
        for key, value in base_params.items():
            if self._should_mutate(key, value):
                mutated_params[key] = self._mutate_value(key, value)
            else:
                mutated_params[key] = value
        
        return mutated_params
    
    def _should_mutate(self, key: str, value: Any) -> bool:
        """Determinar si un parámetro debe ser mutado"""
        # No mutar parámetros especiales
        if key.startswith('_') or key in ['name', 'description', 'enabled']:
            return False
        
        # Solo mutar números
        return isinstance(value, (int, float)) and value > 0
    
    def _mutate_value(self, key: str, value: Any) -> Any:
        """Mutar un valor específico"""
        if isinstance(value, bool):
            return value  # No mutar booleanos
        
        if isinstance(value, int):
            # Para enteros, variar ±variance%
            min_val = max(1, int(value * (1 - self.variance)))
            max_val = int(value * (1 + self.variance))
            return random.randint(min_val, max_val)
        
        elif isinstance(value, float):
            # Para floats, usar distribución normal
            std_dev = value * self.variance * 0.3  # 30% del valor como std dev
            new_value = np.random.normal(value, std_dev)
            
            # Asegurar valores positivos para la mayoría de parámetros
            if key.endswith('_pct') or 'threshold' in key or 'multiplier' in key:
                new_value = max(0.001, new_value)
            
            return float(new_value)
        
        return value


class MonkeyTestRunner:
    """Ejecutor de monkey tests para estrategias"""
    
    def __init__(self, config: MonkeyTestConfig, strategy_name: str = "macdv"):
        self.config = config
        self.strategy_name = strategy_name
        self.logger = logging.getLogger(self.__class__.__name__)
        self.data_generator = MonkeyDataGenerator(config)
        self.param_mutator = StrategyParameterMutator(config)
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO if config.verbose else logging.WARNING,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Crear directorio de resultados si no existe
        if config.save_results:
            os.makedirs(config.results_dir, exist_ok=True)
    
    def run_tests(self) -> List[MonkeyTestResult]:
        """Ejecutar todos los monkey tests configurados"""
        self.logger.info(f"Iniciando monkey testing para estrategia {self.strategy_name} con {self.config.num_monkey_runs} ejecuciones")
        
        # Crear estrategia base para obtener parámetros por defecto
        base_strategy = self._create_strategy(self.strategy_name)
        
        # Intentar obtener parámetros, con manejo especial para estrategias sin get_parameters
        try:
            base_params = base_strategy.get_parameters()
        except AttributeError:
            # Si la estrategia no tiene get_parameters, intentamos acceder a _parameters directamente
            # o usamos un diccionario vacío como fallback
            if hasattr(base_strategy, '_parameters'):
                self.logger.info(f"La estrategia {self.strategy_name} no tiene get_parameters(), usando _parameters directamente")
                base_params = base_strategy._parameters.copy() if base_strategy._parameters else {}
            else:
                self.logger.warning(f"La estrategia {self.strategy_name} no tiene parámetros accesibles, usando valores por defecto")
                base_params = {
                    # Parámetros genéricos que funcionan para la mayoría de estrategias
                    'volume_surge_multiplier': 2.0,
                    'atr_period': 14,
                    'stop_loss_atr_mult': 1.5,
                    'profit_target': 0.15,
                    'trailing_activation_pct': 0.10,
                    'trailing_stop_distance': 0.05,
                }
        
        self.logger.info(f"Parámetros base: {base_params}")
        
        results = []
        for run_id in range(self.config.num_monkey_runs):
            try:
                self.logger.info(f"\n--- Ejecutando monkey test {run_id+1}/{self.config.num_monkey_runs} ---")
                
                # Mutar parámetros para este run
                params = self.param_mutator.mutate_parameters(base_params, run_id)
                self.logger.info(f"Parámetros mutados: {params}")
                
                # Ejecutar test con estos parámetros
                result = self._run_single_test(run_id, params)
                results.append(result)
                
                # Guardar resultado individual
                if self.config.save_results:
                    self._save_result(result)
                
            except Exception as e:
                self.logger.error(f"Error en monkey test {run_id}: {str(e)}")
                self.logger.exception(e)
        
        # Generar reporte final
        if self.config.save_results:
            self._generate_report(results)
        
        return results
    
    def _create_strategy(self, strategy_name: str) -> BaseStrategy:
        """Crear instancia de estrategia según el nombre"""
        self.logger.info(f"Creando estrategia: {strategy_name}")
        
        if strategy_name.lower() == "macdv":
            return MACDVStrategy()
        elif strategy_name.lower() == "volume_breakout":
            return VolumeBreakoutStrategy()
        elif strategy_name.lower() == "volume_momentum":
            return VolumeMomentumStrategy()
        else:
            raise ValueError(f"Estrategia desconocida: {strategy_name}")
    
    def _create_strategy_with_params(self, strategy_name: str, params: Dict[str, Any]) -> BaseStrategy:
        """Crear instancia de estrategia con parámetros personalizados"""
        self.logger.info(f"Creando estrategia {strategy_name} con parámetros personalizados")
        
        if strategy_name.lower() == "macdv":
            return MACDVStrategy(parameters=params)
        elif strategy_name.lower() == "volume_breakout":
            return VolumeBreakoutStrategy(parameters=params)
        elif strategy_name.lower() == "volume_momentum":
            return VolumeMomentumStrategy(parameters=params)
        else:
            raise ValueError(f"Estrategia desconocida: {strategy_name}")
    
    def _initialize_strategy_data_structures(self, strategy: BaseStrategy, symbols: List[str] = None) -> None:
        """Inicializa las estructuras de datos necesarias para la estrategia"""
        # Si no se proporcionan símbolos, usar los de la configuración
        if symbols is None:
            symbols = self.config.symbols
        try:
            # Inicializar estructuras comunes
            if hasattr(strategy, 'bars_history'):
                for symbol in self.config.symbols:
                    if symbol not in strategy.bars_history:
                        strategy.bars_history[symbol] = []
            
            # Inicializar otras estructuras específicas según la estrategia
            if self.strategy_name.lower() == 'macdv':
                if hasattr(strategy, 'macd_values'):
                    for symbol in self.config.symbols:
                        if symbol not in strategy.macd_values:
                            strategy.macd_values[symbol] = []
                if hasattr(strategy, 'signal_values'):
                    for symbol in self.config.symbols:
                        if symbol not in strategy.signal_values:
                            strategy.signal_values[symbol] = []
                if hasattr(strategy, 'histogram_values'):
                    for symbol in self.config.symbols:
                        if symbol not in strategy.histogram_values:
                            strategy.histogram_values[symbol] = []
                if hasattr(strategy, 'ma_values'):
                    for symbol in self.config.symbols:
                        if symbol not in strategy.ma_values:
                            strategy.ma_values[symbol] = []
            
            # Inicializar estructuras específicas para volume_momentum
            elif self.strategy_name.lower() == 'volume_momentum':
                # Inicializar estructuras de datos para análisis de volumen
                if hasattr(strategy, 'volume_data'):
                    for symbol in self.config.symbols:
                        if symbol not in strategy.volume_data:
                            strategy.volume_data[symbol] = []
                
                # Inicializar estructuras para indicadores técnicos
                if hasattr(strategy, 'vwap_data'):
                    for symbol in self.config.symbols:
                        if symbol not in strategy.vwap_data:
                            strategy.vwap_data[symbol] = []
                
                if hasattr(strategy, 'macd_data'):
                    for symbol in self.config.symbols:
                        if symbol not in strategy.macd_data:
                            strategy.macd_data[symbol] = {}
                
                if hasattr(strategy, 'adx_data'):
                    for symbol in self.config.symbols:
                        if symbol not in strategy.adx_data:
                            strategy.adx_data[symbol] = []
                
                # Inicializar estadísticas de trading
                if hasattr(strategy, 'trade_statistics') and not strategy.trade_statistics:
                    strategy.trade_statistics = {
                        'total_signals': 0,
                        'entries_taken': 0,
                        'volume_filtered': 0,
                        'pattern_filtered': 0,
                        'momentum_filtered': 0,
                        'spread_filtered': 0
                    }
            
            self.logger.info("Estructuras de datos inicializadas correctamente")
        except Exception as e:
            self.logger.error(f"Error inicializando estructuras de datos: {e}")
    
    def _run_single_test(self, run_id: int, params: Dict[str, Any]) -> MonkeyTestResult:
        """Ejecutar un solo test con parámetros específicos"""
        # Crear estrategia con parámetros mutados
        strategy = self._create_strategy(self.strategy_name)
        
        # Intentar establecer parámetros, con manejo especial para estrategias sin set_parameters
        try:
            strategy.set_parameters(params)
        except AttributeError:
            # Si la estrategia no tiene set_parameters, intentamos establecer _parameters directamente
            if hasattr(strategy, '_parameters'):
                self.logger.info(f"La estrategia {self.strategy_name} no tiene set_parameters(), estableciendo _parameters directamente")
                # Crear una nueva instancia con los parámetros modificados
                strategy = self._create_strategy_with_params(self.strategy_name, params)
            else:
                self.logger.warning(f"La estrategia {self.strategy_name} no permite modificar parámetros, usando valores por defecto")
                # Continuamos con la estrategia sin modificar parámetros
        
        # Inicializar estructuras de datos necesarias para la estrategia
        self._initialize_strategy_data_structures(strategy, self.config.symbols)
        
        # Generar datos de mercado para todos los símbolos
        start_date = datetime.strptime(self.config.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(self.config.end_date, "%Y-%m-%d")
        
        # Usar solo un día para simplificar
        test_date = start_date + timedelta(days=run_id % (end_date - start_date).days)
        
        # Evitar fines de semana
        while test_date.weekday() >= 5:  # 5=sábado, 6=domingo
            test_date += timedelta(days=1)
        
        self.logger.info(f"Generando datos para fecha: {test_date.strftime('%Y-%m-%d')}")
        
        # Generar datos para todos los símbolos
        market_data_by_symbol = {}
        for symbol in self.config.symbols:
            try:
                market_data = self.data_generator.generate_realistic_intraday_data(symbol, test_date)
                market_data_by_symbol[symbol] = market_data
                self.logger.info(f"Generados {len(market_data)} datos para {symbol}")
            except Exception as e:
                self.logger.error(f"Error generando datos para {symbol}: {str(e)}")
                self.logger.exception(e)
        
        # Ejecutar backtest con estos datos
        trades, portfolio = self._run_backtest(strategy, market_data_by_symbol)
        
        # Calcular métricas
        metrics = self._calculate_metrics(trades, self.config.initial_capital)
        
        # Crear resultado
        result = MonkeyTestResult(
            run_id=run_id,
            params=params,
            final_capital=portfolio[-1] if portfolio else self.config.initial_capital,
            total_trades=metrics.get('total_trades', 0),
            winning_trades=metrics.get('winning_trades', 0),
            losing_trades=metrics.get('losing_trades', 0),
            win_rate=metrics.get('win_rate', 0.0),
            profit_factor=metrics.get('profit_factor', 0.0),
            max_consecutive_losses=metrics.get('max_consecutive_losses', 0),
            largest_loss=metrics.get('largest_loss', 0.0),
            average_hold_time=metrics.get('average_hold_time', 0.0),
            trades=trades
        )
        
        return result
    
    def _run_backtest(self, strategy: BaseStrategy, market_data_by_symbol: Dict[str, List[MarketData]]) -> Tuple[List[TradeResult], List[float]]:
        """Ejecutar backtest con datos generados"""
        self.logger.info("Iniciando backtest...")
        
        # Inicializar portfolio y trades
        portfolio = [self.config.initial_capital]
        trades = []
        open_positions = {}
        
        # Crear timeline consolidada de todos los datos
        all_data = []
        for symbol, data_list in market_data_by_symbol.items():
            all_data.extend(data_list)
        
        # Ordenar por timestamp
        all_data.sort(key=lambda x: x.timestamp)
        
        # Inicializar contador de barras para diagnóstico
        bar_counter = 0
        
        # Procesar cada barra de datos
        for bar in all_data:
            bar_counter += 1
            symbol = bar.symbol
            
            # Obtener datos históricos para este símbolo hasta este momento
            symbol_data = [d for d in market_data_by_symbol[symbol] if d.timestamp <= bar.timestamp]
            
            # Actualizar bars_history en la estrategia para asegurar que tiene suficientes barras
            if hasattr(strategy, 'bars_history'):
                strategy.bars_history[symbol] = symbol_data
            
            try:
                # Procesar barra con la estrategia
                signal = None
                
                # Intentar usar process_bar si existe
                if hasattr(strategy, 'process_bar'):
                    signal = strategy.process_bar(bar, symbol_data)
                    
                    # Si la estrategia devuelve una coroutine (async), ejecutarla
                    if asyncio.iscoroutine(signal):
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            signal = loop.run_until_complete(signal)
                        finally:
                            loop.close()
                else:
                    # Obtener señal de análisis de barra
                    signal = strategy._analyze_bar(bar)
                    # Manejar coroutine si es necesario
                    if asyncio.iscoroutine(signal):
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            signal = loop.run_until_complete(signal)
                        finally:
                            loop.close()
            except Exception as e:
                self.logger.error(f"Error procesando barra {bar.symbol} en {bar.timestamp}: {e}")
                signal = None
            
            # Diagnóstico para volume_momentum_strategy
            if self.strategy_name.lower() == "volume_momentum" and bar_counter % 50 == 0:
                self.logger.info(f"Diagnóstico VolumeMomentum para {symbol} en {bar.timestamp}:")
                self.logger.info(f"  - Barras en historial: {len(strategy.bars_history[symbol]) if hasattr(strategy, 'bars_history') and symbol in strategy.bars_history else 0}")
                self.logger.info(f"  - Min barras requeridas: {strategy._parameters['min_history_bars'] if hasattr(strategy, '_parameters') else 'N/A'}")
        # Cerrar posiciones abiertas al final del backtest
        for symbol, position in list(open_positions.items()):
            try:
                # Obtener último precio
                last_bar = next((bar for bar in reversed(market_data_by_symbol[symbol]) if bar.symbol == symbol), None)
                
                if last_bar:
                    # Aplicar slippage y comisiones
                    slippage = last_bar.close * self.config.slippage_bps / 10000
                    exit_price = last_bar.close - slippage if position['type'] == SignalType.LONG else last_bar.close + slippage
                    commission = max(self.config.min_commission, position['size'] * self.config.commission_per_share)
                    
                    # Calcular P&L
                    if position['type'] == SignalType.LONG:
                        pnl = (exit_price - position['entry_price']) * position['size'] - commission - position['commission']
                    else:  # SHORT
                        pnl = (position['entry_price'] - exit_price) * position['size'] - commission - position['commission']
                    
                    # Registrar trade completado
                    trade = TradeResult(
                        symbol=symbol,
                        entry_time=position['entry_time'],
                        exit_time=last_bar.timestamp,
                        entry_price=position['entry_price'],
                        exit_price=exit_price,
                        size=position['size'],
                        pnl=pnl,
                        signal_type=position['type']
                    )
                    trades.append(trade)
                    
                    # Actualizar portfolio
                    portfolio.append(portfolio[-1] + pnl)
                    
                    self.logger.info(f"Posición cerrada al final: {symbol}, PnL: {pnl:.2f}")
            
            except Exception as e:
                self.logger.error(f"Error cerrando posición para {symbol}: {str(e)}")
                self.logger.exception(e)
        
        return trades, portfolio
    
    def _calculate_position_size(self, signal: Signal, price: float, capital: float, max_risk_pct: float) -> float:
        """Calcular tamaño de posición basado en riesgo"""
        # Usar stop loss de la señal si está disponible, o default 2%
        if hasattr(signal, 'stop_loss') and signal.stop_loss > 0:
            stop_distance = abs(price - signal.stop_loss)
        else:
            stop_distance = price * 0.02  # Default 2% stop
        
        # Calcular riesgo máximo en dólares
        max_risk_dollars = capital * max_risk_pct
        
        # Calcular tamaño de posición
        if stop_distance > 0:
            position_size = max_risk_dollars / stop_distance
        else:
            position_size = 0
        
        return position_size
    
    def _calculate_metrics(self, trades: List[TradeResult], initial_capital: float) -> Dict[str, Any]:
        """Calcular métricas de rendimiento"""
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'max_consecutive_losses': 0,
                'largest_loss': 0.0,
                'average_hold_time': 0.0
            }
        
        # Métricas básicas
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.pnl > 0)
        losing_trades = sum(1 for t in trades if t.pnl <= 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # Métricas financieras
        total_profit = sum(t.pnl for t in trades if t.pnl > 0)
        total_loss = abs(sum(t.pnl for t in trades if t.pnl <= 0))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Métricas de riesgo
        consecutive_losses = 0
        max_consecutive_losses = 0
        largest_loss = 0
        
        for trade in trades:
            if trade.pnl <= 0:
                consecutive_losses += 1
                largest_loss = min(largest_loss, trade.pnl)
            else:
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                consecutive_losses = 0
        
        # Actualizar max_consecutive_losses si terminamos con una racha perdedora
        max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        
        # Tiempo promedio de tenencia
        hold_times = [(t.exit_time - t.entry_time).total_seconds() / 60 for t in trades]  # en minutos
        average_hold_time = sum(hold_times) / len(hold_times) if hold_times else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_consecutive_losses': max_consecutive_losses,
            'largest_loss': largest_loss,
            'average_hold_time': average_hold_time
        }
    
    def _save_result(self, result: MonkeyTestResult) -> None:
        """Guardar resultado individual a archivo"""
        if not self.config.save_results:
            return
        
        # Crear directorio para esta estrategia si no existe
        strategy_dir = os.path.join(self.config.results_dir, self.strategy_name)
        os.makedirs(strategy_dir, exist_ok=True)
        
        # Guardar resultado como JSON
        result_file = os.path.join(strategy_dir, f"run_{result.run_id}.json")
        
        # Convertir a formato serializable
        result_dict = asdict(result)
        
        # Convertir datetime a string
        for trade in result_dict['trades']:
            trade['entry_time'] = trade['entry_time'].isoformat()
            trade['exit_time'] = trade['exit_time'].isoformat()
        
        with open(result_file, 'w') as f:
            json.dump(result_dict, f, indent=2)
    
    def _generate_report(self, results: List[MonkeyTestResult]) -> None:
        """Generar reporte final con todos los resultados"""
        if not self.config.save_results or not results:
            return
        
        # Crear directorio para esta estrategia si no existe
        strategy_dir = os.path.join(self.config.results_dir, self.strategy_name)
        os.makedirs(strategy_dir, exist_ok=True)
        
        # Crear DataFrame con resultados
        results_data = []
        for result in results:
            row = {
                'run_id': result.run_id,
                'final_capital': result.final_capital,
                'total_trades': result.total_trades,
                'winning_trades': result.winning_trades,
                'losing_trades': result.losing_trades,
                'win_rate': result.win_rate,
                'profit_factor': result.profit_factor,
                'max_consecutive_losses': result.max_consecutive_losses,
                'largest_loss': result.largest_loss,
                'average_hold_time': result.average_hold_time
            }
            
            # Añadir parámetros como columnas
            for key, value in result.params.items():
                if isinstance(value, (int, float, str, bool)):
                    row[f'param_{key}'] = value
            
            results_data.append(row)
        
        # Crear DataFrame
        df = pd.DataFrame(results_data)
        
        # Guardar como CSV
        csv_file = os.path.join(strategy_dir, "summary.csv")
        df.to_csv(csv_file, index=False)
        
        # Generar gráficos si está habilitado
        if self.config.generate_plots:
            self._generate_plots(df, strategy_dir)
    
    def _generate_plots(self, df: pd.DataFrame, output_dir: str) -> None:
        """Generar gráficos de análisis"""
        try:
            # Configurar estilo
            plt.style.use('seaborn-v0_8-darkgrid')
            
            # 1. Histograma de rentabilidad final
            plt.figure(figsize=(10, 6))
            sns.histplot(df['final_capital'], kde=True)
            plt.title(f'Distribución de Capital Final - {self.strategy_name}')
            plt.xlabel('Capital Final ($)')
            plt.ylabel('Frecuencia')
            plt.axvline(self.config.initial_capital, color='r', linestyle='--', label=f'Capital Inicial (${self.config.initial_capital})')
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'capital_distribution.png'))
            plt.close()
            
            # 2. Relación entre win rate y profit factor
            plt.figure(figsize=(10, 6))
            sns.scatterplot(x='win_rate', y='profit_factor', data=df, hue='final_capital', palette='viridis', size='total_trades', sizes=(50, 200))
            plt.title(f'Win Rate vs Profit Factor - {self.strategy_name}')
            plt.xlabel('Win Rate')
            plt.ylabel('Profit Factor')
            plt.colorbar(label='Capital Final ($)')
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'winrate_vs_profitfactor.png'))
            plt.close()
            
            # 3. Parámetros vs Rendimiento
            # Identificar columnas de parámetros
            param_cols = [col for col in df.columns if col.startswith('param_')]
            
            if param_cols:
                # Seleccionar hasta 4 parámetros más correlacionados con el capital final
                correlations = [abs(df[col].corr(df['final_capital'])) for col in param_cols]
                top_params = [param_cols[i] for i in np.argsort(correlations)[-4:]][::-1]
                
                # Crear gráficos para los parámetros más importantes
                for param in top_params:
                    plt.figure(figsize=(10, 6))
                    sns.scatterplot(x=param, y='final_capital', data=df, hue='win_rate', palette='coolwarm')
                    plt.title(f'{param.replace("param_", "")} vs Capital Final - {self.strategy_name}')
                    plt.xlabel(param.replace("param_", ""))
                    plt.ylabel('Capital Final ($)')
                    plt.colorbar(label='Win Rate')
                    plt.tight_layout()
                    plt.savefig(os.path.join(output_dir, f'{param}_vs_capital.png'))
                    plt.close()
            
        except Exception as e:
            self.logger.error(f"Error generando gráficos: {str(e)}")
            self.logger.exception(e)


def parse_arguments():
    """Parsear argumentos de línea de comandos"""
    import argparse
    parser = argparse.ArgumentParser(description='Monkey Testing para estrategias de trading')
    
    parser.add_argument('--strategy', type=str, default='macdv',
                        help='Nombre de la estrategia a testear (default: macdv)')
    parser.add_argument('--runs', type=int, default=10,
                        help='Número de ejecuciones de monkey test (default: 10)')
    parser.add_argument('--symbols', type=str, default='AAPL,MSFT,GOOGL',
                        help='Lista de símbolos separados por comas (default: AAPL,MSFT,GOOGL)')
    parser.add_argument('--variance', type=float, default=0.3,
                        help='Varianza de parámetros (0.0-1.0) (default: 0.3)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Semilla aleatoria para reproducibilidad (default: 42)')
    parser.add_argument('--verbose', action='store_true',
                        help='Mostrar logs detallados')
    
    return parser.parse_args()


def main():
    """Función principal"""
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("MonkeyTester")
    
    # Parsear argumentos
    args = parse_arguments()
    
    # Crear configuración
    config = MonkeyTestConfig(
        num_monkey_runs=args.runs,
        parameter_variance=args.variance,
        random_seed=args.seed,
        symbols=args.symbols.split(','),
        verbose=args.verbose
    )
    
    # Crear directorio de resultados con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    config.results_dir = f"tests/monkey_test_results/{args.strategy}_monkey_test_{timestamp}"
    os.makedirs(config.results_dir, exist_ok=True)
    
    logger.info(f"Iniciando monkey testing para estrategia {args.strategy}")
    logger.info(f"Configuración: {config}")
    
    try:
        # Ejecutar monkey tests
        runner = MonkeyTestRunner(config, args.strategy)
        results = runner.run_tests()
        
        # Mostrar resumen
        logger.info("\n===== RESUMEN DE RESULTADOS =====")
        logger.info(f"Estrategia: {args.strategy}")
        logger.info(f"Ejecuciones completadas: {len(results)}/{args.runs}")
        
        if results:
            # Calcular métricas promedio
            avg_win_rate = sum(r.win_rate for r in results) / len(results)
            avg_profit_factor = sum(r.profit_factor for r in results) / len(results)
            avg_final_capital = sum(r.final_capital for r in results) / len(results)
            
            logger.info(f"Win Rate promedio: {avg_win_rate:.2%}")
            logger.info(f"Profit Factor promedio: {avg_profit_factor:.2f}")
            logger.info(f"Capital final promedio: ${avg_final_capital:.2f}")
            
            # Identificar mejor ejecución
            best_run = max(results, key=lambda r: r.final_capital)
            logger.info(f"\nMejor ejecución: Run #{best_run.run_id}")
            logger.info(f"Capital final: ${best_run.final_capital:.2f}")
            logger.info(f"Win Rate: {best_run.win_rate:.2%}")
            logger.info(f"Profit Factor: {best_run.profit_factor:.2f}")
            logger.info(f"Parámetros óptimos: {best_run.params}")
        
        logger.info(f"\nResultados guardados en: {config.results_dir}")
        
    except Exception as e:
        logger.error(f"Error en monkey testing: {str(e)}")
        logger.exception(e)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
