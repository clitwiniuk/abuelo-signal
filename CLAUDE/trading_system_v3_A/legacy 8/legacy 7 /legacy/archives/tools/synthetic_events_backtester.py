#!/usr/bin/env python3
"""
Synthetic Events Backtester
===========================

Backtester especializado para eventos sintéticos extraídos de la base de datos.
Utiliza events_metadata.csv como guía para saber cuándo ocurrió cada evento
y ejecuta backtests masivos sobre múltiples días de trading reales.

Características:
- Lee events_metadata.csv para obtener timing exacto de eventos
- Carga CSVs individuales de synthetic_data/
- Usa datos ANTES del evento para calcular indicadores
- Permite entrada en operativa DESPUÉS del evento
- Ejecuta backtests masivos para detectar edge real
- Estadísticas completas de rendimiento
"""

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class SyntheticEventsBacktester:
    """Backtester para eventos sintéticos con timing real"""
    
    def __init__(self, synthetic_data_dir: str = 'synthetic_data'):
        self.synthetic_data_dir = synthetic_data_dir
        self.metadata_path = os.path.join(synthetic_data_dir, 'events_metadata.csv')
        self.events_metadata = None
        self.results = []
        
        # Configuración de backtesting
        self.config = {
            'initial_capital': 10000,
            'position_size': 0.1,  # 10% del capital por operación
            'stop_loss_pct': 0.05,  # 5% stop loss
            'take_profit_pct': 0.10,  # 10% take profit
            'max_hold_minutes': 60,  # Máximo 1 hora holding
            'min_bars_before_event': 20,  # Mínimo barras antes del evento para indicadores
            'entry_delay_minutes': 1,   # Esperar 1 minuto después del evento para entrar
        }
    
    def load_events_metadata(self) -> bool:
        """
        Cargar archivo de metadatos con información de eventos
        
        Returns:
            True si se cargó correctamente
        """
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
        """
        Cargar datos de un evento específico
        
        Args:
            csv_filename: Nombre del archivo CSV (ej: AAAA.csv)
            
        Returns:
            DataFrame con datos OHLCV o None si hay error
        """
        try:
            csv_path = os.path.join(self.synthetic_data_dir, csv_filename)
            
            if not os.path.exists(csv_path):
                print(f"⚠️ Archivo no encontrado: {csv_filename}")
                return None
            
            # Cargar datos
            df = pd.read_csv(csv_path)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
            # Renombrar columnas para consistencia
            df.columns = ['open', 'high', 'low', 'close', 'volume']
            
            return df
            
        except Exception as e:
            print(f"❌ Error cargando {csv_filename}: {e}")
            return None
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcular indicadores técnicos usando datos previos al evento
        
        Args:
            df: DataFrame con datos OHLCV
            
        Returns:
            DataFrame con indicadores añadidos
        """
        df = df.copy()
        
        # RSI (14 períodos)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Medias móviles
        df['sma_5'] = df['close'].rolling(window=5).mean()
        df['sma_10'] = df['close'].rolling(window=10).mean()
        df['sma_20'] = df['close'].rolling(window=20).mean()
        
        # MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # Bandas de Bollinger
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        return df
    
    def find_event_position_in_data(self, df: pd.DataFrame, event_timestamp: datetime) -> Optional[int]:
        """
        Encontrar la posición del evento en los datos
        
        Args:
            df: DataFrame con datos
            event_timestamp: Timestamp del evento
            
        Returns:
            Índice de la posición del evento o None
        """
        try:
            # Buscar el timestamp más cercano al evento
            time_diff = abs(df.index - event_timestamp)
            
            # Encontrar el índice con la menor diferencia de tiempo
            min_diff_idx = time_diff.argmin()
            closest_idx = df.index[min_diff_idx]
            
            # Obtener la posición numérica
            position = df.index.get_loc(closest_idx)
            
            return position
            
        except Exception as e:
            print(f"⚠️ Error encontrando posición del evento: {e}")
            return None
    
    def simple_momentum_strategy(self, df: pd.DataFrame, event_position: int, 
                                event_metadata: Dict) -> Dict:
        """
        Estrategia simple de momentum post-evento
        
        Args:
            df: DataFrame con datos y indicadores
            event_position: Posición del evento en los datos
            event_metadata: Metadatos del evento
            
        Returns:
            Diccionario con resultado de la operación
        """
        try:
            # Verificar que tenemos suficientes datos antes del evento
            if event_position < self.config['min_bars_before_event']:
                return {'status': 'insufficient_data', 'pnl': 0, 'reason': 'Not enough bars before event'}
            
            # Calcular posición de entrada (después del evento)
            entry_delay = self.config['entry_delay_minutes']
            entry_position = event_position + entry_delay
            
            if entry_position >= len(df):
                return {'status': 'no_entry', 'pnl': 0, 'reason': 'Not enough data after event'}
            
            # Datos en el momento de entrada
            entry_bar = df.iloc[entry_position]
            entry_price = entry_bar['close']
            entry_time = df.index[entry_position]
            
            # Análisis de indicadores PRE-evento para la decisión
            pre_event_bar = df.iloc[event_position - 1]
            
            # Condiciones de entrada (usando datos pre-evento)
            rsi_oversold = pre_event_bar['rsi'] < 30
            rsi_overbought = pre_event_bar['rsi'] > 70
            price_above_sma = pre_event_bar['close'] > pre_event_bar['sma_20']
            volume_spike = event_metadata['ratio_vol'] > 5.0
            macd_bullish = pre_event_bar['macd'] > pre_event_bar['macd_signal']
            
            # Decidir dirección
            bullish_signals = sum([rsi_oversold, price_above_sma, volume_spike, macd_bullish])
            bearish_signals = sum([rsi_overbought, not price_above_sma, not macd_bullish])
            
            if bullish_signals > bearish_signals:
                direction = 'long'
            elif bearish_signals > bullish_signals:
                direction = 'short'
            else:
                return {'status': 'no_signal', 'pnl': 0, 'reason': 'No clear signal'}
            
            # Calcular stop loss y take profit
            if direction == 'long':
                stop_loss = entry_price * (1 - self.config['stop_loss_pct'])
                take_profit = entry_price * (1 + self.config['take_profit_pct'])
            else:
                stop_loss = entry_price * (1 + self.config['stop_loss_pct'])
                take_profit = entry_price * (1 - self.config['take_profit_pct'])
            
            # Simular holding hasta salida
            max_hold_position = min(entry_position + self.config['max_hold_minutes'], len(df) - 1)
            
            for i in range(entry_position + 1, max_hold_position + 1):
                current_bar = df.iloc[i]
                current_price = current_bar['close']
                current_time = df.index[i]
                
                # Verificar stop loss y take profit
                if direction == 'long':
                    if current_price <= stop_loss:
                        exit_price = stop_loss
                        exit_reason = 'stop_loss'
                        break
                    elif current_price >= take_profit:
                        exit_price = take_profit
                        exit_reason = 'take_profit'
                        break
                else:  # short
                    if current_price >= stop_loss:
                        exit_price = stop_loss
                        exit_reason = 'stop_loss'
                        break
                    elif current_price <= take_profit:
                        exit_price = take_profit
                        exit_reason = 'take_profit'
                        break
            else:
                # Max hold time reached
                exit_price = df.iloc[max_hold_position]['close']
                exit_reason = 'max_hold_time'
                current_time = df.index[max_hold_position]
            
            # Calcular P&L
            if direction == 'long':
                pnl_pct = (exit_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - exit_price) / entry_price
            
            pnl_dollar = self.config['initial_capital'] * self.config['position_size'] * pnl_pct
            
            return {
                'status': 'completed',
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'entry_time': entry_time,
                'exit_time': current_time,
                'pnl_pct': pnl_pct * 100,
                'pnl_dollar': pnl_dollar,
                'exit_reason': exit_reason,
                'hold_minutes': (current_time - entry_time).total_seconds() / 60,
                'signals': {
                    'rsi': pre_event_bar['rsi'],
                    'price_above_sma': price_above_sma,
                    'volume_ratio': event_metadata['ratio_vol'],
                    'macd_bullish': macd_bullish,
                    'bullish_signals': bullish_signals,
                    'bearish_signals': bearish_signals
                }
            }
            
        except Exception as e:
            return {'status': 'error', 'pnl': 0, 'reason': str(e)}
    
    def run_backtest_on_event(self, event_idx: int) -> Optional[Dict]:
        """
        Ejecutar backtest en un evento específico
        
        Args:
            event_idx: Índice del evento en metadata
            
        Returns:
            Resultado del backtest o None
        """
        try:
            # Obtener metadatos del evento
            event_meta = self.events_metadata.iloc[event_idx]
            csv_filename = event_meta['csv_file']
            event_timestamp = event_meta['event_timestamp']
            
            print(f"📊 Backtesting {csv_filename} | {event_meta['original_ticker']} | {event_meta['ratio_vol']:.1f}x")
            
            # Cargar datos del evento
            df = self.load_event_data(csv_filename)
            if df is None:
                return None
            
            # Calcular indicadores técnicos
            df = self.calculate_technical_indicators(df)
            
            # Encontrar posición del evento en los datos
            event_position = self.find_event_position_in_data(df, event_timestamp)
            if event_position is None:
                return None
            
            # Ejecutar estrategia
            trade_result = self.simple_momentum_strategy(df, event_position, event_meta.to_dict())
            
            # Añadir metadatos del evento al resultado
            trade_result.update({
                'event_idx': event_idx,
                'csv_file': csv_filename,
                'original_ticker': event_meta['original_ticker'],
                'event_timestamp': event_timestamp,
                'ratio_vol': event_meta['ratio_vol'],
                'percent_var': event_meta['percent_var'],
                'total_bars': event_meta['total_bars']
            })
            
            return trade_result
            
        except Exception as e:
            print(f"❌ Error en backtest del evento {event_idx}: {e}")
            return None
    
    def run_mass_backtest(self, max_events: int = None, start_idx: int = 0) -> bool:
        """
        Ejecutar backtest masivo sobre múltiples eventos
        
        Args:
            max_events: Máximo número de eventos a testear
            start_idx: Índice inicial
            
        Returns:
            True si se completó exitosamente
        """
        if self.events_metadata is None:
            print("❌ Primero debes cargar los metadatos")
            return False
        
        total_events = len(self.events_metadata)
        if max_events is None:
            max_events = total_events
        
        end_idx = min(start_idx + max_events, total_events)
        
        print(f"\n🚀 INICIANDO BACKTEST MASIVO")
        print("=" * 50)
        print(f"📊 Eventos a testear: {end_idx - start_idx} (de {start_idx} a {end_idx-1})")
        print(f"💰 Capital inicial: ${self.config['initial_capital']:,}")
        print(f"📈 Tamaño de posición: {self.config['position_size']*100:.1f}%")
        
        self.results = []
        successful_trades = 0
        
        for i in range(start_idx, end_idx):
            result = self.run_backtest_on_event(i)
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
        """
        Analizar resultados del backtest masivo
        
        Returns:
            Diccionario con estadísticas de rendimiento
        """
        if not self.results:
            print("❌ No hay resultados para analizar")
            return {}
        
        # Filtrar solo trades completados
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
        
        stats = {
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
            'completed_trades': completed_trades
        }
        
        return stats
    
    def print_performance_report(self, stats: Dict):
        """Imprimir reporte de rendimiento"""
        
        print(f"\n📊 REPORTE DE RENDIMIENTO")
        print("=" * 60)
        
        print(f"📈 ESTADÍSTICAS GENERALES:")
        print(f"   Total trades: {stats['total_trades']}")
        print(f"   Trades ganadores: {stats['winning_trades']}")
        print(f"   Trades perdedores: {stats['losing_trades']}")
        print(f"   Win rate: {stats['win_rate']:.1f}%")
        
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
        
        # Análisis de edge
        print(f"\n🎯 ANÁLISIS DE EDGE:")
        if stats['total_return_pct'] > 0 and stats['win_rate'] > 50:
            print("   ✅ EDGE DETECTADO: Estrategia rentable")
        elif stats['total_return_pct'] > 0:
            print("   ⚠️ EDGE MARGINAL: Rentable pero win rate bajo")
        else:
            print("   ❌ SIN EDGE: Estrategia no rentable")
        
        print("=" * 60)
    
    def create_performance_charts(self, stats: Dict):
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
        ax1.set_title('Curva de Equity', fontweight='bold')
        ax1.set_ylabel('P&L Acumulado ($)')
        ax1.grid(True, alpha=0.3)
        
        # 2. Distribution of returns
        pnl_pcts = [t['pnl_pct'] for t in completed_trades]
        ax2.hist(pnl_pcts, bins=20, alpha=0.7, color='green', edgecolor='black')
        ax2.axvline(x=0, color='red', linestyle='--', alpha=0.7)
        ax2.set_title('Distribución de Retornos', fontweight='bold')
        ax2.set_xlabel('Retorno (%)')
        ax2.set_ylabel('Frecuencia')
        
        # 3. Win/Loss analysis
        directions = [t['direction'] for t in completed_trades]
        win_loss = ['Win' if t['pnl_dollar'] > 0 else 'Loss' for t in completed_trades]
        
        win_loss_counts = pd.Series(win_loss).value_counts()
        ax3.pie(win_loss_counts.values, labels=win_loss_counts.index, autopct='%1.1f%%',
                colors=['green', 'red'], startangle=90)
        ax3.set_title('Win/Loss Ratio', fontweight='bold')
        
        # 4. P&L by trade
        trade_nums = list(range(1, len(pnls) + 1))
        colors = ['green' if pnl > 0 else 'red' for pnl in pnls]
        ax4.bar(trade_nums, pnls, color=colors, alpha=0.7)
        ax4.axhline(y=0, color='black', linestyle='-', alpha=0.7)
        ax4.set_title('P&L por Trade', fontweight='bold')
        ax4.set_xlabel('Número de Trade')
        ax4.set_ylabel('P&L ($)')
        
        plt.tight_layout()
        plt.show()


def main():
    """Interfaz principal"""
    
    print("🎯 SYNTHETIC EVENTS BACKTESTER")
    print("=" * 50)
    print("Backtester para eventos sintéticos con timing real")
    print()
    
    # Verificar que existe el directorio synthetic_data
    synthetic_dir = 'synthetic_data'
    if not os.path.exists(synthetic_dir):
        print(f"❌ Directorio no encontrado: {synthetic_dir}")
        print("💡 Ejecuta primero extract_full_trading_days.py")
        return
    
    # Crear backtester
    backtester = SyntheticEventsBacktester(synthetic_dir)
    
    # Cargar metadatos
    if not backtester.load_events_metadata():
        return
    
    # Configuración de backtesting
    print(f"\n⚙️ CONFIGURACIÓN DE BACKTESTING:")
    print(f"   💰 Capital inicial: ${backtester.config['initial_capital']:,}")
    print(f"   📊 Tamaño posición: {backtester.config['position_size']*100:.0f}%")
    print(f"   🛑 Stop loss: {backtester.config['stop_loss_pct']*100:.0f}%")
    print(f"   🎯 Take profit: {backtester.config['take_profit_pct']*100:.0f}%")
    print(f"   ⏱️ Max holding: {backtester.config['max_hold_minutes']} min")
    print(f"   🕐 Delay entrada: {backtester.config['entry_delay_minutes']} min post-evento")
    
    # Opciones de ejecución
    print(f"\n🚀 OPCIONES DE EJECUCIÓN:")
    print("1. Backtest rápido (primeros 20 eventos)")
    print("2. Backtest completo (todos los eventos)")
    print("3. Backtest personalizado")
    
    try:
        choice = input("\n🎯 Selecciona opción (1-3): ").strip()
        
        if choice == "1":
            max_events = 20
            print(f"\n🚀 Ejecutando backtest rápido ({max_events} eventos)...")
            
        elif choice == "2":
            max_events = None
            print(f"\n🚀 Ejecutando backtest completo...")
            
        elif choice == "3":
            max_events = int(input("Número de eventos a testear: "))
            start_idx = int(input("Índice inicial (0 por defecto): ") or "0")
            print(f"\n🚀 Ejecutando backtest personalizado ({max_events} eventos desde {start_idx})...")
            
        else:
            max_events = 20
            start_idx = 0
        
        if choice != "3":
            start_idx = 0
        
        # Ejecutar backtest masivo
        success = backtester.run_mass_backtest(max_events, start_idx)
        
        if success and backtester.results:
            # Analizar resultados
            stats = backtester.analyze_results()
            
            # Mostrar reporte
            backtester.print_performance_report(stats)
            
            # Preguntar si mostrar gráficos
            show_charts = input("\n📈 ¿Mostrar gráficos de rendimiento? (y/n): ").strip().lower()
            if show_charts == 'y':
                backtester.create_performance_charts(stats)
        
    except KeyboardInterrupt:
        print("\n👋 Backtest cancelado")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()