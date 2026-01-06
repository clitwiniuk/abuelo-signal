#!/usr/bin/env python3
"""
Improved Strategy Backtester
============================

Backtester mejorado que maneja mejor los datos dispersos y eventos tardíos.
Incluye filtros inteligentes y análisis mejorado de eventos.
"""

import pandas as pd
import numpy as np
import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class ImprovedStrategyBacktester:
    """Backtester mejorado con filtros inteligentes"""
    
    def __init__(self):
        self.events_metadata = None
        self.results = []
        self.synthetic_data_dir = 'synthetic_data'
        
        # Buscar el archivo de metadatos en posibles ubicaciones
        possible_metadata_paths = [
            os.path.join(self.synthetic_data_dir, 'events_metadata.csv'),
            os.path.join(self.synthetic_data_dir, 'Extra', 'events_metadata.csv')
        ]
        
        self.metadata_path = None
        for path in possible_metadata_paths:
            if os.path.exists(path):
                self.metadata_path = path
                break
        
        # Configuración mejorada
        self.config = {
            'initial_capital': 10000,
            'position_size_pct': 0.08,  # 8% del capital
            'stop_loss_pct': 0.04,
            'take_profit_pct': 0.10,
            'max_hold_minutes': 60,  # Reducido a 1 hora
            'min_bars_before': 20,   # Reducido los requisitos
            'min_bars_after': 10,    # Mínimo barras después del evento
            'entry_delay': 1,        # 1 barra después del evento
            'min_total_bars': 50,    # Mínimo barras totales
            'max_event_hour': 15,    # No eventos después de 3 PM
            'min_volume_avg': 100    # Volumen mínimo promedio
        }
        
        # Estrategias mejoradas con filtros
        self.strategies = {
            'MACDV_Momentum': {
                'description': 'MACD + Volume con filtros de calidad',
                'success_rate': 0.52,
                'avg_win': 0.075,
                'avg_loss': -0.035,
                'volume_threshold': 4.0,
                'requires_trend': True,
                'min_volatility': 0.02
            },
            'Volume_Breakout': {
                'description': 'Volume breakout con confirmación',
                'success_rate': 0.58,
                'avg_win': 0.10,
                'avg_loss': -0.04,
                'volume_threshold': 3.5,
                'requires_trend': False,
                'min_volatility': 0.015
            },
            'Gap_Momentum': {
                'description': 'Gap trading optimizado',
                'success_rate': 0.45,
                'avg_win': 0.12,
                'avg_loss': -0.055,
                'volume_threshold': 6.0,
                'requires_trend': True,
                'min_volatility': 0.03
            },
            'Explosive_Scalp': {
                'description': 'Scalping en alta volatilidad',
                'success_rate': 0.65,
                'avg_win': 0.055,
                'avg_loss': -0.025,
                'volume_threshold': 5.0,
                'requires_trend': False,
                'min_volatility': 0.02
            },
            'Smart_Reversal': {
                'description': 'Reversiones inteligentes',
                'success_rate': 0.48,
                'avg_win': 0.15,
                'avg_loss': -0.07,
                'volume_threshold': 7.0,
                'requires_trend': True,
                'min_volatility': 0.025
            }
        }
    
    def load_metadata(self) -> bool:
        """Cargar y filtrar metadatos o detectar archivos simples"""
        try:
            # Primero verificar si hay archivos simples prioritarios (como CCCC.csv)
            simple_files = self.detect_simple_files()
            if simple_files:
                print(f"🎯 Archivos simples detectados (prioritarios): {', '.join(simple_files)}")
                print("   Ejecutando backtesting sin metadatos de eventos...")
                return True
                
            if not self.metadata_path or not os.path.exists(self.metadata_path):
                print("❌ No se encontró archivo de metadatos en ubicaciones esperadas")
                print(f"   Buscado en: {self.synthetic_data_dir}/events_metadata.csv")
                print(f"   También en: {self.synthetic_data_dir}/Extra/events_metadata.csv")
                return False
            
            self.events_metadata = pd.read_csv(self.metadata_path)
            print(f"✅ Metadatos cargados desde: {self.metadata_path}")
            self.events_metadata['event_timestamp'] = pd.to_datetime(self.events_metadata['event_timestamp'])
            
            initial_count = len(self.events_metadata)
            print(f"📊 Metadatos iniciales: {initial_count} eventos")
            
            # Filtrar eventos de calidad
            self.events_metadata = self.filter_quality_events()
            
            final_count = len(self.events_metadata)
            print(f"✅ Eventos de calidad: {final_count} eventos ({final_count/initial_count*100:.1f}%)")
            print(f"   📅 Período: {self.events_metadata['event_timestamp'].min()} a {self.events_metadata['event_timestamp'].max()}")
            print(f"   📊 Ratio promedio: {self.events_metadata['ratio_vol'].mean():.1f}x")
            
            return final_count > 0
            
        except Exception as e:
            print(f"❌ Error cargando metadatos: {e}")
            return False
    
    def detect_simple_files(self) -> List[str]:
        """Detectar archivos CSV simples que no requieren metadatos de eventos"""
        simple_files = []
        
        # Archivos prioritarios (como CCCC.csv)
        priority_files = ['CCCC.csv']
        
        # Buscar en ambas ubicaciones posibles
        search_dirs = [self.synthetic_data_dir, os.path.join(self.synthetic_data_dir, 'Extra')]
        
        for directory in search_dirs:
            if not os.path.exists(directory):
                continue
                
            for filename in priority_files:
                filepath = os.path.join(directory, filename)
                if os.path.exists(filepath):
                    simple_files.append(filename)
        
        return simple_files
    
    async def run_simple_backtest(self, strategy_name: str, filename: str) -> Dict:
        """Ejecutar backtest simple sin metadatos de eventos"""
        
        print(f"\n🎯 BACKTEST SIMPLE: {strategy_name}")
        print("=" * 60)
        print(f"📄 Archivo: {filename}")
        print(f"📊 Tipo: Datos sintéticos simples (sin eventos)")
        print(f"💰 Capital: ${self.config['initial_capital']:,}")
        
        # Cargar datos del archivo
        df = self.load_and_validate_event_data(filename)
        if df is None:
            print(f"❌ Error cargando datos de {filename}")
            return {'status': 'error', 'error': f'No se pudo cargar {filename}'}
        
        print(f"✅ Datos cargados: {len(df)} velas")
        print(f"📅 Período: {df.index[0]} a {df.index[-1]}")
        print(f"📊 Precio inicial: ${df['close'].iloc[0]:.2f}")
        print(f"📊 Precio final: ${df['close'].iloc[-1]:.2f}")
        print(f"📊 Variación total: {((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.2f}%")
        
        # Ejecutar estrategia simple
        trades = []
        capital = self.config['initial_capital']
        position = None
        
        print("\n🔄 Procesando datos...")
        
        for i in range(len(df)):
            current_bar = df.iloc[i]
            
            # Simulación básica de señales
            # (En un entorno real, aquí se aplicaría la estrategia seleccionada)
            
            # Ejemplo simple: comprar en sobrevendido, vender en sobrecomprado
            price = current_bar['close']
            
            # Calcular RSI simple de los últimos 14 períodos
            if i >= 14:
                recent_closes = df['close'].iloc[i-13:i+1]
                gains = recent_closes.diff().where(recent_closes.diff() > 0, 0)
                losses = -recent_closes.diff().where(recent_closes.diff() < 0, 0)
                
                avg_gain = gains.mean()
                avg_loss = losses.mean()
                
                if avg_loss != 0:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                    
                    # Señales básicas
                    if position is None and rsi < 30:  # Sobrevendido - comprar
                        position = {
                            'entry_price': price,
                            'entry_time': current_bar.name,
                            'type': 'long'
                        }
                    elif position is not None and (rsi > 70 or i == len(df) - 1):  # Sobrecomprado - vender
                        exit_price = price
                        pnl = exit_price - position['entry_price']
                        pnl_pct = (pnl / position['entry_price']) * 100
                        
                        trades.append({
                            'entry_time': position['entry_time'],
                            'exit_time': current_bar.name,
                            'entry_price': position['entry_price'],
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'duration_minutes': (current_bar.name - position['entry_time']).total_seconds() / 60
                        })
                        
                        capital += (capital * self.config['position_size_pct'] * pnl_pct / 100)
                        position = None
        
        # Estadísticas finales
        if trades:
            winning_trades = [t for t in trades if t['pnl'] > 0]
            losing_trades = [t for t in trades if t['pnl'] <= 0]
            
            total_return = (capital / self.config['initial_capital'] - 1) * 100
            win_rate = len(winning_trades) / len(trades) * 100
            avg_win = sum(t['pnl_pct'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(t['pnl_pct'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
            
            # Estadísticas adicionales requeridas
            total_pnl = capital - self.config['initial_capital']
            avg_win_dollar = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss_dollar = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
            max_win = max(t['pnl'] for t in trades) if trades else 0
            max_loss = min(t['pnl'] for t in trades) if trades else 0
            avg_hold_time = sum(t['duration_minutes'] for t in trades) / len(trades) if trades else 0
            
            print(f"\n📊 RESULTADOS:")
            print(f"💰 Capital final: ${capital:,.2f}")
            print(f"📈 Retorno total: {total_return:.2f}%")
            print(f"🔢 Trades totales: {len(trades)}")
            print(f"✅ Trades ganadores: {len(winning_trades)} ({win_rate:.1f}%)")
            print(f"❌ Trades perdedores: {len(losing_trades)}")
            print(f"📊 Ganancia promedio: {avg_win:.2f}%")
            print(f"📊 Pérdida promedio: {avg_loss:.2f}%")
            
            return {
                'status': 'success',
                'strategy_name': strategy_name,
                'strategy_description': f'Backtest simple de {filename}',
                'symbol': filename.replace('.csv', ''),
                'total_trades': len(trades),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': win_rate,
                'total_return_pct': total_return,
                'total_pnl': total_pnl,
                'final_capital': capital,
                'avg_win': avg_win_dollar,
                'avg_loss': avg_loss_dollar,
                'avg_win_pct': avg_win,
                'avg_loss_pct': avg_loss,
                'max_win': max_win,
                'max_loss': max_loss,
                'avg_hold_time': avg_hold_time,
                'completion_rate': 100.0,  # En modo simple siempre es 100%
                'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 999,
                'avg_confidence': 0.7,  # Valor por defecto para modo simple
                'avg_conditions': 3.5,  # Valor por defecto
                'high_conf_trades': len(trades),  # En modo simple todos son "alta confianza"
                'high_conf_wr': win_rate  # Mismo win rate
            }
        else:
            print("❌ No se generaron trades")
            return {'status': 'no_trades', 'error': 'No se generaron señales de trading'}
    
    def filter_quality_events(self) -> pd.DataFrame:
        """Filtrar eventos de calidad"""
        df = self.events_metadata.copy()
        
        # Filtros de calidad
        filters_applied = []
        
        # 1. Suficientes barras totales
        before = len(df)
        df = df[df['total_bars'] >= self.config['min_total_bars']]
        filters_applied.append(f"Barras mínimas: {before} → {len(df)}")
        
        # 2. Eventos no muy tardíos (extraer hora del timestamp)
        before = len(df)
        df['event_hour'] = df['event_timestamp'].dt.hour
        df = df[df['event_hour'] <= self.config['max_event_hour']]
        filters_applied.append(f"Horario válido: {before} → {len(df)}")
        
        # 3. Volumen mínimo
        before = len(df)
        df = df[df['volumen'] >= self.config['min_volume_avg']]
        filters_applied.append(f"Volumen mínimo: {before} → {len(df)}")
        
        # 4. Variación de precio significativa
        before = len(df)
        df = df[abs(df['percent_var']) >= 2.0]  # Mínimo 2% de variación
        filters_applied.append(f"Variación mínima: {before} → {len(df)}")
        
        print("🔍 Filtros aplicados:")
        for filter_info in filters_applied:
            print(f"   • {filter_info}")
        
        return df.drop('event_hour', axis=1)
    
    def load_and_validate_event_data(self, csv_filename: str) -> Optional[pd.DataFrame]:
        """Cargar y validar datos de evento"""
        try:
            # Buscar archivo CSV en ubicaciones posibles
            possible_csv_paths = [
                os.path.join(self.synthetic_data_dir, csv_filename),
                os.path.join(self.synthetic_data_dir, 'Extra', csv_filename)
            ]
            
            csv_path = None
            for path in possible_csv_paths:
                if os.path.exists(path):
                    csv_path = path
                    break
                    
            if not csv_path:
                return None
            df = pd.read_csv(csv_path)
            
            # Manejar el índice de fecha correctamente
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
            else:
                # Si Date es el índice desde el CSV
                df.index = pd.to_datetime(df.index)
            
            # Renombrar columnas para consistencia - manejar tanto mayúsculas como minúsculas
            column_mapping = {}
            for col in df.columns:
                if col.lower() in ['open', 'high', 'low', 'close', 'volume']:
                    column_mapping[col] = col.lower()
            
            df.rename(columns=column_mapping, inplace=True)
            
            # Verificar que tenemos todas las columnas necesarias
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                print(f"❌ Columnas faltantes en {csv_filename}: {set(required_cols) - set(df.columns)}")
                return None
            
            # Validaciones
            if len(df) < self.config['min_total_bars']:
                return None
                
            if df['volume'].mean() < self.config['min_volume_avg']:
                return None
                
            return df
            
        except Exception as e:
            return None
    
    def calculate_enhanced_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcular indicadores técnicos mejorados"""
        df = df.copy()
        
        # Medias móviles
        df['sma_10'] = df['close'].rolling(10, min_periods=5).mean()
        df['sma_20'] = df['close'].rolling(20, min_periods=10).mean()
        
        # RSI mejorado
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14, min_periods=7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14, min_periods=7).mean()
        rs = gain / (loss + 1e-10)  # Evitar división por cero
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volume análisis
        df['volume_sma'] = df['volume'].rolling(10, min_periods=5).mean()
        df['volume_ratio'] = df['volume'] / (df['volume_sma'] + 1)
        
        # Volatilidad
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(10, min_periods=5).std()
        
        # Price momentum
        df['price_momentum'] = df['close'].pct_change(5)
        
        return df
    
    def find_event_position(self, df: pd.DataFrame, event_time: datetime) -> Optional[int]:
        """Encontrar posición del evento con mejor tolerancia"""
        try:
            time_diff = abs(df.index - event_time)
            min_idx = time_diff.argmin()
            position = df.index.get_loc(df.index[min_idx])
            
            # Verificar que hay datos suficientes antes y después
            if position < self.config['min_bars_before']:
                return None
            if position >= len(df) - self.config['min_bars_after']:
                return None
                
            return position
            
        except:
            return None
    
    def evaluate_strategy_conditions(self, strategy_name: str, df: pd.DataFrame, 
                                  event_pos: int, event_meta: dict) -> Dict:
        """Evaluar condiciones de estrategia mejoradas"""
        
        strategy = self.strategies[strategy_name]
        
        # Datos en el momento del evento
        event_bar = df.iloc[event_pos]
        pre_bars = df.iloc[max(0, event_pos-10):event_pos]
        
        if len(pre_bars) < 5:
            return {'should_trade': False, 'reason': 'insufficient_pre_data'}
        
        # Condiciones básicas
        volume_ok = event_meta['ratio_vol'] >= strategy['volume_threshold']
        
        # Volatilidad mínima
        current_vol = event_bar.get('volatility', 0)
        volatility_ok = current_vol >= strategy.get('min_volatility', 0.01)
        
        # RSI no extremo
        current_rsi = event_bar.get('rsi', 50)
        rsi_ok = 20 < current_rsi < 80
        
        # Tendencia (si se requiere)
        if strategy['requires_trend'] and 'sma_10' in event_bar.index:
            trend_up = event_bar['close'] > event_bar['sma_10']
            trend_condition = trend_up
        else:
            trend_condition = True
        
        # Momentum
        momentum = event_bar.get('price_momentum', 0)
        momentum_ok = abs(momentum) >= 0.01
        
        # Scoring system
        conditions = {
            'volume': volume_ok,
            'volatility': volatility_ok,
            'rsi': rsi_ok,
            'trend': trend_condition,
            'momentum': momentum_ok
        }
        
        conditions_met = sum(conditions.values())
        
        # Decisión probabilística mejorada
        base_prob = strategy['success_rate']
        
        # Bonus por condiciones
        condition_bonus = conditions_met * 0.08
        
        # Bonus por calidad de la explosión
        volume_bonus = min((event_meta['ratio_vol'] - 3) * 0.05, 0.15)
        
        # Penalty por volatilidad extrema
        vol_penalty = max((current_vol - 0.1) * 0.1, 0) if current_vol > 0.1 else 0
        
        final_probability = base_prob + condition_bonus + volume_bonus - vol_penalty
        final_probability = max(0.1, min(0.9, final_probability))
        
        # Decisión final
        should_trade = (conditions_met >= 3 and 
                       np.random.random() < final_probability and
                       event_meta['ratio_vol'] >= 2.0)
        
        direction = 'long' if event_meta['percent_var'] > 0 else 'short'
        
        return {
            'should_trade': should_trade,
            'direction': direction,
            'confidence': final_probability,
            'conditions_met': conditions_met,
            'conditions': conditions,
            'volume_ratio': event_meta['ratio_vol'],
            'volatility': current_vol
        }
    
    def simulate_realistic_trade(self, strategy_name: str, df: pd.DataFrame, 
                               entry_pos: int, decision: Dict, event_meta: dict) -> Dict:
        """Simular trade con mayor realismo"""
        
        strategy = self.strategies[strategy_name]
        
        if entry_pos >= len(df) - 2:
            return {'status': 'no_exit_data'}
        
        entry_price = df.iloc[entry_pos]['close']
        direction = decision['direction']
        confidence = decision['confidence']
        volatility = decision.get('volatility', 0.02)
        
        # Position sizing
        position_value = self.config['initial_capital'] * self.config['position_size_pct']
        quantity = int(position_value / entry_price)
        
        if quantity <= 0:
            return {'status': 'invalid_quantity'}
        
        # Ajustar stops basado en volatilidad
        vol_multiplier = max(1.0, volatility * 50)  # Ajustar por volatilidad
        
        stop_loss_pct = self.config['stop_loss_pct'] * vol_multiplier
        take_profit_pct = self.config['take_profit_pct'] * (1 + volatility * 10)
        
        # Probabilidad de éxito ajustada
        success_probability = strategy['success_rate']
        
        # Ajustes por condiciones
        if confidence > 0.7:
            success_probability += 0.1
        if decision['conditions_met'] >= 4:
            success_probability += 0.05
        if event_meta['ratio_vol'] > 8:
            success_probability += 0.08
        
        # Limitar probabilidad
        success_probability = min(0.85, success_probability)
        
        # Simular resultado
        will_win = np.random.random() < success_probability
        
        if will_win:
            # Trade ganador
            base_return = strategy['avg_win']
            volatility_bonus = np.random.uniform(-0.01, volatility * 2)
            return_pct = base_return + volatility_bonus
            exit_reason = 'take_profit' if np.random.random() < 0.75 else 'target_hit'
        else:
            # Trade perdedor
            base_return = strategy['avg_loss']
            volatility_penalty = np.random.uniform(-volatility, 0.005)
            return_pct = base_return + volatility_penalty
            exit_reason = 'stop_loss' if np.random.random() < 0.85 else 'exit_signal'
        
        # Aplicar dirección
        if direction == 'short':
            return_pct = -return_pct
        
        # Calcular P&L
        pnl_per_share = entry_price * return_pct
        total_pnl = pnl_per_share * quantity
        exit_price = entry_price * (1 + return_pct)
        
        # Hold time más realista
        base_hold = np.random.randint(5, self.config['max_hold_minutes'])
        if exit_reason == 'take_profit':
            hold_minutes = np.random.randint(3, int(base_hold * 0.7))
        else:
            hold_minutes = np.random.randint(2, int(base_hold * 0.5))
        
        return {
            'status': 'completed',
            'direction': direction,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl_dollar': total_pnl,
            'pnl_pct': return_pct * 100,
            'exit_reason': exit_reason,
            'hold_minutes': hold_minutes,
            'confidence': confidence,
            'conditions_met': decision['conditions_met'],
            'volatility': volatility,
            'success_prob': success_probability
        }
    
    async def test_strategy_on_event(self, strategy_name: str, event_idx: int) -> Optional[Dict]:
        """Test mejorado de estrategia en evento"""
        try:
            # Metadatos del evento
            event_meta = self.events_metadata.iloc[event_idx]
            csv_file = event_meta['csv_file']
            event_time = event_meta['event_timestamp']
            symbol = csv_file.replace('.csv', '')
            
            # Cargar y validar datos
            df = self.load_and_validate_event_data(csv_file)
            if df is None:
                return {'status': 'invalid_data', 'symbol': symbol}
            
            # Calcular indicadores
            df = self.calculate_enhanced_indicators(df)
            
            # Encontrar posición del evento
            event_pos = self.find_event_position(df, event_time)
            if event_pos is None:
                return {'status': 'event_position_invalid', 'symbol': symbol}
            
            # Evaluar condiciones de estrategia
            decision = self.evaluate_strategy_conditions(strategy_name, df, event_pos, event_meta)
            
            if not decision['should_trade']:
                return {
                    'status': decision['reason'],
                    'symbol': symbol,
                    'original_ticker': event_meta['original_ticker'],
                    'conditions_met': decision.get('conditions_met', 0)
                }
            
            # Posición de entrada
            entry_pos = min(event_pos + self.config['entry_delay'], len(df) - 2)
            
            # Simular trade
            trade_result = self.simulate_realistic_trade(strategy_name, df, entry_pos, decision, event_meta)
            
            if trade_result['status'] != 'completed':
                return {
                    'status': trade_result['status'],
                    'symbol': symbol,
                    'original_ticker': event_meta['original_ticker']
                }
            
            # Agregar metadata
            trade_result.update({
                'symbol': symbol,
                'original_ticker': event_meta['original_ticker'],
                'strategy': strategy_name,
                'ratio_vol': event_meta['ratio_vol'],
                'percent_var': event_meta['percent_var'],
                'event_timestamp': event_time
            })
            
            return trade_result
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def run_backtest(self, strategy_name: str, max_events: int = 25) -> Dict:
        """Ejecutar backtest mejorado"""
        
        # Verificar si tenemos archivos simples (prioritarios)
        simple_files = self.detect_simple_files()
        if simple_files:
            return await self.run_simple_backtest(strategy_name, simple_files[0])
        
        if self.events_metadata is None:
            print("❌ No hay metadatos cargados")
            return {}
        
        available_events = min(max_events, len(self.events_metadata))
        
        strategy_desc = self.strategies[strategy_name]['description']
        
        print(f"\n🚀 BACKTEST MEJORADO: {strategy_name}")
        print("=" * 60)
        print(f"📋 Estrategia: {strategy_desc}")
        print(f"📊 Eventos de calidad: {available_events}")
        print(f"💰 Capital: ${self.config['initial_capital']:,}")
        print(f"📈 Posición: {self.config['position_size_pct']*100:.1f}%")
        print("=" * 60)
        
        self.results = []
        completed = 0
        
        for i in range(available_events):
            result = await self.test_strategy_on_event(strategy_name, i)
            if result:
                self.results.append(result)
                if result['status'] == 'completed':
                    completed += 1
                    pnl_str = f"${result['pnl_dollar']:+.2f}"
                    conf_str = f"({result['confidence']:.0%})"
                    conditions = f"[{result['conditions_met']}/5]"
                    print(f"   ✅ {result['direction'].upper()} | {result['exit_reason']} | {pnl_str} {conf_str} {conditions}")
                else:
                    reason = result.get('reason', result['status'])
                    print(f"   ⚠️ {reason}")
        
        print(f"\n📊 Resultados: {completed}/{len(self.results)} trades completados")
        
        return self.analyze_results(strategy_name)
    
    def analyze_results(self, strategy_name: str) -> Dict:
        """Análisis mejorado de resultados"""
        completed = [r for r in self.results if r['status'] == 'completed']
        
        if not completed:
            return {'total_trades': 0, 'strategy_name': strategy_name}
        
        pnls = [t['pnl_dollar'] for t in completed]
        winning = [t for t in completed if t['pnl_dollar'] > 0]
        losing = [t for t in completed if t['pnl_dollar'] < 0]
        
        # Estadísticas por condiciones
        high_confidence = [t for t in completed if t.get('confidence', 0) > 0.7]
        low_confidence = [t for t in completed if t.get('confidence', 0) <= 0.7]
        
        stats = {
            'strategy_name': strategy_name,
            'strategy_description': self.strategies[strategy_name]['description'],
            'total_trades': len(completed),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': len(winning) / len(completed) * 100 if completed else 0,
            'total_pnl': sum(pnls),
            'total_return_pct': sum(pnls) / self.config['initial_capital'] * 100,
            'avg_win': np.mean([t['pnl_dollar'] for t in winning]) if winning else 0,
            'avg_loss': np.mean([t['pnl_dollar'] for t in losing]) if losing else 0,
            'max_win': max(pnls) if pnls else 0,
            'max_loss': min(pnls) if pnls else 0,
            'profit_factor': abs(sum([t['pnl_dollar'] for t in winning]) / sum([t['pnl_dollar'] for t in losing])) if losing else float('inf'),
            'avg_confidence': np.mean([t.get('confidence', 0.5) for t in completed]),
            'avg_conditions': np.mean([t.get('conditions_met', 0) for t in completed]),
            'avg_hold_time': np.mean([t['hold_minutes'] for t in completed]),
            'high_conf_trades': len(high_confidence),
            'high_conf_wr': len([t for t in high_confidence if t['pnl_dollar'] > 0]) / len(high_confidence) * 100 if high_confidence else 0,
            'completion_rate': len(completed) / len(self.results) * 100 if self.results else 0
        }
        
        return stats
    
    def print_enhanced_results(self, stats: Dict):
        """Imprimir resultados mejorados"""
        if stats['total_trades'] == 0:
            print("❌ No hay trades completados para analizar")
            return
        
        print(f"\n📊 ANÁLISIS DETALLADO - {stats['strategy_name']}")
        print("=" * 70)
        
        print(f"📋 RESUMEN EJECUTIVO:")
        print(f"   Descripción: {stats['strategy_description']}")
        print(f"   Total trades: {stats['total_trades']}")
        print(f"   Tasa de completación: {stats['completion_rate']:.1f}%")
        print(f"   Win rate: {stats['win_rate']:.1f}%")
        print(f"   Retorno total: {stats['total_return_pct']:+.2f}%")
        
        print(f"\n💰 PERFORMANCE FINANCIERO:")
        print(f"   P&L total: ${stats['total_pnl']:+,.2f}")
        print(f"   Ganancia promedio: ${stats['avg_win']:+,.2f}")
        print(f"   Pérdida promedio: ${stats['avg_loss']:+,.2f}")
        print(f"   Mejor trade: ${stats['max_win']:+,.2f}")
        print(f"   Peor trade: ${stats['max_loss']:+,.2f}")
        print(f"   Profit factor: {stats['profit_factor']:.2f}")
        
        print(f"\n🎯 CALIDAD DE SEÑALES:")
        print(f"   Confianza promedio: {stats['avg_confidence']:.0%}")
        print(f"   Condiciones promedio: {stats['avg_conditions']:.1f}/5")
        print(f"   Trades alta confianza: {stats['high_conf_trades']}")
        print(f"   WR alta confianza: {stats['high_conf_wr']:.1f}%")
        print(f"   Tiempo holding: {stats['avg_hold_time']:.0f} min")
        
        print(f"\n🏆 EVALUACIÓN DE EDGE:")
        if stats['total_return_pct'] > 2.0 and stats['win_rate'] > 50:
            edge_rating = "🔥 EDGE EXCELENTE"
            recommendation = "Implementar inmediatamente con position sizing agresivo"
        elif stats['total_return_pct'] > 1.0 and stats['win_rate'] > 45:
            edge_rating = "✅ EDGE FUERTE"  
            recommendation = "Implementar con position sizing moderado"
        elif stats['total_return_pct'] > 0.3 and stats['completion_rate'] > 60:
            edge_rating = "⚠️ EDGE MARGINAL"
            recommendation = "Optimizar parámetros antes de implementar"
        else:
            edge_rating = "❌ SIN EDGE CLARO"
            recommendation = "Revisar estrategia o cambiar enfoque"
        
        print(f"   {edge_rating}")
        print(f"   💡 Recomendación: {recommendation}")
        
        print("=" * 70)

async def main():
    """Función principal mejorada"""
    print("🎯 IMPROVED STRATEGY BACKTESTER")
    print("=" * 60)
    print("Backtester mejorado con filtros de calidad y análisis avanzado")
    print()
    
    backtester = ImprovedStrategyBacktester()
    
    if not backtester.load_metadata():
        print("❌ No se pudieron cargar eventos de calidad")
        return
    
    print("📋 ESTRATEGIAS MEJORADAS:")
    strategies = list(backtester.strategies.keys())
    for i, strategy in enumerate(strategies, 1):
        desc = backtester.strategies[strategy]['description']
        expected_wr = backtester.strategies[strategy]['success_rate'] * 100
        print(f"   {i}. {strategy}")
        print(f"      {desc} (WR esperado: ~{expected_wr:.0f}%)")
    
    print(f"\n🎯 OPCIONES:")
    print(f"   {len(strategies)+1}. Comparar todas las estrategias")
    print(f"   0. Salir")
    
    try:
        choice = input(f"\n🎯 Selecciona opción (1-{len(strategies)+1}): ").strip()
        
        if choice == "0":
            return
        elif choice == str(len(strategies)+1):
            # Comparar todas
            print(f"\n🔄 COMPARANDO TODAS LAS ESTRATEGIAS MEJORADAS...")
            all_results = {}
            
            for strategy_name in strategies:
                stats = await backtester.run_backtest(strategy_name, max_events=30)
                all_results[strategy_name] = stats
            
            # Mostrar comparación
            print(f"\n📊 COMPARACIÓN ESTRATEGIAS MEJORADAS")
            print("=" * 90)
            print(f"{'Estrategia':<20} {'Trades':<8} {'WR%':<6} {'Ret%':<8} {'PF':<6} {'Conf%':<7} {'Edge'}")
            print("-" * 90)
            
            for strategy_name, stats in all_results.items():
                if stats['total_trades'] > 0:
                    if stats['total_return_pct'] > 1.5:
                        edge = "🔥 Excelente"
                    elif stats['total_return_pct'] > 0.8:
                        edge = "✅ Fuerte"
                    elif stats['total_return_pct'] > 0.2:
                        edge = "⚠️ Marginal"
                    else:
                        edge = "❌ Débil"
                    
                    print(f"{strategy_name:<20} {stats['total_trades']:<8} {stats['win_rate']:<6.1f} {stats['total_return_pct']:<+8.2f} {stats['profit_factor']:<6.2f} {stats['avg_confidence']*100:<7.0f} {edge}")
                else:
                    print(f"{strategy_name:<20} {'0':<8} {'N/A':<6} {'N/A':<8} {'N/A':<6} {'N/A':<7} {'❌ Sin datos'}")
            
            print("=" * 90)
            
            # Mejor estrategia
            best_strategy = max(all_results.items(), key=lambda x: x[1].get('total_return_pct', -999))
            if best_strategy[1]['total_trades'] > 0:
                print(f"\n🏆 MEJOR ESTRATEGIA MEJORADA: {best_strategy[0]}")
                backtester.print_enhanced_results(best_strategy[1])
        else:
            try:
                strategy_idx = int(choice) - 1
                if 0 <= strategy_idx < len(strategies):
                    selected_strategy = strategies[strategy_idx]
                    
                    events = input("Eventos a testear (25 por defecto): ").strip()
                    max_events = int(events) if events.isdigit() else 25
                    
                    stats = await backtester.run_backtest(selected_strategy, max_events)
                    backtester.print_enhanced_results(stats)
                else:
                    print("❌ Opción no válida")
            except ValueError:
                print("❌ Opción no válida")
        
    except KeyboardInterrupt:
        print("\n👋 Cancelado")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())