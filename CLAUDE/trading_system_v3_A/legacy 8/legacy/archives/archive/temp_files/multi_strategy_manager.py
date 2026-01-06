# strategies/multi_strategy_manager.py
"""
Gestor de múltiples estrategias que permite ejecutar varias estrategias simultáneamente.
Actúa como una única estrategia para el motor de trading, pero internamente gestiona múltiples estrategias.
"""

import logging
import asyncio
import time
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from zoneinfo import ZoneInfo

# Importar monitor de rendimiento
try:
    from utils.performance_monitor import performance_monitor
except ImportError:
    # Fallback si no está disponible
    performance_monitor = None

from core.interfaces import (
    IStrategy, Signal, SignalType, Position, MarketData, EventBus,
    OrderSide
)
from core.events import EventHandlerMixin, event_handler


class MultiStrategyManager(IStrategy, EventHandlerMixin):
    """
    Gestor de múltiples estrategias que permite ejecutar varias estrategias simultáneamente.
    Actúa como una única estrategia para el motor de trading, pero internamente gestiona múltiples estrategias.
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        self._name = "multi_strategy"
        self._parameters = parameters or {}
        self.logger = logging.getLogger("MultiStrategyManager")
        
        # Estrategias gestionadas
        self.strategies: Dict[str, IStrategy] = {}
        self.strategy_symbols: Dict[str, Set[str]] = {}  # Mapeo de estrategia -> símbolos
        
        # Estado compartido
        self.positions: Dict[str, Position] = {}
        self.bars_history: Dict[str, List[MarketData]] = {}
        self.signals_history: Dict[str, List[Signal]] = {}  # Historial de señales por estrategia
        
        # Máximo número de señales a almacenar por estrategia (OPTIMIZADO)
        self.max_signals_history = 50  # Reducido de 100 a 50 para mejor performance
        
        # Event bus será establecido durante la inicialización
        self.event_bus: Optional[EventBus] = None
        
        # Inicializar con event bus vacío inicialmente
        super().__init__(None)
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters.copy()
    
    async def initialize(self, event_bus: EventBus) -> None:
        """Inicializar el gestor de estrategias con el event bus"""
        self.event_bus = event_bus
        
        # Registrar manejadores de eventos
        self._register_event_handlers()
        
        # Inicializar cada estrategia
        for strategy_id, strategy in self.strategies.items():
            try:
                await strategy.initialize(event_bus)
                self.logger.info(f"Estrategia {strategy_id} inicializada correctamente")
            except Exception as e:
                self.logger.error(f"Error inicializando estrategia {strategy_id}: {e}")
        
        self.logger.info(f"Gestor de estrategias múltiples inicializado con {len(self.strategies)} estrategias")
    
    async def _initialize_strategy(self) -> None:
        """Implementación requerida pero no utilizada"""
        pass
    
    def add_strategy(self, strategy_id: str, strategy: IStrategy, symbols: List[str] = None) -> None:
        """
        Añadir una estrategia al gestor
        
        Args:
            strategy_id: Identificador único para la estrategia
            strategy: Instancia de la estrategia
            symbols: Lista opcional de símbolos para esta estrategia
        """
        self.strategies[strategy_id] = strategy
        self.strategy_symbols[strategy_id] = set(symbols) if symbols else set()
        self.logger.info(f"Estrategia {strategy_id} añadida con símbolos: {symbols}")
    
    def remove_strategy(self, strategy_id: str) -> None:
        """Eliminar una estrategia del gestor"""
        if strategy_id in self.strategies:
            self.strategies.pop(strategy_id)
            self.strategy_symbols.pop(strategy_id, None)
            self.logger.info(f"Estrategia {strategy_id} eliminada")
    
    def assign_symbol_to_strategy(self, strategy_id: str, symbol: str) -> bool:
        """Asignar un símbolo a una estrategia específica"""
        if strategy_id not in self.strategies:
            self.logger.warning(f"Estrategia {strategy_id} no encontrada")
            return False
        
        if strategy_id not in self.strategy_symbols:
            self.strategy_symbols[strategy_id] = set()
        
        self.strategy_symbols[strategy_id].add(symbol)
        self.logger.info(f"Símbolo {symbol} asignado a estrategia {strategy_id}")
        return True
    
    def remove_symbol_from_strategy(self, strategy_id: str, symbol: str) -> bool:
        """Eliminar un símbolo de una estrategia específica"""
        if strategy_id not in self.strategy_symbols:
            return False
        
        self.strategy_symbols[strategy_id].discard(symbol)
        self.logger.info(f"Símbolo {symbol} eliminado de estrategia {strategy_id}")
        return True
    
    def get_strategy_symbols(self, strategy_id: str) -> Set[str]:
        """Obtener los símbolos asignados a una estrategia"""
        return self.strategy_symbols.get(strategy_id, set()).copy()
    
    def get_all_symbols(self) -> Set[str]:
        """Obtener todos los símbolos de todas las estrategias"""
        all_symbols = set()
        for symbols in self.strategy_symbols.values():
            all_symbols.update(symbols)
        return all_symbols
        
    def update_strategy_parameters(self, strategy_id: str, parameters: Dict[str, Any]) -> bool:
        """
        Actualizar parámetros de una estrategia específica
        
        Args:
            strategy_id: ID de la estrategia a actualizar
            parameters: Diccionario de parámetros a actualizar
            
        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        if strategy_id not in self.strategies:
            self.logger.warning(f"Estrategia {strategy_id} no encontrada para actualizar parámetros")
            return False
            
        try:
            strategy = self.strategies[strategy_id]
            
            # Verificar si la estrategia tiene un método para actualizar parámetros
            if hasattr(strategy, 'update_parameters') and callable(getattr(strategy, 'update_parameters')):
                strategy.update_parameters(parameters)
                self.logger.info(f"Parámetros actualizados para estrategia {strategy_id}: {parameters}")
                return True
            # Si no tiene método específico, intentar actualizar directamente los atributos
            else:
                for param_name, param_value in parameters.items():
                    if hasattr(strategy, param_name):
                        setattr(strategy, param_name, param_value)
                        self.logger.info(f"Parámetro {param_name} actualizado a {param_value} para estrategia {strategy_id}")
                    else:
                        self.logger.warning(f"Parámetro {param_name} no encontrado en estrategia {strategy_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error actualizando parámetros para estrategia {strategy_id}: {e}")
            return False
            
    def get_strategy_parameters(self, strategy_id: str) -> Dict[str, Any]:
        """
        Obtener los parámetros actuales de una estrategia
        
        Args:
            strategy_id: ID de la estrategia
            
        Returns:
            Diccionario con los parámetros de la estrategia
        """
        if strategy_id not in self.strategies:
            self.logger.warning(f"Estrategia {strategy_id} no encontrada para obtener parámetros")
            return {}
            
        try:
            strategy = self.strategies[strategy_id]
            
            # Verificar si la estrategia tiene un método para obtener parámetros
            if hasattr(strategy, 'get_parameters') and callable(getattr(strategy, 'get_parameters')):
                return strategy.get_parameters()
            # Si no tiene método específico, obtener los parámetros del objeto
            else:
                # Obtener parámetros de la estrategia (excluyendo métodos y atributos privados)
                params = {}
                for attr_name in dir(strategy):
                    if not attr_name.startswith('_') and not callable(getattr(strategy, attr_name)):
                        try:
                            value = getattr(strategy, attr_name)
                            # Solo incluir tipos simples que se pueden serializar
                            if isinstance(value, (int, float, str, bool, list, dict, tuple, set)):
                                params[attr_name] = value
                        except Exception:
                            pass
                return params
                
        except Exception as e:
            self.logger.error(f"Error obteniendo parámetros para estrategia {strategy_id}: {e}")
            return {}
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """
        Procesar nueva barra de datos
        Distribuye la barra a las estrategias que están monitoreando este símbolo
        """
        try:
            # Almacenar barra en historial
            if bar.symbol not in self.bars_history:
                self.bars_history[bar.symbol] = []
            
            self.bars_history[bar.symbol].append(bar)
            
            # Limitar historial (OPTIMIZADO)
            max_bars = 1000  # Reducido de 1500 a 1000 para mejor performance
            if len(self.bars_history[bar.symbol]) > max_bars:
                self.bars_history[bar.symbol] = self.bars_history[bar.symbol][-max_bars:]
            
            # Distribuir barra a las estrategias que monitorean este símbolo
            signals = []
            for strategy_id, strategy in self.strategies.items():
                if bar.symbol in self.strategy_symbols.get(strategy_id, set()):
                    try:
                        # Medir tiempo de procesamiento
                        start_time = time.time()
                        
                        # Procesar barra en la estrategia
                        signal = await strategy.on_bar(bar)
                        
                        # Calcular tiempo de procesamiento en ms
                        processing_time_ms = (time.time() - start_time) * 1000
                        
                        # Registrar métricas de rendimiento
                        if performance_monitor:
                            performance_monitor.record_strategy_processing(strategy_id, processing_time_ms)
                        
                        if signal:
                            # Añadir metadatos para identificar la estrategia
                            if not hasattr(signal, 'metadata'):
                                signal.metadata = {}
                            signal.metadata['strategy'] = strategy_id
                            signal.metadata['strategy_name'] = getattr(strategy, 'name', 'unknown')
                            signal.metadata['timestamp'] = datetime.now(ZoneInfo("America/New_York")).isoformat()
                            signal.metadata['processing_time_ms'] = processing_time_ms
                            signals.append(signal)
                            
                            # Almacenar señal en el historial
                            self._store_signal(strategy_id, signal)
                            
                            # Registrar señal generada
                            if performance_monitor:
                                performance_monitor.record_strategy_signal(strategy_id)
                    except Exception as e:
                        self.logger.error(f"Error en estrategia {strategy_id} procesando barra para {bar.symbol}: {e}")
            
            # Verificar conflictos entre señales
            if len(signals) > 1:
                # Ordenar señales por prioridad (si existe) o por timestamp
                signals = self._resolve_signal_conflicts(signals, bar.symbol)
                self.logger.info(f"Resueltos {len(signals)} conflictos de señales para {bar.symbol}")
            
            # Retornar la primera señal (si hay varias, el resto se procesarán en la siguiente iteración)
            return signals[0] if signals else None
            
        except Exception as e:
            self.logger.error(f"Error procesando barra para {bar.symbol}: {e}")
            return None
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """No utilizado directamente, la lógica está en on_bar"""
        return None
    
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """
        Manejar actualizaciones de posición
        Distribuye la actualización a las estrategias relevantes
        """
        try:
            self.positions[position.symbol] = position
            
            # Distribuir actualización a las estrategias que monitorean este símbolo
            signals = []
            for strategy_id, strategy in self.strategies.items():
                if position.symbol in self.strategy_symbols.get(strategy_id, set()):
                    try:
                        # Medir tiempo de procesamiento
                        start_time = time.time()
                        
                        # Procesar actualización de posición
                        signal = await strategy.on_position_update(position)
                        
                        # Calcular tiempo de procesamiento en ms
                        processing_time_ms = (time.time() - start_time) * 1000
                        
                        # Registrar métricas de rendimiento
                        if performance_monitor:
                            performance_monitor.record_strategy_processing(strategy_id, processing_time_ms)
                        
                        if signal:
                            # Añadir metadatos para identificar la estrategia
                            if not hasattr(signal, 'metadata'):
                                signal.metadata = {}
                            signal.metadata['strategy'] = strategy_id
                            signal.metadata['strategy_name'] = getattr(strategy, 'name', 'unknown')
                            signal.metadata['timestamp'] = datetime.now(ZoneInfo("America/New_York")).isoformat()
                            signal.metadata['processing_time_ms'] = processing_time_ms
                            signals.append(signal)
                            
                            # Almacenar señal en el historial
                            self._store_signal(strategy_id, signal)
                            
                            # Registrar señal generada
                            if performance_monitor:
                                performance_monitor.record_strategy_signal(strategy_id)
                    except Exception as e:
                        self.logger.error(f"Error en estrategia {strategy_id} procesando actualización de posición para {position.symbol}: {e}")
            
            # Retornar la primera señal (si hay varias, el resto se procesarán en la siguiente iteración)
            return signals[0] if signals else None
            
        except Exception as e:
            self.logger.error(f"Error manejando actualización de posición para {position.symbol}: {e}")
            return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """
        Determinar si se debe salir de una posición
        Consulta a todas las estrategias que monitorean este símbolo
        """
        try:
            # Consultar a cada estrategia que monitorea este símbolo
            for strategy_id, strategy in self.strategies.items():
                if position.symbol in self.strategy_symbols.get(strategy_id, set()):
                    try:
                        signal = strategy.should_exit(position, current_bar)
                        if signal:
                            # Añadir metadatos para identificar la estrategia
                            if not hasattr(signal, 'metadata'):
                                signal.metadata = {}
                            signal.metadata['strategy'] = strategy_id
                            return signal
                    except Exception as e:
                        self.logger.error(f"Error en estrategia {strategy_id} verificando condiciones de salida para {position.symbol}: {e}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error verificando condiciones de salida para {position.symbol}: {e}")
            return None
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """
        Calcular tamaño de posición
        Delega el cálculo a la estrategia que generó la señal
        """
        try:
            # Identificar la estrategia que generó la señal
            strategy_id = signal.metadata.get('strategy') if hasattr(signal, 'metadata') else None
            
            if strategy_id and strategy_id in self.strategies:
                return self.strategies[strategy_id].calculate_position_size(signal, capital, risk_per_trade)
            else:
                # Si no se puede identificar la estrategia, usar un valor predeterminado seguro
                self.logger.warning(f"No se pudo identificar la estrategia para la señal de {signal.symbol}")
                return int(capital * risk_per_trade / signal.price) if signal.price > 0 else 0
                
        except Exception as e:
            self.logger.error(f"Error calculando tamaño de posición para {signal.symbol}: {e}")
            return 0
    
    def _store_signal(self, strategy_id: str, signal: Signal) -> None:
        """
        Almacenar una señal en el historial de la estrategia
        
        Args:
            strategy_id: ID de la estrategia que generó la señal
            signal: La señal generada
        """
        if strategy_id not in self.signals_history:
            self.signals_history[strategy_id] = []
        
        # Crear una copia de la señal con la información relevante
        signal_info = {
            'symbol': signal.symbol,
            'action': signal.action.name,
            'direction': signal.direction.name if hasattr(signal, 'direction') else 'UNKNOWN',
            'quantity': signal.quantity if hasattr(signal, 'quantity') else 0,
            'price': signal.price if hasattr(signal, 'price') else 0.0,
            'timestamp': signal.metadata.get('timestamp', datetime.now(ZoneInfo("America/New_York")).isoformat()),
            'strategy': strategy_id,
            'strategy_name': signal.metadata.get('strategy_name', 'unknown'),
            'reason': signal.reason if hasattr(signal, 'reason') else ''
        }
        
        # Añadir al historial
        self.signals_history[strategy_id].append(signal_info)
        
        # Limitar el tamaño del historial
        if len(self.signals_history[strategy_id]) > self.max_signals_history:
            self.signals_history[strategy_id] = self.signals_history[strategy_id][-self.max_signals_history:]
    
    def get_signals_history(self, strategy_id: str = None) -> Dict[str, List[Dict]]:
        """
        Obtener el historial de señales
        
        Args:
            strategy_id: ID de la estrategia (opcional). Si no se especifica, devuelve todas las señales.
            
        Returns:
            Diccionario con el historial de señales por estrategia
        """
        if strategy_id:
            return {strategy_id: self.signals_history.get(strategy_id, [])}
        else:
            return self.signals_history
    
    def _resolve_signal_conflicts(self, signals: List[Signal], symbol: str) -> List[Signal]:
        """
        Resolver conflictos entre señales de diferentes estrategias para el mismo símbolo
        
        Args:
            signals: Lista de señales en conflicto
            symbol: Símbolo para el que se generaron las señales
            
        Returns:
            Lista de señales ordenada por prioridad
        """
        if not signals:
            return []
        
        # Verificar si hay conflictos reales (señales contradictorias)
        buy_signals = [s for s in signals if s.side == OrderSide.BUY]
        sell_signals = [s for s in signals if s.side == OrderSide.SELL]
        
        # Si todas las señales son del mismo lado, no hay conflicto real
        if not buy_signals or not sell_signals:
            # Ordenar por timestamp para mantener consistencia
            return sorted(signals, key=lambda s: s.metadata.get('timestamp', ''))
        
        # Hay conflicto real entre señales de compra y venta
        self.logger.warning(f"Conflicto detectado para {symbol}: {len(buy_signals)} señales de compra y {len(sell_signals)} señales de venta")
        
        # Estrategia de resolución: priorizar señales de salida (SELL) sobre entradas (BUY)
        # Esto es más conservador y evita quedar atrapado en posiciones
        if sell_signals:
            # Ordenar señales de venta por timestamp y devolver la más reciente primero
            result = sorted(sell_signals, key=lambda s: s.metadata.get('timestamp', ''), reverse=True)
            
            # Registrar la decisión tomada
            chosen_signal = result[0]
            chosen_strategy = chosen_signal.metadata.get('strategy', 'unknown')
            self.logger.info(f"Resolución de conflicto para {symbol}: se eligió señal {chosen_signal.type} de estrategia {chosen_strategy}")
            
            return result
        else:
            # No deberíamos llegar aquí si la lógica anterior es correcta
            return sorted(signals, key=lambda s: s.metadata.get('timestamp', ''))
    
    def _get_strategy_priority(self, strategy_id: str) -> int:
        """
        Obtener la prioridad de una estrategia para resolver conflictos
        Prioridad más alta = número más bajo
        """
        # Implementación básica: todas las estrategias tienen la misma prioridad
        # Se puede extender para asignar prioridades personalizadas a cada estrategia
        return 1
