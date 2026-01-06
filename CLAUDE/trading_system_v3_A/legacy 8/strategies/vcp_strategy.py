# strategies/vcp_strategy.py
"""
VCP (Volatility Contraction Pattern) Strategy - Intraday Version
Adaptación del patrón VCP de Mark Minervini para trading intraday en smallcaps

Características VCP Intraday:
1. 2-4 contracciones con volatilidad decreciente (en timeframe 5min)
2. Cada pullback más shallow que el anterior
3. Volumen se seca durante contracciones
4. Breakout con volumen aumentado
5. Soporte en EMAs clave (9, 21)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, time
import logging

try:
    from .base import BaseStrategy
    from core.interfaces import Signal, SignalType, Position, MarketData
    from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from strategies.base import BaseStrategy
    from core.interfaces import Signal, SignalType, Position, MarketData
    from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config

logger = logging.getLogger(__name__)

class IntradayVCPDetector:
    """Detector VCP adaptado para timeframes intraday"""
    
    def __init__(self, config: Dict[str, Any]):
        # Ensure all config values are properly typed
        self.config = {}
        for key, value in config.items():
            if isinstance(value, str) and value.strip():
                try:
                    # Clean inline comments (everything after #)
                    clean_value = value.split('#')[0].strip()
                    if not clean_value:
                        self.config[key] = value
                        continue
                    
                    # Try to convert to int first
                    if '.' not in clean_value and clean_value.replace('-', '').isdigit():
                        self.config[key] = int(clean_value)
                    elif clean_value.replace('-', '').replace('.', '', 1).isdigit():
                        self.config[key] = float(clean_value)
                    else:
                        self.config[key] = clean_value
                except ValueError:
                    self.config[key] = value
            else:
                self.config[key] = value
        
        self.logger = logging.getLogger(f"{__name__}.IntradayVCPDetector")
    
    def detect_pattern(self, bars: List[MarketData]) -> Optional[Dict[str, Any]]:
        """Detecta patrón VCP en datos intraday"""
        if len(bars) < self.config['min_bars_required']:
            return None
        
        df = self._to_dataframe(bars)
        
        # 1. Encontrar contracciones
        contractions = self._find_contractions(df)
        if len(contractions) < self.config['min_contractions']:
            return None
        
        # 2. Validar secuencia de contracciones
        if not self._validate_contraction_sequence(contractions):
            return None
        
        # 3. Verificar soporte en EMAs
        ema_support = self._check_ema_support(df)
        
        # 4. Detectar setup de breakout
        breakout_setup = self._detect_breakout_setup(df, contractions)
        
        if breakout_setup:
            return {
                'contractions': contractions,
                'ema_support': ema_support,
                'breakout_price': breakout_setup['breakout_price'],
                'volume_quality': breakout_setup['volume_quality'],
                'pattern_strength': self._calculate_strength(contractions, ema_support)
            }
        
        return None
    
    def _to_dataframe(self, bars: List[MarketData]) -> pd.DataFrame:
        """Convierte datos a DataFrame con indicadores"""
        data = []
        for bar in bars:
            data.append({
                'timestamp': bar.timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        
        # EMAs para soporte intraday
        df['ema_9'] = df['close'].ewm(span=9).mean()
        df['ema_21'] = df['close'].ewm(span=21).mean()
        
        # Volatilidad intraday
        df['range_pct'] = (df['high'] - df['low']) / df['close']
        df['volatility'] = df['range_pct'].rolling(window=10).mean()
        
        # Volumen promedio
        df['volume_ma'] = df['volume'].rolling(window=self.config['volume_ma_period']).mean()
        
        return df
    
    def _find_contractions(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Encuentra contracciones en el patrón"""
        contractions = []
        
        # Buscar pivots locales
        window = self.config['pivot_window']
        local_highs = []
        local_lows = []
        
        for i in range(window, len(df) - window):
            # Pivot high
            if df['high'].iloc[i] == df['high'].iloc[i-window:i+window+1].max():
                local_highs.append({'idx': i, 'price': df['high'].iloc[i]})
            
            # Pivot low
            if df['low'].iloc[i] == df['low'].iloc[i-window:i+window+1].min():
                local_lows.append({'idx': i, 'price': df['low'].iloc[i]})
        
        # Formar contracciones (high to low pairs)
        for i, high in enumerate(local_highs[:-1]):
            # Buscar siguiente low
            next_lows = [low for low in local_lows if low['idx'] > high['idx']]
            if not next_lows:
                continue
            
            next_low = min(next_lows, key=lambda x: x['idx'])
            
            # Calcular métricas de contracción
            depth = (high['price'] - next_low['price']) / high['price']
            duration = next_low['idx'] - high['idx']
            
            if depth >= self.config['min_contraction_depth'] and duration >= self.config['min_contraction_duration']:
                # Analizar volumen durante contracción
                contraction_data = df.iloc[high['idx']:next_low['idx']+1]
                avg_volume = contraction_data['volume'].mean()
                avg_volatility = contraction_data['volatility'].mean()
                
                contractions.append({
                    'start_idx': high['idx'],
                    'end_idx': next_low['idx'],
                    'high_price': high['price'],
                    'low_price': next_low['price'],
                    'depth_pct': depth,
                    'duration': duration,
                    'avg_volume': avg_volume,
                    'avg_volatility': avg_volatility
                })
        
        return contractions[-self.config['max_contractions']:] # Solo las más recientes
    
    def _validate_contraction_sequence(self, contractions: List[Dict[str, Any]]) -> bool:
        """Valida que las contracciones sigan reglas VCP"""
        if len(contractions) < 2:
            return False
        
        # Cada contracción debe ser más shallow
        for i in range(1, len(contractions)):
            if contractions[i]['depth_pct'] >= contractions[i-1]['depth_pct']:
                return False
        
        # Volumen debe decrecer
        for i in range(1, len(contractions)):
            vol_ratio = contractions[i]['avg_volume'] / contractions[i-1]['avg_volume']
            if vol_ratio > self.config['volume_decrease_threshold']:
                return False
        
        return True
    
    def _check_ema_support(self, df: pd.DataFrame) -> bool:
        """Verifica soporte en EMAs clave"""
        recent_bars = df.tail(10)
        
        support_count = 0
        total_checks = 0
        
        for _, row in recent_bars.iterrows():
            if pd.isna(row['ema_9']) or pd.isna(row['ema_21']):
                continue
            
            total_checks += 1
            
            # Precio cerca de EMA9 o EMA21
            ema9_distance = abs(row['low'] - row['ema_9']) / row['close']
            ema21_distance = abs(row['low'] - row['ema_21']) / row['close']
            
            if ema9_distance <= 0.02 or ema21_distance <= 0.02:  # Dentro del 2%
                support_count += 1
        
        return (support_count / total_checks) >= 0.3 if total_checks > 0 else False
    
    def _detect_breakout_setup(self, df: pd.DataFrame, contractions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Detecta setup de breakout"""
        if not contractions:
            return None
        
        # Último pivot high como nivel de breakout
        last_contraction = contractions[-1]
        breakout_price = last_contraction['high_price']
        
        # Precio actual debe estar cerca del breakout
        current_price = df['close'].iloc[-1]
        distance_to_breakout = (breakout_price - current_price) / current_price
        
        if distance_to_breakout > self.config['max_distance_to_breakout']:
            return None
        
        # Analizar calidad del volumen reciente
        recent_volume = df['volume'].tail(5).mean()
        avg_volume = df['volume_ma'].iloc[-1]
        volume_quality = recent_volume / avg_volume if avg_volume > 0 else 0
        
        return {
            'breakout_price': breakout_price,
            'current_price': current_price,
            'distance_pct': distance_to_breakout,
            'volume_quality': volume_quality
        }
    
    def _calculate_strength(self, contractions: List[Dict[str, Any]], ema_support: bool) -> float:
        """Calcula fuerza del patrón (0-1)"""
        score = 0.0
        
        # Número de contracciones
        if len(contractions) >= 3:
            score += 0.3
        elif len(contractions) == 2:
            score += 0.2
        
        # Contracciones decrecientes
        if len(contractions) >= 2:
            depths = [c['depth_pct'] for c in contractions]
            if all(depths[i] < depths[i-1] for i in range(1, len(depths))):
                score += 0.3
        
        # Soporte en EMAs
        if ema_support:
            score += 0.2
        
        # Última contracción muy tight
        if contractions and contractions[-1]['depth_pct'] <= 0.03:  # Menos del 3%
            score += 0.2
        
        return min(score, 1.0)

class VCPStrategy(BaseStrategy):
    """
    Estrategia VCP para trading intraday en smallcaps
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # Initialize base first  
        super().__init__("VCPStrategy", parameters)
        
        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()
        
        # Cargar configuración desde config.ini
        config_params = self._load_strategy_config('VCP_STRATEGY', {
            'min_bars_required': 50,
            'min_contractions': 2,
            'max_contractions': 4,
            'min_contraction_depth': 0.02,
            'min_contraction_duration': 3,
            'volume_decrease_threshold': 0.8,
            'max_distance_to_breakout': 0.005,
            'pivot_window': 3,
            'volume_ma_period': 20,
            'breakout_volume_multiplier': 1.3
        })
        
        # Combinar con parámetros pasados
        if parameters:
            config_params.update(parameters)
        
        # Convert string values to appropriate types (fix config.ini parsing with inline comments)
        for key, value in config_params.items():
            if isinstance(value, str) and value.strip():
                try:
                    # Clean inline comments (everything after #)
                    clean_value = value.split('#')[0].strip()
                    if not clean_value:
                        continue
                    
                    # Try to convert to int first
                    if '.' not in clean_value and clean_value.replace('-', '').isdigit():
                        config_params[key] = int(clean_value)
                    elif clean_value.replace('-', '').replace('.', '', 1).isdigit():
                        config_params[key] = float(clean_value)
                except ValueError:
                    # Keep as string if conversion fails
                    pass
        
        # Update parameters
        self._parameters.update(config_params)
        
        self.detector = IntradayVCPDetector(self._parameters)
        self.pattern_cache = {}  # Cache de patrones detectados
        self.cooldown_symbols = {}  # Símbolos en cooldown
        
        self.logger.info(f"✅ VCP Strategy initialized (Intraday) with centralized stop loss management")
        self.logger.info(f"   Min contractions: {self._parameters['min_contractions']}")
        self.logger.info(f"   Min bars required: {self._parameters['min_bars_required']}")
        self.logger.info(f"   Breakout volume multiplier: {self._parameters['breakout_volume_multiplier']}x")
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analiza barra para detectar señales VCP"""
        try:
            symbol = bar.symbol
            
            # Verificar cooldown
            if self._is_in_cooldown(symbol):
                return None
            
            # Verificar filtros básicos
            if not self._passes_basic_filters(bar):
                return None
            
            # Obtener historial de barras
            min_bars_required = int(self._parameters['min_bars_required'])
            if symbol not in self.bars_history or len(self.bars_history[symbol]) < min_bars_required:
                return None
            
            bars = self.bars_history[symbol]
            
            # Detectar patrón VCP
            pattern = self.detector.detect_pattern(bars)
            if not pattern:
                return None
            
            # Verificar si estamos en setup de breakout
            if self._is_breakout_signal(bar, pattern):
                return await self._create_entry_signal(bar, pattern)
            
            return None
            
        except TypeError as e:
            if "'<' not supported between instances of 'int' and 'str'" in str(e):
                self.logger.error(f"❌ TypeError in _analyze_bar for {bar.symbol}: {e}")
                self.logger.error(f"   Parameters types: {[(k, type(v), v) for k, v in self._parameters.items() if isinstance(v, str) or (isinstance(v, (int, float)) and k in ['min_bars_required', 'min_contractions'])]}")
                return None
            else:
                raise
        except Exception as e:
            self.logger.error(f"❌ Error in _analyze_bar for {bar.symbol}: {e}")
            return None
    
    def _passes_basic_filters(self, bar: MarketData) -> bool:
        """Filtros básicos para smallcaps"""
        try:
            # Usar parámetros globales con conversión explícita de tipos
            min_price = float(self._parameters.get('min_price', 1.0))
            max_price = float(self._parameters.get('max_price', 15.0))
            min_volume = int(self._parameters.get('min_volume', 10000))
            
            if not (min_price <= bar.close <= max_price):
                return False
            
            if bar.volume < min_volume:
                return False
            
            # Horario de trading
            current_time = datetime.now().time()
            market_open = time(9, 30)
            market_close = time(15, 30)  # Evitar últimos 30min
            
            if not (market_open <= current_time <= market_close):
                return False
            
            return True
            
        except (TypeError, ValueError) as e:
            self.logger.error(f"❌ Error in _passes_basic_filters for {bar.symbol}: {e}")
            self.logger.error(f"   min_price: {self._parameters.get('min_price')} (type: {type(self._parameters.get('min_price'))})")
            self.logger.error(f"   max_price: {self._parameters.get('max_price')} (type: {type(self._parameters.get('max_price'))})")
            self.logger.error(f"   min_volume: {self._parameters.get('min_volume')} (type: {type(self._parameters.get('min_volume'))})")
            return False
    
    def _is_breakout_signal(self, bar: MarketData, pattern: Dict[str, Any]) -> bool:
        """Verifica si tenemos señal de breakout"""
        try:
            breakout_price = pattern['breakout_price']
            current_price = bar.close
            
            # Precio debe romper nivel de breakout
            if current_price <= breakout_price:
                return False
            
            # Verificar volumen de breakout
            volume_quality = pattern['volume_quality']
            breakout_volume_multiplier = float(self._parameters['breakout_volume_multiplier'])
            if volume_quality < breakout_volume_multiplier:
                return False
            
            # Patrón debe tener fuerza mínima
            if pattern['pattern_strength'] < 0.5:
                return False
            
            return True
            
        except (TypeError, ValueError) as e:
            self.logger.error(f"❌ Error in _is_breakout_signal for {bar.symbol}: {e}")
            self.logger.error(f"   breakout_volume_multiplier: {self._parameters.get('breakout_volume_multiplier')} (type: {type(self._parameters.get('breakout_volume_multiplier'))})")
            return False
    
    async def _create_entry_signal(self, bar: MarketData, pattern: Dict[str, Any]) -> Signal:
        """Crea señal de entrada"""
        symbol = bar.symbol
        entry_price = bar.close
        
        # Calcular stop loss
        last_contraction = pattern['contractions'][-1]
        support_level = last_contraction['low_price']
        stop_loss_pct = self._parameters.get('stop_loss_pct', 0.05)
        stop_loss = max(support_level, entry_price * (1 - stop_loss_pct))
        
        # Take profit
        take_profit_pct = self._parameters.get('take_profit_pct', 0.08)
        take_profit = entry_price * (1 + take_profit_pct)
        
        # Position size
        position_value = self._parameters.get('max_position_value', 200.0)
        quantity = int(position_value / entry_price)
        
        # Añadir cooldown
        self._add_cooldown(symbol)
        
        self.logger.info(f"🚀 VCP BREAKOUT: {symbol} @ ${entry_price:.2f}")
        self.logger.info(f"   Pattern strength: {pattern['pattern_strength']:.2f}")
        self.logger.info(f"   Volume quality: {pattern['volume_quality']:.1f}x")
        self.logger.info(f"   Stop loss: ${stop_loss:.2f}")
        self.logger.info(f"   Take profit: ${take_profit:.2f}")
        
        return Signal(
            symbol=symbol,
            signal_type=SignalType.ENTRY_LONG,
            price=entry_price,
            quantity=quantity,
            timestamp=datetime.now(),
            confidence=pattern['pattern_strength'],
            strategy_name="VCPStrategy",
            metadata={
                'pattern_type': 'vcp_breakout',
                'contractions_count': len(pattern['contractions']),
                'ema_support': pattern['ema_support'],
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'volume_quality': pattern['volume_quality']
            }
        )
    
    def _is_in_cooldown(self, symbol: str) -> bool:
        """Verifica si símbolo está en cooldown"""
        if symbol not in self.cooldown_symbols:
            return False
        
        cooldown_time = self._parameters.get('cooldown_minutes', 30)
        elapsed = (datetime.now() - self.cooldown_symbols[symbol]).total_seconds() / 60
        
        return elapsed < cooldown_time
    
    def _add_cooldown(self, symbol: str):
        """Añade símbolo a cooldown"""
        self.cooldown_symbols[symbol] = datetime.now()
    
    def on_position_update(self, symbol: str, position: Position):
        """Handle position updates"""
        self.positions[symbol] = position
        self.logger.debug(f"Position updated for {symbol}: {position.quantity} shares @ ${position.avg_price:.2f}")
    
    def should_exit(self, symbol: str, current_bar: MarketData, position: Position) -> Optional[Signal]:
        """Check if we should exit current position (handled by external risk management)"""
        return None
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Información de la estrategia"""
        return {
            'name': 'VCPStrategy',
            'type': 'Intraday VCP Breakout',
            'timeframe': '1m-5m',
            'description': 'Detecta patrones VCP intraday con contracciones decrecientes y breakout con volumen',
            'parameters': {
                'min_contractions': self._parameters['min_contractions'],
                'breakout_volume_multiplier': self._parameters['breakout_volume_multiplier'],
                'stop_loss_pct': self._parameters.get('stop_loss_pct', 0.05),
                'take_profit_pct': self._parameters.get('take_profit_pct', 0.08)
            }
        }

# Factory function
def get_strategy_class():
    return VCPStrategy

if __name__ == "__main__":
    strategy = VCPStrategy()
    info = strategy.get_strategy_info()
    
    print("🧪 VCP Strategy Test (Intraday)")
    print("=" * 50)
    print(f"Strategy: {info['name']}")
    print(f"Type: {info['type']}")
    print(f"Timeframe: {info['timeframe']}")
    print(f"Description: {info['description']}")
    print("\nKey Parameters:")
    for key, value in info['parameters'].items():
        print(f"  {key}: {value}")
    print("=" * 50)
    print("✅ VCP Strategy ready for intraday trading!")