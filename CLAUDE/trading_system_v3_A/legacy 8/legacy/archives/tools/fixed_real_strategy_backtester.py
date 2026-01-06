#!/usr/bin/env python3
"""
Fixed Real Strategy Backtester
==============================

Backtester corregido que usa las estrategias REALES del sistema 
con el método correcto on_bar() en lugar de analyze().
"""

import pandas as pd
import numpy as np
import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system components
from core.interfaces import MarketData, SignalType, TradingConfig
from strategies import get_strategy_class, list_strategies, STRATEGY_REGISTRY

class FixedRealStrategyBacktester:
    """Backtester corregido usando estrategias reales del sistema"""
    
    def __init__(self, synthetic_data_dir: str = 'synthetic_data'):
        self.synthetic_data_dir = synthetic_data_dir
        self.events_metadata = None
        self.results = []
        
        # Buscar el archivo de metadatos en posibles ubicaciones
        possible_metadata_paths = [
            os.path.join(synthetic_data_dir, 'events_metadata.csv'),
            os.path.join(synthetic_data_dir, 'Extra', 'events_metadata.csv')
        ]
        
        self.metadata_path = None
        for path in possible_metadata_paths:
            if os.path.exists(path):
                self.metadata_path = path
                break
        
        # Strategy management
        self.strategy = None
        self.strategy_name = None
        
        # Configuración
        self.config = {
            'initial_capital': 25000,
            'position_size': 0.02,  # 2% del capital por operación
            'max_hold_minutes': 120,  # 2 horas máximo
            'min_bars_before_event': 30,  # Reducido a 30 barras
            'entry_delay_minutes': 2,   # Esperar 2 minutos después del evento
        }
        
        # Trading config for strategy initialization
        self.trading_config = TradingConfig(
            max_positions=10,
            max_risk_per_trade=0.025,
            max_daily_loss=-2000.0,
            max_daily_trades=50,
            strategy_name="test",
            timeframe="1 min",
            log_level="WARNING"
        )
    
    def load_events_metadata(self) -> bool:
        """Cargar metadatos de eventos"""
        try:
            if not self.metadata_path or not os.path.exists(self.metadata_path):
                print("❌ No se encontró archivo de metadatos en ubicaciones esperadas")
                print(f"   Buscado en: {self.synthetic_data_dir}/events_metadata.csv")
                print(f"   También en: {self.synthetic_data_dir}/Extra/events_metadata.csv")
                return False
            
            self.events_metadata = pd.read_csv(self.metadata_path)
            print(f"✅ Metadatos cargados desde: {self.metadata_path}")
            self.events_metadata['event_timestamp'] = pd.to_datetime(self.events_metadata['event_timestamp'])
            
            # Filtros básicos de calidad
            initial_count = len(self.events_metadata)
            
            # Solo eventos con suficientes barras
            self.events_metadata = self.events_metadata[self.events_metadata['total_bars'] >= 60]
            
            # Solo eventos en horario normal (no muy tarde)
            self.events_metadata['event_hour'] = self.events_metadata['event_timestamp'].dt.hour
            self.events_metadata = self.events_metadata[self.events_metadata['event_hour'] <= 15]
            
            final_count = len(self.events_metadata)
            
            print(f"✅ Metadatos cargados: {final_count}/{initial_count} eventos de calidad")
            print(f"   📅 Período: {self.events_metadata['event_timestamp'].min()} a {self.events_metadata['event_timestamp'].max()}")
            print(f"   📊 Ratio promedio: {self.events_metadata['ratio_vol'].mean():.1f}x")
            
            return final_count > 0
            
        except Exception as e:
            print(f"❌ Error cargando metadatos: {e}")
            return False
    
    def load_event_data(self, csv_filename: str) -> Optional[pd.DataFrame]:
        """Cargar datos de un evento específico"""
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
            
            # Validar datos mínimos
            if len(df) < 40 or df['volume'].mean() < 50:
                return None
            
            return df
            
        except Exception as e:
            return None
    
    def initialize_strategy(self, strategy_name: str, strategy_params: dict = None) -> bool:
        """Inicializar estrategia real del sistema"""
        try:
            # Find strategy class
            strategy_class = None
            for name, cls in STRATEGY_REGISTRY.items():
                if name.lower() == strategy_name.lower() or strategy_name.lower() in name.lower():
                    strategy_class = cls
                    self.strategy_name = name
                    break
            
            if not strategy_class:
                print(f"❌ Estrategia '{strategy_name}' no encontrada")
                return False
            
            # Initialize strategy with parameters
            # Let the strategy use its own defaults if no parameters provided
            self.strategy = strategy_class(strategy_params)
            
            print(f"✅ Estrategia inicializada: {self.strategy_name}")
            params_count = len(strategy_params) if strategy_params else 0
            print(f"   📊 Parámetros: {params_count} configurados")
            
            return True
            
        except Exception as e:
            print(f"❌ Error inicializando estrategia {strategy_name}: {e}")
            return False
    
    def _get_default_strategy_params(self, strategy_name: str) -> dict:
        """Obtener parámetros por defecto para una estrategia"""
        base_params = {
            'max_position_value': 500.0,
            'max_portfolio_exposure': 2000.0,
            'stop_loss_pct': 0.05,
            'take_profit_pct': 0.12,
        }
        return base_params
    
    def df_to_market_data_list(self, df: pd.DataFrame, symbol: str) -> List[MarketData]:
        """Convertir DataFrame a lista de MarketData"""
        market_data_list = []
        
        for timestamp, row in df.iterrows():
            market_data = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row['volume']) if pd.notna(row['volume']) else 0,
                timeframe="1 min"
            )
            market_data_list.append(market_data)
        
        return market_data_list
    
    def find_event_position_in_data(self, df: pd.DataFrame, event_timestamp: datetime) -> Optional[int]:
        """Encontrar posición del evento en los datos"""
        try:
            time_diff = abs(df.index - event_timestamp)
            min_diff_idx = time_diff.argmin()
            closest_idx = df.index[min_diff_idx]
            position = df.index.get_loc(closest_idx)
            
            # Verificar que hay suficientes barras antes del evento
            if position < self.config['min_bars_before_event']:
                return None
                
            return position
        except Exception as e:
            return None
    
    async def backtest_event_with_real_strategy(self, event_idx: int, strategy_params: dict = None) -> Optional[Dict]:
        """Ejecutar backtest en un evento usando estrategia real"""
        try:
            # Obtener metadatos del evento
            event_meta = self.events_metadata.iloc[event_idx]
            csv_filename = event_meta['csv_file']
            event_timestamp = event_meta['event_timestamp']
            original_symbol = event_meta['original_ticker']
            
            synthetic_symbol = csv_filename.replace('.csv', '')
            print(f"📊 Backtesting {synthetic_symbol} | {original_symbol} | {event_meta['ratio_vol']:.1f}x")
            
            # Cargar datos del evento
            df = self.load_event_data(csv_filename)
            if df is None:
                return {
                    'status': 'no_data',
                    'symbol': synthetic_symbol,
                    'original_ticker': original_symbol,
                    'pnl': 0
                }
            
            # Encontrar posición del evento
            event_position = self.find_event_position_in_data(df, event_timestamp)
            if event_position is None:
                return {
                    'status': 'insufficient_data',
                    'symbol': synthetic_symbol,
                    'original_ticker': original_symbol,
                    'pnl': 0,
                    'reason': 'Not enough bars before event'
                }
            
            # Convertir datos a MarketData
            market_data_list = self.df_to_market_data_list(df, synthetic_symbol)
            
            # Crear nueva instancia de estrategia para cada evento  
            strategy_class = STRATEGY_REGISTRY[self.strategy_name]
            print(f"   🔍 Debug: Creating {self.strategy_name} with params: {strategy_params}")
            print(f"   🔍 Debug: strategy_class: {strategy_class}")
            try:
                strategy_instance = strategy_class(strategy_params)
                print(f"   ✅ Strategy instance created successfully")
            except Exception as e:
                import traceback
                print(f"   ❌ Error creating strategy instance: {e}")
                print(f"   📍 Full traceback: {traceback.format_exc()}")
                raise
            
            # Initialize the strategy properly (required by BaseStrategy)
            # We pass None for event_bus since we're in backtesting mode
            try:
                await strategy_instance._initialize_strategy()
            except Exception as e:
                import traceback
                print(f"   ⚠️ Strategy initialization failed: {e}")
                print(f"   📍 Full traceback: {traceback.format_exc()}")
                return {
                    'status': 'init_error',
                    'symbol': synthetic_symbol,
                    'original_ticker': original_symbol,
                    'pnl': 0,
                    'reason': f'Strategy initialization failed: {e}'
                }
            
            # Alimentar barras a la estrategia hasta el evento + delay
            analysis_end = min(event_position + self.config['entry_delay_minutes'], len(market_data_list) - 1)
            signal = None
            
            print(f"   🔍 Analysis window: bars 0 to {analysis_end} (event at {event_position}, total {len(market_data_list)})")
            
            for i in range(analysis_end + 1):
                try:
                    current_signal = await strategy_instance.on_bar(market_data_list[i])
                    if current_signal and current_signal.signal_type in [SignalType.LONG, SignalType.SHORT]:
                        signal = current_signal
                        print(f"   🎯 SIGNAL GENERATED at bar {i}: {current_signal.signal_type}")
                        break
                except Exception as e:
                    print(f"   ❌ Exception at bar {i}: {e}")
                    continue
            
            if not signal or signal.signal_type not in [SignalType.LONG, SignalType.SHORT]:
                return {
                    'status': 'no_signal',
                    'symbol': synthetic_symbol,
                    'original_ticker': original_symbol,
                    'pnl': 0,
                    'reason': 'No trading signal generated'
                }
            
            # Calcular entrada después del evento
            entry_position = event_position + self.config['entry_delay_minutes']
            if entry_position >= len(market_data_list):
                return {
                    'status': 'no_entry_data',
                    'symbol': synthetic_symbol,
                    'original_ticker': original_symbol,
                    'pnl': 0,
                    'reason': 'No data after event for entry'
                }
            
            entry_bar = market_data_list[entry_position]
            entry_price = entry_bar.close
            direction = 'long' if signal.signal_type == SignalType.LONG else 'short'
            
            # Calcular position size
            position_value = self.config['initial_capital'] * self.config['position_size']
            quantity = int(position_value / entry_price)
            
            if quantity <= 0:
                return {
                    'status': 'invalid_quantity',
                    'symbol': synthetic_symbol,
                    'original_ticker': original_symbol,
                    'pnl': 0,
                    'reason': f'Invalid quantity: {quantity}'
                }
            
            # Usar stops de la señal o defaults
            stop_loss_pct = getattr(signal, 'stop_loss_pct', 0.05)
            take_profit_pct = getattr(signal, 'take_profit_pct', 0.10)
            
            # Calcular stop loss y take profit
            if direction == 'long':
                stop_loss = entry_price * (1 - stop_loss_pct)
                take_profit = entry_price * (1 + take_profit_pct)
            else:
                stop_loss = entry_price * (1 + stop_loss_pct)
                take_profit = entry_price * (1 - take_profit_pct)
            
            # Simular holding
            max_hold_position = min(entry_position + self.config['max_hold_minutes'], len(market_data_list) - 1)
            
            exit_price = None
            exit_reason = None
            exit_time = None
            
            for i in range(entry_position + 1, max_hold_position + 1):
                current_bar = market_data_list[i]
                current_price = current_bar.close
                
                # Check exit conditions
                if direction == 'long':
                    if current_price <= stop_loss:
                        exit_price = stop_loss
                        exit_reason = 'stop_loss'
                        exit_time = current_bar.timestamp
                        break
                    elif current_price >= take_profit:
                        exit_price = take_profit
                        exit_reason = 'take_profit'
                        exit_time = current_bar.timestamp
                        break
                else:  # short
                    if current_price >= stop_loss:
                        exit_price = stop_loss
                        exit_reason = 'stop_loss'
                        exit_time = current_bar.timestamp
                        break
                    elif current_price <= take_profit:
                        exit_price = take_profit
                        exit_reason = 'take_profit'
                        exit_time = current_bar.timestamp
                        break
            
            if exit_price is None:
                # Max hold time reached
                exit_bar = market_data_list[max_hold_position]
                exit_price = exit_bar.close
                exit_reason = 'max_hold_time'
                exit_time = exit_bar.timestamp
            
            # Calcular P&L
            if direction == 'long':
                pnl_per_share = exit_price - entry_price
            else:
                pnl_per_share = entry_price - exit_price
            
            total_pnl = pnl_per_share * quantity
            pnl_pct = (pnl_per_share / entry_price) * 100
            
            hold_minutes = (exit_time - entry_bar.timestamp).total_seconds() / 60
            
            result = {
                'status': 'completed',
                'symbol': synthetic_symbol,
                'original_ticker': original_symbol,
                'strategy': self.strategy_name,
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'entry_time': entry_bar.timestamp,
                'exit_time': exit_time,
                'quantity': quantity,
                'pnl_dollar': total_pnl,
                'pnl_pct': pnl_pct,
                'exit_reason': exit_reason,
                'hold_minutes': hold_minutes,
                'event_timestamp': event_timestamp,
                'ratio_vol': event_meta['ratio_vol'],
                'percent_var': event_meta['percent_var'],
                'signal_strength': getattr(signal, 'confidence', 0.5)
            }
            
            return result
            
        except Exception as e:
            print(f"❌ Error en backtest del evento {event_idx}: {e}")
            return {
                'status': 'error',
                'symbol': 'unknown',
                'original_ticker': 'unknown',
                'pnl': 0,
                'error': str(e)
            }
    
    async def run_mass_backtest(self, strategy_name: str, max_events: int = None, 
                              start_idx: int = 0, strategy_params: dict = None) -> bool:
        """Ejecutar backtest masivo con estrategia real"""
        
        if not self.initialize_strategy(strategy_name, strategy_params):
            return False
        
        if self.events_metadata is None:
            print("❌ Primero debes cargar los metadatos")
            return False
        
        total_events = len(self.events_metadata)
        if max_events is None:
            max_events = total_events
        
        end_idx = min(start_idx + max_events, total_events)
        
        print(f"\n🚀 INICIANDO BACKTEST CON ESTRATEGIA REAL")
        print("=" * 60)
        print(f"📊 Estrategia: {self.strategy_name}")
        print(f"📊 Eventos a testear: {end_idx - start_idx} (de {start_idx} a {end_idx-1})")
        print(f"💰 Capital inicial: ${self.config['initial_capital']:,}")
        print(f"📈 Tamaño de posición: {self.config['position_size']*100:.1f}%")
        print("=" * 60)
        
        self.results = []
        successful_trades = 0
        
        for i in range(start_idx, end_idx):
            result = await self.backtest_event_with_real_strategy(i, strategy_params)
            if result is not None:
                self.results.append(result)
                if result['status'] == 'completed':
                    successful_trades += 1
                    pnl_str = f"${result['pnl_dollar']:+.2f}" if result['pnl_dollar'] != 0 else "$0.00"
                    print(f"   ✅ {result['direction'].upper()} | {result['exit_reason']} | {pnl_str}")
                else:
                    reason = result.get('reason', result['status'])
                    print(f"   ⚠️ {reason}")
        
        print(f"\n📊 Backtest completado: {successful_trades}/{len(self.results)} trades exitosos")
        return True
    
    def analyze_results(self) -> Dict:
        """Analizar resultados del backtest"""
        if not self.results:
            return {'total_trades': 0, 'strategy_name': self.strategy_name or 'Unknown'}
        
        completed_trades = [r for r in self.results if r['status'] == 'completed']
        
        if not completed_trades:
            return {'total_trades': 0, 'strategy_name': self.strategy_name or 'Unknown'}
        
        # Calcular estadísticas
        pnls = [t['pnl_dollar'] for t in completed_trades]
        pnl_pcts = [t['pnl_pct'] for t in completed_trades]
        
        winning_trades = [t for t in completed_trades if t['pnl_dollar'] > 0]
        losing_trades = [t for t in completed_trades if t['pnl_dollar'] < 0]
        
        total_pnl = sum(pnls)
        total_return_pct = (total_pnl / self.config['initial_capital']) * 100
        
        win_rate = len(winning_trades) / len(completed_trades) * 100
        avg_win = np.mean([t['pnl_dollar'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl_dollar'] for t in losing_trades]) if losing_trades else 0
        
        profit_factor = abs(sum([t['pnl_dollar'] for t in winning_trades]) / sum([t['pnl_dollar'] for t in losing_trades])) if losing_trades else float('inf')
        
        max_win = max(pnls) if pnls else 0
        max_loss = min(pnls) if pnls else 0
        
        # Calcular drawdown
        cumulative_pnl = np.cumsum(pnls)
        peak = np.maximum.accumulate(cumulative_pnl)
        drawdown = (cumulative_pnl - peak)
        max_drawdown = abs(min(drawdown)) if len(drawdown) > 0 else 0
        
        # Análisis por dirección
        long_trades = [t for t in completed_trades if t['direction'] == 'long']
        short_trades = [t for t in completed_trades if t['direction'] == 'short']
        
        stats = {
            'strategy_name': self.strategy_name or 'Unknown',
            'total_trades': len(completed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_win': max_win,
            'max_loss': max_loss,
            'max_drawdown': max_drawdown,
            'avg_pnl_pct': np.mean(pnl_pcts) if pnl_pcts else 0,
            'sharpe_ratio': np.mean(pnl_pcts) / np.std(pnl_pcts) if np.std(pnl_pcts) > 0 else 0,
            'long_trades': len(long_trades),
            'short_trades': len(short_trades),
            'avg_hold_time': np.mean([t['hold_minutes'] for t in completed_trades]) if completed_trades else 0,
            'completion_rate': len(completed_trades) / len(self.results) * 100 if self.results else 0
        }
        
        return stats
    
    def print_performance_report(self, stats: Dict):
        """Imprimir reporte de rendimiento detallado"""
        
        if stats['total_trades'] == 0:
            print(f"\n❌ NO HAY TRADES COMPLETADOS - {stats['strategy_name']}")
            print("=" * 70)
            print("💡 Posibles causas:")
            print("   • Datos insuficientes en los eventos")
            print("   • Estrategia no genera señales con estos datos")
            print("   • Parámetros de la estrategia muy restrictivos")
            print("   • Eventos ocurren fuera del horario de la estrategia")
            print("=" * 70)
            return
        
        print(f"\n📊 REPORTE DE RENDIMIENTO - {stats['strategy_name']}")
        print("=" * 70)
        
        print(f"📈 ESTADÍSTICAS GENERALES:")
        print(f"   Estrategia: {stats['strategy_name']}")
        print(f"   Total trades: {stats['total_trades']}")
        print(f"   Tasa completación: {stats['completion_rate']:.1f}%")
        print(f"   Trades ganadores: {stats['winning_trades']}")
        print(f"   Trades perdedores: {stats['losing_trades']}")
        print(f"   Win rate: {stats['win_rate']:.1f}%")
        print(f"   Trades LONG: {stats['long_trades']}")
        print(f"   Trades SHORT: {stats['short_trades']}")
        print(f"   Tiempo holding promedio: {stats['avg_hold_time']:.1f} minutos")
        
        print(f"\n💰 RENDIMIENTO FINANCIERO:")
        print(f"   P&L total: ${stats['total_pnl']:+,.2f}")
        print(f"   Retorno total: {stats['total_return_pct']:+.2f}%")
        print(f"   Ganancia promedio: ${stats['avg_win']:+,.2f}")
        print(f"   Pérdida promedio: ${stats['avg_loss']:+,.2f}")
        print(f"   Máxima ganancia: ${stats['max_win']:+,.2f}")
        print(f"   Máxima pérdida: ${stats['max_loss']:+,.2f}")
        
        print(f"\n📊 MÉTRICAS DE RIESGO:")
        print(f"   Profit factor: {stats['profit_factor']:.2f}")
        print(f"   Max drawdown: ${stats['max_drawdown']:,.2f}")
        print(f"   Sharpe ratio: {stats['sharpe_ratio']:.2f}")
        print(f"   Avg return per trade: {stats['avg_pnl_pct']:+.2f}%")
        
        # Análisis de edge
        print(f"\n🎯 ANÁLISIS DE EDGE:")
        if stats['total_return_pct'] > 1.0 and stats['win_rate'] > 45:
            print("   ✅ EDGE FUERTE DETECTADO: Estrategia muy rentable")
        elif stats['total_return_pct'] > 0.5 and stats['win_rate'] > 40:
            print("   ✅ EDGE DETECTADO: Estrategia rentable")
        elif stats['total_return_pct'] > 0:
            print("   ⚠️ EDGE MARGINAL: Rentable pero necesita optimización")
        else:
            print("   ❌ SIN EDGE: Estrategia no rentable con estos parámetros")
        
        print("=" * 70)

async def main():
    """Interfaz principal corregida"""
    
    print("🎯 FIXED REAL STRATEGY BACKTESTER")
    print("=" * 60)
    print("Backtester corregido con estrategias reales del sistema de trading")
    print()
    
    # Verificar datos sintéticos
    synthetic_dir = 'synthetic_data'
    if not os.path.exists(synthetic_dir):
        print(f"❌ Directorio no encontrado: {synthetic_dir}")
        print("💡 Ejecuta primero extract_full_trading_days.py")
        return
    
    # Crear backtester
    backtester = FixedRealStrategyBacktester(synthetic_dir)
    
    # Cargar metadatos
    if not backtester.load_events_metadata():
        return
    
    # Mostrar estrategias disponibles
    available_strategies = list(STRATEGY_REGISTRY.keys())
    print(f"\n📋 ESTRATEGIAS DISPONIBLES:")
    for i, strategy in enumerate(available_strategies, 1):
        print(f"   {i}. {strategy}")
    print()
    
    try:
        # Seleccionar estrategia
        strategy_choice = input("🎯 Selecciona estrategia por número o nombre: ").strip()
        
        if strategy_choice.isdigit():
            idx = int(strategy_choice) - 1
            if 0 <= idx < len(available_strategies):
                selected_strategy = available_strategies[idx]
            else:
                print("❌ Número inválido")
                return
        else:
            # Buscar por nombre
            selected_strategy = None
            for strategy in available_strategies:
                if strategy_choice.lower() in strategy.lower():
                    selected_strategy = strategy
                    break
            
            if not selected_strategy:
                print(f"❌ Estrategia '{strategy_choice}' no encontrada")
                return
        
        print(f"✅ Estrategia seleccionada: {selected_strategy}")
        
        # Opciones de ejecución
        print(f"\n🚀 OPCIONES DE EJECUCIÓN:")
        print("1. Backtest rápido (primeros 15 eventos)")
        print("2. Backtest medio (30 eventos)")
        print("3. Backtest completo (todos los eventos)")
        print("4. Backtest personalizado")
        
        choice = input("\n🎯 Selecciona opción (1-4): ").strip()
        
        max_events = 15
        start_idx = 0
        
        if choice == "1":
            max_events = 15
            print(f"\n🚀 Ejecutando backtest rápido ({max_events} eventos)...")
        elif choice == "2":
            max_events = 30
            print(f"\n🚀 Ejecutando backtest medio ({max_events} eventos)...")
        elif choice == "3":
            max_events = None
            print(f"\n🚀 Ejecutando backtest completo (todos los eventos)...")
        elif choice == "4":
            max_events = int(input("Número de eventos a testear: "))
            start_idx = int(input("Índice inicial (0 por defecto): ") or "0")
            print(f"\n🚀 Ejecutando backtest personalizado ({max_events} eventos desde {start_idx})...")
        else:
            max_events = 15
            start_idx = 0
        
        # Ejecutar backtest
        success = await backtester.run_mass_backtest(
            strategy_name=selected_strategy,
            max_events=max_events,
            start_idx=start_idx
        )
        
        if success and backtester.results:
            # Analizar resultados
            stats = backtester.analyze_results()
            
            # Mostrar reporte
            backtester.print_performance_report(stats)
        
    except KeyboardInterrupt:
        print("\n👋 Backtest cancelado")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())