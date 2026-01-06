#!/usr/bin/env python3
"""
Real Strategy Backtester for Synthetic Events
===========================================

Backtester que utiliza las estrategias REALES del sistema de trading
para evaluar rendimiento con datos sintéticos de explosiones de volumen.

Características:
- Usa las mismas estrategias que el sistema principal
- Integra con MarketData y interfaces reales
- Timing exacto de eventos para entrada precisa
- Configuración de parámetros por estrategia
- Análisis completo de rendimiento
"""

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
import matplotlib.pyplot as plt
import seaborn as sns
import asyncio
import logging

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system components
from core.interfaces import MarketData, SignalType, TradingConfig
from strategies import get_strategy_class, list_strategies, STRATEGY_REGISTRY
from core.risk_manager import RiskManager
from adapters.csv_data_provider import CSVDataProvider

class RealStrategyBacktester:
    """Backtester usando estrategias reales del sistema"""
    
    def __init__(self, synthetic_data_dir: str = 'synthetic_data'):
        self.synthetic_data_dir = synthetic_data_dir
        self.metadata_path = os.path.join(synthetic_data_dir, 'events_metadata.csv')
        self.events_metadata = None
        self.results = []
        
        # Strategy and risk management
        self.strategy = None
        self.risk_manager = None
        self.strategy_name = None
        
        # Setup logging
        logging.basicConfig(level=logging.WARNING)  # Reduce noise
        
        # Configuración por defecto
        self.config = {
            'initial_capital': 25000,
            'position_size': 0.02,  # 2% del capital por operación
            'max_hold_minutes': 180,  # 3 horas máximo
            'min_bars_before_event': 50,  # Mínimo barras antes del evento
            'entry_delay_minutes': 2,   # Esperar 2 minutos después del evento
        }
        
        # Trading config for strategy initialization
        self.trading_config = TradingConfig(
            max_positions=10,
            max_risk_per_trade=0.025,
            max_daily_loss=-2000.0,
            max_daily_trades=50,
            strategy_name="macdv",
            timeframe="1 min",
            log_level="WARNING"
        )
    
    def load_events_metadata(self) -> bool:
        """Cargar metadatos de eventos"""
        try:
            if not os.path.exists(self.metadata_path):
                print(f"❌ Archivo de metadatos no encontrado: {self.metadata_path}")
                return False
            
            self.events_metadata = pd.read_csv(self.metadata_path)
            self.events_metadata['event_timestamp'] = pd.to_datetime(self.events_metadata['event_timestamp'])
            
            print(f"✅ Metadatos cargados: {len(self.events_metadata)} eventos")
            print(f"   📅 Período: {self.events_metadata['event_timestamp'].min()} a {self.events_metadata['event_timestamp'].max()}")
            print(f"   📊 Ratio promedio: {self.events_metadata['ratio_vol'].mean():.1f}x")
            
            return True
            
        except Exception as e:
            print(f"❌ Error cargando metadatos: {e}")
            return False
    
    def load_event_data(self, csv_filename: str) -> Optional[pd.DataFrame]:
        """Cargar datos de un evento específico"""
        try:
            csv_path = os.path.join(self.synthetic_data_dir, csv_filename)
            
            if not os.path.exists(csv_path):
                print(f"⚠️ Archivo no encontrado: {csv_filename}")
                return None
            
            df = pd.read_csv(csv_path)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
            # Renombrar columnas para consistencia
            df.columns = ['open', 'high', 'low', 'close', 'volume']
            
            return df
            
        except Exception as e:
            print(f"❌ Error cargando {csv_filename}: {e}")
            return None
    
    def initialize_strategy(self, strategy_name: str, strategy_params: dict = None) -> bool:
        """Inicializar estrategia real del sistema"""
        try:
            if strategy_name.lower() not in [s.lower() for s in STRATEGY_REGISTRY.keys()]:
                print(f"❌ Estrategia '{strategy_name}' no encontrada")
                print(f"📋 Estrategias disponibles: {list(STRATEGY_REGISTRY.keys())}")
                return False
            
            # Find exact strategy class name
            strategy_class = None
            for name, cls in STRATEGY_REGISTRY.items():
                if name.lower().replace('strategy', '') in strategy_name.lower():
                    strategy_class = cls
                    self.strategy_name = name
                    break
            
            if not strategy_class:
                strategy_class = get_strategy_class(strategy_name.lower())
                if not strategy_class:
                    print(f"❌ No se pudo cargar la estrategia {strategy_name}")
                    return False
                self.strategy_name = strategy_name
            
            # Initialize strategy with parameters
            if strategy_params is None:
                strategy_params = self._get_default_strategy_params(strategy_name)
            
            self.strategy = strategy_class(strategy_params)
            
            # Initialize risk manager
            self.risk_manager = RiskManager(self.trading_config)
            
            print(f"✅ Estrategia inicializada: {self.strategy_name}")
            print(f"   📊 Parámetros: {len(strategy_params)} configurados")
            
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
        
        if 'macdv' in strategy_name.lower():
            return {
                **base_params,
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'volume_threshold': 2.0,
                'stop_loss_pct': 0.04,
                'take_profit_pct': 0.08,
            }
        elif 'volume' in strategy_name.lower():
            return {
                **base_params,
                'volume_threshold': 3.0,
                'breakout_periods': 20,
                'stop_loss_pct': 0.06,
                'take_profit_pct': 0.15,
            }
        elif 'gap' in strategy_name.lower():
            return {
                **base_params,
                'min_gap_percent': 3.0,
                'max_gap_percent': 25.0,
                'volume_multiplier': 2.0,
                'stop_loss_pct': 0.08,
                'take_profit_pct': 0.20,
            }
        else:
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
            return position
        except Exception as e:
            print(f"⚠️ Error encontrando posición del evento: {e}")
            return None
    
    async def backtest_event_with_real_strategy(self, event_idx: int) -> Optional[Dict]:
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
                return None
            
            # Encontrar posición del evento
            event_position = self.find_event_position_in_data(df, event_timestamp)
            if event_position is None:
                return None
            
            # Verificar datos suficientes
            if event_position < self.config['min_bars_before_event']:
                return {
                    'status': 'insufficient_data',
                    'symbol': synthetic_symbol,
                    'original_ticker': original_symbol,
                    'pnl': 0,
                    'reason': 'Not enough bars before event'
                }
            
            # Convertir datos a MarketData
            market_data_list = self.df_to_market_data_list(df, synthetic_symbol)
            
            # Usar datos hasta el evento + delay para análisis
            analysis_end = min(event_position + self.config['entry_delay_minutes'], len(market_data_list) - 1)
            analysis_data = market_data_list[:analysis_end + 1]
            
            # Analizar con la estrategia real
            signal = await self.strategy.analyze(analysis_data)
            
            if not signal or signal.signal_type == SignalType.EXIT_LONG or signal.signal_type == SignalType.EXIT_SHORT:
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
            
            # Get strategy exit parameters
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
            return None
    
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
            result = await self.backtest_event_with_real_strategy(i)
            if result is not None:
                self.results.append(result)
                if result['status'] == 'completed':
                    successful_trades += 1
                    pnl_str = f"${result['pnl_dollar']:+.2f}" if result['pnl_dollar'] != 0 else "$0.00"
                    print(f"   ✅ {result['direction'].upper()} | {result['exit_reason']} | {pnl_str}")
                else:
                    print(f"   ⚠️ {result['status']} | {result.get('reason', 'N/A')}")
        
        print(f"\n📊 Backtest completado: {successful_trades}/{len(self.results)} trades exitosos")
        return True
    
    def analyze_results(self) -> Dict:
        """Analizar resultados del backtest"""
        if not self.results:
            print("❌ No hay resultados para analizar")
            return {}
        
        completed_trades = [r for r in self.results if r['status'] == 'completed']
        
        if not completed_trades:
            print("❌ No hay trades completados para analizar")
            return {}
        
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
            'strategy_name': self.strategy_name,
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
            'avg_pnl_pct': np.mean(pnl_pcts),
            'sharpe_ratio': np.mean(pnl_pcts) / np.std(pnl_pcts) if np.std(pnl_pcts) > 0 else 0,
            'long_trades': len(long_trades),
            'short_trades': len(short_trades),
            'avg_hold_time': np.mean([t['hold_minutes'] for t in completed_trades]),
            'completed_trades': completed_trades
        }
        
        return stats
    
    def print_performance_report(self, stats: Dict):
        """Imprimir reporte de rendimiento detallado"""
        
        print(f"\n📊 REPORTE DE RENDIMIENTO - {stats['strategy_name']}")
        print("=" * 70)
        
        print(f"📈 ESTADÍSTICAS GENERALES:")
        print(f"   Estrategia: {stats['strategy_name']}")
        print(f"   Total trades: {stats['total_trades']}")
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
        
        # Análisis de edge mejorado
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
    """Interfaz principal mejorada"""
    
    print("🎯 REAL STRATEGY BACKTESTER")
    print("=" * 60)
    print("Backtester con estrategias reales del sistema de trading")
    print()
    
    # Verificar datos sintéticos
    synthetic_dir = 'synthetic_data'
    if not os.path.exists(synthetic_dir):
        print(f"❌ Directorio no encontrado: {synthetic_dir}")
        print("💡 Ejecuta primero extract_full_trading_days.py")
        return
    
    # Crear backtester
    backtester = RealStrategyBacktester(synthetic_dir)
    
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
        print("1. Backtest rápido (primeros 20 eventos)")
        print("2. Backtest medio (50 eventos)")
        print("3. Backtest completo (todos los eventos)")
        print("4. Backtest personalizado")
        
        choice = input("\n🎯 Selecciona opción (1-4): ").strip()
        
        max_events = 20
        start_idx = 0
        
        if choice == "1":
            max_events = 20
            print(f"\n🚀 Ejecutando backtest rápido ({max_events} eventos)...")
        elif choice == "2":
            max_events = 50
            print(f"\n🚀 Ejecutando backtest medio ({max_events} eventos)...")
        elif choice == "3":
            max_events = None
            print(f"\n🚀 Ejecutando backtest completo (todos los eventos)...")
        elif choice == "4":
            max_events = int(input("Número de eventos a testear: "))
            start_idx = int(input("Índice inicial (0 por defecto): ") or "0")
            print(f"\n🚀 Ejecutando backtest personalizado ({max_events} eventos desde {start_idx})...")
        else:
            max_events = 20
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
            
            # Preguntar si mostrar gráficos
            show_charts = input("\n📈 ¿Mostrar gráficos de rendimiento? (y/n): ").strip().lower()
            if show_charts == 'y':
                try:
                    # Crear gráficos básicos
                    create_performance_charts(stats)
                except Exception as e:
                    print(f"⚠️ Error creando gráficos: {e}")
        
    except KeyboardInterrupt:
        print("\n👋 Backtest cancelado")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def create_performance_charts(stats: Dict):
    """Crear gráficos de rendimiento"""
    completed_trades = stats['completed_trades']
    if not completed_trades:
        return
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    
    # 1. Equity curve
    pnls = [t['pnl_dollar'] for t in completed_trades]
    cumulative_pnl = np.cumsum(pnls)
    
    ax1.plot(cumulative_pnl, linewidth=2, color='blue')
    ax1.axhline(y=0, color='red', linestyle='--', alpha=0.7)
    ax1.set_title(f'Curva de Equity - {stats["strategy_name"]}', fontweight='bold')
    ax1.set_ylabel('P&L Acumulado ($)')
    ax1.grid(True, alpha=0.3)
    
    # 2. Distribution of returns
    pnl_pcts = [t['pnl_pct'] for t in completed_trades]
    ax2.hist(pnl_pcts, bins=15, alpha=0.7, color='green', edgecolor='black')
    ax2.axvline(x=0, color='red', linestyle='--', alpha=0.7)
    ax2.set_title('Distribución de Retornos', fontweight='bold')
    ax2.set_xlabel('Retorno (%)')
    ax2.set_ylabel('Frecuencia')
    
    # 3. Win/Loss pie chart
    win_loss = ['Win' if t['pnl_dollar'] > 0 else 'Loss' for t in completed_trades]
    win_loss_counts = pd.Series(win_loss).value_counts()
    
    colors = ['green' if label == 'Win' else 'red' for label in win_loss_counts.index]
    ax3.pie(win_loss_counts.values, labels=win_loss_counts.index, autopct='%1.1f%%',
            colors=colors, startangle=90)
    ax3.set_title('Win/Loss Ratio', fontweight='bold')
    
    # 4. P&L por trade
    trade_nums = list(range(1, len(pnls) + 1))
    colors = ['green' if pnl > 0 else 'red' for pnl in pnls]
    ax4.bar(trade_nums, pnls, color=colors, alpha=0.7)
    ax4.axhline(y=0, color='black', linestyle='-', alpha=0.7)
    ax4.set_title('P&L por Trade', fontweight='bold')
    ax4.set_xlabel('Número de Trade')
    ax4.set_ylabel('P&L ($)')
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    asyncio.run(main())